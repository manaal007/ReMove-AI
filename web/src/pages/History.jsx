import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { api } from '../lib/api.js'
import Header from '../components/Header.jsx'
import Bi, { Txt } from '../components/Bi.jsx'
import { Button, Card, Segmented } from '../components/ui.jsx'
import { Alert, ArrowBack, ArrowNext } from '../components/Icons.jsx'

const CONDITIONS = ['bp', 'diabetes', 'heart', 'jointPain']

function Field({ k, children, className = '' }) {
  return (
    <label className={`flex flex-col gap-2 text-lg font-semibold ${className}`}>
      <Bi k={k} subClassName="text-sm" />
      {children}
    </label>
  )
}
const inputCls = 'h-14 rounded-xl border-2 border-slate-300 px-4 text-[19px] text-navy focus:border-teal-dark'

export default function History() {
  const { patient, setPatient, mock } = useApp()
  const nav = useNavigate()
  const [f, setF] = useState(patient ?? { name: '', age: '', strokeDate: '', side: null, pain: 2, conditions: [], doctorOk: null, recentInjury: null, chestDizzy: null })
  const [error, setError] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saving, setSaving] = useState(false)
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }))
  const toggle = (c) => set('conditions')(f.conditions.includes(c) ? f.conditions.filter((x) => x !== c) : [...f.conditions, c])

  const painHigh = f.pain >= 7
  // Safety stop: any of these blocks the session (the server checks the same rules)
  const stopKey = f.chestDizzy === true ? 'chestStop'
    : f.recentInjury === true ? 'injuryStop'
    : f.doctorOk === false ? 'noDoctor'
    : painHigh ? 'painHigh' : null
  const blocked = stopKey !== null
  const unanswered = f.recentInjury === null || f.chestDizzy === null || f.doctorOk === null
  const painBg = painHigh ? 'bg-red-300' : f.pain >= 4 ? 'bg-gold' : 'bg-teal-light'

  const submit = async (e) => {
    e.preventDefault()
    if (!f.name.trim() || !f.age || !f.side || unanswered) { setError(true); return }
    if (blocked) return
    setSaveError(null)
    if (mock) { setPatient(f); nav('/exercise'); return }
    setSaving(true)
    try {
      const { id } = await api.addPatient(f)   // saved in storage/db/remove.db
      setPatient({ ...f, id })
      nav('/exercise')
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex min-h-full flex-col bg-page text-navy">
      <Header step={2} />
      <form onSubmit={submit} className="mx-auto flex w-full max-w-[1240px] flex-1 flex-col gap-6 px-6 py-9 lg:px-12">
        <div>
          <Txt as="h1" k="healthTitle" className="m-0 text-[38px] font-extrabold tracking-tight" />
          <Txt as="p" k="healthSub" className="m-0 text-[19px] text-slate-600" />
        </div>

        <div className="flex flex-wrap gap-6">
          <Card className="grid min-w-0 flex-[1_1_520px] grid-cols-2 content-start gap-5 p-7">
            <Field k="fullName" className="col-span-2">
              <input className={inputCls} value={f.name} maxLength={40} onChange={(e) => set('name')(e.target.value)} autoComplete="off" required />
              <Txt k="nameHint" className="text-sm font-normal text-slate-600" />
            </Field>
            <Field k="age">
              <input className={inputCls} type="number" min="18" max="110" value={f.age} onChange={(e) => set('age')(e.target.value)} required />
            </Field>
            <Field k="strokeDate">
              <input className={inputCls} type="date" value={f.strokeDate} onChange={(e) => set('strokeDate')(e.target.value)} />
            </Field>
            <fieldset className="col-span-2 m-0 flex flex-col gap-2.5 border-0 p-0">
              <legend className="mb-2.5 p-0 text-lg font-semibold"><Bi k="weakSide" subClassName="text-sm" /></legend>
              <Segmented value={f.side} onChange={set('side')}
                options={[{ value: 'left', label: <Bi k="left" inline /> }, { value: 'right', label: <Bi k="right" inline /> }]} />
            </fieldset>
            <Field k="painToday" className="col-span-2">
              <div className="flex items-center gap-4">
                <input type="range" min="0" max="10" value={f.pain} onChange={(e) => set('pain')(Number(e.target.value))} className="h-8 flex-1 accent-teal" />
                <span className={`flex h-12 min-w-16 items-center justify-center rounded-xl text-[22px] font-extrabold ${painBg}`}>{f.pain}</span>
              </div>
            </Field>
          </Card>

          <section className="flex min-w-0 flex-[1_1_420px] flex-col gap-6">
            <Card className="flex flex-col gap-3.5 p-7">
              <Bi k="otherConditions" className="text-lg font-semibold" subClassName="text-sm" />
              <div className="grid grid-cols-2 gap-3">
                {CONDITIONS.map((c) => {
                  const on = f.conditions.includes(c)
                  return (
                    <label key={c} className={`flex min-h-[52px] items-center gap-3 rounded-xl border-2 px-3.5 text-[17px] font-medium ${on ? 'border-teal bg-teal-50' : 'border-slate-200'}`}>
                      <input type="checkbox" checked={on} onChange={() => toggle(c)} className="h-[22px] w-[22px] accent-teal-dark" />
                      <Txt k={c} />
                    </label>
                  )
                })}
              </div>
            </Card>
            <Card className="flex flex-col gap-3.5 p-7">
              <Bi k="safetyTitle" className="text-xl font-extrabold" subClassName="text-sm" />
              {['recentInjury', 'chestDizzy', 'doctorOk'].map((q) => (
                <div key={q} className="flex flex-col gap-2.5">
                  <Bi k={q} className="text-lg font-semibold" subClassName="text-sm" />
                  <Segmented value={f[q]} onChange={set(q)}
                    options={[{ value: true, label: <Bi k="yes" inline /> }, { value: false, label: <Bi k="no" inline /> }]} />
                </div>
              ))}
            </Card>
            {saveError && (
              <div role="alert" className="rounded-xl bg-red-100 px-4 py-4 text-[17px] font-medium text-red-900">
                Could not save: {saveError}. Is the server running? (uvicorn api.server:app --port 8000)
              </div>
            )}
            {(blocked || error) && (
              <div role="alert" className="flex items-start gap-3 rounded-xl bg-amber-100 px-4 py-4 text-[17px] font-medium text-amber-900">
                <Alert />
                <Txt k={stopKey ?? 'fillRequired'} />
              </div>
            )}
          </section>
        </div>

        <div className="mt-auto flex flex-wrap items-center justify-between gap-4">
          <Button variant="outline" onClick={() => nav('/')}><ArrowBack /><Txt k="back" /></Button>
          <Button type="submit" size="lg" disabled={blocked || saving}><Bi k="saveContinue" inline subClassName="text-[17px]" /><ArrowNext /></Button>
        </div>
      </form>
    </div>
  )
}
