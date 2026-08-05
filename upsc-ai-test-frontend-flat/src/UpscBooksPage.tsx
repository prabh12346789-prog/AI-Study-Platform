import { useEffect, useMemo, useState } from 'react'
import { Bookmark, BookOpen, Clock3, ExternalLink, FileCheck2, Search, Sparkles, Target } from 'lucide-react'
import {
  API_BASE_URL, BookCollectionItem, BookSubjectCount, ContentBlock, UPSCBook,
  UPSCBookContentResponse, getUpscBookCollections, getUpscBookContent,
  getUpscBookSubjects, getUpscBooks, saveUpscBook, updateUpscBookProgress,
} from './api'
import type { AppPage } from './AppShell'
import { ContentBlocks, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from './PhaseTwoUI'
import { BOOK_PREVIEW_CARDS, BOOK_PREVIEW_SUBJECTS } from './phaseTwoFallback'

type Section = 'prelims' | 'mains'

function PreviewSubjects({ onExplore }: { onExplore: (subject: string) => void }) {
  return <div className="subject-card-grid demo-preview-grid">{BOOK_PREVIEW_SUBJECTS.map(item => <article key={item.subject}><BookOpen size={25} /><div><StatusBadge tone="violet">Demo preview</StatusBadge><h3>{item.subject}</h3><p>{item.count} example titles</p></div><footer><button onClick={() => onExplore(item.subject)}>Explore preview</button><button disabled title="Import verified books to enable tests"><Target size={14} />Test unavailable</button></footer></article>)}</div>
}

function PreviewBooks({ subject }: { subject: string }) {
  const items = BOOK_PREVIEW_CARDS.filter(item => subject === 'All Subjects' || item.subject === subject)
  return <div className="book-card-grid demo-preview-grid">{items.map(item => <article className="book-card p2-card" key={item.title}><header><StatusBadge tone="violet">Demo preview</StatusBadge><Bookmark size={17} /></header><div className="demo-book-cover"><BookOpen size={34} /></div><h3>{item.title}</h3><p>{item.subject} · {item.stage}</p><div className="book-facts"><span><FileCheck2 />Verified import required</span><span><Clock3 />Preview only</span></div><footer><button disabled>Read after import</button><button disabled>Test after indexing</button></footer></article>)}</div>
}

function safeBooks(items: UPSCBook[]) {
  return items.filter(item => item.resource_kind !== 'qa_bank' && !/isolated test book|prog book|both relevant book|evil book/i.test(item.title) && !/^(test|demo|sample)-/.test(item.id))
}

export function UpscBooksPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  const [section, setSection] = useState<Section>(() => localStorage.getItem('upsc_books_active_tab') === 'prelims' ? 'prelims' : 'mains')
  const [subjects, setSubjects] = useState<BookSubjectCount[]>([])
  const [collections, setCollections] = useState<BookCollectionItem[]>([])
  const [books, setBooks] = useState<UPSCBook[]>([])
  const [selectedSubject, setSelectedSubject] = useState('All Subjects')
  const [collection, setCollection] = useState('all')
  const [search, setSearch] = useState('')
  const [savedOnly, setSavedOnly] = useState(false)
  const [progressFilter, setProgressFilter] = useState<'all' | 'not_started' | 'in_progress' | 'complete'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reader, setReader] = useState<UPSCBook | null>(null)
  const [content, setContent] = useState<UPSCBookContentResponse | null>(null)
  const [chapterId, setChapterId] = useState<string>()
  const [readerTab, setReaderTab] = useState<'material' | 'pdf'>('material')
  const [readerLoading, setReaderLoading] = useState(false)
  const [progress, setProgress] = useState(0)

  async function load() {
    setLoading(true); setError('')
    try {
      const [subjectData, collectionData, bookData] = await Promise.all([
        getUpscBookSubjects(`section=${section}`), getUpscBookCollections(`section=${section}`).catch(() => []), getUpscBooks(`section=${section}`),
      ])
      setSubjects(subjectData); setCollections(collectionData); setBooks(safeBooks(bookData))
    } catch { setError('The verified UPSC Books catalog is temporarily unavailable.') }
    finally { setLoading(false) }
  }

  useEffect(() => { setSelectedSubject('All Subjects'); void load() }, [section])

  const filtered = useMemo(() => books.filter(book => {
    if (selectedSubject !== 'All Subjects' && book.subject !== selectedSubject) return false
    if (collection !== 'all' && book.collection_id !== collection) return false
    if (savedOnly && !book.saved) return false
    if (progressFilter === 'not_started' && book.progress_percentage > 0) return false
    if (progressFilter === 'in_progress' && !(book.progress_percentage > 0 && book.progress_percentage < 100)) return false
    if (progressFilter === 'complete' && book.progress_percentage < 100) return false
    const query = search.trim().toLowerCase()
    return !query || book.title.toLowerCase().includes(query) || book.subject.toLowerCase().includes(query)
  }), [books, selectedSubject, collection, savedOnly, progressFilter, search])

  function chooseSection(next: Section) { setSection(next); localStorage.setItem('upsc_books_active_tab', next) }
  function startSubjectTest(subject: string) {
    sessionStorage.setItem('upsc-test-entry', JSON.stringify({ section, subject, source: 'upsc_books' }))
    onNavigate('tests')
  }
  function askCoach(book: UPSCBook) {
    sessionStorage.setItem('upsc-coach-draft', `Help me study this verified UPSC book: ${book.title} (${book.subject}).`)
    onNavigate('chat')
  }

  async function toggleSave(book: UPSCBook) {
    try { await saveUpscBook(book.id, book.saved); setBooks(old => old.map(item => item.id === book.id ? { ...item, saved: !item.saved } : item)); setReader(old => old?.id === book.id ? { ...old, saved: !old.saved } : old) }
    catch { setError('The saved state could not be updated.') }
  }

  async function openReader(book: UPSCBook, tab: 'material' | 'pdf' = 'material', selectedChapter?: string) {
    setReader(book); setReaderTab(tab); setChapterId(selectedChapter); setReaderLoading(true); setProgress(book.progress_percentage)
    try { const result = await getUpscBookContent(book.id, selectedChapter); setContent(result); await updateUpscBookProgress(book.id, Math.max(1, book.progress_percentage), selectedChapter) }
    catch { setContent(null) }
    finally { setReaderLoading(false) }
  }

  async function chooseChapter(next: string) {
    if (!reader) return; setChapterId(next); setReaderLoading(true)
    try { setContent(await getUpscBookContent(reader.id, next)) } finally { setReaderLoading(false) }
  }

  function trackReading(event: React.UIEvent<HTMLDivElement>) {
    if (!reader) return
    const { scrollTop, scrollHeight, clientHeight } = event.currentTarget
    if (scrollHeight <= clientHeight) return
    const next = Math.round(scrollTop / (scrollHeight - clientHeight) * 100)
    if (next >= progress + 5) { setProgress(next); void updateUpscBookProgress(reader.id, next, chapterId) }
  }

  return <div className="p2-page books-redesign">
    <PageHeader eyebrow="Verified study library" title="UPSC Books" subtitle="Subject-first access to imported Prelims and Mains material." />
    <div className="books-toolbar">
      <div className="p2-segment" role="tablist" aria-label="Book section"><button role="tab" aria-selected={section === 'prelims'} className={section === 'prelims' ? 'active' : ''} onClick={() => chooseSection('prelims')}>Prelims</button><button role="tab" aria-selected={section === 'mains'} className={section === 'mains' ? 'active' : ''} onClick={() => chooseSection('mains')}>Mains</button></div>
      <label className="p2-search"><Search size={14} /><input aria-label="Search books" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search books or subjects…" /></label>
      <label><span>Collection</span><select value={collection} onChange={event => setCollection(event.target.value)}><option value="all">All collections</option>{collections.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>
      <label><span>Reading</span><select value={progressFilter} onChange={event => setProgressFilter(event.target.value as typeof progressFilter)}><option value="all">Any progress</option><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="complete">Completed</option></select></label>
      <label className="p2-check"><input type="checkbox" checked={savedOnly} onChange={event => setSavedOnly(event.target.checked)} /> Saved only</label>
    </div>

    {error && <ErrorState description={error} retry={() => void load()} />}
    {loading ? <LoadingState label="Loading verified books…" /> : <>
      <section className="books-subject-section"><div className="p2-section-head"><div><h2>Browse by Subject</h2><p>Counts reflect the verified material currently available.</p></div>{selectedSubject !== 'All Subjects' && <button onClick={() => setSelectedSubject('All Subjects')}>Show all subjects</button>}</div>
        {subjects.length ? <div className="subject-card-grid">{subjects.map(item => {
          const subjectBooks = books.filter(book => book.subject === item.subject)
          const started = subjectBooks.filter(book => book.progress_percentage > 0).length
          return <article className={selectedSubject === item.subject ? 'active' : ''} key={item.subject}><BookOpen size={21} /><div><h3>{item.subject}</h3><p>{item.book_count} verified {item.book_count === 1 ? 'book' : 'books'}{started ? ` · ${started} started` : ''}</p></div><footer><button onClick={() => setSelectedSubject(item.subject)}>Explore subject</button><button onClick={() => startSubjectTest(item.subject)}><Target size={13} />Take subject test</button></footer></article>
        })}</div> : <PreviewSubjects onExplore={setSelectedSubject} />}
      </section>

      <section className="books-results"><div className="p2-section-head"><div><h2>{selectedSubject === 'All Subjects' ? `${section === 'prelims' ? 'Prelims' : 'Mains'} Books` : selectedSubject}</h2><p>{filtered.length} matching verified {filtered.length === 1 ? 'book' : 'books'}</p></div></div>
        {filtered.length ? <div className="book-card-grid">{filtered.map(book => <article className="book-card p2-card" key={book.id}><header><StatusBadge tone="violet">{book.subject}</StatusBadge><button aria-label={book.saved ? `Unsave ${book.title}` : `Save ${book.title}`} onClick={() => void toggleSave(book)}><Bookmark size={15} fill={book.saved ? 'currentColor' : 'none'} /></button></header><h3>{book.title}</h3><p>{book.description || `Verified ${book.provider} study material.`}</p><div className="book-facts"><span><FileCheck2 />{book.page_count ? `${book.page_count} pages` : 'Pages unavailable'}</span><span><Clock3 />{book.estimated_reading_minutes ? `${book.estimated_reading_minutes} min` : 'Time unavailable'}</span><span><StatusBadge tone={book.extraction_status === 'extracted' ? 'green' : 'amber'}>{book.extraction_status}</StatusBadge></span><span><StatusBadge tone={book.indexing_status === 'indexed' ? 'green' : 'amber'}>{book.indexing_status}</StatusBadge></span></div><div className="book-progress"><span>Reading progress <strong>{book.progress_percentage}%</strong></span><i><b style={{ width: `${book.progress_percentage}%` }} /></i></div><footer><button className="p2-primary" onClick={() => void openReader(book)}>{book.progress_percentage ? 'Continue reading' : 'Read material'}</button><button onClick={() => void openReader(book, 'pdf')}>Original PDF</button><button onClick={() => askCoach(book)}><Sparkles size={13} />Ask AI</button><button onClick={() => onNavigate('revision')}>Quick revision</button><button disabled={book.indexing_status !== 'indexed'} onClick={() => startSubjectTest(book.subject)}>Take test</button></footer></article>)}</div> : books.length ? <EmptyState title="No books match these filters" description="Change the subject or filters to see available verified books." /> : <PreviewBooks subject={selectedSubject} />}
      </section>
    </>}

    {reader && <div className="p2-dialog book-reader-dialog" role="dialog" aria-modal="true" aria-label={reader.title}><article><header><div><StatusBadge>{reader.subject}</StatusBadge><h2>{reader.title}</h2></div><button aria-label="Close reader" onClick={() => setReader(null)}>×</button></header><nav className="p2-segment"><button className={readerTab === 'material' ? 'active' : ''} onClick={() => setReaderTab('material')}>Read material</button><button className={readerTab === 'pdf' ? 'active' : ''} onClick={() => setReaderTab('pdf')}>Original PDF</button></nav>{content?.chapters.length ? <label className="chapter-picker"><span>Chapter</span><select value={chapterId ?? ''} onChange={event => void chooseChapter(event.target.value)}><option value="">All material</option>{content.chapters.map(chapter => <option value={chapter.id} key={chapter.id}>{chapter.title}</option>)}</select></label> : null}<div className="book-reader-body" onScroll={trackReading}>{readerLoading ? <LoadingState label="Loading book material…" /> : readerTab === 'pdf' ? <iframe title={`${reader.title} PDF`} src={`${API_BASE_URL}/upsc-books/${reader.id}/pdf`} /> : content?.content_blocks?.length ? <ContentBlocks blocks={content.content_blocks as ContentBlock[]} /> : <EmptyState title="Extracted material unavailable" description="This verified book does not currently have readable extracted text." />}</div><footer><span>Progress: {progress}%</span><button onClick={() => void toggleSave(reader)}>{reader.saved ? 'Unsave' : 'Save'}</button><a href={reader.official_pdf_url || `${API_BASE_URL}/upsc-books/${reader.id}/pdf`} target="_blank" rel="noreferrer">Open PDF <ExternalLink size={13} /></a><button onClick={() => { setReader(null); askCoach(reader) }}>Ask AI</button><button disabled={reader.indexing_status !== 'indexed'} onClick={() => startSubjectTest(reader.subject)}>Take test</button></footer></article></div>}
  </div>
}
