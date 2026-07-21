import { apiRequest } from './client'
import type { HealthResponse } from './types'
export const getHealth = (signal?: AbortSignal) => apiRequest<HealthResponse>('/health', { signal })
