"""
Compare a dataset's good/bad form labels with our six-label rules, using a
per-person baseline (for clips too short for the app's own calibration).

Input: an --out folder made by research/eval_public_videos.py (videos.csv +
landmarks/), whose classes are the form labels ("good" / "bad"), and a regex
that pulls the person id out of the file name.

For each person:
  1. count-only rep detection on each clip (no camera check, side = better-seen side)
  2. baseline = median of the first 3 valid reps of the person's GOOD clip(s)
     (session.rules.build_baseline); those 3 reps are not scored
  3. every other rep (rest of the good clip, all of the bad clip) is labelled by
     session.rules.label_rep against that baseline
Then: rep-level confusion (their label x our label) and clip-level tables.

Run from inside remove-pk:
    python research/eval_form_labels.py --out data/public/mendeley_curl --exercise E3 \\
        --person "subject_(\\d+)"
"""
import argparse
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())
from research.eval_own_landmarks import run_file  # noqa: E402
from session.config import load_config  # noqa: E402
from session.rules import build_baseline, label_rep  # noqa: E402

N_BASE = 3


def clip_reps(row, out_root, exercise, fps):
    e, _ = run_file(os.path.join(out_root, row["landmarks"]), exercise, fps,
                    width=row["width"], height=row["height"], count_only=True)
    return e.log.side, [r["features"] for r in e.log.reps]


def evaluate(out_root, exercise, person_re, fps=15.0):
    cfg = load_config(exercise)
    vids = pd.read_csv(os.path.join(out_root, "videos.csv"))
    vids["person"] = vids["video"].map(lambda v: re.search(person_re, os.path.basename(v)).group(1))
    reps, clips, skipped = [], [], []
    for person, g in vids.groupby("person"):
        per_clip = {}
        for _, row in g.iterrows():
            per_clip[row["video"]] = (row["class"],) + clip_reps(row, out_root, exercise, fps)
        good_feats = [f for lab, _, fs in per_clip.values() if lab == "good" for f in fs if f.get("valid")]
        if len(good_feats) < N_BASE:
            skipped.append((person, len(good_feats)))
            continue
        base_ids = {id(f) for f in good_feats[:N_BASE]}
        baseline = build_baseline(good_feats[:N_BASE])
        for video, (their, side, feats) in per_clip.items():
            ours = []
            for f in feats:
                if id(f) in base_ids:
                    continue
                label, faults = label_rep(f, cfg, baseline)
                ours.append(label)
                reps.append({"person": person, "video": video, "their": their, "ours": label,
                             "faults": "|".join(faults), "swing": f.get("comp_change_max"),
                             "base_swing": baseline.get("comp_change_max"),
                             "duration_s": f.get("duration_s"), "base_duration_s": baseline["duration_s"],
                             "rom": f.get("rom"), "base_rom": baseline["rom"]})
            flagged = sum(x != "good" for x in ours)
            clips.append({"person": person, "video": video, "their": their, "side": side,
                          "reps_found": len(feats), "scored": len(ours), "flagged": flagged})
    return pd.DataFrame(reps), pd.DataFrame(clips), skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exercise", required=True)
    ap.add_argument("--person", required=True, help="regex with one group: the person id in the file name")
    ap.add_argument("--fps", type=float, default=15.0)
    args = ap.parse_args()
    reps, clips, skipped = evaluate(args.out, args.exercise, args.person, args.fps)
    reps.to_csv(os.path.join(args.out, "form_reps.csv"), index=False)
    clips.to_csv(os.path.join(args.out, "form_clips.csv"), index=False)
    print(f"people scored: {clips['person'].nunique() if len(clips) else 0}; skipped (fewer than {N_BASE} good reps): {skipped}")
    if len(reps):
        print("\nRep level (rows: their label, columns: our label)")
        print(pd.crosstab(reps["their"], reps["ours"], margins=True).to_string())
        print("\nRep level, any fault vs good")
        print(pd.crosstab(reps["their"], reps["ours"] != "good", margins=True)
              .rename(columns={False: "ours good", True: "ours fault"}).to_string())


if __name__ == "__main__":
    main()
