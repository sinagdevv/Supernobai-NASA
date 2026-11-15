import { ArrowLeft, ArrowRight, CircleHelp, X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { readGuide, STEPS, WELCOME, writeGuide } from '../lib/guide'
import { go } from '../lib/router'
import { Button, cx } from './ui'

/*
 * The optional guide: a welcome card on the first visit and a six-step walk-through any time after.
 * It is a non-modal dialog: nothing is inert, nothing traps focus, and the app works the same without it.
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

export function GuideProvider({ ready, inApp, children }: { ready: boolean; inApp: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(-1) // -1: the welcome card
  const trigger = useRef<HTMLButtonElement>(null)
  const card = useRef<HTMLDivElement>(null)

  // First visit: offer it once, and only after the intro has finished or been skipped.
  useEffect(() => {
    if (ready && readGuide() === null) setOpen(true)
  }, [ready])

  // Focus moves into the card whenever it opens.
  useEffect(() => {
    if (open) card.current?.focus({ preventScroll: true })
  }, [open])

  const show = useCallback(() => { setStep(-1); setOpen(true) }, [])
  const close = (outcome: 'done' | 'skipped') => {
    if (readGuide() === null || outcome === 'done') writeGuide(outcome)
    const hadFocus = card.current?.contains(document.activeElement)
    setOpen(false)
    if (hadFocus) trigger.current?.focus()
  }

  const s = STEPS[step]
  const last = step === STEPS.length - 1
  const act = () => {
    if (!s) return
    if (s.action.screen) go({ page: 'app', screen: s.action.screen })
    else document.querySelector<HTMLElement>('[aria-label="Planetary target"] [aria-checked="true"]')?.focus()
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') { e.stopPropagation(); close('skipped') }
  }

  return (
    <GuideCtx.Provider value={{ open, show, trigger }}>
      {children}
      {open && (
        <div ref={card} id="tw-guide" role="dialog" aria-modal="false" aria-labelledby="tw-guide-h" tabIndex={-1} onKeyDown={onKey}
          style={{ bottom: inApp ? 'calc(var(--tabbar-h) + 8px)' : undefined }}
          className={cx('tw-guide no-print fixed right-2 left-2 z-50 rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-ink-800 p-4 text-paper shadow-[var(--shadow-pop)] outline-none sm:left-auto sm:w-[360px] md:right-4 md:bottom-4', !inApp && 'bottom-2')}>
          <button type="button" onClick={() => close('skipped')} aria-label="Close guide" className="absolute top-1 right-1 grid h-11 w-11 place-items-center rounded-full text-silver-300 hover:text-paper"><X size={18} aria-hidden /></button>
          {!s ? (
            <>
              <h2 id="tw-guide-h" className="pr-10 text-[16px] font-semibold">Guide</h2>
              <p className="mt-1.5 text-[14px] leading-snug text-silver-200">{WELCOME}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="primary" onClick={() => setStep(0)}>Start guide</Button>
                <Button variant="ghost" onClick={() => close('skipped')}>Skip</Button>
              </div>
            </>
          ) : (
            <>
              <p className="mono text-xs text-silver-300" aria-live="polite">Step {step + 1} of {STEPS.length}</p>
              <h2 id="tw-guide-h" className="mt-1 pr-10 text-[16px] font-semibold">{s.title}</h2>
              <p className="mt-1.5 text-[14px] leading-snug text-silver-200">{s.body}</p>
              <button type="button" onClick={act} className="mt-2 inline-flex min-h-11 items-center gap-1.5 text-[14px] font-medium text-amber underline-offset-4 hover:underline">{s.action.label} <ArrowRight size={14} aria-hidden /></button>
              <div className="mt-1 flex items-center gap-2">
                <Button size="sm" variant="ghost" onClick={() => setStep(step - 1)}><ArrowLeft size={14} aria-hidden />Back</Button>
                <Button size="sm" variant="primary" onClick={() => (last ? close('done') : setStep(step + 1))}>{last ? 'Done' : 'Next'}</Button>
                {!last && <Button size="sm" variant="ghost" className="ml-auto" onClick={() => close('skipped')}>Skip</Button>}
              </div>
            </>
          )}
        </div>
      )}
    </GuideCtx.Provider>
  )
}
