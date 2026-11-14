import { ArrowLeft, ArrowRight, Check, Plus } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { DEMO_HORIZON_DAYS } from '../../data/mission'
import { shortName, siteById } from '../../data/sites'
import { NOT_REPRODUCIBLE } from '../../data/sources'
import type { Assessment, Status } from '../../data/types'
import { resolvable, rmsAt, shareBelow, STATUS_LABEL } from '../../lib/assess'
import { go } from '../../lib/router'
import { useApp } from '../../lib/store'
import { GeoDot, ProfileThumb, RoughSpark, SlopeSpark, SunArc } from '../viz'
import { Button, Disclosure, StatusGlyph } from '../ui'
import { fmtLat, fmtLon } from './shared'

const MAX_COMPARE = 3
const SUN_EL = 2.4

function verdict(a: Assessment): string {
  const screened = a.criteria.filter((c) => c.id !== 'environment')
  const n = (s: Status) => screened.filter((c) => c.status === s).length
  if (a.overall === 'potential') return `Potentially suitable on ${n('potential')} screened criteria`
  if (a.overall === 'not-suitable') return `${n('not-suitable')} screened ${n('not-suitable') === 1 ? 'criterion fails' : 'criteria fail'}`
  return `Evidence incomplete: ${n('not-assessed')} criteria not yet assessed`
}

function Metric({ graphic, value, caption }: { graphic: ReactNode; value: string; caption: string }) {
  return (
    <div className="grid grid-cols-[104px_1fr] items-center gap-3">
      <div aria-hidden>{graphic}</div>
      <div>
        <p className="mono text-[14px] text-paper">{value}</p>
        <p className="text-[12px] leading-snug text-silver-400">{caption}</p>
      </div>
    </div>
  )
}

export function SiteDetail({ id }: { id: string }) {
  const { select, assessments, mission, compareIds, toggleCompare, date } = useApp()
  const [crit, setCrit] = useState<string | null>(null)
  const site = siteById(id)
  const a = assessments.get(id)
  if (!site || !a) return null
  const inCmp = compareIds.includes(id)
  const full = !inCmp && compareIds.length >= MAX_COMPARE
  const share = shareBelow(site.slopeHist, mission.slopeMax)
  const rms = rmsAt(site.rough, mission.roughBaseline)
  const canResolve = resolvable(site.dem.resM, mission.roughBaseline)
  const active = a.criteria.find((c) => c.id === crit)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <header className="px-4 pt-3 pb-4">
          <Button variant="ghost" size="sm" className="-ml-3" onClick={() => select(null)}><ArrowLeft size={15} aria-hidden /> All candidates</Button>
          <h2 className="font-display mt-1 text-[28px] leading-[1.06] text-paper">{shortName(site)}</h2>
          <p className="text-[14px] text-silver-400">{site.place}</p>
          <p className="mt-3 flex items-center gap-2 text-[14px] text-silver-200"><StatusGlyph status={a.overall} size={18} /><span>{verdict(a)}</span></p>
          <p className="mt-0.5 pl-[26px] text-[12px] text-silver-400">Screened criteria only. <span className="sr-only">{STATUS_LABEL[a.overall]}.</span></p>
        </header>

        {/* Lunar reference above, this Earth site below, both lit by the same low sun. */}
        <section aria-label="Terrain profile comparison" className="px-4 pb-4">
          <p className="text-[12px] font-medium text-silver-300">Lunar reference</p>
          <ProfileThumb kind="moon" w={320} h={46} sunEl={SUN_EL} className="mt-0.5 h-[46px] w-full" />
          <p className="mt-2 text-[12px] font-medium text-cyan">{shortName(site)}</p>
          <ProfileThumb seed={site.seed} w={320} h={46} sunEl={SUN_EL} className="mt-0.5 h-[46px] w-full" label={`Terrain profile of ${site.name} (schematic)`} />
          <p className="mt-1.5 text-[12px] text-silver-400">Schematic profiles lit at <span className="mono">{SUN_EL}°</span>. Illustrative, not survey data.</p>
        </section>

        <section aria-label="Location" className="flex items-center gap-3 border-t border-[var(--line)] px-4 py-3">
          <GeoDot lat={site.lat} lon={site.lon} className="h-9 w-[72px] shrink-0 rounded-[var(--radius-xs)]" />
          <p className="mono text-[12px] leading-relaxed text-silver-200">{fmtLat(site.lat)} {fmtLon(site.lon)}<br /><span className="text-silver-400">{site.elevM.toLocaleString('en-US')} m · {site.tzLabel.split(' ')[0]}</span></p>
          <p className="ml-auto text-right text-[12px] leading-snug text-silver-400">{site.terrain}</p>
        </section>

        <section aria-label="Mission metrics" className="space-y-3.5 border-t border-[var(--line)] px-4 py-4">
          <Metric
            graphic={<SlopeSpark hist={site.slopeHist} limit={mission.slopeMax} w={104} h={34} className="h-[34px] w-full" />}
            value={`${share.toFixed(0)}% ≤ ${mission.slopeMax}°`}
            caption={`of area · needs ≥ ${mission.minTraversable}%`}
          />
          <Metric
            graphic={<RoughSpark rough={site.rough} resM={site.dem.resM} baseline={mission.roughBaseline} max={mission.roughMax} w={104} h={34} className="h-[34px] w-full" />}
            value={`${rms.toFixed(2)} m RMS`}
            caption={canResolve ? `at ${mission.roughBaseline} m · limit ${mission.roughMax.toFixed(1)} m` : `${site.dem.resM} m grid can’t resolve ${mission.roughBaseline} m`}
          />
          <Metric
            graphic={<SunArc site={site} date={date} lo={mission.elMin} hi={mission.elMax} minDur={mission.minDuration} w={104} h={34} className="h-[34px] w-full" />}
            value={`${a.qualifyingDays}/${DEMO_HORIZON_DAYS} days`}
            caption={`sun in ${mission.elMin}–${mission.elMax}° for ≥ ${mission.minDuration} min`}
          />
        </section>

        <section aria-label="Criteria" className="border-t border-[var(--line)] px-4 py-3">
          <div role="group" aria-label="Assessment by criterion" className="-ml-2 flex">
            {a.criteria.map((c) => (
              <button key={c.id} type="button" aria-label={`${c.label}: ${STATUS_LABEL[c.status]}`} aria-pressed={crit === c.id}
                onPointerEnter={(e) => e.pointerType === 'mouse' && setCrit(c.id)} onFocus={() => setCrit(c.id)} onClick={() => setCrit(c.id)}
                className={`grid h-11 w-11 place-items-center rounded-full transition-[background-color,transform] active:scale-[0.92] ${crit === c.id ? 'bg-white/10' : 'hover:bg-white/6'}`}>
                <StatusGlyph status={c.status} size={20} />
              </button>
            ))}
          </div>
          <p className="min-h-[2.75rem] text-[13px] leading-snug text-silver-300" aria-live="polite">
            {active ? <><span className="font-medium text-paper">{active.label}.</span> {active.reason}</> : 'Hover or tap a symbol for its criterion.'}
          </p>
          <p className="mt-1 text-[12px] leading-snug text-silver-400">Earth cannot reproduce lunar gravity, vacuum, radiation or polar thermal extremes.</p>
          <div className="mt-1">
            <Disclosure title={<span className="text-[13px] font-medium text-silver-200">Details</span>}>
              <ul className="space-y-3">
                {a.criteria.map((c) => (
                  <li key={c.id} className="flex gap-2.5">
                    <span className="mt-0.5 shrink-0"><StatusGlyph status={c.status} size={16} /></span>
                    <span><span className="font-medium text-paper">{c.label}.</span> {c.reason}<span className="mt-0.5 block text-[12px] text-silver-400">{c.detail}</span></span>
                  </li>
                ))}
              </ul>
            </Disclosure>
            <Disclosure title={<span className="text-[13px] font-medium text-silver-200">Data &amp; limits</span>}>
              <dl className="mono grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
                <dt className="text-silver-500">DEM</dt><dd className="text-silver-200">{site.dem.name}</dd>
                <dt className="text-silver-500">Grid</dt><dd className="text-silver-200">{site.dem.resM} m · baselines ≥ {2 * site.dem.resM} m</dd>
                <dt className="text-silver-500">Values</dt><dd className="text-silver-200">Illustrative fixtures</dd>
              </dl>
              <p className="mt-3 text-[12px] text-silver-400">{site.summary}{site.heritage ? ` ${site.heritage}` : ''}</p>
              <ul className="mt-3 list-disc space-y-1 pl-4 text-[13px] text-silver-300">{site.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              <p className="mt-3 text-[13px] font-medium text-paper">Earth cannot reproduce</p>
              <ul className="mt-1 space-y-1.5 text-[13px]">
                {NOT_REPRODUCIBLE.map((n) => <li key={n.id}><span className="text-paper">{n.label}.</span> {n.detail}</li>)}
              </ul>
              <p className="mt-3 text-[12px] text-silver-500">Product names and resolutions are demonstration assumptions. Verify against the real dataset.</p>
            </Disclosure>
          </div>
        </section>
      </div>

      <footer className="space-y-2 border-t border-[var(--line)] bg-ink-850 p-3">
        <Button variant="primary" className="w-full" onClick={() => go({ page: 'app', screen: 'windows' })}>Find rehearsal windows <ArrowRight size={16} aria-hidden /></Button>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="secondary" size="sm" aria-pressed={inCmp} disabled={full} title={full ? 'Comparison is limited to 3 sites' : undefined} onClick={() => toggleCompare(id)}>
            {inCmp ? <Check size={14} aria-hidden /> : <Plus size={14} aria-hidden />}{inCmp ? 'Remove from comparison' : 'Add to comparison'}
          </Button>
          <Button variant="secondary" size="sm" disabled={full} onClick={() => { if (!inCmp) toggleCompare(id); go({ page: 'app', screen: 'compare' }) }}>Compare <ArrowRight size={14} aria-hidden /></Button>
        </div>
      </footer>
    </div>
  )
}
