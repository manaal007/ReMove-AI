"""Weight check with the real bottle detector on our own raw clips (data/own/raw, not in git).
Skipped when the videos or the model are not on this machine.
research/eval_weight_check.py prints the full table (all windows, not only the first)."""
import os

import pandas as pd
import pytest

pytest.importorskip("mediapipe")
from research.eval_weight_check import LMS, RAW, clip_observations, vote  # noqa: E402
from session.config import load_config  # noqa: E402

MANIFEST = os.path.join(LMS, "manifest.csv")
MODEL = load_config("E3")["weight_check"]["model"]
if not (os.path.exists(MANIFEST) and os.path.isdir(RAW) and os.path.exists(MODEL)):
    pytest.skip("own raw clips or detector model not present", allow_module_level=True)

M = pd.read_csv(MANIFEST)
M = M[M["file"].map(lambda f: os.path.exists(os.path.join(RAW, f.replace("_landmarks.csv", ".mp4"))))]


@pytest.fixture(scope="module")
def first_windows():
    from api.object_detector import BottleDetector
    det = BottleDetector(MODEL)
    window = load_config("E3")["weight_check"]["window_s"]
    out = {}
    for _, r in M.iterrows():
        name, ex_id = r["file"].replace("_landmarks.csv", ""), r["exercise"].split("_")[0]
        cfg, obs = clip_observations(name, ex_id, 15.0, det, max_t=window + 1.0)
        out[name] = (r["weight_seen"], vote(cfg, ex_id, obs, 0.0))
    det.close()
    return out


def test_first_window_tells_weight_from_none(first_windows):
    """P01/P02 curls hold a bottle, P02 knee clips have bottles at the ankle, P01 knee clips none."""
    judged = {k: (truth, res["suggested"]) for k, (truth, res) in first_windows.items() if res is not None}
    assert len(judged) >= 10                     # 11.33.34 is a 2 s clip: shorter than the window
    wrong = {k: v for k, v in judged.items() if (v[0] == "none") != (v[1] == "none")}
    assert not wrong, wrong


def test_no_weight_clips_are_never_called_a_weight(first_windows):
    for name, (truth, res) in first_windows.items():
        if truth == "none" and res is not None:
            assert res["suggested"] == "none", name


def test_small_bottles_are_light_not_heavy(first_windows):
    """Every bottle in these clips is a small drinks bottle."""
    assert all(res["suggested"] != "heavy" for _, res in first_windows.values() if res is not None)
