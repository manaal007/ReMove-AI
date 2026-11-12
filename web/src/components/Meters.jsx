import { Txt } from './Bi.jsx'

// Semicircle gauge: current angle vs target
export function AngleGauge({ value, target, max, label }) {
  const cx = 75, cy = 80, r = 60
  const pt = (v, rr = r) => {
    const a = Math.PI - (Math.min(v, max) / max) * Math.PI
    return [cx + rr * Math.cos(a), cy - rr * Math.sin(a)]
  }
  const [vx, vy] = pt(value)
  const [n1x, n1y] = pt(value, 45)
  const [t1x, t1y] = pt(target, 48)
  const [t2x, t2y] = pt(target, 72)
  return (
    <svg width="150" height="88" viewBox="0 0 150 88" role="img" aria-label={label}>
      <path d="M15 80 A 60 60 0 0 1 135 80" stroke="#E2E8F0" strokeWidth="14" fill="none" strokeLinecap="round" />
      {value > 0 && <path d={`M15 80 A 60 60 0 0 1 ${vx.toFixed(1)} ${vy.toFixed(1)}`} stroke="#14B8A6" strokeWidth="14" fill="none" strokeLinecap="round" />}
      <line x1={t1x} y1={t1y} x2={t2x} y2={t2y} stroke="#B45309" strokeWidth="4" strokeLinecap="round" />
      <line x1={cx} y1={cy} x2={n1x} y2={n1y} stroke="#0B1F3A" strokeWidth="4" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="6" fill="#0B1F3A" />
    </svg>
  )
}

export function ProgressRing({ done, total, size = 104 }) {
  const r = 44, c = 2 * Math.PI * r
  const pct = total ? Math.min(done / total, 1) : 0
  return (
    <svg width={size} height={size} viewBox="0 0 104 104" role="img" aria-label={`${done} / ${total}`}>
      <circle cx="52" cy="52" r={r} fill="none" stroke="#E2E8F0" strokeWidth="12" />
      <circle cx="52" cy="52" r={r} fill="none" stroke="#14B8A6" strokeWidth="12" strokeLinecap="round"
        strokeDasharray={`${(pct * c).toFixed(1)} ${c.toFixed(1)}`} transform="rotate(-90 52 52)" style={{ transition: 'stroke-dasharray .4s' }} />
      <text x="52" y="60" textAnchor="middle" fontFamily="Inter, sans-serif" fontSize="24" fontWeight="800" fill="#0B1F3A">{Math.round(pct * 100)}%</text>
    </svg>
  )
}

// Range-of-motion bar with baseline and target markers. Uses logical "start" so it flips in RTL.
export function RomBar({ value, baseline, target, max }) {
  const p = (v) => `${Math.min(100, (v / max) * 100)}%`
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between text-[15px] font-bold">
        <Txt k="rangeOfMotion" />
        <span className="text-teal-dark">{Math.round((value / target) * 100)}% <Txt k="ofTarget" /></span>
      </div>
      <div className="relative h-[18px] rounded-full bg-slate-200">
        <div className="absolute inset-y-0 start-0 rounded-full bg-teal transition-[width] duration-150" style={{ width: p(value) }} />
        {baseline != null && <div className="absolute -top-1 h-[26px] w-[3px] bg-slate-500" style={{ insetInlineStart: p(baseline) }} />}
        <div className="absolute -top-1 h-[26px] w-1 rounded bg-amber-700" style={{ insetInlineStart: p(target) }} />
      </div>
      <div className="flex flex-wrap justify-between gap-2 text-[13px] font-semibold text-slate-600">
        <span>0°</span>
        {baseline != null && <span>▏<Txt k="baseline" /> {Math.round(baseline)}°</span>}
        <span className="text-amber-800">▏<Txt k="target" /> {target}°</span>
        <span>{max}°</span>
      </div>
    </div>
  )
}
