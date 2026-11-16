"""Side-view exercises E3 (elbow curl) and E4 (seated knee extension) on synthetic frames:
signals, config, camera check, rules and whole sessions. E1 is covered by the other tests."""
import numpy as np
import pytest

from capture.camera_check import check_frame, shoulder_torso_ratio
from features import signals as S
from features.signals import FPS
from feedback import messages as M
from session.config import is_side_view, load_config
from session.engine import SessionEngine
from session.rules import find_faults, label_rep
from tests.synth import SIDE_H, SIDE_W, rep_angles, side_pose

ASPECT = SIDE_W / SIDE_H
REST = {"E3": 10.0, "E4": 90.0}
HIGH = {"E3": 120.0, "E4": 165.0}


@pytest.fixture(params=["E3", "E4"])
def ex_id(request):
    return request.param


# ---------------------------------------------------------------- signals

@pytest.mark.parametrize("flex", [0, 45, 90, 130])
def test_elbow_flexion_is_180_minus_shoulder_elbow_wrist(flex):
    ex = load_config("E3")["exercise"]
    a, c, v = S.side_signals(side_pose("E3", flex, comp=0), SIDE_W, SIDE_H, ex, "right")
    assert a[0] == pytest.approx(flex, abs=0.5)
    assert c[0] == pytest.approx(0, abs=0.5) and v[0] == pytest.approx(0.9)


@pytest.mark.parametrize("swing", [0, 15, 30])
def test_shoulder_angle_follows_upper_arm_swing(swing):
    ex = load_config("E3")["exercise"]
    a, c, _ = S.side_signals(side_pose("E3", 60, comp=swing), SIDE_W, SIDE_H, ex, "right")
    assert c[0] == pytest.approx(swing, abs=0.5)
    assert a[0] == pytest.approx(60, abs=0.5)          # flexion does not change with the swing


@pytest.mark.parametrize("knee", [90, 130, 175])
def test_knee_angle_is_hip_knee_ankle(knee):
    ex = load_config("E4")["exercise"]
    a, c, _ = S.side_signals(side_pose("E4", knee), SIDE_W, SIDE_H, ex, "right")
    assert a[0] == pytest.approx(knee, abs=0.5)
    assert c[0] == pytest.approx(0, abs=0.5)


def test_trunk_angle_follows_leaning_back():
    ex = load_config("E4")["exercise"]
    _, c, _ = S.side_signals(side_pose("E4", 120, comp=20), SIDE_W, SIDE_H, ex, "right")
    assert abs(c[0]) == pytest.approx(20, abs=0.5)


def test_best_side_is_the_better_seen_side():
    joints = ["shoulder", "elbow", "wrist", "hip"]
    assert S.best_side(side_pose("E3", side="left"), joints) == "left"
    assert S.best_side(side_pose("E3", side="right"), joints) == "right"


def test_low_visibility_gives_nan():
    ex = load_config("E3")["exercise"]
    a, c, _ = S.side_signals(side_pose("E3", 60, vis=0.3), SIDE_W, SIDE_H, ex, "right")
    assert np.isnan(a[0]) and np.isnan(c[0])


def test_side_rep_features_measure_change_from_rep_start():
    n = 90
    a = REST["E3"] + 100 * np.sin(np.pi * np.arange(n) / n)
    comp = 5 + 25 * np.sin(np.pi * np.arange(n) / n)   # starts at 5, swings 25 more
    f = S.side_rep_features(a, comp, np.full(n, 0.9), 0, n - 1)
    assert f["valid"]
    # reference = mean of the first 5 frames, which already include ~2 deg of the swing
    assert f["comp_change_max"] == pytest.approx(25, abs=3)
    assert f["rom"] == pytest.approx(100, abs=5)       # 5-frame smoothing trims the peak a little
    assert "trunk_lean_max" not in f and "elbow_min" not in f


# ---------------------------------------------------------------- config

def test_side_view_configs_load(ex_id):
    cfg = load_config(ex_id)
    assert is_side_view(cfg["exercise"])
    assert cfg["exercise"]["camera_view"] == "side"
    assert not is_side_view(load_config("E1")["exercise"])


def test_overrides_apply_to_one_exercise_only():
    assert load_config("E4")["framing"]["min_body_height_fraction"] == 0.2
    assert load_config("E1")["framing"]["min_body_height_fraction"] == 0.25
    assert load_config("E3")["framing"]["min_body_height_fraction"] == 0.25


def test_compensation_limits_from_spec():
    assert load_config("E3")["exercise"]["compensation"] == {"signal": "shoulder_angle", "baseline_margin_deg": 15}
    assert load_config("E4")["exercise"]["compensation"] == {"signal": "trunk_angle", "max_change_deg": 15}


def test_side_view_config_is_validated(tmp_path):
    import shutil
    import yaml
    from session.config import CONFIG_DIR
    shutil.copy(CONFIG_DIR / "thresholds.yaml", tmp_path / "thresholds.yaml")
    bad = {"X": {**load_config("E3")["exercise"], "required_landmarks": ["elbow", "toe"]}}
    (tmp_path / "exercises.yaml").write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config("X", tmp_path)


# ---------------------------------------------------------------- camera check

def test_side_on_person_passes(ex_id):
    cfg = load_config(ex_id)
    assert check_frame(side_pose(ex_id, REST[ex_id]), 120, cfg, aspect=ASPECT) == []


def test_facing_the_camera_asks_to_turn_sideways(ex_id):
    cfg = load_config(ex_id)
    lm = side_pose(ex_id, REST[ex_id], facing_camera=True, far_vis=0.9)
    assert shoulder_torso_ratio(lm, ASPECT) > cfg["side_view"]["max_shoulder_torso_ratio"]
    assert check_frame(lm, 120, cfg, aspect=ASPECT) == ["turn_sideways"]


def test_side_on_ratio_is_small():
    assert shoulder_torso_ratio(side_pose("E3", 10), ASPECT) < 0.1


def test_ankle_cut_off_asks_to_step_back_for_e4_only():
    lm = side_pose("E4", 90, ankle_y=1.05)
    assert check_frame(lm, 120, load_config("E4"), aspect=ASPECT) == ["step_back"]
    lm3 = side_pose("E3", 10, ankle_y=1.05)           # E3 does not need the legs
    assert check_frame(lm3, 120, load_config("E3"), aspect=ASPECT) == []


def test_check_uses_the_given_side():
    cfg = load_config("E3")
    lm = side_pose("E3", 10, side="left")             # right side poorly seen
    assert check_frame(lm, 120, cfg, side="left", aspect=ASPECT) == []
    assert check_frame(lm, 120, cfg, side="right", aspect=ASPECT) == ["step_back"]


def test_e1_camera_check_unchanged_by_side_view_code():
    from tests.synth import pose
    cfg = load_config("E1")
    assert check_frame(pose(10), 120, cfg) == []
    assert check_frame(pose(10), 120, cfg, aspect=0.5) == []   # aspect is ignored for front view


# ---------------------------------------------------------------- rules

def _feat(**kw):
    f = {"valid": True, "duration_s": 3.0, "rom": 100.0, "peak_angle": 110.0, "min_angle": 10.0,
         "sparc": -1.5, "jerk_norm": 1e5, "comp_change_max": 2.0, "comp_range": 2.0}
    f.update(kw)
    return f


def test_e4_lean_limit_is_absolute():
    cfg = load_config("E4")
    assert "trunk_compensation" not in find_faults(_feat(comp_change_max=14.5), cfg)
    assert find_faults(_feat(comp_change_max=15.5), cfg) == ["trunk_compensation"]


E3_BASE = {"rom": 100.0, "duration_s": 3.0, "sparc": -1.5, "peak_angle": 110.0, "min_angle": 10.0,
           "jerk_norm": 1e5, "comp_change_max": 25.0}


@pytest.mark.parametrize("swing,flagged", [(25.0, False), (40.0, False), (40.5, True), (60.0, True)])
def test_e3_swing_is_relative_to_own_baseline(swing, flagged):
    cfg = load_config("E3")                           # limit = 25 + 15 = 40
    assert ("trunk_compensation" in find_faults(_feat(comp_change_max=swing), cfg, E3_BASE)) == flagged


def test_e3_swing_rule_needs_a_baseline_swing():
    cfg = load_config("E3")
    assert find_faults(_feat(comp_change_max=80.0), cfg) == []                    # calibration
    old = {k: v for k, v in E3_BASE.items() if k != "comp_change_max"}            # older baseline
    assert "trunk_compensation" not in find_faults(_feat(comp_change_max=80.0), cfg, old)
    nan = {**E3_BASE, "comp_change_max": float("nan")}
    assert "trunk_compensation" not in find_faults(_feat(comp_change_max=80.0), cfg, nan)


def test_baseline_has_swing_only_for_side_view():
    from session.rules import build_baseline
    side = build_baseline([_feat(comp_change_max=s) for s in (20.0, 25.0, 40.0)])
    assert side["comp_change_max"] == 25.0
    e1 = build_baseline([{k: v for k, v in _feat().items() if not k.startswith("comp")}] * 3)
    assert "comp_change_max" not in e1


def test_browser_baseline_keeps_swing():
    from api.live import clean_baseline
    b = clean_baseline({**E3_BASE})
    assert b["comp_change_max"] == 25.0
    assert "comp_change_max" not in clean_baseline({k: v for k, v in E3_BASE.items() if k != "comp_change_max"})


def test_side_view_uses_the_same_six_labels():
    cfg = load_config("E4")
    base = {"rom": 70.0, "duration_s": 3.0, "sparc": -1.5, "peak_angle": 160.0, "min_angle": 90.0}
    assert label_rep(_feat(rom=70.0, peak_angle=160.0, min_angle=90.0), cfg, base)[0] == "good"
    assert label_rep(_feat(rom=40.0, peak_angle=130.0, min_angle=90.0), cfg, base)[0] == "reduced_range"
    assert label_rep(_feat(rom=70.0, peak_angle=160.0, duration_s=1.5), cfg, base)[0] == "too_fast"
    assert label_rep({"valid": False}, cfg, base)[0] == "not_tracked"


# ---------------------------------------------------------------- phrases

def test_every_exercise_phrase_exists_in_both_languages():
    for ex_id in ("E1", "E2", "E3", "E4"):
        for key, pk in (load_config(ex_id)["exercise"].get("phrases") or {}).items():
            assert key in M.REP_LABELS + M.PROMPTS, (ex_id, key)
            for lang in M.LANGS:
                text, path = M.get_feedback(key, lang, {key: pk})
                assert text.strip() and path.name == f"{lang}_{pk}.mp3"


def test_exercise_wording():
    p3 = load_config("E3")["exercise"]["phrases"]
    p4 = load_config("E4")["exercise"]["phrases"]
    assert "elbow" in M.get_feedback("reduced_range", "en", p3)[0]
    assert "knee" in M.get_feedback("reduced_range", "en", p4)[0]
    assert "lean back" in M.get_feedback("trunk_compensation", "en", p4)[0]
    assert "upper arm" in M.get_feedback("trunk_compensation", "en", p3)[0]
    assert "leg" in M.get_feedback("jerky", "en", p4)[0]
    assert M.get_feedback("good", "en", p4)[0] == M.PHRASES["good"]["en"]     # shared phrase
    assert M.get_feedback("reduced_range", "en")[0] == M.PHRASES["raise_higher"]["en"]   # E1 as before


# ---------------------------------------------------------------- whole sessions

class Sim:
    def __init__(self, ex_id, **kw):
        self.ex_id = ex_id
        self.cfg = load_config(ex_id)
        self.e = SessionEngine(self.cfg, SIDE_W, SIDE_H, language="en", **kw)
        self.i, self.prompts = 0, []
        self.pose_kw = {}

    def feed(self, lm, gray=120):
        self.prompts += self.e.process(self.i / FPS, lm, gray)
        self.i += 1

    def settle(self, n=35, **kw):
        for _ in range(n):
            self.feed(side_pose(self.ex_id, REST[self.ex_id], **{**self.pose_kw, **kw}))

    def rep(self, comp=0.0, high=None, **kw):
        a = rep_angles(low=REST[self.ex_id], high=high or HIGH[self.ex_id], **kw)
        rest = int(kw.get("rest_s", 1.0) * FPS)
        n_rep = len(a) - 2 * rest
        comps = np.r_[np.zeros(rest), comp * np.sin(np.pi * np.arange(n_rep) / n_rep), np.zeros(rest)]
        for ang, c in zip(a, comps):
            self.feed(side_pose(self.ex_id, ang, comp=c, **self.pose_kw))

    def keys(self, reason=None):
        return [p.key for p in self.prompts if reason is None or p.reason == reason]

    def phrases(self, reason=None):
        return [p.phrase for p in self.prompts if reason is None or p.reason == reason]

    def labels(self):
        return [r["label"] for r in self.e.log.reps]


def test_e3_person_who_always_swings_is_judged_against_own_swing():
    s = Sim("E3")
    s.settle()
    for _ in range(3):
        s.rep(comp=25)                        # this person swings 25 deg on every curl
    # measured from the mean of the first 5 rep frames, which already hold ~2 deg of the swing
    assert s.e.log.baseline["comp_change_max"] == pytest.approx(25, abs=3)
    s.rep(comp=25)                            # their normal swing: good
    s.rep(comp=35)                            # +10: still good
    s.rep(comp=50)                            # +25: flagged
    assert s.labels()[3:] == ["good", "good", "trunk_compensation"]


@pytest.mark.parametrize("side", ["left", "right"])
def test_side_is_locked_when_the_camera_check_passes(ex_id, side):
    s = Sim(ex_id)
    s.pose_kw = {"side": side}
    s.settle()
    assert not s.e.checking and s.e.log.side == side and s.e.status()["side"] == side
    s.rep()
    assert s.e.log.reps and s.e.log.reps[0]["label"] == "good"


def test_full_e3_session_labels_and_wording():
    s = Sim("E3")
    s.settle()
    for _ in range(3):
        s.rep()                               # baseline swing ~0
    assert s.e.phase == "scoring"
    assert s.e.log.baseline["comp_change_max"] == pytest.approx(0, abs=1)
    s.rep()                                   # 4 good
    s.rep(high=60)                            # 5 reduced_range (60 vs 120 range)
    s.rep(comp=30)                            # 6 upper arm swings 30 > 0 + 15
    s.rep(comp=12)                            # 7 small swing: fine
    s.rep(duration_s=1.2)                     # 8 too fast
    assert s.labels() == ["good"] * 4 + ["reduced_range", "trunk_compensation", "good", "too_fast"]
    said = dict(zip(s.keys("rep"), s.phrases("rep")))
    assert said["reduced_range"] == "bend_more"
    assert said["trunk_compensation"] == "upper_arm_still"
    assert said["too_fast"] == "too_fast_elbow"
    assert said["good"] == "good"


def test_full_e4_session_labels_and_wording():
    s = Sim("E4")
    s.settle()
    for _ in range(3):
        s.rep()
    s.rep(comp=20)                            # leans back 20 > 15
    s.rep(comp=10)                            # 10: fine
    s.rep(high=125)                           # 35 of 75 deg -> reduced_range
    s.rep(wobble=10)                          # jerky
    assert s.labels() == ["good"] * 3 + ["trunk_compensation", "good", "reduced_range", "jerky"]
    said = dict(zip(s.keys("rep"), s.phrases("rep")))
    assert said["trunk_compensation"] == "sit_straight"
    assert said["reduced_range"] == "straighten_more"
    assert said["jerky"] == "jerky_leg"
    texts = [p.text for p in s.prompts if p.key == "reduced_range"]
    assert texts == ["Straighten your knee a little more."]


def test_e4_leaning_during_baseline_is_not_used_for_baseline():
    s = Sim("E4")
    s.settle()
    s.rep(comp=25)
    for _ in range(3):
        s.rep()
    assert [r["used_for_baseline"] for r in s.e.log.reps] == [False, True, True, True]


def test_facing_camera_says_turn_sideways_and_does_not_start(ex_id):
    s = Sim(ex_id)
    s.settle(int(2 * FPS), facing_camera=True, far_vis=0.9)
    assert s.e.checking and s.keys() == ["turn_sideways"]
    s.settle()
    assert not s.e.checking and s.keys()[-1] == "start"


def test_e4_step_back_uses_chair_wording():
    s = Sim("E4")
    s.settle(int(2 * FPS), ankle_y=1.05)
    assert s.keys() == ["step_back"] and s.phrases() == ["move_chair_back"]
    assert "chair" in s.prompts[0].text


def test_e4_tracking_lost_uses_leg_wording():
    s = Sim("E4")
    s.settle()
    for _ in range(int(3 * FPS)):
        s.feed(None)
    assert s.e.paused
    lost = [p for p in s.prompts if p.reason == "camera"]
    assert [p.phrase for p in lost] == ["not_tracked_leg"] and "leg" in lost[0].text


def test_cap_counts_scored_reps_for_side_view_too():
    s = Sim("E3")
    s.settle()
    for _ in range(3 + s.cfg["caps"]["max_reps_per_set"] + 1):
        s.rep()
    assert s.e.done and len(s.e.log.reps) == 3 + s.cfg["caps"]["max_reps_per_set"]


def test_e1_session_has_side_right_and_old_phrases():
    from tests.synth import pose
    e = SessionEngine(load_config("E1"), 100, 100, language="en")
    out = []
    for i in range(40):
        out += e.process(i / FPS, pose(10), 120)
    assert e.log.side == "right" and e.status()["side"] == "right"
    assert [(p.key, p.phrase) for p in out] == [("start", "start")]
