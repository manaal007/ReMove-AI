import { Txt } from './Bi.jsx'
import { Button } from './ui.jsx'
import { Camera } from './Icons.jsx'

const BONES = [
  ['shoulder', 'elbow'], ['elbow', 'wrist'],
  ['hip', 'knee'], ['knee', 'ankle'],
  ['shoulder', 'otherShoulder'], ['shoulder', 'hip'], ['hip', 'otherHip'],
]

// Live webcam with the skeleton drawn on top.
// Video and overlay are mirrored together, like a selfie camera.
export default function CameraFeed({ videoRef, status, onStart, points, joint, angle, showFrame = false, className = '' }) {
  const j = points?.[joint]
  return (
    <div className={`relative overflow-hidden rounded-[20px] bg-slate-800 ${className}`}>
      <div className="absolute inset-0 -scale-x-100">
        <video ref={videoRef} muted playsInline className={`h-full w-full object-cover ${status === 'on' ? '' : 'invisible'}`} />
        {points && (
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden="true">
            {BONES.map(([a, b]) => points[a] && points[b] && (
              <line key={a + b} x1={points[a][0] * 100} y1={points[a][1] * 100} x2={points[b][0] * 100} y2={points[b][1] * 100}
                stroke="#5EEAD4" strokeWidth="4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            ))}
            {Object.entries(points).map(([name, p]) => (
              // zero-length line + round cap = a perfect dot, even with preserveAspectRatio="none"
              <line key={name} x1={p[0] * 100} y1={p[1] * 100} x2={p[0] * 100} y2={p[1] * 100}
                stroke={name === joint ? '#14B8A6' : '#F5B841'} strokeWidth={name === joint ? 18 : 11} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            ))}
          </svg>
        )}
        {showFrame && <div className="absolute inset-y-[6%] left-1/2 w-[38%] -translate-x-1/2 rounded-3xl border-4 border-dashed border-teal" />}
      </div>

      {j && typeof angle === 'number' && (
        <span
          className="absolute rounded-lg bg-navy px-2.5 py-1 font-en text-[17px] font-extrabold text-teal-light"
          style={{ left: `calc(${(1 - j[0]) * 100}% + 18px)`, top: `calc(${j[1] * 100}% - 14px)` }}
        >
          {angle}°
        </span>
      )}

      {status !== 'on' && (
        <div className="absolute inset-x-0 bottom-0 flex flex-col items-center gap-3 bg-gradient-to-t from-navy/90 to-transparent p-6 text-center text-white">
          <Camera size={32} />
          <Txt k={status === 'denied' ? 'cameraOff' : 'cameraAllow'} className="text-lg font-semibold" />
          {onStart && <Button size="md" onClick={onStart}><Txt k="cameraAllow" /></Button>}
        </div>
      )}
    </div>
  )
}
