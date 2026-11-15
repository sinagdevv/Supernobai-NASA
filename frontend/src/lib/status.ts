import type { Planet } from './planet'
import type { Screen } from './router'

/*
 * What the data on the current screen actually is. One label per screen, planet and result, never one global label:
 *   measured     numbers the Layer 2/3 service measured from a stored raster, loaded now
 *   computed     a Layer 4 or Layer 5 result computed by the service in this session. Computed is not validated.
 *   illustrative a visualization or example data that is not a measurement
 *   pending      nothing has been computed for this screen yet
 *   unavailable  the service, or what a call needed, cannot be reached; nothing is shown in its place
 */
export type DataState = 'measured' | 'computed' | 'illustrative' | 'pending' | 'unavailable' | 'checking'
export type Service = 'checking' | 'online' | 'offline'
export interface ContextStatus { state: DataState; label: string; detail: string }

/** Where a Layer 4 or Layer 5 call stands for the current planet. */
export type CallState = 'none' | 'running' | 'computed' | 'failed'
export interface EvidenceSnapshot { rehearsal: CallState; assessment: CallState }
export const NO_EVIDENCE: EvidenceSnapshot = { rehearsal: 'none', assessment: 'none' }

/** The part of a call the status needs. Evidence entries satisfy it. */
export interface CallSlot { data: unknown; loading: boolean; error: unknown }

/** Several calls as one state: running wins, then any result, then any failure. */
export function callState(slots: CallSlot[]): CallState {
  if (slots.some((s) => s.loading)) return 'running'
  if (slots.some((s) => s.data)) return 'computed'
  if (slots.some((s) => s.error)) return 'failed'
  return 'none'
}

/**
 * What this screen's chip should reflect for the selected planet. Rehearsal keys are `moon`, `mars` and `earth:<id>` (an
 * Earth analog belongs to the Moon only); assessment keys are `<planet>|<target key>`. Mission looks at the planet's own
 * target, the Explorer at Earth analogs, anything else at every assessment of this planet.
 */
export function evidenceSnapshot(planet: Planet, screen: Screen, rehearsal: Record<string, CallSlot>, assessments: Record<string, CallSlot>): EvidenceSnapshot {
  const l4 = Object.entries(rehearsal).filter(([k]) => k === planet || (planet === 'moon' && k.startsWith('earth:'))).map(([, v]) => v)
  const l5 = Object.entries(assessments).filter(([k]) => k.startsWith(`${planet}|`) && (screen === 'analogs' ? k.includes('|earth:') : screen === 'mission' ? k === `${planet}|${planet}` : true)).map(([, v]) => v)
  return { rehearsal: callState(l4), assessment: callState(l5) }
}

export const PLANET_CONTEXT: Record<Planet, { title: string; place: string }> = {
  moon: { title: 'Moon', place: 'South polar exploration' },
  mars: { title: 'Mars', place: 'Jezero regional terrain' },
}

/** The labels a single result can carry. "Independently validated" is listed so it is never invented: nothing in the platform earns it yet. */
export type EvidenceKind = 'computed' | 'validated' | 'illustrative' | 'insufficient' | 'unavailable'
export const EVIDENCE_LABEL: Record<EvidenceKind, { label: string; meaning: string }> = {
  computed: { label: 'Computed', meaning: 'Calculated by the service from stored data. Not checked against observations.' },
  validated: { label: 'Independently validated', meaning: 'Checked against independent observations.' },
  illustrative: { label: 'Illustrative', meaning: 'A schematic or example, not a calculation from data.' },
  insufficient: { label: 'Insufficient evidence', meaning: 'The data did not support a decision. This is neither a pass nor a fail.' },
  unavailable: { label: 'Service unavailable', meaning: 'The service did not answer, so nothing is shown.' },
}

/** The engine's own validation status decides, and only an explicit VALIDATED can say so. Today it reports NOT_VALIDATED, so this is always "computed". */
export const evidenceKind = (observationalValidation: string | undefined): EvidenceKind => (observationalValidation === 'VALIDATED' ? 'validated' : 'computed')

const checking = (what: string): ContextStatus => ({ state: 'checking', label: 'Checking service', detail: `Looking for the ${what} service.` })
const L4_UNAVAILABLE = 'The service could not be reached, so nothing is computed and nothing is substituted.'

export function contextStatus(planet: Planet, screen: Screen, service: Service, marsDataReady: boolean, ev: EvidenceSnapshot = NO_EVIDENCE): ContextStatus {
  if (planet === 'moon') {
    switch (screen) {
      case 'mission':
        if (ev.assessment === 'computed') return { state: 'computed', label: 'Computed assessment', detail: 'The Layer 5 assessment is computed by the service from stored terrain. Thresholds are adjustable assumptions and Layer 4 values stay unverified claims. The example-site screening beside it is illustrative.' }
        if (ev.assessment === 'running') return { state: 'checking', label: 'Assessing', detail: 'The service is computing the Layer 5 assessment.' }
        if (ev.assessment === 'failed') return { state: 'unavailable', label: 'Assessment unavailable', detail: 'The Layer 5 assessment could not be computed, so none is shown. The example-site screening below is illustrative.' }
        return { state: 'illustrative', label: 'Illustrative screening', detail: 'Example sites and their screening are illustrative. The computed Layer 5 assessment needs the service, which is not answering.' }
      case 'analogs': return ev.assessment === 'computed'
        ? { state: 'computed', label: 'Computed evidence', detail: 'A stored Earth dataset has a computed Layer 5 assessment. Example sites on the map remain illustrative; live terrain is measured.' }
        : { state: 'illustrative', label: 'Illustrative sites', detail: 'Example sites are illustrative. Live terrain on the map is measured Earth data from the Layer 3 service.' }
      case 'windows':
        if (ev.rehearsal === 'computed') return { state: 'computed', label: 'Computed · not validated', detail: 'Windows are computed by the solar-geometry engine (Layer 4) from stored terrain and SPICE kernels. They have not been checked against observations.' }
        if (ev.rehearsal === 'running') return { state: 'checking', label: 'Computing windows', detail: 'The solar-geometry engine is running. The first call after the service starts can take about 25 seconds.' }
        if (ev.rehearsal === 'failed') return { state: 'unavailable', label: 'Calculation failed', detail: `The Layer 4 calculation did not complete, so no window is shown. ${service === 'offline' ? L4_UNAVAILABLE : 'The reason is on the page.'}` }
        if (service === 'offline') return { state: 'unavailable', label: 'Service unavailable', detail: `No window can be computed. ${L4_UNAVAILABLE} The illustrative preview is not a result.` }
        return { state: 'illustrative', label: 'Illustrative preview', detail: 'Nothing has been computed yet. The timeline shown is a simplified solar model in the browser. Run a calculation for real Layer 4 output.' }
      case 'compare': return service === 'online'
        ? { state: 'measured', label: 'Measured evidence available', detail: 'The measured panel is computed by the Layer 3 service. The sections above it are illustrative.' }
        : service === 'checking' ? checking('Layer 2/3')
        : { state: 'unavailable', label: 'Service unavailable', detail: 'The Layer 2/3 service is not reachable, so no measured evidence is shown. Illustrative sections still work.' }
      case 'dossier':
        if (ev.rehearsal === 'computed' || ev.assessment === 'computed') return { state: 'computed', label: 'Part computed · not stored', detail: 'The dossier includes computed Layer 4 and Layer 5 results from this session. It is not stored (Layer 6 is not connected); the rest of it is illustrative.' }
        return { state: 'illustrative', label: 'Illustrative report', detail: 'The dossier is built from illustrative data and states that it contains no measured evidence. Computed results appear in it after you run them.' }
    }
  }
  // Mars
  if (screen === 'analogs') {
    return ev.assessment === 'computed'
      ? { state: 'computed', label: 'Computed evidence', detail: 'A stored Earth dataset has a computed Layer 5 assessment against the Mars criteria. Earth terrain on the map is real; no Mars site is assessed here.' }
      : { state: 'pending', label: 'Not assessed yet', detail: 'Earth terrain on the map is real. No assessment against the Mars criteria has been computed for a stored dataset yet.' }
  }
  if (screen === 'windows') {
    if (ev.rehearsal === 'computed') return { state: 'computed', label: 'Computed · not validated', detail: 'Computed by the solar-geometry engine on the 1.85 km MOLA grid. Not checked against observations; unobserved bins are reported as insufficient coverage, never as shadow.' }
    if (ev.rehearsal === 'running') return { state: 'checking', label: 'Computing windows', detail: 'The solar-geometry engine is running. The first call after the service starts can take about 25 seconds.' }
    if (ev.rehearsal === 'failed') return { state: 'unavailable', label: 'Calculation failed', detail: 'The Layer 4 calculation did not complete, so no window is shown. Nothing is substituted.' }
    if (service === 'offline') return { state: 'unavailable', label: 'Service unavailable', detail: `No Mars window can be computed. ${L4_UNAVAILABLE}` }
    return { state: 'pending', label: 'Not computed yet', detail: 'No Mars rehearsal window has been computed. Run a calculation for the Jezero region.' }
  }
  if (service === 'checking') return checking('Layer 2/3')
  if (service === 'offline') return { state: 'unavailable', label: 'Service unavailable', detail: 'The service is not reachable, so no Martian terrain is measured or shown. Nothing is substituted.' }
  if (!marsDataReady) return { state: 'unavailable', label: 'Dataset not retrieved', detail: 'The service is running, but the Jezero MOLA region has not been retrieved on this machine.' }
  if (screen === 'mission' && ev.assessment === 'computed') return { state: 'computed', label: 'Computed assessment', detail: 'Layer 5 assessment of the Jezero region computed from MOLA terrain. Thresholds are adjustable assumptions, defined for Mars separately; not validated.' }
  if (screen === 'dossier' && (ev.rehearsal === 'computed' || ev.assessment === 'computed')) return { state: 'computed', label: 'Part computed · not stored', detail: 'Includes computed Layer 4 and Layer 5 results from this session. Not stored (Layer 6 is not connected). Terrain sections are measured MOLA data.' }
  return { state: 'measured', label: 'Measured terrain', detail: 'MOLA topography of the Jezero region, measured by the Layer 3 service at 463 m and coarser scales.' }
}
