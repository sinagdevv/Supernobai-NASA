import { MARK_GAP, MARK_POINTS, MARK_T } from '../brand/paths'

/*
 * Illustrative terrain profiles shared by the intro and the hero.
 * Heights are in metres on a 10 m sample spacing, then drawn with vertical exaggeration.
 * They are schematic, NOT survey or LRO data; the Earth profile deliberately follows the lunar relief
 * with its own deviations, which is what an analog is.
 *
 * N = 113 so that the mark's three interior vertices (t = 33/112, 56/112, 79/112) fall exactly on samples,
 * which lets the profiles morph into the mark without corner rounding.
 */
export const N = 113
export const CELL_M = 10

function hash(i: number, seed: number) {
  let h = Math.imul(i, 374761393) ^ Math.imul(seed + 7, 668265263)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}
function noise(x: number, seed: number) {
  const i = Math.floor(x), f = x - i
  const u = f * f * (3 - 2 * f)
  return hash(i, seed) * (1 - u) + hash(i + 1, seed) * u
}
function fbm(x: number, seed: number, oct: number) {
  let s = 0, a = 0.5, n = 0
  for (let o = 0; o < oct; o++) {
    s += a * noise(x * 2 ** o, seed + o * 31)
    n += a
    a *= 0.5
  }
  return s / n
}

const CRATERS = [
  { c: 0.16, r: 0.075, d: 15 },
  { c: 0.42, r: 0.05, d: 9 },
  { c: 0.67, r: 0.095, d: 17 },
  { c: 0.88, r: 0.04, d: 6 },
]

export function lunarMeters(): number[] {
  return Array.from({ length: N }, (_, i) => {
    const t = i / (N - 1)
    let h = (fbm(t * 3.2, 5, 4) - 0.5) * 9 + (fbm(t * 38, 9, 2) - 0.5) * 0.7
    for (const k of CRATERS) {
      const u = (t - k.c) / k.r
      const a = Math.abs(u)
      h += a < 1 ? -k.d * (1 - u * u) : 0.2 * k.d * Math.exp(-(((a - 1) / 0.3) ** 2))
    }
    return h
  })
}

export function earthMeters(lunar: number[], variant = 0): number[] {
  return lunar.map((l, i) => {
    const t = i / (N - 1)
    const ridged = 1 - Math.abs(fbm(t * 6, 21 + variant * 17, 4) * 2 - 1)
    return 0.55 * l + (ridged * ridged - 0.35) * 14 + (fbm(t * 45, 23 + variant, 2) - 0.5) * 1.2
  })
}

export interface Layout {
  vw: number
  vh: number
  xs: number[]
  /** Ribbon edges: lunar top, lunar bottom (= profile), Earth top (= profile), Earth bottom. */
  E: [number[], number[], number[], number[]]
  hL: number[]
  hE: number[]
  dx: number
  T: number
  G: number
  yBase: number
  /** Pixels per metre (isotropic horizontally; exaggerated vertically by `exag`) */
  k: number
  x0: number
  x1: number
  /** Vertical exaggeration actually used (for scale-bar labels) */
  exag: number
}

export interface Rect { x: number; w: number; yBase: number; T?: number }
/** The four ribbon edges (lunar top, lunar profile, Earth profile, Earth bottom). `amp*` scale the relief, `dyE` slides the Earth ribbon: the intro animates these, layout() uses the defaults. */
export function edgesAt(lm: number[], em: number[], o: { yBase: number; k: number; T: number; G: number }, ampL = 1, ampE = 1, dyE = 0): [number[], number[], number[], number[]] {
  const E2 = lm.map((h) => o.yBase - h * o.k * ampL)
  const E1 = E2.map((y) => y - o.T)
  const E3 = em.map((h, i) => Math.max(E2[i] + o.G * 0.3, o.yBase + o.G - h * o.k * ampE) + dyE)
  return [E1, E2, E3, E3.map((y) => y + o.T)]
}

/** One layout for the intro overlay, the hero plate and the story figures, so every hand-off is exact. */
export function layout(vw: number, vh: number, exag = 2.5, rect: Rect = { x: 0, w: vw, yBase: vh * (vw < 700 ? 0.8 : 0.72) }): Layout {
  const yBase = rect.yBase
  const dx = rect.w / (N - 1)
  const k = (dx / CELL_M) * exag
  const T = rect.T ?? Math.max(14, Math.min(28, vh * 0.03))
  const G = T * 0.55
  const lm = lunarMeters(), em = earthMeters(lm)
  const xs = lm.map((_, i) => rect.x + i * dx)
  const E = edgesAt(lm, em, { yBase, k, T, G })
  return { vw, vh, xs, E, hL: E[1].map((y) => -y), hE: E[2].map((y) => -y), dx, T, G, yBase, k, x0: rect.x, x1: rect.x + rect.w, exag }
}

/**
 * The hero's observation plate: a w×h pixel box that is measured from the DOM, never derived from the viewport, so the figure
 * keeps one composition at every window size. Relief fills about a fifth of the height; the sky above holds the sun and its ray.
 */
export function plateLayout(w: number, h: number): Layout {
  const dx = w / (N - 1)
  const k = Math.max(0.9, (0.21 * h) / 30) // ≈30 m of relief in the fixture profile
  return layout(w, h, (k * CELL_M) / dx, { x: 0, w, yBase: h * 0.5, T: Math.max(18, Math.min(46, h * 0.1)) })
}

/** Mark target edges at a given on-screen size and centre (same vertex count as the profile). */
export function markEdges(cx: number, cy: number, markPx: number) {
  const s = markPx / 56
  const P = MARK_POINTS
  const c = (xm: number) => {
    for (let i = 0; i < P.length - 1; i++) {
      const [x0, y0] = P[i], [x1, y1] = P[i + 1]
      if (xm <= x1 + 1e-9) return y0 + ((y1 - y0) * (xm - x0)) / (x1 - x0)
    }
    return P[P.length - 1][1]
  }
  const h = MARK_GAP / 2
  const xs: number[] = [], M: [number[], number[], number[], number[]] = [[], [], [], []]
  const yMid = 23.5
  for (let i = 0; i < N; i++) {
    const xm = (i / (N - 1)) * 56
    const cm = c(xm)
    xs.push(cx + (xm - 28) * s)
    M[0].push(cy + (cm - h - MARK_T - yMid) * s)
    M[1].push(cy + (cm - h - yMid) * s)
    M[2].push(cy + (cm + h - yMid) * s)
    M[3].push(cy + (cm + h + MARK_T - yMid) * s)
  }
  return { xs, M }
}

/** Horizon sweep: sun low on the left (elevation el°) throws shadows rightwards. True where a sample is shaded. */
export function shade(h: number[], dx: number, elDeg: number): boolean[] {
  const drop = dx * Math.tan((elDeg * Math.PI) / 180)
  const out: boolean[] = new Array(h.length).fill(false)
  let ray = h[0]
  for (let i = 1; i < h.length; i++) {
    ray -= drop
    if (ray > h[i] + 0.001) out[i] = true
    ray = Math.max(ray, h[i])
  }
  return out
}

/** Polygon through two edges over [from, to] indices (inclusive). */
export function band(xs: number[], top: number[], bot: number[], from = 0, to = xs.length - 1): string {
  let d = ''
  for (let i = from; i <= to; i++) d += `${i === from ? 'M' : 'L'}${xs[i].toFixed(1)} ${top[i].toFixed(1)}`
  for (let i = to; i >= from; i--) d += `L${xs[i].toFixed(1)} ${bot[i].toFixed(1)}`
  return d + 'Z'
}

export function line(xs: number[], y: number[]): string {
  return xs.map((x, i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y[i].toFixed(1)}`).join('')
}

/** Contiguous runs of `true`, as [from, to] index pairs. */
export function runs(mask: boolean[]): [number, number][] {
  const r: [number, number][] = []
  let s = -1
  mask.forEach((v, i) => {
    if (v && s < 0) s = i
    if (!v && s >= 0) { r.push([s, i - 1]); s = -1 }
  })
  if (s >= 0) r.push([s, mask.length - 1])
  return r
}

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t
