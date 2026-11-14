import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { Site } from '../../data/types'
import { sunAt, type Segment } from '../../lib/solar'

export interface TrackPt {
  m: number
  el: number
  az: number
}

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

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']

interface Props {
  site: Site
  date: string
  track: TrackPt[]
  segments: Segment[]
  lo: number
  hi: number
  sun: { el: number; az: number }
  mode: 'natural' | 'artificial'
  lampEl: number
  heading: number
  zoom: boolean
  smooth: boolean
  description: string
}

/** Altitude–azimuth plot of the sun's daily track with the lunar-reference elevation band. */
export function SolarPlot({ site, date, track, segments, lo, hi, sun, mode, lampEl, heading, zoom, smooth, description }: Props) {
  const [wrap, W] = useWidth()
  const clipId = useId()
  const narrow = W < 480
  const H = Math.round(Math.min(340, Math.max(230, W * 0.46)))
  const L = narrow ? 34 : 44
  const R = 12
  const T = 14
  const B = 26
  const pw = W - L - R
  const ph = H - T - B

  const maxEl = useMemo(() => Math.max(...track.map((p) => p.el)), [track])
  const yMin = zoom ? -3 : -10
  const yMax = zoom ? 12 : Math.max(20, Math.ceil((maxEl + 4) / 10) * 10)
  const x = (az: number) => L + (az / 360) * pw
  const y = (el: number) => T + ((yMax - el) / (yMax - yMin)) * ph

  const path = (pts: { az: number; el: number }[]) => {
    let d = ''
    let prev: { az: number } | null = null
    for (const p of pts) {
      d += !prev || Math.abs(p.az - prev.az) > 180 ? `M${x(p.az).toFixed(1)} ${y(p.el).toFixed(1)}` : `L${x(p.az).toFixed(1)} ${y(p.el).toFixed(1)}`
      prev = p
    }
    return d
  }

  const trackD = useMemo(() => path(track), [track, W, H, yMin, yMax]) // eslint-disable-line react-hooks/exhaustive-deps
  const segD = useMemo(
    () =>
      segments.map((s) => {
        const pts = []
        for (let m = s.startMin; m <= s.endMin; m += 5) pts.push(sunAt(site, date, Math.min(m, 1439)))
        return path(pts)
      }),
    [segments, site, date, W, H, yMin, yMax], // eslint-disable-line react-hooks/exhaustive-deps
  )

  const yStep = zoom ? 2 : yMax - yMin > 60 ? 20 : 10
  const yTicks: number[] = []
  for (let v = Math.ceil(yMin / yStep) * yStep; v <= yMax; v += yStep) yTicks.push(v)
  const xTickStep = narrow ? 2 : 1

  const markEl = mode === 'natural' ? sun.el : lampEl
  const markAz = mode === 'natural' ? sun.az : heading
  const clampedEl = Math.max(yMin, Math.min(yMax, markEl))
  const offScale = markEl !== clampedEl
  const bandTop = y(hi)
  const bandH = Math.max(2, y(lo) - y(hi))

  return (
    <div ref={wrap} className="w-full">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={description} className="block max-w-full overflow-visible">
        <defs>
          <clipPath id={clipId}>
            <rect x={L} y={T} width={pw} height={ph} />
          </clipPath>
        </defs>
        <rect x={L} y={T} width={pw} height={ph} fill="var(--color-ink-900)" stroke="var(--line)" strokeWidth="1" />
        <g clipPath={`url(#${clipId})`}>
          {/* below-horizon shade */}
          <rect x={L} y={y(0)} width={pw} height={Math.max(0, T + ph - y(0))} fill="var(--color-ink-950)" opacity="0.8" />
          {/* gridlines */}
          {yTicks.map((v) => (
            <line key={v} x1={L} x2={L + pw} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={v === 0 ? '' : '2 4'} />
          ))}
          {COMPASS.map((_, i) => (
            <line key={i} x1={x(i * 45)} x2={x(i * 45)} y1={T} y2={T + ph} stroke="var(--line)" strokeDasharray="2 4" />
          ))}
          {/* lunar reference band */}
          <rect x={L} y={bandTop} width={pw} height={bandH} fill="var(--color-amber)" opacity="0.2" />
          <line x1={L} x2={L + pw} y1={bandTop} y2={bandTop} stroke="var(--color-amber)" strokeDasharray="4 3" opacity="0.8" />
          <line x1={L} x2={L + pw} y1={bandTop + bandH} y2={bandTop + bandH} stroke="var(--color-amber)" strokeDasharray="4 3" opacity="0.8" />
          {/* daily track */}
          <path d={trackD} fill="none" stroke="var(--color-silver-400)" strokeWidth="1.5" opacity={mode === 'natural' ? 1 : 0.35} />
          {mode === 'natural' && segD.map((d, i) => <path key={i} d={d} fill="none" stroke="var(--color-amber)" strokeWidth="4.5" strokeLinecap="round" />)}
          {/* horizon */}
          <line x1={L} x2={L + pw} y1={y(0)} y2={y(0)} stroke="var(--color-silver-300)" strokeWidth="1.2" />
          {mode === 'artificial' && <line x1={L} x2={L + pw} y1={y(lampEl)} y2={y(lampEl)} stroke="var(--color-paper)" strokeWidth="1.5" strokeDasharray="7 5" />}
        </g>

        {/* labels */}
        <text x={L + 6} y={Math.max(T + 11, bandTop - 5)} className="mono" fontSize="12" fill="var(--color-amber)" stroke="var(--color-ink-900)" strokeWidth="3" paintOrder="stroke">
          Lunar reference band {lo}–{hi}°
        </text>
        <text x={L + pw - 6} y={Math.min(T + ph - 5, y(0) + 14)} textAnchor="end" className="mono" fontSize="12" fill="var(--color-silver-400)">
          Horizon 0°
        </text>
        {mode === 'artificial' && (
          <text x={L + pw - 6} y={Math.max(T + 11, y(lampEl) - 6)} textAnchor="end" className="mono" fontSize="12" fill="var(--color-paper)" stroke="var(--color-ink-900)" strokeWidth="3" paintOrder="stroke">
            Lamp elevation {lampEl}°
          </text>
        )}
        {yTicks.map((v) => (
          <text key={v} x={L - 6} y={y(v) + 3.5} textAnchor="end" className="mono" fontSize="12" fill="var(--color-silver-400)">
            {v}°
          </text>
        ))}
        {COMPASS.map((c, i) =>
          i % xTickStep === 0 ? (
            <text key={i} x={x(i * 45)} y={T + ph + 15} textAnchor={i === 0 ? 'start' : i === 8 ? 'end' : 'middle'} className="mono" fontSize="12" fill="var(--color-silver-300)">
              {c}
              {!narrow || i % 2 === 0 ? ` ${i * 45}°` : ''}
            </text>
          ) : null,
        )}

        {/* current light marker */}
        <g style={{ transform: `translate(${x(markAz)}px, ${y(clampedEl)}px)`, transition: smooth ? 'transform 220ms var(--ease-out)' : 'none' }} opacity={offScale ? 0.55 : 1}>
          {mode === 'natural' ? (
            <>
              <circle r="13" fill="var(--color-amber)" opacity="0.22" />
              <circle r="6.5" fill="var(--color-amber)" stroke="var(--color-ink-900)" strokeWidth="2" />
            </>
          ) : (
            <rect x="-6" y="-6" width="12" height="12" fill="var(--color-paper)" stroke="var(--color-ink-900)" strokeWidth="2" transform="rotate(45)" />
          )}
        </g>
      </svg>
    </div>
  )
}
