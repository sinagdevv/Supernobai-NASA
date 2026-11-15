import { ArrowRight, Lock } from 'lucide-react'
import type { ReactNode } from 'react'
import { HorizonDiagram, RoughChart, SlopeChart } from '../../components/mission/charts'
import { AssessmentWorkspace } from '../../components/mission/AssessmentWorkspace'
import { LiveAssessment } from '../../components/mission/LiveAssessment'
import { RegionPicker } from '../../components/mission/RegionPicker'
import { Button, cx, Segmented, Slider } from '../../components/ui'
import { PageHeader, ReadingKey } from '../../components/ui/Page'
import { Term } from '../../components/ui/Term'
import { go } from '../../lib/router'
import { RegionProfile } from '../../components/mission/RegionProfile'
import { OBJECTIVES, ROUGH_BASELINES } from '../../data/mission'
import { siteById } from '../../data/sites'
import MarsReference from '../../components/MarsReference'
import { regionById } from '../../lib/assess'
import { usePlanet } from '../../lib/planet'
import { useApp } from '../../lib/store'

function Area({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="border-t border-[var(--line)] pt-6">
      <h2 className="text-[17px] font-semibold">{title}</h2>
      {hint && <p className="mt-1 text-[13px] text-silver-400">{hint}</p>}
      <div className="mt-5 space-y-8">{children}</div>
    </section>
  )
}

/** One criterion: its scientific definition drawn as a chart, with the controls that move it beneath. */
function Criterion({ name, children, controls }: { name: string; children: ReactNode; controls: ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-[13px] font-medium text-silver-300">{name}</h3>
      {children}
      <div className="mt-1 grid gap-x-8 sm:grid-cols-2">{controls}</div>
    </div>
  )
}

const chip = (on: boolean, locked?: boolean) =>
  cx('inline-flex min-h-11 items-center gap-2 rounded-[var(--radius-md)] border px-3 text-[14px] font-medium transition-[border-color,background-color,transform] duration-[var(--duration-fast)] ease-[var(--ease-out)] active:scale-[0.97]',
    on ? 'border-amber bg-amber-soft' : locked ? 'cursor-not-allowed border-dashed border-[var(--line-strong)] text-silver-500' : 'border-[var(--line)] hover:border-[var(--line-strong)]')

/** Mars: the measured reference region, then the Layer 5 assessment against criteria defined for Mars alone. */
function MarsMission() {
  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 md:px-8 lg:py-12">
      <PageHeader eyebrow="Mars · Jezero regional terrain · secondary target" title="Jezero region" lede="Regional terrain measured from NASA MOLA topography: elevation, slope and roughness at the scales the data can support."
        actions={<Button variant="primary" onClick={() => go({ page: 'app', screen: 'compare' })}>Compare with Earth <ArrowRight size={16} aria-hidden /></Button>} />
      <ReadingKey className="mt-8" items={[
        { term: 'Measured now', text: <>Elevation, slope, roughness and relief from 463 m to 1.8 km, with <Term id="coverage">coverage</Term> and <Term id="provenance">provenance</Term>.</> },
        { term: 'Needs finer data', text: 'Rover-scale slope, rocks and traction need a HiRISE or CTX terrain model of the site.' },
        { term: <Term id="computed">Computed, not validated</Term>, text: 'Rehearsal windows (Layer 4) and the suitability assessment (Layer 5) below are computed by the service. Neither has been checked against observations.' },
      ]} />
      <div className="mt-8"><MarsReference /></div>
      <div className="mt-10"><AssessmentWorkspace planet="mars" /></div>
    </div>
  )
}

export default function Mission() {
  const { planet } = usePlanet()
  return planet === 'mars' ? <MarsMission /> : <LunarMission />
}

function LunarMission() {
  const { mission: m, setMission, selectedId, date } = useApp()
  const region = regionById(m.regionId)
  const site = siteById(selectedId)
  const mid = (m.elMin + m.elMax) / 2

  return (
    <div className="mx-auto max-w-[1320px] px-4 py-8 md:px-8 lg:py-12">
      <PageHeader eyebrow="Moon · lunar south pole · primary mission" title="Mission" lede="What the rover must handle. Test the stored lunar terrain against your criteria, then screen example Earth sites."
        actions={<Button variant="primary" onClick={() => go({ page: 'app', screen: 'analogs' })}>Explore Earth candidate sites <ArrowRight size={16} aria-hidden /></Button>} />
      <ReadingKey className="mt-8" items={[
        { term: 'Measured terrain', text: <>The assessment tests stored lunar Site01 terrain. Terrain criteria are measured at a stated <Term id="scale">analysis scale</Term> and can pass or fail.</> },
        { term: <Term id="computed">Computed, not validated</Term>, text: 'Light criteria and the verdict are computed by the service. Nothing is checked against observations, and nothing is stored.' },
        { term: 'Illustrative examples', text: 'The example Earth sites further down, and their screening, are fixtures, not measurements.' },
      ]} />
      <div className="mt-8"><AssessmentWorkspace planet="moon" /></div>

      <div className="mt-12 grid gap-x-12 gap-y-10 border-t border-[var(--line)] pt-8 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0">
        <h2 className="text-[20px] font-semibold">Screen example Earth sites</h2>
        <p className="mt-2 max-w-[40rem] text-[14px] leading-relaxed text-silver-300">Illustrative: these example sites and their slope, roughness and sun figures are fixtures, not measurements. Every control here re-screens them. The computed assessment above is separate.</p>

        <div className="mt-8 space-y-10">
          <Area title="Mission reference">
            <div className="flex flex-wrap gap-2">
              <span className="inline-flex min-h-11 items-center rounded-[var(--radius-md)] border border-[var(--line)] px-3 text-[14px] font-medium text-silver-300">Moon · south pole</span>
              <div role="radiogroup" aria-label="Mission objective" className="flex flex-wrap gap-2">
                {OBJECTIVES.map((o) => (
                  <button key={o.id} type="button" role="radio" aria-checked={o.id === m.objectiveId} aria-disabled={!o.active} title={o.blurb} onClick={() => o.active && setMission({ objectiveId: o.id })} className={chip(o.id === m.objectiveId, !o.active)}>
                    {!o.active && <Lock size={13} aria-hidden />}
                    {o.active ? 'Rover mobility & navigation, low sun' : o.label.split(/ & | imaging/)[0] + ' · roadmap'}
                  </button>
                ))}
              </div>
            </div>
            <RegionPicker value={m.regionId} onChange={(id) => setMission({ regionId: id })} />
            <figure>
              <RegionProfile seed={region.seed} w={640} h={96} sunEl={Math.max(0.5, mid)} className="h-24 w-full" label={`${region.name} reference terrain profile, lit by a sun at ${mid.toFixed(1)} degrees (schematic)`} />
              <figcaption className="mono mt-2 text-xs text-silver-400">{region.name} · {region.approxLat} · sun {mid.toFixed(1)}° · schematic profile, not LRO data</figcaption>
            </figure>
          </Area>

          <Area title="Experiment criteria" hint="Drawn on the reference region. Candidates are screened against the same limits.">
            <Criterion name="Terrain slope" controls={<>
              <Slider label="Slope limit" value={m.slopeMax} min={2} max={30} unit="°" onChange={(v) => setMission({ slopeMax: v })} />
              <Slider label="Min. traversable share" value={m.minTraversable} min={20} max={95} step={5} unit="%" onChange={(v) => setMission({ minTraversable: v })} />
            </>}>
              <SlopeChart region={region} m={m} />
            </Criterion>

            <Criterion name="Roughness" controls={<>
              <Slider label="Max. roughness (RMS height)" value={m.roughMax} min={0.2} max={4} step={0.1} format={(v) => `${v.toFixed(1)} m`} onChange={(v) => setMission({ roughMax: v })} />
              <div className="space-y-3 py-2">
                <div className="flex flex-wrap items-center gap-3"><span className="w-28 text-[13px] font-medium text-silver-200">Baseline</span><Segmented label="Roughness baseline" value={m.roughBaseline} onChange={(v) => setMission({ roughBaseline: v })} options={ROUGH_BASELINES.map((b) => ({ value: b, label: `${b} m` }))} /></div>
                <div className="flex flex-wrap items-center gap-3"><span className="w-28 text-[13px] font-medium text-silver-200">Required grid</span><Segmented label="Required DEM resolution" value={m.maxDemRes} onChange={(v) => setMission({ maxDemRes: v })} options={[2, 5, 10, 30].map((b) => ({ value: b, label: `≤ ${b} m` }))} /></div>
              </div>
            </>}>
              <RoughChart region={region} m={m} />
            </Criterion>

            <Criterion name="Solar elevation band" controls={<>
              <Slider label="Sun elevation — minimum" value={m.elMin} min={0} max={5} step={0.1} format={(v) => `${v.toFixed(1)}°`} onChange={(v) => setMission({ elMin: v, elMax: Math.max(m.elMax, v + 0.5) })} />
              <Slider label="Sun elevation — maximum" value={m.elMax} min={0.5} max={10} step={0.1} format={(v) => `${v.toFixed(1)}°`} onChange={(v) => setMission({ elMax: v, elMin: Math.min(m.elMin, v - 0.5) })} />
              <Slider label="Minimum time in band" value={m.minDuration} min={5} max={120} step={5} unit=" min" onChange={(v) => setMission({ minDuration: v })} />
            </>}>
              <HorizonDiagram m={m} site={site} date={date} />
              <p className="mt-2 text-xs text-silver-400">The band stands in for the lunar lighting to rehearse. Lunar illumination timelines need ephemerides and are not computed here. Natural sunlight only.</p>
            </Criterion>
          </Area>
        </div>
      </div>

      <LiveAssessment />
      </div>
    </div>
  )
}
