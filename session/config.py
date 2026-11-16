"""Load config/exercises.yaml + config/thresholds.yaml into one dict.

An exercise may carry `overrides:` (same layout as thresholds.yaml); those
values replace the shared thresholds for that exercise only.
"""
import copy
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TIMING_MODES = ("every_rep", "every_3_4_reps")
SIDE_JOINTS = ("shoulder", "elbow", "wrist", "hip", "knee", "ankle")
PRIMARY_ANGLES = ("elbow_flexion", "knee_angle")
COMPENSATION_SIGNALS = ("shoulder_angle", "trunk_angle")


def load_config(exercise="E1", config_dir=CONFIG_DIR):
    config_dir = Path(config_dir)
    with open(config_dir / "exercises.yaml", encoding="utf-8") as f:
        exercises = yaml.safe_load(f)
    with open(config_dir / "thresholds.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if exercise not in exercises:
        raise KeyError(f"Unknown exercise {exercise!r}; have {list(exercises)}")
    ex = exercises[exercise]
    _deep_update(cfg, copy.deepcopy(ex.get("overrides") or {}))
    cfg["exercise_id"] = exercise
    cfg["exercise"] = ex
    validate(cfg)
    return cfg


def is_side_view(ex):
    """Side-view exercises pick the better-seen body side themselves (side: auto)."""
    return ex.get("side") == "auto"


def _deep_update(base, upd):
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def validate(cfg):
    fb = cfg["feedback"]
    if fb["timing"] not in TIMING_MODES:
        raise ValueError(f"feedback.timing must be one of {TIMING_MODES}, got {fb['timing']!r}")
    if fb["block_size"] not in (3, 4):
        raise ValueError("feedback.block_size must be 3 or 4")
    b = cfg["baseline"]
    if not 1 <= b["min_reps"] <= b["max_reps"]:
        raise ValueError("baseline: need 1 <= min_reps <= max_reps")
    if cfg["caps"]["max_reps_per_set"] < 1:
        raise ValueError("caps.max_reps_per_set must be at least 1 (scored reps, baseline not counted)")
    ex = cfg["exercise"]
    if is_side_view(ex):
        if ex.get("primary_angle") not in PRIMARY_ANGLES:
            raise ValueError(f"primary_angle must be one of {PRIMARY_ANGLES}")
        comp = ex.get("compensation") or {}
        if comp.get("signal") not in COMPENSATION_SIGNALS or not comp.get("max_change_deg"):
            raise ValueError(f"compensation needs signal in {COMPENSATION_SIGNALS} and max_change_deg")
        req = ex.get("required_landmarks") or []
        if not req or any(j not in SIDE_JOINTS for j in req):
            raise ValueError(f"required_landmarks must be a non-empty list of {SIDE_JOINTS}")
