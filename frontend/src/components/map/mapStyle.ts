import type { Map as MapLibreMap, MapOptions } from 'maplibre-gl'
import type { BaseMap } from '../../lib/store'

export type Style = Exclude<MapOptions['style'], string | undefined>

export const BASE_KEYS: BaseMap[] = ['satellite', 'topo', 'dark']
export const baseId = (b: BaseMap) => `base-${b}`

export const BASE_INFO: Record<BaseMap, { label: string; credit: string }> = {
  satellite: { label: 'Satellite', credit: 'Esri World Imagery' },
  topo: { label: 'Topo', credit: 'OpenTopoMap / OSM' },
  dark: { label: 'Dark', credit: 'CARTO / OSM' },
}

type Line = { type: 'Feature'; properties: Record<string, never>; geometry: { type: 'LineString'; coordinates: number[][] } }

/** 30° graticule so a tile-less map is still legible. */
function graticule(): { type: 'FeatureCollection'; features: Line[] } {
  const line = (coordinates: number[][]): Line => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates } })
  const features: Line[] = []
  for (let lon = -180; lon <= 180; lon += 30) features.push(line([[lon, -80], [lon, 80]]))
  for (let lat = -60; lat <= 60; lat += 30) features.push(line([[-180, lat], [180, lat]]))
  return { type: 'FeatureCollection', features }
}

export function buildStyle(base: BaseMap): Style {
  const vis = (on: boolean) => ({ visibility: on ? ('visible' as const) : ('none' as const) })
  return {
    version: 8,
    sources: {
      [baseId('satellite')]: {
        type: 'raster',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256,
        maxzoom: 18,
        attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
      },
      [baseId('topo')]: {
        type: 'raster',
        tiles: ['https://tile.opentopomap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 17,
        attribution: '© OpenTopoMap (CC-BY-SA), © OpenStreetMap contributors',
      },
      [baseId('dark')]: {
        type: 'raster',
        tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© CARTO, © OpenStreetMap contributors',
      },
      graticule: { type: 'geojson', data: graticule() },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#151a20' } },
      ...BASE_KEYS.map((b) => ({ id: baseId(b), type: 'raster' as const, source: baseId(b), layout: vis(b === base) })),
      { id: 'graticule', type: 'line', source: 'graticule', paint: { 'line-color': '#ffffff', 'line-opacity': 0.14, 'line-width': 0.6, 'line-dasharray': [2, 3] } },
    ],
  }
}

/**
 * Terrain relief is optional context. Its source is added only while enabled (so its unreliable public tiles never
 * touch the default experience), starts at zoom 3, and its tile errors are never treated as a basemap failure.
 */
export function setRelief(map: MapLibreMap, on: boolean) {
  if (on && !map.getSource('dem')) {
    map.addSource('dem', {
      type: 'raster-dem',
      tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
      encoding: 'terrarium',
      tileSize: 256,
      maxzoom: 12,
      attribution: 'Terrain Tiles (Mapzen / AWS Open Data)',
    })
    map.addLayer(
      { id: 'relief', type: 'hillshade', source: 'dem', minzoom: 3, paint: { 'hillshade-exaggeration': 0.45, 'hillshade-shadow-color': '#05070a', 'hillshade-highlight-color': 'rgba(255,255,255,0.3)' } },
      'graticule',
    )
  } else if (!on && map.getSource('dem')) {
    if (map.getLayer('relief')) map.removeLayer('relief')
    map.removeSource('dem')
  }
}
