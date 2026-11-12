// 2.5D trainer that demonstrates the exercise.
// Later you can swap this for a real 3D model (Mixamo GLB + react-three-fiber) with the same props.
// The SVG loop is 4 s per rep, the same timing as the mock pose stream.
function Defs() {
  return (
    <defs>
      <radialGradient id="av-glow" cx="50%" cy="45%" r="60%"><stop offset="0" stopColor="#16406B" /><stop offset="1" stopColor="#0B1F3A" /></radialGradient>
      <radialGradient id="av-floor" cx="50%" cy="50%" r="50%"><stop offset="0" stopColor="#14B8A6" stopOpacity="0.45" /><stop offset="1" stopColor="#14B8A6" stopOpacity="0" /></radialGradient>
      <linearGradient id="av-skin" x1="0" x2="1"><stop offset="0" stopColor="#F1F5F9" /><stop offset="0.55" stopColor="#CBD5E1" /><stop offset="1" stopColor="#7C8DA6" /></linearGradient>
      <radialGradient id="av-head" cx="38%" cy="35%" r="70%"><stop offset="0" stopColor="#FFFFFF" /><stop offset="0.6" stopColor="#CBD5E1" /><stop offset="1" stopColor="#7C8DA6" /></radialGradient>
      <linearGradient id="av-limb" x1="0" x2="1"><stop offset="0" stopColor="#99F6E4" /><stop offset="0.5" stopColor="#14B8A6" /><stop offset="1" stopColor="#0F766E" /></linearGradient>
      <radialGradient id="av-joint" cx="35%" cy="35%" r="70%"><stop offset="0" stopColor="#FDE68A" /><stop offset="1" stopColor="#D97706" /></radialGradient>
    </defs>
  )
}

// Rotating limb segment around a pivot
function Swing({ cx, cy, target, playing, children }) {
  if (!playing) return <g transform={`rotate(${-target * 0.7} ${cx} ${cy})`}>{children}</g>
  return (
    <g>
      <animateTransform
        attributeName="transform"
        type="rotate"
        values={`0 ${cx} ${cy}; ${-target} ${cx} ${cy}; ${-target} ${cx} ${cy}; 0 ${cx} ${cy}; 0 ${cx} ${cy}`}
        keyTimes="0; 0.4; 0.5; 0.9; 1"
        dur="4s"
        repeatCount="indefinite"
      />
      {children}
    </g>
  )
}

// Dashed target arc from "straight down" to the target angle, around a pivot
function TargetArc({ cx, cy, r, target }) {
  const a = (target * Math.PI) / 180
  const x = cx + r * Math.sin(a)
  const y = cy + r * Math.cos(a)
  return <path d={`M${cx} ${cy + r} A ${r} ${r} 0 0 0 ${x.toFixed(1)} ${y.toFixed(1)}`} stroke="#F5B841" strokeWidth="3" fill="none" strokeDasharray="7 7" strokeLinecap="round" />
}

function Elbow({ target, playing }) {
  const ex = 278, ey = 280
  return (
    <>
      <rect x="232" y="300" width="30" height="138" rx="15" fill="url(#av-skin)" />
      <rect x="266" y="300" width="30" height="138" rx="15" fill="url(#av-skin)" opacity="0.85" />
      <rect x="222" y="150" width="84" height="164" rx="40" fill="url(#av-skin)" />
      <circle cx="268" cy="102" r="38" fill="url(#av-head)" />
      <path d="M300 96 l12 6 l-12 4" fill="#94A3B8" />
      <TargetArc cx={ex} cy={ey} r={104} target={target} />
      <g transform={`rotate(${-target} ${ex} ${ey})`} opacity="0.28"><rect x="266" y="280" width="24" height="112" rx="12" fill="#F5B841" /></g>
      <rect x="264" y="164" width="28" height="120" rx="14" fill="url(#av-limb)" />
      <Swing cx={ex} cy={ey} target={target} playing={playing}>
        <rect x="266" y="280" width="24" height="112" rx="12" fill="url(#av-limb)" />
        <rect x="262" y="384" width="32" height="26" rx="8" fill="#F5B841" />
      </Swing>
      <circle cx={ex} cy={ey} r="14" fill="url(#av-joint)" />
      <circle cx="278" cy="170" r="12" fill="url(#av-joint)" />
    </>
  )
}

// Front view, the moving arm is on the viewer's right so it matches the mirrored camera.
// E1: shoulder abduction, the straight arm swings out to the side.
function Abduction({ target, playing }) {
  const sx = 318, sy = 156
  return (
    <>
      <rect x="226" y="300" width="34" height="138" rx="17" fill="url(#av-skin)" />
      <rect x="270" y="300" width="34" height="138" rx="17" fill="url(#av-skin)" />
      <rect x="216" y="140" width="98" height="172" rx="42" fill="url(#av-skin)" />
      <circle cx="265" cy="98" r="38" fill="url(#av-head)" />
      <rect x="196" y="150" width="24" height="150" rx="12" fill="url(#av-skin)" opacity="0.9" />
      <TargetArc cx={sx} cy={sy} r={150} target={target} />
      <g transform={`rotate(${-target} ${sx} ${sy})`} opacity="0.28"><rect x="306" y={sy} width="24" height="150" rx="12" fill="#F5B841" /></g>
      <Swing cx={sx} cy={sy} target={target} playing={playing}>
        <rect x="306" y={sy} width="24" height="150" rx="12" fill="url(#av-limb)" />
        <circle cx="318" cy={sy + 76} r="9" fill="url(#av-joint)" />
      </Swing>
      <circle cx={sx} cy={sy} r="14" fill="url(#av-joint)" />
    </>
  )
}

// Side view facing right. E2: shoulder flexion, the straight arm swings forward and up.
function Flexion({ target, playing }) {
  const sx = 272, sy = 168
  return (
    <>
      <rect x="236" y="300" width="30" height="138" rx="15" fill="url(#av-skin)" />
      <rect x="262" y="300" width="30" height="138" rx="15" fill="url(#av-skin)" opacity="0.85" />
      <rect x="226" y="150" width="80" height="164" rx="38" fill="url(#av-skin)" />
      <circle cx="268" cy="102" r="38" fill="url(#av-head)" />
      <path d="M300 96 l12 6 l-12 4" fill="#94A3B8" />
      <TargetArc cx={sx} cy={sy} r={150} target={target} />
      <g transform={`rotate(${-target} ${sx} ${sy})`} opacity="0.28"><rect x="260" y={sy} width="24" height="150" rx="12" fill="#F5B841" /></g>
      <Swing cx={sx} cy={sy} target={target} playing={playing}>
        <rect x="260" y={sy} width="24" height="150" rx="12" fill="url(#av-limb)" />
        <circle cx="272" cy={sy + 76} r="9" fill="url(#av-joint)" />
      </Swing>
      <circle cx={sx} cy={sy} r="14" fill="url(#av-joint)" />
    </>
  )
}

function Leg({ target, playing }) {
  const kx = 360, ky = 300
  return (
    <>
      {/* chair */}
      <rect x="170" y="300" width="150" height="14" rx="7" fill="#475569" />
      <rect x="170" y="150" width="14" height="164" rx="7" fill="#475569" />
      <rect x="176" y="314" width="10" height="120" rx="5" fill="#475569" />
      <rect x="304" y="314" width="10" height="120" rx="5" fill="#475569" />
      {/* body */}
      <rect x="200" y="130" width="78" height="176" rx="36" fill="url(#av-skin)" />
      <circle cx="240" cy="92" r="36" fill="url(#av-head)" />
      <path d="M272 86 l12 6 l-12 4" fill="#94A3B8" />
      <rect x="244" y="160" width="24" height="120" rx="12" fill="url(#av-skin)" opacity="0.9" />
      {/* other leg, resting */}
      <rect x="236" y="276" width="124" height="28" rx="14" fill="url(#av-skin)" opacity="0.6" />
      <rect x="338" y="290" width="26" height="120" rx="13" fill="url(#av-skin)" opacity="0.6" />
      {/* moving leg */}
      <TargetArc cx={kx} cy={ky} r={110} target={target} />
      <g transform={`rotate(${-target} ${kx} ${ky})`} opacity="0.28"><rect x="347" y="300" width="26" height="118" rx="13" fill="#F5B841" /></g>
      <rect x="240" y="286" width="130" height="30" rx="15" fill="url(#av-limb)" />
      <Swing cx={kx} cy={ky} target={target} playing={playing}>
        <rect x="347" y="300" width="26" height="118" rx="13" fill="url(#av-limb)" />
        <rect x="344" y="406" width="44" height="20" rx="8" fill="#F5B841" />
      </Swing>
      <circle cx={kx} cy={ky} r="14" fill="url(#av-joint)" />
      <circle cx="252" cy="300" r="12" fill="url(#av-joint)" />
    </>
  )
}

const BODIES = { abduction: Abduction, flexion: Flexion, elbow: Elbow, knee: Leg }
const DEFAULT_TARGET = { abduction: 90, flexion: 90, elbow: 130, knee: 80 }

// kind: 'abduction' (E1) | 'flexion' (E2) | 'elbow' | 'knee'
export default function ExerciseAvatar({ kind = 'abduction', side = 'right', target, playing = true, label }) {
  const t = target ?? DEFAULT_TARGET[kind]
  const Body = BODIES[kind] ?? Abduction
  // Drawn for the right side. For the left side we mirror it.
  const mirror = side === 'left' ? 'translate(560 0) scale(-1 1)' : undefined
  return (
    <svg viewBox="0 0 560 480" preserveAspectRatio="xMidYMid meet" role="img" aria-label={label} className="absolute inset-0 h-full w-full">
      <Defs />
      <rect width="560" height="480" fill="url(#av-glow)" />
      <ellipse cx="270" cy="440" rx="170" ry="26" fill="url(#av-floor)" />
      <ellipse cx="270" cy="440" rx="120" ry="14" fill="none" stroke="#14B8A6" strokeOpacity="0.5" strokeWidth="2" />
      <g transform={mirror}>
        <Body target={t} playing={playing} />
      </g>
      <g>
        <rect x="400" y="40" width="124" height="36" rx="18" fill="#F5B841" />
        <text x="462" y="64" textAnchor="middle" fontFamily="Inter, sans-serif" fontSize="16" fontWeight="800" fill="#0B1F3A">Target {t}°</text>
      </g>
    </svg>
  )
}
