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
export function MarsNote({ children, label = 'Mars · terrain measured, results computed.' }: { children: React.ReactNode; label?: string }) {
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

/** Martian reference facts, for orientation beside the computed windows. */
export function MarsFacts() {
  return (
    <section aria-labelledby="mars-ref" className="border-t border-[var(--line)] pt-6">
      <h2 id="mars-ref" className="eyebrow">Martian reference, for context</h2>
      <dl className="mt-3 max-w-xl divide-y divide-[var(--line)]">
        {FACTS.map(([k, v]) => (
          <div key={k} className="flex flex-wrap justify-between gap-x-6 gap-y-0.5 py-2.5 text-[14px]"><dt className="text-silver-400">{k}</dt><dd className="mono text-right text-silver-200">{v}</dd></div>
        ))}
      </dl>
      <p className="mt-3 max-w-xl text-xs leading-snug text-silver-400">From the <a className="text-cyan underline underline-offset-2 hover:text-paper" href="https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html" target="_blank" rel="noreferrer noopener">NASA Mars Fact Sheet<span className="sr-only"> (opens in new tab)</span></a>. Shown for orientation only: the solar-geometry engine takes the planet’s orientation from SPICE kernels, not from this table, and it does not model the sky’s scattering of light.</p>
    </section>
  )
}
