import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, compare, getHealth, overlay, screen } from './client'
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
