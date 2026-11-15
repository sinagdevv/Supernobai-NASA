import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { RehearsalResult } from '../../lib/api/types'
import { CLASS_META, fmtDuration } from '../../lib/rehearsal'
import { cellPaint, ClassPatterns, CLASS_COLOR } from './classVis'

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(640)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))))
    ro.observe(node)
    setW(Math.max(260, node.clientWidth || 640))
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null)
const two = (n: number) => String(n).padStart(2, '0')
const hhmm = (t: number) => { const d = new Date(t); return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}` }
const mmdd = (t: number) => { const d = new Date(t); return `${two(d.getUTCMonth() + 1)}-${two(d.getUTCDate())}` }

/** The computed counterpart of the illustrative solar plot: real sun elevation over the span, what the engine decided at each sample, and the windows it found. */
export function ComputedTimeline({ r, sel }: { r: RehearsalResult; sel: number }) {
  const [wrap, W] = useWidth()
  const prefix = useId().replace(/:/g, '')
  const narrow = W < 480
  const L = narrow ? 36 : 46, R = 12, T = 12
  const plotH = Math.round(Math.min(190, Math.max(130, W * 0.26)))
  const stripY = T + plotH + 10, stripH = 26
  const winY = stripY + stripH + 8, winH = 10
  const axisY = winY + winH + 16
  const H = axisY + 6
  const pw = W - L - R

  const t0 = Date.parse(r.start_utc), t1 = Date.parse(r.end_utc)
  const x = (t: number) => L + ((t - t0) / (t1 - t0)) * pw
  const obs = r.observations
  const elMin = num(r.criteria.solar_elevation_min_deg), elMax = num(r.criteria.solar_elevation_max_deg)

  const dom = useMemo(() => {
    const els = obs.map((o) => o.solar_elevation_deg)
    const lo = Math.min(0, ...els, elMin ?? 0) - 1
    const hi = Math.max(5, ...els, (elMax ?? 0) + 1) + 1
    return { lo: Math.floor(lo), hi: Math.ceil(hi) }
  }, [obs, elMin, elMax])
  const y = (el: number) => T + ((dom.hi - el) / (dom.hi - dom.lo)) * plotH

  const line = obs.map((o, i) => `${i ? 'L' : 'M'}${x(Date.parse(o.time_utc)).toFixed(1)} ${y(o.solar_elevation_deg).toFixed(1)}`).join('')

  const span = t1 - t0
  const stepT = span <= 2 * 86_400_000 ? 6 * 3_600_000 : span <= 8 * 86_400_000 ? 86_400_000 : Math.ceil(span / 86_400_000 / 6) * 86_400_000
  const ticks: number[] = []
  for (let t = Math.ceil(t0 / stepT) * stepT; t <= t1; t += stepT) ticks.push(t)
  const yStep = dom.hi - dom.lo > 40 ? 20 : dom.hi - dom.lo > 16 ? 10 : dom.hi - dom.lo > 8 ? 4 : 2
  const yTicks: number[] = []
  for (let v = Math.ceil(dom.lo / yStep) * yStep; v <= dom.hi; v += yStep) yTicks.push(v)

  const so = obs[sel]
  const selX = so ? x(Date.parse(so.time_utc)) : null
  const label = `Computed sun elevation from ${hhmm(t0)} ${mmdd(t0)} to ${hhmm(t1)} ${mmdd(t1)} UTC, ${obs.length} samples, ranging from ${r.solar_elevation_min_deg.toFixed(1)} to ${r.solar_elevation_max_deg.toFixed(1)} degrees. ${r.candidate_windows.filter((w) => w.is_candidate !== false).length} candidate windows. Classification per sample is in the table below.`

  return (
    <div ref={wrap} className="w-full">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="block max-w-full overflow-visible">
        <ClassPatterns prefix={prefix} />
        <clipPath id={`${prefix}-clip`}><rect x={L} y={T} width={pw} height={plotH} /></clipPath>
        <rect x={L} y={T} width={pw} height={plotH} fill="var(--color-ink-900)" stroke="var(--line)" />
        <g clipPath={`url(#${prefix}-clip)`}>
          <rect x={L} y={y(0)} width={pw} height={Math.max(0, T + plotH - y(0))} fill="var(--color-ink-950)" opacity="0.8" />
          {yTicks.map((v) => <line key={v} x1={L} x2={L + pw} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={v === 0 ? '' : '2 4'} />)}
          {ticks.map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={T} y2={T + plotH} stroke="var(--line)" strokeDasharray="2 4" />)}
          {r.candidate_windows.filter((w) => w.is_candidate !== false).map((w) => (
            <rect key={w.start_utc} x={x(Date.parse(w.start_utc))} width={Math.max(2, x(Date.parse(w.end_utc)) - x(Date.parse(w.start_utc)))} y={T} height={plotH} fill="var(--color-amber)" opacity="0.1" />
          ))}
          {elMin !== null && elMax !== null && <>
            <rect x={L} y={y(elMax)} width={pw} height={Math.max(2, y(elMin) - y(elMax))} fill="var(--color-cyan)" opacity="0.14" />
            <line x1={L} x2={L + pw} y1={y(elMax)} y2={y(elMax)} stroke="var(--color-cyan)" strokeDasharray="4 3" opacity="0.7" />
            <line x1={L} x2={L + pw} y1={y(elMin)} y2={y(elMin)} stroke="var(--color-cyan)" strokeDasharray="4 3" opacity="0.7" />
          </>}
          <line x1={L} x2={L + pw} y1={y(0)} y2={y(0)} stroke="var(--color-silver-300)" strokeWidth="1.2" />
          <path d={line} fill="none" stroke="var(--color-silver-300)" strokeWidth="1.5" />
          {obs.map((o) => <circle key={o.time_utc} cx={x(Date.parse(o.time_utc))} cy={y(o.solar_elevation_deg)} r="3" fill={CLASS_COLOR[o.target_classification]} stroke="var(--color-ink-900)" strokeWidth="1" />)}
        </g>
        {elMin !== null && elMax !== null && (
          <text x={L + 6} y={Math.max(T + 11, y(elMax) - 5)} className="mono" fontSize="12" fill="var(--color-cyan)" stroke="var(--color-ink-900)" strokeWidth="3" paintOrder="stroke">Criteria band {elMin}–{elMax}°</text>
        )}
        {yTicks.map((v) => <text key={v} x={L - 6} y={y(v) + 3.5} textAnchor="end" className="mono" fontSize="12" fill="var(--color-silver-400)">{v}°</text>)}

        {/* One cell per sample, filled by what the engine decided. */}
        <text x={L - 6} y={stripY + stripH / 2 + 4} textAnchor="end" className="mono" fontSize="12" fill="var(--color-silver-400)">Target</text>
        {obs.map((o) => {
          const a = x(Date.parse(o.time_utc)), b = x(Date.parse(o.interval_end_utc))
          const p = cellPaint(o.target_classification, prefix)
          return <rect key={o.time_utc} x={a + 0.5} y={stripY} width={Math.max(1, b - a - 1)} height={stripH} fill={p.fill} stroke={p.stroke} strokeDasharray={p.strokeDasharray} strokeWidth="1" />
        })}

        {/* Candidate windows. */}
        <text x={L - 6} y={winY + winH - 1} textAnchor="end" className="mono" fontSize="12" fill="var(--color-silver-400)">Windows</text>
        <rect x={L} y={winY} width={pw} height={winH} fill="#fff" opacity="0.05" />
        {r.candidate_windows.filter((w) => w.is_candidate !== false).map((w) => (
          <rect key={w.start_utc} x={x(Date.parse(w.start_utc))} y={winY} width={Math.max(2, x(Date.parse(w.end_utc)) - x(Date.parse(w.start_utc)))} height={winH} rx="2" fill="var(--color-amber)"><title>{`Candidate window, ${fmtDuration(w.duration_seconds)}`}</title></rect>
        ))}

        {ticks.map((t, i) => (
          <text key={t} x={x(t)} y={axisY} textAnchor={i === 0 && x(t) - L < 20 ? 'start' : 'middle'} className="mono" fontSize="12" fill="var(--color-silver-300)">
            {stepT >= 86_400_000 ? mmdd(t) : new Date(t).getUTCHours() === 0 ? mmdd(t) : hhmm(t)}
          </text>
        ))}

        {selX !== null && <>
          <line x1={selX} x2={selX} y1={T} y2={winY + winH} stroke="var(--color-paper)" strokeWidth="1.5" />
          <circle cx={selX} cy={y(so.solar_elevation_deg)} r="6" fill="none" stroke="var(--color-paper)" strokeWidth="2" />
        </>}
      </svg>
      {so && <p className="sr-only" aria-live="polite">{`Selected sample ${so.time_utc}: ${CLASS_META[so.target_classification].label}, elevation ${so.solar_elevation_deg.toFixed(2)} degrees.`}</p>}
    </div>
  )
}

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']

/** The solar diagram from real samples: azimuth (N = 0°, clockwise) against elevation, each sample coloured by its classification. */
export function AzElTrack({ r, sel }: { r: RehearsalResult; sel: number }) {
  const [wrap, W] = useWidth()
  const narrow = W < 480
  const L = narrow ? 34 : 44, R = 12, T = 12, B = 26
  const H = Math.round(Math.min(300, Math.max(200, W * 0.4)))
  const pw = W - L - R, ph = H - T - B
  const obs = r.observations
  const elMin = num(r.criteria.solar_elevation_min_deg), elMax = num(r.criteria.solar_elevation_max_deg)
  const lo = Math.floor(Math.min(0, ...obs.map((o) => o.solar_elevation_deg), elMin ?? 0) - 1)
  const hi = Math.ceil(Math.max(5, ...obs.map((o) => o.solar_elevation_deg), (elMax ?? 0) + 1) + 1)
  const x = (az: number) => L + (az / 360) * pw
  const y = (el: number) => T + ((hi - el) / (hi - lo)) * ph
  const step = hi - lo > 40 ? 20 : hi - lo > 16 ? 10 : hi - lo > 8 ? 4 : 2
  const yTicks: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) yTicks.push(v)
  let d = ''
  obs.forEach((o, i) => { const prev = obs[i - 1]; d += !prev || Math.abs(o.solar_azimuth_deg - prev.solar_azimuth_deg) > 180 ? `M${x(o.solar_azimuth_deg).toFixed(1)} ${y(o.solar_elevation_deg).toFixed(1)}` : `L${x(o.solar_azimuth_deg).toFixed(1)} ${y(o.solar_elevation_deg).toFixed(1)}` })
  const so = obs[sel]
  const azLo = Math.min(...obs.map((o) => o.solar_azimuth_deg)), azHi = Math.max(...obs.map((o) => o.solar_azimuth_deg))
  const label = `Computed sun track: azimuth ${azLo.toFixed(0)} to ${azHi.toFixed(0)} degrees, elevation ${r.solar_elevation_min_deg.toFixed(1)} to ${r.solar_elevation_max_deg.toFixed(1)} degrees, over ${obs.length} samples.`
  return (
    <div ref={wrap} className="w-full">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="block max-w-full overflow-visible">
        <rect x={L} y={T} width={pw} height={ph} fill="var(--color-ink-900)" stroke="var(--line)" />
        <rect x={L} y={y(0)} width={pw} height={Math.max(0, T + ph - y(0))} fill="var(--color-ink-950)" opacity="0.8" />
        {yTicks.map((v) => <line key={v} x1={L} x2={L + pw} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={v === 0 ? '' : '2 4'} />)}
        {COMPASS.map((_, i) => <line key={i} x1={x(i * 45)} x2={x(i * 45)} y1={T} y2={T + ph} stroke="var(--line)" strokeDasharray="2 4" />)}
        {elMin !== null && elMax !== null && <rect x={L} y={y(elMax)} width={pw} height={Math.max(2, y(elMin) - y(elMax))} fill="var(--color-cyan)" opacity="0.14" />}
        <line x1={L} x2={L + pw} y1={y(0)} y2={y(0)} stroke="var(--color-silver-300)" strokeWidth="1.2" />
        <path d={d} fill="none" stroke="var(--color-silver-400)" strokeWidth="1.2" opacity="0.8" />
        {obs.map((o) => <circle key={o.time_utc} cx={x(o.solar_azimuth_deg)} cy={y(o.solar_elevation_deg)} r="3.2" fill={CLASS_COLOR[o.target_classification]} stroke="var(--color-ink-900)" strokeWidth="1" />)}
        {so && <circle cx={x(so.solar_azimuth_deg)} cy={y(so.solar_elevation_deg)} r="8" fill="none" stroke="var(--color-paper)" strokeWidth="2" />}
        {yTicks.map((v) => <text key={v} x={L - 6} y={y(v) + 3.5} textAnchor="end" className="mono" fontSize="12" fill="var(--color-silver-400)">{v}°</text>)}
        {COMPASS.map((c, i) => (i % (narrow ? 2 : 1) === 0 ? <text key={i} x={x(i * 45)} y={T + ph + 15} textAnchor={i === 0 ? 'start' : i === 8 ? 'end' : 'middle'} className="mono" fontSize="12" fill="var(--color-silver-300)">{c}{!narrow || i % 2 === 0 ? ` ${i * 45}°` : ''}</text> : null))}
      </svg>
    </div>
  )
}
