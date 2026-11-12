"""SQLite store for patients and session logs (standard library only).

File: storage/db/remove.db (ignored by git). Pass ":memory:" in tests.
"""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "remove.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,       -- patient ID or first name only (no full names)
    age INTEGER,
    stroke_date TEXT,
    weak_side TEXT,
    pain INTEGER,
    conditions TEXT,          -- JSON list
    doctor_ok INTEGER,
    recent_injury INTEGER,    -- fracture / dislocation / surgery in the last 6 weeks
    chest_symptoms INTEGER    -- chest pain, dizziness or breathlessness on movement
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    exercise TEXT NOT NULL,
    mode TEXT NOT NULL,       -- calibration | session
    started_at TEXT,
    ended_at TEXT,
    ended_reason TEXT,
    scored_reps INTEGER,
    good_reps INTEGER,
    avg_peak REAL,
    baseline TEXT,            -- JSON
    log TEXT                  -- JSON, the full SessionLog
);
"""


class Store:
    def __init__(self, path=DEFAULT_PATH):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            # older remove.db files: add the safety columns if they are missing
            cols = {r["name"] for r in self.db.execute("PRAGMA table_info(patients)")}
            for col in ("recent_injury", "chest_symptoms"):
                if col not in cols:
                    self.db.execute(f"ALTER TABLE patients ADD COLUMN {col} INTEGER")
            self.db.commit()

    def add_patient(self, p):
        name = str(p.get("name", "")).strip()
        if not name:
            raise ValueError("name is required")
        if len(name) > MAX_NAME:
            raise ValueError(f"use a patient ID or first name (max {MAX_NAME} characters)")
        stop = safety_stop(p)
        if stop:
            raise ValueError(f"safety check: {stop}")
        with self.lock, self.db:
            cur = self.db.execute(
                "INSERT INTO patients (created_at, name, age, stroke_date, weak_side, pain, conditions, doctor_ok, "
                "recent_injury, chest_symptoms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), name, _int(p.get("age")), p.get("strokeDate") or None,
                 p.get("side"), _int(p.get("pain")), json.dumps(p.get("conditions") or []),
                 _bool(p.get("doctorOk")), _bool(p.get("recentInjury")), _bool(p.get("chestDizzy"))))
            return cur.lastrowid

    def get_patient(self, pid):
        with self.lock:
            row = self.db.execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["conditions"] = json.loads(d["conditions"] or "[]")
        return d

    def save_session(self, patient_id, summary, log):
        with self.lock, self.db:
            cur = self.db.execute(
                "INSERT INTO sessions (patient_id, exercise, mode, started_at, ended_at, ended_reason, "
                "scored_reps, good_reps, avg_peak, baseline, log) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (patient_id, summary["exercise"]["id"], summary["mode"], summary["started_at"], summary["ended_at"],
                 summary["ended_reason"], summary["scored_reps"], summary["good_reps"], summary["avg_peak"],
                 json.dumps(summary["baseline"]), json.dumps(log, ensure_ascii=False)))
            return cur.lastrowid

    def list_sessions(self, patient_id, exercise=None, mode="session", limit=20):
        q = ("SELECT id, exercise, mode, started_at, ended_at, ended_reason, scored_reps, good_reps, avg_peak "
             "FROM sessions WHERE patient_id = ? AND mode = ?")
        args = [patient_id, mode]
        if exercise:
            q += " AND exercise = ?"
            args.append(exercise)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.lock:
            rows = self.db.execute(q, args).fetchall()
        return [dict(r) for r in reversed(rows)]

    def latest_baseline(self, patient_id, exercise):
        """Most recent baseline for this patient + exercise, so calibration can be skipped next time."""
        with self.lock:
            row = self.db.execute(
                "SELECT baseline FROM sessions WHERE patient_id = ? AND exercise = ? AND baseline IS NOT NULL "
                "AND baseline != 'null' ORDER BY id DESC LIMIT 1", (patient_id, exercise)).fetchone()
        return json.loads(row["baseline"]) if row else None

    def close(self):
        self.db.close()


MAX_NAME = 40
PAIN_STOP = 7


def safety_stop(p):
    """Reason the patient must not start, or None. Same rules as web/src/pages/History.jsx.
    Starting values: confirm with the physiotherapy advisor."""
    if p.get("chestDizzy") is True:
        return "chest pain, dizziness or breathlessness on movement"
    if p.get("recentInjury") is True:
        return "fracture, dislocation or surgery in the last 6 weeks"
    if p.get("doctorOk") is False:
        return "doctor has not allowed exercise"
    pain = _int(p.get("pain"))
    if pain is not None and pain >= PAIN_STOP:
        return f"pain {pain}/10 today"
    return None


def _bool(v):
    return None if v is None else int(bool(v))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
