import { ArrowRight, RotateCcw } from 'lucide-react'
import { useEffect, useId, useMemo, useRef } from 'react'
import { useBackend } from '../../lib/api/backend'
import { currentAssessKey, assessKey, useEvidence, type AssessEntry } from '../../lib/api/evidence'
import { explain } from '../../lib/api/explain'
import type { CriterionResult, MissionAssessment } from '../../lib/api/types'
import type { Planet } from '../../lib/planet'
import { primaryTarget, utc } from '../../lib/rehearsal'
import { CATEGORY_LABEL, categoriesOf, CRITERION_META, fmtTarget, fmtValue, OVERALL_META, SPATIAL_META, SPECS, tally, type CriterionSpec } from '../../lib/suitability'
import { NotValidatedChip, EvidenceChip, OverallChip, VerdictChip } from '../evidence/chips'
import { ServiceUnavailable } from '../ServiceUnavailable'
import { Button, cx, Disclosure } from '../ui'
import { go } from '../../lib/router'

/*
 * Layer 5 on the Mission screen: the planet's own criteria on the left, the service's assessment on the right. Editing a
 * criterion re-runs the assessment after a short pause; the previous result stays visible while it runs and a stale
 * request is cancelled. The words are the service's: a claim is never a pass, a gap is never a pass, and "configured
 * thresholds met" is never a safety finding.
 */

function CriterionRow({ spec, planet }: { spec: CriterionSpec; planet: Planet }) {
  const { edits, setEdit } = useEvidence()
  const e = edits[planet][spec.def.id]
  const id = useId()
  const f = spec.shown?.factor ?? 1
  const unit = spec.shown?.unit ?? (spec.def.unit === 'degrees' ? '°' : spec.def.unit === 'metres' ? 'm' : spec.def.unit === 'percent' ? '%' : spec.def.unit === 'fraction' ? '' : spec.def.unit)
  const op = spec.def.operator === 'lte' ? '≤' : '≥'
  const claim = spec.def.source_layer === 'layer4'
  return (
    <li className={cx('py-3.5', !e.enabled && 'opacity-60')}>
      <div className="flex items-start gap-3">
        <input id={`${id}-on`} type="checkbox" checked={e.enabled} onChange={(ev) => setEdit(planet, spec.def.id, { enabled: ev.target.checked })} className="mt-1 h-5 w-5 shrink-0 accent-[var(--color-amber)]" aria-label={`Include ${spec.def.name}`} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px] font-medium text-paper">{spec.def.name}{claim && <span className="mono rounded-[var(--radius-sm)] border border-dashed border-amber/60 px-1.5 text-xs leading-5 font-normal text-amber">Layer 4 claim</span>}</p>
          <p className="mt-0.5 text-xs leading-snug text-silver-400">{spec.def.description}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <label htmlFor={`${id}-v`} className="flex items-center gap-2 text-[13px] text-silver-200">
              <span aria-hidden className="mono text-silver-400">{op}</span><span className="sr-only">{spec.def.operator === 'lte' ? 'at most' : 'at least'}</span>
              <input id={`${id}-v`} type="number" inputMode="decimal" disabled={!e.enabled} value={Number((e.target / f).toFixed(4))} min={spec.min / f} max={spec.max / f} step={spec.step / f}
                onChange={(ev) => { const v = Number(ev.target.value); if (Number.isFinite(v) && ev.target.value !== '') setEdit(planet, spec.def.id, { target: Math.min(spec.max, Math.max(spec.min, v * f)) }) }}
                className="mono min-h-11 w-28 rounded-[var(--radius-md)] border border-[var(--control-edge)] bg-ink-800 px-3 text-[14px] text-paper hover:border-silver-500" />
              <span className="text-silver-400">{unit}</span>
            </label>
            <label className="flex min-h-11 items-center gap-2 text-[13px] text-silver-300">
              <input type="checkbox" checked={e.required} disabled={!e.enabled} onChange={(ev) => setEdit(planet, spec.def.id, { required: ev.target.checked })} className="h-5 w-5 accent-[var(--color-amber)]" />
              Required
            </label>
          </div>
        </div>
      </div>
    </li>
  )
}

function Editor({ planet }: { planet: Planet }) {
  const { resetEdits } = useEvidence()
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[15px] font-medium">Your criteria</h3>
        <Button size="sm" variant="ghost" onClick={() => resetEdits(planet)}><RotateCcw size={14} aria-hidden />Defaults</Button>
      </div>
      <p className="mt-1 text-xs leading-snug text-silver-400">Starting points for {planet === 'moon' ? 'lunar south-polar rover mobility' : 'regional Martian terrain'}, set for this planet alone. They are assumptions you can change, not standards. Every change re-runs the assessment.</p>
      {categoriesOf(planet).map((cat) => (
        <div key={cat} className="mt-4">
          <h4 className="mono text-xs tracking-[0.04em] text-silver-400 uppercase">{CATEGORY_LABEL[cat] ?? cat}</h4>
          <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
            {SPECS[planet].filter((s) => s.def.category === cat).map((s) => <CriterionRow key={s.def.id} spec={s} planet={planet} />)}
          </ul>
        </div>
      ))}
    </div>
  )
}

function ResultRow({ c }: { c: CriterionResult }) {
  const m = CRITERION_META[c.status]
  const value = c.measured_value !== null ? `Measured ${fmtValue(c.measured_value, c.unit)}` : c.claimed_value !== null ? `Claimed ${fmtValue(c.claimed_value, c.unit)} (unverified)` : 'No value'
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <p className="min-w-0 text-[14px] font-medium text-paper">{c.name}{!c.required && <span className="ml-2 text-xs font-normal text-silver-400">optional</span>}</p>
        <VerdictChip verdict={c.status} />
      </div>
      <p className="mono mt-1 text-[13px] text-silver-200">{value} <span className="text-silver-400">· required {fmtTarget(c)}</span></p>
      <p className="mt-1 text-xs leading-snug text-silver-400">{c.explanation}</p>
      {m.tone === 'claim' && <p className="mt-1 text-xs leading-snug text-amber">{m.meaning}</p>}
    </li>
  )
}

function Panel({ planet, entry, hasLayer4 }: { planet: Planet; entry: AssessEntry | undefined; hasLayer4: boolean }) {
  const { recheck } = useBackend()
  const ev = useEvidence()
  const target = primaryTarget(planet)
  const a: MissionAssessment | null = entry?.data ?? null
  const err = entry?.error
  return (
    <div className="min-w-0 [overflow-wrap:anywhere]" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[15px] font-medium">Assessment of {target.label}</h3>
        {a && <EvidenceChip kind="computed" />}
        {a && <NotValidatedChip />}
      </div>

      <p className="mt-2 text-[13px] leading-snug text-silver-300">
        {hasLayer4
          ? 'The rehearsal-window result for this target is attached. Its values are shown as claims.'
          : <>No rehearsal windows have been computed for this target, so the illumination criteria have no evidence and stay indeterminate. <a href="#/app/windows" onClick={() => go({ page: 'app', screen: 'windows' })} className="inline-flex min-h-11 items-center gap-1 font-medium text-amber underline-offset-4 hover:underline">Compute windows <ArrowRight size={14} aria-hidden /></a></>}
      </p>

      {entry?.loading && <p role="status" className="mono mt-3 text-xs text-silver-300">{a ? 'Updating with your change…' : 'Assessing…'}</p>}

      {err && !entry?.loading && (
        err.code === 'unreachable' || err.code === 'unavailable' || err.code === 'rate_limited' ? (
          <div className="mt-4"><ServiceUnavailable kind="offline" heading="h4" title="The assessment couldn't be computed" onRetry={() => { recheck(); ev.assessTarget(planet, target) }} context={`${explain(err).text} No assessment is shown, and nothing is substituted for one.`} /></div>
        ) : (
          <div role="alert" className="mt-4 rounded-[var(--radius-md)] border border-bad/50 p-4 text-[14px]">
            <p className="font-medium text-bad">The assessment was not returned ({err.code})</p>
            <p className="mt-1 text-silver-300">{explain(err).text}</p>
          </div>
        )
      )}

      {a && <Body a={a} loading={!!entry?.loading} />}
    </div>
  )
}

function Body({ a, loading }: { a: MissionAssessment; loading: boolean }) {
  const o = OVERALL_META[a.overall_status]
  const t = tally(a)
  const sp = a.spatial_association
  const cats = Object.entries(a.profile_completeness.category_statuses)
  return (
    <div className={cx('mt-4 space-y-7 transition-opacity', loading && 'opacity-60')}>
      <div>
        <OverallChip verdict={a.overall_status} />
        <p className="mt-3 max-w-prose text-[15px] leading-relaxed text-paper">{a.overall_explanation}</p>
        <p className="mt-1 max-w-prose text-[13px] leading-snug text-silver-300">{o.caution}</p>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          {([['Pass', t.pass], ['Fail', t.fail], ['Unverified claim', t.claim], ['Missing evidence', t.missing]] as const).map(([k, v]) => (
            <div key={k}><dt className="text-xs text-silver-400">{k}</dt><dd className="mono mt-0.5 text-[24px] leading-none text-paper">{v}</dd></div>
          ))}
        </dl>
        <p className="mt-3 text-xs leading-snug text-silver-400">Profile {a.profile_completeness.status.toLowerCase()}: {cats.map(([k, v]) => `${CATEGORY_LABEL[k] ?? k} ${v.toLowerCase().replace(/_/g, ' ')}`).join(' · ')}. A verdict of “suitable” needs every declared category to have a required, measured pass.</p>
      </div>

      <div>
        <h4 className="mb-1 text-[14px] font-medium">Criterion by criterion</h4>
        <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">{a.criterion_results.map((c) => <ResultRow key={c.criterion_id} c={c} />)}</ul>
      </div>

      {a.suitability_gaps.length > 0 && (
        <div>
          <h4 className="mb-1 text-[14px] font-medium">What evidence is missing</h4>
          <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
            {a.suitability_gaps.map((g) => (
              <li key={g.id} className="py-3 text-[13px] leading-snug">
                <p className="text-paper">{g.description}</p>
                <p className="mt-1 text-silver-300"><span className="text-silver-400">Effect: </span>{g.assessment_effect}</p>
                <p className="mt-1 text-silver-300"><span className="text-silver-400">Needed: </span>{g.additional_evidence_needed}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="border-t border-[var(--line)]">
        <Disclosure title={<span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[14px] font-medium">Does the Layer 4 result describe this terrain?{sp && <span className="mono text-xs font-normal text-silver-300">{SPATIAL_META[sp.status]?.label ?? sp.status}</span>}</span>}>
          {sp ? (
            <>
              <p>{SPATIAL_META[sp.status]?.text}</p>
              <dl className="mono mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
                {Object.entries(sp.checks).map(([k, v]) => <div key={k} className="contents"><dt className="text-silver-500">{k.replace(/_/g, ' ')}</dt><dd className="text-silver-200">{v}</dd></div>)}
              </dl>
              <ul className="mt-3 list-disc space-y-1 pl-5">{sp.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </>
          ) : <p>{SPATIAL_META.UNPAIRED.text}</p>}
        </Disclosure>
        <Disclosure title={<span className="text-[14px] font-medium">Limitations</span>}>
          <ul className="list-disc space-y-1.5 pl-5">{a.uncertainty_and_limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </Disclosure>
        <Disclosure title={<span className="text-[14px] font-medium">Provenance</span>}>
          <dl className="mono grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
            <dt className="text-silver-500">Terrain</dt><dd className="break-words text-silver-200">{a.layer3_provenance?.dataset_name ?? a.candidate.dataset_id}</dd>
            <dt className="text-silver-500">Assessed</dt><dd className="text-silver-200">{utc(a.assessed_at_utc).slice(0, 19)} UTC</dd>
            <dt className="text-silver-500">Profile</dt><dd className="break-words text-silver-200">{a.mission_profile_name}</dd>
            <dt className="text-silver-500">Layer 4 trust</dt><dd className="text-silver-200">{a.layer4_provenance?.trust_status ?? 'no Layer 4 result supplied'}</dd>
          </dl>
          {a.layer3_provenance?.citation && <p className="mt-3 text-xs text-silver-400">{a.layer3_provenance.citation}</p>}
          <p className="mt-3 text-xs text-silver-400">Computed for this session only. It is not stored: Layer 6 (research storage) is not connected.</p>
        </Disclosure>
      </div>
    </div>
  )
}

export function AssessmentWorkspace({ planet }: { planet: Planet }) {
  const { state, recheck } = useBackend()
  const ev = useEvidence()
  const online = state.status === 'online'
  const target = primaryTarget(planet)
  const edits = ev.edits[planet]
  const l4 = ev.rehearsal[target.key]?.data ?? null
  const entry = ev.assessments[assessKey(planet, target.key)]
  const { assessTarget } = ev
  const first = useRef(true)
  const entryKey = useRef(entry?.key)
  useEffect(() => { entryKey.current = entry?.key })
  const wanted = useMemo(() => currentAssessKey(planet, target, edits, l4), [planet, target, edits, l4])

  useEffect(() => {
    if (!online) return
    // Coming back to this screen with a current result needs no new request; a change to criteria or to the Layer 4 run does.
    if (first.current && wanted && entryKey.current === wanted) { first.current = false; return }
    assessTarget(planet, target, { debounce: !first.current })
    first.current = false
  }, [online, planet, target, wanted, assessTarget])

  return (
    <section aria-labelledby="aw-h" className="border-t border-[var(--line)] pt-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 id="aw-h" className="text-[20px] font-semibold">{planet === 'moon' ? 'Assess the lunar candidate' : 'Assess the Jezero region'}</h2>
        <span className="mono rounded-[var(--radius-sm)] border border-cyan/50 px-1.5 py-0.5 text-xs leading-4 text-cyan">LAYER 5 · SUITABILITY EVIDENCE</span>
      </div>
      <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-silver-300">
        {planet === 'moon'
          ? 'Tests the stored Site01 terrain against the criteria below. Terrain criteria are measured and can pass or fail. Light criteria come from the rehearsal calculation and are shown as unverified claims. Missing evidence is never read as a pass.'
          : 'Tests the stored Jezero MOLA terrain against criteria defined for Mars. Terrain criteria are measured at 926 m and can pass or fail. The Layer 4 result is on a different, coarser grid (1.85 km) than the terrain, so the service cannot pair them and the light criterion comes back as not assessed.'}
      </p>
      {!online ? (
        <div className="mt-6"><ServiceUnavailable kind={state.status === 'checking' ? 'checking' : 'offline'} heading="h3" title="No assessment can be computed right now" onRetry={recheck} context="The service is not reachable, so no suitability assessment is shown. No illustrative verdict stands in for one." /></div>
      ) : (
        <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-x-12 gap-y-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <Editor planet={planet} />
          <Panel planet={planet} entry={entry} hasLayer4={!!l4} />
        </div>
      )}
    </section>
  )
}
