import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { STRINGS } from '../lib/i18n.js'
import { EXERCISES } from '../lib/exercises.js'
import { api, MOCK } from '../lib/api.js'

const AppContext = createContext(null)

function loadLang() {
  try { return localStorage.getItem('remove-lang') || 'ur' } catch { return 'ur' }
}

export function AppProvider({ children }) {
  const [lang, setLangState] = useState(loadLang)   // 'en' | 'ur'
  const [patient, setPatient] = useState(null)      // health form data (+ id from the server)
  const [exercise, setExercise] = useState(null)    // exercise id: 'E1' | 'E2' | 'LEG'
  const [side, setSide] = useState(null)            // 'left' | 'right'
  const [baseline, setBaseline] = useState(null)    // engine baseline from calibration
  const [result, setResult] = useState(null)        // session summary
  const [exercises, setExercises] = useState(EXERCISES)
  const [serverOk, setServerOk] = useState(MOCK ? null : undefined) // undefined = checking

  // Exercises come from config/exercises.yaml via the server
  useEffect(() => {
    if (MOCK) return
    api.exercises()
      .then((list) => {
        const merged = {}
        for (const e of list) merged[e.id] = { ...(EXERCISES[e.id] ?? { group: 'arm', kind: 'abduction', joint: 'shoulder', angleKey: 'shoulderAngle', title: null }), ...e }
        merged.LEG = EXERCISES.LEG   // shown as "coming soon" until the engine supports it
        setExercises(merged)
        setServerOk(true)
      })
      .catch(() => setServerOk(false))
  }, [])

  const setLang = (l) => {
    setLangState(l)
    try { localStorage.setItem('remove-lang', l) } catch { /* storage blocked */ }
  }

  // RTL switch: the whole page flips when Urdu is chosen
  useEffect(() => {
    const el = document.documentElement
    el.lang = lang
    el.dir = lang === 'ur' ? 'rtl' : 'ltr'
  }, [lang])

  const value = useMemo(() => {
    const other = lang === 'ur' ? 'en' : 'ur'
    const ex = exercise ? exercises[exercise] : null
    return {
      lang, setLang, isRtl: lang === 'ur', other,
      t: (key) => STRINGS[key]?.[lang] ?? key,
      t2: (key) => STRINGS[key]?.[other] ?? '',
      mock: MOCK, serverOk,
      exercises, ex,
      // usable now? (LEG needs mock mode until the Python engine supports it)
      available: (e) => MOCK || (!e.mockOnly && e.ready !== false),
      patient, setPatient, exercise, setExercise, side, setSide,
      baseline, setBaseline, result, setResult,
      resetSession: () => { setBaseline(null); setResult(null) },
    }
  }, [lang, patient, exercise, side, baseline, result, exercises, serverOk])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside AppProvider')
  return ctx
}
