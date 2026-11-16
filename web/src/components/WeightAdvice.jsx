import { useState } from 'react'
import { useApp } from '../context/AppContext.jsx'
import Bi, { Txt } from './Bi.jsx'
import { Button, Card, Chip } from './ui.jsx'
import { Alert } from './Icons.jsx'
import { api } from '../lib/api.js'
import useVoice from '../hooks/useVoice.js'

// Weight guidance after the set (session/weight_advice.py, rules TO CONFIRM WITH PHYSIO).
// 1) the patient rates pain now, 2) the server decides up / stay / down for the next
// session and saves it, 3) the advice is shown in Urdu + English and spoken.
export default function WeightAdvice({ sessionId }) {
  const { lang } = useApp()
  const voice = useVoice({ lang, muted: false })
  const [pain, setPain] = useState(0)
  const [res, setRes] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const ask = async () => {
    setBusy(true); setError(null)
    try {
      const r = await api.advice(sessionId, pain)
      setRes(r)
      r.prompts.forEach((p) => voice.speak(p))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const a = res?.advice
  const tone = a?.action === 'up' ? 'good' : a?.action === 'down' ? 'adjust' : 'neutral'
  const painBg = pain >= 4 ? 'bg-gold' : 'bg-teal-light'

  return (
    <Card className="flex flex-col gap-4 p-6">
      <Bi as="h2" k="weightAdvice" className="m-0 text-xl font-extrabold" subClassName="text-base" />
      {!a ? (
        <>
          <label className="flex flex-col gap-2 text-lg font-semibold">
            <Bi k="painNow" subClassName="text-sm" />
            <div className="flex items-center gap-4">
              <input type="range" min="0" max="10" value={pain} onChange={(e) => setPain(Number(e.target.value))} className="h-8 flex-1 accent-teal" />
              <span className={`flex h-12 min-w-16 items-center justify-center rounded-xl text-[22px] font-extrabold ${painBg}`}>{pain}</span>
            </div>
          </label>
          {error && <p role="alert" className="m-0 rounded-xl bg-red-100 px-4 py-3 text-base font-medium text-red-900">{error}</p>}
          <Button onClick={ask} disabled={busy} className="self-start"><Bi k="getAdvice" inline subClassName="text-base" /></Button>
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Chip tone={tone}><Bi k={`advice_${a.action}`} inline /></Chip>
            <span className="text-lg"><Txt k="thisSession" />: <b><Txt k={`weight_${a.current}`} /></b> → <Txt k="nextSession" />: <b><Txt k={`weight_${a.next}`} /></b></span>
          </div>
          {res.prompts.filter((p) => p.key !== 'talk_to_physio').map((p) => (
            <p key={p.key} className="m-0 flex flex-col text-[19px] font-semibold">
              <span dir={lang === 'ur' ? 'rtl' : 'ltr'} className={lang === 'ur' ? 'font-urdu' : 'font-en'}>{lang === 'ur' ? p.ur : p.en}</span>
              <span dir={lang === 'ur' ? 'ltr' : 'rtl'} className={`text-base font-normal text-slate-600 ${lang === 'ur' ? 'font-en' : 'font-urdu'}`}>{lang === 'ur' ? p.en : p.ur}</span>
            </p>
          ))}
          {a.talk_to_physio && (
            <div role="alert" className="flex items-start gap-3 rounded-xl bg-amber-100 px-4 py-3 text-[17px] font-semibold text-amber-900">
              <Alert />
              <span className="flex flex-col">
                <span>{res.prompts.find((p) => p.key === 'talk_to_physio')?.[lang]}</span>
                <span className="text-sm font-normal">{res.prompts.find((p) => p.key === 'talk_to_physio')?.[lang === 'ur' ? 'en' : 'ur']}</span>
              </span>
            </div>
          )}
          <ul className="m-0 flex list-disc flex-col gap-1 ps-6 text-[15px] text-slate-700">
            {a.reasons.map((k) => <li key={k}><Bi k={`reason_${k}`} inline subClassName="text-sm" /></li>)}
          </ul>
          <Txt k="adviceToConfirm" className="text-sm text-slate-600" />
        </div>
      )}
    </Card>
  )
}
