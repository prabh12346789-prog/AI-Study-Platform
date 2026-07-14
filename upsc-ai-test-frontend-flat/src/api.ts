export type StudyMode = 'learn' | 'revision' | 'prelims' | 'mains' | 'interview'

export interface ChatRequest {
  question: string
  mode: StudyMode
  conversation_id?: string
  language?: 'auto' | 'english' | 'hindi' | 'punjabi'
  depth?: 'quick' | 'standard' | 'detailed'
  format?: 'bullets' | 'structured' | 'explanation' | 'mixed'
}

export interface ChatResponse {
  status: string
  answer: string
  provider: string
  sources: Array<Record<string, unknown>>
  conversation_id: string
  subject?: string
  topic?: string
  effective_language?: string
  effective_depth?: string
  effective_format?: string
}

export interface ActivityEventInput {
  event_type: 'study_time_logged'
  conversation_id?: string
  subject?: string
  topic?: string
  duration_seconds: number
  metadata?: Record<string, unknown>
}

export interface ActivityBreakdown { name: string; study_seconds: number; event_count: number }
export interface ActivityEvent { id: string; event_type: string; subject: string | null; topic: string | null; occurred_at: string }
export interface ActivitySummary {
  total_study_seconds: number; questions_asked: number; answers_generated: number; pdfs_uploaded: number
  subjects_studied: number; top_subject: string | null; top_topic: string | null
  subject_breakdown: ActivityBreakdown[]; topic_breakdown: ActivityBreakdown[]; recent_events: ActivityEvent[]
}

export interface LearnerProfile {
  id: string; user_id: string
  preferred_language: 'auto' | 'english' | 'hindi' | 'punjabi'
  preferred_depth: 'quick' | 'standard' | 'detailed'
  preferred_format: 'bullets' | 'structured' | 'explanation' | 'mixed'
  daily_study_target_minutes: number
  preferred_content_type: 'text' | 'quiz' | 'video' | 'mixed'
  onboarding_completed: boolean
}
export type ProfileInput = Omit<LearnerProfile, 'id' | 'user_id' | 'onboarding_completed'>
export interface ProfileInsights {
  most_studied_subject: string | null; most_studied_topic: string | null
  total_study_seconds_7d: number; questions_asked_7d: number; active_days_7d: number
  average_daily_study_seconds: number; preferred_mode_observed: string | null
}

export interface TopicMastery {
  id: string; subject: string; topic: string; mastery_score: number; forgetting_risk: number
  risk_level: 'low' | 'medium' | 'high'; last_revised_at: string | null; next_revision_at: string | null
  explanation: string[]; updated_at: string
}
export interface MasteryOverview {
  average_mastery: number; strong_topics: TopicMastery[]; weak_topics: TopicMastery[]
  high_risk_topics: TopicMastery[]; due_for_revision: TopicMastery[]
  subject_breakdown: Array<{ subject: string; mastery_score: number }>; recent_changes: TopicMastery[]
}
export interface MentorAction {
  id: string; subject: string; topic: string; action_type: string; title: string; reason: string[]
  priority_score: number; priority_level: 'low' | 'medium' | 'high' | 'urgent'
  estimated_minutes: number; status: string; source_mastery_id: string
}
export interface NextMentorAction { action: MentorAction | null; alternatives: MentorAction[] }
export interface MentorDashboardData {
  today: { study_seconds: number; questions_asked: number; subjects_studied: number; top_subject: string | null; top_topic: string | null; subject_breakdown: ActivityBreakdown[] }
  mentor_brief: { summary: string; strengths: TopicMastery[]; weaknesses: TopicMastery[]; likely_to_forget: TopicMastery[]; next_best_action: MentorAction | null }
  mastery: { average_mastery: number; strong_topics: TopicMastery[]; weak_topics: TopicMastery[]; high_risk_topics: TopicMastery[]; subject_breakdown: Array<{ subject: string; mastery_score: number }> }
  recommendations: { primary: MentorAction | null; alternatives: MentorAction[] }
  recommended_videos: VideoRecommendation[]
  profile: { preferred_language: string; preferred_depth: string; preferred_format: string; daily_target_minutes: number }
  recent_activity: ActivityEvent[]
}

export interface VideoResource {
  id: string; title: string; description: string; subject: string; topic: string
  language: 'english' | 'hindi' | 'punjabi'; source_name: string; source_url: string
  thumbnail_url: string; duration_seconds: number; difficulty: 'beginner' | 'standard' | 'advanced'
  verified: boolean; active: boolean
}
export interface VideoRecommendation { video: VideoResource; reasons: string[] }

export interface Conversation { id: string; title: string; created_at: string; updated_at: string }
export interface ConversationMessage { id: number; conversation_id: string; role: 'user' | 'assistant'; content: string; timestamp: string }
export interface CommunityGroup { id: string; name: string; slug: string; description: string; subject: string }
export interface CommunityPost { id: string; user_id: string; group_id: string; group_name: string; subject: string; title: string; content: string; language: string; source_url: string | null; display_name: string; comment_count: number; saved: boolean; created_at: string }
export interface CommunityComment { id: string; user_id: string; post_id: string; content: string; created_at: string }

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

function extractToken(data: string): string {
  try {
    const parsed = JSON.parse(data) as Record<string, unknown>
    const value = parsed.token ?? parsed.text ?? parsed.response ?? parsed.content
    return typeof value === 'string' ? value : ''
  } catch {
    return data
  }
}

export async function checkBackend(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/`, { signal })
    return response.ok
  } catch {
    return false
  }
}

export async function sendChat(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Chat request failed (${response.status}): ${detail}`)
  }

  return (await response.json()) as ChatResponse
}

export async function streamChat(
  request: ChatRequest,
  onToken: (token: string) => void,
  onConversation: (conversationId: string, subject?: string, topic?: string, effectiveLanguage?: string, effectiveDepth?: string, effectiveFormat?: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Streaming request failed (${response.status}): ${detail}`)
  }

  if (!response.body) {
    throw new Error('This browser did not provide a readable response stream.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = 'message'
  let finished = false

  while (!finished) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })

    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop() ?? ''

    for (const rawLine of lines) {
      if (rawLine.startsWith('event:')) {
        eventName = rawLine.slice(6).trim()
        continue
      }

      if (rawLine.startsWith('data:')) {
        let data = rawLine.slice(5)
        if (data.startsWith(' ')) data = data.slice(1)

        const marker = data.trim()
        if (eventName === 'conversation') {
          const payload = JSON.parse(data) as { conversation_id: string; subject?: string; topic?: string; effective_language?: string; effective_depth?: string; effective_format?: string }
          onConversation(payload.conversation_id, payload.subject, payload.topic, payload.effective_language, payload.effective_depth, payload.effective_format)
          continue
        }
        if (eventName === 'done' || marker === 'END' || marker === '[DONE]') {
          finished = true
          break
        }

        const token = extractToken(data)
        if (token) onToken(token)
        continue
      }

      if (rawLine === '') {
        eventName = 'message'
      }
    }

    if (done) break
  }

  if (!finished && buffer.startsWith('data:')) {
    const data = buffer.slice(5).replace(/^ /, '')
    const marker = data.trim()
    if (marker !== 'END' && marker !== '[DONE]') {
      const token = extractToken(data)
      if (token) onToken(token)
    }
  }
}

async function conversationRequest<T>(path = '', init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/conversations${path}`, init)
  if (!response.ok) throw new Error(`Conversation request failed (${response.status}): ${await response.text()}`)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const createConversation = () => conversationRequest<Conversation>('', { method: 'POST' })
export const listConversations = () => conversationRequest<Conversation[]>()
export const loadConversationMessages = (id: string) => conversationRequest<ConversationMessage[]>(`/${id}/messages`)
export const renameConversation = (id: string, title: string) => conversationRequest<Conversation>(`/${id}`, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }),
})
export const deleteConversation = (id: string) => conversationRequest<void>(`/${id}`, { method: 'DELETE' })

export async function recordActivityEvent(event: ActivityEventInput, keepalive = false): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/activity/events`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event), keepalive,
  })
  if (!response.ok) throw new Error(`Activity logging failed (${response.status}): ${await response.text()}`)
}

export async function getActivitySummary(period: 'today' | '7d' = 'today'): Promise<ActivitySummary> {
  const response = await fetch(`${API_BASE_URL}/activity/summary?period=${period}`)
  if (!response.ok) throw new Error(`Activity summary failed (${response.status}): ${await response.text()}`)
  return response.json()
}

async function profileRequest<T>(path = '', init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/profile${path}`, init)
  if (!response.ok) throw new Error(`Profile request failed (${response.status}): ${await response.text()}`)
  return response.status === 204 ? (undefined as T) : response.json()
}
export const getProfile = () => profileRequest<LearnerProfile>()
export const getProfileInsights = () => profileRequest<ProfileInsights>('/insights')
export const saveProfile = (profile: ProfileInput, onboarding = false) => profileRequest<LearnerProfile>(
  onboarding ? '/onboarding' : '', {
    method: onboarding ? 'POST' : 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  },
)
export const resetProfile = () => profileRequest<void>('', { method: 'DELETE' })

export async function getMasteryOverview(): Promise<MasteryOverview> {
  const response = await fetch(`${API_BASE_URL}/mastery/overview`)
  if (!response.ok) throw new Error(`Mastery request failed (${response.status}): ${await response.text()}`)
  return response.json()
}
export async function listMasteryTopics(): Promise<TopicMastery[]> {
  const response = await fetch(`${API_BASE_URL}/mastery/topics`)
  if (!response.ok) throw new Error(`Mastery request failed (${response.status}): ${await response.text()}`)
  return response.json()
}
export async function deleteMasteryTopic(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/mastery/topics/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(`Mastery reset failed (${response.status}): ${await response.text()}`)
}
export async function getNextMentorAction(): Promise<NextMentorAction> {
  const response = await fetch(`${API_BASE_URL}/mentor/actions/next`)
  if (!response.ok) throw new Error(`Mentor plan failed (${response.status}): ${await response.text()}`)
  return response.json()
}
export async function regenerateMentorActions(): Promise<MentorAction[]> {
  const response = await fetch(`${API_BASE_URL}/mentor/actions/generate`, { method: 'POST' })
  if (!response.ok) throw new Error(`Mentor plan failed (${response.status}): ${await response.text()}`)
  return response.json()
}
export async function updateMentorAction(id: string, operation: 'accept' | 'complete' | 'skip'): Promise<MentorAction> {
  const response = await fetch(`${API_BASE_URL}/mentor/actions/${id}/${operation}`, { method: 'POST' })
  if (!response.ok) throw new Error(`Mentor action failed (${response.status}): ${await response.text()}`)
  return response.json()
}
export async function getMentorDashboard(): Promise<MentorDashboardData> {
  const response = await fetch(`${API_BASE_URL}/mentor/dashboard`)
  if (!response.ok) throw new Error(`Dashboard failed (${response.status}): ${await response.text()}`)
  return response.json()
}

export async function getVideoRecommendations(filters: { subject?: string | null; topic?: string | null; language?: string; maxDurationSeconds?: number; explicitRequest?: boolean } = {}): Promise<VideoRecommendation[]> {
  const params = new URLSearchParams()
  if (filters.subject) params.set('subject', filters.subject)
  if (filters.topic) params.set('topic', filters.topic)
  if (filters.language) params.set('language', filters.language)
  if (filters.maxDurationSeconds) params.set('max_duration_seconds', String(filters.maxDurationSeconds))
  if (filters.explicitRequest) params.set('explicit_request', 'true')
  const response = await fetch(`${API_BASE_URL}/videos/recommendations?${params}`)
  if (!response.ok) throw new Error(`Video recommendations failed (${response.status}): ${await response.text()}`)
  return response.json()
}
export async function openVideo(id: string): Promise<VideoResource> {
  const response = await fetch(`${API_BASE_URL}/videos/${id}/open`, { method: 'POST' })
  if (!response.ok) throw new Error(`Video link unavailable (${response.status})`)
  return response.json()
}
export async function dismissVideo(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/videos/${id}/dismiss`, { method: 'POST' })
  if (!response.ok) throw new Error(`Unable to dismiss video (${response.status})`)
}

export async function uploadPdf(file: File, signal?: AbortSignal): Promise<unknown> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/pdf/upload`, {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`PDF upload failed (${response.status}): ${detail}`)
  }

  const contentType = response.headers.get('content-type') ?? ''
  return contentType.includes('application/json') ? response.json() : response.text()
}

async function communityRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/community${path}`, init)
  if (!response.ok) throw new Error(`Community request failed (${response.status}): ${await response.text()}`)
  return response.status === 204 ? undefined as T : response.json()
}
export const getCommunityGroups = () => communityRequest<CommunityGroup[]>('/groups')
export const getCommunityPosts = (params = '') => communityRequest<CommunityPost[]>(`/posts${params ? `?${params}` : ''}`)
export const getCommunityPost = (id: string) => communityRequest<CommunityPost>(`/posts/${id}`)
export const createCommunityPost = (data: { group_id: string; title: string; content: string; language: string; source_url?: string }) => communityRequest<CommunityPost>('/posts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
export const updateCommunityPost = (id: string, data: Partial<{ title: string; content: string; language: string; source_url: string | null }>) => communityRequest<CommunityPost>(`/posts/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
export const deleteCommunityPost = (id: string) => communityRequest<void>(`/posts/${id}`, { method: 'DELETE' })
export const getCommunityComments = (id: string) => communityRequest<CommunityComment[]>(`/posts/${id}/comments`)
export const createCommunityComment = (id: string, content: string) => communityRequest<CommunityComment>(`/posts/${id}/comments`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) })
export const deleteCommunityComment = (id: string) => communityRequest<void>(`/comments/${id}`, { method: 'DELETE' })
export const saveCommunityPost = (id: string, saved: boolean) => communityRequest<void>(`/posts/${id}/save`, { method: saved ? 'DELETE' : 'POST' })
export const reportCommunityPost = (id: string, reason: string, details?: string) => communityRequest<void>('/reports', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target_type: 'post', target_id: id, reason, details }) })

export { API_BASE_URL }
