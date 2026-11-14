import { motion } from 'motion/react'
import { ArrowRight, RotateCcw } from 'lucide-react'
import { useMemo } from 'react'
import { SITES, shortName } from '../../data/sites'
import { SOURCES } from '../../data/sources'
import type { Status } from '../../data/types'
import { STATUS_LABEL } from '../../lib/assess'
import { useApp } from '../../lib/store'
import { Button, cx, StatusGlyph } from '../ui'
import { ProfileThumb, RoughSpark, SlopeSpark } from '../viz'

const ORDER: Status[] = ['potential', 'not-assessed', 'not-suitable']
const SEG: Record<Status, string> = {
  potential: 'bg-ok',
  'not-assessed': 'bg-[repeating-linear-gradient(135deg,var(--color-silver-500)_0_3px,transparent_3px_6px)] ring-1 ring-inset ring-silver-500',
  'not-suitable': 'bg-bad',
}

const go = (hash: string) => { window.location.hash = hash }

/** How the criteria change the shortlist: a stacked category bar, the counts, and a ranked, clickable site list. */
export function LiveAssessment() {
  const { mission: m, resetMission, assessments, select } = useApp()
  const counts = useMemo(() => {
    const c: Record<Status, number> = { potential: 0, 'not-assessed': 0, 'not-suitable': 0 }
    assessments.forEach((a) => c[a.overall]++)
    return c
  }, [assessments])
  const rows = useMemo(() => [...SITES].sort((a, b) => ORDER.indexOf(assessments.get(a.id)!.overall) - ORDER.indexOf(assessments.get(b.id)!.overall) || a.name.localeCompare(b.name)), [assessments])

  return (
    <aside aria-label="Live assessment" className="min-w-0 lg:sticky lg:top-[calc(var(--topbar-h)+24px)] lg:self-start">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[17px] font-semibold">Live assessment</h2>
        <Button size="sm" variant="ghost" onClick={resetMission}><RotateCcw size={14} aria-hidden />Defaults</Button>
      </div>

      <div aria-hidden className="mt-4 flex h-3 overflow-hidden rounded-[2px]">
        {ORDER.map((s) => counts[s] > 0 && <div key={s} className={SEG[s]} style={{ flex: counts[s] }} />)}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2" aria-live="polite">
        {ORDER.map((s) => (
          <div key={s}>
            <div className="flex items-center gap-1.5 text-[12px] leading-tight text-silver-300"><StatusGlyph status={s} size={14} />{STATUS_LABEL[s]}</div>
            <div className="mono mt-1 text-[28px] leading-none font-medium">{counts[s]}</div>
          </div>
        ))}
      </div>

      <ul className="mt-4 border-t border-[var(--line)]">
        {rows.map((s) => {
          const a = assessments.get(s.id)!
          return (
            <motion.li key={s.id} layout transition={{ type: 'spring', bounce: 0, duration: 0.3 }} className="border-b border-[var(--line)]">
              <button type="button" onClick={() => { select(s.id); go('#/app/analogs') }} className={cx('flex min-h-14 w-full items-center gap-3 py-1.5 text-left transition-[background-color,transform] duration-[var(--duration-fast)] active:scale-[0.99] hover:bg-white/3')}>
                <ProfileThumb seed={s.seed} w={56} h={26} className="h-[26px] w-14 shrink-0" label={`${s.name} terrain profile (schematic)`} />
                <span className="min-w-0 flex-1 truncate text-[14px]">{shortName(s)}</span>
                <span className="flex items-center gap-2 max-[379px]:hidden">
                  <SlopeSpark hist={s.slopeHist} limit={m.slopeMax} w={36} h={20} className="h-5 w-9" />
                  <RoughSpark rough={s.rough} resM={s.dem.resM} baseline={m.roughBaseline} max={m.roughMax} w={36} h={20} className="h-5 w-9" />
                </span>
                <StatusGlyph status={a.overall} />
              </button>
            </motion.li>
          )
        })}
      </ul>
      <p className="mt-2 text-[12px] leading-snug text-silver-400">Per row: share of area under the rover limit, then roughness against scale (dashed where the grid can’t resolve it). Open a row to inspect it.</p>

      <Button variant="primary" className="mt-5 w-full" onClick={() => go('#/app/analogs')}>Explore Earth analogs <ArrowRight size={16} aria-hidden /></Button>

      <p className="mt-6 border-t border-[var(--line)] pt-4 text-[12px] leading-relaxed text-silver-400">
        Illustrative prototype data, not NASA results. Only slope, roughness and low-sun availability are screened; every other criterion stays Not Yet Assessed.{' '}
        {SOURCES.map((x, i) => (
          <span key={x.id}><a className="text-cyan underline underline-offset-2 hover:text-paper" href={x.url} target="_blank" rel="noreferrer noopener">{x.name.split(' (')[0]}</a>{i < SOURCES.length - 1 ? ' · ' : ''}</span>
        ))}
      </p>
    </aside>
  )
}
