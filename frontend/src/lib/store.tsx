import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { DEFAULT_MISSION } from '../data/mission'
import { SITES } from '../data/sites'
import type { Assessment, Mission, Status, TerrainClass } from '../data/types'
import { assessSite } from './assess'

export interface Filters {
  terrain: TerrainClass[]
  maxDemRes: number
  statuses: Status[]
  query: string
}
export type BaseMap = 'satellite' | 'topo' | 'dark'
export type Lighting = 'natural' | 'artificial'

const DEFAULT_FILTERS: Filters = { terrain: [], maxDemRes: 30, statuses: [], query: '' }

interface AppState {
  mission: Mission
  setMission: (p: Partial<Mission>) => void
  resetMission: () => void
  selectedId: string | null
  select: (id: string | null) => void
  compareIds: string[]
  toggleCompare: (id: string) => void
  filters: Filters
  setFilters: (p: Partial<Filters>) => void
  baseMap: BaseMap
  setBaseMap: (b: BaseMap) => void
  relief: boolean
  setRelief: (b: boolean) => void
  /** Selected rehearsal date (YYYY-MM-DD) and local minute-of-day */
  date: string
  minute: number
  setWhen: (date: string, minute?: number) => void
  setMinute: (m: number) => void
  heading: number
  setHeading: (h: number) => void
  lighting: Lighting
  setLighting: (l: Lighting) => void
  lampEl: number
  setLampEl: (e: number) => void
  assessments: Map<string, Assessment>
  /** Sites passing the sidebar filters, best category first */
  results: string[]
  resetAll: () => void
}

const Ctx = createContext<AppState | null>(null)
export const useApp = () => {
  const c = useContext(Ctx)
  if (!c) throw new Error('useApp outside provider')
  return c
}

const ORDER: Record<Status, number> = { potential: 0, 'not-assessed': 1, 'not-suitable': 2 }

export function AppProvider({ children }: { children: ReactNode }) {
  const [mission, setM] = useState<Mission>(DEFAULT_MISSION)
  const [selectedId, select] = useState<string | null>(null)
  const [compareIds, setCompare] = useState<string[]>([])
  const [filters, setF] = useState<Filters>(DEFAULT_FILTERS)
  const [baseMap, setBaseMap] = useState<BaseMap>('satellite')
  // Relief uses a public tile source that is not always reachable, so it is opt-in.
  const [relief, setRelief] = useState(false)
  const [date, setDate] = useState('2026-12-14')
  const [minute, setMinute] = useState(360)
  const [heading, setHeading] = useState(180)
  const [lighting, setLighting] = useState<Lighting>('natural')
  const [lampEl, setLampEl] = useState(2)

  const setMission = useCallback((p: Partial<Mission>) => setM((m) => ({ ...m, ...p })), [])
  const resetMission = useCallback(() => setM(DEFAULT_MISSION), [])
  const setFilters = useCallback((p: Partial<Filters>) => setF((f) => ({ ...f, ...p })), [])
  const toggleCompare = useCallback((id: string) => setCompare((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= 3 ? c : [...c, id])), [])
  const setWhen = useCallback((d: string, m?: number) => {
    setDate(d)
    if (m !== undefined) setMinute(m)
  }, [])
  const resetAll = useCallback(() => {
    setM(DEFAULT_MISSION); select(null); setCompare([]); setF(DEFAULT_FILTERS)
    setDate('2026-12-14'); setMinute(360); setHeading(180); setLighting('natural'); setLampEl(2)
  }, [])

  const assessments = useMemo(() => new Map(SITES.map((s) => [s.id, assessSite(s, mission)])), [mission])
  const results = useMemo(() => {
    const q = filters.query.trim().toLowerCase()
    return SITES.filter((s) => {
      if (filters.terrain.length && !filters.terrain.includes(s.terrain)) return false
      if (s.dem.resM > filters.maxDemRes) return false
      if (filters.statuses.length && !filters.statuses.includes(assessments.get(s.id)!.overall)) return false
      if (q && !`${s.name} ${s.place}`.toLowerCase().includes(q)) return false
      return true
    })
      .sort((a, b) => ORDER[assessments.get(a.id)!.overall] - ORDER[assessments.get(b.id)!.overall] || a.name.localeCompare(b.name))
      .map((s) => s.id)
  }, [filters, assessments])

  const value: AppState = {
    mission, setMission, resetMission, selectedId, select, compareIds, toggleCompare, filters, setFilters,
    baseMap, setBaseMap, relief, setRelief, date, minute, setWhen, setMinute, heading, setHeading,
    lighting, setLighting, lampEl, setLampEl, assessments, results, resetAll,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
