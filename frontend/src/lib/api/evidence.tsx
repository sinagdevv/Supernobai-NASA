import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Planet } from '../profiles'
import { buildAssessRequest, defaultEdits, type CriterionEdit, type Edits } from '../suitability'
import { buildRehearseRequest, type RehearsalParams, type RehearsalTarget } from '../rehearsal'
import { ApiError, assess, getRehearsalStatus, rehearse } from './client'
import { useBackend } from './backend'
import type { MissionAssessment, RehearsalResult, RehearsalStatus } from './types'

/*
 * The Layer 4 and Layer 5 results of this session, kept above the screens so Rehearsal Windows, Mission, the Explorer,
 * Comparison and the Dossier read the same thing. Nothing is stored anywhere (Layer 6 is not connected): reload and it is gone.
 * A failed call leaves an error and no data. Nothing is ever substituted for it.
 */

/** One call's state. While a newer call runs the previous `data` stays, so the screen does not blank on every edit. */
export interface Call<T> { data: T | null; loading: boolean; error: ApiError | null; /** What the data was computed from. */ key: string | null }
const idle = <T,>(): Call<T> => ({ data: null, loading: false, error: null, key: null })

export interface RehearsalEntry extends Call<RehearsalResult> { target: RehearsalTarget; params: RehearsalParams }
export type AssessEntry = Call<MissionAssessment>

const asError = (e: unknown) => (e instanceof ApiError ? e : new ApiError('bad_response', 'Unexpected failure.'))
export const assessKey = (planet: Planet, targetKey: string) => `${planet}|${targetKey}`

interface Evidence {
  /** Layer 4 service status; null until asked or when the service is offline. */
  status: Call<RehearsalStatus>
  rehearsal: Record<string, RehearsalEntry>
  runRehearsal: (target: RehearsalTarget, params: RehearsalParams) => void
  edits: Record<Planet, Edits>
  setEdit: (planet: Planet, id: string, patch: Partial<CriterionEdit>) => void
  resetEdits: (planet: Planet) => void
  assessments: Record<string, AssessEntry>
  /** Runs Layer 5 for a target now, or after the debounce when criteria are being edited. */
  assessTarget: (planet: Planet, target: RehearsalTarget, opts?: { debounce?: boolean }) => void
  /** The Layer 4 result Layer 5 pairs with this target, if there is one. */
  layer4For: (planet: Planet, target: RehearsalTarget) => RehearsalResult | null
}

const Ctx = createContext<Evidence | null>(null)

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const { state: backend } = useBackend()
  const online = backend.status === 'online'
  const [status, setStatus] = useState<Call<RehearsalStatus>>(idle)
  const [rehearsal, setRehearsal] = useState<Record<string, RehearsalEntry>>({})
  const [edits, setEdits] = useState<Record<Planet, Edits>>({ moon: defaultEdits('moon'), mars: defaultEdits('mars') })
  const [assessments, setAssessments] = useState<Record<string, AssessEntry>>({})
  const l4Seq = useRef<Record<string, { n: number; ctl?: AbortController }>>({})
  const l5Seq = useRef<Record<string, { n: number; ctl?: AbortController; timer?: ReturnType<typeof setTimeout> }>>({})
  // Layer 5 reads the latest edits and results at the moment it runs, not when it was scheduled.
  const latest = useRef({ edits, rehearsal })
  useEffect(() => { latest.current = { edits, rehearsal } })

  useEffect(() => {
    if (!online) return
    let live = true
    setStatus((s) => ({ ...s, loading: true }))
    getRehearsalStatus().then(
      (data) => live && setStatus({ data, loading: false, error: null, key: 'status' }),
      (e) => live && setStatus({ data: null, loading: false, error: asError(e), key: null }),
    )
    return () => { live = false }
  }, [online])

  const runRehearsal = useCallback((target: RehearsalTarget, params: RehearsalParams) => {
    const slot = (l4Seq.current[target.key] ??= { n: 0 })
    slot.ctl?.abort()
    const ctl = (slot.ctl = new AbortController())
    const n = ++slot.n
    const req = buildRehearseRequest(target, params)
    const key = JSON.stringify(req)
    setRehearsal((m) => ({ ...m, [target.key]: { target, params, data: m[target.key]?.data ?? null, loading: true, error: null, key: m[target.key]?.key ?? null } }))
    rehearse(req, ctl.signal).then(
      (data) => n === slot.n && setRehearsal((m) => ({ ...m, [target.key]: { target, params, data, loading: false, error: null, key } })),
      (e) => n === slot.n && setRehearsal((m) => ({ ...m, [target.key]: { target, params, data: null, loading: false, error: asError(e), key: null } })),
    )
  }, [])

  const layer4For = useCallback((planet: Planet, target: RehearsalTarget): RehearsalResult | null => {
    // Earth lighting is not the Martian sun: an Earth analog assessed against Mars criteria gets no rehearsal evidence.
    if (planet === 'mars' && target.body === 'earth') return null
    return latest.current.rehearsal[target.key]?.data ?? null
  }, [])

  const setEdit = useCallback((planet: Planet, id: string, patch: Partial<CriterionEdit>) => setEdits((e) => ({ ...e, [planet]: { ...e[planet], [id]: { ...e[planet][id], ...patch } } })), [])
  const resetEdits = useCallback((planet: Planet) => setEdits((e) => ({ ...e, [planet]: defaultEdits(planet) })), [])

  const assessTarget = useCallback((planet: Planet, target: RehearsalTarget, opts?: { debounce?: boolean }) => {
    const k = assessKey(planet, target.key)
    const slot = (l5Seq.current[k] ??= { n: 0 })
    clearTimeout(slot.timer)
    const go = () => {
      const l4 = layer4For(planet, target)
      const req = buildAssessRequest(planet, target, latest.current.edits[planet], l4)
      slot.ctl?.abort()
      const n = ++slot.n
      if (!req) {
        setAssessments((m) => ({ ...m, [k]: idle() }))
        return
      }
      const ctl = (slot.ctl = new AbortController())
      // The key records what the result was computed from, so a screen can tell when criteria or the Layer 4 run have since changed.
      const key = JSON.stringify({ p: req.mission_profile.criteria, c: req.candidate, l4: l4?.generated_at ?? null })
      setAssessments((m) => ({ ...m, [k]: { data: m[k]?.data ?? null, loading: true, error: null, key: m[k]?.key ?? null } }))
      assess(req, ctl.signal).then(
        (data) => n === slot.n && setAssessments((m) => ({ ...m, [k]: { data, loading: false, error: null, key } })),
        (e) => n === slot.n && setAssessments((m) => ({ ...m, [k]: { data: null, loading: false, error: asError(e), key: null } })),
      )
    }
    // Even an immediate call waits one tick, so the edits and results it reads have been committed.
    slot.timer = setTimeout(go, opts?.debounce ? 600 : 0)
  }, [layer4For])

  const value = useMemo(() => ({ status, rehearsal, runRehearsal, edits, setEdit, resetEdits, assessments, assessTarget, layer4For }), [status, rehearsal, runRehearsal, edits, setEdit, resetEdits, assessments, assessTarget, layer4For])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useEvidence() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useEvidence outside EvidenceProvider')
  return c
}

/** The key Layer 5 would compute for these inputs now. Compare with `AssessEntry.key` to see whether a shown result is current. */
export function currentAssessKey(planet: Planet, target: RehearsalTarget, edits: Edits, layer4: RehearsalResult | null): string | null {
  const req = buildAssessRequest(planet, target, edits, layer4)
  return req ? JSON.stringify({ p: req.mission_profile.criteria, c: req.candidate, l4: layer4?.generated_at ?? null }) : null
}
