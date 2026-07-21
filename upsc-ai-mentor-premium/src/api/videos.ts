import { apiRequest } from './client'
import type { VideoRecommendation } from './types'
export const getVideoRecommendations = (signal?:AbortSignal) => apiRequest<VideoRecommendation[]>('/videos/recommendations',{signal})
