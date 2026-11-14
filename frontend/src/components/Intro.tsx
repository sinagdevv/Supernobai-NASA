import { animate, motion, useMotionValue, useReducedMotion, useTransform, type AnimationPlaybackControls } from 'motion/react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { WORDMARK_GLYPHS, WORDMARK_WIDTH } from '../brand/paths'
import { band, earthMeters, edgesAt, lerp, line, lunarMeters, markEdges, N, plateLayout, runs, shade } from '../lib/profiles'
import { PLATE_ATTR } from './landing/HeroPlate'

/*
 * PLANETARY ALIGNMENT (≈2.6 s, skippable at any moment)
 * 01 Darkness      a horizon line draws; the relief rises under a grazing sun and the shadows pull back
 * 02 Two worlds    the Earth analog slides up beneath the Moon's profile and settles into alignment
 * 03 The window    the channel between them opens (amber) and the same vertices become the TERRAWINDOW mark; the wordmark resolves
 * 04 The product   the mark unfolds into the hero plate's exact geometry while a copy docks into the navigation.
 *                  The page is already underneath; nothing is replaced and nothing fades to a different scene.
 *
 * One paint() writes every path from a handful of motion values, so skipping from any frame continues from where the drawing is.
 */

const EASE_OUT = [0.23, 1, 0.32, 1] as const
const EASE_IO = [0.77, 0, 0.175, 1] as const
const INK = '#0b0e12'
const REST_EL = 2.4
const sleep = (s: number) => new Promise<void>((r) => setTimeout(r, s * 1000))

type Edges = [number[], number[], number[], number[]]
interface Geo {
  w: number; h: number
  lm: number[]; em: number[]
  F: { yBase: number; k: number; T: number; G: number }; Fxs: number[]
  M: { xs: number[]; M: Edges }
  P: { xs: number[]; E: Edges }
  markPx: number; cx: number; cy: number; dy0: number
}

/** The plate the intro unfolds into: measured from the DOM, then laid out with the very function the hero uses. */
let plateKey = '', plateCache: Geo['P'] | null = null
function plateGeo(w: number, h: number): Geo['P'] {
  const el = document.querySelector<HTMLElement>(`[${PLATE_ATTR}]`)
  const r = el?.getBoundingClientRect()
  const pw = el?.clientWidth || Math.round(w * 0.55), ph = el?.clientHeight || 340
  const ox = r?.left ?? w * 0.4, oy = r?.top ?? h * 0.3
  const key = `${pw}|${ph}|${ox.toFixed(2)}|${oy.toFixed(2)}`
  if (key !== plateKey || !plateCache) {
    const pl = plateLayout(pw, ph)
    plateCache = { xs: pl.xs.map((x) => x + ox), E: pl.E.map((e) => e.map((y) => y + oy)) as Edges }
    plateKey = key
  }
  return plateCache
}

/** `w`×`h` are the overlay's own pixel size (it excludes any scrollbar gutter), so its viewBox is exactly 1:1 with the screen. */
function measure(w: number, h: number): Geo {
  const lm = lunarMeters(), em = earthMeters(lm)
  const P = plateGeo(w, h)
  // The cinematic frame: relief bleeds off both sides, so no end of the terrain is ever visible.
  const x0 = -w * 0.05, ww = w * 1.1
  const T = Math.max(22, Math.min(46, h * 0.05))
  const F = { yBase: h * 0.6, k: Math.max(2.4, (h * 0.17) / 30), T, G: T * 0.55 }
  const Fxs = lm.map((_, i) => x0 + (i * ww) / (N - 1))
  const markPx = Math.max(150, Math.min(240, w * 0.3))
  const cx = w / 2, cy = h * 0.42
  return { w, h, lm, em, F, Fxs, M: markEdges(cx, cy, markPx), P, markPx, cx, cy, dy0: h * 0.17 }
}

type Props = { onDone: () => void; onDock: () => void }

export function Intro({ onDone, onDock }: Props) {
  const reduce = useReducedMotion()
  const [geo, setGeo] = useState<Geo | null>(null)
  const geoRef = useRef<Geo | null>(null)
  const rootEl = useRef<HTMLDivElement>(null)

  const drawL = useMotionValue(0), drawE = useMotionValue(0)
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

  // The SVG nodes paint() writes to, collected from `data-k` attributes once they exist (never read during render).
  const nodes = useRef<Record<string, SVGElement>>({})
  const svgEl = useRef<SVGSVGElement>(null)
  const finished = useRef(false), docking = useRef(false)
  const controls = useRef<AnimationPlaybackControls[]>([])
  const target = useRef({ tx: 0, ty: 0, sc: 0.12 })

  const run = useCallback((c: AnimationPlaybackControls) => (controls.current.push(c), c), [])
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
    if (b > 0) g.P = plateGeo(g.w, g.h)
    const Ef = edgesAt(g.lm, g.em, g.F, ampL.get(), ampE.get(), dyE.get())
    const xs = g.Fxs.map((x, i) => lerp(lerp(x, g.M.xs[i], a), g.P.xs[i], b))
    const E = Ef.map((arr, k) => arr.map((y, i) => lerp(lerp(y, g.M.M[k][i], a), g.P.E[k][i], b))) as Edges
    const r = nodes.current
    const set = (k: string, name: string, v: string) => r[k]?.setAttribute(name, v)
    const op = (k: string, v: number) => { const el = r[k]; if (el) el.style.opacity = String(v) }

    set('upper', 'd', band(xs, E[0], E[1])); op('upper', fillL.get())
    set('chan', 'd', band(xs, E[1], E[2])); op('chan', chan.get())
    set('lower', 'd', band(xs, E[2], E[3])); op('lower', fillE.get())
    const dl = line(xs, E[1]), de = line(xs, E[2])
    set('lineL', 'd', dl); set('lineE', 'd', de)
    set('lineL', 'stroke-dashoffset', String(1 - drawL.get())); set('lineE', 'stroke-dashoffset', String(1 - drawE.get()))
    op('lineL', 1 - fillL.get()); op('lineE', 1 - fillE.get())

    // Shadows are computed from the drawing as it is now, so they always agree with the geometry (and with the hero's, at the end).
    const so = 1 - a + a * b
    if (so > 0.01) {
      const dx = (xs[N - 1] - xs[0]) / (N - 1), el = lerp(light.get(), REST_EL, b)
      const mk = (top: number[], bot: number[]) => runs(shade(bot.map((y) => -y), dx, el)).map(([i, j]) => band(xs, top, bot, i, j)).join('')
      set('shL', 'd', mk(E[0], E[1])); set('shE', 'd', mk(E[2], E[3]))
    }
    op('shL', so * fillL.get()); op('shE', so * fillE.get())

    const s = dolly.get()
    r.cam?.setAttribute('transform', s === 1 ? '' : `translate(${g.cx} ${g.F.yBase}) scale(${s}) translate(${-g.cx} ${-g.F.yBase})`)
  }, [ampE, ampL, chan, drawE, drawL, dyE, fillE, fillL, light, dolly, toMark, toPlate])

  // Measure once, before the first paint: the intro and the hero must agree on one geometry. Lock the page behind the intro.
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
    const ov = rootEl.current
    const g = measure(ov?.clientWidth ?? window.innerWidth, ov?.clientHeight ?? window.innerHeight)
    geoRef.current = g
    dyE.set(g.dy0)
    setGeo(g)
    // Dev builds only: lets QA freeze the sequence and inspect or compare any state.
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__twIntro = { done: () => finish(), dock: () => onDock(), stop: () => { controls.current.forEach((c) => c.stop()); controls.current = [] }, set: (k: string, v: number) => ({ drawL, drawE, ampL, ampE, dyE, fillL, fillE, chan, light, toMark, toPlate, dolly, glow, bg, dock, fly, wordW, tag, rootOp } as Record<string, { set: (n: number) => void }>)[k]?.set(v) }
    // Lock the page behind the intro; paint the root in the intro's ink so a reserved scrollbar gutter matches it.
    const root = document.documentElement
    const prev = { overflow: root.style.overflow, background: root.style.background }
    root.style.overflow = 'hidden'
    root.style.background = INK
    return () => { root.style.overflow = prev.overflow; root.style.background = prev.background }
    // the dev hook closes over stable motion values and callbacks
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
    const off = [drawL, drawE, ampL, ampE, dyE, fillL, fillE, chan, light, toMark, toPlate, dolly].map((m) => m.on('change', sched))
    return () => { off.forEach((f) => f()); cancelAnimationFrame(raf) }
  }, [paint, drawL, drawE, ampL, ampE, dyE, fillL, fillE, chan, light, toMark, toPlate, dolly])

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

  /** Unfold into the hero plate and dock a copy of the mark into the navigation. From any current state. */
  const dockNow = useCallback(async (mode: 'full' | 'fast' | 'reduced') => {
    const g = geoRef.current
    if (docking.current || !g) return
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
    const d = mode === 'fast' ? 0.34 : 0.56
    // Bring every part of the drawing to its final state while it unfolds, so the last frame equals the hero exactly.
    for (const mv of [fillL, fillE, chan, drawL, drawE]) run(animate(mv, 1, { duration: d, ease: EASE_OUT }))
    run(animate(light, REST_EL, { duration: d, ease: EASE_OUT }))
    run(animate(dolly, 1, { duration: d, ease: EASE_OUT }))
    run(animate(glow, 0, { duration: d, ease: EASE_OUT }))
    run(animate(bg, 0, { duration: d * 0.8, ease: EASE_OUT }))
    // The copy of the mark leaves first and quickly, so the unfolding ribbons never read as a second mark.
    run(animate(dock, 1, { duration: d * 0.78, ease: EASE_OUT }))
    await run(animate(toPlate, 1, { duration: d, delay: 0.06, ease: EASE_IO }))
    finish()
  }, [bg, chan, dock, dolly, drawE, drawL, fillE, fillL, finish, fly, glow, light, onDock, rootOp, run, stopAll, toMark, toPlate])

  const skip = useCallback(() => { if (!finished.current && !docking.current) void dockNow(reduce ? 'reduced' : 'fast') }, [dockNow, reduce])

  useEffect(() => {
    if (!geo) return
    let live = true
    const seq = async () => {
      if (reduce) {
        for (const mv of [fillL, fillE, chan, ampL, ampE, drawL, drawE, toMark, tag]) mv.set(1)
        dyE.set(0); dolly.set(1); glow.set(1); light.set(REST_EL); wordW.set(WORDMARK_WIDTH + 4)
        await sleep(0.45)
        if (live) void dockNow('reduced')
        return
      }
      // 01 Darkness and discovery
      run(animate(drawL, 1, { duration: 0.55, ease: EASE_OUT }))
      run(animate(glow, 1, { duration: 0.9, ease: 'easeOut' }))
      run(animate(dolly, 1, { duration: 1.75, ease: EASE_OUT }))
      await sleep(0.2); if (!live) return
      run(animate(ampL, 1, { duration: 0.65, ease: EASE_OUT }))
      run(animate(fillL, 1, { duration: 0.45, delay: 0.12, ease: 'easeOut' }))
      run(animate(light, REST_EL, { duration: 1, ease: EASE_OUT }))
      await sleep(0.4); if (!live) return
      // 02 The two worlds
      run(animate(drawE, 1, { duration: 0.5, ease: EASE_OUT }))
      run(animate(ampE, 1, { duration: 0.6, ease: EASE_OUT }))
      run(animate(dyE, 0, { duration: 0.65, ease: EASE_IO }))
      run(animate(fillE, 1, { duration: 0.35, delay: 0.15, ease: 'easeOut' }))
      await sleep(0.45); if (!live) return
      // 03 The window
      run(animate(chan, 1, { duration: 0.22, ease: 'easeOut' }))
      await sleep(0.08); if (!live) return
      run(animate(wordW, WORDMARK_WIDTH + 4, { duration: 0.4, delay: 0.4, ease: EASE_OUT }))
      run(animate(tag, 1, { duration: 0.3, delay: 0.54, ease: 'easeOut' }))
      await run(animate(toMark, 1, { duration: 0.55, ease: EASE_IO }))
      await sleep(0.12); if (!live) return
      // 04 Into the product
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
    <motion.div ref={rootEl} role="dialog" aria-label="TERRAWINDOW introduction" aria-modal="false" onClick={skip} className="fixed inset-0 z-[200] cursor-pointer" style={{ opacity: rootOp }}>
      <motion.div aria-hidden className="absolute inset-0" style={{ background: INK, opacity: bg }} />
      {/* A low sun at the left horizon: the only atmosphere */}
      <motion.div aria-hidden className="absolute inset-0" style={{ opacity: glowOp, background: 'radial-gradient(85% 58% at 6% 64%, rgb(228 169 91 / 0.17), transparent 64%)' }} />
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
      <button type="button" onClick={(e) => { e.stopPropagation(); skip() }} className="absolute right-4 bottom-4 min-h-11 rounded-md px-4 text-[13px] text-silver-400 transition-[color,transform] hover:text-paper active:scale-[0.97]">
        Skip
      </button>
    </motion.div>
  )
}

