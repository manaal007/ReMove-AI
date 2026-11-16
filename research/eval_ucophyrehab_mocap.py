"""
E4 rep counting and rules on UCOPhyRehab++ motion-capture knee angles (Zenodo 17935737).

Data (data/public/ucophyrehab/, not in git):
  dataset_3d_with_angles.json  OptiTrack 3D hip/knee/ankle of the working leg + the
                               hip-knee-ankle angle per video frame (30 fps, frame ids
                               match the RGB video)
  ucophyrehab2_data.jsonl      per recording: rep segments [init_frame, final_frame]
                               and a quality score per rep (2-5)
Seated knee exercises (UCO numbering, checked on samples.zip silhouettes and the
JSON's position/side fields): 01 / 02 left knee without / with support,
05 / 06 right knee without / with support.

Pipeline: the same parts the live engine uses, on the mocap angle instead of
MediaPipe: session.rep_counter.RepCounter -> features.signals.side_rep_features
-> session.rules.label_rep with config E4. The angle is fed at --fps (15 = the
browser's rate) picked by time. Only the working leg is in the mocap, so there is
no shoulder: the trunk-lean rule cannot be evaluated (comp_change_max is NaN).

Baseline, per person and leg (01+02 left, 05+06 right): the first 3 of OUR reps
that fall in a segment THEY scored 4-5, in recording order. Those 3 are not scored.

Matching: one of our reps belongs to the segment that holds most of its frames.
Their segment is "found" if at least one of our reps belongs to it.

Run from inside remove-pk:
    python research/eval_ucophyrehab_mocap.py
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
from features.signals import side_rep_features  # noqa: E402
from session.config import load_config  # noqa: E402
from session.rep_counter import RepCounter  # noqa: E402
from session.rules import build_baseline, label_rep  # noqa: E402

DATA = os.path.join("data", "public", "ucophyrehab")
VIDEO_FPS = 30.0
EXERCISES = {"01": ("left", "no support"), "02": ("left", "support"),
             "05": ("right", "no support"), "06": ("right", "support")}
N_BASE = 3


def load(data_dir):
    with open(os.path.join(data_dir, "dataset_3d_with_angles.json"), encoding="utf-8") as f:
        mocap = json.load(f)["data"]
    meta = {}
    with open(os.path.join(data_dir, "ucophyrehab2_data.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            meta[(r["subject_id"], r["exercise_id"])] = sorted(r["scores"], key=lambda s: s["init_frame"])
    return mocap, meta


def detect(ids, angle, cfg, fps):
    """Our reps on one recording: list of (start_frame_id, end_frame_id, features)."""
    t = ids / VIDEO_FPS
    keep, next_t = [], t[0]
    for i, ti in enumerate(t):                       # pick frames by time, like the live app
        if ti >= next_t - 1e-9:
            keep.append(i)
            next_t = ti + 1.0 / fps
    ids, t, a = ids[keep], t[keep], angle[keep]
    rc = RepCounter(cfg)
    reps = []
    comp = np.full(len(a), np.nan)                   # no shoulder in the mocap
    vis = np.ones(len(a))
    window = cfg["tracking"]["smoothing_window"]
    for i in range(len(a)):
        for ev in rc.update(i, float(t[i]), float(a[i])):
            if ev.kind != "rep":
                continue
            dt = t[ev.end] - t[ev.start]
            rfps = (ev.end - ev.start) / dt if dt > 0 else fps
            feat = side_rep_features(a, comp, vis, ev.start, ev.end, fps=rfps, window=window)
            reps.append((int(ids[ev.start]), int(ids[ev.end]), feat))
    return reps


def owner(rep, segs):
    """Index of the segment holding most of the rep's frames (None if none overlap)."""
    s, e, _ = rep
    best, best_ov = None, 0
    for k, g in enumerate(segs):
        ov = min(e, g["final_frame"]) - max(s, g["init_frame"])
        if ov > best_ov:
            best, best_ov = k, ov
    return best


def evaluate(fps=15.0, data_dir=DATA):
    cfg = load_config("E4")
    mocap, meta = load(data_dir)
    rec_rows, rep_rows = [], []
    by_person_leg = {}
    for r in mocap:
        ex = r["exercise"]
        if ex not in EXERCISES:
            continue
        person = r["folder"]
        segs = meta.get((person, ex), [])
        # the angle is stored inside each frame's "joints" object, next to the 3D points
        fr = [(f["id"], (f.get("joints") or {}).get("angle")) for f in (r.get("frames") or [])]
        fr = [(i, a) for i, a in fr if a is not None]
        ids = np.array([i for i, _ in fr], dtype=float)
        ang = np.array([float(a) for _, a in fr], dtype=float)
        if len(fr) < 2:                              # recording without usable mocap angles
            rec_rows.append({"person": person, "exercise": ex, "leg": EXERCISES[ex][0],
                             "support": EXERCISES[ex][1], "their_reps": len(segs), "our_reps": 0,
                             "segments_found": 0, "ours_outside_segments": 0, "extra_in_same_segment": 0,
                             "angle_min": np.nan, "angle_max": np.nan, "no_mocap": True})
            continue
        reps = detect(ids, ang, cfg, fps)
        owners = [owner(x, segs) for x in reps]
        rec_rows.append({"person": person, "exercise": ex, "leg": EXERCISES[ex][0], "support": EXERCISES[ex][1],
                         "their_reps": len(segs), "our_reps": len(reps),
                         "segments_found": len({o for o in owners if o is not None}),
                         "ours_outside_segments": sum(o is None for o in owners),
                         "extra_in_same_segment": len([o for o in owners if o is not None]) - len({o for o in owners if o is not None}),
                         "angle_min": round(float(np.nanmin(ang)), 1), "angle_max": round(float(np.nanmax(ang)), 1),
                         "no_mocap": False})
        leg = EXERCISES[ex][0]
        for (s, e, feat), o in zip(reps, owners):
            score = segs[o]["score"] if o is not None else np.nan
            by_person_leg.setdefault((person, leg), []).append(
                {"person": person, "exercise": ex, "leg": leg, "start": s, "end": e,
                 "segment": o, "score": score, "feat": feat})
    for (person, leg), reps in by_person_leg.items():
        reps.sort(key=lambda x: (x["exercise"], x["start"]))
        base = [x for x in reps if x["feat"].get("valid") and x["score"] >= 4][:N_BASE]
        if len(base) < N_BASE:
            for x in reps:
                rep_rows.append({**{k: v for k, v in x.items() if k != "feat"}, "ours": "no_baseline", "faults": ""})
            continue
        baseline = build_baseline([x["feat"] for x in base])
        base_ids = {id(x) for x in base}
        for x in reps:
            if id(x) in base_ids:
                continue
            label, faults = label_rep(x["feat"], cfg, baseline)
            f = x["feat"]
            rep_rows.append({**{k: v for k, v in x.items() if k != "feat"}, "ours": label, "faults": "|".join(faults),
                             "duration_s": f.get("duration_s"), "base_duration_s": baseline["duration_s"],
                             "rom": f.get("rom"), "base_rom": baseline["rom"],
                             "sparc": f.get("sparc"), "base_sparc": baseline.get("sparc")})
    return pd.DataFrame(rec_rows), pd.DataFrame(rep_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=float, default=15.0)
    args = ap.parse_args()
    recs, reps = evaluate(args.fps)
    recs.to_csv(os.path.join(DATA, "mocap_recordings.csv"), index=False)
    reps.to_csv(os.path.join(DATA, "mocap_reps.csv"), index=False)
    print(f"{len(recs)} recordings, {recs['person'].nunique()} people, fed at {args.fps} fps; "
          f"{int(recs['no_mocap'].sum())} recordings have no mocap angles "
          f"({int(recs.loc[recs['no_mocap'], 'their_reps'].sum())} of their reps)\n")
    missing = recs[recs["no_mocap"]]
    recs = recs[~recs["no_mocap"]]
    g = recs.groupby(["exercise", "leg", "support"]).agg(
        recordings=("person", "size"), their_reps=("their_reps", "sum"), our_reps=("our_reps", "sum"),
        segments_found=("segments_found", "sum"), outside=("ours_outside_segments", "sum"),
        split=("extra_in_same_segment", "sum"))
    g.loc[("all", "", ""), :] = g.sum()
    g["found_%"] = (100 * g["segments_found"] / g["their_reps"]).round(1)
    print("Rep counting (their segments vs our reps)")
    print(g.astype({c: int for c in g.columns if c != "found_%"}).to_string())
    d = (recs["our_reps"] - recs["their_reps"])
    print("\nour - their per recording:", d.value_counts().sort_index().to_dict())

    s = reps[reps["ours"] != "no_baseline"].dropna(subset=["score"]).copy()
    s["their"] = np.where(s["score"] <= 3, "lower (2-3)", "normal (4-5)")
    print(f"\nLabels: {len(s)} scored reps matched to a segment "
          f"(people/legs without {N_BASE} baseline reps: {(reps['ours'] == 'no_baseline').sum()} reps)")
    print(pd.crosstab(s["their"], s["ours"], margins=True).to_string())
    print()
    print(pd.crosstab(s["score"], s["ours"] != "good", margins=True)
          .rename(columns={False: "ours good", True: "ours fault"}).to_string())


if __name__ == "__main__":
    main()
