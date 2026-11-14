import { motion } from 'motion/react'
import { ChevronDown, CircleCheck, CircleMinus, CircleX, Info, Moon, Sunrise, Sunset } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { DayCalendar } from '../../components/windows/DayCalendar'
import { RoverCompass } from '../../components/windows/RoverCompass'
import { SolarPlot, type TrackPt } from '../../components/windows/SolarPlot'
import { TimeScrubber } from '../../components/windows/TimeScrubber'
import { TerrainCanvas } from '../../components/TerrainCanvas'
import { SunArc } from '../../components/viz'
import { Button, cx, Disclosure, EmptyState, Panel, Segmented, Select, Slider, StatusBadge, Tabs } from '../../components/ui'
import { SITES, siteById } from '../../data/sites'
import { NOT_REPRODUCIBLE } from '../../data/sources'
import type { Site } from '../../data/types'
import { regionById } from '../../lib/assess'
import { EASE } from '../../lib/motion'
import { compass, dayWindows, fmtDur, fmtMin, MONTHS, monthSummary, relBearing, shadowRatio, sunAt } from '../../lib/solar'
import { useApp } from '../../lib/store'

const fmtDate = (d: string, long = true) => `${+d.slice(8)} ${long ? MONTHS[+d.slice(5, 7) - 1] : MONTHS[+d.slice(5, 7) - 1].slice(0, 3)} ${d.slice(0, 4)}`
const fmtCoord = (s: Site) => `${Math.abs(s.lat).toFixed(2)}°${s.lat >= 0 ? 'N' : 'S'} ${Math.abs(s.lon).toFixed(2)}°${s.lon >= 0 ? 'E' : 'W'}`

export default function Windows() {
  const { selectedId, select, results } = useApp()
  const site = siteById(selectedId)
  if (!site) {
    const quick = (results.length ? results : SITES.map((s) => s.id)).slice(0, 4).map((id) => siteById(id)!)
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <EmptyState
          title="Choose an Earth site first"
          body="Rehearsal windows depend on where you test. Pick a candidate below, or explore the map to compare sites."
          action={
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              {quick.map((s) => (
                <Button key={s.id} onClick={() => select(s.id)}>
                  {s.name}
                </Button>
              ))}
              <a href="#/app/analogs" className="inline-flex min-h-11 items-center rounded-[var(--radius-md)] px-4 text-[15px] font-medium text-amber underline-offset-4 hover:underline">
                Open the analog map →
              </a>
            </div>
          }
        />
      </div>
    )
  }
  return <Explorer key={site.id} site={site} />
}

function Chip({ active, onClick, children }: { active?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      className={cx('min-h-11 rounded-full border px-3.5 text-[13px] transition-[background-color,color,transform] duration-[var(--duration-fast)] ease-[var(--ease-out)] active:scale-[0.97] md:min-h-9', active ? 'border-amber bg-amber-soft text-amber' : 'border-[var(--line-strong)] text-silver-300 hover:bg-white/8 hover:text-paper')}>
      {children}
    </button>
  )
}

function BandBadge({ inside }: { inside: boolean }) {
  const Icon = inside ? CircleCheck : CircleMinus
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[12px] font-medium leading-5 whitespace-nowrap', inside ? 'border-amber/50 bg-amber-soft text-amber' : 'border-silver-500 bg-white/4 text-silver-300')}>
      <Icon size={14} aria-hidden strokeWidth={2.2} />
      {inside ? 'Inside lunar reference band' : 'Outside band'}
    </span>
  )
}

function Explorer({ site }: { site: Site }) {
  const { mission, date, minute, setWhen, setMinute, heading, setHeading, lighting, setLighting, lampEl, setLampEl, select } = useApp()
  const { elMin: lo, elMax: hi, minDuration: minDur } = mission
  const region = regionById(mission.regionId)
  const tz = site.tzLabel.split(' ')[0]
  const natural = lighting === 'natural'

  const [view, setView] = useState({ y: +date.slice(0, 4), m: +date.slice(5, 7) })
  const [zoom, setZoom] = useState(false)
  const [tab, setTab] = useState<'windows' | 'lighting' | 'why'>('windows')
  const [caveat, setCaveat] = useState(false)
  // One visual language for change: markers and shadows move. They follow input 1:1 while dragging and only ease on a jump.
  const [smooth, setSmooth] = useState(false)
  const drag = (fn: (v: number) => void) => (v: number) => {
    setSmooth(false)
    fn(v)
  }
  const jump = (fn: () => void) => () => {
    setSmooth(true)
    fn()
  }
  useEffect(() => setView({ y: +date.slice(0, 4), m: +date.slice(5, 7) }), [date])
  const moveMonth = (d: number) =>
    setView((v) => {
      const t = v.m - 1 + d
      return { y: v.y + Math.floor(t / 12), m: (((t % 12) + 12) % 12) + 1 }
    })

  const days = useMemo(() => monthSummary(site, view.y, view.m, lo, hi, minDur), [site, view, lo, hi, minDur])
  const day = useMemo(() => dayWindows(site, date, lo, hi, minDur), [site, date, lo, hi, minDur])
  const passes = useMemo(() => dayWindows(site, date, lo, hi, 5), [site, date, lo, hi])
  // On entering (or switching site) start inside a qualifying window so the previews open lit, not dark.
  useEffect(() => {
    const first = day.segments[0]
    if (first && !day.segments.some((g) => minute >= g.startMin && minute <= g.endMin)) setMinute(first.startMin + 5)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site.id])
  const track = useMemo<TrackPt[]>(
    () => Array.from({ length: 145 }, (_, i) => {
      const m = Math.min(i * 10, 1439)
      return { m, ...sunAt(site, date, m) }
    }),
    [site, date],
  )
  const dayMax = track.reduce((a, b) => (b.el > a.el ? b : a))
  const dayMin = Math.min(...track.map((p) => p.el))

  const sun = sunAt(site, date, minute)
  const light = natural ? sun : { el: lampEl, az: heading }
  const below = natural && sun.el <= 0
  const inBand = !below && light.el >= lo && light.el <= hi
  const active = day.segments.find((s) => minute >= s.startMin && minute <= s.endMin)
  const ratio = shadowRatio(light.el)
  const rel = relBearing(heading, light.az)
  const clockStr = `${fmtMin(minute)} ${tz}`

  const sunSide = (s: (typeof day.segments)[number]) => `${s.rising ? 'Sun rising' : 'Sun setting'} ${fmtMin(s.startMin)}–${fmtMin(s.endMin)}`
  const description = `Sun altitude–azimuth track for ${fmtDate(date)} at ${site.name}. Daily elevation from ${dayMin.toFixed(1)}° to ${dayMax.el.toFixed(1)}°. Lunar reference band ${lo} to ${hi} degrees. ${
    day.segments.length ? `Qualifying windows: ${day.segments.map(sunSide).join('; ')}.` : 'No qualifying window on this date.'
  }${natural ? ` Selected time ${clockStr}: elevation ${sun.el.toFixed(1)}°, azimuth ${sun.az.toFixed(0)}°.` : ` Artificial lamp at ${lampEl}° elevation shown as a dashed reference.`}`

  const month = +date.slice(5, 7) - 1
  const riskWord = { L: 'Low', M: 'Moderate', H: 'High' }[site.seasonalRisk[month]] ?? 'Moderate'
  const longest = Math.max(0, ...passes.segments.map((s) => s.durationMin))
  const rules: { ok: boolean | null; title: string; detail: string }[] = [
    { ok: passes.segments.length > 0, title: `Sun enters the ${lo}–${hi}° band`, detail: `Daily sun elevation spans ${dayMin.toFixed(1)}° to ${dayMax.el.toFixed(1)}° on this date.` },
    { ok: longest >= minDur, title: `Stays in band for at least ${minDur} min`, detail: longest ? `Longest single pass: ${fmtDur(longest)}.` : 'No pass through the band on this date.' },
    { ok: !!active, title: 'Selected time is inside a qualifying window', detail: active ? `${clockStr} falls in ${sunSide(active).toLowerCase()}.` : `${clockStr} is outside every qualifying window for this date.` },
    { ok: null, title: 'Natural sunlight only', detail: 'Windows use direct sun from a simplified model. Artificial lighting is a different condition (see Lighting).' },
  ]

  const nextDays = days.filter((d) => d.segments.length && d.date !== date).slice(0, 6)
  const terrainEl = natural ? (below ? 0 : Math.max(0.3, sun.el)) : lampEl
  const terrainAz = light.az
  const noon = dayMax.m

  const relText =
    !natural ? 'Lamp rig is mounted ahead of the rover: its azimuth follows the heading.' : Math.abs(rel) <= 45 ? 'Driving into the sun: glare and long shadows ahead.' : Math.abs(rel) >= 135 ? 'Sun behind: shadows fall ahead of the rover.' : 'Cross-sun: shadows fall across the path.'
  const relNum = natural ? `Sun ${Math.abs(Math.round(rel))}° ${Math.abs(rel) < 1 ? 'dead ahead' : Math.abs(rel) > 179 ? 'directly behind' : rel > 0 ? 'right of heading' : 'left of heading'}` : 'Lamp 0° — dead ahead'

  const scrubber = <TimeScrubber minute={minute} onChange={drag(setMinute)} segments={day.segments} tz={tz} smooth={smooth} label={`Local time · ${fmtDate(date, false)}`} />

  return (
    <div className="mx-auto w-full max-w-[1680px] px-3 pb-16 md:px-6">
      <header className="pt-6 pb-2 md:pt-8">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
          <div className="min-w-0">
            <h1 className="font-display text-[32px] md:text-[44px]">Rehearsal windows</h1>
            <p className="mt-1.5 text-[16px] text-silver-300">
              <span className="font-medium text-paper">{site.name}</span> · {site.place}
            </p>
          </div>
          <div className="w-full max-w-xs">
            <Select label="Candidate site" value={site.id} onChange={select} options={SITES.map((s) => ({ value: s.id, label: s.name }))} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px] text-silver-300">
          <span className="mono">{fmtCoord(site)}</span>
          <span className="mono">{site.tzLabel}</span>
          <span>{region.name}</span>
          <span className="mono text-amber">{lo}–{hi}° · ≥ {minDur} min</span>
          <button type="button" aria-expanded={caveat} aria-controls="caveat" onClick={() => setCaveat((v) => !v)}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-amber/40 px-3 text-[12px] font-medium text-amber transition-[background-color,transform] hover:bg-amber-soft active:scale-[0.97] md:min-h-8">
            <Info size={14} aria-hidden /> Illustrative · simplified solar model <ChevronDown size={14} aria-hidden className={cx('transition-transform duration-[var(--duration-fast)]', caveat && 'rotate-180')} />
          </button>
        </div>
        {caveat && <p id="caveat" className="mt-2 max-w-3xl text-[13px] leading-snug text-silver-300">Not a validated prediction: the model ignores terrain horizon, atmospheric refraction, daylight-saving time and weather. Window dates are for discussion only.</p>}
      </header>

      {/* Mobile: the time scrubber stays reachable while scrolling the shadow previews */}
      <div className="glass sticky top-[var(--topbar-h)] z-30 -mx-3 border-b border-[var(--line)] px-3 pt-1 md:hidden">
        {scrubber}
        <p className="mono pb-2 text-[12px] text-silver-300" aria-live="polite">
          {natural ? 'Sun' : 'Lamp'} el {light.el.toFixed(1)}° · az {light.az.toFixed(0)}° {compass(light.az)} · {below ? 'below horizon' : inBand ? 'inside band' : 'outside band'}
        </p>
      </div>

      <div className="mt-6 grid gap-x-10 gap-y-10 md:grid-cols-[minmax(0,296px)_minmax(0,1fr)] xl:grid-cols-[minmax(0,296px)_minmax(0,1fr)_minmax(0,340px)]">
        {/* ── Date */}
        <div className="space-y-8">
          <Panel title="Date">
            <div className="-mx-3 sm:mx-0">
              <DayCalendar y={view.y} m={view.m} days={days} selected={date} onSelect={(d) => { setSmooth(true); setWhen(d, dayWindows(site, d, lo, hi, minDur).segments[0]?.startMin) }} onMonth={moveMonth} />
            </div>
          </Panel>
          <Panel title={`Sun that day · ${fmtDate(date, false)}`} aside={<span className="mono text-[12px] text-amber">{day.minutes ? `${day.minutes} min in band` : 'no window'}</span>}>
            <SunArc site={site} date={date} lo={lo} hi={hi} minDur={minDur} minute={minute} w={296} h={56} className="h-auto w-full" />
          </Panel>
          {nextDays.length > 0 && (
            <Panel title="Other qualifying days">
              <div className="flex flex-wrap gap-2">
                {nextDays.map((d) => (
                  <Chip key={d.date} active={d.date === date} onClick={jump(() => setWhen(d.date, d.segments[0].startMin))}>
                    {fmtDate(d.date, false).slice(0, -5)} · <span className="mono">{d.minutes}m</span>
                  </Chip>
                ))}
              </div>
            </Panel>
          )}
        </div>

        {/* ── One instrument: sun position → timeline → readout → the shadows it casts */}
        <div className="min-w-0 space-y-10">
          <Panel title="Sun position" aside={<Segmented label="Plot scale" value={zoom ? 'z' : 'f'} onChange={(v) => setZoom(v === 'z')} options={[{ value: 'f', label: 'Full day' }, { value: 'z', label: 'Low-sun zoom' }]} />}>
            <figure>
              <SolarPlot site={site} date={date} track={track} segments={day.segments} lo={lo} hi={hi} sun={sun} mode={lighting} lampEl={lampEl} heading={heading} zoom={zoom} smooth={smooth} description={description} />
              <figcaption className="mt-2 text-[12px] leading-snug text-silver-400">
                Azimuth (N = 0°, clockwise) · elevation · <span className="text-amber">thick amber</span> = in band ≥ {minDur} min
              </figcaption>
            </figure>

            <div className="mt-3 hidden md:block">{scrubber}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {day.segments.map((s) => (
                <Chip key={s.startMin} active={minute === s.startMin} onClick={jump(() => setMinute(s.startMin))}>
                  {s.rising ? 'Rise' : 'Set'} window <span className="mono">{fmtMin(s.startMin)}</span>
                </Chip>
              ))}
              <Chip active={minute === noon} onClick={jump(() => setMinute(noon))}>
                Solar noon <span className="mono">{fmtMin(noon)}</span>
              </Chip>
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
              {[
                ['Local date & time', `${fmtDate(date, false)} ${clockStr}`],
                [natural ? 'Solar elevation' : 'Lamp elevation', `${light.el.toFixed(1)}°`],
                [natural ? 'Solar azimuth' : 'Lamp azimuth', `${light.az.toFixed(0)}° ${compass(light.az)}`],
                ['1 m rock shadow', below ? 'sun below horizon' : ratio > 99 ? '> 99 m' : `≈ ${ratio.toFixed(ratio < 10 ? 2 : 1)} m`],
              ].map(([k, v]) => (
                <div key={k} className="min-w-0">
                  <dt className="text-[12px] text-silver-400">{k}</dt>
                  <dd className="mono mt-0.5 text-[15px] break-words text-paper" aria-live="polite">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <BandBadge inside={inBand} />
              {below && <span className="inline-flex items-center gap-1.5 text-[12px] text-silver-300"><Moon size={14} aria-hidden /> Sun below horizon</span>}
            </div>
          </Panel>

          <Panel title="Shadows at this moment">
            <div className="grid gap-4 sm:grid-cols-2">
              {([
                ['moon', region.seed, 'Lunar reference terrain', 'text-silver-300'],
                ['earth', site.seed, 'Earth candidate', 'text-cyan'],
              ] as const).map(([kind, seed, title, cls]) => (
                <figure key={kind}>
                  <div className="relative aspect-[7/4] overflow-hidden rounded-[var(--radius-sm)] bg-ink-950">
                    <TerrainCanvas kind={kind} seed={seed} el={terrainEl} az={terrainAz} label={`${title} (illustrative synthetic terrain) lit from azimuth ${terrainAz.toFixed(0)}° at ${terrainEl.toFixed(1)}° elevation`} />
                    {below && <div className="absolute inset-0 grid place-items-center bg-ink-950/75 text-[13px] text-silver-300">Sun below horizon</div>}
                  </div>
                  <figcaption className={cx('mt-1.5 text-[13px]', cls)}>{title}</figcaption>
                </figure>
              ))}
            </div>
            <p className="mt-3 text-[12px] leading-snug text-silver-400">
              Illustrative synthetic terrain · 10 m/px · ×3 exaggeration · lit at the current {natural ? 'sun' : 'lamp'} geometry.
            </p>
          </Panel>
        </div>

        {/* ── Inspector: one group at a time (overview → selection → inspection → evidence) */}
        <div className="grid min-w-0 gap-8 md:col-span-2 md:grid-cols-2 md:items-start xl:col-span-1 xl:grid-cols-1">
          <section aria-label="Inspector" className="border-t border-[var(--line)] pt-4">
            <Segmented label="Lighting mode" value={lighting} onChange={(v) => { setLighting(v); if (v === 'artificial') setTab('lighting') }} options={[{ value: 'natural', label: 'Natural sun' }, { value: 'artificial', label: 'Artificial lamp rig' }]} />
            <div className="mt-4"><Tabs label="Inspector" value={tab} onChange={setTab} tabs={[{ id: 'windows', label: 'Windows' }, { id: 'lighting', label: 'Lighting' }, { id: 'why', label: 'Why' }]} /></div>
            {/* Instant switch; the incoming group only fades in (120 ms), nothing exits. */}
            <motion.div key={tab} role="tabpanel" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.12, ease: EASE }} className="pt-4">
              {tab === 'windows' && (
                <>
                  {!natural && <p className="mb-3 text-[12px] text-silver-400">Natural sun only; a lamp rig can run any time.</p>}
                  {day.segments.length ? (
                    <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
                      {day.segments.map((s) => {
                        const on = active === s
                        const Icon = s.rising ? Sunrise : Sunset
                        return (
                          <li key={s.startMin}>
                            <button type="button" onClick={jump(() => setMinute(s.startMin))} aria-pressed={on} aria-label={`${s.rising ? 'Sun rising' : 'Sun setting'} ${fmtMin(s.startMin)} to ${fmtMin(s.endMin)}, ${fmtDur(s.durationMin)}`}
                              className={cx('flex min-h-11 w-full items-start gap-3 border-l-2 py-3 pl-3 text-left transition-colors duration-[var(--duration-fast)] active:bg-white/8', on ? 'border-amber bg-amber-soft' : 'border-transparent hover:bg-white/5')}>
                              <Icon size={18} aria-hidden className="mt-0.5 shrink-0 text-amber" />
                              <span className="min-w-0 flex-1 pr-2">
                                <span className="flex items-baseline justify-between gap-2 text-[14px]">
                                  <span className="mono text-paper">{fmtMin(s.startMin)}–{fmtMin(s.endMin)}</span>
                                  <span className="mono text-[12px] text-silver-400">{fmtDur(s.durationMin)}</span>
                                </span>
                                <span aria-hidden className="relative mt-1.5 block h-1.5 rounded-full bg-white/8"><span className="absolute inset-y-0 rounded-full bg-amber" style={{ left: `${(s.startMin / 1440) * 100}%`, width: `${Math.max(1.5, (s.durationMin / 1440) * 100)}%` }} /></span>
                                <span className="mono mt-1.5 block text-[12px] text-silver-300">{s.elStart.toFixed(1)}° → {s.elEnd.toFixed(1)}° · {s.azStart.toFixed(0)}° {compass(s.azStart)} → {s.azEnd.toFixed(0)}° {compass(s.azEnd)}</span>
                              </span>
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  ) : (
                    <p className="border-l-2 border-silver-500 pl-3 text-[13px] text-silver-300"><span className="font-medium text-paper">No window this day.</span> {longest ? `Sun is in band for at most ${fmtDur(longest)}.` : `Sun spans ${dayMin.toFixed(1)}° to ${dayMax.el.toFixed(1)}°.`}</p>
                  )}
                </>
              )}
              {tab === 'lighting' && (
                <div className="space-y-4 text-[13px] leading-snug text-silver-300">
                  {natural ? (
                    <p>Direct sun from the simplified model: the only source that produces the windows here.</p>
                  ) : (
                    <>
                      <Slider label="Lamp elevation" value={lampEl} min={0.5} max={10} step={0.5} unit="°" onChange={drag(setLampEl)} hint="Lamp azimuth follows the rover heading." />
                      <p>A lamp rig is a <span className="font-medium text-paper">different lighting condition</span>: finite distance, diverging beam, no solar angular diameter.</p>
                      <StatusBadge status="not-assessed" />
                      <p className="text-silver-400">Needs photometric characterisation; it does not replace natural low-sun validation.</p>
                    </>
                  )}
                  <ElevationBars lo={lo} hi={hi} el={light.el} natural={natural} below={below} inBand={inBand} />
                </div>
              )}
              {tab === 'why' && (
                <div>
                  <ul className="space-y-2.5">
                    {rules.map((r) => {
                      const Icon = r.ok === null ? Info : r.ok ? CircleCheck : CircleX
                      return (
                        <li key={r.title} className="flex gap-3">
                          <Icon size={18} aria-hidden className={cx('mt-0.5 shrink-0', r.ok === null ? 'text-silver-400' : r.ok ? 'text-ok' : 'text-bad')} />
                          <p className="text-[13px] leading-snug"><span className="font-medium text-paper">{r.title}</span> <span className="mono text-[12px] text-silver-400">{r.ok === null ? 'scope' : r.ok ? 'met' : 'not met'}</span></p>
                        </li>
                      )
                    })}
                  </ul>
                  <div className="mt-5">
                    <p className="text-[12px] text-silver-400">Weather limitation by month (illustrative)</p>
                    <div role="img" aria-label={`Qualitative weather-limitation risk by month: ${MONTHS.map((m, i) => `${m} ${{ L: 'low', M: 'moderate', H: 'high' }[site.seasonalRisk[i]]}`).join(', ')}`} className="mt-2">
                      <div className="grid grid-cols-12 gap-0.5">
                        {site.seasonalRisk.split('').map((c, i) => (
                          <span key={i} className={cx('mono grid h-9 place-items-center rounded-[3px] text-[12px]', c === 'H' ? 'bg-bad/25 text-bad' : c === 'M' ? 'bg-white/10 text-silver-200' : 'bg-ok/15 text-ok', i === month && 'ring-1 ring-amber ring-offset-1 ring-offset-ink-900')}>{c}</span>
                        ))}
                      </div>
                      <div aria-hidden className="mt-0.5 grid grid-cols-12 text-center text-[12px] text-silver-500">{MONTHS.map((m) => <span key={m}>{m[0]}</span>)}</div>
                    </div>
                    <p className="mt-2 text-[13px] text-paper">{riskWord} risk in {MONTHS[month]}</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px] text-silver-300">{site.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
                  </div>
                  <Disclosure title={<span className="text-[13px] font-medium">What a window cannot reproduce</span>}>
                    <ul className="space-y-2">{NOT_REPRODUCIBLE.map((n) => <li key={n.id}><span className="font-medium text-paper">{n.label}.</span> {n.detail}</li>)}</ul>
                  </Disclosure>
                </div>
              )}
            </motion.div>
          </section>

          <Panel title="Rover direction">
            <RoverCompass heading={heading} lightAz={light.az} lightLabel={natural ? 'Sun' : 'Lamp'} dim={below} smooth={smooth} />
            <div className="mt-2">
              <Slider label="Rover heading" value={heading} min={0} max={359} unit="°" onChange={drag(setHeading)} format={(v) => `${v}° ${compass(v)}`} />
            </div>
            {natural && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={jump(() => setHeading(Math.round(light.az) % 360))}>Toward sun</Button>
                <Button size="sm" onClick={jump(() => setHeading(Math.round(light.az + 180) % 360))}>Away from sun</Button>
                <Button size="sm" onClick={jump(() => setHeading(Math.round(light.az + 90) % 360))}>Cross-sun</Button>
              </div>
            )}
            <p className="mono mt-3 text-[13px] text-paper">{relNum}</p>
            <p className="mt-1 text-[13px] text-silver-300" aria-live="polite">{relText}{below && ' (sun below horizon)'}</p>
          </Panel>
        </div>
      </div>
    </div>
  )
}

/** Two aligned bars: lunar reference band vs the Earth sun (or lamp) elevation, with text result. */
function ElevationBars({ lo, hi, el, natural, below, inBand }: { lo: number; hi: number; el: number; natural: boolean; below: boolean; inBand: boolean }) {
  const MAX = 12
  const pct = (v: number) => Math.min(100, Math.max(0, (v / MAX) * 100))
  const over = el > MAX
  return (
    <div>
      <div className="grid grid-cols-[96px_minmax(0,1fr)] items-center gap-x-3 gap-y-2.5">
        <span className="text-[12px] text-silver-300">Lunar band</span>
        <div className="relative h-3 rounded-full bg-white/6" aria-hidden>
          <div className="absolute inset-y-0 rounded-full bg-silver-300" style={{ left: `${pct(lo)}%`, width: `${Math.max(2, pct(hi) - pct(lo))}%` }} />
        </div>
        <span className="text-[12px] text-cyan">{natural ? 'Earth sun now' : 'Lamp elevation'}</span>
        <div className="relative h-3 rounded-full bg-white/6" aria-hidden>
          <div className="absolute inset-y-0 -translate-x-1/2" style={{ left: `${over ? 98 : pct(Math.max(0, el))}%` }}>
            <div className="h-3 w-1.5 rounded-full bg-cyan ring-2 ring-ink-900" />
          </div>
        </div>
        <span aria-hidden />
        <div className="mono relative h-4 text-[12px] text-silver-500" aria-hidden>
          {[0, 6, 12].map((v) => (
            <span key={v} className="absolute -translate-x-1/2" style={{ left: `${pct(v)}%` }}>{v}°</span>
          ))}
        </div>
      </div>
      <p className="mt-2 flex items-start gap-2 text-[13px] text-paper" aria-live="polite">
        {inBand ? <CircleCheck size={16} aria-hidden className="mt-0.5 shrink-0 text-amber" /> : <CircleMinus size={16} aria-hidden className="mt-0.5 shrink-0 text-silver-400" />}
        <span>
          {below ? 'Sun is below the horizon' : `${natural ? 'Earth sun' : 'Lamp'} at ${el.toFixed(1)}°`}
          {over && ' (scale ends at 12°)'} — {below ? 'outside' : inBand ? 'inside' : 'outside'} the {lo}–{hi}° lunar reference band.
        </span>
      </p>
    </div>
  )
}
