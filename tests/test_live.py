"""api/live.py, storage/db/store.py and api/server.py on synthetic frames (no camera, no MediaPipe)."""
import asyncio
import json
from collections import deque

import cv2
import numpy as np
import pytest

from api.live import LiveSession, clean_baseline
from features.signals import FPS
from storage.db.store import Store
from tests.synth import pose, rep_angles

JPEG = b"fake-jpeg"


class FakeDetector:
    """Plays back a queue of landmark dicts, ignoring the JPEG bytes."""

    def __init__(self):
        self.frames = deque()
        self.closed = False

    def detect(self, jpeg, t_ms):
        lm = self.frames.popleft() if self.frames else pose(10)
        return lm, 120.0, 100, 100

    def close(self):
        self.closed = True


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        v = self.t
        self.t += 1 / FPS
        return v


def settle_frames(n=35):
    return [pose(10) for _ in range(n)]


def rep_frames(**kw):
    return [pose(a) for a in rep_angles(**kw)]


def make(store=None):
    det = FakeDetector()
    live = LiveSession(lambda: det, store=store, clock=Clock())
    return live, det


def run(live, det, frames):
    det.frames.extend(frames)
    out = []
    for _ in range(len(frames)):
        out += live.frame(JPEG)
    return out


def of_type(msgs, kind):
    return [m for m in msgs if m["type"] == kind]


def calibrate(store=None):
    live, det = make(store)
    ready = live.start({"type": "start", "mode": "calibration", "exercise": "E1", "lang": "en"})
    frames = settle_frames()
    for _ in range(3):
        frames += rep_frames(duration_s=3.0, high=90)
    out = run(live, det, frames)
    return live, det, ready, out


def test_calibration_sends_baseline_then_stops():
    live, det, ready, out = calibrate()
    assert ready[0]["type"] == "ready" and ready[0]["exercise"]["id"] == "E1"
    frames = of_type(out, "frame")
    assert frames[0]["points"]["shoulder"] and frames[0]["status"]["checking"]
    prompts = [p["key"] for f in frames for p in f["prompts"]]
    assert prompts[0] == "start"
    start = next(p for f in frames for p in f["prompts"] if p["key"] == "start")
    assert start["audio"] == {"ur": "/audio/ur_start.mp3", "en": "/audio/en_start.mp3"}
    assert start["ur"] and start["en"]
    reps = [r for f in frames for r in f["reps"]]
    assert [r["phase"] for r in reps] == ["baseline"] * 3
    assert all(r["used_for_baseline"] and 70 < r["peak"] <= 92 for r in reps)
    base = of_type(out, "baseline")
    assert len(base) == 1 and base[0]["baseline"]["rom"] > 60
    done = of_type(out, "done")
    assert len(done) == 1 and done[0]["summary"]["ended_reason"] == "calibration_done"
    assert live.finished
    # frames after the end are answered (keeps the browser's send loop simple) but do nothing
    assert live.frame(JPEG)[0]["status"]["phase"] == "done"


def test_session_with_baseline_scores_every_rep_and_saves():
    store = Store(":memory:")
    pid = store.add_patient({"name": "Test Patient", "age": "58", "side": "right", "pain": 2,
                             "conditions": ["bp"], "doctorOk": True})
    _, _, _, cal = calibrate()
    baseline = of_type(cal, "baseline")[0]["baseline"]
    baseline = json.loads(json.dumps(baseline))          # as it comes back from the browser

    live, det = make(store)
    live.start({"type": "start", "mode": "session", "exercise": "E1", "lang": "ur",
                "baseline": baseline, "patient_id": pid})
    frames = settle_frames()
    for i in range(10):
        frames += rep_frames(duration_s=3.0, high=90 if i % 2 == 0 else 45)
    out = run(live, det, frames)

    reps = [r for f in of_type(out, "frame") for r in f["reps"]]
    assert len(reps) == 10 and all(r["phase"] == "scoring" for r in reps)
    assert {r["label"] for r in reps[1::2]} == {"reduced_range"}
    assert reps[0]["label"] == "good" and reps[0]["tag"] == "good"
    done = of_type(out, "done")[0]["summary"]
    assert done["ended_reason"] == "set_done" and done["scored_reps"] == 10 and done["good_reps"] == 5
    assert done["avg_peak"] is not None and done["session_id"] == 1
    hist = store.list_sessions(pid, "E1")
    assert len(hist) == 1 and hist[0]["scored_reps"] == 10
    assert store.latest_baseline(pid, "E1")["rom"] == pytest.approx(baseline["rom"])
    assert store.get_patient(pid)["conditions"] == ["bp"]


def test_stop_midway_saves_partial_session():
    store = Store(":memory:")
    live, det = make(store)
    live.start({"type": "start", "mode": "session", "exercise": "E1", "lang": "en"})
    run(live, det, settle_frames() + rep_frames(duration_s=3.0))
    out = live.stop("user_stopped")
    assert out[0]["summary"]["ended_reason"] == "user_stopped"
    assert live.stop() == []
    assert out[0]["summary"]["session_id"] == 1             # saved even without a patient id


def test_bad_baseline_is_ignored():
    assert clean_baseline({"rom": 70, "duration_s": None}) is None
    assert clean_baseline("nope") is None
    b = clean_baseline({"rom": 70, "duration_s": 3, "peak_angle": 85, "min_angle": 12, "sparc": None})
    assert b["sparc"] is None and b["rom"] == 70.0


def test_start_errors():
    live, _ = make()
    with pytest.raises(RuntimeError):
        live.frame(JPEG)
    with pytest.raises(ValueError):
        live.start({"mode": "warmup"})
    with pytest.raises(ValueError):
        live.start({"lang": "fr"})
    with pytest.raises(KeyError):
        live.start({"exercise": "E9"})


def test_store_rejects_empty_name():
    with pytest.raises(ValueError):
        Store(":memory:").add_patient({"name": "  "})


# ---------------------------------------------------------------- server, through raw ASGI calls

def _app(det):
    from api.server import create_app
    return create_app(store=Store(":memory:"), detector_factory=lambda: det)


async def _http(app, method, path, body=None):
    msgs = [{"type": "http.request", "body": json.dumps(body).encode() if body is not None else b"", "more_body": False}]
    sent = []
    path, _, query = path.partition("?")
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
             "query_string": query.encode(), "headers": [(b"content-type", b"application/json")],
             "client": ("test", 1), "server": ("test", 80)}

    async def receive():
        return msgs.pop(0) if msgs else {"type": "http.disconnect"}

    async def send(m):
        sent.append(m)

    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


async def _ws(app, inbound):
    """Send inbound messages one by one, collecting every JSON reply."""
    inq, replies = asyncio.Queue(), []
    await inq.put({"type": "websocket.connect"})
    for m in inbound:
        await inq.put(m)
    await inq.put({"type": "websocket.disconnect", "code": 1000})
    scope = {"type": "websocket", "asgi": {"version": "3.0"}, "path": "/ws/session", "raw_path": b"/ws/session",
             "root_path": "", "query_string": b"", "headers": [], "client": ("test", 1), "server": ("test", 80),
             "subprotocols": [], "scheme": "ws"}

    async def send(m):
        if m["type"] == "websocket.send":
            replies.append(json.loads(m["text"]))

    await app(scope, inq.get, send)
    return replies


def test_server_rest_routes():
    app = _app(FakeDetector())

    async def go():
        s, b = await _http(app, "GET", "/api/exercises")
        assert s == 200 and [e["id"] for e in json.loads(b)] == ["E1", "E2"]
        s, b = await _http(app, "POST", "/api/patients", {"name": "Aslam", "age": 58, "side": "right"})
        assert s == 201
        pid = json.loads(b)["id"]
        s, b = await _http(app, "GET", f"/api/patients/{pid}")
        assert s == 200 and json.loads(b)["name"] == "Aslam"
        s, _ = await _http(app, "POST", "/api/patients", {"name": ""})
        assert s == 400
        s, b = await _http(app, "GET", f"/api/patients/{pid}/sessions?exercise=E1")
        assert s == 200
        s, _ = await _http(app, "GET", "/audio/ur_good.mp3")
        assert s == 200
    asyncio.run(go())


def test_server_websocket_round_trip():
    det = FakeDetector()
    app = _app(det)
    inbound = [{"type": "websocket.receive", "text": json.dumps({"type": "hello"})},
               {"type": "websocket.receive", "text": json.dumps({"type": "start", "mode": "session", "exercise": "E2", "lang": "en"})}]
    inbound += [{"type": "websocket.receive", "bytes": JPEG} for _ in range(5)]
    replies = asyncio.run(_ws(app, inbound))
    assert replies[0]["type"] == "error"
    assert replies[1]["type"] == "ready" and replies[1]["exercise"]["camera_view"] == "side_right"
    assert [r["type"] for r in replies[2:]] == ["frame"] * 5
    assert det.closed


def test_real_pose_detector_on_blank_frame():
    pytest.importorskip("mediapipe")
    from api.pose_detector import PoseDetector
    try:
        det = PoseDetector()
    except FileNotFoundError:
        pytest.skip("pose model not downloaded")
    ok, buf = cv2.imencode(".jpg", np.full((240, 320, 3), 128, np.uint8))
    lm, gray, W, H = det.detect(buf.tobytes(), 0)
    det.close()
    assert lm is None and (W, H) == (320, 240) and 120 < gray < 136
