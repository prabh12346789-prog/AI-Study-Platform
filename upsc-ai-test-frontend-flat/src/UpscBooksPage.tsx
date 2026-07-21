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

export function UpscBooksPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [subjects, setSubjects] = useState<BookSubjectCount[]>([])
  const [books, setBooks] = useState<UPSCBook[]>([])
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [prelimsOnly, setPrelimsOnly] = useState(false)
  const [mainsOnly, setMainsOnly] = useState(false)
  const [savedOnly, setSavedOnly] = useState(false)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [readerBook, setReaderBook] = useState<UPSCBook | null>(null)
  const [readerContent, setReaderContent] = useState<UPSCBookContentResponse | null>(null)
  const [selectedChapterId, setSelectedChapterId] = useState<string | undefined>(undefined)
  const [readerLoading, setReaderLoading] = useState(false)
  const [progressPct, setProgressPct] = useState(0)

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [subjData, booksData] = await Promise.all([
        getUpscBookSubjects(),
        getUpscBooks()
      ])
      setSubjects(subjData.filter(s => s.book_count > 0))
      setBooks(booksData)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'UPSC Books unavailable.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const continueReadingBooks = useMemo(() => {
    return books.filter(b => b.progress_percentage > 0 && b.progress_percentage < 100)
  }, [books])

  const filteredBooks = useMemo(() => {
    let result = books
    if (selectedSubject) {
      result = result.filter(b => b.subject === selectedSubject)
    }
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
  }, [books, selectedSubject, prelimsOnly, mainsOnly, savedOnly, search])

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
    <div className="upsc-books-page phase-four-page" style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <header className="phase-page-head" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow" style={{ color: '#2563eb', fontWeight: 'bold', fontSize: '0.85rem' }}>Source: PWOnlyIAS</p>
            <h1 style={{ margin: '4px 0', fontSize: '1.8rem', color: '#0f172a' }}>UPSC Books</h1>
            <small style={{ color: '#64748b' }}>Complete static books & booklets exclusively from official PWOnlyIAS resources.</small>
          </div>
          {selectedSubject && (
            <button
              style={{ padding: '6px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: 'pointer', fontSize: '0.85rem' }}
              onClick={() => setSelectedSubject(null)}
            >
              ← All Subjects
            </button>
          )}
        </div>
      </header>

      {/* Search & Filters */}
      <section className="premium-card" style={{ padding: '16px', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search books by title or subject..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: '240px', padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.9rem' }}
          />
          <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={prelimsOnly} onChange={e => setPrelimsOnly(e.target.checked)} />
            Prelims
          </label>
          <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={mainsOnly} onChange={e => setMainsOnly(e.target.checked)} />
            Mains
          </label>
          <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={savedOnly} onChange={e => setSavedOnly(e.target.checked)} />
            Saved Only
          </label>
        </div>
      </section>

      {loading ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Loading official PWOnlyIAS books...</div>
      ) : error ? (
        <div style={{ padding: '24px', background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', borderRadius: '8px' }}>{error}</div>
      ) : (
        <>
          {/* Subject Cards Overview */}
          {!selectedSubject && subjects.length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#0f172a' }}>Subjects Overview</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px' }}>
                {subjects.map(s => (
                  <article
                    key={s.subject}
                    onClick={() => setSelectedSubject(s.subject)}
                    style={{ padding: '16px', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', cursor: 'pointer', transition: 'border-color 0.2s' }}
                  >
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#2563eb', textTransform: 'uppercase' }}>Subject</span>
                    <h3 style={{ margin: '6px 0 4px 0', fontSize: '1.05rem', color: '#0f172a' }}>{s.subject}</h3>
                    <p style={{ fontSize: '0.85rem', color: '#64748b', margin: 0 }}>{s.book_count} official books</p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* Continue Reading Section */}
          {!selectedSubject && continueReadingBooks.length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#0f172a' }}>Continue Reading</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                {continueReadingBooks.map(b => (
                  <article key={b.id} style={{ padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 'bold' }}>{b.subject}</span>
                    <h3 style={{ margin: '4px 0', fontSize: '1rem' }}>{b.title}</h3>
                    <div style={{ background: '#e2e8f0', height: '6px', borderRadius: '3px', margin: '10px 0 6px 0' }}>
                      <div style={{ background: '#2563eb', height: '100%', width: `${b.progress_percentage}%`, borderRadius: '3px' }} />
                    </div>
                    <small style={{ color: '#64748b', fontSize: '0.8rem' }}>{Math.round(b.progress_percentage)}% completed</small>
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

          {/* Books List Grid */}
          <section>
            <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#0f172a' }}>
              {selectedSubject ? `${selectedSubject} Books` : 'All Available Books'} ({filteredBooks.length})
            </h2>
            {filteredBooks.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
                {filteredBooks.map(book => (
                  <article key={book.id} style={{ padding: '16px', background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '10px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#2563eb' }}>{book.subject}</span>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {book.prelims_relevant && <span style={{ fontSize: '0.7rem', background: '#ecfdf5', color: '#047857', padding: '2px 6px', borderRadius: '4px' }}>Prelims</span>}
                        {book.mains_relevant && <span style={{ fontSize: '0.7rem', background: '#fff7ed', color: '#c2410c', padding: '2px 6px', borderRadius: '4px' }}>Mains</span>}
                      </div>
                    </div>

                    <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem', color: '#0f172a' }}>{book.title}</h3>
                    <p style={{ fontSize: '0.85rem', color: '#475569', flex: 1, marginBottom: '12px' }}>{book.description || book.title}</p>

                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '12px', display: 'flex', gap: '12px' }}>
                      <span>⏱️ {book.estimated_reading_minutes} min</span>
                      <span>📄 {book.page_count} pages</span>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #f1f5f9' }}>
                      <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => openReader(book)}>
                        Read Book
                      </button>
                      <a href={book.official_source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#2563eb' }}>
                        Official Source
                      </a>
                      {book.official_pdf_url && (
                        <a href={book.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#059669' }}>
                          View PDF
                        </a>
                      )}
                      <button onClick={() => void toggleSave(book)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', color: '#64748b' }}>
                        {book.saved ? '♥ Saved' : '♡ Save'}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p style={{ color: '#64748b' }}>No books found matching your filters.</p>
            )}
          </section>
        </>
      )}

      {/* Internal Book Reader Modal */}
      {readerBook && (
        <div className="ca-modal" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <article style={{ background: '#ffffff', width: '100%', maxWidth: '900px', maxHeight: '92vh', display: 'flex', flexDirection: 'column', borderRadius: '12px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#2563eb' }}>Source: PWOnlyIAS</span>
                  <span style={{ fontSize: '0.75rem', background: '#eff6ff', color: '#1d4ed8', padding: '2px 8px', borderRadius: '4px' }}>{readerBook.subject}</span>
                </div>
                <h2 style={{ margin: '4px 0 0 0', fontSize: '1.4rem', color: '#0f172a' }}>{readerBook.title}</h2>
              </div>
              <button className="icon-button" style={{ padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#f8fafc', cursor: 'pointer' }} onClick={() => setReaderBook(null)}>
                ✕ Close
              </button>
            </div>

            {/* Reading progress bar */}
            <div style={{ background: '#e2e8f0', height: '4px', borderRadius: '2px', marginBottom: '14px' }}>
              <div style={{ background: '#2563eb', height: '100%', width: `${progressPct}%`, borderRadius: '2px', transition: 'width 0.3s' }} />
            </div>

            {/* Chapter Selector if chapters present */}
            {readerContent?.chapters && readerContent.chapters.length > 0 && (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#334155' }}>Chapters:</span>
                <button
                  style={{ padding: '4px 10px', fontSize: '0.8rem', borderRadius: '4px', border: '1px solid #cbd5e1', background: !selectedChapterId ? '#2563eb' : '#ffffff', color: !selectedChapterId ? '#ffffff' : '#334155', cursor: 'pointer' }}
                  onClick={() => openReader(readerBook, undefined)}
                >
                  All Chapters
                </button>
                {readerContent.chapters.map(ch => (
                  <button
                    key={ch.id}
                    style={{ padding: '4px 10px', fontSize: '0.8rem', borderRadius: '4px', border: '1px solid #cbd5e1', background: selectedChapterId === ch.id ? '#2563eb' : '#ffffff', color: selectedChapterId === ch.id ? '#ffffff' : '#334155', cursor: 'pointer' }}
                    onClick={() => changeChapter(ch.id)}
                  >
                    Ch {ch.chapter_order}: {ch.title}
                  </button>
                ))}
              </div>
            )}

            {readerLoading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Loading book content...</div>
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
                          <h3 style={{ margin: '12px 0 6px 0', color: '#0f172a', fontSize: '1.1rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>
                            {block.text || block.title}
                          </h3>
                        )}
                        {block.type === 'paragraph' && block.text && (
                          <p style={{ fontSize: '0.95rem', color: '#334155', lineHeight: '1.6', margin: '4px 0' }}>{block.text}</p>
                        )}
                        {(block.type === 'bullet_list' || block.items) && (
                          <ul style={{ paddingLeft: '20px', fontSize: '0.95rem', color: '#334155', lineHeight: '1.6' }}>
                            {(block.items || []).map((it, idx) => <li key={idx}>{it}</li>)}
                          </ul>
                        )}
                        {block.type === 'numbered_list' && block.items && (
                          <ol style={{ paddingLeft: '20px', fontSize: '0.95rem', color: '#334155', lineHeight: '1.6' }}>
                            {block.items.map((it, idx) => <li key={idx}>{it}</li>)}
                          </ol>
                        )}
                        {block.type === 'important_fact' && (
                          <div style={{ padding: '10px 14px', background: '#ecfdf5', borderLeft: '4px solid #10b981', borderRadius: '4px', margin: '8px 0', fontSize: '0.9rem', color: '#065f46' }}>
                            <strong>Key Concept:</strong> {block.text}
                          </div>
                        )}
                        {block.page_ref && <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Page Ref: p. {block.page_ref}</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ padding: '16px', background: '#fffbeb', color: '#b45309', borderRadius: '8px', fontSize: '0.9rem' }}>
                    {readerBook.extraction_status === 'image_only'
                      ? 'This book could not be extracted. You can still view the original PDF.'
                      : 'Book content summary ready.'}
                  </div>
                )}
              </div>
            )}

            {/* Reader Footer Actions */}
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
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
              <a href={readerBook.official_source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', textDecoration: 'none', color: '#2563eb', fontSize: '0.85rem', fontWeight: '500' }}>
                Official Source
              </a>
              {readerBook.official_pdf_url && (
                <a href={readerBook.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 12px', border: '1px solid #059669', color: '#059669', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                  View PDF
                </a>
              )}
              <button onClick={() => void toggleSave(readerBook)} style={{ marginLeft: 'auto', background: 'none', border: '1px solid #cbd5e1', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
                {readerBook.saved ? '♥ Saved' : '♡ Save Book'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
