import { useEffect, useMemo, useState } from 'react'
import {
  BookSubjectCount,
  UPSCBook,
  UPSCBookContentResponse,
  getUpscBookContent,
  getUpscBookSubjects,
  getUpscBooks,
  saveUpscBook,
  updateUpscBookProgress,
  API_BASE_URL
} from './api'
import type { AppPage } from './AppShell'

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
  'Budget and Economic Survey',
  'Essay',
  'Other'
]

export function UpscBooksPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [activeTab, setActiveTab] = useState<'prelims' | 'mains' | 'qa_bank'>(() => {
    const saved = localStorage.getItem('upsc_books_active_tab')
    if (saved === 'prelims' || saved === 'mains' || saved === 'qa_bank') {
      return saved
    }
    return 'mains'
  })
  const [tabCounts, setTabCounts] = useState<Record<string, number>>({ prelims: 0, mains: 0, qa_bank: 0 })
  const [subjectCounts, setSubjectCounts] = useState<Record<string, number>>({})
  const [books, setBooks] = useState<UPSCBook[]>([])
  const [selectedSubject, setSelectedSubject] = useState<string>('All Subjects')

  const [search, setSearch] = useState('')
  const [savedOnly, setSavedOnly] = useState(false)

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const [readerBook, setReaderBook] = useState<UPSCBook | null>(null)
  const [readerContent, setReaderContent] = useState<UPSCBookContentResponse | null>(null)
  const [selectedChapterId, setSelectedChapterId] = useState<string | undefined>(undefined)
  const [readerLoading, setReaderLoading] = useState(false)
  const [progressPct, setProgressPct] = useState(0)
  const [readerTab, setReaderTab] = useState<'material' | 'pdf'>('material')

  async function fetchTabCounts() {
    try {
      const [p, m, q] = await Promise.all([
        getUpscBooks('section=prelims'),
        getUpscBooks('section=mains'),
        getUpscBooks('section=qa_bank')
      ])
      setTabCounts({
        prelims: p.length,
        mains: m.length,
        qa_bank: q.length
      })
    } catch {
      // Ignore
    }
  }

  async function fetchSubjectCounts(section: string) {
    try {
      const counts = await getUpscBookSubjects(`section=${section}`)
      const map: Record<string, number> = {}
      counts.forEach(s => { map[s.subject] = s.book_count })
      setSubjectCounts(map)
    } catch {
      setSubjectCounts({})
    }
  }

  async function loadBooks(subj: string, section: string) {
    setLoading(true)
    setError('')
    try {
      const paramParts = [`section=${section}`]
      if (subj !== 'All Subjects') {
        paramParts.push(`subject=${encodeURIComponent(subj)}`)
      }
      const booksData = await getUpscBooks(paramParts.join('&'))
      // Exclude any synthetic test books
      const clean = booksData.filter(b =>
        !b.title.toLowerCase().includes('isolated test book') &&
        !b.title.toLowerCase().includes('prog book') &&
        !b.title.toLowerCase().includes('both relevant book') &&
        !b.title.toLowerCase().includes('evil book') &&
        !b.id.startsWith('test-') &&
        !b.id.startsWith('isolated-') &&
        !b.id.startsWith('demo-') &&
        !b.id.startsWith('sample-')
      )
      setBooks(clean)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'UPSC Books unavailable.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchSubjectCounts(activeTab)
    void fetchTabCounts()
    void loadBooks(selectedSubject, activeTab)
  }, [selectedSubject, activeTab])

  const handleTabChange = (newTab: 'prelims' | 'mains' | 'qa_bank') => {
    setActiveTab(newTab)
    localStorage.setItem('upsc_books_active_tab', newTab)
  }

  async function handleRefresh() {
    setRefreshing(true)
    await fetchSubjectCounts(activeTab)
    await fetchTabCounts()
    await loadBooks(selectedSubject, activeTab)
    setRefreshing(false)
  }

  const continueReadingBooks = useMemo(() => {
    const map = new Map<string, UPSCBook>()
    for (const b of books) {
      if (b.progress_percentage > 0 && b.progress_percentage < 100) {
        if (!map.has(b.id) || (map.get(b.id)?.progress_percentage || 0) < b.progress_percentage) {
          map.set(b.id, b)
        }
      }
    }
    return Array.from(map.values()).slice(0, 6)
  }, [books])

  const filteredBooks = useMemo(() => {
    let result = books
    if (savedOnly) {
      result = result.filter(b => b.saved)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(b =>
        b.title.toLowerCase().includes(q) ||
        b.subject.toLowerCase().includes(q)
      )
    }
    return result
  }, [books, savedOnly, search])

  async function toggleSave(book: UPSCBook) {
    await saveUpscBook(book.id, book.saved)
    setBooks(prev => prev.map(b => (b.id === book.id ? { ...b, saved: !b.saved } : b)))
    if (readerBook && readerBook.id === book.id) {
      setReaderBook(prev => (prev ? { ...prev, saved: !prev.saved } : null))
    }
  }

  async function openReader(book: UPSCBook, chapterId?: string, initialTab: 'material' | 'pdf' = 'material') {
    setReaderBook(book)
    setSelectedChapterId(chapterId)
    setReaderTab(initialTab)
    setReaderLoading(true)
    setProgressPct(book.progress_percentage || 10)
    try {
      const content = await getUpscBookContent(book.id, chapterId)
      setReaderContent(content)
      void updateUpscBookProgress(book.id, Math.max(10, book.progress_percentage), chapterId)
    } catch {
      setReaderContent(null)
    } finally {
      setReaderLoading(false)
    }
  }

  async function changeChapter(chapterId: string) {
    if (!readerBook) return
    setSelectedChapterId(chapterId)
    setReaderLoading(true)
    try {
      const content = await getUpscBookContent(readerBook.id, chapterId)
      setReaderContent(content)
    } catch {
      setReaderContent(null)
    } finally {
      setReaderLoading(false)
    }
  }

  function handleScroll(e: React.UIEvent<HTMLDivElement>) {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
    if (scrollHeight <= clientHeight || !readerBook) return
    const pct = Math.min(100, Math.round((scrollTop / (scrollHeight - clientHeight)) * 100))
    if (pct > progressPct) {
      setProgressPct(pct)
      void updateUpscBookProgress(readerBook.id, pct, selectedChapterId)
    }
  }

  return (
    <div className="upsc-books-page phase-four-page" style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', color: '#f8fafc' }}>
      <header className="phase-page-head" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow" style={{ color: '#60a5fa', fontWeight: 'bold', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Source: PWOnlyIAS</p>
            <h1 style={{ margin: '4px 0', fontSize: '1.8rem', color: '#f8fafc' }}>
              {selectedSubject === 'All Subjects' ? 'UPSC Books' : `UPSC Books — ${selectedSubject}`}
            </h1>
            <small style={{ color: '#94a3b8' }}>Complete static books and booklets imported from verified public PWOnlyIAS resources.</small>
          </div>
          {selectedSubject !== 'All Subjects' && (
            <button
              style={{ padding: '6px 14px', borderRadius: '6px', border: '1px solid #334155', background: '#1e293b', color: '#f8fafc', cursor: 'pointer', fontSize: '0.85rem' }}
              onClick={() => setSelectedSubject('All Subjects')}
            >
              ← All Subjects
            </button>
          )}
        </div>
      </header>

      {/* Three Primary Sections Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #334155', marginBottom: '24px', flexWrap: 'wrap' }}>
        <button
          style={{
            padding: '10px 20px',
            background: 'none',
            border: 'none',
            color: activeTab === 'prelims' ? '#60a5fa' : '#94a3b8',
            borderBottom: activeTab === 'prelims' ? '3px solid #3b82f6' : '3px solid transparent',
            fontWeight: 'bold',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
          onClick={() => handleTabChange('prelims')}
        >
          Prelims Books ({tabCounts.prelims})
        </button>
        <button
          style={{
            padding: '10px 20px',
            background: 'none',
            border: 'none',
            color: activeTab === 'mains' ? '#60a5fa' : '#94a3b8',
            borderBottom: activeTab === 'mains' ? '3px solid #3b82f6' : '3px solid transparent',
            fontWeight: 'bold',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
          onClick={() => handleTabChange('mains')}
        >
          Mains Books ({tabCounts.mains})
        </button>
        <button
          style={{
            padding: '10px 20px',
            background: 'none',
            border: 'none',
            color: activeTab === 'qa_bank' ? '#60a5fa' : '#94a3b8',
            borderBottom: activeTab === 'qa_bank' ? '3px solid #3b82f6' : '3px solid transparent',
            fontWeight: 'bold',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
          onClick={() => handleTabChange('qa_bank')}
        >
          Q/A Bank ({tabCounts.qa_bank})
        </button>
      </div>

      {/* Mandatory Subject Selector & Filter Controls Bar */}
      <section className="premium-card" style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Mandated Subject Selector Dropdown */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '220px', flex: '0 1 auto' }}>
            <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa', textTransform: 'uppercase' }}>
              Select Subject
            </label>
            <select
              value={selectedSubject}
              onChange={e => setSelectedSubject(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#f8fafc', fontSize: '0.9rem', width: '100%', cursor: 'pointer' }}
            >
              {MANDATED_SUBJECTS.map(subj => {
                const count = subj === 'All Subjects' ? Object.values(subjectCounts).reduce((a, b) => a + b, 0) : (subjectCounts[subj] || 0)
                return (
                  <option key={subj} value={subj}>
                    {subj} ({count})
                  </option>
                )
              })}
            </select>
          </div>

          {/* Search Bar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: '220px' }}>
            <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase' }}>Search</label>
            <input
              type="text"
              placeholder="Search books by title..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#f8fafc', fontSize: '0.9rem' }}
            />
          </div>

          {/* Checkboxes */}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '18px' }}>
            <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer', color: '#e2e8f0' }}>
              <input type="checkbox" checked={savedOnly} onChange={e => setSavedOnly(e.target.checked)} />
              Saved Only
            </label>
          </div>
        </div>
      </section>

      {loading ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading official PWOnlyIAS books...</div>
      ) : error ? (
        <div style={{ padding: '24px', background: '#451a1a', border: '1px solid #7f1d1d', color: '#fca5a5', borderRadius: '8px' }}>{error}</div>
      ) : filteredBooks.length === 0 ? (
        /* Honest Subject-Aware Empty State Card */
        <section className="premium-card" style={{ padding: '48px 24px', background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', textAlign: 'center', maxWidth: '650px', margin: '30px auto' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📚</div>
          <h2 style={{ fontSize: '1.3rem', color: '#f8fafc', marginBottom: '8px' }}>
            {activeTab === 'prelims' && "No verified Prelims books have been imported yet."}
            {activeTab === 'mains' && "No verified Mains books have been imported yet."}
            {activeTab === 'qa_bank' && "No verified Q/A Bank resources have been imported yet."}
          </h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '24px' }}>
            {activeTab === 'prelims' && "Import a PWOnlyIAS PDF and classify it as Prelims to make it available here."}
            {activeTab === 'mains' && "Import a PWOnlyIAS PDF and classify it as Mains to make it available here."}
            {activeTab === 'qa_bank' && "Question banks and solved-practice PDFs classified as Q/A Bank will appear here."}
          </p>
          <button
            className="send-button"
            disabled={refreshing}
            style={{ padding: '10px 24px', fontSize: '0.9rem', cursor: 'pointer' }}
            onClick={() => void handleRefresh()}
          >
            {refreshing ? 'Checking for Books...' : 'Check for Books'}
          </button>
        </section>
      ) : (
        <>
          {/* Optional Subject Cards Overview */}
          {selectedSubject === 'All Subjects' && Object.keys(subjectCounts).length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#f8fafc' }}>Subjects Overview</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px' }}>
                {Object.entries(subjectCounts).map(([subj, count]) => (
                  <article
                    key={subj}
                    onClick={() => setSelectedSubject(subj)}
                    style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', cursor: 'pointer', transition: 'border-color 0.2s' }}
                  >
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa', textTransform: 'uppercase' }}>Subject</span>
                    <h3 style={{ margin: '6px 0 4px 0', fontSize: '1.05rem', color: '#f8fafc' }}>{subj}</h3>
                    <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>{count} official books</p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* Continue Reading Section (Deduplicated) */}
          {continueReadingBooks.length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#f8fafc' }}>Continue Reading</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                {continueReadingBooks.map(b => (
                  <article key={b.id} style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#60a5fa', fontWeight: 'bold' }}>{b.subject}</span>
                    <h3 style={{ margin: '4px 0', fontSize: '1rem', color: '#f8fafc' }}>{b.title}</h3>
                    <div style={{ background: '#0f172a', height: '6px', borderRadius: '3px', margin: '10px 0 6px 0' }}>
                      <div style={{ background: '#3b82f6', height: '100%', width: `${b.progress_percentage}%`, borderRadius: '3px' }} />
                    </div>
                    <small style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{Math.round(b.progress_percentage)}% completed</small>
                    <div style={{ marginTop: '10px' }}>
                      <button className="send-button" style={{ padding: '4px 12px', fontSize: '0.85rem' }} onClick={() => openReader(b, undefined, 'material')}>
                        Resume Book
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* Books Grid List */}
          <section>
            <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#f8fafc' }}>
              {selectedSubject !== 'All Subjects' ? `${selectedSubject} Books` : 'All Available Books'} ({filteredBooks.length})
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
              {filteredBooks.map(book => (
                <article key={book.id} style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa' }}>{book.subject}</span>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {book.resource_kind === 'qa_bank' ? (
                        <span style={{ fontSize: '0.7rem', background: '#3b82f6', color: '#eff6ff', padding: '2px 6px', borderRadius: '4px' }}>Q/A Bank</span>
                      ) : (
                        <>
                          {book.prelims_relevant && <span style={{ fontSize: '0.7rem', background: '#064e3b', color: '#a7f3d0', padding: '2px 6px', borderRadius: '4px' }}>Prelims</span>}
                          {book.mains_relevant && <span style={{ fontSize: '0.7rem', background: '#7c2d12', color: '#ffedd5', padding: '2px 6px', borderRadius: '4px' }}>Mains</span>}
                        </>
                      )}
                    </div>
                  </div>

                  <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem', color: '#f8fafc' }}>{book.title}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#cbd5e1', flex: 1, marginBottom: '12px' }}>{book.description || book.title}</p>

                  <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '12px', display: 'flex', gap: '12px' }}>
                    <span>⏱️ {book.estimated_reading_minutes} min</span>
                    <span>📄 {book.page_count} pages</span>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #334155' }}>
                    <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => openReader(book, undefined, 'material')}>
                      Read Book
                    </button>
                    <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem', background: '#3b82f6', color: '#f8fafc' }} onClick={() => openReader(book, undefined, 'pdf')}>
                      View PDF
                    </button>
                    <a href={book.official_source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#60a5fa' }}>
                      Official Source
                    </a>
                    <button onClick={() => void toggleSave(book)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', color: '#94a3b8' }}>
                      {book.saved ? '♥ Saved' : '♡ Save'}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      )}

      {/* Internal Book Reader Modal */}
      {readerBook && (
        <div className="ca-modal" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <article style={{ background: '#0f172a', border: '1px solid #334155', width: '100%', maxWidth: '900px', maxHeight: '92vh', display: 'flex', flexDirection: 'column', borderRadius: '12px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)', color: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#60a5fa' }}>Source: PWOnlyIAS</span>
                  <span style={{ fontSize: '0.75rem', background: '#1e3a8a', color: '#93c5fd', padding: '2px 8px', borderRadius: '4px' }}>{readerBook.subject}</span>
                </div>
                <h2 style={{ margin: '4px 0 0 0', fontSize: '1.4rem', color: '#f8fafc' }}>{readerBook.title}</h2>
              </div>
              <button className="icon-button" style={{ padding: '6px 12px', border: '1px solid #334155', borderRadius: '6px', background: '#1e293b', color: '#f8fafc', cursor: 'pointer' }} onClick={() => setReaderBook(null)}>
                ✕ Close
              </button>
            </div>

            {/* Tabs for Read Material vs Original PDF */}
            <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #334155', marginBottom: '16px' }}>
              <button
                style={{
                  padding: '8px 16px',
                  background: 'none',
                  border: 'none',
                  color: readerTab === 'material' ? '#60a5fa' : '#94a3b8',
                  borderBottom: readerTab === 'material' ? '2px solid #3b82f6' : '2px solid transparent',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
                onClick={() => setReaderTab('material')}
              >
                Read Material
              </button>
              <button
                style={{
                  padding: '8px 16px',
                  background: 'none',
                  border: 'none',
                  color: readerTab === 'pdf' ? '#60a5fa' : '#94a3b8',
                  borderBottom: readerTab === 'pdf' ? '2px solid #3b82f6' : '2px solid transparent',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
                onClick={() => setReaderTab('pdf')}
              >
                Original PDF
              </button>
            </div>

            {/* Chapter Selector */}
            {readerContent?.chapters && readerContent.chapters.length > 0 && readerTab === 'material' && (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#e2e8f0' }}>Chapters:</span>
                <button
                  style={{ padding: '4px 10px', fontSize: '0.8rem', borderRadius: '4px', border: '1px solid #334155', background: !selectedChapterId ? '#3b82f6' : '#1e293b', color: '#f8fafc', cursor: 'pointer' }}
                  onClick={() => openReader(readerBook, undefined, 'material')}
                >
                  All Chapters
                </button>
                {readerContent.chapters.map(ch => (
                  <button
                    key={ch.id}
                    style={{ padding: '4px 10px', fontSize: '0.8rem', borderRadius: '4px', border: '1px solid #334155', background: selectedChapterId === ch.id ? '#3b82f6' : '#1e293b', color: '#f8fafc', cursor: 'pointer' }}
                    onClick={() => changeChapter(ch.id)}
                  >
                    Ch {ch.chapter_order}: {ch.title}
                  </button>
                ))}
              </div>
            )}

            {readerLoading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading book content...</div>
            ) : readerTab === 'material' ? (
              <div
                onScroll={handleScroll}
                style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '8px' }}
              >
                {/* Structured Blocks */}
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
                        {block.type === 'numbered_list' && block.items && (
                          <ol style={{ paddingLeft: '20px', fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6' }}>
                            {block.items.map((it, idx) => <li key={idx}>{it}</li>)}
                          </ol>
                        )}
                        {block.type === 'important_fact' && (
                          <div style={{ padding: '10px 14px', background: '#064e3b', borderLeft: '4px solid #10b981', borderRadius: '4px', margin: '8px 0', fontSize: '0.9rem', color: '#a7f3d0' }}>
                            <strong>Key Concept:</strong> {block.text}
                          </div>
                        )}
                        {block.page_ref && <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Page Ref: p. {block.page_ref}</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ padding: '16px', background: '#451a1a', color: '#fca5a5', borderRadius: '8px', fontSize: '0.9rem' }}>
                    {readerBook.extraction_status === 'image_only'
                      ? 'This book could not be extracted. You can still view the original PDF in the Original PDF tab.'
                      : 'Book content summary ready.'}
                  </div>
                )}
              </div>
            ) : (
              /* Original PDF Tab using secure endpoint */
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
                <object
                  data={`${API_BASE_URL}/upsc-books/${readerBook.id}/pdf`}
                  type="application/pdf"
                  style={{ width: '100%', height: '100%', minHeight: '520px', border: 'none', borderRadius: '8px' }}
                >
                  <div style={{ padding: '24px', textAlign: 'center', background: '#1e293b', borderRadius: '8px' }}>
                    <p style={{ marginBottom: '16px', color: '#94a3b8' }}>PDF preview is not supported by your browser or cannot be embedded.</p>
                    <a
                      href={`${API_BASE_URL}/upsc-books/${readerBook.id}/pdf`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="send-button"
                      style={{ display: 'inline-block', textDecoration: 'none', padding: '8px 16px' }}
                    >
                      Open PDF in New Tab
                    </a>
                  </div>
                </object>
              </div>
            )}

            {/* Reader Footer Actions */}
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #334155', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                className="send-button"
                disabled={readerBook.indexing_status !== 'indexed'}
                style={{
                  padding: '8px 14px',
                  fontSize: '0.85rem',
                  opacity: readerBook.indexing_status === 'indexed' ? 1 : 0.5,
                  cursor: readerBook.indexing_status === 'indexed' ? 'pointer' : 'not-allowed'
                }}
                onClick={() => {
                  if (readerBook.indexing_status === 'indexed') {
                    setReaderBook(null);
                    onNavigate('chat');
                  }
                }}
              >
                Ask AI About Book
              </button>
              {readerBook.resource_kind !== 'qa_bank' && (
                <>
                  <button
                    className="send-button"
                    disabled={!readerBook.prelims_relevant || readerBook.indexing_status !== 'indexed'}
                    style={{
                      padding: '8px 14px',
                      background: '#059669',
                      fontSize: '0.85rem',
                      opacity: (readerBook.prelims_relevant && readerBook.indexing_status === 'indexed') ? 1 : 0.5,
                      cursor: (readerBook.prelims_relevant && readerBook.indexing_status === 'indexed') ? 'pointer' : 'not-allowed'
                    }}
                    onClick={() => {
                      if (readerBook.prelims_relevant && readerBook.indexing_status === 'indexed') {
                        setReaderBook(null);
                        onNavigate('quizzes');
                      }
                    }}
                  >
                    Generate Prelims Quiz
                  </button>
                  <button
                    className="send-button"
                    disabled={!readerBook.mains_relevant || readerBook.indexing_status !== 'indexed'}
                    style={{
                      padding: '8px 14px',
                      background: '#d97706',
                      fontSize: '0.85rem',
                      opacity: (readerBook.mains_relevant && readerBook.indexing_status === 'indexed') ? 1 : 0.5,
                      cursor: (readerBook.mains_relevant && readerBook.indexing_status === 'indexed') ? 'pointer' : 'not-allowed'
                    }}
                    onClick={() => {
                      if (readerBook.mains_relevant && readerBook.indexing_status === 'indexed') {
                        setReaderBook(null);
                        onNavigate('quizzes');
                      }
                    }}
                  >
                    Mains Practice
                  </button>
                  <button
                    className="send-button"
                    disabled={readerBook.indexing_status !== 'indexed'}
                    style={{
                      padding: '8px 14px',
                      background: '#4f46e5',
                      fontSize: '0.85rem',
                      opacity: readerBook.indexing_status === 'indexed' ? 1 : 0.5,
                      cursor: readerBook.indexing_status === 'indexed' ? 'pointer' : 'not-allowed'
                    }}
                    onClick={() => {
                      if (readerBook.indexing_status === 'indexed') {
                        setReaderBook(null);
                        onNavigate('revision');
                      }
                    }}
                  >
                    Quick Revision
                  </button>
                </>
              )}
              <a href={readerBook.official_source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 12px', border: '1px solid #334155', borderRadius: '6px', textDecoration: 'none', color: '#60a5fa', fontSize: '0.85rem', fontWeight: '500' }}>
                Official Source
              </a>
              <a href={`${API_BASE_URL}/upsc-books/${readerBook.id}/pdf`} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 12px', border: '1px solid #059669', color: '#34d399', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                Open PDF
              </a>
              <button onClick={() => void toggleSave(readerBook)} style={{ marginLeft: 'auto', background: 'none', border: '1px solid #334155', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem', color: '#94a3b8' }}>
                {readerBook.saved ? '♥ Saved' : '♡ Save Book'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
