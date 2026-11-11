"""
Non-blocking mp3 playback with a queue, so clips never talk over each other.

Windows: uses the built-in MCI player (winmm.dll) through ctypes, no extra
packages. Other systems: prints the clip name instead (good enough for tests).

Call poll() once per video frame; it starts the next queued clip when the
current one has finished.
"""
import ctypes
import os
import sys
from collections import deque

MAX_QUEUE = 3   # if prompts pile up, drop the oldest rather than lag behind the patient


class AudioPlayer:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.queue = deque(maxlen=MAX_QUEUE)
        self.playing = False
        self._mci = ctypes.windll.winmm.mciSendStringW if (enabled and sys.platform == "win32") else None

    def play(self, path):
        if self.enabled:
            self.queue.append(str(path))
        self.poll()

    def poll(self):
        if self.playing and self._is_playing():
            return
        self._close()
        while self.queue:
            path = self.queue.popleft()
            if not os.path.exists(path):
                print(f"[audio] missing file: {path}")
                continue
            self._start(path)
            return

    def stop(self):
        self.queue.clear()
        self._close()

    # ---- backend ----

    def _send(self, cmd):
        buf = ctypes.create_unicode_buffer(128)
        err = self._mci(cmd, buf, 128, 0)
        return err, buf.value

    def _start(self, path):
        if self._mci is None:
            print(f"[audio] {os.path.basename(path)}")
            return
        err, _ = self._send(f'open "{path}" type mpegvideo alias remove_fb')
        if err == 0:
            err, _ = self._send("play remove_fb")
        if err:
            print(f"[audio] could not play {path} (MCI error {err})")
            self._close()
        else:
            self.playing = True

    def _is_playing(self):
        if self._mci is None:
            return False
        err, mode = self._send("status remove_fb mode")
        return err == 0 and mode == "playing"

    def _close(self):
        if self._mci is not None and self.playing:
            self._send("close remove_fb")
        self.playing = False
