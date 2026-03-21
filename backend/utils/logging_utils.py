"""Logging utilities for Graider — request correlation and structured output."""
import logging
from flask import g


class RequestIdFilter(logging.Filter):
    """Inject request_id into every log record for request tracing."""

    def filter(self, record):
        record.request_id = getattr(g, 'request_id', '-')
        return True


def configure_logging(app):
    """Set up logging with request_id correlation.

    Call this after app creation, before init_auth().
    Adds request_id to all log output for tracing requests
    through route handlers and background threads.
    """
    # Add filter to root logger so all loggers inherit it
    request_filter = RequestIdFilter()
    root = logging.getLogger()

    # Only add if not already added
    if not any(isinstance(f, RequestIdFilter) for f in root.filters):
        root.addFilter(request_filter)

    # Update format to include request_id
    handler_format = '%(asctime)s [%(request_id)s] %(name)s %(levelname)s: %(message)s'
    for handler in root.handlers:
        handler.setFormatter(logging.Formatter(handler_format))

    # If no handlers exist, add a basic one
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(handler_format))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
