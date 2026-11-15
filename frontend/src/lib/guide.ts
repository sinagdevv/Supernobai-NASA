import type { Screen } from './router'

/* The optional first-visit guide: its steps and its persistence. Pure logic, no React. */

export const GUIDE_KEY = 'tw-guide'

export type GuideState = 'done' | 'skipped'

export type GuideStep = {
  id: string
  title: string
  body: string
  /** Where the step lives. Next and Back go there; the guide never changes anything else. */
  screen?: Screen
  /** Selectors for the real control to highlight, most specific first; the first visible match wins. */
  targets: string[]
  /** What the optional "try it" button does: it only moves focus to that control. */
  action: string
  /** Shown on Mars in place of nothing: what differs there. */
  mars?: string
  /** The same step seen from the landing page. */
  home?: { title: string; body: string; targets: string[]; action: string }
}

export const WELCOME = 'Welcome to TERRAWINDOW — it helps researchers identify, compare and assess Earth environments for planetary experiments.'

export const STEPS: GuideStep[] = [
  { id: 'planet', title: 'Select Moon or Mars', body: 'The planet switcher sets the target for every screen. The Moon is the primary mission; Mars covers regional terrain only.', targets: ['[aria-label="Planetary target"]'], action: 'Focus the planet switcher' },
  {
    id: 'mission', title: 'Define a mission', body: 'Set the terrain and sunlight limits your experiment needs. The assessment checks stored terrain data against them.', screen: 'mission',
    targets: ['[aria-label="Mission objective"]', '#main h1', '#main'], action: 'Focus the mission controls',
    mars: 'On Mars this screen shows Jezero regional terrain. Mission limits and the suitability assessment apply to the Moon only.',
    home: { title: 'Open the workspace', body: 'The Open workspace button leads to the mission, where you set what your experiment needs.', targets: ['[data-guide="open-workspace"]'], action: 'Open workspace' },
  },
  { id: 'analogs', title: 'Explore Earth candidate sites', body: 'The map shows candidate sites with measured terrain statistics. Filter them and pin the ones worth comparing.', screen: 'analogs', targets: ['[aria-label="Candidate sites and evidence"]', '#main'], action: 'Focus the candidate list', mars: 'On Mars the markers carry no suitability verdict, because no Martian assessment exists.' },
  { id: 'compare', title: 'Compare scientific evidence', body: 'See slope, roughness, elevation, resolution and coverage side by side, with the evidence status of each.', screen: 'compare', targets: ['[aria-label="Earth candidates to compare"]', '#main h1', '#main'], action: 'Focus the candidates' },
  { id: 'windows', title: 'Explore computed rehearsal windows', body: 'Compute when the sun is in the band you need and whether terrain or missing data blocks it.', screen: 'windows', targets: ['#main h1', '#main'], action: 'Focus the screen', mars: 'On Mars the windows are computed on the 1.85 km MOLA grid.' },
  { id: 'dossier', title: 'Review the research dossier', body: 'The dossier collects the evidence and its limits. Results are computed, not validated against observations, and not stored.', screen: 'dossier', targets: ['[aria-label="Dossier sections"]', '[aria-label="Research dossier"]', '#main'], action: 'Focus the dossier' },
]

export const SCREEN_LABEL: Record<Screen, string> = { mission: 'Mission', analogs: 'Analog Explorer', windows: 'Rehearsal Windows', compare: 'Comparison', dossier: 'Dossier' }

/* ───────── Geometry: pure, so the placement rules are testable without a browser ───────── */

export type Box = { top: number; left: number; width: number; height: number }
/** The part of the viewport the guide may use: below the header, above any bottom tab bar. */
export type Area = { width: number; top: number; bottom: number }
export type Placement =
  | { mode: 'dock' }
  | { mode: 'float'; x: number; y: number; side: 'top' | 'bottom' | 'left' | 'right'; arrow: number }

export const CARD_W = 360
const EDGE = 8
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi))

/** Where the card goes relative to the highlighted control: below, above, right, left, else docked. Phones always dock. */
export function placeCard(t: Box | null, card: { width: number; height: number }, a: Area, gap = 16): Placement {
  if (!t || a.width < 640) return { mode: 'dock' }
  if (t.top >= a.bottom || t.top + t.height <= a.top) return { mode: 'dock' } // still scrolling toward it: do not float beside something off screen
  const w = Math.min(card.width, a.width - 2 * EDGE), h = card.height
  const cx = t.left + t.width / 2, cy = t.top + t.height / 2
  const x = clamp(cx - w / 2, EDGE, a.width - w - EDGE)
  const y = clamp(cy - h / 2, a.top + EDGE, a.bottom - h - EDGE)
  if (t.top + t.height + gap + h <= a.bottom - EDGE) return { mode: 'float', x, y: t.top + t.height + gap, side: 'bottom', arrow: clamp(cx - x, 20, w - 20) }
  if (t.top - gap - h >= a.top + EDGE) return { mode: 'float', x, y: t.top - gap - h, side: 'top', arrow: clamp(cx - x, 20, w - 20) }
  if (t.left + t.width + gap + w <= a.width - EDGE) return { mode: 'float', x: t.left + t.width + gap, y, side: 'right', arrow: clamp(cy - y, 20, h - 20) }
  if (t.left - gap - w >= EDGE) return { mode: 'float', x: t.left - gap - w, y, side: 'left', arrow: clamp(cy - y, 20, h - 20) }
  return { mode: 'dock' }
}

/** How far to scroll (positive = down) so the control sits fully inside the usable area. Tall controls show their start. */
export function scrollDelta(t: Box, a: Area, pad = 12): number {
  const room = a.bottom - a.top
  if (t.top >= a.top + pad && t.top + t.height <= a.bottom - pad) return 0
  if (t.height > room - 2 * pad) return t.top - (a.top + pad)
  return t.top + t.height / 2 - (a.top + room / 2)
}

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
