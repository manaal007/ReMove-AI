"""Whole-session behaviour of session/engine.py on synthetic frames (no camera)."""
import json

import numpy as np
import pytest

from features.signals import FPS
from session.config import load_config
from session.engine import SessionEngine
from tests.synth import lean_profile, pose, rep_angles

W = H = 100
GRAY = 120


@pytest.fixture
def cfg():
    return load_config("E1")


class Sim:
    """Drives an engine frame by frame and collects every prompt."""

    def __init__(self, engine):
        self.e, self.i, self.prompts = engine, 0, []

    def feed(self, lm, gray=GRAY):
        self.prompts += self.e.process(self.i / FPS, lm, gray)
        self.i += 1

    def settle(self, n=35):
        for _ in range(n):
            self.feed(pose(10))

    def rep(self, lean=0.0, **kw):
        a = rep_angles(**kw)
        rest = int(kw.get("rest_s", 1.0) * FPS)
        leans = lean_profile(rest, len(a) - 2 * rest, lean)
        for ang, ln in zip(a, leans):
            self.feed(pose(ang, ln))

    def keys(self, reason=None):
        return [p.key for p in self.prompts if reason is None or p.reason == reason]


def labels(engine):
    return [r["label"] for r in engine.log.reps]


def started(cfg, **kw):
    s = Sim(SessionEngine(cfg, W, H, **kw))
    s.settle()
    return s


# ---------------------------------------------------------------- camera check

def hold_frames(cfg):
    return int(cfg["camera_check"]["issue_hold_s"] * FPS)


def test_waits_for_camera_check_then_says_start(cfg):
    s = Sim(SessionEngine(cfg, W, H))
    for _ in range(hold_frames(cfg) - 3):
        s.feed(pose(10), gray=20)
    assert s.keys() == []                             # not spoken before issue_hold_s
    for _ in range(10):
        s.feed(pose(10), gray=20)
    assert s.keys() == ["too_dark"]                   # spoken once, not every frame
    assert s.e.checking and s.e.status()["issue"] == "too_dark"
    s.settle(cfg["camera_check"]["pass_frames"] - 1)
    assert s.e.checking
    s.settle(1)
    assert not s.e.checking and s.e.phase == "baseline"
    assert s.keys()[-1] == "start"


def test_brief_camera_problems_are_not_spoken(cfg):
    s = Sim(SessionEngine(cfg, W, H))
    for _ in range(3):                                # 1 s dark, 0.3 s fine, repeated
        for _ in range(30):
            s.feed(pose(10), gray=20)
        for _ in range(10):
            s.feed(pose(10))
    assert s.keys() == [] and s.e.checking


def test_same_camera_prompt_not_repeated_within_interval(cfg):
    cc = cfg["camera_check"]
    s = Sim(SessionEngine(cfg, W, H))
    for _ in range(int((cc["issue_hold_s"] + cc["prompt_every_s"]) * FPS) - 3):
        s.feed(None)
    assert s.keys() == ["not_tracked"]
    for _ in range(6):
        s.feed(None)
    assert s.keys() == ["not_tracked", "not_tracked"]


def test_reps_before_check_passes_are_ignored(cfg):
    s = Sim(SessionEngine(cfg, W, H))
    for a in rep_angles():
        s.feed(pose(a), gray=20)
    assert s.e.log.reps == []


# ---------------------------------------------------------------- labels

def test_baseline_then_all_six_labels(cfg):
    s = started(cfg, language="en")
    for _ in range(3):
        s.rep()
    assert s.e.phase == "scoring"
    assert s.e.log.baseline["rom"] == pytest.approx(80, abs=5)

    s.rep()                                   # 4 good
    s.rep(duration_s=1.2)                     # 5 too_fast  (then rest prompt)
    s.rep(wobble=8)                           # 6 jerky
    s.rep(high=40)                            # 7 reduced_range
    s.rep(lean=15)                            # 8 trunk_compensation
    # 9 not_tracked: tracking lost mid-rep
    a = rep_angles()
    for k, ang in enumerate(a):
        s.feed(None if 55 <= k < 70 else pose(ang))
    assert "not_tracked" not in s.keys("camera")   # 0.5 s loss: shorter than issue_hold_s
    assert not s.e.paused
    s.settle()
    s.rep()                                   # 10 good (7th scored rep)
    assert not s.e.done                       # cap counts scored reps only
    for _ in range(3):
        s.rep()                               # 11-13 good -> 10th scored rep, set done

    assert labels(s.e) == ["good"] * 4 + ["too_fast", "jerky", "reduced_range",
                                          "trunk_compensation", "not_tracked"] + ["good"] * 4
    assert [r["used_for_baseline"] for r in s.e.log.reps[:3]] == [True] * 3
    assert s.e.done and s.e.log.ended_reason == "set_done"


def test_slow_smooth_reps_are_not_jerky(cfg):
    """Live-test case: 4.2 s baseline, then smooth reps of 6.2-7.6 s."""
    s = started(cfg)
    for _ in range(3):
        s.rep(duration_s=4.2)
    for d in (6.2, 6.8, 7.2, 7.6):
        s.rep(duration_s=d)
    assert labels(s.e)[3:] == ["good"] * 4


def test_every_rep_prompt_sequence(cfg):
    s = started(cfg)
    for _ in range(5):
        s.rep()
    assert s.keys() == ["start", "good", "good", "good", "good", "good", "rest"]


def test_feedback_uses_language_and_audio_mapping(cfg):
    s = started(cfg, language="ur")
    for _ in range(3):
        s.rep()
    s.rep(high=40)
    p = s.prompts[-1]
    assert p.key == "reduced_range" and p.audio.endswith("ur_raise_higher.mp3")
    assert "بازو" in p.text


def test_short_tracking_gap_does_not_pause(cfg):
    s = started(cfg)
    a = rep_angles()
    for k, ang in enumerate(a):
        s.feed(None if 60 <= k < 60 + cfg["tracking"]["gap_frames_N"] - 1 else pose(ang))
        assert not s.e.paused and not s.e.checking
    assert labels(s.e) == ["good"]
    assert s.keys() == ["start", "good"]


def test_tracking_loss_pauses_and_resumes_without_start(cfg):
    s = started(cfg)
    s.rep()
    for _ in range(cfg["tracking"]["gap_frames_N"] + 2):
        s.feed(None)
    assert s.e.paused and not s.e.checking and s.e.phase == "baseline"
    assert "not_tracked" not in s.keys()      # paused silently until issue_hold_s
    for _ in range(hold_frames(cfg)):
        s.feed(None)
    assert s.keys()[-1] == "not_tracked" and s.keys().count("not_tracked") == 1
    assert len(s.e.log.reps) == 1             # loss at rest: no extra rep logged
    s.feed(pose(10))
    assert not s.e.paused                     # resumes on the first tracked frame
    s.settle()
    s.rep()
    assert len(s.e.log.reps) == 2
    assert s.keys().count("start") == 1       # "start" is never said again


def test_rep_lost_mid_way_is_logged_but_only_camera_prompt_spoken(cfg):
    s = started(cfg)
    a = rep_angles()
    for k, ang in enumerate(a):
        s.feed(None if k >= 60 else pose(ang))
    assert labels(s.e) == ["not_tracked"]
    assert s.keys("rep") == [] and s.keys("camera") == ["not_tracked"]


# ---------------------------------------------------------------- baseline

def test_unclean_reps_not_used_for_baseline(cfg):
    s = started(cfg)
    s.rep(lean=15)
    for _ in range(3):
        s.rep()
    assert [r["used_for_baseline"] for r in s.e.log.reps] == [False, True, True, True]
    assert s.e.phase == "scoring"


def test_failed_baseline_asks_to_adjust_and_restarts(cfg):
    s = started(cfg, language="en")
    for _ in range(cfg["baseline"]["max_reps"]):
        s.rep(lean=15)
    assert not s.e.done and s.e.phase == "baseline"
    assert s.e.log.baseline_restarts == 1
    # rep 5 is also the rest point: its own feedback, then adjust, then rest
    assert s.keys()[-3:] == ["trunk_compensation", "adjust_position", "rest"]
    assert "adjust your position" in s.prompts[-2].text
    for _ in range(cfg["baseline"]["min_reps"]):
        s.rep()
    assert s.e.phase == "scoring" and s.e.log.baseline is not None
    assert [r["used_for_baseline"] for r in s.e.log.reps] == [False] * 5 + [True] * 3


def test_previous_baseline_skips_calibration(cfg):
    base = {"rom": 80.0, "duration_s": 2.8, "jerk_norm": 1e6, "peak_angle": 90.0, "min_angle": 10.0}
    s = started(cfg, baseline=base)
    assert s.e.phase == "scoring" and s.e.log.baseline_from_previous
    s.rep(high=40)
    assert labels(s.e) == ["reduced_range"]


# ---------------------------------------------------------------- caps + timing

def test_set_cap_counts_scored_reps_only(cfg):
    s = started(cfg)
    cap, n_base = cfg["caps"]["max_reps_per_set"], cfg["baseline"]["min_reps"]
    for _ in range(cap + n_base + 2):
        s.rep()
    reps = s.e.log.reps
    assert len(reps) == cap + n_base                  # 3 baseline + 10 scored
    assert [r["phase"] for r in reps].count("scoring") == cap
    assert s.e.log.ended_reason == "set_done"
    # rest prompts count every rep, baseline included: reps 5 and 10
    assert s.keys("session").count("rest") == 2
    assert s.keys()[-2:] == ["good", "set_done"]      # rep 12's good, then straight to set_done
    # the last rep's "good, do the next rep" is skipped: set_done follows straight away
    assert s.keys("rep").count("good") == cap + n_base - 1


def test_failed_baselines_do_not_end_the_session(cfg):
    s = started(cfg)
    cap = cfg["caps"]["max_reps_per_set"]
    for _ in range(2 * cfg["baseline"]["max_reps"]):  # two failed baseline rounds = 10 reps
        s.rep(lean=15)
    assert not s.e.done and s.e.phase == "baseline"
    assert s.e.log.baseline_restarts == 2
    for _ in range(cfg["baseline"]["min_reps"]):
        s.rep()
    assert s.e.phase == "scoring"
    for _ in range(cap - 1):
        s.rep()
    assert not s.e.done
    s.rep()
    assert s.e.done and s.e.log.ended_reason == "set_done"
    assert s.e.status()["scored_reps"] == cap


def test_block_timing_summarizes_most_common_fault(cfg):
    s = started(cfg, timing="every_3_4_reps")
    for _ in range(3):
        s.rep()                                # block 1: good good good
    s.rep(duration_s=1.2)                      # block 2 ...
    s.rep(duration_s=1.2)                      # rep 5 -> rest: flush partial block first
    s.rep(high=40)
    s.rep(high=40)
    s.rep()                                    # block 3: reduced reduced good
    s.rep(wobble=8)
    s.rep()                                    # rep 10 -> rest: flush partial block (jerky good)
    s.rep()
    s.rep()
    s.rep()                                    # rep 13 = 10th scored -> block 5, then set done
    assert s.keys("rep") == []
    assert s.keys() == ["start", "good", "too_fast", "rest", "reduced_range",
                        "jerky", "rest", "good", "set_done"]
    assert [p.reason for p in s.prompts if p.key in ("too_fast", "reduced_range", "jerky")] == ["block"] * 3


def test_log_records_mode_language_and_is_json(cfg):
    s = started(cfg, language="en", timing="every_3_4_reps")
    s.rep()
    log = s.e.stop()
    assert (log.language, log.timing, log.block_size) == ("en", "every_3_4_reps", 3)
    assert log.ended_reason == "user_stopped"
    json.dumps(log.to_dict(), ensure_ascii=False)


def test_stopped_engine_ignores_frames(cfg):
    s = started(cfg)
    s.e.stop()
    s.rep()
    assert s.e.log.reps == [] and s.e.process(99.0, pose(), GRAY) == []


def test_bad_timing_rejected(cfg):
    with pytest.raises(ValueError):
        SessionEngine(cfg, W, H, timing="sometimes")
