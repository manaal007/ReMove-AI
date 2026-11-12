import { Link } from 'react-router-dom'

const VARIANTS = {
  primary: 'bg-teal text-navy shadow-teal hover:brightness-95',
  dark: 'bg-navy text-white hover:bg-navy-700',
  gold: 'bg-gold text-navy hover:brightness-95',
  outline: 'bg-white text-navy border-2 border-slate-300 hover:border-navy',
  warn: 'bg-amber-100 text-amber-900 border-2 border-amber-500',
}
const SIZES = {
  md: 'min-h-[60px] px-6 text-[19px]',
  lg: 'min-h-[64px] px-9 text-[21px]',
}
const cls = (variant, size, extra) =>
  `inline-flex items-center justify-center gap-3 rounded-[14px] font-extrabold no-underline transition disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${extra}`

export function Button({ variant = 'primary', size = 'md', className = '', ...props }) {
  return <button type="button" className={cls(variant, size, className)} {...props} />
}

export function LinkButton({ variant = 'primary', size = 'md', className = '', to, ...props }) {
  return <Link to={to} className={cls(variant, size, className)} {...props} />
}

export function Card({ className = '', children, ...props }) {
  return <div className={`rounded-2xl bg-white shadow-card ${className}`} {...props}>{children}</div>
}

const CHIP = {
  good: 'bg-green-100 text-green-900',
  adjust: 'bg-amber-100 text-amber-900',
  neutral: 'bg-slate-100 text-navy',
  dark: 'bg-navy text-white',
  teal: 'bg-teal-50 text-navy',
}
export function Chip({ tone = 'neutral', className = '', children }) {
  return <span className={`inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-base font-bold ${CHIP[tone]} ${className}`}>{children}</span>
}

// Two-option toggle (Left/Right, Yes/No)
export function Segmented({ options, value, onChange, className = '' }) {
  return (
    <div role="radiogroup" className={`grid grid-cols-2 gap-3 ${className}`}>
      {options.map((o) => {
        const on = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            className={`min-h-[60px] rounded-xl border-2 text-[19px] font-bold text-navy transition ${on ? 'border-teal-dark bg-teal-50' : 'border-slate-300 bg-white hover:border-slate-400'}`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
