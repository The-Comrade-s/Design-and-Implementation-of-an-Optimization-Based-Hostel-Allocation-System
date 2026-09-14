"""Database engine, session factory and declarative base."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context-managed database session with commit/rollback handling."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> bool:
    """Verify database connectivity. Used by health checks and startup."""
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Database connection failed: %s", exc)
        return False


def init_db() -> None:
    """Create all tables. Used for local/dev setup and by scripts.

    In production, prefer Alembic migrations (see /migrations) instead of
    relying on automatic table creation.
    """
    import app.models  # noqa: F401  (ensures all models are registered)

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ensured via metadata.create_all")
