from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import POSTGRES_URL
import os
if not POSTGRES_URL:
    raise RuntimeError(
        "Database configuration missing. Ensure POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT are set in .env"
    )

# Configure SQLAlchemy engine with safer defaults
# Control SQL echo via env var (default off)
_SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

engine = create_engine(
    POSTGRES_URL,
    echo=_SQL_ECHO,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
