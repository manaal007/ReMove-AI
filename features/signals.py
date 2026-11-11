"""
Shared movement signal code for E1 (right shoulder abduction).

Used by both the offline research scripts (features/build_features_ex1.py,
research/EXP-3/compression_test.py) and the live session, so the app scores
reps with exactly the same math the models were tested on.

All angles are in degrees. Landmarks come as a DataFrame with columns
x{i}, y{i}, v{i} (MediaPipe normalized coords + visibility), one row per frame.
"""
import numpy as np
import pandas as pd

FPS = 30.0
MIN_VIS = 0.5          # thresholds.yaml: visibility.min_landmark_visibility
SMOOTH = 5             # thresholds.yaml: tracking.smoothing_window
MAX_NAN_FRAC = 0.2     # rep is invalid if more than this share of frames is missing
MIN_REP_FRAMES = 10

# numpy 2 renamed trapz to trapezoid
_trapz = getattr(np, "trapezoid", None) or np.trapz

# MediaPipe landmark ids (subject's own left/right)
L_SH, R_SH, R_EL, R_WR, L_HIP, R_HIP = 11, 12, 14, 16, 23, 24
REQUIRED_LM = [R_SH, R_EL, R_WR, R_HIP, L_SH, L_HIP]

FEATURE_NAMES = ["duration_s", "peak_angle", "rom", "peak_speed", "mean_speed",
                 "jerk_norm", "elbow_min", "elbow_mean", "trunk_lean_max", "trunk_lean_range"]


def angle_at(b, a, c):
    """Angle at point b between b->a and b->c, arrays (N,2) in pixels."""
    v1, v2 = a - b, c - b
    n = np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1)
    cos = (v1 * v2).sum(axis=1) / np.where(n == 0, np.nan, n)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def frame_signals(lm, W, H, min_vis=MIN_VIS):
    """Per-frame abduction angle, elbow angle and trunk lean (all degrees), plus
    the lowest visibility of the required landmarks. Frames where any required
    landmark is below min_vis get NaN angles."""
    def P(i):
        return np.c_[lm[f"x{i}"].values * W, lm[f"y{i}"].values * H].astype(float)

    abd = angle_at(P(R_SH), P(R_HIP), P(R_EL))       # hip-shoulder-elbow
    elbow = angle_at(P(R_EL), P(R_SH), P(R_WR))      # shoulder-elbow-wrist
    mid_sh = (P(L_SH) + P(R_SH)) / 2
    mid_hip = (P(L_HIP) + P(R_HIP)) / 2
    trunk = mid_sh - mid_hip                         # points from hips up to shoulders
    lean = np.degrees(np.arctan2(trunk[:, 0], -trunk[:, 1]))  # 0 = upright

    vis = lm[[f"v{i}" for i in REQUIRED_LM]].astype(float).min(axis=1).values
    bad = ~(vis >= min_vis)                          # NaN visibility counts as bad
    for s in (abd, elbow, lean):
        s[bad] = np.nan
    return abd, elbow, lean, vis


def smooth(x, window=SMOOTH):
    """Fill gaps by interpolation, then centered moving average."""
    return pd.Series(x).interpolate(limit_direction="both").rolling(
        window, center=True, min_periods=1).mean().values


def rep_features(abd, elbow, lean, vis, f0, f1, fps=FPS, window=SMOOTH):
    """Features for one rep spanning frames f0..f1 (inclusive)."""
    sl = slice(int(f0), int(f1) + 1)
    a, e, l, v = abd[sl], elbow[sl], lean[sl], vis[sl]
    nan_frac = float(np.mean(np.isnan(a))) if len(a) else 1.0
    out = {"n_frames": len(a), "nan_frac": nan_frac,
           "vis_mean": float(np.nanmean(v)) if len(v) and not np.all(np.isnan(v)) else np.nan}
    if len(a) < MIN_REP_FRAMES or nan_frac > MAX_NAN_FRAC:
        out["valid"] = False
        return out
    a, e, l = smooth(a, window), smooth(e, window), smooth(l, window)
    dt = 1 / fps
    vel = np.gradient(a, dt)
    acc = np.gradient(vel, dt)
    jerk = np.gradient(acc, dt)
    dur = len(a) * dt
    rom = a.max() - a.min()
    out.update({
        "valid": True,
        "duration_s": dur,
        "peak_angle": a.max(),
        "min_angle": a.min(),
        "rom": rom,
        "peak_speed": np.abs(vel).max(),
        "mean_speed": np.abs(vel).mean(),
        # dimensionless jerk: lower = smoother, comparable across speeds and sizes
        "jerk_norm": (_trapz(jerk ** 2, dx=dt) * dur ** 5) / (rom ** 2 + 1e-9),
        "elbow_min": e.min(),
        "elbow_mean": e.mean(),
        # trunk lean relative to the lean at the start of the rep (removes camera tilt)
        "trunk_lean_max": np.abs(l - l[:5].mean()).max(),
        "trunk_lean_range": l.max() - l.min(),
    })
    return out
