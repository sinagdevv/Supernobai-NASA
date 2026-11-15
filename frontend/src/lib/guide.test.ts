import { afterEach, describe, expect, it, vi } from 'vitest'
import { GLOSSARY } from './glossary'
import { GUIDE_KEY, readGuide, STEPS, writeGuide } from './guide'
import { SCREENS } from './router'

const store = () => {
  const m = new Map<string, string>()
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) }
}
afterEach(() => vi.unstubAllGlobals())

describe('guide persistence', () => {
  it('is null on a first visit, then returns what was saved', () => {
    vi.stubGlobal('localStorage', store())
    expect(readGuide()).toBeNull()
    expect(writeGuide('skipped')).toBe(true)
    expect(readGuide()).toBe('skipped')
    writeGuide('done')
    expect(readGuide()).toBe('done')
  })
  it('ignores unexpected stored values', () => {
    const s = store()
    s.setItem(GUIDE_KEY, 'garbage')
    vi.stubGlobal('localStorage', s)
    expect(readGuide()).toBeNull()
  })
  it('survives storage that throws', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } })
    expect(readGuide()).toBeNull()
    expect(writeGuide('done')).toBe(false)
  })
  it('works with no storage at all', () => {
    vi.stubGlobal('localStorage', undefined)
    expect(readGuide()).toBeNull()
    expect(writeGuide('done')).toBe(false)
  })
})

describe('guide steps', () => {
  it('are the six steps in order, each with text and a valid target', () => {
    expect(STEPS.map((s) => s.id)).toEqual(['planet', 'mission', 'analogs', 'compare', 'windows', 'dossier'])
    for (const s of STEPS) {
      expect(s.title && s.body && s.action.label).toBeTruthy()
      if (s.action.screen) expect(SCREENS).toContain(s.action.screen)
    }
  })
  it('end by saying results are computed, not validated and not stored', () => {
    expect(STEPS[5].body).toMatch(/not validated/)
    expect(STEPS[5].body).toMatch(/not stored/)
  })
})

describe('glossary', () => {
  it('has the eight required terms, all defined', () => {
    expect(Object.keys(GLOSSARY).sort()).toEqual(['computed', 'coverage', 'indeterminate', 'insufficient', 'provenance', 'roughness', 'scale', 'unverified'])
    for (const g of Object.values(GLOSSARY)) {
      expect(g.term.length).toBeGreaterThan(2)
      expect(g.def.length).toBeGreaterThan(40)
    }
  })
})
