# UPSC AI Mentor Agent

## Product purpose

This is not a generic chatbot. It must behave like a physical mentor while the learner uses the platform. It should observe consented activity inside the platform, understand what the learner studies, identify strengths and weaknesses, estimate forgetting risk, adapt language and content depth, and recommend the next best action.

## Current stack

- Backend: FastAPI, Python, SQLite, SQLAlchemy, Ollama, Qwen local model, ChromaDB, Ollama `nomic-embed-text`, `pypdf`, RAG, and SSE streaming.
- Frontend: React, TypeScript, and the Vite test frontend.

## Current endpoints

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
- `DELETE /activity/events/{event_id}`

Supported modes: `learn`, `revision`, `prelims`, `mains`, and `interview`.

## Permanent rules

- Community is not part of the active MVP. Do not restore its routes, UI, activity creation types, seed data, or tests; legacy SQLite tables and historical activity rows remain readable until a controlled migration.
- Do not create a generic ChatGPT clone.
- Preserve working APIs unless a requirement explicitly changes them.
- Keep normal and streaming chat compatible.
- Do not duplicate RAG, prompt, memory, or streaming logic.
- Use local models first and avoid unnecessary paid APIs.
- Prefer transparent rule-based mentor logic before heavy machine learning.
- Track only consented activity inside the study platform. Do not monitor unrelated device or browser activity.
- Do not make medical or psychological diagnoses.
- Manual user preferences always override automatic inference.
- Video recommendations must use trusted sources and links only.
- Every recommendation must include a human-readable reason.
- Implement every feature as a small, testable milestone.

## After every feature

1. Confirm the feature is attached to the active project flow.
2. Run relevant unit and integration tests.
3. Confirm existing functionality is not broken.
4. Update `docs/PROJECT_STATE.md`.
5. Update `docs/DECISIONS.md` when an architectural decision is made.
6. Record modified files and commands executed.
7. Do not start the next feature automatically.

## Current status and priority

The UPSC AI Mentor MVP is implemented and tested across Chat, PDF/RAG, My Library, learner profile, mastery and forgetting risk, mentor recommendations, trusted videos, personalized Current Affairs, separate quizzes, Visual Roadmaps, activity, progress, and revision. Community is removed. No next feature is selected.

The mode-aware format-repair system is postponed because it is not reliable. Do not mark strict formatting complete; revisit it after the mentor foundation is stable.

Historical delivery order (completed; not a future priority list):

1. Explicit conversation IDs — completed
2. Conversation memory synchronization — completed
3. Activity Event Store — completed
4. Subject/topic/time tracking — completed
5. Learner Profile
6. Mastery and forgetting-risk engine
7. Next-Best-Action engine
8. Actionable Mentor Intelligence dashboard
9. Language and content-depth adaptation
10. Video recommendations

## Testing and reporting

Run targeted tests first, then the wider suites:

- Backend: `python -m pytest -q`
- Frontend: `npm run build`

At the end of a task, report the summary, files changed, commands run, tests passed, remaining limitations, and exact next starting point.
CODEX CREDIT-SAVING RULES

- Read AGENTS.md and docs/PROJECT_STATE.md before working.
- Work only on the current milestone.
- Do not scan the entire repository unless necessary.
- Inspect only relevant files first.
- Run targeted tests before the full test suite.
- Do not rewrite working files unnecessarily.
- Do not regenerate reports or documentation unless requested.
- Do not start parallel agents for dependent tasks.
- Use parallel agents only for isolated work in separate worktrees.
- Do not repeat completed investigation.
- Stop immediately after the requested task is implemented and tested.
- Report blockers instead of repeatedly attempting the same failing command.
- Reuse existing modules, helpers, schemas, and tests.
- Prefer small patches over full-file replacements.
- Ask for clarification before making a large architectural change.
- Do not start the next milestone automatically.
FRONTEND INTEGRATION RULES

- Every user-facing backend feature must be connected to the frontend.
- Do not mark a feature complete when only the backend works.
- Preserve the existing clean desktop design direction.
- Reuse shared components and existing styles.
- Avoid unnecessary redesigns.
- Add loading, error, empty and success states.
- Keep layouts responsive.
- Show useful actions, not only raw data.
- Connect components to real APIs instead of permanent mock data.
- Run the frontend production build after relevant UI changes.
- Keep advanced visual polish secondary to working functionality.
