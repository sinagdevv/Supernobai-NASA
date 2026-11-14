import { motion, useReducedMotion } from 'motion/react'
import { ArrowDown, ArrowRight, ExternalLink } from 'lucide-react'
import { memo, useState } from 'react'
import { Lockup } from '../brand/Logo'
import { HeroPlate } from '../components/landing/HeroPlate'
import { Magnetic } from '../components/landing/kit'
import { Button, cx, StatusBadge, Tabs } from '../components/ui'
import { BASEMAP_CREDITS, DISCLAIMER, SOURCES } from '../data/sources'
import type { Status } from '../data/types'
import { enterWorkspace } from '../lib/transition'
import What from './landing/What'
import When from './landing/When'
import Where from './landing/Where'

const enter = () => enterWorkspace('mission')
const EASE = [0.23, 1, 0.32, 1] as const

/* ───────────── Navigation: translucent material over content ───────────── */
const Nav = memo(function Nav() {
  return (
    <header className="glass fixed inset-x-0 top-0 z-30 border-b border-[var(--line)]">
      <div className="mx-auto flex h-14 max-w-[1680px] items-center justify-between px-4 md:px-8">
        <a href="#/" aria-label="TERRAWINDOW home" className="vt-lockup -ml-1 flex h-11 items-center rounded-md px-1 text-paper"><Lockup target className="h-[22px]" /></a>
        <nav aria-label="Page sections" className="hidden items-center gap-1 md:flex">
          {[['#where', 'Where'], ['#when', 'When'], ['#what', 'What'], ['#workspace', 'Workspace'], ['#transparency', 'Transparency']].map(([h, l]) => (
            <a key={h} href={h} className="flex min-h-11 items-center rounded-md px-3 text-[14px] text-silver-300 transition-colors hover:text-paper">{l}</a>
          ))}
        </nav>
        <Button variant="primary" size="sm" onClick={enter}><span className="min-[400px]:hidden">Workspace</span><span className="hidden min-[400px]:inline">Open workspace</span> <ArrowRight size={15} aria-hidden /></Button>
      </div>
    </header>
  )
})

/* ───────────── Hero: the headline beside the observation plate ───────────── */
function Hero({ show, ribbons }: { show: boolean; ribbons: boolean }) {
  const reduce = useReducedMotion()
  const item = (i: number) => ({ initial: reduce ? false : { opacity: 0, y: 10 }, animate: show ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }, transition: { duration: 0.5, delay: show ? 0.1 + i * 0.07 : 0, ease: EASE } })
  return (
    <section aria-labelledby="hero-title" className="relative">
      <div className="mx-auto grid min-h-[min(100svh,900px)] max-w-[1680px] *:min-w-0 items-center gap-x-12 gap-y-10 px-4 pt-[88px] pb-12 md:px-8 lg:grid-cols-12 lg:pt-[72px]">
        <div className="lg:col-span-5">
          <motion.h1 id="hero-title" {...item(0)} className="font-display text-[clamp(38px,4.5vw,84px)] leading-[0.98] tracking-[-0.032em]">
            Find the Earth.<br />Test for the Moon.
          </motion.h1>
          <motion.p {...item(1)} className="mt-6 max-w-[27rem] text-[17px] leading-[1.55] text-silver-300">
            Discover terrestrial analog environments, explore potential rehearsal windows, and evaluate mission-specific testing conditions.
          </motion.p>
          <motion.div {...item(2)} className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2">
            <Magnetic><Button variant="primary" onClick={enter} className="px-5">Explore Earth Analogs <ArrowRight size={17} aria-hidden /></Button></Magnetic>
            <a href="#where" className="inline-flex min-h-11 items-center gap-2 text-[15px] font-medium text-silver-200 transition-colors hover:text-paper">How it works <ArrowDown size={15} aria-hidden /></a>
          </motion.div>
        </div>
        <div className="lg:col-span-7">
          <HeroPlate ribbons={ribbons} chrome={show} />
        </div>
      </div>
    </section>
  )
}

/* ───────────── The problem: four facets in one row ───────────── */
const FACETS: { id: string; label: string; status: Status; badge: string; body: string }[] = [
  { id: 'geology', label: 'Geology', status: 'not-assessed', badge: 'Verify composition', body: 'Polar lunar highland regolith is not mare basalt.' },
  { id: 'terrain', label: 'Terrain', status: 'potential', badge: 'Can be screened', body: 'Slope and roughness compare, where the data resolve them.' },
  { id: 'sun', label: 'Sunlight', status: 'potential', badge: 'Date-dependent', body: 'A sun a few degrees up reaches Earth near sunrise and sunset.' },
  { id: 'env', label: 'Environment', status: 'not-suitable', badge: 'Not reproducible', body: 'Gravity, vacuum, radiation and polar cold do not transfer.' },
]

const Problem = memo(function Problem() {
  return (
    <section id="problem" aria-labelledby="problem-title" className="border-t border-[var(--line)] py-14 md:py-20">
      <div className="mx-auto max-w-[1680px] px-4 md:px-8">
        <h2 id="problem-title" className="font-display max-w-[22ch] text-[clamp(28px,3.2vw,44px)]">Looking like the Moon is not the same as testing like it.</h2>
        <dl className="mt-8 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
          {FACETS.map((f) => (
            <div key={f.id} className="border-t border-[var(--line-strong)] pt-4">
              <dt className="flex flex-wrap items-center gap-x-3 gap-y-2"><span className="text-[17px] font-medium">{f.label}</span><StatusBadge status={f.status} label={f.badge} /></dt>
              <dd className="mt-2 text-[15px] leading-[1.5] text-silver-300">{f.body}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
})

/* ───────────── Chapter 04: the instrument itself ───────────── */
const SHOTS = [
  { id: 'mission', label: 'Mission', title: 'Define the experiment', body: 'Rover limits and the lighting band; candidates re-sort live.' },
  { id: 'analogs', label: 'Analog Explorer', title: 'Find ground worth testing', body: 'A map with a visual candidate browser and a per-site inspector.' },
  { id: 'windows', label: 'Rehearsal Windows', title: 'Find the days the sun is right', body: 'Calendar, solar track and terrain shadows as one instrument.' },
  { id: 'compare', label: 'Comparison', title: 'See what the evidence supports', body: 'Earth against the lunar reference, criterion by criterion.' },
  { id: 'dossier', label: 'Dossier', title: 'Take it into the field', body: 'A printable preliminary assessment with provenance.' },
] as const

const Workspace = memo(function Workspace() {
  const [id, setId] = useState<(typeof SHOTS)[number]['id']>('windows')
  const s = SHOTS.find((x) => x.id === id)!
  return (
    <section id="workspace" aria-labelledby="workspace-title" className="scroll-mt-14 border-t border-[var(--line)] py-16 md:py-24">
      <div className="mx-auto max-w-[1680px] px-4 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-x-12 gap-y-6">
          <div>
            <p className="mono text-[13px] tracking-[0.04em] text-amber">04 — Enter the workspace</p>
            <h2 id="workspace-title" className="font-display mt-3 text-[clamp(32px,4vw,60px)] leading-[1.02]">Open the instrument.</h2>
          </div>
          <Magnetic><Button variant="primary" onClick={enter} className="min-h-12 px-6 text-[16px]">Enter the workspace <ArrowRight size={18} aria-hidden /></Button></Magnetic>
        </div>

        <div className="mt-10 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-ink-850 shadow-[var(--shadow-pop)]">
          <div className="bg-ink-900 px-2"><Tabs label="Workspace screens" value={id} onChange={setId} tabs={SHOTS.map((x) => ({ id: x.id, label: x.label }))} /></div>
          <div className="relative aspect-[16/9.6]">
            {SHOTS.map((x) => (
              <img key={x.id} src={`/shots/${x.id}.jpg`} alt={`The ${x.label} tab of the TERRAWINDOW workspace (illustrative prototype data)`} width={1440} height={900} loading="lazy" decoding="async"
                className={cx('absolute inset-0 h-full w-full object-cover object-top transition-opacity duration-200 ease-out', x.id === id ? 'opacity-100' : 'pointer-events-none opacity-0')} />
            ))}
            {/* The crop is deliberate: the window fades into the page instead of ending mid-widget. */}
            <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3" style={{ background: 'linear-gradient(to bottom, transparent, var(--color-ink-850) 92%)' }} />
          </div>
        </div>
        <div className="mt-5 flex flex-wrap items-baseline justify-between gap-x-10 gap-y-2">
          <p className="text-[16px]"><span className="font-medium">{s.title}.</span> <span className="text-silver-300">{s.body}</span></p>
          <a href={`#/app/${s.id}`} className="inline-flex min-h-11 items-center gap-2 text-[15px] font-medium text-amber hover:underline">Open {s.label} <ArrowRight size={15} aria-hidden /></a>
        </div>
        <p className="mt-6 max-w-3xl border-t border-[var(--line)] pt-5 text-[14px] text-silver-400"><span className="font-medium text-amber">Working prototype:</span> lunar south-polar rover mobility and navigation under low-angle illumination. <span className="font-medium text-silver-300">Not implemented:</span> Mars, shown as a locked roadmap item.</p>
      </div>
    </section>
  )
})

/* ───────────── Transparency (paper surface) ───────────── */
const Transparency = memo(function Transparency() {
  return (
    <section id="transparency" aria-labelledby="transp-title" className="paper scroll-mt-14 py-16 md:py-24">
      <div className="mx-auto grid max-w-[1680px] gap-10 px-4 md:px-8 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-6">
          <h2 id="transp-title" className="font-display text-[clamp(30px,3.6vw,50px)]">Preliminary planning. Not certification.</h2>
          <p className="mt-5 max-w-[32rem] text-[16px] leading-[1.6] text-graphite-soft">{DISCLAIMER}</p>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-[14px] font-medium text-graphite">It helps you</h3>
              <ul className="mt-2 space-y-1.5 text-[15px] leading-snug text-graphite-soft"><li>Shortlist terrain to look at</li><li>Time a rehearsal around low sun</li><li>See which evidence is missing</li></ul>
            </div>
            <div>
              <h3 className="text-[14px] font-medium text-graphite">It does not</h3>
              <ul className="mt-2 space-y-1.5 text-[15px] leading-snug text-graphite-soft"><li>Give a single similarity score</li><li>Predict lighting with a validated ephemeris</li><li>Reproduce gravity, vacuum or radiation</li></ul>
            </div>
          </div>
        </div>
        <div className="lg:col-span-5 lg:col-start-8">
          <h3 className="text-[14px] font-medium text-graphite">Data resources</h3>
          <ul className="mt-2 divide-y divide-[var(--line)] border-y border-[var(--line)]">
            {SOURCES.map((s) => (
              <li key={s.id}>
                <a href={s.url} target="_blank" rel="noreferrer noopener" className="group flex min-h-12 items-center justify-between gap-4 py-2">
                  <span><span className="block text-[15px] font-medium text-graphite group-hover:underline">{s.name}</span><span className="block text-[13px] text-graphite-soft">{s.role}</span></span>
                  <ExternalLink size={15} aria-label="opens in new tab" className="shrink-0 text-graphite-soft" />
                </a>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] leading-relaxed text-graphite-soft">No agency sponsorship or endorsement is implied. Basemaps: {BASEMAP_CREDITS.join(' · ')}.</p>
        </div>
      </div>
    </section>
  )
})

const Footer = memo(function Footer() {
  return (
    <footer className="py-8">
      <div className="mx-auto flex max-w-[1680px] flex-col gap-3 px-4 text-[13px] text-silver-400 md:flex-row md:items-center md:justify-between md:px-8">
        <Lockup className="h-5 text-silver-300" />
        <p className="max-w-2xl">A NASA Space Apps Challenge prototype with illustrative data. Not affiliated with, or endorsed by, NASA.</p>
      </div>
    </footer>
  )
})

/** `introPlayed`: the intro ran this load; `heroIn` flips when the intro starts handing over; `introDone` when its drawing is removed. Without an intro the hero is simply there. */
export default function Landing({ introPlayed, heroIn, introDone }: { introPlayed: boolean; heroIn: boolean; introDone: boolean }) {
  return (
    <div>
      <Nav />
      <main id="main">
        <Hero show={!introPlayed || heroIn} ribbons={!introPlayed || introDone} />
        <Problem />
        <Where />
        <When />
        <What />
        <Workspace />
        <Transparency />
      </main>
      <Footer />
    </div>
  )
}
