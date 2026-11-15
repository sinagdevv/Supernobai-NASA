import { ArrowLeft, ArrowRight, CircleHelp, X } from 'lucide-react'
import { useReducedMotion } from 'motion/react'
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { CARD_W, placeCard, readGuide, SCREEN_LABEL, scrollDelta, STEPS, WELCOME, writeGuide, type Area, type Box, type Placement } from '../lib/guide'
import { usePlanet } from '../lib/planet'
import { go, type Route } from '../lib/router'
import { Button, cx } from './ui'

/*
 * The optional guide: a welcome card on the first visit, then a six-step walk-through any time after.
 * Each step lights the real control it talks about. It is a non-modal dialog: nothing is inert, nothing
 * traps focus, the highlight never blocks a click, and the app works the same without it.
 */

type Ctx = { open: boolean; show: () => void; trigger: React.RefObject<HTMLButtonElement | null> }
const GuideCtx = createContext<Ctx>({ open: false, show: () => {}, trigger: { current: null } })

/** The header control that opens the guide at any time. */
export function GuideButton({ className }: { className?: string }) {
  const { open, show, trigger } = useContext(GuideCtx)
  return (
    <button ref={trigger} type="button" onClick={show} aria-expanded={open} aria-controls="tw-guide" aria-label="Guide"
      className={cx('flex h-11 w-11 shrink-0 items-center justify-center gap-2 rounded-md text-[14px] font-medium text-silver-300 transition-[color,transform] hover:text-paper md:w-auto md:px-2.5 active:scale-[0.97]', className)}>
      <CircleHelp size={18} aria-hidden /><span className="hidden md:inline">Guide</span>
    </button>
  )
}

const FOCUSABLE = '[role="radio"][aria-checked="true"], button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex="0"]'

/** The first match that is actually on screen: hidden, inert and zero-size copies (a desktop-only tab bar on a phone) are skipped. */
function visible(selectors: string[]): HTMLElement | null {
  for (const sel of selectors) {
    for (const el of document.querySelectorAll<HTMLElement>(sel)) {
      const r = el.getBoundingClientRect()
      if (r.width > 0 && r.height > 0 && !el.closest('[inert], [hidden], .tw-guide-wrap')) return el
    }
  }
  return null
}

const toBox = (r: DOMRect): Box => ({ top: r.top, left: r.left, width: r.width, height: r.height })

/** The usable viewport: under the header, above the phone tab bar. */
function usable(): Area {
  const head = document.querySelector('header')?.getBoundingClientRect()
  const tabs = document.querySelector('nav.fixed[data-tabs]')?.getBoundingClientRect()
  return { width: window.innerWidth, top: Math.max(0, head?.bottom ?? 0), bottom: tabs && tabs.height > 0 ? tabs.top : window.innerHeight }
}

export function GuideProvider({ ready, route, children }: { ready: boolean; route: Route; children: ReactNode }) {
  const { planet } = usePlanet()
  const reduce = useReducedMotion()
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(-1) // -1: the welcome card
  const [target, setTarget] = useState<HTMLElement | null>(null)
  const [box, setBox] = useState<Box | null>(null)
  const [place, setPlace] = useState<Placement>({ mode: 'dock' })
  const trigger = useRef<HTMLButtonElement>(null)
  const card = useRef<HTMLDivElement>(null)
  const resume = useRef(-1) // where Exit left off; reopening picks up there
  const scrolled = useRef<HTMLElement | null>(null)

  const s = STEPS[step]
  const home = route.page === 'home'
  const variant = s && home && s.home ? s.home : s
  const targets = variant?.targets
  const last = step === STEPS.length - 1
  // A highlight that covers most of the screen (a whole empty screen) points at nothing: skip it.
  const big = !!box && box.width * box.height > 0.6 * window.innerWidth * window.innerHeight
  const here = !!s && (!s.screen || (route.page === 'app' && route.screen === s.screen))

  // First visit: offer it once, and only after the intro has finished or been skipped.
  useEffect(() => {
    if (ready && readGuide() === null) setOpen(true)
  }, [ready])

  // Focus moves into the card when it opens, and back to it if a step change removed the control that had it.
  useEffect(() => {
    if (open) card.current?.focus({ preventScroll: true })
  }, [open])
  useEffect(() => {
    if (open && document.activeElement === document.body) card.current?.focus({ preventScroll: true })
  }, [step, open])


  const show = useCallback(() => { setStep(resume.current); setOpen(true) }, [])
  const close = useCallback((outcome: 'done' | 'skipped' | 'exit') => {
    if (outcome === 'exit') { resume.current = step; if (readGuide() === null) writeGuide('skipped') }
    else { resume.current = -1; if (readGuide() === null || outcome === 'done') writeGuide(outcome) }
    const hadFocus = card.current?.contains(document.activeElement)
    setOpen(false)
    setTarget(null)
    scrolled.current = null
    if (hadFocus) trigger.current?.focus()
  }, [step])

  // Escape closes from anywhere, unless a real modal (the About dialog) is open and claimed it.
  useEffect(() => {
    if (!open) return
    const on = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented || document.querySelector('dialog[open], [aria-modal="true"]')) return
      close('exit')
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [open, close])

  // Find the real control for this step. The screen may still be loading, so keep looking while the step is open.
  useEffect(() => {
    if (!open || !targets) { setTarget(null); return }
    const find = () => setTarget((prev) => { const el = visible(targets); return el === prev ? prev : el })
    find()
    const id = window.setInterval(find, 250)
    return () => window.clearInterval(id)
  }, [open, targets, route, planet])

  // Follow it: scroll it into the usable area once, then track its position through scrolling, resizing and reflow.
  useEffect(() => {
    if (!open || !target) { setBox(null); return }
    const measure = () => { if (target.isConnected) setBox(toBox(target.getBoundingClientRect())) }
    const reveal = () => {
      const a = usable()
      if (a.width < 640) a.bottom -= (card.current?.offsetHeight ?? 0) + 16 // phones: the card docks at the bottom, so the control must clear it
      const dy = scrollDelta(toBox(target.getBoundingClientRect()), a)
      if (Math.abs(dy) > 1) window.scrollBy({ top: dy, behavior: reduce ? 'instant' : 'smooth' })
    }
    // A screen keeps growing as its data arrives, so look again after it settles, until the reader scrolls themselves.
    const timers: number[] = []
    let mine = true
    const stop = () => { mine = false }
    if (scrolled.current !== target) {
      scrolled.current = target
      reveal()
      for (const ms of [700, 1600]) timers.push(window.setTimeout(() => { if (mine) reveal() }, ms))
    }
    window.addEventListener('wheel', stop, { passive: true, once: true })
    window.addEventListener('touchmove', stop, { passive: true, once: true })
    measure()
    let raf = 0
    const tick = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(measure) }
    window.addEventListener('scroll', tick, { capture: true, passive: true })
    window.addEventListener('resize', tick)
    const ro = new ResizeObserver(tick)
    ro.observe(target)
    const poll = window.setInterval(measure, 400)
    return () => { timers.forEach(clearTimeout); window.removeEventListener('wheel', stop); window.removeEventListener('touchmove', stop); cancelAnimationFrame(raf); window.clearInterval(poll); ro.disconnect(); window.removeEventListener('scroll', tick, true); window.removeEventListener('resize', tick) }
  }, [open, target, reduce])

  // Place the card by the control it explains.
  useLayoutEffect(() => {
    if (!open) return
    setPlace(placeCard(big ? null : box, { width: CARD_W, height: card.current?.offsetHeight ?? 220 }, usable()))
  }, [open, box, big, step, planet, route])

  const goTo = (i: number) => {
    const next = STEPS[i]
    // From the landing page the mission step first points at the Open workspace button, so stay put for it.
    if (next?.screen && !(route.page === 'app' && route.screen === next.screen) && !(home && next.home)) go({ page: 'app', screen: next.screen })
    setStep(i)
  }
  const act = () => {
    if (!s) return
    if (home && s.home) { go({ page: 'app', screen: 'mission' }); return }
    if (!here && s.screen) { go({ page: 'app', screen: s.screen }); return }
    const el = target?.matches(FOCUSABLE) ? target : target?.querySelector<HTMLElement>(FOCUSABLE)
    el?.focus()
  }
  const actLabel = !s ? '' : home && s.home ? s.home.action : here ? s.action : `Go to ${SCREEN_LABEL[s.screen!]}`

  const pad = 6
  const float = place.mode === 'float' ? place : null
  return (
    <GuideCtx.Provider value={{ open, show, trigger }}>
      {children}
      {open && box && !big && (
        <div aria-hidden className="tw-spot no-print pointer-events-none fixed top-0 left-0 z-[49]"
          style={{ transform: `translate(${box.left - pad}px, ${box.top - pad}px)`, width: box.width + 2 * pad, height: box.height + 2 * pad }} />
      )}
      {open && (
        <div className={cx('tw-guide-wrap no-print fixed z-50', !float && 'right-2 left-2 sm:left-auto sm:w-[360px] md:right-4')}
          style={float ? { left: 0, top: 0, width: CARD_W, maxWidth: 'calc(100vw - 16px)', transform: `translate(${float.x}px, ${float.y}px)` } : { bottom: 'calc(var(--tabbar-h) + 8px)' }}>
          <div ref={card} id="tw-guide" role="dialog" aria-modal="false" aria-labelledby="tw-guide-h" aria-describedby="tw-guide-b" tabIndex={-1}
            className="tw-guide relative rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-ink-800 p-4 text-paper shadow-[var(--shadow-pop)] outline-none">
            {float && <i aria-hidden className={cx('tw-guide-arrow', `tw-guide-arrow-${float.side}`)} style={float.side === 'top' || float.side === 'bottom' ? { left: float.arrow } : { top: float.arrow }} />}
            <span className="sr-only" role="status">{s ? `Step ${step + 1} of ${STEPS.length}: ${variant!.title}` : ''}</span>
            <button type="button" onClick={() => close('exit')} aria-label="Exit guide" className="absolute top-1 right-1 grid h-11 w-11 place-items-center rounded-full text-silver-300 hover:text-paper"><X size={18} aria-hidden /></button>
            {!s ? (
              <>
                <h2 id="tw-guide-h" className="pr-10 text-[16px] font-semibold">Guide</h2>
                <p id="tw-guide-b" className="mt-1.5 text-[14px] leading-snug text-silver-200">{WELCOME}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button key="next" variant="primary" onClick={() => goTo(0)}>Start guide</Button>
                  <Button key="skip" variant="ghost" onClick={() => close('skipped')}>Skip</Button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-3 pr-10" aria-hidden>
                  <span className="mono text-xs text-silver-300">Step {step + 1} of {STEPS.length}</span>
                  <span className="flex gap-1">{STEPS.map((x, i) => <i key={x.id} className={cx('h-1 rounded-full transition-[width,background-color]', i === step ? 'w-4 bg-amber' : i < step ? 'w-1.5 bg-amber/60' : 'w-1.5 bg-silver-500/60')} />)}</span>
                </div>
                <h2 id="tw-guide-h" className="mt-1 pr-10 text-[16px] font-semibold">{variant!.title}</h2>
                <p id="tw-guide-b" className="mt-1.5 text-[14px] leading-snug text-silver-200">{variant!.body}{planet === 'mars' && !home && s.mars ? ` ${s.mars}` : ''}</p>
                {(target || !here) && (
                  <button type="button" onClick={act} className="mt-2 inline-flex min-h-11 items-center gap-1.5 text-[14px] font-medium text-amber underline-offset-4 hover:underline">{actLabel} <ArrowRight size={14} aria-hidden /></button>
                )}
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <Button key="back" size="sm" variant="ghost" onClick={() => goTo(step - 1)}><ArrowLeft size={14} aria-hidden />Back</Button>
                  <Button key="next" size="sm" variant="primary" onClick={() => (last ? close('done') : goTo(step + 1))}>{last ? 'Done' : 'Next'}{!last && <ArrowRight size={14} aria-hidden />}</Button>
                  {!last && <Button key="skip" size="sm" variant="ghost" className="ml-auto" onClick={() => close('skipped')}>Skip tour</Button>}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </GuideCtx.Provider>
  )
}
