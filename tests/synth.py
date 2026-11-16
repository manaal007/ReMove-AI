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


SIDE_W, SIDE_H = 1080, 1920     # portrait phone frame, like the own recordings
_SIDE_IDS = {"left": dict(shoulder=11, elbow=13, wrist=15, hip=23, knee=25, ankle=27),
             "right": dict(shoulder=12, elbow=14, wrist=16, hip=24, knee=26, ankle=28)}


def _unit(deg_from_down):
    """Unit vector in pixels (y down): 0 = straight down, +90 = forward (+x)."""
    a = np.radians(deg_from_down)
    return np.array([np.sin(a), np.cos(a)])


def side_pose(exercise="E3", angle=10.0, comp=0.0, side="right", vis=0.9, far_vis=0.3,
              facing_camera=False, ankle_y=None, W=SIDE_W, H=SIDE_H):
    """Landmark dict for a person side-on to the camera, facing image-right.

    E3 (standing elbow curl): angle = elbow flexion (0 straight, 90 forearm forward),
        comp = upper arm swung forward from hanging (= hip-shoulder-elbow angle).
    E4 (seated knee extension): angle = hip-knee-ankle (90 shin down, 180 leg straight),
        comp = trunk leaning back from upright (= trunk angle change).
    `side` is the side facing the camera (well seen, vis); the other side gets far_vis.
    facing_camera=True spreads the shoulders/hips like a front view (for turn_sideways).
    ankle_y: force the ankle's normalized y (e.g. 1.05 = cut off at the bottom)."""
    if exercise == "E3":
        hip = np.array([540.0, 1150.0])
        sh = hip + [0.0, -520.0]                  # torso 520 px, upright
        el = sh + 300 * _unit(comp)               # upper arm: hanging, swung forward by comp
        wr = el + 270 * _unit(comp + angle)       # forearm: bent forward by angle
        kn, an = hip + [0.0, 420.0], hip + [0.0, 800.0]
    else:
        hip = np.array([420.0, 1000.0])
        sh = hip + 520 * _unit(180 + comp)        # straight up, tilted back (-x) by comp
        el, wr = sh + [0.0, 280.0], sh + [0.0, 540.0]
        kn = hip + [380.0, 0.0]                   # thigh level, forward
        an = kn + 380 * _unit(angle - 90)         # shin: down at 90, forward at 180
    px = dict(shoulder=sh, elbow=el, wrist=wr, hip=hip, knee=kn, ankle=an)
    # far side: almost behind the near side when side-on; spread out when facing the camera
    near_dx, far_dx = (180.0, -180.0) if facing_camera else (0.0, -12.0)
    d = {}
    for s, ids in _SIDE_IDS.items():
        near = s == side
        shift = np.array([near_dx if near else far_dx, 0.0])
        for j, i in ids.items():
            x, y = (px[j] + shift) / [W, H]
            if j == "ankle" and ankle_y is not None:
                y = ankle_y
            d[f"x{i}"], d[f"y{i}"], d[f"v{i}"] = float(x), float(y), vis if near else far_vis
    nose = (px["shoulder"] + [60.0, -200.0]) / [W, H]
    d["x0"], d["y0"], d["v0"] = float(nose[0]), float(nose[1]), vis
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
