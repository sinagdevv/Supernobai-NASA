/*
 * Synthetic terrain for illustration. Deterministic heightfield + cast-shadow hillshade.
 * It is NOT lunar or satellite data; every use is captioned as an illustrative rendering.
 */

export type TerrainKind = 'moon' | 'earth'

export interface Field {
  w: number
  h: number
  z: Float32Array
  nx: Float32Array
  ny: Float32Array
}

export const CELL_M = 10

function hash(ix: number, iy: number, seed: number) {
  let h = Math.imul(ix, 374761393) ^ Math.imul(iy, 668265263) ^ Math.imul(seed + 1, 1103515245)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}
function vnoise(x: number, y: number, seed: number) {
  const ix = Math.floor(x), iy = Math.floor(y)
  const fx = x - ix, fy = y - iy
  const u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy)
  const a = hash(ix, iy, seed), b = hash(ix + 1, iy, seed), c = hash(ix, iy + 1, seed), d = hash(ix + 1, iy + 1, seed)
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v
}
function fbm(x: number, y: number, seed: number, oct: number) {
  let s = 0, amp = 0.5, f = 1, norm = 0
  for (let i = 0; i < oct; i++) {
    s += amp * vnoise(x * f, y * f, seed + i * 17)
    norm += amp
    amp *= 0.5
    f *= 2
  }
  return s / norm
}
function rng(seed: number) {
  let s = seed >>> 0 || 1
  return () => ((s = Math.imul(s ^ (s >>> 15), 2246822519) + 0x9e3779b9), ((s ^ (s >>> 13)) >>> 0) / 4294967296)
}

const cache = new Map<string, Field>()

export function heightfield(kind: TerrainKind, seed: number, w: number, h: number, exag: number): Field {
  const key = `${kind}|${seed}|${w}|${h}|${exag}`
  const hit = cache.get(key)
  if (hit) return hit
  const z = new Float32Array(w * h)
  const r = rng(seed * 977 + (kind === 'moon' ? 1 : 2))
  const sc = 1 / Math.max(w, h)

  if (kind === 'moon') {
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) z[y * w + x] = (fbm(x * sc * 2, y * sc * 2, seed, 5) - 0.5) * 16 + (fbm(x * sc * 40, y * sc * 40, seed + 5, 2) - 0.5) * 0.8
    const n = Math.round((w * h) / 700)
    for (let i = 0; i < n; i++) {
      const rad = 2.5 + Math.pow(r(), 3.6) * 46
      const cx = r() * w, cy = r() * h, depth = rad * 0.2
      const x0 = Math.max(0, Math.floor(cx - rad * 1.8)), x1 = Math.min(w - 1, Math.ceil(cx + rad * 1.8))
      const y0 = Math.max(0, Math.floor(cy - rad * 1.8)), y1 = Math.min(h - 1, Math.ceil(cy + rad * 1.8))
      for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
        const d = Math.hypot(x - cx, y - cy) / rad
        z[y * w + x] += d < 1 ? -depth * (1 - d * d) : 0.28 * depth * Math.exp(-(((d - 1) / 0.45) ** 2)) + 0.05 * depth * Math.exp(-(d - 1) * 1.2)
      }
    }
  } else {
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const wx = x * sc * 4 + (fbm(x * sc * 6, y * sc * 6, seed + 3, 2) - 0.5) * 1.6
      const wy = y * sc * 4 + (fbm(x * sc * 6 + 9, y * sc * 6, seed + 4, 2) - 0.5) * 1.6
      const ridged = 1 - Math.abs(fbm(wx, wy, seed, 5) * 2 - 1)
      z[y * w + x] = ridged * ridged * 16 + (fbm(x * sc * 30, y * sc * 30, seed + 9, 3) - 0.5) * 2
    }
    const n = Math.max(3, Math.round((w * h) / 2600))
    for (let i = 0; i < n; i++) {
      const rad = 6 + r() * 12, cx = r() * w, cy = r() * h, hgt = rad * 0.5
      for (let y = Math.max(0, Math.floor(cy - rad * 2)); y <= Math.min(h - 1, Math.ceil(cy + rad * 2)); y++)
        for (let x = Math.max(0, Math.floor(cx - rad * 2)); x <= Math.min(w - 1, Math.ceil(cx + rad * 2)); x++) {
          const d = Math.hypot(x - cx, y - cy) / rad
          z[y * w + x] += hgt * Math.exp(-d * d * 1.4) - (d < 0.25 ? hgt * 0.35 * (1 - d / 0.25) : 0)
        }
    }
  }
  // one 3×3 box pass removes single-pixel rim speckle before gradients are taken
  const src = z.slice()
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
    let a = 0
    for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) a += src[(y + j) * w + x + i]
    z[y * w + x] = a / 9
  }
  for (let i = 0; i < z.length; i++) z[i] *= exag
  const nx = new Float32Array(w * h), ny = new Float32Array(w * h)
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const xl = z[y * w + Math.max(0, x - 1)], xr = z[y * w + Math.min(w - 1, x + 1)]
    const yu = z[Math.max(0, y - 1) * w + x], yd = z[Math.min(h - 1, y + 1) * w + x]
    nx[y * w + x] = -(xr - xl) / (2 * CELL_M)
    ny[y * w + x] = -(yd - yu) / (2 * CELL_M)
  }
  const f = { w, h, z, nx, ny }
  cache.set(key, f)
  return f
}

export interface Palette {
  lit: [number, number, number]
  dark: [number, number, number]
}
export const PALETTES: Record<TerrainKind, Palette> = {
  moon: { lit: [236, 232, 222], dark: [10, 12, 16] },
  earth: { lit: [186, 208, 214], dark: [9, 14, 18] },
}

const rad = Math.PI / 180
const MAX_STEPS = 56

/** Paint the field lit from azimuth `az` (° from north, clockwise, image-up = north), elevation `el` (°). */
export function paintTerrain(ctx: CanvasRenderingContext2D, f: Field, el: number, az: number, pal: Palette, warm = 0) {
  const { w, h, z, nx, ny } = f
  const img = ctx.createImageData(w, h)
  const d = img.data
  const e = Math.max(0.05, el) * rad
  const a = az * rad
  const dx = Math.sin(a), dy = -Math.cos(a)
  const lx = dx * Math.cos(e), ly = dy * Math.cos(e), lz = Math.sin(e)
  const tan = Math.tan(e)
  const exposure = 0.55 / Math.sin(Math.max(el, 3) * rad)
  const night = el <= 0
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x
    let lum = 0
    if (!night) {
      const nz = 1 / Math.sqrt(nx[i] * nx[i] + ny[i] * ny[i] + 1)
      const diff = Math.max(0, (nx[i] * lx + ny[i] * ly + 1 * lz) * nz)
      if (diff > 0) {
        let occ = -1
        const z0 = z[i]
        for (let s = 1; s <= MAX_STEPS; s++) {
          const fx = x + dx * s, fy = y + dy * s
          const x0 = Math.floor(fx), y0 = Math.floor(fy)
          if (x0 < 0 || y0 < 0 || x0 >= w - 1 || y0 >= h - 1) break
          const u = fx - x0, v = fy - y0, k = y0 * w + x0
          // bilinear height sample keeps shadow edges smooth
          const zs = z[k] * (1 - u) * (1 - v) + z[k + 1] * u * (1 - v) + z[k + w] * (1 - u) * v + z[k + w + 1] * u * v
          const o = (zs - z0) / (s * CELL_M) - tan
          if (o > occ) occ = o
        }
        // soft penumbra instead of a hard binary edge
        const lit = occ <= -0.004 ? 1 : occ >= 0.01 ? 0 : 1 - (occ + 0.004) / 0.014
        lum = diff * exposure * lit
      }
    }
    const t = Math.min(1, 0.05 + (1 - Math.exp(-1.3 * lum)))
    const o = i * 4
    const lr = pal.lit[0] + (240 - pal.lit[0]) * warm * 0.55, lg = pal.lit[1] + (206 - pal.lit[1]) * warm * 0.55, lb = pal.lit[2] + (150 - pal.lit[2]) * warm * 0.55
    d[o] = pal.dark[0] + (lr - pal.dark[0]) * t
    d[o + 1] = pal.dark[1] + (lg - pal.dark[1]) * t
    d[o + 2] = pal.dark[2] + (lb - pal.dark[2]) * t
    d[o + 3] = 255
  }
  ctx.putImageData(img, 0, 0)
}

/** Row profile through the heightfield (relative elevation in metres, un-exaggerated). */
export function profile(kind: TerrainKind, seed: number, w: number, h: number, exag: number, row = 0.5, step = 4) {
  const f = heightfield(kind, seed, w, h, exag)
  const y = Math.floor(h * row)
  const out: { x: number; z: number }[] = []
  let base = 0
  for (let x = 0; x < w; x += step) {
    const v = f.z[y * w + x] / exag
    if (x === 0) base = v
    out.push({ x: x * CELL_M, z: +(v - base).toFixed(2) })
  }
  return out
}
