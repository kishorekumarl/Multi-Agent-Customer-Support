"""Shared SQLAlchemy engine, seeded once at import time."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from src.config.settings import settings
from src.database.seed_data.seed import seed_database


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared, seeded database engine (created once, reused after).

    An in-memory SQLite database only survives on the connection that created
    it, so a StaticPool (one shared connection) is required to keep the seeded
    data visible across requests from different threads.
    """
    is_sqlite_memory = settings.database_url.startswith("sqlite:///:memory:")
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if is_sqlite_memory else {},
        poolclass=StaticPool if is_sqlite_memory else None,
    )
    seed_database(engine)
    return engine
