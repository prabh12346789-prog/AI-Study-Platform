import { describe, expect, it } from 'vitest'
import { validateEnvironment } from './env'
describe('environment configuration', () => {
  it('accepts and normalizes the API URL', () => expect(validateEnvironment({ VITE_API_BASE_URL: 'http://127.0.0.1:8000/' }).apiBaseUrl).toBe('http://127.0.0.1:8000'))
  it('reports a readable missing URL', () => expect(() => validateEnvironment({})).toThrow(/VITE_API_BASE_URL is missing/))
  it('rejects non-http URLs', () => expect(() => validateEnvironment({ VITE_API_BASE_URL: 'file:///secret' })).toThrow(/http or https/))
})
