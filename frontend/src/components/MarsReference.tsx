import { useEffect, useState } from 'react'
import { ApiError, overlay as fetchOverlay, profile as fetchProfile } from '../lib/api/client'
import { useBackend } from '../lib/api/backend'
import { explain } from '../lib/api/explain'
import type { OverlayLayer, OverlayResponse, TerrainProfile } from '../lib/api/types'
import { Button, Segmented } from './ui'

/*
 * The Martian reference region as the Layer 2/3 service measures it. Every number and the picture come from the service,
 * computed from a stored MOLA elevation raster; nothing here is sample data, and a failed request is shown as a failure.
 */

/** Two and four times the 463.06 m MOLA pixel, plus the pixel itself: the scales this dataset supports. Finer scales are refused by the service. */
const NATIVE_M = 463.0576672
const SCALES_M = [NATIVE_M, 2 * NATIVE_M, 4 * NATIVE_M]
const LAYERS: { value: OverlayLayer; label: string }[] = [{ value: 'elevation', label: 'Elevation' }, { value: 'hillshade', label: 'Hillshade' }, { value: 'slope', label: 'Slope' }]

type Load<T> = { status: 'loading' } | { status: 'done'; data: T } | { status: 'error'; error: ApiError }
const asError = (e: unknown) => (e instanceof ApiError ? e : new ApiError('bad_response', 'Unexpected failure.'))
const n = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? '—' : v.toFixed(d))

export default function MarsReference() {
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

  if (state.status !== 'online') {
    return (
      <div className="rounded-[var(--radius-md)] border border-dashed border-silver-500 p-4 text-[14px] text-silver-300">
        <p>{state.status === 'checking' ? 'Checking for the Layer 2/3 service…' : 'The geoprocessing service is not running, so no Martian terrain can be measured or shown. Nothing is substituted.'}</p>
        {state.status === 'offline' && <><p className="mono mt-2 text-[12px] text-silver-400">cd backend/geoprocessing &amp;&amp; python -m uvicorn terrawindow_geo.api.app:app --port 8000</p><Button className="mt-3" onClick={recheck}>Check again</Button></>}
      </div>
    )
  }
  if (!ready) {
    return (
      <div className="rounded-[var(--radius-md)] border border-dashed border-silver-500 p-4 text-[14px] text-silver-300">
        <p>{blocked ? `The Martian region is listed but cannot be used: ${blocked.availability.detail}` : 'No Martian elevation dataset has been retrieved on this machine.'}</p>
        <p className="mono mt-2 break-words text-[12px] text-silver-400">{blocked?.availability.setup ?? 'terrawindow-data region mola-megdr128 jezero 76.4 17.4 78.6 19.4'}</p>
      </div>
    )
  }

  const img = images[layer]
  const p = profile.status === 'done' ? profile.data : null
  const d = ready.details
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="mono inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border border-cyan/50 px-2 py-0.5 text-[12px] text-cyan">MEASURED · LAYER 2/3 · {ready.id}</span>
        <Segmented<OverlayLayer> label="Terrain layer" value={layer} onChange={setLayer} options={LAYERS} />
      </div>

      <figure>
        <div className="relative overflow-hidden rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-[#0c0f13]">
          {img?.status === 'done' ? (
            <img src={`data:image/png;base64,${img.data.image_base64}`} alt={`${img.data.layer} of the Jezero region of Mars, rendered from MOLA topography by the Layer 3 service`} width={img.data.width} height={img.data.height} className="block h-auto max-h-[460px] w-full object-contain" style={{ imageRendering: 'auto' }} />
          ) : (
            <div className="grid aspect-[16/9] place-items-center px-4 text-center text-[14px] text-silver-400" role={img?.status === 'error' ? 'alert' : 'status'}>
              {img?.status === 'error' ? explain(img.error).text : 'Rendering from the MOLA raster…'}
            </div>
          )}
        </div>
        <figcaption className="mono mt-2 text-[12px] leading-relaxed text-silver-400">
          {img?.status === 'done' ? `${img.data.layer} · ${img.data.value_range[0].toFixed(0)} to ${img.data.value_range[1].toFixed(0)} ${img.data.unit} · ${img.data.scale_m.toFixed(0)} m grid · ` : ''}
          {ready.region ? `${ready.region.bbox_lonlat[1]}°N to ${ready.region.bbox_lonlat[3]}°N, ${ready.region.bbox_lonlat[0]}°E to ${ready.region.bbox_lonlat[2]}°E · ` : ''}Mars Global Surveyor MOLA, NASA PDS
        </figcaption>
      </figure>

      <div>
        <h3 className="text-[13px] font-medium text-silver-300">Measured terrain, by analysis scale</h3>
        {profile.status === 'loading' && <p className="mt-2 text-[13px] text-silver-400" role="status">Measuring…</p>}
        {profile.status === 'error' && <p role="alert" className="mt-2 text-[13px] text-bad">Could not measure ({profile.error.code}): {explain(profile.error).text}</p>}
        {p && (
          <>
            <div className="mt-2 overflow-x-auto" tabIndex={0} role="region" aria-label="Slope and roughness table, scrollable">
              <table className="w-full min-w-[30rem] border-collapse text-left">
                <caption className="sr-only">Slope and roughness of the Jezero region at three analysis scales</caption>
                <thead><tr className="text-[12px] text-silver-400"><th scope="col" className="pb-2 font-medium">Scale</th><th scope="col" className="pb-2 text-right font-medium">Mean slope</th><th scope="col" className="pb-2 text-right font-medium">90th pct slope</th><th scope="col" className="pb-2 text-right font-medium">Roughness (RMS)</th><th scope="col" className="pb-2 text-right font-medium">Valid cells</th></tr></thead>
                <tbody>
                  {(p.scales ?? []).map((s) => (
                    <tr key={s.scale_m} className="border-t border-[var(--line)]">
                      <th scope="row" className="mono py-2 text-[13px] font-normal text-silver-200">{s.scale_m.toFixed(0)} m</th>
                      {s.slope && s.roughness ? (
                        <>
                          <td className="mono py-2 text-right text-[13px]">{n(s.slope.stats.mean)}°</td>
                          <td className="mono py-2 text-right text-[13px]">{n(s.slope.stats.p90)}°</td>
                          <td className="mono py-2 text-right text-[13px]">{n(s.roughness.rms_height_m.median)} m</td>
                        </>
                      ) : <td colSpan={3} className="py-2 text-right text-[13px] text-silver-400">insufficient coverage</td>}
                      <td className="mono py-2 text-right text-[13px] text-silver-400">{(s.coverage_fraction * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mono mt-2 text-[12px] leading-relaxed text-silver-400">
              Elevation {n(p.elevation?.min, 0)} to {n(p.elevation?.max, 0)} m above the MOLA areoid · {n(p.patch.area_km2 && p.patch.area_km2 / 1000, 1)} thousand km² · {p.coverage.valid_fraction >= 0.99 ? 'full' : `${(p.coverage.valid_fraction * 100).toFixed(1)}%`} coverage · measured on a local {p.provenance.working_pixel_size_m.toFixed(0)} m grid ({p.provenance.resampling}), because the source pixel is not true-scale away from the equator
            </p>
          </>
        )}
      </div>

      <details className="text-[13px] text-silver-300">
        <summary className="min-h-11 cursor-pointer py-2 font-medium text-paper">Source, provenance and limitations</summary>
        <div className="space-y-3 pb-2">
          <p><span className="font-medium text-paper">{ready.name}.</span> {ready.citation}</p>
          {d && (
            <dl className="mono grid gap-x-4 gap-y-1 text-[12px] text-silver-400 sm:grid-cols-[10rem_1fr]">
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
