import { apiRequest } from './client'
import type { MentorAction, MentorDashboard } from './types'
export const getMentorDashboard = (signal?:AbortSignal) => apiRequest<MentorDashboard>('/mentor/dashboard',{signal})
export const updateMentorAction = (id:string, operation:'accept'|'complete'|'skip') => apiRequest<MentorAction>(`/mentor/actions/${id}/${operation}`,{method:'POST'})
