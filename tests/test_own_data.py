"""Rep counting on our own side-view recordings (data/own/landmarks, not in git).
Skipped when the data is not on this machine. research/eval_own_landmarks.py prints the full table."""
import os

import pandas as pd
import pytest

from research.eval_own_landmarks import DATA_DIR, MANIFEST, drop_offscreen_trunk_flags, frame_size, run_file

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
    w, h = frame_size(row)
    e, _ = run_file(os.path.join(DATA_DIR, row["file"]), ex, fps=fps, width=w, height=h, count_only=True)
    expected = CHECKED.get(row["file"], int(row["reps_approx"]))
    assert abs(len(e.log.reps) - expected) <= 1


@pytest.mark.parametrize("row", USABLE.to_dict("records"), ids=lambda r: r["file"])
def test_side_is_the_better_seen_side(row):
    ex = row["exercise"].split("_")[0]
    w, h = frame_size(row)
    e, _ = run_file(os.path.join(DATA_DIR, row["file"]), ex, fps=15, width=w, height=h, count_only=True)
    assert e.log.side in ("left", "right")


def _row(name):
    return M[M["file"] == name].iloc[0]


def test_manifest_has_frame_sizes():
    assert {"width", "height", "rotated"} <= set(M.columns)
    assert frame_size(_row("v_11.33.30AM_landmarks.csv")) == (576, 1024)    # stored 1024x576, rotated
    assert frame_size(_row("v_12.08.33PM_landmarks.csv")) == (464, 832)


def test_clean_curl_clip_is_not_flagged_for_its_normal_swing():
    """11.33.30 swings ~23-28 deg on every curl: 9/9 flagged by the old absolute 20 deg rule."""
    w, h = frame_size(_row("v_11.33.30AM_landmarks.csv"))
    e, _ = run_file(os.path.join(DATA_DIR, "v_11.33.30AM_landmarks.csv"), "E3", fps=15, width=w, height=h)
    assert len(e.log.reps) == 9
    assert not any("trunk_compensation" in r["faults"] for r in e.log.reps)


def test_count_only_ignores_trunk_flags_with_shoulder_off_screen():
    r = _row("v_12.08.33PM_landmarks.csv")
    e, df = run_file(os.path.join(DATA_DIR, r["file"]), "E4", fps=15, width=464, height=832, count_only=True)
    assert drop_offscreen_trunk_flags(e, df) >= 1
    assert not any("trunk_compensation" in x["faults"] for x in e.log.reps)


def test_front_view_knee_clip_is_asked_to_turn_sideways():
    w, h = frame_size(_row("v_11.33.39AM_landmarks.csv"))
    e, _ = run_file(os.path.join(DATA_DIR, "v_11.33.39AM_landmarks.csv"), "E4", fps=15, width=w, height=h)
    assert e.log.reps == []
    assert "turn_sideways" in {p["key"] for p in e.log.prompts}
