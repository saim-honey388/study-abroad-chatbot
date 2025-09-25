# Study Abroad Chatbot (Monorepo)

Fast, modern intake assistant for students planning to study abroad.

- Backend: FastAPI + SQLAlchemy + LangChain (Gemini)
- Frontend: React (Vite) + Tailwind CSS

## Demo
- Backend docs: `http://127.0.0.1:8000/docs`
- Frontend dev: `http://127.0.0.1:5173`

## Repository Layout
```
backend/   # FastAPI service
frontend/  # React UI (Vite + Tailwind)
scripts/   # Optional CI/deploy helpers
```

## Quick Start

### 1) Backend
Requirements: Python 3.10+, PostgreSQL running locally

1. Create venv and install deps:
   ```bash
   cd backend
   python -m venv ../venv
   ../venv/bin/pip install -r requirements.txt || true  # if requirements present
   ```

2. Configure env: create `backend/.env`:
   ```env
   POSTGRES_USER=myuser
   POSTGRES_PASSWORD=mypassword
   POSTGRES_DB=chatbot
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432

   GEMINI_MODEL=gemini-2.5-pro
   GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_KEY

   REDIS_URL=redis://localhost:6379/0
   ```

3. Run backend:
   ```bash
   ../venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
   ```

### 2) Frontend
Requirements: Node 20+

```bash
cd frontend
npm install
npm run dev
```
Set `VITE_API_BASE` in `frontend/.env` if backend is not `http://127.0.0.1:8000`.

## Features
- Conversational intake with LLM-first extractor & dialog (Gemini)
- Rule-based fallback + retries
- Sessions, messages, documents persisted in Postgres
- File upload with background processing
- Quick replies, modern UI, responsive layout
- Environment-driven configuration

## Development Notes
- Mono-repo simplifies issue tracking and CI.
- Only `backend/.env` holds server secrets. `frontend/.env` should contain only `VITE_*` vars.
- To avoid port conflicts, kill stale uvicorn processes:
  ```bash
  pkill -f "uvicorn app.main:app" || true
  ```

## Deployment
- Recommended: containerize backend & frontend separately; serve frontend as static assets via CDN or reverse proxy and expose backend behind HTTPS.
- Ensure `GEMINI_API_KEY` and DB credentials are set as secrets in your deployment environment.

## License
MIT
