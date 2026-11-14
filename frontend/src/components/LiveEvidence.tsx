import { useId, useState } from 'react'
import { ApiError, compare } from '../lib/api/client'
import { useBackend } from '../lib/api/backend'
import type { ComparisonCriterion, ComparisonResult, CriterionStatus, StoredDataset } from '../lib/api/types'
import type { Status } from '../data/types'
import { Button, StatusBadge, cx } from './ui'

/*
 * The one place the interface shows measured terrain statistics from the Layer 2/3 service. Everything above it on the
 * Comparison screen is demonstration data; everything inside this panel is computed from a stored DEM by Layer 3 and
 * carries its dataset, citation, pixel size and limitations. If the service is down, or a raster is missing, the panel
 * says so. It never substitutes demonstration numbers.
 */

const STATUS: Record<CriterionStatus, { status: Status; label: string }> = {
  within_tolerance: { status: 'potential', label: 'Within tolerance' },
  outside_tolerance: { status: 'not-suitable', label: 'Outside tolerance' },
  not_assessed: { status: 'not-assessed', label: 'Not assessed' },
}

const METRIC: Record<string, string> = {
  slope_mean: 'Mean slope',
  slope_median: 'Median slope',
  slope_p90: '90th-percentile slope',
  rms_slope: 'RMS slope',
  fraction_steeper_than_15deg: 'Share steeper than 15°',
  slope_distribution_distance: 'Slope distribution distance',
  roughness_rms_height_median: 'Median RMS roughness',
  relief_median_330m_window: 'Median relief (330 m window)',
}

/** Metric ids carry their threshold or window (`fraction_steeper_than_10deg`, `relief_median_990m_window`); name them from the id. */
const label = (m: string) => {
  if (METRIC[m]) return METRIC[m]
  const f = m.match(/^fraction_steeper_than_(\d+)deg$/), r = m.match(/^relief_median_(\d+)m_window$/)
  return f ? `Share steeper than ${f[1]}°` : r ? `Median relief (${r[1]} m window)` : m.replace(/_/g, ' ')
}

const fmt = (v: number | null, unit: string) => (v === null ? '—' : `${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(Math.abs(v) < 1 ? 3 : 2)}${unit === 'fraction' ? '' : ` ${unit}`}`)

function Pill({ children, tone }: { children: React.ReactNode; tone: 'live' | 'warn' | 'quiet' }) {
  return <span className={cx('mono inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border px-2 py-0.5 text-[12px]', tone === 'live' ? 'border-cyan/50 text-cyan' : tone === 'warn' ? 'border-amber/50 text-amber' : 'border-[var(--line-strong)] text-silver-400')}>{children}</span>
}

function Row({ c }: { c: ComparisonCriterion }) {
  const s = STATUS[c.status]
  return (
    <tr className="border-t border-[var(--line)] align-top">
      <th scope="row" className="py-2.5 pr-4 text-left text-[14px] font-medium text-paper">{label(c.metric)}{c.scale_m !== null && <span className="mono block text-[12px] font-normal text-silver-400">at {c.scale_m} m grid</span>}</th>
      {c.reference === null && c.candidate === null && c.difference !== null ? (
        <td colSpan={2} className="mono py-2.5 pr-4 text-right text-[13px] text-silver-200">distance {fmt(c.difference, c.unit)}</td>
      ) : (
        <>
          <td className="mono py-2.5 pr-4 text-right text-[13px] text-silver-200">{fmt(c.reference, c.unit)}</td>
          <td className="mono py-2.5 pr-4 text-right text-[13px] text-silver-200">{fmt(c.candidate, c.unit)}</td>
        </>
      )}
      <td className="py-2.5 text-[13px]">
        <StatusBadge status={s.status} label={s.label} compact />
        {c.reason && <span className="mt-1 block max-w-[24rem] text-[12px] text-silver-400">{c.reason}</span>}
      </td>
    </tr>
  )
}

function Result({ r }: { r: ComparisonResult }) {
  const cand = r.candidate_profile, ref = r.reference_profile
  return (
    <div className="mt-5 space-y-5">
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-silver-300">
        <span>{r.counts.within_tolerance} within tolerance</span><span>{r.counts.outside_tolerance} outside</span><span>{r.counts.not_assessed} not assessed</span>
        <span className="text-silver-400">· a tally per criterion, not a similarity score</span>
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse">
          <caption className="sr-only">Terrain criteria, lunar reference against Earth candidate, from the Layer 3 service</caption>
          <thead>
            <tr className="text-left text-[12px] text-silver-400">
              <th scope="col" className="pb-2 font-medium">Criterion</th>
              <th scope="col" className="pb-2 pr-4 text-right font-medium">Lunar reference</th>
              <th scope="col" className="pb-2 pr-4 text-right font-medium">Earth candidate</th>
              <th scope="col" className="pb-2 font-medium">Result</th>
            </tr>
          </thead>
          <tbody>{r.criteria.map((c) => <Row key={`${c.metric}-${c.scale_m}`} c={c} />)}</tbody>
        </table>
      </div>
      <p className="text-[12px] text-silver-400">Tolerances are screening assumptions: {Object.entries(r.tolerances).map(([k, v]) => `${k} ${v}`).join(' · ')}.</p>

      <details className="text-[13px] text-silver-300">
        <summary className="min-h-11 cursor-pointer py-2 font-medium text-paper">Provenance and limitations</summary>
        <div className="grid gap-6 pb-2 md:grid-cols-2">
          {[['Lunar reference', ref], ['Earth candidate', cand]].map(([label, p]) => {
            const prof = p as typeof ref
            return (
              <div key={label as string} className="space-y-1.5">
                <h3 className="text-[13px] font-medium text-paper">{label as string}: {prof.provenance.dataset_name}</h3>
                <p className="text-silver-400">{prof.provenance.citation}</p>
                <p className="mono text-[12px] text-silver-400">native {prof.provenance.native_pixel_size_m.toFixed(1)} m · working {prof.provenance.working_pixel_size_m.toFixed(1)} m ({prof.provenance.resampling}) · vertical {prof.provenance.vertical_unit} · coverage {(prof.coverage.valid_fraction * 100).toFixed(0)}% · engine {prof.provenance.engine_version} · {prof.provenance.generated_at}</p>
                <ul className="list-disc space-y-1 pl-5 text-silver-300">{prof.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
                {prof.skipped.length > 0 && <p className="text-silver-400">Not computed: {prof.skipped.map((s) => `${s.item} (${s.reason})`).join('; ')}</p>}
              </div>
            )
          })}
        </div>
        {r.notes.length > 0 && <ul className="list-disc space-y-1 pl-5 text-silver-400">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      </details>
    </div>
  )
}

const explain = (e: ApiError) =>
  e.code === 'source_unavailable' ? 'The service knows this dataset, but its raster is not on this machine. Fetch it with Layer 2 (see the README), then run again.'
  : e.code === 'scale_not_supported' || e.code === 'patch_too_small' ? `${e.message} The requested analysis scale is not supported by one of these datasets.`
  : e.code === 'unreachable' ? 'The Layer 3 service stopped answering.'
  : e.message

export default function LiveEvidence() {
  const { state, recheck } = useBackend()
  const id = useId()
  const [refId, setRef] = useState<string>('')
  const [candId, setCand] = useState<string>('')
  const [run, setRun] = useState<{ status: 'idle' } | { status: 'running' } | { status: 'done'; result: ComparisonResult } | { status: 'error'; error: ApiError }>({ status: 'idle' })

  const stored = state.status === 'online' ? state.stored.filter((d) => d.ready) : []
  const moons = stored.filter((d) => d.body === 'moon')
  const earths = stored.filter((d) => d.body === 'earth')
  const rid = refId || moons[0]?.id || '', cid = candId || earths[0]?.id || ''

  const go = async () => {
    setRun({ status: 'running' })
    try {
      setRun({ status: 'done', result: await compare({ reference: { dataset: { id: rid } }, candidate: { dataset: { id: cid } }, scales_m: [30, 60] }) })
    } catch (e) {
      setRun({ status: 'error', error: e instanceof ApiError ? e : new ApiError('bad_response', 'Unexpected failure.') })
    }
  }

  const select = (label: string, value: string, set: (v: string) => void, opts: StoredDataset[]) => (
    <label className="block text-[12px] text-silver-400">
      {label}
      <select value={value} onChange={(e) => { set(e.target.value); setRun({ status: 'idle' }) }} className="mt-1 block min-h-11 w-full rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-ink-850 px-3 text-[14px] text-paper">
        {opts.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </label>
  )

  return (
    <section aria-labelledby={`${id}-h`} className="border-t border-[var(--line)] py-8">
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 id={`${id}-h`} className="text-[15px] font-medium">Measured terrain evidence</h2>
        {state.status === 'online' ? <Pill tone="live">LIVE · LAYER 3 SERVICE v{state.version}</Pill> : state.status === 'offline' ? <Pill tone="warn">SERVICE OFFLINE · DEMONSTRATION ONLY</Pill> : <Pill tone="quiet">CHECKING SERVICE…</Pill>}
      </div>
      <p className="mb-4 max-w-3xl text-[14px] text-silver-300">Everything above is demonstration data. This panel asks the Layer 2/3 service to compute slope and roughness statistics from stored elevation models, with their source and limits.</p>

      {state.status === 'offline' && (
        <div className="max-w-3xl rounded-[var(--radius-md)] border border-dashed border-silver-500 p-4 text-[14px] text-silver-300">
          <p>The geoprocessing service is not running, so no measured results can be shown. Nothing here is substituted.</p>
          <p className="mono mt-2 text-[12px] text-silver-400">cd backend/geoprocessing &amp;&amp; python -m uvicorn terrawindow_geo.api.app:app --port 8000</p>
          <Button className="mt-3" onClick={recheck}>Check again</Button>
        </div>
      )}

      {state.status === 'online' && (moons.length === 0 || earths.length === 0) && (
        <p className="max-w-3xl rounded-[var(--radius-md)] border border-dashed border-silver-500 p-4 text-[14px] text-silver-300">The service is online, but Layer 2 has not stored both a lunar and an Earth dataset that passed validation. Fetch them first (see the README).</p>
      )}

      {state.status === 'online' && moons.length > 0 && earths.length > 0 && (
        <>
          <div className="grid max-w-3xl gap-4 sm:grid-cols-2">
            {select('Lunar reference (Layer 2 store)', rid, setRef, moons)}
            {select('Earth candidate (Layer 2 store)', cid, setCand, earths)}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <Button variant="primary" onClick={go} disabled={run.status === 'running'}>{run.status === 'running' ? 'Reading rasters…' : 'Compare with Layer 3'}</Button>
            <span className="text-[12px] text-silver-400" aria-live="polite">{run.status === 'running' ? 'Reading the elevation rasters; the first run can take several seconds.' : 'Runs on demand. Results are computed by the service, not cached in the page.'}</span>
          </div>
          {run.status === 'error' && (
            <div role="alert" className="mt-4 max-w-3xl rounded-[var(--radius-md)] border border-bad/50 p-4 text-[14px]">
              <p className="font-medium text-bad">Could not compute ({run.error.code})</p>
              <p className="mt-1 text-silver-300">{explain(run.error)}</p>
            </div>
          )}
          {run.status === 'done' && <Result r={run.result} />}
        </>
      )}
    </section>
  )
}
