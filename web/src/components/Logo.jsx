export default function Logo({ size = 40, dark = false, showText = true }) {
  return (
    <div className="flex items-center gap-3">
      <svg width={size} height={size} viewBox="0 0 52 52" aria-hidden="true">
        <rect width="52" height="52" rx="14" fill={dark ? '#14B8A6' : '#0B1F3A'} />
        <path d="M14 36 L24 24 L36 30" stroke={dark ? '#0B1F3A' : '#14B8A6'} strokeWidth="4.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="24" cy="24" r="5" fill="#F5B841" />
      </svg>
      {showText && (
        <span className="font-en text-[22px] font-extrabold" dir="ltr">
          ReMove <span className={dark ? 'text-teal-light' : 'text-teal-dark'}>PK</span>
        </span>
      )}
    </div>
  )
}
