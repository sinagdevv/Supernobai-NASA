import { useRef, type KeyboardEvent } from 'react'
import { LUNAR_REGIONS } from '../../data/mission'
import { cx } from '../ui'
import { RegionProfile } from './RegionProfile'

/** Visual radio group of the lunar reference regions: a terrain profile, a name and an approximate latitude each. */
export function RegionPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const i0 = LUNAR_REGIONS.findIndex((r) => r.id === value)
  const onKey = (e: KeyboardEvent) => {
    const n = LUNAR_REGIONS.length
    const next = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? (i0 + 1) % n : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? (i0 - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1
    if (next < 0) return
    e.preventDefault()
    onChange(LUNAR_REGIONS[next].id)
    refs.current[next]?.focus()
  }
  return (
    <div role="radiogroup" aria-label="Lunar reference region" onKeyDown={onKey} className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
      {LUNAR_REGIONS.map((r, i) => {
        const on = r.id === value
        return (
          <button key={r.id} ref={(el) => { refs.current[i] = el }} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} title={r.summary} onClick={() => onChange(r.id)}
            className={cx('min-h-[76px] rounded-[var(--radius-md)] border p-2 text-left transition-[border-color,background-color,transform] duration-[var(--duration-fast)] ease-[var(--ease-out)] active:scale-[0.97]', on ? 'border-amber bg-amber-soft' : 'border-[var(--line)] hover:border-[var(--line-strong)]')}>
            <RegionProfile seed={r.seed} w={96} h={30} className="h-[30px] w-full" label={`${r.name} reference terrain profile (schematic)`} />
            <span className="mt-1.5 block truncate text-[13px] font-medium leading-tight">{r.name}</span>
            <span className="mono block text-[12px] text-silver-400">{r.approxLat}</span>
          </button>
        )
      })}
    </div>
  )
}
