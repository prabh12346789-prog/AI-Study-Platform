import { apiRequest } from './client'
import type { Conversation, ConversationMessage } from './types'
export const listConversations=(signal?:AbortSignal)=>apiRequest<Conversation[]>('/conversations',{signal})
export const createConversation=()=>apiRequest<Conversation>('/conversations',{method:'POST'})
export const getConversationMessages=(id:string,signal?:AbortSignal)=>apiRequest<ConversationMessage[]>(`/conversations/${encodeURIComponent(id)}/messages`,{signal})
export const renameConversation=(id:string,title:string)=>apiRequest<Conversation>(`/conversations/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})})
export const deleteConversation=(id:string)=>apiRequest<void>(`/conversations/${encodeURIComponent(id)}`,{method:'DELETE'})
