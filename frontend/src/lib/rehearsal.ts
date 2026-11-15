import type { Planet } from './profiles'
import type { GeoBBox, RehearseRequest, RehearsalCriteriaInput, RehearsalResult, StoredDataset, TargetClass } from './api/types'

/*
 * Pure logic for the Layer 4 (rehearsal windows) screen: which stored dataset a target maps to, the request it
 * produces, whether a request is inside the engine's limits, and how a response is summarised. Nothing here calls
 * the service; the result is whatever the engine returned.
 */

export const MAX_SAMPLES = 96
export const MAX_SPAN_DAYS = 30
/** The Earth orientation kernel in the service stops here; later Earth dates are rejected by the engine. */
export const EARTH_KERNEL_END = '2027-02-08'
export const DEFAULT_START = '2026-12-14'

/** A place the engine can evaluate: a stored dataset, plus how the request must be shaped for its body. */
export interface RehearsalTarget {
  /** Stable key for stored state: `moon`, `mars` or `earth:<dataset id>`. */
  key: string
  body: 'moon' | 'mars' | 'earth'
  datasetId: string
  label: string
  place: string
  /** Grid the engine analyses on, in metres. Absent for Mars, whose native 32 ppd MOLA grid is used as is. */
  scaleM?: number
  /** Sun/terrain search distance. Mars needs a short one: the default 50 km almost always lands on unobserved bins. */
  maxDistanceM?: number
  /** Earth: a window around the dataset centre. Mars: a small box whose centre is the target. Moon: none, the whole raster is used. */
  bbox?: GeoBBox
  /** `PatchRequest` shared with Layer 5, so both layers describe the same patch. */
  candidate: { dataset: { id: string }; bbox?: GeoBBox; scales_m?: number[] }
}

export const MOON_SITE01: RehearsalTarget = {
  key: 'moon', body: 'moon', datasetId: 'lola-5mpp-site01', label: 'Site01 · Connecting ridge', place: 'Lunar south pole, about 89.46° S',
  scaleM: 40, candidate: { dataset: { id: 'lola-5mpp-site01' }, scales_m: [40] },
}

export const MARS_JEZERO: RehearsalTarget = {
  key: 'mars', body: 'mars', datasetId: 'jezero-mola-megdr128', label: 'Jezero region', place: 'Mars, 18.4° N 77.5° E',
  maxDistanceM: 10_000, bbox: { west: 77.45, south: 18.35, east: 77.55, north: 18.45, crs: 'geographic' }, candidate: { dataset: { id: 'jezero-mola-megdr128' }, scales_m: [926.1153344] },
}

export const primaryTarget = (planet: Planet): RehearsalTarget => (planet === 'moon' ? MOON_SITE01 : MARS_JEZERO)

/** Half-width of the Earth window in degrees: the engine needs at least ~0.07° and at most 200,000 cells (0.1° is about 110,000 at 30 m). */
const EARTH_HALF = 0.05

/** An Earth analog is a stored Earth dataset, evaluated on a 0.1° window around its centre at its 30 m grid. */
export function earthTarget(d: Pick<StoredDataset, 'id' | 'name' | 'summary' | 'region'>): RehearsalTarget | null {
  const c = d.summary?.center_lonlat
  if (!c) return null
  const r = (n: number) => Math.round(n * 1e4) / 1e4
  const bbox: GeoBBox = { west: r(c[0] - EARTH_HALF), south: r(c[1] - EARTH_HALF), east: r(c[0] + EARTH_HALF), north: r(c[1] + EARTH_HALF), crs: 'geographic' }
  return {
    key: `earth:${d.id}`, body: 'earth', datasetId: d.id, label: d.region?.name ? d.region.name.replace(/-/g, ' ') : d.name, place: `Earth analog, ${c[1].toFixed(2)}° N ${Math.abs(c[0]).toFixed(2)}° ${c[0] < 0 ? 'W' : 'E'}`,
    scaleM: 30, bbox, candidate: { dataset: { id: d.id }, bbox, scales_m: [30] },
  }
}

export interface RehearsalParams {
  /** YYYY-MM-DD, interpreted as 00:00 UTC. */
  startDate: string
  days: number
  stepMinutes: number
  minContinuousMinutes: number
  minCoveragePercent: number
  maxObstructionPercent: number
  /** null leaves the sun's elevation unconstrained. */
  elevationMin: number | null
  elevationMax: number | null
}

export const STEP_OPTIONS = [30, 60, 120, 240, 360, 720]

export function defaultParams(planet: Planet | 'earth'): RehearsalParams {
  const base = { startDate: DEFAULT_START, minContinuousMinutes: 60, minCoveragePercent: 90, maxObstructionPercent: 50 }
  if (planet === 'mars') return { ...base, days: 3, stepMinutes: 120, elevationMin: null, elevationMax: null }
  // Moon and the Earth analog share the low-sun band used to rehearse lunar lighting.
  return { ...base, days: planet === 'earth' ? 2 : 7, stepMinutes: planet === 'earth' ? 60 : 120, elevationMin: 0.5, elevationMax: 10 }
}

const DAY_MS = 86_400_000
const parseDate = (s: string) => (/^\d{4}-\d{2}-\d{2}$/.test(s) ? Date.parse(`${s}T00:00:00Z`) : NaN)
export const addDays = (s: string, n: number) => new Date(parseDate(s) + n * DAY_MS).toISOString().slice(0, 10)

export function sampleCount(p: Pick<RehearsalParams, 'days' | 'stepMinutes'>) {
  return Math.ceil((p.days * 1440) / p.stepMinutes)
}

/** The first thing wrong with the parameters, in the user's words, or null when the engine will accept them. */
export function validateParams(t: RehearsalTarget, p: RehearsalParams): string | null {
  if (Number.isNaN(parseDate(p.startDate))) return 'Choose a start date.'
  if (!(p.days >= 1 && p.days <= MAX_SPAN_DAYS)) return `The span must be between 1 and ${MAX_SPAN_DAYS} days.`
  if (sampleCount(p) > MAX_SAMPLES) return `That is ${sampleCount(p)} samples; the engine takes at most ${MAX_SAMPLES}. Use a coarser step or a shorter span.`
  if (t.body === 'earth' && addDays(p.startDate, p.days) > EARTH_KERNEL_END) return `The Earth orientation data in the service ends on ${EARTH_KERNEL_END}. Choose earlier dates for an Earth analog.`
  if (p.elevationMin !== null && p.elevationMax !== null && p.elevationMin >= p.elevationMax) return 'The minimum solar elevation must be below the maximum.'
  return null
}

export function buildRehearseRequest(t: RehearsalTarget, p: RehearsalParams): RehearseRequest {
  const criteria: RehearsalCriteriaInput = {
    minimum_continuous_illumination_minutes: p.minContinuousMinutes,
    minimum_valid_terrain_coverage_percent: p.minCoveragePercent,
    maximum_terrain_obstruction_percent: p.maxObstructionPercent,
  }
  if (p.elevationMin !== null) criteria.solar_elevation_min_deg = p.elevationMin
  if (p.elevationMax !== null) criteria.solar_elevation_max_deg = p.elevationMax
  const req: RehearseRequest = {
    // Mars Layer 4 takes the bbox centre as the target; Layer 5 describes the whole stored region, so the bbox is added only to this request.
    candidate: t.bbox && !t.candidate.bbox ? { ...t.candidate, bbox: t.bbox } : t.candidate,
    start_utc: `${p.startDate}T00:00:00Z`,
    end_utc: `${addDays(p.startDate, p.days)}T00:00:00Z`,
    step_minutes: p.stepMinutes,
    criteria,
  }
  if (t.scaleM !== undefined) req.scale_m = t.scaleM
  if (t.maxDistanceM !== undefined) req.max_distance_m = t.maxDistanceM
  return req
}

/* ───────────── How a sample is shown ───────────── */

export interface ClassMeta {
  label: string
  /** What it means, in a sentence a reader can act on. */
  meaning: string
  /** `lit`: sun reaches the target. `dark`: it cannot. `unknown`: the engine could not tell. */
  kind: 'lit' | 'dark' | 'unknown'
}

export const CLASS_META: Record<TargetClass, ClassMeta> = {
  ILLUMINATED: { label: 'Sunlit', meaning: 'The sun reaches the target pixel along the searched horizon.', kind: 'lit' },
  TERRAIN_OBSTRUCTED: { label: 'Terrain shadow', meaning: 'Terrain between the target and the sun blocks it.', kind: 'dark' },
  SURFACE_FACING_AWAY: { label: 'Facing away', meaning: 'The slope itself faces away from the sun.', kind: 'dark' },
  INSUFFICIENT_COVERAGE: { label: 'Insufficient coverage', meaning: 'The elevation data could not support a decision. This is not shadow and not light.', kind: 'unknown' },
  NO_DATA: { label: 'No data', meaning: 'There is no elevation value at the target.', kind: 'unknown' },
  UNKNOWN: { label: 'Unknown', meaning: 'The engine did not classify this sample.', kind: 'unknown' },
}

export const CLASS_ORDER: TargetClass[] = ['ILLUMINATED', 'TERRAIN_OBSTRUCTED', 'SURFACE_FACING_AWAY', 'INSUFFICIENT_COVERAGE', 'NO_DATA', 'UNKNOWN']

export function fmtDuration(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`
  const m = seconds / 60
  if (m < 120) return `${Math.round(m)} min`
  const h = m / 60
  if (h < 48) return `${h.toFixed(h < 10 ? 1 : 0).replace(/\.0$/, '')} h`
  return `${(h / 24).toFixed(1).replace(/\.0$/, '')} days`
}

export interface RehearsalSummary {
  samples: number
  /** Number of samples per classification, in CLASS_ORDER, zeros dropped. */
  byClass: { cls: TargetClass; n: number }[]
  litSamples: number
  undeterminedSamples: number
  windowCount: number
  longestWindowSeconds: number
  litSeconds: number
  qualifyingSeconds: number
  spanSeconds: number
}

export function summarize(r: RehearsalResult): RehearsalSummary {
  const count = (c: TargetClass) => r.observations.filter((o) => o.target_classification === c).length
  const byClass = CLASS_ORDER.map((cls) => ({ cls, n: count(cls) })).filter((x) => x.n > 0)
  const undetermined = r.observations.filter((o) => CLASS_META[o.target_classification].kind === 'unknown').length
  return {
    samples: r.observations.length,
    byClass,
    litSamples: count('ILLUMINATED'),
    undeterminedSamples: undetermined,
    windowCount: r.candidate_windows.filter((w) => w.is_candidate !== false).length,
    longestWindowSeconds: Math.max(0, ...r.candidate_windows.map((w) => w.duration_seconds)),
    litSeconds: r.total_illumination_duration_seconds,
    qualifyingSeconds: r.total_qualifying_illumination_duration_seconds,
    spanSeconds: (Date.parse(r.end_utc) - Date.parse(r.start_utc)) / 1000,
  }
}

/** The one-line reading of a result. A run with no determinable sample says that, never "no windows". */
export function headline(r: RehearsalResult): { tone: 'computed' | 'insufficient'; text: string } {
  const s = summarize(r)
  if (s.samples > 0 && s.undeterminedSamples === s.samples) {
    return { tone: 'insufficient', text: 'The engine could not decide any sample at this target: the elevation data does not support it. No window can be reported, and this is not a finding of darkness.' }
  }
  const undet = s.undeterminedSamples ? ` ${s.undeterminedSamples} of ${s.samples} samples could not be decided.` : ''
  if (s.windowCount === 0) return { tone: 'computed', text: `No candidate window meets the criteria in this span.${undet}` }
  return { tone: 'computed', text: `${s.windowCount} candidate ${s.windowCount === 1 ? 'window' : 'windows'}, longest ${fmtDuration(s.longestWindowSeconds)}.${undet}` }
}

/** The sampling uncertainty sentence: windows are as coarse as the step. */
export function uncertaintyNote(r: RehearsalResult): string {
  const step = fmtDuration(r.step_seconds), u = fmtDuration(r.boundary_uncertainty_seconds)
  return `Each sample stands for ${step}. A window's start and end are known only to within ±${u}, and a lit or shadowed spell shorter than the step can be missed.`
}

/** What the evidence block says. Computed never reads as validated: only the engine's own status can change that, and it says NOT_VALIDATED. */
export function evidenceLines(r: RehearsalResult): { label: string; value: string; good: boolean }[] {
  const e = r.evidence
  const validated = e.observational_validation_status === 'VALIDATED'
  return [
    { label: 'Computed', value: 'Yes — returned by the solar-geometry engine for this request', good: e.implementation_status === 'PASS' },
    { label: 'Independently validated', value: validated ? 'Reported as validated by the engine' : `No (${e.observational_validation_status})`, good: validated },
    { label: 'Synthetic verification', value: e.synthetic_verification_status, good: false },
    { label: 'Real-terrain execution record', value: e.real_terrain_execution_status, good: false },
  ]
}

export const utc = (iso: string) => iso.replace(/\.\d+/, '').replace('T', ' ').replace(/(\+00:00|Z)$/, ' UTC')
export const utcShort = (iso: string) => utc(iso).slice(5, 16)
