import { ArrowRight, Check, Plus, Search, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { DEMO_HORIZON_DAYS } from '../../data/mission'
import { shortName, siteById } from '../../data/sites'
import { STATUS_LABEL } from '../../lib/assess'
import { go, href } from '../../lib/router'
import { useApp } from '../../lib/store'
import { ProfileThumb, RoughSpark, SlopeSpark } from '../viz'
import { Button, cx, StatusGlyph } from '../ui'
import { activeFilterCount, EMPTY_FILTERS } from './shared'

const MAX_COMPARE = 3
type Sort = 'fit' | 'name' | 'sun'

function Measure({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <span className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-[12px] leading-none whitespace-nowrap text-silver-400">{label}</span>
      {children}
    </span>
  )
}

export function SiteList({ onHover, onPick, onFilters }: { onHover: (id: string | null) => void; onPick: (id: string) => void; onFilters: () => void }) {
  const { results, assessments, selectedId, compareIds, toggleCompare, mission, filters, setFilters } = useApp()
  const [notice, setNotice] = useState('')
  const [sort, setSort] = useState<Sort>('fit')
  const nFilters = activeFilterCount(filters)

  useEffect(() => {
    if (!notice) return
    const t = window.setTimeout(() => setNotice(''), 4000)
    return () => window.clearTimeout(t)
  }, [notice])

  const ordered = useMemo(() => {
    if (sort === 'fit') return results
    const byName = (a: string, b: string) => shortName(siteById(a)!).localeCompare(shortName(siteById(b)!))
    return [...results].sort(sort === 'name' ? byName : (a, b) => assessments.get(b)!.qualifyingDays - assessments.get(a)!.qualifyingDays || byName(a, b))
  }, [results, sort, assessments])

  const onCompare = (id: string) => {
    if (!compareIds.includes(id) && compareIds.length >= MAX_COMPARE) return setNotice('Up to 3 sites. Remove one first.')
    setNotice('')
    toggleCompare(id)
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="space-y-2 border-b border-[var(--line)] px-3 pt-3 pb-2.5">
        <div className="relative">
          <Search size={16} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-silver-400" />
          <input
            type="search"
            aria-label="Search candidates"
            placeholder="Search candidates"
            value={filters.query}
            onChange={(e) => setFilters({ query: e.target.value })}
            className="min-h-11 w-full rounded-[var(--radius-md)] bg-white/6 pr-3 pl-9 text-[14px] text-paper placeholder:text-silver-500 focus:bg-white/9"
          />
        </div>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[14px] font-medium text-paper"><span className="mono">{results.length}</span> {results.length === 1 ? 'candidate' : 'candidates'}</h2>
          <div className="flex items-center gap-1">
            <label className="sr-only" htmlFor="site-sort">Sort candidates</label>
            <select id="site-sort" value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="min-h-11 rounded-[var(--radius-md)] bg-transparent px-2 text-[13px] text-silver-200 hover:bg-white/6">
              <option value="fit">Best screen first</option>
              <option value="sun">Most low-sun days</option>
              <option value="name">Name</option>
            </select>
            <button type="button" onClick={onFilters} className="hidden min-h-11 items-center gap-1.5 rounded-[var(--radius-md)] px-2.5 text-[13px] font-medium text-silver-200 transition-[background-color,transform] hover:bg-white/6 active:scale-[0.97] lg:flex">
              <SlidersHorizontal size={15} aria-hidden /> Filters
              {nFilters > 0 && <span className="mono grid h-4 min-w-4 place-items-center rounded-full bg-amber px-1 text-[12px] leading-none text-ink-900" aria-label={`${nFilters} active`}>{nFilters}</span>}
            </button>
          </div>
        </div>
        <p className="text-[12px] leading-snug text-silver-400">
          Slope ≤ <span className="mono">{mission.slopeMax}°</span> · rough ≤ <span className="mono">{mission.roughMax.toFixed(1)} m</span> · sun <span className="mono">{mission.elMin}–{mission.elMax}°</span>{' '}
          <a className="text-amber underline underline-offset-2" href={href({ page: 'app', screen: 'mission' })}>Edit</a>
        </p>
        {notice && <p role="status" className="rounded-[var(--radius-sm)] bg-amber-soft px-2 py-1 text-[12px] text-amber">{notice}</p>}
      </header>

      {results.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
          <p className="text-[15px] font-medium">No candidates match</p>
          <Button variant="secondary" onClick={() => setFilters(EMPTY_FILTERS)}>Clear filters</Button>
        </div>
      ) : (
        <ul aria-label="Candidate sites" className="scroll-thin min-h-0 flex-1 overflow-y-auto">
          {ordered.map((id) => {
            const s = siteById(id)!
            const a = assessments.get(id)!
            const sel = id === selectedId
            const inCmp = compareIds.includes(id)
            const maxFrac = Math.min(1, a.qualifyingDays / DEMO_HORIZON_DAYS)
            return (
              <li key={id} onMouseEnter={() => onHover(id)} onMouseLeave={() => onHover(null)} className={cx('relative border-b border-[var(--line)] transition-colors duration-[var(--duration-fast)]', sel ? 'bg-amber/7' : 'hover:bg-white/3')}>
                {sel && <span aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-amber" />}
                <button type="button" onClick={() => onPick(id)} onFocus={() => onHover(id)} onBlur={() => onHover(null)} aria-current={sel ? 'true' : undefined} className="block w-full px-3 py-3 pr-14 text-left transition-colors active:bg-white/5">
                  <span className="flex items-center gap-3">
                    <span aria-hidden className="shrink-0"><ProfileThumb seed={s.seed} w={80} h={40} className="h-10 w-20 rounded-[var(--radius-xs)] bg-ink-800" /></span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15px] leading-tight font-medium text-paper">{shortName(s)}</span>
                      <span className="block truncate text-[13px] text-silver-400">{s.place}</span>
                    </span>
                    <span className="shrink-0"><StatusGlyph status={a.overall} size={18} /></span>
                  </span>
                  <span className="sr-only">{STATUS_LABEL[a.overall]}. Slope, roughness and low-sun days shown below.</span>
                  <span aria-hidden className="mt-2.5 flex gap-3">
                    <Measure label="Slope"><SlopeSpark hist={s.slopeHist} limit={mission.slopeMax} w={64} h={20} className="h-5 w-full" /></Measure>
                    <Measure label="Roughness"><RoughSpark rough={s.rough} resM={s.dem.resM} baseline={mission.roughBaseline} max={mission.roughMax} w={64} h={20} className="h-5 w-full" /></Measure>
                    <Measure label="Low sun">
                      <span className="block">
                        <span className="mt-1 block h-1.5 rounded-full bg-white/10"><span className="block h-full rounded-full bg-amber" style={{ width: `${maxFrac * 100}%` }} /></span>
                        <span className="mono mt-1 block text-[12px] leading-none whitespace-nowrap text-silver-300">{a.qualifyingDays}/{DEMO_HORIZON_DAYS} days</span>
                      </span>
                    </Measure>
                  </span>
                </button>
                <button type="button" onClick={() => onCompare(id)} aria-pressed={inCmp} aria-label={inCmp ? `Remove ${s.name} from comparison` : `Add ${s.name} to comparison`}
                  className={cx('absolute top-1 right-1 grid h-11 w-11 place-items-center rounded-full transition-[color,background-color,transform] active:scale-[0.92]', inCmp ? 'text-cyan' : 'text-silver-500 hover:bg-white/6 hover:text-paper')}>
                  <span className={cx('grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] border-[1.5px]', inCmp ? 'border-cyan bg-cyan/20' : 'border-current')}>
                    {inCmp ? <Check size={13} strokeWidth={3} aria-hidden /> : <Plus size={13} aria-hidden />}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {compareIds.length > 0 && (
        <div className="flex items-center gap-2 border-t border-[var(--line-strong)] bg-ink-850 px-3 py-2">
          <ul aria-label="Selected for comparison" className="flex min-w-0 flex-1 flex-wrap gap-1.5">
            {compareIds.map((id) => (
              <li key={id}>
                <button type="button" onClick={() => toggleCompare(id)} aria-label={`Remove ${siteById(id)!.name} from comparison`} className="flex min-h-8 items-center gap-1 rounded-full border border-cyan/40 bg-cyan-soft py-1 pr-1.5 pl-2.5 text-[12px] text-cyan transition-transform active:scale-[0.96]">
                  <span className="max-w-[7.5rem] truncate">{shortName(siteById(id)!)}</span><X size={12} aria-hidden />
                </button>
              </li>
            ))}
          </ul>
          <Button variant="primary" size="sm" disabled={compareIds.length < 2} onClick={() => go({ page: 'app', screen: 'compare' })}>
            Compare {compareIds.length} site{compareIds.length === 1 ? '' : 's'} <ArrowRight size={14} aria-hidden />
          </Button>
        </div>
      )}
    </div>
  )
}
