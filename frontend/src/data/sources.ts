import type { Source } from './types'

/** Authentic public data resources. Listing them does not imply endorsement by, or affiliation with, any agency. */
export const SOURCES: Source[] = [
  {
    id: 'pgda',
    name: 'NASA Planetary Geodesy Data Archive',
    url: 'https://pgda.gsfc.nasa.gov/',
    role: 'Lunar reference terrain (LOLA-derived gridded products)',
    note: 'Where real lunar south-polar DEMs would be sourced. This prototype uses synthetic terrain and illustrative statistics instead.',
  },
  {
    id: 'earthdata',
    name: 'NASA Earthdata',
    url: 'https://www.earthdata.nasa.gov/',
    role: 'Earth observation datasets',
    note: 'Candidate source for Earth-side terrain and surface-property layers.',
  },
  {
    id: 'copernicus',
    name: 'Copernicus DEM (Copernicus Data Space)',
    url: 'https://dataspace.copernicus.eu/',
    role: 'Global 30 m Earth elevation model',
    note: 'A 30 m grid cannot resolve the same terrain scales as a 5 m lunar grid — the interface shows this explicitly.',
  },
  {
    id: 'worldcover',
    name: 'ESA WorldCover',
    url: 'https://esa-worldcover.org/',
    role: 'Land-cover context',
    note: 'Used conceptually to flag vegetation, snow and water that change surface character.',
  },
]

export const BASEMAP_CREDITS = [
  'Imagery © Esri, Maxar, Earthstar Geographics and the GIS User Community',
  'Topographic tiles © OpenTopoMap (CC-BY-SA), data © OpenStreetMap contributors',
  'Dark base © CARTO, data © OpenStreetMap contributors',
  'Relief tiles: Terrain Tiles (Mapzen / AWS Open Data)',
]

export const DISCLAIMER =
  'TERRAWINDOW is a prototype for preliminary research planning. It does not certify any location as safe, equivalent to, or qualified for planetary operations. All figures are illustrative demonstration values, not validated results, and no NASA endorsement is implied.'

/** What Earth analogs cannot reproduce — shown wherever suitability appears. */
export const NOT_REPRODUCIBLE = [
  { id: 'gravity', label: 'Lunar gravity (≈1/6 g)', detail: 'Earth surface gravity changes wheel–soil loading, slip and sinkage. Not reproducible at an Earth site.' },
  { id: 'vacuum', label: 'Hard vacuum', detail: 'Thermal, dust and outgassing behaviour differ in the lunar exosphere. Not reproducible in the field.' },
  { id: 'radiation', label: 'Space radiation environment', detail: 'Cosmic-ray and solar-particle exposure is not present at the Earth surface.' },
  { id: 'thermal', label: 'Polar thermal extremes & permanent shadow', detail: 'Cold-trap temperatures in permanently shadowed terrain are far outside most Earth sites.' },
]
