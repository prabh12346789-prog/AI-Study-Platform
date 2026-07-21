import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  CurrentAffairsArticle,
  CurrentAffairsBrief,
  CurrentAffairsContentResponse,
  CurrentAffairsSummary,
  getCurrentAffairsArticle,
  getCurrentAffairsArticleContent,
  getCurrentAffairsArticles,
  getCurrentAffairsBriefOptional,
  getCurrentAffairsSummary,
  saveCurrentAffairsArticle
} from './api'
import { resolveInitialCurrentAffairsDate } from './currentAffairsDate'
import type { AppPage } from './AppShell'

type SectionTab = 'day' | 'weekly' | 'monthly' | 'subject' | 'qa'

const UPSC_SUBJECTS = [
  'Polity and Governance',
  'Economy',
  'History',
  'Geography',
  'Environment and Ecology',
  'Science and Technology',
  'International Relations',
  'Society',
  'Social Justice',
  'Internal Security',
  'Disaster Management',
  'Ethics',
  'Art and Culture',
  'Agriculture',
  'Government Schemes',
  'Reports and Indices',
  'Places in News',
  'Other'
]

const today = () => new Date().toISOString().slice(0, 10)

export function CurrentAffairsPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [activeTab, setActiveTab] = useState<SectionTab>('day')
  const [date, setDate] = useState(today())
  const [search, setSearch] = useState('')
  const [subjectFilter, setSubjectFilter] = useState('')
  const [qaFilter, setQaFilter] = useState<'all' | 'prelims' | 'mains'>('all')
  const [savedOnly, setSavedOnly] = useState(false)

  const [articles, setArticles] = useState<CurrentAffairsArticle[]>([])
  const [available, setAvailable] = useState<CurrentAffairsArticle[]>([])
  const [brief, setBrief] = useState<CurrentAffairsBrief | null>(null)
  const [summary, setSummary] = useState<CurrentAffairsSummary | null>(null)
  const [readerArticle, setReaderArticle] = useState<CurrentAffairsArticle | null>(null)
  const [readerContent, setReaderContent] = useState<CurrentAffairsContentResponse | null>(null)
  const [readerLoading, setReaderLoading] = useState(false)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [briefError, setBriefError] = useState('')
  const [dateReady, setDateReady] = useState(false)
  const manuallySelectedDate = useRef(false)

  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({})

  async function loadArticles() {
    setLoading(true)
    setError('')
    const params = new URLSearchParams()
    if (activeTab === 'day' && date) params.set('date', date)
    if (activeTab === 'weekly') params.set('cadence', 'weekly')
    if (activeTab === 'monthly') params.set('cadence', 'monthly')
    if (activeTab === 'subject' && subjectFilter) params.set('subject', subjectFilter)
    if (search) params.set('search', search)

    try {
      const data = await getCurrentAffairsArticles(params.toString())
      setArticles(data.filter(a => !a.publisher || a.publisher.toLowerCase().includes('pwonlyias') || a.publisher === 'PWOnlyIAS'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Current Affairs unavailable.')
    } finally {
      setLoading(false)
    }
  }

  async function loadBrief(force = false) {
    setBriefError('')
    try {
      setBrief(await getCurrentAffairsBriefOptional(date, force))
    } catch (reason) {
      setBriefError(reason instanceof Error ? reason.message : 'Daily brief unavailable.')
    }
  }

  async function refresh(event?: FormEvent) {
    event?.preventDefault()
    const catalog = await getCurrentAffairsArticles()
    const pwCatalog = catalog.filter(a => !a.publisher || a.publisher.toLowerCase().includes('pwonlyias') || a.publisher === 'PWOnlyIAS')
    setAvailable(pwCatalog)
    await Promise.all([
      loadArticles(),
      loadBrief(true),
      getCurrentAffairsSummary().then(setSummary).catch(() => setSummary(null))
    ])
  }

  useEffect(() => {
    let active = true
    void Promise.all([getCurrentAffairsArticles(), getCurrentAffairsSummary().catch(() => null)])
      .then(([catalog, overview]) => {
        if (!active) return
        const pwCatalog = catalog.filter(a => !a.publisher || a.publisher.toLowerCase().includes('pwonlyias') || a.publisher === 'PWOnlyIAS')
        setAvailable(pwCatalog)
        setSummary(overview)
        setDate(current => resolveInitialCurrentAffairsDate(pwCatalog, today(), current, manuallySelectedDate.current))
        setDateReady(true)
      })
      .catch(reason => {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'Current Affairs unavailable.')
          setDateReady(true)
        }
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (dateReady) void loadArticles()
  }, [dateReady, date, activeTab, subjectFilter, search])

  useEffect(() => {
    if (dateReady && activeTab === 'day') void loadBrief()
  }, [dateReady, date, activeTab])

  const subjectsWithData = useMemo(() => {
    const present = new Set(available.map(item => item.subject))
    return UPSC_SUBJECTS.filter(s => present.has(s) || s === 'Other')
  }, [available])

  const visibleArticles = useMemo(() => {
    let result = savedOnly ? articles.filter(item => item.saved) : articles
    if (activeTab === 'subject' && subjectFilter) {
      result = result.filter(item => item.subject === subjectFilter)
    }
    return result
  }, [articles, savedOnly, activeTab, subjectFilter])

  async function toggleSave(item: CurrentAffairsArticle) {
    await saveCurrentAffairsArticle(item.id, item.saved)
    const update = (rows: CurrentAffairsArticle[]) =>
      rows.map(row => (row.id === item.id ? { ...row, saved: !row.saved } : row))
    setArticles(update)
    setAvailable(update)
    if (readerArticle && readerArticle.id === item.id) {
      setReaderArticle(prev => prev ? { ...prev, saved: !prev.saved } : null)
    }
    window.dispatchEvent(new Event('mentor-data-changed'))
  }

  async function openReader(item: CurrentAffairsArticle) {
    setReaderArticle(item)
    setReaderLoading(true)
    try {
      const content = await getCurrentAffairsArticleContent(item.id)
      setReaderContent(content)
    } catch {
      setReaderContent(null)
    } finally {
      setReaderLoading(false)
    }
  }

  return (
    <div className="current-affairs-page phase-four-page">
      <header className="phase-page-head">
        <div>
          <p className="eyebrow">Official PWOnlyIAS Source Intelligence</p>
          <h1>Current Affairs</h1>
          <small>Structured web reader & analysis exclusively from official PWOnlyIAS content.</small>
        </div>
        <button className="icon-button" onClick={() => void refresh()}>Refresh</button>
      </header>

      <nav className="ca-primary-tabs" style={{ display: 'flex', gap: '8px', marginBottom: '16px', borderBottom: '2px solid #e2e8f0', paddingBottom: '8px' }}>
        <button className={`tab-btn ${activeTab === 'day' ? 'active' : ''}`} style={{ padding: '8px 16px', borderRadius: '6px', fontWeight: activeTab === 'day' ? 'bold' : 'normal', background: activeTab === 'day' ? '#2563eb' : '#f1f5f9', color: activeTab === 'day' ? '#fff' : '#334155', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('day')}>
          1. Day-wise
        </button>
        <button className={`tab-btn ${activeTab === 'weekly' ? 'active' : ''}`} style={{ padding: '8px 16px', borderRadius: '6px', fontWeight: activeTab === 'weekly' ? 'bold' : 'normal', background: activeTab === 'weekly' ? '#2563eb' : '#f1f5f9', color: activeTab === 'weekly' ? '#fff' : '#334155', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('weekly')}>
          2. Weekly-wise
        </button>
        <button className={`tab-btn ${activeTab === 'monthly' ? 'active' : ''}`} style={{ padding: '8px 16px', borderRadius: '6px', fontWeight: activeTab === 'monthly' ? 'bold' : 'normal', background: activeTab === 'monthly' ? '#2563eb' : '#f1f5f9', color: activeTab === 'monthly' ? '#fff' : '#334155', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('monthly')}>
          3. Monthly-wise
        </button>
        <button className={`tab-btn ${activeTab === 'subject' ? 'active' : ''}`} style={{ padding: '8px 16px', borderRadius: '6px', fontWeight: activeTab === 'subject' ? 'bold' : 'normal', background: activeTab === 'subject' ? '#2563eb' : '#f1f5f9', color: activeTab === 'subject' ? '#fff' : '#334155', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('subject')}>
          4. Subject-wise
        </button>
        <button className={`tab-btn ${activeTab === 'qa' ? 'active' : ''}`} style={{ padding: '8px 16px', borderRadius: '6px', fontWeight: activeTab === 'qa' ? 'bold' : 'normal', background: activeTab === 'qa' ? '#2563eb' : '#f1f5f9', color: activeTab === 'qa' ? '#fff' : '#334155', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('qa')}>
          5. Q&A
        </button>
      </nav>

      <form className="ca-toolbar premium-toolbar" onSubmit={refresh}>
        {activeTab === 'day' && (
          <label>
            Date
            <input type="date" value={date} onChange={e => { manuallySelectedDate.current = true; setDate(e.target.value) }} />
          </label>
        )}
        {activeTab === 'subject' && (
          <label>
            Subject
            <select value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)}>
              <option value="">All PWOnlyIAS Subjects</option>
              {subjectsWithData.map(sub => <option key={sub} value={sub}>{sub}</option>)}
            </select>
          </label>
        )}
        {activeTab === 'qa' && (
          <label>
            Type
            <select value={qaFilter} onChange={e => setQaFilter(e.target.value as any)}>
              <option value="all">All Q&A</option>
              <option value="prelims">Prelims Q&A</option>
              <option value="mains">Mains Q&A</option>
            </select>
          </label>
        )}
        <label className="grow">
          Search PWOnlyIAS Content
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search articles, topics or keywords..." />
        </label>
        <label className="saved-toggle">
          <input type="checkbox" checked={savedOnly} onChange={e => setSavedOnly(e.target.checked)} /> Saved
        </label>
        <button className="send-button">Filter</button>
      </form>

      {loading && <section className="visual-state">Loading PWOnlyIAS Current Affairs...</section>}
      {error && (
        <section className="visual-state error">
          <strong>Content Unavailable</strong>
          <p>{error}</p>
          <button onClick={() => void refresh()}>Retry</button>
        </section>
      )}

      {!loading && !error && (
        <>
          {activeTab === 'day' && (
            <div className="ca-above-fold">
              <section className="ca-brief premium-card">
                {briefError ? (
                  <>
                    <p className="eyebrow">Source: PWOnlyIAS</p>
                    <h2>Daily Brief Unavailable</h2>
                    <p>{briefError}</p>
                    <button onClick={() => void loadBrief(true)}>Retry Brief</button>
                  </>
                ) : brief ? (
                  <>
                    <div className="card-kicker">
                      <span>Daily Brief — Source: PWOnlyIAS</span>
                      <time>{brief.brief_date}</time>
                    </div>
                    <h2>{brief.title}</h2>
                    <p>{brief.overview}</p>
                    <small style={{ color: '#64748b', display: 'block', marginBottom: '12px' }}>AI-generated study summary based on the cited PWOnlyIAS source.</small>
                    <div className="ca-brief-grid">
                      <article>
                        <h3>Prelims Key Points</h3>
                        {brief.prelims_points_json.slice(0, 4).map((p, idx) => <p key={idx}>{p}</p>)}
                      </article>
                      <article>
                        <h3>Mains Key Themes</h3>
                        {brief.mains_points_json.slice(0, 4).map((p, idx) => <p key={idx}>{p}</p>)}
                      </article>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="eyebrow">Source: PWOnlyIAS</p>
                    <h2>Daily Brief for {date}</h2>
                    <p>Articles for {date} are listed below.</p>
                  </>
                )}
              </section>

              <section className="ca-headlines premium-card">
                <div className="card-kicker">
                  <span>Day-wise Articles ({date})</span>
                  <span>{visibleArticles.length} stories</span>
                </div>
                {visibleArticles.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
                    {visibleArticles.map(item => (
                      <article key={item.id} style={{ padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#2563eb' }}>Source: PWOnlyIAS · {item.subject}</span>
                          <span className={`ca-importance ${item.importance_level}`}>{item.importance_level}</span>
                        </div>
                        <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem' }}>{item.title}</h3>
                        <p style={{ fontSize: '0.9rem', color: '#475569', marginBottom: '8px' }}>{item.summary}</p>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                          <button className="send-button" style={{ padding: '4px 12px', fontSize: '0.85rem' }} onClick={() => openReader(item)}>
                            Read on Webpage
                          </button>
                          <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.85rem', color: '#2563eb', textDecoration: 'underline' }}>
                            Open Official Source
                          </a>
                          {item.pdf_url && (
                            <a href={item.pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.85rem', color: '#059669', textDecoration: 'underline' }}>
                              View Official PDF
                            </a>
                          )}
                          <button onClick={() => void toggleSave(item)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', color: '#64748b' }}>
                            {item.saved ? '♥ Saved' : '♡ Save'}
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p style={{ padding: '16px', color: '#64748b' }}>No PWOnlyIAS day-wise articles discovered for date {date}.</p>
                )}
              </section>
            </div>
          )}

          {activeTab === 'weekly' && (
            <section className="premium-card">
              <h2>Weekly Current Affairs Compilations</h2>
              <p style={{ color: '#64748b', marginBottom: '16px' }}>Source: PWOnlyIAS Official Weekly Issues</p>
              {visibleArticles.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                  {visibleArticles.map(item => (
                    <article key={item.id} style={{ padding: '16px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#059669', textTransform: 'uppercase' }}>
                        Weekly Issue {item.week_label ? `· ${item.week_label}` : ''}
                      </span>
                      <h3 style={{ margin: '8px 0', fontSize: '1rem' }}>{item.title}</h3>
                      <p style={{ fontSize: '0.85rem', color: '#475569', marginBottom: '12px' }}>{item.summary}</p>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button className="send-button" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => openReader(item)}>
                          Read Weekly Issue
                        </button>
                        <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#2563eb' }}>
                          Official Link
                        </a>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p>No PWOnlyIAS weekly compilations loaded yet.</p>
              )}
            </section>
          )}

          {activeTab === 'monthly' && (
            <section className="premium-card">
              <h2>Monthly Current Affairs Magazines (Manthan)</h2>
              <p style={{ color: '#64748b', marginBottom: '16px' }}>Source: Official PWOnlyIAS Monthly Magazines & Compilations</p>
              {visibleArticles.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                  {visibleArticles.map(item => (
                    <article key={item.id} style={{ padding: '16px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#d97706', textTransform: 'uppercase' }}>
                        Monthly Edition {item.month && item.year ? `· ${item.month}/${item.year}` : ''}
                      </span>
                      <h3 style={{ margin: '8px 0', fontSize: '1rem' }}>{item.title}</h3>
                      <p style={{ fontSize: '0.85rem', color: '#475569', marginBottom: '12px' }}>{item.summary}</p>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button className="send-button" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => openReader(item)}>
                          Read Monthly Issue
                        </button>
                        <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#2563eb' }}>
                          Official Source
                        </a>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p>No PWOnlyIAS monthly magazines loaded yet.</p>
              )}
            </section>
          )}

          {activeTab === 'subject' && (
            <section className="premium-card">
              <h2>Subject-wise Current Affairs</h2>
              <p style={{ color: '#64748b', marginBottom: '16px' }}>Filtered exclusively across PWOnlyIAS UPSC Subject Domains</p>
              {visibleArticles.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {visibleArticles.map(item => (
                    <article key={item.id} style={{ padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 'bold', color: '#2563eb' }}>{item.subject}</span>
                        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Source: PWOnlyIAS</span>
                      </div>
                      <h3 style={{ margin: '6px 0' }}>{item.title}</h3>
                      <p style={{ fontSize: '0.9rem', color: '#475569', marginBottom: '8px' }}>{item.summary}</p>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button className="send-button" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => openReader(item)}>
                          Read Article
                        </button>
                        <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.85rem', color: '#2563eb' }}>
                          Open Official Source
                        </a>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p>No articles found for the selected subject filter.</p>
              )}
            </section>
          )}

          {activeTab === 'qa' && (
            <section className="premium-card">
              <h2>Official PWOnlyIAS Current Affairs Q&A Browser</h2>
              <p style={{ color: '#64748b', marginBottom: '16px' }}>Grounded practice questions extracted from official PWOnlyIAS resources.</p>
              {visibleArticles.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {visibleArticles.map(item => (
                    <article key={item.id} style={{ padding: '16px', border: '1px solid #cbd5e1', borderRadius: '8px', background: '#f8fafc' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 'bold', color: '#0f172a' }}>{item.subject} · {item.topic}</span>
                        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Source: PWOnlyIAS</span>
                      </div>

                      {(qaFilter === 'all' || qaFilter === 'prelims') && item.relevance_prelims && (
                        <div style={{ marginBottom: '12px', padding: '12px', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                          <h4 style={{ margin: '0 0 8px 0', color: '#1e293b' }}>Prelims Question Practice</h4>
                          <p style={{ fontWeight: '500', marginBottom: '8px' }}>{item.title}</p>
                          <p style={{ fontSize: '0.9rem', color: '#334155' }}>Key Fact: {item.relevance_prelims}</p>
                          <div style={{ marginTop: '8px' }}>
                            <button
                              style={{ padding: '4px 12px', borderRadius: '4px', background: userAnswers[item.id] ? '#e2e8f0' : '#2563eb', color: userAnswers[item.id] ? '#334155' : '#fff', border: 'none', cursor: 'pointer', fontSize: '0.85rem' }}
                              onClick={() => setUserAnswers(prev => ({ ...prev, [item.id]: 'revealed' }))}
                            >
                              {userAnswers[item.id] ? 'Hide Answer Explanation' : 'Check Explanation'}
                            </button>
                            {userAnswers[item.id] && (
                              <div style={{ marginTop: '8px', padding: '8px', background: '#f1f5f9', borderRadius: '4px', fontSize: '0.85rem' }}>
                                <strong>Explanation & Source:</strong> Grounded in official PWOnlyIAS release for {item.publication_date || 'current period'}.
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {(qaFilter === 'all' || qaFilter === 'mains') && item.relevance_mains && (
                        <div style={{ padding: '12px', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                          <h4 style={{ margin: '0 0 8px 0', color: '#1e293b' }}>Mains Question Approach</h4>
                          <p style={{ fontWeight: '500', marginBottom: '4px' }}>Discuss the dimensions of: {item.title}</p>
                          <p style={{ fontSize: '0.85rem', color: '#475569' }}><strong>Model Approach Dimensions:</strong> {item.relevance_mains}</p>
                        </div>
                      )}

                      <div style={{ marginTop: '8px', display: 'flex', gap: '12px' }}>
                        <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.85rem', color: '#2563eb' }}>
                          Open Official Source
                        </a>
                        {item.pdf_url && (
                          <a href={item.pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.85rem', color: '#059669' }}>
                            View Official PDF
                          </a>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p>No Q&A items currently loaded.</p>
              )}
            </section>
          )}
        </>
      )}

      {readerArticle && (
        <div className="ca-modal" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <article style={{ background: '#ffffff', width: '100%', maxWidth: '820px', maxHeight: '90vh', overflowY: 'auto', borderRadius: '12px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#2563eb', textTransform: 'uppercase' }}>
                    Source: PWOnlyIAS
                  </span>
                  <span style={{ fontSize: '0.75rem', background: '#eff6ff', color: '#1d4ed8', padding: '2px 8px', borderRadius: '4px', fontWeight: '600' }}>
                    {readerArticle.subject}
                  </span>
                </div>
                <h2 style={{ margin: '4px 0 0 0', fontSize: '1.4rem', color: '#0f172a' }}>{readerArticle.title}</h2>
                <small style={{ color: '#64748b' }}>Published / Period: {readerArticle.publication_date || readerArticle.week_label || 'Current Period'}</small>
              </div>
              <button className="icon-button" style={{ padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#f8fafc', cursor: 'pointer' }} onClick={() => setReaderArticle(null)}>
                ✕ Close
              </button>
            </div>

            <div style={{ padding: '10px 14px', background: '#eff6ff', borderLeft: '4px solid #2563eb', borderRadius: '4px', marginBottom: '16px', fontSize: '0.85rem', color: '#1e40af' }}>
              AI-generated study summary based on the cited PWOnlyIAS source.
            </div>

            {readerLoading ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>Loading PWOnlyIAS article content...</div>
            ) : (
              <div className="reader-content" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Table of Contents if headings exist */}
                {readerContent?.content_blocks && readerContent.content_blocks.some(b => b.type === 'heading' || b.title) && (
                  <nav style={{ background: '#f8fafc', padding: '12px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    <h4 style={{ margin: '0 0 6px 0', fontSize: '0.9rem', color: '#334155' }}>Table of Contents</h4>
                    <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.85rem', color: '#2563eb' }}>
                      {readerContent.content_blocks
                        .filter(b => b.type === 'heading' || Boolean(b.title))
                        .map((b, i) => (
                          <li key={i}>{b.text || b.title}</li>
                        ))}
                    </ul>
                  </nav>
                )}

                <section>
                  <h3 style={{ fontSize: '1.1rem', color: '#0f172a', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>Overview</h3>
                  <p style={{ lineHeight: '1.6', color: '#334155' }}>{readerArticle.summary}</p>
                </section>

                {readerArticle.relevance_prelims && (
                  <section style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
                    <h3 style={{ fontSize: '1rem', color: '#059669', margin: '0 0 8px 0' }}>Prelims Key Points</h3>
                    <p style={{ whiteSpace: 'pre-line', fontSize: '0.9rem', color: '#1e293b' }}>{readerArticle.relevance_prelims}</p>
                  </section>
                )}

                {readerArticle.relevance_mains && (
                  <section style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
                    <h3 style={{ fontSize: '1rem', color: '#d97706', margin: '0 0 8px 0' }}>Mains Analysis & Dimensions</h3>
                    <p style={{ whiteSpace: 'pre-line', fontSize: '0.9rem', color: '#1e293b' }}>{readerArticle.relevance_mains}</p>
                  </section>
                )}

                {readerContent?.content_blocks && readerContent.content_blocks.length > 0 ? (
                  <section>
                    <h3 style={{ fontSize: '1.1rem', color: '#0f172a' }}>Structured Content Blocks</h3>
                    {readerContent.content_blocks.map((block, i) => (
                      <div key={i} style={{ marginBottom: '12px' }}>
                        {(block.type === 'heading' || block.title) && (
                          <h4 style={{ margin: '6px 0 4px 0', color: '#1e293b', fontSize: '1rem' }}>{block.text || block.title}</h4>
                        )}
                        {block.type === 'paragraph' && block.text && !block.title && (
                          <p style={{ fontSize: '0.9rem', color: '#334155', lineHeight: '1.5' }}>{block.text}</p>
                        )}
                        {(block.type === 'bullet_list' || block.items) && (
                          <ul style={{ paddingLeft: '20px', fontSize: '0.9rem', color: '#334155' }}>
                            {(block.items || []).map((it: string, idx: number) => <li key={idx}>{it}</li>)}
                          </ul>
                        )}
                        {block.page_ref && <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PDF Page Reference: p. {block.page_ref}</span>}
                      </div>
                    ))}
                  </section>
                ) : (
                  <section style={{ padding: '12px', background: '#fffbeb', borderRadius: '8px', border: '1px solid #fef3c7', fontSize: '0.9rem', color: '#b45309' }}>
                    {readerArticle.extraction_status === 'image_only'
                      ? 'This document is an image-only/scanned PDF. Text extraction is unavailable, but you can view the official PDF below.'
                      : 'Structured content extraction is pending or completed via summary.'}
                  </section>
                )}

                {readerContent?.page_references && readerContent.page_references.length > 0 && (
                  <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    <strong>Indexed Page References:</strong> Pages {readerContent.page_references.join(', ')}
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                className="send-button"
                style={{ padding: '8px 16px' }}
                onClick={() => { setReaderArticle(null); onNavigate('quizzes') }}
              >
                Take Quiz
              </button>
              <a href={readerArticle.source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #cbd5e1', borderRadius: '6px', textDecoration: 'none', color: '#2563eb', fontSize: '0.85rem', fontWeight: '500' }}>
                Open Official Source
              </a>
              {readerArticle.pdf_url ? (
                <a href={readerArticle.pdf_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #059669', color: '#059669', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                  View Official PDF
                </a>
              ) : (
                <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>PDF status: {readerArticle.pdf_availability || 'Source Webpage Only'}</span>
              )}
              <button onClick={() => void toggleSave(readerArticle)} style={{ marginLeft: 'auto', background: 'none', border: '1px solid #cbd5e1', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>
                {readerArticle.saved ? '♥ Saved' : '♡ Save Story'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
