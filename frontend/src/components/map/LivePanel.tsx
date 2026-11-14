import { X } from 'lucide-react'
import { useBackend } from '../../lib/api/backend'
import { explain } from '../../lib/api/explain'
import type { LiveTerrain, Req } from '../../lib/api/live'
import type { OverlayLayer, PatchFeature, PatchStatus, StoredDataset } from '../../lib/api/types'
import { Button, Segmented, Slider, StatusBadge } from '../ui'
import type { Status } from '../../data/types'

/*
 * Layer 3 on the map: pick a stored Earth dataset, draw a terrain overlay, screen it for candidate patches.
 * Everything here is measured by the service from a stored DEM and is labelled that way; nothing is sample data.
 */

export const PATCH_STATUS: Record<PatchStatus, { status: Status; label: string }> = {
  candidate: { status: 'potential', label: 'Passes screened criteria' },
  rejected: { status: 'not-suitable', label: 'Fails a criterion' },
  insufficient_data: { status: 'not-assessed', label: 'Not enough data' },
}

export const LivePill = ({ children = 'LIVE · LAYER 3' }: { children?: string }) => (
  <span className="mono rounded-[var(--radius-sm)] border border-cyan/50 px-1.5 py-0.5 text-[12px] leading-4 text-cyan">{children}</span>
)

function Failure({ req }: { req: Req<unknown> }) {
  if (req.status !== 'error') return null
  const x = explain(req.error)
  return (
    <div role="alert" className="rounded-[var(--radius-md)] border border-bad/50 p-2.5 text-[12px] leading-snug">
      <p className="font-medium text-bad">Could not compute ({req.error.code})</p>
      <p className="mt-1 text-silver-300">{x.text}</p>
      {x.setup && <p className="mono mt-1.5 break-words text-silver-400">{x.setup}</p>}
    </div>
  )
}

function Unavailable({ list }: { list: StoredDataset[] }) {
  return (
    <ul className="space-y-2.5 text-[12px] leading-snug">
      {list.map((d) => (
        <li key={d.id} className="rounded-[var(--radius-md)] border border-dashed border-silver-500 p-2.5">
          <p className="font-medium text-silver-200">{d.name}</p>
          <p className="mt-0.5 text-silver-400">{d.availability.status === 'missing' ? 'Setup required: the raster is not in the data store.' : d.availability.detail}</p>
          {d.availability.setup && <p className="mono mt-1 break-words text-silver-400">{d.availability.setup}</p>}
        </li>
      ))}
    </ul>
  )
}

const LAYERS: { value: OverlayLayer | 'off'; label: string }[] = [
  { value: 'off', label: 'Off' }, { value: 'slope', label: 'Slope' }, { value: 'hillshade', label: 'Shade' }, { value: 'elevation', label: 'Height' },
]
const SIZES = [{ value: 1500, label: '1.5 km' }, { value: 3000, label: '3 km' }]

export function LivePanel({ live }: { live: LiveTerrain }) {
  const { state, recheck } = useBackend()
  const earth = state.status === 'online' ? state.stored.filter((d) => d.body === 'earth') : []
  const ready = earth.filter((d) => d.ready)
  const blocked = earth.filter((d) => !d.ready)
  const lunarOnly = state.status === 'online' && earth.length === 0
  const sel = ready.find((d) => d.id === live.datasetId) ?? null
  const scr = live.screen

  return (
    <div className="w-[min(300px,calc(100vw-120px))] space-y-3.5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[13px] font-medium text-paper">Live terrain</h2>
        {state.status === 'online' ? <LivePill /> : <span className="mono text-[12px] text-silver-400">{state.status === 'offline' ? 'SERVICE OFFLINE' : 'CHECKING…'}</span>}
      </div>

      {state.status === 'offline' && (
        <div className="space-y-2 text-[12px] leading-snug text-silver-300">
          <p>The Layer 3 service is not running, so no measured terrain can be shown. The example sites on the map are demonstration data and still work.</p>
          <Button size="sm" onClick={recheck}>Check again</Button>
        </div>
      )}

      {state.status === 'online' && lunarOnly && <p className="text-[12px] leading-snug text-silver-300">The service has no Earth datasets in its store. Fetch some with Layer 2 (see the README).</p>}

      {state.status === 'online' && earth.length > 0 && (
        <>
          {ready.length > 0 ? (
            <label className="block text-[12px] text-silver-400">
              Stored dataset
              <select value={sel?.id ?? ''} onChange={(e) => live.chooseDataset(e.target.value || null)} className="mt-1 block min-h-11 w-full rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-ink-850 px-2.5 text-[13px] text-paper">
                <option value="">Choose a dataset…</option>
                {ready.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
          ) : (
            <p className="text-[12px] leading-snug text-silver-300">No Earth dataset is ready to use on this machine.</p>
          )}
          {blocked.length > 0 && (
            <details className="text-[12px] text-silver-300">
              <summary className="min-h-11 cursor-pointer py-2 text-silver-200">{blocked.length} need{blocked.length === 1 ? 's' : ''} setup</summary>
              <Unavailable list={blocked} />
            </details>
          )}

          {sel && (
            <>
              <div className="space-y-1.5">
                <p className="text-[12px] text-silver-400">Terrain layer</p>
                <Segmented<OverlayLayer | 'off'> label="Terrain layer" value={live.layer} onChange={live.setLayer} options={LAYERS} />
                {live.overlay.status === 'loading' && <p role="status" className="text-[12px] text-silver-400">Rendering from the raster…</p>}
                <Failure req={live.overlay} />
              </div>

              <div className="space-y-2.5 border-t border-[var(--line)] pt-3">
                <p className="text-[12px] text-silver-400">Screen for candidate patches</p>
                <Segmented<number> label="Patch size" value={live.params.patchSizeM} onChange={(v) => live.setParams({ ...live.params, patchSizeM: v })} options={SIZES} />
                <Slider label="Mean slope up to" value={live.params.slopeMeanMax} min={2} max={20} unit="°" onChange={(v) => live.setParams({ ...live.params, slopeMeanMax: v })} />
                <Button variant="primary" size="sm" onClick={live.runScreen} disabled={scr.status === 'loading'} className="w-full">{scr.status === 'loading' ? 'Screening…' : 'Screen patches'}</Button>
                <Failure req={scr} />
                {scr.status === 'done' && (
                  <div className="space-y-1.5">
                    {scr.data.summary.cells === 0 ? (
                      <p className="text-[12px] text-silver-300">No patches fit this dataset at that size.</p>
                    ) : (
                      (Object.keys(PATCH_STATUS) as PatchStatus[]).map((k) => (
                        <p key={k} className="flex items-center justify-between gap-2 text-[12px] text-silver-300">
                          <StatusBadge status={PATCH_STATUS[k].status} label={PATCH_STATUS[k].label} compact />
                          <span className="mono text-paper">{scr.data.summary[k]}</span>
                        </p>
                      ))
                    )}
                    <p className="text-[12px] leading-snug text-silver-400">A passing patch is a shortlist entry for these criteria, not a suitability verdict. Select a patch on the map for its evidence.</p>
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

const fmt = (v: number | null, d = 1) => (v === null ? '—' : v.toFixed(d))

/** On-map provenance: which dataset, which layer, its colour scale, and how to clear it. */
export function LiveChip({ live }: { live: LiveTerrain }) {
  const ov = live.overlay.status === 'done' ? live.overlay.data : null
  const sc = live.screen.status === 'done' ? live.screen.data : null
  if (!ov && !sc) return null
  const prov = (ov ?? sc)!.provenance
  const limits = sc?.limitations ?? []
  const ramp = ov ? `linear-gradient(90deg, ${ov.legend.map((l) => l.color).join(', ')})` : null
  return (
    <div className="glass absolute top-2.5 left-2.5 z-10 w-[min(272px,calc(100%-80px))] rounded-[var(--radius-md)] border border-[var(--line-strong)] p-2.5 text-[12px] leading-snug shadow-[var(--shadow-pop)]">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0"><LivePill /><p className="mt-1.5 font-medium break-words text-paper">{prov.dataset_name}</p></div>
        <button type="button" onClick={live.clear} aria-label="Remove live layers" className="-mt-1 -mr-1 grid h-11 w-11 shrink-0 place-items-center rounded-full text-silver-400 transition-[color,transform] hover:text-paper active:scale-95"><X size={15} aria-hidden /></button>
      </div>
      {ov && ramp && (
        <div className="mt-1.5">
          <div aria-hidden className="h-2 rounded-[2px]" style={{ background: ramp }} />
          <p className="mono mt-1 flex justify-between text-silver-300"><span>{ov.value_range[0]}</span><span>{ov.layer === 'hillshade' ? 'relative light' : ov.unit}</span><span>{ov.value_range[1]}</span></p>
          {ov.layer === 'hillshade' && <p className="mt-0.5 text-silver-400">Sun 7° from 120°. Shading only, no cast shadows.</p>}
        </div>
      )}
      <p className="mono mt-1.5 text-silver-400">{prov.working_pixel_size_m} m grid · source {prov.native_pixel_size_m.toFixed(0)} m</p>
      <details className="mt-1 text-silver-300">
        <summary className="min-h-11 cursor-pointer py-2.5 text-silver-200">Source and limits</summary>
        <p className="text-silver-400">{prov.citation}</p>
        {limits.length > 0 && <ul className="mt-1.5 list-disc space-y-1 pl-4 text-silver-300">{limits.map((l) => <li key={l}>{l}</li>)}</ul>}
      </details>
    </div>
  )
}

/** The selected screening patch: what the service measured and which criteria it passed. */
export function PatchCard({ live }: { live: LiveTerrain }) {
  const sc = live.screen.status === 'done' ? live.screen.data : null
  const f: PatchFeature | undefined = sc?.features.find((x) => x.properties.id === live.patchId)
  if (!f) return null
  const p = f.properties, st = PATCH_STATUS[p.status]
  return (
    <div className="glass absolute bottom-[calc(var(--sheet-offset,0px)+76px)] left-2.5 z-10 w-[min(272px,calc(100%-80px))] rounded-[var(--radius-md)] border border-amber/50 p-2.5 text-[12px] leading-snug shadow-[var(--shadow-pop)]">
      <div className="flex items-start justify-between gap-2">
        <div><StatusBadge status={st.status} label={st.label} compact /><p className="mono mt-1.5 text-silver-400">Patch {p.id} · {(p.patch_size_m / 1000).toFixed(1)} km · {p.center_lat.toFixed(3)}°, {p.center_lon.toFixed(3)}°</p></div>
        <button type="button" onClick={() => live.setPatchId(null)} aria-label="Close patch details" className="-mt-1 -mr-1 grid h-11 w-11 shrink-0 place-items-center rounded-full text-silver-400 transition-[color,transform] hover:text-paper active:scale-95"><X size={15} aria-hidden /></button>
      </div>
      <p className="mono mt-1.5 text-paper">mean {fmt(p.metrics.slope_mean_deg)}° · p90 {fmt(p.metrics.slope_p90_deg)}° · relief {fmt(p.metrics.relief_m, 0)} m</p>
      <details className="mt-1 text-silver-300">
        <summary className="min-h-11 cursor-pointer py-2.5 text-silver-200">Criteria</summary>
        <ul className="space-y-1.5">
          {p.criteria.map((c) => (
            <li key={c.criterion} className="flex items-start gap-1.5">
              <StatusBadge status={c.status === 'pass' ? 'potential' : c.status === 'fail' ? 'not-suitable' : 'not-assessed'} label={c.status === 'pass' ? 'Pass' : c.status === 'fail' ? 'Fail' : 'Not assessed'} compact />
              <span className="min-w-0 text-silver-300">{c.criterion.replace(/_/g, ' ')}{c.value !== null && <span className="mono"> {c.value.toFixed(2)} {c.unit}</span>}{c.reason && <span className="block text-silver-400">{c.reason}</span>}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
