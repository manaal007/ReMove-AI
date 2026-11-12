import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In dev, /api, /audio and /ws go to the Python server (uvicorn api.server:app --port 8000),
// so the browser sees one origin and the same URLs work after `npm run build`.
const API = process.env.API_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': API,
      '/audio': API,
      '/ws': { target: API.replace(/^http/, 'ws'), ws: true },
    },
  },
})
