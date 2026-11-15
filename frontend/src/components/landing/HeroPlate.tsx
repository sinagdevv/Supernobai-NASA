import { animate, useMotionValue, useMotionValueEvent, useReducedMotion, useSpring } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CELL_M, lerpTerrain, N, plateLayout, terrain, type Terrain } from '../../lib/profiles'
import { PLANET_COPY, usePlanet, type Planet } from '../../lib/planet'
import { ProfileRibbons, type MorphApi, type SunApi } from '../ProfileFigure'
import { Plate, Swatch, useBox, useFinePointer, useOnScreen } from './kit'

/** The intro measures this element so its terrain can unfold into exactly this drawing. */
export const PLATE_ATTR = 'data-plate-svg'
/** Resting sun in the figure. The lunar value is the south-polar grazing sun; Mars gets a plainly illustrative higher one (no Mars lighting model exists here). */
export const REST_EL: Record<Planet, number> = { moon: 2.4, mars: 12 }
const EASE_OUT = [0.23, 1, 0.32, 1] as const

/** Slope in degrees over a 20 m baseline at sample i, read off the drawn (schematic) profile. */
const slopeAt = (edge: number[], k: number, i: number) => {
  const a = Math.max(0, i - 1), b = Math.min(N - 1, i + 1)
  return (Math.atan(Math.abs(edge[b] - edge[a]) / k / ((b - a) * CELL_M)) * 180) / Math.PI
}

/**
 * Hero figure: a reference ribbon (Moon or Mars), the amber comparison window, and an Earth analog ribbon, framed as one observation window.
 * On a fine pointer, moving across it scrubs the local slope of both profiles; height lowers or raises the sun and the shadows follow.
 * Switching planet deforms the same ribbons in place (terrain, colour and sun together); it can be interrupted by another switch.
 * `ribbons` and `chrome` are separate so the intro can hand its own (identical) ribbons over before the labels arrive.
 */
export function HeroPlate({ ribbons, chrome }: { ribbons: boolean; chrome: boolean }) {
  const fine = useFinePointer()
  const reduce = useReducedMotion()
  const { planet } = usePlanet()
  const copy = PLANET_COPY[planet]
  const [boxRef, box] = useBox<HTMLDivElement>()
  const onScreen = useOnScreen(boxRef, '120px')
  // `shown` is the planet the ribbons were last laid out for; it trails `planet` only while a morph is running.
  const [shown, setShown] = useState(planet)
  const cur = useRef<Terrain>(terrain(planet))
  const L = useMemo(() => (box.w ? plateLayout(box.w, box.h, terrain(shown)) : null), [box.w, box.h, shown])
  const rest = useRef(REST_EL[planet])
  useEffect(() => { rest.current = REST_EL[planet] }, [planet])

  const sun: SunApi = useRef(null)
  const morph: MorphApi = useRef(null)
  const scrub = useRef<SVGGElement>(null)
  const parts = useRef<{ line: SVGLineElement | null; dm: SVGCircleElement | null; de: SVGCircleElement | null; tm: SVGTextElement | null; te: SVGTextElement | null }>({ line: null, dm: null, de: null, tm: null, te: null })

  const elTarget = useMotionValue(REST_EL[planet])
  const elSpring = useSpring(elTarget, { stiffness: 150, damping: 24, mass: 0.7 })
  const xTarget = useMotionValue(0)
  const xSpring = useSpring(xTarget, { stiffness: 520, damping: 40, mass: 0.35 })
  useMotionValueEvent(elSpring, 'change', (v) => sun.current?.(v))
  useMotionValueEvent(xSpring, 'change', (x) => {
    if (!L) return
    const p = parts.current
    const i = Math.max(0, Math.min(N - 1, Math.round(x / L.dx)))
    const px = L.xs[i]
    p.line?.setAttribute('x1', String(px)); p.line?.setAttribute('x2', String(px))
    p.line?.setAttribute('y1', String(L.E[0][i] - 6)); p.line?.setAttribute('y2', String(L.E[3][i] + 6))
    p.dm?.setAttribute('cx', String(px)); p.dm?.setAttribute('cy', String(L.E[1][i]))
    p.de?.setAttribute('cx', String(px)); p.de?.setAttribute('cy', String(L.E[2][i]))
    const tx = String(Math.max(48, Math.min(L.x1 - 48, px)))
    if (p.tm) { p.tm.setAttribute('x', tx); p.tm.setAttribute('y', String(L.E[0][i] - 12)); p.tm.textContent = `${copy.label} ${slopeAt(L.E[1], L.k, i).toFixed(0)}°` }
    if (p.te) { p.te.setAttribute('x', tx); p.te.setAttribute('y', String(L.E[3][i] + 24)); p.te.textContent = `Earth ${slopeAt(L.E[2], L.k, i).toFixed(0)}°` }
  })

  // Planet switch: one eased deformation from wherever the drawing is now. Interrupting restarts from the current frame, never from the old target.
  useEffect(() => {
    const to = terrain(planet)
    // Compare with what is drawn now, not with `shown`: switching back to the planet last laid out, mid-morph, must still animate home.
    if (cur.current === to || !box.w) return
    const from = cur.current
    elTarget.set(REST_EL[planet])
    const a = animate(0, 1, {
      duration: reduce ? 0.01 : 0.6, ease: EASE_OUT,
      onUpdate: (t) => { cur.current = lerpTerrain(from, to, t); morph.current?.(plateLayout(box.w, box.h, cur.current)) },
      onComplete: () => { cur.current = to; setShown(planet) },
    })
    return () => a.stop()
  }, [planet, box.w, box.h, reduce, elTarget])

  // Pointer handling exists only while the figure is on screen, for a fine pointer, and is coalesced to one update per frame.
  useEffect(() => {
    const host = boxRef.current
    if (!host || !fine || !onScreen || !L) return
    let raf = 0
    const show = (v: boolean) => { if (scrub.current) scrub.current.style.opacity = v ? '1' : '0' }
    const move = (e: PointerEvent) => {
      if (e.pointerType === 'touch') return
      const cx = e.clientX, cy = e.clientY
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const r = host.getBoundingClientRect()
        const x = cx - r.left, y = cy - r.top
        xTarget.set(Math.max(0, Math.min(L.x1, x)))
        elTarget.set(1 + (1 - Math.max(0, Math.min(1, y / r.height))) * 8)
        show(true)
      })
    }
    const leave = () => { cancelAnimationFrame(raf); show(false); elTarget.set(rest.current) }
    host.addEventListener('pointermove', move, { passive: true })
    host.addEventListener('pointerleave', leave)
    return () => { host.removeEventListener('pointermove', move); host.removeEventListener('pointerleave', leave); cancelAnimationFrame(raf); leave() }
  }, [fine, onScreen, L, boxRef, elTarget, xTarget])

  const barY = box.h - 30
  const halo = { paintOrder: 'stroke' as const, stroke: '#0c0f13', strokeWidth: 5, strokeLinejoin: 'round' as const, fontFamily: 'var(--font-mono)' }

  return (
    <Plate
      shown={chrome}
      label={`Terrain comparison figure: a ${copy.reference.toLowerCase()} profile above an Earth analog profile, with the comparison window between them (schematic, illustrative)`}
      bar={
        <>
          <Swatch color="var(--planet-ref)">{copy.reference}</Swatch>
          <Swatch color="var(--color-amber)">Comparison window</Swatch>
          <Swatch color="var(--color-cyan)">Earth analog</Swatch>
          <span className="mono ml-auto hidden text-xs text-silver-400 sm:inline">Schematic · not survey data</span>
        </>
      }
      foot={fine ? <>Move across to read slope; height sets the sun.</> : <>Schematic profile, illustrative.</>}
    >
      <div ref={boxRef} {...{ [PLATE_ATTR]: '' }} className="relative aspect-[2/1] max-h-[520px] min-h-[300px] w-full touch-pan-y">
        {L && (
          <svg viewBox={`0 0 ${box.w} ${box.h}`} width={box.w} height={box.h} aria-hidden className="absolute inset-0 block">
            <defs>
              <radialGradient id="plate-sky" cx="0" cy="0.42" r="0.85">
                <stop offset="0" stopOpacity="0.13" style={{ stopColor: 'rgb(var(--planet-glow))', transition: 'stop-color 480ms var(--ease-out)' }} />
                <stop offset="1" stopOpacity="0" style={{ stopColor: 'rgb(var(--planet-glow))' }} />
              </radialGradient>
              <linearGradient id="plate-haze" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#c48060" stopOpacity="0" />
                <stop offset="0.55" stopColor="#c48060" stopOpacity="0.14" />
                <stop offset="1" stopColor="#c48060" stopOpacity="0" />
              </linearGradient>
            </defs>
            <rect width={box.w} height={box.h} fill="url(#plate-sky)" style={{ opacity: chrome ? 1 : 0, transition: 'opacity 700ms var(--ease-out)' }} />
            <rect x="0" y={L.yBase - box.h * 0.3} width={box.w} height={box.h * 0.46} fill="url(#plate-haze)" style={{ opacity: chrome && planet === 'mars' ? 1 : 0, transition: 'opacity 480ms var(--ease-out)' }} />
            <ProfileRibbons L={L} el={REST_EL[planet]} apiRef={sun} morphRef={morph} ray rayOpacity={chrome ? 1 : 0} bandOpacity={ribbons ? 1 : 0} refFill="var(--planet-ref)" sunLabel={copy.sunLabel} />

            <g ref={scrub} style={{ opacity: 0, transition: 'opacity 140ms var(--ease-out)' }}>
              <line ref={(el) => { parts.current.line = el }} stroke="var(--color-paper)" strokeOpacity="0.55" strokeWidth="1" strokeDasharray="2 3" />
              <circle ref={(el) => { parts.current.dm = el }} r="4" fill="var(--color-silver-200)" stroke="#0c0f13" strokeWidth="1.5" />
              <circle ref={(el) => { parts.current.de = el }} r="4" fill="var(--color-cyan)" stroke="#0c0f13" strokeWidth="1.5" />
              <text ref={(el) => { parts.current.tm = el }} textAnchor="middle" fontSize="13" fill="var(--color-silver-200)" style={halo} />
              <text ref={(el) => { parts.current.te = el }} textAnchor="middle" fontSize="13" fill="var(--color-cyan)" style={halo} />
            </g>

            {/* Scale bars: the figure is a measurement. 100 m across, 10 m up (drawn exaggerated). */}
            <g style={{ fontFamily: 'var(--font-mono)', opacity: chrome ? 1 : 0, transition: 'opacity 420ms var(--ease-out)' }} fontSize="12.5" fill="var(--color-silver-400)" stroke="none">
              <g stroke="var(--color-silver-400)" strokeWidth="1" fill="none">
                <path d={`M16 ${barY}H${16 + 10 * L.dx}M16 ${barY - 4}V${barY + 4}M${16 + 10 * L.dx} ${barY - 4}V${barY + 4}`} />
                <path d={`M${44 + 10 * L.dx} ${barY + 4}v${-10 * L.k}m-4 0h8m-8 ${10 * L.k}h8`} />
              </g>
              <text x="16" y={barY + 20}>100 m</text>
              <text x={58 + 10 * L.dx} y={barY + 4}>{`10 m (×${L.exag.toFixed(1)})`}</text>
            </g>
          </svg>
        )}
      </div>
    </Plate>
  )
}
