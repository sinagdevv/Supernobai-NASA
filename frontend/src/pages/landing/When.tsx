import { useMotionValueEvent, useReducedMotion, useScroll } from 'motion/react'
import { useEffect, useMemo, useRef, memo } from 'react'
import { ChapterText, Plate, Swatch, useBox, useMedia } from '../../components/landing/kit'
import { ProfileRibbons, type SunApi } from '../../components/ProfileFigure'
import { DEFAULT_MISSION } from '../../data/mission'
import { siteById, shortName } from '../../data/sites'
import { plateLayout } from '../../lib/profiles'
import { dayWindows, fmtMin, sunAt } from '../../lib/solar'

/*
 * Chapter 02 · WHEN. One instrument: a day of sun elevation above, the terrain it lights below.
 * Scrolling raises the sun along the real curve of the prototype's simplified solar model; the amber band is the lunar reference
 * elevation range; the terrain's shadows are recomputed from the same elevation. Pinned on large screens, in flow elsewhere.
 */

const SITE = siteById('craters-of-the-moon')!
const DATE = '2026-12-14'
const { elMin: LO, elMax: HI, minDuration } = DEFAULT_MISSION
const TOP_EL = 26, BOT_EL = -5, EL0 = -2.2
const REST_EL = 2.4

const MODEL = (() => {
  const pts = Array.from({ length: 361 }, (_, i) => ({ m: i * 4, el: sunAt(SITE, DATE, i * 4).el }))
  const rise = pts.find((q) => q.el > 0)!.m
  const peakI = pts.reduce((b, q, i) => (q.el > pts[b].el ? i : b), 0)
  const span = { a: rise - 40, b: rise + 290 }
  const day = dayWindows(SITE, DATE, LO, HI, minDuration)
  return { pts: pts.filter((q) => q.m >= span.a && q.m <= span.b), span, peak: pts[peakI], segs: day.segments, minutes: day.minutes }
})()

/** Scroll position → sun elevation, slowed through the low band where the story is. */
const elOf = (p: number) => EL0 + (MODEL.peak.el - EL0) * Math.pow(p, 1.8)
/** Elevation on the morning branch → local minute (linear interpolation). */
const minuteOf = (el: number) => {
  const up = MODEL.pts.filter((q) => q.m <= MODEL.peak.m)
  for (let i = 1; i < up.length; i++) if (up[i].el >= el) { const f = (el - up[i - 1].el) / Math.max(1e-6, up[i].el - up[i - 1].el); return up[i - 1].m + f * (up[i].m - up[i - 1].m) }
  return el <= up[0].el ? up[0].m : MODEL.peak.m
}

function Instrument({ progress, still }: { progress: ReturnType<typeof useScroll>['scrollYProgress']; still: boolean }) {
  const [ref, box] = useBox<HTMLDivElement>()
  const sun: SunApi = useRef(null)
  const parts = useRef<{ dot: SVGCircleElement | null; drop: SVGLineElement | null; read: SVGTextElement | null }>({ dot: null, drop: null, read: null })

  const g = useMemo(() => {
    if (!box.w) return null
    const ctH = Math.round(box.h * 0.44)
    const padL = 48, padR = 30, padT = 38, padB = 30
    const X = (m: number) => padL + ((m - MODEL.span.a) / (MODEL.span.b - MODEL.span.a)) * (box.w - padL - padR)
    const Y = (el: number) => padT + ((TOP_EL - el) / (TOP_EL - BOT_EL)) * (ctH - padT - padB)
    const path = (from: number, to: number) => MODEL.pts.filter((q) => q.m >= from && q.m <= to).map((q, i) => `${i ? 'L' : 'M'}${X(q.m).toFixed(1)} ${Y(q.el).toFixed(1)}`).join('')
    const ticks: number[] = []
    // One label per hour when there is room for it, per two hours on a phone.
    const step = box.w < 480 ? 120 : 60
    for (let m = Math.ceil(MODEL.span.a / step) * step; m <= MODEL.span.b; m += step) ticks.push(m)
    return { ctH, X, Y, path, ticks, padB, L: plateLayout(box.w, box.h - ctH) }
  }, [box.w, box.h])

  const setEl = (el: number) => {
    if (!g) return
    sun.current?.(el)
    const m = minuteOf(el), x = g.X(m), y = g.Y(Math.max(el, BOT_EL))
    const p = parts.current
    p.dot?.setAttribute('cx', String(x)); p.dot?.setAttribute('cy', String(y))
    p.drop?.setAttribute('x1', String(x)); p.drop?.setAttribute('x2', String(x)); p.drop?.setAttribute('y1', String(y)); p.drop?.setAttribute('y2', String(g.ctH - g.padB))
    const inBand = el >= LO && el <= HI
    if (p.read) {
      p.read.textContent = `${fmtMin(m)}  ·  ${el < 0 ? 'Sun below the horizon' : `Sun ${el.toFixed(1)}°`}  ·  ${el < LO ? 'before the band' : inBand ? 'inside the band' : 'above the band'}`
      p.read.setAttribute('fill', inBand ? 'var(--color-amber)' : 'var(--color-silver-300)')
    }
    p.dot?.setAttribute('fill', inBand ? 'var(--color-amber)' : 'var(--color-paper)')
  }
  useMotionValueEvent(progress, 'change', (v) => { if (!still) setEl(elOf(Math.max(0, Math.min(1, v)))) })
  useEffect(() => { setEl(still ? REST_EL : elOf(Math.max(0, Math.min(1, progress.get())))) })

  const seg0 = MODEL.segs[0]
  return (
    <Plate
      label="Sun elevation through a morning, with the lunar reference band and the terrain it lights (schematic, illustrative)"
      bar={<><Swatch color="var(--color-silver-300)">Sun elevation</Swatch><Swatch color="var(--color-amber)">Lunar reference band {LO}–{HI}°</Swatch><span className="mono ml-auto hidden text-[12px] text-silver-400 sm:inline">{shortName(SITE)} · 14 Dec 2026</span></>}
      foot={<>Simplified solar model, illustrative.{seg0 ? ` In band ${fmtMin(seg0.startMin)}–${fmtMin(seg0.endMin)} (${MODEL.minutes} min that day).` : ''}</>}
    >
      <div ref={ref} className="relative h-[460px] w-full sm:h-[520px] lg:h-[min(520px,calc(100svh-16rem))] lg:min-h-[420px]">
        {g && (
          <svg viewBox={`0 0 ${box.w} ${box.h}`} width={box.w} height={box.h} aria-hidden className="absolute inset-0 block">
            {/* Sky: elevation against local time */}
            <g fontSize="12.5" style={{ fontFamily: 'var(--font-mono)' }} fill="var(--color-silver-400)">
              <rect x="48" width={box.w - 78} y={g.Y(HI)} height={g.Y(LO) - g.Y(HI)} fill="var(--color-amber)" fillOpacity="0.2" />
              <line x1="48" x2={box.w - 30} y1={g.Y(0)} y2={g.Y(0)} stroke="var(--color-silver-500)" strokeWidth="1" />
              <text x="40" y={g.Y(0) + 4} textAnchor="end">0°</text>
              <text x="40" y={g.Y(20) + 4} textAnchor="end">20°</text>
              <line x1="48" x2={box.w - 30} y1={g.Y(20)} y2={g.Y(20)} stroke="var(--line)" strokeWidth="1" />
              {g.ticks.map((m) => (
                <g key={m}>
                  <line x1={g.X(m)} x2={g.X(m)} y1={g.ctH - g.padB} y2={g.ctH - g.padB + 4} stroke="var(--color-silver-500)" />
                  <text x={g.X(m)} y={g.ctH - 8} textAnchor="middle">{fmtMin(m)}</text>
                </g>
              ))}
            </g>
            <path d={g.path(MODEL.span.a, MODEL.span.b)} fill="none" stroke="var(--color-silver-300)" strokeWidth="1.6" strokeLinejoin="round" />
            {MODEL.segs.map((s, i) => <path key={i} d={g.path(s.startMin, s.endMin)} fill="none" stroke="var(--color-amber)" strokeWidth="4.5" strokeLinecap="round" />)}
            <line ref={(el) => { parts.current.drop = el }} stroke="var(--color-paper)" strokeOpacity="0.4" strokeDasharray="2 3" />
            <circle ref={(el) => { parts.current.dot = el }} r="6" stroke="#0c0f13" strokeWidth="2" fill="var(--color-paper)" />
            <text ref={(el) => { parts.current.read = el }} x="16" y="26" fontSize="14" fontWeight="500" style={{ fontFamily: 'var(--font-sans)' }} />

            {/* Ground: the same two profiles as the hero, lit by that elevation */}
            <line x1="0" x2={box.w} y1={g.ctH} y2={g.ctH} stroke="var(--line)" />
            <g transform={`translate(0 ${g.ctH})`}>
              <ProfileRibbons L={g.L} el={REST_EL} apiRef={sun} ray />
            </g>
          </svg>
        )}
      </div>
    </Plate>
  )
}

function WhenSection({ pinned }: { pinned: boolean }) {
  const reduce = !!useReducedMotion()
  const wrap = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: wrap, offset: pinned ? ['start start', 'end end'] : ['start 75%', 'end 45%'] })
  return (
    <section ref={wrap} id="when" aria-labelledby="when-title" className={pinned ? 'h-[250vh] border-t border-[var(--line)]' : 'scroll-mt-14 border-t border-[var(--line)] py-16 md:py-24'}>
      <div className={pinned ? 'sticky top-14 flex h-[calc(100svh-3.5rem)] items-center' : ''}>
        <div className="mx-auto grid w-full max-w-[1680px] gap-x-12 gap-y-8 px-4 *:min-w-0 md:px-8 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-4">
            <ChapterText id="when-title" n="02" q="When to test" title="Find the days the sun is right.">
              A few degrees of sun is a few minutes of an Earth morning. {reduce ? 'The figure shows the sun inside the band.' : 'Keep scrolling: the sun rises through the band and the shadows pull back.'}
            </ChapterText>
          </div>
          <div className="lg:col-span-8">
            <Instrument progress={scrollYProgress} still={reduce} />
          </div>
        </div>
      </div>
    </section>
  )
}

function When() {
  // The pin exists only to scrub the sun with scroll; without that motion it would be a screen and a half of nothing.
  const roomy = useMedia('(min-width: 1024px) and (min-height: 640px)')
  const reduce = useReducedMotion()
  const pinned = roomy && !reduce
  return <WhenSection key={String(pinned)} pinned={pinned} />
}

export default memo(When)
