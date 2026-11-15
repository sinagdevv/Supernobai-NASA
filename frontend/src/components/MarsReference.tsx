import { useEffect, useState, type ReactNode } from 'react'
import { ApiError, overlay as fetchOverlay, profile as fetchProfile } from '../lib/api/client'
import { useBackend } from '../lib/api/backend'
import { explain } from '../lib/api/explain'
import type { OverlayLayer, OverlayResponse, TerrainProfile } from '../lib/api/types'
import { JEZERO_PREVIEW, ServiceUnavailable } from './ServiceUnavailable'
import { Segmented } from './ui'

/*
 * The Martian reference region as the Layer 2/3 service measures it. Every number and the picture come from the service,
 * computed from a stored MOLA elevation raster; nothing here is sample data, and a failed request is shown as a failure.
 */

/** The 463.06 m MOLA pixel and two and four times it: the scales this dataset supports. Finer scales are refused by the service. */
const NATIVE_M = 463.0576672
const SCALES_M = [NATIVE_M, 2 * NATIVE_M, 4 * NATIVE_M]
const LAYERS: { value: OverlayLayer; label: string }[] = [{ value: 'elevation', label: 'Elevation' }, { value: 'hillshade', label: 'Hillshade' }, { value: 'slope', label: 'Slope' }]

type Load<T> = { status: 'loading' } | { status: 'done'; data: T } | { status: 'error'; error: ApiError }
const asError = (e: unknown) => (e instanceof ApiError ? e : new ApiError('bad_response', 'Unexpected failure.'))
const n = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? '—' : v.toFixed(d))

function Tile({ label, value, sub }: { label: string; value: ReactNode; sub: string }) {
  return (
    <div className="min-w-0 rounded-[var(--radius-md)] border border-[var(--line)] px-3.5 py-3">
      <p className="text-xs text-silver-400">{label}</p>
      <p className="mono mt-1 text-[20px] leading-tight text-paper">{value}</p>
      <p className="mono mt-0.5 text-xs text-silver-400">{sub}</p>
    </div>
  )
}

/** `heading` is the level for the unavailable-state title: h2 when the page title is the h1 above it (Mission), h3 inside a section (Dossier). */
export default function MarsReference({ heading = 'h2' }: { heading?: 'h2' | 'h3' }) {
  const { state, recheck } = useBackend()
  const mars = state.status === 'online' ? state.stored.filter((d) => d.body === 'mars') : []
  const ready = mars.find((d) => d.ready)
  const blocked = mars.find((d) => !d.ready)
  const [profile, setProfile] = useState<Load<TerrainProfile>>({ status: 'loading' })
  const [layer, setLayer] = useState<OverlayLayer>('elevation')
  const [images, setImages] = useState<Partial<Record<OverlayLayer, Load<OverlayResponse>>>>({})
  const id = ready?.id

  useEffect(() => {
    if (!id) return
    let live = true
    fetchProfile({ dataset: { id }, scales_m: SCALES_M, relief_windows_m: [5000] }).then(
      (data) => live && setProfile({ status: 'done', data }),
      (e) => live && setProfile({ status: 'error', error: asError(e) }),
    )
    return () => { live = false }
  }, [id])

  useEffect(() => {
    if (!id || images[layer]) return
    let live = true
    fetchOverlay({ dataset: { id }, layer, sun_azimuth_deg: 315, sun_elevation_deg: 35 }).then(
      (data) => live && setImages((m) => ({ ...m, [layer]: { status: 'done', data } })),
      (e) => live && setImages((m) => ({ ...m, [layer]: { status: 'error', error: asError(e) } })),
    )
    return () => { live = false }
  }, [id, layer, images])

  const context = <>Jezero region of Mars · NASA MOLA topography · 463 m pixels · 76.4°E to 78.6°E, 17.4°N to 19.4°N.</>
  if (state.status !== 'online') {
    return (
      <ServiceUnavailable heading={heading} kind={state.status === 'checking' ? 'checking' : 'offline'} title="Measured terrain isn't available right now"
        context={<>{state.status === 'checking' ? 'Looking for the terrain service.' : 'This session cannot reach the terrain service, so no Martian measurements are shown and nothing is substituted.'} {context}</>}
        onRetry={recheck} preview={JEZERO_PREVIEW} setup="cd backend/geoprocessing && python -m uvicorn terrawindow_geo.api.app:app --port 8000" />
    )
  }
  if (!ready) {
    return (
      <ServiceUnavailable heading={heading} kind="dataset" title="The Jezero region isn't on this machine"
        context={<>{blocked ? `It is listed but cannot be used: ${blocked.availability.detail}` : 'The terrain service is running, but the Martian elevation dataset has not been retrieved.'} {context}</>}
        onRetry={recheck} preview={JEZERO_PREVIEW} setup={blocked?.availability.setup ?? 'terrawindow-data region mola-megdr128 jezero 76.4 17.4 78.6 19.4'} />
    )
  }

  const img = images[layer]
  const p = profile.status === 'done' ? profile.data : null
  const d = ready.details
  const s463 = p?.scales?.[0]
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <figure className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <Segmented<OverlayLayer> label="Terrain layer" value={layer} onChange={setLayer} options={LAYERS} />
            <span className="mono text-xs text-cyan">Measured · {ready.id}</span>
          </div>
          <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-[#0c0f13]">
            {img?.status === 'done' ? (
              <img src={`data:image/png;base64,${img.data.image_base64}`} alt={`${img.data.layer} of the Jezero region of Mars, rendered from MOLA topography by the Layer 3 service`} width={img.data.width} height={img.data.height} className="block h-auto max-h-[460px] w-full object-contain" />
            ) : (
              <div className="grid aspect-[16/10] place-items-center px-4 text-center text-[14px] text-silver-400" role={img?.status === 'error' ? 'alert' : 'status'}>
                {img?.status === 'error' ? explain(img.error).text : 'Rendering from the MOLA raster…'}
              </div>
            )}
          </div>
          <figcaption className="mono mt-2 text-xs leading-relaxed text-silver-400">
            {img?.status === 'done' ? `${img.data.layer} · ${img.data.value_range[0].toFixed(0)} to ${img.data.value_range[1].toFixed(0)} ${img.data.unit} · ` : ''}
            {ready.region ? `${ready.region.bbox_lonlat[1]}–${ready.region.bbox_lonlat[3]}°N, ${ready.region.bbox_lonlat[0]}–${ready.region.bbox_lonlat[2]}°E · ` : ''}Mars Global Surveyor MOLA
          </figcaption>
        </figure>

        <div className="min-w-0">
          <div className="grid grid-cols-2 gap-3">
            <Tile label="Elevation" value={p ? <>{n(p.elevation?.min, 0)} to {n(p.elevation?.max, 0)}</> : '…'} sub="m above the MOLA areoid" />
            <Tile label="Resolution" value="463 m" sub="per pixel, MOLA" />
            <Tile label="Mean slope" value={s463?.slope ? `${n(s463.slope.stats.mean)}°` : '…'} sub="at 463 m" />
            <Tile label="Roughness" value={s463?.roughness ? `${n(s463.roughness.rms_height_m.median)} m` : '…'} sub="RMS height at 463 m" />
          </div>
          <p className="mt-5 text-[13px] font-medium text-silver-300">By analysis scale</p>
          {profile.status === 'loading' && <p className="mt-2 text-[13px] text-silver-400" role="status">Measuring…</p>}
          {profile.status === 'error' && <p role="alert" className="mt-2 text-[13px] text-bad">Could not measure ({profile.error.code}): {explain(profile.error).text}</p>}
          {p && (
            <div className="mt-1 overflow-x-auto" tabIndex={0} role="region" aria-label="Slope and roughness table, scrollable">
              <table className="w-full min-w-[22rem] border-collapse text-left">
                <caption className="sr-only">Slope and roughness of the Jezero region at three analysis scales</caption>
                <thead><tr className="text-xs text-silver-400"><th scope="col" className="pb-2 font-medium">Scale</th><th scope="col" className="pb-2 text-right font-medium">Mean slope</th><th scope="col" className="pb-2 text-right font-medium">P90</th><th scope="col" className="pb-2 text-right font-medium">Roughness</th></tr></thead>
                <tbody>
                  {(p.scales ?? []).map((s) => (
                    <tr key={s.scale_m} className="border-t border-[var(--line)]">
                      <th scope="row" className="mono py-2 text-[13px] font-normal text-silver-200">{s.scale_m.toFixed(0)} m</th>
                      {s.slope && s.roughness ? (
                        <><td className="mono py-2 text-right text-[13px]">{n(s.slope.stats.mean)}°</td><td className="mono py-2 text-right text-[13px]">{n(s.slope.stats.p90)}°</td><td className="mono py-2 text-right text-[13px]">{n(s.roughness.rms_height_m.median)} m</td></>
                      ) : <td colSpan={3} className="py-2 text-right text-[13px] text-silver-400">insufficient coverage</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {p && <p className="mono mt-2 text-xs leading-relaxed text-silver-400">{(p.coverage.valid_fraction * 100).toFixed(1)}% valid cells · measured on a local {p.provenance.working_pixel_size_m.toFixed(0)} m grid, because the source pixel is not true-scale away from the equator</p>}
        </div>
      </div>

      <details className="text-[13px] text-silver-300">
        <summary className="min-h-11 cursor-pointer py-2 font-medium text-paper">Source, provenance and limitations</summary>
        <div className="space-y-3 pb-2">
          <p><span className="font-medium text-paper">{ready.name}.</span> {ready.citation}</p>
          {d && (
            <dl className="mono grid gap-x-4 gap-y-1 text-xs text-silver-400 sm:grid-cols-[10rem_1fr]">
              {Object.entries({ Instrument: d.instrument, Product: d.product_type, 'PDS dataset': d.pds3_dataset_id, 'PDS4 bundle': d.pds4_bundle, Acquired: d.acquired, Processing: d.processing }).map(([k, v]) => v && (
                <div key={k} className="contents"><dt>{k}</dt><dd className="text-silver-300">{v}</dd></div>
              ))}
            </dl>
          )}
          {ready.vertical_datum && <p className="text-silver-400">Heights: {ready.vertical_datum}</p>}
          {ready.limitations && <ul className="list-disc space-y-1 pl-5">{ready.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
          {ready.source_page && <p><a className="text-cyan underline underline-offset-2 hover:text-paper" href={ready.source_page} target="_blank" rel="noreferrer noopener">Official source page (opens in new tab)</a></p>}
        </div>
      </details>
    </div>
  )
}
