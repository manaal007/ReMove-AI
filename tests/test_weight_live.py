"""Weight check in the live session (api/live.py), the server message and storage."""
import asyncio
import json
import sqlite3

import numpy as np
import pytest

from api.live import LiveSession
from capture.weight_check import Box
from features.signals import FPS
from storage.db.store import Store
from tests.synth import SIDE_H, SIDE_W, rep_angles, side_pose
from tests.test_live import JPEG, Clock, FakeDetector, _ws, of_type, run

WINDOW_FRAMES = int(4.0 * FPS) + 2          # weight_check.window_s at the fake clock's 30 fps


class FakeBottle:
    """Answers every crop with a bottle `ratio` limb lengths tall at the crop centre (the joint)."""

    def __init__(self, ratio=0.7, every=1):
        self.ratio, self.every, self.calls, self.closed = ratio, every, 0, False

    def detect(self, rgb, region):
        self.calls += 1
        if self.ratio is None or self.calls % self.every:
            return []
        x0, y0, x1, y1 = region
        limb = (x1 - x0) / 2.5                         # crop_limb_lengths
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        h = self.ratio * limb
        return [Box(cx - 0.15 * limb, cy - h / 2, 0.3 * limb, h, 0.6)]

    def close(self):
        self.closed = True


def make(bottle=None, store=None, factory=True):
    det = FakeDetector(size=(SIDE_W, SIDE_H))
    live = LiveSession(lambda: det, store=store, clock=Clock(),
                       bottle_factory=(lambda cfg: bottle) if factory else None)
    return live, det


def rest(ex_id, n, side="left"):
    return [side_pose(ex_id, 90 if ex_id == "E4" else 10, side=side) for _ in range(n)]


def reps(ex_id, k, side="left"):
    lo, hi = (90, 165) if ex_id == "E4" else (10, 120)
    out = []
    for _ in range(k):
        out += [side_pose(ex_id, a, side=side) for a in rep_angles(low=lo, high=hi)]
    return out


def test_e4_asks_before_calibration_and_saves_the_patients_choice():
    store = Store(":memory:")
    bottle = FakeBottle(ratio=0.5)                      # 0.5 shin -> light (< 0.65)
    live, det = make(bottle, store)
    ready = live.start({"type": "start", "mode": "calibration", "exercise": "E4", "lang": "en"})
    assert ready[0]["exercise"]["weight_check"] is True
    out = run(live, det, rest("E4", WINDOW_FRAMES))
    frames = of_type(out, "frame")
    assert all(f["status"]["phase"] == "weight" for f in frames)
    assert live.engine is None                          # calibration has not started
    ask = of_type(out, "weight")
    assert len(ask) == 1 and ask[0]["suggested"] == "light"
    assert ask[0]["prompt"]["en"] == "We see: a light weight. Is that right?"
    assert ask[0]["prompt"]["audio"]["ur"] == "/audio/ur_weight_ask_light.mp3"
    assert ask[0]["evidence"]["hits"] == ask[0]["evidence"]["frames"]

    more = run(live, det, rest("E4", 10))               # waiting for the answer: still no engine
    assert live.engine is None and not of_type(more, "weight")
    assert all(f["status"]["weight"] == "ask" for f in of_type(more, "frame"))

    assert live.choose_weight("heavy") == [{"type": "weight_saved", "chosen": "heavy"}]   # patient corrects us
    out = run(live, det, rest("E4", 35) + reps("E4", 3))
    assert live.engine is not None
    done = of_type(out, "done")[0]["summary"]
    assert done["ended_reason"] == "calibration_done"
    assert done["weight"]["suggested"] == "light" and done["weight"]["chosen"] == "heavy"
    row = store.db.execute("SELECT weight_suggested, weight FROM sessions").fetchone()
    assert (row["weight_suggested"], row["weight"]) == ("light", "heavy")


def test_e3_no_bottle_seen_suggests_none():
    live, det = make(FakeBottle(ratio=None))
    live.start({"type": "start", "mode": "calibration", "exercise": "E3", "lang": "ur"})
    ask = of_type(run(live, det, rest("E3", WINDOW_FRAMES)), "weight")
    assert ask[0]["suggested"] == "none" and ask[0]["prompt"]["key"] == "weight_ask_none"


def test_e3_big_bottle_is_heavy():
    live, det = make(FakeBottle(ratio=1.1))             # 1.1 forearm >= 1.0
    live.start({"type": "start", "mode": "calibration", "exercise": "E3", "lang": "en"})
    assert of_type(run(live, det, rest("E3", WINDOW_FRAMES)), "weight")[0]["suggested"] == "heavy"


def test_window_starts_when_the_limb_is_first_seen():
    live, det = make(FakeBottle())
    live.start({"type": "start", "mode": "calibration", "exercise": "E4", "lang": "en"})
    out = run(live, det, [None] * 60 + rest("E4", WINDOW_FRAMES - 5))   # 2 s nobody, then < 4 s
    assert not of_type(out, "weight")
    assert of_type(out, "frame")[0]["status"]["issue"] == "not_tracked"
    assert of_type(run(live, det, rest("E4", 10)), "weight")


def test_weight_from_calibration_skips_the_check_in_the_session():
    store = Store(":memory:")
    bottle = FakeBottle()
    live, det = make(bottle, store)
    live.start({"type": "start", "mode": "session", "exercise": "E4", "lang": "en", "weight": "light"})
    out = run(live, det, rest("E4", 40))
    assert bottle.calls == 0 and not of_type(out, "weight")
    assert of_type(out, "frame")[-1]["status"]["phase"] != "weight"
    done = live.stop()[0]["summary"]
    assert done["weight"] == {"suggested": None, "chosen": "light"}
    assert store.db.execute("SELECT weight FROM sessions").fetchone()["weight"] == "light"


def test_e1_has_no_weight_check():
    bottle = FakeBottle()
    live, det = make(bottle)
    live.start({"type": "start", "mode": "calibration", "exercise": "E1", "lang": "en"})
    det.size = (100, 100)
    out = run(live, det, [None] * 5)
    assert bottle.calls == 0 and live.weight_state is None
    assert of_type(out, "frame")[0]["status"]["phase"] == "check"


def test_no_detector_means_no_check():
    live, det = make(factory=False)
    live.start({"type": "start", "mode": "calibration", "exercise": "E3", "lang": "en"})
    assert live.weight_state is None
    live2, _ = make(bottle=None)                        # factory returned None: model missing
    live2.start({"type": "start", "mode": "calibration", "exercise": "E3", "lang": "en"})
    assert live2.weight_state is None


def test_bad_weight_values_are_refused():
    live, _ = make(FakeBottle())
    with pytest.raises(ValueError):
        live.start({"type": "start", "exercise": "E3", "weight": "medium"})
    live.start({"type": "start", "exercise": "E3"})
    with pytest.raises(ValueError):
        live.choose_weight("2kg")


def test_bottle_detector_is_closed():
    bottle = FakeBottle()
    live, _ = make(bottle)
    live.start({"type": "start", "exercise": "E3"})
    live.close()
    assert bottle.closed


def test_server_routes_the_weight_answer():
    from api.server import create_app
    det, bottle = FakeDetector(size=(SIDE_W, SIDE_H)), FakeBottle()
    app = create_app(store=Store(":memory:"), detector_factory=lambda: det, bottle_factory=lambda cfg: bottle)
    det.frames.extend(rest("E3", 5))
    inbound = [{"type": "websocket.receive", "text": json.dumps({"type": "start", "mode": "calibration", "exercise": "E3"})},
               {"type": "websocket.receive", "bytes": JPEG},
               {"type": "websocket.receive", "text": json.dumps({"type": "weight", "choice": "none"})},
               {"type": "websocket.receive", "text": json.dumps({"type": "weight", "choice": "big"})}]
    replies = asyncio.run(_ws(app, inbound))
    assert [r["type"] for r in replies] == ["ready", "frame", "weight_saved", "error"]
    assert replies[2]["chosen"] == "none"


def test_old_database_gets_the_weight_columns(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE sessions (id INTEGER PRIMARY KEY, patient_id INTEGER, exercise TEXT NOT NULL,
        mode TEXT NOT NULL, started_at TEXT, ended_at TEXT, ended_reason TEXT, scored_reps INTEGER,
        good_reps INTEGER, avg_peak REAL, baseline TEXT, log TEXT);""")
    db.close()
    s = Store(path)
    cols = {r["name"] for r in s.db.execute("PRAGMA table_info(sessions)")}
    assert {"weight_suggested", "weight"} <= cols
    summary = {"exercise": {"id": "E3"}, "mode": "session", "started_at": "t", "ended_at": "t",
               "ended_reason": "set_done", "scored_reps": 0, "good_reps": 0, "avg_peak": None, "baseline": None,
               "weight": {"suggested": "light", "chosen": "light"}}
    pid = s.add_patient({"name": "P01", "doctorOk": True, "recentInjury": False, "chestDizzy": False})
    s.save_session(pid, summary, {})
    assert s.list_sessions(pid, "E3")[0]["weight"] == "light"
    assert s.list_sessions(pid, "E3")[0]["weight_suggested"] == "light"


def test_session_without_weight_info_still_saves():
    s = Store(":memory:")
    summary = {"exercise": {"id": "E1"}, "mode": "session", "started_at": "t", "ended_at": "t",
               "ended_reason": "set_done", "scored_reps": 0, "good_reps": 0, "avg_peak": None, "baseline": None}
    s.save_session(None, summary, {})
    row = s.db.execute("SELECT weight, weight_suggested FROM sessions").fetchone()
    assert row["weight"] is None and row["weight_suggested"] is None
