"""Database engine, session factory and declarative base."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Streamlit pages read related objects (e.g. block.hostel.name) after the
# session has closed, so load relationships eagerly by default.
import sqlalchemy.orm as _orm

_orig_relationship = _orm.relationship


def _eager_relationship(*args, **kwargs):
    kwargs.setdefault("lazy", "selectin")
    return _orig_relationship(*args, **kwargs)


_orm.relationship = _eager_relationship
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

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def _load_all_relationships(session: Session, limit: int = 20000) -> None:
    """Load every object reachable from the session's objects, so they can
    still be read (including related objects) after the session is closed."""
    from sqlalchemy import inspect as sa_inspect

    seen: set[int] = set()
    queue = list(session.identity_map.values())
    while queue and len(seen) < limit:
        obj = queue.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        try:
            for rel in sa_inspect(obj).mapper.relationships:
                value = getattr(obj, rel.key)
                if value is None:
                    continue
                queue.extend(value if rel.uselist else [value])
        except Exception:  # noqa: BLE001
            continue


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context-managed database session with commit/rollback handling."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
        _load_all_relationships(session)
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
