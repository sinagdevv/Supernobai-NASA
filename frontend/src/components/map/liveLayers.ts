import { LngLatBounds, type ExpressionSpecification, type GeoJSONSource, type ImageSource, type Map as MapLibreMap } from 'maplibre-gl'
import type { LonLat, OverlayResponse, PatchStatus, ScreenResponse } from '../../lib/api/types'

/*
 * Layer 3 results drawn on the Explorer map. The map is created once; these functions add, update and remove sources and
 * layers on it. Footprints are placed from the service's own lon/lat coordinates and never from assumptions.
 */

type GeoJSONData = Parameters<GeoJSONSource['setData']>[0]

const OVERLAY = 'live-overlay'
const SCREEN = 'live-screen'
const FILL = 'live-screen-fill'
const LINE = 'live-screen-line'
const PICK = 'live-screen-selected'

/** The same three colours the interface uses for pass / fail / missing evidence. */
export const PATCH_COLOR: Record<PatchStatus, string> = { candidate: '#93c49a', rejected: '#e08d82', insufficient_data: '#a9afb7' }
export const PATCH_LAYER = FILL

/**
 * Run `fn` as soon as sources and layers can be added. That needs the style document, not the tiles: map.isStyleLoaded() is false
 * whenever any source is still fetching, and the `load` event fires only once, so waiting on either can drop the update for good.
 * Adding to a style that has not loaded yet throws; only then do we wait for `load`.
 */
const whenReady = (map: MapLibreMap, fn: () => void) => {
  try {
    fn()
  } catch (e) {
    if (!/not done loading/i.test(String((e as Error)?.message))) throw e
    map.once('load', fn)
  }
}

export function syncOverlay(map: MapLibreMap, ov: OverlayResponse | null) {
  whenReady(map, () => {
    const src = map.getSource(OVERLAY) as ImageSource | undefined
    if (!ov) {
      if (map.getLayer(OVERLAY)) map.removeLayer(OVERLAY)
      if (src) map.removeSource(OVERLAY)
      return
    }
    const url = `data:image/png;base64,${ov.image_base64}`
    if (src) return void src.updateImage({ url, coordinates: ov.coordinates })
    map.addSource(OVERLAY, { type: 'image', url, coordinates: ov.coordinates })
    // Under the screening patches when those exist, so patch outlines stay readable over the terrain colours.
    map.addLayer({ id: OVERLAY, type: 'raster', source: OVERLAY, paint: { 'raster-opacity': 0.66, 'raster-fade-duration': 200 } }, map.getLayer(FILL) ? FILL : undefined)
  })
}

export function syncScreen(map: MapLibreMap, fc: ScreenResponse | null, selectedId: string | null) {
  whenReady(map, () => {
    const src = map.getSource(SCREEN) as GeoJSONSource | undefined
    if (!fc) {
      for (const id of [PICK, LINE, FILL]) if (map.getLayer(id)) map.removeLayer(id)
      if (src) map.removeSource(SCREEN)
      return
    }
    if (src) src.setData(fc as unknown as GeoJSONData)
    else {
      map.addSource(SCREEN, { type: 'geojson', data: fc as unknown as GeoJSONData })
      const color: ExpressionSpecification = ['match', ['get', 'status'], 'candidate', PATCH_COLOR.candidate, 'rejected', PATCH_COLOR.rejected, PATCH_COLOR.insufficient_data]
      map.addLayer({ id: FILL, type: 'fill', source: SCREEN, paint: { 'fill-color': color, 'fill-opacity': ['match', ['get', 'status'], 'insufficient_data', 0.1, 0.22] } })
      map.addLayer({ id: LINE, type: 'line', source: SCREEN, paint: { 'line-color': color, 'line-width': 1.2, 'line-opacity': 0.9 } })
      map.addLayer({ id: PICK, type: 'line', source: SCREEN, filter: ['==', ['get', 'id'], ''], paint: { 'line-color': '#e4a95b', 'line-width': 3 } })
    }
    setSelectedPatch(map, selectedId)
  })
}

export function setSelectedPatch(map: MapLibreMap, id: string | null) {
  if (map.getLayer(PICK)) map.setFilter(PICK, ['==', ['get', 'id'], id ?? ''])
}

export function fitCoords(map: MapLibreMap, coords: LonLat[], padding: { top: number; left: number; right: number; bottom: number }) {
  const b = new LngLatBounds()
  coords.forEach((c) => b.extend(c))
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  map.fitBounds(b, { padding, maxZoom: 12, duration: reduce ? 0 : 1400, essential: true })
}
