"""
Run the live session engine over our own side-view recordings (E3 elbow curl,
E4 seated knee extension) and compare the reps it finds with the manifest.

Data: data/own/landmarks/manifest.csv + *_landmarks.csv (MediaPipe, one row per
video frame, with time_s). One clip is 240 fps slow motion, so frames are picked
by time_s, never by frame count: the engine is fed one frame every 1/fps seconds
of real time, like the browser app (it sends at most 15 frames per second).

The videos themselves are not in the repo, so the frame size is assumed:
portrait phone video, 1080 x 1920. (Fitting the constant forearm / shin length
gives width/height 0.50-0.70 on every usable clip, i.e. portrait.)

Two modes:
  full        (default) the whole live pipeline: camera check -> baseline -> scoring.
              A clip whose framing fails the camera check never starts, as in the app.
  count-only  (--count-only) skip the camera check: the counter starts on the first
              frame, on the side seen best over the whole clip. Shows what the rep
              counter does even when the framing would be rejected live.

Run from inside remove-pk:
    python research/eval_own_landmarks.py               # 15 fps (live app rate)
    python research/eval_own_landmarks.py --fps 30
    python research/eval_own_landmarks.py --count-only
    python research/eval_own_landmarks.py --all         # also the unusable clips
"""
import argparse
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
from features.signals import ALL_LM, best_side  # noqa: E402
from session.config import load_config  # noqa: E402
from session.engine import SessionEngine  # noqa: E402
from session.rep_counter import RepCounter  # noqa: E402

DATA_DIR = os.path.join("data", "own", "landmarks")
MANIFEST = os.path.join(DATA_DIR, "manifest.csv")
W, H = 1080, 1920
GRAY = 128.0          # no video, so brightness is assumed fine


def frames_by_time(df, fps):
    """Rows picked every 1/fps seconds of time_s (all rows if fps is None)."""
    if fps is None:
        return df
    t = df["time_s"].to_numpy()
    keep, next_t = [], t[0]
    for i, ti in enumerate(t):
        if ti >= next_t - 1e-9:
            keep.append(i)
            next_t = ti + 1.0 / fps
    return df.iloc[keep]


def _skip_camera_check(e, side):
    """Research only: start counting at once, as if the camera check had passed."""
    e.checking = False
    e.counter = RepCounter(e.cfg)
    e.phase = "baseline"
    if e.side_view:
        e.side = e.log.side = side


def run_file(path, exercise, fps=15.0, width=W, height=H, cfg=None, count_only=False):
    """Feed one landmark CSV to a fresh engine. Returns (engine, frames fed)."""
    cfg = cfg or load_config(exercise)
    raw = pd.read_csv(path)
    df = frames_by_time(raw, fps)
    cols = [f"{c}{i}" for i in ALL_LM for c in "xyv"]
    X = df[cols].to_numpy(dtype=float)
    T = df["time_s"].to_numpy(dtype=float)
    e = SessionEngine(cfg, width, height, language="en", timing="every_rep")
    if count_only:
        req = cfg["exercise"].get("required_landmarks")
        _skip_camera_check(e, best_side(raw, req) if req else None)
    for t, row in zip(T, X):
        lm = None if np.isnan(row[0]) else dict(zip(cols, row))
        e.process(float(t), lm, GRAY)
        if e.done:
            break
    e.stop("video_ended")
    return e, len(df)


def summarize(e):
    reps = e.log.reps
    start = next((p["t"] for p in e.log.prompts if p["key"] == "start"), None)
    return {
        "side": e.log.side,
        "start_s": start,
        "found": len(reps),
        "labels": Counter(r["label"] for r in reps),
        "baseline_restarts": e.log.baseline_restarts,
        "camera_prompts": Counter(p["key"] for p in e.log.prompts if p["reason"] == "camera"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=float, default=15.0, help="frames per second fed to the engine (0 = every row)")
    ap.add_argument("--all", action="store_true", help="include clips marked usable=no")
    ap.add_argument("--count-only", action="store_true", help="skip the camera check (see above)")
    args = ap.parse_args()
    fps = args.fps or None

    m = pd.read_csv(MANIFEST)
    if not args.all:
        m = m[m["usable"] != "no"]
    mode = "count-only (no camera check)" if args.count_only else "full pipeline"
    print(f"{mode}; engine fed at {fps or 'native'} fps by time_s; frame size assumed {W}x{H}\n")
    print(f"{'file':28s} {'ex':3s} {'usable':6s} {'side':5s} {'start':>5s} {'manifest':>8s} {'found':>5s}  labels")
    for _, r in m.iterrows():
        ex = r["exercise"].split("_")[0]
        e, _ = run_file(os.path.join(DATA_DIR, r["file"]), ex, fps, count_only=args.count_only)
        s = summarize(e)
        labels = ", ".join(f"{k} {v}" for k, v in s["labels"].most_common())
        extra = f"  [camera: {dict(s['camera_prompts'])}]" if s["camera_prompts"] else ""
        start = f"{s['start_s']:.1f}" if s["start_s"] is not None else "-"
        print(f"{r['file']:28s} {ex:3s} {r['usable']:6s} {str(s['side']):5s} {start:>5s} "
              f"{str(r['reps_approx']):>8s} {s['found']:5d}  {labels}{extra}")


if __name__ == "__main__":
    main()
