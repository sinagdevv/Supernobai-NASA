import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'
import type { Planet } from './profiles'

export type { Planet }
export const DEFAULT_PLANET: Planet = 'moon'
const KEY = 'tw-planet'

/** Reference ribbon colour per planet. Mirrors `--planet-ref` in index.css; the intro paints with these directly so its last frame is the hero's colour. */
export const REF_COLOR: Record<Planet, [number, number, number]> = { moon: [197, 202, 208], mars: [176, 118, 90] }
export const rgb = (c: number[]) => `rgb(${c.map(Math.round).join(' ')})`

export const PLANET_COPY: Record<Planet, { label: string; reference: string; headline: [string, string]; lede: string; transect: string; sunLabel: string }> = {
  moon: {
    label: 'Moon',
    reference: 'Lunar reference',
    headline: ['Find the Earth.', 'Test for the Moon.'],
    lede: 'Discover terrestrial analog environments, explore potential rehearsal windows, and evaluate mission-specific testing conditions.',
    transect: 'south-polar highland profile',
    sunLabel: 'Sun',
  },
  mars: {
    label: 'Mars',
    reference: 'Martian reference',
    headline: ['Find the Earth.', 'Prepare for Mars.'],
    lede: 'Explore terrestrial analog environments for Martian rover mobility. Mars terrain is measured from MOLA data; Mars criteria and assessments are not built yet.',
    transect: 'basin, mesa and dune profile',
    sunLabel: 'Illustrative sun',
  },
}

interface PlanetState { planet: Planet; setPlanet: (p: Planet) => void }
const Ctx = createContext<PlanetState | null>(null)
export const usePlanet = () => {
  const c = useContext(Ctx)
  if (!c) throw new Error('usePlanet outside provider')
  return c
}

function initial(): Planet {
  try { return sessionStorage.getItem(KEY) === 'mars' ? 'mars' : DEFAULT_PLANET } catch { return DEFAULT_PLANET }
}

/** One selected planet for the whole session: landing, intro and workspace read the same value. */
export function PlanetProvider({ children }: { children: ReactNode }) {
  const [planet, set] = useState<Planet>(initial)
  const setPlanet = useCallback((p: Planet) => {
    set(p)
    try { sessionStorage.setItem(KEY, p) } catch { /* private mode: the choice lasts until reload */ }
  }, [])
  useLayoutEffect(() => { document.documentElement.dataset.planet = planet }, [planet])
  const value = useMemo(() => ({ planet, setPlanet }), [planet, setPlanet])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
