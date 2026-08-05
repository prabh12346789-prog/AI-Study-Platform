import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowRight, BookOpen, BrainCircuit, CalendarClock, CheckCircle2, Clock3,
  FileText, Gauge, Newspaper, RefreshCcw, Sparkles, Target, TrendingUp,
} from 'lucide-react'
import {
  ActivitySummary, CurrentAffairsArticle, CurrentAffairsSummary, PdfDocument,
  VisualRoadmap, getActivitySummary, getCurrentAffairsArticles,
  getCurrentAffairsSummary, getMentorDashboard, listPdfDocuments,
  listVisualRoadmaps, MentorDashboardData,
} from './api'
import type { AppPage } from './AppShell'
import { extractDailyTrend, formatStudyDuration, StudyTrendChart, SubjectDonutChart } from './StudyCharts'

const riskOrder: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 }

function greeting() {
  const hour = new Date().getHours()
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
}

function dateLabel(value: string | null | undefined) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function MentorDashboard({ trackingActive, onNavigate }: { trackingActive: boolean; onNavigate?: (page: AppPage) => void }) {
  const [data, setData] = useState<MentorDashboardData | null>(null)
  const [activity, setActivity] = useState<ActivitySummary | null>(null)
  const [currentAffairs, setCurrentAffairs] = useState<CurrentAffairsSummary | null>(null)
  const [articles, setArticles] = useState<CurrentAffairsArticle[]>([])
  const [pdfs, setPdfs] = useState<PdfDocument[]>([])
  const [roadmaps, setRoadmaps] = useState<VisualRoadmap[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [dashboard, summary, caSummary, caArticles, documents, maps] = await Promise.all([
        getMentorDashboard(), getActivitySummary('7d'),
        getCurrentAffairsSummary().catch(() => null), getCurrentAffairsArticles().catch(() => []),
        listPdfDocuments().catch(() => []), listVisualRoadmaps().catch(() => []),
      ])
      setData(dashboard)
      setActivity(summary)
      setCurrentAffairs(caSummary)
      setArticles(caArticles.slice(0, 3))
      setPdfs(documents.slice(0, 3))
      setRoadmaps(maps.slice(0, 3))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load the dashboard.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    const listener = () => void refresh()
    window.addEventListener('mentor-data-changed', listener)
    return () => window.removeEventListener('mentor-data-changed', listener)
  }, [refresh])

  const trend = useMemo(() => activity ? extractDailyTrend(activity) : [], [activity])
  const revisionTopics = useMemo(() => {
    if (!data) return []
    return [...data.mastery.high_risk_topics]
      .sort((a, b) => (riskOrder[a.risk_level] ?? 4) - (riskOrder[b.risk_level] ?? 4))
      .slice(0, 3)
  }, [data])
  const recommendations = useMemo(() => {
    if (!data) return []
    return [data.recommendations.primary, ...data.recommendations.alternatives].filter(Boolean).slice(0, 3)
  }, [data])

  if (loading) return <section className="mentor-dashboard reference-dashboard dashboard-skeleton">Loading your mentor dashboard…</section>
  if (error && !data) return <section className="mentor-dashboard reference-dashboard profile-state error">{error}<button className="icon-button" onClick={() => void refresh()}>Retry</button></section>
  if (!data) return null

  const weeklySeconds = activity?.total_study_seconds ?? 0
  const weeklyTarget = data.profile.daily_target_minutes * 7 * 60
  const weeklyProgress = weeklyTarget ? Math.min(100, Math.round(weeklySeconds / weeklyTarget * 100)) : 0
  const averageMastery = Math.round((data.mastery.average_mastery ?? 0) * 100)
  const action = data.recommendations.primary

  const quickActions: Array<{ label: string; detail: string; page: AppPage; icon: typeof Sparkles; tone: string }> = [
    { label: 'AI Coach', detail: 'Ask anything', page: 'chat', icon: Sparkles, tone: 'violet' },
    { label: 'Practice Test', detail: 'Test yourself', page: 'tests', icon: CheckCircle2, tone: 'blue' },
    { label: 'Current Affairs', detail: 'Latest updates', page: 'current_affairs', icon: Newspaper, tone: 'cyan' },
    { label: 'UPSC Books', detail: 'Study material', page: 'upsc_books', icon: BookOpen, tone: 'orange' },
    { label: 'Revision', detail: 'Review due topics', page: 'revision', icon: RefreshCcw, tone: 'green' },
    { label: 'Visual Learning', detail: 'Build a roadmap', page: 'visual', icon: BrainCircuit, tone: 'pink' },
  ]

  return (
    <section className="mentor-dashboard reference-dashboard">
      <header className="reference-welcome">
        <div><h1>{greeting()} <span aria-hidden="true">👋</span></h1><p>{data.mentor_brief.summary}</p></div>
        <div className="reference-target"><Target size={20} /><span>Daily target<strong>{data.profile.daily_target_minutes ? `${data.profile.daily_target_minutes} min` : 'Not set'}</strong></span><i className={trackingActive ? 'active' : ''}>{trackingActive ? 'Tracking' : 'Paused'}</i></div>
      </header>

      <div className="reference-top-grid">
        <article className="reference-card goal-card">
          <div className="card-title-row"><h2>Study Goal Progress</h2><span>This week</span></div>
          <div className="goal-body">
            <div className="goal-ring" style={{ '--goal': `${weeklyProgress * 3.6}deg` } as React.CSSProperties}><strong>{weeklyTarget ? `${weeklyProgress}%` : '—'}</strong><small>Goal</small></div>
            <div className="goal-copy"><strong>{formatStudyDuration(weeklySeconds)} <span>/ {weeklyTarget ? formatStudyDuration(weeklyTarget) : 'target not set'}</span></strong><small>Study time from recorded activity</small><div className="wide-progress"><i style={{ width: `${weeklyProgress}%` }} /></div><p><Clock3 size={13} />{weeklyTarget ? `${formatStudyDuration(Math.max(0, weeklyTarget - weeklySeconds))} remaining` : 'Set a daily target in Profile'}</p></div>
          </div>
        </article>

        <article className="reference-card quick-actions-card">
          <div className="card-title-row"><h2>Quick Actions</h2></div>
          <div className="reference-actions">{quickActions.map(({ label, detail, page, icon: Icon, tone }) => <button key={page} onClick={() => onNavigate?.(page)}><i className={tone}><Icon size={18} /></i><strong>{label}</strong><small>{detail}</small></button>)}</div>
        </article>
      </div>

      <div className="reference-main-grid">
        <div className="reference-left-column">
          <article className="reference-card overview-card">
            <div className="card-title-row"><h2>Study Overview</h2><span>Last 7 days</span></div>
            <div className="overview-metrics">
              <div><Clock3 /><span>Total Study Time<strong>{formatStudyDuration(weeklySeconds)}</strong></span></div>
              <div><TrendingUp /><span>Questions Asked<strong>{activity?.questions_asked ?? 0}</strong></span></div>
              <div><BookOpen /><span>Subjects Studied<strong>{activity?.subjects_studied ?? 0}</strong></span></div>
              <div><Gauge /><span>Average Mastery<strong>{data.mastery.subject_breakdown.length ? `${averageMastery}%` : '—'}</strong></span></div>
              <div><RefreshCcw /><span>High-risk Topics<strong>{data.mastery.high_risk_topics.length}</strong></span></div>
            </div>
            <StudyTrendChart data={trend} />
          </article>

          <div className="reference-split-grid">
            <article className="reference-card mastery-card">
              <div className="card-title-row"><h2>Subject Study Time</h2><button onClick={() => onNavigate?.('progress')}>View details</button></div>
              <SubjectDonutChart breakdown={activity?.subject_breakdown ?? []} />
            </article>
            <article className="reference-card resource-card-compact">
              <div className="card-title-row"><h2>Recent Study Material</h2><button onClick={() => onNavigate?.('library')}>Library</button></div>
              {pdfs.length || roadmaps.length ? <div className="compact-list">
                {pdfs.map(pdf => <div key={pdf.document_id}><FileText size={16} /><span><strong>{pdf.name}</strong><small>{pdf.indexed ? 'Indexed PDF' : 'PDF processing incomplete'}</small></span></div>)}
                {roadmaps.map(map => <div key={map.id}><BrainCircuit size={16} /><span><strong>{map.title}</strong><small>{map.visual_type.replaceAll('_', ' ')}</small></span></div>)}
              </div> : <div className="reference-empty">No PDFs or visual roadmaps are available yet.</div>}
            </article>
          </div>
        </div>

        <aside className="reference-right-column">
          <article className="reference-card current-snapshot">
            <div className="card-title-row"><h2>Current Affairs Snapshot</h2><button onClick={() => onNavigate?.('current_affairs')}>View all <ArrowRight size={13} /></button></div>
            {articles.length ? <div className="snapshot-list">{articles.map(article => <button key={article.id} onClick={() => onNavigate?.('current_affairs')}><span className={`article-accent ${article.importance_level}`} /><span><small>{article.subject} · {dateLabel(article.publication_date ?? article.retrieved_at)}</small><strong>{article.title}</strong></span></button>)}</div> : <div className="reference-empty">No accepted Current Affairs stories are available yet.</div>}
            {currentAffairs ? <div className="snapshot-meta"><span>{currentAffairs.today_quiz_completed ? 'Today’s quiz complete' : 'Today’s quiz pending'}</span><span>{currentAffairs.high_risk_article_count} high-risk</span></div> : null}
          </article>

          <article className="reference-card revision-card">
            <div className="card-title-row"><h2>Upcoming Revision</h2><button onClick={() => onNavigate?.('revision')}>View all</button></div>
            {revisionTopics.length ? <div className="revision-list">{revisionTopics.map(topic => <button key={topic.id} onClick={() => onNavigate?.('revision')}><CalendarClock size={17} /><span><strong>{topic.subject} — {topic.topic}</strong><small>{topic.next_revision_at ? `Due ${dateLabel(topic.next_revision_at)}` : 'Review recommended'} · {Math.round(topic.mastery_score * 100)}% mastery</small></span><i className={`risk-${topic.risk_level}`}>{topic.risk_level}</i></button>)}</div> : <div className="reference-empty">No topics are currently due for revision.</div>}
          </article>
        </aside>
      </div>

      <div className="reference-bottom-grid">
        <article className="reference-card recommendation-card">
          <div className="card-title-row"><h2><Sparkles size={17} /> AI Recommendations</h2></div>
          {recommendations.length ? <div className="recommendation-list">{recommendations.map((item) => item && <button key={item.id} onClick={() => onNavigate?.(item.action_type.includes('quiz') ? 'tests' : 'revision')}><Target size={18} /><span><strong>{item.title}</strong><small>{item.reason[0] ?? 'Recommended from your current study state.'}</small></span></button>)}</div> : <div className="reference-empty">Complete a study session or test to receive a personalized recommendation.</div>}
        </article>
        <article className="reference-card insight-card">
          <div className="card-title-row"><h2><Sparkles size={17} /> Smart Insights</h2></div>
          <div className="insight-grid">
            <div><TrendingUp /><span>Top subject<strong>{activity?.top_subject ?? 'No data yet'}</strong></span></div>
            <div><Clock3 /><span>Today’s study<strong>{formatStudyDuration(data.today.study_seconds)}</strong></span></div>
            <div><Target /><span>Next action<strong>{action?.estimated_minutes ? `${action.estimated_minutes} min` : 'Not available'}</strong></span></div>
          </div>
        </article>
      </div>
    </section>
  )
}
