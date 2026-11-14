import { motion } from 'motion/react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { addDays, daysInMonth, isoDate, MONTHS, pad, type DaySummary } from '../../lib/solar'
import { cx } from '../ui'

const WEEK = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
const short = (min: number) => (min >= 100 ? `${Math.floor(min / 60)}h${pad(min % 60)}` : `${min}m`)

interface Props {
  y: number
  m: number
  days: DaySummary[]
  selected: string
  onSelect: (date: string) => void
  onMonth: (delta: number) => void
}

/** Month grid. One tab stop (roving), arrow keys move by day/week, PageUp/PageDown by month. */
export function DayCalendar({ y, m, days, selected, onSelect, onMonth }: Props) {
  const grid = useRef<HTMLDivElement>(null)
  const kbd = useRef(false)
  const [byKey, setByKey] = useState(false) // keyboard moves never animate
  const first = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7
  const cells: (DaySummary | null)[] = [...Array(first).fill(null), ...days]
  while (cells.length % 7) cells.push(null)
  const rows = Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7))
  const maxMin = Math.max(1, ...days.map((d) => d.minutes))
  const inView = selected.startsWith(`${y}-${pad(m)}`)
  const tabDate = inView ? selected : isoDate(y, m, 1)

  useEffect(() => {
    if (!kbd.current) return
    const b = grid.current?.querySelector<HTMLButtonElement>(`[data-date="${selected}"]`)
    if (b) {
      b.focus()
      kbd.current = false
    }
  }, [selected, y, m])

  const onKey = (e: React.KeyboardEvent) => {
    const base = (document.activeElement as HTMLElement | null)?.dataset?.date ?? selected
    const delta = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key as 'ArrowLeft']
    let next: string | null = delta ? addDays(base, delta) : null
    if (e.key === 'PageUp' || e.key === 'PageDown') {
      const [by, bm, bd] = base.split('-').map(Number)
      const t = bm - 1 + (e.key === 'PageUp' ? -1 : 1)
      const ny = by + Math.floor(t / 12)
      const nm = ((t % 12) + 12) % 12 + 1
      next = isoDate(ny, nm, Math.min(bd, daysInMonth(ny, nm)))
    }
    if (e.key === 'Home' || e.key === 'End') next = isoDate(y, m, e.key === 'Home' ? 1 : days.length)
    if (!next) return
    e.preventDefault()
    kbd.current = true
    setByKey(true)
    onSelect(next)
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <button type="button" onClick={() => onMonth(-1)} aria-label="Previous month" className="grid h-11 w-11 place-items-center rounded-md text-silver-300 transition-colors hover:bg-white/8 hover:text-paper">
          <ChevronLeft size={18} aria-hidden />
        </button>
        <p className="text-[15px] font-medium" aria-live="polite">
          {MONTHS[m - 1]} {y}
        </p>
        <button type="button" onClick={() => onMonth(1)} aria-label="Next month" className="grid h-11 w-11 place-items-center rounded-md text-silver-300 transition-colors hover:bg-white/8 hover:text-paper">
          <ChevronRight size={18} aria-hidden />
        </button>
      </div>
      <div ref={grid} role="grid" aria-label={`${MONTHS[m - 1]} ${y}: days with sun inside the lunar reference band`} onKeyDown={onKey}>
        <div role="row" className="grid grid-cols-7">
          {WEEK.map((w) => (
            <div key={w} role="columnheader" className="mono py-1 text-center text-[12px] text-silver-500">
              {w}
            </div>
          ))}
        </div>
        {rows.map((row, ri) => (
          <div key={ri} role="row" className="grid grid-cols-7">
            {row.map((d, ci) => {
              if (!d) return <div key={ci} role="gridcell" aria-hidden className="h-[52px]" />
              const day = +d.date.slice(8)
              const on = d.date === selected
              const has = d.segments.length > 0
              return (
                <div key={ci} role="gridcell" aria-selected={on}>
                  <button
                    type="button"
                    data-date={d.date}
                    tabIndex={d.date === tabDate ? 0 : -1}
                    onClick={() => { setByKey(false); onSelect(d.date) }}
                    aria-label={`${day} ${MONTHS[m - 1]}, ${has ? `${d.minutes} minutes qualifying` : 'no qualifying window'}`}
                    className={cx('relative flex h-[52px] w-full min-w-11 flex-col items-center justify-center gap-0.5 rounded-[var(--radius-sm)] transition-colors duration-[var(--duration-fast)] active:scale-[0.97]', on ? 'text-paper' : 'text-silver-300 hover:bg-white/8')}
                  >
                    {on && <motion.span layoutId="day-ring" className="absolute inset-0.5 rounded-[var(--radius-sm)] border border-amber bg-amber-soft" transition={byKey ? { duration: 0 } : { type: 'spring', duration: 0.26, bounce: 0 }} />}
                    <span className="relative text-[13px] font-medium leading-none">{day}</span>
                    {has ? (
                      <>
                        <span className="mono relative text-[12px] leading-none text-amber">{short(d.minutes)}</span>
                        <span aria-hidden className="relative h-[2px] w-[60%] overflow-hidden rounded bg-white/10">
                          <span className="block h-full rounded bg-amber" style={{ width: `${Math.max(12, (d.minutes / maxMin) * 100)}%` }} />
                        </span>
                      </>
                    ) : (
                      <span className="mono relative text-[12px] leading-none text-silver-500" aria-hidden>
                        —
                      </span>
                    )}
                  </button>
                </div>
              )
            })}
          </div>
        ))}
      </div>
      <p className="mt-2 px-3 text-[12px] leading-snug text-silver-500 sm:px-0">
        Amber bar and minutes = time in band; — = no window.
      </p>
    </div>
  )
}
