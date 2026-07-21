import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  NoteSubjectCount,
  UPSCNote,
  UPSCNoteContentResponse,
  getUpscNoteContent,
  getUpscNoteSubjects,
  getUpscNotes,
  saveUpscNote,
  updateUpscNoteProgress
} from './api'
import type { AppPage } from './AppShell'

export function UpscNotesPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [subjects, setSubjects] = useState<NoteSubjectCount[]>([])
  const [notes, setNotes] = useState<UPSCNote[]>([])
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [prelimsOnly, setPrelimsOnly] = useState(false)
  const [mainsOnly, setMainsOnly] = useState(false)
  const [savedOnly, setSavedOnly] = useState(false)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [readerNote, setReaderNote] = useState<UPSCNote | null>(null)
  const [readerContent, setReaderContent] = useState<UPSCNoteContentResponse | null>(null)
  const [readerLoading, setReaderLoading] = useState(false)
  const [progressPct, setProgressPct] = useState(0)

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [subjData, notesData] = await Promise.all([
        getUpscNoteSubjects(),
        getUpscNotes()
      ])
      setSubjects(subjData.filter(s => s.note_count > 0))
      setNotes(notesData)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'UPSC Notes unavailable.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const continueReadingNotes = useMemo(() => {
    return notes.filter(n => n.progress_percentage > 0 && n.progress_percentage < 100)
  }, [notes])

  const filteredNotes = useMemo(() => {
    let result = notes
    if (selectedSubject) {
      result = result.filter(n => n.subject === selectedSubject)
    }
    if (prelimsOnly) {
      result = result.filter(n => n.prelims_relevant)
    }
    if (mainsOnly) {
      result = result.filter(n => n.mains_relevant)
    }
    if (savedOnly) {
      result = result.filter(n => n.saved)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(n =>
        n.title.toLowerCase().includes(q) ||
        n.subject.toLowerCase().includes(q) ||
        n.topic.toLowerCase().includes(q)
      )
    }
    return result
  }, [notes, selectedSubject, prelimsOnly, mainsOnly, savedOnly, search])

  async function toggleSave(note: UPSCNote) {
    await saveUpscNote(note.id, note.saved)
    setNotes(prev => prev.map(n => (n.id === note.id ? { ...n, saved: !n.saved } : n)))
    if (readerNote && readerNote.id === note.id) {
      setReaderNote(prev => (prev ? { ...prev, saved: !prev.saved } : null))
    }
  }

  async function openReader(note: UPSCNote) {
    setReaderNote(note)
    setReaderLoading(true)
    setProgressPct(note.progress_percentage || 10)
    try {
      const content = await getUpscNoteContent(note.id)
      setReaderContent(content)
      // Save initial progress
      void updateUpscNoteProgress(note.id, Math.max(10, note.progress_percentage))
    } catch {
      setReaderContent(null)
    } finally {
      setReaderLoading(false)
    }
  }

  function handleScroll(e: React.UIEvent<HTMLDivElement>) {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
    if (scrollHeight <= clientHeight || !readerNote) return
    const pct = Math.min(100, Math.round((scrollTop / (scrollHeight - clientHeight)) * 100))
    if (pct > progressPct) {
      setProgressPct(pct)
      void updateUpscNoteProgress(readerNote.id, pct)
    }
  }

  return (
    <div className="upsc-notes-page phase-four-page" style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <header className="phase-page-head" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow" style={{ color: '#2563eb', fontWeight: 'bold', fontSize: '0.85rem' }}>Source: PWOnlyIAS</p>
            <h1 style={{ margin: '4px 0', fontSize: '1.8rem', color: '#0f172a' }}>UPSC Notes</h1>
            <small style={{ color: '#64748b' }}>Static syllabus-oriented study materials exclusively from official PWOnlyIAS resources.</small>
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
            placeholder="Search notes by title, subject, or topic..."
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
        <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Loading official PWOnlyIAS study notes...</div>
      ) : error ? (
        <div style={{ padding: '24px', background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', borderRadius: '8px' }}>{error}</div>
      ) : (
        <>
          {/* Subject Cards (Home View) */}
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
                    <p style={{ fontSize: '0.85rem', color: '#64748b', margin: 0 }}>{s.note_count} ready study notes</p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* Continue Reading Section */}
          {!selectedSubject && continueReadingNotes.length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#0f172a' }}>Continue Reading</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                {continueReadingNotes.map(n => (
                  <article key={n.id} style={{ padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 'bold' }}>{n.subject}</span>
                    <h3 style={{ margin: '4px 0', fontSize: '1rem' }}>{n.title}</h3>
                    <div style={{ background: '#e2e8f0', height: '6px', borderRadius: '3px', margin: '10px 0 6px 0' }}>
                      <div style={{ background: '#2563eb', height: '100%', width: `${n.progress_percentage}%`, borderRadius: '3px' }} />
                    </div>
                    <small style={{ color: '#64748b', fontSize: '0.8rem' }}>{Math.round(n.progress_percentage)}% completed</small>
                    <div style={{ marginTop: '10px' }}>
                      <button className="send-button" style={{ padding: '4px 12px', fontSize: '0.85rem' }} onClick={() => openReader(n)}>
                        Resume Note
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* Notes Grid List */}
          <section>
            <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#0f172a' }}>
              {selectedSubject ? `${selectedSubject} Notes` : 'All Available Notes'} ({filteredNotes.length})
            </h2>
            {filteredNotes.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
                {filteredNotes.map(note => (
                  <article key={note.id} style={{ padding: '16px', background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '10px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#2563eb' }}>{note.subject} · {note.topic}</span>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {note.prelims_relevant && <span style={{ fontSize: '0.7rem', background: '#ecfdf5', color: '#047857', padding: '2px 6px', borderRadius: '4px' }}>Prelims</span>}
                        {note.mains_relevant && <span style={{ fontSize: '0.7rem', background: '#fff7ed', color: '#c2410c', padding: '2px 6px', borderRadius: '4px' }}>Mains</span>}
                      </div>
                    </div>

                    <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem', color: '#0f172a' }}>{note.title}</h3>
                    <p style={{ fontSize: '0.85rem', color: '#475569', flex: 1, marginBottom: '12px' }}>{note.description || note.title}</p>

                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '12px', display: 'flex', gap: '12px' }}>
                      <span>⏱️ {note.estimated_reading_minutes} min read</span>
                      <span>📄 {note.page_count} pages</span>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #f1f5f9' }}>
                      <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => openReader(note)}>
                        Read Note
                      </button>
                      <a href={note.official_source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#2563eb' }}>
                        Official Source
                      </a>
                      {note.official_pdf_url && (
                        <a href={note.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#059669' }}>
                          View PDF
                        </a>
                      )}
                      <button onClick={() => void toggleSave(note)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', color: '#64748b' }}>
                        {note.saved ? '♥ Saved' : '♡ Save'}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p style={{ color: '#64748b' }}>No notes found matching your filters.</p>
            )}
          </section>
        </>
      )}

      {/* Internal Note Reader Modal */}
      {readerNote && (
        <div className="ca-modal" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <article style={{ background: '#ffffff', width: '100%', maxWidth: '850px', maxHeight: '92vh', display: 'flex', flexDirection: 'column', borderRadius: '12px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#2563eb' }}>Source: PWOnlyIAS</span>
                  <span style={{ fontSize: '0.75rem', background: '#eff6ff', color: '#1d4ed8', padding: '2px 8px', borderRadius: '4px' }}>{readerNote.subject}</span>
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Topic: {readerNote.topic}</span>
                </div>
                <h2 style={{ margin: '4px 0 0 0', fontSize: '1.4rem', color: '#0f172a' }}>{readerNote.title}</h2>
              </div>
              <button className="icon-button" style={{ padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#f8fafc', cursor: 'pointer' }} onClick={() => setReaderNote(null)}>
                ✕ Close
              </button>
            </div>

            {/* Reading progress bar */}
            <div style={{ background: '#e2e8f0', height: '4px', borderRadius: '2px', marginBottom: '16px' }}>
              <div style={{ background: '#2563eb', height: '100%', width: `${progressPct}%`, borderRadius: '2px', transition: 'width 0.3s' }} />
            </div>

            <div style={{ padding: '8px 12px', background: '#eff6ff', borderLeft: '4px solid #2563eb', borderRadius: '4px', marginBottom: '16px', fontSize: '0.85rem', color: '#1e40af' }}>
              Study note content extracted from official PWOnlyIAS syllabus resources.
            </div>

            {readerLoading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Loading UPSC study note content...</div>
            ) : (
              <div
                onScroll={handleScroll}
                style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '8px' }}
              >
                {/* Table of Contents */}
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
                    {readerNote.extraction_status === 'image_only'
                      ? 'This note document is an image-only PDF. Text extraction is unavailable, but you can view the official PDF below.'
                      : 'Structured content extraction completed via topic summary.'}
                  </div>
                )}
              </div>
            )}

            {/* Footer Actions */}
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="send-button" style={{ padding: '8px 16px' }} onClick={() => { setReaderNote(null); onNavigate('chat') }}>
                Ask AI About Note
              </button>
              <button className="send-button" style={{ padding: '8px 16px', background: '#059669' }} onClick={() => { setReaderNote(null); onNavigate('quizzes') }}>
                Take Quiz
              </button>
              <a href={readerNote.official_source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #cbd5e1', borderRadius: '6px', textDecoration: 'none', color: '#2563eb', fontSize: '0.85rem', fontWeight: '500' }}>
                Official Source
              </a>
              {readerNote.official_pdf_url && (
                <a href={readerNote.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #059669', color: '#059669', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                  View PDF
                </a>
              )}
              <button onClick={() => void toggleSave(readerNote)} style={{ marginLeft: 'auto', background: 'none', border: '1px solid #cbd5e1', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}>
                {readerNote.saved ? '♥ Saved' : '♡ Save Note'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
