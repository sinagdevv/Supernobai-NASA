import { ArrowRight } from 'lucide-react'
import { assessKey, useEvidence } from '../../lib/api/evidence'
import { explain } from '../../lib/api/explain'
import type { MissionAssessment, RehearsalResult } from '../../lib/api/types'
import type { Planet } from '../../lib/planet'
import { evidenceLines, fmtDuration, headline, primaryTarget, summarize, utc } from '../../lib/rehearsal'
import { CRITERION_META, fmtTarget, fmtValue, OVERALL_META, tally } from '../../lib/suitability'
import { go, type Screen } from '../../lib/router'
import { OverallChip, VerdictChip } from './chips'
import { cx } from '../ui'

/*
 * Computed Layer 4 and Layer 5 results as compact blocks, shared by the Dossier, Comparison and the Explorer. They show
 * exactly what the service returned for this session, say so, and say what is missing when nothing has been run.
 */

export const NOT_STORED = 'Computed — not stored (Layer 6 not connected)'

/** One criterion per line: the verdict, the value (measured or claimed) and the threshold. */
export function CompactAssessment({ a, loading, className }: { a: MissionAssessment; loading?: boolean; className?: string }) {
  const t = tally(a)
  return (
    <div className={cx('space-y-3 [overflow-wrap:anywhere]', loading && 'opacity-60', className)}>
      <OverallChip verdict={a.overall_status} />
      <p className="text-[13px] leading-snug text-paper">{a.overall_explanation}</p>
      <p className="text-xs leading-snug text-silver-400">{OVERALL_META[a.overall_status].caution}</p>
      <p className="mono text-xs text-silver-300">{t.pass} pass · {t.fail} fail · {t.claim} unverified claim · {t.missing} missing evidence</p>
      <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
        {a.criterion_results.map((c) => (
          <li key={c.criterion_id} className="py-2">
            <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1"><span className="min-w-0 text-[13px] text-paper">{c.name}</span><VerdictChip verdict={c.status} /></div>
            <p className="mono mt-1 text-xs text-silver-300">{c.measured_value !== null ? `measured ${fmtValue(c.measured_value, c.unit)}` : c.claimed_value !== null ? `claimed ${fmtValue(c.claimed_value, c.unit)} (unverified)` : 'no value'} <span className="text-silver-400">· needs {fmtTarget(c)}</span></p>
            {CRITERION_META[c.status].tone === 'missing' && <p className="mt-0.5 text-xs leading-snug text-silver-400">{c.explanation}</p>}
          </li>
        ))}
      </ul>
      {a.suitability_gaps.length > 0 && <p className="text-xs leading-snug text-silver-400">{a.suitability_gaps.length} evidence {a.suitability_gaps.length === 1 ? 'gap' : 'gaps'} recorded. Layer 4 values are unverified, and nothing has been checked against observations.</p>}
    </div>
  )
}

export function RehearsalSummary({ r }: { r: RehearsalResult }) {
  const s = summarize(r), h = headline(r)
  return (
    <div className="space-y-2.5">
      <p className="text-[13px] leading-snug text-paper">{h.text}</p>
      <dl className="mono grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-4">
        {[['Span (UTC)', `${utc(r.start_utc).slice(5, 16)} → ${utc(r.end_utc).slice(5, 16)}`], ['Qualifying light', fmtDuration(s.qualifyingSeconds)], ['Peak terrain shadow', `${r.terrain_obstruction_max_percent.toFixed(1)} %`], ['Sample step', `${fmtDuration(r.step_seconds)} (±${fmtDuration(r.boundary_uncertainty_seconds)})`]].map(([k, v]) => (
          <div key={k}><dt className="text-silver-500">{k}</dt><dd className="mt-0.5 text-silver-200">{v}</dd></div>
        ))}
      </dl>
      <p className="text-xs leading-snug text-silver-400">{evidenceLines(r).slice(0, 2).map((l) => `${l.label}: ${l.value.split(' — ')[0]}`).join(' · ')}.</p>
    </div>
  )
}

const Link = ({ to, children }: { to: Screen; children: string }) => (
  <a href={`#/app/${to}`} onClick={() => go({ page: 'app', screen: to })} className="inline-flex min-h-11 items-center gap-1 text-[13px] font-medium text-amber underline-offset-4 hover:underline">{children} <ArrowRight size={14} aria-hidden /></a>
)

/** The planet's own Layer 4 and Layer 5 results for the Dossier. If a result has not been run, it says so and links to where it is run. */
export function ComputedEvidence({ planet, heading: H = 'h3' }: { planet: Planet; heading?: 'h3' | 'h4' }) {
  const ev = useEvidence()
  const t = primaryTarget(planet)
  const l4 = ev.rehearsal[t.key]
  const l5 = ev.assessments[assessKey(planet, t.key)]
  const place = planet === 'moon' ? 'Site01, lunar south pole' : 'Jezero region'
  return (
    <div className="space-y-6">
      <p className="mono text-xs tracking-[0.04em] text-silver-300 uppercase">{NOT_STORED}</p>
      <div>
        <H className="text-[16px] font-semibold text-paper">Rehearsal windows · Layer 4 · {place}</H>
        <div className="mt-2">
          {l4?.data ? <RehearsalSummary r={l4.data} /> : l4?.error ? (
            <p className="text-[13px] leading-snug text-silver-300">The calculation did not complete ({l4.error.code}): {explain(l4.error).text} No window is reported.</p>
          ) : l4?.loading ? <p className="text-[13px] text-silver-300">Computing…</p> : (
            <p className="text-[13px] leading-snug text-silver-300">Not run in this session, so this dossier has no computed window for {place}. <Link to="windows">Compute rehearsal windows</Link></p>
          )}
        </div>
      </div>
      <div>
        <H className="text-[16px] font-semibold text-paper">Suitability assessment · Layer 5 · {place}</H>
        <div className="mt-2">
          {l5?.data ? <CompactAssessment a={l5.data} loading={l5.loading} /> : l5?.error ? (
            <p className="text-[13px] leading-snug text-silver-300">The assessment did not complete ({l5.error.code}): {explain(l5.error).text} No assessment is reported.</p>
          ) : l5?.loading ? <p className="text-[13px] text-silver-300">Assessing…</p> : (
            <p className="text-[13px] leading-snug text-silver-300">Not run in this session, so this dossier has no assessment for {place}. <Link to="mission">Open the Mission workspace</Link></p>
          )}
        </div>
      </div>
      <p className="text-xs leading-snug text-silver-400">Computed by the service for this session and lost on reload. Not checked against observations. Thresholds in the assessment are assumptions set in the Mission workspace.</p>
    </div>
  )
}

/** The same content as plain text for the Markdown export. */
export function computedMarkdown(planet: Planet, l4: RehearsalResult | null, a: MissionAssessment | null): string {
  const place = planet === 'moon' ? 'Site01, lunar south pole' : 'Jezero region'
  const lines = [`## Computed evidence · ${place}`, '', `_${NOT_STORED}. Not independently validated._`, '']
  if (l4) {
    lines.push(`**Rehearsal windows (Layer 4):** ${headline(l4).text} Span ${utc(l4.start_utc).slice(0, 16)} to ${utc(l4.end_utc).slice(0, 16)} UTC, step ${fmtDuration(l4.step_seconds)} (boundaries uncertain by ±${fmtDuration(l4.boundary_uncertainty_seconds)}).`, '')
  } else lines.push('**Rehearsal windows (Layer 4):** not run in this session.', '')
  if (a) {
    lines.push(`**Suitability assessment (Layer 5):** ${OVERALL_META[a.overall_status].label}. ${a.overall_explanation}`, '')
    for (const c of a.criterion_results) lines.push(`- ${c.name}: ${CRITERION_META[c.status].label} (${c.measured_value !== null ? `measured ${fmtValue(c.measured_value, c.unit)}` : c.claimed_value !== null ? `claimed ${fmtValue(c.claimed_value, c.unit)}, unverified` : 'no value'}; needs ${fmtTarget(c)})`)
    lines.push('')
  } else lines.push('**Suitability assessment (Layer 5):** not run in this session.', '')
  return lines.join('\n')
}
