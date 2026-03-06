"""Database session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

_ENGINE_CACHE: dict[str, Engine] = {}


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if make_url(database_url).get_backend_name() == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {}


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine."""
    return create_engine(database_url, future=True, **_engine_kwargs(database_url))


def get_engine_cached(database_url: str) -> Engine:
    """Return a cached SQLAlchemy engine for the URL."""
    if database_url not in _ENGINE_CACHE:
        _ENGINE_CACHE[database_url] = create_engine(
            database_url, future=True, **_engine_kwargs(database_url)
        )
    return _ENGINE_CACHE[database_url]


def get_session(database_url: str) -> Session:
    """Create a session bound to the given database URL."""
    engine = get_engine(database_url)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return maker()


def get_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Create a session and ensure it closes after use."""
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = maker()
    try:
        yield session
    finally:
        session.close()
