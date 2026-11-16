"""
Per-frame camera check: light, is the person tracked, are they framed right.

Pure function, no camera access, so it is easy to test. The session engine
calls it every frame and only starts (or resumes) once it has passed for
camera_check.pass_frames frames in a row.

Issues, in the order they are reported (only the first one is spoken):
  too_dark / too_bright  - mean gray level outside brightness limits
  not_tracked            - no pose found at all
  show_left_side /       - side-view exercises with the patient's side given: the OTHER side
  show_right_side          faces the camera (its joints are clearly better seen)
  step_back              - a required landmark is cut off or poorly seen
  turn_sideways          - side-view exercises only: the person faces the camera
                           (shoulder width / torso length above side_view.max_shoulder_torso_ratio)
  come_closer            - person too small: head-to-hips below min_body_height_fraction

Front-view exercises (E1) check visibility.required_landmarks. Side-view
exercises (side: auto, E3/E4) check the exercise's required_landmarks on one
side: the patient's weak side (wanted_side, from the health form), else the
side passed in, else whichever side is better seen in this frame.
"""
import numpy as np

from features.signals import SIDE_LM, best_side
from session.config import is_side_view

LANDMARK_IDS = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}
NOSE, L_SH, R_SH, L_HIP, R_HIP = 0, 11, 12, 23, 24


def mean_gray(frame_bgr):
    """Mean brightness 0..255 of a BGR frame (same weights as cv2 BGR2GRAY)."""
    f = np.asarray(frame_bgr, dtype=np.float32)
    return float((f[..., 0] * 0.114 + f[..., 1] * 0.587 + f[..., 2] * 0.299).mean())


def _in_frame(lm, i):
    x, y = lm.get(f"x{i}"), lm.get(f"y{i}")
    return x is not None and y is not None and 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0


def _visible(lm, i, min_vis):
    v = lm.get(f"v{i}")
    return v is not None and not np.isnan(v) and v >= min_vis and _in_frame(lm, i)


def required_ids(cfg, side=None, lm=None):
    """Landmark ids that must be visible. Side-view: the chosen side's joints."""
    ex = cfg["exercise"]
    if not is_side_view(ex):
        return [LANDMARK_IDS[n] for n in cfg["visibility"]["required_landmarks"]]
    side = side or best_side(lm, ex["required_landmarks"])
    return [SIDE_LM[side][j] for j in ex["required_landmarks"]]


def shoulder_torso_ratio(lm, aspect):
    """Shoulder width / torso length in pixels (aspect = frame width / height).
    About 0.65-0.75 facing the camera, below about 0.4 side-on. None if unknown."""
    try:
        sx = (lm[f"x{L_SH}"] - lm[f"x{R_SH}"]) * aspect
        sy = lm[f"y{L_SH}"] - lm[f"y{R_SH}"]
        tx = ((lm[f"x{L_SH}"] + lm[f"x{R_SH}"]) - (lm[f"x{L_HIP}"] + lm[f"x{R_HIP}"])) / 2 * aspect
        ty = ((lm[f"y{L_SH}"] + lm[f"y{R_SH}"]) - (lm[f"y{L_HIP}"] + lm[f"y{R_HIP}"])) / 2
    except (KeyError, TypeError):
        return None
    torso = float(np.hypot(tx, ty))
    r = float(np.hypot(sx, sy)) / torso if torso > 0 else np.nan
    return None if np.isnan(r) else r


def _mean_vis(lm, ids):
    v = [lm.get(f"v{i}") for i in ids]
    v = [0.0 if x is None or np.isnan(x) else float(x) for x in v]
    return sum(v) / len(v)


def wrong_side_facing(lm, cfg, wanted_side):
    """True if the other side faces the camera: all its required joints are seen and
    their mean visibility beats the wanted side's by side_view.wrong_side_margin.
    Visibility only, not "inside the frame": a near-side shoulder just past the edge
    (seated E4 clips) must still count, or the far leg would be measured."""
    ex = cfg["exercise"]
    other = "left" if wanted_side == "right" else "right"
    min_vis = cfg["visibility"]["min_landmark_visibility"]
    want_ids = [SIDE_LM[wanted_side][j] for j in ex["required_landmarks"]]
    other_ids = [SIDE_LM[other][j] for j in ex["required_landmarks"]]
    if min(_mean_vis(lm, [i]) for i in other_ids) < min_vis:
        return False
    return _mean_vis(lm, other_ids) - _mean_vis(lm, want_ids) > cfg["side_view"]["wrong_side_margin"]


def check_frame(lm, gray, cfg, side=None, aspect=None, wanted_side=None):
    """
    lm     : dict of one frame's landmarks {"x12": .., "y12": .., "v12": ..}, or None if no pose
    gray   : mean gray level of the frame (see mean_gray)
    cfg    : merged config from session.config.load_config
    side   : side-view exercises: 'left' / 'right', or None = better-seen side of this frame
    aspect : frame width / height, for the side-on check (skipped if None)
    wanted_side : side-view exercises: the patient's weak side; overrides `side` and adds
             the show_<side>_side check
    Returns a list of issue codes; empty list = frame is OK.
    """
    issues = []
    br = cfg["brightness"]
    if gray < br["min_mean_gray"]:
        issues.append("too_dark")
    elif gray > br["max_mean_gray"]:
        issues.append("too_bright")

    if lm is None:
        issues.append("not_tracked")
        return issues

    min_vis = cfg["visibility"]["min_landmark_visibility"]
    if wanted_side and is_side_view(cfg["exercise"]):
        side = wanted_side
        if wrong_side_facing(lm, cfg, wanted_side):
            issues.append(f"show_{wanted_side}_side")
            return issues
    required = required_ids(cfg, side, lm)
    if not all(_visible(lm, i, min_vis) for i in required):
        issues.append("step_back")
        return issues

    if is_side_view(cfg["exercise"]) and aspect:
        r = shoulder_torso_ratio(lm, aspect)
        if r is not None and r > cfg["side_view"]["max_shoulder_torso_ratio"]:
            issues.append("turn_sideways")
            return issues

    # head-to-hips height as a share of frame height (needs the nose too)
    if _visible(lm, NOSE, min_vis):
        hip_y = (lm[f"y{L_HIP}"] + lm[f"y{R_HIP}"]) / 2
        if hip_y - lm[f"y{NOSE}"] < cfg["framing"]["min_body_height_fraction"]:
            issues.append("come_closer")
    return issues
