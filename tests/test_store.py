"""Health form safety rules and storage (no camera, no server)."""
import sqlite3

import pytest

from api.live import exercise_info
from storage.db.store import Store, safety_stop

OK = {"name": "P01", "age": "58", "side": "right", "pain": 2, "conditions": [],
      "doctorOk": True, "recentInjury": False, "chestDizzy": False}


def test_safe_patient_is_saved_with_safety_answers():
    s = Store(":memory:")
    p = s.get_patient(s.add_patient(OK))
    assert p["name"] == "P01"
    assert p["doctor_ok"] == 1 and p["recent_injury"] == 0 and p["chest_symptoms"] == 0


@pytest.mark.parametrize("change", [
    {"chestDizzy": True},
    {"recentInjury": True},
    {"doctorOk": False},
    {"pain": 7},
    {"pain": "9"},
])
def test_unsafe_answers_are_refused(change):
    assert safety_stop({**OK, **change})
    with pytest.raises(ValueError, match="safety check"):
        Store(":memory:").add_patient({**OK, **change})


def test_pain_below_cutoff_and_unanswered_are_not_stops():
    assert safety_stop({**OK, "pain": 6}) is None
    assert safety_stop({"name": "P02"}) is None      # the form itself requires answers


def test_long_name_is_refused():
    with pytest.raises(ValueError, match="patient ID or first name"):
        Store(":memory:").add_patient({**OK, "name": "x" * 41})


def test_old_database_gets_safety_columns(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE patients (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, "
               "name TEXT NOT NULL, age INTEGER, stroke_date TEXT, weak_side TEXT, pain INTEGER, "
               "conditions TEXT, doctor_ok INTEGER)")
    db.commit()
    db.close()
    s = Store(path)
    assert s.get_patient(s.add_patient(OK))["chest_symptoms"] == 0
    s.close()


def test_only_tested_exercises_are_ready():
    assert exercise_info("E1")["ready"] is True
    assert exercise_info("E2")["ready"] is False
