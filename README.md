# UPSC AI Mentor

UPSC AI Mentor is a local-first study platform combining grounded AI tutoring with learner preferences, revision evidence, Current Affairs, quizzes, and visual learning. It is designed as an explainable UPSC mentor rather than a generic chatbot.

## Core differentiators

- Local Ollama generation and embeddings; no paid API is required for the normal workflow.
- PDF-first grounded Chat with visible document and page citations.
- Consent-aware activity tracking limited to actions inside the platform.
- Transparent mastery, forgetting-risk, and next-best-action rules.
- Personalized Current Affairs reading with separate grounded quizzes and retention revision.
- Grounded Visual Roadmaps with strict validation and deterministic fallback when Qwen returns malformed JSON.
- Community is intentionally excluded from the MVP.

## Completed MVP

- Normal and SSE-streaming Chat across Learn, Revision, Prelims, Mains, and Interview modes.
- Persistent, isolated conversations with rename and delete.
- PDF upload through `pypdf`, Ollama `nomic-embed-text` indexing, Chroma retrieval, and My Library metadata.
- Learner profile preferences for language, depth, format, content type, and daily target.
- Evidence-based mastery, forgetting risk, mentor recommendations, progress, and revision views.
- Trusted-source video recommendations.
- Personalized Current Affairs with controlled sources, duplicate grouping, saved stories, daily briefs, and automatic collection.
- A separate Quizzes page for Current Affairs and roadmap recall.
- Six roadmap types with SVG output, grounded quizzes, and deterministic grounded fallback.
- Responsive premium React interface validated at desktop, laptop, tablet, and mobile widths.

## Architecture and stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite, Pydantic, Ollama HTTP APIs, ChromaDB, and SSE.
- Frontend: React 19, TypeScript, Vite, React Markdown, and Lucide icons.
- Generation: configurable Ollama chat model, commonly `qwen2.5:3b`.
- Embeddings: local Ollama `nomic-embed-text`; SentenceTransformers and PyTorch are not runtime dependencies.
- PDF parsing: pure-Python `pypdf`; PyMuPDF is not used.
- Persistence: local SQLite plus filesystem PDF metadata and a local Chroma collection.

Local databases, uploads, extracted text, Chroma vectors, logs, generated SVG files, caches, and secrets are excluded from Git.

## Prerequisites

- Windows 10 or 11
- Python compatible with the backend dependencies
- Node.js and npm
- Ollama installed and running
- PowerShell for the Windows commands and scheduler installer

## Ollama model setup

```powershell
ollama serve
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
ollama list
```

If a different chat model is installed, set `OLLAMA_MODEL` accordingly. Keep `OLLAMA_EMBEDDING_MODEL=nomic-embed-text` unless content is deliberately re-indexed into a new compatible collection.

## Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation is available at `http://127.0.0.1:8000/docs`.

## Frontend setup

```powershell
cd upsc-ai-test-frontend-flat
npm install
Copy-Item .env.example .env
npm run dev
```

Open the Vite URL, normally `http://127.0.0.1:5173`.

## Environment configuration

Copy `backend/.env.example` to `backend/.env` and replace only local placeholders. Never commit `.env`.

Important settings include:

- `DATABASE_URL` and `MEMORY_DB_PATH`
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL`
- `EMBEDDING_PROVIDER`, `OLLAMA_EMBEDDING_MODEL`, and `CHROMA_COLLECTION`
- trusted-web provider, cache, and grounding settings
- `INTERNAL_ADMIN_KEY`, which protects internal Current Affairs collection operations
- `CA_DAILY_MAX_RESULTS`, `CA_DAILY_LANGUAGE`, and `CA_DAILY_TIME`

Use a newly generated local admin key. Any key previously committed or shared must be rotated.

## PDF behavior and limitations

Text PDFs are parsed with `pypdf`, chunked, embedded through Ollama, and indexed into Chroma. Successful documents appear in My Library with page count, chunk count, provider, model, collection, and status. Legacy BGE documents are shown as inactive and must be re-indexed.

Image-only scans require OCR and are not supported. Encrypted PDFs require a usable password before upload. Very narrow questions may not meet the grounding threshold even when a related PDF is indexed; the assistant refuses to invent an answer in that case.

## Automatic Current Affairs collection

Current Affairs uses controlled official and approved analysis adapters, allowlist validation, duplicate grouping, and original grounded summaries. Full coaching articles and copied quiz questions are not stored.

To register the Windows Task Scheduler job at the default 7:00 AM local time:

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File .\scripts\install_current_affairs_task.ps1
```

The task definition contains no secrets. It reads `backend/.env` at runtime, uses an overlap lock, checks Ollama availability, and writes timestamped local logs. Adjust the installer or `CA_DAILY_TIME` before registration when another time is required.

Manual collection and re-indexing utilities are available under `backend/scripts/`.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\upsc-ai-test-frontend-flat
npx tsc -b --pretty false
npm run build
```

## Demo workflow

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_demo.py
$env:MEMORY_DB_PATH="$PWD\data\demo.sqlite3"
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal. Then demonstrate:

1. Mentor Dashboard and evidence-based next action.
2. Streaming AI Study Coach with preferences.
3. PDF upload, My Library metadata, and a cited grounded answer.
4. Mastery, revision risk, and Progress.
5. Personalized Current Affairs and the separate Quizzes page.
6. A grounded Visual Roadmap, SVG, and five-question roadmap quiz.
7. Profile preferences and privacy explanation.

## Known limitations

- Local Qwen generation can be slow, especially for detailed answers and schema repair.
- Strict answer formatting remains prompt-guided rather than guaranteed.
- Visual Roadmap animation is not implemented.
- OCR for image-only PDFs is not implemented.
- Live Current Affairs coverage depends on approved pages exposing accessible server-rendered text and valid dates.
- Optional roadmap-quiz discovery can return a handled 404 when a roadmap has no quiz.
- Mastery, forgetting risk, and recommendation priorities are transparent estimates, not medical, psychological, or scientifically precise diagnoses.

See `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, and `AGENTS.md` for current implementation details and product constraints.
