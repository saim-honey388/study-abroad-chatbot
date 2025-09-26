from alembic import context
from sqlalchemy import engine_from_config, pool
import os
import sys

# Make app importable (so Alembic can see Base and models)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db.session import Base  # noqa: E402
from app.models.session import Session as SessionModel  # noqa
from app.models.message import Message  # noqa
from app.models.document import Document  # noqa
from app.models.student_profile import StudentProfile  # noqa
from app.models.academic_history import AcademicHistory  # noqa
from app.models.english_test import EnglishTest  # noqa
from app.models.study_preference import StudyPreference  # noqa


config = context.config

# Deployment-friendly: read from env at runtime
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
