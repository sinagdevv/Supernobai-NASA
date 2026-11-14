/*
 * Contract types for the Layer 2/3 service (backend/geoprocessing). Written from docs/layer3-api-contract.md and
 * checked against live responses. Only the parts the interface reads are modelled; the service returns more.
 */

export interface Health { status: string; service: string; version: string }

export interface DatasetInfo {
  id: string
  name: string
  body: 'earth' | 'moon' | 'mars'
  kind: string
  nominal_resolution_m: number
  coverage?: string
  citation: string
  license: string
}

/** Whether the dataset's file can be used now, judged by the service from the file itself. */
export type Availability =
  | { status: 'available'; detail: null; setup: null }
  | { status: 'missing' | 'unreadable' | 'not_validated'; detail: string; setup: string }

/** A dataset in the Layer 2 store. `ready` means usable now (file present and readable); `validated` is Layer 2's recorded verdict. */
export interface StoredDataset extends DatasetInfo {
  ready: boolean
  availability: Availability
  validated: boolean | null
  summary: { pixel_size_m: number; extent_km: [number, number]; center_lonlat: [number, number]; valid_fraction: number } | null
}

export interface DatasetsResponse { datasets: DatasetInfo[]; stored_datasets: StoredDataset[] }

export interface Provenance {
  dataset_id: string | null
  dataset_name: string
  sources: string[]
  citation: string | null
  native_crs: string
  native_pixel_size_m: number
  working_crs: string
  working_pixel_size_m: number
  resampling: string
  vertical_unit: string
  methods: Record<string, string>
  engine_version: string
  generated_at: string
}

export interface TerrainProfile {
  patch: { body: 'earth' | 'moon' | 'mars'; center_lon: number; center_lat: number; area_km2: number }
  provenance: Provenance
  coverage: { valid_fraction: number; sufficient: boolean }
  skipped: { item: string; code: string; reason: string }[]
  limitations: string[]
}

export type CriterionStatus = 'within_tolerance' | 'outside_tolerance' | 'not_assessed'

export interface ComparisonCriterion {
  metric: string
  scale_m: number | null
  unit: string
  reference: number | null
  candidate: number | null
  difference: number | null
  tolerance: number | null
  tolerance_kind: 'absolute' | 'relative'
  normalized_difference: number | null
  status: CriterionStatus
  reason: string | null
}

export interface ComparisonResult {
  common_scales_m: number[]
  criteria: ComparisonCriterion[]
  counts: { within_tolerance: number; outside_tolerance: number; not_assessed: number }
  notes: string[]
  tolerances: Record<string, number>
  reference_profile: TerrainProfile
  candidate_profile: TerrainProfile
}

export interface CompareRequest {
  reference: { dataset: { id: string } }
  candidate: { dataset: { id: string } }
  scales_m?: number[]
}

export type LonLat = [number, number]

export type OverlayLayer = 'slope' | 'hillshade' | 'elevation'

export interface OverlayRequest {
  dataset: { id: string }
  layer: OverlayLayer
  sun_azimuth_deg?: number
  sun_elevation_deg?: number
}

/** A rendered raster as PNG plus its footprint. `coordinates` are the image corners (top-left, top-right, bottom-right, bottom-left) in lon/lat. */
export interface OverlayResponse {
  layer: OverlayLayer
  media_type: 'image/png'
  image_base64: string
  coordinates: [LonLat, LonLat, LonLat, LonLat]
  width: number
  height: number
  scale_m: number
  value_range: [number, number]
  unit: string
  legend: { value: number; color: string }[]
  provenance: Provenance
}

export interface ScreenRequest {
  dataset: { id: string }
  patch_size_m: number
  criteria: { slope_mean_deg?: { min?: number; max?: number }; slope_p90_deg?: { min?: number; max?: number } }
}

export type PatchStatus = 'candidate' | 'rejected' | 'insufficient_data'

export interface PatchCriterion {
  criterion: string
  unit: string
  value: number | null
  min: number | null
  max: number | null
  status: 'pass' | 'fail' | 'not_assessed'
  reason: string | null
}

export interface PatchMetrics {
  coverage_fraction: number
  slope_mean_deg: number | null
  slope_median_deg: number | null
  slope_p90_deg: number | null
  slope_max_deg: number | null
  roughness_rms_height_m: number | null
  relief_m: number | null
  elevation_mean_m: number | null
}

export interface PatchFeature {
  type: 'Feature'
  id: string
  geometry: { type: 'Polygon'; coordinates: LonLat[][] }
  properties: { id: string; status: PatchStatus; center_lon: number; center_lat: number; patch_size_m: number; scale_m: number; metrics: PatchMetrics; criteria: PatchCriterion[]; not_assessed: string[] }
}

export interface ScreenResponse {
  type: 'FeatureCollection'
  features: PatchFeature[]
  summary: { cells: number; candidate: number; rejected: number; insufficient_data: number; scale_m: number; patch_size_m: number }
  provenance: Provenance
  limitations: string[]
}
