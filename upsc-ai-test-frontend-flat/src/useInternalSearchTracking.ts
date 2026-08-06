import { useEffect, useRef } from 'react'
import { recordActivityEvent } from './api'

export function useInternalSearchTracking(query: string, page: string, context: string) {
  const lastRecorded = useRef('')
  useEffect(() => {
    const normalized = query.trim().replace(/\s+/g, ' ')
    if (normalized.length < 2 || normalized === lastRecorded.current) return
    const timer = window.setTimeout(() => {
      lastRecorded.current = normalized
      void recordActivityEvent({
        event_type: 'internal_search', subject: context, topic: normalized,
        duration_seconds: 0, metadata: { page, source: 'platform_search' },
      }).catch(() => undefined)
    }, 900)
    return () => window.clearTimeout(timer)
  }, [query, page, context])
}
