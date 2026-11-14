import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { cx } from '../ui'

/** Measured size of an element in CSS pixels. Figures are drawn in these pixels, so text is never scaled and nothing is cropped by a mismatched viewBox. */
export function useBox<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [box, set] = useState({ w: 0, h: 0 })
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const read = () => set((p) => (p.w === el.clientWidth && p.h === el.clientHeight ? p : { w: el.clientWidth, h: el.clientHeight }))
    read()
    const ro = new ResizeObserver(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, box] as const
}

/** True while the element is on screen. Pointer and scroll effects subscribe only while this holds. */
export function useOnScreen(ref: RefObject<Element | null>, margin = '0px') {
  const [on, setOn] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), { rootMargin: margin })
    io.observe(el)
    return () => io.disconnect()
  }, [ref, margin])
  return on
}

/** Decorative pointer effects exist only for a fine pointer that can hover, and never under reduced motion. */
export function useFinePointer() {
  const reduce = useReducedMotion()
  const [fine, setFine] = useState(false)
  useEffect(() => {
    const q = window.matchMedia('(hover: hover) and (pointer: fine)')
    const on = () => setFine(q.matches)
    on()
    q.addEventListener('change', on)
    return () => q.removeEventListener('change', on)
  }, [])
  return fine && !reduce
}

/**
 * The shared frame of every figure on the page: a hairline window with corner ticks. Terrain that meets the frame is cropped by it, on purpose.
 * `bar` is an optional legend row above the drawing.
 */
export function Plate({ children, bar, foot, className, label, shown = true }: { children: ReactNode; bar?: ReactNode; foot?: ReactNode; className?: string; label?: string; shown?: boolean }) {
  const fade = { opacity: shown ? 1 : 0, transition: 'opacity 420ms var(--ease-out)' }
  return (
    <figure aria-label={label} className={cx('relative min-w-0 max-w-full overflow-hidden rounded-[var(--radius-md)] border transition-[border-color,background-color] duration-[420ms]', shown ? 'border-[var(--line-strong)] bg-[#0c0f13]' : 'border-transparent bg-transparent', className)}>
      {bar && <div style={fade} className="relative z-10 flex min-h-11 flex-wrap items-center gap-x-5 gap-y-1 border-b border-[var(--line)] px-3.5 py-2 text-[13px] text-silver-300">{bar}</div>}
      {children}
      {foot && <div style={fade} className="relative z-10 border-t border-[var(--line)] px-3.5 py-2.5 text-[13px] leading-snug text-silver-400">{foot}</div>}
    </figure>
  )
}

export function Swatch({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <i aria-hidden className="h-2.5 w-2.5 rounded-[2px]" style={{ background: color }} />
      {children}
    </span>
  )
}

/**
 * Very slight pull toward the pointer for one large call to action. Capped at a few pixels, critically damped, off for touch and reduced motion.
 * The wrapper only translates; the button inside keeps its own press feedback.
 */
export function Magnetic({ children, className }: { children: ReactNode; className?: string }) {
  const fine = useFinePointer()
  const box = useRef<HTMLSpanElement>(null)
  const x = useMotionValue(0), y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 260, damping: 26, mass: 0.5 }), sy = useSpring(y, { stiffness: 260, damping: 26, mass: 0.5 })
  useEffect(() => {
    if (!fine) return
    let raf = 0
    const on = (e: PointerEvent) => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const r = box.current?.getBoundingClientRect()
        if (!r) return
        const dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2)
        const reach = 72 + r.width / 2
        if (Math.hypot(dx, dy) > reach) { x.set(0); y.set(0); return }
        x.set(Math.max(-5, Math.min(5, dx * 0.14)))
        y.set(Math.max(-4, Math.min(4, dy * 0.18)))
      })
    }
    window.addEventListener('pointermove', on, { passive: true })
    return () => { window.removeEventListener('pointermove', on); cancelAnimationFrame(raf); x.set(0); y.set(0) }
  }, [fine, x, y])
  return <motion.span ref={box} style={{ x: sx, y: sy }} className={cx('inline-flex', className)}>{children}</motion.span>
}

/** The text half of a chapter: a numbered question, a headline, one short line. */
export function ChapterText({ id, n, q, title, children }: { id: string; n: string; q: string; title: string; children: ReactNode }) {
  return (
    <div>
      <p className="mono text-[13px] tracking-[0.04em] text-amber">{n} — {q}</p>
      <h2 id={id} className="font-display mt-3 text-[clamp(30px,3.5vw,50px)] leading-[1.02]">{title}</h2>
      <p className="mt-4 max-w-[26rem] text-[16px] leading-[1.55] text-silver-300">{children}</p>
    </div>
  )
}

export function useMedia(query: string) {
  const [m, setM] = useState(() => (typeof window === 'undefined' ? false : window.matchMedia(query).matches))
  useEffect(() => {
    const q = window.matchMedia(query)
    const on = () => setM(q.matches)
    on()
    q.addEventListener('change', on)
    return () => q.removeEventListener('change', on)
  }, [query])
  return m
}
