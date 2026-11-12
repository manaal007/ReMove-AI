"""Load config/exercises.yaml + config/thresholds.yaml into one dict."""
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TIMING_MODES = ("every_rep", "every_3_4_reps")


def load_config(exercise="E1", config_dir=CONFIG_DIR):
    config_dir = Path(config_dir)
    with open(config_dir / "exercises.yaml", encoding="utf-8") as f:
        exercises = yaml.safe_load(f)
    with open(config_dir / "thresholds.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if exercise not in exercises:
        raise KeyError(f"Unknown exercise {exercise!r}; have {list(exercises)}")
    cfg["exercise_id"] = exercise
    cfg["exercise"] = exercises[exercise]
    validate(cfg)
    return cfg


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
