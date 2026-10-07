"""Shared logging configuration."""

import logging

from src.config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

logging.basicConfig(level=settings.log_level, format=_LOG_FORMAT)


class _DropRemainingStepsNotice(logging.Filter):
    """Hide one harmless LangGraph notice, and nothing else.

    langgraph-supervisor uses a custom state_schema for both the supervisor agent and the
    outer workflow. The agent writes its `remaining_steps` counter, the workflow has no
    channel for it, and LangGraph logs "wrote to unknown channel remaining_steps, ignoring
    it". We need the custom schema (it carries customer_id and memory), and the dropped
    counter is never used, so the notice is noise on every handoff.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not ("unknown channel" in message and "remaining_steps" in message)


logging.getLogger("langgraph").addFilter(_DropRemainingStepsNotice())


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured with the app's log level."""
    return logging.getLogger(name)
