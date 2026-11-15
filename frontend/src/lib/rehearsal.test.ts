import { describe, expect, it } from 'vitest'
import type { RehearsalResult } from './api/types'
import { addDays, buildRehearseRequest, defaultParams, earthTarget, fmtDuration, headline, MARS_JEZERO, MOON_SITE01, sampleCount, summarize, uncertaintyNote, validateParams } from './rehearsal'

const obs = (cls: string) => ({ target_classification: cls, time_utc: '2026-12-14T00:00:00+00:00', interval_end_utc: '2026-12-14T02:00:00+00:00' })
const result = (classes: string[], windows = 0): RehearsalResult => ({
  body: 'mars', start_utc: '2026-12-14T00:00:00+00:00', end_utc: '2026-12-15T00:00:00+00:00', step_seconds: 7200, boundary_uncertainty_seconds: 7200,
  observations: classes.map(obs), candidate_windows: Array.from({ length: windows }, () => ({ duration_seconds: 7200, is_candidate: true })),
  total_illumination_duration_seconds: 0, total_qualifying_illumination_duration_seconds: 0,
  evidence: { implementation_status: 'PASS', synthetic_verification_status: 'NOT_RUN', real_terrain_execution_status: 'NOT_AVAILABLE', observational_validation_status: 'NOT_VALIDATED' },
} as unknown as RehearsalResult)

describe('rehearsal requests', () => {
  it('Moon uses the whole Site01 raster at 40 m, with the same scale in both layers', () => {
    const req = buildRehearseRequest(MOON_SITE01, defaultParams('moon'))
    expect(req.candidate).toEqual({ dataset: { id: 'lola-5mpp-site01' }, scales_m: [40] })
    expect(req.scale_m).toBe(40)
    expect(req.candidate.bbox).toBeUndefined()
    expect(req.start_utc).toBe('2026-12-14T00:00:00Z')
    expect(req.end_utc).toBe('2026-12-21T00:00:00Z')
  })

  it('Mars runs on the native MOLA grid with a 10 km search, and sends no scale', () => {
    const req = buildRehearseRequest(MARS_JEZERO, defaultParams('mars'))
    expect(req.max_distance_m).toBe(10_000)
    expect(req.scale_m).toBeUndefined()
    expect(req.criteria).not.toHaveProperty('solar_elevation_min_deg')
    // The engine needs a Mars bbox whose centre is the target; Layer 5 keeps describing the whole region.
    expect(req.candidate.bbox).toMatchObject({ west: 77.45, east: 77.55, crs: 'geographic' })
    expect(MARS_JEZERO.candidate.bbox).toBeUndefined()
  })

  it('an Earth analog is a 0.1 degree window centred on the stored dataset, in geographic coordinates', () => {
    const t = earthTarget({ id: 'sp-crater-copernicus-glo30', name: 'SP', region: { name: 'sp-crater', bbox_lonlat: [0, 0, 0, 0], parent_dataset: 'x' }, summary: { pixel_size_m: 30, extent_km: [16, 16], center_lonlat: [-111.63, 35.58], valid_fraction: 1 } })!
    expect(t.bbox).toEqual({ west: -111.68, south: 35.53, east: -111.58, north: 35.63, crs: 'geographic' })
    expect(t.key).toBe('earth:sp-crater-copernicus-glo30')
    expect(t.label).toBe('sp crater')
    expect(buildRehearseRequest(t, defaultParams('earth')).scale_m).toBe(30)
  })

  it('an Earth dataset without a summary cannot be targeted', () => {
    expect(earthTarget({ id: 'x', name: 'x', summary: null, region: null })).toBeNull()
  })

  it('converts minutes of continuous light and omits an unset elevation band', () => {
    const req = buildRehearseRequest(MARS_JEZERO, { ...defaultParams('mars'), minContinuousMinutes: 90 })
    expect(req.criteria).toMatchObject({ minimum_continuous_illumination_minutes: 90, minimum_valid_terrain_coverage_percent: 90, maximum_terrain_obstruction_percent: 50 })
  })
})

describe('validateParams: the limits the engine enforces', () => {
  const moon = defaultParams('moon')
  it('accepts the defaults for each target', () => {
    expect(validateParams(MOON_SITE01, moon)).toBeNull()
    expect(validateParams(MARS_JEZERO, defaultParams('mars'))).toBeNull()
  })
  it('refuses more than 96 samples and more than 30 days', () => {
    expect(sampleCount({ days: 7, stepMinutes: 120 })).toBe(84)
    expect(validateParams(MOON_SITE01, { ...moon, days: 10, stepMinutes: 120 })).toMatch(/120 samples/)
    expect(validateParams(MOON_SITE01, { ...moon, days: 31, stepMinutes: 720 })).toMatch(/30 days/)
  })
  it('refuses Earth dates after the orientation kernel ends, but not the Moon', () => {
    const earth = earthTarget({ id: 'e', name: 'e', summary: { pixel_size_m: 30, extent_km: [1, 1], center_lonlat: [0, 0], valid_fraction: 1 }, region: null })!
    const late = { ...defaultParams('earth'), startDate: '2027-02-07', days: 2 }
    expect(validateParams(earth, late)).toMatch(/2027-02-08/)
    expect(validateParams(MOON_SITE01, { ...late, elevationMin: 0.5, elevationMax: 10 })).toBeNull()
  })
  it('refuses an inverted elevation band and a missing date', () => {
    expect(validateParams(MOON_SITE01, { ...moon, elevationMin: 5, elevationMax: 2 })).toMatch(/below/)
    expect(validateParams(MOON_SITE01, { ...moon, startDate: '' })).toMatch(/start date/)
  })
  it('adds days across month ends', () => {
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })
})

describe('reading a result honestly', () => {
  it('a run where nothing could be decided is "insufficient", not "no windows"', () => {
    const h = headline(result(['INSUFFICIENT_COVERAGE', 'INSUFFICIENT_COVERAGE']))
    expect(h.tone).toBe('insufficient')
    expect(h.text).toMatch(/not a finding of darkness/)
  })
  it('counts undecided samples next to a real answer', () => {
    const r = result(['ILLUMINATED', 'INSUFFICIENT_COVERAGE', 'TERRAIN_OBSTRUCTED'], 1)
    expect(headline(r).text).toMatch(/1 candidate window.*1 of 3 samples could not be decided/)
    expect(summarize(r)).toMatchObject({ samples: 3, litSamples: 1, undeterminedSamples: 1, windowCount: 1 })
  })
  it('reports no windows only when samples were decided', () => {
    expect(headline(result(['TERRAIN_OBSTRUCTED', 'SURFACE_FACING_AWAY'])).text).toMatch(/^No candidate window/)
  })
  it('states the sampling uncertainty from the response', () => {
    expect(uncertaintyNote(result(['ILLUMINATED']))).toMatch(/2 h.*±2 h/)
  })
  it('formats durations', () => {
    expect([45, 3600, 7200, 86400, 345600].map(fmtDuration)).toEqual(['45 s', '60 min', '2 h', '24 h', '4 days'])
  })
})
