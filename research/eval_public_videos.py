"""
Pose extraction + E3/E4 rep counting on public exercise videos.

  1. extract: every video under --videos (one sub-folder per class) -> MediaPipe
     landmarks CSV under --out/landmarks/<class>/<name>_landmarks.csv (skipped if it
     exists). The size of the DECODED frames (after OpenCV's auto-rotation, i.e. what
     MediaPipe saw) is recorded in --out/videos.csv with fps and duration.
  2. evaluate: each landmarks file is run through the session engine (research/
     eval_own_landmarks.run_file) for the exercise its class maps to, in both modes:
       full        camera check -> baseline -> scoring (what the app would do)
       count-only  no camera check, side = better-seen side over the clip
     plus the clip's camera view: median shoulder width / torso length
     (side-on below side_view.max_shoulder_torso_ratio, 0.6).
     Results: --out/results.csv. Optional --labels CSV (file,label with good/bad)
     is merged in so form labels can be compared with our rule labels.

Run from inside remove-pk:
    python research/eval_public_videos.py --videos data/public/kaggle_workout \\
        --out data/public/kaggle_workout --map "barbell biceps curl=E3" "hammer curl=E3" "leg extension=E4"
"""
import argparse
import glob
import os
import sys
from collections import Counter

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
from capture.camera_check import shoulder_torso_ratio  # noqa: E402
from research.eval_own_landmarks import drop_offscreen_trunk_flags, run_file  # noqa: E402
from session.config import load_config  # noqa: E402

VIDEO_EXT = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")


def video_info(path):
    """Decoded frame size (after auto-rotation), fps, frame count, duration."""
    cap = cv2.VideoCapture(path)
    ok, frame = cap.read()
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    if not ok:
        return None
    h, w = frame.shape[:2]
    return {"width": w, "height": h, "fps": fps, "n_frames": n, "duration_s": n / fps if fps else np.nan}


def list_videos(root):
    out = []
    for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if p.lower().endswith(VIDEO_EXT) and os.sep + "landmarks" + os.sep not in p:
            out.append((os.path.basename(os.path.dirname(p)), p))
    return out


def landmarks_path(out_root, cls, video):
    name = os.path.splitext(os.path.basename(video))[0]
    return os.path.join(out_root, "landmarks", cls, f"{name}_landmarks.csv")


def extract_all(videos, out_root):
    from pose.extract_landmarks import extract
    rows = []
    for i, (cls, v) in enumerate(videos, 1):
        info = video_info(v)
        if info is None:
            print(f"[{i}/{len(videos)}] cannot read {v}")
            continue
        lm = landmarks_path(out_root, cls, v)
        if not os.path.exists(lm):
            os.makedirs(os.path.dirname(lm), exist_ok=True)
            print(f"[{i}/{len(videos)}] {cls}/{os.path.basename(v)} ({info['duration_s']:.0f} s)", flush=True)
            extract(v, lm)
        rows.append({"class": cls, "video": os.path.relpath(v, out_root), "landmarks": os.path.relpath(lm, out_root), **info})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_root, "videos.csv"), index=False)
    return df


def view_ratio(lm_csv, w, h):
    d = pd.read_csv(lm_csv)
    cols = [c for c in d.columns if c[0] in "xy" and c[1:].isdigit()]
    r = [shoulder_torso_ratio(row, w / h) for row in d[cols].dropna().to_dict("records")[::5]]
    r = [x for x in r if x is not None]
    return float(np.median(r)) if r else np.nan, float(d["x0"].notna().mean())


def evaluate(videos_df, out_root, class_map, fps=15.0, labels=None):
    max_ratio = load_config("E3")["side_view"]["max_shoulder_torso_ratio"]
    rows = []
    for _, v in videos_df.iterrows():
        ex = class_map.get(v["class"])
        if ex is None:
            continue
        lm = os.path.join(out_root, v["landmarks"])
        if not os.path.exists(lm):
            continue
        ratio, detected = view_ratio(lm, v["width"], v["height"])
        row = {"class": v["class"], "video": v["video"], "exercise": ex, "width": v["width"], "height": v["height"],
               "duration_s": round(v["duration_s"], 1), "pose_found": round(detected, 2),
               "shoulder_torso": round(ratio, 2), "side_on": bool(ratio <= max_ratio)}
        for mode, count_only in (("full", False), ("count", True)):
            e, df = run_file(lm, ex, fps, width=v["width"], height=v["height"], count_only=count_only)
            dropped = drop_offscreen_trunk_flags(e, df) if count_only else 0
            reps = e.log.reps
            labs = Counter(r["label"] for r in reps)
            scored = [r for r in reps if r["phase"] == "scoring"]
            row.update({
                f"{mode}_reps": len(reps),
                f"{mode}_scored": len(scored),
                f"{mode}_labels": ";".join(f"{k}:{n}" for k, n in labs.most_common()),
                f"{mode}_scored_faults": sum(r["label"] != "good" for r in scored),
            })
            if count_only:
                row["side"] = e.log.side
                row["trunk_flags_ignored"] = dropped
            else:
                row["camera_prompts"] = ";".join(sorted({p["key"] for p in e.log.prompts if p["reason"] == "camera"}))
        rows.append(row)
    res = pd.DataFrame(rows)
    if labels is not None and len(res):
        res = res.merge(labels, on="video", how="left")
    res.to_csv(os.path.join(out_root, "results.csv"), index=False)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", required=True, help="folder with one sub-folder of videos per class")
    ap.add_argument("--out", required=True, help="where landmarks/, videos.csv and results.csv go")
    ap.add_argument("--map", nargs="+", required=True, metavar="CLASS=EX", help='e.g. "hammer curl=E3"')
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--labels", help="optional CSV with columns video,label (video relative to --out)")
    ap.add_argument("--skip-extract", action="store_true")
    args = ap.parse_args()
    class_map = dict(m.split("=", 1) for m in args.map)

    videos = [(c, v) for c, v in list_videos(args.videos) if c in class_map]
    print(f"{len(videos)} videos in classes {sorted(class_map)}")
    vdf = pd.read_csv(os.path.join(args.out, "videos.csv")) if args.skip_extract else extract_all(videos, args.out)
    labels = pd.read_csv(args.labels) if args.labels else None
    res = evaluate(vdf, args.out, class_map, args.fps, labels)
    print(f"\nwrote {os.path.join(args.out, 'results.csv')} ({len(res)} videos)")


if __name__ == "__main__":
    main()
