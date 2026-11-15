import LiveEvidence from '../../components/LiveEvidence'
import MarsReference from '../../components/MarsReference'
import { ComputedEvidence } from '../../components/evidence/ComputedEvidence'
import { PageHeader } from '../../components/ui/Page'

/** Mars Comparison: measured Martian terrain against measured Earth terrain, per criterion at one stated scale. No verdict, no score. */
export function MarsCompare() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8 lg:py-12">
      <PageHeader eyebrow="Mars · Jezero regional terrain · Earth candidate" title="Jezero against Earth" lede="Measured terrain on both sides, criterion by criterion, at one stated scale. A match at 926 m is not a suitability verdict." />
      <LiveEvidence planet="mars" />
    </div>
  )
}

const TAG = { measured: 'border-cyan/50 text-cyan', computed: 'border-cyan/50 text-cyan', scope: 'border-[var(--line-strong)] text-silver-300', limits: 'border-[var(--line-strong)] text-silver-300', pending: 'border-amber/50 text-amber' } as const
const TAG_LABEL = { measured: 'Measured', computed: 'Computed · not stored', scope: 'Scope', limits: 'Limits', pending: 'Pending' } as const

const Section = ({ n, title, tag, children }: { n: string; title: string; tag: keyof typeof TAG; children: React.ReactNode }) => (
  <section className="border-t border-[var(--line)] py-7">
    <h2 className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[17px] font-semibold">
      <span className="mono text-[13px] font-normal text-silver-400">{n}</span>{title}
      <span className={`mono rounded-[var(--radius-sm)] border px-2 py-0.5 text-xs font-normal ${TAG[tag]}`}>{TAG_LABEL[tag]}</span>
    </h2>
    <div className="mt-4">{children}</div>
  </section>
)

/** Mars Dossier: a preliminary evidence summary. Each section says whether it is measured, a scope statement, a limit, or pending. */
export function MarsDossier() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8 lg:py-12">
      <PageHeader eyebrow="Mars · Jezero regional terrain" title="Terrain evidence dossier" lede="A preliminary summary of measured terrain, with the Layer 4 and 5 results you have computed. It is not stored, not validated, and carries no certification." />

      <Section n="01" tag="measured" title="Planetary reference"><MarsReference heading="h3" /></Section>
      <Section n="02" tag="scope" title="Mission objective">
        <p className="max-w-2xl text-[15px] text-silver-300">Regional terrain characterisation for Martian rover mobility. A screening of terrain statistics only; it does not assess whether a rover could traverse the ground.</p>
      </Section>
      <Section n="03" tag="measured" title="Earth analog and comparison"><LiveEvidence planet="mars" /></Section>
      <Section n="04" tag="limits" title="Uncertainty and what is not measured">
        <ul className="list-disc space-y-1.5 pl-5 text-[14px] text-silver-300">
          <li>The Martian terrain is 463 m MOLA data. Slopes from 463 m to about 1.8 km are measured; rover-scale slope, rocks and wheel traction are not represented.</li>
          <li>Heights are relative to the MOLA areoid, with at least 3 m of vertical uncertainty; interpolated cells cannot be told from measured ones.</li>
          <li>Earth candidates are 30 m surface models aggregated to 926 m, so the comparison only holds at that regional scale.</li>
          <li>Gravity (3.73 m/s²), the thin dusty atmosphere, temperature, radiation and regolith cannot be reproduced on Earth and are not modelled.</li>
        </ul>
      </Section>
      <Section n="05" tag="limits" title="Additional verification required">
        <ul className="list-disc space-y-1.5 pl-5 text-[14px] text-silver-300">
          <li>Metre-scale terrain from a HiRISE or CTX digital terrain model of the specific site.</li>
          <li>Surface material and strength data for the Earth candidate and the Martian site.</li>
        </ul>
      </Section>
      <Section n="06" tag="computed" title="Computed evidence · Layer 4 and 5"><ComputedEvidence planet="mars" /></Section>
      <Section n="07" tag="limits" title="What the computed results are, and are not">
        <ul className="max-w-2xl list-disc space-y-1.5 pl-5 text-[14px] text-silver-300">
          <li>Both are computed by the service, not checked against observations. “Suitable” would only ever mean the thresholds you set were met, never that the ground is safe.</li>
          <li>Rehearsal windows use the 1.85 km MOLA grid (32 pixels per degree); the terrain statistics above use 463 m. The service cannot pair results from different grids, so illumination criteria come back as not assessed.</li>
          <li>About a fifth of the MOLA bins around Jezero have no laser observations. Where the sun’s path crosses them the engine reports insufficient coverage, which is neither shadow nor light.</li>
          <li>This page is not stored. Layer 6 (research storage and reporting) is a separate service with its own database and is not connected to the interface.</li>
        </ul>
      </Section>
    </div>
  )
}
