"""E3/E4 use the patient's weak side (health form), not the better-seen side:
camera check, engine, weight check, live session, and our own clips."""
import os

import numpy as np
import pandas as pd
import pytest

from api.live import LiveSession
from capture.camera_check import check_frame, wrong_side_facing
from capture.weight_check import crop_region, limb_geometry
from features.signals import ALL_LM, FPS, SIDE_LM
from session.config import load_config
from session.engine import SessionEngine
from tests.synth import SIDE_H, SIDE_W, rep_angles, side_pose
from tests.test_live import Clock, FakeDetector, of_type, run
from tests.test_weight_live import WINDOW_FRAMES, FakeBottle

ASPECT = SIDE_W / SIDE_H
REST = {"E3": 10.0, "E4": 90.0}
HIGH = {"E3": 120.0, "E4": 165.0}


def facing(ex_id, side, angle=None, **kw):
    """Person with `side` towards the camera; the other side seen less well (but seen)."""
    return side_pose(ex_id, REST[ex_id] if angle is None else angle, side=side, far_vis=kw.pop("far_vis", 0.6), **kw)


# ---------------------------------------------------------------- camera check

@pytest.mark.parametrize("ex_id", ["E3", "E4"])
@pytest.mark.parametrize("side", ["left", "right"])
def test_weak_side_facing_the_camera_passes(ex_id, side):
    assert check_frame(facing(ex_id, side), 120, load_config(ex_id), aspect=ASPECT, wanted_side=side) == []


@pytest.mark.parametrize("ex_id", ["E3", "E4"])
@pytest.mark.parametrize("weak", ["left", "right"])
def test_other_side_facing_asks_to_turn(ex_id, weak):
    other = "left" if weak == "right" else "right"
    cfg = load_config(ex_id)
    assert check_frame(facing(ex_id, other), 120, cfg, aspect=ASPECT, wanted_side=weak) == [f"show_{weak}_side"]
    # without the weak side the old behaviour stays: the better-seen side is fine
    assert check_frame(facing(ex_id, other), 120, cfg, aspect=ASPECT) == []


def test_weak_side_hidden_behind_a_clearly_seen_side_asks_to_turn():
    lm = side_pose("E3", 10, side="left", far_vis=0.3)     # left faces, right hidden
    assert check_frame(lm, 120, load_config("E3"), aspect=ASPECT, wanted_side="right") == ["show_right_side"]


def test_neither_side_well_seen_is_step_back():
    lm = side_pose("E3", 10, side="left", vis=0.4, far_vis=0.3)
    assert check_frame(lm, 120, load_config("E3"), aspect=ASPECT, wanted_side="right") == ["step_back"]


def test_facing_the_camera_is_turn_sideways_not_turn_side():
    lm = side_pose("E3", 10, side="right", facing_camera=True, far_vis=0.9)
    assert check_frame(lm, 120, load_config("E3"), aspect=ASPECT, wanted_side="left") == ["turn_sideways"]


def test_wrong_side_uses_visibility_even_off_screen():
    """Seated clips: the near shoulder can be just past the frame edge but still well seen."""
    cfg = load_config("E4")
    lm = facing("E4", "right")
    lm[f"x{SIDE_LM['right']['shoulder']}"] = -0.05
    assert wrong_side_facing(lm, cfg, "left")


def test_margin_is_in_thresholds_yaml():
    assert load_config("E3")["side_view"]["wrong_side_margin"] == 0.10


def test_e1_ignores_the_weak_side():
    from tests.synth import pose
    assert check_frame(pose(10), 120, load_config("E1"), wanted_side="left") == []


# ---------------------------------------------------------------- engine

class Sim:
    def __init__(self, ex_id, side):
        self.ex_id = ex_id
        self.e = SessionEngine(load_config(ex_id), SIDE_W, SIDE_H, language="en", side=side)
        self.i, self.prompts = 0, []

    def feed(self, lm):
        self.prompts += self.e.process(self.i / FPS, lm, 120)
        self.i += 1

    def hold(self, toward, n=35):
        for _ in range(n):
            self.feed(facing(self.ex_id, toward))

    def rep(self, toward):
        for a in rep_angles(low=REST[self.ex_id], high=HIGH[self.ex_id]):
            self.feed(facing(self.ex_id, toward, angle=a))


@pytest.mark.parametrize("ex_id", ["E3", "E4"])
def test_engine_uses_the_weak_side_from_the_first_frame(ex_id):
    s = Sim(ex_id, "left")
    assert s.e.side == "left" and s.e.log.side == "left" and s.e.status()["side"] == "left"
    s.hold("left")
    assert not s.e.checking
    s.rep("left")
    assert s.e.log.reps[0]["label"] == "good" and s.e.log.side == "left"


@pytest.mark.parametrize("ex_id", ["E3", "E4"])
def test_engine_waits_and_asks_to_turn_until_the_weak_side_faces(ex_id):
    s = Sim(ex_id, "right")
    s.hold("left", n=int(2 * FPS))
    assert s.e.checking
    camera = [p for p in s.prompts if p.reason == "camera"]
    assert [p.key for p in camera] == ["show_right_side"]
    assert camera[0].text == "Please turn so your right side faces the camera."
    s.hold("right")
    assert not s.e.checking and s.e.side == "right"
    assert [p.key for p in s.prompts][-1] == "start"


def test_engine_never_switches_to_the_better_seen_side():
    s = Sim("E3", "right")
    s.hold("right")
    for _ in range(int(3 * FPS)):              # patient turns round mid-session
        s.feed(facing("E3", "left"))
    assert s.e.side == "right" and s.e.log.side == "right"


def test_engine_without_a_side_still_picks_the_better_seen_side():
    s = Sim("E4", None)
    s.hold("left")
    assert s.e.log.side == "left"


def test_bad_side_is_refused():
    with pytest.raises(ValueError):
        SessionEngine(load_config("E3"), SIDE_W, SIDE_H, side="up")


def test_e1_keeps_the_right_arm():
    e = SessionEngine(load_config("E1"), 100, 100, side="left")
    assert e.side == "right" and e.log.side == "right"


# ---------------------------------------------------------------- live session + weight check

class RegionBottle(FakeBottle):
    def __init__(self):
        super().__init__(ratio=0.7)
        self.regions = []

    def detect(self, rgb, region):
        self.regions.append(region)
        return super().detect(rgb, region)


def make(bottle):
    det = FakeDetector(size=(SIDE_W, SIDE_H))
    return LiveSession(lambda: det, clock=Clock(), bottle_factory=lambda cfg: bottle), det


@pytest.mark.parametrize("ex_id,joint", [("E3", "wrist"), ("E4", "ankle")])
def test_weight_check_looks_at_the_weak_side_joint(ex_id, joint):
    bottle = RegionBottle()
    live, det = make(bottle)
    live.start({"type": "start", "mode": "calibration", "exercise": ex_id, "side": "right"})
    lm = facing(ex_id, "right")
    run(live, det, [lm] * 5)
    cfg = load_config(ex_id)
    expected = {s: crop_region(*limb_geometry(lm, cfg["exercise"], SIDE_W, SIDE_H, side=s), SIDE_W, SIDE_H, cfg)
                for s in ("left", "right")}
    assert expected["left"] != expected["right"]
    assert set(bottle.regions) == {expected["right"]}


def test_weight_check_waits_while_the_other_side_faces():
    bottle = RegionBottle()
    live, det = make(bottle)
    live.start({"type": "start", "mode": "calibration", "exercise": "E3", "side": "right"})
    out = run(live, det, [facing("E3", "left")] * (WINDOW_FRAMES + 10))
    assert bottle.calls == 0 and not of_type(out, "weight")
    st = of_type(out, "frame")[-1]["status"]
    assert st["issue"] == "show_right_side" and st["side"] == "right"
    out = run(live, det, [facing("E3", "right")] * WINDOW_FRAMES)
    assert of_type(out, "weight")[0]["suggested"] == "light"


def test_live_session_passes_the_side_to_the_engine():
    live, det = make(None)
    live.start({"type": "start", "mode": "session", "exercise": "E4", "side": "left", "weight": "none"})
    out = run(live, det, [facing("E4", "left")] * 40)
    assert live.engine.side == "left" and of_type(out, "frame")[-1]["status"]["side"] == "left"
    pts = of_type(out, "frame")[-1]["points"]
    assert pts["knee"] == [round(facing("E4", "left")[f"x{SIDE_LM['left']['knee']}"], 4),
                           round(facing("E4", "left")[f"y{SIDE_LM['left']['knee']}"], 4)]


def test_live_session_refuses_a_bad_side():
    live, _ = make(None)
    with pytest.raises(ValueError):
        live.start({"type": "start", "exercise": "E3", "side": "middle"})


# ---------------------------------------------------------------- own clips

OWN = os.path.join("data", "own", "landmarks", "manifest.csv")


@pytest.mark.skipif(not os.path.exists(OWN), reason="own recordings not present (data/ is not in git)")
def test_own_clips_far_side_never_starts_near_side_unchanged():
    from features.signals import best_side
    from research.eval_own_landmarks import DATA_DIR, frame_size, frames_by_time
    m = pd.read_csv(OWN)
    m = m[m["usable"] != "no"]
    cols = [f"{c}{i}" for i in ALL_LM for c in "xyv"]
    for _, r in m.iterrows():
        ex_id = r["exercise"].split("_")[0]
        cfg = load_config(ex_id)
        raw = pd.read_csv(os.path.join(DATA_DIR, r["file"]))
        near = best_side(raw, cfg["exercise"]["required_landmarks"])
        far = "left" if near == "right" else "right"
        w, h = frame_size(r)
        df = frames_by_time(raw, 15)
        reps = {}
        for side in (None, near, far):
            e = SessionEngine(cfg, w, h, language="en", side=side)
            for t, row in zip(df["time_s"].to_numpy(), df[cols].to_numpy(float)):
                e.process(float(t), None if np.isnan(row[0]) else dict(zip(cols, row)), 128.0)
            reps[side] = len(e.log.reps)
        assert reps[near] == reps[None], r["file"]           # weak side facing: same as before
        assert reps[far] == 0, r["file"]                      # weak side away: never measured
