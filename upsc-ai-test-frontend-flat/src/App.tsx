import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  API_BASE_URL,
  checkBackend,
  sendChat,
  streamChat,
  StudyMode,
  uploadPdf,
} from './api'

type Role = 'user' | 'assistant'

type Message = {
  id: string
  role: Role
  content: string
  createdAt: string
  error?: boolean
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
  const [messages, setMessages] = useState<Message[]>([initialAssistantMessage()])
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<StudyMode>('learn')
  const [useStreaming, setUseStreaming] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [uploadState, setUploadState] = useState('No PDF selected')
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)

  const selectedMode = useMemo(() => MODES.find((item) => item.value === mode)!, [mode])

  useEffect(() => {
    const controller = new AbortController()
    void checkBackend(controller.signal).then(setBackendOnline)
    return () => controller.abort()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isGenerating])

  function updateAssistant(messageId: string, updater: (current: string) => string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, content: updater(message.content), error: false } : message,
      ),
    )
  }

  async function submitQuestion(event?: FormEvent) {
    event?.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isGenerating) return

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
      createdAt: new Date().toISOString(),
    }

    setMessages((current) => [...current, userMessage, assistantMessage])
    setQuestion('')
    setIsGenerating(true)
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const payload = { question: trimmed, mode }
      if (useStreaming) {
        await streamChat(payload, (token) => updateAssistant(assistantId, (current) => current + token), controller.signal)
      } else {
        const response = await sendChat(payload, controller.signal)
        updateAssistant(assistantId, () => response.answer)
      }
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

        <button className="new-chat" onClick={() => setMessages([initialAssistantMessage()])}>
          <span>＋</span> New test chat
        </button>

        <section className="side-section">
          <p className="eyebrow">Backend</p>
          <div className="status-card">
            <span className={`status-dot ${backendOnline === true ? 'online' : backendOnline === false ? 'offline' : ''}`} />
            <div>
              <strong>{backendOnline === null ? 'Checking…' : backendOnline ? 'Connected' : 'Not connected'}</strong>
              <small>{API_BASE_URL}</small>
            </div>
          </div>
        </section>

        <section className="side-section">
          <p className="eyebrow">Current request contract</p>
          <pre className="contract">{`POST /chat/stream\n{\n  "question": "...",\n  "mode": "${mode}"\n}`}</pre>
        </section>

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
          <span>Local browser chat only</span>
          <span>Backend memory IDs come later</span>
        </div>
      </aside>

      <section className="workspace">
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

        <section className="message-list" aria-live="polite">
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
                  <div className="typing" aria-label="Assistant is generating">
                    <span /> <span /> <span />
                  </div>
                )}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </section>

        <form className="composer" onSubmit={(event) => void submitQuestion(event)}>
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
        </form>
      </section>
    </main>
  )
}
