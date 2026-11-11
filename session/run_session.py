"""
Run one E1 session in an OpenCV window (webcam or a video file).

Run from inside remove-pk, with .venv active:
    python session/run_session.py                          # webcam 0, Urdu, timing from config
    python session/run_session.py --lang en --timing every_3_4_reps
    python session/run_session.py --video data/public/rehab24_6/Videos/Ex1/PM_000-Camera17-30fps.mp4
    python session/run_session.py --video ... --mute --log session.json

Keys: q or Esc = stop.  The webcam view is mirrored for the patient; pose
tracking always runs on the unmirrored frame (angles in config are unmirrored).
On-screen text is English for whoever is testing; spoken feedback uses --lang.
"""
import argparse
import json
import os
import sys
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.getcwd())
from capture.camera_check import mean_gray  # noqa: E402
from feedback.audio_player import AudioPlayer  # noqa: E402
from feedback.messages import LANGS  # noqa: E402
from features.signals import L_HIP, L_SH, R_EL, R_HIP, R_SH, R_WR  # noqa: E402
from pose.extract_landmarks import MODEL_PATH, ensure_model  # noqa: E402
from session.config import TIMING_MODES, load_config  # noqa: E402
from session.engine import SessionEngine  # noqa: E402
from session.rules import reference_rom  # noqa: E402

WIN = "ReMove PK"
LM_IDS = (0, L_SH, R_SH, 13, R_EL, 15, R_WR, L_HIP, R_HIP)   # what the engine + check need
BONES = [(R_SH, R_EL), (R_EL, R_WR), (L_SH, R_SH), (L_HIP, R_HIP), (R_SH, R_HIP), (L_SH, L_HIP)]
GREEN, ORANGE, RED, WHITE, GREY = (80, 200, 80), (0, 160, 255), (60, 60, 230), (255, 255, 255), (160, 160, 160)
END_LINGER_S = 4.0   # keep the window open this long after the set ends, so set_done is heard


def landmarks_dict(result):
    if not result.pose_landmarks:
        return None
    lms = result.pose_landmarks[0]
    d = {}
    for i in LM_IDS:
        d[f"x{i}"], d[f"y{i}"], d[f"v{i}"] = lms[i].x, lms[i].y, lms[i].visibility
    return d


def draw_skeleton(frame, lm, W, H):
    if lm is None:
        return
    pt = lambda i: (int(lm[f"x{i}"] * W), int(lm[f"y{i}"] * H))  # noqa: E731
    for a, b in BONES:
        cv2.line(frame, pt(a), pt(b), (255, 200, 0) if R_EL in (a, b) or R_WR in (a, b) else GREY, 3)
    for i in (R_SH, R_EL, R_WR):
        cv2.circle(frame, pt(i), 6, (255, 200, 0), -1)


def put(frame, text, org, color=WHITE, scale=0.8, thick=2):
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def draw_status(frame, s, last_text):
    h = frame.shape[0]
    if s["phase"] == "done":
        head = "Set finished"
    elif s["checking"]:
        head = f"Camera check: {s['issue'] or 'hold still...'}"
    elif s["paused"]:
        head = "Paused: tracking lost"
    elif s["phase"] == "baseline":
        head = f"Baseline reps {s['baseline_reps']}"
    else:
        head = "Scoring"
    put(frame, head, (20, 40), ORANGE if (s["checking"] or s["paused"]) else WHITE)
    put(frame, f"Reps {s['reps_done']}/{s['max_reps']}", (20, 80), WHITE, 1.1, 3)
    if s["angle"] is not None:
        put(frame, f"Arm {s['angle']:.0f} deg{'  ^' if s['in_rep'] else ''}", (20, 120), GREY, 0.7)
    if s["last_label"]:
        c = GREEN if s["last_label"] == "good" else RED if s["last_label"] == "not_tracked" else ORANGE
        put(frame, s["last_label"].replace("_", " "), (20, h - 60), c, 1.0, 2)
    if last_text:
        put(frame, last_text, (20, h - 20), WHITE, 0.6, 1)


def _num(v, fmt):
    return format(v, fmt) if isinstance(v, (int, float)) else "-"


def _ratio(v, base):
    return f"{v / base:.2f}" if isinstance(v, (int, float)) and base else "-"


def print_summary(log, cfg):
    """End-of-session table: each rep's duration, range and peak next to the
    baseline and the exact cut-offs the rules used, so a label can be checked."""
    rules, ex = cfg["rules"], cfg["exercise"]
    b = log.baseline
    print(f"\nEnded: {log.ended_reason}   reps: {len(log.reps)}   "
          f"language={log.language}  timing={log.timing}  baseline restarts={log.baseline_restarts}")
    if b:
        src = "previous session" if log.baseline_from_previous else "this session"
        print(f"\nBaseline ({src}, median of clean calibration reps):")
        print(f"  duration {b['duration_s']:.2f} s   range {b['rom']:.1f} deg   "
              f"peak {b['peak_angle']:.1f} deg   rest {b['min_angle']:.1f} deg   smoothness (SPARC) {_num(b.get('sparc'), '.2f')}")
        print("Cut-offs used in scoring:")
        print(f"  too_fast       duration < {rules['too_fast_frac']} x {b['duration_s']:.2f} s "
              f"= {rules['too_fast_frac'] * b['duration_s']:.2f} s")
        ref = reference_rom(b, cfg)
        print(f"  reduced_range  range < {rules['reduced_range_frac']} x {ref:.1f} deg "
              f"= {rules['reduced_range_frac'] * ref:.1f} deg   AND peak < max_safe_deg {ex['max_safe_deg']}")
        print(f"                 (reference = min(baseline range {b['rom']:.1f}, "
              f"max_safe {ex['max_safe_deg']} - rest {b['min_angle']:.1f}) = {ref:.1f} deg)")
        if b.get("sparc") is not None:
            print(f"  jerky          SPARC < {rules['jerky_sparc_ratio']} x {b['sparc']:.2f} "
                  f"= {rules['jerky_sparc_ratio'] * b['sparc']:.2f}   (i.e. 'smooth x' column > {rules['jerky_sparc_ratio']})")
        else:
            print("  jerky          off (baseline has no SPARC value)")
        print(f"  trunk          lean > {ex['max_trunk_lean_deg']} deg")
    else:
        print("\nNo baseline was set, so only not_tracked / trunk_compensation could fire.")

    dur_b, rom_b, sparc_b = (b["duration_s"], b["rom"], b.get("sparc")) if b else (None, None, None)
    print(f"\n  {'rep':>3} {'phase':8} {'label':19} {'dur s':>6} {'x base':>6} {'range':>6} "
          f"{'x base':>6} {'peak':>6} {'smooth x':>8} {'lean':>5}  faults")
    for r in log.reps:
        f = r["features"]
        print(f"  {r['n']:>3} {r['phase']:8} {r['label']:19} "
              f"{_num(f.get('duration_s'), '6.2f')} {_ratio(f.get('duration_s'), dur_b):>6} "
              f"{_num(f.get('rom'), '6.1f')} {_ratio(f.get('rom'), rom_b):>6} "
              f"{_num(f.get('peak_angle'), '6.1f')} {_ratio(f.get('sparc'), sparc_b):>8} "
              f"{_num(f.get('trunk_lean_max'), '5.1f')}  {r['faults']}")
    print("  (baseline-phase reps are not scored against the baseline; their ratios are for reference)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=LANGS, default="ur")
    ap.add_argument("--timing", choices=TIMING_MODES, help="default: feedback.timing in thresholds.yaml")
    ap.add_argument("--exercise", default="E1")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--video", help="use a video file instead of the webcam")
    ap.add_argument("--mute", action="store_true", help="print prompts instead of playing audio")
    ap.add_argument("--log", help="save the session log as JSON here")
    args = ap.parse_args()

    cfg = load_config(args.exercise)
    cap = cv2.VideoCapture(args.video if args.video else args.camera)
    if not cap.isOpened():
        sys.exit(f"Could not open {'video ' + args.video if args.video else f'camera {args.camera}'}")
    W, H = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    src_fps = (cap.get(cv2.CAP_PROP_FPS) or 30.0) if args.video else None

    engine = SessionEngine(cfg, W, H, language=args.lang, timing=args.timing)
    player = AudioPlayer(enabled=not args.mute)
    ensure_model()
    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=0.5, min_tracking_confidence=0.5)

    print(f"Session: {args.exercise}  language={args.lang}  timing={engine.timing}  "
          f"source={'video' if args.video else 'camera'}  {int(W)}x{int(H)}")
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    t0, idx, last_ms, last_text, done_at = time.monotonic(), 0, -1, "", None
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = idx / src_fps if args.video else time.monotonic() - t0
            ms = max(int(t * 1000), last_ms + 1)          # MediaPipe needs increasing timestamps
            last_ms = ms
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            lm = landmarks_dict(landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms))

            for p in engine.process(t, lm, mean_gray(frame[::4, ::4])):
                print(f"[{t:6.1f}s] {p.reason:7s} {p.key:20s} {p.text}")
                last_text = p.text if args.lang == "en" else p.key.replace("_", " ")
                player.play(p.audio)
            player.poll()

            draw_skeleton(frame, lm, W, H)
            if not args.video:
                frame = cv2.flip(frame, 1)
            draw_status(frame, engine.status(), last_text)
            cv2.imshow(WIN, frame)

            delay = 1
            if args.video:   # play the file at its real speed so audio lines up
                delay = max(1, int((t - (time.monotonic() - t0)) * 1000))
            key = cv2.waitKey(delay) & 0xFF
            if key in (ord("q"), 27) or cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
                break
            if engine.done:
                done_at = done_at or time.monotonic()
                if time.monotonic() - done_at > END_LINGER_S:
                    break
            idx += 1

    cap.release()
    cv2.destroyAllWindows()
    player.stop()
    log = engine.stop("video_ended" if args.video and not engine.done else "user_stopped")

    print_summary(log, cfg)
    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump(log.to_dict(), f, ensure_ascii=False, indent=2)
        print("Saved log:", args.log)


if __name__ == "__main__":
    main()
