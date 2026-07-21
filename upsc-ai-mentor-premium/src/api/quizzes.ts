import { apiRequest } from './client'
import type { CurrentAffairsQuiz, QuizAttempt } from './types'
export type QuizCreate={period_type:'daily'|'weekly'|'custom';date_from?:string;date_to?:string;question_count?:number;difficulty:'easy'|'standard'|'difficult'}
export const getQuizzes=(signal?:AbortSignal)=>apiRequest<CurrentAffairsQuiz[]>('/current-affairs/quizzes',{signal})
export const createQuiz=(payload:QuizCreate)=>apiRequest<CurrentAffairsQuiz>('/current-affairs/quizzes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
export const getQuiz=(id:string,signal?:AbortSignal)=>apiRequest<CurrentAffairsQuiz>(`/current-affairs/quizzes/${id}`,{signal})
export const getQuizAttempts=(id:string,signal?:AbortSignal)=>apiRequest<QuizAttempt[]>(`/current-affairs/quizzes/${id}/attempts`,{signal})
export const submitQuiz=(id:string,answers:Array<{question_id:string;answer:string}>)=>apiRequest<QuizAttempt>(`/current-affairs/quizzes/${id}/submit`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers})})
