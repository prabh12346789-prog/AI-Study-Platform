import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  CurrentAffairsArticle,
  CurrentAffairsContentResponse,
  CurrentAffairsDatesResponse,
  CurrentAffairsSyncStatusResponse,
  getCurrentAffairsArticleContent,
  getCurrentAffairsArticles,
  getCurrentAffairsDates,
  getCurrentAffairsSyncStatus,
  refreshCurrentAffairs,
  saveCurrentAffairsArticle,
} from './api'
import type { AppPage } from './AppShell'


type SectionTab = 'day' | 'weekly' | 'monthly' | 'subject' | 'qa'

const MANDATED_SUBJECTS = [
  'All Subjects',
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
  'Other',
]

const todayStr = () => new Date().toISOString().slice(0, 10)

export function CurrentAffairsPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [activeTab, setActiveTab] = useState<SectionTab>('day')
  const [date, setDate] = useState(todayStr())
  const [search, setSearch] = useState('')
  const [selectedSubject, setSelectedSubject] = useState<string>('All Subjects')
  const [savedOnly, setSavedOnly] = useState(false)

  const [articles, setArticles] = useState<CurrentAffairsArticle[]>([])
  const [datesMeta, setDatesMeta] = useState<CurrentAffairsDatesResponse | null>(null)
  const [syncStatus, setSyncStatus] = useState<CurrentAffairsSyncStatusResponse | null>(null)

  const [readerArticle, setReaderArticle] = useState<CurrentAffairsArticle | null>(null)
  const [readerContent, setReaderContent] = useState<CurrentAffairsContentResponse | null>(null)
  const [readerLoading, setReaderLoading] = useState(false)

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [dateReady, setDateReady] = useState(false)
  const manuallySelectedDate = useRef(false)

  // ── Helpers ──────────────────────────────────────────────────────────────

  function cleanArticles(data: CurrentAffairsArticle[]) {
    return data.filter(
      (a) =>
        !a.title.toLowerCase().includes('pending backfill') &&
        !a.title.toLowerCase().includes('image only pdf') &&
        !a.title.toLowerCase().includes('mode test') &&
        !a.title.toLowerCase().includes('internal reader test') &&
        !a.title.toLowerCase().includes('july week 3') &&
        !a.title.toLowerCase().includes('july 2026') &&
        !a.id.startsWith('test-') &&
        !a.id.startsWith('demo-') &&
        !a.id.startsWith('dmy-') &&
        !a.id.startsWith('sample-'),
    )
  }

  // ── Data Loading ──────────────────────────────────────────────────────────

  async function loadArticles() {
    setLoading(true)
    setError('')
    const params = new URLSearchParams()
    if (activeTab === 'day' && date) params.set('date', date)
    if (activeTab === 'weekly') params.set('cadence', 'weekly')
    if (activeTab === 'monthly') params.set('cadence', 'monthly')
    if (activeTab === 'subject' && selectedSubject !== 'All Subjects') params.set('subject', selectedSubject)
    if (activeTab === 'qa') params.set('content_type', 'prelims_qa')
    if (search) params.set('search', search)

    try {
      const data = await getCurrentAffairsArticles(params.toString())
      setArticles(cleanArticles(data))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Current Affairs unavailable.')
    } finally {
      setLoading(false)
    }
  }

  async function handleRefresh(event?: FormEvent) {
    event?.preventDefault()
    if (refreshing) return
    setRefreshing(true)
    setError('')
    try {
      await refreshCurrentAffairs()
      const [datesData, statusData] = await Promise.all([
        getCurrentAffairsDates().catch(() => null),
        getCurrentAffairsSyncStatus().catch(() => null),
      ])
      if (datesData) {
        setDatesMeta(datesData)
        if (!manuallySelectedDate.current) {
          setDate(datesData.today_record_count > 0 ? todayStr() : datesData.latest_available_date)
        }
      }
      if (statusData) setSyncStatus(statusData)
      await loadArticles()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Refresh failed.')
    } finally {
      setRefreshing(false)
    }
  }

  // ── Initial Mount ─────────────────────────────────────────────────────────

  useEffect(() => {
    let active = true
    void Promise.all([
      getCurrentAffairsDates().catch(() => null),
      getCurrentAffairsSyncStatus().catch(() => null),
      getCurrentAffairsArticles(),
    ]).then(([datesData, statusData, catalog]) => {
      if (!active) return
      if (datesData) {
        setDatesMeta(datesData)
        if (!manuallySelectedDate.current) {
          setDate(datesData.today_record_count > 0 ? todayStr() : datesData.latest_available_date || todayStr())
        }
      }
      if (statusData) setSyncStatus(statusData)
      setArticles(cleanArticles(catalog))
      setDateReady(true)
    }).catch((reason) => {
      if (active) {
        setError(reason instanceof Error ? reason.message : 'Current Affairs unavailable.')
        setDateReady(true)
      }
    })
    return () => { active = false }
  }, [])

  // ── Re-load on tab / date / filter changes ────────────────────────────────

  useEffect(() => {
    if (!dateReady) return
    void loadArticles()
  }, [activeTab, date, selectedSubject, search, dateReady])

  // ── Deduplication ─────────────────────────────────────────────────────────

  const filteredArticles = useMemo(() => {
    const map = new Map<string, CurrentAffairsArticle>()
    for (const a of articles) {
      const key = a.source_url || a.title.trim().toLowerCase()
      if (!map.has(key)) map.set(key, a)
    }
    let result = Array.from(map.values())
    if (savedOnly) result = result.filter((a) => a.saved)
    return result
  }, [articles, savedOnly])

  // ── Save toggle ───────────────────────────────────────────────────────────

  async function toggleSave(article: CurrentAffairsArticle) {
    await saveCurrentAffairsArticle(article.id, article.saved)
    setArticles((prev) => prev.map((a) => (a.id === article.id ? { ...a, saved: !a.saved } : a)))
    if (readerArticle?.id === article.id) {
      setReaderArticle((prev) => (prev ? { ...prev, saved: !prev.saved } : null))
    }
  }

  // ── Reader modal ──────────────────────────────────────────────────────────

  async function openReader(article: CurrentAffairsArticle) {
    setReaderArticle(article)
    setReaderLoading(true)
    try {
      setReaderContent(await getCurrentAffairsArticleContent(article.id))
    } catch {
      setReaderContent(null)
    } finally {
      setReaderLoading(false)
    }
  }

  // ── Sources display ───────────────────────────────────────────────────────

  const sourcesLabel = (syncStatus?.sources_checked ?? ['PIB', 'RBI', 'MEA']).join(', ')
  const acceptedCount = syncStatus?.accepted_article_count ?? filteredArticles.length
  const lastSync = syncStatus?.last_synchronized_at
    ? new Date(syncStatus.last_synchronized_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null

  const showBanner = activeTab === 'day' && !loading && date !== todayStr() && datesMeta?.latest_available_date

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div
      className="current-affairs-page phase-four-page"
      style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', color: '#f8fafc' }}
    >
      {/* ── Header ── */}
      <header className="phase-page-head" style={{ marginBottom: '24px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div>
            <p
              className="eyebrow"
              style={{
                color: '#60a5fa',
                fontWeight: 'bold',
                fontSize: '0.8rem',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                margin: 0,
              }}
            >
              Official Government Sources — PIB · RBI · MEA
            </p>
            <h1 style={{ margin: '6px 0 4px', fontSize: '1.8rem', color: '#f8fafc' }}>
              {activeTab === 'subject' && selectedSubject !== 'All Subjects'
                ? `Current Affairs — ${selectedSubject}`
                : 'Current Affairs'}
            </h1>
            <div
              style={{
                display: 'flex',
                gap: '14px',
                flexWrap: 'wrap',
                fontSize: '0.8rem',
                color: '#94a3b8',
              }}
            >
              <span>
                Sources: <strong style={{ color: '#e2e8f0' }}>{sourcesLabel}</strong>
              </span>
              <span>·</span>
              <span>
                Accepted: <strong style={{ color: '#e2e8f0' }}>{acceptedCount}</strong>
              </span>
              {lastSync && (
                <>
                  <span>·</span>
                  <span>Last sync: {lastSync}</span>
                </>
              )}
            </div>
          </div>

          <button
            id="ca-refresh-btn"
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: '1px solid #3b82f6',
              background: refreshing ? '#1e3a8a' : '#2563eb',
              color: '#fff',
              cursor: refreshing ? 'not-allowed' : 'pointer',
              fontSize: '0.9rem',
              fontWeight: '600',
              opacity: refreshing ? 0.7 : 1,
              transition: 'background 0.2s',
            }}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? '🔄 Refreshing…' : '🔄 Refresh'}
          </button>
        </div>
      </header>

      {/* ── Tabs ── */}
      <nav
        style={{
          display: 'flex',
          gap: '8px',
          marginBottom: '24px',
          borderBottom: '1px solid #334155',
          paddingBottom: '12px',
          flexWrap: 'wrap',
        }}
      >
        {(
          [
            { id: 'day', label: '1. Day-wise' },
            { id: 'weekly', label: '2. Weekly-wise' },
            { id: 'monthly', label: '3. Monthly-wise' },
            { id: 'subject', label: '4. Subject-wise' },
            { id: 'qa', label: '5. Q&A' },
          ] as { id: SectionTab; label: string }[]
        ).map((tab) => (
          <button
            key={tab.id}
            id={`ca-tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: activeTab === tab.id ? '2px solid #3b82f6' : '1px solid #334155',
              background: activeTab === tab.id ? '#1e3a8a' : '#1e293b',
              color: activeTab === tab.id ? '#ffffff' : '#94a3b8',
              fontWeight: activeTab === tab.id ? 'bold' : 'normal',
              cursor: 'pointer',
              fontSize: '0.9rem',
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* ── Filter Bar ── */}
      <section
        className="premium-card"
        style={{
          padding: '16px',
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: '10px',
          marginBottom: '24px',
        }}
      >
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {activeTab === 'day' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa', textTransform: 'uppercase' }}>
                Select Date
              </label>
              <input
                id="ca-date-picker"
                type="date"
                value={date}
                onChange={(e) => {
                  manuallySelectedDate.current = true
                  setDate(e.target.value)
                }}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #334155',
                  background: '#0f172a',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                }}
              />
            </div>
          )}

          {activeTab === 'subject' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '240px', flex: '0 1 auto' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa', textTransform: 'uppercase' }}>
                Select Subject
              </label>
              <select
                id="ca-subject-picker"
                value={selectedSubject}
                onChange={(e) => setSelectedSubject(e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #334155',
                  background: '#0f172a',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                }}
              >
                {MANDATED_SUBJECTS.map((subj) => (
                  <option key={subj} value={subj}>
                    {subj}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: '220px' }}>
            <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase' }}>
              Search
            </label>
            <input
              id="ca-search"
              type="text"
              placeholder="Search by keyword or topic…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                border: '1px solid #334155',
                background: '#0f172a',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <label
            style={{
              display: 'flex',
              gap: '6px',
              alignItems: 'center',
              fontSize: '0.85rem',
              cursor: 'pointer',
              color: '#e2e8f0',
              paddingBottom: '4px',
            }}
          >
            <input type="checkbox" checked={savedOnly} onChange={(e) => setSavedOnly(e.target.checked)} />
            Saved Only
          </label>
        </div>
      </section>

      {/* ── Date Banner ── */}
      {showBanner && (
        <div
          style={{
            padding: '10px 16px',
            background: '#1e3a8a',
            border: '1px solid #3b82f6',
            color: '#93c5fd',
            borderRadius: '8px',
            marginBottom: '20px',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <span>
            📅 Showing latest available Current Affairs:{' '}
            <strong>{datesMeta?.latest_available_date}</strong>
          </span>
          <button
            onClick={() => {
              manuallySelectedDate.current = true
              setDate(todayStr())
            }}
            style={{
              background: 'none',
              border: '1px solid #60a5fa',
              color: '#60a5fa',
              padding: '4px 10px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.8rem',
            }}
          >
            Check Today ({todayStr()})
          </button>
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div
          style={{
            padding: '14px 16px',
            background: '#2d1a1a',
            border: '1px solid #7f1d1d',
            color: '#fca5a5',
            borderRadius: '8px',
            marginBottom: '16px',
            fontSize: '0.9rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>⚠️ {error}</span>
          <button
            onClick={() => void handleRefresh()}
            style={{
              background: '#7f1d1d',
              border: 'none',
              color: '#fff',
              padding: '4px 10px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.85rem',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {loading ? (
        <div style={{ padding: '48px', textAlign: 'center', color: '#94a3b8', fontSize: '1rem' }}>
          Loading Official Current Affairs…
        </div>
      ) : filteredArticles.length === 0 ? (
        /* ── Empty State ── */
        <section
          className="premium-card"
          style={{
            padding: '48px 24px',
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            textAlign: 'center',
            maxWidth: '650px',
            margin: '30px auto',
          }}
        >
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>{activeTab === 'qa' ? '❓' : '📰'}</div>
          <h2 style={{ fontSize: '1.3rem', color: '#f8fafc', marginBottom: '8px' }}>
            {activeTab === 'day' && 'No verified Current Affairs available'}
            {activeTab === 'weekly' && 'No verified weekly compilation imported yet.'}
            {activeTab === 'monthly' && 'No verified monthly magazine imported yet.'}
            {activeTab === 'subject' && 'No verified Current Affairs available yet'}
            {activeTab === 'qa' && 'No verified Current Affairs Q&A available yet.'}
          </h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '20px' }}>
            {activeTab === 'day' && `No records from PIB, RBI, or MEA are available for ${date} yet.`}
            {activeTab === 'weekly' && 'Weekly compilations will appear here after official weekly issues are imported.'}
            {activeTab === 'monthly' && 'Monthly magazines will appear here after official monthly issues are imported.'}
            {activeTab === 'subject' &&
              `No publicly accessible Current Affairs have been imported for ${selectedSubject} yet.`}
            {activeTab === 'qa' &&
              'Practice questions will appear here after official Current Affairs Q&A articles are verified.'}
          </p>
          {activeTab === 'day' && datesMeta?.latest_available_date && datesMeta.latest_available_date !== date && (
            <button
              id="ca-view-latest-btn"
              onClick={() => {
                manuallySelectedDate.current = true
                setDate(datesMeta!.latest_available_date)
              }}
              style={{
                padding: '10px 20px',
                background: '#2563eb',
                border: 'none',
                color: '#fff',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: '600',
              }}
            >
              View latest available ({datesMeta.latest_available_date})
            </button>
          )}
        </section>
      ) : (
        /* ── Articles Grid ── */
        <section id="ca-articles-grid">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: '16px',
            }}
          >
            {filteredArticles.map((article) => (
              <article
                key={article.id}
                style={{
                  padding: '18px',
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'border-color 0.2s',
                }}
              >
                {/* Badges row */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    marginBottom: '8px',
                    flexWrap: 'wrap',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {article.subject && (
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: '700',
                          color: '#60a5fa',
                          background: '#0f172a',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          border: '1px solid #1e3a8a',
                        }}
                      >
                        {article.subject}
                      </span>
                    )}
                    {article.publisher && (
                      <span
                        style={{
                          fontSize: '0.7rem',
                          padding: '2px 6px',
                          background: '#1e3a8a',
                          color: '#93c5fd',
                          borderRadius: '4px',
                        }}
                      >
                        {article.publisher}
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: '0.72rem', color: '#64748b', whiteSpace: 'nowrap' }}>
                    {article.publication_date}
                  </span>
                </div>

                {/* Title */}
                <h3
                  style={{
                    margin: '0 0 8px',
                    fontSize: '1rem',
                    color: '#f8fafc',
                    lineHeight: '1.4',
                    fontWeight: '600',
                  }}
                >
                  {article.title}
                </h3>

                {/* Summary */}
                <p
                  style={{
                    fontSize: '0.85rem',
                    color: '#cbd5e1',
                    flex: 1,
                    marginBottom: '10px',
                    lineHeight: '1.55',
                  }}
                >
                  {article.summary || article.title}
                </p>

                {/* Legal attribution */}
                <p
                  style={{
                    fontSize: '0.7rem',
                    color: '#475569',
                    fontStyle: 'italic',
                    marginBottom: '12px',
                    lineHeight: '1.4',
                  }}
                >
                  Summary generated from a publicly accessible official source. Refer to the original link for complete
                  information.
                </p>

                {/* Actions */}
                <div
                  style={{
                    display: 'flex',
                    gap: '10px',
                    alignItems: 'center',
                    paddingTop: '10px',
                    borderTop: '1px solid #334155',
                    flexWrap: 'wrap',
                  }}
                >
                  {article.source_url && (
                    <a
                      href={article.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: '0.82rem',
                        color: '#60a5fa',
                        textDecoration: 'none',
                        fontWeight: '500',
                      }}
                    >
                      Read Original Source ↗
                    </a>
                  )}
                  <button
                    onClick={() => void toggleSave(article)}
                    style={{
                      marginLeft: 'auto',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.85rem',
                      color: article.saved ? '#f472b6' : '#94a3b8',
                    }}
                  >
                    {article.saved ? '♥ Saved' : '♡ Save'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* ── Reader Modal ── */}
      {readerArticle && (
        <div
          className="ca-modal"
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.85)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px',
          }}
        >
          <article
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              width: '100%',
              maxWidth: '850px',
              maxHeight: '92vh',
              display: 'flex',
              flexDirection: 'column',
              borderRadius: '12px',
              padding: '24px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)',
              color: '#f8fafc',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: '12px',
              }}
            >
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#60a5fa' }}>
                    Source: {readerArticle.publisher || 'Official'}
                  </span>
                  {readerArticle.subject && (
                    <span
                      style={{
                        fontSize: '0.75rem',
                        background: '#1e3a8a',
                        color: '#93c5fd',
                        padding: '2px 8px',
                        borderRadius: '4px',
                      }}
                    >
                      {readerArticle.subject}
                    </span>
                  )}
                </div>
                <h2 style={{ margin: '4px 0 0', fontSize: '1.35rem', color: '#f8fafc' }}>{readerArticle.title}</h2>
              </div>
              <button
                className="icon-button"
                style={{
                  padding: '6px 12px',
                  border: '1px solid #334155',
                  borderRadius: '6px',
                  background: '#1e293b',
                  color: '#f8fafc',
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
                onClick={() => setReaderArticle(null)}
              >
                ✕ Close
              </button>
            </div>

            {readerLoading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading article content…</div>
            ) : (
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  paddingRight: '8px',
                }}
              >
                {readerContent?.content_blocks && readerContent.content_blocks.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {readerContent.content_blocks.map((block, i) => (
                      <div key={i}>
                        {(block.type === 'heading' || block.title) && (
                          <h3
                            style={{
                              margin: '12px 0 6px',
                              color: '#f8fafc',
                              fontSize: '1.1rem',
                              borderBottom: '1px solid #334155',
                              paddingBottom: '4px',
                            }}
                          >
                            {block.text || block.title}
                          </h3>
                        )}
                        {block.type === 'paragraph' && block.text && (
                          <p style={{ fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6', margin: '4px 0' }}>
                            {block.text}
                          </p>
                        )}
                        {(block.type === 'bullet_list' || block.items) && (
                          <ul style={{ paddingLeft: '20px', fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6' }}>
                            {(block.items || []).map((it: string, idx: number) => (
                              <li key={idx}>{it}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: '16px',
                      background: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      fontSize: '0.95rem',
                      color: '#cbd5e1',
                      lineHeight: '1.6',
                    }}
                  >
                    {readerArticle.summary || readerArticle.title}
                  </div>
                )}
              </div>
            )}

            <div
              style={{
                marginTop: '16px',
                paddingTop: '14px',
                borderTop: '1px solid #334155',
                display: 'flex',
                gap: '10px',
                alignItems: 'center',
                flexWrap: 'wrap',
              }}
            >
              <button
                className="send-button"
                style={{ padding: '8px 16px' }}
                onClick={() => {
                  setReaderArticle(null)
                  onNavigate('chat')
                }}
              >
                Ask AI About Article
              </button>
              {readerArticle.source_url && (
                <a
                  href={readerArticle.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: '8px 14px',
                    border: '1px solid #334155',
                    borderRadius: '6px',
                    textDecoration: 'none',
                    color: '#60a5fa',
                    fontSize: '0.85rem',
                    fontWeight: '500',
                  }}
                >
                  Official Source ↗
                </a>
              )}
              <button
                onClick={() => void toggleSave(readerArticle)}
                style={{
                  marginLeft: 'auto',
                  background: 'none',
                  border: '1px solid #334155',
                  padding: '8px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  color: '#94a3b8',
                }}
              >
                {readerArticle.saved ? '♥ Saved' : '♡ Save Article'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
