import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import Header from '../components/Header.jsx'
import Bi, { Txt } from '../components/Bi.jsx'
import { Button, Card, Chip, Segmented } from '../components/ui.jsx'
import { ArrowBack, Check, Info } from '../components/Icons.jsx'
import CameraFeed from '../components/CameraFeed.jsx'
import useCamera from '../hooks/useCamera.js'

function Item({ k, warn = false }) {
  return (
    <div className="flex items-center gap-3.5 text-lg">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${warn ? 'bg-amber-100 text-amber-800' : 'bg-teal-50 text-teal-dark'}`}>
        {warn ? <span className="font-extrabold">!</span> : <Check />}
      </span>
      <Txt k={k} />
    </div>
  )
}

export default function Setup() {
  const { ex, side, setSide } = useApp()
  const nav = useNavigate()
  const cam = useCamera(true)
  const arm = ex.group === 'arm'
  const sideLocked = Boolean(ex.side)   // the engine measures this side only
  const camKey = ex.camera_view === 'front' ? 'camFront' : ex.camera_view === 'side_right' ? 'camSideRight' : arm ? 'cam2Arm' : 'cam2Leg'

  return (
    <div className="flex min-h-full flex-col bg-page text-navy">
      <Header step={4} right={<Chip tone="teal" className="hidden xl:inline-flex">{ex.title ? <Txt k={ex.title} /> : ex.name}</Chip>} />
      <main className="mx-auto flex w-full max-w-[1360px] flex-1 flex-wrap gap-7 px-6 py-8 lg:px-12">
        <section className="flex min-w-0 flex-[1_1_460px] flex-col gap-5">
          <Bi as="div" k="setupTitle" className="text-4xl font-extrabold tracking-tight" subClassName="text-[22px]" />

          <Card className="flex flex-col gap-3.5 p-6">
            <Bi k={arm ? 'whichArm' : 'whichLeg'} className="text-[19px] font-bold" subClassName="text-[15px]" />
            {sideLocked ? (
              <div className="flex items-center gap-3">
                <span className="flex min-h-[60px] flex-1 items-center justify-center rounded-xl border-2 border-teal-dark bg-teal-50 text-[19px] font-bold"><Bi k={ex.side} inline /></span>
                <Chip tone="adjust"><Txt k="rightArmOnly" /></Chip>
              </div>
            ) : (
              <Segmented value={side} onChange={setSide}
                options={[{ value: 'left', label: <Bi k="left" inline /> }, { value: 'right', label: <Bi k="right" inline /> }]} />
            )}
          </Card>

          <Card className="flex flex-col gap-3 p-6">
            <Bi k="placeCamera" className="text-[19px] font-bold" subClassName="text-[15px]" />
            <Item k="cam1" />
            <Item k={camKey} />
            <Item k="cam3" />
            <Item k={arm ? 'cam4Arm' : 'cam4Leg'} warn />
          </Card>

          <div className="flex items-start gap-3.5 rounded-2xl bg-navy px-5 py-4 text-white">
            <span className="shrink-0 text-gold"><Info /></span>
            <div className="flex flex-col gap-1">
              <Txt k="practiceInfoTitle" className="text-lg font-bold" />
              <Txt k="practiceInfo" className="text-base leading-normal text-slate-300" />
            </div>
          </div>
        </section>

        <section className="flex min-w-0 flex-[1.3_1_560px] flex-col gap-4">
          <div className="relative min-h-[520px] flex-1">
            <CameraFeed videoRef={cam.videoRef} status={cam.status} onStart={cam.start} showFrame className="absolute inset-0 shadow-[0_10px_34px_rgba(11,31,58,0.18)]" />
            <div className="absolute start-4 top-4 flex flex-wrap gap-2.5">
              {cam.status === 'on'
                ? <Chip tone="good"><span className="h-2.5 w-2.5 rounded-full bg-green-600" /><Txt k="cameraOk" /></Chip>
                : <Chip tone="adjust"><Txt k={cam.status === 'denied' ? 'cameraOff' : 'cameraAllow'} /></Chip>}
            </div>
            <span className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-xl bg-navy/85 px-5 py-2.5 text-lg font-semibold text-white">
              <Bi k="standInFrame" inline subClassName="text-base" />
            </span>
          </div>
          <div className="flex flex-wrap justify-between gap-3.5">
            <Button variant="outline" onClick={() => nav('/exercise')}><ArrowBack /><Txt k="back" /></Button>
            <Button size="lg" disabled={!side} onClick={() => nav('/calibration')} title={side ? undefined : 'Choose a side first'}>
              <Bi k={side ? 'imReady' : 'chooseSideFirst'} inline subClassName="text-[17px]" />
            </Button>
          </div>
        </section>
      </main>
    </div>
  )
}
