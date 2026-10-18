"""
Plot the right shoulder abduction angle over time for one REHAB24-6 video,
with the labeled reps shaded (green = correct, red = incorrect).

Run AFTER extract_landmarks.py, from inside remove-pk:
    python features/plot_angle.py data/public/rehab24_6/Videos/Ex1/PM_000-Camera17-30fps.mp4
"""
import sys
import os
import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEG_CSV = "data/public/rehab24_6/Segmentation.csv"
R_SHOULDER, R_ELBOW, R_HIP = 12, 14, 24   # MediaPipe landmark ids (subject's right)
MIN_VIS = 0.5
SMOOTH = 5


def angle_deg(a, b, c):
    """Angle at point b between b->a and b->c. Inputs are (N,2) arrays in pixels."""
    v1, v2 = a - b, c - b
    dot = (v1 * v2).sum(axis=1)
    n = np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1)
    cos = np.clip(dot / np.where(n == 0, np.nan, n), -1, 1)
    return np.degrees(np.arccos(cos))


def main(video_path):
    name = os.path.splitext(os.path.basename(video_path))[0]
    lm_csv = os.path.join("data", "own", f"{name}_landmarks.csv")
    if not os.path.exists(lm_csv):
        print("Run extract_landmarks.py on this video first.")
        return

    cap = cv2.VideoCapture(video_path)
    W = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    H = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()

    df = pd.read_csv(lm_csv)

    def pts(i):
        # convert normalized coords to pixels so angles are not distorted
        return np.c_[df[f"x{i}"].values * W, df[f"y{i}"].values * H]

    ang = angle_deg(pts(R_HIP), pts(R_SHOULDER), pts(R_ELBOW))
    vis = df[[f"v{R_SHOULDER}", f"v{R_ELBOW}", f"v{R_HIP}"]].min(axis=1).values
    ang[vis < MIN_VIS] = np.nan
    ang_s = pd.Series(ang).rolling(SMOOTH, center=True, min_periods=1).mean().values

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df["frame"], ang_s, color="black", lw=1.5, label="right shoulder abduction angle")

    video_id = name.split("-")[0]  # e.g. PM_000
    seg = pd.read_csv(SEG_CSV, sep=None, engine="python")
    seg = seg[(seg["video_id"] == video_id) & (seg["exercise_id"] == 1)]
    for _, r in seg.iterrows():
        color = "green" if r["correctness"] == 1 else "red"
        ax.axvspan(r["first_frame"], r["last_frame"], color=color, alpha=0.15)
        ax.text((r["first_frame"] + r["last_frame"]) / 2, np.nanmax(ang_s) * 0.97,
                f"rep {int(r['repetition_number'])}", ha="center", fontsize=8)

    ax.set_xlabel("frame (30 fps)")
    ax.set_ylabel("angle (degrees)")
    ax.set_title(f"{name}  |  green = correct rep, red = incorrect rep")
    ax.legend(loc="lower right")
    plt.tight_layout()
    out = os.path.join("data", "own", f"{name}_angle.png")
    plt.savefig(out, dpi=150)

    print(f"Reps labeled for this video: {len(seg)}")
    print(f"Angle range: {np.nanmin(ang_s):.0f} to {np.nanmax(ang_s):.0f} degrees")
    print(f"Saved plot: {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python features/plot_angle.py path/to/video.mp4")
    else:
        main(sys.argv[1])
