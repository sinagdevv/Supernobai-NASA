import LiveEvidence from '../../components/LiveEvidence'
import MarsReference from '../../components/MarsReference'

/** Mars Comparison: measured Martian terrain against measured Earth terrain, per criterion at one stated scale. No verdict, no score. */
export function MarsCompare() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8 lg:py-12">
      <h1 className="font-display text-[38px] font-medium md:text-[48px]">Jezero against Earth</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-silver-300">Measured terrain on both sides, criterion by criterion, at one stated scale. A match at 926 m is not a suitability verdict.</p>
      <LiveEvidence planet="mars" />
    </div>
  )
}

const TAG = { measured: 'border-cyan/50 text-cyan', scope: 'border-[var(--line-strong)] text-silver-300', limits: 'border-[var(--line-strong)] text-silver-300', pending: 'border-amber/50 text-amber' } as const
const TAG_LABEL = { measured: 'Measured', scope: 'Scope', limits: 'Limits', pending: 'Pending' } as const

const Section = ({ n, title, tag, children }: { n: string; title: string; tag: keyof typeof TAG; children: React.ReactNode }) => (
  <section className="border-t border-[var(--line)] py-7">
    <h2 className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[17px] font-semibold">
      <span className="mono text-[13px] font-normal text-silver-400">{n}</span>{title}
      <span className={`mono rounded-[var(--radius-sm)] border px-2 py-0.5 text-[12px] font-normal ${TAG[tag]}`}>{TAG_LABEL[tag]}</span>
    </h2>
    <div className="mt-4">{children}</div>
  </section>
)

/** Mars Dossier: a preliminary evidence summary. Each section says whether it is measured, a scope statement, a limit, or pending. */
export function MarsDossier() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8 lg:py-12">
      <p className="eyebrow">Mars · Jezero regional terrain</p>
      <h1 className="font-display mt-3 text-[38px] font-medium md:text-[54px]">Terrain evidence dossier</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-silver-300">A preliminary summary of measured terrain. It is not a mission assessment and carries no certification.</p>

      <Section n="01" tag="measured" title="Planetary reference"><MarsReference /></Section>
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
      <Section n="06" tag="pending" title="Pending in the platform">
        <p className="max-w-2xl text-[14px] text-silver-300"><span className="font-medium text-paper">Layer 4</span> (solar geometry and rehearsal windows) and <span className="font-medium text-paper">Layer 5</span> (mission suitability and evidence) are not built: no rehearsal window and no suitability classification exists for Mars. This page is not stored. Layer 6 (research storage and reporting) is a separate service with its own database and is not connected to the interface.</p>
      </Section>
    </div>
  )
}
