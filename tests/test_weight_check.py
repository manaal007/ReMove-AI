"""Weight check before calibration (capture/weight_check.py): geometry, gates, vote, classes."""
import numpy as np
import pytest

from capture.weight_check import (WEIGHT_CLASSES, Box, WeightVote, box_ratio, classify, crop_region,
                                  has_weight_check, limb_geometry, observe)
from session.config import load_config
from tests.synth import SIDE_H, SIDE_W, side_pose


@pytest.fixture
def e3():
    return load_config("E3")


@pytest.fixture
def e4():
    return load_config("E4")


def bottle_at(joint, limb, ratio, score=0.5, dx=0.0):
    """A box `ratio` limb lengths tall, centred on the joint (shifted dx limb lengths)."""
    h = ratio * limb
    return Box(joint[0] - 0.15 * limb + dx * limb, joint[1] - h / 2, 0.3 * limb, h, score)


def geo(cfg, ex_id, **kw):
    return limb_geometry(side_pose(ex_id, 10 if ex_id == "E3" else 90, **kw), cfg["exercise"], SIDE_W, SIDE_H)


def test_only_side_view_exercises_with_a_weight_limb_are_checked():
    assert has_weight_check(load_config("E3")["exercise"])
    assert has_weight_check(load_config("E4")["exercise"])
    assert not has_weight_check(load_config("E1")["exercise"])


def test_limb_is_forearm_for_e3_and_shin_for_e4(e3, e4):
    (wx, wy), forearm = geo(e3, "E3")
    assert forearm == pytest.approx(270, abs=1)              # synth forearm, pixels
    (ax, ay), shin = geo(e4, "E4")
    assert shin == pytest.approx(380, abs=1)


def test_limb_not_seen_gives_none(e3):
    assert geo(e3, "E3", vis=0.2) is None


def test_crop_is_square_around_joint_and_clipped(e3):
    joint, limb = np.array([100.0, 500.0]), 200.0
    x0, y0, x1, y1 = crop_region(joint, limb, SIDE_W, SIDE_H, e3)
    assert (x0, y1 - y0) == (0, 500)                          # 2.5 x 200, clipped at the left edge
    assert crop_region(np.array([5.0, 5.0]), 4.0, SIDE_W, SIDE_H, e3) is None   # too small


@pytest.mark.parametrize("ratio,counts", [(0.1, False), (0.5, True), (1.1, True), (2.0, False)])
def test_box_size_gate(e3, ratio, counts):
    joint, limb = np.array([500.0, 900.0]), 250.0
    assert (box_ratio(bottle_at(joint, limb, ratio), joint, limb, e3) is not None) == counts


def test_box_far_from_the_joint_or_low_score_does_not_count(e3):
    joint, limb = np.array([500.0, 900.0]), 250.0
    assert box_ratio(bottle_at(joint, limb, 0.6, dx=1.0), joint, limb, e3) is None
    assert box_ratio(bottle_at(joint, limb, 0.6, score=0.1), joint, limb, e3) is None
    assert box_ratio(bottle_at(joint, limb, 0.6, dx=0.3), joint, limb, e3) == pytest.approx(0.6)


def test_observe_keeps_the_most_confident_counting_box(e3):
    joint, limb = np.array([500.0, 900.0]), 250.0
    boxes = [bottle_at(joint, limb, 0.5, score=0.3), bottle_at(joint, limb, 0.9, score=0.6),
             bottle_at(joint, limb, 2.5, score=0.9)]              # biggest score, but not bottle-sized
    assert observe(boxes, joint, limb, e3) == pytest.approx(0.9)
    assert observe([], joint, limb, e3) is None


@pytest.mark.parametrize("ex_id,ratio,expected", [
    ("E3", 0.8, "light"), ("E3", 1.0, "heavy"), ("E3", 1.15, "heavy"),
    ("E4", 0.5, "light"), ("E4", 0.65, "heavy"),
])
def test_light_or_heavy_from_size_cut_offs(ex_id, ratio, expected):
    cfg = load_config(ex_id)
    assert classify([ratio] * 10, 60, ex_id, cfg) == expected


def test_cut_offs_live_in_thresholds_yaml():
    wc = load_config("E3")["weight_check"]
    assert wc["heavy_min_ratio"] == {"E3": 1.0, "E4": 0.65}
    assert wc["model"].endswith("efficientdet_lite0.tflite")


@pytest.mark.parametrize("hits,frames,expected", [
    (0, 60, "none"), (1, 10, "none"),       # fewer than min_hits
    (2, 100, "none"),                        # 2% < min_hit_fraction
    (2, 60, "light"), (30, 60, "light"),
])
def test_vote_needs_enough_frames_with_a_bottle(e3, hits, frames, expected):
    assert classify([0.6] * hits, frames, "E3", e3) == expected


def test_no_frames_is_none(e3):
    assert classify([], 0, "E3", e3) == "none"


def test_vote_waits_for_the_window_from_the_first_frame_with_the_limb(e3):
    v = WeightVote(e3, "E3")
    v.add(0.0, None, limb_seen=False)       # not counted, does not start the clock
    assert not v.ready(10.0)
    for k in range(60):
        t = 1.0 + k / 15
        v.add(t, 0.7 if k % 10 == 0 else None)
    assert not v.ready(1.0 + 59 / 15)       # 3.93 s < window_s 4.0
    assert v.ready(5.0)
    res = v.result()
    assert res == {"suggested": "light", "frames": 60, "hits": 6, "hit_fraction": 0.1, "ratio": 0.7}
    assert res["suggested"] in WEIGHT_CLASSES
