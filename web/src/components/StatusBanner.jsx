import { useApp } from '../context/AppContext.jsx'
import { STRINGS } from '../lib/i18n.js'

// Engine status shown over the trainer: camera check, tracking lost, server problems.
// The camera issue codes are the prompt keys from feedback/messages.py.
const ISSUE = {
  too_dark: { en: 'Room is too dark', ur: 'کمرے میں روشنی کم ہے' },
  too_bright: { en: 'Too much light behind you', ur: 'پیچھے روشنی بہت زیادہ ہے' },
  not_tracked: { en: 'Stand in front of the camera', ur: 'کیمرے کے سامنے کھڑے ہوں' },
  step_back: { en: 'Step back a little', ur: 'تھوڑا پیچھے ہٹیں' },
  come_closer: { en: 'Come a little closer', ur: 'تھوڑا قریب آئیں' },
}

export default function StatusBanner({ status, connected, error }) {
  const { lang, mock } = useApp()
  let text = null
  let tone = 'bg-amber-100 text-amber-900'
  if (!mock && !connected) {
    text = STRINGS.serverOffline[lang]
    tone = 'bg-red-100 text-red-900'
  } else if (error && error !== 'connection') {
    text = error
    tone = 'bg-red-100 text-red-900'
  } else if (status?.checking) {
    const issue = status.issue && ISSUE[status.issue]
    text = `${STRINGS.cameraCheck[lang]}: ${issue ? issue[lang] : STRINGS.holdStill[lang]}`
  } else if (status?.paused) {
    text = STRINGS.trackingLost[lang]
  }
  if (!text) return null
  return (
    <div role="status" className={`absolute inset-x-6 bottom-16 rounded-xl px-4 py-3 text-center text-lg font-bold ${tone}`}>
      <span dir={lang === 'ur' ? 'rtl' : 'ltr'} className={lang === 'ur' ? 'font-urdu' : 'font-en'}>{text}</span>
    </div>
  )
}
