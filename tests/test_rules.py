"""Six-label rules (session/rules.py)."""
import pytest

from session.config import load_config
from session.rules import build_baseline, find_faults, label_rep, summarize_block

BASE = {"rom": 80.0, "duration_s": 3.0, "jerk_norm": 1000.0, "sparc": -1.5,
        "peak_angle": 90.0, "min_angle": 10.0}


@pytest.fixture(scope="module")
def cfg():
    return load_config("E1")


def rep(**kw):
    f = {"valid": True, "rom": 80.0, "duration_s": 3.0, "jerk_norm": 1000.0, "sparc": -1.5,
         "peak_angle": 90.0, "min_angle": 10.0, "trunk_lean_max": 2.0}
    f.update(kw)
    return f


def test_good(cfg):
    assert label_rep(rep(), cfg, BASE) == ("good", [])


@pytest.mark.parametrize("kw,label", [
    ({"valid": False}, "not_tracked"),
    ({"trunk_lean_max": 12.0}, "trunk_compensation"),
    ({"duration_s": 1.9}, "too_fast"),            # < 0.65 x 3.0 s
    ({"sparc": -1.85}, "jerky"),                  # 1.23x less smooth than -1.5
    ({"rom": 60.0, "peak_angle": 70.0}, "reduced_range"),  # < 0.8 x 80 deg
])
def test_each_label(cfg, kw, label):
    assert label_rep(rep(**kw), cfg, BASE)[0] == label


def test_cut_off_values(cfg):
    assert cfg["rules"]["too_fast_frac"] == 0.65
    assert cfg["rules"]["reduced_range_frac"] == 0.8
    assert cfg["rules"]["jerky_sparc_ratio"] == 1.2
    assert "jerky_ratio" not in cfg["rules"]


@pytest.mark.parametrize("key,value", [
    ("trunk_lean_max", lambda c: c["exercise"]["max_trunk_lean_deg"]),       # at the limit, not over
    ("duration_s", lambda c: c["rules"]["too_fast_frac"] * BASE["duration_s"]),
    ("sparc", lambda c: c["rules"]["jerky_sparc_ratio"] * BASE["sparc"]),
    ("rom", lambda c: c["rules"]["reduced_range_frac"] * BASE["rom"]),
])
def test_boundaries_are_not_faults(cfg, key, value):
    assert label_rep(rep(**{key: value(cfg)}), cfg, BASE)[0] == "good"


def test_just_past_boundaries_are_faults(cfg):
    r = cfg["rules"]
    assert label_rep(rep(duration_s=r["too_fast_frac"] * 3.0 - 0.01), cfg, BASE)[0] == "too_fast"
    assert label_rep(rep(rom=r["reduced_range_frac"] * 80.0 - 0.1, peak_angle=70.0),
                     cfg, BASE)[0] == "reduced_range"
    assert label_rep(rep(sparc=r["jerky_sparc_ratio"] * -1.5 - 0.01), cfg, BASE)[0] == "jerky"


def test_jerky_ignores_jerk_norm(cfg):
    # a slow smooth rep can have a huge jerk_norm from tracking noise; it must not matter
    assert label_rep(rep(jerk_norm=1e9, duration_s=6.2), cfg, BASE)[0] == "good"


@pytest.mark.parametrize("feat_sparc,base_sparc", [(float("nan"), -1.5), (-3.0, None), (-3.0, float("nan"))])
def test_jerky_skipped_when_sparc_missing(cfg, feat_sparc, base_sparc):
    base = dict(BASE, sparc=base_sparc)
    assert "jerky" not in find_faults(rep(sparc=feat_sparc), cfg, base)


def test_jerky_skipped_for_old_baseline_without_sparc(cfg):
    old = {k: v for k, v in BASE.items() if k != "sparc"}
    assert "jerky" not in find_faults(rep(sparc=-9.0), cfg, old)


def test_priority_order(cfg):
    label, faults = label_rep(rep(trunk_lean_max=15, duration_s=1.0, sparc=-5.0, rom=30), cfg, BASE)
    assert label == "trunk_compensation"
    assert faults == ["trunk_compensation", "too_fast", "jerky", "reduced_range"]


def test_reference_range_is_capped_at_max_safe(cfg):
    from session.rules import reference_rom
    # healthy tester: baseline 10 -> 160 deg. Reference = min(150, 100 - 10) = 90
    base = dict(BASE, rom=150.0, peak_angle=160.0, min_angle=10.0)
    assert reference_rom(base, cfg) == 90.0
    # patient-like baseline below the cap: reference is their own range
    assert reference_rom(BASE, cfg) == 80.0


def test_never_ask_above_max_safe(cfg):
    base = dict(BASE, rom=150.0, peak_angle=160.0, min_angle=10.0)   # cut-off 0.8 x 90 = 72
    assert label_rep(rep(rom=95.0, peak_angle=105.0), cfg, base)[0] == "good"   # reached max_safe
    assert label_rep(rep(rom=75.0, peak_angle=85.0), cfg, base)[0] == "good"    # reached 0.8 x safe target
    assert label_rep(rep(rom=60.0, peak_angle=70.0), cfg, base)[0] == "reduced_range"


def test_high_rest_angle_lowers_reference(cfg):
    from session.rules import reference_rom
    base = dict(BASE, rom=80.0, min_angle=40.0)       # rests at 40: reference = min(80, 60) = 60
    assert reference_rom(base, cfg) == 60.0
    assert label_rep(rep(rom=50.0, peak_angle=90.0), cfg, base)[0] == "good"    # 50 >= 48
    assert label_rep(rep(rom=45.0, peak_angle=85.0), cfg, base)[0] == "reduced_range"


def test_without_baseline_only_absolute_rules(cfg):
    assert find_faults(rep(duration_s=0.5, rom=5), cfg, None) == []
    assert find_faults(rep(trunk_lean_max=20), cfg, None) == ["trunk_compensation"]
    assert find_faults({"valid": False}, cfg, None) == ["not_tracked"]


def test_baseline_is_median():
    b = build_baseline([rep(rom=70), rep(rom=80), rep(rom=200)])
    assert b["rom"] == 80


def test_baseline_skips_missing_sparc():
    b = build_baseline([rep(sparc=-1.4), rep(sparc=float("nan")), rep(sparc=-1.6)])
    assert b["sparc"] == pytest.approx(-1.5)
    assert build_baseline([rep(sparc=float("nan"))])["sparc"] is None


@pytest.mark.parametrize("labels,expected", [
    (["good", "good", "good"], "good"),
    (["good", "jerky", "good"], "jerky"),
    (["jerky", "too_fast", "jerky"], "jerky"),
    (["reduced_range", "too_fast", "good"], "too_fast"),          # tie -> priority
    (["reduced_range", "reduced_range", "trunk_compensation", "good"], "reduced_range"),
])
def test_summarize_block(cfg, labels, expected):
    assert summarize_block(labels, cfg["rules"]["priority"]) == expected
