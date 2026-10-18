"""
Build per-rep features for REHAB24-6 Exercise 1 (right arm abduction).

Does three things for every Ex1 Camera17 video:
  1. runs pose extraction if the landmarks CSV does not exist yet
  2. cuts out each labeled rep using Segmentation.csv
  3. calculates features per rep and saves one table

Run from inside remove-pk (takes a while the first time):
    python features/build_features_ex1.py
"""
import os
import sys
import glob
import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

VIDEO_DIR = "data/public/rehab24_6/Videos/Ex1"
SEG_CSV = "data/public/rehab24_6/Segmentation.csv"
OUT_CSV = "data/own/ex1_rep_features.csv"
FPS = 30.0
MIN_VIS = 0.5
SMOOTH = 5
MAX_NAN_FRAC = 0.2

# numpy 2 renamed trapz to trapezoid
_trapz = getattr(np, "trapezoid", None) or np.trapz

# MediaPipe landmark ids (subject's own left/right)
L_SH, R_SH, R_EL, R_WR, L_HIP, R_HIP = 11, 12, 14, 16, 23, 24


def angle_at(b, a, c):
    """Angle at point b between b->a and b->c, arrays (N,2) in pixels."""
    v1, v2 = a - b, c - b
    n = np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1)
    cos = (v1 * v2).sum(axis=1) / np.where(n == 0, np.nan, n)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def frame_signals(lm, W, H):
    """Per-frame abduction angle, elbow angle and trunk lean (all degrees)."""
    def P(i):
        return np.c_[lm[f"x{i}"].values * W, lm[f"y{i}"].values * H]

    abd = angle_at(P(R_SH), P(R_HIP), P(R_EL))       # hip-shoulder-elbow
    elbow = angle_at(P(R_EL), P(R_SH), P(R_WR))      # shoulder-elbow-wrist
    mid_sh = (P(L_SH) + P(R_SH)) / 2
    mid_hip = (P(L_HIP) + P(R_HIP)) / 2
    trunk = mid_sh - mid_hip                         # points from hips up to shoulders
    lean = np.degrees(np.arctan2(trunk[:, 0], -trunk[:, 1]))  # 0 = upright

    need = [R_SH, R_EL, R_WR, R_HIP, L_SH, L_HIP]
    vis = lm[[f"v{i}" for i in need]].min(axis=1).values
    bad = vis < MIN_VIS
    for s in (abd, elbow, lean):
        s[bad] = np.nan
    return abd, elbow, lean, vis


def smooth(x):
    return pd.Series(x).interpolate(limit_direction="both").rolling(
        SMOOTH, center=True, min_periods=1).mean().values


def rep_features(abd, elbow, lean, vis, f0, f1):
    sl = slice(int(f0), int(f1) + 1)
    a, e, l, v = abd[sl], elbow[sl], lean[sl], vis[sl]
    nan_frac = float(np.mean(np.isnan(a)))
    out = {"n_frames": len(a), "nan_frac": nan_frac, "vis_mean": float(np.nanmean(v))}
    if len(a) < 10 or nan_frac > MAX_NAN_FRAC:
        out["valid"] = False
        return out
    a, e, l = smooth(a), smooth(e), smooth(l)
    dt = 1 / FPS
    vel = np.gradient(a, dt)
    acc = np.gradient(vel, dt)
    jerk = np.gradient(acc, dt)
    dur = len(a) * dt
    rom = a.max() - a.min()
    out.update({
        "valid": True,
        "duration_s": dur,
        "peak_angle": a.max(),
        "min_angle": a.min(),
        "rom": rom,
        "peak_speed": np.abs(vel).max(),
        "mean_speed": np.abs(vel).mean(),
        # dimensionless jerk: lower = smoother, comparable across speeds and sizes
        "jerk_norm": (_trapz(jerk ** 2, dx=dt) * dur ** 5) / (rom ** 2 + 1e-9),
        "elbow_min": e.min(),
        "elbow_mean": e.mean(),
        # trunk lean relative to the lean at the start of the rep (removes camera tilt)
        "trunk_lean_max": np.abs(l - l[:5].mean()).max(),
        "trunk_lean_range": l.max() - l.min(),
    })
    return out


def main():
    from pose.extract_landmarks import extract

    seg = pd.read_csv(SEG_CSV, sep=None, engine="python")
    seg = seg[seg["exercise_id"] == 1]
    videos = sorted(glob.glob(os.path.join(VIDEO_DIR, "*Camera17*.mp4")))
    print(f"Found {len(videos)} Camera17 videos in Ex1")

    rows = []
    for vp in videos:
        name = os.path.splitext(os.path.basename(vp))[0]
        video_id = name.split("-")[0]
        lm_csv = os.path.join("data", "own", f"{name}_landmarks.csv")
        if not os.path.exists(lm_csv):
            print(f"[{video_id}] extracting landmarks...")
            extract(vp)
        lm = pd.read_csv(lm_csv)
        cap = cv2.VideoCapture(vp)
        W = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        H = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()

        abd, elbow, lean, vis = frame_signals(lm, W, H)
        for _, r in seg[seg["video_id"] == video_id].iterrows():
            feats = rep_features(abd, elbow, lean, vis, r["first_frame"], r["last_frame"])
            feats.update({
                "video_id": video_id,
                "person_id": r["person_id"],
                "rep": int(r["repetition_number"]),
                "correctness": int(r["correctness"]),
                "lights_on": r["lights_on"],
                "cam17_orientation": r["cam17_orientation"],
            })
            rows.append(feats)
        print(f"[{video_id}] done")

    df = pd.DataFrame(rows)
    os.makedirs("data/own", exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {len(df)} reps to {OUT_CSV}  (valid: {int(df['valid'].sum())})")

    # quick look: which features separate correct from incorrect?
    from sklearn.metrics import roc_auc_score
    ok = df[df["valid"] == True]
    cols = ["duration_s", "peak_angle", "rom", "peak_speed", "mean_speed",
            "jerk_norm", "elbow_min", "elbow_mean", "trunk_lean_max", "trunk_lean_range"]
    print("\nFeature | mean (incorrect) | mean (correct) | AUC (0.5 = useless)")
    for c in cols:
        m0 = ok.loc[ok.correctness == 0, c].mean()
        m1 = ok.loc[ok.correctness == 1, c].mean()
        auc = roc_auc_score(ok.correctness, ok[c].fillna(ok[c].median()))
        print(f"{c:18s} {m0:10.2f} {m1:10.2f} {auc:8.2f}")


if __name__ == "__main__":
    main()
