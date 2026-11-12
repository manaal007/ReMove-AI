import { useCallback, useEffect, useRef, useState } from 'react'

// Speaks coach messages one after another (like feedback/audio_player.py):
// a short queue, oldest dropped if prompts pile up, so the voice never talks over itself
// or lags far behind the patient.
// 1) Server prompts carry audio URLs ({en, ur}) for the clips in assets/audio
//    (made by scripts/make_audio.py from feedback/messages.py).
// 2) Otherwise (mock mode, or a missing clip) the browser's speech voice is used.
const MAX_QUEUE = 3

export default function useVoice({ lang, muted }) {
  const [speaking, setSpeaking] = useState(false)
  const queue = useRef([])
  const busy = useRef(false)
  const audioRef = useRef(null)
  const langRef = useRef(lang)
  langRef.current = lang

  const next = useCallback(() => {
    const msg = queue.current.shift()
    if (!msg) { busy.current = false; setSpeaking(false); return }
    busy.current = true
    setSpeaking(true)
    const l = langRef.current
    const done = () => next()

    const speakText = () => {
      const text = l === 'ur' ? msg.ur : msg.en
      if (!window.speechSynthesis || !text) return done()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = l === 'ur' ? 'ur-PK' : 'en-US'
      u.rate = 0.9
      const v = window.speechSynthesis.getVoices().find((x) => x.lang?.startsWith(l === 'ur' ? 'ur' : 'en'))
      if (v) u.voice = v
      u.onend = done
      u.onerror = done
      window.speechSynthesis.speak(u)
    }

    const url = msg.audio?.[l]
    if (!url) return speakText()
    const a = new Audio(url)
    audioRef.current = a
    a.onended = done
    a.onerror = speakText
    a.play().catch(speakText)
  }, [])

  const speak = useCallback((msg) => {
    if (muted || !msg) return
    queue.current.push(msg)
    while (queue.current.length > MAX_QUEUE) queue.current.shift()
    if (!busy.current) next()
  }, [muted, next])

  const stop = useCallback(() => {
    queue.current = []
    audioRef.current?.pause()
    window.speechSynthesis?.cancel()
    busy.current = false
    setSpeaking(false)
  }, [])

  useEffect(() => () => stop(), [stop])
  useEffect(() => { if (muted) stop() }, [muted, stop])

  return { speak, stop, speaking }
}
