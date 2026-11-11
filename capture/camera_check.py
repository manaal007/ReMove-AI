"""
Per-frame camera check: light, is the person tracked, are they framed right.

Pure function, no camera access, so it is easy to test. The session engine
calls it every frame and only starts (or resumes) once it has passed for
camera_check.pass_frames frames in a row.

Issues, in the order they are reported (only the first one is spoken):
  too_dark / too_bright  - mean gray level outside brightness limits
  not_tracked            - no pose found at all
  step_back              - a required landmark is cut off or poorly seen
  come_closer            - person too small: head-to-hips below min_body_height_fraction
"""
import numpy as np

LANDMARK_IDS = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
}
NOSE, L_HIP, R_HIP = 0, 23, 24


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


def check_frame(lm, gray, cfg):
    """
    lm   : dict of one frame's landmarks {"x12": .., "y12": .., "v12": ..}, or None if no pose
    gray : mean gray level of the frame (see mean_gray)
    cfg  : merged config from session.config.load_config
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
    required = [LANDMARK_IDS[n] for n in cfg["visibility"]["required_landmarks"]]
    if not all(_visible(lm, i, min_vis) for i in required):
        issues.append("step_back")
        return issues

    # head-to-hips height as a share of frame height (needs the nose too)
    if _visible(lm, NOSE, min_vis):
        hip_y = (lm[f"y{L_HIP}"] + lm[f"y{R_HIP}"]) / 2
        if hip_y - lm[f"y{NOSE}"] < cfg["framing"]["min_body_height_fraction"]:
            issues.append("come_closer")
    return issues
