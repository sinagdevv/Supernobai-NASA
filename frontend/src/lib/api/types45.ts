/*
 * Contract types for Layer 4 (solar geometry / rehearsal windows) and Layer 5 (mission suitability and evidence).
 * Checked against live responses of /v1/rehearsal/evaluate and /v1/suitability/assess. Re-exported from types.ts.
 */

export interface RehearsalStatus {
  package_installed: boolean
  kernels_present: Record<string, boolean>
  bodies: { earth: boolean; moon: boolean; mars: boolean }
  mars_native_source: { ready: boolean; grid: string } | null
  observational_validation: string
}

export interface GeoBBox { west: number; south: number; east: number; north: number; crs: 'geographic' }
export interface PatchRequest { dataset: { id: string }; bbox?: GeoBBox; scales_m?: number[]; relief_windows_m?: number[] }

export interface RehearsalCriteriaInput {
  minimum_continuous_illumination_minutes?: number
  minimum_valid_terrain_coverage_percent?: number
  solar_elevation_min_deg?: number
  solar_elevation_max_deg?: number
  solar_azimuth_min_deg?: number
  solar_azimuth_max_deg?: number
  maximum_terrain_obstruction_percent?: number
}

export interface RehearseRequest {
  candidate: PatchRequest
  start_utc: string
  end_utc: string
  step_minutes: number
  criteria?: RehearsalCriteriaInput
  max_distance_m?: number
  scale_m?: number
}

/** What the engine decided about the target pixel at one sample. INSUFFICIENT_COVERAGE means "could not be determined", not dark. */
export type TargetClass = 'ILLUMINATED' | 'TERRAIN_OBSTRUCTED' | 'SURFACE_FACING_AWAY' | 'INSUFFICIENT_COVERAGE' | 'NO_DATA' | 'UNKNOWN'

export interface RehearsalObservation {
  time_utc: string
  interval_end_utc: string
  target_classification: TargetClass
  target_ray_status: string
  solar_elevation_deg: number
  solar_azimuth_deg: number
  valid_terrain_coverage_percent: number
  terrain_obstruction_percent: number
  ray_support_percent_of_valid_terrain: number
  measured_terrain_coverage_percent: number | null
}

export interface RehearsalInterval {
  start_utc: string
  end_utc: string
  duration_seconds: number
  sample_count: number
  minimum_valid_terrain_coverage_percent: number
  maximum_terrain_obstruction_percent: number
  solar_elevation_min_deg: number
  solar_elevation_max_deg: number
  solar_azimuth_start_deg: number
  solar_azimuth_end_deg: number
  criteria_satisfied?: string[]
  criteria_failed?: string[]
  is_candidate?: boolean
}

export interface RehearsalEvidence {
  implementation_status: string
  synthetic_verification_status: string
  real_terrain_execution_status: string
  observational_validation_status: string
  details?: Record<string, unknown>
}

export interface KernelIdentity { roles: string[]; filename: string; sha256: string; status: string; warning: string | null }

/** The raw Layer 4 result. It is also what Layer 5 takes as `layer4_result`, so the interface passes it on unchanged. */
export interface RehearsalResult {
  body: 'earth' | 'moon' | 'mars'
  start_utc: string
  end_utc: string
  step_seconds: number
  boundary_uncertainty_seconds: number
  target_pixel: [number, number]
  observations: RehearsalObservation[]
  continuous_illumination_intervals: RehearsalInterval[]
  candidate_windows: RehearsalInterval[]
  interruptions: { start_utc: string; end_utc: string; duration_seconds: number; target_classification_durations_seconds?: Record<string, number> }[]
  total_illumination_duration_seconds: number
  total_qualifying_illumination_duration_seconds: number
  classification_counts: Record<string, number>
  ray_status_counts: Record<string, number>
  valid_terrain_coverage_mean_percent: number
  terrain_obstruction_mean_percent: number
  terrain_obstruction_max_percent: number
  solar_elevation_min_deg: number
  solar_elevation_max_deg: number
  solar_azimuth_start_deg: number
  solar_azimuth_end_deg: number
  solar_azimuth_span_deg: number
  criteria: Record<string, number | null | string>
  provenance: Record<string, unknown>
  scientific_limitations: string[]
  kernel_identities: KernelIdentity[]
  evidence: RehearsalEvidence
  target_longitude_deg: number
  target_latitude_deg: number
  target_coordinate_frame: string
  analysis_grid: { shape: [number, number]; pixel_size_m: number; native_pixel_size_m?: number; resampling?: string; target_lonlat?: [number, number] }
  source_grid_id?: string | null
  generated_at: string
}

export type CriterionOperator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'within_range'
export type MissingDataBehavior = 'INDETERMINATE' | 'NOT_ASSESSED'

export interface MissionCriterionDef {
  id: string
  name: string
  category: string
  description: string
  source_layer: 'layer3' | 'layer4'
  source_metric: string
  operator: CriterionOperator
  target_value?: number
  target_range?: { min: number; max: number }
  equality_tolerance?: number
  unit: string
  required: boolean
  missing_data_behavior: MissingDataBehavior
  rationale: string
  scale_m?: number
  window_m?: number
  threshold_deg?: number
}

export interface MissionProfileDef { id: string; name: string; description: string; required_categories: string[]; criteria: MissionCriterionDef[] }

export interface AssessRequest {
  candidate_id: string
  candidate_name?: string
  candidate: PatchRequest
  mission_profile: MissionProfileDef
  layer4_result?: RehearsalResult | null
}

export type CriterionVerdict = 'PASS' | 'FAIL' | 'UNVERIFIED' | 'INDETERMINATE' | 'NOT_ASSESSED'
export type OverallVerdict = 'SUITABLE' | 'NOT_SUITABLE' | 'INDETERMINATE' | 'PARTIALLY_ASSESSED'

export interface CriterionResult {
  criterion_id: string
  name: string
  category: string
  source_layer: 'layer3' | 'layer4'
  source_metric: string
  required: boolean
  status: CriterionVerdict
  measured_value: number | null
  claimed_value: number | null
  unit: string
  operator: CriterionOperator
  target_value: number | null
  target_range: { min: number; max: number } | null
  explanation: string
  evidence_id?: string
}

export interface SuitabilityGap { id: string; category: string; description: string; assessment_effect: string; additional_evidence_needed: string; affected_criteria?: string[] }

export interface MissionAssessment {
  assessment_id: string
  candidate: { id: string; name: string | null; body: 'earth' | 'moon' | 'mars'; dataset_id: string | null; area_km2?: number }
  mission_profile_id: string
  mission_profile_name: string
  assessed_at_utc: string
  overall_status: OverallVerdict
  overall_explanation: string
  profile_completeness: { status: string; required_categories: string[]; category_statuses: Record<string, string>; note?: string }
  spatial_association: { status: 'MATCHED_METADATA_UNVERIFIED' | 'MISMATCHED' | 'UNPAIRED'; checks: Record<string, string>; limitations: string[] } | null
  criterion_results: CriterionResult[]
  suitability_gaps: SuitabilityGap[]
  uncertainty_and_limitations: string[]
  layer3_provenance?: { dataset_id?: string | null; dataset_name?: string; citation?: string | null }
  layer4_provenance?: { trust_status?: string } | null
}
