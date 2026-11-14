import type { LunarRegion, Mission, Objective } from './types'

export const SLOPE_BINS = ['0–5°', '5–10°', '10–15°', '15–20°', '20–30°', '30°+'] as const
/** Upper bound of each slope bin (deg). Last bin capped at 45° for interpolation. */
export const SLOPE_EDGES = [0, 5, 10, 15, 20, 30, 45] as const

export const ROUGH_BASELINES = [10, 20, 50, 100] as const
/** Baselines (m) plotted on the roughness-by-scale chart. */
export const ROUGH_SCALES = [5, 10, 20, 50, 100, 200] as const

export const DEMO_START = '2026-12-01'
export const DEMO_HORIZON_DAYS = 60

export const OBJECTIVES: Objective[] = [
  {
    id: 'rover-nav',
    label: 'Rover mobility & navigation under low-angle illumination',
    blurb: 'Rehearse perception, path planning and traverse decisions with long shadows and grazing light.',
    active: true,
  },
  { id: 'psr', label: 'Permanently shadowed region imaging', blurb: 'Roadmap — requires low-light sensor characterisation not modelled here.', active: false },
  { id: 'isru', label: 'Regolith excavation & ISRU', blurb: 'Roadmap — requires regolith mechanics evidence this prototype does not hold.', active: false },
]

/** Perturb a base slope histogram deterministically per region so regions differ without invented precision. */
function regionHist(i: number): number[] {
  const base = [34, 26, 17, 11, 9, 3]
  const v = base.map((b, j) => b * (1 + 0.14 * Math.sin(i * 1.9 + j * 1.3)))
  const s = v.reduce((a, b) => a + b, 0)
  return v.map((x) => Math.round((x / s) * 1000) / 10)
}

const lunarDem = { name: 'LOLA gridded south-polar DEM (site product)', resM: 5 }

/** Candidate reference regions follow NASA's publicly announced Artemis III candidate-region names.
 *  Latitudes are rounded for orientation only; slope/roughness values are illustrative fixtures. */
export const LUNAR_REGIONS: LunarRegion[] = [
  ['faustini-rim-a', 'Faustini Rim A', '≈ 87°S', 'Rim of Faustini crater, adjacent to permanently shadowed terrain.'],
  ['shackleton-peak', 'Peak near Shackleton', '≈ 89.5°S', 'Elevated terrain on the Shackleton rim with long, grazing sun geometry.'],
  ['connecting-ridge', 'Connecting Ridge', '≈ 89°S', 'Ridge linking the Shackleton and de Gerlache rims.'],
  ['connecting-ridge-ext', 'Connecting Ridge Extension', '≈ 88.5°S', 'Southern continuation of the connecting ridge.'],
  ['de-gerlache-rim-2', 'de Gerlache Rim 2', '≈ 88.5°S', 'Rim segment of de Gerlache crater.'],
  ['de-gerlache-kocher', 'de Gerlache–Kocher Massif', '≈ 88°S', 'Massif between de Gerlache and Kocher craters.'],
  ['haworth', 'Haworth', '≈ 87.5°S', 'Floor and rim terrain near Haworth crater.'],
  ['malapert', 'Malapert Massif', '≈ 86°S', 'Isolated massif with comparatively long periods of sun and Earth visibility.'],
  ['leibnitz-beta', 'Leibnitz Beta Plateau', '≈ 85°S', 'Plateau terrain in the Leibnitz region.'],
].map(([id, name, approxLat, summary], i) => ({
  id,
  name,
  approxLat,
  summary,
  dem: lunarDem,
  slopeHist: regionHist(i),
  rough: { a: 0.42 + 0.05 * Math.sin(i * 2.3), h: 0.8 },
  seed: 100 + i * 7,
}))

export const DEFAULT_MISSION: Mission = {
  regionId: 'shackleton-peak',
  objectiveId: 'rover-nav',
  slopeMax: 10,
  minTraversable: 60,
  roughBaseline: 20,
  roughMax: 1.5,
  elMin: 0.5,
  elMax: 3,
  minDuration: 15,
  maxDemRes: 10,
}

export const MISSION_REQUIREMENTS = [
  'Mobility: slope and roughness within the rover screening limits at a resolvable baseline.',
  'Navigation: sun held within a low, grazing elevation band so shadow length and glare resemble the lunar south-polar case.',
  'Evidence: terrain data fine enough to support the chosen baseline — otherwise the criterion stays Not Yet Assessed.',
]
