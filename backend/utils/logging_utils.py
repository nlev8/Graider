"""Logging utilities for Graider — request correlation and structured output."""
import json
import logging
import os
import time
from typing import TYPE_CHECKING

from flask import g

if TYPE_CHECKING:
    from flask import Flask, Response


class SafeRequestIdFormatter(logging.Formatter):
    """Formatter that safely includes request_id even if not set on the record."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, 'request_id'):
            try:
                record.request_id = getattr(g, 'request_id', '-')
            except RuntimeError:
                record.request_id = '-'
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for production (Railway).

    Outputs each log line as a JSON object with: timestamp, level, logger,
    request_id, message, and optional exception info.
    """

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, 'request_id'):
            try:
                record.request_id = getattr(g, 'request_id', '-')
            except RuntimeError:
                record.request_id = '-'
        log_obj: dict[str, str] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            # request_id is set above on the record; mypy can't see the
            # dynamic attribute add, so use getattr with the fallback
            # the formatter already established.
            "request_id": getattr(record, 'request_id', '-'),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def configure_logging(app: "Flask") -> None:
    """Set up logging with request_id correlation.

    In production (FLASK_ENV != development), uses JSON structured logging.
    In development, uses human-readable format with request_id.

    Call this after app creation, before init_auth().
    """
    is_prod = os.getenv('FLASK_ENV', '').lower() not in ('development', 'dev', '')

    root = logging.getLogger()

    formatter: logging.Formatter
    if is_prod:
        # Production: JSON structured logging
        formatter = JsonFormatter()
    else:
        # Development: human-readable with request_id
        # Uses SafeRequestIdFormatter which handles missing request_id gracefully
        formatter = SafeRequestIdFormatter(
            '%(asctime)s [%(request_id)s] %(name)s %(levelname)s: %(message)s'
        )

    # Apply formatter to existing handlers
    for handler in root.handlers:
        handler.setFormatter(formatter)

    # If no handlers exist, add a basic one
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
        root.setLevel(logging.INFO)


def log_request_timing(app: "Flask") -> None:
    """Add before/after request hooks to log API response times."""

    @app.before_request
    def start_timer() -> None:
        g._request_start_time = time.time()

    @app.after_request
    def log_response(response: "Response") -> "Response":
        if hasattr(g, '_request_start_time'):
            from flask import request
            duration_ms = round((time.time() - g._request_start_time) * 1000)
            if duration_ms > 500:  # Only log slow requests
                logger = logging.getLogger('performance')
                logger.info("Slow request: %s %s — %dms (status %d)",
                            request.method, request.path, duration_ms, response.status_code)
        return response
