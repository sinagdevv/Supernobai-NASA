import { describe, expect, it } from 'vitest'
import { contextStatus, evidenceKind, EVIDENCE_LABEL, type EvidenceSnapshot } from './status'
import type { Screen } from './router'

const SCREENS: Screen[] = ['mission', 'analogs', 'windows', 'compare', 'dossier']
const CALLS = ['none', 'running', 'computed', 'failed'] as const
const ALL: EvidenceSnapshot[] = CALLS.flatMap((rehearsal) => CALLS.map((assessment) => ({ rehearsal, assessment })))

describe('contextStatus: what the data on this screen is', () => {
  it('Mars terrain never reads as measured unless the service is online AND the Mars region is retrieved', () => {
    for (const screen of ['mission', 'compare', 'dossier'] as Screen[]) {
      expect(contextStatus('mars', screen, 'online', true).state).toBe('measured')
      expect(contextStatus('mars', screen, 'online', false).state).toBe('unavailable')
      expect(contextStatus('mars', screen, 'offline', true).state).toBe('unavailable')
      expect(contextStatus('mars', screen, 'checking', false).state).toBe('checking')
    }
  })

  it('no Mars status, in any evidence state, mentions the Moon', () => {
    for (const screen of SCREENS) for (const ev of ALL) for (const svc of ['checking', 'online', 'offline'] as const) {
      const s = contextStatus('mars', screen, svc, true, ev)
      expect(`${s.label} ${s.detail}`).not.toMatch(/lunar|moon/i)
    }
  })

  it('windows are pending or illustrative until a calculation has actually succeeded, and computed only then', () => {
    expect(contextStatus('moon', 'windows', 'online', true).state).toBe('illustrative')
    expect(contextStatus('mars', 'windows', 'online', true).state).toBe('pending')
    for (const planet of ['moon', 'mars'] as const) {
      expect(contextStatus(planet, 'windows', 'online', true, { rehearsal: 'computed', assessment: 'none' }).state).toBe('computed')
      for (const rehearsal of ['none', 'running', 'failed'] as const) {
        expect(contextStatus(planet, 'windows', 'online', true, { rehearsal, assessment: 'computed' }).state).not.toBe('computed')
      }
    }
  })

  it('a failed or unreachable calculation is "unavailable", never the illustrative preview', () => {
    for (const planet of ['moon', 'mars'] as const) {
      expect(contextStatus(planet, 'windows', 'online', true, { rehearsal: 'failed', assessment: 'none' }).state).toBe('unavailable')
      expect(contextStatus(planet, 'windows', 'offline', true).state).toBe('unavailable')
    }
  })

  it('a computed label never claims validation', () => {
    for (const planet of ['moon', 'mars'] as const) for (const screen of SCREENS) {
      const s = contextStatus(planet, screen, 'online', true, { rehearsal: 'computed', assessment: 'computed' })
      if (s.state === 'computed') expect(`${s.label} ${s.detail}`).not.toMatch(/independently validated|has been validated/i)
    }
  })

  it('the dossier says its computed parts are not stored', () => {
    for (const planet of ['moon', 'mars'] as const) {
      const s = contextStatus(planet, 'dossier', 'online', true, { rehearsal: 'computed', assessment: 'none' })
      expect(s.state).toBe('computed')
      expect(s.label).toMatch(/not stored/i)
    }
  })

  it('the Moon keeps working offline: its sample screens stay illustrative, only measured evidence is unavailable', () => {
    expect(contextStatus('moon', 'mission', 'offline', false).state).toBe('illustrative')
    expect(contextStatus('moon', 'compare', 'offline', false).state).toBe('unavailable')
    expect(contextStatus('moon', 'compare', 'online', false).state).toBe('measured')
  })

  it('the Moon mission screen reflects its own Layer 5 call: computed, running, or failed', () => {
    expect(contextStatus('moon', 'mission', 'online', true, { rehearsal: 'none', assessment: 'computed' }).state).toBe('computed')
    expect(contextStatus('moon', 'mission', 'online', true, { rehearsal: 'none', assessment: 'running' }).state).toBe('checking')
    expect(contextStatus('moon', 'mission', 'online', true, { rehearsal: 'none', assessment: 'failed' }).state).toBe('unavailable')
  })

  it('every status carries a short label and a detail for the tooltip', () => {
    for (const planet of ['moon', 'mars'] as const) for (const screen of SCREENS) for (const svc of ['checking', 'online', 'offline'] as const) for (const ev of ALL) {
      const s = contextStatus(planet, screen, svc, svc === 'online', ev)
      expect(s.label.length).toBeGreaterThan(0)
      expect(s.label.length).toBeLessThanOrEqual(30)
      expect(s.detail.length).toBeGreaterThan(20)
    }
  })
})

describe('evidenceKind', () => {
  it('stays "computed" while the engine reports NOT_VALIDATED, and only an explicit VALIDATED can change it', () => {
    expect(evidenceKind('NOT_VALIDATED')).toBe('computed')
    expect(evidenceKind(undefined)).toBe('computed')
    expect(evidenceKind('VALIDATED')).toBe('validated')
  })

  it('has five distinct labels', () => {
    const labels = Object.values(EVIDENCE_LABEL).map((l) => l.label)
    expect(new Set(labels).size).toBe(5)
  })
})
