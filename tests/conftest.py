"""Shared pytest fixtures: isolated in-memory SQLite DB per test."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
import app.models  # noqa: F401


@pytest.fixture()
def session():
    """A fresh in-memory database + session for each test, isolated from
    the dev/production database file."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    db_module.Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = TestSession()
    try:
        yield sess
        sess.rollback()
    finally:
        sess.close()
        engine.dispose()
