import { SITES, shortName } from '../data/sites'
import type { Site, Status } from '../data/types'
import { cx } from './ui'

/** Equirectangular graticule with site markers. Used as the map fallback (no tiles / no WebGL) and in small compositions. */
export function SchematicMap({ sites = SITES, selectedId, statuses, onSelect, className, interactive = true, labels, label = 'Schematic world map of candidate Earth analog sites' }: {
  sites?: Site[]
  selectedId?: string | null
  statuses?: Map<string, Status>
  onSelect?: (id: string) => void
  className?: string
  interactive?: boolean
  labels?: boolean
  label?: string
}) {
  const X = (lon: number) => ((lon + 180) / 360) * 360
  const Y = (lat: number) => ((90 - lat) / 180) * 180
  return (
    <svg viewBox="0 0 360 180" className={cx('block h-full w-full', className)} role="group" aria-label={label} preserveAspectRatio="xMidYMid slice">
      <rect width="360" height="180" fill="var(--color-ink-850)" />
      {[-60, -30, 0, 30, 60].map((lat) => (
        <line key={lat} x1="0" x2="360" y1={Y(lat)} y2={Y(lat)} stroke="var(--line)" strokeWidth={lat === 0 ? 0.6 : 0.3} strokeDasharray={lat === 0 ? '' : '2 3'} />
      ))}
      {[-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150].map((lon) => (
        <line key={lon} y1="0" y2="180" x1={X(lon)} x2={X(lon)} stroke="var(--line)" strokeWidth={lon === 0 ? 0.6 : 0.3} strokeDasharray={lon === 0 ? '' : '2 3'} />
      ))}
      {sites.map((s) => {
        const on = s.id === selectedId
        const st = statuses?.get(s.id)
        const cls = st === 'potential' ? 'text-ok' : st === 'not-suitable' ? 'text-bad' : 'text-silver-300'
        const inner = (
          <g className={cls} transform={`translate(${X(s.lon)} ${Y(s.lat)})`}>
            {on && <circle r="7" fill="none" stroke="var(--color-amber)" strokeWidth="1" />}
            {st === 'not-suitable' ? <path d="M-3 -3L3 3M3 -3L-3 3" stroke="currentColor" strokeWidth="1.6" /> : st === 'not-assessed' ? <circle r="3" fill="none" stroke="currentColor" strokeWidth="1.2" strokeDasharray="1.5 1.5" /> : <circle r="3" fill="currentColor" />}
            {labels && <text x="6" y="1.6" fontSize="4.6" fill={on ? "var(--color-amber)" : "var(--color-silver-300)"} style={{ fontFamily: "var(--font-mono)" }}>{shortName(s)}</text>}
            {interactive && <circle r="12" fill="transparent" />}
          </g>
        )
        return interactive ? (
          <g key={s.id} role="button" tabIndex={0} aria-label={`${s.name}, ${s.place}`} aria-pressed={on} className="cursor-pointer outline-none [&:focus-visible_circle:first-child]:stroke-amber" onClick={() => onSelect?.(s.id)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect?.(s.id))}>
            {inner}
          </g>
        ) : (
          <g key={s.id}>{inner}</g>
        )
      })}
    </svg>
  )
}
