import { animate, motion, useMotionValue, useReducedMotion, useTransform, type AnimationPlaybackControls } from 'motion/react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { WORDMARK_GLYPHS, WORDMARK_WIDTH } from '../brand/paths'
import { REF_COLOR, rgb, usePlanet, type Planet } from '../lib/planet'
import { band, edgesAt, lerp, lerpTerrain, line, markEdges, N, plateLayout, runs, shade, terrain } from '../lib/profiles'
import { PLATE_ATTR, REST_EL } from './landing/HeroPlate'

/*
 * PLANETARY ALIGNMENT (≈2.9 s, skippable at any moment)
 * 01 Lunar horizon  a horizon line draws; the relief rises under a grazing sun and the shadows pull back
 * 02 Mars           the same ribbon deforms, vertex by vertex, into a Martian landform (basin, mesa, dunes); its colour, sun and a thin
 *                   atmospheric haze change with it. Not a tint: the geometry is different.
 * 03 Earth          the Earth analog slides up beneath the reference of the SELECTED planet (the ribbon settles on it as the analog arrives)
 * 04 The window     the channel between them opens (amber) and the same vertices become the TERRAWINDOW mark; the wordmark resolves
 * 05 The product    the mark unfolds into the hero plate's exact geometry while a copy docks into the navigation.
 *                   The page is already underneath; nothing is replaced and nothing fades to a different scene.
 *
 * One paint() writes every path from a handful of motion values, so skipping from any frame continues from where the drawing is.
 */

const EASE_OUT = [0.23, 1, 0.32, 1] as const
const EASE_IO = [0.77, 0, 0.175, 1] as const
const INK = '#0b0e12'
const MARS_EL = 9 // sun elevation while Mars is on screen: an illustrative value, not a Mars lighting model
const SILVER = REF_COLOR.moon
const lerp3 = (a: number[], b: number[], t: number) => a.map((v, i) => lerp(v, b[i], t))
const sleep = (s: number) => new Promise<void>((r) => setTimeout(r, s * 1000))

type Edges = [number[], number[], number[], number[]]
interface Geo {
  w: number; h: number
  target: Planet
  F: { yBase: number; k: number; T: number; G: number }; Fxs: number[]
  M: { xs: number[]; M: Edges }
  P: { xs: number[]; E: Edges }
  markPx: number; cx: number; cy: number; dy0: number
}

/** The plate the intro unfolds into: measured from the DOM, then laid out with the very function the hero uses. */
let plateKey = '', plateCache: Geo['P'] | null = null
function plateGeo(w: number, h: number, planet: Planet): Geo['P'] {
  const el = document.querySelector<HTMLElement>(`[${PLATE_ATTR}]`)
  const r = el?.getBoundingClientRect()
  const pw = el?.clientWidth || Math.round(w * 0.55), ph = el?.clientHeight || 340
  // The browser snaps the plate's SVG box to whole pixels; the overlay must draw at that same snapped origin or every edge is off by a fraction.
  const ox = r ? Math.round(r.left) : w * 0.4, oy = r ? Math.round(r.top) : h * 0.3
  const key = `${planet}|${pw}|${ph}|${ox}|${oy}`
  if (key !== plateKey || !plateCache) {
    const pl = plateLayout(pw, ph, terrain(planet))
    plateCache = { xs: pl.xs.map((x) => x + ox), E: pl.E.map((e) => e.map((y) => y + oy)) as Edges }
    plateKey = key
  }
  return plateCache
}

/** `w`×`h` are the overlay's own pixel size (it excludes any scrollbar gutter), so its viewBox is exactly 1:1 with the screen. */
function measure(w: number, h: number, target: Planet): Geo {
  const P = plateGeo(w, h, target)
  // The cinematic frame: relief bleeds off both sides, so no end of the terrain is ever visible.
  const x0 = -w * 0.05, ww = w * 1.1
  const T = Math.max(22, Math.min(46, h * 0.05))
  const F = { yBase: h * 0.6, k: Math.max(2.4, (h * 0.17) / 30), T, G: T * 0.55 }
  const Fxs = Array.from({ length: N }, (_, i) => x0 + (i * ww) / (N - 1))
  const markPx = Math.max(150, Math.min(240, w * 0.3))
  const cx = w / 2, cy = h * 0.42
  return { w, h, target, F, Fxs, M: markEdges(cx, cy, markPx), P, markPx, cx, cy, dy0: h * 0.17 }
}

type Props = { onDone: () => void; onDock: () => void }

export function Intro({ onDone, onDock }: Props) {
  const reduce = useReducedMotion()
  const { planet } = usePlanet()
  const [geo, setGeo] = useState<Geo | null>(null)
  const geoRef = useRef<Geo | null>(null)
  const rootEl = useRef<HTMLDivElement>(null)

  const drawL = useMotionValue(0), drawE = useMotionValue(0)
  const mix = useMotionValue(0) // 0 = lunar relief, 1 = Martian
  const labMoon = useMotionValue(0), labMars = useMotionValue(0), labEarth = useMotionValue(0) // scene captions: opacity only
  const ampL = useMotionValue(0), ampE = useMotionValue(0), dyE = useMotionValue(0)
  const fillL = useMotionValue(0), fillE = useMotionValue(0), chan = useMotionValue(0)
  const light = useMotionValue(0.35)
  const toMark = useMotionValue(0), toPlate = useMotionValue(0)
  const dolly = useMotionValue(1.06)
  const glow = useMotionValue(0.5)
  const bg = useMotionValue(1), rootOp = useMotionValue(1)
  const wordW = useMotionValue(0), tag = useMotionValue(0)
  const dock = useMotionValue(0), fly = useMotionValue(0)
  const glowOp = useTransform([glow, bg], ([g, b]: number[]) => g * b)
  const moonGlow = useTransform([glowOp, mix], ([g, m]: number[]) => g * (1 - m))
  const marsGlow = useTransform([glowOp, mix], ([g, m]: number[]) => g * m)
  const haze = useTransform([glowOp, mix], ([g, m]: number[]) => g * m)

  // The SVG nodes paint() writes to, collected from `data-k` attributes once they exist (never read during render).
  const nodes = useRef<Record<string, SVGElement>>({})
  const svgEl = useRef<SVGSVGElement>(null)
  const finished = useRef(false), docking = useRef(false), frozen = useRef(false) // frozen: dev QA only
  const controls = useRef<AnimationPlaybackControls[]>([])
  const target = useRef({ tx: 0, ty: 0, sc: 0.12 })

  const run = useCallback((c: AnimationPlaybackControls) => { if (frozen.current) c.stop(); else controls.current.push(c); return c }, [])
  const stopAll = useCallback(() => { controls.current.forEach((c) => c.stop()); controls.current = [] }, [])
  const finish = useCallback(() => {
    if (finished.current) return
    finished.current = true
    onDone()
  }, [onDone])

  /* ── paint: every path, from the current motion values ── */
  const paint = useCallback(() => {
    const g = geoRef.current
    if (!g) return
    const a = toMark.get(), b = toPlate.get()
    // Fonts and images can still move the hero after the intro measured it; while unfolding, follow the real plate so the last frame is exact.
    if (b > 0) g.P = plateGeo(g.w, g.h, g.target)
    const m = mix.get()
    const T = lerpTerrain(terrain('moon'), terrain('mars'), m)
    const Ef = edgesAt(T.lm, T.em, g.F, ampL.get(), ampE.get(), dyE.get())
    const xs = g.Fxs.map((x, i) => lerp(lerp(x, g.M.xs[i], a), g.P.xs[i], b))
    const E = Ef.map((arr, k) => arr.map((y, i) => lerp(lerp(y, g.M.M[k][i], a), g.P.E[k][i], b))) as Edges
    const r = nodes.current
    const set = (k: string, name: string, v: string) => r[k]?.setAttribute(name, v)
    const op = (k: string, v: number) => { const el = r[k]; if (el) el.style.opacity = String(v) }

    // The reference ribbon is the planet's colour, silver while it is the brand mark, and the selected planet's colour again once it is the hero's ribbon.
    const ref = rgb(lerp3(lerp3(lerp3(REF_COLOR.moon, REF_COLOR.mars, m), SILVER, a), REF_COLOR[g.target], b))
    set('upper', 'd', band(xs, E[0], E[1])); op('upper', fillL.get()); set('upper', 'fill', ref); set('lineL', 'stroke', ref)
    set('chan', 'd', band(xs, E[1], E[2])); op('chan', chan.get())
    set('lower', 'd', band(xs, E[2], E[3])); op('lower', fillE.get())
    const dl = line(xs, E[1]), de = line(xs, E[2])
    set('lineL', 'd', dl); set('lineE', 'd', de)
    set('lineL', 'stroke-dashoffset', String(1 - drawL.get())); set('lineE', 'stroke-dashoffset', String(1 - drawE.get()))
    op('lineL', 1 - fillL.get()); op('lineE', 1 - fillE.get())

    // Shadows are computed from the drawing as it is now, so they always agree with the geometry (and with the hero's, at the end).
    const so = 1 - a + a * b
    if (so > 0.01) {
      const dx = (xs[N - 1] - xs[0]) / (N - 1), el = lerp(light.get(), REST_EL[g.target], b)
      const mk = (top: number[], bot: number[]) => runs(shade(bot.map((y) => -y), dx, el)).map(([i, j]) => band(xs, top, bot, i, j)).join('')
      set('shL', 'd', mk(E[0], E[1])); set('shE', 'd', mk(E[2], E[3]))
    }
    op('shL', so * fillL.get()); op('shE', so * fillE.get())

    const s = dolly.get()
    r.cam?.setAttribute('transform', s === 1 ? '' : `translate(${g.cx} ${g.F.yBase}) scale(${s}) translate(${-g.cx} ${-g.F.yBase})`)
  }, [mix, ampE, ampL, chan, drawE, drawL, dyE, fillE, fillL, light, dolly, toMark, toPlate])

  // Measure once, before the first paint: the intro and the hero must agree on one geometry. Lock the page behind the intro.
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
    const ov = rootEl.current
    const g = measure(ov?.clientWidth ?? window.innerWidth, ov?.clientHeight ?? window.innerHeight, planet)
    geoRef.current = g
    dyE.set(g.dy0)
    setGeo(g)
    // Dev builds only: lets QA freeze the sequence and inspect or compare any state.
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__twIntro = { done: () => finish(), dock: () => onDock(), stop: () => { frozen.current = true; controls.current.forEach((c) => c.stop()); controls.current = [] }, set: (k: string, v: number) => ({ labMoon, labMars, labEarth, mix, drawL, drawE, ampL, ampE, dyE, fillL, fillE, chan, light, toMark, toPlate, dolly, glow, bg, dock, fly, wordW, tag, rootOp } as Record<string, { set: (n: number) => void }>)[k]?.set(v) }
    // Lock the page behind the intro; paint the root in the intro's ink so a reserved scrollbar gutter matches it.
    const root = document.documentElement
    const prev = { overflow: root.style.overflow, background: root.style.background }
    root.style.overflow = 'hidden'
    root.style.background = INK
    return () => { root.style.overflow = prev.overflow; root.style.background = prev.background }
    // the dev hook closes over stable motion values and callbacks; the intro measures once, for the planet selected when it started
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dyE])
  useLayoutEffect(() => {
    if (!geo) return
    nodes.current = {}
    svgEl.current?.querySelectorAll<SVGElement>('[data-k]').forEach((el) => { nodes.current[el.dataset.k!] = el })
    paint()
  }, [geo, paint])

  useEffect(() => {
    let raf = 0
    const sched = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; paint() }) }
    const off = [mix, drawL, drawE, ampL, ampE, dyE, fillL, fillE, chan, light, toMark, toPlate, dolly].map((m) => m.on('change', sched))
    return () => { off.forEach((f) => f()); cancelAnimationFrame(raf) }
  }, [paint, mix, drawL, drawE, ampL, ampE, dyE, fillL, fillE, chan, light, toMark, toPlate, dolly])

  const markStatic = useMemo(() => {
    if (!geo) return ['', '', '']
    const poly = (i: number, j: number) => {
      let d = ''
      for (let n = 0; n < N; n++) d += `${n ? 'L' : 'M'}${geo.M.xs[n].toFixed(1)} ${geo.M.M[i][n].toFixed(1)}`
      for (let n = N - 1; n >= 0; n--) d += `L${geo.M.xs[n].toFixed(1)} ${geo.M.M[j][n].toFixed(1)}`
      return d + 'Z'
    }
    return [poly(0, 1), poly(1, 2), poly(2, 3)]
  }, [geo])

  const groupTransform = useTransform(dock, (d) => `translate(${target.current.tx * d}px, ${target.current.ty * d}px) scale(${lerp(1, target.current.sc, d)})`)
  const wordOpacity = useTransform(dock, [0, 0.5], [1, 0])
  const skipOpacity = useTransform(dock, [0, 0.4], [1, 0])

  /** Unfold into the hero plate and dock a copy of the mark into the navigation. From any current state. */
  const dockNow = useCallback(async (mode: 'full' | 'fast' | 'reduced') => {
    const g = geoRef.current
    if (docking.current || !g || frozen.current) return
    docking.current = true
    stopAll()
    onDock()
    if (mode === 'reduced') {
      await run(animate(rootOp, 0, { duration: 0.25, ease: 'easeOut' }))
      finish()
      return
    }
    const nav = document.querySelector('[data-nav-mark]')?.getBoundingClientRect()
    if (nav) target.current = { tx: nav.left + nav.width / 2 - g.cx, ty: nav.top + nav.height / 2 - g.cy, sc: nav.width / g.markPx }
    fly.set(toMark.get() > 0.5 ? 1 : 0)
    // A skip is the user asking for the page: no start delay and the shortest unfold that still reads as motion.
    const d = mode === 'fast' ? 0.26 : 0.5
    // Bring every part of the drawing to its final state while it unfolds, so the last frame equals the hero exactly.
    for (const mv of [fillL, fillE, chan, drawL, drawE]) run(animate(mv, 1, { duration: d, ease: EASE_OUT }))
    run(animate(light, REST_EL[g.target], { duration: d, ease: EASE_OUT }))
    run(animate(mix, g.target === 'mars' ? 1 : 0, { duration: d, ease: EASE_OUT }))
    for (const mv of [labMoon, labMars, labEarth]) run(animate(mv, 0, { duration: d * 0.5, ease: EASE_OUT }))
    run(animate(dolly, 1, { duration: d, ease: EASE_OUT }))
    run(animate(glow, 0, { duration: d, ease: EASE_OUT }))
    run(animate(bg, 0, { duration: d * 0.8, ease: EASE_OUT }))
    // The copy of the mark leaves first and quickly, so the unfolding ribbons never read as a second mark.
    run(animate(dock, 1, { duration: d * 0.78, ease: EASE_OUT }))
    await run(animate(toPlate, 1, { duration: d, delay: mode === 'fast' ? 0 : 0.06, ease: EASE_IO }))
    finish()
  }, [bg, chan, dock, dolly, drawE, drawL, fillE, fillL, finish, fly, glow, labEarth, labMars, labMoon, light, mix, onDock, rootOp, run, stopAll, toMark, toPlate])

  const skip = useCallback(() => { if (!finished.current && !docking.current) void dockNow(reduce ? 'reduced' : 'fast') }, [dockNow, reduce])

  useEffect(() => {
    if (!geo) return
    let live = true
    const seq = async () => {
      const want = geoRef.current?.target ?? 'moon'
      if (reduce) {
        for (const mv of [fillL, fillE, chan, ampL, ampE, drawL, drawE, toMark, tag]) mv.set(1)
        dyE.set(0); dolly.set(1); glow.set(1); light.set(REST_EL[want]); mix.set(want === 'mars' ? 1 : 0); wordW.set(WORDMARK_WIDTH + 4)
        await sleep(0.45)
        if (live) void dockNow('reduced')
        return
      }
      // 01 Lunar horizon
      run(animate(drawL, 1, { duration: 0.45, ease: EASE_OUT }))
      run(animate(labMoon, 1, { duration: 0.3, delay: 0.22, ease: 'easeOut' }))
      run(animate(glow, 1, { duration: 0.7, ease: 'easeOut' }))
      run(animate(dolly, 1, { duration: 1.4, ease: EASE_OUT }))
      await sleep(0.12); if (!live) return
      run(animate(ampL, 1, { duration: 0.5, ease: EASE_OUT }))
      run(animate(fillL, 1, { duration: 0.35, delay: 0.08, ease: 'easeOut' }))
      run(animate(light, REST_EL.moon, { duration: 0.6, ease: EASE_OUT }))
      await sleep(0.38); if (!live) return
      // 02 Mars: the same vertices, a different landform
      run(animate(mix, 1, { duration: 0.5, ease: EASE_IO }))
      run(animate(light, MARS_EL, { duration: 0.5, ease: EASE_IO }))
      run(animate(labMoon, 0, { duration: 0.2, ease: 'easeOut' }))
      run(animate(labMars, 1, { duration: 0.3, delay: 0.2, ease: 'easeOut' }))
      await sleep(0.62); if (!live) return
      // 03 Earth arrives beneath the selected planet's reference
      run(animate(drawE, 1, { duration: 0.35, ease: EASE_OUT }))
      run(animate(labMars, 0, { duration: 0.2, ease: 'easeOut' }))
      run(animate(labEarth, 1, { duration: 0.3, delay: 0.15, ease: 'easeOut' }))
      run(animate(ampE, 1, { duration: 0.45, ease: EASE_OUT }))
      run(animate(dyE, 0, { duration: 0.5, ease: EASE_IO }))
      run(animate(fillE, 1, { duration: 0.28, delay: 0.08, ease: 'easeOut' }))
      run(animate(mix, want === 'mars' ? 1 : 0, { duration: 0.5, delay: 0.08, ease: EASE_IO }))
      run(animate(light, REST_EL[want], { duration: 0.5, delay: 0.08, ease: EASE_IO }))
      await sleep(0.45); if (!live) return
      // 04 The window
      run(animate(chan, 1, { duration: 0.2, ease: 'easeOut' }))
      run(animate(labEarth, 0, { duration: 0.18, ease: 'easeOut' }))
      await sleep(0.05); if (!live) return
      run(animate(wordW, WORDMARK_WIDTH + 4, { duration: 0.32, delay: 0.25, ease: EASE_OUT }))
      run(animate(tag, 1, { duration: 0.28, delay: 0.36, ease: 'easeOut' }))
      await run(animate(toMark, 1, { duration: 0.45, ease: EASE_IO }))
      await sleep(0.06); if (!live) return
      // 05 Into the product
      await dockNow('full')
    }
    void seq()
    const key = (e: KeyboardEvent) => { if (e.key !== 'Tab' && !e.metaKey && !e.ctrlKey && !e.altKey) skip() }
    window.addEventListener('keydown', key)
    return () => { live = false; window.removeEventListener('keydown', key); stopAll() }
    // runs once the geometry exists; the sequence reads stable motion values
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo])

  const markPx = geo?.markPx ?? 180, cx = geo?.cx ?? 0, cy = geo?.cy ?? 0
  const wmScale = (markPx * 1.5) / WORDMARK_WIDTH
  const wmX = cx - (markPx * 1.5) / 2
  const wmY = cy + markPx * 0.5 + 34

  return (
    <motion.div ref={rootEl} role="dialog" aria-label="TERRAWINDOW introduction" aria-modal="false" onPointerDown={skip} className="fixed inset-0 z-[200] cursor-pointer" style={{ opacity: rootOp }}>
      <motion.div aria-hidden className="absolute inset-0" style={{ background: INK, opacity: bg }} />
      {/* A low sun at the left horizon: the only atmosphere */}
      <motion.div aria-hidden className="absolute inset-0" style={{ opacity: moonGlow, background: 'radial-gradient(85% 58% at 6% 64%, rgb(228 169 91 / 0.17), transparent 64%)' }} />
      {/* Mars: a lower, wider warm light and a thin dusty haze above the horizon (the Moon has neither). */}
      <motion.div aria-hidden className="absolute inset-0" style={{ opacity: marsGlow, background: 'radial-gradient(95% 60% at 8% 62%, rgb(214 120 78 / 0.2), transparent 66%)' }} />
      <motion.div aria-hidden className="absolute inset-x-0" style={{ opacity: haze, top: '28%', height: '34%', background: 'linear-gradient(to top, transparent, rgb(196 128 96 / 0.13) 45%, transparent)' }} />
      {geo && (
        <svg ref={svgEl} viewBox={`0 0 ${geo.w} ${geo.h}`} className="absolute inset-0 h-full w-full" aria-hidden>
          <g data-k="cam">
            <path data-k="upper" fill="var(--color-silver-300)" />
            <path data-k="shL" fill={INK} fillOpacity="0.68" />
            <path data-k="chan" fill="var(--color-amber)" />
            <path data-k="lower" fill="var(--color-cyan)" />
            <path data-k="shE" fill={INK} fillOpacity="0.68" />
            <path data-k="lineL" fill="none" stroke="var(--color-silver-300)" strokeWidth="1.5" pathLength={1} strokeDasharray="1" strokeDashoffset="1" />
            <path data-k="lineE" fill="none" stroke="var(--color-cyan)" strokeWidth="1.5" pathLength={1} strokeDasharray="1" strokeDashoffset="1" />
          </g>

          {/* One caption per scene, in the room above the terrain. Opacity only; each hands over to the next. */}
          {([['MOON', labMoon, 'var(--color-silver-300)'], ['MARS', labMars, '#c9876a'], ['EARTH ANALOG', labEarth, 'var(--color-cyan)']] as const).map(([t, o, c]) => (
            <motion.text key={t} x={Math.max(20, geo.w * 0.04)} y={geo.h * 0.3} fill={c} fontSize="12" letterSpacing="0.16em" style={{ opacity: o, fontFamily: 'var(--font-mono)' }}>{t}</motion.text>
          ))}

          {/* The wordmark, and a copy of the finished mark that docks into the navigation */}
          <motion.g style={{ transform: groupTransform, transformOrigin: `${cx}px ${cy}px` }}>
            <motion.g style={{ opacity: fly }}>
              <path d={markStatic[0]} fill="var(--color-silver-300)" />
              <path d={markStatic[1]} fill="var(--color-amber)" />
              <path d={markStatic[2]} fill="var(--color-cyan)" />
            </motion.g>
            <motion.g style={{ opacity: wordOpacity }}>
              <defs>
                <clipPath id="intro-word">
                  <motion.rect x="-2" y="-2" height="14" width={wordW} />
                </clipPath>
              </defs>
              <g transform={`translate(${wmX} ${wmY}) scale(${wmScale})`}>
                <g fill="none" stroke="var(--color-paper)" strokeWidth="1.7" strokeLinejoin="miter" strokeMiterlimit="12" clipPath="url(#intro-word)" dangerouslySetInnerHTML={{ __html: WORDMARK_GLYPHS }} />
              </g>
              <motion.text x={cx} y={wmY + markPx * 0.36} textAnchor="middle" fill="var(--color-silver-400)" fontSize="14" letterSpacing="0.06em" style={{ opacity: tag, fontFamily: 'var(--font-sans)' }}>
                Where Earth becomes the proving ground.
              </motion.text>
            </motion.g>
          </motion.g>
        </svg>
      )}
      <motion.div style={{ opacity: skipOpacity }} className="absolute right-4 bottom-4">
        <button type="button" onClick={skip} className="min-h-11 rounded-md px-4 text-[13px] text-silver-400 transition-[color,transform] hover:text-paper active:scale-[0.97]">
          Skip
        </button>
      </motion.div>
    </motion.div>
  )
}

