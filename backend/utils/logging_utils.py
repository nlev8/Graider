"""Logging utilities for Graider — request correlation and structured output."""
import json
import logging
import os
import time
from flask import g


class RequestIdFilter(logging.Filter):
    """Inject request_id into every log record for request tracing."""

    def filter(self, record):
        try:
            record.request_id = getattr(g, 'request_id', '-')
        except RuntimeError:
            # Outside Flask request context (e.g., httpx logging in background thread)
            record.request_id = '-'
        return True


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for production (Railway).

    Outputs each log line as a JSON object with: timestamp, level, logger,
    request_id, message, and optional exception info.
    """

    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, 'request_id', '-'),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def configure_logging(app):
    """Set up logging with request_id correlation.

    In production (FLASK_ENV != development), uses JSON structured logging.
    In development, uses human-readable format with request_id.

    Call this after app creation, before init_auth().
    """
    is_prod = os.getenv('FLASK_ENV', '').lower() not in ('development', 'dev', '')

    # Add filter to root logger so all loggers inherit it
    request_filter = RequestIdFilter()
    root = logging.getLogger()

    # Only add if not already added
    if not any(isinstance(f, RequestIdFilter) for f in root.filters):
        root.addFilter(request_filter)

    if is_prod:
        # Production: JSON structured logging
        formatter = JsonFormatter()
    else:
        # Development: human-readable with request_id
        formatter = logging.Formatter(
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


def log_request_timing(app):
    """Add before/after request hooks to log API response times."""

    @app.before_request
    def start_timer():
        g._request_start_time = time.time()

    @app.after_request
    def log_response(response):
        if hasattr(g, '_request_start_time'):
            from flask import request
            duration_ms = round((time.time() - g._request_start_time) * 1000)
            if duration_ms > 500:  # Only log slow requests
                logger = logging.getLogger('performance')
                logger.info("Slow request: %s %s — %dms (status %d)",
                            request.method, request.path, duration_ms, response.status_code)
        return response
