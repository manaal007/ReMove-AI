"""
Run MediaPipe PoseLandmarker (new Tasks API) on a video and save
33 landmarks per frame to CSV.

Usage (from inside remove-pk, with .venv active):
    python pose/extract_landmarks.py data/public/rehab24_6/Videos/Ex1/PM_000-Camera17-30fps.mp4
"""
import sys
import os
import urllib.request
import cv2
import pandas as pd
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

NUM_LM = 33
MODEL_PATH = os.path.join("models_store", "pose_landmarker_full.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)


def ensure_model():
    if os.path.exists(MODEL_PATH):
        return
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    print("Downloading pose model (one time)...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Saved:", MODEL_PATH)


def extract(video_path, out_csv=None):
    if not os.path.exists(video_path):
        print(f"Can't find video: {video_path}")
        return
    ensure_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("OpenCV could not open this video.")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    rows = []
    frame_idx = 0
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms = int(frame_idx * 1000 / fps)
            result = landmarker.detect_for_video(mp_image, ts_ms)

            row = {"frame": frame_idx, "time_s": frame_idx / fps}
            if result.pose_landmarks:
                lms = result.pose_landmarks[0]
                for i, lm in enumerate(lms):
                    row[f"x{i}"] = lm.x
                    row[f"y{i}"] = lm.y
                    row[f"z{i}"] = lm.z
                    row[f"v{i}"] = lm.visibility
            else:
                for i in range(NUM_LM):
                    row[f"x{i}"] = row[f"y{i}"] = row[f"z{i}"] = row[f"v{i}"] = None
            rows.append(row)
            frame_idx += 1

    cap.release()

    df = pd.DataFrame(rows)
    if out_csv is None:
        name = os.path.splitext(os.path.basename(video_path))[0]
        out_dir = os.path.join("data", "own")
        os.makedirs(out_dir, exist_ok=True)
        out_csv = os.path.join(out_dir, f"{name}_landmarks.csv")
    df.to_csv(out_csv, index=False)

    detected = df["x0"].notna().mean() * 100
    vis_cols = [f"v{i}" for i in range(NUM_LM)]
    print(f"Frames: {len(df)}  |  FPS: {fps:.1f}")
    print(f"Pose found in {detected:.1f}% of frames")
    print(f"Mean landmark visibility: {df[vis_cols].mean().mean():.2f}")
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pose/extract_landmarks.py path/to/video.mp4")
    else:
        extract(sys.argv[1])
