import { useCallback, useLayoutEffect, useRef, type MutableRefObject } from 'react'
import { band, runs, shade, type Layout } from '../lib/profiles'

export type SunApi = MutableRefObject<((elDeg: number) => void) | null>

/**
 * The lunar ribbon, the amber window and the Earth analog ribbon, with the sun's shadows dimming the stretches
 * that fall in shade. Shading is applied imperatively (setSun) so pointer/scroll-driven changes never re-render React.
 * `ray` adds the sun and a dashed grazing ray drawn at the very angle used to compute the shadows.
 * Render inside an <svg> whose viewBox matches the Layout's pixel size.
 */
export function ProfileRibbons({ L, el, apiRef, shadeColor = '#0b0e12', earthOpacity = 1, ray, rayOpacity = 1, bandOpacity = 1 }: { L: Layout; el: number; apiRef?: SunApi; shadeColor?: string; earthOpacity?: number; ray?: boolean; rayOpacity?: number; bandOpacity?: number }) {
  const shL = useRef<SVGPathElement>(null)
  const shE = useRef<SVGPathElement>(null)
  const rayLine = useRef<SVGLineElement>(null)
  const rayText = useRef<SVGTextElement>(null)
  const [E0, E1, E2, E3] = L.E
  const sunX = L.x0 + 18
  const sunY = Math.min(...E0) - 64

  const setSun = useCallback(
    (e: number) => {
      const make = (mask: boolean[], top: number[], bot: number[]) => runs(mask).map(([a, b]) => band(L.xs, top, bot, a, b)).join('')
      shL.current?.setAttribute('d', make(shade(L.hL, L.dx, e), E0, E1))
      shE.current?.setAttribute('d', make(shade(L.hE, L.dx, e), E2, E3))
      if (ray) {
        const run = L.x1 - sunX
        rayLine.current?.setAttribute('x2', String(L.x1))
        rayLine.current?.setAttribute('y2', String(sunY + run * Math.tan((e * Math.PI) / 180)))
        if (rayText.current) rayText.current.textContent = `Sun ${e.toFixed(1)}°`
      }
    },
    [L, E0, E1, E2, E3, ray, sunX, sunY],
  )

  useLayoutEffect(() => {
    setSun(el)
    if (apiRef) apiRef.current = setSun
  }, [setSun, el, apiRef])

  return (
    <g>
      <g style={{ opacity: bandOpacity }}>
      <path d={band(L.xs, E0, E1)} fill="var(--color-silver-300)" />
      <path ref={shL} fill={shadeColor} fillOpacity="0.68" />
      <g style={{ opacity: earthOpacity, transition: 'opacity 240ms var(--ease-out)' }}>
        <path d={band(L.xs, E1, E2)} fill="var(--color-amber)" />
        <path d={band(L.xs, E2, E3)} fill="var(--color-cyan)" />
        <path ref={shE} fill={shadeColor} fillOpacity="0.68" />
      </g>
      </g>
      {ray && (
        <g style={{ opacity: rayOpacity, transition: 'opacity 420ms var(--ease-out)' }}>
          <line ref={rayLine} x1={sunX} y1={sunY} x2={L.x1} y2={sunY} stroke="var(--color-amber)" strokeWidth="1" strokeDasharray="3 5" vectorEffect="non-scaling-stroke" strokeOpacity="0.85" />
          <circle cx={sunX} cy={sunY} r="5" fill="var(--color-amber)" />
          <circle cx={sunX} cy={sunY} r="11" fill="none" stroke="var(--color-amber)" strokeOpacity="0.28" />
          <text ref={rayText} x={sunX + 16} y={sunY - 12} fill="var(--color-amber)" fontSize="13" style={{ fontFamily: 'var(--font-mono)' }}>Sun 2.4°</text>
        </g>
      )}
    </g>
  )
}
