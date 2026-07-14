# Project State

## Product identity

UPSC AI Mentor Agent is a local-first study mentor, not a generic chatbot. Its intended role is to understand consented learning activity within the platform and provide explainable, adaptive next actions.

## Current architecture

- FastAPI backend with normal JSON chat and SSE streaming.
- Ollama/Qwen local generation with mode-based generation profiles.
- ChromaDB, Sentence Transformers, and RAG for uploaded study material.
- SQLite/SQLAlchemy conversation and message persistence.
- React/TypeScript/Vite test frontend.
- A shared `MemoryManager` boundary isolates persistence from orchestration.

## Completed features

- Normal and streaming chat across learn, revision, prelims, mains, and interview modes.
- PDF upload and RAG foundations.
- Persistent conversations and messages.
- Explicit, backward-compatible conversation IDs in chat requests and responses.
- Conversation CRUD APIs.
- Conversation-specific history loading and persistence.
- First SSE conversation event and final-only assistant-message persistence.
- Frontend conversation creation, selection, loading, rename, and deletion.
- Automated conversation-isolation coverage and frontend production build.
- Targeted A/B/A validation confirms a Fundamental Rights follow-up retains only conversation A history and never receives conversation B Inflation history.
- Activity Event Store backed by SQLite/SQLAlchemy with user, conversation, event type, optional subject/topic/duration/metadata, and occurrence/creation timestamps.
- Activity APIs support create, retrieve, filtered newest-first listing, and delete. Event types are restricted to the accepted platform taxonomy.
- Normal and streaming chat record exactly one `question_asked` and one successful `answer_generated`; failed generation records no answer event.
- Successful PDF processing records `pdf_uploaded`; failed processing records no upload event.
- Twelve targeted activity, affected chat, and PDF integration tests pass.
- Deterministic UPSC keyword taxonomy classifies chat activity without an LLM; manual subject/topic values override automatic rules and low-confidence text falls back to General Studies/Unclassified.
- Positive active-study durations are batched by the frontend only while a visible conversation is active and the learner recently interacted.
- `GET /activity/summary` aggregates today or seven-day stored events into study time, counts, subject/topic breakdowns, and recent activity.
- The frontend includes a responsive Activity Overview with loading, empty, error, refresh, real metrics, study-time bars, recent events, and active-tracking status.
- Eighteen targeted taxonomy, activity-summary, and affected conversation tests pass; the frontend production build passes.
- Learner Profile persists one validated manual-preference record per user with default creation, replace, partial update, onboarding completion, and safe reset APIs.
- Read-only seven-day profile insights derive studied subject/topic, study time, questions, active days, daily average, and observed mode from stored activity without changing preferences.
- Chat generation loads language, depth, and format as soft guidance; explicit current-request preferences override the saved profile without mutating it.
- The frontend includes a responsive profile/onboarding panel with five choices, skip/edit-later behavior, loading/error/saved states, reset confirmation, insights, and a platform-activity privacy note.
- Fifteen targeted profile, activity, and affected conversation tests pass; the frontend production build passes.
- Topic Mastery stores one bounded, explainable mastery/risk record per user, subject, and topic alongside validated learning evidence.
- The deterministic calculator applies small confidence- and recency-weighted changes for quiz, recall, revision, self-rating, and scored mains evidence; question volume and unrelated activity never count as mastery.
- Forgetting risk is explicitly labeled as an estimate and uses mastery, revision age, recent failures, and revision recency to assign low/medium/high risk and a next revision date.
- Reliable `quiz_answered` and `revision_completed` activity can create evidence once using activity-event deduplication.
- Mastery CRUD, evidence, recalculation, filtering, and overview APIs are connected to a responsive frontend Mastery Overview with filters, explanations, subject bars, due topics, refresh, and topic reset.
- Twenty-two targeted mastery, activity, profile, and conversation tests pass; the frontend production build passes.
- Mentor recommendations persist validated action, priority, duration, status, mastery source, validity, and lifecycle timestamps.
- The deterministic Next-Best-Action engine combines forgetting risk, weakness, overdue revision, recent failures, inactivity, reliable evidence, profile preferences, and optional available time into at most three explainable actions.
- Pending duplicates, significantly stale mastery snapshots, expired actions, and recently skipped actions are suppressed through deduplication, expiry, and cooldown rules.
- Accept, skip, and revision-completion lifecycle changes record platform activity; completion alone never assumes quiz correctness or recall success.
- The frontend includes Today's Mentor Plan with deterministic priority summary, primary and alternative actions, mastery/risk context, full reasons, refresh, Start/Complete/Skip/View Topic controls, feedback, and transparency text.
- Eighteen targeted recommendation, mastery, activity, and profile tests pass; the frontend production build passes.
- `GET /mentor/dashboard` is a lightweight aggregation endpoint over existing activity, profile, mastery, and recommendation services; it does not duplicate their calculations.
- A deterministic, maximum-three-sentence mentor brief mentions only available study, strength/risk, and next-action data, with a neutral insufficient-data fallback.
- The consolidated frontend MentorDashboard presents today's progress, daily target, mentor brief, primary and alternative actions, strengths, weaknesses, likely-to-forget topics, preferences, recent activity, subject mastery, study-time bars, revision risk, and lifecycle controls.
- Dashboard action updates refresh the aggregate data, and transparency, loading, empty, error, refresh, and last-updated states are included.
- Eighteen targeted dashboard, recommendation, mastery, activity, and profile tests pass; the frontend production build passes.
- A deterministic adaptation policy resolves language, depth, and format in message-override, saved-profile, then auto/default priority without mutating the profile.
- Auto language selection recognizes Gurmukhi as Punjabi and Devanagari as Hindi; ambiguous Romanized input uses an explicit saved language or English fallback.
- Prompt-level language guidance preserves Articles, Acts, official names, dates, citations, technical terms, sources, and UPSC mode intent without a translation or repair call.
- Quick, standard, and detailed depth settings use increasing Ollama generation limits and guidance ranges; bullets, structured, explanation, and mixed formats are prompt guidance only.
- Normal responses and initial SSE metadata return the same effective settings, and compact frontend message controls expose profile defaults and one-message overrides with answer labels.
- Fourteen targeted adaptation, chat, streaming, and profile tests pass; the frontend production build passes.
- Frontend visual polish now provides a normalized calm design system, consistent cards and controls, clearer active conversation and dashboard hierarchy, improved chat readability, responsive layouts, keyboard focus, and reduced-motion support; the production build passes.

## Partially completed features

- Mentor behavior exists through prompts, study modes, learner state, and deterministic actions, but broader adaptive delivery remains incomplete.
- RAG is operational, but production hardening and broader live validation remain.

## Postponed issues

- Mode-aware format repair is not reliable. Strict formatting must not be marked complete until revisited after the mentor foundation is stable.

## Current blocker

No known blocker recorded for the video recommendation milestone.

## Current task

Language, answer-depth, and answer-format adaptation — completed and tested.

## Exact next task

Define and implement trusted-source video recommendations only when explicitly requested.

## Relevant endpoints

- `GET /`
- `POST /chat/`
- `POST /chat/stream`
- `POST /pdf/upload`
- `POST /conversations`
- `GET /conversations`
- `GET /conversations/{conversation_id}`
- `GET /conversations/{conversation_id}/messages`
- `PATCH /conversations/{conversation_id}`
- `DELETE /conversations/{conversation_id}`
- `POST /activity/events`
- `GET /activity/events`
- `GET /activity/events/{event_id}`
- `DELETE /activity/events/{event_id}`
- `GET /activity/summary`
- `GET /profile`
- `PUT /profile`
- `PATCH /profile`
- `DELETE /profile`
- `POST /profile/onboarding`
- `GET /profile/insights`
- `POST /mastery/evidence`
- `GET /mastery/topics`
- `GET /mastery/topics/{id}`
- `GET /mastery/overview`
- `POST /mastery/topics/{id}/recalculate`
- `DELETE /mastery/topics/{id}`
- `GET /mentor/actions/next`
- `GET /mentor/actions`
- `POST /mentor/actions/generate`
- `PATCH /mentor/actions/{id}`
- `POST /mentor/actions/{id}/accept`
- `POST /mentor/actions/{id}/complete`
- `POST /mentor/actions/{id}/skip`
- `GET /mentor/dashboard`

## Known limitations

- Classification uses a deliberately small keyword taxonomy and may fall back to `General Studies / Unclassified` for unfamiliar wording.
- Active study time is browser-side and is flushed in batches; abrupt browser or device termination can lose the current unflushed batch.
- Profile preferences are soft presentation guidance only; they do not yet personalize curriculum or alter study-state calculations.
- Mastery and forgetting risk are transparent heuristic estimates, not scientifically precise measurements.
- Evidence support is foundational; richer quiz and answer-scoring producers remain future integrations.
- Recommendation priorities are transparent heuristics, not scientific or psychological judgments.
- Actions are limited to revision, quizzes, explanations, recall, and Mains practice; no video, community, or advanced planning recommendations are included.
- Dashboard visualizations intentionally use lightweight CSS bars rather than advanced charting.
- Romanized Hindi or Punjabi is intentionally treated as ambiguous and uses the saved preference or English fallback.
- Word ranges and response formats are prompt guidance, not strict truncation or deterministic repair.
- No translation API, second LLM call, video recommendation, community, or current-affairs work is included.

## Test commands

Run focused tests first. Wider validation:

```powershell
cd backend
python -m pytest -q

cd ..\upsc-ai-test-frontend-flat
npm run build
```
