"""
Train and test generic movement quality models on REHAB24-6 Ex1 features.

Testing is leave-one-person-out: each person is held out in turn, the model
trains on the other people, and predictions are pooled at the end. This is
the honest way to test, because the app will meet new people.

"Positive" = incorrect rep. False positive rate = correct reps wrongly flagged.

Run from inside remove-pk:
    python features/build_features_ex1.py     (once, makes the features file)
    python models/train_models_ex1.py
"""
import os
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, confusion_matrix

warnings.filterwarnings("ignore")
FEATURES_CSV = "data/own/ex1_rep_features.csv"
OUT_CSV = "data/own/ex1_model_results.csv"
SEED = 42

FEATS = ["duration_s", "peak_angle", "rom", "peak_speed", "mean_speed",
         "jerk_norm", "elbow_min", "elbow_mean", "trunk_lean_max", "trunk_lean_range"]
LOG_FEATS = ["peak_speed", "mean_speed", "jerk_norm"]   # heavy tails, so log them


def load():
    df = pd.read_csv(FEATURES_CSV)
    df = df[df["valid"] == True].copy()
    for c in LOG_FEATS:
        df[c] = np.log1p(df[c].clip(lower=0))
    df["incorrect"] = 1 - df["correctness"]
    return df


def models():
    m = {
        "Majority class (floor)": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=3, class_weight="balanced",
            random_state=SEED, n_jobs=-1),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8,
            random_state=SEED),
        "SVM (RBF)": make_pipeline(
            StandardScaler(), SVC(C=1.0, probability=True, class_weight="balanced",
                                  random_state=SEED)),
    }
    try:
        from xgboost import XGBClassifier
        m["XGBoost"] = XGBClassifier(
            n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8,
            eval_metric="logloss", random_state=SEED, verbosity=0)
    except Exception:
        print("(xgboost not installed, skipping it. Install with: python -m pip install xgboost)")
    return m


def run_lopo(model, X, y, groups):
    pred = np.zeros(len(y), dtype=int)
    prob = np.zeros(len(y))
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        model.fit(X[tr], y[tr])
        pred[te] = model.predict(X[te])
        if hasattr(model, "predict_proba"):
            prob[te] = model.predict_proba(X[te])[:, 1]
        else:
            prob[te] = pred[te]
    return pred, prob


def metrics(y, pred, prob):
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y, pred),
        "f1_incorrect": f1_score(y, pred, zero_division=0),
        "false_pos_rate": fp / (fp + tn) if (fp + tn) else np.nan,
        "recall_incorrect": tp / (tp + fn) if (tp + fn) else np.nan,
        "auc": roc_auc_score(y, prob) if len(set(prob)) > 1 else 0.5,
    }


def main():
    df = load()
    X = df[FEATS].fillna(df[FEATS].median()).values
    y = df["incorrect"].values
    groups = df["person_id"].values
    print(f"{len(df)} reps, {len(set(groups))} people, "
          f"{int(y.sum())} incorrect / {int((1 - y).sum())} correct\n")

    rows, store = [], {}
    for name, mdl in models().items():
        pred, prob = run_lopo(mdl, X, y, groups)
        r = {"model": name, **metrics(y, pred, prob)}
        rows.append(r)
        store[name] = pred
    res = pd.DataFrame(rows).round(3)
    print("Leave-one-person-out results:")
    print(res.to_string(index=False))
    res.to_csv(OUT_CSV, index=False)

    # per-person accuracy for the best non-dummy model by F1
    best = res[res["model"] != "Majority class (floor)"].sort_values(
        "f1_incorrect", ascending=False).iloc[0]["model"]
    per = pd.DataFrame({"person": groups, "ok": store[best] == y}).groupby("person")["ok"].agg(
        ["mean", "count"]).round(2)
    print(f"\nPer-person accuracy for {best} (how steady is it across people?):")
    print(per.to_string())

    # which features does a random forest lean on (fit on everyone, for interpretation only)
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                class_weight="balanced", random_state=SEED).fit(X, y)
    imp = pd.Series(rf.feature_importances_, index=FEATS).sort_values(ascending=False)
    print("\nRandom Forest feature importance (all data, interpretation only):")
    print(imp.round(3).to_string())
    print(f"\nSaved: {OUT_CSV}")


if __name__ == "__main__":
    main()
