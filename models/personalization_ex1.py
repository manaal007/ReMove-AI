"""
Experiment A (proposal): generic model vs personalized baseline, Ex1.

For every video (one person, one session) the first 3 CORRECT reps act as the
calibration reps, like the app will do. Those reps are then NOT tested.
Every other rep is scored two ways, on the same reps, with leave-one-person-out:

  A. Generic       : raw features
  B. Personalized  : features as z-scores against that person's own calibration reps
  C. Distance only : one number per rep, the average |z| from the person's baseline

Run from inside remove-pk:
    python models/personalization_ex1.py
"""
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, confusion_matrix

warnings.filterwarnings("ignore")
FEATURES_CSV = "data/own/ex1_rep_features.csv"
N_BASE = 3
SEED = 42
FEATS = ["duration_s", "peak_angle", "rom", "peak_speed", "mean_speed",
         "jerk_norm", "elbow_min", "elbow_mean", "trunk_lean_max", "trunk_lean_range"]
LOG_FEATS = ["peak_speed", "mean_speed", "jerk_norm"]


def load():
    df = pd.read_csv(FEATURES_CSV)
    df = df[df["valid"] == True].copy()
    for c in LOG_FEATS:
        df[c] = np.log1p(df[c].clip(lower=0))
    df["incorrect"] = 1 - df["correctness"]
    return df.sort_values(["video_id", "rep"]).reset_index(drop=True)


def personalize(df):
    """Add z-score columns vs each video's first N_BASE correct reps; mark baseline reps."""
    global_sd = df[FEATS].std()
    out, skipped = [], []
    for vid, g in df.groupby("video_id"):
        base = g[g["correctness"] == 1].head(N_BASE)
        if len(base) < N_BASE:
            skipped.append(vid)
            continue
        mu = base[FEATS].mean()
        # only 3 reps give a shaky std, so never let it fall below 20% of the overall spread
        sd = np.maximum(base[FEATS].std(), 0.2 * global_sd)
        z = (g[FEATS] - mu) / sd
        z.columns = [f"z_{c}" for c in FEATS]
        g = pd.concat([g, z], axis=1)
        g["is_baseline"] = g.index.isin(base.index)
        g["dist"] = z.abs().mean(axis=1)
        out.append(g)
    if skipped:
        print("Skipped (fewer than 3 correct reps):", skipped)
    return pd.concat(out)


def lopo(model, X, y, groups, test_mask):
    """Train on other people's reps (all of them), test on this person's non-baseline reps."""
    pred = np.full(len(y), -1)
    prob = np.zeros(len(y))
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        te = te[test_mask[te]]
        model.fit(X[tr], y[tr])
        pred[te] = model.predict(X[te])
        prob[te] = model.predict_proba(X[te])[:, 1]
    return pred, prob


def score(y, pred, prob, mask):
    y, pred, prob = y[mask], pred[mask], prob[mask]
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y, pred),
        "f1_incorrect": f1_score(y, pred, zero_division=0),
        "false_pos_rate": fp / (fp + tn),
        "recall_incorrect": tp / (tp + fn),
        "auc": roc_auc_score(y, prob),
    }


def main():
    df = personalize(load())
    test = ~df["is_baseline"].values
    y = df["incorrect"].values
    groups = df["person_id"].values
    print(f"{len(df)} reps from {df['video_id'].nunique()} videos; "
          f"{int(test.sum())} test reps ({int(y[test].sum())} incorrect, "
          f"{int((1 - y[test]).sum())} correct)\n")

    sets = {
        "A. Generic (raw features)": df[FEATS].values,
        "B. Personalized (z-scores)": df[[f"z_{c}" for c in FEATS]].values,
        "C. Distance from baseline only": df[["dist"]].values,
    }
    learners = {
        "Logistic Regression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Gradient Boosting": lambda: GradientBoostingClassifier(
            n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8,
            random_state=SEED),
    }

    rows = []
    for set_name, X in sets.items():
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        for lname, make in learners.items():
            if set_name.startswith("C.") and lname != "Logistic Regression":
                continue
            pred, prob = lopo(make(), X, y, groups, test)
            rows.append({"features": set_name, "model": lname, **score(y, pred, prob, test)})
    res = pd.DataFrame(rows).round(3)
    print(res.to_string(index=False))
    res.to_csv("data/own/ex1_personalization_results.csv", index=False)
    print("\nSaved: data/own/ex1_personalization_results.csv")
    print("\nHow to read it: compare A vs B (same reps, same model). If B is higher and its\n"
          "false positive rate is lower, personalization helped.")


if __name__ == "__main__":
    main()
