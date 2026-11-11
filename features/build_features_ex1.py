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
import pandas as pd

sys.path.insert(0, os.getcwd())
from features.signals import frame_signals, rep_features, FEATURE_NAMES  # noqa: E402

VIDEO_DIR = "data/public/rehab24_6/Videos/Ex1"
SEG_CSV = "data/public/rehab24_6/Segmentation.csv"
OUT_CSV = "data/own/ex1_rep_features.csv"


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
    print("\nFeature | mean (incorrect) | mean (correct) | AUC (0.5 = useless)")
    for c in FEATURE_NAMES:
        m0 = ok.loc[ok.correctness == 0, c].mean()
        m1 = ok.loc[ok.correctness == 1, c].mean()
        auc = roc_auc_score(ok.correctness, ok[c].fillna(ok[c].median()))
        print(f"{c:18s} {m0:10.2f} {m1:10.2f} {auc:8.2f}")


if __name__ == "__main__":
    main()
