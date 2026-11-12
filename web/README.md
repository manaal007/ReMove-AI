# ReMove PK — web app (React + Vite + Tailwind)

See the main README for how to run it with the Python server.

- `src/pages/` one file per screen
- `src/hooks/usePoseStream.js` WebSocket client for `api/server.py` (+ mock mode)
- `src/hooks/useVoice.js` plays the server's audio clips in order (browser voice as fallback)
- `src/lib/exercises.js` fallback exercise info (the server's `/api/exercises` wins)
- `src/lib/i18n.js` screen text in English and Urdu
- `src/components/ExerciseAvatar.jsx` trainer animation: `abduction` (E1), `flexion` (E2), `knee`
- `src/components/FitScreen.jsx` scales the layout to fit any laptop screen

RTL: use logical Tailwind classes (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`), never `ml-`/`left-`.
Frames are sent **unmirrored** (the engine's angles are unmirrored); only the on-screen video is mirrored.
