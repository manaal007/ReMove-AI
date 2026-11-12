import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import Header from '../components/Header.jsx'
import Bi, { Txt } from '../components/Bi.jsx'
import { Button, Card, Chip } from '../components/ui.jsx'
import { Clock, Reps } from '../components/Icons.jsx'
import ExerciseAvatar from '../components/ExerciseAvatar.jsx'

function Option({ on, onClick, children }) {
  return (
    <button type="button" role="radio" aria-checked={on} onClick={onClick}
      className={`flex min-h-[56px] flex-1 flex-col items-start justify-center rounded-xl border-2 px-4 py-2 text-start transition ${on ? 'border-teal-dark bg-teal-50' : 'border-slate-300 bg-white hover:border-slate-400'}`}>
      {children}
    </button>
  )
}

export default function ExerciseChoice() {
  const { patient, exercises, available, setExercise, setSide, resetSession, lang, other, serverOk, mock } = useApp()
  const nav = useNavigate()
  const arms = Object.values(exercises).filter((e) => e.group === 'arm')
  const leg = exercises.LEG
  const [armId, setArmId] = useState(arms[0]?.id ?? 'E1')
  const arm = exercises[armId] ?? arms[0]

  const choose = (e) => {
    setExercise(e.id)
    // the engine supports one side per exercise for now (config/exercises.yaml: side)
    setSide(e.side ?? patient?.side ?? null)
    resetSession()
    nav('/setup')
  }
  const label = (e, l) => (l === 'ur' ? e.label_ur : e.label_en)
  // the engine measures one side per exercise; a patient whose weak side differs can't use it yet
  const wrongSide = Boolean(arm?.side && patient?.side && patient.side !== arm.side)
  const armOk = arm && available(arm) && !wrongSide

  return (
    <div className="flex min-h-full flex-col bg-page text-navy">
      <Header step={3} right={patient && <span className="hidden text-lg font-semibold xl:inline"><Txt k="greeting" />, {patient.name.split(' ')[0]}</span>} />
      <main className="mx-auto flex w-full max-w-[1280px] flex-1 flex-col gap-6 px-6 py-7 lg:px-12">
        <Bi as="div" k="chooseTitle" className="items-center text-center text-[42px] font-extrabold tracking-tight" subClassName="text-[26px] font-normal" />
        {!mock && serverOk === false && (
          <div role="alert" className="rounded-xl bg-red-100 px-4 py-3 text-center text-base font-semibold text-red-900"><Txt k="serverOffline" /></div>
        )}

        <div className="grid grid-cols-[repeat(auto-fit,minmax(380px,1fr))] gap-6">
          {/* ARM: the exercises the Python engine supports */}
          {arm && (
            <Card className="flex flex-col overflow-hidden shadow-[0_8px_30px_rgba(11,31,58,0.08)]">
              <div className="relative h-[230px] bg-navy">
                <ExerciseAvatar kind={arm.kind} target={arm.target_deg} label={arm.label_en} />
                <span className="absolute start-[18px] top-[18px] rounded-full bg-white px-3.5 py-1.5 font-en text-[15px] font-bold text-navy">ARM · {arm.id}</span>
              </div>
              <div className="flex flex-col gap-3.5 px-7 py-5">
                <Bi k="armTitle" className="text-[28px] font-extrabold" subClassName="text-[19px]" />
                <div role="radiogroup" aria-label="Movement" className="flex gap-3">
                  {arms.map((e) => (
                    <Option key={e.id} on={e.id === armId} onClick={() => setArmId(e.id)}>
                      <span className="text-[17px] font-bold">{e.title ? <Txt k={e.title} /> : e.name}</span>
                      <span dir={lang === 'ur' ? 'rtl' : 'ltr'} className={`${lang === 'ur' ? 'font-urdu' : 'font-en'} text-[14px] text-slate-600`}>{label(e, lang)}</span>
                    </Option>
                  ))}
                </div>
                <p dir={other === 'ur' ? 'rtl' : 'ltr'} className={`${other === 'ur' ? 'font-urdu' : 'font-en'} m-0 text-[16px] text-slate-600`}>{label(arm, other)}</p>
                <div className="flex flex-wrap gap-2.5">
                  <Chip><Clock /><Txt k="about5" /></Chip>
                  <Chip><Reps /><span className="font-en">{arm.max_reps}</span>&nbsp;<Txt k="repetition" /></Chip>
                  {arm.side && <Chip tone="adjust"><Txt k="rightArmOnly" /></Chip>}
                </div>
                {wrongSide && (
                  <p role="alert" className="m-0 rounded-xl bg-amber-100 px-4 py-3 text-[17px] font-medium text-amber-900"><Txt k="sideNotYet" /></p>
                )}
                {!wrongSide && !available(arm) && (
                  <p className="m-0 rounded-xl bg-slate-100 px-4 py-3 text-[17px] font-medium text-navy"><Txt k="notTestedYet" /></p>
                )}
                <Button size="lg" onClick={() => choose(arm)} disabled={!armOk} className="w-full">
                  {armOk ? <Bi k="startArm" inline subClassName="text-[17px]" /> : <Txt k="comingSoon" />}
                </Button>
              </div>
            </Card>
          )}

          {/* LEG: mock mode only until the engine supports knee exercises */}
          {leg && (
            <Card className="flex flex-col overflow-hidden shadow-[0_8px_30px_rgba(11,31,58,0.08)]">
              <div className="relative h-[230px] bg-navy">
                <ExerciseAvatar kind="knee" target={leg.target_deg} label="Sit and straighten the knee" playing={available(leg)} />
                <span className="absolute start-[18px] top-[18px] rounded-full bg-white px-3.5 py-1.5 font-en text-[15px] font-bold text-navy">LEG</span>
                {!available(leg) && <span className="absolute end-[18px] top-[18px] rounded-full bg-gold px-3.5 py-1.5 text-[15px] font-bold text-navy"><Txt k="comingSoon" /></span>}
              </div>
              <div className="flex flex-col gap-3.5 px-7 py-5">
                <Bi k="legTitle" className="text-[28px] font-extrabold" subClassName="text-[19px]" />
                <p className="m-0 text-[19px] text-slate-700"><Txt k="legSub" /></p>
                <div className="flex flex-wrap gap-2.5">
                  <Chip><Clock /><Txt k="about6" /></Chip>
                  <Chip><Reps /><Txt k="reps10" /></Chip>
                  <Chip tone="adjust"><Txt k="legEquip" /></Chip>
                </div>
                <Button variant="dark" size="lg" onClick={() => choose(leg)} disabled={!available(leg)} className="w-full">
                  {available(leg) ? <Bi k="startLeg" inline subClassName="text-[17px]" /> : <Txt k="comingSoon" />}
                </Button>
              </div>
            </Card>
          )}
        </div>

        <p className="m-0 text-center text-[17px] text-slate-600">
          <Txt k="chooseTip" /> <Link to="/history" className="font-semibold text-teal-dark"><Txt k="back" /></Link>
        </p>
      </main>
    </div>
  )
}
