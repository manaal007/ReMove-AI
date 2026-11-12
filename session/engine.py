"""
Session engine: camera check -> baseline reps -> scored reps -> set done.

Pure state machine, no camera / audio / UI. Feed it one frame at a time with
process(t, lm, gray); it returns the prompts to show/play for that frame.
The same engine runs on a webcam, a video file, or synthetic test frames.

Phases
  check     camera check must pass for camera_check.pass_frames frames in a row
            (only once, before the session starts)
  baseline  first clean reps (min_reps..max_reps) become the person's baseline;
            if max_reps attempts give too few clean reps, say adjust_position
            and start the baseline again
  scoring   every rep gets one of the six labels (session.rules)
  done      set finished (max_reps_per_set) or stopped

Tracking loss after the start never goes back to the camera check. Short gaps
are ignored; after gap_frames_N lost frames the engine pauses silently, and it
resumes by itself (no "start") as soon as the arm is tracked again. A rep cut
off by tracking loss is logged as not_tracked.

Camera prompts (too_dark, step_back, not_tracked, ...) are spoken only when the
problem has lasted camera_check.issue_hold_s, and the same prompt is never
repeated within camera_check.prompt_every_s.

Feedback timing (feedback.timing, or the timing argument):
  every_rep        speak each rep's label right after the rep (a "good" on the
                   last rep of the set is skipped: set_done follows straight away)
  every_3_4_reps   collect block_size reps, then speak the most common fault
                   (session.rules.summarize_block). A partial block is spoken
                   before a rest prompt and at the end of the set.

caps.max_reps_per_set counts scored reps only: baseline reps (including failed
baseline attempts) do not count, so a bad baseline never ends the session.
caps.rest_prompt_after_reps counts every rep, baseline included, since rest is
about how many reps the patient has physically done.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

from capture.camera_check import check_frame
from feedback.messages import get_feedback
from features.signals import FPS, REQUIRED_LM, frame_signals, rep_features
from session.config import TIMING_MODES
from session.rep_counter import RepCounter
from session.rules import ABSOLUTE, build_baseline, label_rep, summarize_block

_NAN_ROW = {f"{c}{i}": np.nan for i in REQUIRED_LM for c in "xyv"}


@dataclass
class Prompt:
    key: str            # rep label or prompt key from feedback.messages
    text: str
    audio: str
    reason: str         # "rep" | "block" | "camera" | "session"


@dataclass
class RepRecord:
    n: int              # 1-based rep number in the set
    phase: str          # "baseline" | "scoring"
    start_frame: int
    end_frame: int
    start_t: float
    end_t: float
    label: str
    faults: list
    features: dict
    used_for_baseline: bool = False


@dataclass
class SessionLog:
    exercise_id: str
    language: str
    timing: str
    block_size: int
    started_at: str
    ended_at: Optional[str] = None
    ended_reason: Optional[str] = None
    baseline: Optional[dict] = None
    baseline_from_previous: bool = False
    baseline_restarts: int = 0
    reps: list = field(default_factory=list)
    prompts: list = field(default_factory=list)   # {"t", "key", "reason"}

    def to_dict(self):
        return asdict(self)


class SessionEngine:
    def __init__(self, cfg, width, height, language="ur", timing=None, baseline=None):
        timing = timing or cfg["feedback"]["timing"]
        if timing not in TIMING_MODES:
            raise ValueError(f"timing must be one of {TIMING_MODES}")
        self.cfg, self.W, self.H = cfg, width, height
        self.lang, self.timing = language, timing
        self.block_size = cfg["feedback"]["block_size"]
        self.priority = cfg["rules"]["priority"]
        self.log = SessionLog(cfg["exercise_id"], language, timing, self.block_size,
                              datetime.now().isoformat(timespec="seconds"))
        self.baseline = baseline
        if baseline is not None:
            self.log.baseline, self.log.baseline_from_previous = dict(baseline), True

        cc = cfg["camera_check"]
        self.hold_s, self.repeat_s = cc["issue_hold_s"], cc["prompt_every_s"]
        self.phase = "check"
        self.checking = True              # initial camera check (before start only)
        self.paused = False               # tracking lost after the start
        self.pause_since = None
        self.pass_count = 0
        self.issue = None                 # current camera issue, for the overlay
        self.issue_since = None
        self.last_spoken = {}             # camera prompt key -> t
        self.counter = None
        self.baseline_feats, self.baseline_attempts = [], 0
        self.block = []
        self.reps_done = 0                # all reps (rep numbers, rest prompts)
        self.scored_done = 0              # scoring-phase reps only (set cap)
        self.last_label = None

        self.i = -1
        self.ts, self.abd, self.elbow, self.lean, self.vis = [], [], [], [], []

    # ---------------------------------------------------------------- public

    @property
    def done(self):
        return self.phase == "done"

    def process(self, t, lm, gray):
        """One frame. lm: landmark dict (x/y/v per id) or None if no pose. Returns [Prompt]."""
        if self.done:
            return []
        self.i += 1
        self._append_signals(t, lm)
        out = []
        if self.checking:
            self._camera_check(t, lm, gray, out)
            return out
        for ev in self.counter.update(self.i, t, self.abd[-1]):
            if ev.kind == "lost":
                if ev.start is not None:
                    self._finish_rep(ev.start, ev.end, {"valid": False}, out, speak=False)
                self.paused = True
                # the loss began gap_frames_N frames ago
                self.pause_since = self.ts[-self.cfg["tracking"]["gap_frames_N"]]
                self.issue = "not_tracked"
            elif ev.kind == "found":
                self.paused, self.issue = False, None
            elif ev.kind == "rep":
                self._score_rep(ev.start, ev.end, out)
            if self.done:
                return out
        if self.paused:
            self._maybe_say_issue("not_tracked", self.pause_since, t, out)
        return out

    def stop(self, reason="user_stopped"):
        if not self.done:
            self._end(reason, [], speak=False)
        return self.log

    def status(self):
        """Snapshot for the on-screen overlay."""
        a = self.abd[-1] if self.abd else np.nan
        return {
            "phase": self.phase, "checking": self.checking, "paused": self.paused,
            "issue": self.issue,
            "reps_done": self.reps_done, "scored_reps": self.scored_done,
            "max_reps": self.cfg["caps"]["max_reps_per_set"],
            "baseline_reps": len(self.baseline_feats), "last_label": self.last_label,
            "angle": None if np.isnan(a) else float(a),
            "in_rep": bool(self.counter and self.counter.in_rep),
        }

    # ---------------------------------------------------------------- frames

    def _append_signals(self, t, lm):
        abd, elbow, lean, vis = frame_signals(
            lm if lm is not None else _NAN_ROW, self.W, self.H, min_vis=self.cfg["visibility"]["min_landmark_visibility"])
        self.ts.append(t)
        self.abd.append(float(abd[0]))
        self.elbow.append(float(elbow[0]))
        self.lean.append(float(lean[0]))
        self.vis.append(float(vis[0]))

    def _camera_check(self, t, lm, gray, out):
        issues = check_frame(lm, gray, self.cfg)
        if issues:
            self.pass_count = 0
            if issues[0] != self.issue:
                self.issue, self.issue_since = issues[0], t
            self._maybe_say_issue(self.issue, self.issue_since, t, out)
            return
        self.issue = self.issue_since = None
        self.pass_count += 1
        if self.pass_count >= self.cfg["camera_check"]["pass_frames"]:
            self.checking = False
            self.counter = RepCounter(self.cfg)
            if self.phase == "check":
                self.phase = "scoring" if self.baseline is not None else "baseline"
            self._say("start", "session", t, out)

    def _maybe_say_issue(self, key, since, t, out):
        """Speak a camera prompt only once the problem has lasted hold_s, and not
        again within repeat_s of the last time this prompt was spoken."""
        if t - since >= self.hold_s and t - self.last_spoken.get(key, -np.inf) >= self.repeat_s:
            self.last_spoken[key] = t
            self._say(key, "camera", t, out)

    # ---------------------------------------------------------------- reps

    def _score_rep(self, start, end, out):
        dt = self.ts[end] - self.ts[start]
        fps = (end - start) / dt if dt > 0 else FPS
        feat = rep_features(np.array(self.abd), np.array(self.elbow), np.array(self.lean),
                            np.array(self.vis), start, end, fps=fps,
                            window=self.cfg["tracking"]["smoothing_window"])
        self._finish_rep(start, end, feat, out, speak=True)

    def _finish_rep(self, start, end, feat, out, speak):
        phase = self.phase
        label, faults = label_rep(feat, self.cfg, self.baseline if phase == "scoring" else None)
        rec = RepRecord(self.reps_done + 1, phase, int(start), int(end),
                        self.ts[start], self.ts[end], label, faults, _clean(feat))
        self.reps_done += 1
        if phase == "scoring":
            self.scored_done += 1
        self.last_label = label
        t = self.ts[end]

        if phase == "baseline":
            self.baseline_attempts += 1
            if not any(f in ABSOLUTE for f in faults):
                self.baseline_feats.append(feat)
                rec.used_for_baseline = True
        self.log.reps.append(asdict(rec))

        caps = self.cfg["caps"]
        last_rep = phase == "scoring" and self.scored_done >= caps["max_reps_per_set"]
        self._feedback(label, t, out, speak and not (last_rep and label == "good"))

        if phase == "baseline":
            b = self.cfg["baseline"]
            if len(self.baseline_feats) >= b["min_reps"]:
                self.baseline = build_baseline(self.baseline_feats)
                self.log.baseline = dict(self.baseline)
                self.phase = "scoring"
            elif self.baseline_attempts >= b["max_reps"]:
                # too few clean reps: ask to adjust and collect the baseline again
                self.baseline_feats, self.baseline_attempts = [], 0
                self.block = []
                self.log.baseline_restarts += 1
                self._say("adjust_position", "session", t, out)

        if last_rep:
            self._end("set_done", out)
        elif self.reps_done % caps["rest_prompt_after_reps"] == 0:
            self._flush_block(t, out)
            self._say("rest", "session", t, out)

    # ---------------------------------------------------------------- feedback

    def _feedback(self, label, t, out, speak):
        if self.timing == "every_rep":
            if speak:
                self._say(label, "rep", t, out)
            return
        self.block.append(label)
        if len(self.block) >= self.block_size:
            self._flush_block(t, out)

    def _flush_block(self, t, out):
        if self.block:
            self._say(summarize_block(self.block, self.priority), "block", t, out)
            self.block = []

    def _say(self, key, reason, t, out):
        text, audio = get_feedback(key, self.lang)
        out.append(Prompt(key, text, str(audio), reason))
        self.log.prompts.append({"t": round(float(t), 3), "key": key, "reason": reason})

    def _end(self, reason, out, speak=True):
        t = self.ts[-1] if self.ts else 0.0
        if speak:
            self._flush_block(t, out)
            self._say("set_done", "session", t, out)
        self.phase = "done"
        self.checking = False
        self.log.ended_reason = reason
        self.log.ended_at = datetime.now().isoformat(timespec="seconds")


def _clean(feat):
    """numpy scalars -> plain Python, so the log is JSON / SQLite friendly."""
    out = {}
    for k, v in feat.items():
        if isinstance(v, (np.floating, float)):
            out[k] = None if np.isnan(v) else float(v)
        elif isinstance(v, (np.bool_, bool)):
            out[k] = bool(v)
        elif isinstance(v, np.integer):
            out[k] = int(v)
        else:
            out[k] = v
    return out
