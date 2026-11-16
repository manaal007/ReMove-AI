"""
Weight check before calibration: is the patient holding (E3) or wearing at the
ankle (E4) a bottle, and is it light or heavy?

Pure functions + a small vote, no camera and no model, so it is easy to test.
The bottle detector (api.object_detector.BottleDetector, MediaPipe EfficientDet-
Lite0, COCO "bottle") is called by the live session on the crop that crop_region()
returns; its boxes come back here in full-frame pixels.

Per frame (observe):
  limb  = the exercise's weight_limb from config/exercises.yaml, e.g. elbow->wrist;
          its far end (wrist / ankle) is where a weight would be
  crop  = square around that joint, crop_limb_lengths x limb length wide: the
          detector sees the bottle much bigger than in the whole frame
  a box counts when score >= min_score, its edge is within max_distance_limbs of
  the joint, and min_box_ratio <= box height / limb length <= max_box_ratio
Over the window (WeightVote, window_s from the first frame with the limb seen):
  none   fewer than min_hits frames, or under min_hit_fraction of the frames, had a box
  light  else, median box height / limb length < heavy_min_ratio[exercise]
  heavy  else

This is a suggestion: the patient confirms or corrects it, and the choice is final.
"""
from dataclasses import dataclass, field

import numpy as np

from features.signals import SIDE_LM, best_side

WEIGHT_CLASSES = ("none", "light", "heavy")


@dataclass
class Box:
    x: float          # full-frame pixels, top-left corner
    y: float
    w: float
    h: float
    score: float


def has_weight_check(ex):
    return bool(ex.get("weight_limb"))


def limb_geometry(lm, ex, W, H, side=None, min_vis=0.5):
    """(joint_xy, limb_length) in pixels for the weight limb, or None if not seen."""
    near, far = ex["weight_limb"]
    side = side or best_side(lm, ex.get("required_landmarks") or [near, far])
    pts = []
    for j in (near, far):
        i = SIDE_LM[side][j]
        x, y, v = lm.get(f"x{i}"), lm.get(f"y{i}"), lm.get(f"v{i}")
        if x is None or y is None or v is None or np.isnan(v) or v < min_vis:
            return None
        pts.append(np.array([x * W, y * H], dtype=float))
    length = float(np.linalg.norm(pts[1] - pts[0]))
    return (pts[1], length) if length > 1.0 else None


def crop_region(joint, limb, W, H, cfg):
    """Integer (x0, y0, x1, y1) of the square to run the detector on, clipped to the frame."""
    half = cfg["weight_check"]["crop_limb_lengths"] * limb / 2
    x0, y0 = int(max(0, joint[0] - half)), int(max(0, joint[1] - half))
    x1, y1 = int(min(W, joint[0] + half)), int(min(H, joint[1] + half))
    return (x0, y0, x1, y1) if x1 - x0 >= 16 and y1 - y0 >= 16 else None


def box_ratio(box, joint, limb, cfg):
    """Box height / limb length if this box counts as a weight at the joint, else None."""
    wc = cfg["weight_check"]
    if box.score < wc["min_score"]:
        return None
    dx = max(box.x - joint[0], 0.0, joint[0] - (box.x + box.w))
    dy = max(box.y - joint[1], 0.0, joint[1] - (box.y + box.h))
    if np.hypot(dx, dy) > wc["max_distance_limbs"] * limb:
        return None
    r = box.h / limb
    return r if wc["min_box_ratio"] <= r <= wc["max_box_ratio"] else None


def observe(boxes, joint, limb, cfg):
    """Best counting box's height ratio for one frame (highest score), or None."""
    best = None
    for b in boxes:
        r = box_ratio(b, joint, limb, cfg)
        if r is not None and (best is None or b.score > best[0]):
            best = (b.score, r)
    return None if best is None else best[1]


def classify(ratios, n_frames, exercise_id, cfg):
    """ratios: box ratio of each frame that had a bottle; n_frames: frames with the limb seen."""
    wc = cfg["weight_check"]
    hits = len(ratios)
    if n_frames == 0 or hits < wc["min_hits"] or hits / n_frames < wc["min_hit_fraction"]:
        return "none"
    return "heavy" if float(np.median(ratios)) >= wc["heavy_min_ratio"][exercise_id] else "light"


@dataclass
class WeightVote:
    """Collects one observation per frame for window_s seconds, then gives a suggestion."""
    cfg: dict
    exercise_id: str
    t0: float = None
    n_frames: int = 0
    ratios: list = field(default_factory=list)

    def add(self, t, ratio, limb_seen=True):
        if not limb_seen:
            return
        if self.t0 is None:
            self.t0 = t
        self.n_frames += 1
        if ratio is not None:
            self.ratios.append(float(ratio))

    def ready(self, t):
        return self.t0 is not None and t - self.t0 >= self.cfg["weight_check"]["window_s"]

    def result(self):
        suggested = classify(self.ratios, self.n_frames, self.exercise_id, self.cfg)
        return {
            "suggested": suggested,
            "frames": self.n_frames,
            "hits": len(self.ratios),
            "hit_fraction": round(len(self.ratios) / self.n_frames, 3) if self.n_frames else 0.0,
            "ratio": round(float(np.median(self.ratios)), 3) if self.ratios else None,
        }
