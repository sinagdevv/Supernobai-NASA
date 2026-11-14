import { useLayoutEffect, useRef, useState } from 'react'
import { ROUGH_SCALES, SLOPE_BINS, SLOPE_EDGES } from '../../data/mission'
import type { LunarRegion, Mission, Site } from '../../data/types'
import { rmsAt, shareBelow } from '../../lib/assess'
import { dayWindows } from '../../lib/solar'
import { SunArc } from '../viz'

/** Measure a container so SVG coordinates are real pixels and in-chart text stays 12 px at every width. */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [w, setW] = useState(300)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setW(Math.max(200, Math.round(el.clientWidth)))
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, Math.round(e.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

const T = { fontFamily: 'var(--font-mono)', fontSize: 12 } as const
const mute = 'var(--color-silver-400)'

/** Slope distribution of the reference region (% of area per bin) with the rover limit as an amber marker. */
export function SlopeChart({ region, m }: { region: LunarRegion; m: Mission }) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const H = 184, L = 34, R = 8, Tp = 24, B = 46
  const iw = W - L - R, ih = H - Tp - B, bw = iw / 6
  const maxY = Math.ceil(Math.max(...region.slopeHist) / 10) * 10
  const Y = (v: number) => Tp + ih - (v / maxY) * ih
  let lx = 0
  for (let i = 0; i < 6; i++) {
    const lo = SLOPE_EDGES[i], hi = SLOPE_EDGES[i + 1]
    if (m.slopeMax >= hi) lx = (i + 1) * bw
    else if (m.slopeMax > lo) lx = (i + (m.slopeMax - lo) / (hi - lo)) * bw
  }
  const share = shareBelow(region.slopeHist, m.slopeMax)
  return (
    <div ref={ref}>
      <p className="mono mb-1 text-[13px] text-silver-300"><span className="text-paper">{share.toFixed(0)}%</span> of the reference area is at or below {m.slopeMax}° · candidates need ≥ {m.minTraversable}%</p>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Slope distribution of ${region.name}, percent of area per slope bin: ${SLOPE_BINS.map((b, i) => `${b} ${region.slopeHist[i]}%`).join(', ')}. Rover cutoff marked at ${m.slopeMax} degrees. Illustrative.`}>
        {[0, maxY / 2, maxY].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="var(--line)" />
            <text x={L - 6} y={Y(v) + 4} textAnchor="end" fill={mute} style={T}>{v}</text>
          </g>
        ))}
        {region.slopeHist.map((v, i) => {
          const within = SLOPE_EDGES[i + 1] <= m.slopeMax
          return (
            <g key={i}>
              <rect x={L + i * bw + 4} y={Y(v)} width={bw - 8} height={Math.max(1, Tp + ih - Y(v))} fill="var(--color-silver-300)" fillOpacity={within ? 0.95 : 0.3} />
              <text x={L + i * bw + bw / 2} y={Y(v) - 5} textAnchor="middle" fill="var(--color-paper)" fillOpacity={within ? 1 : 0.6} style={T}>{v.toFixed(0)}</text>
              <text x={L + i * bw} y={H - 26} fill={mute} style={T}>{i === 5 ? '30+' : SLOPE_EDGES[i]}</text>
            </g>
          )
        })}
        <line x1={L + lx} x2={L + lx} y1={Tp - 8} y2={Tp + ih} stroke="var(--color-amber)" strokeWidth="2" />
        <text x={Math.min(L + lx + 5, W - 34)} y={Tp - 4} fill="var(--color-amber)" style={T}>{m.slopeMax}°</text>
        <text x={W - R} y={H - 4} textAnchor="end" fill={mute} style={T}>slope (°) · % of area</text>
      </svg>
    </div>
  )
}

/** RMS height vs analysis baseline (log x). Baselines under two grid cells of the required resolution are hatched. */
export function RoughChart({ region, m }: { region: LunarRegion; m: Mission }) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const H = 184, L = 42, R = 10, Tp = 16, B = 46
  const iw = W - L - R, ih = H - Tp - B
  const lo = Math.log(ROUGH_SCALES[0]), hi = Math.log(ROUGH_SCALES[ROUGH_SCALES.length - 1])
  const X = (s: number) => L + ((Math.log(Math.max(s, ROUGH_SCALES[0])) - lo) / (hi - lo)) * iw
  const vals = ROUGH_SCALES.map((s) => rmsAt(region.rough, s))
  const top = Math.ceil(Math.max(m.roughMax * 1.25, ...vals) * 2) / 2
  const Y = (v: number) => Tp + ih - (v / top) * ih
  const cut = 2 * m.maxDemRes
  const cutX = X(cut)
  const at = rmsAt(region.rough, m.roughBaseline)
  const unresolved = m.roughBaseline < cut
  return (
    <div ref={ref}>
      <p className="mono mb-1 text-[13px] text-silver-300">
        <span className="text-paper">{at.toFixed(2)} m</span> RMS at {m.roughBaseline} m (reference) · limit {m.roughMax.toFixed(1)} m
        {unresolved && <span className="text-amber"> · below 2 × {m.maxDemRes} m grid</span>}
      </p>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Roughness of ${region.name}: RMS height ${vals.map((v, i) => `${v.toFixed(2)} m at ${ROUGH_SCALES[i]} m`).join(', ')}. Cutoff ${m.roughMax.toFixed(1)} m; baseline ${m.roughBaseline} m. Baselines under ${cut} m are unresolvable at the required ${m.maxDemRes} m grid. Illustrative.`}>
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-silver-500)" strokeOpacity="0.5" /></pattern>
        </defs>
        {[0, top / 2, top].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="var(--line)" />
            <text x={L - 6} y={Y(v) + 4} textAnchor="end" fill={mute} style={T}>{v.toFixed(1)}</text>
          </g>
        ))}
        {cutX > L + 1 && <rect x={L} y={Tp} width={Math.min(cutX, W - R) - L} height={ih} fill="url(#hatch)" />}
        {ROUGH_SCALES.map((s) => <text key={s} x={X(s)} y={H - 26} textAnchor="middle" fill={mute} style={T}>{s}</text>)}
        <line x1={L} x2={W - R} y1={Y(m.roughMax)} y2={Y(m.roughMax)} stroke="var(--color-amber)" strokeDasharray="4 3" strokeWidth="1.5" />
        <path d={ROUGH_SCALES.map((s, i) => `${i ? 'L' : 'M'}${X(s).toFixed(1)} ${Y(vals[i]).toFixed(1)}`).join('')} fill="none" stroke="var(--color-silver-300)" strokeWidth="2" />
        {ROUGH_SCALES.map((s, i) => <circle key={s} cx={X(s)} cy={Y(vals[i])} r="2.5" fill="var(--color-silver-300)" />)}
        <line x1={X(m.roughBaseline)} x2={X(m.roughBaseline)} y1={Tp} y2={Tp + ih} stroke="var(--color-paper)" strokeOpacity="0.55" />
        <circle cx={X(m.roughBaseline)} cy={Y(at)} r="5" fill="none" stroke="var(--color-paper)" strokeWidth="2" />
        <text x={W - R} y={H - 4} textAnchor="end" fill={mute} style={T}>baseline (m) · RMS height (m)</text>
      </svg>
    </div>
  )
}

/** Horizon diagram: the sun-elevation band the Earth site must reproduce, on a 0–10° scale. */
export function HorizonDiagram({ m, site, date }: { m: Mission; site?: Site; date: string }) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const H = 120, L = 34, R = 44, g = 26
  const y0 = H - g
  const Y = (el: number) => y0 - (el / 10) * (y0 - 10)
  const minutes = site ? dayWindows(site, date, m.elMin, m.elMax, m.minDuration).minutes : 0
  return (
    <div ref={ref}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Lunar-reference sun elevation band from ${m.elMin.toFixed(1)} to ${m.elMax.toFixed(1)} degrees above the horizon, on a 0 to 10 degree scale.`}>
        {[0, 5, 10].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke={v === 0 ? 'var(--color-silver-400)' : 'var(--line)'} />
            <text x={L - 6} y={Y(v) + 4} textAnchor="end" fill={mute} style={T}>{v}°</text>
          </g>
        ))}
        <rect x={L} y={Y(m.elMax)} width={W - R - L} height={Math.max(2, Y(m.elMin) - Y(m.elMax))} fill="var(--color-amber)" fillOpacity="0.22" />
        <line x1={L} x2={W - R} y1={Y(m.elMax)} y2={Y(m.elMax)} stroke="var(--color-amber)" strokeWidth="1.5" />
        <line x1={L} x2={W - R} y1={Y(m.elMin)} y2={Y(m.elMin)} stroke="var(--color-amber)" strokeWidth="1.5" />
        <text x={W - R + 6} y={Y(m.elMax) + 4} fill="var(--color-amber)" style={T}>{m.elMax.toFixed(1)}°</text>
        <text x={W - R + 6} y={Math.max(Y(m.elMin) + 4, Y(m.elMax) + 18)} fill="var(--color-amber)" style={T}>{m.elMin.toFixed(1)}°</text>
        <rect x={L} y={y0} width={W - R - L} height={g} fill="var(--color-ink-700)" />
        <circle cx={L + 22} cy={(Y(m.elMin) + Y(m.elMax)) / 2} r="5" fill="var(--color-paper)" />
        <text x={W - R} y={H - 8} textAnchor="end" fill={mute} style={T}>elevation above horizon</text>
      </svg>
      {site && (
        <div className="mt-3">
          <SunArc site={site} date={date} lo={m.elMin} hi={m.elMax} minDur={m.minDuration} w={W} h={56} className="block w-full" />
          <p className="mono mt-1 text-[12px] text-silver-400">{site.name.split(' ').slice(0, 3).join(' ')} · {date} · {minutes ? `${minutes} min in band` : 'no window'}</p>
        </div>
      )}
    </div>
  )
}
