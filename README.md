# Study Abroad Chatbot (Mono‑repo)

LLM‑powered intake assistant for students planning to study abroad.

- Backend: FastAPI + SQLAlchemy + Alembic + LangChain (Gemini)
- Frontend: React (Vite) + Tailwind CSS

## Live Dev Endpoints
- Backend docs: `http://127.0.0.1:8000/docs`
- Frontend dev: `http://127.0.0.1:5173`

## Repo Layout
```
backend/   FastAPI service (REST API, DB models, services)
frontend/  React UI (chat widget, Start Card, settings)
```

## Quick Start

### Backend
Requirements: Python 3.10+, PostgreSQL running locally

1) Create venv & install deps
```bash
cd backend
python3 -m venv ../venv
../venv/bin/pip install -r requirements.txt
```

2) Configure env (`backend/.env`)
```env
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_DB=chatbot
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

GEMINI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_KEY

REDIS_URL=redis://localhost:6379/0
LOG_LLM_DEBUG=true
```

3) Run DB migrations
```bash
../venv/bin/alembic upgrade head
```

4) Start backend
```bash
../venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

### Frontend
Requirements: Node 20+
```bash
cd frontend
npm install
npm run dev
```
If backend is not `http://127.0.0.1:8000`, set `VITE_API_BASE` in `frontend/.env`.

## Key Features
- LLM‑first extraction and dialog policy with rule‑based fallbacks
- Normalized Postgres schema (profiles, academic history, english tests, preferences)
- Alembic migrations; `tests/show_db.py` to inspect data by session
- Modern chat UI with Start Card, quick replies, scroll‑to‑bottom button
- Detailed LLM logging toggle via `LOG_LLM_DEBUG`

## Troubleshooting
- Verify Gemini key at runtime: `GET /api/debug/llm-key`
- Kill stale dev servers if ports are busy:
```bash
pkill -f "uvicorn app.main:app" || true
```

## Deployment Notes
- Keep secrets out of the repo; use environment variables in prod
- Serve frontend as static files (Vite build) and FastAPI behind HTTPS

## License
MIT
