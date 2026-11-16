import Bi, { Txt } from './Bi.jsx'

const CHOICES = ['none', 'light', 'heavy']

// Weight check before calibration (E3 / E4): the camera's guess, then the patient decides.
// "We see: Light weight. Is that right?"  [No weight] [Light] [Heavy]
// The tapped answer is final: the server saves it with the session.
export default function WeightQuestion({ suggested, onChoose }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="weight-q"
      className="absolute inset-x-4 top-1/2 z-10 flex -translate-y-1/2 flex-col gap-4 rounded-2xl bg-white p-6 text-navy shadow-[0_12px_40px_rgba(11,31,58,0.35)]">
      <div id="weight-q" className="flex flex-col gap-1">
        <span className="text-[26px] font-extrabold leading-tight">
          <Txt k="weightWeSee" />: <Txt k={`weight_${suggested}`} className="text-teal-dark" />. <Txt k="weightIsRight" />
        </span>
        <Bi k="weightPick" className="text-[17px] text-slate-600" subClassName="text-[15px]" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {CHOICES.map((c) => (
          <button key={c} type="button" onClick={() => onChoose(c)}
            className={`flex min-h-[72px] flex-col items-center justify-center rounded-xl border-2 px-2 py-2 text-center text-[19px] font-bold transition
              ${c === suggested ? 'border-teal-dark bg-teal-50' : 'border-slate-300 bg-white hover:border-slate-400'}`}>
            <Bi k={`weight_${c}`} className="items-center" subClassName="text-[14px]" />
          </button>
        ))}
      </div>
    </div>
  )
}
