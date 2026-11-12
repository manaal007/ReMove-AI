import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import Header from '../components/Header.jsx'
import Bi, { Txt } from '../components/Bi.jsx'
import { Button, Card } from '../components/ui.jsx'
import { Bot, Check, Share } from '../components/Icons.jsx'
import { api } from '../lib/api.js'

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

function Stat({ k, value, unit, note, noteTone = 'text-teal-dark' }) {
  return (
    <Card className="flex flex-col gap-1 p-[22px]">
      <Txt k={k} className="text-[15px] font-bold text-slate-600" />
      <span className="font-en text-[40px] font-extrabold" dir="ltr">{value} {unit && <span className="text-xl font-semibold text-slate-600">{unit}</span>}</span>
      {note && <span className={`text-[15px] font-semibold ${noteTone}`}>{note}</span>}
    </Card>
  )
}

export default function Summary() {
  const { result: r, patient, setResult, resetSession, mock, exercises } = useApp()
  const nav = useNavigate()
  const [copied, setCopied] = useState(false)

  // Last 5 sessions of this exercise: SQLite through the server, or localStorage in mock mode
  const [history, setHistory] = useState([])
  useEffect(() => {
    if (!mock && patient?.id) {
      api.sessions(patient.id, r.exercise)
        .then((rows) => setHistory(rows.filter((x) => x.avg_peak != null).map((x) => ({ date: x.started_at, avg: Math.round(x.avg_peak) })).slice(-5)))
        .catch(() => setHistory([]))
      return
    }
    try {
      setHistory(JSON.parse(localStorage.getItem('remove-history') || '[]').filter((h) => h.exercise === r.exercise).slice(-5))
    } catch { setHistory([]) }
  }, [mock, patient?.id, r.exercise])

  const diff = r.baseline != null && r.reps.length ? r.avg - Math.round(r.baseline) : null
  const leanReps = r.reps.filter((x) => x.lean).map((x) => x.n)
  const top = Math.max(r.target, ...history.map((h) => h.avg)) * 1.1

  const share = async () => {
    const text = `ReMove PK — ${patient?.name ?? ''}\n${exercises[r.exercise]?.label_en ?? r.exercise} (${r.side}), ${new Date(r.date).toLocaleDateString()}\nReps: ${r.reps.length}/${r.total}\nAverage: ${r.avg}° (target ${r.target}°), best ${r.best}°\nGood posture: ${r.goodPosture}/${r.reps.length}\nTime: ${fmt(r.seconds)}`
    try {
      if (navigator.share) await navigator.share({ title: 'ReMove PK session', text })
      else { await navigator.clipboard.writeText(text); setCopied(true) }
    } catch { /* user cancelled */ }
  }

  return (
    <div className="flex min-h-full flex-col bg-page text-navy">
      <Header right={<span className="hidden text-lg font-semibold xl:inline">{patient?.name} · {new Date(r.date).toLocaleDateString()}</span>} />
      <main className="mx-auto flex w-full max-w-[1360px] flex-1 flex-col gap-6 px-6 py-8 lg:px-12">

        <div className="flex flex-wrap items-center gap-6 rounded-[20px] bg-navy px-8 py-7 text-white">
          <span className="flex h-[84px] w-[84px] shrink-0 items-center justify-center rounded-full bg-teal text-navy"><Check size={44} /></span>
          <Bi as="div" k="wellDone" className="min-w-[300px] flex-1 text-[38px] font-extrabold tracking-tight" subClassName="!text-teal-light text-2xl" />
          {diff != null && (
            <div className="flex flex-col items-end">
              <Txt k="vsBaseline" className="text-sm font-bold text-slate-400" />
              <span className="font-en text-[34px] font-extrabold text-gold" dir="ltr">{diff >= 0 ? '+' : ''}{diff}°</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-[18px]">
          <Stat k="repsDone" value={r.reps.length} unit={`/ ${r.total}`} />
          <Stat k="avgAngle" value={`${r.avg}°`} unit={`/ ${r.target}°`} note={<><Txt k="bestRep" />: {r.best}°</>} />
          <Stat k="goodPosture" value={r.goodPosture} unit={`/ ${r.reps.length}`}
            note={leanReps.length ? `Leaned: rep ${leanReps.join(', ')}` : null} noteTone="text-amber-800" />
          <Stat k="sessionTime" value={fmt(r.seconds)} />
        </div>

        <div className="flex flex-wrap gap-5">
          <Card className="flex min-w-0 flex-[1.3_1_520px] flex-col gap-4 p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="m-0 text-[22px] font-extrabold">Progress · last {history.length} sessions</h2>
              <Txt k="avgAngle" className="text-[15px] font-semibold text-slate-600" />
            </div>
            <div className="relative flex h-[190px] items-end gap-[18px] border-b-2 border-slate-200" dir="ltr">
              <div className="absolute inset-x-0 border-t-2 border-dashed border-amber-700" style={{ bottom: `${(r.target / top) * 190}px` }} />
              <span className="absolute end-0 text-[13px] font-bold text-amber-800" style={{ bottom: `${(r.target / top) * 190 + 4}px` }}>Target {r.target}°</span>
              {history.map((h, i) => {
                // newest bar = this session
                const last = i === history.length - 1
                return (
                  <div key={h.date} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                    <span className={`text-[15px] ${last ? 'font-extrabold' : 'font-bold'}`}>{h.avg}°</span>
                    <div className={`w-full max-w-16 rounded-t-lg ${last ? 'bg-teal-dark' : 'bg-teal-light'}`} style={{ height: `${(h.avg / top) * 160}px` }} />
                  </div>
                )
              })}
            </div>
            <div className="flex gap-[18px] text-sm font-semibold text-slate-600" dir="ltr">
              {history.map((h, i) => <span key={h.date} className="flex-1 text-center">{i === history.length - 1 ? 'Today' : new Date(h.date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span>)}
            </div>
          </Card>

          <section className="flex min-w-0 flex-[1_1_400px] flex-col gap-5">
            <Card className="flex flex-col gap-3.5 p-6">
              <Txt as="h2" k="eachRep" className="m-0 text-xl font-extrabold" />
              <div className="grid grid-cols-10 gap-2" dir="ltr">
                {r.reps.map((x) => (
                  <span key={x.n} title={`${x.peak}°`} className={`flex aspect-square items-center justify-center rounded-[10px] text-[15px] font-extrabold ${x.tag === 'good' ? 'bg-teal' : 'bg-gold'}`}>{x.n}</span>
                ))}
              </div>
              <div className="flex gap-4 text-sm font-semibold text-slate-700">
                <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded bg-teal" /><Txt k="good" /></span>
                <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded bg-gold" /><Txt k="needsAdjust" /></span>
              </div>
            </Card>
            <div className="flex items-start gap-3.5 rounded-2xl border-2 border-teal bg-teal-50 px-5 py-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal text-navy"><Bot size={22} /></span>
              <div className="flex flex-col gap-0.5">
                <Txt k="coachTip" className="text-[17px] font-bold" />
                <Bi k="tipText" className="text-[17px]" />
              </div>
            </div>
          </section>
        </div>

        <div className="flex flex-wrap justify-end gap-3.5">
          <Button variant="outline" className="border-navy" onClick={share}><Share />{copied ? 'Copied ✓' : <Txt k="share" />}</Button>
          <Button variant="gold" onClick={() => { resetSession(); nav('/exercise') }}><Txt k="another" /></Button>
          <Button onClick={() => { nav('/'); setResult(null) }}><Bi k="finish" inline subClassName="text-base" /></Button>
        </div>
      </main>
    </div>
  )
}
