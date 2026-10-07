import json
import re
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import text

from src.database.connection import get_engine
from src.tools._common import _BadInput, _json_errors
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_ROWS = 200


def _require_read_only(sql: str) -> None:
    """Allow a single SELECT/WITH statement only (defense in depth; the connection is also read-only)."""
    cleaned = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql or "", flags=re.DOTALL).strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", cleaned):
        raise _BadInput("Only SELECT queries are allowed.")
    if ";" in cleaned:
        raise _BadInput("Only a single SQL statement is allowed.")


@tool
@_json_errors
def run_sql_query(sql: str, params: dict[str, Any] | None = None) -> str:
    """Run a SQL query against the Chinook customer support database and return the results as JSON.

    The database has tables including Artist, Album, Track, Customer, Invoice,
    InvoiceLine, and Employee. Use standard SQLite syntax.

    Args:
        sql: The SQL query to run. Use named placeholders (e.g. ":customer_id")
            for any values instead of inlining them, to avoid SQL injection.
        params: A dict mapping each named placeholder to its value, e.g.
            {"customer_id": 5}. Omit if the query has no placeholders.

    Returns:
        A JSON string containing a list of row objects (empty list if no rows matched),
        capped at 200 rows, or an {"error": ...} object if the query was rejected or failed.
    """
    _require_read_only(sql)
    with get_engine().connect() as conn:
        conn.exec_driver_sql("PRAGMA query_only = ON")
        try:
            result = conn.execute(text(sql), params or {})
            rows = [dict(row) for row in result.mappings().fetchmany(MAX_ROWS)]
        finally:
            conn.exec_driver_sql("PRAGMA query_only = OFF")

    return json.dumps(rows, default=str)
