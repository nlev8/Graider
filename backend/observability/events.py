"""Structured-event emit() helper for machine-parsed logs.

The existing JsonFormatter (backend/utils/logging_utils.py) serializes
only a fixed set of outer fields (timestamp, level, logger, request_id,
message, optional exception). Structured event data is carried INSIDE
the `message` field as a JSON-encoded string — consumers parse `message`
as JSON to extract the `event` name and its fields. Same pattern as
backend/observability/db_mode.py, which this PR refactors to use the
helper.

Example output after the JsonFormatter runs:

    {"timestamp": "2026-04-20T12:34:56Z", "level": "INFO",
     "logger": "backend.observability.events",
     "request_id": "abc-123",
     "message": "{\\"event\\": \\"llm.call.start\\", \\"model\\": \\"gpt-4\\"}"}
"""
from __future__ import annotations

import json
import logging

_logger = logging.getLogger(__name__)

_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def emit(event: str, level: str = "info", **fields) -> None:
    """Emit a structured event as a JSON payload inside the log record's message.

    Args:
        event: short dotted name for the event (e.g. "llm.call.start").
            Becomes the "event" key in the serialized payload.
        level: logging level — one of debug/info/warning/error/critical.
            Controls the log level, NOT included in the payload.
        **fields: arbitrary serializable key/value pairs.

    Raises:
        ValueError: if level is not a recognized level name.
    """
    level_int = _LEVEL_MAP.get(level.lower())
    if level_int is None:
        raise ValueError(f"unknown log level: {level!r}")

    payload = {"event": event, **fields}
    _logger.log(level_int, json.dumps(payload))
