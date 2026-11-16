// Exercises the app can show.
// All of them come from config/exercises.yaml through GET /api/exercises (the server is the
// source of truth: targets, camera view, side). The values here are only fallbacks for
// mock mode and for the first render before the API answers, plus UI-only fields
// (group, kind, joint, angleKey, title, avatarRest).
// side: null = either side; the engine measures whichever side the camera sees better.
// avatarRest: angle at rest, for exercises whose angle does not start near 0 (the knee is
// ~90° when sitting), so the trainer animation swings target - rest degrees.
export const EXERCISES = {
  E1: {
    id: 'E1', group: 'arm', kind: 'abduction', joint: 'shoulder', angleKey: 'shoulderAngle',
    title: 'e1Title', label_en: 'Raise your right arm out to the side', label_ur: 'اپنا دایاں بازو پہلو کی طرف اٹھائیں',
    camera_view: 'front', side: 'right', rest_deg: 20, target_deg: 90, max_safe_deg: 100,
    max_reps: 10, baseline_reps: 3,
  },
  E2: {
    id: 'E2', group: 'arm', kind: 'flexion', joint: 'shoulder', angleKey: 'shoulderAngle',
    title: 'e2Title', label_en: 'Raise your right arm forward', label_ur: 'اپنا دایاں بازو آگے کی طرف اٹھائیں',
    camera_view: 'side_right', side: 'right', rest_deg: 20, target_deg: 90, max_safe_deg: 100,
    max_reps: 10, baseline_reps: 3, ready: false,
  },
  E3: {
    id: 'E3', group: 'arm', kind: 'elbow', joint: 'elbow', angleKey: 'elbowBend',
    title: 'e3Title', label_en: 'Bend your elbow, then straighten it', label_ur: 'کہنی موڑیں، پھر سیدھی کریں',
    camera_view: 'side', side: null, rest_deg: 10, target_deg: 120, max_safe_deg: 145,
    max_reps: 10, baseline_reps: 3, weight_check: true,
  },
  E4: {
    id: 'E4', group: 'leg', kind: 'knee', joint: 'knee', angleKey: 'kneeAngle', avatarRest: 90,
    title: 'e4Title', label_en: 'Sit, straighten your knee, then bend it', label_ur: 'بیٹھ کر گھٹنا سیدھا کریں، پھر موڑیں',
    camera_view: 'side', side: null, rest_deg: 90, target_deg: 160, max_safe_deg: 180,
    max_reps: 10, baseline_reps: 3, weight_check: true,
  },
}

// Gauge / bar scale: a little above the safe maximum, never past 180° (a straight joint)
export const gaugeMax = (ex) => Math.min(180, Math.ceil(((ex.max_safe_deg ?? ex.target_deg) * 1.15) / 10) * 10)

export const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0)
export const std = (xs) => {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)))
}
