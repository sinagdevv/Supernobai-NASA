import { useMemo, useState, type ReactNode } from 'react'
import { DEMO_HORIZON_DAYS, DEMO_START } from '../../data/mission'
import type { Criterion, Mission, Site } from '../../data/types'
import { STATUS_LABEL } from '../../lib/assess'
import { CELL_M, N } from '../../lib/profiles'
import { addDays, dayWindows } from '../../lib/solar'
import { ProfileThumb } from '../viz'
import { StatusGlyph, cx } from '../ui'

const SHORT: Record<string, string> = { slope: 'Slope', roughness: 'Rough', illumination: 'Sun', resolution: 'Grid', regolith: 'Soil', rocks: 'Rocks', environment: 'Gravity+' }

/* ─────────── Evidence: how much of a criterion the data can actually speak to ─────────── */
export type Evidence = 'assessed' | 'partial' | 'none'
const EV: Record<Evidence, { n: number; text: string }> = { assessed: { n: 3, text: 'Assessed' }, partial: { n: 2, text: 'Partly resolved' }, none: { n: 0, text: 'No evidence' } }

/** Roughness/resolution can be partly resolved (the grid speaks to coarser scales); soil and rocks have no data at all. */
export function evidenceOf(c: Criterion): Evidence {
  if (c.status !== 'not-assessed') return 'assessed'
  return c.id === 'roughness' || c.id === 'resolution' ? 'partial' : 'none'
}

export function Pips({ level, paper }: { level: Evidence; paper?: boolean }) {
  const { n, text } = EV[level]
  return (
    <span className="inline-flex items-center gap-1.5" role="img" aria-label={`Evidence: ${text}`}>
      <span className="flex gap-0.5" aria-hidden>
        {[0, 1, 2].map((i) => <i key={i} className={cx('h-2 w-3 rounded-[1px] border', i < n ? (paper ? 'border-graphite bg-graphite' : 'border-silver-300 bg-silver-300') : paper ? 'border-graphite-soft/60' : 'border-silver-500')} />)}
      </span>
      <span className={cx('text-[12px]', paper ? 'text-graphite-soft' : 'text-silver-400')}>{text}</span>
    </span>
  )
}

/* ─────────── Verdict strip: one mark per criterion; focus / hover / tap reveals the reason ─────────── */
export function Verdict({ criteria }: { criteria: Criterion[] }) {
  const [i, setI] = useState<number | null>(null)
  const c = i === null ? null : criteria[i]
  return (
    <div>
      <ul className="flex flex-wrap gap-x-1 gap-y-1">
        {criteria.map((k, j) => (
          <li key={k.id}>
            <button type="button" aria-label={`${k.label}: ${k.id === 'environment' ? 'Earth cannot reproduce' : STATUS_LABEL[k.status]}`} aria-pressed={i === j}
              onMouseEnter={() => setI(j)} onMouseLeave={() => setI(null)} onFocus={() => setI(j)} onBlur={() => setI(null)} onClick={() => setI(i === j ? null : j)}
              className={cx('flex min-h-11 min-w-[44px] flex-col items-center justify-center gap-0.5 rounded-md px-1.5 transition-[background-color,transform] duration-[var(--duration-fast)] active:scale-[0.97]', i === j ? 'bg-white/8' : 'hover:bg-white/5')}>
              <StatusGlyph status={k.status} size={18} />
              <span className="text-[12px] leading-none text-silver-400">{SHORT[k.id]}</span>
            </button>
          </li>
        ))}
      </ul>
      <p aria-live="polite" className="mt-1 min-h-10 max-w-[44rem] text-[13px] leading-snug text-silver-300">
        {c ? <><span className="font-medium text-paper">{c.label}</span> · {c.id === 'environment' ? 'Earth cannot reproduce' : STATUS_LABEL[c.status]}. {c.reason}</> : <span className="text-silver-500">Hover, focus or tap a mark for its reason.</span>}
      </p>
    </div>
  )
}

/* ─────────── Same low sun on both profiles, with each dataset's cell size drawn to scale ─────────── */
const SPAN_M = (N - 1) * CELL_M
export function ProfilePair({ moonSeed, siteSeed, moonRes, earthRes, el = 3 }: { moonSeed: number; siteSeed: number; moonRes: number; earthRes: number; el?: number }) {
  const bar = (m: number) => `${Math.max((m / SPAN_M) * 100, 0.35)}%`
  const rows = [
    { k: 'moon' as const, label: 'Lunar reference', seed: moonSeed, res: moonRes, c: 'text-silver-200' },
    { k: 'earth' as const, label: 'Earth candidate', seed: siteSeed, res: earthRes, c: 'text-cyan' },
  ]
  return (
    <figure>
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.k} className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[11rem_1fr]">
            <div>
              <p className={cx('text-[13px] font-medium', r.c)}>{r.label}</p>
              <p className="flex items-center gap-2 text-[12px] text-silver-400">
                <span aria-hidden className="relative h-2 w-16 bg-white/10"><i className="absolute inset-y-0 left-0 bg-amber" style={{ width: bar(r.res) }} /></span>
                <span className="mono whitespace-nowrap">1 cell = {r.res} m</span>
              </p>
            </div>
            <ProfileThumb kind={r.k} seed={r.seed} sunEl={el} w={640} h={56} className="h-14 w-full" label={`${r.label} terrain profile lit by a ${el}° sun (schematic)`} />
          </div>
        ))}
      </div>
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-silver-400 sm:pl-[12rem]">
        <span className="flex items-center gap-2"><i aria-hidden className="h-px w-[17.7%] min-w-8 bg-silver-300" /><span className="mono">200 m</span></span>
        <span>Sun {el}° · shaded stretches dimmed · features under 2 cells ({earthRes * 2} m on Earth) are unresolved · schematic</span>
      </figcaption>
    </figure>
  )
}

/* ─────────── Which of the next 60 days have a qualifying window ─────────── */
export function QualifyingStrip({ site, mission }: { site: Site; mission: Mission }) {
  const days = useMemo(() => Array.from({ length: DEMO_HORIZON_DAYS }, (_, i) => dayWindows(site, addDays(DEMO_START, i), mission.elMin, mission.elMax, mission.minDuration).minutes), [site, mission.elMin, mission.elMax, mission.minDuration])
  const n = days.filter(Boolean).length
  const max = Math.max(1, ...days)
  return (
    <figure>
      <div role="img" aria-label={`${n} of ${DEMO_HORIZON_DAYS} days from ${DEMO_START} have the sun in ${mission.elMin}–${mission.elMax}° for at least ${mission.minDuration} minutes (illustrative).`} className="flex h-10 items-end gap-px">
        {days.map((m, i) => <i key={i} className={cx('flex-1', m ? 'bg-amber' : 'bg-white/10')} style={{ height: m ? `${Math.max(25, (m / max) * 100)}%` : '8%' }} />)}
      </div>
      <figcaption className="mt-1.5 flex justify-between text-[12px] text-silver-400"><span className="mono">{DEMO_START}</span><span><span className="mono text-amber">{n}</span> of {DEMO_HORIZON_DAYS} days qualify</span><span className="mono">+{DEMO_HORIZON_DAYS} d</span></figcaption>
    </figure>
  )
}

/* ─────────── One measurement = one ruled row: question + answer on the left, the figure on the right ─────────── */
export function Row({ q, answer, pips, children, id }: { q: string; answer: ReactNode; pips?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="grid gap-x-12 gap-y-5 border-t border-[var(--line)] py-8 md:grid-cols-[15rem_minmax(0,1fr)]">
      <div>
        <h2 className="text-[15px] font-medium">{q}</h2>
        <div className="mt-3 space-y-1.5">{answer}</div>
        {pips && <div className="mt-3">{pips}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

export function Stat({ tone, value, unit, note, ok }: { tone: 'moon' | 'earth'; value: string; unit?: string; note?: string; ok?: boolean }) {
  return (
    <p className="flex flex-wrap items-baseline gap-x-2">
      <span aria-hidden className={cx('h-2 w-2 shrink-0 self-center rounded-full', tone === 'moon' ? 'bg-silver-300' : 'bg-cyan')} />
      <span className="sr-only">{tone === 'moon' ? 'Lunar reference' : 'Earth candidate'}:</span>
      <span className={cx('mono text-[22px] leading-none font-medium', tone === 'earth' ? 'text-cyan' : 'text-silver-200')}>{value}</span>
      {unit && <span className="mono text-[12px] text-silver-400">{unit}</span>}
      {note && <span className="text-[12px] text-silver-400">{ok === undefined ? '' : ok ? '✓ ' : '✗ '}{note}</span>}
    </p>
  )
}
