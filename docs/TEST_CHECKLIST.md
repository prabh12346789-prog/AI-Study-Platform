# Test Checklist

Run milestone-specific tests first, then complete the applicable regression checks.

## Backend and API

- [ ] Backend starts without configuration or import errors.
- [ ] `GET /` returns a successful health response.
- [ ] Swagger UI at `/docs` loads and lists the current endpoints.
- [ ] CORS permits the configured Vite development origins.

## Chat

- [ ] Normal chat returns status, answer, provider, sources, and conversation ID.
- [ ] Streaming chat emits the conversation event first and streams the answer.
- [ ] SSE completion closes cleanly without rendering a sentinel token.
- [ ] Only the completed assistant response is persisted; partial tokens are not.
- [ ] Learn mode works.
- [ ] Revision mode works.
- [ ] Prelims mode works.
- [ ] Mains mode works.
- [ ] Interview mode works.

## PDF and RAG

- [ ] PDF upload accepts a valid PDF and reports processing status.
- [ ] RAG retrieves relevant uploaded content.
- [ ] Chat responses preserve and return source metadata where available.
- [ ] Conversation changes do not regress PDF upload or RAG behavior.

## Conversations and memory

- [ ] Conversation create, list, get, rename, and delete work.
- [ ] Selecting a conversation loads only its messages.
- [ ] Two conversations remain isolated during follow-up questions.
- [ ] Requests without a conversation ID remain backward compatible.
- [ ] Invalid conversation IDs return a clear error.
- [ ] Conversation order follows descending `updated_at`.
- [ ] Messages and conversations persist across backend restarts.
- [ ] New Chat never reuses the previous conversation history.

## Activity events

- [ ] Consented platform activity can be appended and listed.
- [ ] Unconsented activity is rejected and never persisted.
- [ ] Events are ordered by occurrence time.
- [ ] A stored event can be deleted for user-data control.

## Frontend and regression

- [ ] `npm run build` succeeds.
- [ ] Sidebar creation, selection, rename, and delete controls work.
- [ ] Normal and streaming UI modes remain compatible.
- [ ] Existing API contracts remain backward compatible unless explicitly changed.
- [ ] Targeted backend tests pass.
- [ ] Full backend suite passes with `python -m pytest -q`.
- [ ] No unrelated product files or generated artifacts were changed.
