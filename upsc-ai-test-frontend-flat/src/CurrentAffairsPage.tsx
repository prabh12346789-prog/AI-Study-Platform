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

const MANDATED_SUBJECTS = [
  'All PWOnlyIAS Subjects',
  'Indian Polity and Governance',
  'History',
  'Art and Culture',
  'Geography',
  'Indian Economy',
  'Environment and Ecology',
  'Science and Technology',
  'International Relations',
  'Indian Society and Social Justice',
  'Internal Security',
  'Disaster Management',
  'Ethics',
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
  const [selectedSubject, setSelectedSubject] = useState<string>('All PWOnlyIAS Subjects')
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
    if (activeTab === 'subject' && selectedSubject !== 'All PWOnlyIAS Subjects') params.set('subject', selectedSubject)
    if (activeTab === 'qa') params.set('content_type', 'prelims_qa')
    if (search) params.set('search', search)

    try {
      const data = await getCurrentAffairsArticles(params.toString())
      const clean = data.filter(a =>
        (!a.publisher || 
         a.publisher.toLowerCase().includes('pwonlyias') || 
         a.publisher === 'PWOnlyIAS' || 
         ['pib', 'rbi', 'mea', 'forumias', 'insightsias', 'drishti ias'].includes(a.publisher.toLowerCase()) ||
         a.id.startsWith('dmy-')) &&
        !a.title.toLowerCase().includes('pending backfill') &&
        !a.title.toLowerCase().includes('image only pdf') &&
        !a.title.toLowerCase().includes('mode test') &&
        !a.title.toLowerCase().includes('internal reader test') &&
        !a.title.toLowerCase().includes('july week 3') &&
        !a.title.toLowerCase().includes('july 2026') &&
        !a.id.startsWith('test-') &&
        !a.id.startsWith('demo-') &&
        !a.id.startsWith('sample-')
      )
      setArticles(clean)
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
    const pwCatalog = catalog.filter(a =>
      (!a.publisher || 
       a.publisher.toLowerCase().includes('pwonlyias') || 
       a.publisher === 'PWOnlyIAS' || 
       ['pib', 'rbi', 'mea', 'forumias', 'insightsias', 'drishti ias'].includes(a.publisher.toLowerCase()) ||
       a.id.startsWith('dmy-')) &&
      !a.title.toLowerCase().includes('pending backfill') &&
      !a.title.toLowerCase().includes('image only pdf') &&
      !a.title.toLowerCase().includes('mode test') &&
      !a.title.toLowerCase().includes('internal reader test') &&
      !a.title.toLowerCase().includes('july week 3') &&
      !a.title.toLowerCase().includes('july 2026') &&
      !a.id.startsWith('test-')
    )
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
        const pwCatalog = catalog.filter(a =>
          (!a.publisher || 
           a.publisher.toLowerCase().includes('pwonlyias') || 
           a.publisher === 'PWOnlyIAS' || 
           ['pib', 'rbi', 'mea', 'forumias', 'insightsias', 'drishti ias'].includes(a.publisher.toLowerCase()) ||
           a.id.startsWith('dmy-')) &&
          !a.title.toLowerCase().includes('pending backfill') &&
          !a.title.toLowerCase().includes('image only pdf') &&
          !a.title.toLowerCase().includes('mode test') &&
          !a.title.toLowerCase().includes('internal reader test') &&
          !a.title.toLowerCase().includes('july week 3') &&
          !a.title.toLowerCase().includes('july 2026') &&
          !a.id.startsWith('test-')
        )
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
    if (!dateReady) return
    void loadArticles()
    if (activeTab === 'day') {
      void loadBrief()
    }
  }, [activeTab, date, selectedSubject, search, dateReady])

  const filteredArticles = useMemo(() => {
    const map = new Map<string, CurrentAffairsArticle>()
    for (const a of articles) {
      const key = a.source_url || a.title.trim().toLowerCase()
      if (!map.has(key)) {
        map.set(key, a)
      }
    }
    let result = Array.from(map.values())
    if (savedOnly) {
      result = result.filter(a => a.saved)
    }
    return result
  }, [articles, savedOnly])

  async function toggleSave(article: CurrentAffairsArticle) {
    await saveCurrentAffairsArticle(article.id, article.saved)
    setArticles(prev => prev.map(a => (a.id === article.id ? { ...a, saved: !a.saved } : a)))
    if (readerArticle && readerArticle.id === article.id) {
      setReaderArticle(prev => (prev ? { ...prev, saved: !prev.saved } : null))
    }
  }

  async function openReader(article: CurrentAffairsArticle) {
    setReaderArticle(article)
    setReaderLoading(true)
    try {
      const content = await getCurrentAffairsArticleContent(article.id)
      setReaderContent(content)
    } catch {
      setReaderContent(null)
    } finally {
      setReaderLoading(false)
    }
  }

  return (
    <div className="current-affairs-page phase-four-page" style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', color: '#f8fafc' }}>
      {/* Header */}
      <header className="phase-page-head" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow" style={{ color: '#60a5fa', fontWeight: 'bold', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Current Affairs & Fallbacks</p>
            <h1 style={{ margin: '4px 0', fontSize: '1.8rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
              {activeTab === 'subject' && selectedSubject !== 'All PWOnlyIAS Subjects'
                ? `Current Affairs — ${selectedSubject}`
                : 'Current Affairs'}
              {articles.some(a => a.id.startsWith('dmy-')) && (
                <span style={{ fontSize: '0.75rem', fontWeight: 'bold', background: '#f59e0b', color: '#1e293b', padding: '2px 8px', borderRadius: '9999px', textTransform: 'uppercase' }}>Report Demo Mode</span>
              )}
            </h1>
            <small style={{ color: '#94a3b8' }}>Verified static & daily UPSC Current Affairs from official PWOnlyIAS and verified fallback sources.</small>
          </div>
          <button
            style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #334155', background: '#1e293b', color: '#f8fafc', cursor: 'pointer', fontSize: '0.85rem' }}
            onClick={refresh}
          >
            🔄 Refresh
          </button>
        </div>
      </header>

      {/* 5 Primary Navigation Tabs */}
      <nav style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid #334155', paddingBottom: '12px', flexWrap: 'wrap' }}>
        {[
          { id: 'day', label: '1. Day-wise' },
          { id: 'weekly', label: '2. Weekly-wise' },
          { id: 'monthly', label: '3. Monthly-wise' },
          { id: 'subject', label: '4. Subject-wise' },
          { id: 'qa', label: '5. Q&A' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as SectionTab)}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: activeTab === tab.id ? '2px solid #3b82f6' : '1px solid #334155',
              background: activeTab === tab.id ? '#1e3a8a' : '#1e293b',
              color: activeTab === tab.id ? '#ffffff' : '#94a3b8',
              fontWeight: activeTab === tab.id ? 'bold' : 'normal',
              cursor: 'pointer',
              fontSize: '0.9rem'
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Search & Filter Controls Bar */}
      <section className="premium-card" style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          {activeTab === 'day' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa', textTransform: 'uppercase' }}>Select Date</label>
              <input
                type="date"
                value={date}
                onChange={e => {
                  manuallySelectedDate.current = true
                  setDate(e.target.value)
                }}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#f8fafc', fontSize: '0.9rem' }}
              />
            </div>
          )}

          {activeTab === 'subject' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '240px', flex: '0 1 auto' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa', textTransform: 'uppercase' }}>Select Subject</label>
              <select
                value={selectedSubject}
                onChange={e => setSelectedSubject(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#f8fafc', fontSize: '0.9rem', width: '100%', cursor: 'pointer' }}
              >
                {MANDATED_SUBJECTS.map(subj => (
                  <option key={subj} value={subj}>{subj}</option>
                ))}
              </select>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: '220px' }}>
            <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase' }}>Search</label>
            <input
              type="text"
              placeholder="Search Current Affairs by keyword or topic..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#f8fafc', fontSize: '0.9rem' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '18px' }}>
            <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer', color: '#e2e8f0' }}>
              <input type="checkbox" checked={savedOnly} onChange={e => setSavedOnly(e.target.checked)} />
              Saved Only
            </label>
          </div>
        </div>
      </section>

      {/* Main Tab Views */}
      {error && (
        <div style={{ padding: '16px', background: '#2d1a1a', border: '1px solid #7f1d1d', color: '#fca5a5', borderRadius: '8px', marginBottom: '16px', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {error}</span>
          <button onClick={() => void refresh()} style={{ background: '#7f1d1d', border: 'none', color: '#fff', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem' }}>Retry</button>
        </div>
      )}

      {loading ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading PWOnlyIAS Current Affairs...</div>
      ) : filteredArticles.length === 0 ? (
        /* Honest Tab-Specific Empty States */
        <section className="premium-card" style={{ padding: '48px 24px', background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', textAlign: 'center', maxWidth: '650px', margin: '30px auto' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>
            {activeTab === 'qa' ? '❓' : '📰'}
          </div>
          <h2 style={{ fontSize: '1.3rem', color: '#f8fafc', marginBottom: '8px' }}>
            {activeTab === 'day' && 'No verified Current Affairs available'}
            {activeTab === 'weekly' && 'No verified weekly compilation has been imported yet.'}
            {activeTab === 'monthly' && 'No verified monthly magazine has been imported yet.'}
            {activeTab === 'subject' && 'No verified Current Affairs available yet'}
            {activeTab === 'qa' && 'No verified Current Affairs Q&A is available yet.'}
          </h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '16px' }}>
            {activeTab === 'day' && 'No verified Current Affairs records are available for this date yet.'}
            {activeTab === 'weekly' && 'Weekly compilations will appear here after official weekly issues are imported.'}
            {activeTab === 'monthly' && 'Monthly Manthan magazines will appear here after official monthly issues are imported.'}
            {activeTab === 'subject' && `No publicly accessible Current Affairs records have been imported for ${selectedSubject} yet.`}
            {activeTab === 'qa' && 'Grounded practice questions will appear here after official Current Affairs Q&A articles are verified.'}
          </p>
        </section>
      ) : (
        /* Articles Grid List */
        <section>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {filteredArticles.map(article => {
              const canRead = article.extraction_status === 'ready' || article.extraction_status === 'completed'
              return (
                <article key={article.id} style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa' }}>{article.subject}</span>
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                      {article.id.startsWith('dmy-') && (
                        <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: '#374151', color: '#fbbf24', borderRadius: '4px', fontWeight: 'bold' }}>Demo Data</span>
                      )}
                      {article.publisher && article.publisher !== 'PWOnlyIAS' && (
                        <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: '#1e3a8a', color: '#93c5fd', borderRadius: '4px' }}>Source: {article.publisher}</span>
                      )}
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{article.publication_date}</span>
                    </div>
                  </div>

                  <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem', color: '#f8fafc' }}>{article.title}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#cbd5e1', flex: 1, marginBottom: '12px', lineHeight: '1.5' }}>
                    {article.summary || article.title}
                  </p>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #334155' }}>
                    {canRead ? (
                      <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => openReader(article)}>
                        Read on Webpage
                      </button>
                    ) : (
                      <span style={{ fontSize: '0.8rem', color: '#94a3b8', background: '#0f172a', padding: '4px 10px', borderRadius: '4px', border: '1px solid #334155' }}>
                        Content not extracted
                      </span>
                    )}
                    <a href={article.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#60a5fa' }}>
                      Official Source
                    </a>
                    {article.pdf_url && (
                      <a href={article.pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#34d399' }}>
                        View PDF
                      </a>
                    )}
                    <button onClick={() => void toggleSave(article)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', color: '#94a3b8' }}>
                      {article.saved ? '♥ Saved' : '♡ Save'}
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        </section>
      )}

      {/* Internal Article Reader Modal */}
      {readerArticle && (
        <div className="ca-modal" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <article style={{ background: '#0f172a', border: '1px solid #334155', width: '100%', maxWidth: '850px', maxHeight: '92vh', display: 'flex', flexDirection: 'column', borderRadius: '12px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)', color: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#60a5fa' }}>Source: {readerArticle.publisher || 'PWOnlyIAS'}</span>
                  <span style={{ fontSize: '0.75rem', background: '#1e3a8a', color: '#93c5fd', padding: '2px 8px', borderRadius: '4px' }}>{readerArticle.subject}</span>
                </div>
                <h2 style={{ margin: '4px 0 0 0', fontSize: '1.4rem', color: '#f8fafc' }}>{readerArticle.title}</h2>
              </div>
              <button className="icon-button" style={{ padding: '6px 12px', border: '1px solid #334155', borderRadius: '6px', background: '#1e293b', color: '#f8fafc', cursor: 'pointer' }} onClick={() => setReaderArticle(null)}>
                ✕ Close
              </button>
            </div>

            {readerLoading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading article content...</div>
            ) : (
              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '8px' }}>
                {/* Structured Content Blocks */}
                {readerContent?.content_blocks && readerContent.content_blocks.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {readerContent.content_blocks.map((block, i) => (
                      <div key={i}>
                        {(block.type === 'heading' || block.title) && (
                          <h3 style={{ margin: '12px 0 6px 0', color: '#f8fafc', fontSize: '1.1rem', borderBottom: '1px solid #334155', paddingBottom: '4px' }}>
                            {block.text || block.title}
                          </h3>
                        )}
                        {block.type === 'paragraph' && block.text && (
                          <p style={{ fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6', margin: '4px 0' }}>{block.text}</p>
                        )}
                        {(block.type === 'bullet_list' || block.items) && (
                          <ul style={{ paddingLeft: '20px', fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6' }}>
                            {(block.items || []).map((it, idx) => <li key={idx}>{it}</li>)}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6' }}>
                    <p style={{ margin: '0 0 8px 0' }}>{readerArticle.summary || readerArticle.title}</p>
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #334155', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="send-button" style={{ padding: '8px 16px' }} onClick={() => { setReaderArticle(null); onNavigate('chat') }}>
                Ask AI About Article
              </button>
              <a href={readerArticle.source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #334155', borderRadius: '6px', textDecoration: 'none', color: '#60a5fa', fontSize: '0.85rem', fontWeight: '500' }}>
                Official Source
              </a>
              {readerArticle.pdf_url && (
                <a href={readerArticle.pdf_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #059669', color: '#34d399', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                  View PDF
                </a>
              )}
              <button onClick={() => void toggleSave(readerArticle)} style={{ marginLeft: 'auto', background: 'none', border: '1px solid #334155', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer', color: '#94a3b8' }}>
                {readerArticle.saved ? '♥ Saved' : '♡ Save Article'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
