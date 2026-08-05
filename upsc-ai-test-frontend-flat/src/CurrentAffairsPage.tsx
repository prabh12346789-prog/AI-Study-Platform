import { useEffect, useMemo, useRef, useState } from 'react'
import { Bookmark, BookOpenCheck, CalendarDays, ExternalLink, Newspaper, RefreshCcw, Search, Sparkles } from 'lucide-react'
import {
  CurrentAffairsArticle, CurrentAffairsContentResponse, CurrentAffairsDatesResponse,
  CurrentAffairsSyncStatusResponse, getCurrentAffairsArticleContent,
  getCurrentAffairsArticles, getCurrentAffairsDates, getCurrentAffairsSyncStatus,
  refreshCurrentAffairs, saveCurrentAffairsArticle,
} from './api'
import type { AppPage } from './AppShell'
import { ContentBlocks, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from './PhaseTwoUI'

const SOURCES = ['All', 'PIB', 'RBI', 'MEA'] as const
const today = () => new Date().toISOString().slice(0, 10)

function clean(items: CurrentAffairsArticle[]) {
  return items.filter(item => !item.is_demo && !/pending backfill|image only pdf|mode test|internal reader test/i.test(item.title))
}

function safeMessage(reason: unknown) {
  return reason instanceof Error && /failed \(5|network|fetch/i.test(reason.message) ? 'The Current Affairs service is temporarily unavailable.' : 'Official Current Affairs could not be loaded.'
}

export function CurrentAffairsPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [date, setDate] = useState(today())
  const [source, setSource] = useState<(typeof SOURCES)[number]>('All')
  const [subject, setSubject] = useState('All Subjects')
  const [search, setSearch] = useState('')
  const [savedOnly, setSavedOnly] = useState(false)
  const [articles, setArticles] = useState<CurrentAffairsArticle[]>([])
  const [dates, setDates] = useState<CurrentAffairsDatesResponse | null>(null)
  const [status, setStatus] = useState<CurrentAffairsSyncStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [dateReady, setDateReady] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [reader, setReader] = useState<CurrentAffairsArticle | null>(null)
  const [content, setContent] = useState<CurrentAffairsContentResponse | null>(null)
  const [readerLoading, setReaderLoading] = useState(false)
  const manualDate = useRef(false)
  const requestSequence = useRef(0)
  const articlesRef = useRef<HTMLDivElement | null>(null)
  const scrollAfterLoad = useRef(false)

  async function loadMetadata() {
    const [dateData, statusData] = await Promise.all([getCurrentAffairsDates(), getCurrentAffairsSyncStatus().catch(() => null)])
    setDates(dateData); setStatus(statusData)
    if (!manualDate.current) setDate(dateData.latest_available_date || today())
    setDateReady(true)
  }

  async function loadArticles(requestedDate = date) {
    const requestId = ++requestSequence.current
    setLoading(true); setError('')
    const params = new URLSearchParams({ date: requestedDate })
    if (subject !== 'All Subjects') params.set('subject', subject)
    if (search.trim()) params.set('search', search.trim())
    try {
      const result = clean(await getCurrentAffairsArticles(params.toString()))
      if (requestId !== requestSequence.current) return
      setArticles(result)
      if (scrollAfterLoad.current && result.length) {
        scrollAfterLoad.current = false
        window.requestAnimationFrame(() => articlesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
      }
    }
    catch (reason) { if (requestId === requestSequence.current) setError(safeMessage(reason)) }
    finally { if (requestId === requestSequence.current) setLoading(false) }
  }

  useEffect(() => { void loadMetadata().catch(reason => { setError(safeMessage(reason)); setLoading(false) }) }, [])
  useEffect(() => { if (dateReady && date) void loadArticles() }, [dateReady, date, subject, search])

  const subjects = useMemo(() => ['All Subjects', ...Array.from(new Set(articles.map(item => item.subject).filter(Boolean))).sort()], [articles])
  const visible = useMemo(() => articles.filter(item => (source === 'All' || item.publisher.toUpperCase() === source) && (!savedOnly || item.saved)), [articles, source, savedOnly])
  const savedCount = articles.filter(item => item.saved).length

  async function refresh() {
    setRefreshing(true); setError('')
    try { await refreshCurrentAffairs(); await loadMetadata() }
    catch (reason) { setError(safeMessage(reason)) }
    finally { setRefreshing(false) }
  }

  async function toggleSave(item: CurrentAffairsArticle) {
    try { await saveCurrentAffairsArticle(item.id, item.saved); setArticles(old => old.map(article => article.id === item.id ? { ...article, saved: !article.saved } : article)) }
    catch { setError('The article could not be saved. Please retry.') }
  }

  async function openReader(item: CurrentAffairsArticle) {
    setReader(item); setContent(null); setReaderLoading(true)
    try { setContent(await getCurrentAffairsArticleContent(item.id)) } finally { setReaderLoading(false) }
  }

  function askCoach(item: CurrentAffairsArticle) {
    sessionStorage.setItem('upsc-coach-draft', `Explain the UPSC relevance of this verified Current Affairs article: ${item.title}`)
    onNavigate('chat')
  }

  const sourceStates = ['PIB', 'RBI', 'MEA'].map(name => ({ name, ok: status?.successful_sources.includes(name), unavailable: status?.unavailable_sources.includes(name) }))
  const viewLatest = () => {
    const latest = dates?.latest_available_date
    if (!latest) return
    scrollAfterLoad.current = true
    if (date === latest) void loadArticles(latest)
    else setDate(latest)
  }

  return <div className="p2-page ca-redesign">
    <PageHeader eyebrow="Verified official sources" title="Current Affairs" subtitle="Daily, curated UPSC updates from PIB, RBI and MEA." actions={<button className="p2-primary" onClick={() => void refresh()} disabled={refreshing}><RefreshCcw size={15} />{refreshing ? 'Refreshing…' : 'Refresh sources'}</button>} />

    <section className="ca-metrics p2-card">
      <div><Newspaper /><span>Accepted articles<strong>{dates?.total_active_records ?? status?.accepted_article_count ?? 0}</strong></span></div>
      <div><BookOpenCheck /><span>Active sources<strong>{status?.successful_sources.length ?? 0}</strong></span></div>
      <div><RefreshCcw /><span>Last synchronized<strong>{status?.last_synchronized_at ? new Date(status.last_synchronized_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Not available'}</strong></span></div>
      <div><Bookmark /><span>Saved on this date<strong>{savedCount}</strong></span></div>
    </section>

    <section className="p2-filter-bar" aria-label="Current Affairs filters">
      <label><span>Date</span><input type="date" value={date} onChange={event => { manualDate.current = true; setDate(event.target.value) }} /></label>
      <button onClick={viewLatest}>View latest available</button>
      <label><span>Source</span><select value={source} onChange={event => setSource(event.target.value as typeof source)}>{SOURCES.map(item => <option key={item}>{item}</option>)}</select></label>
      <label><span>Subject</span><select value={subject} onChange={event => setSubject(event.target.value)}>{subjects.map(item => <option key={item}>{item}</option>)}</select></label>
      <label className="p2-search"><Search size={14} /><input aria-label="Search Current Affairs" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search articles…" /></label>
      <label className="p2-check"><input type="checkbox" checked={savedOnly} onChange={event => setSavedOnly(event.target.checked)} /> Saved only</label>
    </section>

    {error && <ErrorState description={error} retry={() => void loadArticles()} />}
    <div className="ca-layout" ref={articlesRef}><main>{loading ? <LoadingState label="Loading official Current Affairs…" /> : visible.length ? <div className="ca-article-list">{visible.map(item => <article className="ca-official-card p2-card" key={item.id}>
      <div className="ca-card-meta"><StatusBadge tone={item.publisher.toUpperCase() === 'PIB' ? 'amber' : item.publisher.toUpperCase() === 'RBI' ? 'blue' : 'green'}>{item.publisher}</StatusBadge><StatusBadge tone="violet">{item.subject}</StatusBadge><time>{item.publication_date ?? new Date(item.retrieved_at).toLocaleDateString()}</time></div>
      <h2>{item.title}</h2><p>{item.summary || 'A concise verified summary is not available for this article.'}</p>
      {item.syllabus_tags_json?.length ? <small className="ca-gs-tags">{item.syllabus_tags_json.join(' · ')}</small> : null}
      <footer><button onClick={() => void toggleSave(item)} aria-pressed={item.saved}><Bookmark size={14} />{item.saved ? 'Saved' : 'Save'}</button><button onClick={() => void openReader(item)}>Read material</button><a href={item.source_url} target="_blank" rel="noreferrer">Read original <ExternalLink size={13} /></a><button onClick={() => askCoach(item)}><Sparkles size={14} />Ask AI</button><button onClick={() => onNavigate('tests')}>Generate quiz</button></footer>
    </article>)}</div> : <EmptyState title={articles.length ? 'No articles match the selected filters.' : 'No verified Current Affairs were published for this date.'} description={articles.length ? 'Change the source, subject, search, or saved-only filter.' : `No accepted official records are available for ${date}.`} action={<button onClick={viewLatest}>View Latest Available</button>} />}</main>
      <aside className="ca-status-panel p2-card"><h2>Source status</h2>{sourceStates.map(item => <div key={item.name}><span>{item.name}</span><StatusBadge tone={item.ok ? 'green' : item.unavailable ? 'amber' : 'blue'}>{item.ok ? 'Operational' : item.unavailable ? 'Partial failure' : 'Not checked'}</StatusBadge></div>)}<p><CalendarDays size={14} />{status?.last_synchronized_at ? `Updated ${new Date(status.last_synchronized_at).toLocaleString()}` : 'No synchronization timestamp available'}</p></aside>
    </div>

    {reader && <div className="p2-dialog" role="dialog" aria-modal="true" aria-label={reader.title}><article><header><div><StatusBadge>{reader.publisher}</StatusBadge><h2>{reader.title}</h2></div><button aria-label="Close reader" onClick={() => setReader(null)}>×</button></header>{readerLoading ? <LoadingState label="Loading article…" /> : content?.content_blocks?.length ? <ContentBlocks blocks={content.content_blocks} /> : <EmptyState title="Extracted material unavailable" description="Use the verified original-source link to read this article." />}<footer><button onClick={() => void toggleSave(reader)}>{reader.saved ? 'Unsave' : 'Save'}</button><a href={reader.source_url} target="_blank" rel="noreferrer">Open official source</a></footer></article></div>}
  </div>
}
