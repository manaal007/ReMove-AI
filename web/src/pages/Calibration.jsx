import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import Header from '../components/Header.jsx'
import Bi, { Txt } from '../components/Bi.jsx'
import { Button, Card } from '../components/ui.jsx'
import { ArrowNext, Check, Eye } from '../components/Icons.jsx'
import ExerciseAvatar from '../components/ExerciseAvatar.jsx'
import CameraFeed from '../components/CameraFeed.jsx'
import StatusBanner from '../components/StatusBanner.jsx'
import useCamera from '../hooks/useCamera.js'
import usePoseStream from '../hooks/usePoseStream.js'
import useVoice from '../hooks/useVoice.js'
import { api } from '../lib/api.js'

// Practice reps -> personal baseline. The engine (session/engine.py, "baseline" phase)
// keeps only clean reps and stops here once it has baseline.min_reps of them.
export default function Calibration() {
  const { ex, side, lang, patient, mock, setBaseline } = useApp()
  const nav = useNavigate()
  const cam = useCamera(true)
  const voice = useVoice({ lang, muted: false })
  const [lastBaseline, setLastBaseline] = useState(null)

  const pose = usePoseStream({
    videoRef: cam.videoRef, ex, mode: 'calibration', lang, patientId: patient?.id,
    active: cam.status === 'on' || mock, onPrompt: voice.speak,
  })

  // a baseline from an earlier session lets the patient skip practice
  useEffect(() => {
    if (mock || !patient?.id) return
    api.lastBaseline(patient.id, ex.id).then((r) => setLastBaseline(r.baseline)).catch(() => {})
  }, [mock, patient?.id, ex.id])

  const clean = pose.reps.filter((r) => r.phase === 'baseline' && r.used_for_baseline)
  const needed = ex.baseline_reps
  const b = pose.baselineOut
  const finished = Boolean(b)

  const go = (baseline) => {
    voice.stop()
    setBaseline(baseline)
    nav('/session')
  }

  return (
    <div className="flex min-h-full flex-col bg-page text-navy">
      <Header step={5} />
      <main className="mx-auto flex w-full max-w-[1360px] flex-1 flex-col gap-5 px-6 py-6 lg:px-12">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <Bi as="div" k="calibTitle" className="text-4xl font-extrabold tracking-tight" subClassName="text-[22px]" />
            <Txt as="p" k="calibSub" className="m-0 text-[19px] text-slate-600" />
          </div>
          {lastBaseline && !finished && (
            <Button variant="outline" onClick={() => go(lastBaseline)}><Txt k="useLastBaseline" /></Button>
          )}
        </div>

        <div className="flex min-h-0 flex-1 flex-wrap gap-6">
          <div className="relative min-h-[400px] min-w-0 flex-[1_1_480px] overflow-hidden rounded-[20px] bg-navy">
            <ExerciseAvatar kind={ex.kind} side={side} target={ex.target_deg} playing={!finished} label="Trainer demonstration" />
            <span className="absolute start-4 top-4 flex items-center gap-2.5 rounded-full bg-teal px-4 py-2.5 text-xl font-extrabold text-navy">
              <Eye /><Txt k="followMe" />
            </span>
            <StatusBanner status={pose.status} connected={pose.connected} error={pose.error} />
          </div>
          <CameraFeed videoRef={cam.videoRef} status={cam.status} onStart={cam.start} points={pose.points} joint={ex.joint} angle={pose.angle}
            className="min-h-[400px] min-w-0 flex-[1_1_480px]" />
        </div>

        <Card className="flex flex-wrap items-center gap-6 p-5">
          <div className="flex gap-3" aria-label={`${clean.length} / ${needed}`}>
            {Array.from({ length: needed }, (_, i) => (
              <span key={i} className={`flex h-16 w-16 flex-col items-center justify-center rounded-2xl text-lg font-extrabold ${clean[i] ? 'bg-teal text-navy' : i === clean.length ? 'border-2 border-dashed border-teal-dark text-teal-dark' : 'bg-slate-100 text-slate-500'}`}>
                {clean[i] ? <><Check size={16} /><span className="text-sm">{Math.round(clean[i].peak)}°</span></> : i + 1}
              </span>
            ))}
          </div>
          <div className="flex min-w-[240px] flex-1 flex-col">
            {finished ? (
              <>
                <Txt k="calibDone" className="text-xl font-bold text-teal-dark" />
                <span className="text-lg"><Txt k="yourRange" />: <b className="font-en">{Math.round(b.peak_angle)}°</b> <span className="font-en text-slate-600">(range {Math.round(b.rom)}°)</span></span>
              </>
            ) : (
              <span className="text-xl font-bold"><Txt k={ex.angleKey} />: <span className="font-en">{pose.angle}°</span></span>
            )}
          </div>
          <Button size="lg" disabled={!finished} onClick={() => go(b)}>
            <Bi k="startSession" inline subClassName="text-[17px]" /><ArrowNext />
          </Button>
        </Card>
      </main>
    </div>
  )
}
