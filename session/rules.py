"""
Six-label rules for v1 (no ML).

  not_tracked         rep features invalid (too many missing frames) or tracking lost mid-rep
  trunk_compensation  trunk_lean_max > exercise max_trunk_lean_deg
  too_fast            duration_s < too_fast_frac   * baseline duration_s
  jerky               jerk_norm  > jerky_ratio     * baseline jerk_norm
  reduced_range       rom        < reduced_range_frac * baseline rom
                      (never fired if the peak already reached max_safe_deg:
                       we never ask for more than that)
  good                none of the above

The baseline is the median of the person's clean calibration reps. Only the
two absolute rules (not_tracked, trunk_compensation) can be checked before a
baseline exists, so those are what decide if a calibration rep is clean.

Starting cut-off for jerky (3x own baseline): on REHAB24-6 Ex1 it flags 2% of
correct reps and 48% of incorrect ones (data/own/ex1_rep_features.csv,
baseline = median of first 3 correct reps per video, those reps not scored).
"""
from collections import Counter

import numpy as np

BASELINE_KEYS = ("rom", "duration_s", "jerk_norm", "peak_angle", "min_angle")
ABSOLUTE = ("not_tracked", "trunk_compensation")


def build_baseline(feature_list):
    """Median of each baseline key over clean calibration reps."""
    return {k: float(np.median([f[k] for f in feature_list])) for k in BASELINE_KEYS}


def find_faults(feat, cfg, baseline=None):
    """All faults that fire for this rep, in cfg priority order (empty = good)."""
    rules, ex = cfg["rules"], cfg["exercise"]
    fired = set()
    if not feat.get("valid", False):
        fired.add("not_tracked")
    else:
        if feat["trunk_lean_max"] > ex["max_trunk_lean_deg"]:
            fired.add("trunk_compensation")
        if baseline is not None:
            if feat["duration_s"] < rules["too_fast_frac"] * baseline["duration_s"]:
                fired.add("too_fast")
            if feat["jerk_norm"] > rules["jerky_ratio"] * baseline["jerk_norm"]:
                fired.add("jerky")
            if (feat["rom"] < rules["reduced_range_frac"] * baseline["rom"]
                    and feat["peak_angle"] < ex["max_safe_deg"]):
                fired.add("reduced_range")
    return [f for f in rules["priority"] if f in fired]


def label_rep(feat, cfg, baseline=None):
    faults = find_faults(feat, cfg, baseline)
    return (faults[0] if faults else "good"), faults


def summarize_block(labels, priority):
    """Most common fault in a block of rep labels; ties go to the higher-priority
    fault; 'good' only if no rep in the block had a fault."""
    faults = Counter(l for l in labels if l != "good")
    if not faults:
        return "good"
    top = max(faults.values())
    return next(p for p in priority if faults.get(p) == top)
