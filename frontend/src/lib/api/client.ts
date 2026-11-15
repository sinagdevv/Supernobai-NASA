import type { AssessRequest, CompareRequest, ComparisonResult, DatasetsResponse, Health, MissionAssessment, OverlayRequest, OverlayResponse, ProfileRequest, RehearsalResult, RehearsalStatus, RehearseRequest, ScreenRequest, ScreenResponse, TerrainProfile } from './types'

/** The service is reached through the dev/preview proxy at `/api`, or at `VITE_TERRAWINDOW_API` when set. */
const BASE = (import.meta.env.VITE_TERRAWINDOW_API as string | undefined)?.replace(/\/$/, '') ?? '/api'

/** Every failure from the service, or on the way to it, as one shape the interface can show. */
export class ApiError extends Error {
  constructor(
    /** The service's error code (`source_unavailable`, `scale_not_supported`, ...) or `unreachable` / `bad_response`. */
    readonly code: string,
    message: string,
    readonly details?: unknown,
    readonly status?: number,
  ) {
    super(message)
  }
}

/** `Retry-After` as seconds (the delta form; an HTTP date is not worth parsing here). */
const retryAfter = (res: Response) => {
  const n = Number(res.headers.get('retry-after'))
  return Number.isFinite(n) && n > 0 ? Math.ceil(n) : undefined
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeoutMs)
  // A caller that supersedes its own request (a newer criterion edit) can cancel this one.
  const outer = init?.signal
  if (outer?.aborted) ctl.abort()
  else outer?.addEventListener('abort', () => ctl.abort(), { once: true })
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, signal: ctl.signal, headers: { 'content-type': 'application/json', ...init?.headers } })
  } catch (e) {
    if (outer?.aborted) throw new ApiError('aborted', 'The request was superseded.')
    throw new ApiError('unreachable', e instanceof DOMException && e.name === 'AbortError' ? 'The service did not answer in time.' : 'The service could not be reached.')
  } finally {
    clearTimeout(timer)
  }
  let body: unknown
  try {
    body = await res.json()
  } catch {
    // A dev proxy answers 5xx with HTML when nothing listens behind it: that is "unreachable", not a bad payload.
    throw new ApiError(res.status >= 500 ? 'unreachable' : 'bad_response', res.status >= 500 ? 'The service could not be reached.' : 'The service returned something that is not JSON.', undefined, res.status)
  }
  if (!res.ok) {
    // A gateway in front of the service may rate-limit (429) or shed load (503): say how long to wait, never show a result.
    if (res.status === 429 || res.status === 503) {
      const g = (body as { error?: { code?: string; message?: string; details?: unknown } }).error
      const wait = retryAfter(res)
      const msg = res.status === 429 ? 'The service is receiving too many requests.' : g?.message ?? 'The service is temporarily unavailable.'
      throw new ApiError(res.status === 429 ? 'rate_limited' : g?.code ?? 'unavailable', `${msg}${wait ? ` Try again in ${wait} s.` : ' Try again shortly.'}`, g?.details, res.status)
    }
    const e =(body as { error?: { code?: string; message?: string; details?: unknown } }).error
    throw new ApiError(e?.code ?? 'bad_response', e?.message ?? `Request failed (${res.status}).`, e?.details, res.status)
  }
  return body as T
}

export const getHealth = () => request<Health>('/health', undefined, 4_000)
export const getDatasets = () => request<DatasetsResponse>('/v1/datasets', undefined, 10_000)
export const profile = (req: ProfileRequest) => request<TerrainProfile>('/v1/patches/profile', { method: 'POST', body: JSON.stringify(req) })
export const compare = (req: CompareRequest) => request<ComparisonResult>('/v1/patches/compare', { method: 'POST', body: JSON.stringify(req) })
export const overlay = (req: OverlayRequest) => request<OverlayResponse>('/v1/patches/overlay', { method: 'POST', body: JSON.stringify(req) })
export const screen = (req: ScreenRequest) => request<ScreenResponse>('/v1/discovery/screen', { method: 'POST', body: JSON.stringify(req) }, 180_000)

/** Layers 4 and 5 can take ~25 s on the first call after the service starts (compiling), then a few seconds. */
const LONG = 180_000
export const getRehearsalStatus = () => request<RehearsalStatus>('/v1/rehearsal/status', undefined, 6_000)
export const rehearse = (req: RehearseRequest, signal?: AbortSignal) => request<RehearsalResult>('/v1/rehearsal/evaluate', { method: 'POST', body: JSON.stringify(req), signal }, LONG)
export const getSuitabilityMetrics = () => request<{ metrics: { id: string; source_layer: 'layer3' | 'layer4'; unit: string; description: string; selectors: string[] }[] }>('/v1/suitability/metrics', undefined, 10_000)
export const assess = (req: AssessRequest, signal?: AbortSignal) => request<MissionAssessment>('/v1/suitability/assess', { method: 'POST', body: JSON.stringify(req), signal }, LONG)
