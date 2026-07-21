import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BookOpen, Newspaper, RefreshCcw, Sparkles } from 'lucide-react'
import {
  ActivitySummary,
  CurrentAffairsArticle,
  CurrentAffairsSummary,
  PdfDocument,
  VisualRoadmap,
  getActivitySummary,
  getCurrentAffairsArticles,
  getCurrentAffairsSummary,
  getMentorDashboard,
  listPdfDocuments,
  listVisualRoadmaps,
  MentorDashboardData,
} from './api'
import type { AppPage } from './AppShell'
import {
  extractDailyTrend,
  formatStudyDuration,
  RevealSection,
  SubjectDonutChart,
  StudyTrendChart,
} from './StudyCharts'

const riskOrder: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 }

function formatGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function isMeaningfulEvent(event: { event_type: string }) {
  return event.event_type !== 'system' && event.event_type !== 'heartbeat'
}

export function MentorDashboard({ trackingActive, onNavigate }: { trackingActive: boolean; onNavigate?: (page: AppPage) => void }) {
  const [data, setData] = useState<MentorDashboardData | null>(null)
  const [activity, setActivity] = useState<ActivitySummary | null>(null)
  const [currentAffairs, setCurrentAffairs] = useState<CurrentAffairsSummary | null>(null)
  const [currentArticles, setCurrentArticles] = useState<CurrentAffairsArticle[]>([])
  const [pdfs, setPdfs] = useState<PdfDocument[]>([])
  const [roadmaps, setRoadmaps] = useState<VisualRoadmap[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [updated, setUpdated] = useState<Date | null>(null)
  const detailsRef = useRef<HTMLDivElement | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [dashboard, summary, current, articles, pdfDocuments, visualRoadmaps] = await Promise.all([
        getMentorDashboard(),
        getActivitySummary('7d'),
        getCurrentAffairsSummary().catch(() => null),
        getCurrentAffairsArticles().catch(() => []),
        listPdfDocuments().catch(() => []),
        listVisualRoadmaps().catch(() => []),
      ])
      setData(dashboard)
      setActivity(summary)
      setCurrentAffairs(current)
      setCurrentArticles(articles.slice(0, 3))
      setPdfs(pdfDocuments.slice(0, 3))
      setRoadmaps(visualRoadmaps.slice(0, 3))
      setUpdated(new Date())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load dashboard.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    const listener = () => void refresh()
    window.addEventListener('mentor-data-changed', listener)
    return () => window.removeEventListener('mentor-data-changed', listener)
  }, [refresh])

  const studyTrend = useMemo(() => (activity ? extractDailyTrend(activity) : null), [activity])
  const totalWeeklyStudySeconds = activity?.total_study_seconds ?? 0
  const subjectBreakdown = activity?.subject_breakdown ?? []

  const attentionTopics = useMemo(() => {
    if (!data) return []
    const items = data.mastery.high_risk_topics.length ? data.mastery.high_risk_topics : data.mentor_brief.weaknesses
    return [...items]
      .sort((a, b) => (riskOrder[a.risk_level] ?? 4) - (riskOrder[b.risk_level] ?? 4) || a.mastery_score - b.mastery_score)
      .slice(0, 4)
  }, [data])

  const recentActivity = useMemo(() => {
    if (!data) return []
    const seen = new Set<string>()
    return data.recent_activity.filter((event) => {
      if (!isMeaningfulEvent(event)) return false
      const key = `${event.event_type}|${event.subject ?? ''}|${event.topic ?? ''}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    }).slice(0, 5)
  }, [data])

  const action = data?.recommendations.primary
  const targetSeconds = data?.profile.daily_target_minutes ? data.profile.daily_target_minutes * 60 : 0
  const studySecondsToday = data?.today?.study_seconds ?? 0
  const targetProgress = targetSeconds ? Math.min(100, Math.round(studySecondsToday / targetSeconds * 100)) : 0
  const targetText = targetSeconds ? `${Math.round(studySecondsToday / 60)}m of ${data?.profile.daily_target_minutes}m` : 'No daily target set'

  const scrollToDetails = () => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    detailsRef.current?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' })
  }

  if (loading) return <section className="mentor-dashboard dashboard-skeleton">Loading Mentor Intelligence…</section>
  if (error && !data) return <section className="mentor-dashboard profile-state error">{error}<button className="icon-button" onClick={() => void refresh()}>Retry</button></section>
  if (!data) return null

  return (
    <section className="mentor-dashboard">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Mentor wireframe</p>
          <h1>{formatGreeting()}</h1>
          <p>{data.mentor_brief.summary}</p>
          <div className="hero-actions">
            <button className="send-button" onClick={() => onNavigate?.('chat')}>Continue Studying</button>
            <button className="secondary-button" onClick={() => onNavigate?.('revision')}>Quick Revision</button>
            <button className="secondary-button" onClick={() => onNavigate?.('chat')}>Ask AI Coach</button>
          </div>
        </div>
        <div className="hero-progress-card">
          <span className="eyebrow">Daily target progress</span>
          <strong>{targetProgress ? `${targetProgress}%` : '—'}</strong>
          <p>{targetText}</p>
          <div className="progress-track"><div className="progress-fill" style={{ width: `${targetProgress}%` }} /></div>
          {action?.estimated_minutes ? <small>Estimated action time: {action.estimated_minutes} min</small> : null}
          <small>{trackingActive ? 'Active tracking enabled' : 'Study tracking paused'}</small>
        </div>
      </div>

      <div className="summary-grid">
        <article className="metric-card"><span>Study time today</span><strong>{formatStudyDuration(data.today.study_seconds)}</strong><small>{targetText}</small></article>
        <article className="metric-card"><span>Study time last 7 days</span><strong>{formatStudyDuration(totalWeeklyStudySeconds)}</strong><small>From real activity history</small></article>
        <article className="metric-card"><span>Average mastery</span><strong>{data.mastery.average_mastery != null ? `${Math.round(data.mastery.average_mastery * 100)}%` : '—'}</strong><small>Estimated from mastery evidence</small></article>
        <article className="metric-card"><span>High-risk topics</span><strong>{data.mastery.high_risk_topics.length}</strong><small>Urgent revision focus</small></article>
      </div>

      <div className="chart-row">
        <StudyTrendChart data={studyTrend ?? []} />
        <SubjectDonutChart breakdown={subjectBreakdown} />
      </div>

      <div className="scroll-indicator"><button className="secondary-button" onClick={scrollToDetails}>Explore detailed progress and recommendations</button></div>

      <div ref={detailsRef} className="dashboard-details">
        <RevealSection className="dashboard-section attention-section">
          <header className="section-heading"><div><span className="eyebrow">Subjects requiring attention</span><h2>Urgent review topics</h2></div><button className="secondary-button" onClick={() => onNavigate?.('revision')}>Open Revision Center</button></header>
          {attentionTopics.length ? attentionTopics.map((topic) => (
            <article key={topic.id} className="attention-card">
              <div><span>{topic.subject}</span><em className={`risk-pill risk-${topic.risk_level}`}>{topic.risk_level}</em></div>
              <h3>{topic.topic}</h3>
              <div className="attention-bar"><div style={{ width: `${Math.max(6, topic.mastery_score * 100)}%` }} /></div>
              <small>{topic.mastery_score != null ? `${Math.round(topic.mastery_score * 100)}% mastery` : 'Mastery unavailable'}</small>
              {topic.explanation?.[0] ? <p>{topic.explanation[0]}</p> : null}
            </article>
          )) : <div className="profile-state">No urgent revision topics are available yet.</div>}
        </RevealSection>

        <RevealSection className="dashboard-section actions-section">
          <header className="section-heading"><div><span className="eyebrow">Quick actions</span><h2>Move faster</h2></div></header>
          <div className="action-grid">
            <button className="route-button" onClick={() => onNavigate?.('chat')}><Sparkles size={18} /><span>Ask AI Coach</span></button>
            <button className="route-button" onClick={() => onNavigate?.('revision')}><RefreshCcw size={18} /><span>Start Revision</span></button>
            <button className="route-button" onClick={() => onNavigate?.('quizzes')}><BookOpen size={18} /><span>Take Quiz</span></button>
            <button className="route-button" onClick={() => onNavigate?.('current_affairs')}><Newspaper size={18} /><span>View Current Affairs</span></button>
          </div>
        </RevealSection>

        <RevealSection className="dashboard-section summary-section">
          <header className="section-heading"><div><span className="eyebrow">Revision summary</span><h2>What to focus on next</h2></div></header>
          <div className="summary-card-grid">
            <article className="summary-card"><span>High-risk topics</span><strong>{data.mastery.high_risk_topics.length}</strong></article>
            <article className="summary-card"><span>Weak topics</span><strong>{data.mentor_brief.weaknesses.length}</strong></article>
            <article className="summary-card"><span>Next recommended action</span><strong>{action?.title ?? 'Complete another study session or quiz to refresh the plan.'}</strong><small>{action?.estimated_minutes ? `Estimated ${action.estimated_minutes} min` : 'No estimate available'}</small></article>
          </div>
        </RevealSection>

        <RevealSection className="dashboard-section current-affairs-section">
          <header className="section-heading"><div><span className="eyebrow">Current Affairs preview</span><h2>Accepted stories and risk</h2></div><button className="secondary-button" onClick={() => onNavigate?.('current_affairs')}>Open Current Affairs</button></header>
          {currentArticles.length ? (
            <div className="current-affairs-list">
              {currentArticles.map((article) => (
                <article key={article.id} className="current-affairs-card">
                  <h3>{article.title}</h3>
                  <p>{article.publisher} · {article.subject}</p>
                  <small>{article.publication_date ?? article.retrieved_at.slice(0, 10)}</small>
                </article>
              ))}
            </div>
          ) : <div className="profile-state">No accepted Current Affairs stories are available yet.</div>}
          {currentAffairs ? <div className="current-affairs-meta"><span>{currentAffairs.today_quiz_completed ? 'Quiz complete' : 'Quiz pending'}</span><span>High risk: {currentAffairs.high_risk_article_count}</span><span>Next revision: {currentAffairs.next_revision ? new Date(currentAffairs.next_revision).toLocaleDateString() : '—'}</span></div> : null}
        </RevealSection>

        <RevealSection className="dashboard-section resources-section">
          <header className="section-heading"><div><span className="eyebrow">Recent study material</span><h2>PDFs and roadmaps</h2></div></header>
          <div className="resource-grid">
            <article className="resource-card">
              <h3>Recent PDFs</h3>
              {pdfs.length ? pdfs.map((document) => (
                <p key={document.document_id}>{document.name}<small>{new Date(document.uploaded_at).toLocaleDateString()}</small></p>
              )) : <p>No recent PDFs yet.</p>}
            </article>
            <article className="resource-card">
              <h3>Saved roadmaps</h3>
              {roadmaps.length ? roadmaps.map((roadmap) => (
                <p key={roadmap.id}>{roadmap.title}<small>{roadmap.visual_type.replaceAll('_', ' ')}</small></p>
              )) : <p>No saved roadmaps yet.</p>}
            </article>
          </div>
        </RevealSection>

        <RevealSection className="dashboard-section activity-section">
          <header className="section-heading"><div><span className="eyebrow">Recent activity</span><h2>What happened last</h2></div><button className="secondary-button" onClick={() => onNavigate?.('progress')}>View full progress</button></header>
          {recentActivity.length ? <div className="activity-list">{recentActivity.map((event) => <article key={event.id}><strong>{event.event_type.replaceAll('_', ' ')}</strong><p>{event.topic ?? event.subject ?? 'General'}</p><small>{new Date(event.occurred_at).toLocaleString()}</small></article>)}</div> : <div className="profile-state">No meaningful recent activity recorded yet.</div>}
        </RevealSection>
      </div>

      <div className="dashboard-footer"><small>Last updated {updated?.toLocaleTimeString() ?? '—'}. Mentor insights are estimates based on your study activity, mastery evidence and revision history.</small></div>
    </section>
  )
}
