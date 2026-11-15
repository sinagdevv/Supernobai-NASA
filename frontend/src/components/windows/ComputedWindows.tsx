import { Play, RotateCw } from 'lucide-react'
import { Fragment, useId, useMemo, useState, type ReactNode } from 'react'
import { useBackend } from '../../lib/api/backend'
import { useEvidence, type RehearsalEntry } from '../../lib/api/evidence'
import { explain } from '../../lib/api/explain'
import type { RehearsalInterval, RehearsalResult, TargetClass } from '../../lib/api/types'
import type { Planet } from '../../lib/planet'
import { CLASS_META, defaultParams, earthTarget, EARTH_KERNEL_END, evidenceLines, fmtDuration, headline, MAX_SAMPLES, MAX_SPAN_DAYS, primaryTarget, STEP_OPTIONS, summarize, uncertaintyNote, utc, validateParams, type RehearsalParams, type RehearsalTarget } from '../../lib/rehearsal'
import { evidenceKind } from '../../lib/status'
import { EvidenceChip, NotValidatedChip } from '../evidence/chips'
import { ServiceUnavailable } from '../ServiceUnavailable'
import { Button, cx, Disclosure, Segmented, Select, Slider } from '../ui'
import { Journey, ParamGroup } from '../ui/Journey'
import { Term } from '../ui/Term'
import { ClassLegend, ClassSwatch } from './classVis'
import { AzElTrack, ComputedTimeline } from './ComputedTimeline'

/*
 * Layer 4 on the Rehearsal Windows screen: choose a target and a span, run the solar-geometry engine, read what it
 * decided. Everything in a result comes from the engine's response. If the call fails there is an explanation and no
 * numbers; the illustrative preview is never put in its place.
 */

function Field({ label, hint, children }: { label: string; hint?: string; children: (id: string) => ReactNode }) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-silver-200">{label}</label>
      {children(id)}
      {hint && <p className="mt-1 text-xs leading-snug text-silver-500">{hint}</p>}
    </div>
  )
}

const INPUT = 'min-h-11 w-full rounded-[var(--radius-md)] border border-[var(--control-edge)] bg-ink-800 px-3 text-[14px] text-paper transition-colors hover:border-silver-500'

function NumberInput({ label, hint, value, min, max, step, onChange, unit, optional }: { label: string; hint?: string; value: number | null; min?: number; max?: number; step?: number; onChange: (v: number | null) => void; unit?: string; optional?: boolean }) {
  return (
    <Field label={`${label}${unit ? ` (${unit})` : ''}`} hint={hint}>
      {(id) => <input id={id} type="number" inputMode="decimal" className={cx(INPUT, 'mono')} value={value ?? ''} min={min} max={max} step={step} placeholder={optional ? 'none' : undefined}
        onChange={(e) => { const v = e.target.value; onChange(v === '' ? (optional ? null : value) : Number(v)) }} />}
    </Field>
  )
}

function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="min-w-0 rounded-[var(--radius-md)] border border-[var(--line)] px-3.5 py-3">
      <p className="text-xs text-silver-400">{label}</p>
      <p className="mono mt-1 text-[20px] leading-tight text-paper">{value}</p>
      {sub && <p className="mono mt-0.5 text-xs text-silver-400">{sub}</p>}
    </div>
  )
}

const pct = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? '—' : `${v.toFixed(d)} %`)

/** The planet's windows panel: a target, the span, the run, and the result or the reason there is none. */
export function ComputedWindows({ planet }: { planet: Planet }) {
  const { state, recheck } = useBackend()
  const [mode, setMode] = useState<'primary' | 'analog'>('primary')
  const [analogId, setAnalogId] = useState('')

  const stored = state.status === 'online' ? state.stored : []
  const primary = primaryTarget(planet)
  const primaryDs = stored.find((d) => d.id === primary.datasetId)
  const earths = stored.filter((d) => d.body === 'earth' && d.ready && d.summary)
  const analogDs = earths.find((d) => d.id === analogId) ?? earths[0]
  // An Earth analog is a lunar-rehearsal idea: Mars has none, so a Martian page never offers Earth's sun.
  const analog = planet === 'moon' && mode === 'analog' && analogDs ? earthTarget(analogDs) : null
  const target = analog ?? primary
  const bodyName = planet === 'moon' ? 'lunar' : 'Martian'

  return (
    <section aria-labelledby="cw-h" className="border-t border-[var(--line)] pt-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 id="cw-h" className="text-[20px] font-semibold">Compute rehearsal windows</h2>
        <span className="mono rounded-[var(--radius-sm)] border border-cyan/50 px-1.5 py-0.5 text-xs leading-4 text-cyan">LAYER 4 · SOLAR GEOMETRY</span>
      </div>
      <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-silver-300">
        Runs the solar-geometry engine on a stored {bodyName} elevation model with SPICE ephemerides: where the sun is, and whether terrain blocks it at the target, sample by sample. The result is computed, not checked against observations.
      </p>

      {state.status === 'offline' && (
        <div className="mt-6"><ServiceUnavailable kind="offline" heading="h3" title="No window can be computed right now" onRetry={recheck} context="This session cannot reach the service, so nothing is computed. No illustrative numbers are shown in place of a calculation." setup="cd backend/geoprocessing && python -m uvicorn terrawindow_geo.api.app:app --port 8000" /></div>
      )}
      {state.status === 'checking' && <div className="mt-6"><ServiceUnavailable kind="checking" heading="h3" title="Looking for the solar-geometry service" context="Checking whether the service is running." /></div>}

      {state.status === 'online' && !primaryDs?.ready && (
        <div className="mt-6"><ServiceUnavailable kind="dataset" heading="h3" title={`The ${bodyName} dataset isn't on this machine`} onRetry={recheck} context={<>The service is running, but its store has no ready {primary.label} raster, so there is nothing to compute on.</>} setup="terrawindow-data list" /></div>
      )}

      {state.status === 'online' && primaryDs?.ready && (
        <>
          <TargetPanel key={target.key} planet={planet} target={target} where={<>
            {planet === 'moon' && (
              <div className="mb-4 flex flex-wrap items-end gap-x-6 gap-y-3">
                <Segmented<'primary' | 'analog'> label="Reference target" value={mode} onChange={setMode} options={[{ value: 'primary', label: 'Moon · Site01' }, { value: 'analog', label: 'Earth analog' }]} />
                {mode === 'analog' && earths.length > 0 && (
                  <div className="w-full max-w-xs">
                    <Select label="Earth analog (stored dataset)" value={analogDs?.id ?? ''} onChange={setAnalogId} options={earths.map((d) => ({ value: d.id, label: d.region ? `${d.region.name.replace(/-/g, ' ')} · ${d.name}` : d.name }))} />
                  </div>
                )}
              </div>
            )}
            {planet === 'moon' && mode === 'analog' && earths.length === 0 && <p className="mb-3 text-[13px] text-silver-300">No Earth dataset is ready in the service, so there is no analog to compute on.</p>}
          </>} />
        </>
      )}
    </section>
  )
}

function TargetPanel({ planet, target, where }: { planet: Planet; target: RehearsalTarget; where: ReactNode }) {
  const ev = useEvidence()
  const { recheck } = useBackend()
  const entry = ev.rehearsal[target.key]
  const [params, setParams] = useState<RehearsalParams>(() => entry?.params ?? defaultParams(target.body === 'earth' ? 'earth' : planet))
  const set = (p: Partial<RehearsalParams>) => setParams((x) => ({ ...x, ...p }))
  const problem = validateParams(target, params)
  const engine = ev.status.data
  const engineDown = !!ev.status.data && (!engine?.package_installed || engine.bodies[target.body] === false)
  const samples = Math.ceil((params.days * 1440) / params.stepMinutes)

  return (
    <div className="mt-5">
      <Journey label="Rehearsal windows journey" current={entry?.loading ? 2 : entry?.data ? 3 : 1} steps={[{ label: 'Choose reference', target: 'cw-where' }, { label: 'Configure conditions', target: 'cw-when' }, { label: 'Calculate', target: 'cw-calc' }, { label: 'Inspect windows', target: 'cw-results' }, { label: 'Review limitations', target: 'cw-limits' }]} />
      <div className="mt-5">
        <ParamGroup id="cw-where" n={1} title="Where" hint="The reference whose sun and terrain are computed.">
          {where}
          <p className="text-[14px] text-silver-200"><span className="font-medium text-paper">{target.label}</span> · {target.place}{target.scaleM ? ` · analysed on a ${target.scaleM} m grid` : ' · native 32 pixels/degree MOLA grid (about 1.85 km)'}</p>
          {target.body === 'earth' && <p className="mt-1 text-xs leading-snug text-silver-400">The sun here is Earth’s. This tests the rehearsal geometry on Earth terrain; it is not lunar illumination.</p>}
          {target.body === 'mars' && <p className="mt-1 text-xs leading-snug text-silver-400">Sun and terrain are searched out to {(target.maxDistanceM ?? 0) / 1000} km. Some MOLA bins have no laser observations; they come back as <Term id="insufficient">insufficient coverage</Term>, not as shadow.</p>}
        </ParamGroup>

        <ParamGroup id="cw-when" n={2} title="When" hint="The span of time and how finely it is sampled.">
          <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Start (00:00 UTC)" hint={target.body === 'earth' ? `Earth dates must end by ${EARTH_KERNEL_END}.` : undefined}>
              {(id) => <input id={id} type="date" className={cx(INPUT, 'mono')} value={params.startDate} onChange={(e) => set({ startDate: e.target.value })} />}
            </Field>
            <Select label="Span" value={String(params.days)} onChange={(v) => set({ days: Number(v) })} options={[1, 2, 3, 7, 14, 30].map((d) => ({ value: String(d), label: `${d} ${d === 1 ? 'day' : 'days'}` }))} />
            <Select label="Sample every" value={String(params.stepMinutes)} onChange={(v) => set({ stepMinutes: Number(v) })} options={STEP_OPTIONS.map((m) => ({ value: String(m), label: m >= 60 ? `${m / 60} h` : `${m} min` }))} />
            <div className="self-end pb-2 text-xs text-silver-400"><span className="mono text-silver-200">{samples}</span> samples · at most {MAX_SAMPLES} samples, {MAX_SPAN_DAYS} days</div>
          </div>
        </ParamGroup>

        <ParamGroup n={2} title="Window criteria" hint="What counts as a candidate window.">
          <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <Slider label="Continuous light at least" value={params.minContinuousMinutes} min={0} max={720} step={15} format={(v) => (v >= 60 ? `${v / 60} h` : `${v} min`)} onChange={(v) => set({ minContinuousMinutes: v })} />
            <Slider label="Valid terrain coverage at least" value={params.minCoveragePercent} min={0} max={100} step={5} unit=" %" onChange={(v) => set({ minCoveragePercent: v })} />
            <Slider label="Terrain shadow at most" value={params.maxObstructionPercent} min={0} max={100} step={5} unit=" %" onChange={(v) => set({ maxObstructionPercent: v })} />
            <NumberInput label="Sun elevation at least" unit="°" value={params.elevationMin} step={0.1} onChange={(v) => set({ elevationMin: v })} optional hint="Leave empty for no lower limit." />
            <NumberInput label="Sun elevation at most" unit="°" value={params.elevationMax} step={0.1} onChange={(v) => set({ elevationMax: v })} optional hint="Leave empty for no upper limit." />
          </div>
          <p className="mt-3 text-xs leading-snug text-silver-400">These are rehearsal criteria you set. They decide which stretches count as candidate windows; they are not standards.</p>
        </ParamGroup>

        <ParamGroup id="cw-calc" n={3} title="Calculate" hint="Runs on demand. Nothing is stored.">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button variant="primary" onClick={() => ev.runRehearsal(target, params)} disabled={!!problem || engineDown}>
              {entry?.loading ? <RotateCw size={15} aria-hidden className="animate-spin motion-reduce:animate-none" /> : <Play size={15} aria-hidden />}
              {entry?.loading ? 'Recompute' : entry?.data ? 'Compute again' : 'Compute windows'}
            </Button>
            <p role="status" className={cx('text-[13px]', problem ? 'text-amber' : 'text-silver-400')}>{problem ?? (entry?.loading ? 'Computing…' : 'Runs on demand. Results are not stored.')}</p>
          </div>
        </ParamGroup>
      </div>

      {engineDown && (
        <div className="mt-5"><ServiceUnavailable kind="offline" heading="h3" title="The solar-geometry engine isn't available" onRetry={recheck} context={`The service is running, but it reports that Layer 4 cannot run for ${target.body === 'moon' ? 'the Moon' : target.body === 'mars' ? 'Mars' : 'Earth'} (engine package or kernels missing). Nothing is computed.`} /></div>
      )}

      <Outcome entry={entry} />
    </div>
  )
}

function Outcome({ entry }: { entry: RehearsalEntry | undefined }) {
  const { recheck } = useBackend()
  const ev = useEvidence()
  if (!entry) return null
  const err = entry.error
  return (
    <div id="cw-results" className="mt-2 scroll-mt-24" aria-live="polite">
      {entry.loading && <Computing hasPrevious={!!entry.data} />}
      {err && !entry.loading && (
        err.code === 'unreachable' || err.code === 'unavailable' || err.code === 'rate_limited' ? (
          <ServiceUnavailable kind="offline" heading="h3" title={err.code === 'rate_limited' ? 'The service asked us to slow down' : 'The calculation could not be completed'} onRetry={() => { recheck(); ev.runRehearsal(entry.target, entry.params) }}
            context={err.code === 'unreachable' ? `${err.message} No window is shown, and nothing is substituted for one.` : `${explain(err).text} No window is shown.`} />
        ) : (
          <div role="alert" className="rounded-[var(--radius-md)] border border-bad/50 p-4 text-[14px]">
            <p className="font-medium text-bad">The engine did not return a result ({err.code})</p>
            <p className="mt-1 text-silver-300">{explain(err).text}</p>
            <p className="mt-1 text-xs text-silver-400">No window is shown. Nothing is substituted for the calculation.</p>
          </div>
        )
      )}
      {entry.data && <Result key={entry.data.generated_at} r={entry.data} target={entry.target} stale={entry.loading} />}
    </div>
  )
}

function Computing({ hasPrevious }: { hasPrevious: boolean }) {
  return (
    <div role="status" className="mb-5 rounded-[var(--radius-lg)] border border-[var(--line)] p-4">
      <p className="text-[14px] font-medium text-paper">{hasPrevious ? 'Recomputing. The result below is from the previous run.' : 'Computing windows…'}</p>
      <p className="mt-1 text-xs text-silver-400">Reading terrain, tracing the horizon at every sample. The first run after the service starts takes about 25 seconds; later runs take a few seconds.</p>
      <div aria-hidden className="mt-3 space-y-2">
        <div className="h-24 animate-pulse rounded-[var(--radius-sm)] bg-white/6 motion-reduce:animate-none" />
        <div className="h-6 animate-pulse rounded-[var(--radius-sm)] bg-white/6 motion-reduce:animate-none" />
      </div>
    </div>
  )
}

const PROV_KEYS: [string, string][] = [['frame', 'Frame'], ['frame_realization', 'Frame realisation'], ['elevation_reference', 'Elevation reference'], ['vertical_reference', 'Vertical reference'], ['resampling', 'Resampling'], ['surface', 'Surface'], ['coverage', 'Coverage'], ['max_distance_m', 'Horizon search (m)'], ['frame_alignment_note', 'Frame alignment']]

function windowTitle(w: RehearsalInterval) {
  return `${utc(w.start_utc).slice(0, 16)} to ${utc(w.end_utc).slice(0, 16)} UTC`
}

function Result({ r, target, stale }: { r: RehearsalResult; target: RehearsalTarget; stale: boolean }) {
  const [sel, setSel] = useState(0)
  const s = useMemo(() => summarize(r), [r])
  const h = headline(r)
  const so = r.observations[Math.min(sel, r.observations.length - 1)]
  const present = s.byClass.map((x) => x.cls)
  const counts = Object.fromEntries(s.byClass.map((x) => [x.cls, x.n])) as Partial<Record<TargetClass, number>>
  const kind = h.tone === 'insufficient' ? 'insufficient' : evidenceKind(r.evidence.observational_validation_status)
  const windows = r.candidate_windows
  const bodyLabel = r.body === 'moon' ? 'Moon' : r.body === 'mars' ? 'Mars' : 'Earth analog'
  const idx = (iso: string) => Math.max(0, r.observations.findIndex((o) => o.time_utc === iso))
  const kernelRows = r.kernel_identities
  const prov = PROV_KEYS.filter(([k]) => typeof r.provenance[k] === 'string' || typeof r.provenance[k] === 'number').map(([k, l]) => [l, String(r.provenance[k])] as const)

  return (
    <div className={cx('space-y-9 transition-opacity', stale && 'opacity-60')}>
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[17px] font-semibold">Computed result</h3>
          <EvidenceChip kind={kind} />
          <NotValidatedChip />
        </div>
        <p className="mt-3 max-w-[62ch] text-[18px] leading-snug font-medium text-paper">{h.text}</p>
        <p className="mt-1.5 max-w-[62ch] text-[13px] leading-snug text-silver-300">{windows.length ? `Across ${fmtDuration(s.spanSeconds)} at a ${fmtDuration(r.step_seconds)} step, ${fmtDuration(s.qualifyingSeconds)} of light meets your criteria.` : `Across ${fmtDuration(s.spanSeconds)} at a ${fmtDuration(r.step_seconds)} step.`} This is <Term id="computed">computed, not validated</Term>.</p>
        <dl className="mt-4 grid gap-x-8 gap-y-3 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Body', bodyLabel],
            ['Target', `${target.label}`],
            ['Target position', `${r.target_latitude_deg.toFixed(3)}°, ${r.target_longitude_deg.toFixed(3)}° (${r.target_coordinate_frame})`],
            ['Analysis grid', `${r.analysis_grid.shape.join(' × ')} cells · ${r.analysis_grid.pixel_size_m.toFixed(r.analysis_grid.pixel_size_m < 100 ? 0 : 1)} m`],
            ['From (UTC)', utc(r.start_utc).slice(0, 16)],
            ['To (UTC)', utc(r.end_utc).slice(0, 16)],
            ['Sample step', fmtDuration(r.step_seconds)],
            ['Computed', utc(r.generated_at).slice(0, 19) + ' UTC'],
          ].map(([k, v]) => <div key={k} className="min-w-0"><dt className="text-silver-400">{k === 'Analysis grid' ? <Term id="scale">Analysis scale</Term> : k}</dt><dd className="mono mt-0.5 break-words text-paper">{v}</dd></div>)}
        </dl>
      </div>

      <div>
        <h3 className="mb-3 text-[15px] font-medium">Candidate windows</h3>
        {windows.length === 0 ? (
          <p className="text-[14px] text-silver-300">{h.tone === 'insufficient' ? 'None can be reported: no sample was decided.' : 'No stretch of light met the criteria in this span.'}</p>
        ) : (
          <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
            {windows.map((w) => {
              const ok = w.is_candidate !== false
              const a = ((Date.parse(w.start_utc) - Date.parse(r.start_utc)) / (Date.parse(r.end_utc) - Date.parse(r.start_utc))) * 100
              const b = ((Date.parse(w.end_utc) - Date.parse(w.start_utc)) / (Date.parse(r.end_utc) - Date.parse(r.start_utc))) * 100
              return (
                <li key={w.start_utc}>
                  <button type="button" onClick={() => setSel(idx(w.start_utc))} className="block min-h-11 w-full py-3 text-left transition-colors hover:bg-white/3 active:bg-white/6">
                    <span className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                      <span className="mono text-[14px] text-paper">{windowTitle(w)}</span>
                      <span className="mono text-[13px] text-amber">{fmtDuration(w.duration_seconds)}</span>
                    </span>
                    <span aria-hidden className="relative mt-2 block h-1.5 rounded-full bg-white/8"><span className="absolute inset-y-0 rounded-full bg-amber" style={{ left: `${a}%`, width: `${Math.max(1.5, b)}%` }} /></span>
                    <span className="mono mt-2 block text-xs text-silver-300">sun {w.solar_elevation_min_deg.toFixed(1)}–{w.solar_elevation_max_deg.toFixed(1)}° · az {w.solar_azimuth_start_deg.toFixed(0)}°→{w.solar_azimuth_end_deg.toFixed(0)}° · shadow ≤ {w.maximum_terrain_obstruction_percent.toFixed(1)} % · coverage ≥ {w.minimum_valid_terrain_coverage_percent.toFixed(0)} % · {w.sample_count} {w.sample_count === 1 ? 'sample' : 'samples'}</span>
                    <span className="mt-1 block text-xs text-silver-400">{ok ? 'Meets every criterion you set.' : `Lit, but not a candidate: ${(w.criteria_failed ?? []).map((c) => c.replace(/_/g, ' ')).join(', ') || 'a criterion failed'}.`}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        <p className="mt-3 max-w-3xl text-xs leading-snug text-silver-400">{uncertaintyNote(r)}</p>
      </div>

      <div className="grid gap-x-10 gap-y-8 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <figure className="min-w-0">
          <figcaption className="mb-2 text-[13px] font-medium text-silver-300">Sun elevation, what the engine decided at each sample, and the windows it found</figcaption>
          <ComputedTimeline r={r} sel={sel} />
          <div className="mt-3">
            <Slider label="Inspect a sample" value={sel} min={0} max={Math.max(0, r.observations.length - 1)} format={(v) => `${v + 1} of ${r.observations.length}`} onChange={setSel} />
            {so && (
              <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4" aria-live="polite">
                {[
                  ['Time (UTC)', utc(so.time_utc).slice(0, 16)],
                  ['Classification', CLASS_META[so.target_classification].label],
                  ['Sun elevation / azimuth', `${so.solar_elevation_deg.toFixed(2)}° / ${so.solar_azimuth_deg.toFixed(1)}°`],
                  ['Terrain shadow · coverage', `${so.terrain_obstruction_percent.toFixed(1)} % · ${so.valid_terrain_coverage_percent.toFixed(0)} %`],
                ].map(([k, v], i) => <div key={k} className="min-w-0"><dt className="text-xs text-silver-400">{k}</dt><dd className="mono mt-0.5 flex items-center gap-1.5 text-[14px] break-words text-paper">{i === 1 && <ClassSwatch cls={so.target_classification} />}{v}</dd></div>)}
              </dl>
            )}
          </div>
        </figure>
        <figure className="min-w-0">
          <figcaption className="mb-2 text-[13px] font-medium text-silver-300">Solar diagram · azimuth and elevation of the computed samples</figcaption>
          <AzElTrack r={r} sel={sel} />
          <p className="mt-2 text-xs leading-snug text-silver-400">Azimuth N = 0°, clockwise. Each dot is one sample, coloured by classification. The shaded band is your elevation criterion, if you set one.</p>
        </figure>
      </div>

      <div>
        <h3 className="mb-3 text-[15px] font-medium">What each sample means</h3>
        <ClassLegend present={present} counts={counts} />
        {present.includes('INSUFFICIENT_COVERAGE') && (
          <p role="note" className="mt-4 max-w-3xl border-l-2 border-amber pl-3 text-[13px] leading-relaxed text-silver-300">
            <span className="font-medium text-paper"><Term id="insufficient">Insufficient coverage</Term> is not darkness and not light.</span> At {s.undeterminedSamples} of {s.samples} samples the elevation data around the target could not support a decision{r.body === 'mars' ? ' (about a fifth of the MOLA bins around Jezero have no laser observations)' : ''}. They are left out of every duration below.
          </p>
        )}
      </div>

      <div>
        <h3 className="mb-3 text-[15px] font-medium">Terrain shadow and coverage</h3>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Lit time (decided samples)" value={fmtDuration(s.litSeconds)} sub={`of ${fmtDuration(s.spanSeconds)}`} />
          <Stat label="Qualifying light" value={fmtDuration(s.qualifyingSeconds)} sub="inside candidate windows" />
          <Stat label="Terrain shadow, peak" value={pct(r.terrain_obstruction_max_percent)} sub={`mean ${pct(r.terrain_obstruction_mean_percent)}`} />
          <Stat label="Valid terrain coverage" value={pct(r.valid_terrain_coverage_mean_percent, 0)} sub="mean over the patch" />
        </div>
        <p className="mt-2 max-w-3xl text-xs leading-snug text-silver-400">Shadow is the share of the analysed patch the engine found blocked by terrain, not just the target pixel. Sun elevation {r.solar_elevation_min_deg.toFixed(2)}° to {r.solar_elevation_max_deg.toFixed(2)}°, azimuth swing {r.solar_azimuth_span_deg.toFixed(1)}°.</p>
      </div>

      <section id="cw-limits" aria-labelledby="cw-limits-h" className="scroll-mt-24 space-y-6 border-t border-[var(--line)] pt-6">
        <h3 id="cw-limits-h" className="text-[17px] font-semibold">Review limitations</h3>
      <div>
        <h4 className="text-[14px] font-medium">How much to trust this</h4>
        <dl className="mt-3 divide-y divide-[var(--line)] text-[13px]">
          {evidenceLines(r).map((l) => (
            <div key={l.label} className="grid gap-x-4 gap-y-0.5 py-2 sm:grid-cols-[13rem_1fr]"><dt className="text-silver-400">{l.label}</dt><dd className="text-paper">{l.value}</dd></div>
          ))}
        </dl>
        <p className="mt-3 text-xs leading-snug text-silver-400">“Computed” means the engine returned this for the request above. It does not mean the shadows were compared with images or measurements.</p>
      </div>

      <div>
        <h4 className="mb-2 text-[14px] font-medium">Limitations stated by the engine</h4>
        <ul className="list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-silver-300">{r.scientific_limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </div>

      <div className="border-t border-[var(--line)]">
        <Disclosure title={<span className="text-[14px] font-medium">Dataset, kernels and provenance</span>}>
          <dl className="mono grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
            <dt className="text-silver-500">Dataset</dt><dd className="break-words text-silver-200">{r.source_grid_id ?? target.datasetId}</dd>
            <dt className="text-silver-500">Target pixel</dt><dd className="text-silver-200">row {r.target_pixel[0]}, column {r.target_pixel[1]}</dd>
            {r.analysis_grid.resampling && <Fragment><dt className="text-silver-500">Grid resampling</dt><dd className="break-words text-silver-200">{r.analysis_grid.resampling}</dd></Fragment>}
            {prov.map(([k, v]) => <Fragment key={k}><dt className="text-silver-500">{k}</dt><dd className="break-words text-silver-200">{v}</dd></Fragment>)}
          </dl>
          <h5 className="mt-4 text-[13px] font-medium text-paper">SPICE kernels</h5>
          <ul className="mt-2 space-y-1.5 text-xs">
            {kernelRows.map((k) => (
              <li key={k.filename} className="min-w-0"><span className="mono break-all text-silver-200">{k.filename}</span> <span className="text-silver-400">· {k.roles.join(', ')} · {k.status}{k.warning ? ` · ${k.warning}` : ''}</span><span className="mono block break-all text-silver-500">sha256 {k.sha256.slice(0, 16)}…</span></li>
            ))}
          </ul>
        </Disclosure>
        <Disclosure title={<span className="text-[14px] font-medium">Every sample, as a table</span>}>
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Samples, scrollable">
            <table className="w-full min-w-[34rem] border-collapse text-left text-xs">
              <caption className="sr-only">Computed samples</caption>
              <thead><tr className="text-silver-400">{['Time (UTC)', 'Classification', 'Elevation', 'Azimuth', 'Shadow', 'Coverage'].map((c) => <th key={c} scope="col" className="pb-2 pr-3 font-medium">{c}</th>)}</tr></thead>
              <tbody>
                {r.observations.map((o) => (
                  <tr key={o.time_utc} className="border-t border-[var(--line)]">
                    <th scope="row" className="mono py-1.5 pr-3 font-normal whitespace-nowrap text-silver-200">{utc(o.time_utc).slice(0, 16)}</th>
                    <td className="py-1.5 pr-3 whitespace-nowrap text-silver-200"><span className="inline-flex items-center gap-1.5"><ClassSwatch cls={o.target_classification} size={14} />{CLASS_META[o.target_classification].label}</span></td>
                    <td className="mono py-1.5 pr-3 text-silver-200">{o.solar_elevation_deg.toFixed(2)}°</td>
                    <td className="mono py-1.5 pr-3 text-silver-200">{o.solar_azimuth_deg.toFixed(1)}°</td>
                    <td className="mono py-1.5 pr-3 text-silver-200">{o.terrain_obstruction_percent.toFixed(1)} %</td>
                    <td className="mono py-1.5 text-silver-200">{o.valid_terrain_coverage_percent.toFixed(0)} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Disclosure>
      </div>
      </section>
    </div>
  )
}
