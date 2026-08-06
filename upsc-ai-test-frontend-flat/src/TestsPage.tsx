import { useEffect, useRef, useState } from 'react'

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SourcesInfo {
  notes: { available: boolean; count: number; subjects: string[]; message?: string }
  books: { available: boolean; count: number; subjects: string[]; message?: string }
  prelims_books?: { available: boolean; count: number; subjects: string[]; message?: string }
  current_affairs: { available: boolean; count: number; message?: string }
  demo_mode?: boolean
}

interface PrelimsQuestion {
  id: string
  question: string
  options: string[]
  correct_answer: string
  explanation: string
  subject: string
  topic: string
  source_id: string
  source_type: string
  source_title: string
  source_url?: string
}

interface PrelimsQuiz {
  quiz_id: string
  questions: PrelimsQuestion[]
  generated_at: string
}

interface PrelimsResult {
  quiz_id: string
  score: number
  total: number
  percentage: number
  total_questions?: number
  answered_count?: number
  unanswered_count?: number
  correct_count?: number
  incorrect_count?: number
  breakdown: Array<{ question_id: string; correct: boolean; status?: 'correct' | 'incorrect' | 'unanswered'; selected_answer?: string | null; explanation: string; source_url?: string }>
}

interface TestActivitySummary {
  recent_events: Array<{ event_type: string; occurred_at: string; metadata?: Record<string, unknown> | null }>
  daily_breakdown?: Array<{ date: string; study_seconds: number; event_count: number }>
}

const INVALID_QUIZ_TEXT = /<|>|querySelector|addEventListener|DOMContentLoaded|function\s*\(|Subscribe Release|Screen Reader Access|PIB Delhi|PIB Mumbai/i

function quizHasInvalidText(quiz: PrelimsQuiz) {
  return quiz.questions.some(q =>
    INVALID_QUIZ_TEXT.test(q.question) || q.options.length !== 4 ||
    new Set(q.options.map(option => option.trim().toLocaleLowerCase())).size !== 4 ||
    q.options.some(option => option.length > 180 || INVALID_QUIZ_TEXT.test(option))
  )
}

interface MainsQuestion {
  session_id: string
  question_id: string
  question_text: string
  directive: string
  marks: number
  word_limit: number
  subject: string
  gs_paper: string
  source_title: string
  disclaimer: string
}

interface RubricBreakdown {
  demand_and_relevance: number
  structure_and_headings: number
  content_coverage: number
  analysis_and_examples: number
  conclusion_presentation: number
}

interface MainsEvaluation {
  question_id: string
  score: number
  max_marks: number
  percentage: number
  rubric_breakdown: RubricBreakdown
  strengths: string[]
  missing_dimensions: string[]
  improved_framework: string
  word_count: number
  word_limit: number
  disclaimer: string
}

type Tab = 'prelims' | 'ca' | 'mains'
type PrelimsSource = 'general' | 'books'
type TestPhase = 'config' | 'active' | 'result'

// ── Fetch helper ──────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    })
  } catch {
    throw new Error(`Cannot reach the Tests backend at ${API}. Start the FastAPI server and try again.`)
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return res.json() as Promise<T>
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ScoreRing({ pct, size = 80, color }: { pct: number; size?: number; color: string }) {
  const r = (size - 12) / 2
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={8} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth={8}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)' }}
      />
      <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize={size * 0.22} fill="var(--fg)" fontWeight="700">
        {pct}%
      </text>
    </svg>
  )
}

// ── Rubric bar ────────────────────────────────────────────────────────────────

function RubricRow({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = max > 0 ? Math.round((score / max) * 100) : 0
  return (
    <div className="rubric-row">
      <div className="rubric-label">{label}</div>
      <div className="rubric-bar-track">
        <div className="rubric-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="rubric-score">{score}/{max}</div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function TestsPage() {
  const [tab, setTab] = useState<Tab>('prelims')
  const [sources, setSources] = useState<SourcesInfo | null>(null)
  const [sourcesError, setSourcesError] = useState('')

  // Prelims state
  const [prelimsSource, setPrelimsSource] = useState<PrelimsSource>('general')
  const [prelimsSubject, setPrelimsSubject] = useState('')
  const [prelimsTopic, setPrelimsTopic] = useState('')
  const [prelimsDifficulty, setPrelimsDifficulty] = useState<'Easy' | 'Medium' | 'Hard'>('Medium')
  const [prelimsTimeMode, setPrelimsTimeMode] = useState<'timed' | 'untimed'>('timed')
  const [prelimsMinutes, setPrelimsMinutes] = useState(30)
  const [prelimsCount, setPrelimsCount] = useState(10)
  const [currentQuestion, setCurrentQuestion] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [activity, setActivity] = useState<TestActivitySummary | null>(null)
  const [quiz, setQuiz] = useState<PrelimsQuiz | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<PrelimsResult | null>(null)
  const [prelimsPhase, setPrelimsPhase] = useState<TestPhase>('config')
  const [prelimsLoading, setPrelLoading] = useState(false)
  const [prelimsError, setPrelimsError] = useState('')
  const [prelimsConfirmOpen, setPrelimsConfirmOpen] = useState(false)
  const [prelimsMarked, setPrelimsMarked] = useState<Record<string, boolean>>({})

  // Current Affairs Quiz state
  const [caQuiz, setCaQuiz] = useState<PrelimsQuiz | null>(null)
  const [caAnswers, setCaAnswers] = useState<Record<string, string>>({})
  const [caResult, setCaResult] = useState<PrelimsResult | null>(null)
  const [caPhase, setCaPhase] = useState<TestPhase>('config')
  const [caCount, setCaCount] = useState(10)
  const [caLoading, setCaLoading] = useState(false)
  const [caError, setCaError] = useState('')
  const [caConfirmOpen, setCaConfirmOpen] = useState(false)
  const [caHighlightedId, setCaHighlightedId] = useState('')
  const [caInvalidQuiz, setCaInvalidQuiz] = useState(false)
  const [caRecoveryLoading, setCaRecoveryLoading] = useState(false)
  const caQuestionRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const caRecoveryRef = useRef(false)

  // Mains state
  const [mainsMarks, setMainsMarks] = useState<10 | 15>(10)
  const [mainsSubject, setMainsSubject] = useState('')
  const [mainsQuestion, setMainsQuestion] = useState<MainsQuestion | null>(null)
  const [answerText, setAnswerText] = useState('')
  const [mainsEval, setMainsEval] = useState<MainsEvaluation | null>(null)
  const [mainsPhase, setMainsPhase] = useState<TestPhase>('config')
  const [mainsLoading, setMainsLoading] = useState(false)
  const [mainsError, setMainsError] = useState('')
  const textRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    apiFetch<SourcesInfo>('/tests/sources')
      .then(setSources)
      .catch((e) => setSourcesError(e.message))
    apiFetch<TestActivitySummary>('/activity/summary?range=7d').then(setActivity).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (prelimsPhase !== 'active' || prelimsTimeMode !== 'timed') return
    const timer = window.setInterval(() => setElapsedSeconds(value => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [prelimsPhase, prelimsTimeMode])

  useEffect(() => {
    const raw = sessionStorage.getItem('upsc-test-entry')
    if (!raw) return
    sessionStorage.removeItem('upsc-test-entry')
    try {
      const entry = JSON.parse(raw) as { section?: string; subject?: string }
      if (entry.section === 'mains') { setTab('mains'); setMainsSubject(entry.subject ?? '') }
      else { setTab('prelims'); setPrelimsSubject(entry.subject ?? '') }
    } catch { /* Ignore malformed local navigation state. */ }
  }, [])

  // ── Prelims handlers ────────────────────────────────────────────────────────

  const prelimsLoadingRef = useRef(false)

  async function startPrelims() {
    if (prelimsLoadingRef.current) return
    prelimsLoadingRef.current = true
    setPrelLoading(true)
    setPrelimsError('')
    try {
      const data = await apiFetch<PrelimsQuiz>('/tests/prelims/generate', {
        method: 'POST',
        body: JSON.stringify({ source_type: prelimsSource, subject: prelimsSubject || undefined, topic: prelimsTopic || undefined, difficulty: prelimsDifficulty, question_count: prelimsCount }),
      })
      setQuiz(data)
      setAnswers({})
      setPrelimsMarked({})
      setCurrentQuestion(0)
      setElapsedSeconds(0)
      setResult(null)
      setPrelimsPhase('active')
    } catch (e) {
      setPrelimsError(e instanceof Error ? e.message : 'Failed to generate quiz')
    } finally {
      prelimsLoadingRef.current = false
      setPrelLoading(false)
    }
  }

  function submitPrelims() {
    if (!quiz || prelimsLoadingRef.current) return
    const answered = Object.keys(answers).length
    if (!answered) return
    if (answered < quiz.questions.length) { setPrelimsConfirmOpen(true); return }
    void performPrelimsSubmit()
  }
  async function performPrelimsSubmit() {
    if (!quiz || prelimsLoadingRef.current) return
    prelimsLoadingRef.current = true
    setPrelimsConfirmOpen(false)
    setPrelLoading(true)
    setPrelimsError('')
    try {
      const res = await apiFetch<PrelimsResult>(`/tests/prelims/${quiz.quiz_id}/submit`, {
        method: 'POST',
        body: JSON.stringify({ questions: quiz.questions, answers }),
      })
      setResult(res)
      setPrelimsPhase('result')
    } catch (e) {
      setPrelimsError(e instanceof Error ? e.message : 'Submission failed')
    } finally {
      prelimsLoadingRef.current = false
      setPrelLoading(false)
    }
  }

  // ── CA Quiz handlers ────────────────────────────────────────────────────────

  const caLoadingRef = useRef(false)

  async function startCaQuiz() {
    if (caLoadingRef.current) return
    caLoadingRef.current = true
    setCaLoading(true)
    setCaError('')
    try {
      const data = await apiFetch<PrelimsQuiz>('/tests/prelims/generate', {
        method: 'POST',
        body: JSON.stringify({ source_type: 'current_affairs', question_count: caCount }),
      })
      setCaQuiz(data)
      setCaAnswers({})
      setCaResult(null)
      setCaInvalidQuiz(quizHasInvalidText(data))
      setCaPhase('active')
    } catch (e) {
      setCaError(e instanceof Error ? e.message : 'Failed to generate quiz')
    } finally {
      caLoadingRef.current = false
      setCaLoading(false)
    }
  }

  function submitCaQuiz() {
    if (!caQuiz || caLoadingRef.current) return
    const answered = Object.keys(caAnswers).length
    if (answered === 0) return
    if (answered < caQuiz.questions.length) {
      setCaConfirmOpen(true)
      return
    }
    void performCaSubmit()
  }

  async function performCaSubmit() {
    if (!caQuiz || caLoadingRef.current) return
    caLoadingRef.current = true
    setCaConfirmOpen(false)
    setCaLoading(true)
    setCaError('')
    try {
      const res = await apiFetch<PrelimsResult>(`/tests/prelims/${caQuiz.quiz_id}/submit`, {
        method: 'POST',
        body: JSON.stringify({ questions: caQuiz.questions, answers: caAnswers }),
      })
      setCaResult(res)
      setCaPhase('result')
    } catch (e) {
      setCaError(e instanceof Error ? e.message : 'Submission failed')
    } finally {
      caLoadingRef.current = false
      setCaLoading(false)
    }
  }

  function reviewUnansweredCaQuestion() {
    if (!caQuiz) return
    setCaConfirmOpen(false)
    const first = caQuiz.questions.find(question => !caAnswers[question.id])
    if (!first) return
    setCaHighlightedId(first.id)
    caQuestionRefs.current[first.id]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => setCaHighlightedId(current => current === first.id ? '' : current), 1800)
  }

  async function recoverInvalidCaQuiz() {
    if (!caQuiz || caRecoveryRef.current) return
    caRecoveryRef.current = true
    setCaRecoveryLoading(true)
    setCaError('')
    try {
      await apiFetch(`/tests/current-affairs/${caQuiz.quiz_id}/abandon`, { method: 'POST' })
      setCaQuiz(null)
      setCaAnswers({})
      setCaResult(null)
      setCaConfirmOpen(false)
      setCaHighlightedId('')
      setCaInvalidQuiz(false)
      setCaPhase('config')
    } catch (error) {
      setCaError(error instanceof Error ? error.message : 'Could not abandon the invalid quiz. Please try again.')
    } finally {
      caRecoveryRef.current = false
      setCaRecoveryLoading(false)
    }
  }

  // ── Mains handlers ──────────────────────────────────────────────────────────

  const mainsLoadingRef = useRef(false)

  async function generateMainsQuestion() {
    if (mainsLoadingRef.current) return
    mainsLoadingRef.current = true
    setMainsLoading(true)
    setMainsError('')
    try {
      const data = await apiFetch<MainsQuestion>('/tests/mains/generate', {
        method: 'POST',
        body: JSON.stringify({
          source_mode: 'static',
          subject: mainsSubject || undefined,
          marks: mainsMarks,
          word_limit: mainsMarks === 10 ? 150 : 250,
        }),
      })
      setMainsQuestion(data)
      setAnswerText('')
      setMainsEval(null)
      setMainsPhase('active')
      setTimeout(() => textRef.current?.focus(), 100)
    } catch (e) {
      setMainsError(e instanceof Error ? e.message : 'Failed to generate question')
    } finally {
      mainsLoadingRef.current = false
      setMainsLoading(false)
    }
  }

  async function submitMainsAnswer() {
    if (!mainsQuestion || !answerText.trim()) return
    setMainsLoading(true)
    setMainsError('')
    try {
      const data = await apiFetch<MainsEvaluation>('/tests/mains/submit', {
        method: 'POST',
        body: JSON.stringify({ question_id: mainsQuestion.question_id, answer_text: answerText }),
      })
      setMainsEval(data)
      setMainsPhase('result')
    } catch (e) {
      setMainsError(e instanceof Error ? e.message : 'Evaluation failed')
    } finally {
      setMainsLoading(false)
    }
  }

  const wordCount = answerText.trim() ? answerText.trim().split(/\s+/).length : 0
  const wordLimit = mainsQuestion?.word_limit ?? (mainsMarks === 10 ? 150 : 250)
  const wordPct = Math.min(100, Math.round((wordCount / wordLimit) * 100))

  // ── Render helpers ──────────────────────────────────────────────────────────

  function renderSourceBadge(info: SourcesInfo) {
    return (
      <div className="tests-sources" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <span className={`source-badge ${info.prelims_books?.available ? 'ok' : 'warn'}`}>
          Prelims Books: {info.prelims_books?.count ?? 0}
        </span>
        <span className={`source-badge ${info.books.available ? 'ok' : 'warn'}`}>
          Mains Books: {info.books.count}
        </span>
        <span className={`source-badge ${info.current_affairs.available ? 'ok' : 'warn'}`}>
          Current Affairs: {info.current_affairs.count}
        </span>
        {info.demo_mode && (
          <span className="source-badge info" style={{ background: '#f59e0b', color: '#1e293b', fontWeight: 'bold' }}>
            DEMO MODE
          </span>
        )}
      </div>
    )
  }

  function renderPrelimsConfig() {
    const availableSubjects = Array.from(new Set([
      ...(sources?.prelims_books?.subjects ?? []),
      'Indian Polity and Governance', 'History', 'Geography', 'Indian Economy',
      'Environment and Ecology', 'Science and Technology', 'Art and Culture',
      'International Relations', 'Ethics', 'Indian Society', 'CSAT',
    ])).sort()
    return (
      <div className="tests-config-card test-builder-card">
        <h2 className="tests-section-title">Create a New Test</h2>
        <p className="tests-description">
          Build a dynamic UPSC MCQ test from general UPSC knowledge or your extracted Books library.
        </p>
        {sources && renderSourceBadge(sources)}

        <div className="tests-form">
          <label className="tests-label">
            <span><b>1</b> Test type</span>
            <select className="tests-select" value={tab} onChange={e => setTab(e.target.value as Tab)}>
              <option value="prelims">Prelims MCQ</option><option value="ca">Current Affairs Quiz</option><option value="mains">Mains Answer Writing</option>
            </select>
          </label>
          <label className="tests-label">
            <span><b>2</b> Source</span>
            <select className="tests-select" value={prelimsSource} onChange={e => setPrelimsSource(e.target.value as PrelimsSource)}>
              <option value="general">General Subject · local AI</option>
              <option value="books" disabled={!sources?.prelims_books?.available}>
                UPSC Books{!sources?.prelims_books?.available ? ' (no verified books yet)' : ''}
              </option>
            </select>
          </label>

          <label className="tests-label">
            <span><b>3</b> Subject</span>
            <input className="tests-select" list="test-subjects" value={prelimsSubject} onChange={e => setPrelimsSubject(e.target.value)} placeholder="Choose or type any subject" />
            <datalist id="test-subjects">{availableSubjects.map(subject => <option key={subject} value={subject} />)}</datalist>
          </label>

          <label className="tests-label"><span><b>4</b> Topic <small>optional</small></span><input className="tests-select" value={prelimsTopic} onChange={e => setPrelimsTopic(e.target.value)} placeholder="e.g. Fundamental Rights" /></label>

          <label className="tests-label"><span><b>5</b> Difficulty</span><div className="tests-segmented">{(['Easy', 'Medium', 'Hard'] as const).map(level => <button type="button" key={level} className={prelimsDifficulty === level ? 'active' : ''} onClick={() => setPrelimsDifficulty(level)}>{level}</button>)}</div></label>

          <label className="tests-label">
            <span><b>6</b> Number of questions</span>
            <div className="tests-counter">
              <button className="counter-btn" onClick={() => setPrelimsCount(c => Math.max(5, c - 5))}>−</button>
              <span className="counter-val">{prelimsCount}</span>
              <button className="counter-btn" onClick={() => setPrelimsCount(c => Math.min(25, c + 5))}>+</button>
            </div>
          </label>

          <label className="tests-label"><span><b>7</b> Time mode</span><div className="tests-time-row"><div className="tests-segmented"><button type="button" className={prelimsTimeMode === 'timed' ? 'active' : ''} onClick={() => setPrelimsTimeMode('timed')}>Timed</button><button type="button" className={prelimsTimeMode === 'untimed' ? 'active' : ''} onClick={() => setPrelimsTimeMode('untimed')}>Untimed</button></div>{prelimsTimeMode === 'timed' && <select aria-label="Test duration" className="tests-select" value={prelimsMinutes} onChange={e => setPrelimsMinutes(Number(e.target.value))}><option value={15}>15 min</option><option value={30}>30 min</option><option value={60}>60 min</option><option value={120}>120 min</option></select>}</div></label>
        </div>

        {prelimsError && <div className="tests-error">{prelimsError}</div>}

        <button className="tests-start-btn" onClick={startPrelims} disabled={prelimsLoading || (prelimsSource === 'books' && !sources?.prelims_books?.available)}>
          {prelimsLoading ? 'Generating…' : 'Start Quiz'}
        </button>

        {sources && prelimsSource === 'books' && !sources.prelims_books?.available && (
          <p className="tests-unavail">No eligible UPSC Books are indexed yet. Add books via the UPSC Books page to unlock Prelims Quiz.</p>
        )}
      </div>
    )
  }

  function renderPrelimsActive() {
    if (!quiz) return null
    const answered = Object.keys(answers).length
    const total = quiz.questions.length
    const remaining = Math.max(0, prelimsMinutes * 60 - elapsedSeconds)
    const timerLabel = prelimsTimeMode === 'timed' ? `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}` : 'Untimed'
    return (
      <div className="tests-active test-workspace">
        <header className="active-test-header"><div><span className="live-pill">● Live</span><small>{prelimsSubject || 'General Studies'} · {prelimsTopic || 'All topics'}</small><h2>Prelims MCQ Test</h2></div><div className="active-test-metrics"><span><b>{answered}/{total}</b> Answered</span><span><b>{timerLabel}</b> Time left</span><span><b>{prelimsDifficulty}</b> Difficulty</span></div></header>
        <div className="tests-progress-bar">
          <div className="tests-progress-fill" style={{ width: `${(answered / total) * 100}%` }} />
        </div>
        <p className="tests-progress-label">{answered} / {total} answered</p>
        <nav className="question-navigator" aria-label="Question navigator">{quiz.questions.map((q, idx) => <button key={q.id} aria-current={currentQuestion === idx ? 'step' : undefined} aria-label={`Question ${idx + 1}: ${answers[q.id] ? 'answered' : 'unanswered'}${prelimsMarked[q.id] ? ', marked for review' : ''}`} className={`${answers[q.id] ? 'answered' : 'unanswered'} ${prelimsMarked[q.id] ? 'marked' : ''} ${currentQuestion === idx ? 'current' : ''}`} onClick={() => setCurrentQuestion(idx)}>{idx + 1}</button>)}</nav>

        {quiz.questions.map((q, idx) => idx !== currentQuestion ? null : (
          <div id={`prelims-${q.id}`} key={q.id} className={`tests-question-card ${answers[q.id] ? 'answered' : ''}`}>
            <p className="q-number">Q{idx + 1} · <span className="q-subject">{q.subject}</span></p>
            <p className="q-text">{q.question}</p>
            <div className="q-options">
              {q.options.map(opt => (
                <button
                  key={opt}
                  className={`q-option ${answers[q.id] === opt ? 'selected' : ''}`}
                  onClick={() => setAnswers(a => ({ ...a, [q.id]: opt }))}
                >
                  {opt}
                </button>
              ))}
            </div>
            <div className="question-tools">
              <button onClick={() => setPrelimsMarked(old => ({ ...old, [q.id]: !old[q.id] }))}>
                {prelimsMarked[q.id] ? 'Unmark review' : 'Mark for review'}
              </button>
              <button disabled={!answers[q.id]} onClick={() => setAnswers(old => {
                const next = { ...old }
                delete next[q.id]
                return next
              })}>Clear answer</button>
            </div>
          </div>
        ))}

        {prelimsError && <div className="tests-error">{prelimsError}</div>}

        <div className="tests-action-row">
          <button className="tests-ghost-btn" disabled={currentQuestion === 0} onClick={() => setCurrentQuestion(value => Math.max(0, value - 1))}>Previous</button>
          <button className="tests-ghost-btn" disabled={currentQuestion === total - 1} onClick={() => setCurrentQuestion(value => Math.min(total - 1, value + 1))}>Next</button>
          <button className="tests-ghost-btn" onClick={() => { setPrelimsPhase('config'); setQuiz(null) }}>
            ← Back
          </button>
          <button
            className="tests-start-btn"
            onClick={submitPrelims}
            disabled={answered === 0 || prelimsLoading}
          >
            {prelimsLoading ? 'Evaluating…' : `Submit (${answered}/${total})`}
          </button>
        </div>
        {prelimsConfirmOpen && <div role="dialog" aria-modal="true" aria-labelledby="prelims-confirm-title" className="tests-config-card"><h3 id="prelims-confirm-title">Submit partial test?</h3><p>{total - answered} unanswered questions will count as incorrect. Your score denominator remains {total}.</p><div className="tests-action-row"><button className="tests-ghost-btn" onClick={() => setPrelimsConfirmOpen(false)}>Continue answering</button><button className="tests-start-btn" onClick={() => void performPrelimsSubmit()}>Submit anyway</button></div></div>}
      </div>
    )
  }

  function renderPrelimsResult() {
    if (!result || !quiz) return null
    const score = result.score
    const total = result.total
    const pct = result.percentage
    const color = pct >= 70 ? 'var(--accent)' : pct >= 50 ? '#f59e0b' : '#ef4444'

    return (
      <div className="tests-result">
        <div className="result-header">
          <ScoreRing pct={pct} size={96} color={color} />
          <div>
            <h2 className="result-score-text">{score} / {total} correct</h2>
            <p className="result-grade" style={{ color }}>{pct >= 70 ? '🎉 Excellent' : pct >= 50 ? '👍 Good effort' : '📚 Keep practising'}</p>
          </div>
        </div>

        <div className="result-breakdown">
          {quiz.questions.map((q, idx) => {
            const bd = result.breakdown?.find(b => b.question_id === q.id)
            const isCorrect = bd?.correct ?? (answers[q.id] === q.correct_answer)
            return (
              <details key={q.id} className={`result-item ${isCorrect ? 'correct' : 'wrong'}`}>
                <summary>
                  <span className="result-item-icon">{isCorrect ? '✓' : '✗'}</span>
                  Q{idx + 1}: {q.question.slice(0, 80)}{q.question.length > 80 ? '…' : ''}
                </summary>
                <div className="result-item-body">
                  <p><strong>Your answer:</strong> {answers[q.id] || 'Not answered'}</p>
                  <p><strong>Correct answer:</strong> {q.correct_answer}</p>
                  <p className="result-explanation">{q.explanation}</p>
                </div>
              </details>
            )
          })}
        </div>

        <div className="tests-action-row">
          <button className="tests-ghost-btn" onClick={() => { setPrelimsPhase('config'); setQuiz(null); setResult(null) }}>
            ← New Quiz
          </button>
          <button className="tests-start-btn" onClick={() => { setAnswers({}); setResult(null); setPrelimsPhase('active') }}>
            Retry same quiz
          </button>
        </div>
      </div>
    )
  }

  function renderCAConfig() {
    return (
      <div className="tests-config-card">
        <h2 className="tests-section-title">Current Affairs Quiz</h2>
        <p className="tests-description">
          Questions are generated from accepted official Current Affairs sources, including PIB, RBI, and MEA.
        </p>
        {sources && renderSourceBadge(sources)}

        <div className="tests-form">
          <label className="tests-label">
            Number of questions
            <div className="tests-counter">
              <button className="counter-btn" onClick={() => setCaCount(c => Math.max(5, c - 5))}>−</button>
              <span className="counter-val">{caCount}</span>
              <button className="counter-btn" onClick={() => setCaCount(c => Math.min(20, c + 5))}>+</button>
            </div>
          </label>
        </div>

        {caError && <div className="tests-error">{caError}</div>}

        <button className="tests-start-btn" onClick={startCaQuiz} disabled={caLoading || !sources?.current_affairs.available}>
          {caLoading ? 'Generating…' : 'Start Current Affairs Quiz'}
        </button>

        {sources && !sources.current_affairs.available && (
          <p className="tests-unavail">No eligible official Current Affairs articles are available for quiz generation.</p>
        )}
      </div>
    )
  }

  function renderCAActive() {
    if (!caQuiz) return null
    if (caInvalidQuiz) return (
      <div className="tests-config-card">
        <div className="tests-error">This quiz contains invalid extracted source text. Please generate a new quiz.</div>
        {caError && <div className="tests-error">{caError}</div>}
        <button className="tests-start-btn" onClick={() => void recoverInvalidCaQuiz()} disabled={caRecoveryLoading}>
          {caRecoveryLoading ? 'Preparing clean quiz…' : 'Generate New Quiz'}
        </button>
      </div>
    )
    const answered = Object.keys(caAnswers).length
    const total = caQuiz.questions.length
    const unanswered = total - answered
    return (
      <div className="tests-active">
        <div className="tests-progress-bar">
          <div className="tests-progress-fill" style={{ width: `${(answered / total) * 100}%` }} />
        </div>
        <p className="tests-progress-label">{answered} / {total} answered</p>

        {caQuiz.questions.map((q, idx) => (
          <div ref={node => { caQuestionRefs.current[q.id] = node }} key={q.id}
            className={`tests-question-card ${caAnswers[q.id] ? 'answered' : ''}`}
            style={caHighlightedId === q.id ? { outline: '2px solid #f59e0b', outlineOffset: '3px' } : undefined}>
            <p className="q-number">Q{idx + 1} · <span className="q-subject">{q.subject}</span>
              {caHighlightedId === q.id && !caAnswers[q.id] && <span style={{ marginLeft: 8, color: '#f59e0b', fontWeight: 700 }}>Unanswered</span>}
            </p>
            <p className="q-text">{q.question}</p>
            <div className="q-options">
              {q.options.map(opt => (
                <button
                  key={opt}
                  className={`q-option ${caAnswers[q.id] === opt ? 'selected' : ''}`}
                  onClick={() => setCaAnswers(a => ({ ...a, [q.id]: opt }))}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        ))}

        {caError && <div className="tests-error">{caError}</div>}

        <div className="tests-action-row">
          <button className="tests-ghost-btn" onClick={() => { setCaPhase('config'); setCaQuiz(null) }}>
            ← Back
          </button>
          <button
            className="tests-start-btn"
            onClick={submitCaQuiz}
            disabled={answered === 0 || caLoading}
          >
            {caLoading ? 'Submitting…' : `Submit Quiz (${answered}/${total} answered)`}
          </button>
        </div>
        {caConfirmOpen && (
          <div role="dialog" aria-modal="true" aria-labelledby="ca-confirm-title" className="tests-config-card" style={{ marginTop: 16 }}>
            <h3 id="ca-confirm-title">Submit partial quiz?</h3>
            <p>{unanswered} {unanswered === 1 ? 'question is' : 'questions are'} unanswered. Unanswered questions will be marked incorrect. Do you want to submit the quiz?</p>
            <div className="tests-action-row">
              <button className="tests-ghost-btn" onClick={reviewUnansweredCaQuestion}>Review Questions</button>
              <button className="tests-start-btn" onClick={() => void performCaSubmit()} disabled={caLoading}>Submit Anyway</button>
            </div>
          </div>
        )}
      </div>
    )
  }

  function renderCAResult() {
    if (!caResult || !caQuiz) return null
    const pct = caResult.percentage
    const color = pct >= 70 ? 'var(--accent)' : pct >= 50 ? '#f59e0b' : '#ef4444'
    return (
      <div className="tests-result">
        <div className="result-header">
          <ScoreRing pct={pct} size={96} color={color} />
          <div>
            <h2 className="result-score-text">{caResult.score} / {caResult.total} correct</h2>
            <p className="result-grade" style={{ color }}>{pct >= 70 ? '🎉 Excellent' : pct >= 50 ? '👍 Good effort' : '📚 Keep practising'}</p>
            <p>{caResult.answered_count ?? Object.keys(caAnswers).length} answered · {caResult.unanswered_count ?? (caResult.total - Object.keys(caAnswers).length)} unanswered</p>
            <p>{caResult.correct_count ?? caResult.score} correct · {caResult.incorrect_count ?? (caResult.total - caResult.score)} incorrect</p>
          </div>
        </div>
        <div className="result-breakdown">
          {caQuiz.questions.map((q, idx) => {
            const bd = caResult.breakdown?.find(b => b.question_id === q.id)
            const isCorrect = bd?.correct ?? (caAnswers[q.id] === q.correct_answer)
            return (
              <details key={q.id} className={`result-item ${isCorrect ? 'correct' : 'wrong'}`}>
                <summary>
                  <span className="result-item-icon">{isCorrect ? '✓' : '✗'}</span>
                  Q{idx + 1}: {q.question.slice(0, 80)}{q.question.length > 80 ? '…' : ''}
                </summary>
                <div className="result-item-body">
                  <p><strong>Your answer:</strong> {caAnswers[q.id] || 'Not answered'}</p>
                  <p><strong>Correct:</strong> {q.correct_answer}</p>
                  <p className="result-explanation">{q.explanation}</p>
                  {(bd?.source_url || q.source_url) && <a href={bd?.source_url || q.source_url} target="_blank" rel="noopener noreferrer">Official source</a>}
                </div>
              </details>
            )
          })}
        </div>
        <div className="tests-action-row">
          <button className="tests-ghost-btn" onClick={() => { setCaPhase('config'); setCaQuiz(null); setCaResult(null) }}>← New Quiz</button>
          <button className="tests-start-btn" onClick={() => { setCaAnswers({}); setCaResult(null); setCaPhase('active') }}>Retry</button>
        </div>
      </div>
    )
  }

  function renderMainsConfig() {
    return (
      <div className="tests-config-card">
        <h2 className="tests-section-title">Mains Answer Writing</h2>
        <p className="tests-description">
          Practice structured long-form answers grounded in official PWOnlyIAS study material.
          Your response is evaluated against a UPSC-aligned rubric with AI feedback.
        </p>
        {sources && renderSourceBadge(sources)}

        <div className="tests-disclaimer">
          ⚠️ This is an AI-assisted practice tool. It is not an official UPSC evaluation system and scores are indicative only.
        </div>

        <div className="tests-form">
          <label className="tests-label">
            Marks
            <div className="marks-toggle">
              <button className={`marks-btn ${mainsMarks === 10 ? 'active' : ''}`} onClick={() => setMainsMarks(10)}>
                10 Marks <span className="marks-hint">(150 words)</span>
              </button>
              <button className={`marks-btn ${mainsMarks === 15 ? 'active' : ''}`} onClick={() => setMainsMarks(15)}>
                15 Marks <span className="marks-hint">(250 words)</span>
              </button>
            </div>
          </label>

          {sources?.books.subjects && sources.books.subjects.length > 0 && (
            <label className="tests-label">
              Subject (optional)
              <select className="tests-select" value={mainsSubject} onChange={e => setMainsSubject(e.target.value)}>
                <option value="">Any subject</option>
                {sources.books.subjects.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          )}
        </div>

        {mainsError && <div className="tests-error">{mainsError}</div>}

        <button className="tests-start-btn" onClick={generateMainsQuestion} disabled={mainsLoading || !sources?.books.available}>
          {mainsLoading ? 'Generating…' : 'Get Question'}
        </button>

        {sources && !sources.books.available && (
          <p className="tests-unavail">No extracted and indexed UPSC Books are available for Mains practice.</p>
        )}
      </div>
    )
  }

  function renderMainsActive() {
    if (!mainsQuestion) return null
    return (
      <div className="tests-mains-active">
        <div className="mains-question-card">
          <div className="mains-meta">
            <span className="mains-badge">{mainsQuestion.gs_paper}</span>
            <span className="mains-badge secondary">{mainsQuestion.marks} Marks</span>
            <span className="mains-badge secondary">{mainsQuestion.word_limit} words</span>
            <span className="mains-badge secondary">{mainsQuestion.directive}</span>
          </div>
          <p className="mains-question-text">{mainsQuestion.question_text}</p>
          <p className="mains-source-credit">Source: {mainsQuestion.source_title} (PWOnlyIAS)</p>
        </div>

        <div className="mains-editor-wrap">
          <div className="mains-editor-header">
            <span>Your Answer</span>
            <span className={`word-counter ${wordPct > 100 ? 'over' : wordPct > 80 ? 'near' : ''}`}>
              {wordCount} / {wordLimit} words
            </span>
          </div>
          <div className="word-bar">
            <div className="word-bar-fill" style={{ width: `${wordPct}%`, background: wordPct > 100 ? '#ef4444' : wordPct > 80 ? '#f59e0b' : 'var(--accent)' }} />
          </div>
          <textarea
            ref={textRef}
            className="mains-textarea"
            rows={14}
            placeholder={`Write your answer here (aim for ~${wordLimit} words). Use Introduction → Body → Conclusion structure. Be specific with examples.`}
            value={answerText}
            onChange={e => setAnswerText(e.target.value)}
          />
        </div>

        <div className="mains-disclaimer">{mainsQuestion.disclaimer}</div>

        {mainsError && <div className="tests-error">{mainsError}</div>}

        <div className="tests-action-row">
          <button className="tests-ghost-btn" onClick={() => setMainsPhase('config')}>← Change question</button>
          <button
            className="tests-start-btn"
            onClick={submitMainsAnswer}
            disabled={mainsLoading || wordCount < 10}
          >
            {mainsLoading ? 'Evaluating…' : 'Submit Answer'}
          </button>
        </div>
      </div>
    )
  }

  function renderMainsResult() {
    if (!mainsEval || !mainsQuestion) return null
    const { score, max_marks, percentage, rubric_breakdown, strengths, missing_dimensions, improved_framework, disclaimer } = mainsEval
    const color = percentage >= 70 ? 'var(--accent)' : percentage >= 50 ? '#f59e0b' : '#ef4444'

    const rubricLabels: Record<keyof RubricBreakdown, string> = {
      demand_and_relevance: 'Demand & Relevance',
      structure_and_headings: 'Structure & Headings',
      content_coverage: 'Content Coverage',
      analysis_and_examples: 'Analysis & Examples',
      conclusion_presentation: 'Conclusion',
    }

    return (
      <div className="tests-result">
        <div className="result-header">
          <ScoreRing pct={percentage} size={100} color={color} />
          <div>
            <h2 className="result-score-text">{score} / {max_marks} marks</h2>
            <p className="result-grade" style={{ color }}>
              {percentage >= 70 ? '🎉 Strong attempt' : percentage >= 50 ? '👍 Developing well' : '📚 Needs more depth'}
            </p>
          </div>
        </div>

        <div className="rubric-section">
          <h3 className="rubric-title">Rubric Breakdown</h3>
          {Object.entries(rubric_breakdown).map(([key, val]) => {
            const totalPerKey = max_marks === 10 ? 2 : 3
            return (
              <RubricRow
                key={key}
                label={rubricLabels[key as keyof RubricBreakdown] ?? key}
                score={val as number}
                max={totalPerKey}
              />
            )
          })}
        </div>

        {strengths.length > 0 && (
          <div className="eval-section">
            <h3 className="eval-heading strengths-heading">✅ Strengths</h3>
            <ul className="eval-list">
              {strengths.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
        )}

        {missing_dimensions.length > 0 && (
          <div className="eval-section">
            <h3 className="eval-heading missing-heading">📌 Missing Dimensions</h3>
            <ul className="eval-list">
              {missing_dimensions.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </div>
        )}

        {improved_framework && (
          <div className="eval-section">
            <h3 className="eval-heading framework-heading">💡 Suggested Framework</h3>
            <div className="eval-framework">{improved_framework}</div>
          </div>
        )}

        <div className="mains-disclaimer">{disclaimer}</div>

        <div className="tests-action-row">
          <button className="tests-ghost-btn" onClick={() => { setMainsPhase('config'); setMainsQuestion(null); setMainsEval(null) }}>
            ← New Question
          </button>
          <button className="tests-start-btn" onClick={() => { setAnswerText(''); setMainsEval(null); setMainsPhase('active') }}>
            Rewrite Answer
          </button>
        </div>
      </div>
    )
  }

  // ── Page structure ──────────────────────────────────────────────────────────

  const completedTests = activity?.recent_events.filter(event => /test_completed/.test(event.event_type)) ?? []
  const scores = completedTests.map(event => Number(event.metadata?.percentage)).filter(Number.isFinite)
  const averageScore = scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : null
  const bestScore = scores.length ? Math.max(...scores) : null
  const activeDays = new Set((activity?.daily_breakdown ?? []).filter(day => day.event_count > 0).map(day => day.date)).size

  return (
    <div className="tests-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Exam Practice</p>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <h1>Tests Center</h1>
          </div>
          <small>Prelims MCQs, Current Affairs Quiz, and Mains Answer Writing — grounded in verified study material and official Current Affairs sources.</small>
        </div>
      </header>

      <section className="tests-metric-strip" aria-label="Test performance summary"><article><span>Tests taken</span><strong>{completedTests.length}</strong></article><article><span>Average score</span><strong>{averageScore == null ? 'No attempts' : `${averageScore}%`}</strong></article><article><span>Best score</span><strong>{bestScore == null ? 'No attempts' : `${bestScore}%`}</strong></article><article><span>Active days</span><strong>{activeDays}</strong></article></section>

      {sourcesError && <div className="tests-error global-error">{sourcesError}</div>}

      <div className="tests-tabs">
        {(['prelims', 'ca', 'mains'] as Tab[]).map(t => (
          <button
            key={t}
            className={`tests-tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'prelims' ? '📝 Prelims Quiz' : t === 'ca' ? '📰 Current Affairs Quiz' : '✍️ Mains Writing'}
          </button>
        ))}
      </div>

      <div className="tests-body">
        {tab === 'prelims' && (
          <>
            {prelimsPhase === 'config' && renderPrelimsConfig()}
            {prelimsPhase === 'active' && renderPrelimsActive()}
            {prelimsPhase === 'result' && renderPrelimsResult()}
          </>
        )}
        {tab === 'ca' && (
          <>
            {caPhase === 'config' && renderCAConfig()}
            {caPhase === 'active' && renderCAActive()}
            {caPhase === 'result' && renderCAResult()}
          </>
        )}
        {tab === 'mains' && (
          <>
            {mainsPhase === 'config' && renderMainsConfig()}
            {mainsPhase === 'active' && renderMainsActive()}
            {mainsPhase === 'result' && renderMainsResult()}
          </>
        )}
      </div>
    </div>
  )
}
