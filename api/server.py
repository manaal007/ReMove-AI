"""
ReMove PK web server: the browser app talks to the existing SessionEngine.

Run from inside the repo, with .venv active:
    uvicorn api.server:app --port 8000            # API only (frontend: cd web && npm run dev)
    uvicorn api.server:app --port 8000 --host 0.0.0.0
After `cd web && npm run build`, the same server also serves the app at http://localhost:8000

Routes
  GET  /api/health
  GET  /api/exercises                       exercises from config/exercises.yaml
  POST /api/patients                        health form -> {"id": ...}
  GET  /api/patients/{id}                   one patient
  GET  /api/patients/{id}/sessions?exercise=E1
  GET  /api/patients/{id}/baseline?exercise=E1   last baseline (to skip calibration)
  WS   /ws/session                          live session, protocol in api/live.py
  GET  /audio/{lang}_{phrase}.mp3           feedback clips from assets/audio

Built with Starlette (the base FastAPI runs on), so it needs only
starlette + uvicorn[standard].
"""
import json
import logging
from pathlib import Path

import yaml
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from api.live import LiveSession, exercise_info
from feedback.messages import AUDIO_DIR
from session.config import CONFIG_DIR
from storage.db.store import Store

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"
log = logging.getLogger("remove.api")


def default_detector():
    from api.pose_detector import PoseDetector   # imported late: tests don't need MediaPipe
    return PoseDetector()


def list_exercises():
    with open(Path(CONFIG_DIR) / "exercises.yaml", encoding="utf-8") as f:
        ids = list(yaml.safe_load(f))
    return [exercise_info(i) for i in ids]


# ---------------------------------------------------------------- REST

async def health(request):
    return JSONResponse({"ok": True})


async def exercises(request):
    return JSONResponse(list_exercises())


async def add_patient(request):
    try:
        data = await request.json()
        pid = request.app.state.store.add_patient(data)
    except (ValueError, json.JSONDecodeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"id": pid}, status_code=201)


async def get_patient(request):
    p = request.app.state.store.get_patient(request.path_params["pid"])
    return JSONResponse(p) if p else JSONResponse({"error": "not found"}, status_code=404)


async def patient_sessions(request):
    pid = request.path_params["pid"]
    ex = request.query_params.get("exercise")
    return JSONResponse(request.app.state.store.list_sessions(pid, ex))


async def patient_baseline(request):
    pid = request.path_params["pid"]
    ex = request.query_params.get("exercise", "E1")
    return JSONResponse({"baseline": request.app.state.store.latest_baseline(pid, ex)})


# ---------------------------------------------------------------- live session

async def ws_session(ws: WebSocket):
    await ws.accept()
    live = LiveSession(ws.app.state.detector_factory, store=ws.app.state.store)
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            try:
                if msg.get("bytes") is not None:
                    out = await run_in_threadpool(live.frame, msg["bytes"])
                else:
                    data = json.loads(msg.get("text") or "{}")
                    kind = data.get("type")
                    if kind == "start":
                        out = await run_in_threadpool(live.start, data)
                    elif kind == "stop":
                        out = live.stop(data.get("reason", "user_stopped"))
                    else:
                        out = [{"type": "error", "message": f"unknown message type {kind!r}"}]
            except (ValueError, KeyError, RuntimeError) as e:
                out = [{"type": "error", "message": str(e)}]
            for o in out:
                await ws.send_json(o)
    except WebSocketDisconnect:
        pass
    finally:
        if not live.finished and live.engine is not None:
            live.stop("disconnected")          # still saves the log
        live.close()


# ---------------------------------------------------------------- built frontend (optional)

async def spa(request):
    """Serve web/dist; unknown paths get index.html so /session etc. work on refresh."""
    rel = request.path_params.get("path", "")
    f = (WEB_DIST / rel).resolve()
    if rel and f.is_file() and WEB_DIST.resolve() in f.parents:
        return FileResponse(f)
    return FileResponse(WEB_DIST / "index.html")


def create_app(store=None, detector_factory=default_detector, cors_origins=("http://localhost:5173", "http://127.0.0.1:5173")):
    routes = [
        Route("/api/health", health),
        Route("/api/exercises", exercises),
        Route("/api/patients", add_patient, methods=["POST"]),
        Route("/api/patients/{pid:int}", get_patient),
        Route("/api/patients/{pid:int}/sessions", patient_sessions),
        Route("/api/patients/{pid:int}/baseline", patient_baseline),
        WebSocketRoute("/ws/session", ws_session),
        Mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio"),
    ]
    if (WEB_DIST / "index.html").exists():
        routes += [Route("/", spa), Route("/{path:path}", spa)]
    app = Starlette(routes=routes, middleware=[
        Middleware(CORSMiddleware, allow_origins=list(cors_origins), allow_methods=["*"], allow_headers=["*"]),
    ])
    app.state.store = store if store is not None else Store()
    app.state.detector_factory = detector_factory
    return app


app = create_app()
