# ReMove PK

Home rehab movement feedback for stroke survivors: webcam pose tracking (MediaPipe),
a personal baseline, rule-based rep scoring and spoken feedback in Urdu and English.

```
browser (web/)  ──JPEG frames──▶  api/server.py  ──▶  api/live.py  ──▶  session/engine.py
   React UI     ◀──JSON + audio──  (Starlette WS)       (one session)     camera check → baseline → scoring
                                         │                                        │
                                  storage/db (SQLite)                 features/signals.py, session/rules.py,
                                                                      feedback/messages.py + assets/audio
```

## Run the app

Two terminals, from the repo root.

```bash
# 1) Python server (once: python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt)
uvicorn api.server:app --port 8000

# 2) Web app (needs Node 18+)
cd web
npm install
npm run dev          # open http://localhost:5173
```

- The web app forwards `/api`, `/audio` and `/ws` to port 8000 (see `web/vite.config.js`).
- UI work without Python: `cd web && cp .env.example .env`, set `VITE_MOCK=true` (fake pose data).
- One-server demo: `cd web && npm run build`, then only `uvicorn api.server:app --port 8000` and open http://localhost:8000.
- The camera only works on `localhost` or `https`. To use a phone on the same Wi-Fi you need https (e.g. `npx vite --host` with a certificate, or a tunnel).

Desktop version (no browser): `python session/run_session.py --lang ur` (OpenCV window).

## Screens (web/)

Language → Health info → Exercise → Side & camera → Practice (baseline) → Live session → Summary.

Health info asks for a patient ID or first name (never a full name) and three safety questions:
a fracture, dislocation or surgery in the last 6 weeks, chest pain or dizziness on movement, and
whether a doctor allowed exercise. Any "stop" answer, or pain 7/10 or more, blocks the session in
the browser and again on the server (`storage/db/store.py: safety_stop`). These are starting rules
to confirm with the physiotherapy advisor.

Only E1 (right arm, side raise) is enabled. E2 is marked `ready: false` in `config/exercises.yaml`
until it is tested, and patients whose weak side is the left see "coming soon".
Urdu switches the whole layout to right-to-left. Text: `web/src/lib/i18n.js`; spoken feedback: `feedback/messages.py`.

## API

| Route | What |
|---|---|
| `GET /api/exercises` | exercises from `config/exercises.yaml` |
| `POST /api/patients` | health form → `{id}` |
| `GET /api/patients/{id}/sessions?exercise=E1` | progress history |
| `GET /api/patients/{id}/baseline?exercise=E1` | last baseline (skip practice) |
| `WS /ws/session` | live session, protocol at the top of `api/live.py` |
| `GET /audio/{lang}_{phrase}.mp3` | feedback clips |

Data is saved in `storage/db/remove.db` (SQLite, not committed): patients, and every session with its full engine log.

## Tests

```bash
pytest            # engine, rules, signals, camera check, messages, API (no camera needed)
```

## Project status

| Area | Status |
|---|---|
| Pose extraction (MediaPipe Tasks) | done — `pose/extract_landmarks.py` |
| E1 features (angle, elbow, trunk lean, SPARC smoothness) | done — `features/signals.py`, `features/build_features_ex1.py` |
| Generic models, leave-one-person-out | done for E1 — `models/train_models_ex1.py` |
| Experiment A: generic vs personal baseline | done for E1 — `models/personalization_ex1.py` |
| Experiment B: WhatsApp-style compression | script done — `research/EXP-3/compression_test.py` |
| Experiment C: feedback timing / Urdu vs English | engine supports both timings and languages; each session's language + timing is now saved — study script still to write |
| Live engine (camera check, baseline, 6 labels, rest prompts) | done — `session/` |
| Urdu + English phrases and audio | done — `feedback/`, `assets/audio/` |
| Web app + API + SQLite | done — `web/`, `api/`, `storage/db/store.py` |
| Exercises | right arm only: E1 shoulder abduction (tuned on REHAB24-6), E2 shoulder flexion (config only, thresholds not validated) |
| Leg exercise | not started — shown as "coming soon" (works in mock mode) |
| Trained ML models in the live app | not used yet: v1 scores reps with rules (`session/rules.py`) |
| Empty folders | `ui/`, `models/baseline|generic|fusion`, `research/EXP-1|EXP-2`, `storage/export|progress` |
