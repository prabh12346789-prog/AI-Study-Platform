import { createCachedOptionalLoader } from './cachedOptionalLoader'

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
  event_type: 'study_time_logged' | 'internal_search'
  conversation_id?: string
  subject?: string
  topic?: string
  duration_seconds: number
  metadata?: Record<string, unknown>
}

export interface ActivityBreakdown { name: string; study_seconds: number; event_count: number }
export interface ActivityEvent { id: string; event_type: string; subject: string | null; topic: string | null; occurred_at: string; duration_seconds?: number | null; metadata?: Record<string, unknown> | null }
export interface ActivitySummary {
  total_study_seconds: number; questions_asked: number; answers_generated: number; pdfs_uploaded: number
  searches_made?: number; top_searches?: string[]
  first_activity_at?: string | null; total_learning_days?: number
  subjects_studied: number; top_subject: string | null; top_topic: string | null
  subject_breakdown: ActivityBreakdown[]; topic_breakdown: ActivityBreakdown[]; recent_events: ActivityEvent[]
  daily_breakdown?: Array<{ date: string; study_seconds: number; event_count: number }>
  monthly_breakdown?: Array<{ month: string; study_seconds: number; event_count: number; searches_made: number; questions_asked: number }>
  demo_mode?: boolean
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
  demo_mode?: boolean
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
export interface PdfDocument {
  document_id: string; name: string; uploaded_at: string; status: string
  page_count: number | null; chunk_count: number | null
  embedding_provider: string | null; embedding_model: string | null; embedding_collection: string | null
  indexed: boolean
}
export type VisualType = 'timeline' | 'flowchart' | 'concept_map' | 'comparison' | 'process' | 'cause_effect'
export interface RoadmapSource { id: string; source_type: 'pdf' | 'web' | 'general'; document: string | null; title: string | null; url: string | null; publisher: string | null; domain: string | null; retrieved_at: string | null; source_category: string | null; trust_level: string | null; page_start: number | null; page_end: number | null; chunk_id: string | null }
export interface VisualRoadmap { id: string; status: string; title: string; subject: string; topic: string; visual_type: VisualType; language: string; conversation_id: string | null; svg_url: string; created_at: string; updated_at: string; sources: RoadmapSource[]; structure: { title: string; summary: string; visual_type: VisualType; nodes: Array<{ id: string; label: string; description: string; source_ids: string[] }>; connections: Array<{ from: string; to: string; label: string }>; exam_points: string[]; sources: RoadmapSource[] } }
export interface RoadmapQuizQuestion { id: string; roadmap_id: string; question_type: 'mcq' | 'sequence' | 'match_year' | 'true_false' | 'short_recall'; question: string; options: string[]; correct_answer: string; explanation: string; source_node_ids: string[]; difficulty: 'easy' | 'standard' | 'difficult' }
export interface RoadmapQuiz { id: string; roadmap_id: string; difficulty: string; questions: RoadmapQuizQuestion[] }
export interface RoadmapQuizResult { score: number; total: number; percentage: number; correct_answers: QuizAnswerResult[]; incorrect_answers: QuizAnswerResult[]; explanations: string[]; weak_source_nodes: string[] }
export interface QuizAnswerResult { question_id: string; correct: boolean; submitted_answer: string; correct_answer: string; explanation: string; source_node_ids: string[] }
export interface ContentBlock {
  type: 'heading' | 'subheading' | 'paragraph' | 'bullet' | 'bullet_list' | 'numbered_list' | 'important_fact' | 'table' | 'key_fact' | 'prelims_point' | 'mains_point'
  title?: string
  text?: string
  items?: string[]
  headers?: string[]
  rows?: string[][]
  page_ref?: number
}

export interface CurrentAffairsArticle {
  id: string; title: string; summary: string; source_title: string; publisher: string; source_url: string; source_type: string
  publication_date: string | null; retrieved_at: string; subject: string; topic: string; syllabus_tags_json: string[]
  importance_level: 'low' | 'medium' | 'high'; relevance_prelims: string; relevance_mains: string; status: string; is_demo: boolean
  saved: boolean; opened: boolean
  slug?: string | null; cadence?: 'daily' | 'weekly' | 'monthly' | 'special' | null
  content_type?: 'article' | 'compilation' | 'editorial' | 'prelims_qa' | 'mains_qa' | null
  week_label?: string | null; month?: number | null; year?: number | null
  pdf_url?: string | null; pdf_availability?: string | null; extraction_status?: string | null
  content_blocks_json?: ContentBlock[] | null
  qa_pairs_json?: Array<{ question: string; options?: string[]; answer?: string; explanation?: string; page_ref?: number; marks?: number; word_limit?: number }> | null
}
export interface CurrentAffairsBrief { id: string; brief_date: string; language: string; title: string; overview: string; article_ids_json: string[]; subject_breakdown_json: Record<string, string[]>; prelims_points_json: string[]; mains_points_json: string[]; updated_at: string }
export interface CurrentAffairsSummary { unread_important_stories: number; top_subject: string | null; saved_articles: number; daily_brief_completed: boolean; today_quiz_completed: boolean; latest_quiz_score: number | null; high_risk_article_count: number; next_revision: string | null; demo_mode?: boolean }
export interface CurrentAffairsQuizQuestion { id: string; question_type: string; question: string; options_json: string[]; article_id: string; source_url: string; subject: string; topic: string; difficulty: string }
export interface CurrentAffairsQuiz { id: string; title: string; period_type: string; date_from: string; date_to: string; question_count: number; difficulty: string; status: string; article_ids_json: string[]; questions: CurrentAffairsQuizQuestion[] }
export interface CurrentAffairsQuizResult { id: string; score: number; total: number; percentage: number; results: Array<{ question_id: string; correct: boolean; submitted_answer: string; correct_answer: string; explanation: string; article_id: string; source_url: string; topic: string }>; weak_article_ids: string[]; weak_topics: string[] }
export interface CurrentAffairsRetention { id: string; article_id: string; subject: string; topic: string; retention_score: number; correct_attempts: number; incorrect_attempts: number; recall_failures: number; last_attempt_at: string | null; last_revised_at: string | null; next_revision_at: string | null; risk_level: string }
export interface CurrentAffairsRetentionOverview { average_retention: number; high_risk_articles: CurrentAffairsRetention[]; due_for_revision: CurrentAffairsRetention[]; weak_subjects: Array<{ subject: string; score: number }>; weekly_trend: Array<{ date: string; percentage: number }>; saved_but_unrevised_article_ids: string[] }
export interface PersonalizedIssue { issue_id: string; title: string; summary: string; subject: string; topic: string; importance_level: 'low' | 'medium' | 'high'; publication_date: string | null; prelims: string; mains: string; saved: boolean; score: number; reasons: string[]; source_tier: string; sources: Array<{ article_id: string; publisher: string; url: string; tier: string }> }
export interface PersonalizedCurrentAffairs { effective_language: string; effective_depth: string; effective_format: string; exam_mode: string; daily_target_minutes: number; issues: PersonalizedIssue[]; top_stories: PersonalizedIssue[]; prelims_facts: PersonalizedIssue[]; mains_analysis: PersonalizedIssue[]; editorials: PersonalizedIssue[]; monthly_revision: PersonalizedIssue[]; saved_stories: PersonalizedIssue[]; revision_due: number; recommended_videos: Array<{ publisher: string; url: string; reason: string }> }

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
  onSources?: (sources: Array<Record<string, unknown>>) => void,
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
  let finished = false

  const processEvent = (block: string) => {
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    if (!dataLines.length) return
    const data = dataLines.join('\n')
    const marker = data.trim()
    if (eventName === 'conversation') {
      const payload = JSON.parse(data) as { conversation_id: string; subject?: string; topic?: string; effective_language?: string; effective_depth?: string; effective_format?: string }
      onConversation(payload.conversation_id, payload.subject, payload.topic, payload.effective_language, payload.effective_depth, payload.effective_format)
    } else if (eventName === 'sources') {
      const payload = JSON.parse(data) as { sources?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>
      onSources?.(Array.isArray(payload) ? payload : payload.sources ?? [])
    } else if (eventName === 'done' || marker === 'END' || marker === '[DONE]') {
      finished = true
    } else if (eventName === 'error') {
      const payload = JSON.parse(data) as { detail?: string }
      throw new Error(payload.detail || 'Streaming request failed.')
    } else {
      const token = extractToken(data)
      if (token) onToken(token)
    }
  }

  while (!finished) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const events = buffer.split(/\r?\n\r?\n/)
    buffer = events.pop() ?? ''
    for (const block of events) processEvent(block)
    if (done) break
  }

  if (!finished && buffer.trim()) processEvent(buffer)
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

export async function getActivitySummary(period: 'today' | '7d' | '30d' | '90d' | '1y' | 'all' = 'today'): Promise<ActivitySummary> {
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

export async function listPdfDocuments(): Promise<PdfDocument[]> {
  const response = await fetch(`${API_BASE_URL}/pdf/documents`)
  if (!response.ok) throw new Error(`Document library failed (${response.status})`)
  return response.json()
}

export class VisualRoadmapApiError extends Error {
  constructor(public code: string, message: string, public model?: string, public action?: string) { super(message) }
}
export async function recordMasteryEvidence(input: { subject: string; topic: string; evidence_type: 'revision_completed' | 'recall_success' | 'recall_failure'; score?: number; confidence?: number; source?: string }): Promise<TopicMastery> {
  const response = await fetch(`${API_BASE_URL}/mastery/evidence`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) })
  if (!response.ok) throw new Error(`Revision evidence failed (${response.status}): ${await response.text()}`)
  return response.json()
}
async function roadmapRequest<T>(path = '', init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/visual-roadmaps${path}`, init)
  if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: string | { code?: string; message?: string; model?: string; action?: string } } | null; const detail = typeof body?.detail === 'object' ? body.detail : null; throw new VisualRoadmapApiError(detail?.code || 'request_failed', detail?.message || (typeof body?.detail === 'string' ? body.detail : `Visual roadmap request failed (${response.status})`), detail?.model, detail?.action) }
  return response.status === 204 ? undefined as T : response.json()
}
export type VisualSourceType = 'general' | 'upsc_book' | 'uploaded_pdf' | 'current_affairs'
export const createVisualRoadmap = (input: { topic: string; visual_type: VisualType; language: string; detail_level?: 'concise' | 'standard' | 'detailed'; source_type?: VisualSourceType; conversation_id?: string | null }) => roadmapRequest<VisualRoadmap>('', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) })
export const listVisualRoadmaps = () => roadmapRequest<VisualRoadmap[]>()
export const deleteVisualRoadmap = (id: string) => roadmapRequest<void>(`/${id}`, { method: 'DELETE' })
export const saveVisualRoadmap = (id: string) => roadmapRequest<void>(`/${id}/save`, { method: 'POST' })
export const createRoadmapQuiz = (id: string, question_count = 5, difficulty = 'standard') => roadmapRequest<RoadmapQuiz>(`/${id}/quiz`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_count, difficulty }) })
export const getRoadmapQuiz = (id: string) => roadmapRequest<RoadmapQuiz>(`/${id}/quiz`)
export const submitRoadmapQuiz = (id: string, answers: Array<{ question_id: string; answer: string }>) => roadmapRequest<RoadmapQuizResult>(`/${id}/quiz/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) })

async function currentAffairsRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`${API_BASE_URL}/current-affairs${path}`, init) }
  catch { throw new CurrentAffairsApiError(0, 'Unable to reach the Current Affairs service. Check the backend and retry.') }
  if (!response.ok) {
    const raw = await response.text(); let message = raw
    try { const parsed = JSON.parse(raw) as { detail?: string | Array<{ msg?: string }> }; message = typeof parsed.detail === 'string' ? parsed.detail : Array.isArray(parsed.detail) ? parsed.detail.map(item => item.msg).filter(Boolean).join('; ') : raw } catch { /* use text */ }
    throw new CurrentAffairsApiError(response.status, message || `Request failed (${response.status})`)
  }
  return response.status === 204 ? undefined as T : response.json()
}
export class CurrentAffairsApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = 'CurrentAffairsApiError' } }
export const getCurrentAffairsArticles = (params = '') => currentAffairsRequest<CurrentAffairsArticle[]>(`/articles${params ? `?${params}` : ''}`)
export const getCurrentAffairsArticle = (id: string) => currentAffairsRequest<CurrentAffairsArticle>(`/articles/${id}`)
export interface CurrentAffairsContentResponse {
  id: string
  slug: string
  title: string
  provider: string
  cadence: string
  subjects: string[]
  publication_date: string | null
  coverage_period: string
  description: string
  content_blocks: ContentBlock[]
  page_references: string[]
  source_page_url: string
  official_pdf_url: string | null
  extraction_status: 'ready' | 'pending' | 'image_only' | 'failed'
  availability: 'available' | 'unavailable'
  saved: boolean
}
export const getCurrentAffairsArticleContent = (id: string) => currentAffairsRequest<CurrentAffairsContentResponse>(`/${id}/content`)
export const getCurrentAffairsBrief = (date: string) => currentAffairsRequest<CurrentAffairsBrief>(`/daily?date=${encodeURIComponent(date)}`)
export const getCurrentAffairsBriefOptional = createCachedOptionalLoader(getCurrentAffairsBrief, reason => reason instanceof CurrentAffairsApiError && reason.status === 404)
export const saveCurrentAffairsArticle = (id: string, saved: boolean) => currentAffairsRequest<void>(`/articles/${id}/save`, { method: saved ? 'DELETE' : 'POST' })
export const getCurrentAffairsSummary = () => currentAffairsRequest<CurrentAffairsSummary>('/summary')
export const getPersonalizedCurrentAffairs = (date?: string) => currentAffairsRequest<PersonalizedCurrentAffairs>(`/personalized${date ? `?date=${encodeURIComponent(date)}` : ''}`)
export type CurrentAffairsQuizPeriod = 'daily' | 'weekly' | 'custom'
export type CurrentAffairsQuizDifficulty = 'easy' | 'standard' | 'difficult'
export interface CurrentAffairsQuizCreate { period_type: CurrentAffairsQuizPeriod; date_from: string; date_to: string; question_count: number; difficulty: CurrentAffairsQuizDifficulty }
export const createCurrentAffairsQuiz = (payload: CurrentAffairsQuizCreate) => currentAffairsRequest<CurrentAffairsQuiz>('/quizzes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
export const getCurrentAffairsQuizzes = () => currentAffairsRequest<CurrentAffairsQuiz[]>('/quizzes')
export const getCurrentAffairsQuizAttempts = (id: string) => currentAffairsRequest<CurrentAffairsQuizResult[]>(`/quizzes/${id}/attempts`)
export const submitCurrentAffairsQuiz = (id: string, answers: Array<{ question_id: string; answer: string }>) => currentAffairsRequest<CurrentAffairsQuizResult>(`/quizzes/${id}/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) })
export const getCurrentAffairsRetentionOverview = () => currentAffairsRequest<CurrentAffairsRetentionOverview>('/retention/overview')
export interface CurrentAffairsDatesResponse {
  available_dates: string[]
  latest_available_date: string
  earliest_available_date: string
  today_record_count: number
  total_active_records: number
}
export interface CurrentAffairsSyncStatusResponse {
  last_synchronized_at: string | null
  sources_checked: string[]
  successful_sources: string[]
  unavailable_sources: string[]
  accepted_article_count: number
  last_run_status: string
}
export const getCurrentAffairsDates = () => currentAffairsRequest<CurrentAffairsDatesResponse>('/dates')
export const getCurrentAffairsSyncStatus = () => currentAffairsRequest<CurrentAffairsSyncStatusResponse>('/status')
export const refreshCurrentAffairs = () => currentAffairsRequest<{ run_id: string; status: string; accepted: number; fetched: number }>('/refresh', { method: 'POST' })
export const markCurrentAffairsRevised = (id: string) => currentAffairsRequest<CurrentAffairsRetention>(`/retention/${id}/revise`, { method: 'POST' })

// UPSC Books API
export interface BookSubjectCount { subject: string; book_count: number }
export interface BookCollectionItem { id: string; provider: string; title: string; slug: string; collection_type: string; description?: string; language: string; exam_stage: string; official_source_url: string }
export interface BookChapterItem { id: string; title: string; chapter_order: number; page_start: number; page_end: number }
export interface UPSCBook {
  id: string
  collection_id?: string | null
  provider: string
  title: string
  slug: string
  subject: string
  original_subject?: string | null
  description?: string | null
  language: string
  prelims_relevant: boolean
  mains_relevant: boolean
  resource_kind?: 'study_book' | 'qa_bank'
  official_source_url: string
  official_pdf_url?: string | null
  publication_year?: number | null
  content_status: string
  extraction_status: string
  indexing_status: string
  page_count: number
  estimated_reading_minutes: number
  saved: boolean
  progress_percentage: number
  last_opened_at?: string | null
  chapters?: BookChapterItem[]
}
export interface UPSCBookContentResponse {
  id: string
  slug: string
  title: string
  provider: string
  subject: string
  description?: string | null
  language: string
  prelims_relevant: boolean
  mains_relevant: boolean
  resource_kind?: 'study_book' | 'qa_bank'
  estimated_reading_minutes: number
  page_count: number
  chapters: BookChapterItem[]
  content_blocks: ContentBlock[]
  page_references: string[]
  official_source_url: string
  official_pdf_url?: string | null
  extraction_status: string
  content_status: string
  indexing_status: string
  availability: 'available' | 'unavailable'
  saved: boolean
  progress_percentage: number
}

async function upscBooksRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/upsc-books${path}`, init)
  if (!response.ok) throw new Error(`UPSC Books request failed (${response.status})`)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const getUpscBookSubjects = (params = '') => upscBooksRequest<BookSubjectCount[]>(`/subjects${params ? `?${params}` : ''}`)
export const getUpscBookCollections = (params = '') => upscBooksRequest<BookCollectionItem[]>(`/collections${params ? `?${params}` : ''}`)
export const getUpscBooks = (params = '') => upscBooksRequest<UPSCBook[]>(`${params ? `?${params}` : ''}`)
export const getUpscBook = (id: string) => upscBooksRequest<UPSCBook>(`/${id}`)
export const getUpscBookContent = (id: string, chapterId?: string) => upscBooksRequest<UPSCBookContentResponse>(`/${id}/content${chapterId ? `?chapter_id=${chapterId}` : ''}`)
export const saveUpscBook = (id: string, saved: boolean) => upscBooksRequest<void>(`/${id}/save`, { method: saved ? 'DELETE' : 'POST' })
export const updateUpscBookProgress = (id: string, progress_percentage: number, chapter_id?: string, last_position = 0) =>
  upscBooksRequest<{ book_id: string; progress_percentage: number }>(`/${id}/progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ progress_percentage, chapter_id, last_position })
  })

export { API_BASE_URL }
