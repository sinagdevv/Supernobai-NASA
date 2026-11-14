import { createContext, useContext, type ReactNode } from 'react'
import { useLiveTerrain, type LiveTerrain } from './live'

/** Live terrain state lives above the screens so the dataset, overlay and screening survive switching tabs, like the rest of the app state. */
const Ctx = createContext<LiveTerrain | null>(null)

export function LiveTerrainProvider({ children }: { children: ReactNode }) {
  return <Ctx.Provider value={useLiveTerrain()}>{children}</Ctx.Provider>
}

export function useLive() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useLive outside LiveTerrainProvider')
  return c
}
