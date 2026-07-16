import { useCallback, useEffect, useMemo, useState } from 'react'
import { deleteMasteryTopic, getMasteryOverview, listMasteryTopics, MasteryOverview as Overview, TopicMastery } from './api'

function date(value: string | null) { return value ? new Date(value).toLocaleDateString() : 'Not recorded' }

export function MasteryOverview() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [topics, setTopics] = useState<TopicMastery[]>([])
  const [subject, setSubject] = useState('all')
  const [risk, setRisk] = useState('all')
  const [open, setOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { const [next, rows] = await Promise.all([getMasteryOverview(), listMasteryTopics()]); setOverview(next); setTopics(rows) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load mastery.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => { const listener = () => void refresh(); window.addEventListener('mentor-data-changed', listener); return () => window.removeEventListener('mentor-data-changed', listener) }, [refresh])
  const subjects = useMemo(() => [...new Set(topics.map(item => item.subject))], [topics])
  const filtered = topics.filter(item => (subject === 'all' || item.subject === subject) && (risk === 'all' || item.risk_level === risk))
  async function reset(item: TopicMastery) {
    if (!window.confirm(`Reset mastery evidence for ${item.topic}?`)) return
    try { await deleteMasteryTopic(item.id); await refresh() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to reset topic.') }
  }

  return <section className="mastery-panel">
    <button className="profile-heading" onClick={() => setOpen(value => !value)}>
      <span><span className="eyebrow">Mastery overview</span><strong>Estimated learning strength & revision risk</strong></span><span>{open ? 'Close' : 'View details'}</span>
    </button>
    {open && (loading ? <div className="profile-state">Loading mastery…</div> : error && !overview ?
      <div className="profile-state error">{error}</div> : overview && <>
        <div className="mastery-metrics">
          <div><span>Average mastery</span><strong>{Math.round(overview.average_mastery * 100)}%</strong></div>
          <div><span>Strong topics</span><strong>{overview.strong_topics.length}</strong></div>
          <div><span>Weak topics</span><strong>{overview.weak_topics.length}</strong></div>
          <div><span>High risk</span><strong>{overview.high_risk_topics.length}</strong></div>
          <div><span>Due for revision</span><strong>{overview.due_for_revision.length}</strong></div>
        </div>
        <div className="mastery-toolbar">
          <select value={subject} onChange={event => setSubject(event.target.value)}><option value="all">All subjects</option>{subjects.map(value => <option key={value}>{value}</option>)}</select>
          <select value={risk} onChange={event => setRisk(event.target.value)}><option value="all">All risks</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select>
          <button className="icon-button" onClick={() => void refresh()}>Refresh</button>
          <small>Last updated {overview.recent_changes[0] ? new Date(overview.recent_changes[0].updated_at).toLocaleString() : '—'}</small>
        </div>
        {topics.length === 0 ? <div className="profile-state">No reliable quiz, recall, revision, or scored-answer evidence yet.</div> : <>
          <div className="mastery-subjects">{overview.subject_breakdown.map(item => <div key={item.subject}><span>{item.subject}</span><i><b style={{ width: `${item.mastery_score * 100}%` }} /></i><small>{Math.round(item.mastery_score * 100)}%</small></div>)}</div>
          <div className="mastery-cards">{filtered.map(item => <article key={item.id}>
            <div><span>{item.subject}</span><em className={`risk-${item.risk_level}`}>{item.risk_level} risk</em></div>
            <h3>{item.topic}</h3><strong>{Math.round(item.mastery_score * 100)}% mastery</strong>
            <p>{item.explanation.slice(0, 2).join(' · ')}</p>
            <small>Last revision: {date(item.last_revised_at)} · Next: {date(item.next_revision_at)}</small>
            <button className="icon-button" onClick={() => void reset(item)}>View details / reset</button>
          </article>)}</div>
        </>}
        <p className="privacy-note">Mastery and forgetting risk are estimates based on your activity, quiz results and revision history.</p>
        {error && <div className="profile-state error">{error}</div>}
      </>)}
  </section>
}
