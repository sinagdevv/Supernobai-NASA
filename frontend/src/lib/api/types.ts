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

/** A dataset that Layer 2 has fetched and validated into the local store. `ready` is the validation verdict, not proof the file is on this machine. */
export interface StoredDataset extends DatasetInfo {
  ready: boolean
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
