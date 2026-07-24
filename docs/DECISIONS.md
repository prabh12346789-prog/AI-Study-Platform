# Architectural Decisions

## Reversible Report Demo Mode

- Date: 2026-07-24
- Decision: Add a local-only `REPORT_DEMO_MODE=true` environment toggle that serves realistic demo data dynamically for the Dashboard/Progress, Current Affairs, and Tests screens without modifying the real SQL tables, Chroma vectors, or user profile records. Implement a `seed_report_demo_data.py` script to toggle this setting in `.env`.
- Reason: Simplifies generating reports and demo screenshots by instantly populating all areas with realistic mock data while avoiding database pollution or risk to real user learning data.
- Status: Accepted

## Removal of UPSC Notes Feature

## Independent premium frontend

- Date: 2026-07-16
- Decision: Build the premium interface as a second frontend in `upsc-ai-mentor-premium`, sharing only the existing FastAPI contracts and leaving `upsc-ai-test-frontend-flat` unchanged.
- Reason: Controlled phases need a clean feature-oriented foundation without risking regressions in the completed MVP interface.
- Trade-off: Until later phases connect each feature, non-foundation routes show explicit placeholders rather than mock data.
- Status: Accepted; Phase 1 complete

## Local-first generation

- Date: Existing project decision; recorded 2026-07-14
- Decision: Use a local-first Ollama architecture with Qwen as the primary model.
- Reason: Preserve privacy, reduce paid API dependency, and support local development.
- Trade-off: Local hardware performance and model quality can vary.
- Status: Accepted

## Retrieval architecture

- Date: Existing project decision; recorded 2026-07-14
- Decision: Use ChromaDB and RAG for study-document context. The original Sentence Transformers implementation was superseded by the accepted Ollama HTTP embedding decision below.
- Reason: Ground answers in learner-provided material using local components.
- Trade-off: Index lifecycle and retrieval quality require ongoing validation.
- Status: Accepted

## Streaming transport

- Date: Existing project decision; recorded 2026-07-14
- Decision: Stream chat through Server-Sent Events (SSE).
- Reason: SSE provides a simple one-way browser streaming contract.
- Trade-off: It is less suitable than WebSockets for bidirectional real-time features.
- Status: Accepted

## Generation modes

- Date: Existing project decision; recorded 2026-07-14
- Decision: Use mode-based generation profiles for learn, revision, prelims, mains, and interview.
- Reason: UPSC study tasks require different depth and answer styles.
- Trade-off: More profiles increase prompt and regression-test maintenance.
- Status: Accepted

## Product positioning

- Date: Existing project decision; recorded 2026-07-14
- Decision: Position the product as an AI Mentor rather than a generic chatbot.
- Reason: The core value is longitudinal, actionable learning guidance.
- Trade-off: This requires learner-state infrastructure beyond chat.
- Status: Accepted

## Activity observation

- Date: Existing project decision; recorded 2026-07-14
- Decision: Observe only consented activity inside the study platform.
- Reason: Personalization must respect privacy and clear user boundaries.
- Trade-off: Signals outside the platform are intentionally unavailable.
- Status: Accepted

## Personalization MVP

- Date: Existing project decision; recorded 2026-07-14
- Decision: Begin with transparent rule-based personalization.
- Reason: Explainable rules are faster to validate and safer than premature heavy ML.
- Trade-off: Early personalization may be less nuanced.
- Status: Accepted

## Mentor analytics

- Date: Existing project decision; recorded 2026-07-14
- Decision: Build actionable analytics rather than a marks-only dashboard.
- Reason: Learners need reasons and next actions, not only scores.
- Trade-off: Recommendations require more context and careful explanation.
- Status: Accepted

## Community removed from the MVP

- Date: 2026-07-15
- Decision: Community removed from the MVP.
- Reason: The project is focusing on the core AI mentor, personalization, mastery, Current Affairs, RAG, visual learning, and exam preparation experience.
- Trade-off: Existing local Community tables remain unused until a future controlled migration removes them.
- Status: Accepted

## Premium frontend application shell

- Date: 2026-07-15
- Decision: Compose existing frontend features inside one desktop-first application shell with a fixed navigation sidebar, sticky local-navigation header, and responsive drawer.
- Reason: A stable shell gives the AI mentor, Current Affairs, revision, progress, profile, and visual-learning workflows one serious UPSC-focused identity without changing backend contracts.
- Trade-off: Library and quiz overview pages can only expose actions supported by existing APIs; no mock document catalog or aggregate quiz backend was introduced.
- Status: Accepted

## Formatting repair

- Date: Existing project decision; recorded 2026-07-14
- Decision: Postpone strict mode-aware formatting repair.
- Reason: It is not currently reliable and the mentor foundation has higher priority.
- Trade-off: Output structure may remain inconsistent in the interim.
- Status: Postponed

## Activity event persistence

- Date: 2026-07-14
- Decision: Persist only explicitly consented, platform-scoped activity as immutable event facts, with listing and user-data deletion APIs.
- Reason: A small event store provides an auditable foundation for later mentor analytics without prematurely adding inference or aggregation.
- Trade-off: Clients must supply consent and a stable event taxonomy; subject/topic/time summaries are intentionally deferred.
- Status: Accepted

## Roadmap-derived recall quizzes

- Date: 2026-07-15
- Decision: Generate and score recall quizzes deterministically from validated persisted roadmap JSON, with no additional LLM call, and treat one persisted quiz attempt as the submission idempotency boundary.
- Reason: Quiz facts and distractors must remain auditable against the roadmap while repeated submission must never duplicate mastery evidence.
- Trade-off: Question variety is constrained by available roadmap nodes; short or sparse roadmaps are rejected instead of being supplemented with invented content.
- Status: Accepted

## Mode and presentation separation

- Date: 2026-07-15
- Decision: Treat UPSC mode as purpose/exam orientation and the resolved answer format as the independent presentation contract, enforced through one shared normal/streaming prompt policy with no post-generation repair.
- Reason: Fixed mode templates overrode learner-selected presentation and sometimes displaced the exact current question with a generic topic.
- Trade-off: Local-model adherence remains probabilistic; strict formatting is still postponed and factual reliability depends on relevant grounding.
- Status: Accepted

## Grounding and trusted web fallback

- Date: 2026-07-15
- Decision: Apply one shared heuristic grounding decision to PDF-first chat and stricter visual-roadmap retrieval, and permit fallback only to manually allowlisted web publishers with explicit provenance and freshness-aware caching.
- Reason: Nonempty or highly ranked context is not necessarily relevant or trustworthy, while ungrounded local generation produced factual errors.
- Trade-off: The conservative allowlist and lightweight extraction reduce coverage, and confidence is an explainable threshold signal rather than a scientific probability.
- Status: Accepted

## Current Affairs Phase 1

- Date: 2026-07-15
- Decision: Build current affairs over the existing trusted web policy, persist grounded UPSC summaries and deterministic daily briefs, and index accepted summaries in the existing RAG collection with explicit current-affairs provenance.
- Reason: Learners need reusable, source-transparent daily material that chat can retrieve without duplicating search or allowing reading activity to inflate mastery.
- Trade-off: Collection is conservative and internal/manual in Phase 1; extraction limits coverage, and scheduling, notifications, quizzes, payments, and institutional analytics remain out of scope.
- Status: Accepted

## Current Affairs live search provider

- Date: 2026-07-15
- Decision: Configure Bing RSS as the credential-free live discovery provider, reject legacy placeholder provider names, and keep direct URL validation independent of provider credentials while enforcing the same trusted-domain and extraction policy.
- Reason: The previous `local_first` label concealed a DuckDuckGo HTTP 202 challenge page as a valid zero-result collection.
- Trade-off: Public search ranking can still return irrelevant results; diagnostics expose those domain rejections and explicit query overrides allow focused retries.
- Status: Accepted

## Current Affairs article acceptance boundary

- Date: 2026-07-15
- Decision: Apply deterministic article-page quality checks before Ollama and retain a separate post-generation grounding check for core facts and every numeric claim.
- Reason: Trusted home and index pages are valid domains but poor current-affairs evidence, while optional summary fields should not invalidate a grounded article.
- Trade-off: Conservative URL/body heuristics may reject unusual official layouts; direct trusted URLs expose the exact quality reason for targeted diagnosis.
- Status: Accepted

## Current Affairs quiz and retention

- Date: 2026-07-15
- Decision: Generate quizzes deterministically from accepted persisted article fields, use one user/quiz attempt as the idempotency boundary, and maintain a separate bounded article-retention estimate driven only by quiz answers and explicit revision.
- Reason: Current Affairs recall needs auditable source citations and must never let reading, saving, popularity, or repeated submission inflate retention or mastery.
- Trade-off: Question variety is limited by stored facts, true/false statements remain grounded true statements, and insufficient distinct content returns an error rather than inventing distractors.
- Status: Accepted
# Ollama HTTP embeddings replace SentenceTransformers

- Decision: Generate normalized embeddings through the local Ollama `/api/embed` endpoint using configurable `nomic-embed-text` rather than importing SentenceTransformers/PyTorch.
- Reason: Windows Application Control blocks PyTorch's native `torch/lib/shm.dll`, while the Ollama service keeps native model execution outside the FastAPI process.
- Compatibility: Use the separate `documents_ollama_nomic_embed_text` Chroma collection. Never mix legacy BGE vectors with Ollama vectors; existing content must be re-indexed.
# Deterministic grounded fallback for malformed roadmap JSON

- Decision: Attempt direct tolerant JSON parsing and strict schema validation, make at most one schema-guided repair call, then build a deterministic roadmap only from retrieved chunk sentences when model output remains invalid.
- Reason: Local Qwen can truncate or corrupt structured JSON even with a JSON-only prompt. Repeated generation is slow and unreliable, while grounded sentence extraction can safely preserve facts and citations.
- Safety boundary: The fallback never runs without sufficient grounding, never invents facts or sources, validates through the same `RoadmapStructure`, and records `generation_method=deterministic_fallback` in internal metadata and activity.
# Controlled, grouped, personalized Current Affairs

- Decision: Keep one explicit source-adapter catalog with primary, daily-analysis, Mains/editorial, and monthly-revision tiers; all discovered URLs still pass the shared allowlist, redirect, article-quality, and grounded-summary gates.
- Issue grouping: Canonical URL and content hash are exact duplicate keys. Same-date records are grouped when their normalized titles are similar or their classified topics match, with the highest-tier source leading and supporting citations retained.
- Personalization: Use transparent additive ranking signals from importance, source confidence, freshness, activity/mode, profile preferences, mastery/risk, Current Affairs retention, and saved state. Reading and saving remain non-mastery activity.
- Scheduling: Windows Task Scheduler calls a secret-free local Python runner daily at 7:00 AM. The runner reads `.env` at runtime, rejects overlapping execution, checks Ollama/model availability with a timeout, collects idempotently, re-indexes accepted rows, and writes timestamped logs.
# Atomic, official-first Current Affairs ingestion

- Discovery order: Public RSS/Atom source adapters first, then approved public source listings, then controlled search queries, with manually supplied allowlisted article URLs available for diagnosis. Feed/listing metadata influences ranking but never bypasses URL, redirect, extraction, quality, or grounding checks.
- Trust boundary: Current Affairs accepts only domains in its explicit source-adapter catalog even when another domain is permitted for general Chat grounding. Quiz, test, answer-writing, archive, index, tag, search, login, and channel pages are rejected before extraction.
- Atomicity: An active article is indexed before its database commit. Summary/grounding/indexing failures return structured diagnostics but create no article record. Legacy misclassified active records are archived and their Current Affairs vectors removed.
- Diagnostics: Every collection result carries zero-inclusive rejection counts for URL, domain, redirect, page type, duplicates, HTTP/challenge, extraction quality, metadata, summarization, grounding, and indexing stages without storing page bodies or secrets.
