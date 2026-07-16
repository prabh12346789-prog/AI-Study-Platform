import assert from 'node:assert/strict'
import test from 'node:test'
import { createCachedOptionalLoader } from '../src/cachedOptionalLoader.ts'
import { buildCurrentAffairsQuizRequest } from '../src/currentAffairsQuizRequest.ts'
import { articlesInRange, resolveInitialCurrentAffairsDate } from '../src/currentAffairsDate.ts'
import { createSingleFlight } from '../src/singleFlight.ts'
import { existsSync, readFileSync } from 'node:fs'

test('missing brief is an empty result and is not repeatedly requested', async () => {
  let calls = 0
  const load = createCachedOptionalLoader(async () => { calls += 1; throw { status: 404 } }, reason => reason?.status === 404)
  assert.equal(await load('2026-07-15'), null)
  assert.equal(await load('2026-07-15'), null)
  assert.equal(calls, 1)
})

test('explicit refresh retries a missing brief once', async () => {
  let calls = 0
  const load = createCachedOptionalLoader(async () => { calls += 1; throw { status: 404 } }, reason => reason?.status === 404)
  await load('2026-07-15')
  await load('2026-07-15', true)
  assert.equal(calls, 2)
})

test('daily quiz sends the selected date and supported enums', () => {
  assert.deepEqual(buildCurrentAffairsQuizRequest('daily', '2025-07-04'), {
    period_type: 'daily', date_from: '2025-07-04', date_to: '2025-07-04', question_count: 5, difficulty: 'standard',
  })
})

test('weekly quiz covers selected date and preceding six days', () => {
  assert.deepEqual(buildCurrentAffairsQuizRequest('weekly', '2025-07-04'), {
    period_type: 'weekly', date_from: '2025-06-28', date_to: '2025-07-04', question_count: 5, difficulty: 'standard',
  })
})

const article = date => ({ publication_date: date, retrieved_at: `${date}T00:00:00Z` })

test('latest accepted date is selected, while a manual date is preserved', () => {
  const articles = [article('2025-07-03'), article('2025-07-04')]
  assert.equal(resolveInitialCurrentAffairsDate(articles, '2026-07-15', '2026-07-15', false), '2025-07-04')
  assert.equal(resolveInitialCurrentAffairsDate(articles, '2026-07-15', '2025-06-01', true), '2025-06-01')
})

test('insufficient selected-range content is detected before quiz creation', () => {
  assert.equal(articlesInRange([article('2025-07-04')], '2026-07-15', '2026-07-15').length, 0)
})

test('two immediate clicks run one quiz mutation', async () => {
  let calls = 0
  let release
  const pending = new Promise(resolve => { release = resolve })
  const run = createSingleFlight()
  const first = run(async () => { calls += 1; await pending })
  const second = run(async () => { calls += 1 })
  release()
  await Promise.all([first, second])
  assert.equal(calls, 1)
})

test('quiz creation is not mounted in an effect and local favicon is referenced', () => {
  const panel = readFileSync(new URL('../src/CurrentAffairsQuizPanel.tsx', import.meta.url), 'utf8')
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  assert.equal(/useEffect\([^)]*createCurrentAffairsQuiz/s.test(panel), false)
  assert.equal(existsSync(new URL('../public/favicon.svg', import.meta.url)), true)
  assert.match(html, /href="\/favicon\.svg"/)
})

test('custom payload has exactly the backend fields with no undefined values', () => {
  const request = buildCurrentAffairsQuizRequest('custom', '2025-07-04', '2025-07-01', '2025-07-03')
  assert.deepEqual(Object.keys(request).sort(), ['date_from', 'date_to', 'difficulty', 'period_type', 'question_count'])
  assert.equal(Object.values(request).includes(undefined), false)
})
