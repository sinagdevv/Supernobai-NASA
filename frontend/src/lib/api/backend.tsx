import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getDatasets, getHealth } from './client'
import type { StoredDataset } from './types'

/**
 * Whether the Layer 2/3 service is reachable. Nothing else in the app depends on it: when it is offline every screen keeps
 * its demonstration data, and the one panel that wants live results says so instead of showing numbers.
 */
type State =
  | { status: 'checking' }
  | { status: 'offline' }
  | { status: 'online'; version: string; stored: StoredDataset[] }

interface Backend { state: State; recheck: () => void }
const Ctx = createContext<Backend | null>(null)

export function BackendProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'checking' })
  const [tick, setTick] = useState(0)
  const recheck = useCallback(() => { setState({ status: 'checking' }); setTick((t) => t + 1) }, [])

  useEffect(() => {
    let live = true
    Promise.all([getHealth(), getDatasets()])
      .then(([h, d]) => live && setState({ status: 'online', version: h.version, stored: d.stored_datasets }))
      .catch(() => live && setState({ status: 'offline' }))
    return () => { live = false }
  }, [tick])

  const value = useMemo(() => ({ state, recheck }), [state, recheck])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useBackend() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useBackend outside BackendProvider')
  return c
}
