// Small stroke icons (inline SVG, no icon library needed)
const base = { fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

// flip: point the other way in Urdu (RTL). Turn off when the arrow sits inside a fixed-direction block.
export const ArrowNext = ({ size = 24, className = '', flip = true }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base} className={`${flip ? 'rtl:rotate-180' : ''} ${className}`}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
)
export const ArrowBack = ({ size = 22, className = '', flip = true }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base} className={`${flip ? 'rtl:rotate-180' : ''} ${className}`}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
)
export const Check = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base} strokeWidth={3} className={className}><path d="M5 12l5 5 9-10" /></svg>
)
export const Clock = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
)
export const Reps = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M4 12h3M17 12h3M7 8v8M17 8v8M7 12h10" /></svg>
)
export const Camera = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><rect x="3" y="6" width="13" height="12" rx="2" /><path d="M16 10l5-3v10l-5-3" /></svg>
)
export const Waves = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" /></svg>
)
export const Shield = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /></svg>
)
export const Speaker = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M17 8.5a5 5 0 0 1 0 7M19.5 6a8.5 8.5 0 0 1 0 12" /></svg>
)
export const SpeakerOff = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M17 9l5 6M22 9l-5 6" /></svg>
)
export const Pause = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
)
export const Play = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="rtl:-scale-x-100"><path d="M7 5l12 7-12 7z" /></svg>
)
export const Stop = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
)
export const Alert = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M12 3l9 16H3z" /><path d="M12 10v4M12 17v.5" /></svg>
)
export const Info = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="12" cy="12" r="9" /><path d="M12 8v.5M12 11v5" /></svg>
)
export const Bot = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base} strokeWidth={2}><rect x="5" y="8" width="14" height="11" rx="4" /><path d="M12 4v4M9 13v1M15 13v1" /></svg>
)
export const Share = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 10.5l6.8-4M8.6 13.5l6.8 4" /></svg>
)
export const Eye = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>
)
export const Timer = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2M9 3h6" /></svg>
)
