"""MediaPipe PoseLandmarker on JPEG bytes, for api.live.LiveSession.

One detector per browser session: VIDEO mode keeps tracking state between
frames and needs increasing timestamps, so detectors are never shared.
"""
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from capture.camera_check import mean_gray
from pose.extract_landmarks import MODEL_PATH

ROOT = Path(__file__).resolve().parent.parent
LM_IDS = (0, 11, 12, 13, 14, 15, 16, 23, 24)   # what the engine and camera check use


class PoseDetector:
    def __init__(self, model_path=ROOT / MODEL_PATH):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Pose model missing: {model_path}. Run pose/extract_landmarks.py once to download it.")
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO, num_poses=1,
            min_pose_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.landmarker = vision.PoseLandmarker.create_from_options(options)

    def detect(self, jpeg, t_ms):
        """Returns (landmark dict or None, mean gray 0-255, width, height)."""
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("could not decode JPEG frame")
        H, W = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = self.landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(t_ms))
        lm = None
        if result.pose_landmarks:
            lms = result.pose_landmarks[0]
            lm = {}
            for i in LM_IDS:
                lm[f"x{i}"], lm[f"y{i}"], lm[f"v{i}"] = lms[i].x, lms[i].y, lms[i].visibility
        return lm, mean_gray(img[::4, ::4]), W, H

    def close(self):
        self.landmarker.close()
