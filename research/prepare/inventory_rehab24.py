"""
Summarize REHAB24-6 per exercise: reps, people, correct/incorrect, subtypes.

Run from inside remove-pk:
    python research/prepare/inventory_rehab24.py
"""
import pandas as pd

CSV = "data/public/rehab24_6/Segmentation.csv"
d = pd.read_csv(CSV, sep=None, engine="python")
d["exercise_subtype"] = d["exercise_subtype"].fillna("none")

print("Total reps:", len(d))
print("People:", d["person_id"].nunique(), "| Videos:", d["video_id"].nunique())
print("\nValues in 'correctness':", sorted(d["correctness"].unique()))
print("Values in 'exercise_subtype':", sorted(d["exercise_subtype"].unique()))

print("\n--- Per exercise ---")
summary = d.groupby("exercise_id").agg(
    reps=("repetition_number", "count"),
    videos=("video_id", "nunique"),
    people=("person_id", "nunique"),
)
cor = d.pivot_table(index="exercise_id", columns="correctness",
                    values="repetition_number", aggfunc="count", fill_value=0)
cor.columns = [f"correctness_{c}" for c in cor.columns]
print(summary.join(cor))

print("\n--- Subtypes per exercise ---")
print(d.groupby(["exercise_id", "exercise_subtype"]).size())

print("\n--- Lights on vs off ---")
print(d["lights_on"].value_counts())

out = "data/public/rehab24_6/inventory_summary.csv"
summary.join(cor).to_csv(out)
print("\nSaved:", out)
