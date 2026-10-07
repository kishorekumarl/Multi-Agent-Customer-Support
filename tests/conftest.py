import logging
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.seed_data.seed import seed_database


@pytest.fixture
def seeded_engine():
    """A fresh, isolated in-memory Chinook database for each test."""
    # Same setup as src/database/connection.py: one shared connection, so tools that
    # LangGraph runs in worker threads see the seeded data too.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    logging.info("Seeding database...")
    seed_database(engine)
    return engine


@pytest.fixture
def empty_engine():
    """An in-memory SQLite database with no tables."""
    logging.info("Creating empty database...")
    return create_engine("sqlite:///:memory:")
