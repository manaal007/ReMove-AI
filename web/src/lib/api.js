// Small client for api/server.py. Same-origin URLs: Vite proxies them in dev.
export const MOCK = import.meta.env.VITE_MOCK === 'true'

export const wsUrl = () =>
  import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/session`

async function req(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`)
  return data
}

export const api = {
  exercises: () => req('/api/exercises'),
  addPatient: (p) => req('/api/patients', { method: 'POST', body: JSON.stringify(p) }),
  sessions: (pid, exercise) => req(`/api/patients/${pid}/sessions?exercise=${encodeURIComponent(exercise)}`),
  lastBaseline: (pid, exercise) => req(`/api/patients/${pid}/baseline?exercise=${encodeURIComponent(exercise)}`),
}
