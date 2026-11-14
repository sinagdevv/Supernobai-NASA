import { useMemo } from 'react'
import { band, line, lunarMeters, N, runs, shade } from '../../lib/profiles'

/**
 * Schematic lunar reference profile that differs per region (the shared ProfileThumb keeps one lunar profile).
 * Same fixture terrain, shifted and scaled by the region seed so regions are visibly distinct. Illustrative only.
 */
export function RegionProfile({ seed, w, h, sunEl, className, label }: { seed: number; w: number; h: number; sunEl?: number; className?: string; label: string }) {
  const g = useMemo(() => {
    const base = lunarMeters()
    const off = (seed * 5) % N
    const amp = 0.7 + ((seed * 7) % 10) / 22
    const m = base.map((_, i) => base[(i + off) % N] * amp)
    const min = Math.min(...m), max = Math.max(...m), span = Math.max(max - min, 1)
    const pad = 4, T = Math.max(5, h * 0.18)
    const xs = m.map((_, i) => (i / (N - 1)) * w)
    const y = m.map((v) => h - pad - T - ((v - min) / span) * (h - pad * 2 - T - 4))
    const bot = y.map((v) => v + T)
    const hs = m.map((v) => ((v - min) / span) * 30)
    const sh = sunEl ? runs(shade(hs, (w / (N - 1)) * 0.6, sunEl)) : []
    return { area: band(xs, y, bot), edge: line(xs, y), shade: sh.map(([a, b]) => band(xs, y, bot, a, b)).join('') }
  }, [seed, w, h, sunEl])
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={className} role="img" aria-label={label}>
      <path d={g.area} fill="var(--color-silver-300)" />
      {g.shade && <path d={g.shade} fill="#0b0e12" fillOpacity="0.62" />}
    </svg>
  )
}
