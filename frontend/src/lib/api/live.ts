import { useCallback, useRef, useState } from 'react'
import { ApiError, overlay as fetchOverlay, screen as fetchScreen } from './client'
import type { LonLat, OverlayLayer, OverlayResponse, ScreenResponse } from './types'

/** A request that is idle, in flight, answered, or failed. A failure keeps its error: it is never replaced by sample data. */
export type Req<T> = { status: 'idle' } | { status: 'loading' } | { status: 'done'; data: T } | { status: 'error'; error: ApiError }

export interface ScreenParams { patchSizeM: number; slopeMeanMax: number }
export const DEFAULT_PARAMS: ScreenParams = { patchSizeM: 1500, slopeMeanMax: 8 }

const asError = (e: unknown) => (e instanceof ApiError ? e : new ApiError('bad_response', 'Unexpected failure.'))

/**
 * What the Explorer shows from the Layer 3 service: one stored dataset, an optional terrain overlay, and an optional
 * candidate screening. Each request is independent; a newer request for the same thing supersedes an older one.
 */
export function useLiveTerrain() {
  const [datasetId, setDatasetId] = useState<string | null>(null)
  const [layer, setLayerState] = useState<OverlayLayer | 'off'>('off')
  const [overlay, setOverlay] = useState<Req<OverlayResponse>>({ status: 'idle' })
  const [screen, setScreen] = useState<Req<ScreenResponse>>({ status: 'idle' })
  const [params, setParams] = useState<ScreenParams>(DEFAULT_PARAMS)
  const [patchId, setPatchId] = useState<string | null>(null)
  /** Footprint the map should frame, and a counter so asking again re-frames. */
  const [fit, setFit] = useState<{ coords: LonLat[]; token: number } | null>(null)
  const seq = useRef({ overlay: 0, screen: 0 })

  const loadOverlay = useCallback((id: string, l: OverlayLayer) => {
    const n = ++seq.current.overlay
    setOverlay({ status: 'loading' })
    fetchOverlay({ dataset: { id }, layer: l, sun_azimuth_deg: 120, sun_elevation_deg: 7 }).then(
      (data) => {
        if (n !== seq.current.overlay) return
        setOverlay({ status: 'done', data })
        setFit((f) => ({ coords: data.coordinates, token: (f?.token ?? 0) + 1 }))
      },
      (e) => n === seq.current.overlay && setOverlay({ status: 'error', error: asError(e) }),
    )
  }, [])

  const reset = useCallback(() => {
    seq.current.overlay++; seq.current.screen++
    setOverlay({ status: 'idle' }); setScreen({ status: 'idle' }); setPatchId(null)
  }, [])

  const chooseDataset = useCallback((id: string | null) => {
    reset()
    setDatasetId(id)
    setLayerState('off')
  }, [reset])

  const setLayer = useCallback((l: OverlayLayer | 'off') => {
    setLayerState(l)
    if (l === 'off' || !datasetId) { seq.current.overlay++; setOverlay({ status: 'idle' }); return }
    loadOverlay(datasetId, l)
  }, [datasetId, loadOverlay])

  const runScreen = useCallback(() => {
    if (!datasetId) return
    const n = ++seq.current.screen
    setScreen({ status: 'loading' }); setPatchId(null)
    fetchScreen({ dataset: { id: datasetId }, patch_size_m: params.patchSizeM, criteria: { slope_mean_deg: { max: params.slopeMeanMax } } }).then(
      (data) => {
        if (n !== seq.current.screen) return
        setScreen({ status: 'done', data })
        const ring = data.features.flatMap((f) => f.geometry.coordinates[0] as LonLat[])
        if (ring.length) setFit((f) => ({ coords: ring, token: (f?.token ?? 0) + 1 }))
      },
      (e) => n === seq.current.screen && setScreen({ status: 'error', error: asError(e) }),
    )
  }, [datasetId, params])

  const clear = useCallback(() => { reset(); setLayerState('off') }, [reset])

  return { datasetId, chooseDataset, layer, setLayer, overlay, screen, runScreen, params, setParams, patchId, setPatchId, fit, clear }
}

export type LiveTerrain = ReturnType<typeof useLiveTerrain>
