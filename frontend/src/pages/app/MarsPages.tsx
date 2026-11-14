import LiveEvidence from '../../components/LiveEvidence'
import MarsReference from '../../components/MarsReference'
import { MarsNote } from '../../components/PlanetNotice'

/** Mars Comparison: measured Martian terrain against measured Earth terrain, per criterion at one stated scale. No verdict, no score. */
export function MarsCompare() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8 lg:py-12">
      <h1 className="font-display text-[38px] font-medium md:text-[48px]">Comparison</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-silver-300">Measured terrain of the Martian reference region beside a measured Earth candidate, criterion by criterion, with the scale and source of each side.</p>
      <div className="mt-6"><MarsNote>Both sides are real measurements, but a terrain comparison at 926 m is not proof that an Earth site suits a Mars experiment. Rover-scale terrain, soil, atmosphere, gravity and lighting are not represented, and the suitability engine (Layer 5) is not built.</MarsNote></div>
      <LiveEvidence planet="mars" />
    </div>
  )
}

const Section = ({ n, title, children }: { n: string; title: string; children: React.ReactNode }) => (
  <section className="border-t border-[var(--line)] py-7">
    <h2 className="text-[17px] font-semibold"><span className="mono mr-3 text-[13px] font-normal text-silver-400">{n}</span>{title}</h2>
    <div className="mt-4">{children}</div>
  </section>
)

/** Mars Dossier: a preliminary evidence summary. Measured results come from the service; everything else is stated as a reference, a gap, or pending. */
export function MarsDossier() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8 lg:py-12">
      <h1 className="font-display text-[38px] font-medium md:text-[48px]">Dossier</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-silver-300">A preliminary Mars terrain evidence summary. It is not a mission assessment and carries no certification.</p>
      <div className="mt-6"><MarsNote>Measured results below come from the Layer 2/3 service. This page is not stored: Layer 6 (research storage and reporting) runs as its own service with a database and is not connected to the interface. Store a run with <span className="mono">terrawindow-report ingest-result</span>.</MarsNote></div>

      <Section n="01" title="Planetary reference, measured"><MarsReference /></Section>
      <Section n="02" title="Mission objective">
        <p className="max-w-2xl text-[15px] text-silver-300">Regional terrain characterisation for Martian rover mobility. This is a screening of terrain statistics only; it does not assess whether a rover could traverse the ground.</p>
      </Section>
      <Section n="03" title="Earth analog and measured comparison"><LiveEvidence planet="mars" /></Section>
      <Section n="04" title="Uncertainty and what is not measured">
        <ul className="list-disc space-y-1.5 pl-5 text-[14px] text-silver-300">
          <li>The Martian terrain is 463 m MOLA data. Slopes between 463 m and about 1.8 km are measured; anything finer is not, and rover-scale slope, rocks and wheel traction are not represented.</li>
          <li>Heights are relative to the MOLA areoid, with at least 3 m of vertical uncertainty; interpolated cells cannot be told from measured ones.</li>
          <li>Earth candidates are 30 m surface models aggregated to 926 m for comparison, so the comparison only holds at that regional scale.</li>
          <li>Gravity (3.73 m/s²), the thin dusty atmosphere, temperature, radiation and regolith cannot be reproduced on Earth and are not modelled here.</li>
        </ul>
      </Section>
      <Section n="05" title="Additional verification required">
        <ul className="list-disc space-y-1.5 pl-5 text-[14px] text-silver-300">
          <li>Metre-scale terrain from a HiRISE or CTX digital terrain model of the specific site.</li>
          <li>Surface material and strength data for the Earth candidate and the Martian site.</li>
        </ul>
      </Section>
      <Section n="06" title="Pending in the platform">
        <p className="max-w-2xl text-[14px] text-silver-300"><span className="font-medium text-paper">Layer 4</span> (solar geometry and rehearsal windows) and <span className="font-medium text-paper">Layer 5</span> (mission suitability and evidence) are not built. No rehearsal window and no suitability classification exists for Mars.</p>
      </Section>
    </div>
  )
}
