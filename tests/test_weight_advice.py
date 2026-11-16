"""Weight guidance after a set (session/weight_advice.py), storage, the advice route,
and the weight being locked during a set."""
import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from session.config import CONFIG_DIR, load_config
from session.weight_advice import REASONS, advise, set_facts
from storage.db.store import Store

REF = 100.0                     # no-weight baseline range


@pytest.fixture
def cfg():
    return load_config("E3")


def facts(good=9, comp=0, rng=95.0, scored=10):
    return {"scored": scored, "good": good, "compensation": comp, "range": rng}


def adv(cfg, f=None, pain=1, current="none", max_level="heavy", ref=REF, prior=1):
    """prior: qualifying sessions in a row before this one (1 = this one completes the 2-for-2)."""
    return advise(f or facts(), pain, current, max_level, ref, cfg, prior_streak=prior)


# ---------------------------------------------------------------- config

def test_rules_are_in_config_and_marked_for_the_physio(cfg):
    g = cfg["weight_guidance"]
    assert g["levels"] == ["none", "light", "heavy"]
    assert (g["up"]["min_good_reps"], g["up"]["min_range_frac"], g["up"]["max_compensation_reps"], g["up"]["max_pain"]) == (8, 0.9, 0, 3)
    assert (g["down"]["max_range_frac"], g["down"]["min_compensation_reps"], g["down"]["min_pain"]) == (0.8, 3, 4)
    assert g["up"]["consecutive_sessions"] == 2
    text = (Path(CONFIG_DIR) / "thresholds.yaml").read_text(encoding="utf-8")
    block = text[text.index("weight_guidance:"):text.index("side_view:")]
    assert "TO CONFIRM WITH PHYSIO" in block


# ---------------------------------------------------------------- move up

def test_all_criteria_met_twice_in_a_row_moves_up_one_level(cfg):
    a = adv(cfg, facts(good=8, comp=0, rng=90.0), pain=3, prior=1)
    assert (a["action"], a["next"], a["reasons"]) == ("up", "light", ["all_criteria_met"])
    assert a["phrases"] == ["weight_up_light"] and not a["talk_to_physio"]
    assert a["range_frac"] == 0.9
    assert (a["up_qualified"], a["qualifying_streak"], a["sessions_needed"]) == (True, 2, 2)


# ---------------------------------------------------------------- 2-for-2 rule

def test_first_qualifying_session_stays_with_one_more_message(cfg):
    a = adv(cfg, prior=0)
    assert (a["action"], a["next"], a["reasons"]) == ("stay", "none", ["qualified_need_more"])
    assert a["phrases"] == ["weight_stay_one_more"]
    assert a["up_qualified"] and a["qualifying_streak"] == 1


def test_the_one_more_message_text():
    from feedback.messages import get_feedback
    assert get_feedback("weight_stay_one_more", "en")[0] == \
        "Stay at this weight. If next session goes as well, you can try the next weight."
    assert get_feedback("weight_stay_one_more", "ur")[0]


def test_a_longer_run_still_moves_up_only_one_level(cfg):
    a = adv(cfg, prior=5, current="none")
    assert (a["action"], a["next"]) == ("up", "light")


def test_session_count_comes_from_config(cfg):
    cfg["weight_guidance"]["up"]["consecutive_sessions"] = 3
    a = adv(cfg, prior=0)                                # 1 of 3: two more needed -> plain stay
    assert (a["action"], a["reasons"], a["phrases"]) == ("stay", ["qualified_need_more"], ["weight_stay"])
    a = adv(cfg, prior=1)                                # 2 of 3: one more -> "if next session goes as well"
    assert a["phrases"] == ["weight_stay_one_more"]
    a = adv(cfg, prior=2)                                # 3 of 3
    assert a["action"] == "up"
    cfg["weight_guidance"]["up"]["consecutive_sessions"] = 1
    assert adv(cfg, prior=0)["action"] == "up"           # 1 = the old immediate rule


def test_a_session_that_does_not_qualify_resets_the_run(cfg):
    a = adv(cfg, facts(good=7), prior=1)
    assert a["action"] == "stay" and not a["up_qualified"] and a["qualifying_streak"] == 0


def test_moving_down_stays_immediate(cfg):
    a = adv(cfg, pain=5, current="light", prior=0)       # one bad session is enough
    assert (a["action"], a["next"]) == ("down", "none")
    a = adv(cfg, facts(comp=3), current="heavy", prior=4)  # even after a good run
    assert (a["action"], a["next"]) == ("down", "light") and not a["up_qualified"]


def test_at_max_does_not_need_the_run(cfg):
    a = adv(cfg, current="light", max_level="light", prior=0)
    assert a["reasons"] == ["at_max"] and a["phrases"] == ["weight_at_max"] and a["up_qualified"]


def test_never_more_than_one_level_per_session(cfg):
    assert adv(cfg, current="none", max_level="heavy")["next"] == "light"
    assert adv(cfg, current="light", max_level="heavy")["next"] == "heavy"


@pytest.mark.parametrize("change,reason", [
    ({"f": facts(good=7)}, "few_good_reps"),
    ({"f": facts(comp=1)}, "some_compensation"),
    ({"pain": 3}, None),                               # pain 3 is still fine for moving up
    ({"f": facts(rng=89.0)}, "range_short"),
    ({"ref": None}, "no_reference"),
])
def test_each_up_criterion_is_needed(cfg, change, reason):
    a = adv(cfg, **change)
    if reason is None:
        assert a["action"] == "up"
    else:
        assert a["action"] == "stay" and reason in a["reasons"] and a["phrases"] == ["weight_stay"]


def test_up_pain_limit_comes_from_config(cfg):
    cfg["weight_guidance"]["up"]["max_pain"] = 2                  # physio makes it stricter
    a = adv(cfg, pain=3)
    assert a["action"] == "stay" and a["reasons"] == ["pain_some"]


def test_at_the_physios_max_stays_with_its_own_message(cfg):
    a = adv(cfg, current="light", max_level="light")
    assert (a["action"], a["next"], a["reasons"], a["phrases"]) == ("stay", "light", ["at_max"], ["weight_at_max"])


def test_unknown_physio_max_is_treated_as_no_weight(cfg):
    a = adv(cfg, current="none", max_level=None)
    assert a["max_level"] == "none" and a["action"] == "stay" and a["reasons"] == ["at_max"]


# ---------------------------------------------------------------- move down

def test_pain_four_moves_down_and_says_talk_to_physio(cfg):
    a = adv(cfg, pain=4, current="heavy")
    assert (a["action"], a["next"]) == ("down", "light")
    assert a["talk_to_physio"] and a["reasons"] == ["pain_high"]
    assert a["phrases"] == ["weight_down_light", "talk_to_physio"]


def test_compensation_in_three_reps_moves_down(cfg):
    a = adv(cfg, facts(comp=3), current="light")
    assert (a["action"], a["next"], a["reasons"]) == ("down", "none", ["compensation"])
    assert a["phrases"] == ["weight_down_none"] and not a["talk_to_physio"]


def test_range_drop_over_20_percent_moves_down(cfg):
    assert adv(cfg, facts(rng=79.0), current="light")["reasons"] == ["range_drop"]
    assert adv(cfg, facts(rng=80.0), current="light")["action"] == "stay"   # exactly 20%: not more


def test_down_wins_over_up(cfg):
    a = adv(cfg, facts(good=10, comp=0, rng=100.0), pain=5, current="light")
    assert a["action"] == "down" and "pain_high" in a["reasons"]


def test_several_down_reasons_are_all_listed_but_one_level_only(cfg):
    a = adv(cfg, facts(comp=4, rng=50.0), pain=6, current="heavy")
    assert a["next"] == "light" and set(a["reasons"]) == {"pain_high", "compensation", "range_drop"}


def test_no_weight_cannot_go_lower_but_still_says_talk_to_physio(cfg):
    a = adv(cfg, pain=7, current="none")
    assert (a["action"], a["next"]) == ("stay", "none")
    assert a["phrases"] == ["weight_stay", "talk_to_physio"]


def test_without_a_reference_range_drop_is_off(cfg):
    a = adv(cfg, facts(rng=10.0), current="light", ref=None)
    assert a["action"] == "stay" and "range_drop" not in a["reasons"]


# ---------------------------------------------------------------- physio max

def test_never_above_the_physios_max(cfg):
    a = adv(cfg, current="heavy", max_level="none")              # max wins over one-level-per-session
    assert (a["action"], a["next"]) == ("down", "none") and a["reasons"][0] == "above_max"
    a = adv(cfg, current="heavy", max_level="light", pain=5)
    assert a["next"] == "light" and "pain_high" in a["reasons"]


def test_every_reason_code_is_known(cfg):
    for kw in ({}, {"pain": 5, "current": "heavy"}, {"current": "heavy", "max_level": "none"},
               {"f": facts(good=1, comp=1, rng=85)}, {"ref": None}, {"current": "light", "max_level": "light"}):
        assert set(adv(cfg, **kw)["reasons"]) <= set(REASONS)


@pytest.mark.parametrize("pain", [-1, 11, 2.5, None, "3"])
def test_bad_pain_is_refused(cfg, pain):
    with pytest.raises(ValueError):
        adv(cfg, pain=pain)


def test_bad_level_is_refused(cfg):
    with pytest.raises(ValueError):
        adv(cfg, current="medium")


# ---------------------------------------------------------------- facts from a session log

def rep(n, label="good", rom=95.0, phase="scoring", faults=None):
    return {"n": n, "phase": phase, "label": label, "faults": faults or ([] if label == "good" else [label]),
            "features": {"rom": rom} if rom is not None else {"valid": False}}


def test_set_facts_counts_scored_reps_only():
    log = {"reps": [rep(1, phase="baseline", rom=200.0), rep(2, rom=90.0), rep(3, rom=100.0),
                    rep(4, "trunk_compensation", rom=80.0), rep(5, "not_tracked", rom=None)]}
    f = set_facts(log)
    assert f == {"scored": 4, "good": 2, "compensation": 1, "range": 90.0}


def test_set_facts_counts_compensation_even_when_another_fault_is_spoken():
    f = set_facts({"reps": [rep(1, "too_fast", faults=["trunk_compensation", "too_fast"])]})
    assert f["compensation"] == 1


# ---------------------------------------------------------------- storage

OK = {"name": "P01", "age": "60", "side": "right", "pain": 2, "doctorOk": True,
      "recentInjury": False, "chestDizzy": False, "physioMaxWeight": "light"}


def summary(ex="E3", mode="session", weight="none", baseline=None, scored=10):
    return {"exercise": {"id": ex}, "mode": mode, "started_at": "t", "ended_at": "t", "ended_reason": "set_done",
            "scored_reps": scored, "good_reps": scored, "avg_peak": 100.0, "baseline": baseline,
            "weight": {"suggested": weight, "chosen": weight}}


def log_of(n_good=10, rom=95.0, comp=0):
    reps = [rep(i, rom=rom) for i in range(n_good)]
    reps += [rep(100 + i, "trunk_compensation", rom=rom) for i in range(comp)]
    return {"reps": reps}


def test_physio_max_is_saved_and_checked():
    s = Store(":memory:")
    assert s.get_patient(s.add_patient(OK))["max_weight"] == "light"
    assert s.get_patient(s.add_patient({**OK, "physioMaxWeight": None}))["max_weight"] is None
    with pytest.raises(ValueError):
        s.add_patient({**OK, "physioMaxWeight": "5kg"})


def test_no_weight_rom_is_the_latest_no_weight_baseline():
    s = Store(":memory:")
    pid = s.add_patient(OK)
    s.save_session(pid, summary(mode="calibration", baseline={"rom": 80.0}), {})
    s.save_session(pid, summary(mode="calibration", weight="light", baseline={"rom": 50.0}), {})
    s.save_session(pid, summary(mode="calibration", baseline={"rom": 110.0}), {})
    s.save_session(pid, summary(ex="E4", mode="calibration", baseline={"rom": 70.0}), {})
    assert s.no_weight_rom(pid, "E3") == 110.0
    assert s.no_weight_rom(pid, "E4") == 70.0
    assert s.no_weight_rom(pid + 1, "E3") is None


def test_advice_is_saved_with_the_session():
    s = Store(":memory:")
    sid = s.save_session(None, summary(), log_of())
    s.save_advice(sid, 2, {"action": "up", "next": "light"})
    row = s.get_session(sid)
    assert row["pain_after"] == 2 and row["advice"] == {"action": "up", "next": "light"}
    assert row["log"]["reps"][0]["label"] == "good"


def test_old_database_gets_the_new_columns(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE patients (id INTEGER PRIMARY KEY, created_at TEXT, name TEXT, age INTEGER,
        stroke_date TEXT, weak_side TEXT, pain INTEGER, conditions TEXT, doctor_ok INTEGER);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, patient_id INTEGER, exercise TEXT NOT NULL, mode TEXT NOT NULL,
        started_at TEXT, ended_at TEXT, ended_reason TEXT, scored_reps INTEGER, good_reps INTEGER, avg_peak REAL,
        baseline TEXT, log TEXT);""")
    db.close()
    s = Store(path)
    pcols = {r["name"] for r in s.db.execute("PRAGMA table_info(patients)")}
    scols = {r["name"] for r in s.db.execute("PRAGMA table_info(sessions)")}
    assert "max_weight" in pcols and {"pain_after", "advice", "weight"} <= scols


# ---------------------------------------------------------------- the advice route

def _app(store):
    from api.server import create_app
    return create_app(store=store, detector_factory=lambda: None, bottle_factory=lambda cfg: None)


def _post(app, sid, body):
    from tests.test_live import _http
    s, b = asyncio.run(_http(app, "POST", f"/api/sessions/{sid}/advice", body))
    return s, json.loads(b)


def test_route_two_good_sessions_in_a_row_then_up():
    store = Store(":memory:")
    pid = store.add_patient({**OK, "physioMaxWeight": "heavy"})
    store.save_session(pid, summary(mode="calibration", baseline={"rom": 100.0}), {})
    app = _app(store)
    first = store.save_session(pid, summary(), log_of(rom=95.0))
    status, body = _post(app, first, {"pain": 2})
    assert status == 200 and body["advice"]["action"] == "stay"
    assert [p["key"] for p in body["prompts"]] == ["weight_stay_one_more"]
    assert body["prompts"][0]["audio"]["en"] == "/audio/en_weight_stay_one_more.mp3"
    sid = store.save_session(pid, summary(), log_of(rom=95.0))
    status, body = _post(app, sid, {"pain": 2})
    assert status == 200
    a = body["advice"]
    assert (a["action"], a["current"], a["next"]) == ("up", "none", "light")
    assert a["range"] == 95.0 and a["no_weight_range"] == 100.0
    p = body["prompts"][0]
    assert p["key"] == "weight_up_light" and p["audio"]["ur"] == "/audio/ur_weight_up_light.mp3"
    assert p["en"] == "Well done! Next session, try a light weight." and p["ur"]
    row = store.get_session(sid)
    assert row["pain_after"] == 2 and row["advice"]["next"] == "light"


def test_route_pain_moves_down_with_physio_message():
    store = Store(":memory:")
    pid = store.add_patient(OK)                                     # max light
    sid = store.save_session(pid, summary(weight="light"), log_of())
    status, body = _post(_app(store), sid, {"pain": 6})
    assert status == 200 and body["advice"]["next"] == "none"
    assert [p["key"] for p in body["prompts"]] == ["weight_down_none", "talk_to_physio"]


@pytest.mark.parametrize("make,body,code", [
    (lambda s: 999, {"pain": 1}, 404),
    (lambda s: s.save_session(None, summary(ex="E1"), log_of()), {"pain": 1}, 400),   # no weight guidance for E1
    (lambda s: s.save_session(None, {**summary(), "weight": None}, log_of()), {"pain": 1}, 400),   # weight unknown
    (lambda s: s.save_session(None, summary(), log_of()), {"pain": 12}, 400),
    (lambda s: s.save_session(None, summary(), log_of()), {}, 400),
    (lambda s: s.save_session(None, summary(), log_of()), {"pain": True}, 400),
])
def test_route_errors(make, body, code):
    store = Store(":memory:")
    status, _ = _post(_app(store), make(store), body)
    assert status == code


def test_route_asking_again_for_the_same_session_does_not_count_it_twice():
    store = Store(":memory:")
    pid = store.add_patient({**OK, "physioMaxWeight": "heavy"})
    store.save_session(pid, summary(mode="calibration", baseline={"rom": 100.0}), {})
    sid = store.save_session(pid, summary(), log_of(rom=95.0))
    app = _app(store)
    assert _post(app, sid, {"pain": 1})[1]["advice"]["action"] == "stay"
    assert _post(app, sid, {"pain": 1})[1]["advice"]["action"] == "stay"


# ---------------------------------------------------------------- the qualifying run in storage

def _saved(store, pid, weight="none", qualified=True, advice=True, ex="E3", mode="session"):
    sid = store.save_session(pid, summary(ex=ex, mode=mode, weight=weight), {})
    if advice:
        store.save_advice(sid, 1, {"up_qualified": qualified})
    return sid


def test_streak_counts_good_sessions_in_a_row_at_the_same_weight():
    s = Store(":memory:")
    pid = s.add_patient(OK)
    _saved(s, pid)
    _saved(s, pid)
    now = _saved(s, pid, advice=False)
    assert s.qualifying_streak(pid, "E3", "none", now) == 2


@pytest.mark.parametrize("breaker", [
    {"qualified": False},                    # not all conditions met
    {"weight": "light"},                     # another weight in between
    {"advice": False},                       # pain never asked: cannot know
])
def test_streak_is_broken(breaker):
    s = Store(":memory:")
    pid = s.add_patient(OK)
    _saved(s, pid)
    _saved(s, pid, **breaker)
    now = _saved(s, pid, advice=False)
    assert s.qualifying_streak(pid, "E3", "none", now) == 0


def test_streak_ignores_calibration_other_exercises_and_other_patients():
    s = Store(":memory:")
    pid, other = s.add_patient(OK), s.add_patient(OK)
    _saved(s, pid)
    _saved(s, pid, mode="calibration", qualified=False)
    _saved(s, pid, ex="E4", qualified=False)
    _saved(s, other, qualified=False)
    now = _saved(s, pid, advice=False)
    assert s.qualifying_streak(pid, "E3", "none", now) == 1
    assert s.qualifying_streak(None, "E3", "none", now) == 0


def test_older_saved_advice_without_the_flag_does_not_count():
    s = Store(":memory:")
    pid = s.add_patient(OK)
    sid = s.save_session(pid, summary(), {})
    s.save_advice(sid, 1, {"action": "stay"})            # saved before the 2-for-2 rule
    now = _saved(s, pid, advice=False)
    assert s.qualifying_streak(pid, "E3", "none", now) == 0


# ---------------------------------------------------------------- never during a set

def test_weight_cannot_change_once_the_set_has_started():
    from api.live import LiveSession
    from tests.synth import SIDE_H, SIDE_W, side_pose
    from tests.test_live import Clock, FakeDetector, run
    from tests.test_weight_live import WINDOW_FRAMES, FakeBottle
    det = FakeDetector(size=(SIDE_W, SIDE_H))
    live = LiveSession(lambda: det, clock=Clock(), bottle_factory=lambda cfg: FakeBottle())
    live.start({"type": "start", "mode": "calibration", "exercise": "E3", "side": "left"})
    run(live, det, [side_pose("E3", 10, side="left")] * WINDOW_FRAMES)
    live.choose_weight("light")
    run(live, det, [side_pose("E3", 10, side="left")] * 5)            # the set has started
    with pytest.raises(ValueError, match="during a set"):
        live.choose_weight("heavy")
    assert live.weight["chosen"] == "light"


def test_weight_given_at_start_cannot_be_changed():
    from api.live import LiveSession
    from tests.test_live import Clock, FakeDetector
    live = LiveSession(lambda: FakeDetector(), clock=Clock(), bottle_factory=lambda cfg: None)
    live.start({"type": "start", "mode": "session", "exercise": "E3", "weight": "light"})
    with pytest.raises(ValueError, match="during a set"):
        live.choose_weight("none")
