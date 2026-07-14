import { useCallback, useEffect, useState } from 'react'
import { getMentorDashboard, MentorDashboardData, regenerateMentorActions, updateMentorAction } from './api'

const minutes = (seconds: number) => `${Math.floor(seconds / 60)}m`

export function MentorDashboard({ trackingActive }: { trackingActive: boolean }) {
  const [data, setData] = useState<MentorDashboardData | null>(null)
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [updated, setUpdated] = useState<Date | null>(null); const [why, setWhy] = useState(false); const [feedback, setFeedback] = useState('')
  const refresh = useCallback(async () => { setLoading(true); setError(''); try { setData(await getMentorDashboard()); setUpdated(new Date()) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load dashboard.') } finally { setLoading(false) } }, [])
  useEffect(() => { void refresh() }, [refresh])
  async function act(operation: 'accept' | 'complete' | 'skip') {
    const action = data?.recommendations.primary; if (!action || operation === 'skip' && !window.confirm('Skip this recommendation?')) return
    try { await updateMentorAction(action.id, operation); setFeedback(operation === 'complete' ? 'Completed.' : operation === 'accept' ? 'Started.' : 'Skipped.'); await refresh() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to update action.') }
  }
  async function regenerate() { try { await regenerateMentorActions(); await refresh() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to refresh plan.') } }
  if (loading) return <section className="mentor-dashboard dashboard-skeleton">Loading Mentor Intelligence…</section>
  if (error && !data) return <section className="mentor-dashboard profile-state error">{error}<button className="icon-button" onClick={() => void refresh()}>Retry</button></section>
  if (!data) return null
  const action = data.recommendations.primary
  const target = data.profile.daily_target_minutes * 60
  const progress = Math.min(100, target ? data.today.study_seconds / target * 100 : 0)
  return <section className="mentor-dashboard">
    <header className="dashboard-head"><div><p className="eyebrow">Mentor Intelligence</p><h2>{data.mentor_brief.summary}</h2><small>{trackingActive ? '● Active study tracking' : '○ Tracking paused'} · Updated {updated?.toLocaleTimeString()}</small></div><button className="icon-button" onClick={() => void refresh()}>Refresh dashboard</button></header>
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <div className="dashboard-metrics"><article><span>Active study</span><strong>{minutes(data.today.study_seconds)}</strong><small>{Math.round(progress)}% of daily target</small><i><b style={{ width: `${progress}%` }} /></i></article><article><span>Questions</span><strong>{data.today.questions_asked}</strong><small>Questions indicate activity, not mastery.</small></article><article><span>Subjects</span><strong>{data.today.subjects_studied}</strong><small>{data.today.top_subject ? `${data.today.top_subject} led today.` : 'Start studying to build a pattern.'}</small></article></div>
        <article className="dashboard-action"><p className="eyebrow">Primary next action</p>{action ? <><h3>{action.title}</h3><div><span>{action.subject} · {action.topic}</span><em>{action.priority_level} · {action.estimated_minutes} min</em></div><p>{action.reason[0]}</p><button className="why-button" aria-expanded={why} onClick={() => setWhy(value => !value)}>Why this recommendation?</button>{why && <ul className="why-details">{action.reason.map(reason => <li key={reason}>{reason}</li>)}</ul>}<div className="profile-actions"><button className="send-button" onClick={() => void act('accept')}>Start</button><button className="icon-button" onClick={() => void act('complete')}>Complete</button><button className="icon-button" onClick={() => void act('skip')}>Skip</button><button className="icon-button" onClick={() => void regenerate()}>Regenerate</button></div></> : <p>No immediate recommendation. Reliable quiz, recall, and revision evidence will create a plan.</p>}</article>
        <article className="dashboard-card"><h3>Recent activity</h3>{data.recent_activity.length ? data.recent_activity.slice(0, 5).map(event => <p key={event.id}>{event.event_type.replaceAll('_', ' ')} · {event.topic ?? event.subject ?? 'General'}</p>) : <p>No activity recorded today.</p>}</article>
      </div>
      <aside className="dashboard-side"><article><h3>Strengths</h3>{data.mentor_brief.strengths.slice(0, 3).map(item => <p key={item.id}>{item.topic} · {Math.round(item.mastery_score * 100)}%</p>)}{!data.mentor_brief.strengths.length && <p>More evidence needed.</p>}</article><article><h3>Needs attention</h3>{data.mentor_brief.weaknesses.slice(0, 3).map(item => <p key={item.id}>{item.topic} needs practice.</p>)}</article><article><h3>Likely to forget</h3>{data.mentor_brief.likely_to_forget.slice(0, 3).map(item => <p key={item.id}>{item.topic} · {item.risk_level} risk</p>)}</article><article><h3>Your preferences</h3><p>{data.profile.preferred_language} · {data.profile.preferred_depth} · {data.profile.preferred_format}</p></article></aside>
    </div>
    <div className="dashboard-lower"><article><h3>Subject mastery</h3>{data.mastery.subject_breakdown.map(item => <div className="dash-bar" key={item.subject}><span>{item.subject}</span><i><b style={{ width: `${item.mastery_score * 100}%` }} /></i><small>{Math.round(item.mastery_score * 100)}% — {item.mastery_score < .5 ? 'needs attention' : 'building well'}</small></div>)}</article><article><h3>Study-time breakdown</h3>{data.today.subject_breakdown.map(item => <div className="dash-bar" key={item.name}><span>{item.name}</span><i><b style={{ width: `${Math.max(3, data.today.study_seconds ? item.study_seconds / data.today.study_seconds * 100 : 3)}%` }} /></i><small>{minutes(item.study_seconds)}</small></div>)}</article><article><h3>Revision risk</h3><p>{data.mastery.high_risk_topics.length} high-risk topics. {data.mastery.high_risk_topics[0] ? `Review ${data.mastery.high_risk_topics[0].topic} first.` : 'No urgent revision risk detected.'}</p><h3>Alternatives</h3>{data.recommendations.alternatives.map(item => <p key={item.id}>{item.title} · {item.estimated_minutes}m</p>)}</article></div>
    {feedback && <div className="saved-state">{feedback}</div>}{error && <div className="profile-state error">{error}</div>}<p className="privacy-note">Mentor insights are estimates based on your study activity, quiz evidence, revision history and saved preferences.</p>
  </section>
}
