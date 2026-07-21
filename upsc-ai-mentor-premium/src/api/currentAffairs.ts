import { apiRequest } from './client'
import type { CurrentAffairsArticle, CurrentAffairsRetention, DailyBrief, PersonalizedCurrentAffairs, RetentionOverview } from './types'
const query=(values:Record<string,string|boolean|undefined>)=>{const value=new URLSearchParams();Object.entries(values).forEach(([key,item])=>item!==undefined&&value.set(key,String(item)));return value.size?`?${value}`:''}
export const getPersonalizedCurrentAffairs = (signal?:AbortSignal,date?:string) => apiRequest<PersonalizedCurrentAffairs>(`/current-affairs/personalized${query({date})}`,{signal})
export const getCurrentAffairsArticles = (filters:Record<string,string|boolean|undefined>={},signal?:AbortSignal) => apiRequest<CurrentAffairsArticle[]>(`/current-affairs/articles${query(filters)}`,{signal})
export const getDailyBrief = (date:string,language:string,signal?:AbortSignal)=>apiRequest<DailyBrief>(`/current-affairs/daily${query({date,language})}`,{signal})
export const getSavedCurrentAffairs = (signal?:AbortSignal)=>apiRequest<CurrentAffairsArticle[]>('/current-affairs/saved',{signal})
export const setCurrentAffairsSaved = (id:string,saved:boolean) => apiRequest<void>(`/current-affairs/articles/${id}/save`,{method:saved?'DELETE':'POST'})
export const getCurrentAffairsRetention = (signal?:AbortSignal) => apiRequest<RetentionOverview>('/current-affairs/retention/overview',{signal})
export const getCurrentAffairsRetentionItems=(signal?:AbortSignal)=>apiRequest<CurrentAffairsRetention[]>('/current-affairs/retention',{signal})
export const markCurrentAffairsRevised=(articleId:string)=>apiRequest<CurrentAffairsRetention>(`/current-affairs/retention/${articleId}/revise`,{method:'POST'})
