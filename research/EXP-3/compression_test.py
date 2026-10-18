"""
Experiment B: how much does WhatsApp style compression hurt pose tracking?

Takes one video, makes three compressed copies (the original is never touched),
runs pose tracking on each copy, and compares with the original.

Run from inside remove-pk, with .venv active and ffmpeg installed:
    python research/EXP-3/compression_test.py data/public/rehab24_6/Videos/Ex1/PM_001-Camera17-30fps.mp4
"""
import os
import sys
import shutil
import subprocess
import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
from features.build_features_ex1 import frame_signals
from pose.extract_landmarks import extract

# Three severity levels. These APPROXIMATE a messaging app, they are not official
# WhatsApp settings. Check them against a real WhatsApp copy (see the notes printed
# at the end) and adjust the numbers if your real copy looks very different.
LEVELS = {
    "L1_mild":     {"short_side": 720, "crf": 28, "maxrate": "1500k"},
    "L2_moderate": {"short_side": 480, "crf": 32, "maxrate": "800k"},
    "L3_severe":   {"short_side": 360, "crf": 36, "maxrate": "300k"},
}
OUT_ROOT = os.path.join("data", "own", "compressed")


def even(n):
    return int(round(n / 2) * 2)


def compress(src, level, cfg):
    name = os.path.splitext(os.path.basename(src))[0]
    out_dir = os.path.join(OUT_ROOT, level)
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"{name}_{level}.mp4")

    cap = cv2.VideoCapture(src)
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    scale = min(1.0, cfg["short_side"] / min(w, h))        # never upscale
    new_w, new_h = even(w * scale), even(h * scale)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
           "-vf", f"scale={new_w}:{new_h}",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(cfg["crf"]),
           "-maxrate", cfg["maxrate"], "-bufsize", cfg["maxrate"],
           "-pix_fmt", "yuv420p", "-r", "30", "-an", dst]
    subprocess.run(cmd, check=True)
    return dst, (new_w, new_h)


def angle_series(video, csv_path):
    if not os.path.exists(csv_path):
        extract(video, csv_path)
    lm = pd.read_csv(csv_path)
    cap = cv2.VideoCapture(video)
    W = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    H = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    abd, _, _, vis = frame_signals(lm, W, H)
    found = lm["x0"].notna().mean() * 100
    return abd, vis, found


def main(src):
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found. Install it with:  winget install ffmpeg\n"
              "then close and reopen VS Code and try again.")
        return
    name = os.path.splitext(os.path.basename(src))[0]
    orig_csv = os.path.join("data", "own", f"{name}_landmarks.csv")
    print("Original video: running pose tracking (skipped if already done)...")
    abd0, vis0, found0 = angle_series(src, orig_csv)
    size0 = os.path.getsize(src) / 1e6

    rows = [{"level": "original", "resolution": "", "size_mb": round(size0, 1),
             "pose_found_pct": round(found0, 1), "mean_visibility": round(float(np.nanmean(vis0)), 3),
             "mean_abs_angle_diff_deg": 0.0, "rms_angle_diff_deg": 0.0}]
    for level, cfg in LEVELS.items():
        print(f"\n{level}: compressing...")
        dst, (w, h) = compress(src, level, cfg)
        csv_c = os.path.join(OUT_ROOT, level, f"{name}_{level}_landmarks.csv")
        print(f"{level}: running pose tracking...")
        abd1, vis1, found1 = angle_series(dst, csv_c)
        n = min(len(abd0), len(abd1))
        d = abd1[:n] - abd0[:n]
        rows.append({
            "level": level, "resolution": f"{w}x{h}",
            "size_mb": round(os.path.getsize(dst) / 1e6, 1),
            "pose_found_pct": round(found1, 1),
            "mean_visibility": round(float(np.nanmean(vis1)), 3),
            "mean_abs_angle_diff_deg": round(float(np.nanmean(np.abs(d))), 2),
            "rms_angle_diff_deg": round(float(np.sqrt(np.nanmean(d ** 2))), 2),
        })
        if abs(len(abd0) - len(abd1)) > 2:
            print(f"  note: frame counts differ ({len(abd0)} vs {len(abd1)}), compared the first {n}")

    res = pd.DataFrame(rows)
    out = os.path.join("data", "own", f"{name}_compression_results.csv")
    res.to_csv(out, index=False)
    print("\n" + res.to_string(index=False))
    print(f"\nSaved: {out}")
    print("\nHow to read it: the angle difference is how far the compressed video's right shoulder\n"
          "angle is from the original's, averaged over all frames (degrees). Lower is better.\n"
          "\nTo check how close these levels are to real WhatsApp: send the original to a phone\n"
          "through WhatsApp, save the copy it receives, and run:\n"
          "    ffprobe -v error -show_entries stream=width,height,bit_rate,r_frame_rate -of default=nw=1 yourcopy.mp4\n"
          "If its resolution and bitrate are far from the levels above, change LEVELS at the top of this script.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python research/EXP-3/compression_test.py path/to/video.mp4")
    else:
        main(sys.argv[1])
