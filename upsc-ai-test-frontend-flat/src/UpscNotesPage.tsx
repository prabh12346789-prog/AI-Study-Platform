import { useEffect, useMemo, useState } from 'react'
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

export function UpscNotesPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [subjectCounts, setSubjectCounts] = useState<Record<string, number>>({})
  const [notes, setNotes] = useState<UPSCNote[]>([])
  const [selectedSubject, setSelectedSubject] = useState<string>('All Subjects')

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

  async function fetchSubjectCounts() {
    try {
      const counts = await getUpscNoteSubjects()
      const map: Record<string, number> = {}
      counts.forEach(s => { map[s.subject] = s.note_count })
      setSubjectCounts(map)
    } catch {
      setSubjectCounts({})
    }
  }

  async function loadNotes(subj: string) {
    setLoading(true)
    setError('')
    try {
      const param = subj !== 'All Subjects' ? `subject=${encodeURIComponent(subj)}` : ''
      const notesData = await getUpscNotes(param)
      // Filter out synthetic or test notes
      const clean = notesData.filter(n =>
        !n.title.toLowerCase().includes('prog test') &&
        !n.title.toLowerCase().includes('test note') &&
        !n.title.toLowerCase().includes('demo note') &&
        !n.id.startsWith('test-') &&
        !n.id.startsWith('demo-') &&
        !n.id.startsWith('sample-') &&
        !n.id.startsWith('prog-')
      )
      setNotes(clean)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'UPSC Notes unavailable.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchSubjectCounts()
    void loadNotes(selectedSubject)
  }, [selectedSubject])

  const continueReadingNotes = useMemo(() => {
    const map = new Map<string, UPSCNote>()
    for (const n of notes) {
      if (n.progress_percentage > 0 && n.progress_percentage < 100) {
        if (!map.has(n.id) || (map.get(n.id)?.progress_percentage || 0) < n.progress_percentage) {
          map.set(n.id, n)
        }
      }
    }
    return Array.from(map.values()).slice(0, 6)
  }, [notes])

  const filteredNotes = useMemo(() => {
    let result = notes
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
  }, [notes, prelimsOnly, mainsOnly, savedOnly, search])

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
    <div className="upsc-notes-page phase-four-page" style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', color: '#f8fafc' }}>
      <header className="phase-page-head" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow" style={{ color: '#60a5fa', fontWeight: 'bold', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Source: PWOnlyIAS</p>
            <h1 style={{ margin: '4px 0', fontSize: '1.8rem', color: '#f8fafc' }}>
              {selectedSubject === 'All Subjects' ? 'UPSC Notes' : `UPSC Notes — ${selectedSubject}`}
            </h1>
            <small style={{ color: '#94a3b8' }}>Static syllabus-oriented study materials exclusively from official PWOnlyIAS resources.</small>
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
              placeholder="Search notes by title, subject, or topic..."
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
        <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading official PWOnlyIAS study notes...</div>
      ) : error ? (
        <div style={{ padding: '24px', background: '#451a1a', border: '1px solid #7f1d1d', color: '#fca5a5', borderRadius: '8px' }}>{error}</div>
      ) : filteredNotes.length === 0 ? (
        /* Honest Subject-Aware Empty State */
        <section className="premium-card" style={{ padding: '48px 24px', background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', textAlign: 'center', maxWidth: '650px', margin: '30px auto' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📝</div>
          <h2 style={{ fontSize: '1.3rem', color: '#f8fafc', marginBottom: '8px' }}>
            {selectedSubject === 'All Subjects'
              ? 'No verified PWOnlyIAS notes available yet.'
              : 'No verified notes available yet'}
          </h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '24px' }}>
            {selectedSubject === 'All Subjects'
              ? 'Study notes will appear here after a publicly accessible PWOnlyIAS note is imported and verified.'
              : `No publicly accessible PWOnlyIAS notes have been imported for ${selectedSubject} yet.`}
          </p>
        </section>
      ) : (
        <>
          {/* Subject Cards Overview (Highlighted Active Card) */}
          <section style={{ marginBottom: '32px' }}>
            <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#f8fafc' }}>Subjects Overview</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '16px' }}>
              {MANDATED_SUBJECTS.slice(1).map(subj => {
                const count = subjectCounts[subj] || 0
                const isActive = selectedSubject === subj
                return (
                  <article
                    key={subj}
                    onClick={() => setSelectedSubject(subj)}
                    style={{
                      padding: '16px',
                      background: isActive ? '#1e3a8a' : '#1e293b',
                      border: isActive ? '2px solid #3b82f6' : '1px solid #334155',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: isActive ? '#93c5fd' : '#60a5fa', textTransform: 'uppercase' }}>
                      {isActive ? '✓ Active Subject' : 'Subject'}
                    </span>
                    <h3 style={{ margin: '6px 0 4px 0', fontSize: '1.05rem', color: '#f8fafc' }}>{subj}</h3>
                    <p style={{ fontSize: '0.85rem', color: isActive ? '#bfdbfe' : '#94a3b8', margin: 0 }}>
                      {count} {count === 1 ? 'note' : 'notes'}
                    </p>
                  </article>
                )
              })}
            </div>
          </section>

          {/* Continue Reading Section (Deduplicated & Respecting Selected Subject) */}
          {continueReadingNotes.length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#f8fafc' }}>Continue Reading</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                {continueReadingNotes.map(n => (
                  <article key={n.id} style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#60a5fa', fontWeight: 'bold' }}>{n.subject}</span>
                    <h3 style={{ margin: '4px 0', fontSize: '1rem', color: '#f8fafc' }}>{n.title}</h3>
                    <div style={{ background: '#0f172a', height: '6px', borderRadius: '3px', margin: '10px 0 6px 0' }}>
                      <div style={{ background: '#3b82f6', height: '100%', width: `${n.progress_percentage}%`, borderRadius: '3px' }} />
                    </div>
                    <small style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{Math.round(n.progress_percentage)}% completed</small>
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
            <h2 style={{ fontSize: '1.2rem', marginBottom: '14px', color: '#f8fafc' }}>
              {selectedSubject !== 'All Subjects' ? `${selectedSubject} Notes` : 'All Available Notes'} ({filteredNotes.length})
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
              {filteredNotes.map(note => (
                <article key={note.id} style={{ padding: '16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#60a5fa' }}>{note.subject} · {note.topic}</span>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {note.prelims_relevant && <span style={{ fontSize: '0.7rem', background: '#064e3b', color: '#a7f3d0', padding: '2px 6px', borderRadius: '4px' }}>Prelims</span>}
                      {note.mains_relevant && <span style={{ fontSize: '0.7rem', background: '#7c2d12', color: '#ffedd5', padding: '2px 6px', borderRadius: '4px' }}>Mains</span>}
                    </div>
                  </div>

                  <h3 style={{ margin: '4px 0 8px 0', fontSize: '1.05rem', color: '#f8fafc' }}>{note.title}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#cbd5e1', flex: 1, marginBottom: '12px' }}>{note.description || note.title}</p>

                  <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '12px', display: 'flex', gap: '12px' }}>
                    <span>⏱️ {note.estimated_reading_minutes} min read</span>
                    <span>📄 {note.page_count} pages</span>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #334155' }}>
                    <button className="send-button" style={{ padding: '6px 14px', fontSize: '0.85rem' }} onClick={() => openReader(note)}>
                      Read Note
                    </button>
                    <a href={note.official_source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#60a5fa' }}>
                      Official Source
                    </a>
                    {note.official_pdf_url && (
                      <a href={note.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#34d399' }}>
                        View PDF
                      </a>
                    )}
                    <button onClick={() => void toggleSave(note)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', color: '#94a3b8' }}>
                      {note.saved ? '♥ Saved' : '♡ Save'}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      )}

      {/* Internal Note Reader Modal */}
      {readerNote && (
        <div className="ca-modal" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <article style={{ background: '#0f172a', border: '1px solid #334155', width: '100%', maxWidth: '850px', maxHeight: '92vh', display: 'flex', flexDirection: 'column', borderRadius: '12px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)', color: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#60a5fa' }}>Source: PWOnlyIAS</span>
                  <span style={{ fontSize: '0.75rem', background: '#1e3a8a', color: '#93c5fd', padding: '2px 8px', borderRadius: '4px' }}>{readerNote.subject}</span>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Topic: {readerNote.topic}</span>
                </div>
                <h2 style={{ margin: '4px 0 0 0', fontSize: '1.4rem', color: '#f8fafc' }}>{readerNote.title}</h2>
              </div>
              <button className="icon-button" style={{ padding: '6px 12px', border: '1px solid #334155', borderRadius: '6px', background: '#1e293b', color: '#f8fafc', cursor: 'pointer' }} onClick={() => setReaderNote(null)}>
                ✕ Close
              </button>
            </div>

            {/* Reading progress bar */}
            <div style={{ background: '#1e293b', height: '4px', borderRadius: '2px', marginBottom: '16px' }}>
              <div style={{ background: '#3b82f6', height: '100%', width: `${progressPct}%`, borderRadius: '2px', transition: 'width 0.3s' }} />
            </div>

            <div style={{ padding: '8px 12px', background: '#1e3a8a', borderLeft: '4px solid #3b82f6', borderRadius: '4px', marginBottom: '16px', fontSize: '0.85rem', color: '#bfdbfe' }}>
              Study note content extracted from official PWOnlyIAS syllabus resources.
            </div>

            {readerLoading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>Loading UPSC study note content...</div>
            ) : (
              <div
                onScroll={handleScroll}
                style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '8px' }}
              >
                {/* Table of Contents */}
                {readerContent?.content_blocks && readerContent.content_blocks.some(b => b.type === 'heading' || b.title) && (
                  <nav style={{ background: '#1e293b', padding: '12px 16px', borderRadius: '8px', border: '1px solid #334155' }}>
                    <h4 style={{ margin: '0 0 6px 0', fontSize: '0.9rem', color: '#f8fafc' }}>Table of Contents</h4>
                    <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.85rem', color: '#60a5fa' }}>
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
                    {readerNote.extraction_status === 'image_only'
                      ? 'This note document is an image-only PDF. Text extraction is unavailable, but you can view the official PDF below.'
                      : 'Structured content extraction completed via topic summary.'}
                  </div>
                )}
              </div>
            )}

            {/* Footer Actions */}
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #334155', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="send-button" style={{ padding: '8px 16px' }} onClick={() => { setReaderNote(null); onNavigate('chat') }}>
                Ask AI About Note
              </button>
              <button className="send-button" style={{ padding: '8px 16px', background: '#059669' }} onClick={() => { setReaderNote(null); onNavigate('quizzes') }}>
                Take Quiz
              </button>
              <a href={readerNote.official_source_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #334155', borderRadius: '6px', textDecoration: 'none', color: '#60a5fa', fontSize: '0.85rem', fontWeight: '500' }}>
                Official Source
              </a>
              {readerNote.official_pdf_url && (
                <a href={readerNote.official_pdf_url} target="_blank" rel="noopener noreferrer" style={{ padding: '8px 14px', border: '1px solid #059669', color: '#34d399', borderRadius: '6px', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500' }}>
                  View PDF
                </a>
              )}
              <button onClick={() => void toggleSave(readerNote)} style={{ marginLeft: 'auto', background: 'none', border: '1px solid #334155', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer', color: '#94a3b8' }}>
                {readerNote.saved ? '♥ Saved' : '♡ Save Note'}
              </button>
            </div>
          </article>
        </div>
      )}
    </div>
  )
}
