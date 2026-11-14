import { useCallback, useLayoutEffect, useRef, type MutableRefObject } from 'react'
import { band, runs, shade, type Layout } from '../lib/profiles'

export type SunApi = MutableRefObject<((elDeg: number) => void) | null>
/** Redraws the whole figure for another layout (same size, different terrain) without re-rendering React: the planet morph. */
export type MorphApi = MutableRefObject<((L: Layout) => void) | null>

/**
 * The reference ribbon, the amber window and the Earth analog ribbon, with the sun's shadows dimming the stretches
 * that fall in shade. Every path is written imperatively (draw), so pointer-, scroll- and morph-driven changes never re-render React.
 * `ray` adds the sun and a dashed grazing ray drawn at the very angle used to compute the shadows.
 * Render inside an <svg> whose viewBox matches the Layout's pixel size.
 */
export function ProfileRibbons({ L, el, apiRef, morphRef, shadeColor = '#0b0e12', earthOpacity = 1, ray, rayOpacity = 1, bandOpacity = 1, refFill = 'var(--color-silver-300)', sunLabel = 'Sun' }: { L: Layout; el: number; apiRef?: SunApi; morphRef?: MorphApi; shadeColor?: string; earthOpacity?: number; ray?: boolean; rayOpacity?: number; bandOpacity?: number; refFill?: string; sunLabel?: string }) {
  const up = useRef<SVGPathElement>(null)
  const ch = useRef<SVGPathElement>(null)
  const lo = useRef<SVGPathElement>(null)
  const shL = useRef<SVGPathElement>(null)
  const shE = useRef<SVGPathElement>(null)
  const rayLine = useRef<SVGLineElement>(null)
  const rayText = useRef<SVGTextElement>(null)
  const dot = useRef<SVGCircleElement>(null)
  const ring = useRef<SVGCircleElement>(null)
  const cur = useRef(L)
  const elNow = useRef(el)
  const sunX = L.x0 + 18

  const draw = useCallback(
    (Lx: Layout, e: number) => {
      const [E0, E1, E2, E3] = Lx.E
      const make = (mask: boolean[], top: number[], bot: number[]) => runs(mask).map(([a, b]) => band(Lx.xs, top, bot, a, b)).join('')
      up.current?.setAttribute('d', band(Lx.xs, E0, E1))
      ch.current?.setAttribute('d', band(Lx.xs, E1, E2))
      lo.current?.setAttribute('d', band(Lx.xs, E2, E3))
      shL.current?.setAttribute('d', make(shade(Lx.hL, Lx.dx, e), E0, E1))
      shE.current?.setAttribute('d', make(shade(Lx.hE, Lx.dx, e), E2, E3))
      if (ray) {
        const sunY = Math.min(...E0) - 64
        const run = Lx.x1 - sunX
        rayLine.current?.setAttribute('y1', String(sunY))
        rayLine.current?.setAttribute('x2', String(Lx.x1))
        rayLine.current?.setAttribute('y2', String(sunY + run * Math.tan((e * Math.PI) / 180)))
        for (const c of [dot.current, ring.current]) c?.setAttribute('cy', String(sunY))
        if (rayText.current) { rayText.current.setAttribute('y', String(sunY - 12)); rayText.current.textContent = `${sunLabel} ${e.toFixed(1)}°` }
      }
    },
    [ray, sunX, sunLabel],
  )

  useLayoutEffect(() => {
    cur.current = L
    elNow.current = el
    draw(L, el)
    if (apiRef) apiRef.current = (e) => { elNow.current = e; draw(cur.current, e) }
    if (morphRef) morphRef.current = (Lx) => { cur.current = Lx; draw(Lx, elNow.current) }
  }, [L, el, draw, apiRef, morphRef])

  return (
    <g>
      <g style={{ opacity: bandOpacity }}>
        <path ref={up} style={{ fill: refFill, transition: 'fill 480ms var(--ease-out)' }} />
        <path ref={shL} fill={shadeColor} fillOpacity="0.68" />
        <g style={{ opacity: earthOpacity, transition: 'opacity 240ms var(--ease-out)' }}>
          <path ref={ch} fill="var(--color-amber)" />
          <path ref={lo} fill="var(--color-cyan)" />
          <path ref={shE} fill={shadeColor} fillOpacity="0.68" />
        </g>
      </g>
      {ray && (
        <g style={{ opacity: rayOpacity, transition: 'opacity 420ms var(--ease-out)' }}>
          <line ref={rayLine} x1={sunX} x2={L.x1} stroke="var(--color-amber)" strokeWidth="1" strokeDasharray="3 5" vectorEffect="non-scaling-stroke" strokeOpacity="0.85" />
          <circle ref={dot} cx={sunX} r="5" fill="var(--color-amber)" />
          <circle ref={ring} cx={sunX} r="11" fill="none" stroke="var(--color-amber)" strokeOpacity="0.28" />
          <text ref={rayText} x={sunX + 16} fill="var(--color-amber)" fontSize="13" style={{ fontFamily: 'var(--font-mono)' }} />
        </g>
      )}
    </g>
  )
}
