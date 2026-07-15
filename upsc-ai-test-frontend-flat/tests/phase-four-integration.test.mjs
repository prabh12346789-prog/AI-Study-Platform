import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { buildVisualRoadmapRequest } from '../src/visualRoadmapRequest.ts'

test('visual generation uses backend enum values and explicit null conversation', () => {
  assert.deepEqual(buildVisualRoadmapRequest(' Historical Background of the Indian Constitution ', 'timeline', 'english'), {
    topic: 'Historical Background of the Indian Constitution', visual_type: 'timeline', language: 'english', conversation_id: null,
  })
})

test('Current Affairs and Visual Learning navigation IDs match their views', () => {
  const shell = readFileSync(new URL('../src/AppShell.tsx', import.meta.url), 'utf8')
  const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
  assert.match(shell, /page: 'current_affairs'/)
  assert.match(shell, /page: 'visual'/)
  assert.match(app, /page === 'current_affairs'.*<CurrentAffairsPage/s)
  assert.match(app, /page === 'visual'.*<VisualLearningPage/s)
})

test('roadmap history, SVG error and grounding errors remain readable', () => {
  const page = readFileSync(new URL('../src/VisualLearningPage.tsx', import.meta.url), 'utf8')
  assert.match(page, /Roadmap history/)
  assert.match(page, /SVG file is unavailable/)
  assert.match(page, /Upload a relevant PDF/)
  assert.match(page, /Pan left/)
})

test('Current Affairs retains accepted-date and nullable-brief paths', () => {
  const page = readFileSync(new URL('../src/CurrentAffairsPage.tsx', import.meta.url), 'utf8')
  assert.match(page, /resolveInitialCurrentAffairsDate/)
  assert.match(page, /No daily brief/)
  assert.match(page, /No accepted articles/)
})
