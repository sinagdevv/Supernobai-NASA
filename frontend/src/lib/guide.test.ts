import { afterEach, describe, expect, it, vi } from 'vitest'
import { GLOSSARY } from './glossary'
import { GUIDE_KEY, placeCard, readGuide, scrollDelta, STEPS, writeGuide } from './guide'
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
      expect(s.title && s.body && s.action).toBeTruthy()
      expect(s.targets.length).toBeGreaterThan(0)
      if (s.screen) expect(SCREENS).toContain(s.screen)
    }
  })
  it('end by saying results are computed, not validated and not stored', () => {
    expect(STEPS[5].body).toMatch(/not validated/)
    expect(STEPS[5].body).toMatch(/not stored/)
  })
})

describe('guide workspace entry', () => {
  it('points the mission step at the navigation button from the landing page, and says nothing of a removed one', () => {
    const m = STEPS.find((s) => s.id === 'mission')!
    expect(m.home?.targets).toEqual(['[data-guide="open-workspace"]'])
    expect(JSON.stringify(STEPS)).not.toMatch(/Enter the workspace/)
  })
  it('makes no measurement claims', () => {
    expect(JSON.stringify(STEPS)).not.toMatch(/\d+(\.\d+)?\s?(°|deg|%)/)
  })
})

const area = { width: 1280, top: 56, bottom: 800 }
const fits = (p: ReturnType<typeof placeCard>) => p.mode === 'float' && p.x >= 8 && p.x + 360 <= 1272
describe('guide placement', () => {
  const card = { width: 360, height: 220 }
  it('docks with no target and always on a phone', () => {
    expect(placeCard(null, card, area).mode).toBe('dock')
    expect(placeCard({ top: 100, left: 20, width: 100, height: 40 }, card, { ...area, width: 430 }).mode).toBe('dock')
  })
  it('docks while the control is still off screen', () => {
    expect(placeCard({ top: 1500, left: 100, width: 60, height: 40 }, card, area).mode).toBe('dock')
    expect(placeCard({ top: -200, left: 100, width: 60, height: 40 }, card, area).mode).toBe('dock')
  })
  it('puts the card below a control with room, above one near the bottom, and keeps it on screen', () => {
    const below = placeCard({ top: 100, left: 1200, width: 60, height: 40 }, card, area)
    expect(below).toMatchObject({ side: 'bottom', y: 156 })
    expect(fits(below)).toBe(true)
    const above = placeCard({ top: 700, left: 600, width: 60, height: 40 }, card, area)
    expect(above).toMatchObject({ side: 'top', y: 464 })
  })
  it('goes beside a control that is tall, and docks when nothing fits', () => {
    expect(placeCard({ top: 60, left: 20, width: 300, height: 720 }, card, area)).toMatchObject({ side: 'right' })
    expect(placeCard({ top: 60, left: 8, width: 1264, height: 730 }, card, area).mode).toBe('dock')
  })
})

describe('guide scrolling', () => {
  it('leaves a visible control alone, centres a hidden one, and shows the start of a tall one', () => {
    expect(scrollDelta({ top: 200, left: 0, width: 100, height: 50 }, area)).toBe(0)
    expect(scrollDelta({ top: 1500, left: 0, width: 100, height: 100 }, area)).toBe(1550 - 428)
    expect(scrollDelta({ top: 900, left: 0, width: 100, height: 2000 }, area)).toBe(900 - 68)
    expect(scrollDelta({ top: -300, left: 0, width: 100, height: 100 }, area)).toBeLessThan(0)
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
