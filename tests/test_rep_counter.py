"""Live rep detection (session/rep_counter.py) on synthetic angle signals."""
import numpy as np
import pytest

from features.signals import FPS
from session.config import load_config
from session.rep_counter import RepCounter
from tests.synth import rep_angles


@pytest.fixture(scope="module")
def cfg():
    return load_config("E1")


def run(cfg, angles):
    rc, events = RepCounter(cfg), []
    for i, a in enumerate(angles):
        events += rc.update(i, i / FPS, a)
    return events


def reps(events):
    return [e for e in events if e.kind == "rep"]


def test_counts_one_clean_rep_with_sensible_window(cfg):
    a = rep_angles(duration_s=3.0, rest_s=1.0)
    (r,) = reps(run(cfg, a))
    assert r.peak == pytest.approx(90, abs=1)
    # rep starts near the end of the first rest (frame 30) and ends near the end of the movement
    assert 20 <= r.start <= 34
    assert 105 <= r.end <= 120
    assert r.end - r.start >= 0.8 * 90


def test_counts_several_reps(cfg):
    a = np.concatenate([rep_angles() for _ in range(4)])
    assert len(reps(run(cfg, a))) == 4


def test_long_rest_does_not_inflate_rep(cfg):
    a = rep_angles(duration_s=3.0, rest_s=8.0)
    (r,) = reps(run(cfg, a))
    assert r.start >= 8 * FPS - 10


def test_works_with_high_resting_angle(cfg):
    assert len(reps(run(cfg, rep_angles(low=35, high=90)))) == 1


def test_small_reduced_range_rep_still_counts(cfg):
    assert len(reps(run(cfg, rep_angles(low=10, high=35)))) == 1


def test_fidgeting_is_ignored(cfg):
    a = rep_angles(low=10, high=22)          # 12 deg wiggle, below start margin + min rom
    assert reps(run(cfg, a)) == []


def test_quick_swing_is_ignored(cfg):
    a = rep_angles(duration_s=0.6, low=10, high=50)    # wind-up flick, shorter than min_duration_s
    assert reps(run(cfg, a)) == []


def test_rise_without_return_times_out(cfg):
    up = np.r_[np.full(30, 10.0), np.linspace(10, 80, 30), np.full(int(25 * FPS), 80.0)]
    assert reps(run(cfg, up)) == []


def test_short_tracking_gap_is_tolerated(cfg):
    a = rep_angles()
    a[60:63] = np.nan                        # 3 frames < gap_frames_N
    ev = run(cfg, a)
    assert len(reps(ev)) == 1 and not [e for e in ev if e.kind == "lost"]


def test_tracking_loss_mid_rep(cfg):
    a = rep_angles()
    a[60:70] = np.nan
    ev = run(cfg, a)
    lost = [e for e in ev if e.kind == "lost"]
    assert len(lost) == 1 and lost[0].start is not None
    assert [e.kind for e in ev].count("found") == 1
    assert reps(ev) == []                    # the cut-off rep is not reported as a normal rep


def test_tracking_loss_at_rest_has_no_rep_start(cfg):
    a = np.r_[np.full(30, 10.0), np.full(10, np.nan), rep_angles()]
    ev = run(cfg, a)
    assert [e for e in ev if e.kind == "lost"][0].start is None
    assert len(reps(ev)) == 1
