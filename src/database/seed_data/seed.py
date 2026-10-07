"""Seed the SQLite database from the Chinook SQL dump."""

import sqlite3
import sqlalchemy as sa
from pathlib import Path

from sqlalchemy import Engine, text


SEED_SQL_PATH = Path(__file__).parent / "Chinook_Sqlite.sql"


def is_seeded(engine: Engine) -> bool:
    """Return True if the database already has the Chinook schema loaded."""
    with engine.connect() as conn:
        result = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Track'"
        )
        return result.fetchone() is not None


def load_seed_data(engine: Engine) -> None:
    """Execute the Chinook SQL dump (schema + data) against the given engine."""
    if is_seeded(engine):
        return

    sql_script = SEED_SQL_PATH.read_text(encoding="utf-8")

    raw_conn = engine.raw_connection()
    try:
        cursor: sqlite3.Cursor = raw_conn.cursor()
        cursor.executescript(sql_script)
        raw_conn.commit()
    finally:
        raw_conn.close()


def seed_database(engine: Engine) -> Engine:
    """Ensure the database behind `engine` is created and seeded. Returns the engine."""
    load_seed_data(engine)
    return engine


if __name__ == "__main__":

    engine = sa.create_engine("sqlite:///:memory:")
    seed_database(engine)

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM Track")).scalar()
        print(f"Seeded database with {count} tracks.")
