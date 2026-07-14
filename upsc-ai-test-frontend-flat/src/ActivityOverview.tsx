import { useCallback, useEffect, useState } from 'react'
import { ActivitySummary, getActivitySummary } from './api'

function duration(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m`
}

export function ActivityOverview({ trackingActive }: { trackingActive: boolean }) {
  const [summary, setSummary] = useState<ActivitySummary | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { setSummary(await getActivitySummary()) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load activity.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  return <section className="activity-overview">
    <div className="activity-heading">
      <div><p className="eyebrow">Activity overview</p><strong>Today</strong></div>
      <div className="activity-actions"><span className={trackingActive ? 'tracking active' : 'tracking'}>
        {trackingActive ? 'Tracking active study' : 'Tracking paused'}
      </span><button className="icon-button" onClick={() => void refresh()}>Refresh</button></div>
    </div>
    {loading ? <div className="activity-state">Loading activity…</div> : error ?
      <div className="activity-state error">{error}</div> : summary && summary.recent_events.length ? <>
        <div className="activity-metrics">
          <div><span>Active study</span><strong>{duration(summary.total_study_seconds)}</strong></div>
          <div><span>Questions</span><strong>{summary.questions_asked}</strong></div>
          <div><span>Subjects</span><strong>{summary.subjects_studied}</strong></div>
          <div><span>Top subject</span><strong>{summary.top_subject ?? '—'}</strong></div>
          <div><span>Top topic</span><strong>{summary.top_topic ?? '—'}</strong></div>
        </div>
        <div className="activity-details">
          <div>{summary.subject_breakdown.map(item => <div className="activity-bar" key={item.name}>
            <span>{item.name}</span><i style={{ width: `${Math.max(4, summary.total_study_seconds ? item.study_seconds / summary.total_study_seconds * 100 : 4)}%` }} />
            <small>{duration(item.study_seconds)}</small>
          </div>)}</div>
          <div className="recent-activity">{summary.recent_events.slice(0, 4).map(event =>
            <span key={event.id}>{event.event_type.replaceAll('_', ' ')} · {event.topic ?? event.subject ?? 'General'}</span>)}</div>
        </div>
      </> : <div className="activity-state">No study activity recorded today. Open a conversation to begin active tracking.</div>}
  </section>
}
