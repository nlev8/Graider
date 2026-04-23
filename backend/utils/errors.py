"""
Shared error handling utilities for Graider API routes.
"""
import logging
import functools
from flask import jsonify
import pybreaker

logger = logging.getLogger(__name__)


def error_response(message, status_code=400, code=None):
    """Return a consistent JSON error response with proper HTTP status code."""
    payload = {"error": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status_code


def handle_route_errors(f):
    """Decorator that catches unhandled exceptions and returns a clean 500 response.

    Specializes pybreaker.CircuitBreakerError -> 503 with Retry-After: 60,
    matching the Phase 5b breaker-open HTTP contract (non-streaming routes).

    Logs the full traceback server-side but never exposes it to the client.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Circuit breaker open in %s: %s", f.__name__, e)
            payload = {
                "error": "LLM provider temporarily unavailable — circuit breaker open",
                "retry_after_seconds": 60,
            }
            resp = jsonify(payload)
            resp.status_code = 503
            resp.headers["Retry-After"] = "60"
            return resp
        except Exception:
            logger.exception("Unhandled error in %s", f.__name__)
            return error_response("Internal server error", status_code=500)
    return wrapper
