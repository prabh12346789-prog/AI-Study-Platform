import { apiRequest } from './client'
export interface LearnerProfile { id:string; user_id:string; preferred_language:string; preferred_depth:string; preferred_format:string; daily_study_target_minutes:number; preferred_content_type:string; onboarding_completed:boolean }
export const getProfile = (signal?:AbortSignal) => apiRequest<LearnerProfile>('/profile',{signal})
