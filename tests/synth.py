"""Synthetic pose frames for testing the camera check, rep counter and engine."""
import numpy as np

from features.signals import FPS, L_HIP, L_SH, R_EL, R_HIP, R_SH, R_WR

NOSE = 0
HIP_MID = np.array([0.5, 0.6])
TRUNK = 0.3
ARM = 0.15


def pose(abd_deg=10.0, lean_deg=0.0, vis=0.9, nose_y=0.1):
    """Landmark dict (normalized coords, y down) for a person facing the camera
    with the right arm abducted abd_deg and the trunk leaning lean_deg sideways."""
    phi = np.radians(lean_deg)
    mid_sh = HIP_MID + TRUNK * np.array([np.sin(phi), -np.cos(phi)])
    pts = {
        L_HIP: HIP_MID + [0.1, 0], R_HIP: HIP_MID - [0.1, 0],
        L_SH: mid_sh + [0.1, 0], R_SH: mid_sh - [0.1, 0],
        NOSE: np.array([mid_sh[0], nose_y]),
    }
    th = np.radians(abd_deg)
    # straight arm, rotated away from the body towards image-left (subject's right)
    pts[R_EL] = pts[R_SH] + ARM * np.array([-np.sin(th), np.cos(th)])
    pts[R_WR] = pts[R_SH] + 2 * ARM * np.array([-np.sin(th), np.cos(th)])
    d = {}
    for i, (x, y) in pts.items():
        d[f"x{i}"], d[f"y{i}"], d[f"v{i}"] = float(x), float(y), vis
    for i in (13, 15):   # left arm, hanging down
        d[f"x{i}"], d[f"y{i}"], d[f"v{i}"] = float(pts[L_SH][0]), float(pts[L_SH][1] + 0.15), vis
    return d


def rep_angles(duration_s=3.0, low=10.0, high=90.0, rest_s=1.0, wobble=0.0, fps=FPS):
    """Rest at `low`, one smooth up-down rep to `high`, rest again. Optional 3 Hz wobble."""
    rest = np.full(int(rest_s * fps), low)
    n = int(round(duration_s * fps))
    t = np.arange(n) / fps
    up = low + (high - low) * np.sin(np.pi * t / duration_s)
    up = up + wobble * np.sin(2 * np.pi * 3 * t) * np.sin(np.pi * t / duration_s)
    return np.r_[rest, up, rest]


def lean_profile(n_rest, n_rep, max_lean):
    """Upright at rest, leaning up to max_lean in the middle of the rep."""
    rep = max_lean * np.sin(np.pi * np.arange(n_rep) / n_rep)
    return np.r_[np.zeros(n_rest), rep, np.zeros(n_rest)]
