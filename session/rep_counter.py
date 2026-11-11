"""
Live rep detection from the shoulder abduction angle, one frame at a time.

How a rep is found (all relative to the person's own resting angle, so it
works for someone who rests at 10 deg and someone who rests at 30 deg):

  REST : track the lowest angle so far (rest_min) and the latest frame near it.
         When the angle rises more than start_margin above rest_min -> UP.
         The rep starts at that latest low frame (not when the threshold is crossed).
  UP   : track the peak. When the angle falls back within end_margin of the
         starting angle, the rep ends. It counts only if peak - start >= min_rom
         and it lasted at least min_duration_s (drops quick wind-up / follow-through
         swings). A "rep" longer than max_duration_s is dropped.

Tracking: NaN angles (landmarks not seen) are skipped. After gap_frames_N NaN
frames in a row a "lost" event fires once (with the rep start if a rep was in
progress), and the counter resets. The next good frame fires "found".

Detection uses a trailing moving average (only past frames, so it is causal);
reported frame numbers are shifted back by the average's lag so the rep window
lines up with the raw signal that rep_features() smooths itself.
"""
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

LOW_TOL_DEG = 3.0   # frames within this of rest_min count as "still resting"


@dataclass
class RepEvent:
    kind: str                       # "rep" | "lost" | "found"
    start: Optional[int] = None     # first frame of the rep (rep, or lost mid-rep)
    end: Optional[int] = None       # last frame of the rep
    peak: Optional[float] = None


class RepCounter:
    def __init__(self, cfg):
        rd = cfg["rep_detection"]
        self.start_margin = rd["start_margin_deg"]
        self.end_margin = rd["end_margin_deg"]
        self.min_rom = rd["min_rom_deg"]
        self.max_duration = rd["max_duration_s"]
        self.min_duration = rd["min_duration_s"]
        self.gap_n = cfg["tracking"]["gap_frames_N"]
        self.window = cfg["tracking"]["smoothing_window"]
        self.lag = (self.window - 1) // 2
        self.reset()
        self.nan_run = 0
        self.lost = False

    def reset(self):
        self.state = "REST"
        self.recent = deque(maxlen=self.window)
        self.rest_min = np.inf
        self.last_low = self.last_low_t = None
        self.start = self.start_t = self.start_angle = self.peak = None

    @property
    def in_rep(self):
        return self.state == "UP"

    def _shift(self, i):
        return max(0, i - self.lag)

    def update(self, i, t, angle):
        """Feed frame i (time t seconds, angle degrees or NaN). Returns a list of RepEvent."""
        events = []
        if angle is None or np.isnan(angle):
            self.nan_run += 1
            if self.nan_run == self.gap_n and not self.lost:
                self.lost = True
                events.append(RepEvent("lost", start=self.start if self.in_rep else None, end=i))
                self.reset()
            return events

        self.nan_run = 0
        if self.lost:
            self.lost = False
            events.append(RepEvent("found"))

        self.recent.append(angle)
        s = float(np.mean(self.recent))

        if self.state == "REST":
            if s <= self.rest_min:
                self.rest_min = s
            if s <= self.rest_min + LOW_TOL_DEG:
                self.last_low, self.last_low_t = i, t
            if s > self.rest_min + self.start_margin:
                self.state = "UP"
                self.start = self._shift(self.last_low if self.last_low is not None else i)
                self.start_t = self.last_low_t if self.last_low_t is not None else t   # time of the rep start frame
                self.start_angle = self.rest_min
                self.peak = s
            return events

        # UP
        self.peak = max(self.peak, s)
        if t - self.start_t > self.max_duration:
            self.reset()
            self.rest_min, self.last_low, self.last_low_t = s, i, t
            return events
        if s <= self.start_angle + self.end_margin:
            if self.peak - self.start_angle >= self.min_rom and t - self.start_t >= self.min_duration:
                events.append(RepEvent("rep", start=self.start, end=self._shift(i), peak=self.peak))
            self.reset()
            self.recent.append(s)
            self.rest_min, self.last_low, self.last_low_t = s, i, t
        return events
