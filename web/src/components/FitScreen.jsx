import { useEffect, useState } from 'react'

// Makes every screen fit the window on laptops and desktops.
// The app is laid out on a "stage" of at least 1200 x 900 px (the Figma size),
// then scaled down (or up a little) to fill the window exactly — no scrolling,
// no columns jumping to a new line, on 1280x720, 1366x768, 1920x1080, etc.
// On phones and small tablets (< 1024 px wide) the normal responsive layout is used.
const MIN_W = 1200
const MIN_H = 900
const MAX_SCALE = 1.3
const DESKTOP = 1024

function measure() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  if (vw < DESKTOP) return { desktop: false }
  const s = Math.min(vw / MIN_W, vh / MIN_H, MAX_SCALE)
  return { desktop: true, s, w: vw / s, h: vh / s }
}

export default function FitScreen({ children }) {
  const [m, setM] = useState(measure)

  useEffect(() => {
    const on = () => setM(measure())
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])

  if (!m.desktop) {
    return <div className="h-dvh overflow-y-auto bg-page">{children}</div>
  }
  return (
    <div className="fixed inset-0 overflow-hidden bg-page">
      <div
        className="overflow-y-auto overflow-x-hidden"
        style={{ position: 'absolute', left: 0, top: 0, width: m.w, height: m.h, transform: `scale(${m.s})`, transformOrigin: '0 0' }}      >
        {children}
      </div>
    </div>
  )
}
