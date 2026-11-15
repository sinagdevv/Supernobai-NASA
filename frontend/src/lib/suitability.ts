import type { AssessRequest, CriterionVerdict, MissionAssessment, MissionCriterionDef, MissionProfileDef, OverallVerdict, RehearsalResult } from './api/types'
import type { Planet } from './profiles'
import { primaryTarget, type RehearsalTarget } from './rehearsal'

/*
 * Pure logic for Layer 5 (mission suitability and evidence): each planet's own default criteria, how edits become the
 * mission profile the service receives, and how a verdict is labelled. Thresholds are assumptions the user can change,
 * not standards, and Moon and Mars are defined independently: nothing is shared between them but the shape.
 */

export interface CriterionSpec {
  def: Omit<MissionCriterionDef, 'target_value' | 'scale_m'>
  /** True when the metric needs a `scale_m` (slope and roughness metrics). */
  scaled?: boolean
  default: number
  min: number
  max: number
  step: number
  /** The editor shows `target / factor` in `shownUnit`; the service always receives `target` in the metric's own unit. */
  shown?: { unit: string; factor: number }
}

const base = { required: true, missing_data_behavior: 'INDETERMINATE' as const }

const MOON_RATIONALE = 'Assumption for screening a low-gravity (1.62 m/s²), airless surface. A mission team sets the real limit.'
const MARS_RATIONALE = 'Assumption for regional screening at the data’s coarse scale. Mars gravity (3.73 m/s²), dust and a thin atmosphere change what a rover can drive, so these limits are set for Mars on their own, not borrowed from another body.'

/** Moon: south-polar rover mobility under low sun. */
const MOON: CriterionSpec[] = [
  { scaled: true, default: 20, min: 5, max: 35, step: 1, def: { ...base, id: 'slope-p90', name: '90th-percentile slope', category: 'terrain', description: 'The slope that 90 % of the patch is below, at the analysis scale.', source_layer: 'layer3', source_metric: 'terrain.slope.p90_deg', operator: 'lte', unit: 'degrees', rationale: MOON_RATIONALE } },
  { scaled: true, default: 0.15, min: 0, max: 1, step: 0.05, def: { ...base, id: 'steep-share', name: 'Share steeper than 20°', category: 'terrain', description: 'Fraction of the patch steeper than 20°.', source_layer: 'layer3', source_metric: 'terrain.slope.fraction_steeper_than', operator: 'lte', unit: 'fraction', threshold_deg: 20, rationale: MOON_RATIONALE } },
  { scaled: true, default: 1.5, min: 0.1, max: 6, step: 0.1, def: { ...base, id: 'roughness', name: 'Median roughness (RMS height)', category: 'terrain', description: 'Median detrended RMS height in a moving window at the analysis scale.', source_layer: 'layer3', source_metric: 'terrain.roughness.rms_height_median_m', operator: 'lte', unit: 'metres', rationale: MOON_RATIONALE } },
  { default: 0.9, min: 0.5, max: 1, step: 0.05, def: { ...base, id: 'coverage', name: 'Valid elevation coverage', category: 'data-coverage', description: 'Fraction of the patch with a valid elevation value.', source_layer: 'layer3', source_metric: 'terrain.coverage.valid_fraction', operator: 'gte', unit: 'fraction', rationale: 'Terrain statistics from mostly empty data are not evidence.' } },
  { default: 3600, min: 600, max: 86_400, step: 600, shown: { unit: 'min', factor: 60 }, def: { ...base, id: 'illumination', name: 'Qualifying illumination', category: 'illumination', description: 'Total time inside candidate windows from the Rehearsal Windows calculation. A claim from Layer 4: shown, never passed or failed.', source_layer: 'layer4', source_metric: 'rehearsal.total_qualifying_illumination_duration_seconds', operator: 'gte', unit: 'seconds', rationale: 'Low-sun rehearsal needs sustained, usable light.' } },
  { default: 50, min: 0, max: 100, step: 5, def: { ...base, id: 'obstruction', name: 'Peak terrain shadow', category: 'illumination', description: 'Highest share of the patch shadowed by terrain at any sample, from the Layer 4 calculation.', source_layer: 'layer4', source_metric: 'rehearsal.terrain_obstruction_max_percent', operator: 'lte', unit: 'percent', rationale: 'A heavily shadowed patch is a poor place to test camera and hazard detection.' } },
]

/** Mars: regional terrain at MOLA's coarse scale. No lunar threshold is reused; Layer 4 here runs on a different (1.85 km) grid than Layer 3 (463 m), so its claims arrive as not assessed. */
const MARS: CriterionSpec[] = [
  { scaled: true, default: 10, min: 2, max: 30, step: 1, def: { ...base, id: 'slope-p90', name: '90th-percentile slope', category: 'terrain', description: 'The slope that 90 % of the region is below, at 926 m (two MOLA pixels).', source_layer: 'layer3', source_metric: 'terrain.slope.p90_deg', operator: 'lte', unit: 'degrees', rationale: MARS_RATIONALE } },
  { scaled: true, default: 0.05, min: 0, max: 1, step: 0.01, def: { ...base, id: 'steep-share', name: 'Share steeper than 10°', category: 'terrain', description: 'Fraction of the region steeper than 10° at the analysis scale.', source_layer: 'layer3', source_metric: 'terrain.slope.fraction_steeper_than', operator: 'lte', unit: 'fraction', threshold_deg: 10, rationale: MARS_RATIONALE } },
  { scaled: true, default: 40, min: 5, max: 150, step: 5, def: { ...base, id: 'roughness', name: 'Median roughness (RMS height)', category: 'terrain', description: 'Median detrended RMS height in a moving window at the analysis scale (kilometre windows, not rover scale).', source_layer: 'layer3', source_metric: 'terrain.roughness.rms_height_median_m', operator: 'lte', unit: 'metres', rationale: MARS_RATIONALE } },
  { default: 0.9, min: 0.5, max: 1, step: 0.05, def: { ...base, id: 'coverage', name: 'Valid elevation coverage', category: 'data-coverage', description: 'Fraction of the region with a valid elevation value.', source_layer: 'layer3', source_metric: 'terrain.coverage.valid_fraction', operator: 'gte', unit: 'fraction', rationale: 'Terrain statistics from mostly empty data are not evidence.' } },
  { default: 3600, min: 600, max: 86_400, step: 600, shown: { unit: 'min', factor: 60 }, def: { ...base, id: 'illumination', name: 'Qualifying illumination', category: 'illumination', description: 'Total time inside candidate windows from the Mars Rehearsal Windows calculation (1.85 km MOLA grid). A claim from Layer 4, and on a different grid from the terrain statistics, so it cannot be paired with them.', source_layer: 'layer4', source_metric: 'rehearsal.total_qualifying_illumination_duration_seconds', operator: 'gte', unit: 'seconds', rationale: 'Solar-powered operation needs sustained light; this is a usable-light check, not an energy budget.' } },
]

export const SPECS: Record<Planet, CriterionSpec[]> = { moon: MOON, mars: MARS }
export const categoriesOf = (planet: Planet) => [...new Set(SPECS[planet].map((s) => s.def.category))]

export const CATEGORY_LABEL: Record<string, string> = { terrain: 'Terrain', 'data-coverage': 'Data coverage', illumination: 'Illumination (Layer 4)' }

export interface CriterionEdit { enabled: boolean; target: number; required: boolean }
export type Edits = Record<string, CriterionEdit>

export const defaultEdits = (planet: Planet): Edits => Object.fromEntries(SPECS[planet].map((s) => [s.def.id, { enabled: true, target: s.default, required: true }]))

const ids: Record<Planet, { id: string; name: string; description: string }> = {
  moon: { id: 'terrawindow-moon-rover-low-sun', name: 'Lunar south-polar rover mobility, low sun', description: 'Default lunar screening criteria. Thresholds are adjustable assumptions, not standards.' },
  mars: { id: 'terrawindow-mars-regional-terrain', name: 'Martian regional terrain screening', description: 'Default Mars screening criteria, defined separately from the lunar ones. Thresholds are adjustable assumptions, not standards.' },
}

/** The profile the service receives. Every category stays declared as required, so switching a category off makes the profile incomplete rather than quietly easier. */
export function buildProfile(planet: Planet, edits: Edits, scaleM: number): MissionProfileDef | null {
  const criteria: MissionCriterionDef[] = SPECS[planet]
    .filter((s) => edits[s.def.id]?.enabled)
    .map((s) => {
      const e = edits[s.def.id]
      const c: MissionCriterionDef = { ...s.def, required: e.required, target_value: e.target }
      if (s.scaled) c.scale_m = scaleM
      return c
    })
  if (criteria.length === 0) return null
  return { ...ids[planet], required_categories: categoriesOf(planet), criteria }
}

/** The Layer 4 result is attached only when it describes this same target; anything else would be pairing evidence from another place. */
export function buildAssessRequest(planet: Planet, target: RehearsalTarget, edits: Edits, layer4: RehearsalResult | null): AssessRequest | null {
  const scale = target.candidate.scales_m?.[0]
  if (scale === undefined) return null
  const profile = buildProfile(planet, edits, scale)
  if (!profile) return null
  // Earth's sun is not the Martian sun: an Earth analog assessed against Mars criteria never gets a rehearsal result.
  const l4 = layer4 && layer4.body === target.body && !(planet === 'mars' && target.body === 'earth') ? layer4 : null
  return { candidate_id: target.key, candidate_name: target.label, candidate: target.candidate, mission_profile: profile, layer4_result: l4 }
}

/* ───────────── How a verdict is shown ───────────── */

export type Tone = 'pass' | 'fail' | 'claim' | 'missing'

/** Only a measured PASS is positive. A claim, a gap and a non-assessment each get their own non-green treatment. */
export const CRITERION_META: Record<CriterionVerdict, { label: string; tone: Tone; meaning: string }> = {
  PASS: { label: 'Pass', tone: 'pass', meaning: 'Measured by the service from the stored terrain, and within the threshold.' },
  FAIL: { label: 'Fail', tone: 'fail', meaning: 'Measured by the service from the stored terrain, and outside the threshold.' },
  UNVERIFIED: { label: 'Unverified claim', tone: 'claim', meaning: 'A value claimed by the Layer 4 calculation. The service does not verify it, so it is shown but never passed or failed.' },
  INDETERMINATE: { label: 'Indeterminate', tone: 'missing', meaning: 'The evidence needed is missing, so this cannot be decided either way.' },
  NOT_ASSESSED: { label: 'Not assessed', tone: 'missing', meaning: 'This could not be assessed, for example because the Layer 4 result is for a different grid than the terrain.' },
}

export const OVERALL_META: Record<OverallVerdict, { label: string; tone: Tone; caution: string }> = {
  SUITABLE: { label: 'Configured thresholds met', tone: 'pass', caution: 'Every required criterion passed on measured evidence. This is not a safety or readiness finding.' },
  NOT_SUITABLE: { label: 'Not suitable on these thresholds', tone: 'fail', caution: 'At least one required, measured criterion failed.' },
  INDETERMINATE: { label: 'Indeterminate', tone: 'missing', caution: 'Evidence is missing, so there is no verdict.' },
  PARTIALLY_ASSESSED: { label: 'Partially assessed', tone: 'missing', caution: 'Some criteria were assessed and others could not be. There is no overall verdict.' },
}

export const SPATIAL_META: Record<string, { label: string; text: string }> = {
  MATCHED_METADATA_UNVERIFIED: { label: 'Matched, not authenticated', text: 'The Layer 4 result’s source, projection and grid metadata match this candidate. The match is not authenticated and does not prove the contents are the same.' },
  MISMATCHED: { label: 'Mismatched', text: 'The Layer 4 result is on a different grid or source than this candidate’s terrain, so its values cannot be paired with the terrain statistics.' },
  UNPAIRED: { label: 'No Layer 4 result', text: 'No rehearsal calculation was supplied, so illumination criteria have no evidence.' },
}

export interface AssessmentTally { pass: number; fail: number; claim: number; missing: number; total: number }

export function tally(a: MissionAssessment): AssessmentTally {
  const t: AssessmentTally = { pass: 0, fail: 0, claim: 0, missing: 0, total: a.criterion_results.length }
  for (const c of a.criterion_results) t[CRITERION_META[c.status].tone]++
  return t
}

export function fmtValue(v: number | null, unit: string): string {
  if (v === null) return '—'
  if (unit === 'seconds') return v >= 3600 ? `${(v / 3600).toFixed(v % 3600 ? 1 : 0)} h` : `${Math.round(v / 60)} min`
  const n = Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toFixed(3)
  return `${Number(n)}${unit === 'fraction' || unit === 'count' ? '' : unit === 'percent' ? ' %' : unit === 'degrees' ? '°' : unit === 'metres' ? ' m' : ` ${unit}`}`
}

const OP: Record<string, string> = { gt: '>', gte: '≥', lt: '<', lte: '≤', eq: '=' }
export function fmtTarget(c: Pick<MissionAssessment['criterion_results'][number], 'operator' | 'target_value' | 'target_range' | 'unit'>): string {
  if (c.operator === 'within_range' && c.target_range) return `${fmtValue(c.target_range.min, c.unit)} to ${fmtValue(c.target_range.max, c.unit)}`
  return `${OP[c.operator] ?? c.operator} ${fmtValue(c.target_value, c.unit)}`
}

/**
 * The patch an Earth analog is assessed on, per planet. Against lunar criteria it is the same window and grid Layer 4 ran on, so the two
 * layers can be paired. Against Mars criteria it is the whole stored dataset at 926 m (two MOLA pixels), the regional scale those criteria are
 * defined for; Layer 4 for Earth is not attached to it, because Earth's sun is not the Martian sun.
 */
export function analogTarget(planet: Planet, earth: RehearsalTarget): RehearsalTarget {
  if (planet === 'moon') return earth
  const scales_m = primaryTarget('mars').candidate.scales_m
  return { ...earth, bbox: undefined, scaleM: scales_m?.[0], candidate: { dataset: earth.candidate.dataset, scales_m } }
}
