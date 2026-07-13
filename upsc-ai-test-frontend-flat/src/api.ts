export type StudyMode = 'learn' | 'revision' | 'prelims' | 'mains' | 'interview'

export interface ChatRequest {
  question: string
  mode: StudyMode
}

export interface ChatResponse {
  status: string
  answer: string
  provider: string
  sources: Array<Record<string, unknown>>
}

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

export { API_BASE_URL }
