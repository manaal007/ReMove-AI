"""Six-label rules (session/rules.py)."""
import pytest

from session.config import load_config
from session.rules import build_baseline, find_faults, label_rep, summarize_block

BASE = {"rom": 80.0, "duration_s": 3.0, "jerk_norm": 1000.0, "peak_angle": 90.0, "min_angle": 10.0}


@pytest.fixture(scope="module")
def cfg():
    return load_config("E1")


def rep(**kw):
    f = {"valid": True, "rom": 80.0, "duration_s": 3.0, "jerk_norm": 1000.0,
         "peak_angle": 90.0, "min_angle": 10.0, "trunk_lean_max": 2.0}
    f.update(kw)
    return f


def test_good(cfg):
    assert label_rep(rep(), cfg, BASE) == ("good", [])


@pytest.mark.parametrize("kw,label", [
    ({"valid": False}, "not_tracked"),
    ({"trunk_lean_max": 12.0}, "trunk_compensation"),
    ({"duration_s": 1.4}, "too_fast"),
    ({"jerk_norm": 3100.0}, "jerky"),
    ({"rom": 50.0, "peak_angle": 60.0}, "reduced_range"),
])
def test_each_label(cfg, kw, label):
    assert label_rep(rep(**kw), cfg, BASE)[0] == label


@pytest.mark.parametrize("kw", [
    {"trunk_lean_max": 10.0},     # at the limit, not over
    {"duration_s": 1.5},          # exactly half
    {"jerk_norm": 3000.0},        # exactly 3x
    {"rom": 56.0},                # exactly 70%
])
def test_boundaries_are_not_faults(cfg, kw):
    assert label_rep(rep(**kw), cfg, BASE)[0] == "good"


def test_priority_order(cfg):
    label, faults = label_rep(rep(trunk_lean_max=15, duration_s=1.0, jerk_norm=9999, rom=30), cfg, BASE)
    assert label == "trunk_compensation"
    assert faults == ["trunk_compensation", "too_fast", "jerky", "reduced_range"]


def test_never_ask_above_max_safe(cfg):
    base = dict(BASE, rom=150.0, peak_angle=160.0)
    # 100 deg rom is < 70% of 150, but the peak already reached max_safe_deg (100)
    assert label_rep(rep(rom=95.0, peak_angle=105.0), cfg, base)[0] == "good"
    assert label_rep(rep(rom=80.0, peak_angle=90.0), cfg, base)[0] == "reduced_range"


def test_without_baseline_only_absolute_rules(cfg):
    assert find_faults(rep(duration_s=0.5, rom=5), cfg, None) == []
    assert find_faults(rep(trunk_lean_max=20), cfg, None) == ["trunk_compensation"]
    assert find_faults({"valid": False}, cfg, None) == ["not_tracked"]


def test_baseline_is_median():
    b = build_baseline([rep(rom=70), rep(rom=80), rep(rom=200)])
    assert b["rom"] == 80


@pytest.mark.parametrize("labels,expected", [
    (["good", "good", "good"], "good"),
    (["good", "jerky", "good"], "jerky"),
    (["jerky", "too_fast", "jerky"], "jerky"),
    (["reduced_range", "too_fast", "good"], "too_fast"),          # tie -> priority
    (["reduced_range", "reduced_range", "trunk_compensation", "good"], "reduced_range"),
])
def test_summarize_block(cfg, labels, expected):
    assert summarize_block(labels, cfg["rules"]["priority"]) == expected
