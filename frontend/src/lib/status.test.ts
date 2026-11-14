import { describe, expect, it } from 'vitest'
import { contextStatus } from './status'
import type { Screen } from './router'

const SCREENS: Screen[] = ['mission', 'analogs', 'windows', 'compare', 'dossier']

describe('contextStatus: what the data on this screen is', () => {
  it('Mars never reads as measured unless the service is online AND the Mars region is retrieved', () => {
    for (const screen of ['mission', 'compare', 'dossier'] as Screen[]) {
      expect(contextStatus('mars', screen, 'online', true).state).toBe('measured')
      expect(contextStatus('mars', screen, 'online', false).state).toBe('unavailable')
      expect(contextStatus('mars', screen, 'offline', true).state).toBe('unavailable')
      expect(contextStatus('mars', screen, 'checking', false).state).toBe('checking')
    }
  })

  it('no Mars screen is ever labelled as a lunar or illustrative-lunar status', () => {
    for (const screen of SCREENS) {
      const s = contextStatus('mars', screen, 'online', true)
      expect(`${s.label} ${s.detail}`).not.toMatch(/lunar|moon/i)
    }
  })

  it('anything that needs Layer 4 or Layer 5 is pending on both planets, never measured', () => {
    expect(contextStatus('moon', 'windows', 'online', true).state).toBe('pending')
    expect(contextStatus('mars', 'windows', 'online', true).state).toBe('pending')
    expect(contextStatus('mars', 'analogs', 'online', true).state).toBe('pending')
  })

  it('the Moon keeps working offline: its sample screens stay illustrative, only measured evidence is unavailable', () => {
    expect(contextStatus('moon', 'mission', 'offline', false).state).toBe('illustrative')
    expect(contextStatus('moon', 'compare', 'offline', false).state).toBe('unavailable')
    expect(contextStatus('moon', 'compare', 'online', false).state).toBe('measured')
  })

  it('every status carries a short label and a detail for the tooltip', () => {
    for (const planet of ['moon', 'mars'] as const) for (const screen of SCREENS) for (const svc of ['checking', 'online', 'offline'] as const) {
      const s = contextStatus(planet, screen, svc, svc === 'online')
      expect(s.label.length).toBeGreaterThan(0)
      expect(s.label.length).toBeLessThanOrEqual(30)
      expect(s.detail.length).toBeGreaterThan(20)
    }
  })
})
