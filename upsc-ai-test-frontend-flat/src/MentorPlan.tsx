import { useCallback, useEffect, useState } from 'react'
import { getNextMentorAction, listMasteryTopics, MentorAction, regenerateMentorActions, TopicMastery, updateMentorAction } from './api'

export function MentorPlan() {
  const [action, setAction] = useState<MentorAction | null>(null)
  const [alternatives, setAlternatives] = useState<MentorAction[]>([])
  const [mastery, setMastery] = useState<TopicMastery[]>([])
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [feedback, setFeedback] = useState(''); const [why, setWhy] = useState(false)
  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { const [next, topics] = await Promise.all([getNextMentorAction(), listMasteryTopics()]); setAction(next.action); setAlternatives(next.alternatives); setMastery(topics) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load mentor plan.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  async function change(operation: 'accept' | 'complete' | 'skip') {
    if (!action || operation === 'skip' && !window.confirm('Skip this recommendation for now?')) return
    try { await updateMentorAction(action.id, operation); setFeedback(operation === 'complete' ? 'Action completed.' : operation === 'accept' ? 'Action started.' : 'Action skipped.'); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to update action.') }
  }
  async function regenerate() { try { await regenerateMentorActions(); await refresh() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to regenerate.') } }
  const source = action ? mastery.find(item => item.id === action.source_mastery_id) : null
  return <section className="mentor-plan">
    <div className="activity-heading"><div><p className="eyebrow">Today's Mentor Plan</p><strong>{action ? `Your highest priority today is ${action.subject} because ${action.reason[0].toLowerCase()}.` : 'Your focused study plan'}</strong></div><button className="icon-button" onClick={() => void regenerate()}>Refresh plan</button></div>
    {loading ? <div className="profile-state">Building your plan…</div> : error && !action ? <div className="profile-state error">{error}</div> : !action ? <div className="profile-state">No immediate action is needed. Add reliable quiz, recall, or revision evidence to build a plan.</div> : <>
      <article className="mentor-primary"><div><span>{action.subject} · {action.topic}</span><em>{action.priority_level} priority</em></div><h2>{action.title}</h2>
        <div className="mentor-facts"><span>{action.estimated_minutes} min</span><span>{Math.round((source?.mastery_score ?? 0) * 100)}% mastery</span><span>{source?.risk_level ?? 'unknown'} forgetting risk</span></div>
        <p>{action.reason[0]}</p><button className="why-button" onClick={() => setWhy(value => !value)}>Why this?</button>{why && <ul>{action.reason.map(reason => <li key={reason}>{reason}</li>)}</ul>}
        <div className="profile-actions"><button className="send-button" onClick={() => void change('accept')}>Start</button><button className="icon-button" onClick={() => void change('complete')}>Complete</button><button className="icon-button" onClick={() => void change('skip')}>Skip</button><button className="icon-button">View Topic</button></div>
      </article>
      {alternatives.length > 0 && <div className="mentor-alternatives">{alternatives.map(item => <span key={item.id}><strong>{item.title}</strong><small>{item.estimated_minutes} min · {item.priority_level}</small></span>)}</div>}
      {feedback && <div className="saved-state">{feedback}</div>}{error && <div className="profile-state error">{error}</div>}
    </>}
    <p className="privacy-note">Recommendations are based on your study activity, quiz evidence, mastery estimate and revision history.</p>
  </section>
}
