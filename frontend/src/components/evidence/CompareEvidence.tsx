import { Play } from 'lucide-react'
import { assessKey, useEvidence } from '../../lib/api/evidence'
import type { StoredDataset } from '../../lib/api/types'
import type { Planet } from '../../lib/planet'
import { PLANET_COPY } from '../../lib/planet'
import { primaryTarget, type RehearsalTarget } from '../../lib/rehearsal'
import { Button } from '../ui'
import { analogFor, L4Line, L5Summary } from './AnalogEvidence'
import { CompactAssessment } from './ComputedEvidence'

function Side({ planet, title, target }: { planet: Planet; title: string; target: RehearsalTarget | null }) {
  const ev = useEvidence()
  if (!target) return <div><h4 className="text-[13px] font-medium text-paper">{title}</h4><p className="mt-1 text-xs leading-snug text-silver-400">No Layer 4 or 5 evidence is defined for this dataset, so none is shown.</p></div>
  const entry = ev.assessments[assessKey(planet, target.key)]
  // A rehearsal result applies to a Moon target, or to the Moon's Earth analog. Mars criteria never carry Earth's sun.
  const showL4 = planet === 'moon' || target.body === 'mars'
  return (
    <div className="min-w-0 space-y-2.5">
      <h4 className="text-[13px] font-medium text-paper">{title}</h4>
      {showL4 ? <L4Line entry={ev.rehearsal[target.key]} planet={planet} /> : <L4Line entry={undefined} planet={planet} />}
      <Button size="sm" variant="secondary" onClick={() => ev.assessTarget(planet, target)} disabled={entry?.loading}><Play size={14} aria-hidden />{entry?.data ? 'Assess again' : 'Assess with Layer 5'}</Button>
      <L5Summary entry={entry} />
      {entry?.data && (
        <details className="text-[13px] text-silver-300">
          <summary className="min-h-11 cursor-pointer py-2.5 text-silver-200">Criteria and gaps</summary>
          <CompactAssessment a={entry.data} loading={entry.loading} />
        </details>
      )}
    </div>
  )
}

/**
 * Layer 4 and Layer 5 for the two datasets compared above: the reference region and the Earth candidate, each against this planet's
 * criteria. Only what the service has returned is shown; a side with nothing run says so, and an unrun side is not a pass.
 */
export function CompareEvidence({ planet, refId, candidate }: { planet: Planet; refId: string; candidate: StoredDataset | undefined }) {
  const prim = primaryTarget(planet)
  const ref = refId === prim.datasetId ? prim : null
  const cand = candidate ? analogFor(planet, candidate) : null
  return (
    <section aria-label="Layer 4 and 5 evidence for the compared datasets" className="mt-8 border-t border-[var(--line)] pt-6">
      <h3 className="text-[15px] font-medium">Rehearsal and suitability evidence</h3>
      <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-silver-300">Computed by the service against the {PLANET_COPY[planet].label} criteria in Mission. It is evidence for each dataset on its own, not a similarity score between them, and none of it is validated against observations.</p>
      <div className="mt-4 grid gap-x-10 gap-y-8 md:grid-cols-2">
        <Side planet={planet} title={PLANET_COPY[planet].reference} target={ref} />
        <Side planet={planet} title="Earth candidate" target={cand} />
      </div>
    </section>
  )
}
