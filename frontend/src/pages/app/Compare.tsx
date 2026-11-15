import LiveEvidence from '../../components/LiveEvidence'
import { ArrowRight, Pin, PinOff, Plus } from 'lucide-react'
import { ElevationChart, ResolutionGrid, RoughnessChart, SlopeChart } from '../../components/analysis/charts'
import { Pips, ProfilePair, QualifyingStrip, Row, Stat, Verdict, evidenceOf } from '../../components/analysis/figures'
import { DataTable, NoSite, Note, fmtCoord } from '../../components/analysis/shared'
import { TerrainReveal } from '../../components/analysis/TerrainReveal'
import { Button, Disclosure, StatusBadge, StatusGlyph, cx } from '../../components/ui'
import { EvidenceChip } from '../../components/evidence/chips'
import { MetricGroup } from '../../components/ui/Metrics'
import { PageHeader } from '../../components/ui/Page'
import { Term } from '../../components/ui/Term'
import { SunArc } from '../../components/viz'
import { NOT_REPRODUCIBLE } from '../../data/sources'
import { DEMO_HORIZON_DAYS } from '../../data/mission'
import { siteById } from '../../data/sites'
import type { Site } from '../../data/types'
import { regionById, resolvable, rmsAt, shareBelow } from '../../lib/assess'
import { compass, dayWindows, fmtMin } from '../../lib/solar'
import { useApp } from '../../lib/store'

function SiteSwitcher({ site }: { site: Site }) {
  const { compareIds, select, toggleCompare, assessments } = useApp()
  const ids = Array.from(new Set([site.id, ...compareIds]))
  const pinned = compareIds.includes(site.id)
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Earth candidates to compare">
      {ids.map((id) => {
        const s = siteById(id)!
        const on = id === site.id
        return (
          <button key={id} type="button" aria-pressed={on} onClick={() => select(id)}
            className={cx('flex min-h-11 items-center gap-2 rounded-[var(--radius-md)] border px-3.5 text-[13px] font-medium transition-[background-color,border-color,color,transform] duration-[var(--duration-fast)] active:scale-[0.97]', on ? 'border-cyan bg-cyan-soft text-paper' : 'border-[var(--line-strong)] text-silver-300 hover:text-paper')}>
            <StatusGlyph status={assessments.get(id)!.overall} size={14} />
            {s.name}
          </button>
        )
      })}
      <Button size="sm" variant="ghost" onClick={() => toggleCompare(site.id)} disabled={!pinned && compareIds.length >= 3} aria-pressed={pinned}>
        {pinned ? <PinOff size={15} aria-hidden /> : <Pin size={15} aria-hidden />}
        {pinned ? 'Unpin' : compareIds.length >= 3 ? 'List full (3)' : 'Pin to compare'}
      </Button>
      <a href="#/app/analogs" className="inline-flex min-h-11 items-center gap-1.5 rounded-md px-3 text-[13px] text-silver-300 transition-colors hover:text-paper md:min-h-9"><Plus size={15} aria-hidden />Add site</a>
    </div>
  )
}

function CompareBody({ site }: { site: Site }) {
  const { mission, assessments, date } = useApp()
  const region = regionById(mission.regionId)
  const a = assessments.get(site.id)!
  const cr = (id: string) => a.criteria.find((c) => c.id === id)!
  const shareM = shareBelow(region.slopeHist, mission.slopeMax)
  const shareE = shareBelow(site.slopeHist, mission.slopeMax)
  const rM = rmsAt(region.rough, mission.roughBaseline)
  const rE = rmsAt(site.rough, mission.roughBaseline)
  const okE = resolvable(site.dem.resM, mission.roughBaseline)
  const day = dayWindows(site, date, mission.elMin, mission.elMax, mission.minDuration)
  const missing = a.criteria.filter((c) => c.status === 'not-assessed' && c.id !== 'resolution' && c.id !== 'roughness')

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6 md:px-6 md:py-10">
      {/* Verdict */}
      <header className="space-y-4 pb-8">
        <PageHeader eyebrow="Moon reference · Earth candidate" title="Comparison" lede={<>Lunar reference against {site.name}, criterion by criterion. Screened criteria only, with no single similarity score.</>}
          actions={<Button variant="primary" onClick={() => (window.location.hash = '#/app/dossier')}>Open research dossier <ArrowRight size={16} aria-hidden /></Button>} />
        <SiteSwitcher site={site} />
        <Verdict criteria={a.criteria} />
      </header>

      {/* At a glance: the numbers, grouped, before the imagery */}
      <section aria-labelledby="glance-h" className="pb-8">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 id="glance-h" className="text-[20px] font-semibold">At a glance</h2>
          <EvidenceChip kind="illustrative" />
        </div>
        <p className="mt-1 mb-4 max-w-[62ch] text-[13px] leading-relaxed text-silver-300">Example-site figures are illustrative fixtures, with the lunar reference drawn from the same kind of model. Thresholds are your Mission criteria. Measured values with their <Term id="provenance">provenance</Term> are in Measured terrain evidence below.</p>
        <div className="grid gap-x-10 lg:grid-cols-2">
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title="Slope" rows={[{ label: `Share of area at or below ${mission.slopeMax}°`, ref: `${shareM.toFixed(0)} %`, cand: `${shareE.toFixed(0)} %`, need: `≥ ${mission.minTraversable} %`, status: cr('slope').status }]} />
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title={<>Roughness <span className="text-[13px] font-normal text-silver-400">(<Term id="roughness">what is this?</Term>)</span></>} rows={[{ label: `RMS height at a ${mission.roughBaseline} m baseline`, ref: `${rM.toFixed(2)} m`, cand: okE ? `${rE.toFixed(2)} m` : 'unresolved', need: `≤ ${mission.roughMax.toFixed(1)} m`, status: cr('roughness').status }]} />
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title="Elevation" rows={[{ label: 'Site elevation above sea level', ref: 'relative only', cand: `${site.elevM.toLocaleString('en-US')} m` }]} />
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title="Resolution" rows={[{ label: <>Grid cell size, which sets the <Term id="scale">analysis scale</Term></>, ref: `${region.dem.resM} m`, cand: `${site.dem.resM} m`, need: `≤ ${mission.maxDemRes} m`, status: cr('resolution').status }]} />
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title="Coverage" rows={[{ label: 'Criteria with evidence', cand: `${a.assessedCount} of ${a.totalCount}`, note: a.assessedCount === a.totalCount ? 'Complete' : 'Incomplete: some criteria have no evidence' }]} />
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title="Illumination" rows={[{ label: `Days in ${mission.elMin}–${mission.elMax}° for at least ${mission.minDuration} min, of ${DEMO_HORIZON_DAYS}`, ref: 'not computed', cand: `${a.qualifyingDays} days`, status: cr('illumination').status }]} />
          <MetricGroup refLabel="Lunar reference" candLabel="Earth candidate" title="Evidence status" rows={[{ label: 'Overall category, screened criteria only. There is no single similarity score.', ref: 'not assessed', cand: `${a.assessedCount} of ${a.totalCount} assessed`, status: a.overall }]} />
        </div>
      </section>

      {/* Hero: the same low sun on both surfaces */}
      <section className="space-y-5 border-t border-[var(--line)] pt-6 pb-10" aria-label="Terrain, lunar reference versus Earth candidate">
        <TerrainReveal moonSeed={region.seed} earthSeed={site.seed} moonLabel={region.name} earthLabel={site.name} />
        <ProfilePair moonSeed={region.seed} siteSeed={site.seed} moonRes={region.dem.resM} earthRes={site.dem.resM} />
        <dl className="grid gap-x-10 gap-y-1 text-[13px] sm:grid-cols-2">
          <div className="flex gap-3"><dt className="shrink-0 text-silver-400">Lunar</dt><dd className="text-silver-200">{region.name} · {region.approxLat}</dd></div>
          <div className="flex gap-3"><dt className="shrink-0 text-cyan">Earth</dt><dd className="text-silver-200">{site.name} · <span className="mono text-xs">{fmtCoord(site.lat, site.lon)}</span> · {site.terrain}</dd></div>
        </dl>
      </section>

      {/* Measures */}
      <Row q="Is the slope workable?" pips={<Pips level={evidenceOf(cr('slope'))} />}
        answer={<><Stat tone="moon" value={shareM.toFixed(0)} unit={`% ≤ ${mission.slopeMax}°`} /><Stat tone="earth" value={shareE.toFixed(0)} unit={`% ≤ ${mission.slopeMax}°`} note={`needs ≥ ${mission.minTraversable}%`} ok={shareE >= mission.minTraversable} /></>}>
        <SlopeChart region={region} site={site} mission={mission} />
      </Row>

      <Row q={`Is it smooth enough at ${mission.roughBaseline} m?`} pips={<Pips level={evidenceOf(cr('roughness'))} />}
        answer={<><Stat tone="moon" value={rM.toFixed(2)} unit="m RMS" /><Stat tone="earth" value={rE.toFixed(2)} unit="m RMS" note={okE ? `limit ${mission.roughMax.toFixed(1)} m` : 'grid cannot resolve this baseline'} ok={okE ? rE <= mission.roughMax : undefined} /></>}>
        <RoughnessChart region={region} site={site} mission={mission} />
      </Row>

      <Row q="Can the data see that detail?" pips={<Pips level={evidenceOf(cr('resolution'))} />}
        answer={<><Stat tone="moon" value={String(region.dem.resM)} unit="m cells" /><Stat tone="earth" value={String(site.dem.resM)} unit="m cells" note={`need ≤ ${mission.maxDemRes} m`} ok={site.dem.resM <= mission.maxDemRes} /></>}>
        <ResolutionGrid region={region} site={site} />
      </Row>

      <Row q="When is the sun low enough?" pips={<Pips level={evidenceOf(cr('illumination'))} />}
        answer={<><Stat tone="earth" value={String(a.qualifyingDays)} unit="days of 60" note={`in ${mission.elMin}–${mission.elMax}° for ≥ ${mission.minDuration} min`} /><p className="text-xs text-silver-400">Lunar timeline: not computed (needs ephemerides).</p></>}>
        <div className="space-y-6">
          <QualifyingStrip site={site} mission={mission} />
          <figure>
            <SunArc site={site} date={date} lo={mission.elMin} hi={mission.elMax} minDur={mission.minDuration} w={640} h={110} className="h-auto w-full" />
            <figcaption className="mt-1 flex flex-wrap justify-between gap-x-4 text-xs text-silver-400">
              <span className="mono">{date} · local day 00–24 h</span>
              <span>{day.segments.length ? day.segments.map((s) => <span key={s.startMin} className="mono mr-3 text-amber">{fmtMin(s.startMin)}–{fmtMin(s.endMin)} az {Math.round(s.azStart)}° {compass(s.azStart)}</span>) : 'No qualifying window on this date'}</span>
            </figcaption>
          </figure>
          <Note>Simplified flat-horizon solar model, ≈1° accuracy. Illustrative, not a validated prediction.</Note>
        </div>
      </Row>

      <section className="border-t border-[var(--line)] py-8">
        <Disclosure title={<span className="text-[15px] font-medium">Elevation transect</span>} meta={<span className="text-xs text-silver-400">relative metres</span>}>
          <ElevationChart region={region} site={site} />
        </Disclosure>
      </section>

      {/* Criteria on demand */}
      <section className="grid gap-x-12 gap-y-8 border-t border-[var(--line)] py-8 md:grid-cols-[15rem_minmax(0,1fr)]" aria-labelledby="crit-h">
        <h2 id="crit-h" className="text-[15px] font-medium">Criteria</h2>
        <div className="max-w-3xl">
          <div className="border-t border-[var(--line)]">
            {a.criteria.filter((c) => c.id !== 'environment').map((c) => (
              <Disclosure key={c.id} title={<span className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-3"><span className="text-[14px] font-medium">{c.label}</span><span className="text-[13px] text-silver-400">{c.reason}</span></span>} meta={<span className="flex items-center gap-3"><span className="hidden sm:inline"><Pips level={evidenceOf(c)} /></span><StatusBadge status={c.status} compact /></span>}>{c.detail}</Disclosure>
            ))}
            <Disclosure title={<span className="text-[14px] font-medium">Earth cannot reproduce <span className="font-normal text-silver-400">· excluded from the category</span></span>} meta={<StatusBadge status="not-suitable" compact label="Not reproducible" />}>
              <ul className="space-y-2">{NOT_REPRODUCIBLE.map((n) => <li key={n.id}><span className="font-medium text-paper">{n.label}.</span> {n.detail}</li>)}</ul>
            </Disclosure>
          </div>
        </div>
      </section>

      {/* Gaps */}
      <section className="grid gap-x-12 gap-y-4 border-t border-[var(--line)] py-8 md:grid-cols-[15rem_minmax(0,1fr)]" aria-labelledby="gap-h">
        <h2 id="gap-h" className="text-[15px] font-medium">Still missing</h2>
        <ul className="max-w-3xl divide-y divide-[var(--line)] text-[14px]">
          {[...missing.map((c) => c.label), 'Terrain horizon (flat-ground sun model)', 'Weather and visibility on the day', 'Lunar-side illumination timeline'].map((m) => (
            <li key={m} className="flex items-center gap-3 py-2.5 text-silver-200"><i aria-hidden className="h-3 w-3 shrink-0 rounded-[2px] border border-dashed border-silver-400" />{m}</li>
          ))}
        </ul>
      </section>

      <LiveEvidence />

      <div className="flex flex-wrap items-center gap-3 border-t border-[var(--line)] pt-8">
        <Button onClick={() => (window.location.hash = '#/app/dossier')}>Open research dossier</Button>
        <a href="#/app/windows" className="inline-flex min-h-11 items-center px-3 text-[14px] text-silver-300 transition-colors hover:text-paper">← Rehearsal windows</a>
      </div>
      <details className="mt-6 max-w-3xl text-[13px] text-silver-400">
        <summary className="min-h-11 cursor-pointer py-2">Screening numbers (table)</summary>
        <DataTable caption="Screening numbers" head={['Metric', 'Lunar ref.', 'Earth cand.']} rows={[[`Area ≤ ${mission.slopeMax}° (%)`, shareM.toFixed(1), shareE.toFixed(1)], [`RMS at ${mission.roughBaseline} m (m)`, rM.toFixed(2), rE.toFixed(2)], ['Grid spacing (m)', region.dem.resM, site.dem.resM]]} />
      </details>
    </div>
  )
}

export default function Compare() {
  const { selectedId } = useApp()
  const site = siteById(selectedId)
  if (!site) return <><NoSite what="scientific comparison" /><div className="mx-auto max-w-[1280px] px-4 pb-10 md:px-6"><LiveEvidence /></div></>
  return <CompareBody site={site} />
}
