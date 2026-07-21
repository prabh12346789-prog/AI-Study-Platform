import { apiRequest } from './client'
import type { ActivityEvent, ActivitySummary } from './types'
export const getActivitySummary = (period:'today'|'7d',signal?:AbortSignal) => apiRequest<ActivitySummary>(`/activity/summary?period=${period}`,{signal})
export const getRecentActivity = (signal?:AbortSignal) => apiRequest<ActivityEvent[]>('/activity/events?limit=100',{signal})
