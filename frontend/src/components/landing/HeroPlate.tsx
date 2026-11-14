import { useMotionValue, useMotionValueEvent, useSpring } from 'motion/react'
import { useEffect, useMemo, useRef } from 'react'
import { CELL_M, N, plateLayout } from '../../lib/profiles'
import { ProfileRibbons, type SunApi } from '../ProfileFigure'
import { Plate, Swatch, useBox, useFinePointer, useOnScreen } from './kit'

/** The intro measures this element so its terrain can unfold into exactly this drawing. */
export const PLATE_ATTR = 'data-plate-svg'
const REST_EL = 2.4

/** Slope in degrees over a 20 m baseline at sample i, read off the drawn (schematic) profile. */
const slopeAt = (edge: number[], k: number, i: number) => {
  const a = Math.max(0, i - 1), b = Math.min(N - 1, i + 1)
  return (Math.atan(Math.abs(edge[b] - edge[a]) / k / ((b - a) * CELL_M)) * 180) / Math.PI
}

/**
 * Hero figure: a lunar reference ribbon, the amber comparison window, and an Earth analog ribbon, framed as one observation window.
 * On a fine pointer, moving across it scrubs the local slope of both profiles; height lowers or raises the sun and the shadows follow.
 * `ribbons` and `chrome` are separate so the intro can hand its own (identical) ribbons over before the labels arrive.
 */
export function HeroPlate({ ribbons, chrome }: { ribbons: boolean; chrome: boolean }) {
  const fine = useFinePointer()
  const [boxRef, box] = useBox<HTMLDivElement>()
  const onScreen = useOnScreen(boxRef, '120px')
  const L = useMemo(() => (box.w ? plateLayout(box.w, box.h) : null), [box.w, box.h])

  const sun: SunApi = useRef(null)
  const scrub = useRef<SVGGElement>(null)
  const parts = useRef<{ line: SVGLineElement | null; dm: SVGCircleElement | null; de: SVGCircleElement | null; tm: SVGTextElement | null; te: SVGTextElement | null }>({ line: null, dm: null, de: null, tm: null, te: null })

  const elTarget = useMotionValue(REST_EL)
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
    if (p.tm) { p.tm.setAttribute('x', tx); p.tm.setAttribute('y', String(L.E[0][i] - 12)); p.tm.textContent = `Moon ${slopeAt(L.E[1], L.k, i).toFixed(0)}°` }
    if (p.te) { p.te.setAttribute('x', tx); p.te.setAttribute('y', String(L.E[3][i] + 24)); p.te.textContent = `Earth ${slopeAt(L.E[2], L.k, i).toFixed(0)}°` }
  })

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
    const leave = () => { cancelAnimationFrame(raf); show(false); elTarget.set(REST_EL) }
    host.addEventListener('pointermove', move, { passive: true })
    host.addEventListener('pointerleave', leave)
    return () => { host.removeEventListener('pointermove', move); host.removeEventListener('pointerleave', leave); cancelAnimationFrame(raf); leave() }
  }, [fine, onScreen, L, boxRef, elTarget, xTarget])

  const barY = box.h - 30
  const halo = { paintOrder: 'stroke' as const, stroke: '#0c0f13', strokeWidth: 5, strokeLinejoin: 'round' as const, fontFamily: 'var(--font-mono)' }

  return (
    <Plate
      shown={chrome}
      label="Terrain comparison figure: a lunar reference profile above an Earth analog profile, with the comparison window between them (schematic, illustrative)"
      bar={
        <>
          <Swatch color="var(--color-silver-300)">Lunar reference</Swatch>
          <Swatch color="var(--color-amber)">Comparison window</Swatch>
          <Swatch color="var(--color-cyan)">Earth analog</Swatch>
          <span className="mono ml-auto hidden text-[12px] text-silver-400 sm:inline">1.1 km transect</span>
        </>
      }
      foot={<>Schematic profiles, illustrative; not survey data.{fine && <span className="text-silver-300"> Move across to scrub slope; height sets the sun.</span>}</>}
    >
      <div ref={boxRef} {...{ [PLATE_ATTR]: '' }} className="relative aspect-[2/1] max-h-[520px] min-h-[300px] w-full touch-pan-y">
        {L && (
          <svg viewBox={`0 0 ${box.w} ${box.h}`} width={box.w} height={box.h} aria-hidden className="absolute inset-0 block">
            <defs>
              <radialGradient id="plate-sky" cx="0" cy="0.42" r="0.85">
                <stop offset="0" stopColor="#e4a95b" stopOpacity="0.13" />
                <stop offset="1" stopColor="#e4a95b" stopOpacity="0" />
              </radialGradient>
            </defs>
            <rect width={box.w} height={box.h} fill="url(#plate-sky)" style={{ opacity: chrome ? 1 : 0, transition: 'opacity 700ms var(--ease-out)' }} />
            <ProfileRibbons L={L} el={REST_EL} apiRef={sun} ray rayOpacity={chrome ? 1 : 0} bandOpacity={ribbons ? 1 : 0} />

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
