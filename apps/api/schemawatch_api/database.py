from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from schemawatch_api.models import Base


def create_db_engine(database_url: str) -> Engine:
    """Create a synchronous SQLAlchemy engine for SQLite or PostgreSQL."""
    connect_args: dict[str, object] = {}
    kwargs: dict[str, object] = {}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool

    return create_engine(database_url, connect_args=connect_args, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a scoped or standard sessionmaker bound to engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(engine: Engine) -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
