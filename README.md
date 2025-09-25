# Study Abroad Chatbot (Monorepo)

This repository contains both the backend (FastAPI) and frontend (React + Vite + Tailwind) for the Study Abroad Intake chatbot.

## Structure
- `backend/` — FastAPI, SQLAlchemy, LangChain (Gemini)
- `frontend/` — React (Vite), Tailwind UI
- `scripts/` — optional helper scripts (dev/build/deploy)

## Quick start
### Backend
1. Create and populate `backend/.env` (database, Gemini key)
2. Run:
   ```bash
   /home/linux/Projects/study_abroad_chatbot/venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
   ```

### Frontend
1. From `frontend/`:
   ```bash
   npm install
   npm run dev
   ```

Open `http://localhost:5173` and ensure `VITE_API_BASE` points to the backend.

