"""
Six-label rules for v1 (no ML).

  not_tracked         rep features invalid (too many missing frames) or tracking lost mid-rep
  trunk_compensation  E1: trunk_lean_max > exercise max_trunk_lean_deg (sideways lean)
                      E4 (absolute): comp_change_max > compensation.max_change_deg
                          (leaning back: trunk angle change during the rep)
                      E3 (relative): comp_change_max > baseline comp_change_max
                          + compensation.baseline_margin_deg (upper arm swing: shoulder
                          angle). Most people swing the upper arm a little on every
                          curl (own volunteers: 17-32 deg), so only extra swing counts.
  too_fast            duration_s < too_fast_frac   * baseline duration_s
  jerky               sparc      < jerky_sparc_ratio * baseline sparc
                      (SPARC is negative, so this means "ratio times less smooth";
                       per-phase spectral arc length, independent of rep duration)
  reduced_range       rom        < reduced_range_frac * reference range, where
                      reference = min(baseline rom, max_safe_deg - baseline rest angle)
                      so the target never goes above max_safe_deg; also never
                      fired if the peak already reached max_safe_deg
  good                none of the above

The baseline is the median of the person's clean calibration reps. Only the
two absolute rules (not_tracked, trunk_compensation) can be checked before a
baseline exists, so those are what decide if a calibration rep is clean.
E3's relative swing rule needs a baseline, so it cannot fire on calibration reps
(the baseline swing is a median, so one big swing there moves it little).

Jerky used to compare dimensionless jerk (jerk_norm) with the baseline, but
tracking noise makes jerk_norm grow roughly with duration^6, so slow smooth reps
were flagged (6.2 s vs a 4.2 s baseline -> ~10x). SPARC per phase stays flat
across 2.5-8 s on smooth synthetic reps with realistic noise. Cut-off 1.4x own
baseline: on REHAB24-6 Ex1 it flags 0% of correct reps and 10% of incorrect ones
(labeled rep windows, baseline = median of first 3 correct reps per video, those
reps not scored). It was 1.2x (0% / 24%), but live normal reps reached 1.21-1.24x
and were flagged, while a real jerky rep was 1.75x.
"""
from collections import Counter

import numpy as np

BASELINE_KEYS = ("rom", "duration_s", "jerk_norm", "sparc", "peak_angle", "min_angle")
OPTIONAL_BASELINE_KEYS = ("comp_change_max",)    # side-view exercises only (E3 swing rule)
ABSOLUTE = ("not_tracked", "trunk_compensation")


def build_baseline(feature_list):
    """Median of each baseline key over clean calibration reps (missing values skipped).
    Optional keys are added only when the features have them, so E1 baselines are unchanged."""
    out = {}
    keys = BASELINE_KEYS + tuple(k for k in OPTIONAL_BASELINE_KEYS if any(k in f for f in feature_list))
    for k in keys:
        vals = [f[k] for f in feature_list if f.get(k) is not None and not np.isnan(f[k])]
        out[k] = float(np.median(vals)) if vals else None
    return out


def reference_rom(baseline, cfg):
    """Range a rep is compared with: the person's own baseline range, capped so
    that reaching it never needs more than max_safe_deg from their rest angle."""
    return min(baseline["rom"], cfg["exercise"]["max_safe_deg"] - baseline["min_angle"])


def _is_jerky(feat, baseline, ratio):
    """SPARC is negative; jerky = more than `ratio` times less smooth than baseline.
    Skipped when either value is missing (very short phase, or an older baseline
    saved before SPARC existed)."""
    s, b = feat.get("sparc"), (baseline or {}).get("sparc")
    if s is None or b is None or np.isnan(s) or np.isnan(b):
        return False
    return s < ratio * b


def _is_compensating(feat, ex, baseline=None):
    comp = ex.get("compensation")
    if not comp:                                   # E1
        return feat["trunk_lean_max"] > ex["max_trunk_lean_deg"]
    swing = feat["comp_change_max"]
    if "baseline_margin_deg" in comp:              # E3: relative to the person's own swing
        b = (baseline or {}).get("comp_change_max")
        if b is None or np.isnan(b):               # calibration, or a baseline saved without it
            return False
        return swing > b + comp["baseline_margin_deg"]
    return swing > comp["max_change_deg"]          # E4: absolute


def find_faults(feat, cfg, baseline=None):
    """All faults that fire for this rep, in cfg priority order (empty = good)."""
    rules, ex = cfg["rules"], cfg["exercise"]
    fired = set()
    if not feat.get("valid", False):
        fired.add("not_tracked")
    else:
        if _is_compensating(feat, ex, baseline):
            fired.add("trunk_compensation")
        if baseline is not None:
            if feat["duration_s"] < rules["too_fast_frac"] * baseline["duration_s"]:
                fired.add("too_fast")
            if _is_jerky(feat, baseline, rules["jerky_sparc_ratio"]):
                fired.add("jerky")
            if (feat["rom"] < rules["reduced_range_frac"] * reference_rom(baseline, cfg)
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
