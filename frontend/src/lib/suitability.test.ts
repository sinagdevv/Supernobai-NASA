import { describe, expect, it } from 'vitest'
import type { MissionAssessment, RehearsalResult } from './api/types'
import { MARS_JEZERO, MOON_SITE01 } from './rehearsal'
import { analogTarget, buildAssessRequest, buildProfile, CRITERION_META, defaultEdits, fmtTarget, fmtValue, OVERALL_META, SPECS, tally } from './suitability'

const l4 = (body: 'moon' | 'mars' | 'earth') => ({ body, generated_at: 'now' }) as unknown as RehearsalResult

describe('mission profiles', () => {
  it('Moon and Mars are defined independently: different thresholds, not a copy', () => {
    const moon = Object.fromEntries(SPECS.moon.map((s) => [s.def.id, s.default]))
    const mars = Object.fromEntries(SPECS.mars.map((s) => [s.def.id, s.default]))
    expect(moon['slope-p90']).not.toBe(mars['slope-p90'])
    expect(moon['roughness']).not.toBe(mars['roughness'])
    expect(SPECS.mars.map((s) => s.def.rationale).join(' ')).not.toMatch(/lunar|1\.62/i)
    expect(SPECS.moon.map((s) => s.def.rationale).join(' ')).not.toMatch(/Mars/i)
  })

  it('selectors match the metric: scale for slope and roughness, threshold only for the steep share, nothing for coverage', () => {
    const p = buildProfile('moon', defaultEdits('moon'), 40)!
    const by = Object.fromEntries(p.criteria.map((c) => [c.id, c]))
    expect(by['slope-p90']).toMatchObject({ scale_m: 40 })
    expect(by['steep-share']).toMatchObject({ scale_m: 40, threshold_deg: 20 })
    expect(by['coverage']).not.toHaveProperty('scale_m')
    expect(by['coverage']).not.toHaveProperty('threshold_deg')
    expect(by['illumination']).not.toHaveProperty('scale_m')
    expect(by['illumination'].source_layer).toBe('layer4')
  })

  it('declares every category as required even when a category is switched off, so it cannot quietly become easier', () => {
    const edits = defaultEdits('moon')
    edits['illumination'].enabled = false
    edits['obstruction'].enabled = false
    const p = buildProfile('moon', edits, 40)!
    expect(p.required_categories).toEqual(['terrain', 'data-coverage', 'illumination'])
    expect(p.criteria.some((c) => c.category === 'illumination')).toBe(false)
  })

  it('sends the edited threshold and required flag', () => {
    const edits = defaultEdits('mars')
    edits['slope-p90'].target = 7
    edits['coverage'].required = false
    const c = Object.fromEntries(buildProfile('mars', edits, 926.1153344)!.criteria.map((x) => [x.id, x]))
    expect(c['slope-p90']).toMatchObject({ target_value: 7, required: true, scale_m: 926.1153344 })
    expect(c['coverage'].required).toBe(false)
  })

  it('has no profile when every criterion is off', () => {
    const edits = defaultEdits('moon')
    for (const k of Object.keys(edits)) edits[k].enabled = false
    expect(buildProfile('moon', edits, 40)).toBeNull()
  })
})

describe('assessment requests', () => {
  it('attach the Layer 4 result only for the same body, and null otherwise', () => {
    const e = defaultEdits('moon')
    expect(buildAssessRequest('moon', MOON_SITE01, e, l4('moon'))!.layer4_result).toBeTruthy()
    expect(buildAssessRequest('moon', MOON_SITE01, e, l4('mars'))!.layer4_result).toBeNull()
    expect(buildAssessRequest('moon', MOON_SITE01, e, null)!.layer4_result).toBeNull()
  })
  it('describe the same patch Layer 4 ran on', () => {
    const r = buildAssessRequest('mars', MARS_JEZERO, defaultEdits('mars'), null)!
    expect(r.candidate).toEqual(MARS_JEZERO.candidate)
    expect(r.candidate_id).toBe('mars')
  })
})

describe('labels never make missing evidence look good', () => {
  it('only a measured PASS is positive', () => {
    const positive = Object.entries(CRITERION_META).filter(([, m]) => m.tone === 'pass').map(([k]) => k)
    expect(positive).toEqual(['PASS'])
    expect(CRITERION_META.UNVERIFIED.tone).toBe('claim')
    expect(CRITERION_META.INDETERMINATE.tone).toBe('missing')
    expect(CRITERION_META.NOT_ASSESSED.tone).toBe('missing')
  })
  it('the overall verdicts without a decision are not positive', () => {
    expect(OVERALL_META.INDETERMINATE.tone).toBe('missing')
    expect(OVERALL_META.PARTIALLY_ASSESSED.tone).toBe('missing')
    expect(OVERALL_META.SUITABLE.caution).toMatch(/not a safety or readiness/)
  })
  it('tallies a mixed assessment by tone', () => {
    const a = { criterion_results: ['PASS', 'FAIL', 'UNVERIFIED', 'INDETERMINATE', 'NOT_ASSESSED'].map((status) => ({ status })) } as unknown as MissionAssessment
    expect(tally(a)).toEqual({ pass: 1, fail: 1, claim: 1, missing: 2, total: 5 })
  })
})

describe('value formatting', () => {
  it('uses units and never invents a value', () => {
    expect(fmtValue(null, 'degrees')).toBe('—')
    expect(fmtValue(19.913, 'degrees')).toBe('19.91°')
    expect(fmtValue(86400, 'seconds')).toBe('24 h')
    expect(fmtValue(1800, 'seconds')).toBe('30 min')
    expect(fmtValue(0.983, 'fraction')).toBe('0.983')
    expect(fmtTarget({ operator: 'lte', target_value: 20, target_range: null, unit: 'degrees' })).toBe('≤ 20°')
  })
})

describe('analog targets', () => {
  const earth = { key: 'earth:x', body: 'earth' as const, datasetId: 'x', label: 'x', place: 'p', scaleM: 30, bbox: { west: 0, south: 0, east: 0.1, north: 0.1, crs: 'geographic' as const }, candidate: { dataset: { id: 'x' }, bbox: { west: 0, south: 0, east: 0.1, north: 0.1, crs: 'geographic' as const }, scales_m: [30] } }
  it('against lunar criteria keeps the window and grid Layer 4 ran on', () => {
    expect(analogTarget('moon', earth)).toBe(earth)
  })
  it('against Mars criteria uses the whole dataset at 926 m, with no Layer 4 pairing', () => {
    const t = analogTarget('mars', earth)
    expect(t.candidate).toEqual({ dataset: { id: 'x' }, scales_m: [926.1153344] })
    expect(buildAssessRequest('mars', t, defaultEdits('mars'), l4('earth'))!.layer4_result).toBeNull()
  })
})
