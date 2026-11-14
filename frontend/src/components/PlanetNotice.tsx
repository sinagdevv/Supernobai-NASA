import { ArrowRight } from 'lucide-react'
import { PLANET_COPY, usePlanet, type Planet } from '../lib/planet'
import { Segmented } from './ui'

/** The one planet control: same component in the landing hero, the workspace header and the Mission page. */
export function PlanetSwitch({ className }: { className?: string }) {
  const { planet, setPlanet } = usePlanet()
  return (
    <div className={className}>
      <Segmented<Planet> label="Planetary target" value={planet} onChange={setPlanet} options={[{ value: 'moon', label: PLANET_COPY.moon.label }, { value: 'mars', label: PLANET_COPY.mars.label }]} />
    </div>
  )
}

/** What Mars mode is, said once and the same everywhere it applies. */
export function MarsNote({ children, label = 'Mars · terrain measured, nothing assessed.' }: { children: React.ReactNode; label?: string }) {
  return (
    <p role="note" className="mb-6 max-w-3xl border-l-2 border-[var(--planet-ref)] pl-3 text-[13px] leading-relaxed text-silver-300">
      <span className="font-medium text-paper">{label}</span> {children}
    </p>
  )
}

const FACTS: [string, string][] = [
  ['Surface gravity (mean)', '3.73 m/s², about 38 % of Earth’s'],
  ['Solar day (sol)', '≈ 24 h 40 min'],
  ['Obliquity', '25.19°, so there are seasons'],
  ['Surface pressure (mean)', '≈ 640 Pa; 400 to 870 Pa through the year'],
]

const TEXT = {
  windows: { title: 'Rehearsal Windows', body: 'Rehearsal windows need the solar-geometry engine (Layer 4), which is not built, so none is computed for Mars. Mars would also need its own geometry: the sky scatters light and the sun follows a different tilt and day length, so the lunar south-polar logic does not transfer.' },
} as const

/** Shown instead of a lunar-only screen while Mars is selected: says what is missing, gives context, never fabricates a result. */
export function MarsUnavailable({ screen }: { screen: keyof typeof TEXT }) {
  const { setPlanet } = usePlanet()
  const t = TEXT[screen]
  return (
    <div className="mx-auto max-w-[1320px] px-4 py-8 md:px-8 lg:py-12">
      <h1 className="font-display text-[38px] font-medium md:text-[48px]">{t.title}</h1>
      <div className="mt-8 grid gap-x-12 gap-y-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
        <section className="border-t border-[var(--line)] pt-6">
          <p className="mono flex items-center gap-2 text-[12px] tracking-[0.04em] text-silver-300 uppercase"><i aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber" />Layer 4 pending</p>
          <p className="mt-3 max-w-[34rem] text-[16px] leading-[1.6] text-silver-300">{t.body}</p>
          <button type="button" onClick={() => setPlanet('moon')} className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-md text-[15px] font-medium text-amber transition-transform hover:underline active:scale-[0.97]">See the lunar illustration <ArrowRight size={15} aria-hidden /></button>
        </section>
        <section aria-labelledby="mars-ref" className="border-t border-[var(--line)] pt-6">
          <h2 id="mars-ref" className="eyebrow">Martian reference, for context</h2>
          <dl className="mt-3 divide-y divide-[var(--line)]">
            {FACTS.map(([k, v]) => (
              <div key={k} className="flex flex-wrap justify-between gap-x-6 gap-y-0.5 py-2.5 text-[14px]"><dt className="text-silver-400">{k}</dt><dd className="mono text-right text-silver-200">{v}</dd></div>
            ))}
          </dl>
          <p className="mt-3 text-[12px] leading-snug text-silver-400">From the <a className="text-cyan underline underline-offset-2 hover:text-paper" href="https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html" target="_blank" rel="noreferrer noopener">NASA Mars Fact Sheet<span className="sr-only"> (opens in new tab)</span></a>. Shown for orientation only; the prototype uses none of them in a calculation.</p>
        </section>
      </div>
    </div>
  )
}
