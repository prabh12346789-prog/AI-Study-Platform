import { apiRequest } from './client'
import type { MasteryOverview } from './types'
export const getMasteryOverview = (signal?:AbortSignal) => apiRequest<MasteryOverview>('/mastery/overview',{signal})
