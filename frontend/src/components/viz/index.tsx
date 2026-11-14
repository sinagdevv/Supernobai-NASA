import { useMemo } from 'react'
import { ROUGH_SCALES, SLOPE_EDGES } from '../../data/mission'
import type { Site } from '../../data/types'
import { resolvable, rmsAt, shareBelow } from '../../lib/assess'
import { band, earthMeters, line, lunarMeters, N, runs, shade } from '../../lib/profiles'
import { dayWindows, sunAt } from '../../lib/solar'

/*
 * Small scientific graphics: each answers one question at a glance and carries a text alternative.
 * All values come from the local fixtures and are illustrative; nothing here is a measurement.
 */

/** Terrain profile of a site (or the lunar reference) as a filled ribbon; optionally shaded by a low sun. */
export function ProfileThumb({ seed = 0, kind = 'earth', w = 120, h = 40, sunEl, className, label }: { seed?: number; kind?: 'earth' | 'moon'; w?: number; h?: number; sunEl?: number; className?: string; label?: string }) {
  const d = useMemo(() => {
    const lm = lunarMeters()
    const sd = Math.abs(seed)
    // The lunar reference varies per region (scaled and shifted fixture relief) so thumbnails differ; the Earth profile uses its own variant.
    const m = kind === 'moon' ? lm.map((_, i) => lm[(i + (sd % 17) * 3) % lm.length] * (0.8 + (sd % 5) * 0.09)) : earthMeters(lm, (sd % 13) + 1)
    const min = Math.min(...m), max = Math.max(...m)
    const pad = 5, span = Math.max(max - min, 1)
    const xs = m.map((_, i) => (i / (N - 1)) * w)
    const y = m.map((v) => h - pad - ((v - min) / span) * (h - pad * 2 - 6))
    const T = Math.max(5, h * 0.16)
    const bottom = y.map((v) => v + T)
    const dx = w / (N - 1)
    const hs = m.map((v) => ((v - min) / span) * (h - pad * 2 - 6) * (100 / h)) // metres-ish scale, only for shading geometry
    const sh = sunEl ? runs(shade(hs, dx * (100 / h) * 3, sunEl)) : []
    return { top: line(xs, y), area: band(xs, y, bottom), shade: sh.map(([a, b]) => band(xs, y, bottom, a, b)).join('') }
  }, [seed, kind, w, h, sunEl])
  const c = kind === 'moon' ? 'var(--color-silver-300)' : 'var(--color-cyan)'
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={className} role="img" aria-label={label ?? (kind === 'moon' ? 'Lunar reference terrain profile (schematic)' : 'Terrain profile (schematic)')}>
      <path d={d.area} fill={c} fillOpacity="0.9" />
      {d.shade && <path d={d.shade} fill="#0b0e12" fillOpacity="0.62" />}
    </svg>
  )
}

/** Slope distribution as six bars; bins within the rover limit are solid, the rest recede; a tick marks the limit. */
export function SlopeSpark({ hist, limit, w = 72, h = 28, color = 'var(--color-cyan)', className }: { hist: number[]; limit: number; w?: number; h?: number; color?: string; className?: string }) {
  const max = Math.max(...hist), bw = w / hist.length
  const share = shareBelow(hist, limit)
  // x position of the limit across the bin axis (linear inside each bin)
  let lx = 0
  for (let i = 0; i < hist.length; i++) {
    const lo = SLOPE_EDGES[i], hi = SLOPE_EDGES[i + 1]
    if (limit >= hi) lx = (i + 1) * bw
    else if (limit > lo) lx = (i + (limit - lo) / (hi - lo)) * bw
  }
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} role="img" aria-label={`Slope distribution: ${share.toFixed(0)}% of area at or below ${limit}°`}>
      {hist.map((v, i) => {
        const bh = Math.max(1.5, (v / max) * (h - 4))
        const within = SLOPE_EDGES[i + 1] <= limit
        return <rect key={i} x={i * bw + 1} y={h - bh} width={bw - 2} height={bh} fill={color} fillOpacity={within ? 0.95 : 0.28} />
      })}
      <line x1={lx} x2={lx} y1="0" y2={h} stroke="var(--color-amber)" strokeWidth="1.5" />
    </svg>
  )
}

/** RMS roughness against analysis scale (log x). Scales below two grid cells are dashed (not resolvable). */
export function RoughSpark({ rough, resM, baseline, max, w = 72, h = 28, color = 'var(--color-cyan)', className }: { rough: { a: number; h: number }; resM: number; baseline: number; max: number; w?: number; h?: number; color?: string; className?: string }) {
  const lo = Math.log(ROUGH_SCALES[0]), hi = Math.log(ROUGH_SCALES[ROUGH_SCALES.length - 1])
  const vals = ROUGH_SCALES.map((L) => rmsAt(rough, L))
  const top = Math.max(max * 1.15, ...vals) || 1
  const X = (L: number) => ((Math.log(L) - lo) / (hi - lo)) * (w - 4) + 2
  const Y = (v: number) => h - 2 - (v / top) * (h - 4)
  const segs = ROUGH_SCALES.slice(1).map((L, i) => ({ d: `M${X(ROUGH_SCALES[i]).toFixed(1)} ${Y(vals[i]).toFixed(1)}L${X(L).toFixed(1)} ${Y(vals[i + 1]).toFixed(1)}`, ok: resolvable(resM, ROUGH_SCALES[i]) && resolvable(resM, L) }))
  const at = rmsAt(rough, baseline)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} role="img" aria-label={`Roughness ${at.toFixed(2)} m RMS at ${baseline} m baseline${resolvable(resM, baseline) ? '' : ' (below this dataset’s resolving power)'}; limit ${max.toFixed(1)} m`}>
      <line x1="0" x2={w} y1={Y(max)} y2={Y(max)} stroke="var(--color-amber)" strokeWidth="1" strokeDasharray="2 2" />
      {segs.map((s, i) => <path key={i} d={s.d} fill="none" stroke={color} strokeWidth="1.6" strokeOpacity={s.ok ? 1 : 0.4} strokeDasharray={s.ok ? undefined : '2 2'} />)}
      <circle cx={X(baseline)} cy={Y(at)} r="2.6" fill={resolvable(resM, baseline) ? color : 'none'} stroke={color} strokeWidth="1.2" />
    </svg>
  )
}

/** Sun elevation across one local day with the lunar-reference band and qualifying stretches in amber. */
export function SunArc({ site, date, lo, hi, minDur, minute, w = 160, h = 44, className }: { site: Site; date: string; lo: number; hi: number; minDur: number; minute?: number; w?: number; h?: number; className?: string }) {
  const g = useMemo(() => {
    const pts = Array.from({ length: 73 }, (_, i) => ({ m: i * 20, el: sunAt(site, date, i * 20).el }))
    const maxEl = Math.max(14, ...pts.map((p) => p.el)), minEl = -8
    const X = (m: number) => (m / 1440) * w
    const Y = (el: number) => h - 2 - ((el - minEl) / (maxEl - minEl)) * (h - 4)
    const day = dayWindows(site, date, lo, hi, minDur)
    return { X, Y, d: pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.m).toFixed(1)} ${Y(p.el).toFixed(1)}`).join(''), segs: day.segments, minutes: day.minutes }
  }, [site, date, lo, hi, minDur, w, h])
  const el = minute === undefined ? null : sunAt(site, date, minute).el
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} role="img" aria-label={`Sun elevation over ${date}: ${g.minutes ? `${g.minutes} minutes inside ${lo}–${hi}°` : 'no qualifying window'} (illustrative)`}>
      <rect x="0" y={g.Y(hi)} width={w} height={Math.max(1.5, g.Y(lo) - g.Y(hi))} fill="var(--color-amber)" fillOpacity="0.22" />
      <line x1="0" x2={w} y1={g.Y(0)} y2={g.Y(0)} stroke="var(--color-silver-500)" strokeWidth="0.8" />
      <path d={g.d} fill="none" stroke="var(--color-silver-300)" strokeWidth="1.3" />
      {g.segs.map((s, i) => <rect key={i} x={g.X(s.startMin)} y={g.Y(hi) - 1} width={Math.max(2, g.X(s.endMin) - g.X(s.startMin))} height={Math.max(3, g.Y(lo) - g.Y(hi) + 2)} fill="var(--color-amber)" />)}
      {el !== null && minute !== undefined && <circle cx={g.X(minute)} cy={g.Y(el)} r="3" fill="var(--color-paper)" />}
    </svg>
  )
}

/** Equirectangular locator: graticule and a dot. */
export function GeoDot({ lat, lon, w = 72, h = 36, className }: { lat: number; lon: number; w?: number; h?: number; className?: string }) {
  const x = ((lon + 180) / 360) * w, y = ((90 - lat) / 180) * h
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} role="img" aria-label={`Location ${Math.abs(lat).toFixed(1)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(1)}°${lon >= 0 ? 'E' : 'W'}`}>
      <rect width={w} height={h} fill="var(--color-ink-800)" />
      {[0.25, 0.5, 0.75].map((f) => <line key={'a' + f} x1="0" x2={w} y1={h * f} y2={h * f} stroke="var(--line)" strokeWidth="0.6" />)}
      {[0.25, 0.5, 0.75].map((f) => <line key={'b' + f} y1="0" y2={h} x1={w * f} x2={w * f} stroke="var(--line)" strokeWidth="0.6" />)}
      <circle cx={x} cy={y} r="5.5" fill="none" stroke="var(--color-amber)" strokeWidth="1" />
      <circle cx={x} cy={y} r="2.4" fill="var(--color-amber)" />
    </svg>
  )
}
