import { useEffect, useRef, useState } from 'react'
import { recordActivityEvent } from './api'

const IDLE_AFTER_MS = 60_000
const FLUSH_AFTER_SECONDS = 300

export function useActiveStudyTracker(
  conversationId: string | null, subject: string | null, topic: string | null,
) {
  const [active, setActive] = useState(false)
  const accumulated = useRef(0)
  const lastInteraction = useRef(Date.now())
  const context = useRef({ conversationId, subject, topic })

  function flush(keepalive = false) {
    const seconds = accumulated.current
    if (seconds <= 0 || !context.current.conversationId) return
    accumulated.current = 0
    void recordActivityEvent({
      event_type: 'study_time_logged',
      conversation_id: context.current.conversationId,
      subject: context.current.subject ?? undefined,
      topic: context.current.topic ?? undefined,
      duration_seconds: seconds,
      metadata: { source: 'frontend_active_timer' },
    }, keepalive).catch(() => { accumulated.current += seconds })
  }

  useEffect(() => {
    flush(true)
    context.current = { conversationId, subject, topic }
  }, [conversationId, subject, topic])

  useEffect(() => {
    const interacted = () => { lastInteraction.current = Date.now() }
    const visibility = () => { if (document.hidden) flush(true) }
    window.addEventListener('pointerdown', interacted)
    window.addEventListener('keydown', interacted)
    document.addEventListener('visibilitychange', visibility)
    const timer = window.setInterval(() => {
      const isActive = Boolean(context.current.conversationId) && !document.hidden &&
        Date.now() - lastInteraction.current < IDLE_AFTER_MS
      setActive(isActive)
      if (isActive) accumulated.current += 1
      if (accumulated.current >= FLUSH_AFTER_SECONDS) flush()
    }, 1000)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('pointerdown', interacted)
      window.removeEventListener('keydown', interacted)
      document.removeEventListener('visibilitychange', visibility)
      flush(true)
    }
  }, [])

  return active
}
