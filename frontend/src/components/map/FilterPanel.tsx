import { Search } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { SITES, TERRAIN_CLASSES } from '../../data/sites'
import type { Status } from '../../data/types'
import { STATUS_LABEL } from '../../lib/assess'
import { useApp } from '../../lib/store'
import { Button, Slider, StatusGlyph } from '../ui'
import { activeFilterCount, EMPTY_FILTERS } from './shared'

function Check({ checked, onChange, children }: { checked: boolean; onChange: () => void; children: ReactNode }) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius-sm)] px-1 text-[13px] text-silver-200 transition-colors hover:bg-white/4 active:bg-white/8">
      <input type="checkbox" checked={checked} onChange={onChange} className="h-5 w-5 shrink-0 cursor-pointer accent-[var(--color-amber)]" />
      {children}
    </label>
  )
}

const STATUSES: Status[] = ['potential', 'not-assessed', 'not-suitable']
const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

/** Filter controls — used inline in the desktop sidebar and inside the mobile drawer. */
export function FilterPanel({ onDone }: { onDone?: () => void }) {
  const { filters, setFilters, assessments, results } = useApp()
  const active = activeFilterCount(filters)
  const countBy = (s: Status) => [...assessments.values()].filter((a) => a.overall === s).length
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--line)] px-4 py-3">
        <div>
          <h2 className="text-[15px] font-semibold">Filters</h2>
          <p className="mono text-[12px] text-silver-400">{results.length} of {SITES.length} sites match</p>
        </div>
        <Button variant="ghost" size="sm" disabled={!active} onClick={() => setFilters(EMPTY_FILTERS)}>Clear filters</Button>
      </div>

      <div className="scroll-thin min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <div>
          <label htmlFor="site-search" className="mb-1.5 block text-[13px] font-medium text-silver-200">Search sites</label>
          <div className="relative">
            <Search size={15} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-silver-500" />
            <input id="site-search" type="search" value={filters.query} onChange={(e) => setFilters({ query: e.target.value })} placeholder="Name or region"
              className="min-h-11 w-full rounded-[var(--radius-md)] border border-[var(--line)] bg-ink-800 py-2 pr-3 pl-9 text-[14px] text-paper placeholder:text-silver-500 hover:border-silver-500" />
          </div>
        </div>

        <fieldset>
          <legend className="mb-1 text-[13px] font-medium text-silver-200">Terrain class</legend>
          {TERRAIN_CLASSES.map((t) => (
            <Check key={t} checked={filters.terrain.includes(t)} onChange={() => setFilters({ terrain: toggle(filters.terrain, t) })}>
              <span className="flex-1">{t}</span>
              <span className="mono text-[12px] text-silver-400">{SITES.filter((s) => s.terrain === t).length}</span>
            </Check>
          ))}
        </fieldset>

        <Slider label="Coarsest DEM grid allowed" value={filters.maxDemRes} min={1} max={30} unit=" m" onChange={(v) => setFilters({ maxDemRes: v })}
          hint="Hides sites whose elevation data is coarser than this. A 30 m grid cannot show what a 5 m grid can." />

        <fieldset>
          <legend className="mb-1 text-[13px] font-medium text-silver-200">Assessment</legend>
          {STATUSES.map((s) => (
            <Check key={s} checked={filters.statuses.includes(s)} onChange={() => setFilters({ statuses: toggle(filters.statuses, s) })}>
              <StatusGlyph status={s} size={16} />
              <span className="flex-1">{STATUS_LABEL[s]}</span>
              <span className="mono text-[12px] text-silver-400">{countBy(s)}</span>
            </Check>
          ))}
          <p className="mt-1 text-[12px] leading-snug text-silver-500">Screened criteria only — set in your mission workspace.</p>
        </fieldset>
      </div>

      {onDone && (
        <div className="border-t border-[var(--line)] p-3">
          <Button variant="primary" className="w-full" onClick={onDone}>Show {results.length} {results.length === 1 ? 'site' : 'sites'}</Button>
        </div>
      )}
    </div>
  )
}

/** Left slide-in drawer for tablet/phone. Native <dialog>: focus trap, Esc to close, inert background. */
export function FilterDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} onClose={onClose} onClick={(e) => e.target === ref.current && onClose()} aria-label="Filters"
      className="tw-drawer fixed inset-y-0 left-0 m-0 h-dvh max-h-none w-[min(320px,88vw)] max-w-none overflow-hidden border-r border-[var(--line-strong)] bg-ink-850 p-0 text-paper shadow-[var(--shadow-pop)] backdrop:bg-black/60">
      <style>{`.tw-drawer[open]{animation:tw-drawer-in var(--duration-base) var(--ease-out)}@keyframes tw-drawer-in{from{transform:translateX(-24px);opacity:0}}`}</style>
      {open && <FilterPanel onDone={onClose} />}
    </dialog>
  )
}
