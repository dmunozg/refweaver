"""Database session helpers."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine."""
    return create_engine(database_url, future=True)


def get_session(database_url: str) -> Session:
    """Create a session bound to the given database URL."""
    engine = get_engine(database_url)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return maker()


def get_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
