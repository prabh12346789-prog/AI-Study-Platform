import { BookOpen, BrainCircuit, FileText, Newspaper, RefreshCcw, Settings } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { CurrentAffairsArticle, CurrentAffairsQuizResult, CurrentAffairsRetentionOverview, MasteryOverview as MasteryOverviewData, TopicMastery, ActivitySummary, PdfDocument, VisualRoadmap, getActivitySummary, getCurrentAffairsArticles, getCurrentAffairsQuizAttempts, getCurrentAffairsQuizzes, getCurrentAffairsRetentionOverview, getCurrentAffairsSummary, getRoadmapQuiz, getMasteryOverview, listMasteryTopics, listPdfDocuments, listVisualRoadmaps } from './api'
import { CurrentAffairsQuizPanel } from './CurrentAffairsQuizPanel'
import { MentorPlan } from './MentorPlan'
import { ProfilePanel } from './ProfilePanel'
import { MasteryOverview } from './MasteryOverview'
import { ActivityOverview } from './ActivityOverview'
import type { AppPage } from './AppShell'
import { extractDailyTrend, formatStudyDuration, RevealSection, RiskDonutChart, StudyTrendChart, SubjectDonutChart } from './StudyCharts'

function PageIntro({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return <header className="page-intro"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{copy}</p></header>
}

const roadmapQuizChecks = new Map<string, Promise<boolean>>()

function hasRoadmapQuiz(roadmapId: string) {
  const existing = roadmapQuizChecks.get(roadmapId)
  if (existing) return existing
  const request = getRoadmapQuiz(roadmapId).then(() => true).catch(() => false)
  roadmapQuizChecks.set(roadmapId, request)
  return request
}

function RetentionSnapshot() {
  const [data, setData] = useState<CurrentAffairsRetentionOverview | null>(null)
  useEffect(() => { void getCurrentAffairsRetentionOverview().then(setData).catch(() => setData(null)) }, [])
  return <section className="hub-card retention-snapshot"><div><span>Current Affairs retention</span><strong>{data ? `${Math.round(data.average_retention * 100)}%` : 'No evidence'}</strong></div><div><span>High risk</span><strong>{data?.high_risk_articles.length ?? 0}</strong></div><div><span>Due for revision</span><strong>{data?.due_for_revision.length ?? 0}</strong></div><p>{data?.high_risk_articles[0] ? `Review ${data.high_risk_articles[0].topic} before your next quiz.` : 'Take a grounded Current Affairs quiz to begin retention tracking.'}</p></section>
}

function QuizHistory() {
  const [attempts, setAttempts] = useState<CurrentAffairsQuizResult[]>([])
  const [roadmaps, setRoadmaps] = useState<VisualRoadmap[]>([])
  useEffect(() => { void getCurrentAffairsQuizzes().then(items => Promise.all(items.map(item => getCurrentAffairsQuizAttempts(item.id)))).then(groups => setAttempts(groups.flat())).catch(() => setAttempts([])); void listVisualRoadmaps().then(async items => { const ready: VisualRoadmap[] = []; for (const item of items) { if (await hasRoadmapQuiz(item.id)) ready.push(item) } setRoadmaps(ready) }).catch(() => setRoadmaps([])) }, [])
  return <section className="hub-card"><h2>Previous attempts</h2>{attempts.length ? attempts.map(item => <article key={item.id}><strong>{item.score}/{item.total} · {item.percentage}%</strong><p>Incorrect answers: {item.results.filter(result => !result.correct).length} · Weak topics: {item.weak_topics.join(', ') || 'None'}</p></article>) : <p>No completed Current Affairs attempts yet.</p>}<h3>Roadmap quizzes</h3>{roadmaps.length ? roadmaps.map(item => <p key={item.id}>{item.title} · quiz ready</p>) : <p>No saved roadmap quiz yet.</p>}</section>
}

export function LibraryPage({ onUpload, uploadState, refreshKey, onAsk, onVisual }: { onUpload: () => void; uploadState: string; refreshKey: number; onAsk: (document: PdfDocument) => void; onVisual: (document: PdfDocument) => void }) {
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  async function refresh() {
    setLoading(true); setError('')
    try {
      const items = await listPdfDocuments()
      setDocuments([...new Map(items.map(item => [item.document_id, item])).values()])
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Document library is unavailable.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [refreshKey])
  return <div className="hub-page"><PageIntro eyebrow="Grounded study material" title="My Library" copy="Upload your UPSC PDFs for source-grounded chat and visual roadmaps." /><section className="hub-card library-drop"><FileText size={30} /><h2>Add study material</h2><p>PDF files are processed by the existing local retrieval pipeline. Uploaded material remains the first grounding source.</p><button className="send-button" onClick={onUpload}>Upload PDF</button><small>{uploadState}</small></section><section className="library-section"><header><div><p className="eyebrow">Indexed study material</p><h2>Your documents</h2></div><button className="secondary-button" disabled={loading} onClick={() => void refresh()}>{loading ? 'Loading…' : 'Refresh'}</button></header>{error ? <div className="profile-state error"><strong>Library unavailable</strong><p>{error}</p><button onClick={() => void refresh()}>Retry</button></div> : loading ? <div className="profile-state">Loading uploaded documents…</div> : documents.length === 0 ? <div className="profile-state"><strong>No documents yet</strong><p>Upload a readable text PDF to index it for grounded study.</p></div> : <div className="library-grid">{documents.map(document => <article className="library-document" key={document.document_id}><div className="library-document-title"><FileText size={22} /><div><h3>{document.name}</h3><small>Uploaded {new Date(document.uploaded_at).toLocaleString()}</small></div><span className={`library-status ${document.indexed ? 'indexed' : document.status === 'failed' ? 'failed' : ''}`}>{document.indexed ? 'Indexed' : document.status}</span></div><dl><div><dt>Pages</dt><dd>{document.page_count ?? 'Unavailable'}</dd></div><div><dt>Chunks</dt><dd>{document.chunk_count ?? 'Unavailable'}</dd></div><div><dt>Provider</dt><dd>{document.embedding_provider ?? 'Unavailable'}</dd></div><div><dt>Collection</dt><dd>{document.embedding_collection ?? 'Unavailable'}</dd></div></dl>{document.embedding_model && <p className="library-model">Embedding model: {document.embedding_model}</p>}<div className="roadmap-actions"><button className="send-button" disabled={!document.indexed} onClick={() => onAsk(document)}>Ask AI</button><button className="secondary-button" disabled={!document.indexed} onClick={() => onVisual(document)}>Generate Visual Roadmap</button></div>{!document.indexed && <p className="library-warning">{document.status === 'failed' ? 'Processing failed. Upload a readable text PDF and try again.' : document.status === 'legacy' ? 'Legacy embeddings are not in the active collection. Re-index this PDF before using it.' : 'Processing is not complete yet. Refresh to check again.'}</p>}</article>)}</div>}</section><section className="compact-note"><strong>Use your library</strong><p>Indexed documents can ground AI Study Coach answers and Visual Learning roadmaps.</p></section></div>
}

export function RevisionPage({ trackingActive }: { trackingActive: boolean }) {
  return <div className="hub-page"><PageIntro eyebrow="Focused recovery" title="Revision Center" copy="Review weak mastery, forgetting risk, and mentor actions calculated from reliable evidence." /><MentorPlan /><RetentionSnapshot /><MasteryOverview /><ActivityOverview trackingActive={trackingActive} /></div>
}

export function ProgressPage({ trackingActive }: { trackingActive: boolean }) {
  const [summary, setSummary] = useState<ActivitySummary | null>(null)
  const [overview, setOverview] = useState<MasteryOverviewData | null>(null)
  const [topics, setTopics] = useState<TopicMastery[]>([])
  const [retention, setRetention] = useState<CurrentAffairsRetentionOverview | null>(null)
  const [quizAttempts, setQuizAttempts] = useState<CurrentAffairsQuizResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [activityData, masteryData, masteryTopics, retentionData] = await Promise.all([
        getActivitySummary('7d').catch(() => null),
        getMasteryOverview().catch(() => null),
        listMasteryTopics().catch(() => [] as TopicMastery[]),
        getCurrentAffairsRetentionOverview().catch(() => null),
      ])
      setSummary(activityData)
      setOverview(masteryData)
      setTopics(masteryTopics)
      setRetention(retentionData)

      const quizzes = await getCurrentAffairsQuizzes().catch(() => [])
      if (quizzes.length) {
        const attemptsGroups = await Promise.all(quizzes.map((quiz) => getCurrentAffairsQuizAttempts(quiz.id).catch(() => [] as CurrentAffairsQuizResult[])))
        setQuizAttempts(attemptsGroups.flat())
      } else {
        setQuizAttempts([])
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load progress data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const studyTrend = useMemo(() => (summary ? extractDailyTrend(summary) : null), [summary])
  const mostStudiedSubject = summary?.subject_breakdown.slice().sort((a, b) => b.study_seconds - a.study_seconds)[0]
  const asMostStudied = mostStudiedSubject ? `${mostStudiedSubject.name} · ${formatStudyDuration(mostStudiedSubject.study_seconds)}` : 'No subject study data yet.'
  const attentionTopic = topics.slice().sort((a, b) => a.mastery_score - b.mastery_score)[0]
  const averageQuizAccuracy = quizAttempts.length ? Math.round(quizAttempts.reduce((sum, item) => sum + item.percentage, 0) / quizAttempts.length) : null

  return (
    <div className="hub-page">
      <PageIntro eyebrow="Evidence, not vanity metrics" title="Progress" copy="Seven-day activity, mastery estimates, and revision risk from your real platform usage." />
      <section className="progress-summary-grid">
        <article className="metric-card"><span>Total study time</span><strong>{summary ? formatStudyDuration(summary.total_study_seconds) : '—'}</strong><small>Last seven days from activity</small></article>
        <article className="metric-card"><span>Weekly study</span><strong>{summary ? formatStudyDuration(summary.total_study_seconds) : '—'}</strong><small>Seven-day period summary</small></article>
        <article className="metric-card"><span>Average mastery</span><strong>{overview ? `${Math.round(overview.average_mastery * 100)}%` : '—'}</strong><small>Estimated from mastery evidence</small></article>
        <article className="metric-card"><span>High-risk topics</span><strong>{overview ? overview.high_risk_topics.length : '—'}</strong><small>Current revision risk</small></article>
        {averageQuizAccuracy !== null ? <article className="metric-card"><span>Quiz accuracy</span><strong>{averageQuizAccuracy}%</strong><small>{quizAttempts.length} attempts</small></article> : null}
        {retention ? <article className="metric-card"><span>Current Affairs retention</span><strong>{Math.round(retention.average_retention * 100)}%</strong><small>{retention.high_risk_articles.length} high-risk articles</small></article> : null}
      </section>

      <section className="progress-charts-row">
        <StudyTrendChart data={studyTrend ?? []} />
        <div className="progress-side-charts">
          <SubjectDonutChart breakdown={summary?.subject_breakdown ?? []} />
          <RiskDonutChart topics={topics} />
        </div>
      </section>

      <section className="progress-section">
        <header className="section-heading"><div><span className="eyebrow">Subject analysis</span><h2>Study and mastery by subject</h2></div></header>
        <div className="subject-insights">
          <article className="summary-card"><span>Most studied subject</span><strong>{asMostStudied}</strong></article>
          <article className="summary-card"><span>Subject needing attention</span><strong>{attentionTopic ? `${attentionTopic.subject} · ${Math.round(attentionTopic.mastery_score * 100)}%` : 'No topic-level evidence'}</strong></article>
        </div>
        <div className="subject-bars">
          {overview?.subject_breakdown?.length ? overview.subject_breakdown.map((item) => (
            <div key={item.subject} className="subject-bar-row"><span>{item.subject}</span><i><b style={{ width: `${Math.max(6, item.mastery_score * 100)}%` }} /></i><small>{Math.round(item.mastery_score * 100)}%</small></div>
          )) : <div className="profile-state">No subject mastery breakdown available yet.</div>}
        </div>
      </section>

      <section className="progress-section">
        <header className="section-heading"><div><span className="eyebrow">Quiz analysis</span><h2>Current Affairs performance</h2></div></header>
        {quizAttempts.length ? (
          <div className="quiz-summary"><p>{quizAttempts.length} total attempts · Average accuracy {averageQuizAccuracy}%</p><div className="quiz-attempt-list">{quizAttempts.slice(-3).map((attempt, index) => (
            <article key={`${attempt.id}-${index}`}><strong>{attempt.score}/{attempt.total}</strong><p>{attempt.percentage}%</p></article>
          ))}</div></div>
        ) : <div className="profile-state">No quiz performance history is available yet.</div>}
      </section>

      <section className="progress-section">
        <header className="section-heading"><div><span className="eyebrow">Forgetting risk analysis</span><h2>Topic-level revision risk</h2></div></header>
        {topics.length ? (
          <div className="topic-list">{topics.slice(0, 5).map((topic) => (
            <article key={topic.id} className="topic-row"><div><span>{topic.subject}</span><em className={`risk-pill risk-${topic.risk_level}`}>{topic.risk_level}</em></div><h3>{topic.topic}</h3><div className="attention-bar"><div style={{ width: `${Math.max(6, topic.mastery_score * 100)}%` }} /></div><small>{Math.round(topic.mastery_score * 100)}% mastery · Last revised: {topic.last_revised_at ? new Date(topic.last_revised_at).toLocaleDateString() : 'Unknown'}</small></article>
          ))}</div>
        ) : <div className="profile-state">No topic-level forgetting risk data is available yet.</div>}
      </section>

      <section className="progress-section">
        <header className="section-heading"><div><span className="eyebrow">Current Affairs retention</span><h2>Retention and revision due</h2></div></header>
        {retention ? (
          <div className="retention-summary"><p>{retention.due_for_revision.length} articles due for revision.</p><p>{retention.high_risk_articles.length} articles at high risk.</p><p>{retention.average_retention != null ? `Average retention ${Math.round(retention.average_retention * 100)}%` : 'Average retention unavailable.'}</p></div>
        ) : <div className="profile-state">No Current Affairs retention data is available yet.</div>}
      </section>
    </div>
  )
}

export function ProfilePage({ settings = false }: { settings?: boolean }) {
  return <div className="hub-page"><PageIntro eyebrow={settings ? 'Workspace preferences' : 'Personalisation'} title={settings ? 'Settings' : 'Learner Profile'} copy={settings ? 'Control the same saved learning preferences used by chat and recommendations.' : 'Set language, depth, answer format, daily target, and preferred content type.'} />{settings && <section className="compact-note"><Settings size={18} /><strong>Local-first settings</strong><p>Your preferences apply only inside this study platform.</p></section>}<ProfilePanel /></div>
}

export function QuizzesPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [articles, setArticles] = useState<CurrentAffairsArticle[]>([])
  const today = new Date().toISOString().slice(0, 10)
  useEffect(() => { void getCurrentAffairsArticles().then(setArticles).catch(() => setArticles([])) }, [])
  return <div className="hub-page"><PageIntro eyebrow="Active recall" title="Quizzes" copy="Daily and weekly Current Affairs practice, roadmap recall, incorrect answers, and retention revision." /><CurrentAffairsQuizPanel selectedDate={today} acceptedArticles={articles} /><QuizHistory /><div className="route-card-grid"><button className="route-card" onClick={() => onNavigate('current_affairs')}><Newspaper /><span><strong>Read Current Affairs</strong><small>Return to personalized briefs and grouped issues.</small></span></button><button className="route-card" onClick={() => onNavigate('visual')}><BrainCircuit /><span><strong>Roadmap Quizzes</strong><small>Open a saved roadmap and practice its grounded recall quiz.</small></span></button><button className="route-card" onClick={() => onNavigate('revision')}><RefreshCcw /><span><strong>Previous weaknesses</strong><small>Review incorrect answers and retention risk.</small></span></button></div><section className="compact-note"><BookOpen size={18} /><strong>Original grounded questions</strong><p>Questions come from accepted stored facts, never copied from coaching websites. Reading and saving do not increase mastery.</p></section></div>
}
