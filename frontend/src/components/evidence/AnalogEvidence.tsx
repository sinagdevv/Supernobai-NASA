import { Play } from 'lucide-react'
import { assessKey, useEvidence, type AssessEntry, type RehearsalEntry } from '../../lib/api/evidence'
import { explain } from '../../lib/api/explain'
import type { StoredDataset } from '../../lib/api/types'
import type { Planet } from '../../lib/planet'
import { earthTarget, headline, type RehearsalTarget } from '../../lib/rehearsal'
import { analogTarget, tally } from '../../lib/suitability'
import { Button } from '../ui'
import { CompactAssessment } from './ComputedEvidence'
import { EvidenceChip, NotValidatedChip, OverallChip } from './chips'

/** The target a stored Earth dataset is evaluated on for this planet's criteria, or null when the dataset has no footprint to evaluate. */
export function analogFor(planet: Planet, d: StoredDataset): RehearsalTarget | null {
  const e = earthTarget(d)
  return e ? analogTarget(planet, e) : null
}

/** One line on what Layer 4 has for a target: computed (with its headline), running, failed, or not run. */
export function L4Line({ entry, planet }: { entry: RehearsalEntry | undefined; planet: Planet }) {
  if (entry?.data) return <p className="text-xs leading-snug text-silver-300"><span className="font-medium text-paper">Rehearsal windows:</span> computed. {headline(entry.data).text}</p>
  if (entry?.loading) return <p className="text-xs text-silver-300">Rehearsal windows: computing…</p>
  if (entry?.error) return <p className="text-xs leading-snug text-silver-300"><span className="font-medium text-paper">Rehearsal windows:</span> the calculation failed ({entry.error.code}). None is reported.</p>
  return <p className="text-xs leading-snug text-silver-400"><span className="font-medium text-silver-300">Rehearsal windows:</span> {planet === 'mars' ? 'not applicable to an Earth analog under Mars criteria; Earth’s sun is not the Martian sun.' : <>not run, so illumination criteria stay indeterminate. <a className="font-medium text-amber underline-offset-2 hover:underline" href="#/app/windows">Compute in Rehearsal Windows</a></>}</p>
}

/** The assessment state for one target: nothing yet, running, failed, or the overall verdict with a tally. */
export function L5Summary({ entry }: { entry: AssessEntry | undefined }) {
  if (entry?.data) {
    const t = tally(entry.data)
    return (
      <div className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2"><OverallChip verdict={entry.data.overall_status} className="text-xs" /><EvidenceChip kind="computed" /><NotValidatedChip /></div>
        <p className="mono text-xs text-silver-300">{t.pass} pass · {t.fail} fail · {t.claim} unverified · {t.missing} missing</p>
      </div>
    )
  }
  if (entry?.loading) return <p role="status" className="text-xs text-silver-300">Assessing…</p>
  if (entry?.error) return <p role="alert" className="text-xs leading-snug text-bad">The assessment failed ({entry.error.code}). {explain(entry.error).text} None is shown.</p>
  return <p className="text-xs leading-snug text-silver-400">Not assessed. No verdict exists for this dataset yet; that is not a pass.</p>
}

/** Layer 5 evidence for the stored Earth dataset selected on the map. It runs when asked, never as a side effect of looking. */
export function AnalogEvidence({ planet, dataset }: { planet: Planet; dataset: StoredDataset }) {
  const ev = useEvidence()
  const t = analogFor(planet, dataset)
  if (!t) return <p className="text-xs text-silver-400">This dataset has no footprint to assess.</p>
  const entry = ev.assessments[assessKey(planet, t.key)]
  const l4 = planet === 'moon' ? ev.rehearsal[t.key] : undefined
  return (
    <div className="space-y-2.5">
      <p className="text-xs leading-snug text-silver-400">Assesses this dataset against the {planet === 'moon' ? 'lunar' : 'Mars'} criteria set in Mission: {planet === 'moon' ? 'a 0.1° window at 30 m' : 'the whole region at 926 m'}.</p>
      <L4Line entry={l4} planet={planet} />
      <Button size="sm" variant="secondary" className="w-full" onClick={() => ev.assessTarget(planet, t)} disabled={entry?.loading}><Play size={14} aria-hidden />{entry?.data ? 'Assess again' : 'Assess with Layer 5'}</Button>
      <L5Summary entry={entry} />
      {entry?.data && (
        <details className="text-xs text-silver-300">
          <summary className="min-h-11 cursor-pointer py-2.5 text-silver-200">Criteria and gaps</summary>
          <CompactAssessment a={entry.data} loading={entry.loading} />
        </details>
      )}
    </div>
  )
}
