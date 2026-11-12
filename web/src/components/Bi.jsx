import { useApp } from '../context/AppContext.jsx'
import { STRINGS } from '../lib/i18n.js'

// One string in one language, with the right font and direction.
export function Txt({ k, lang, className = '', as: Tag = 'span' }) {
  const app = useApp()
  const l = lang ?? app.lang
  return (
    <Tag dir={l === 'ur' ? 'rtl' : 'ltr'} className={`${l === 'ur' ? 'font-urdu' : 'font-en'} ${className}`}>
      {STRINGS[k]?.[l] ?? k}
    </Tag>
  )
}

// Bilingual text: main line in the chosen language, smaller line in the other one.
export default function Bi({ k, className = '', subClassName = '', inline = false, as: Tag = 'span' }) {
  const { lang, other } = useApp()
  if (inline) {
    return (
      <Tag className={className}>
        <Txt k={k} lang={lang} />
        <span className={`font-normal opacity-80 ${subClassName}`}> · <Txt k={k} lang={other} /></span>
      </Tag>
    )
  }
  return (
    <Tag className={`flex flex-col ${className}`}>
      <Txt k={k} lang={lang} />
      <Txt k={k} lang={other} className={`text-[0.8em] font-normal text-slate-600 ${subClassName}`} />
    </Tag>
  )
}
