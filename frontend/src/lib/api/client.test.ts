import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, assess, compare, getHealth, getRehearsalStatus, getSuitabilityMetrics, overlay, rehearse, screen } from './client'
import { explain } from './explain'

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const stub = (fn: () => Promise<Response>) => vi.stubGlobal('fetch', vi.fn(fn))
const failure = async (p: Promise<unknown>) => p.then(() => { throw new Error('expected a rejection') }, (e: unknown) => e as ApiError)

afterEach(() => vi.unstubAllGlobals())

describe('the service client', () => {
  it('returns the parsed body on success', async () => {
    stub(async () => json(200, { status: 'ok', service: 'terrawindow-geo', version: '0.1.0' }))
    expect((await getHealth()).version).toBe('0.1.0')
  })

  it('reports a service that is not running as "unreachable"', async () => {
    stub(async () => { throw new TypeError('Failed to fetch') })
    expect(await failure(getHealth())).toMatchObject({ code: 'unreachable' })
  })

  it('treats an HTML 5xx from a dev proxy with nothing behind it as "unreachable", not a bad payload', async () => {
    stub(async () => new Response('<html>Bad gateway</html>', { status: 502 }))
    expect(await failure(getHealth())).toMatchObject({ code: 'unreachable', status: 502 })
  })

  it('keeps the service error code, message and details', async () => {
    const details = { dataset_id: 'lola-5mpp-site01', availability: 'missing', setup: 'terrawindow-data fetch lola-5mpp-site01' }
    stub(async () => json(404, { error: { code: 'source_unavailable', message: 'gone', details } }))
    const e = await failure(compare({ reference: { dataset: { id: 'a' } }, candidate: { dataset: { id: 'b' } } }))
    expect(e).toBeInstanceOf(ApiError)
    expect(e).toMatchObject({ code: 'source_unavailable', message: 'gone', status: 404, details })
  })

  it('does not accept a non-JSON success as data', async () => {
    stub(async () => new Response('ok', { status: 200 }))
    expect(await failure(getHealth())).toMatchObject({ code: 'bad_response' })
  })

  it('sends the screening and overlay requests as the contract defines them', async () => {
    const f = vi.fn(async () => json(200, {}))
    vi.stubGlobal('fetch', f)
    await screen({ dataset: { id: 'x' }, patch_size_m: 1500, criteria: { slope_mean_deg: { max: 8 } } })
    await overlay({ dataset: { id: 'x' }, layer: 'slope' })
    const calls = f.mock.calls as unknown as [string, RequestInit][]
    expect(calls[0][0]).toMatch(/\/v1\/discovery\/screen$/)
    expect(JSON.parse(calls[0][1].body as string)).toEqual({ dataset: { id: 'x' }, patch_size_m: 1500, criteria: { slope_mean_deg: { max: 8 } } })
    expect(calls[1][0]).toMatch(/\/v1\/patches\/overlay$/)
    expect(calls[1][1].method).toBe('POST')
  })
})

describe('explain', () => {
  it('passes the service-suggested fix through', () => {
    const e = new ApiError('source_unavailable', 'x', { setup: 'terrawindow-data fetch a' })
    expect(explain(e)).toEqual({ text: expect.stringContaining('not on this machine'), setup: 'terrawindow-data fetch a' })
  })

  it('has distinct wording for unreadable and unvalidated data, and none claims success', () => {
    expect(explain(new ApiError('source_unreadable', 'x')).text).toMatch(/cannot be read/)
    expect(explain(new ApiError('dataset_not_validated', 'x')).text).toMatch(/failing validation/)
  })

  it('falls back to the service message for codes it does not know', () => {
    expect(explain(new ApiError('something_new', 'Specific message.'))).toEqual({ text: 'Specific message.', setup: undefined })
  })
})

describe('Layer 4 and Layer 5 calls', () => {
  const sent = (f: ReturnType<typeof vi.fn>, i = 0) => {
    const [url, init] = f.mock.calls[i] as unknown as [string, RequestInit]
    return { url, init, body: init.body ? JSON.parse(init.body as string) : undefined }
  }

  it('POSTs the rehearsal request as the contract defines it and returns the raw result', async () => {
    const f = vi.fn(async () => json(200, { body: 'moon', observations: [] }))
    vi.stubGlobal('fetch', f)
    const req = { candidate: { dataset: { id: 'lola-5mpp-site01' }, scales_m: [40] }, start_utc: '2026-12-14T00:00:00Z', end_utc: '2026-12-15T00:00:00Z', step_minutes: 120, scale_m: 40 }
    expect(await rehearse(req)).toEqual({ body: 'moon', observations: [] })
    const s = sent(f)
    expect(s.url).toMatch(/\/v1\/rehearsal\/evaluate$/)
    expect(s.init.method).toBe('POST')
    expect(s.body).toEqual(req)
  })

  it('reads status and the metric catalogue with GET', async () => {
    const f = vi.fn(async () => json(200, { bodies: { earth: true, moon: true, mars: true }, metrics: [] }))
    vi.stubGlobal('fetch', f)
    await getRehearsalStatus()
    await getSuitabilityMetrics()
    expect(sent(f, 0).url).toMatch(/\/v1\/rehearsal\/status$/)
    expect(sent(f, 1).url).toMatch(/\/v1\/suitability\/metrics$/)
    expect(sent(f, 0).init.method).toBeUndefined()
  })

  it('POSTs an assessment with the Layer 4 result attached unchanged', async () => {
    const f = vi.fn(async () => json(200, { overall_status: 'INDETERMINATE' }))
    vi.stubGlobal('fetch', f)
    const l4 = { body: 'moon', generated_at: 'x' }
    await assess({ candidate_id: 'moon', candidate: { dataset: { id: 'a' } }, mission_profile: { id: 'p', name: 'p', description: 'd', required_categories: [], criteria: [] }, layer4_result: l4 as never })
    expect(sent(f).url).toMatch(/\/v1\/suitability\/assess$/)
    expect(sent(f).body.layer4_result).toEqual(l4)
  })

  it('keeps the engine error codes for rejected and unavailable requests', async () => {
    stub(async () => json(422, { error: { code: 'rehearsal_rejected', message: 'Earth kernel ends 2027-02-08', details: {} } }))
    const e = await failure(rehearse({ candidate: { dataset: { id: 'x' } }, start_utc: 'a', end_utc: 'b', step_minutes: 60 }))
    expect(e).toMatchObject({ code: 'rehearsal_rejected', status: 422 })
    expect(explain(e).text).toMatch(/rejected/)
    stub(async () => json(404, { error: { code: 'layer4_unavailable', message: 'x' } }))
    expect(explain(await failure(rehearse({ candidate: { dataset: { id: 'x' } }, start_utc: 'a', end_utc: 'b', step_minutes: 60 }))).text).toMatch(/not available/)
  })

  it('turns a gateway 429 into a rate-limit message that honours Retry-After', async () => {
    stub(async () => new Response(JSON.stringify({ error: { code: 'whatever', message: 'slow down' } }), { status: 429, headers: { 'content-type': 'application/json', 'retry-after': '12' } }))
    const e = await failure(assess({ candidate_id: 'a', candidate: { dataset: { id: 'x' } }, mission_profile: { id: 'p', name: 'p', description: 'd', required_categories: [], criteria: [] } }))
    expect(e).toMatchObject({ code: 'rate_limited', status: 429 })
    expect(e.message).toMatch(/Try again in 12 s/)
  })

  it('treats a gateway 503 as unavailable with a try-again hint, and an HTML 503 as unreachable', async () => {
    stub(async () => new Response(JSON.stringify({ error: { code: 'unavailable', message: 'Busy.' } }), { status: 503, headers: { 'content-type': 'application/json', 'retry-after': '3' } }))
    expect(await failure(rehearse({ candidate: { dataset: { id: 'x' } }, start_utc: 'a', end_utc: 'b', step_minutes: 60 }))).toMatchObject({ code: 'unavailable', message: 'Busy. Try again in 3 s.' })
    stub(async () => new Response('<html>503</html>', { status: 503 }))
    expect(await failure(rehearse({ candidate: { dataset: { id: 'x' } }, start_utc: 'a', end_utc: 'b', step_minutes: 60 }))).toMatchObject({ code: 'unreachable' })
  })

  it('a superseded request is reported as "aborted", not as an unreachable service', async () => {
    vi.stubGlobal('fetch', vi.fn((_u: string, init: RequestInit) => new Promise<Response>((_res, rej) => init.signal!.addEventListener('abort', () => rej(new DOMException('x', 'AbortError'))))))
    const ctl = new AbortController()
    const p = failure(assess({ candidate_id: 'a', candidate: { dataset: { id: 'x' } }, mission_profile: { id: 'p', name: 'p', description: 'd', required_categories: [], criteria: [] } }, ctl.signal))
    ctl.abort()
    expect(await p).toMatchObject({ code: 'aborted' })
  })
})
