import { DEMO_HORIZON_DAYS, DEMO_START, OBJECTIVES } from '../../data/mission'
import { BASEMAP_CREDITS, DISCLAIMER, NOT_REPRODUCIBLE, SOURCES } from '../../data/sources'
import type { Assessment, LunarRegion, Mission, Site } from '../../data/types'
import { STATUS_LABEL, resolvable, rmsAt, shareBelow } from '../../lib/assess'
import { MONTHS, compass, fmtDur, fmtMin, monthSummary } from '../../lib/solar'
import { fmtCoord } from './shared'

export type Row = [string, string]
export interface WindowRow { date: string; time: string; phase: string; el: string; az: string; dur: string }

export interface ReportData {
  title: string
  site: Site
  region: LunarRegion
  assessment: Assessment
  mission: Row[]
  lunar: Row[]
  earth: Row[]
  terrain: [string, string, string][]
  monthLabel: string
  windows: WindowRow[]
  gaps: Row[]
  missing: string[]
  provenance: Row[]
  steps: string[]
}

export const FIELD_STEPS = [
  'Ground-truth the elevation model: run an RTK-GNSS or terrestrial-lidar traverse across the candidate area and compare it against the DEM at the screening baseline.',
  'Count rocks: photograph test plots at rover-eye height and build a size–frequency distribution to replace the missing rock-abundance evidence.',
  'Characterise the soil: measure cone-penetrometer resistance and sieve grain size at several points; record moisture and crust.',
  'Survey the real horizon: capture a panorama (theodolite or drone) from the planned start point and mask the sun track with terrain, not a flat horizon.',
  'Characterise any artificial lighting photometrically (elevation, beam spread, glare) before treating it as a stand-in for low sun.',
  'Check seasonal weather, snow cover and haze for the shortlisted dates, and keep a fallback window.',
  'Confirm land access: permits, protected-area rules, hazard zones and logistics lead time.',
]

export function buildReport(site: Site, mission: Mission, a: Assessment, region: LunarRegion, date: string): ReportData {
  const objective = OBJECTIVES.find((o) => o.id === mission.objectiveId)?.label ?? mission.objectiveId
  const [y, m] = date.split('-').map(Number)
  const days = monthSummary(site, y, m, mission.elMin, mission.elMax, mission.minDuration)
  const windows: WindowRow[] = days
    .flatMap((d) => d.segments.map((s) => ({ d, s })))
    .slice(0, 10)
    .map(({ d, s }) => ({
      date: d.date,
      time: `${fmtMin(s.startMin)}–${fmtMin(s.endMin)}`,
      phase: s.rising ? 'sun rising' : 'sun setting',
      el: `${s.elStart.toFixed(1)}° → ${s.elEnd.toFixed(1)}°`,
      az: `${Math.round(s.azStart)}° ${compass(s.azStart)} → ${Math.round(s.azEnd)}° ${compass(s.azEnd)}`,
      dur: fmtDur(s.durationMin),
    }))

  const sM = shareBelow(region.slopeHist, mission.slopeMax), sE = shareBelow(site.slopeHist, mission.slopeMax)
  const rM = rmsAt(region.rough, mission.roughBaseline), rE = rmsAt(site.rough, mission.roughBaseline)
  const okE = resolvable(site.dem.resM, mission.roughBaseline)

  return {
    title: `${site.name} vs ${region.name}`,
    site, region, assessment: a,
    mission: [
      ['Objective', objective],
      ['Target', 'Moon — south-polar region (prototype scope)'],
      ['Slope screening', `≤ ${mission.slopeMax}° over ≥ ${mission.minTraversable}% of area`],
      ['Roughness screening', `RMS height ≤ ${mission.roughMax} m at ${mission.roughBaseline} m baseline`],
      ['Illumination band', `Sun at ${mission.elMin}–${mission.elMax}° elevation for ≥ ${mission.minDuration} min`],
      ['Elevation-grid requirement', `≤ ${mission.maxDemRes} m spacing`],
    ],
    lunar: [
      ['Reference region', region.name],
      ['Approx. latitude', `${region.approxLat} (orientation only)`],
      ['Description', region.summary],
      ['Elevation grid', `${region.dem.resM} m — ${region.dem.name} (assumed)`],
      ['Terrain figures', 'Illustrative fixtures, not LOLA measurements'],
    ],
    earth: [
      ['Candidate', site.name],
      ['Place', site.place],
      ['Position', fmtCoord(site.lat, site.lon)],
      ['Elevation', `${site.elevM.toLocaleString()} m a.s.l.`],
      ['Terrain class', site.terrain],
      ['Description', site.summary],
      ...(site.heritage ? ([['Heritage', site.heritage]] as Row[]) : []),
      ['Elevation grid', `${site.dem.resM} m — ${site.dem.name}`],
      ['Local time', site.tzLabel],
    ],
    terrain: [
      [`Area ≤ ${mission.slopeMax}° slope`, `${sM.toFixed(0)}%`, `${sE.toFixed(0)}%`],
      [`RMS height at ${mission.roughBaseline} m`, `${rM.toFixed(2)} m`, okE ? `${rE.toFixed(2)} m` : `${rE.toFixed(2)} m — not resolvable on ${site.dem.resM} m grid`],
      ['Grid spacing', `${region.dem.resM} m`, `${site.dem.resM} m`],
      ['Smallest resolvable baseline (2 × spacing)', `${2 * region.dem.resM} m`, `${2 * site.dem.resM} m`],
    ],
    monthLabel: `${MONTHS[m - 1]} ${y}`,
    windows,
    gaps: [
      ...NOT_REPRODUCIBLE.map((n): Row => [n.label, n.detail]),
      ['Illumination model', 'Simplified flat-horizon solar geometry (≈1° accuracy). No terrain shadowing, refraction, twilight sky or weather. Lunar timeline not computed.'],
      ['Natural vs artificial light', 'Natural low sun is what the windows describe. Artificial lighting is a different source (finite distance, beam spread, glare) and would need its own validation.'],
      ['Terrain imagery', 'Terrain renderings are procedural illustrations, not LRO or satellite data.'],
    ],
    missing: [
      ...a.criteria.filter((c) => c.status === 'not-assessed' && c.id !== 'resolution').map((c) => `${c.label} — ${c.reason}`),
      ...(site.dem.resM > mission.maxDemRes ? [`Elevation grid (${site.dem.resM} m) is coarser than the ${mission.maxDemRes} m requirement.`] : []),
      'Surrounding terrain horizon for the real sun path.',
      'Weather, snow cover and visibility for the candidate dates.',
    ],
    provenance: [
      ...SOURCES.map((s): Row => [s.name, `${s.url} — ${s.role}`]),
      ['Basemap', BASEMAP_CREDITS.join('; ')],
      ['Measured evidence', 'None is included in this dossier. Terrain statistics computed by the Layer 3 service (Comparison and Analog Explorer, labelled live) are not part of it.'],
      ['Fixtures', `All terrain statistics, grid resolutions and seasonal risks are illustrative demonstration values. Solar horizon: ${DEMO_HORIZON_DAYS} days from ${DEMO_START}.`],
    ],
    steps: FIELD_STEPS,
  }
}

const row = (r: Row) => `- **${r[0]}:** ${r[1]}`
export function toMarkdown(r: ReportData): string {
  const a = r.assessment
  return [
    `# TERRAWINDOW Research Dossier — Prototype Preliminary Assessment`,
    `_${r.title}_`,
    `> ${DISCLAIMER}`,
    `## 1. Mission overview`, ...r.mission.map(row),
    `## 2. Lunar reference`, ...r.lunar.map(row),
    `## 3. Earth candidate`, ...r.earth.map(row),
    `## 4. Terrain comparison`, `| Metric | Lunar reference | Earth candidate |`, `|---|---|---|`, ...r.terrain.map((t) => `| ${t.join(' | ')} |`),
    `## 5. Potential rehearsal windows — ${r.monthLabel} (illustrative, natural light)`,
    ...(r.windows.length ? [`| Date | Local time | Phase | Elevation | Azimuth | Duration |`, `|---|---|---|---|---|---|`, ...r.windows.map((w) => `| ${w.date} | ${w.time} | ${w.phase} | ${w.el} | ${w.az} | ${w.dur} |`)] : ['No qualifying window this month with the current criteria.']),
    `## 6. Criterion-specific assessment`, `Overall (screened criteria only, ${a.assessedCount} of ${a.totalCount} assessed): **${STATUS_LABEL[a.overall]}**`, ``,
    `| Criterion | Status | Evidence |`, `|---|---|---|`, ...a.criteria.map((c) => `| ${c.label} | ${STATUS_LABEL[c.status]} | ${c.reason} |`),
    `## 7. Known simulation gaps`, ...r.gaps.map(row),
    `## 8. Missing measurements`, ...r.missing.map((m) => `- ${m}`),
    `## 9. Data provenance`, ...r.provenance.map(row),
    `## 10. Recommended field verification`, ...r.steps.map((s, i) => `${i + 1}. ${s}`),
    ``,
  ].join('\n')
}

export function toSummary(r: ReportData): string {
  const a = r.assessment
  return `TERRAWINDOW prototype preliminary assessment — ${r.title}\nOverall (screened criteria only, ${a.assessedCount}/${a.totalCount} assessed): ${STATUS_LABEL[a.overall]}\n${a.criteria.filter((c) => c.id !== 'environment').map((c) => `• ${c.label}: ${STATUS_LABEL[c.status]} — ${c.reason}`).join('\n')}\nNot an official NASA qualification. Illustrative demonstration data.`
}
