import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import Logo from '../components/Logo.jsx'
import { Txt } from '../components/Bi.jsx'
import { ArrowNext, ArrowBack, Camera, Waves, Shield } from '../components/Icons.jsx'
import ExerciseAvatar from '../components/ExerciseAvatar.jsx'

export default function Language() {
  const { setLang, lang, other } = useApp()
  const nav = useNavigate()
  const pick = (l) => { setLang(l); nav('/history') }

  return (
    <div className="flex min-h-full flex-wrap bg-page text-navy">
      <section className="flex min-w-0 flex-[999_1_560px] flex-col gap-10 px-8 py-14 lg:px-[72px]">
        <div className="flex flex-col gap-1">
          <Logo size={52} />
          <Txt k="appTagline" className="text-[15px] text-slate-600" />
        </div>

        <div className="flex max-w-[640px] flex-col gap-3">
          <Txt as="h1" k="heroTitle" className="m-0 text-4xl font-extrabold leading-tight tracking-tight lg:text-[52px]" />
          <Txt as="p" k="heroTitle" lang={other} className="m-0 text-2xl" />
          <Txt as="p" k="heroBody" className="m-0 text-xl leading-relaxed text-slate-700" />
        </div>

        <div className="flex max-w-[640px] flex-col gap-4">
          <span className="text-xl font-bold"><Txt k="chooseLanguage" /> <span className="font-semibold text-slate-600">· <Txt k="chooseLanguage" lang={other} /></span></span>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <button type="button" onClick={() => pick('en')} dir="ltr"
              className={`flex min-h-[92px] items-center justify-between gap-3 rounded-2xl px-7 text-start ${lang === 'en' ? 'bg-teal shadow-teal' : 'border-2 border-navy bg-white'}`}>
              <span className="flex flex-col font-en"><span className="text-[26px] font-extrabold">English</span><span className="text-base font-medium">Voice + text in English</span></span>
              <ArrowNext size={28} flip={false} />
            </button>
            <button type="button" onClick={() => pick('ur')} dir="rtl"
              className={`flex min-h-[92px] items-center justify-between gap-3 rounded-2xl px-7 text-start ${lang === 'ur' ? 'bg-teal shadow-teal' : 'border-2 border-navy bg-white'}`}>
              <span className="flex flex-col font-urdu"><span className="text-[28px] font-bold leading-[1.7]">اردو</span><span className="text-[15px] text-slate-700">آواز اور تحریر اردو میں</span></span>
              <ArrowBack size={28} flip={false} />
            </button>
          </div>
        </div>

        <div className="flex max-w-[680px] flex-wrap gap-3">
          {[[Camera, 'featCamera'], [Waves, 'featVoice'], [Shield, 'featLearns']].map(([Icon, k]) => (
            <span key={k} className="flex items-center gap-2.5 rounded-full bg-white px-4 py-3 text-[17px] font-semibold shadow-card">
              <span className="text-teal-dark"><Icon /></span><Txt k={k} />
            </span>
          ))}
        </div>

        <Txt as="p" k="disclaimer" className="m-0 mt-auto max-w-[640px] text-[15px] text-slate-600" />
      </section>

      <aside className="relative flex min-h-[520px] min-w-0 flex-[1_1_520px] flex-col items-center justify-center gap-6 overflow-hidden bg-navy p-12">
        <div className="relative h-[420px] w-full max-w-[520px]">
          <ExerciseAvatar kind="abduction" label="Trainer raising the arm to the side" />
        </div>
        <div className="flex flex-col items-center gap-1 text-center">
          <span className="font-en text-[22px] font-bold text-white">Watch · Copy · Improve</span>
          <span className="font-urdu text-xl text-teal-light" dir="rtl">دیکھیں · دہرائیں · بہتر بنائیں</span>
        </div>
      </aside>
    </div>
  )
}
