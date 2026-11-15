import type { Source } from './types'

/** Authentic public data resources. Listing them does not imply endorsement by, or affiliation with, any agency. */
export const SOURCES: Source[] = [
  {
    id: 'pgda',
    name: 'NASA Planetary Geodesy Data Archive',
    url: 'https://pgda.gsfc.nasa.gov/',
    role: 'Lunar reference terrain (LOLA 5 m south-pole site model, Site01)',
    note: 'Site01 is retrieved and used for every measured lunar result. The example sites elsewhere in the interface are illustrative.',
  },
  {
    id: 'pds-mola',
    name: 'NASA PDS: MGS MOLA topography (MEGDR)',
    url: 'https://pds-geosciences.wustl.edu/missions/mgs/megdr.html',
    role: 'Martian terrain (Jezero region, 463 m) and Mars solar-geometry terrain (1.85 km)',
    note: 'Heights are relative to the MOLA areoid. The 463 m grid cannot show rover-scale hazards.',
  },
  {
    id: 'naif',
    name: 'NASA/JPL NAIF SPICE',
    url: 'https://naif.jpl.nasa.gov/naif/',
    role: 'Sun position and body orientation for rehearsal windows (Layer 4)',
    note: 'The kernel names and checksums used are returned with every computed result.',
  },
  {
    id: 'earthdata',
    name: 'NASA Earthdata',
    url: 'https://www.earthdata.nasa.gov/',
    role: 'Not used in any result',
    note: 'Listed as a candidate resource. No NASA Earthdata product is read by TERRAWINDOW.',
  },
  {
    id: 'copernicus',
    name: 'Copernicus DEM (Copernicus Data Space)',
    url: 'https://dataspace.copernicus.eu/',
    role: 'Earth elevation model (GLO-30, 30 m), three stored regions',
    note: 'A surface model at 30 m cannot resolve the terrain scales a 5 m lunar grid can; the interface shows this explicitly.',
  },
  {
    id: 'worldcover',
    name: 'ESA WorldCover',
    url: 'https://esa-worldcover.org/',
    role: 'Land-cover context (optional, not used)',
    note: 'An optional code path only. No land-cover data is retrieved and no result uses it.',
  },
]

export const BASEMAP_CREDITS = [
  'Powered by Esri (https://www.esri.com). Imagery © Esri, Vantor, Earthstar Geographics and the GIS User Community',
  'Topographic tiles © OpenTopoMap (CC-BY-SA), data © OpenStreetMap contributors',
  'Dark base: Esri Dark Gray Canvas © Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community',
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
