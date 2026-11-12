import { useApp } from '../context/AppContext.jsx'
import Logo from './Logo.jsx'
import { Txt } from './Bi.jsx'
import { Check } from './Icons.jsx'

const STEPS = ['stepLanguage', 'stepHealth', 'stepExercise', 'stepSetup', 'stepPractice']

export function LangToggle({ dark = false }) {
  const { lang, setLang } = useApp()
  const btn = (l, label) => (
    <button
      type="button"
      onClick={() => setLang(l)}
      aria-pressed={lang === l}
      className={`h-[38px] min-w-[52px] rounded-lg px-3 text-[15px] font-extrabold ${lang === l ? (dark ? 'bg-teal text-navy' : 'bg-navy text-white') : (dark ? 'text-white' : 'text-navy')}`}
    >
      {label}
    </button>
  )
  return (
    <div role="group" aria-label="Language" className={`flex rounded-[10px] p-[3px] ${dark ? 'bg-navy-700' : 'bg-slate-100'}`}>
      {btn('en', <span className="font-en">EN</span>)}
      {btn('ur', <span className="font-urdu leading-[1.6]">اردو</span>)}
    </div>
  )
}

export function Stepper({ current }) {
  return (
    <nav aria-label="Progress" className="flex flex-wrap items-center gap-2 text-base font-semibold">
      {STEPS.map((s, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <div key={s} className="flex items-center gap-2">
            {i > 0 && <span className={`h-0.5 w-8 ${n <= current ? 'bg-teal' : 'bg-slate-300'}`} />}
            <span className={`flex items-center gap-2 ${done ? 'text-teal-dark' : active ? 'text-navy' : 'text-slate-500'}`} aria-current={active ? 'step' : undefined}>
              <span className={`flex h-[30px] w-[30px] items-center justify-center rounded-full text-[15px] ${done ? 'bg-teal text-navy' : active ? 'bg-navy text-white' : 'border-2 border-slate-300'}`}>
                {done ? <Check size={16} /> : n}
              </span>
              <Txt k={s} className="text-base" />
            </span>
          </div>
        )
      })}
    </nav>
  )
}

export default function Header({ step, right }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-[18px] lg:px-12">
      <Logo />
      {step && <Stepper current={step} />}
      <div className="flex items-center gap-3">
        {right}
        <LangToggle />
      </div>
    </header>
  )
}
