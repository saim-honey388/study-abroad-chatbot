# Study Abroad Chatbot

Craft your dream study‑abroad journey with an elegant, LLM‑powered intake assistant. Built as a modern mono‑repo with a production‑ready FastAPI backend and a polished React (Vite + Tailwind) frontend.

<!-- Primary stack (hero row) -->
<div align="center" style="display:flex;gap:18px;align-items:center;justify-content:center;flex-wrap:wrap;margin:8px 0 2px 0;">
  <a href="https://www.langchain.com/" title="LangChain"><img alt="LangChain" height="54" src="https://avatars.githubusercontent.com/u/126733545?s=200&v=4" style="border-radius:12px;box-shadow:0 6px 20px rgba(46,125,50,.25);"/></a>
  <a href="https://www.python.org/" title="Python"><img alt="Python" height="54" src="https://cdn.simpleicons.org/python/3776AB/ffffff"/></a>
  <a href="https://react.dev/" title="React"><img alt="React" height="54" src="https://cdn.simpleicons.org/react/61DAFB/20232A"/></a>
  <a href="https://www.postgresql.org/" title="PostgreSQL"><img alt="PostgreSQL" height="54" src="https://cdn.simpleicons.org/postgresql/336791/ffffff"/></a>
</div>

<div align="center" style="margin-top:6px;">
  <img src="https://img.shields.io/badge/LangChain-powered-2E7D32?style=for-the-badge&logo=chainlink&logoColor=white" alt="LangChain powered"/>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/React-18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React"/>
  <img src="https://img.shields.io/badge/PostgreSQL-14%2B-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
</div>

<!-- Secondary tools -->
<div align="center" style="margin-top:8px;">
  <img src="https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite"/>
  <img src="https://img.shields.io/badge/Tailwind-4-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind"/>
  <img src="https://img.shields.io/badge/made%20with-❤️-ff477e?style=for-the-badge" alt="made with love"/>
</div>

## Why this project?
- LLM‑first data extraction: parse multi‑field user messages (country, budget, degree, major, GPA, year) in one go.
- Natural, context‑aware dialog: don’t re‑ask completed fields; confirm only where needed.
- Clean, normalized schema: student profiles, academic history (with major), English tests, preferences; Alembic migrations included.
- Elegant UX: Start Card, responsive chat UI, quick replies, autoscroll/scroll‑to‑bottom, compact settings.
- Thin backend: trusts the LLM output (types/constraints enforced), with rich debug logs to iterate fast.

## Screenshots
![Start Card](frontend/public/screenshots/start-card.png)
![Chat UI](frontend/public/screenshots/chat-ui.png)

## Architecture
```
[ React (Vite + Tailwind) ]  →  [ FastAPI + LangChain (Gemini) ]  →  [ PostgreSQL ]
         UI/UX                        LLM policy + extract             normalized schema
```

Key Services
- `ExtractorChain`: Gemini‑driven JSON extraction and normalization (synonyms, levels, dates, budget ranges)
- `DialogChain`: Gemini‑driven replies + next question policy with rule fallback
- Alembic migrations; `tests/show_db.py` prints all data per session

## Live Dev Endpoints
- Backend docs: `http://127.0.0.1:8000/docs`
- Frontend dev: `http://127.0.0.1:5173`

## Repository Layout
```
backend/   FastAPI service (REST API, DB models, services)
frontend/  React UI (chat widget, Start Card, settings)
```

## Quick Start

### Backend
Requirements: Python 3.10+, PostgreSQL

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

# Choose one provider (OpenAI preferred)
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=YOUR_OPENAI_KEY

# or Gemini
GEMINI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_KEY

REDIS_URL=redis://localhost:6379/0
LOG_LLM_DEBUG=true
```

3) Run migrations
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
If backend isn’t `http://127.0.0.1:8000`, set `VITE_API_BASE` in `frontend/.env`.

## API Overview
- `GET /health` – health check
- `POST /api/start` – start a session (name, email, phone)
- `POST /api/message` – send/receive chat messages; persists extracted fields
- `POST /api/upload-document` – upload files (e.g., transcripts)
- `GET /api/debug/llm-key` – debug the currently loaded Gemini key suffix (when DEBUG)

## CLI Utilities
Inspect your database by session:
```bash
PYTHONPATH=backend ../venv/bin/python backend/tests/show_db.py
```

## Roadmap
- Program recommendations based on preferences + country policies
- Document parsing (OCR) and auto‑field extraction
- Multi‑tenant admin dashboard
- Docker + CI workflows

## Contributing
PRs welcome! Please open an issue to discuss significant changes first.

## License
MIT
