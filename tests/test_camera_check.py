"""Camera check (capture/camera_check.py) and config loading (session/config.py)."""
import numpy as np
import pytest

from capture.camera_check import check_frame, mean_gray
from features.signals import R_HIP, R_WR
from session.config import load_config
from tests.synth import pose


@pytest.fixture(scope="module")
def cfg():
    return load_config("E1")


def test_good_frame_passes(cfg):
    assert check_frame(pose(), 120, cfg) == []


def test_too_dark_and_too_bright(cfg):
    assert check_frame(pose(), 30, cfg) == ["too_dark"]
    assert check_frame(pose(), 240, cfg) == ["too_bright"]


def test_no_pose_is_not_tracked(cfg):
    assert check_frame(None, 120, cfg) == ["not_tracked"]
    assert check_frame(None, 10, cfg) == ["too_dark", "not_tracked"]


def test_cut_off_landmark_asks_to_step_back(cfg):
    lm = pose()
    lm[f"y{R_HIP}"] = 1.1                    # hips below the bottom edge
    assert check_frame(lm, 120, cfg) == ["step_back"]


def test_poorly_seen_required_landmark_asks_to_step_back(cfg):
    lm = pose()
    lm[f"v{R_WR}"] = 0.2
    assert check_frame(lm, 120, cfg) == ["step_back"]


def test_small_person_asks_to_come_closer(cfg):
    assert cfg["framing"]["min_body_height_fraction"] == 0.25
    assert check_frame(pose(nose_y=0.40), 120, cfg) == ["come_closer"]   # head-to-hips 0.20
    assert check_frame(pose(nose_y=0.32), 120, cfg) == []                # 0.28, like REHAB24-6


def test_hidden_head_does_not_block(cfg):
    lm = pose()
    lm["v0"] = 0.1
    assert check_frame(lm, 120, cfg) == []


def test_mean_gray_matches_opencv():
    cv2 = pytest.importorskip("cv2")
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, (40, 60, 3), dtype=np.uint8)
    assert mean_gray(img) == pytest.approx(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean(), abs=0.6)


def test_config_merges_exercise_and_thresholds(cfg):
    assert cfg["exercise_id"] == "E1"
    assert cfg["exercise"]["max_trunk_lean_deg"] == 10
    assert cfg["rules"]["jerky_sparc_ratio"] == 1.4
    assert cfg["feedback"]["timing"] in ("every_rep", "every_3_4_reps")


def test_unknown_exercise_raises():
    with pytest.raises(KeyError):
        load_config("E9")
