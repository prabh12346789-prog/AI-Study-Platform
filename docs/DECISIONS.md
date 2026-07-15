# Architectural Decisions

## Local-first generation

- Date: Existing project decision; recorded 2026-07-14
- Decision: Use a local-first Ollama architecture with Qwen as the primary model.
- Reason: Preserve privacy, reduce paid API dependency, and support local development.
- Trade-off: Local hardware performance and model quality can vary.
- Status: Accepted

## Retrieval architecture

- Date: Existing project decision; recorded 2026-07-14
- Decision: Use ChromaDB, Sentence Transformers, and RAG for study-document context.
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

## Community sequencing

- Date: Existing project decision; recorded 2026-07-14
- Decision: Implement Community only after Mentor Intelligence.
- Reason: Community popularity must not distort mastery or mentor guidance.
- Trade-off: Social features arrive later in the roadmap.
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
