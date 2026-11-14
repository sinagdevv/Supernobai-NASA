import { DEMO_HORIZON_DAYS, DEMO_START, LUNAR_REGIONS, SLOPE_EDGES } from '../data/mission'
import type { Assessment, Criterion, LunarRegion, Mission, Site, Status } from '../data/types'
import { qualifyingDays } from './solar'

export const STATUS_LABEL: Record<Status, string> = {
  potential: 'Potentially Suitable',
  'not-suitable': 'Not Suitable',
  'not-assessed': 'Not Yet Assessed',
}

export const regionById = (id: string): LunarRegion => LUNAR_REGIONS.find((r) => r.id === id) ?? LUNAR_REGIONS[0]

/** Share of area (%) with slope ≤ limit, linearly interpolated inside each bin. */
export function shareBelow(hist: number[], limit: number): number {
  let acc = 0
  for (let i = 0; i < hist.length; i++) {
    const lo = SLOPE_EDGES[i]
    const hi = SLOPE_EDGES[i + 1]
    if (limit >= hi) acc += hist[i]
    else if (limit > lo) acc += (hist[i] * (limit - lo)) / (hi - lo)
  }
  return acc
}

/** RMS height deviation (m) at baseline L (m). */
export const rmsAt = (r: { a: number; h: number }, L: number) => r.a * Math.pow(L / 10, r.h)

/** A baseline is resolvable when it spans at least two DEM cells (Nyquist). */
export const resolvable = (resM: number, baselineM: number) => baselineM >= 2 * resM

const cache = new Map<string, Assessment>()

export function assessSite(site: Site, m: Mission): Assessment {
  const key = [site.id, m.slopeMax, m.minTraversable, m.roughBaseline, m.roughMax, m.elMin, m.elMax, m.minDuration, m.maxDemRes].join('|')
  const hit = cache.get(key)
  if (hit) return hit

  const share = shareBelow(site.slopeHist, m.slopeMax)
  const rough = rmsAt(site.rough, m.roughBaseline)
  const canResolve = resolvable(site.dem.resM, m.roughBaseline)
  const days = qualifyingDays(site, DEMO_START, DEMO_HORIZON_DAYS, m.elMin, m.elMax, m.minDuration)

  const criteria: Criterion[] = [
    {
      id: 'slope', label: 'Slope distribution', core: true,
      status: share >= m.minTraversable ? 'potential' : 'not-suitable',
      reason: `${share.toFixed(0)}% of area ≤ ${m.slopeMax}° (screening needs ≥ ${m.minTraversable}%).`,
      detail: 'Share of mapped terrain at or below the screening slope limit, from the site slope histogram. The limit is a configurable screening parameter, not a vehicle specification.',
    },
    {
      id: 'roughness', label: `Roughness at ${m.roughBaseline} m`, core: true,
      status: !canResolve ? 'not-assessed' : rough <= m.roughMax ? 'potential' : 'not-suitable',
      reason: !canResolve
        ? `${site.dem.resM} m DEM cannot resolve a ${m.roughBaseline} m baseline (needs ≥ ${2 * site.dem.resM} m).`
        : `RMS height deviation ${rough.toFixed(2)} m vs limit ${m.roughMax.toFixed(1)} m.`,
      detail: 'Roughness is the RMS height deviation over a baseline length. A baseline shorter than two DEM cells is below the data’s resolving power, so the criterion is left unassessed rather than guessed.',
    },
    {
      id: 'illumination', label: 'Low-angle sun availability', core: true,
      status: days > 0 ? 'potential' : 'not-suitable',
      reason: days > 0
        ? `${days} of ${DEMO_HORIZON_DAYS} days have the sun in ${m.elMin}–${m.elMax}° for ≥ ${m.minDuration} min.`
        : `No day in ${DEMO_HORIZON_DAYS} has the sun in ${m.elMin}–${m.elMax}° for ≥ ${m.minDuration} min.`,
      detail: 'Natural-sunlight geometry only, from a simplified solar model with no terrain horizon, weather or twilight refraction. Illustrative — not a validated prediction.',
    },
    {
      id: 'resolution', label: 'Dataset resolution', core: false,
      status: site.dem.resM <= m.maxDemRes ? 'potential' : 'not-assessed',
      reason: `${site.dem.resM} m grid vs ≤ ${m.maxDemRes} m required.`,
      detail: 'A coarser grid smooths over metre-scale hazards. Sites above the required resolution need a finer elevation product before terrain criteria can be trusted.',
    },
    {
      id: 'regolith', label: 'Surface material & soil strength', core: false,
      status: 'not-assessed',
      reason: 'Grain size, cohesion and bearing strength are not quantified in this prototype.',
      detail: 'Terrain shape alone does not describe how a wheel interacts with soil. Field measurements (e.g. cone penetrometer, sieve analysis) would be required.',
    },
    {
      id: 'rocks', label: 'Rock abundance', core: false,
      status: 'not-assessed',
      reason: 'No rock-size / frequency data included.',
      detail: 'Rock size–frequency distributions control obstacle density and navigation difficulty and need dedicated imagery analysis.',
    },
    {
      id: 'environment', label: 'Gravity, vacuum, radiation, thermal', core: false,
      status: 'not-suitable',
      reason: 'Cannot be reproduced at any Earth surface site.',
      detail: 'These conditions must be addressed by other facilities, simulation or flight data. An Earth analog never substitutes for them.',
    },
  ]

  const core = criteria.filter((c) => c.core)
  const overall: Status = core.some((c) => c.status === 'not-suitable') ? 'not-suitable' : core.some((c) => c.status === 'not-assessed') ? 'not-assessed' : 'potential'
  const screened = criteria.filter((c) => c.id !== 'environment')
  const res: Assessment = {
    siteId: site.id, overall, qualifyingDays: days,
    assessedCount: screened.filter((c) => c.status !== 'not-assessed').length,
    totalCount: screened.length,
    criteria,
  }
  cache.set(key, res)
  return res
}
