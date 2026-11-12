// Exercises the app can show.
// E1 / E2 come from config/exercises.yaml through GET /api/exercises (the server is the
// source of truth: targets, camera view, side). The values here are only fallbacks for
// mock mode and for the first render before the API answers.
// LEG is not in the Python engine yet, so it only works in mock mode.
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
  LEG: {
    id: 'LEG', group: 'leg', kind: 'knee', joint: 'knee', angleKey: 'kneeAngle', mockOnly: true,
    title: 'legTitle', label_en: 'Sit and straighten your knee', label_ur: 'بیٹھ کر گھٹنا سیدھا کریں',
    camera_view: 'side', side: null, rest_deg: 0, target_deg: 80, max_safe_deg: 90,
    max_reps: 10, baseline_reps: 3,
  },
}

// Gauge / bar scale: a little above the safe maximum
export const gaugeMax = (ex) => Math.ceil(((ex.max_safe_deg ?? ex.target_deg) * 1.15) / 10) * 10

export const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0)
export const std = (xs) => {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)))
}
