import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ProfilePanel } from './ProfilePanel'
import { MentorDashboard } from './MentorDashboard'
import { VideoRecommendations } from './VideoRecommendations'
import { CommunityPage } from './CommunityPage'
import { VisualLearningPage } from './VisualLearningPage'
import { CurrentAffairsPage } from './CurrentAffairsPage'
import { useActiveStudyTracker } from './useActiveStudyTracker'
import {
  API_BASE_URL,
  checkBackend,
  Conversation,
  createConversation,
  deleteConversation,
  listConversations,
  loadConversationMessages,
  renameConversation,
  sendChat,
  streamChat,
  StudyMode,
  uploadPdf,
  getProfile,
  LearnerProfile,
} from './api'

type Role = 'user' | 'assistant'

type Message = {
  id: string
  role: Role
  content: string
  createdAt: string
  error?: boolean
  adaptation?: { language: string; depth: string; format: string }
  status?: string
}

const MODES: Array<{ value: StudyMode; label: string; hint: string }> = [
  { value: 'learn', label: 'Learn', hint: 'Concept explanation' },
  { value: 'revision', label: 'Revision', hint: 'Concise notes' },
  { value: 'prelims', label: 'Prelims', hint: 'Facts and provisions' },
  { value: 'mains', label: 'Mains', hint: 'Structured answer' },
  { value: 'interview', label: 'Interview', hint: 'Balanced viewpoint' },
]

function id(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function initialAssistantMessage(): Message {
  return {
    id: id('assistant'),
    role: 'assistant',
    content:
      'Your test frontend is connected to the current backend contract. Choose a study mode, ask a UPSC question, or upload a PDF for RAG.',
    createdAt: new Date().toISOString(),
  }
}

export default function App() {
  const [page, setPage] = useState<'dashboard' | 'chat' | 'community' | 'visual' | 'current_affairs'>('dashboard')
  const [messages, setMessages] = useState<Message[]>([initialAssistantMessage()])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [activeSubject, setActiveSubject] = useState<string | null>(null)
  const [activeTopic, setActiveTopic] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<StudyMode>('learn')
  const [useStreaming, setUseStreaming] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [uploadState, setUploadState] = useState('No PDF selected')
  const [profileDefaults, setProfileDefaults] = useState<LearnerProfile | null>(null)
  const [adaptationError, setAdaptationError] = useState('')
  const [messageLanguage, setMessageLanguage] = useState<LearnerProfile['preferred_language'] | null>(null)
  const [messageDepth, setMessageDepth] = useState<LearnerProfile['preferred_depth'] | null>(null)
  const [messageFormat, setMessageFormat] = useState<LearnerProfile['preferred_format'] | null>(null)
  const [videoRequested, setVideoRequested] = useState(false)
  const [showScrollLatest, setShowScrollLatest] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const workspaceRef = useRef<HTMLElement | null>(null)
  const nearBottomRef = useRef(true)
  const fileRef = useRef<HTMLInputElement | null>(null)

  const selectedMode = useMemo(() => MODES.find((item) => item.value === mode)!, [mode])
  const trackingActive = useActiveStudyTracker(conversationId, activeSubject, activeTopic)

  useEffect(() => {
    const controller = new AbortController()
    void checkBackend(controller.signal).then(setBackendOnline)
    void refreshConversations()
    void getProfile().then(setProfileDefaults).catch(() => setAdaptationError('Profile defaults unavailable; safe defaults are active.'))
    return () => controller.abort()
  }, [])

  async function refreshConversations() {
    setConversations(await listConversations())
  }

  async function newChat() {
    const conversation = await createConversation()
    setConversationId(conversation.id)
    setActiveSubject(null)
    setActiveTopic(null)
    setMessages([initialAssistantMessage()])
    setPage('chat')
    await refreshConversations()
  }

  async function selectConversation(id: string) {
    const stored = await loadConversationMessages(id)
    setConversationId(id)
    setActiveSubject(null)
    setActiveTopic(null)
    setMessages(stored.map((message) => ({
      id: String(message.id), role: message.role, content: message.content, createdAt: message.timestamp,
    })))
    setPage('chat')
  }

  async function renameChat(conversation: Conversation) {
    const title = window.prompt('Conversation title', conversation.title)?.trim()
    if (!title) return
    await renameConversation(conversation.id, title)
    await refreshConversations()
  }

  async function removeChat(id: string) {
    await deleteConversation(id)
    if (conversationId === id) {
      setConversationId(null)
      setMessages([initialAssistantMessage()])
    }
    await refreshConversations()
  }

  function scrollToLatest() {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    bottomRef.current?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'end' })
    nearBottomRef.current = true
    setShowScrollLatest(false)
    setUnreadCount(0)
  }

  function handleWorkspaceScroll() {
    const workspace = workspaceRef.current
    if (!workspace) return
    const nearBottom = workspace.scrollHeight - workspace.scrollTop - workspace.clientHeight <= 200
    nearBottomRef.current = nearBottom
    setShowScrollLatest(!nearBottom)
    if (nearBottom) setUnreadCount(0)
  }

  useEffect(() => {
    if (nearBottomRef.current) {
      const frame = requestAnimationFrame(scrollToLatest)
      return () => cancelAnimationFrame(frame)
    }
    setUnreadCount(current => Math.min(99, current + 1))
  }, [messages, isGenerating])

  function updateAssistant(messageId: string, updater: (current: string) => string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, content: updater(message.content), error: false } : message,
      ),
    )
  }

  function setAssistantAdaptation(messageId: string, language?: string, depth?: string, format?: string) {
    if (!language || !depth || !format) return
    setMessages(current => current.map(message => message.id === messageId ? { ...message, adaptation: { language, depth, format } } : message))
  }

  async function submitQuestion(event?: FormEvent) {
    event?.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isGenerating) return
    setVideoRequested(/\b(video|watch|youtube)\b/i.test(trimmed))

    const userMessage: Message = {
      id: id('user'),
      role: 'user',
      content: trimmed,
      createdAt: new Date().toISOString(),
    }
    const assistantId = id('assistant')
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      status: 'Preparing model…',
      createdAt: new Date().toISOString(),
    }

    setMessages((current) => [...current, userMessage, assistantMessage])
    setQuestion('')
    setIsGenerating(true)
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const payload = {
        question: trimmed, mode, ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(messageLanguage ? { language: messageLanguage } : {}),
        ...(messageDepth ? { depth: messageDepth } : {}),
        ...(messageFormat ? { format: messageFormat } : {}),
      }
      if (useStreaming) {
        let pending = ''
        let flushTimer: number | undefined
        const flushTokens = () => {
          if (!pending) return
          const text = pending
          pending = ''
          updateAssistant(assistantId, (current) => current + text)
          setMessages(current => current.map(message => message.id === assistantId ? { ...message, status: undefined } : message))
        }
        const retrievalTimer = window.setTimeout(() => {
          setMessages(current => current.map(message => message.id === assistantId && !message.content ? { ...message, status: 'Retrieving relevant context…' } : message))
        }, 250)
        await streamChat(payload, (token) => {
          pending += token
          if (flushTimer === undefined) flushTimer = window.setTimeout(() => { flushTimer = undefined; flushTokens() }, 45)
        },
          (id, subject, topic, language, depth, format) => {
            window.clearTimeout(retrievalTimer)
            setMessages(current => current.map(message => message.id === assistantId && !message.content ? { ...message, status: 'Generating answer…' } : message))
            setConversationId(id)
            setActiveSubject(subject ?? null)
            setActiveTopic(topic ?? null)
            setAssistantAdaptation(assistantId, language, depth, format)
          }, controller.signal)
        if (flushTimer !== undefined) window.clearTimeout(flushTimer)
        flushTokens()
      } else {
        const response = await sendChat(payload, controller.signal)
        setConversationId(response.conversation_id)
        setActiveSubject(response.subject ?? null)
        setActiveTopic(response.topic ?? null)
        setAssistantAdaptation(assistantId, response.effective_language, response.effective_depth, response.effective_format)
        updateAssistant(assistantId, () => response.answer)
      }
      await refreshConversations()
    } catch (error) {
      if (controller.signal.aborted) {
        updateAssistant(assistantId, (current) => current || 'Generation stopped.')
      } else {
        const message = error instanceof Error ? error.message : 'Unknown request error.'
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId
              ? { ...item, content: `Connection error: ${message}`, error: true }
              : item,
          ),
        )
      }
    } finally {
      abortRef.current = null
      setIsGenerating(false)
    }
  }

  function askFromRoadmap(text: string) {
    setQuestion(text)
    setPage('chat')
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submitQuestion()
    }
  }

  async function handlePdf(file: File | undefined) {
    if (!file) return
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadState('Please select a PDF file.')
      return
    }

    setUploadState(`Uploading ${file.name}...`)
    try {
      await uploadPdf(file)
      setUploadState(`${file.name} uploaded and sent for processing.`)
    } catch (error) {
      setUploadState(error instanceof Error ? error.message : 'PDF upload failed.')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">U</div>
          <div>
            <strong>UPSC AI</strong>
            <span>Test workspace</span>
          </div>
        </div>

        <button className="new-chat" onClick={() => void newChat()}>
          <span>＋</span> New test chat
        </button>
        <nav className="app-navigation" aria-label="Main navigation"><button className={page === 'dashboard' ? 'active' : ''} onClick={() => setPage('dashboard')}>Dashboard</button><button className={page === 'chat' ? 'active' : ''} onClick={() => setPage('chat')}>Chat</button><button className={page === 'current_affairs' ? 'active' : ''} onClick={() => setPage('current_affairs')}>Current Affairs</button><button className={page === 'visual' ? 'active' : ''} onClick={() => setPage('visual')}>Visual Learning</button><button className={page === 'community' ? 'active' : ''} onClick={() => setPage('community')}>Community</button></nav>

        <section className="side-section">
          <p className="eyebrow">Conversations</p>
          {conversations.map((conversation) => (
            <div className={`status-card conversation-item ${conversation.id === conversationId ? 'active' : ''}`} key={conversation.id}>
              <button className="secondary-button" title={conversation.title} aria-pressed={conversation.id === conversationId} onClick={() => void selectConversation(conversation.id)}>
                {conversation.title}
              </button>
              <button className="icon-button" aria-label={`Rename ${conversation.title}`} title="Rename" onClick={() => void renameChat(conversation)}>Edit</button>
              <button className="icon-button danger-button" aria-label={`Delete ${conversation.title}`} title="Delete" onClick={() => void removeChat(conversation.id)}>Delete</button>
            </div>
          ))}
        </section>

        <details className="side-section technical-details">
          <summary>Backend status</summary>
          <div className="status-card">
            <span className={`status-dot ${backendOnline === true ? 'online' : backendOnline === false ? 'offline' : ''}`} />
            <div>
              <strong>{backendOnline === null ? 'Checking…' : backendOnline ? 'Connected' : 'Not connected'}</strong>
              <small>{API_BASE_URL}</small>
            </div>
          </div>
        </details>

        <details className="side-section technical-details">
          <summary>Request details</summary>
          <pre className="contract">{`POST /chat/stream\n{\n  "question": "...",\n  "mode": "${mode}",\n  "conversation_id": "${conversationId ?? '...'}"\n}`}</pre>
        </details>

        <section className="side-section pdf-section">
          <p className="eyebrow">RAG test</p>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(event) => void handlePdf(event.target.files?.[0])}
          />
          <button className="secondary-button" onClick={() => fileRef.current?.click()}>
            Upload PDF
          </button>
          <small className="upload-state">{uploadState}</small>
        </section>

        <div className="sidebar-footer">
          <span>Conversation memory synchronized</span>
        </div>
      </aside>

      <section className={`workspace ${page}`} ref={workspaceRef} onScroll={handleWorkspaceScroll}>
        {page === 'community' && <CommunityPage />}
        {page === 'visual' && <VisualLearningPage onAsk={askFromRoadmap} />}
        {page === 'current_affairs' && <CurrentAffairsPage />}
        {page === 'dashboard' && <div className="dashboard-page">
          <header className="topbar dashboard-topbar"><div><p className="eyebrow">Mentor overview</p><h1>Your study dashboard</h1><small>Progress, next actions, revision risk, and learning preferences.</small></div><button className="send-button" onClick={() => setPage('chat')}>Open Chat</button></header>
          <MentorDashboard trackingActive={trackingActive} />
          <ProfilePanel />
        </div>}
        {page === 'chat' && <div className="chat-page">
        <header className="topbar">
          <div>
            <p className="eyebrow">AI study session</p>
            <h1>{selectedMode.label} mode</h1>
          </div>
          <div className="header-controls">
            <label className="select-wrap">
              <span>Mode</span>
              <select value={mode} onChange={(event) => setMode(event.target.value as StudyMode)}>
                {MODES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="toggle-wrap">
              <input
                type="checkbox"
                checked={useStreaming}
                onChange={(event) => setUseStreaming(event.target.checked)}
              />
              <span>Streaming</span>
            </label>
          </div>
        </header>

        <div className="mode-strip">
          <span>{selectedMode.hint}</span>
          <span>Model settings are selected by the backend generation profile.</span>
        </div>

        <section className="message-list chat-messages" aria-live="polite">
          {messages.map((message) => (
            <article key={message.id} className={`message-row ${message.role}`}>
              <div className="avatar">{message.role === 'user' ? 'You' : 'AI'}</div>
              <div className={`message-card ${message.error ? 'error' : ''}`}>
                <div className="message-meta">
                  <strong>{message.role === 'user' ? 'You' : 'UPSC Study Assistant'}</strong>
                  <time>{new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time>
                </div>
                {message.content ? (
                  <div className="markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="stream-status" role="status" aria-live="polite">
                    <div className="typing" aria-hidden="true"><span /> <span /> <span /></div>
                    <span>{message.status ?? 'Preparing model…'}</span>
                  </div>
                )}
                {message.adaptation && <small className="adaptation-label">{message.adaptation.language} · {message.adaptation.depth} · {message.adaptation.format}</small>}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </section>

        {videoRequested && <VideoRecommendations subject={activeSubject} topic={activeTopic} explicitRequest />}

        {showScrollLatest && <button type="button" className="scroll-latest" aria-label="Scroll to latest message" onClick={scrollToLatest}>
          <span aria-hidden="true">↓</span> Latest {unreadCount > 0 && <span className="unread-count" aria-label={`${unreadCount} new message updates`}>{unreadCount}</span>}
        </button>}

        <div className="chat-composer-shell"><form className="composer" onSubmit={(event) => void submitQuestion(event)}>
          <div className="adaptation-controls" title="Message settings override your saved profile for this message only.">
            <label>Language<select aria-label="Response language" disabled={isGenerating || !profileDefaults} value={messageLanguage ?? profileDefaults?.preferred_language ?? 'auto'} onChange={event => setMessageLanguage(event.target.value as LearnerProfile['preferred_language'])}><option value="auto">Auto</option><option value="english">English</option><option value="hindi">Hindi</option><option value="punjabi">Punjabi</option></select></label>
            <label>Depth<select aria-label="Answer depth" disabled={isGenerating || !profileDefaults} value={messageDepth ?? profileDefaults?.preferred_depth ?? 'standard'} onChange={event => setMessageDepth(event.target.value as LearnerProfile['preferred_depth'])}><option value="quick">Quick</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select></label>
            <label>Format<select aria-label="Answer format" disabled={isGenerating || !profileDefaults} value={messageFormat ?? profileDefaults?.preferred_format ?? 'mixed'} onChange={event => setMessageFormat(event.target.value as LearnerProfile['preferred_format'])}><option value="bullets">Bullets</option><option value="structured">Structured</option><option value="explanation">Explanation</option><option value="mixed">Mixed</option></select></label>
            <button type="button" className="icon-button" disabled={isGenerating} onClick={() => { setMessageLanguage(null); setMessageDepth(null); setMessageFormat(null) }}>Use profile defaults</button>
            <small>{profileDefaults ? messageLanguage || messageDepth || messageFormat ? 'One-message override' : 'Saved profile settings' : 'Loading profile defaults…'}{adaptationError && ` · ${adaptationError}`}</small>
          </div>
          <div className="composer-toolbar">
            <button type="button" className="icon-button" onClick={() => fileRef.current?.click()} title="Upload PDF">
              Attach PDF
            </button>
            <span>{useStreaming ? 'Live token streaming enabled' : 'Standard JSON response enabled'}</span>
          </div>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Ask about polity, history, economy, current affairs…"
            rows={3}
            disabled={isGenerating}
          />
          <div className="composer-bottom">
            <small>Enter to send · Shift+Enter for a new line</small>
            {isGenerating ? (
              <button type="button" className="stop-button" onClick={() => abortRef.current?.abort()}>
                Stop
              </button>
            ) : (
              <button type="submit" className="send-button" disabled={!question.trim()}>
                Send question
              </button>
            )}
          </div>
        </form></div>
        </div>}
      </section>
    </main>
  )
}
