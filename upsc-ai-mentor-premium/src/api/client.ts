import { environment } from '../lib/env'
const baseUrl = environment.apiBaseUrl
export class ApiError extends Error { constructor(public status: number, message: string, public detail?: string) { super(message); this.name = 'ApiError' } }
const messages: Record<number, string> = { 404: 'The requested resource was not found.', 422: 'Some information was invalid. Please review your entries.', 500: 'The service encountered an error. Please try again.' }
function fastApiDetail(raw: string): string | undefined {
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown }
    if (typeof parsed.detail === 'string') return parsed.detail
    if (Array.isArray(parsed.detail)) return parsed.detail.map(item => typeof item === 'object' && item && 'msg' in item ? String(item.msg) : '').filter(Boolean).join(' ')
  } catch { return undefined }
}
export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`${baseUrl}${path}`, { ...init, headers: { Accept: 'application/json', ...init?.headers } }) }
  catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError(0, 'The request was cancelled.'); throw new ApiError(0, 'The backend is unavailable. Check that the local server is running.') }
  if (!response.ok) { const raw = await response.text(); throw new ApiError(response.status, messages[response.status] ?? `Request failed (${response.status}).`, fastApiDetail(raw)) }
  if (response.status === 204 || response.headers.get('content-length') === '0') return undefined as T
  const raw = await response.text()
  if (!raw) return undefined as T
  try { return JSON.parse(raw) as T } catch { throw new ApiError(response.status, 'The service returned an unreadable response.') }
}
export { baseUrl as API_BASE_URL }
