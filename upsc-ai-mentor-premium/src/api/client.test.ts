import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest } from './client'
afterEach(() => vi.restoreAllMocks())
describe('apiRequest', () => {
  it('returns typed JSON from the configured backend', async () => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))); await expect(apiRequest<{status:string}>('/health')).resolves.toEqual({ status: 'ok' }) })
  it('turns network failures into a readable unavailable error', async () => { vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed'))); await expect(apiRequest('/health')).rejects.toMatchObject({ status: 0, message: expect.stringContaining('backend is unavailable') } satisfies Partial<ApiError>) })
  it('maps validation failures without exposing a stack trace', async () => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"bad"}', { status: 422 }))); await expect(apiRequest('/profile')).rejects.toMatchObject({ status: 422, message: expect.stringContaining('invalid') }) })
})
