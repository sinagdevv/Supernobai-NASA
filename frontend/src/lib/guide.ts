import type { Screen } from './router'

/* The optional first-visit guide: its steps and its persistence. Pure logic, no React. */

export const GUIDE_KEY = 'tw-guide'

export type GuideState = 'done' | 'skipped'

export type GuideStep = { id: string; title: string; body: string; action: { label: string; screen?: Screen } }

export const WELCOME = 'Welcome to TERRAWINDOW — it helps researchers identify, compare and assess Earth environments for planetary experiments.'

export const STEPS: GuideStep[] = [
  { id: 'planet', title: 'Select Moon or Mars', body: 'The planet switcher at the top sets the target for every screen. The Moon is the primary mission; Mars covers regional terrain only.', action: { label: 'Go to the planet switcher' } },
  { id: 'mission', title: 'Define a mission', body: 'Set the terrain and sunlight limits your experiment needs. The assessment checks stored terrain data against them.', action: { label: 'Go to Mission', screen: 'mission' } },
  { id: 'analogs', title: 'Explore Earth candidate sites', body: 'The map shows candidate sites with measured terrain statistics. Filter them and pin the ones worth comparing.', action: { label: 'Go to Analog Explorer', screen: 'analogs' } },
  { id: 'compare', title: 'Compare scientific evidence', body: 'See slope, roughness, elevation, resolution and coverage side by side, with the evidence status of each.', action: { label: 'Go to Comparison', screen: 'compare' } },
  { id: 'windows', title: 'Explore computed rehearsal windows', body: 'Compute when the sun is in the band you need and whether terrain or missing data blocks it.', action: { label: 'Go to Rehearsal Windows', screen: 'windows' } },
  { id: 'dossier', title: 'Review the research dossier', body: 'The dossier collects the evidence and its limits. Results are computed, not validated against observations, and not stored.', action: { label: 'Go to Dossier', screen: 'dossier' } },
]

/** Reads the saved outcome. Missing, unreadable or unexpected values all mean "show the guide". */
export function readGuide(): GuideState | null {
  try {
    const v = globalThis.localStorage?.getItem(GUIDE_KEY)
    return v === 'done' || v === 'skipped' ? v : null
  } catch {
    return null
  }
}

/** Saves the outcome. Storage can be blocked or full: the guide then simply returns next visit. */
export function writeGuide(s: GuideState): boolean {
  try {
    globalThis.localStorage.setItem(GUIDE_KEY, s)
    return true
  } catch {
    return false
  }
}
