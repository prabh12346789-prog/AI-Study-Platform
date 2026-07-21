import { apiRequest } from './client'
import type { Roadmap } from './types'
export const getRoadmaps = (signal?:AbortSignal) => apiRequest<Roadmap[]>('/visual-roadmaps',{signal})
