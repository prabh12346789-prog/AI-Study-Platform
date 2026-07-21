# Project State

## Product identity

UPSC AI Mentor Agent is a local-first study mentor, not a generic chatbot. Its intended role is to understand consented learning activity within the platform and provide explainable, adaptive next actions.

## Current architecture

- FastAPI backend with normal JSON chat and SSE streaming.
- Ollama/Qwen local generation with mode-based generation profiles.
- ChromaDB and local Ollama `nomic-embed-text` embeddings for uploaded study material and RAG.
- SQLite/SQLAlchemy conversation and message persistence.
- React/TypeScript/Vite test frontend.
- A shared `MemoryManager` boundary isolates persistence from orchestration.
- Community is removed from the active MVP: its API router, frontend view, activity creation types, demo fixtures, tests, and tracked bytecode artifacts are absent. Older SQLite Community tables are deliberately left untouched for a future controlled migration. Historical activity rows remain readable but unsupported event types are excluded from study summaries, mastery, and progress. Legacy-table/startup, active-router, activity, mastery, mentor, demo, Current Affairs, and Visual Roadmap validation passes: 86 targeted tests and the full 160-test backend suite pass, as do TypeScript and the frontend production build.

- Completed Task A (PWOnlyIAS-Only Current Affairs): All newly collected and displayed Current Affairs come exclusively from official PWOnlyIAS sources (`publisher == 'PWOnlyIAS'`). Non-PWOnlyIAS historical DB records remain preserved for rollback but are filtered out of all learner-facing APIs, daily briefs, quiz generation, and retention recommendations. The Current Affairs frontend has been updated to provide exactly five primary navigation sections: 1. Day-wise, 2. Weekly-wise, 3. Monthly-wise, 4. Subject-wise, 5. Q&A. An integrated internal webpage reader renders structured extracted content blocks, table of contents, Prelims/Mains points, page references, and official PWOnlyIAS source/PDF links.
- Completed Task B (Dashboard and Progress Redesign): The Dashboard has been redesigned so the initial viewport is clean and uncluttered, showing only the compact mentor header, four summary metrics (today study time, 7-day study time, average mastery, high-risk topics), 7-day Study Progress line chart, Subject Time donut chart, and a scroll indicator button. Below-the-fold sections are revealed using a lightweight `IntersectionObserver` scroll-reveal component. The Progress page (`/progress`) is organized into six structured metrics and analytics sections backed by real API data without mock values.
- Twenty-seven targeted Current Affairs backend tests pass 100%. Backend startup smoke test passes. Frontend typecheck (`npx tsc --noEmit`) and frontend production build (`npm run build`) pass with zero errors.

- Premium frontend Phase 4 replaces the Library placeholder with the real `GET /pdf/documents` list and multipart `POST /pdf/upload`. One canonical `['pdf','documents']` query is shared with Dashboard; upload success refreshes that cache plus only the relevant activity/mentor queries. The premium Library supports sanitized names, newest-first backend ordering, indexed/processing/failed/legacy/unknown states, nullable metadata, search, status filters, bounded hidden-tab-aware processing polling, PDF-only selection/drop, synchronous single-flight upload, cancellation, truthful stages, and section-specific empty/error states. Only indexed documents expose Ask AI and Visual Learning navigation with sanitized unsent route state; neither navigation triggers generation. Live validation uploaded one uniquely named known-text PDF exactly once and produced one indexed record with 1 page, 1 chunk, Ollama, `nomic-embed-text`, and `documents_ollama_nomic_embed_text`; the rendered Library showed 36 real records and no filesystem path. The backend exposes no configured upload-size limit, so the frontend does not invent one. Thirty-nine frontend tests, TypeScript, ESLint, and production build pass; a non-blocking bundle-size warning remains.

- Premium frontend Phase 3 replaces the Coach placeholder with real conversation CRUD, conversation-specific history caches, POST-based SSE streaming, progressive token rendering, exact mode/language/depth/format overrides, profile-default labels, learner-controlled cancellation, elapsed generation time, safe Markdown, guarded source disclosure, document/prompt navigation state, near-bottom scrolling, and responsive conversation/context panels. Synchronous stream guards and mutation pending states prevent duplicate requests under Strict Mode; A/B/A tests confirm isolation. The original Vite process on 5173 was stopped as explicitly authorized, and the premium frontend then passed live CORS/browser validation on that origin. A live concise Article 32 request produced exactly one conversation event, one token event, one done event, and exactly one persisted user/assistant pair; the grounded refusal was preserved. The backend currently emits no SSE source event and persisted history has no citation metadata, so live sources cannot be recovered without an unsupported second generation. Thirty-one frontend tests, TypeScript, ESLint, and production build pass. Desktop Dashboard and Coach screenshots pass; Edge headless cannot perform a true 390px layout because it enforces a roughly 500px minimum viewport, though mobile drawer and route behavior are automated-tested.

- Premium frontend Phase 2 replaces the Dashboard placeholder with real mentor, activity, mastery, Current Affairs, document, roadmap, video, retention, profile, and recent-activity queries. Critical mentor/activity/mastery failures use a full retry state; optional sections fail independently. The personalized hero supports single-flight Start/Complete/Skip actions, safe daily-target metrics, real Current Affairs save/unsave, a seven-day study visualization derived from stored study-time events, section-specific empty states, and responsive below-fold previews without mock fallback values or Community content. Live GET validation returned 1,046 study seconds today, one accepted Current Affairs story, 35 document records, four roadmaps, 100 recent events, no current mentor action, and no verified video recommendation. Twenty-four frontend tests, TypeScript, ESLint, and production build pass. Full browser viewport validation remains blocked because the original frontend currently occupies the backend-approved port 5173; the backend and original frontend were not changed or stopped.

- Premium frontend Phase 1 is complete in the independent `upsc-ai-mentor-premium` directory. The audited target contains no Bolt mock-data module, Supabase dependency, simulated production behavior, or hardcoded feature content. It provides a Vite/React/TypeScript/Tailwind foundation, validated public API environment configuration, persisted collapsible desktop shell, accessible Escape-close mobile drawer, `/` to `/dashboard` routing, direct approved routes, a proper Not Found page, and Community exclusion. TanStack Query supplies one shared health cache to the sidebar and Settings with one retry, a 30-second interval paused in hidden tabs, manual retry, and explicit backend/Ollama/model/vector states. The centralized client safely handles JSON, empty responses, cancellation, connection failures, FastAPI validation details, and 404/422/500 errors; shared loading, empty, error, retry, and page-loading primitives are ready for later phases. Fourteen tests, TypeScript, ESLint, and the production build pass. Live `/health` returned all services ready with Ollama `nomic-embed-text`; the original frontend, backend, and contracts are unchanged.

- My Library now lists real PDF ingestion records through the read-only `GET /pdf/documents` endpoint. The existing filesystem metadata boundary records processing before extraction, marks failed attempts without exposing errors or local paths, and reports nullable page/chunk counts, indexed state, Ollama provider/model, and the active Chroma collection. Legacy BGE metadata is explicitly inactive and never mislabeled as belonging to the Ollama collection. The responsive frontend automatically refreshes after upload, deduplicates by document ID, handles loading/empty/error/failed/legacy states, and links indexed documents to prefilled AI Study Coach and Visual Learning. Live Edge validation uploaded `library-live-validation.pdf`, displayed it exactly once with 4 pages, 2 chunks, `ollama`/`nomic-embed-text`, and `documents_ollama_nomic_embed_text`, navigated both actions, showed no desktop/mobile overflow, and captured no console or HTTP errors. Nineteen targeted tests, the full 164-test backend suite, TypeScript, and the frontend production build pass.
- Final headless Edge walkthrough validated Dashboard, AI Study Coach, Library upload, Current Affairs, Quizzes, Visual Learning, Revision, Progress, Profile, and responsive layouts at 1920×1080, 1440×900, 1366×768, 1024×768, and 390×844. A confirmed React development Strict Mode bug that sent duplicate roadmap-quiz creation requests and duplicate missing-quiz probes was fixed with per-roadmap request caching; the retest sends one creation POST per click, opens five questions, submits once, and returns a scored result. The live grounded timeline completed through the deterministic fallback with valid stored nodes/connections, a PDF page citation, a 200 SVG download target, and updated history. TypeScript and the frontend production build pass.
- Live Current Affairs ingestion now performs official-first RSS/Atom and public source-listing discovery before generic search, carries discovery metadata into article ranking, rejects home/index/archive/tag/search/login/quiz/test/answer-writing URLs before extraction, and uses source-specific content containers with a safe generic fallback. Collection logs include a structured rejection breakdown without page content or secrets. Current Affairs uses its narrower source-adapter catalog rather than the broader Chat allowlist. Rejected, unsupported-summary, and indexing-failed articles are not committed; previously misclassified quiz/reference records are archived and removed from Chroma. Direct RBI validation accepted press release `prid=60774`, stored its grounded short summary and metadata, indexed it with `nomic-embed-text`, generated an idempotent brief for its real publication date (2025-07-04), and grounded Chat retrieved it with confidence 0.774 and a Current Affairs citation. Sixty targeted tests, the full 157-test backend suite, TypeScript, and the frontend build pass.
- Personalized Current Affairs expansion adds a controlled adapter hierarchy for official primary sources, approved daily analysis, Mains/editorial analysis, monthly revision, and official video links. Accepted stories are grouped into issues using canonical URL/content hash plus normalized-title, publication-date, topic, and title-token similarity; one primary-source-led card can retain supporting analysis citations. A deterministic personalized feed ranks grouped issues using UPSC importance, source tier, freshness, recent subject activity/current mode, weak or high-risk topics, Current Affairs retention urgency, saved state, profile language/depth/format, and daily target without treating reading or saving as mastery. Current Affairs is now reading-only with personalized brief, Prelims, Mains, editorial, monthly, video, saved, and revision sections; daily/weekly/custom Current Affairs practice and retention moved to the separate Quizzes page alongside roadmap quiz navigation. Existing accepted rows can be idempotently re-indexed into the active Ollama collection. A Windows Task Scheduler runner is registered for 7:00 AM with an overlap lock, bounded Ollama check, timestamped logs, and no secrets in its task definition. Fifty-five targeted tests, the full 152-test backend suite, TypeScript, and the frontend production build pass.
- Visual Roadmap generation now uses a bounded JSON-only pipeline: direct parsing, fence/prose extraction, safe trailing-comma cleanup, strict Pydantic validation with unknown fields forbidden, one schema-guided repair attempt, and a deterministic grounded fallback. The fallback copies sentence-level facts from retrieved chunks in source order, extracts explicit timeline years, builds valid bounded connections, preserves citations, and records its generation method without changing endpoint contracts. Forty-eight targeted tests and the full 147-test backend suite pass. Live validation for `Historical Background of the Indian Constitution` reached sufficient grounding at 0.829; malformed Qwen output safely fell back to a valid seven-node timeline, served source-visible SVG, and opened a five-question roadmap quiz.
- Embeddings now use Ollama's local HTTP API with `nomic-embed-text`, removing the active SentenceTransformers/PyTorch runtime path that Windows Application Control blocked at `torch/lib/shm.dll`. Single and batched inputs are validated, L2-normalized, and dimension-checked with readable provider/model errors. The isolated `documents_ollama_nomic_embed_text` Chroma collection prevents legacy BGE vectors from mixing with the new vectors while preserving ingestion metadata, retrieval thresholds, citations, chat grounding, roadmap grounding, and Current Affairs indexing interfaces. Sixty-one targeted tests and the full 139-test backend suite pass. Live validation installed the model, indexed a text PDF into a 768-dimensional collection, grounded Chat with one PDF source, confirmed roadmap retrieval grounding, and loaded Current Affairs; Qwen's roadmap JSON remained malformed after the existing repair attempt, matching the postponed model-format limitation.
- PDF extraction now uses pure-Python `pypdf` instead of PyMuPDF because Windows Application Control blocked PyMuPDF's unsigned native binaries. The parser preserves the existing extracted text, page count, per-page text, chunking input, and one-based page-range behavior while adding page-number and available document metadata internally.
- The frontend now uses a premium dark navy application shell with a fixed desktop sidebar, compact sticky header, local feature-navigation search, Lucide icons, responsive drawer navigation, and real routes for Dashboard, AI Study Coach, My Library, Current Affairs, Visual Learning, Revision Center, Quizzes, Progress, Profile, and Settings. The mentor dashboard keeps real API data above the fold, while existing chat streaming, PDF upload, Current Affairs, roadmap quizzes, mastery, retention, mentor actions, video recommendations, activity, and profile integrations remain unchanged.
- Dashboard Phase 2 keeps the first viewport focused on the real mentor brief, daily target, four evidence-backed metrics, primary mentor action, and latest accepted Current Affairs story/brief/quiz state. Progress, revision risk, trusted videos, recent visual roadmaps, and activity remain below the explicit Scroll for More control and use existing APIs only.
- AI Study Coach Phase 3 adds an in-page searchable conversation rail, responsive assistant/context drawer, compact real-feature actions, premium message/Markdown presentation, collapsible existing-source metadata, and a responsive sticky composer containing mode, language, depth, format, profile-default, PDF, and streaming controls. Existing conversation isolation, request bodies, SSE event parsing, progressive token updates, near-bottom scrolling, and normal chat behavior remain unchanged.
- Premium frontend Phase 4 reorganizes Current Affairs into a date-consistent brief, real ranked top story, compact headlines, existing quiz/retention workspace, saved-story controls, and below-fold revision content. Visual Learning now uses compact visual-type cards, a focused roadmap viewer, reusable source labeling, and metadata-only roadmap history while preserving grounded generation, SVG, quiz, mastery, and activity contracts.

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
- Trusted-source video recommendations now use a seeded local catalog of active, verified official-source links across seven UPSC subjects, deterministic topic/language/time ranking, two-day dismissal cooldown, and a maximum of three results.
- Read-only video listing, detail, and recommendation APIs are joined by explicit open/dismiss actions; opening records `video_opened` without changing mastery, while mentor `watch_video` actions require an exact trusted match and remain below urgent revision.
- The responsive frontend adds verified video cards to Mentor Intelligence and explicit video requests in chat, with filters, reasons, loading/error/empty/link states, Watch, Save, dismiss, and post-video quiz guidance; targeted tests and the production build pass.
- Backend cold start is HTTP-ready independently of Ollama, embeddings, and Chroma: heavy retrieval/provider construction is deferred to first chat/PDF use, staged startup logs identify settings/router/database readiness, and non-blocking `GET /health` reports component state. Validation reached application-ready in 1.80 seconds.
- End-to-end stabilization passes 41 connected journey tests followed by the full 65-test backend regression and frontend production build. The only failure found was an order-dependent health test, corrected to verify that health reporting observes—but never initializes—shared embedding/vector state.
- Chat SSE now emits conversation/settings metadata before retrieval, forwards each Ollama delta as a named token event, ends with a non-visible done event, and persists the assistant response once only after successful completion. The frontend parses split SSE event blocks incrementally and batches visible deltas for 45 ms, with preparation/retrieval/generation status text and reader-safe scrolling. Live Ollama validation produced 181 cold and 196 warm chunks; first-token time measured 18.41 seconds cold and 2.27 seconds warm.
- A development-only, idempotent demo fixture at `backend/scripts/seed_demo.py` creates `backend/data/demo.sqlite3` with a strong topic, weak/high-risk evidence, completed revision, quiz mistakes, mentor action, and trusted video match; production startup never invokes it.
- Visual Learning Mode creates source-grounded timeline, flowchart, concept-map, comparison, process, and cause-and-effect roadmaps from retrieved study material through the existing local Ollama and RAG boundaries.
- `VisualRoadmap` persists ownership, optional conversation linkage, classification, type/language/status, validated structure, source metadata, and generated-file paths. SVG, JSON, source, and animation-ready metadata files remain outside SQLite under `backend/generated/users/<user>/roadmaps/<id>/`.
- A strict Pydantic schema limits output to twelve concise nodes, unique IDs, valid connections, and retrieved source IDs. Insufficient context fails clearly; one JSON-only repair attempt may fix structure without a second factual pass.
- A deterministic dependency-free SVG renderer provides accessible titles/descriptions, wrapped educational cards, source markers, UPSC exam points, and layouts for all six types.
- Create/list/filter/detail/SVG/save/delete APIs are connected to a responsive Visual Learning page with real stages, history/empty/error states, zoom/fit/pan, source review, download/regenerate/delete/question actions, and disabled quiz/animation actions.
- Generated/opened/saved activity is recorded with roadmap, classification, visual type, and language metadata and never becomes mastery evidence. Targeted roadmap, activity, and conversation tests and the frontend production build pass; animation remains future work.
- Roadmap-derived recall quizzes deterministically create up to ten MCQ, chronology, year-matching, and true/false questions using only validated saved roadmap fields; the default is five and timeline quizzes always begin with a chronology question when sufficient nodes exist.
- Quiz creation and retrieval do not affect mastery. Idempotent submission scores the saved quiz, returns explanations and weak source nodes, records started/completed activity, and creates one `quiz_correct` or `quiz_incorrect` mastery evidence item per answer without duplicating evidence on repeated submission.
- The Visual Learning viewer now includes an enabled recall quiz panel with progress, previous/next controls, ordering and option inputs, submission states, result review, weak roadmap sections, retake, and return actions. Completed attempts refresh Mastery Overview and Mentor Dashboard data. Twenty targeted quiz, roadmap, mastery, and activity tests pass; the frontend production build passes.
- Answer presentation now separates UPSC mode purpose from bullets, structured, explanation, and mixed layout contracts. The fixed Learn Definition/Explanation template and normal-only mode repair call were removed, so normal and streaming generation share one prompt policy and resolved format metadata.
- Chat prompts now prioritize accuracy and grounding, the exact current question and its limiting phrases, mode intent, presentation format, depth, language, relevant retrieved context, and finally non-authoritative conversation history. Historical-background questions explicitly retain constitutional-development chronology rather than collapsing into a generic Constitution definition.
- Seventeen targeted adaptation, prompt, conversation, and async-flow tests pass, and the frontend production build passes. Live local-model checks confirmed distinct bullets/structured/explanation behavior and topic relevance; mixed-format opening-paragraph compliance and ungrounded factual reliability remain model limitations, so strict formatting remains postponed.
- A shared `GroundingDecisionService` now classifies local or trusted-web context as sufficient, insufficient, or absent using configurable chat and stricter roadmap thresholds; confidence is a transparent heuristic rather than scientific precision.
- Local PDFs are evaluated first. Factual chat or roadmap requests use web fallback only when local grounding is insufficient and web search is enabled; casual/rewrite requests, sufficiently grounded PDFs, and local-only configuration do not trigger web retrieval. Missing trusted context returns a clear non-invented response for chat and rejects roadmap generation.
- Trusted web fallback accepts only manually allowlisted official government, legislative, judicial, regulatory, recognized international, and approved reference domains. Approved pages retain publisher, canonical URL, category, trust level, retrieval/publication dates, relevant headings/text, content hash, subject/topic, and explicit `source_type=web`; unknown publishers and suspicious redirects are rejected.
- Web chunks use a separate file cache keyed by canonical URL/content hash, with 30-day stable and 24-hour changing-information defaults. PDF and web provenance remain visible in API sources and Visual Learning labels, including safe open-source links and a fallback notice.
- Thirty-one targeted grounding/search, RAG-facing roadmap, chat, adaptation, and progressive streaming tests pass across the focused runs. The frontend production build passes.
- Current Affairs Phase 1 persists trusted articles, deterministic language/date briefs, and user-isolated saved articles. Records retain grounded UPSC summaries, publisher/canonical source, dates, taxonomy, syllabus tags, importance, Prelims/Mains relevance, content hash, and active/archived/rejected status.
- Collection reuses the existing allowlisted web search and local model. Only sufficiently extracted approved-source text is summarized, URL/hash duplicates are reused, rejected items stay out of the learner feed, and collection/brief generation require a configured internal admin key.
- Accepted summaries are indexed in the existing Chroma collection with explicit `source_type=current_affairs`, article, title, publisher, URL, publication date, subject/topic, retrieval time, and hash metadata. Existing chat retrieval can cite stored weekly or subject-specific developments.
- Daily briefs deterministically aggregate accepted summaries into ranked stories, subject groups, Prelims facts, and Mains themes without another model call. Open/save/brief activity never creates mastery evidence.
- The responsive Current Affairs page provides real date/search/subject/importance filtering, daily briefs, subject-grouped cards, details, save and safe source actions, plus loading/empty/error states. Mentor Dashboard adds a compact unread/top-subject/saved/brief-status card.
- Forty-two targeted current-affairs, grounding/RAG, activity, mastery, mentor, chat, and roadmap tests pass; the frontend production build passes. Current-affairs quizzes, notifications, payments, and advanced institutional analytics are not implemented.
- Current Affairs live discovery now validates the configured provider, uses reachable Bing RSS discovery, logs query/domain/redirect/extraction counters, explains zero-result causes, supports repeatable CLI query overrides and allowlisted direct URLs, and generates five date-aware UPSC query categories. Live validation returned 10 raw results, 5 approved RBI extractions, and reached local summarization; 24 focused Current Affairs and grounding tests pass.
- Current Affairs article selection now rejects homepage/index URLs before Ollama, scores clean body length, title, publication date, paragraph count, duplicate boilerplate, and navigation ratio, ranks article-shaped results first, and parses optional summary fields resiliently without weakening factual grounding. Live direct validation accepted RBI press release `prid=60774` and generated its daily brief; 23 focused Current Affairs tests pass.
- Current Affairs Quiz and Retention Tracking adds deterministic daily, weekly, and custom quizzes generated only from persisted accepted article summaries, Prelims facts, Mains relevance, metadata, and citations. Idempotent submission creates per-question mastery evidence, article retention/risk/revision schedules, activity events, weak-topic/source feedback, mentor Current Affairs actions, a complete quiz/retention interface, and dashboard status. Thirty-nine focused Current Affairs, mastery, and mentor tests and the frontend production build pass.
- Final MVP hardening completes the idempotent demo learner with onboarding, two isolated conversations, PDF fixture/activity, mastery/risk states, mentor/video matches, roadmap and quiz result, and accepted Current Affairs/brief/quiz/high-risk retention. Measured application readiness was 1.37 seconds, cold/warm first chat token 16.86/1.13 seconds, dashboard 32.9 ms, and Current Affairs APIs about 30 ms.

## Partially completed features

- Mentor behavior exists through prompts, study modes, learner state, and deterministic actions, but broader adaptive delivery remains incomplete.
- RAG is operational, but production hardening and broader live validation remain.

## Postponed issues

- Mode-aware format repair is not reliable. Strict formatting must not be marked complete until revisited after the mentor foundation is stable.

## Current blocker

No automated backend or build blocker. The final headless Edge walkthrough completed. Live Qwen detailed generation remained slow enough to require a manual stop after producing a substantial partial answer, and a newly uploaded Constitution PDF was accepted/indexed but the immediate narrow follow-up did not meet the retrieval threshold, so Chat safely refused to invent an answer. The Quizzes page performs one expected `GET` that returns 404 when a ready roadmap has no quiz; this is handled as an unavailable optional quiz but still appears as a failed network response in development tools.

## Current task

Final MVP hardening and demo readiness — completed and tested.

## Exact next task

No next feature is selected. Scheduling/notifications and roadmap animation remain future work and must begin only when requested.

## Relevant endpoints

- `GET /`
- `POST /chat/`
- `POST /chat/stream`
- `POST /pdf/upload`
- `GET /pdf/documents`
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
- `GET /videos`
- `GET /videos/{video_id}`
- `GET /videos/recommendations`
- `POST /videos/{video_id}/open`
- `POST /videos/{video_id}/dismiss`
- `POST /visual-roadmaps`
- `GET /visual-roadmaps`
- `GET /visual-roadmaps/{id}`
- `GET /visual-roadmaps/{id}/svg`
- `POST /visual-roadmaps/{id}/save`
- `DELETE /visual-roadmaps/{id}`
- `POST /visual-roadmaps/{id}/quiz`
- `GET /visual-roadmaps/{id}/quiz`
- `POST /visual-roadmaps/{id}/quiz/submit`
- `POST /current-affairs/collect`
- `GET /current-affairs/articles`
- `GET /current-affairs/articles/{id}`
- `GET /current-affairs/daily`
- `POST /current-affairs/daily/generate`
- `POST /current-affairs/articles/{id}/save`
- `DELETE /current-affairs/articles/{id}/save`
- `GET /current-affairs/saved`
- `GET /current-affairs/summary`

## Known limitations

- Live Current Affairs discovery still depends on feed validity, search-engine coverage, and server-rendered article pages. Several advertised feed URLs currently return non-XML or blocked responses, and Bing can ignore `site:` intent and return noisy results. PIB listing discovery is reachable and returns release URLs, but the live `PRID=2284767` page exposed insufficient clean server-rendered article text and no usable publication date, so it was explicitly rejected and not stored. Official direct URLs remain a policy-equivalent diagnostic fallback; authentication, challenges, JavaScript-only pages, and copyright restrictions are never bypassed.
- Qwen may still return malformed roadmap JSON and can make the single repair call slow. Sufficiently grounded requests now complete through the deterministic fallback; requests without safe extractable grounded facts still fail rather than inventing nodes.
 - PDFs and Current Affairs content indexed in the legacy BGE-backed `documents` collection are intentionally not visible in the new Ollama collection and must be re-indexed. Ollama must be running locally with `nomic-embed-text` installed for ingestion and local retrieval.
- Image-only scanned PDFs still require OCR and are not supported by the text-only `pypdf` extraction path.
- Classification uses a deliberately small keyword taxonomy and may fall back to `General Studies / Unclassified` for unfamiliar wording.
- Active study time is browser-side and is flushed in batches; abrupt browser or device termination can lose the current unflushed batch.
- Profile preferences are soft presentation guidance only; they do not yet personalize curriculum or alter study-state calculations.
- Mastery and forgetting risk are transparent heuristic estimates, not scientifically precise measurements.
- Evidence support is foundational; richer quiz and answer-scoring producers remain future integrations.
- Recommendation priorities are transparent heuristics, not scientific or psychological judgments.
- Actions are limited to revision, quizzes, explanations, recall, Mains practice, and trusted videos; advanced planning recommendations are not included.
- Dashboard visualizations intentionally use lightweight CSS bars rather than advanced charting.
- Romanized Hindi or Punjabi is intentionally treated as ambiguous and uses the saved preference or English fallback.
- Word ranges and response formats are prompt guidance, not strict truncation or deterministic repair.
- The video catalog is deliberately small and manually curated; links are not scraped, downloaded, or automatically freshness-checked.
- No translation API, second LLM call, or current-affairs work is included.
- Visual roadmaps require relevant indexed material and produce SVG only. Recall quizzes are intentionally limited to saved roadmap content; short-recall question generation is reserved by the schema but not prioritized in the current deterministic generator. Animation is not implemented.
- Presentation is prompt-guided rather than deterministically repaired. The local 3B model can still miss part of a mixed-format contract or state inaccurate facts when no relevant retrieved material is available; high-stakes factual answers require grounded sources and review.
- Trusted web extraction is deliberately lightweight and allowlist-based. It does not execute JavaScript, bypass access controls, or guarantee coverage of every official site; pages that cannot provide clean relevant text are rejected.
- Current-affairs coverage depends on approved pages exposing sufficient server-rendered text and usable dates. JavaScript-only, blocked, malformed, or thin pages are rejected; Phase 1 has no scheduler, notifications, quizzes, or advanced analytics.

## Test commands

Run focused tests first. Wider validation:

```powershell
cd backend
python -m pytest -q

cd ..\upsc-ai-test-frontend-flat
npm run build
```

## Deterministic demo steps

```powershell
cd C:\Users\Guest1\AI-Study-Platform\backend
.\.venv\Scripts\python.exe scripts\seed_demo.py
$env:MEMORY_DB_PATH="$PWD\data\demo.sqlite3"
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# In a second terminal
cd C:\Users\Guest1\AI-Study-Platform\upsc-ai-test-frontend-flat
npm run dev
```

Open the shown Vite URL, then use this concise demo checklist:

1. Open Mentor Dashboard.
2. Ask a UPSC question.
3. Show streaming and adaptive format.
4. Upload a PDF and show its citation.
5. Show mastery update from a quiz.
6. Show the next-best action.
7. Generate a roadmap from indexed material.
8. Take the roadmap quiz.
9. Show the Current Affairs brief.
10. Take the Current Affairs quiz.
11. Show the retention recommendation.

Also confirm the sticky composer is visible only in Chat, Scroll to Latest appears after scrolling away from a streaming answer, and the principal pages remain usable at laptop and desktop widths.
