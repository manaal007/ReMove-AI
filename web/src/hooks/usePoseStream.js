import { useCallback, useEffect, useRef, useState } from 'react'
import { MOCK, wsUrl } from '../lib/api.js'
import { COACH } from '../lib/i18n.js'

/**
 * Live pose results for the Calibration and Session screens.
 *
 * Real mode talks to api/server.py (protocol documented in api/live.py):
 *   -> {"type":"start", mode, exercise, lang, baseline, patient_id}, then JPEG frames (binary)
 *   <- ready | frame {status, points, prompts, reps} | baseline | done | error
 * A new frame is sent only after the previous "frame" reply arrives (no backlog on slow laptops).
 *
 * Mock mode (VITE_MOCK=true) fakes the same messages in the browser.
 *
 * mode: 'calibration' (stops when the baseline is ready) | 'session'
 */
const MAX_FPS = 15
const FRAME_W = 640

let msgId = 0
const coachMsg = (p) => ({ id: ++msgId, kind: 'coach', en: p.en, ur: p.ur, tag: p.tag ?? 'adjust', dir: p.dir, audio: p.audio, key: p.key })
const systemMsg = (en, ur) => ({ id: ++msgId, kind: 'system', en, ur })

export default function usePoseStream({ videoRef, ex, mode, baseline, patientId, lang, active, onPrompt }) {
  const [angle, setAngle] = useState(0)
  const [points, setPoints] = useState(null)
  const [reps, setReps] = useState([])
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState({ phase: 'check', checking: true, issue: null })
  const [baselineOut, setBaselineOut] = useState(null)
  const [summary, setSummary] = useState(null)
  const [connected, setConnected] = useState(MOCK)
  const [error, setError] = useState(null)

  const onPromptRef = useRef(onPrompt)
  onPromptRef.current = onPrompt
  const activeRef = useRef(active)
  activeRef.current = active
  const wsRef = useRef(null)
  const stopRef = useRef(() => {})

  const addPrompt = (p) => {
    const m = coachMsg(p)
    setMessages((xs) => [...xs.slice(-40), m])
    onPromptRef.current?.(m)
  }
  const addRep = (r) => {
    setReps((xs) => [...xs, r])
    if (r.peak != null) setMessages((xs) => [...xs.slice(-40), systemMsg(`Rep ${r.n} · ${Math.round(r.peak)}°`, `${r.n} بار مکمل · ${Math.round(r.peak)}°`)])
  }

  // ------------------------------------------------------------ real mode
  useEffect(() => {
    if (MOCK || !ex) return
    const ws = new WebSocket(wsUrl())
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    let inflight = false
    let closed = false
    let lastSent = 0

    const sendFrame = () => {
      const v = videoRef.current
      if (closed || inflight || !activeRef.current || ws.readyState !== 1 || !v || v.readyState < 2 || !v.videoWidth) return
      if (performance.now() - lastSent < 1000 / MAX_FPS) return
      // keep the camera's real aspect ratio: the engine's angles are measured in pixels
      const scale = Math.min(1, FRAME_W / v.videoWidth)
      canvas.width = Math.round(v.videoWidth * scale)
      canvas.height = Math.round(v.videoHeight * scale)
      ctx.drawImage(v, 0, 0, canvas.width, canvas.height)   // NOT mirrored: config angles are unmirrored
      inflight = true
      lastSent = performance.now()
      canvas.toBlob((blob) => {
        if (blob && ws.readyState === 1) ws.send(blob)
        else inflight = false
      }, 'image/jpeg', 0.7)
    }
    const timer = setInterval(sendFrame, 1000 / MAX_FPS / 2)

    ws.onopen = () => {
      setConnected(true)
      ws.send(JSON.stringify({ type: 'start', mode, exercise: ex.id, lang, baseline: baseline ?? null, patient_id: patientId ?? null }))
    }
    ws.onclose = () => { setConnected(false); closed = true }
    ws.onerror = () => { setConnected(false); setError('connection') }
    ws.onmessage = (ev) => {
      let d
      try { d = JSON.parse(ev.data) } catch { return }
      if (d.type === 'frame') {
        inflight = false
        const s = d.status || {}
        setStatus(s)
        if (typeof s.angle === 'number') setAngle(Math.round(s.angle))
        setPoints(d.points)
        for (const p of d.prompts || []) addPrompt(p)
        for (const r of d.reps || []) addRep(r)
      } else if (d.type === 'baseline') {
        setBaselineOut(d.baseline)
      } else if (d.type === 'done') {
        closed = true
        setSummary(d.summary)
      } else if (d.type === 'error') {
        inflight = false
        setError(d.message)
      }
    }
    stopRef.current = () => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'stop' })) }
    return () => { closed = true; clearInterval(timer); ws.close() }
    // start a new server session only when the exercise or mode changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ex?.id, mode])

  // ------------------------------------------------------------ mock mode
  useEffect(() => {
    if (!MOCK || !ex) return
    const target = ex.target_deg
    const rest = ex.rest_deg ?? 0
    const total = mode === 'calibration' ? ex.baseline_reps : ex.max_reps
    const typical = baseline?.peak_angle ?? rest + (target - rest) * 0.85
    const sim = { t: 0, rep: 0, peak: 0, warned: false, lean: false, done: false, started: false, peaks: [] }
    const newRep = () => {
      sim.peak = Math.min(ex.max_safe_deg, typical + (Math.random() - 0.4) * 20)
      sim.lean = mode === 'session' && Math.random() < 0.2
      sim.warned = false
    }
    newRep()
    const finish = (reason) => {
      sim.done = true
      if (mode === 'calibration') {
        const peak = sim.peaks.reduce((a, b) => a + b, 0) / sim.peaks.length
        setBaselineOut({ peak_angle: peak, rom: peak - rest, min_angle: rest, duration_s: 3.6, sparc: null, jerk_norm: null })
      } else {
        setSummary({ ended_reason: reason, mock: true })
      }
    }
    stopRef.current = () => finish('user_stopped')

    const DT = 50
    const id = setInterval(() => {
      if (!activeRef.current || sim.done) return
      if (!sim.started) {
        sim.started = true
        setStatus({ phase: mode === 'calibration' ? 'baseline' : 'scoring', checking: false, issue: null })
        addPrompt(COACH.start())
      }
      sim.t += DT / 1000
      const T = 4                         // seconds per rep, same as the trainer animation
      const p = sim.t % T
      let a
      if (p < 1.6) a = rest + (sim.peak - rest) * (p / 1.6)
      else if (p < 2) a = sim.peak
      else if (p < 3.6) a = sim.peak - (sim.peak - rest) * ((p - 2) / 1.6)
      else a = rest
      const lean = sim.lean && p > 1 && p < 3
      setAngle(Math.round(a))
      setPoints(mockPoints(ex.kind, a, lean))
      setStatus((s) => ({ ...s, angle: a, last_label: lean ? 'trunk_compensation' : s.last_label }))

      if (p >= 1.7 && !sim.warned) {
        sim.warned = true
        const gap = target - sim.peak
        if (sim.lean) addPrompt(COACH.backStraight())
        else if (gap > 8) addPrompt(COACH.raiseMore(Math.round(gap / 10) * 10 || 10))
        else addPrompt(COACH.lower())
      }
      if (p + DT / 1000 >= T) {
        sim.rep += 1
        sim.peaks.push(sim.peak)
        const label = sim.lean ? 'trunk_compensation' : target - sim.peak > 20 ? 'reduced_range' : 'good'
        addRep({
          n: sim.rep, phase: mode === 'calibration' ? 'baseline' : 'scoring', label, faults: label === 'good' ? [] : [label],
          tag: label === 'good' ? 'good' : 'adjust', lean: sim.lean, peak: Math.round(sim.peak), used_for_baseline: true,
        })
        setStatus((s) => ({ ...s, last_label: label, reps_done: sim.rep }))
        if (label === 'good' && Math.random() < 0.5) addPrompt(COACH.great())
        if (sim.rep >= total) finish('set_done')
        else newRep()
      }
    }, DT)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ex?.id, mode])

  const stop = useCallback(() => stopRef.current(), [])
  const posture = status.last_label === 'trunk_compensation' ? 'lean' : 'good'

  return { angle, posture, points, reps, messages, status, baselineOut, summary, connected, error, stop, mock: MOCK }
}

// Fake skeleton for mock mode (unmirrored image coords, 0–1; the patient's right arm is on image-left)
function mockPoints(kind, angle, lean) {
  const rad = (d) => (d * Math.PI) / 180
  const dx = lean ? 0.04 : 0
  if (kind === 'knee') {
    const hip = [0.42, 0.55], knee = [0.62, 0.56], a = rad(90 - angle)
    return { hip, knee, ankle: [knee[0] + 0.24 * Math.cos(a), knee[1] + 0.24 * Math.sin(a)], shoulder: [0.4 + dx, 0.22], otherHip: [0.4, 0.55] }
  }
  const shoulder = [0.42 + dx, 0.32]
  const a = rad(angle)
  const dir = kind === 'flexion' ? [Math.sin(a), Math.cos(a)] : [-Math.sin(a), Math.cos(a)]
  return {
    shoulder,
    elbow: [shoulder[0] + 0.15 * dir[0], shoulder[1] + 0.15 * dir[1]],
    wrist: [shoulder[0] + 0.3 * dir[0], shoulder[1] + 0.3 * dir[1]],
    otherShoulder: [0.58 + dx, 0.32], hip: [0.44, 0.62], otherHip: [0.56, 0.62],
  }
}
