"""Database health check: verifies the Chinook schema is present and queryable."""

import json

from sqlalchemy import Engine, inspect, text

from src.utils.logger import get_logger

logger = get_logger(__name__)

REQUIRED_TABLES = [
    "Album",
    "Artist",
    "Customer",
    "Employee",
    "Genre",
    "Invoice",
    "InvoiceLine",
    "MediaType",
    "Playlist",
    "PlaylistTrack",
    "Track",
]


def check_database_health(engine: Engine) -> dict:
    """Verify the expected tables exist and a basic count query succeeds.

    Returns a dict with:
        healthy (bool): True if all required tables are present and the count query ran.
        missing_tables (list[str]): required tables not found in the database.
        track_count (int | None): row count from Track, or None if the query failed.
        error (str | None): the error message, if any step failed.
    """
    existing_tables = set(inspect(engine).get_table_names())
    missing_tables = [table for table in REQUIRED_TABLES if table not in existing_tables]

    track_count = None
    error = None
    if not missing_tables:
        try:
            with engine.connect() as conn:
                track_count = conn.execute(text("SELECT COUNT(*) FROM Track")).scalar()
        except Exception as exc:
            logger.exception("Health check count query failed")
            error = str(exc)

    healthy = not missing_tables and error is None and track_count is not None

    return {
        "healthy": healthy,
        "missing_tables": missing_tables,
        "track_count": track_count,
        "error": error,
    }


if __name__ == "__main__":
    from src.database.connection import get_engine

    result = check_database_health(get_engine())
    print(json.dumps(result, indent=2))
