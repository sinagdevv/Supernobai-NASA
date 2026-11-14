import { Grid3x3 } from 'lucide-react'
import { useSyncExternalStore } from 'react'
import type { Filters } from '../../lib/store'
import { cx } from '../ui'

export const EMPTY_FILTERS: Filters = { terrain: [], maxDemRes: 30, statuses: [], query: '' }

export const activeFilterCount = (f: Filters) =>
  (f.terrain.length ? 1 : 0) + (f.statuses.length ? 1 : 0) + (f.maxDemRes < 30 ? 1 : 0) + (f.query.trim() ? 1 : 0)

export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(query)
      m.addEventListener('change', cb)
      return () => m.removeEventListener('change', cb)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

export const fmtLat = (v: number) => `${Math.abs(v).toFixed(2)}°${v >= 0 ? 'N' : 'S'}`
export const fmtLon = (v: number) => `${Math.abs(v).toFixed(2)}°${v >= 0 ? 'E' : 'W'}`
export const fmtCoord = (lat: number, lon: number) => `${fmtLat(lat)} ${fmtLon(lon)}`

/** DEM grid chip. Coarser than the mission's requirement is drawn dashed and says so. */
export function DemChip({ resM, maxRes }: { resM: number; maxRes: number }) {
  const coarse = resM > maxRes
  return (
    <span
      title={coarse ? `Coarser than the ${maxRes} m required by your mission settings` : 'Meets the mission’s resolution requirement'}
      className={cx('mono inline-flex items-center gap-1 rounded-[var(--radius-xs)] border px-1.5 py-0.5 text-[12px] leading-4', coarse ? 'border-dashed border-silver-500 text-silver-300' : 'border-cyan/40 bg-cyan-soft text-cyan')}
    >
      <Grid3x3 size={11} aria-hidden />
      {resM} m grid{coarse && <span className="sr-only"> (coarser than required)</span>}
      {coarse && <span aria-hidden> · coarse</span>}
    </span>
  )
}
