import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowRight, BookOpen, BrainCircuit, CalendarClock, CheckCircle2, Clock3,
  FileText, Gauge, Newspaper, RefreshCcw, Search, Sparkles, Target, TrendingUp,
} from 'lucide-react'
import {
  ActivitySummary, CurrentAffairsArticle, CurrentAffairsSummary, PdfDocument,
  VisualRoadmap, getActivitySummary, getCurrentAffairsArticles,
  getCurrentAffairsSummary, getMentorDashboard, listPdfDocuments,
  listVisualRoadmaps, MentorDashboardData,
} from './api'
import type { AppPage } from './AppShell'
import { extractDailyTrend, formatStudyDuration, formatStudyHours, StudyTrendChart, SubjectDonutChart } from './StudyCharts'

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
  const [rangeActivity, setRangeActivity] = useState<Record<'7d' | '30d' | '90d', ActivitySummary | null>>({ '7d': null, '30d': null, '90d': null })
  const [trendRange, setTrendRange] = useState<'7d' | '30d' | '90d'>('7d')
  const [longTermActivity, setLongTermActivity] = useState<ActivitySummary | null>(null)
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
      const [dashboard, summary, monthSummary, quarterSummary, history, caSummary, caArticles, documents, maps] = await Promise.all([
        getMentorDashboard(), getActivitySummary('7d'), getActivitySummary('30d'), getActivitySummary('90d'), getActivitySummary('all'),
        getCurrentAffairsSummary().catch(() => null), getCurrentAffairsArticles().catch(() => []),
        listPdfDocuments().catch(() => []), listVisualRoadmaps().catch(() => []),
      ])
      setData(dashboard)
      setActivity(summary)
      setRangeActivity({ '7d': summary, '30d': monthSummary, '90d': quarterSummary })
      setLongTermActivity(history)
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

  const selectedActivity = rangeActivity[trendRange] ?? activity
  const trend = useMemo(() => selectedActivity ? extractDailyTrend(selectedActivity, trendRange === '7d' ? 7 : trendRange === '30d' ? 30 : 90) : [], [selectedActivity, trendRange])
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
  const historyDays = longTermActivity?.total_learning_days ?? longTermActivity?.daily_breakdown?.filter(day => day.event_count > 0).length ?? 0
  const historyStart = longTermActivity?.first_activity_at ? new Date(longTermActivity.first_activity_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' }) : 'your first activity'
  const monthHistory = new Map((longTermActivity?.monthly_breakdown ?? []).map(item => [item.month, item]))
  const recentMonths = Array.from({ length: 12 }, (_, index) => {
    const date = new Date(); date.setDate(1); date.setMonth(date.getMonth() - (11 - index))
    const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
    return monthHistory.get(month) ?? { month, study_seconds: 0, event_count: 0, searches_made: 0, questions_asked: 0 }
  })

  const quickActions: Array<{ label: string; detail: string; page: AppPage; icon: typeof Sparkles; tone: string }> = [
    { label: 'AI Coach', detail: 'Explanations, answer writing and guided study', page: 'chat', icon: Sparkles, tone: 'violet' },
    { label: 'Practice Test', detail: 'Prelims, Current Affairs and Mains practice', page: 'tests', icon: CheckCircle2, tone: 'blue' },
    { label: 'Current Affairs', detail: 'Verified stories with exam relevance', page: 'current_affairs', icon: Newspaper, tone: 'cyan' },
    { label: 'UPSC Books', detail: 'Read extracted Prelims and Mains material', page: 'upsc_books', icon: BookOpen, tone: 'orange' },
    { label: 'Revision', detail: 'Recall topics due from forgetting risk', page: 'revision', icon: RefreshCcw, tone: 'green' },
    { label: 'Visual Learning', detail: 'Build a grounded visual roadmap', page: 'visual', icon: BrainCircuit, tone: 'pink' },
  ]

  return (
    <section className="mentor-dashboard reference-dashboard">
      <header className="reference-welcome">
        <div><h1>{greeting()} <span aria-hidden="true">👋</span></h1><p>{data.mentor_brief.summary}</p></div>
        <div className="reference-target"><Target size={20} /><span>Daily target<strong>{data.profile.daily_target_minutes ? `${data.profile.daily_target_minutes} min` : 'Not set'}</strong></span><i className={trackingActive ? 'active' : ''}>{trackingActive ? 'Tracking' : 'Paused'}</i></div>
      </header>

      <div className="reference-top-grid">
        <article className="reference-card goal-card">
          <div className="card-title-row"><h2>Study Goal Progress</h2><span>7-day plan</span></div>
          <div className="goal-body">
            <div className="goal-ring" style={{ '--goal': `${weeklyProgress * 3.6}deg` } as React.CSSProperties}><strong>{weeklyTarget ? `${weeklyProgress}%` : '—'}</strong><small>Goal</small></div>
            <div className="goal-copy"><strong>{formatStudyDuration(weeklySeconds)} <span>/ {weeklyTarget ? formatStudyDuration(weeklyTarget) : 'target not set'}</span></strong><small>Only consented study activity completed inside this platform is counted.</small><div className="wide-progress"><i style={{ width: `${weeklyProgress}%` }} /></div><p><Clock3 size={13} />{weeklyTarget ? `${formatStudyDuration(Math.max(0, weeklyTarget - weeklySeconds))} remaining · ${data.profile.daily_target_minutes} min daily target` : 'Set a daily target in Profile for pacing guidance'}</p></div>
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
            <div className="card-title-row"><h2>Study Overview</h2><div className="chart-range" aria-label="Study chart range">{(['7d', '30d', '90d'] as const).map(range => <button key={range} className={trendRange === range ? 'active' : ''} aria-pressed={trendRange === range} onClick={() => setTrendRange(range)}>{range}</button>)}</div></div>
            <div className="overview-metrics">
              <div><Clock3 /><span>Total Study Time<strong>{formatStudyHours(selectedActivity?.total_study_seconds ?? 0)}</strong><small>Recorded in selected range</small></span></div>
              <div><TrendingUp /><span>Questions Asked<strong>{selectedActivity?.questions_asked ?? 0}</strong><small>Coach interactions</small></span></div>
              <div><BookOpen /><span>Subjects Studied<strong>{selectedActivity?.subjects_studied ?? 0}</strong><small>Unique subjects</small></span></div>
              <div><Gauge /><span>Average Mastery<strong>{data.mastery.subject_breakdown.length ? `${averageMastery}%` : '—'}</strong><small>Evidence-based estimate</small></span></div>
              <div><RefreshCcw /><span>High-risk Topics<strong>{data.mastery.high_risk_topics.length}</strong><small>Prioritize revision</small></span></div>
            </div>
            <StudyTrendChart data={trend} />
          </article>

          <div className="reference-split-grid">
            <article className="reference-card mastery-card">
              <div className="card-title-row"><h2>Subject Study Time · {trendRange}</h2><button onClick={() => onNavigate?.('progress')}>View details</button></div>
              <SubjectDonutChart breakdown={selectedActivity?.subject_breakdown ?? []} />
            </article>
            <article className="reference-card resource-card-compact">
              <div className="card-title-row"><h2>Recent Study Material</h2><button onClick={() => onNavigate?.('library')}>Library</button></div>
              {pdfs.length || roadmaps.length ? <div className="compact-list">
                {pdfs.map(pdf => <div key={pdf.document_id}><FileText size={16} /><span><strong>{pdf.name}</strong><small>{pdf.indexed ? `Ready for grounded questions · ${pdf.page_count ?? 'unknown'} pages` : `Processing incomplete · ${pdf.status}`}</small></span></div>)}
                {roadmaps.map(map => <div key={map.id}><BrainCircuit size={16} /><span><strong>{map.title}</strong><small>{map.subject} · {map.visual_type.replaceAll('_', ' ')} · {map.structure.nodes.length} learning points</small></span></div>)}
              </div> : <div className="reference-empty">No PDFs or visual roadmaps are available yet.</div>}
            </article>
          </div>
        </div>

        <aside className="reference-right-column">
          <article className="reference-card current-snapshot">
            <div className="card-title-row"><h2>Current Affairs Snapshot</h2><button onClick={() => onNavigate?.('current_affairs')}>View all <ArrowRight size={13} /></button></div>
            {articles.length ? <div className="snapshot-list">{articles.map(article => <button key={article.id} onClick={() => onNavigate?.('current_affairs')}><span className={`article-accent ${article.importance_level}`} /><span><small>{article.publisher} · {article.subject} · {dateLabel(article.publication_date ?? article.retrieved_at)}</small><strong>{article.title}</strong><em>{article.importance_level} priority · Open exam relevance</em></span></button>)}</div> : <div className="reference-empty">No accepted stories yet. Refresh Current Affairs after official-source ingestion.</div>}
            {currentAffairs ? <div className="snapshot-meta"><span>{currentAffairs.today_quiz_completed ? 'Today’s quiz complete' : 'Today’s quiz pending'}</span><span>{currentAffairs.high_risk_article_count} high-risk</span></div> : null}
          </article>

          <article className="reference-card revision-card">
            <div className="card-title-row"><h2>Upcoming Revision</h2><button onClick={() => onNavigate?.('revision')}>View all</button></div>
            {revisionTopics.length ? <div className="revision-list">{revisionTopics.map(topic => <button key={topic.id} onClick={() => onNavigate?.('revision')}><CalendarClock size={17} /><span><strong>{topic.subject} — {topic.topic}</strong><small>{topic.next_revision_at ? `Due ${dateLabel(topic.next_revision_at)}` : 'Review recommended'} · {Math.round(topic.mastery_score * 100)}% mastery · {Math.round(topic.forgetting_risk * 100)}% risk</small><em>{topic.explanation?.[0] ?? 'Timing is based on your latest mastery evidence.'}</em></span><i className={`risk-${topic.risk_level}`}>{topic.risk_level}</i></button>)}</div> : <div className="reference-empty">No topics are due. Complete a quiz or recall session to create a revision schedule.</div>}
          </article>
        </aside>
      </div>

      <article className="reference-card learning-history-card">
        <div className="card-title-row"><h2><TrendingUp size={17} /> Your Long-Term Learning Journey</h2><button onClick={() => onNavigate?.('progress')}>Full analytics <ArrowRight size={13} /></button></div>
        <p className="history-intro">Lifetime record since {historyStart}. This private history contains only consented activity inside UPSC AI Mentor and continues across months and years.</p>
        <div className="history-metrics">
          <div><Clock3 /><span>Lifetime study<strong>{formatStudyHours(longTermActivity?.total_study_seconds ?? 0)}</strong><small>All recorded focused sessions</small></span></div>
          <div><CalendarClock /><span>Active days<strong>{historyDays}</strong><small>Days with recorded learning activity</small></span></div>
          <div><TrendingUp /><span>Questions asked<strong>{longTermActivity?.questions_asked ?? 0}</strong><small>Your AI Coach learning trail</small></span></div>
          <div><Search /><span>Platform searches<strong>{longTermActivity?.searches_made ?? 0}</strong><small>Books, Current Affairs and navigation</small></span></div>
          <div><BookOpen /><span>Subjects explored<strong>{longTermActivity?.subjects_studied ?? 0}</strong><small>Most studied: {longTermActivity?.top_subject ?? 'Not enough data'}</small></span></div>
        </div>
        <div className="year-history"><strong>Last 12 months</strong>{recentMonths.length ? <div>{recentMonths.map(month => { const peak = Math.max(1, ...recentMonths.map(item => item.study_seconds)); return <span key={month.month} title={`${month.month}: ${formatStudyDuration(month.study_seconds)}, ${month.searches_made} searches, ${month.questions_asked} questions`}><i style={{ height: `${Math.max(6, Math.round(month.study_seconds / peak * 100))}%` }} /><small>{new Date(`${month.month}-01`).toLocaleDateString(undefined, { month: 'short' })}</small></span> })}</div> : <p>Monthly progress bars will appear as your learning history grows.</p>}</div>
        <div className="search-history"><strong>Topics you searched</strong>{longTermActivity?.top_searches?.length ? <div>{longTermActivity.top_searches.slice(0, 8).map(term => <button key={term} onClick={() => onNavigate?.('chat')}><Search size={12} />{term}</button>)}</div> : <p>Your searches will appear here after you use Books, Current Affairs, or the workspace search.</p>}</div>
      </article>

      <div className="reference-bottom-grid">
        <article className="reference-card recommendation-card">
          <div className="card-title-row"><h2><Sparkles size={17} /> AI Recommendations</h2></div>
          {recommendations.length ? <div className="recommendation-list">{recommendations.map((item) => item && <button key={item.id} onClick={() => onNavigate?.(item.action_type.includes('quiz') ? 'tests' : 'revision')}><Target size={18} /><span><strong>{item.title}</strong><small>{item.reason[0] ?? 'Recommended from your current study state.'}</small><em>{item.estimated_minutes} min · {item.priority_level} priority · {item.action_type.replaceAll('_', ' ')}</em></span></button>)}</div> : <div className="reference-empty">Complete a study session or test to receive a reasoned recommendation and time estimate.</div>}
        </article>
        <article className="reference-card insight-card">
          <div className="card-title-row"><h2><Sparkles size={17} /> Smart Insights</h2></div>
          <div className="insight-grid">
            <div><TrendingUp /><span>Top subject<strong>{activity?.top_subject ?? 'No data yet'}</strong><small>{activity?.top_topic ? `Most active topic: ${activity.top_topic}` : 'Activity will reveal your focus area'}</small></span></div>
            <div><Clock3 /><span>Today’s study<strong>{formatStudyDuration(data.today.study_seconds)}</strong><small>{data.today.questions_asked} questions · {data.today.subjects_studied} subjects</small></span></div>
            <div><Target /><span>Next action<strong>{action?.estimated_minutes ? `${action.estimated_minutes} min` : 'Not available'}</strong><small>{action?.title ?? 'Complete more activity to unlock guidance'}</small></span></div>
          </div>
        </article>
      </div>
    </section>
  )
}
