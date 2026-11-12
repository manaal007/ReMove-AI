"""
One live browser session: JPEG frames in -> SessionEngine -> JSON messages out.

No web framework and no camera in here, so it is easy to test: the pose
detector is passed in (api.pose_detector.PoseDetector in the app, a fake in
tests). api/server.py only moves bytes between the WebSocket and this class.

Protocol (browser -> server)
  text   {"type": "start", "mode": "calibration" | "session", "exercise": "E1",
          "lang": "ur" | "en", "timing": null | "every_rep" | "every_3_4_reps",
          "baseline": {...} | null, "patient_id": 1 | null}
  bytes  one JPEG frame, NOT mirrored (pose angles in config are unmirrored)
  text   {"type": "stop"}

Protocol (server -> browser)
  {"type": "ready", "mode", "exercise": {...}}                       after start
  {"type": "frame", "status": {...}, "points": {...} | null,
   "prompts": [...], "reps": [...]}                                  one per JPEG
  {"type": "baseline", "baseline": {...}}     calibration: baseline is ready
  {"type": "done", "summary": {...}}          set finished / stopped
  {"type": "error", "message": "..."}

The browser sends the next frame only after it gets the "frame" reply, so a
slow laptop never builds a backlog: the frame rate simply drops.

Calibration mode stops as soon as the engine has a baseline (min_reps clean
reps). Session mode is started with that baseline, so the engine goes straight
to scoring after the camera check, and every one of max_reps_per_set reps is
scored.
"""
import time

import numpy as np

from feedback.messages import LANGS, get_feedback, phrase_key
from session.config import TIMING_MODES, load_config
from session.engine import SessionEngine

# subject's right side only for now (config/exercises.yaml: side: right)
POINT_IDS = {"shoulder": 12, "elbow": 14, "wrist": 16, "hip": 24,
             "otherShoulder": 11, "otherHip": 23}
GOOD_KEYS = ("good", "start", "rest", "set_done")
MODES = ("calibration", "session")


def exercise_info(exercise_id, cfg=None):
    cfg = cfg or load_config(exercise_id)
    ex = cfg["exercise"]
    lo, hi = ex["target_range_deg"]
    return {
        "id": exercise_id, "name": ex["name"],
        "label_en": ex["label_en"], "label_ur": ex["label_ur"],
        "camera_view": ex["camera_view"], "side": ex["side"],
        "rest_deg": lo, "target_deg": hi, "max_safe_deg": ex["max_safe_deg"],
        "max_reps": cfg["caps"]["max_reps_per_set"],
        "ready": bool(ex.get("ready", True)),
        "baseline_reps": cfg["baseline"]["min_reps"],
    }


def prompt_dict(p):
    en, _ = get_feedback(p.key, "en")
    ur, _ = get_feedback(p.key, "ur")
    pk = phrase_key(p.key)
    return {
        "key": p.key, "reason": p.reason, "en": en, "ur": ur,
        "audio": {lang: f"/audio/{lang}_{pk}.mp3" for lang in LANGS},
        "tag": "good" if p.key in GOOD_KEYS else "adjust",
    }


def rep_dict(r):
    f = r["features"] or {}
    return {
        "n": r["n"], "phase": r["phase"], "label": r["label"], "faults": list(r["faults"]),
        "tag": "good" if r["label"] == "good" else "adjust",
        "lean": "trunk_compensation" in r["faults"],
        "peak": _round(f.get("peak_angle")), "rom": _round(f.get("rom")),
        "duration_s": _round(f.get("duration_s"), 2),
        "used_for_baseline": r.get("used_for_baseline", False),
    }


REQUIRED_BASELINE = ("rom", "duration_s", "peak_angle", "min_angle")


def clean_baseline(b):
    """Baseline sent back by the browser. If anything the rules need is missing,
    return None so the engine simply collects a new baseline itself."""
    if not isinstance(b, dict):
        return None
    out = {}
    for k in ("rom", "duration_s", "jerk_norm", "sparc", "peak_angle", "min_angle"):
        v = b.get(k)
        out[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    if any(out[k] is None for k in REQUIRED_BASELINE):
        return None
    return out


def _round(v, nd=1):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), nd)


def points(lm, min_vis=0.5):
    """Named landmark points (normalized 0-1, unmirrored) for the skeleton overlay."""
    if lm is None:
        return None
    out = {}
    for name, i in POINT_IDS.items():
        v = lm.get(f"v{i}")
        if v is not None and v >= min_vis:
            out[name] = [round(lm[f"x{i}"], 4), round(lm[f"y{i}"], 4)]
    return out or None


class LiveSession:
    def __init__(self, detector_factory, store=None, clock=time.monotonic):
        self.detector_factory = detector_factory
        self.store = store
        self.clock = clock
        self.detector = None
        self.engine = None
        self.cfg = None
        self.started = False
        self.finished = False
        self.baseline_sent = False
        self.n_reps = 0
        self.t0 = None
        self.last_ms = -1

    # ------------------------------------------------------------------ control

    def start(self, msg):
        mode = msg.get("mode", "session")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        lang = msg.get("lang", "ur")
        if lang not in LANGS:
            raise ValueError(f"lang must be one of {LANGS}")
        timing = msg.get("timing")
        if timing is not None and timing not in TIMING_MODES:
            raise ValueError(f"timing must be one of {TIMING_MODES}")
        self.exercise_id = msg.get("exercise", "E1")
        self.cfg = load_config(self.exercise_id)          # KeyError for an unknown exercise
        self.mode, self.lang, self.timing = mode, lang, timing
        self.baseline = clean_baseline(msg.get("baseline")) if mode == "session" else None
        self.patient_id = msg.get("patient_id")
        if self.detector is None:
            self.detector = self.detector_factory()
        self.started = True
        return [{"type": "ready", "mode": mode, "exercise": exercise_info(self.exercise_id, self.cfg)}]

    def frame(self, jpeg):
        if not self.started:
            raise RuntimeError("send a start message first")
        if self.finished:
            return [{"type": "frame", "status": {"phase": "done"}, "points": None, "prompts": [], "reps": []}]
        now = self.clock()
        if self.t0 is None:
            self.t0 = now
        t = now - self.t0
        ms = max(int(t * 1000), self.last_ms + 1)        # MediaPipe needs increasing timestamps
        self.last_ms = ms

        lm, gray, W, H = self.detector.detect(jpeg, ms)
        if self.engine is None:
            self.engine = SessionEngine(self.cfg, W, H, language=self.lang,
                                        timing=self.timing, baseline=self.baseline)
        prompts = self.engine.process(t, lm, gray)
        new = self.engine.log.reps[self.n_reps:]
        self.n_reps += len(new)

        out = [{
            "type": "frame",
            "status": self.engine.status(),
            "points": points(lm, self.cfg["visibility"]["min_landmark_visibility"]),
            "prompts": [prompt_dict(p) for p in prompts],
            "reps": [rep_dict(r) for r in new],
        }]

        if self.mode == "calibration" and self.engine.baseline is not None \
                and self.engine.phase == "scoring" and not self.baseline_sent:
            self.baseline_sent = True
            out.append({"type": "baseline", "baseline": dict(self.engine.baseline)})
            out += self._finish("calibration_done")
        elif self.engine.done:
            out += self._finish(self.engine.log.ended_reason)
        return out

    def stop(self, reason="user_stopped"):
        if self.finished or self.engine is None:
            self.finished = True
            return []
        return self._finish(reason)

    def close(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None

    # ------------------------------------------------------------------ end

    def _finish(self, reason):
        self.finished = True
        log = self.engine.stop(reason)
        reps = [rep_dict(r) for r in log.reps]
        scored = [r for r in reps if r["phase"] == "scoring" and r["peak"] is not None]
        peaks = [r["peak"] for r in scored]
        summary = {
            "mode": self.mode, "exercise": exercise_info(self.exercise_id, self.cfg),
            "ended_reason": log.ended_reason, "started_at": log.started_at, "ended_at": log.ended_at,
            "language": log.language, "timing": log.timing,
            "baseline": log.baseline, "baseline_restarts": log.baseline_restarts,
            "reps": reps,
            "scored_reps": len(scored),
            "good_reps": sum(r["label"] == "good" for r in scored),
            "avg_peak": round(float(np.mean(peaks)), 1) if peaks else None,
            "best_peak": max(peaks) if peaks else None,
        }
        if self.store is not None:
            summary["session_id"] = self.store.save_session(self.patient_id, summary, log.to_dict())
        return [{"type": "done", "summary": summary}]
