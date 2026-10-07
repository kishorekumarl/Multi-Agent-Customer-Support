"""Helpers shared by the tool modules (input validation, queries, error handling)."""

import inspect
import json
import re
import time
from functools import wraps

from sqlalchemy import text

from src.config.settings import settings
from src.database.connection import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


class _BadInput(ValueError):
    """Raised for user input the tools refuse to act on."""


def _like(value: str) -> str:
    """Build a contains-pattern with LIKE wildcards in the input escaped."""
    value = (value or "").strip()
    if not value:
        raise _BadInput("Search text must not be empty.")
    for ch in ("!", "%", "_"):
        value = value.replace(ch, "!" + ch)
    return f"%{value}%"


def _parse_id(value: str, name: str) -> int:
    """Validate a numeric ID passed as a string and return it as an int."""
    text_value = str(value).strip()
    if not re.fullmatch(r"\d+", text_value) or int(text_value) == 0:
        raise _BadInput(f"{name} must be a positive whole number, got {value!r}.")
    return int(text_value)


def _query(sql: str, params: dict) -> list[dict]:
    with get_engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _not_found(message: str, total: int | None = None) -> str:
    """JSON for an empty lookup: a readable message plus an empty result list."""
    payload = {"message": message, "results": []}
    if total is not None:
        payload["total"] = total
    return json.dumps(payload)


_PAYLOAD_LIMIT = 2000  # characters of a response body written to the log


def _request_args(func, args, kwargs) -> dict:
    """The arguments the model sent, for the log. The injected graph state is left out
    (it is the whole conversation); only the verified customer_id is kept from it."""
    try:
        bound = dict(inspect.signature(func).bind_partial(*args, **kwargs).arguments)
    except TypeError:
        bound = dict(kwargs)
    state = bound.pop("state", None)
    if isinstance(state, dict) and state.get("customer_id") is not None:
        bound["customer_id"] = state["customer_id"]
    return bound


def _response_for_log(result: str) -> str:
    """The JSON response, truncated; or just its shape when LOG_TOOL_PAYLOADS is off."""
    if settings.log_tool_payloads:
        if len(result) > _PAYLOAD_LIMIT:
            return f"{result[:_PAYLOAD_LIMIT]}... [truncated, {len(result)} chars]"
        return result
    try:
        data = json.loads(result)
    except ValueError:
        return "<not json>"
    if not isinstance(data, dict):
        return "<json>"
    summary = {k: data[k] for k in ("total", "error", "message") if k in data}
    if isinstance(data.get("results"), list):
        summary["results"] = f"{len(data['results'])} rows"
    return json.dumps(summary)


def _json_errors(func):
    """Return errors as JSON so the agent can react instead of the run crashing.

    Also the one place every tool logs its request and response, so tools do not
    need a logger of their own.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        name = func.__name__
        logger.info("TOOL_REQUEST  %s %s", name, json.dumps(_request_args(func, args, kwargs), default=str))
        started = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except _BadInput as exc:
            result = json.dumps({"error": str(exc)})
        except Exception:
            logger.exception("Tool %s failed", name)
            result = json.dumps({"error": "The service is temporarily unavailable."})
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("TOOL_RESPONSE %s (%.0f ms, %d chars) %s", name, elapsed_ms, len(result), _response_for_log(result))
        return result

    return wrapper
