import { describe, expect, it } from 'vitest'
import { lerpTerrain, N, plateLayout, terrain } from './profiles'

describe('planet terrain used by the intro and the hero (schematic, not survey data)', () => {
  it('Mars is a different landform from the Moon, not a tint', () => {
    const moon = terrain('moon').lm, mars = terrain('mars').lm
    expect(moon).toHaveLength(N)
    expect(mars).toHaveLength(N)
    const rms = Math.sqrt(moon.reduce((a, h, i) => a + (h - mars[i]) ** 2, 0) / N)
    expect(rms).toBeGreaterThan(3) // metres: the profiles differ by several metres of relief
  })

  it('a morph reaches both ends exactly and is continuous between them', () => {
    const a = terrain('moon'), b = terrain('mars')
    expect(lerpTerrain(a, b, 0)).toBe(a)
    expect(lerpTerrain(a, b, 1)).toBe(b)
    const mid = lerpTerrain(a, b, 0.5)
    expect(mid.lm[40]).toBeCloseTo((a.lm[40] + b.lm[40]) / 2, 10)
    // interrupting at t = 0.5 and heading back is the same operation, from the in-between terrain
    expect(lerpTerrain(mid, a, 1)).toBe(a)
  })

  it('the layout is the same size for both planets, so the plate never reflows on a switch', () => {
    const l1 = plateLayout(772, 386, terrain('moon')), l2 = plateLayout(772, 386, terrain('mars'))
    expect(l1.xs).toEqual(l2.xs)
    expect(l1.k).toBe(l2.k)
    expect(l1.E[1]).not.toEqual(l2.E[1])
  })
})
