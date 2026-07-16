import { useEffect, useMemo, useRef, useState } from 'react'
import {
  createCurrentAffairsQuiz,
  CurrentAffairsApiError,
  CurrentAffairsQuiz,
  CurrentAffairsQuizPeriod,
  CurrentAffairsQuizResult,
  CurrentAffairsRetentionOverview,
  getCurrentAffairsRetentionOverview,
  markCurrentAffairsRevised,
  submitCurrentAffairsQuiz,
} from './api'
import { buildCurrentAffairsQuizRequest } from './currentAffairsQuizRequest'
import { articlesInRange } from './currentAffairsDate'
import { createSingleFlight } from './singleFlight'

export function CurrentAffairsQuizPanel({ selectedDate, acceptedArticles }: { selectedDate: string; acceptedArticles: import('./api').CurrentAffairsArticle[] }) {
  const [quiz, setQuiz] = useState<CurrentAffairsQuiz | null>(null)
  const [result, setResult] = useState<CurrentAffairsQuizResult | null>(null)
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [overview, setOverview] = useState<CurrentAffairsRetentionOverview | null>(null)
  const [from, setFrom] = useState(selectedDate)
  const [to, setTo] = useState(selectedDate)
  const [error, setError] = useState('')
  const [insufficient, setInsufficient] = useState(false)
  const [networkFailure, setNetworkFailure] = useState(false)
  const [lastPeriod, setLastPeriod] = useState<CurrentAffairsQuizPeriod>('daily')
  const [busy, setBusy] = useState(false)
  const runQuizCreation = useRef(createSingleFlight()).current

  const refresh = () => getCurrentAffairsRetentionOverview().then(setOverview).catch(() => setOverview(null))
  useEffect(() => { void refresh() }, [])
  useEffect(() => { setFrom(selectedDate); setTo(selectedDate) }, [selectedDate])

  async function start(periodType: CurrentAffairsQuizPeriod) {
    const request = buildCurrentAffairsQuizRequest(periodType, selectedDate, from, to)
    if (!articlesInRange(acceptedArticles, request.date_from, request.date_to).length) return
    await runQuizCreation(async () => {
      setBusy(true); setError(''); setInsufficient(false); setNetworkFailure(false); setLastPeriod(periodType)
      try {
        setQuiz(await createCurrentAffairsQuiz(request))
        setResult(null); setAnswers({}); setStep(0)
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : 'Quiz unavailable.'
        setError(message)
        setInsufficient(reason instanceof CurrentAffairsApiError && reason.status === 422 && /insufficient accepted/i.test(message))
        setNetworkFailure(reason instanceof CurrentAffairsApiError && reason.status === 0)
      } finally { setBusy(false) }
    })
  }

  async function submit() {
    if (!quiz) return
    setBusy(true); setError('')
    try {
      setResult(await submitCurrentAffairsQuiz(quiz.id, quiz.questions.map(question => ({ question_id: question.id, answer: answers[question.id] || '' }))))
      await refresh(); window.dispatchEvent(new Event('mentor-data-changed'))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Submission failed.') } finally { setBusy(false) }
  }

  const question = quiz?.questions[step]
  const dailyAvailable = useMemo(() => articlesInRange(acceptedArticles, selectedDate, selectedDate).length > 0, [acceptedArticles, selectedDate])
  const weeklyRequest = useMemo(() => buildCurrentAffairsQuizRequest('weekly', selectedDate), [selectedDate])
  const weeklyAvailable = useMemo(() => articlesInRange(acceptedArticles, weeklyRequest.date_from, weeklyRequest.date_to).length > 0, [acceptedArticles, weeklyRequest])
  const customAvailable = useMemo(() => articlesInRange(acceptedArticles, from, to).length > 0, [acceptedArticles, from, to])
  return <>
    <section className="ca-brief"><p className="eyebrow">Active recall</p><h2>Current Affairs Quiz</h2><p>Generated only from accepted stored articles. Starting does not change mastery.</p>
      <div className="roadmap-actions"><button disabled={busy || !dailyAvailable} onClick={() => void start('daily')}>Take Today’s Quiz</button><button disabled={busy || !weeklyAvailable} onClick={() => void start('weekly')}>Take Weekly Quiz</button><label>From<input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label><label>To<input type="date" value={to} onChange={event => setTo(event.target.value)} /></label><button disabled={busy || !customAvailable} onClick={() => void start('custom')}>Create Custom Quiz</button></div>
      {!dailyAvailable && <p className="privacy-note">No accepted articles are available for {selectedDate}; quiz creation is disabled.</p>}
      {error && <div className={insufficient ? 'visual-state' : 'visual-state error'}><strong>{insufficient ? 'Insufficient accepted articles' : 'Quiz unavailable'}</strong><p>{error}</p>{networkFailure && <button className="icon-button" disabled={busy} onClick={() => void start(lastPeriod)}>Retry</button>}</div>}
      {question && !result && <article className="ca-card"><small>Question {step + 1} of {quiz!.questions.length} · {question.topic}</small><progress value={step + 1} max={quiz!.questions.length} /><h3>{question.question}</h3>{question.options_json.length ? question.options_json.map(option => <label key={option}><input type="radio" name={question.id} checked={answers[question.id] === option} onChange={() => setAnswers(current => ({ ...current, [question.id]: option }))} /> {option}</label>) : <textarea value={answers[question.id] || ''} onChange={event => setAnswers(current => ({ ...current, [question.id]: event.target.value }))} placeholder="Type your recall answer" />}<div className="roadmap-actions"><button disabled={!step} onClick={() => setStep(value => value - 1)}>Previous</button>{step < quiz!.questions.length - 1 ? <button onClick={() => setStep(value => value + 1)}>Next</button> : <button disabled={busy} onClick={() => void submit()}>Submit</button>}</div></article>}
      {result && <article className="ca-card"><h3>{result.score}/{result.total} · {result.percentage}%</h3><p>Weak topics: {result.weak_topics.join(', ') || 'None'}</p>{result.results.map(item => <details key={item.question_id}><summary>{item.correct ? 'Correct' : 'Review answer'}</summary><p>{item.explanation}</p><p>Correct answer: {item.correct_answer}</p><a href={item.source_url} target="_blank" rel="noreferrer">Official source</a></details>)}<div className="roadmap-actions"><button onClick={() => quiz && void start(quiz.period_type as CurrentAffairsQuizPeriod)}>Retake</button><button onClick={() => { setQuiz(null); setResult(null) }}>Return to Current Affairs</button></div></article>}
    </section>
    <section className="ca-subject"><h2>Current Affairs Retention</h2><small>As of {selectedDate}</small>{!overview ? <p>Complete a quiz to begin retention tracking.</p> : <><div className="ca-dashboard-stats"><span><strong>{Math.round(overview.average_retention * 100)}%</strong><small>Average</small></span><span><strong>{overview.high_risk_articles.length}</strong><small>High risk</small></span><span><strong>{overview.due_for_revision.length}</strong><small>Due</small></span><span><strong>{overview.saved_but_unrevised_article_ids.length}</strong><small>Saved, untested</small></span></div><p>Weak subjects: {overview.weak_subjects.map(item => item.subject).join(', ') || 'None yet'}</p><p>Weekly trend: {overview.weekly_trend.map(item => `${item.date}: ${item.percentage}%`).join(' · ') || 'No attempts yet'}</p>{overview.high_risk_articles.map(item => <article className="ca-card" key={item.id}><h3>{item.topic}</h3><p>{Math.round(item.retention_score * 100)}% retained · {item.risk_level} risk.</p><p>Next useful action: revise this source, then retest it.</p><button onClick={() => void markCurrentAffairsRevised(item.article_id).then(refresh)}>Mark Revised</button></article>)}</>}</section>
  </>
}
