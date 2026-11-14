import { motion } from 'motion/react'
import { Crosshair, FileText, Info, Map as MapIcon, RotateCcw, Scale, Sun, type LucideIcon } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Lockup, LogoMark } from '../brand/Logo'
import { BASEMAP_CREDITS, DISCLAIMER, NOT_REPRODUCIBLE, SOURCES } from '../data/sources'
import { shortName, siteById } from '../data/sites'
import { regionById } from '../lib/assess'
import { href, type Screen } from '../lib/router'
import { prefetch, prefetchAll } from '../lib/screens'
import { useBackend } from '../lib/api/backend'
import { useApp } from '../lib/store'
import { cx, Modal } from './ui'

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
              <p>The Layer 2/3 service is connected (v{state.version}). Mission, Explorer sites, Rehearsal Windows and the Dossier still run on the prototype’s illustrative data. Only the <span className="font-medium text-paper">Measured terrain evidence</span> panel on Comparison reads the service.</p>
              <ul className="mt-2 space-y-1 text-[13px] text-silver-400">{state.stored.map((d) => <li key={d.id}><span className="text-silver-200">{d.name}</span> · {d.body} · {d.nominal_resolution_m} m · {d.ready ? 'validated' : 'not validated'}</li>)}</ul>
            </>
          ) : (
            <p>{state.status === 'checking' ? 'Checking for the Layer 2/3 service…' : 'The Layer 2/3 service is not running, so the whole interface is showing illustrative demonstration data.'}</p>
          )}
          <p className="mt-2 text-[13px] text-silver-400">Rehearsal-window and shadow computation (Layer 4) and mission criteria (Layer 5) are not implemented; those screens are demonstrations.</p>
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
          <ul className="space-y-1 text-[12px] text-silver-400">{BASEMAP_CREDITS.map((c) => <li key={c}>{c}</li>)}</ul>
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
  const { mission, selectedId, resetAll } = useApp()
  const { state: backend } = useBackend()
  const [about, setAbout] = useState(false)
  const main = useRef<HTMLElement>(null)
  const nav = useRef<HTMLUListElement>(null)
  const site = siteById(selectedId)

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
    <div className="flex min-h-dvh flex-col" style={{ paddingBottom: 'var(--tabbar-h)' }}>
      <header className="no-print glass sticky top-0 z-40" style={{ height: 'var(--topbar-h)' }}>
        <div className="mx-auto flex h-full max-w-[1920px] items-center gap-4 px-3 md:px-5">
          <a href="#/" aria-label="TERRAWINDOW home" className="vt-lockup -ml-1 flex h-11 shrink-0 items-center rounded-md px-1 text-paper">
            <Lockup className="hidden h-[22px] md:block" />
            <LogoMark className="h-7 md:hidden" />
          </a>

          {/* Independent tabs: every destination is always reachable; state is kept across them. */}
          <nav aria-label="Workspace" data-tabs onKeyDown={onKey} className="hidden h-full min-w-0 flex-1 justify-center md:flex">
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

          <div className="ml-auto flex items-center gap-1 md:ml-0">
            <a href={href({ page: 'app', screen: 'mission' })} className="hidden min-h-11 max-w-[20rem] items-center gap-2 truncate rounded-md px-2 text-[13px] text-silver-300 transition-colors hover:text-paper xl:flex" title="Mission context">
              <span className="truncate">{regionById(mission.regionId).name}</span>
              {site && <><span aria-hidden className="text-silver-500">/</span><span className="truncate text-cyan">{shortName(site)}</span></>}
            </a>
            <button type="button" onClick={() => setAbout(true)} className="flex min-h-11 items-center gap-2 rounded-md px-2.5 text-[13px] text-silver-300 transition-[color,transform] hover:text-paper active:scale-[0.97]" aria-label={backend.status === 'online' ? 'Data status: demonstration data, Layer 3 service connected. Open details.' : 'Data status: illustrative prototype data. Open details.'}>
              <i aria-hidden className={cx('h-1.5 w-1.5 rounded-full', backend.status === 'online' ? 'bg-cyan' : 'bg-amber')} />
              <span className="hidden xl:inline">{backend.status === 'online' ? 'Demo data · Layer 3 live' : 'Illustrative data'}</span>
              <Info size={16} aria-hidden className="xl:hidden" />
            </button>
            <button type="button" onClick={resetAll} className="grid h-11 w-11 place-items-center rounded-md text-silver-400 transition-[color,transform] hover:text-paper active:scale-[0.97]" aria-label="Reset demonstration state" title="Reset demonstration state"><RotateCcw size={16} aria-hidden /></button>
          </div>
        </div>
        <div aria-hidden className="absolute inset-x-0 bottom-0 h-px bg-[var(--line)]" />
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
                  className={cx('flex h-full flex-col items-center justify-center gap-0.5 text-[12px] font-medium transition-colors active:opacity-70', on ? 'text-paper' : 'text-silver-400')}>
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
