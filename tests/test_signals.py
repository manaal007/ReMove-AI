"""Angle math and per-rep features (features/signals.py). No camera or video needed."""
import os

import numpy as np
import pandas as pd
import pytest

from features import signals as S


# ---------- helpers ----------

def landmarks(n=1, r_sh=(0.4, 0.3), r_hip=(0.4, 0.6), r_el=(0.2, 0.3), r_wr=(0.0, 0.3),
              l_sh=(0.6, 0.3), l_hip=(0.6, 0.6), vis=0.9):
    """n identical frames of a person facing the camera, in normalized coords
    (y grows downward, like MediaPipe). Default pose: right arm straight out at 90 deg."""
    pts = {S.R_SH: r_sh, S.R_HIP: r_hip, S.R_EL: r_el, S.R_WR: r_wr,
           S.L_SH: l_sh, S.L_HIP: l_hip}
    row = {}
    for i, (x, y) in pts.items():
        row[f"x{i}"], row[f"y{i}"], row[f"v{i}"] = x, y, vis
    return pd.DataFrame([row] * n)


def synthetic_rep(duration_s=3.0, low=10.0, high=90.0, fps=S.FPS):
    """One smooth up-and-down rep: low -> high -> low."""
    n = int(round(duration_s * fps))
    t = np.arange(n) / fps
    return low + (high - low) * np.sin(np.pi * t / duration_s)


def features_for(abd, elbow=None, lean=None, vis=None):
    n = len(abd)
    elbow = np.full(n, 170.0) if elbow is None else elbow
    lean = np.zeros(n) if lean is None else lean
    vis = np.full(n, 0.9) if vis is None else vis
    return S.rep_features(abd.copy(), elbow, lean, vis, 0, n - 1)


# ---------- angle_at ----------

def test_angle_at_right_angle():
    b = np.array([[0.0, 0.0]])
    assert S.angle_at(b, np.array([[1.0, 0.0]]), np.array([[0.0, 1.0]]))[0] == pytest.approx(90)


def test_angle_at_straight_and_closed():
    b = np.array([[0.0, 0.0], [0.0, 0.0]])
    a = np.array([[1.0, 0.0], [1.0, 0.0]])
    c = np.array([[-1.0, 0.0], [2.0, 0.0]])
    np.testing.assert_allclose(S.angle_at(b, a, c), [180, 0], atol=1e-6)


def test_angle_at_zero_length_is_nan():
    b = np.array([[1.0, 1.0]])
    assert np.isnan(S.angle_at(b, b.copy(), np.array([[2.0, 1.0]]))[0])


# ---------- frame_signals ----------

def test_arm_out_to_side_is_90_deg_abduction_and_straight_elbow():
    abd, elbow, lean, vis = S.frame_signals(landmarks(), 1, 1)
    assert abd[0] == pytest.approx(90)
    assert elbow[0] == pytest.approx(180)
    assert lean[0] == pytest.approx(0)
    assert vis[0] == pytest.approx(0.9)


def test_arm_down_is_zero_abduction():
    abd, *_ = S.frame_signals(landmarks(r_el=(0.4, 0.45), r_wr=(0.4, 0.6)), 1, 1)
    assert abd[0] == pytest.approx(0, abs=1e-6)


def test_arm_overhead_is_180():
    abd, *_ = S.frame_signals(landmarks(r_el=(0.4, 0.1), r_wr=(0.4, 0.0)), 1, 1)
    assert abd[0] == pytest.approx(180)


def test_bent_elbow():
    # forearm points straight up from an elbow out at the side -> 90 deg elbow
    _, elbow, *_ = S.frame_signals(landmarks(r_wr=(0.2, 0.1)), 1, 1)
    assert elbow[0] == pytest.approx(90)


def test_trunk_lean_sign_and_size():
    # shoulders shifted sideways by 0.3 over a trunk height of 0.3 -> 45 deg
    lm = landmarks(r_sh=(0.7, 0.3), l_sh=(0.9, 0.3), r_el=(0.5, 0.3), r_wr=(0.3, 0.3))
    _, _, lean, _ = S.frame_signals(lm, 1, 1)
    assert lean[0] == pytest.approx(45)


def test_pixel_scaling_matters_for_angles():
    # same normalized points on a wide frame change the geometry: angles use pixels
    abd_sq, *_ = S.frame_signals(landmarks(r_el=(0.3, 0.2)), 1, 1)
    abd_wide, *_ = S.frame_signals(landmarks(r_el=(0.3, 0.2)), 1920, 1080)
    assert abd_sq[0] != pytest.approx(abd_wide[0])


def test_low_visibility_frames_become_nan():
    lm = landmarks(n=3)
    lm.loc[1, f"v{S.R_WR}"] = 0.2           # one required landmark poorly seen
    abd, elbow, lean, vis = S.frame_signals(lm, 1, 1)
    assert np.isnan(abd[1]) and np.isnan(elbow[1]) and np.isnan(lean[1])
    assert not np.isnan(abd[0]) and not np.isnan(abd[2])
    assert vis[1] == pytest.approx(0.2)


def test_missing_pose_frame_is_nan():
    lm = landmarks(n=2)
    lm.loc[1, :] = np.nan                    # MediaPipe found no pose
    abd, *_ = S.frame_signals(lm, 1, 1)
    assert np.isnan(abd[1])


def test_single_frame_dict_matches_dataframe():
    lm = landmarks(r_el=(0.3, 0.2), r_sh=(0.42, 0.31), l_sh=(0.61, 0.29))
    from_df = S.frame_signals(lm, 1920, 1080)
    from_dict = S.frame_signals(lm.iloc[0].to_dict(), 1920, 1080)
    for a, b in zip(from_df, from_dict):
        np.testing.assert_allclose(a, b)


def test_single_frame_dict_all_missing():
    nan = {f"{c}{i}": np.nan for i in S.REQUIRED_LM for c in "xyv"}
    abd, elbow, lean, vis = S.frame_signals(nan, 100, 100)
    assert np.isnan(abd[0]) and np.isnan(vis[0])


def test_min_vis_is_configurable():
    lm = landmarks(vis=0.6)
    assert not np.isnan(S.frame_signals(lm, 1, 1, min_vis=0.5)[0][0])
    assert np.isnan(S.frame_signals(lm, 1, 1, min_vis=0.7)[0][0])


# ---------- smooth ----------

def test_smooth_fills_gaps_and_keeps_constant():
    x = np.array([5.0, np.nan, np.nan, 5.0, 5.0])
    np.testing.assert_allclose(S.smooth(x), 5.0)


def test_smooth_reduces_noise():
    rng = np.random.default_rng(0)
    clean = synthetic_rep()
    noisy = clean + rng.normal(0, 3, len(clean))
    assert np.std(S.smooth(noisy) - clean) < np.std(noisy - clean)


# ---------- rep_features ----------

def test_clean_rep_features():
    f = features_for(synthetic_rep(duration_s=3.0, low=10, high=90))
    assert f["valid"]
    assert f["n_frames"] == 90
    assert f["duration_s"] == pytest.approx(3.0)
    assert f["peak_angle"] == pytest.approx(90, abs=1)
    # smoothing averages the lowest edge frames with their neighbours, so min rises a bit
    assert f["min_angle"] == pytest.approx(10, abs=3)
    assert f["rom"] == pytest.approx(f["peak_angle"] - f["min_angle"])
    assert f["rom"] == pytest.approx(80, abs=4)
    # peak speed of A*sin(pi t/T) is A*pi/T
    assert f["peak_speed"] == pytest.approx(80 * np.pi / 3.0, rel=0.05)
    assert f["elbow_min"] == pytest.approx(170)
    assert f["trunk_lean_max"] == pytest.approx(0)


def test_faster_rep_has_higher_speed():
    slow = features_for(synthetic_rep(duration_s=4.0))
    fast = features_for(synthetic_rep(duration_s=1.5))
    assert fast["peak_speed"] > slow["peak_speed"]
    assert fast["duration_s"] < slow["duration_s"]


def test_jerky_rep_has_higher_jerk():
    smooth_rep = synthetic_rep(duration_s=3.0)
    t = np.arange(len(smooth_rep)) / S.FPS
    shaky = smooth_rep + 6 * np.sin(2 * np.pi * 3 * t)   # 3 Hz wobble
    assert features_for(shaky)["jerk_norm"] > 5 * features_for(smooth_rep)["jerk_norm"]


def test_jerk_norm_is_scale_free():
    # same shape, different size and speed -> same dimensionless jerk
    a = features_for(synthetic_rep(duration_s=3.0, low=10, high=90))["jerk_norm"]
    b = features_for(synthetic_rep(duration_s=3.0, low=10, high=50))["jerk_norm"]
    assert a == pytest.approx(b, rel=0.01)


def test_trunk_lean_is_relative_to_rep_start():
    abd = synthetic_rep()
    tilt = np.full(len(abd), 7.0)            # camera tilted 7 deg, person still
    assert features_for(abd, lean=tilt)["trunk_lean_max"] == pytest.approx(0)
    leaning = tilt + 15 * np.sin(np.pi * np.arange(len(abd)) / len(abd))
    # reference is the mean of the first 5 frames, which already lean ~1 deg here
    assert features_for(abd, lean=leaning)["trunk_lean_max"] == pytest.approx(14, abs=1)


def test_too_short_rep_is_invalid():
    f = features_for(synthetic_rep(duration_s=0.2))   # 6 frames
    assert f["valid"] is False


def test_rep_with_too_many_missing_frames_is_invalid():
    abd = synthetic_rep()
    abd[: int(0.3 * len(abd))] = np.nan
    assert features_for(abd)["valid"] is False


def test_rep_with_few_missing_frames_is_still_valid():
    abd = synthetic_rep()
    abd[40:45] = np.nan
    f = features_for(abd)
    assert f["valid"] and f["peak_angle"] == pytest.approx(90, abs=2)


def test_rep_features_uses_frame_window():
    abd = np.r_[np.full(30, 5.0), synthetic_rep(), np.full(30, 5.0)]
    n = len(abd)
    f = S.rep_features(abd, np.full(n, 170.0), np.zeros(n), np.full(n, 0.9), 30, 119)
    assert f["n_frames"] == 90 and f["peak_angle"] == pytest.approx(90, abs=1)


# ---------- regression against the saved research table ----------

LM_CSV = "data/own/PM_000-Camera17-30fps_landmarks.csv"
FEAT_CSV = "data/own/ex1_rep_features.csv"
SEG_CSV = "data/public/rehab24_6/Segmentation.csv"
VIDEO = "data/public/rehab24_6/Videos/Ex1/PM_000-Camera17-30fps.mp4"


@pytest.mark.skipif(not all(os.path.exists(p) for p in (LM_CSV, FEAT_CSV, SEG_CSV, VIDEO)),
                    reason="local dataset files not present")
def test_matches_saved_research_features():
    """Shared code must reproduce the features the models were trained on."""
    import cv2
    cap = cv2.VideoCapture(VIDEO)
    W, H = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    abd, elbow, lean, vis = S.frame_signals(pd.read_csv(LM_CSV), W, H)
    seg = pd.read_csv(SEG_CSV, sep=None, engine="python")
    seg = seg[(seg.exercise_id == 1) & (seg.video_id == "PM_000")]
    saved = pd.read_csv(FEAT_CSV)
    saved = saved[saved.video_id == "PM_000"].set_index("rep")
    assert len(seg) > 0
    for _, r in seg.iterrows():
        f = S.rep_features(abd, elbow, lean, vis, r.first_frame, r.last_frame)
        old = saved.loc[int(r.repetition_number)]
        assert f["valid"] == bool(old["valid"])
        if f["valid"]:
            for c in S.FEATURE_NAMES:
                assert f[c] == pytest.approx(old[c], rel=1e-9), c
