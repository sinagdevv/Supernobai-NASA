import type { CompareRequest, ComparisonResult, DatasetsResponse, Health, OverlayRequest, OverlayResponse, ScreenRequest, ScreenResponse } from './types'

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

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, signal: ctl.signal, headers: { 'content-type': 'application/json', ...init?.headers } })
  } catch (e) {
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
    const e = (body as { error?: { code?: string; message?: string; details?: unknown } }).error
    throw new ApiError(e?.code ?? 'bad_response', e?.message ?? `Request failed (${res.status}).`, e?.details, res.status)
  }
  return body as T
}

export const getHealth = () => request<Health>('/health', undefined, 4_000)
export const getDatasets = () => request<DatasetsResponse>('/v1/datasets', undefined, 10_000)
export const compare = (req: CompareRequest) => request<ComparisonResult>('/v1/patches/compare', { method: 'POST', body: JSON.stringify(req) })
export const overlay = (req: OverlayRequest) => request<OverlayResponse>('/v1/patches/overlay', { method: 'POST', body: JSON.stringify(req) })
export const screen = (req: ScreenRequest) => request<ScreenResponse>('/v1/discovery/screen', { method: 'POST', body: JSON.stringify(req) }, 180_000)
