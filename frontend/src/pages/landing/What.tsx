import { motion, useReducedMotion } from 'motion/react'
import { useState, type ReactNode, memo } from 'react'
import { ChapterText, Plate, Swatch } from '../../components/landing/kit'
import { StatusBadge, cx } from '../../components/ui'
import { RoughSpark, SlopeSpark, SunArc } from '../../components/viz'
import { DEFAULT_MISSION as M } from '../../data/mission'
import { shortName, siteById } from '../../data/sites'
import type { CriterionId, Status } from '../../data/types'
import { regionById } from '../../lib/assess'
import { useApp } from '../../lib/store'

/*
 * Chapter 03 · WHAT. Lunar reference on the left, Earth analog on the right, the verdict for that criterion between them.
 * The three marks are the whole vocabulary: nothing here is averaged into a score, and some rows are honestly empty.
 */

const SITE = siteById('craters-of-the-moon')!
const EASE = [0.23, 1, 0.32, 1] as const
const SILVER = 'var(--color-silver-300)', CYAN = 'var(--color-cyan)'

// Wide: Moon | verdict | Earth. Narrow: the verdict on top, the two drawings side by side beneath it.
const cols = 'grid grid-cols-2 items-center gap-x-3 gap-y-2 sm:grid-cols-[minmax(0,1fr)_minmax(9.5rem,13rem)_minmax(0,1fr)] sm:gap-x-6'
const dash = <span aria-hidden className="text-[15px] text-silver-500">—</span>
const num = (v: string) => <span className="mono text-[20px] text-paper">{v}</span>

function What() {
  const reduce = !!useReducedMotion()
  const { assessments, mission } = useApp()
  const region = regionById(M.regionId)
  const a = assessments.get(SITE.id)!
  const [on, setOn] = useState<CriterionId | null>(null)
  const crit = (id: CriterionId) => a.criteria.find((c) => c.id === id)!

  const rows: { id: CriterionId; label: string; moon: ReactNode; earth: ReactNode }[] = [
    { id: 'slope', label: 'Slope', moon: <SlopeSpark hist={region.slopeHist} limit={mission.slopeMax} color={SILVER} w={136} h={38} className="block h-[38px] w-[136px] max-w-full" />, earth: <SlopeSpark hist={SITE.slopeHist} limit={mission.slopeMax} color={CYAN} w={136} h={38} className="block h-[38px] w-[136px] max-w-full" /> },
    { id: 'roughness', label: `Roughness at ${mission.roughBaseline} m`, moon: <RoughSpark rough={region.rough} resM={region.dem.resM} baseline={mission.roughBaseline} max={mission.roughMax} color={SILVER} w={136} h={38} className="block h-[38px] w-[136px] max-w-full" />, earth: <RoughSpark rough={SITE.rough} resM={SITE.dem.resM} baseline={mission.roughBaseline} max={mission.roughMax} color={CYAN} w={136} h={38} className="block h-[38px] w-[136px] max-w-full" /> },
    { id: 'illumination', label: 'Low-angle sun', moon: <span className="mono text-[20px] text-amber">{mission.elMin}–{mission.elMax}°</span>, earth: <SunArc site={SITE} date="2026-12-14" lo={mission.elMin} hi={mission.elMax} minDur={mission.minDuration} w={136} h={38} className="block h-[38px] w-[136px] max-w-full" /> },
    { id: 'resolution', label: 'Data resolution', moon: num(`${region.dem.resM} m`), earth: num(`${SITE.dem.resM} m`) },
    { id: 'regolith', label: 'Soil and rocks', moon: dash, earth: dash },
    { id: 'environment', label: 'Gravity, vacuum, radiation', moon: dash, earth: dash },
  ]
  const active = on ? crit(on) : null
  const statusOf = (id: CriterionId): Status => crit(id).status

  return (
    <section id="what" aria-labelledby="what-title" className="scroll-mt-14 border-t border-[var(--line)] py-16 md:py-24">
      <div className="mx-auto grid max-w-[1680px] gap-x-12 gap-y-8 px-4 *:min-w-0 md:px-8 lg:grid-cols-12 lg:items-center">
        <div className="lg:col-span-4">
          <ChapterText id="what-title" n="03" q="What to validate" title="See what the evidence supports.">
            Each criterion is judged on its own. Nothing is averaged into a score, and a missing measurement stays missing.
          </ChapterText>
          <div className="mt-6 flex flex-wrap gap-2">
            <StatusBadge status="potential" compact /><StatusBadge status="not-suitable" compact /><StatusBadge status="not-assessed" compact />
          </div>
        </div>
        <div className="lg:col-span-8">
          <Plate
            label={`Lunar reference compared with ${SITE.name}, one row per criterion`}
            bar={<div className={cols + ' w-full'}><span className="sm:justify-self-end"><Swatch color={SILVER}>Lunar reference</Swatch></span><span aria-hidden className="hidden sm:block" /><span className="justify-self-end sm:justify-self-start"><Swatch color={CYAN}>{shortName(SITE)}</Swatch></span></div>}
            foot={<span aria-live="polite" className="block min-h-[2.75rem]">{active ? <><span className="font-medium text-paper">{active.label}. </span>{active.reason}</> : <>Hover, focus or tap a row for its evidence. Example site, illustrative data.</>}</span>}
          >
            <ul>
              {rows.map((r, i) => {
                const c = crit(r.id)
                return (
                  <li key={r.id} className="relative">
                    <motion.span aria-hidden className="absolute inset-x-0 top-0 h-px origin-left bg-[var(--line)]" initial={reduce ? false : { scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true, margin: '0px 0px -12% 0px' }} transition={{ duration: 0.55, ease: EASE, delay: i * 0.05 }} />
                    <button type="button" onPointerEnter={(e) => e.pointerType === 'mouse' && setOn(r.id)} onPointerLeave={(e) => e.pointerType === 'mouse' && setOn(null)} onFocus={() => setOn(r.id)} onBlur={() => setOn(null)} onClick={() => setOn(r.id)} aria-pressed={on === r.id}
                      className={cx(cols, 'min-h-[68px] w-full px-3.5 py-2 text-left transition-colors duration-[var(--duration-fast)]', on === r.id ? 'bg-white/[0.035]' : '')}>
                      <motion.div className="flex items-center justify-start sm:justify-end" initial={reduce ? false : { opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true, margin: '0px 0px -12% 0px' }} transition={{ duration: 0.4, delay: 0.1 + i * 0.05 }}>{r.moon}</motion.div>
                      <div className="order-first col-span-2 flex min-w-0 flex-col items-center gap-1 text-center sm:order-none sm:col-span-1">
                        <span className="text-[14px] leading-tight font-medium text-paper">{r.label}</span>
                        <StatusBadge status={statusOf(r.id)} compact label={r.id === 'environment' ? 'Earth cannot reproduce' : undefined} />
                      </div>
                      <motion.div className="flex items-center justify-end sm:justify-start" initial={reduce ? false : { opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true, margin: '0px 0px -12% 0px' }} transition={{ duration: 0.4, delay: 0.14 + i * 0.05 }}>{r.earth}</motion.div>
                    </button>
                    <span className="sr-only">{c.reason}</span>
                  </li>
                )
              })}
            </ul>
          </Plate>
        </div>
      </div>
    </section>
  )
}

export default memo(What)
