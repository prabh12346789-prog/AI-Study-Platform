import { useEffect, useMemo, useState } from 'react'
import {
  BookSubjectCount,
  UPSCBook,
  UPSCBookContentResponse,
  getUpscBookContent,
  getUpscBookSubjects,
  getUpscBooks,
  saveUpscBook,
  updateUpscBookProgress
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
  const [subjectCounts, setSubjectCounts] = useState<Record<string, number>>({})
  const [books, setBooks] = useState<UPSCBook[]>([])
  const [selectedSubject, setSelectedSubject] = useState<string>('All Subjects')

  const [search, setSearch] = useState('')
  const [prelimsOnly, setPrelimsOnly] = useState(false)
  const [mainsOnly, setMainsOnly] = useState(false)
  const [savedOnly, setSavedOnly] = useState(false)

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const [readerBook, setReaderBook] = useState<UPSCBook | null>(null)
  const [readerContent, setReaderContent] = useState<UPSCBookContentResponse | null>(null)
  const [selectedChapterId, setSelectedChapterId] = useState<string | undefined>(undefined)
  const [readerLoading, setReaderLoading] = useState(false)
  const [progressPct, setProgressPct] = useState(0)

  async function fetchSubjectCounts() {
    try {
      const counts = await getUpscBookSubjects()
      const map: Record<string, number> = {}
      counts.forEach(s => { map[s.subject] = s.book_count })
      setSubjectCounts(map)
    } catch {
      setSubjectCounts({})
    }
  }

  async function loadBooks(subj: string) {
    setLoading(true)
    setError('')
    try {
      const param = subj !== 'All Subjects' ? `subject=${encodeURIComponent(subj)}` : ''
      const booksData = await getUpscBooks(param)
      // Exclude any synthetic test books
      const clean = booksData.filter(b =>
        !b.title.toLowerCase().includes('isolated test book') &&
        !b.title.toLowerCase().includes('prog book') &&
        !b.id.startsWith('test-') &&
        !b.id.startsWith('isolated-')
      )
      setBooks(clean)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'UPSC Books unavailable.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchSubjectCounts()
    void loadBooks(selectedSubject)
  }, [selectedSubject])

  async function handleRefresh() {
    setRefreshing(true)
    await fetchSubjectCounts()
    await loadBooks(selectedSubject)
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
    if (prelimsOnly) {
      result = result.filter(b => b.prelims_relevant)
    }
    if (mainsOnly) {
      result = result.filter(b => b.mains_relevant)
    }
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
  }, [books, prelimsOnly, mainsOnly, savedOnly, search])

  async function toggleSave(book: UPSCBook) {
    await saveUpscBook(book.id, book.saved)
    setBooks(prev => prev.map(b => (b.id === book.id ? { ...b, saved: !b.saved } : b)))
    if (readerBook && readerBook.id === book.id) {
      setReaderBook(prev => (prev ? { ...prev, saved: !prev.saved } : null))
    }
  }

  async function openReader(book: UPSCBook, chapterId?: string) {
    setReaderBook(book)
    setSelectedChapterId(chapterId)
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
              <input type="checkbox" checked={prelimsOnly} onChange={e => setPrelimsOnly(e.target.checked)} />
              Prelims
            </label>
            <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer', color: '#e2e8f0' }}>
              <input type="checkbox" checked={mainsOnly} onChange={e => setMainsOnly(e.target.checked)} />
              Mains
            </label>
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
            {selectedSubject === 'All Subjects'
              ? 'No verified PWOnlyIAS books have been imported yet.'
              : 'No verified books available yet'}
          </h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '24px' }}>
            {selectedSubject === 'All Subjects'
              ? 'Books will appear here after a publicly accessible PWOnlyIAS PDF is verified, extracted and indexed.'
              : `No publicly accessible PWOnlyIAS book has been verified and imported for ${selectedSubject} yet.`}
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
                      <button className="send-button" style={{ padding: '4px 12px', fontSize: '0.85rem' }} onClick={() => openReader(b)}>
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
                      {book.prelims_relevant && <span style={{ fontSize: '0.7rem', background: '#064e3b', color: '#a7f3d0', padding: '2px 6px', borderRadius: '4px' }}>Prelims</span>}
                      {book.mains_relevant && <span style={{ fontSize: '0.7rem', background: '#7c2d12', color: '#ffedd5', padding: '2px 6px', borderRadius: '4px' }}>Mains</span>}
                    </div>
                  </div>

                  <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem', color: '#f8fafc' }}>{book.title}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#cbd5e1', flex: 1, marginBottom: '12px' }}>{book.description || book.title}</p>

                  <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '12px', display: 'flex', gap: '12px' }}>
                    <span>⏱️ {book.estimated_reading_minutes} min</span>
                    <span>📄 {book.page_count} pages</span>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #334155' }}>
                    <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => openReader(book)}>
                      Read Book
                    </button>
                    <a href={book.official_source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#60a5fa' }}>
                      Official Source
                    </a>
                    {book.official_pdf_url && (
                      <a href={book.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#34d399' }}>
                        View PDF
                      </a>
                    )}
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

            {/* Reading progress bar */}
            <div style={{ background: '#1e293b', height: '4px', borderRadius: '2px', marginBottom: '14px' }}>
              <div style={{ background: '#3b82f6', height: '100%', width: `${progressPct}%`, borderRadius: '2px', transition: 'width 0.3s' }} />
            </div>

            {/* Chapter Selector */}
            {readerContent?.chapters && readerContent.chapters.length > 0 && (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#e2e8f0' }}>Chapters:</span>
                <button
                  style={{ padding: '4px 10px', fontSize: '0.8rem', borderRadius: '4px', border: '1px solid #334155', background: !selectedChapterId ? '#3b82f6' : '#1e293b', color: '#f8fafc', cursor: 'pointer' }}
                  onClick={() => openReader(readerBook, undefined)}
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
            ) : (
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
                      ? 'This book could not be extracted. You can still view the original PDF.'
                      : 'Book content summary ready.'}
                  </div>
                )}
              </div>
            )}

            {/* Reader Footer Actions */}
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #334155', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="send-button" style={{ padding: '8px 14px', fontSize: '0.85rem' }} onClick={() => { setReaderBook(null); onNavigate('chat') }}>
                Ask AI About Book
              </button>
              <button className="send-button" style={{ padding: '8px 14px', background: '#059669', fontSize: '0.85rem' }} onClick={() => { setReaderBook(null); onNavigate('quizzes') }}>
                Generate Prelims Quiz
              </button>
              <button className="send-button" style={{ padding: '8px 14px', background: '#d97706', fontSize: '0.85rem' }} onClick={() => { setReaderBook(null); onNavigate('quizzes') }}>
                Mains Practice
              </button>
              <button className="send-button" style={{ padding: '8px 14px', background: '#4f46e5', fontSize: '0.85rem' }} onClick={() => { setReaderBook(null); onNavigate('revision') }}>
                Quick Revision
              </button>
              <a href={readerBook.official_source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 12px', border: '1px solid #334155', borderRadius: '6px', textDecoration: 'none', color: '#60a5fa', fontSize: '0.85rem', fontWeight: '500' }}>
                Official Source
              </a>
              {readerBook.official_pdf_url && (
                <a href={readerBook.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 12px', border: '1px solid #059669', color: '#34d399', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                  View PDF
                </a>
              )}
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
