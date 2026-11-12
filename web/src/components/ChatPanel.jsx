import { useEffect, useRef } from 'react'
import { useApp } from '../context/AppContext.jsx'
import { Txt } from './Bi.jsx'
import { LangToggle } from './Header.jsx'
import { Bot, Speaker, SpeakerOff } from './Icons.jsx'

function Tag({ tag }) {
  const good = tag === 'good'
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-[13px] font-bold ${good ? 'bg-green-100 text-green-900' : 'bg-amber-100 text-amber-900'}`}>
      <Txt k={good ? 'good' : 'adjust'} />
    </span>
  )
}

function Waveform() {
  return (
    <span className="flex h-[22px] items-center gap-[3px]" aria-hidden="true">
      {[0, 0.15, 0.3, 0.45, 0.1, 0.25, 0.4].map((d, i) => <span key={i} className="wave-bar" style={{ animationDelay: `${d}s` }} />)}
    </span>
  )
}

// Left panel: AI coach chat. Every coach message shows English + Urdu, the chosen language first.
export default function ChatPanel({ messages, muted, onToggleMute, speaking, onSayAgain, onPain }) {
  const { lang } = useApp()
  const listRef = useRef(null)
  const lastCoach = [...messages].reverse().find((m) => m.kind === 'coach')

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  const order = lang === 'ur' ? ['ur', 'en'] : ['en', 'ur']

  return (
    <section aria-label="AI Coach" className="flex min-h-[420px] min-w-0 lg:min-h-0 flex-[3_1_340px] flex-col overflow-hidden rounded-2xl bg-white shadow-card">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-[42px] w-[42px] items-center justify-center rounded-full bg-teal-50 text-teal-dark"><Bot /></span>
          <span className="flex flex-col">
            <Txt k="aiCoach" className="text-[19px] font-extrabold" />
            <span className="text-sm font-semibold text-teal-dark">● <Txt k="listening" /></span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <LangToggle />
          <button type="button" onClick={onToggleMute} aria-label={muted ? 'Turn voice on' : 'Mute voice'}
            className={`flex h-11 w-11 items-center justify-center rounded-[10px] border-2 border-slate-200 bg-white ${muted ? 'text-red-700' : 'text-navy'}`}>
            {muted ? <SpeakerOff /> : <Speaker />}
          </button>
        </div>
      </div>

      <div ref={listRef} aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto bg-slate-50/60 p-4">
        {messages.map((m) => {
          if (m.kind === 'system') {
            return (
              <div key={m.id} className="self-center rounded-full bg-slate-200 px-3.5 py-1.5 text-sm font-semibold text-slate-700">
                <span dir={lang === 'ur' ? 'rtl' : 'ltr'} className={lang === 'ur' ? 'font-urdu' : 'font-en'}>{m[lang]}</span>
              </div>
            )
          }
          const isLast = m.id === lastCoach?.id
          return (
            <div key={m.id}
              className={`flex max-w-[92%] flex-col gap-1 self-start rounded-2xl rounded-ss-sm px-3.5 py-3 ${isLast ? 'border-2 border-teal bg-teal-50' : 'bg-slate-100'}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="flex gap-1.5">
                  <Tag tag={m.tag} />
                  {m.dir && <span className="rounded-full bg-navy px-2.5 py-0.5 text-[13px] font-bold text-white">{m.dir}</span>}
                </span>
                {isLast && !muted && speaking ? (
                  <span className="flex items-center gap-2"><Waveform /><Txt k="speaking" className="text-[13px] font-bold text-teal-dark" /></span>
                ) : (
                  <span className="text-slate-500"><Speaker size={18} /></span>
                )}
              </div>
              {order.map((l, i) => m[l] && (
                <span key={l} dir={l === 'ur' ? 'rtl' : 'ltr'}
                  className={`${l === 'ur' ? 'font-urdu' : 'font-en'} ${i === 0 ? `text-[18px] ${isLast ? 'font-semibold' : ''}` : 'text-[16px] text-slate-700'}`}>
                  {m[l]}
                </span>
              ))}
            </div>
          )
        })}
      </div>

      <div className="flex gap-2.5 border-t border-slate-200 px-4 py-3.5">
        <button type="button" onClick={onSayAgain} className="min-h-[52px] flex-1 rounded-xl border-2 border-slate-300 bg-white text-[17px] font-bold">
          ↻ <Txt k="sayAgain" />
        </button>
        <button type="button" onClick={onPain} className="min-h-[52px] flex-1 rounded-xl border-2 border-amber-500 bg-amber-100 text-[17px] font-bold text-amber-900">
          <Txt k="feelPain" />
        </button>
      </div>
    </section>
  )
}
