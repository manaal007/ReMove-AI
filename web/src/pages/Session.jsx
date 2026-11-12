import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import Logo from '../components/Logo.jsx'
import Bi, { Txt } from '../components/Bi.jsx'
import { Button, Card, Chip } from '../components/ui.jsx'
import { Alert, Eye, Pause, Play, Stop, Timer } from '../components/Icons.jsx'
import ExerciseAvatar from '../components/ExerciseAvatar.jsx'
import CameraFeed from '../components/CameraFeed.jsx'
import ChatPanel from '../components/ChatPanel.jsx'
import { AngleGauge, ProgressRing, RomBar } from '../components/Meters.jsx'
import useCamera from '../hooks/useCamera.js'
import usePoseStream from '../hooks/usePoseStream.js'
import useVoice from '../hooks/useVoice.js'
import StatusBanner from '../components/StatusBanner.jsx'
import { gaugeMax, mean } from '../lib/exercises.js'
import { STRINGS } from '../lib/i18n.js'

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

export default function Session() {
  const { lang, patient, ex, side, baseline, setResult, mock } = useApp()
  const nav = useNavigate()
  const cam = useCamera(true)
  const [playing, setPlaying] = useState(true)
  const [muted, setMuted] = useState(false)
  const [painStop, setPainStop] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const voice = useVoice({ lang, muted })
  const lastCoach = useRef(null)
  const finishedRef = useRef(false)
  const max = gaugeMax(ex)

  const pose = usePoseStream({
    videoRef: cam.videoRef, ex, mode: 'session', baseline, lang, patientId: patient?.id,
    active: playing && !painStop && (cam.status === 'on' || mock),
    onPrompt: (m) => { lastCoach.current = m; voice.speak(m) },
  })

  // session timer
  useEffect(() => {
    if (!playing || painStop) return
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [playing, painStop])

  // The engine ends the set itself after caps.max_reps_per_set reps ("done" message);
  // Stop asks it to end early. Either way the summary arrives here.
  useEffect(() => {
    if (!pose.summary || finishedRef.current) return
    finishedRef.current = true
    const scored = pose.reps.filter((r) => r.phase === 'scoring' && r.peak != null)
    const peaks = scored.map((r) => r.peak)
    const summary = {
      date: new Date().toISOString(), exercise: ex.id, side,
      reps: scored, total: ex.max_reps,
      avg: peaks.length ? Math.round(mean(peaks)) : 0, best: peaks.length ? Math.round(Math.max(...peaks)) : 0,
      goodPosture: scored.filter((r) => !r.lean).length,
      good: scored.filter((r) => r.label === 'good').length,
      seconds, baseline: baseline?.peak_angle ?? null, target: ex.target_deg,
      sessionId: pose.summary.session_id ?? null, endedReason: pose.summary.ended_reason,
    }
    if (mock) {
      try {   // mock mode keeps a local history; with the server it is in SQLite
        const key = 'remove-history'
        const hist = JSON.parse(localStorage.getItem(key) || '[]')
        if (peaks.length) hist.push({ date: summary.date, exercise: ex.id, avg: summary.avg })
        localStorage.setItem(key, JSON.stringify(hist.slice(-20)))
      } catch { /* storage blocked */ }
    }
    setResult(summary)
    // let the last prompt ("set done") play before leaving
    const id = setTimeout(() => nav('/summary'), pose.summary.ended_reason === 'set_done' ? 2500 : 300)
    return () => clearTimeout(id)
  }, [pose.summary]) // eslint-disable-line react-hooks/exhaustive-deps

  const finish = () => pose.stop()

  const onPain = () => {
    setPainStop(true)
    setPlaying(false)
    voice.stop()
    voice.speak({ en: STRINGS.painStop.en, ur: STRINGS.painStop.ur })
  }

  const scoredCount = pose.reps.filter((r) => r.phase === 'scoring').length
  const repNow = Math.min(scoredCount + 1, ex.max_reps)
  const gap = Math.round(ex.target_deg - pose.angle)
  const lastPeak = pose.reps.at(-1)?.peak ?? 0
  const romValue = Math.max(pose.angle, 0)

  return (
    <div className="flex min-h-full flex-col bg-page text-navy lg:h-full">
      <header className="flex flex-wrap items-center justify-between gap-4 bg-navy px-6 py-3.5 text-white lg:px-8">
        <Logo dark />
        <div className="flex flex-wrap items-center gap-7">
          <span className="flex flex-col"><span className="text-[13px] font-semibold tracking-wide text-slate-400">PATIENT</span><span className="text-lg font-bold">{patient?.name}{patient?.age ? ` · ${patient.age}` : ''}</span></span>
          <span className="h-9 w-px bg-slate-700" />
          <span className="flex flex-col"><span className="text-[13px] font-semibold tracking-wide text-slate-400">EXERCISE</span><span className="text-lg font-bold"><Txt k={side ?? 'right'} /> · {ex.title ? <Txt k={ex.title} /> : ex.name}</span></span>
          <span className="h-9 w-px bg-slate-700" />
          <span className="flex items-center gap-2.5 rounded-xl bg-navy-700 px-4 py-2 text-gold"><Timer /><span className="font-en text-[22px] font-extrabold tabular-nums text-white">{fmt(seconds)}</span></span>
        </div>
      </header>

      <main className="flex flex-1 flex-wrap items-stretch gap-5 p-5 lg:grid lg:min-h-0 lg:grid-cols-[3fr_4fr_3fr] lg:grid-rows-[minmax(0,1fr)] lg:px-6">
        {/* LEFT 30%: AI coach chat */}
        <ChatPanel messages={pose.messages} muted={muted} onToggleMute={() => { setMuted((m) => !m); voice.stop() }}
          speaking={voice.speaking} onSayAgain={() => voice.speak(lastCoach.current)} onPain={onPain} />

        {/* CENTER 40%: trainer avatar + rep counter */}
        <section aria-label="Trainer demonstration" className="flex min-w-0 flex-[4_1_440px] flex-col gap-4 lg:min-h-0">
          <div className="relative min-h-[460px] flex-1 overflow-hidden rounded-[20px] bg-navy lg:min-h-0">
            <ExerciseAvatar kind={ex.kind} side={side} target={ex.target_deg} playing={playing && !painStop} label="Trainer demonstration" />
            <StatusBanner status={pose.status} connected={pose.connected} error={pose.error} />
            <span className="absolute start-4 top-4 flex items-center gap-2.5 rounded-full bg-teal px-4 py-2.5 text-xl font-extrabold text-navy">
              <Eye /><Bi k="followMe" inline subClassName="text-[17px]" />
            </span>
            <span className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-xl bg-white/10 px-5 py-2.5 text-[17px] font-semibold text-white">
              <Txt k="rhythm" />
            </span>
            {painStop && (
              <div role="alert" className="absolute inset-x-6 top-20 flex items-start gap-3 rounded-xl bg-amber-100 p-4 text-lg font-semibold text-amber-900">
                <Alert /><Bi k="painStop" subClassName="text-base" />
              </div>
            )}
          </div>

          <Card className="flex flex-wrap items-center gap-5 px-5 py-4">
            <ProgressRing done={scoredCount} total={ex.max_reps} />
            <div className="flex min-w-[140px] flex-1 flex-col">
              <Txt k="repetition" className="text-[15px] font-bold uppercase tracking-wide text-slate-600" />
              <span className="font-en text-[40px] font-extrabold leading-tight" dir="ltr">{repNow} <span className="font-semibold text-slate-500">/ {ex.max_reps}</span></span>
            </div>
            <div className="flex gap-3">
              <Button variant="gold" disabled={painStop} onClick={() => setPlaying((p) => !p)}>
                {playing ? <Pause /> : <Play />}<Txt k={playing ? 'pause' : 'resume'} />
              </Button>
              <Button variant="dark" onClick={finish}><Stop /><Txt k="stop" /></Button>
            </div>
          </Card>
        </section>

        {/* RIGHT 30%: camera + live metrics */}
        <section aria-label="Your camera" className="flex min-w-0 flex-[3_1_340px] flex-col gap-4 lg:min-h-0">
          <div className="relative h-[380px] lg:h-auto lg:min-h-[240px] lg:flex-1">
            <CameraFeed videoRef={cam.videoRef} status={cam.status} onStart={cam.start} points={pose.points} joint={ex.joint} angle={pose.angle} className="absolute inset-0" />
            <span className="absolute start-3.5 top-3.5 flex items-center gap-2 rounded-lg bg-navy/80 px-3 py-1.5 text-sm font-extrabold tracking-wider text-white">
              <span className="live-dot h-2.5 w-2.5 rounded-full bg-red-500" /><Txt k="liveYou" />
            </span>
            
          </div>

          <Card className="flex flex-1 flex-col gap-3.5 p-[18px] lg:flex-none">
            <div className="flex items-center gap-4">
              <AngleGauge value={pose.angle} target={ex.target_deg} max={max} label={`${pose.angle}° / ${ex.target_deg}°`} />
              <div className="flex flex-col">
                <Txt k={ex.angleKey} className="text-sm font-bold uppercase tracking-wide text-slate-600" />
                <span className="font-en text-4xl font-extrabold leading-tight" dir="ltr">{pose.angle}° <span className="text-lg font-semibold text-slate-600">/ {ex.target_deg}°</span></span>
                <span className={`text-[15px] font-bold ${gap > 0 ? 'text-amber-800' : 'text-green-800'}`}>
                  {gap > 0 ? <>↑ {gap}° <Txt k="toTarget" /></> : <Txt k="onTarget" />}
                </span>
              </div>
            </div>
            <RomBar value={romValue} baseline={baseline?.peak_angle} target={ex.target_deg} max={max} />
            <div className="mt-auto flex flex-wrap gap-2.5">
              <Chip tone={pose.posture === 'good' ? 'good' : 'adjust'}><Txt k={pose.posture === 'good' ? 'postureGood' : 'postureLean'} /></Chip>
              <Chip tone={cam.status === 'on' ? 'good' : 'adjust'}><Txt k={cam.status === 'on' ? 'cameraOk' : 'cameraOff'} /></Chip>
              {lastPeak > 0 && <Chip>Last: {lastPeak}°</Chip>}
            </div>
          </Card>
        </section>
      </main>
    </div>
  )
}
