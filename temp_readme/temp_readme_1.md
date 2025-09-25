# Study Abroad Chatbot Backend Overview

- Date: 2025-09-23
- Time: 2025-09-23T17:54:23+05:00
- Summary: Deep overview of backend files, current request flows (start, message, upload-document), and concrete next steps (LLM extractor, dialog policy, Weaviate, richer document processing, startup hooks).

Here’s a clear, deep overview of each backend file, how they work together today, and what we’ll build next.

### backend/app/main.py
- What it is: FastAPI app bootstrap.
- Key parts:
  - Creates `FastAPI` app with title.
  - Adds CORS via `CORSMiddleware` using `ALLOWED_ORIGINS` from config.
  - Simple request logging middleware (currently pass-through).
  - Health endpoints:
    - GET `/health`: basic liveness with `env`.
    - GET `/ready`: placeholder readiness.
  - Includes API router under `/api`.
- Current role in flow:
  - Wires HTTP endpoints; enforces CORS; provides health checks.
- Future:
  - Add startup/shutdown hooks to initialize: Weaviate client, LLM chains (extractor/dialog), warm caches.
  - Optional rate limiting middleware.
  - Readiness check of dependencies (DB, Weaviate, Redis).

### backend/app/config.py
- What it is: Central configuration via `.env`.
- Provides:
  - DB: `POSTGRES_URL`.
  - LLM: `GEMINI_API_KEY`.
  - Vector DB: `WEAVIATE_URL`, `WEAVIATE_API_KEY`.
  - Queues: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
  - App: `ENV`, `DEBUG`, `ALLOWED_ORIGINS`.
- Current role:
  - Single source of truth for service URLs/keys used across modules.
- Future:
  - Typed settings (Pydantic `BaseSettings`), env-specific overrides, validation of required vars.

### backend/app/db/session.py
- What it is: SQLAlchemy base & session factory.
- Key parts:
  - `engine = create_engine(POSTGRES_URL, pool_pre_ping=True, pool_size=5, max_overflow=10, echo=True)`.
  - `SessionLocal` sessionmaker.
  - `Base = declarative_base()` for ORM models.
- Current role:
  - Synchronous DB access pattern for endpoints and background jobs.
- Future:
  - Optional async engine (`sqlalchemy[asyncpg]`) if needed.
  - Connection settings per environment.
  - Ensure Alembic migrations executed; add migration autogeneration scripts.

### backend/app/models/session.py
- What it is: `Session` ORM model (a chat session).
- Columns:
  - `id` UUID PK.
  - `created_at` (server timestamp).
  - `updated_at` (auto on update).
  - `profile` JSON (canonical intake profile).
  - `status` (`active|complete`).
  - `consented_at` (nullable).
- Current role:
  - Stores evolving user profile across conversation.
- Future:
  - Optional `version` and `profile_history` (JSONB) to track changes.
  - Constraints/validation (e.g., status enum).

### backend/app/models/message.py
- What it is: `Message` ORM model (chat messages).
- Columns:
  - `id` UUID PK.
  - `session_id` UUID FK to `sessions` (indexed).
  - `sender` (`user` or `bot`).
  - `text` (message body).
  - `metadata` JSON (e.g., `next_question_id`).
  - `created_at`, `updated_at`.
- Indexes:
  - Composite index (`session_id`, `created_at DESC`) for fast timeline fetch.
- Current role:
  - Persists conversational turns.
- Future:
  - Sender ENUM, content moderation flags, token counts, trace IDs.

### backend/app/models/document.py
- What it is: `Document` ORM model (uploaded files).
- Columns:
  - `id` UUID PK.
  - `session_id` UUID FK (indexed).
  - `s3_key` (local path for now).
  - `filename`, `doc_type`.
  - `extracted_fields` JSON (fields derived from OCR/text).
  - `uploaded_at`, `updated_at`.
- Indexes:
  - Composite index (`session_id`, `uploaded_at DESC`).
- Current role:
  - Tracks uploads and extraction outputs per session.
- Future:
  - Storage abstraction (S3/GCS/Azure); checksum; page counts; embedding status.

### backend/app/api/endpoints.py
- What it is: HTTP API routes.
- Dependencies:
  - `get_db()` yields `SessionLocal` sessions.
- Routes:
  - POST `/api/start`
    - Input: `name`, `phone`, `email`.
    - Creates a `Session` with initial profile scaffold.
    - Returns `session_id` and a greeting from the bot.
  - POST `/api/message`
    - Input: `session_id`, `text`.
    - Flow:
      1) Validates session exists.
      2) Saves user `Message`.
      3) Calls `ExtractorChain.extract(text, profile)` to get `extracted_fields` (stubbed).
      4) Merges into profile via `merge_profile`.
      5) Saves updated session.
      6) Calls `DialogChain.next_question(profile)` to compute `bot_message` and `next_question_id` (stubbed).
      7) Saves bot `Message` with metadata.
      8) Returns `bot_message`, updated `profile`, and `next_question_id`.
  - POST `/api/upload-document`
    - Multipart upload: `session_id`, `file`.
    - Saves file to `/tmp/uploads/{session_id}_{filename}`.
    - Creates `Document` row.
    - Queues background task `process_document(session_id, document_id, path, content_type)`.
    - Returns `{status: queued, document_id}`.
- Current role:
  - Public API surface for chat and document ingestion.
- Future:
  - Request/response Pydantic models for upload response.
  - Auth (if needed), rate limits, pagination for history endpoints (e.g., GET messages).

### backend/app/services/extractor.py
- What it is: Extractor chain stub.
- API: `ExtractorChain.extract(text, profile) -> (extracted_fields, updated_profile)`
- Current behavior:
  - Returns empty `extracted_fields` and echoes `profile`.
- Future:
  - Implement LangChain with Gemini:
    - Strict JSON prompt for: `academic_history`, `english_tests`, `preferred_countries`, `financial`, `career_goals`, etc.
    - Schema validation and coercion.
    - Relative date resolution (“this year”).
    - Multi-answer accumulation (IELTS attempts, multiple preferences).

### backend/app/services/dialog.py
- What it is: Dialog policy stub.
- API: `DialogChain.next_question(profile) -> (bot_message, next_question_id|None)`
- Current behavior:
  - If `academic_history` empty → asks about it; else closes politely.
- Future:
  - LLM-driven dialog with tone guidelines.
  - Next-question selection based on missing fields and priority.
  - Support quick-reply hints for frontend/WhatsApp.

### backend/app/services/document_processor.py
- What it is: Background document processing flow.
- Steps:
  - Read saved file from disk.
  - Naive text extraction (binary decode fallback placeholder).
  - Call `ExtractorChain.extract` on doc text.
  - Merge into session `profile`.
  - Update `Document.extracted_fields`.
- Current role:
  - Demonstrates the async processing loop after uploads.
- Future:
  - PDF parsing via `pdfplumber`; image OCR via `pytesseract`.
  - Chunking + embeddings; push to Weaviate.
  - Error logging, retries, telemetry.

### backend/app/services/weaviate_client.py
- Current: empty (to be implemented).
- Future:
  - Initialize client using `WEAVIATE_URL`, `WEAVIATE_API_KEY`.
  - Methods:
    - `add_embedding(text, metadata)`
    - `semantic_search(query, top_k)`
  - Optionally, auto-create schemas for messages/documents.

### backend/app/utils/merge_utils.py
- What it is: Profile merging utility.
- Behavior:
  - Shallow update for dicts/primitives.
  - List fields: extend with unique values (de-duplicate).
  - Set `profile.last_updated = now (ISO)`.
- Current role:
  - Canonical way to evolve `Session.profile`.
- Future:
  - Field-level strategies (latest-wins vs confidence scores).
  - Value provenance/history tracking.

### backend/app/utils/validators.py
- Current: empty.
- Future:
  - Regex and/or Pydantic-based validators:
    - phone, email, numeric values, years.
  - JSON schema for extractor output validation.

### backend/app/api/whatsapp.py (not opened yet)
- If present to integrate WhatsApp later:
  - Webhook handling, signature validation, mapping inbound/outbound to `/message`.

### backend/app/api/__init__.py and others
- Module initializers; no runtime logic.

---

### Current end-to-end workflow

- POST `/api/start`
  - Creates a `Session` with a basic profile and returns a greeting plus `session_id`.

- POST `/api/message`
  - Saves the user message.
  - Extracts structured data (stubbed) and merges into profile.
  - Determines next bot question (stubbed).
  - Saves bot message and returns bot reply + updated profile + next question id.

- POST `/api/upload-document`
  - Stores file locally, creates `Document`.
  - Background task reads file, extracts text (placeholder), runs extractor, merges profile, stores extracted fields.

- Health checks at `/health` and `/ready`.
- CORS enabled for cross-origin frontends.

---

### Near-term implementation plan

- LLM Extractor
  - Build Gemini-based LangChain chain with strict JSON schema and validators.
  - Handle multi-value fields + relative dates.

- Dialog policy
  - LLM prompt for persona/tone.
  - Deterministic next-question selection backed by required field coverage.

- Vector DB
  - Implement Weaviate client, add embeddings on messages/documents, semantic search.

- Uploads
  - Replace naive extraction with `pdfplumber`/`pytesseract`.
  - Optional: storage abstraction (S3), background queue (Celery/Redis).

- App bootstrap
  - Startup hooks to init clients, warm chains.
  - Readiness to check downstream health.

