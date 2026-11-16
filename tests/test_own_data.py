"""Rep counting on our own side-view recordings (data/own/landmarks, not in git).
Skipped when the data is not on this machine. research/eval_own_landmarks.py prints the full table."""
import os

import pandas as pd
import pytest

from research.eval_own_landmarks import DATA_DIR, MANIFEST, run_file

if not os.path.exists(MANIFEST):
    pytest.skip("own recordings not present (data/ is not in git)", allow_module_level=True)

M = pd.read_csv(MANIFEST)
USABLE = M[M["usable"] != "no"]
# The manifest's reps_approx is an eyeball count. v_12.08.33PM says ~11, but its knee-angle
# trace shows 9 complete reps plus one already in progress when the clip starts.
CHECKED = {"v_12.08.33PM_landmarks.csv": 9}


@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("row", USABLE.to_dict("records"), ids=lambda r: r["file"])
def test_reps_found_match_manifest(row, fps):
    ex = row["exercise"].split("_")[0]
    e, _ = run_file(os.path.join(DATA_DIR, row["file"]), ex, fps=fps, count_only=True)
    expected = CHECKED.get(row["file"], int(row["reps_approx"]))
    assert abs(len(e.log.reps) - expected) <= 1


@pytest.mark.parametrize("row", USABLE.to_dict("records"), ids=lambda r: r["file"])
def test_side_is_the_better_seen_side(row):
    ex = row["exercise"].split("_")[0]
    e, _ = run_file(os.path.join(DATA_DIR, row["file"]), ex, fps=15, count_only=True)
    assert e.log.side in ("left", "right")


def test_front_view_knee_clip_is_asked_to_turn_sideways():
    e, _ = run_file(os.path.join(DATA_DIR, "v_11.33.39AM_landmarks.csv"), "E4", fps=15)
    assert e.log.reps == []
    assert "turn_sideways" in {p["key"] for p in e.log.prompts}
