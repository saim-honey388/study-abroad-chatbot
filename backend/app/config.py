import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

# Load .env from project root (or nearest) reliably
# 1) Try nearest .env from CWD upward
_found = find_dotenv()
if _found:
    load_dotenv(_found)

# 2) Also try project root relative to this file: ../../.env
_project_root_env = Path(__file__).resolve().parents[2] / ".env"
if _project_root_env.exists():
    load_dotenv(_project_root_env, override=False)

# 3) Optional local overrides
_local_env = Path(__file__).resolve().parents[2] / ".env.local"
if _local_env.exists():
    load_dotenv(_local_env, override=True)

# 4) Also support .env placed in backend/ (same dir as this module's parent)
_backend_env = Path(__file__).resolve().parents[1] / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env, override=False)

# Database
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
if POSTGRES_USER and POSTGRES_PASSWORD and POSTGRES_DB and POSTGRES_HOST and POSTGRES_PORT:
    POSTGRES_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
else:
    POSTGRES_URL = None

# LLM / Providers
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# Weaviate / Vector DB
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

# Messaging / Queues
REDIS_URL = os.getenv("REDIS_URL")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# App config
ENV = os.getenv("ENV", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
LOG_LLM_DEBUG = os.getenv("LOG_LLM_DEBUG", "false").lower() == "true"


