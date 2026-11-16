"""MediaPipe Object Detector (EfficientDet-Lite0, COCO) limited to "bottle", for the
weight check before calibration (capture/weight_check.py).

Runs on a crop around the wrist / ankle, IMAGE mode (crops change size every frame).
"""
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from capture.weight_check import Box

ROOT = Path(__file__).resolve().parent.parent
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/object_detector/"
             "efficientdet_lite0/float16/latest/efficientdet_lite0.tflite")


class BottleDetector:
    def __init__(self, model_path, score_threshold=0.1):
        path = Path(model_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Object detector model missing: {path}. Download it from {MODEL_URL}")
        options = vision.ObjectDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE, category_allowlist=["bottle"],
            score_threshold=score_threshold, max_results=5)
        self.detector = vision.ObjectDetector.create_from_options(options)

    def detect(self, rgb, region):
        """Bottle boxes in full-frame pixels. rgb: H x W x 3 uint8; region: (x0, y0, x1, y1) crop."""
        x0, y0, x1, y1 = region
        crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
        res = self.detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop))
        out = []
        for d in res.detections:
            b = d.bounding_box
            out.append(Box(b.origin_x + x0, b.origin_y + y0, b.width, b.height, d.categories[0].score))
        return out

    def close(self):
        self.detector.close()
