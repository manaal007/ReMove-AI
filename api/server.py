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
  POST /api/sessions/{id}/advice            {"pain": 0-10} -> weight guidance for the next session
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
from capture.weight_check import has_weight_check
from feedback.messages import LANGS, get_feedback
from session.config import load_config
from session.weight_advice import advise, set_facts
from feedback.messages import AUDIO_DIR
from session.config import CONFIG_DIR
from storage.db.store import Store

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"
log = logging.getLogger("remove.api")


def default_detector():
    from api.pose_detector import PoseDetector   # imported late: tests don't need MediaPipe
    return PoseDetector()


def default_bottle_detector(cfg):
    """Bottle detector for the weight check, or None (check skipped) if the model is missing."""
    from api.object_detector import BottleDetector
    try:
        return BottleDetector(cfg["weight_check"]["model"])
    except FileNotFoundError as e:
        log.warning("weight check off: %s", e)
        return None


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


async def session_advice(request):
    """Weight guidance after a set: pain is asked on the summary page, the rest is in the saved log."""
    store = request.app.state.store
    sid = request.path_params["sid"]
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = {}
    pain = data.get("pain")
    s = store.get_session(sid)
    if s is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    cfg = load_config(s["exercise"])
    if not has_weight_check(cfg["exercise"]):
        return JSONResponse({"error": "no weight guidance for this exercise"}, status_code=400)
    if s["weight"] is None:
        return JSONResponse({"error": "the weight of this session is not known"}, status_code=400)
    patient = store.get_patient(s["patient_id"]) if s["patient_id"] is not None else None
    try:
        advice = advise(set_facts(s["log"] or {}), pain if not isinstance(pain, bool) else None, s["weight"],
                        (patient or {}).get("max_weight"), store.no_weight_rom(s["patient_id"], s["exercise"]), cfg)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    store.save_advice(sid, pain, advice)
    prompts = []
    for key in advice["phrases"]:
        en, _ = get_feedback(key, "en")
        ur, _ = get_feedback(key, "ur")
        prompts.append({"key": key, "en": en, "ur": ur, "reason": "advice",
                        "audio": {lang: f"/audio/{lang}_{key}.mp3" for lang in LANGS},
                        "tag": "adjust" if key in ("talk_to_physio",) or advice["action"] == "down" else "good"})
    return JSONResponse({"advice": advice, "prompts": prompts})


# ---------------------------------------------------------------- live session

async def ws_session(ws: WebSocket):
    await ws.accept()
    live = LiveSession(ws.app.state.detector_factory, store=ws.app.state.store,
                       bottle_factory=ws.app.state.bottle_factory)
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
                    elif kind == "weight":
                        out = live.choose_weight(data.get("choice"))
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


def create_app(store=None, detector_factory=default_detector, bottle_factory=default_bottle_detector, cors_origins=("http://localhost:5173", "http://127.0.0.1:5173")):
    routes = [
        Route("/api/health", health),
        Route("/api/exercises", exercises),
        Route("/api/patients", add_patient, methods=["POST"]),
        Route("/api/patients/{pid:int}", get_patient),
        Route("/api/patients/{pid:int}/sessions", patient_sessions),
        Route("/api/patients/{pid:int}/baseline", patient_baseline),
        Route("/api/sessions/{sid:int}/advice", session_advice, methods=["POST"]),
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
    app.state.bottle_factory = bottle_factory
    return app


app = create_app()
