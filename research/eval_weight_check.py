"""
Weight check (capture/weight_check.py) on our own raw clips.

data/own/raw/<name>.mp4 + data/own/landmarks/<name>_landmarks.csv (pose from the same
decoded frames) + manifest weight_seen: bottle_in_hand / bottles_tied_at_ankle / none.
Frames are fed at --fps by time_s, like the browser app. The live check uses one
window_s window from the start; here it is also run from several later start times
(every --step s) to see how stable the suggestion is (the clips are mid-exercise,
while a live patient stands still during the check).

Run from inside remove-pk:
    python research/eval_weight_check.py
"""
import argparse
import json
import os
import sys
from collections import Counter

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
from api.object_detector import BottleDetector  # noqa: E402
from capture.weight_check import WeightVote, crop_region, limb_geometry, observe  # noqa: E402
from features.signals import ALL_LM, best_side  # noqa: E402
from session.config import load_config  # noqa: E402

RAW = os.path.join("data", "own", "raw")
LMS = os.path.join("data", "own", "landmarks")


def truth(weight_seen):
    return "none" if weight_seen == "none" else "weight"


def clip_observations(name, ex_id, fps, detector, max_t=None):
    """Per sampled frame: (t, limb_seen, ratio), for the whole clip or up to max_t seconds."""
    cfg = load_config(ex_id)
    ex = cfg["exercise"]
    lm = pd.read_csv(os.path.join(LMS, f"{name}_landmarks.csv"))
    side = best_side(lm, ex["required_landmarks"])
    cols = [f"{c}{i}" for i in ALL_LM for c in "xyv"]
    cap = cv2.VideoCapture(os.path.join(RAW, f"{name}.mp4"))
    out, next_t = [], 0.0
    for i, t in enumerate(lm["time_s"].to_numpy()):
        if max_t is not None and t > max_t:
            break
        ok, frame = cap.read()
        if not ok:
            break
        if t < next_t - 1e-9:
            continue
        next_t = t + 1.0 / fps
        H, W = frame.shape[:2]
        row = {c: float(v) for c, v in zip(cols, lm.iloc[i][cols])}
        geo = limb_geometry(row, ex, W, H, side=side)
        if geo is None:
            out.append((t, False, None))
            continue
        region = crop_region(geo[0], geo[1], W, H, cfg)
        if region is None:
            out.append((t, False, None))
            continue
        boxes = detector.detect(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), region)
        out.append((t, True, observe(boxes, geo[0], geo[1], cfg)))
    cap.release()
    return cfg, out


def vote(cfg, ex_id, obs, start):
    v = WeightVote(cfg, ex_id)
    for t, seen, r in obs:
        if t < start:
            continue
        v.add(t, r, seen)
        if v.ready(t):
            return v.result()
    return None                         # clip ended before the window was full


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--step", type=float, default=4.0, help="seconds between window starts")
    args = ap.parse_args()
    m = pd.read_csv(os.path.join(LMS, "manifest.csv"))
    det = BottleDetector(load_config("E3")["weight_check"]["model"])
    rows, cache = [], {}
    for _, r in m.iterrows():
        name = r["file"].replace("_landmarks.csv", "")
        if not os.path.exists(os.path.join(RAW, f"{name}.mp4")):
            continue
        ex_id = r["exercise"].split("_")[0]
        cfg, obs = clip_observations(name, ex_id, args.fps, det)
        cache[name] = {"ex": ex_id, "truth": r["weight_seen"], "obs": obs}
        dur = obs[-1][0] if obs else 0
        first = vote(cfg, ex_id, obs, 0.0)
        windows = [w for s in np.arange(0, max(dur, 0.1), args.step) if (w := vote(cfg, ex_id, obs, s))]
        c = Counter(w["suggested"] for w in windows)
        rows.append({"clip": name, "ex": ex_id, "who": r["volunteer"], "truth": r["weight_seen"],
                     "usable": r["usable"], "first_window": first["suggested"] if first else "-",
                     "hits": f"{first['hits']}/{first['frames']}" if first else "-",
                     "ratio": first["ratio"] if first else None,
                     "windows": len(windows), **{k: c.get(k, 0) for k in ("none", "light", "heavy")}})
    det.close()
    with open(os.path.join("data", "own", "weight_check_observations.json"), "w") as f:
        json.dump(cache, f)          # per-frame (t, limb_seen, ratio): re-vote without the detector
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join("data", "own", "weight_check_results.csv"), index=False)
    print(df.to_string(index=False))
    ok = df[df["first_window"] != "-"]
    right = (ok["first_window"] == "none") == (ok["truth"] == "none")
    print(f"\nfirst window: weight vs none right on {int(right.sum())}/{len(ok)} clips")
    tot = df[["none", "light", "heavy"]].sum(axis=1)
    wanted = np.where(df["truth"] == "none", df["none"], df["light"] + df["heavy"])
    print(f"all windows: right on {int(wanted.sum())}/{int(tot.sum())}")


if __name__ == "__main__":
    main()
