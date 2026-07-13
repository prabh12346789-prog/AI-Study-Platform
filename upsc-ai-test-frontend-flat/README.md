# UPSC AI Study Platform — Test Frontend

A small React frontend built specifically for the current FastAPI backend contract.

## Supported backend endpoints

- `GET /` — connection check
- `POST /chat/stream` — streaming chat
- `POST /chat/` — non-streaming chat test
- `POST /pdf/upload` — PDF upload using multipart field `file`

The chat payload is exactly:

```json
{
  "question": "Explain Fundamental Rights",
  "mode": "learn"
}
```

Allowed modes:

- `learn`
- `revision`
- `prelims`
- `mains`
- `interview`

The frontend does **not** send `conversationId`, `messages`, `provider`, `model`, or `systemPrompt` because the current backend request schema does not accept those fields.

## Run on Windows PowerShell

```powershell
cd upsc-ai-test-frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Backend

Start your backend from the backend folder, for example:

```powershell
uvicorn src.main:app --reload
```

The default frontend backend URL is:

```text
http://127.0.0.1:8000
```

Change it in `.env` when needed:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## CORS requirement

FastAPI must allow the frontend origin:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Notes

- Conversation history is kept only in React state for this testing build.
- It does not yet synchronize frontend chats with backend `conversation_id` memory.
- The SSE parser ignores `END`, `[DONE]`, and `event: done` markers.
- The assistant message is updated directly while streaming, so it is not rendered twice.
