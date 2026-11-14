import type { Site } from '../data/types'

/*
 * Simplified solar geometry for DEMONSTRATION ONLY.
 * Declination from a cosine approximation; equation of time, refraction, terrain horizon
 * and DST are ignored. Accuracy is about a degree — NOT a validated ephemeris.
 */

const rad = Math.PI / 180
const deg = 180 / Math.PI

export interface Sun {
  el: number
  az: number
}

export function dayOfYear(date: string): number {
  const [y, m, d] = date.split('-').map(Number)
  return Math.round((Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 0)) / 86400000)
}

export function sunAt(site: Pick<Site, 'lat' | 'lon' | 'tz'>, date: string, minute: number): Sun {
  const decl = -23.44 * rad * Math.cos((2 * Math.PI * (dayOfYear(date) + 10)) / 365)
  const utcHours = minute / 60 - site.tz
  const hourAngle = (utcHours + site.lon / 15 - 12) * 15 * rad
  const lat = site.lat * rad
  const sinEl = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(hourAngle)
  const el = Math.asin(Math.max(-1, Math.min(1, sinEl)))
  const az = Math.atan2(Math.sin(hourAngle), Math.cos(hourAngle) * Math.sin(lat) - Math.tan(decl) * Math.cos(lat)) + Math.PI
  return { el: el * deg, az: (az * deg + 360) % 360 }
}

export interface Segment {
  startMin: number
  endMin: number
  durationMin: number
  rising: boolean
  elStart: number
  elEnd: number
  azStart: number
  azEnd: number
}

export interface DaySummary {
  date: string
  minutes: number
  segments: Segment[]
}

const STEP = 5
const dayCache = new Map<string, DaySummary>()

/** Periods of a local day (00:00–24:00 standard time) when the sun sits inside [lo, hi] degrees. */
export function dayWindows(site: Site, date: string, lo: number, hi: number, minDur: number): DaySummary {
  const key = `${site.id}|${date}|${lo}|${hi}|${minDur}`
  const hit = dayCache.get(key)
  if (hit) return hit
  const segments: Segment[] = []
  let start = -1
  const close = (endIdx: number) => {
    const startMin = start * STEP
    const endMin = endIdx * STEP
    if (endMin - startMin >= minDur) {
      const a = sunAt(site, date, startMin)
      const b = sunAt(site, date, endMin)
      const mid = sunAt(site, date, (startMin + endMin) / 2)
      const next = sunAt(site, date, (startMin + endMin) / 2 + STEP)
      segments.push({ startMin, endMin, durationMin: endMin - startMin, rising: next.el > mid.el, elStart: a.el, elEnd: b.el, azStart: a.az, azEnd: b.az })
    }
    start = -1
  }
  const n = (24 * 60) / STEP
  for (let i = 0; i < n; i++) {
    const { el } = sunAt(site, date, i * STEP)
    const inside = el >= lo && el <= hi
    if (inside && start < 0) start = i
    if (!inside && start >= 0) close(i)
  }
  if (start >= 0) close(n)
  const res = { date, segments, minutes: segments.reduce((s, g) => s + g.durationMin, 0) }
  dayCache.set(key, res)
  return res
}

export const pad = (n: number) => String(n).padStart(2, '0')
export const isoDate = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`
export const daysInMonth = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate()
export const addDays = (date: string, n: number) => {
  const [y, m, d] = date.split('-').map(Number)
  const t = new Date(Date.UTC(y, m - 1, d + n))
  return isoDate(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate())
}
export const fmtMin = (min: number) => `${pad(Math.floor(min / 60) % 24)}:${pad(Math.round(min % 60))}`
export const fmtDur = (min: number) => (min >= 60 ? `${Math.floor(min / 60)} h ${pad(min % 60)} min` : `${min} min`)
export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
export const compass = (az: number) => ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'][Math.round(az / 22.5) % 16]

export function monthSummary(site: Site, year: number, month: number, lo: number, hi: number, minDur: number): DaySummary[] {
  return Array.from({ length: daysInMonth(year, month) }, (_, i) => dayWindows(site, isoDate(year, month, i + 1), lo, hi, minDur))
}

/** Number of qualifying days in a horizon starting at `start`. */
export function qualifyingDays(site: Site, start: string, days: number, lo: number, hi: number, minDur: number): number {
  let c = 0
  for (let i = 0; i < days; i++) if (dayWindows(site, addDays(start, i), lo, hi, minDur).segments.length) c++
  return c
}

/** Length of the shadow cast by a 1 m object on flat ground (m). */
export const shadowRatio = (elDeg: number) => (elDeg <= 0.05 ? Infinity : 1 / Math.tan(elDeg * rad))

/** Relative bearing between rover heading and sun azimuth, in -180..180. */
export const relBearing = (heading: number, az: number) => ((az - heading + 540) % 360) - 180
