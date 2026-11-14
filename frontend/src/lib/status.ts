import type { Planet } from './planet'
import type { Screen } from './router'

/*
 * What the data on the current screen actually is. One label per screen and planet, never one global label:
 *   measured     numbers computed by the Layer 2/3 service from a stored raster, loaded now
 *   illustrative a visualization or example data that is not a measurement
 *   pending      the assessment needs an engine that is not built (Layer 4 solar geometry, Layer 5 suitability)
 *   unavailable  the service, or the dataset behind a measured screen, cannot be reached
 */
export type DataState = 'measured' | 'illustrative' | 'pending' | 'unavailable' | 'checking'
export type Service = 'checking' | 'online' | 'offline'
export interface ContextStatus { state: DataState; label: string; detail: string }

export const PLANET_CONTEXT: Record<Planet, { title: string; place: string }> = {
  moon: { title: 'Moon', place: 'South polar exploration' },
  mars: { title: 'Mars', place: 'Jezero regional terrain' },
}

export function contextStatus(planet: Planet, screen: Screen, service: Service, marsDataReady: boolean): ContextStatus {
  if (planet === 'moon') {
    switch (screen) {
      case 'mission': return { state: 'illustrative', label: 'Illustrative screening', detail: 'Example sites and mission criteria are illustrative. Measured lunar terrain is on the Comparison screen.' }
      case 'analogs': return { state: 'illustrative', label: 'Illustrative sites', detail: 'Example sites are illustrative. Live terrain on the map is measured Earth data from the Layer 3 service.' }
      case 'windows': return { state: 'pending', label: 'Assessment pending', detail: 'Windows come from a simplified solar model in the browser. The solar-geometry engine (Layer 4) is not built.' }
      case 'compare': return service === 'online'
        ? { state: 'measured', label: 'Measured evidence available', detail: 'The measured panel is computed by the Layer 3 service. The sections above it are illustrative.' }
        : service === 'checking' ? { state: 'checking', label: 'Checking service', detail: 'Looking for the Layer 2/3 service.' }
        : { state: 'unavailable', label: 'Service unavailable', detail: 'The Layer 2/3 service is not reachable, so no measured evidence is shown. Illustrative sections still work.' }
      case 'dossier': return { state: 'illustrative', label: 'Illustrative report', detail: 'The dossier is built from illustrative data and states that it contains no measured evidence.' }
    }
  }
  // Mars
  if (screen === 'analogs') return { state: 'pending', label: 'Mars assessment pending', detail: 'Earth terrain on the map is real. No Mars suitability assessment exists: the evidence engine (Layer 5) is not built.' }
  if (screen === 'windows') return { state: 'pending', label: 'Layer 4 pending', detail: 'No Mars rehearsal window is computed: the solar-geometry engine (Layer 4) is not built.' }
  if (service === 'checking') return { state: 'checking', label: 'Checking service', detail: 'Looking for the Layer 2/3 service.' }
  if (service === 'offline') return { state: 'unavailable', label: 'Service unavailable', detail: 'The Layer 2/3 service is not reachable, so no Martian terrain is measured or shown. Nothing is substituted.' }
  if (!marsDataReady) return { state: 'unavailable', label: 'Dataset not retrieved', detail: 'The service is running, but the Jezero MOLA region has not been retrieved on this machine.' }
  return { state: 'measured', label: 'Measured terrain', detail: 'MOLA topography of the Jezero region, measured by the Layer 3 service at 463 m and coarser scales.' }
}
