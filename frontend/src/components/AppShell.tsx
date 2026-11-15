import { motion } from 'motion/react'
import { Crosshair, FileText, Map as MapIcon, RotateCcw, Scale, Sun, type LucideIcon } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Lockup, LogoMark } from '../brand/Logo'
import { BASEMAP_CREDITS, DISCLAIMER, NOT_REPRODUCIBLE, SOURCES } from '../data/sources'
import { href, type Screen } from '../lib/router'
import { prefetch, prefetchAll } from '../lib/screens'
import { useBackend } from '../lib/api/backend'
import { usePlanet } from '../lib/planet'
import { contextStatus, evidenceSnapshot, PLANET_CONTEXT } from '../lib/status'
import { useEvidence } from '../lib/api/evidence'
import { PlanetSwitcher } from './PlanetSwitcher'
import { GuideButton } from './Guide'
import { useApp } from '../lib/store'
import { cx, Modal } from './ui'

const STATE_DOT = { measured: 'bg-cyan', computed: 'bg-cyan', illustrative: 'bg-silver-400', pending: 'bg-amber', unavailable: 'bg-bad', checking: 'bg-silver-500' } as const

const TABS: { id: Screen; label: string; short: string; Icon: LucideIcon }[] = [
  { id: 'mission', label: 'Mission', short: 'Mission', Icon: Crosshair },
  { id: 'analogs', label: 'Analog Explorer', short: 'Explorer', Icon: MapIcon },
  { id: 'windows', label: 'Rehearsal Windows', short: 'Windows', Icon: Sun },
  { id: 'compare', label: 'Comparison', short: 'Compare', Icon: Scale },
  { id: 'dossier', label: 'Dossier', short: 'Dossier', Icon: FileText },
]

export function AboutModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { state } = useBackend()
  return (
    <Modal open={open} onClose={onClose} title="About this prototype">
      <div className="space-y-5 text-[14px] leading-relaxed text-silver-300">
        <p>{DISCLAIMER}</p>
        <div>
          <h3 className="eyebrow mb-2">What is live in this session</h3>
          {state.status === 'online' ? (
            <>
              <p>The service is connected (v{state.version}). It supplies four kinds of result, each labelled where it appears: <span className="font-medium text-paper">measured terrain</span> (Live terrain on the Explorer map, Measured terrain evidence on Comparison), <span className="font-medium text-paper">computed rehearsal windows</span> (Layer 4, on Rehearsal Windows), and <span className="font-medium text-paper">computed suitability assessments</span> (Layer 5, on Mission, the Explorer, Comparison and the Dossier). The example sites and the screening beside them are still illustrative.</p>
              <ul className="mt-2 space-y-1 text-[13px] text-silver-400">{state.stored.map((d) => <li key={d.id}><span className="text-silver-200">{d.name}</span> · {d.body} · {d.nominal_resolution_m} m · {d.ready ? 'validated' : 'not validated'}</li>)}</ul>
            </>
          ) : (
            <p>{state.status === 'checking' ? 'Checking for the Layer 2/3 service…' : 'The service is not running. Nothing is measured or computed, and every screen that needs it says so. Example sites and sample figures remain, labelled illustrative.'}</p>
          )}
          <p className="mt-2 text-[13px] text-silver-400">Computed results (rehearsal windows and suitability assessments) come from the solar-geometry and evidence engines. They are computed from stored data, not validated against observations, and not stored: Layer 6 (research storage and reporting) is not connected. Assessment thresholds are assumptions you can change, and a pass means only that your thresholds were met. On Mars, terrain is measured from MOLA and the Layer 4 grid (1.85 km) is coarser than the terrain grid (463 m).</p>
        </div>
        <div>
          <h3 className="eyebrow mb-2">Earth cannot reproduce</h3>
          <ul className="space-y-2">
            {NOT_REPRODUCIBLE.map((n) => (
              <li key={n.id}><span className="font-medium text-paper">{n.label}.</span> {n.detail}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="eyebrow mb-2">Data resources</h3>
          <ul className="space-y-2">
            {SOURCES.map((s) => (
              <li key={s.id}>
                <a className="font-medium text-cyan underline underline-offset-2 hover:text-paper" href={s.url} target="_blank" rel="noreferrer noopener">{s.name}</a>
                <span className="text-silver-400"> — {s.role}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="eyebrow mb-2">Basemap credits</h3>
          <ul className="space-y-1 text-xs text-silver-400">{BASEMAP_CREDITS.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      </div>
    </Modal>
  )
}

/** Remembers each screen's scroll position so switching tabs returns you to where you were. */
const scrollMemory = new Map<Screen, number>()
let restoring = false
/** Time of the last route change. The browser clamps scroll to the (shorter) incoming page and fires scroll events that must not overwrite the saved position. */
let lastNav = 0
if (typeof window !== 'undefined') window.addEventListener('hashchange', () => { lastNav = performance.now() })

export function AppShell({ screen, children }: { screen: Screen; children: ReactNode }) {
  const { resetAll } = useApp()
  const { planet } = usePlanet()
  const { state: backend } = useBackend()
  const ctx = PLANET_CONTEXT[planet]
  const marsReady = backend.status === 'online' && backend.stored.some((d) => d.body === 'mars' && d.ready)
  const evidence = useEvidence()
  const status = contextStatus(planet, screen, backend.status, marsReady, evidenceSnapshot(planet, screen, evidence.rehearsal, evidence.assessments))
  const [about, setAbout] = useState(false)
  const main = useRef<HTMLElement>(null)
  const nav = useRef<HTMLUListElement>(null)

  useEffect(() => prefetchAll(), [])

  // Restore this screen's scroll. Move focus to the new screen when it came from the tab bar.
  useLayoutEffect(() => {
    const target = scrollMemory.get(screen) ?? 0
    window.scrollTo({ top: target, behavior: 'instant' })
    if (document.activeElement?.closest('[data-tabs]')) main.current?.focus({ preventScroll: true })
    // Charts lay out a frame or two later, so the page may be too short to reach the saved position yet: retry briefly.
    let raf = 0, n = 0
    restoring = target > 0
    const tick = () => {
      if (Math.abs(window.scrollY - target) <= 2 || n++ > 45) { restoring = false; return }
      window.scrollTo({ top: target, behavior: 'instant' })
      raf = requestAnimationFrame(tick)
    }
    if (restoring) raf = requestAnimationFrame(tick)
    const stop = () => { restoring = false; cancelAnimationFrame(raf) }
    window.addEventListener('wheel', stop, { passive: true, once: true })
    window.addEventListener('touchstart', stop, { passive: true, once: true })
    return () => { stop(); window.removeEventListener('wheel', stop); window.removeEventListener('touchstart', stop) }
  }, [screen])

  // Record scroll as it happens: by the time an effect cleanup runs, the next screen has already been laid out and the browser has clamped it.
  useEffect(() => {
    const on = () => { if (!restoring && performance.now() - lastNav > 600) scrollMemory.set(screen, window.scrollY) }
    window.addEventListener('scroll', on, { passive: true })
    return () => window.removeEventListener('scroll', on)
  }, [screen])

  const onKey = (e: KeyboardEvent) => {
    const links = [...(nav.current?.querySelectorAll<HTMLAnchorElement>('a') ?? [])]
    const i = links.indexOf(document.activeElement as HTMLAnchorElement)
    const n = e.key === 'ArrowRight' ? (i + 1) % links.length : e.key === 'ArrowLeft' ? (i - 1 + links.length) % links.length : e.key === 'Home' ? 0 : e.key === 'End' ? links.length - 1 : -1
    if (i < 0 || n < 0) return
    e.preventDefault()
    links[n].focus()
  }

  return (
    <div className="tw-shell flex min-h-dvh flex-col" style={{ paddingBottom: 'var(--tabbar-h)' }}>
      <header className="no-print glass sticky top-0 z-40" style={{ height: 'var(--topbar-h)' }}>
        {/* Level 1: the planet. Everything below it is about that planet. */}
        <div className="mx-auto flex h-14 max-w-[1920px] items-center gap-2 px-3 sm:gap-3 md:gap-5 md:px-5">
          <a href="#/" aria-label="TERRAWINDOW home" className="vt-lockup -ml-1 flex h-11 shrink-0 items-center rounded-md px-1 text-paper">
            <Lockup className="hidden h-[22px] md:block" />
            <LogoMark className="h-7 md:hidden" />
          </a>
          <PlanetSwitcher />
          <div className="ml-auto flex items-center gap-1">
            <GuideButton />
            <button type="button" onClick={resetAll} className="grid h-11 w-11 place-items-center rounded-md text-silver-400 transition-[color,transform] hover:text-paper active:scale-[0.97]" aria-label="Reset demonstration state" title="Reset demonstration state"><RotateCcw size={16} aria-hidden /></button>
          </div>
        </div>
        {/* Level 2: the tool, and what the data on it is. Independent tabs keep their state across planets. */}
        <div className="mx-auto flex h-8 max-w-[1920px] items-center gap-4 px-3 md:h-11 md:px-5">
          <nav aria-label="Workspace" data-tabs onKeyDown={onKey} className="hidden h-full min-w-0 md:flex">
            <ul ref={nav} className="flex h-full items-stretch gap-0.5 lg:gap-2">
              {TABS.map((t) => {
                const on = t.id === screen
                return (
                  <li key={t.id} className="relative flex">
                    <a href={href({ page: 'app', screen: t.id })} aria-current={on ? 'page' : undefined} onPointerEnter={() => prefetch(t.id)} onFocus={() => prefetch(t.id)}
                      className={cx('flex items-center px-3 text-[14px] font-medium whitespace-nowrap transition-colors duration-[var(--duration-fast)] active:opacity-70 lg:px-4', on ? 'text-paper' : 'text-silver-400 hover:text-paper')}>
                      <span className="xl:hidden">{t.short}</span>
                      <span className="hidden xl:inline">{t.label}</span>
                    </a>
                    {on && <motion.span layoutId="tab-underline" aria-hidden className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-amber lg:inset-x-4" transition={{ type: 'spring', duration: 0.32, bounce: 0 }} />}
                  </li>
                )
              })}
            </ul>
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-3">
            <p className="mono flex min-w-0 items-center gap-2 text-xs tracking-[0.04em] text-silver-300 uppercase" aria-label={`Research context: ${ctx.title}, ${ctx.place}`}>
              <i aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: planet === 'mars' ? '#c9876a' : 'var(--color-silver-300)' }} />
              <span className="truncate"><span className="font-medium text-paper">{ctx.title}</span><span className="hidden sm:inline"> / {ctx.place}</span></span>
            </p>
            <button type="button" onClick={() => setAbout(true)} aria-label={`Data status: ${status.label}. ${status.detail} Open details.`} title={status.detail}
              className="flex min-h-8 shrink-0 items-center gap-2 rounded-full border border-[var(--line-strong)] px-3 text-xs text-silver-200 transition-[color,transform,border-color] hover:border-silver-500 hover:text-paper active:scale-[0.97]">
              <i aria-hidden className={cx('h-1.5 w-1.5 rounded-full', STATE_DOT[status.state])} />
              {status.label}
            </button>
          </div>
        </div>
        <div aria-hidden className="absolute inset-x-0 bottom-0 h-px transition-colors duration-[var(--duration-slow)]" style={{ background: planet === 'mars' ? 'rgb(201 135 106 / 0.45)' : 'rgb(197 202 208 / 0.28)' }} />
      </header>

      <main id="main" ref={main} tabIndex={-1} className="flex-1 outline-none">{children}</main>

      {/* Phones: a bottom tab bar (thumb reach). Short labels; the active tab carries a shared indicator. */}
      <nav aria-label="Workspace" data-tabs className="no-print glass fixed inset-x-0 bottom-0 z-40 border-t border-[var(--line)] md:hidden" style={{ height: 'var(--tabbar-h)', paddingBottom: 'env(safe-area-inset-bottom)' }}>
        <ul className="grid h-[60px] grid-cols-5">
          {TABS.map((t) => {
            const on = t.id === screen
            return (
              <li key={t.id} className="relative">
                <a href={href({ page: 'app', screen: t.id })} aria-current={on ? 'page' : undefined} onPointerDown={() => prefetch(t.id)}
                  className={cx('flex h-full flex-col items-center justify-center gap-0.5 text-xs font-medium transition-colors active:opacity-70', on ? 'text-paper' : 'text-silver-400')}>
                  <t.Icon size={20} aria-hidden strokeWidth={on ? 2.1 : 1.6} className={on ? 'text-amber' : undefined} />
                  {t.short}
                </a>
                {on && <motion.span layoutId="tab-top" aria-hidden className="absolute inset-x-5 top-0 h-0.5 rounded-b-full bg-amber" transition={{ type: 'spring', duration: 0.32, bounce: 0 }} />}
              </li>
            )
          })}
        </ul>
      </nav>
      <AboutModal open={about} onClose={() => setAbout(false)} />
    </div>
  )
}
