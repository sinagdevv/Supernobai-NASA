/** Three-state assessment. There is deliberately NO combined similarity score. */
export type Status = 'potential' | 'not-suitable' | 'not-assessed'

export type TerrainClass = 'Basaltic lava field' | 'Cinder-cone field' | 'Volcanic summit' | 'Polar desert' | 'High-altitude plateau'

export type CriterionId = 'slope' | 'roughness' | 'illumination' | 'resolution' | 'regolith' | 'rocks' | 'environment'

export interface DemInfo {
  name: string
  /** Ground sampling distance in metres. Fixture assumption — verify against the real product. */
  resM: number
}

export interface Site {
  id: string
  name: string
  place: string
  lat: number
  lon: number
  /** Standard-time UTC offset used for local clock display (no DST). */
  tz: number
  tzLabel: string
  elevM: number
  terrain: TerrainClass
  summary: string
  heritage?: string
  dem: DemInfo
  /** % of area per slope bin (see SLOPE_BINS). Illustrative. */
  slopeHist: number[]
  /** RMS height deviation at 10 m baseline (m) and scaling exponent. Illustrative. */
  rough: { a: number; h: number }
  /** 12 chars Jan→Dec, L/M/H qualitative weather-limitation risk. Illustrative. */
  seasonalRisk: string
  limitations: string[]
  seed: number
}

export interface LunarRegion {
  id: string
  name: string
  approxLat: string
  summary: string
  dem: DemInfo
  slopeHist: number[]
  rough: { a: number; h: number }
  seed: number
}

export interface Objective {
  id: string
  label: string
  blurb: string
  active: boolean
}

export interface Mission {
  regionId: string
  objectiveId: string
  /** Rover slope limit (deg) — screening parameter, not a vehicle specification. */
  slopeMax: number
  /** Minimum share of area at or below slopeMax (%) */
  minTraversable: number
  /** Roughness baseline (m) and maximum RMS height deviation (m) at that baseline */
  roughBaseline: number
  roughMax: number
  /** Solar elevation band representing the lunar reference lighting (deg above horizon) */
  elMin: number
  elMax: number
  /** Minimum minutes the sun must stay inside the band for a day to qualify */
  minDuration: number
  /** Highest acceptable DEM ground-sampling distance (m) for the screening scale */
  maxDemRes: number
}

export interface Source {
  id: string
  name: string
  url: string
  role: string
  note: string
}

export interface Criterion {
  id: CriterionId
  label: string
  status: Status
  /** One-line, evidence-first reason */
  reason: string
  /** Core criteria drive the overall category */
  core: boolean
  /** Longer explanation for expandable panels */
  detail: string
}

export interface Assessment {
  siteId: string
  overall: Status
  assessedCount: number
  totalCount: number
  criteria: Criterion[]
  qualifyingDays: number
}
