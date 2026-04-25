"""
Shared error handling utilities for Graider API routes.

Error responses follow RFC 7807 (Problem Details for HTTP APIs) with a
backward-compatible `error` field preserved for the React frontend.
Response Content-Type is `application/problem+json` per RFC 7807 § 3.

See https://datatracker.ietf.org/doc/html/rfc7807 for the full spec.
"""
import logging
import functools
from flask import jsonify, request
import pybreaker

logger = logging.getLogger(__name__)

# Base URI for problem-type identifiers. Each problem type gets a path under
# this base, e.g. "/internal", "/breaker-open", "/validation". Districts can
# fetch the URI to get human-readable context (we don't host the docs yet —
# the URI is a stable identifier even when nothing serves it). RFC 7807 § 4.2
# allows opaque type URIs.
PROBLEM_BASE_URI = "https://graider.live/errors"


def _slug_from_status(status_code):
    return {
        400: "bad-request",
        401: "unauthenticated",
        403: "forbidden",
        404: "not-found",
        409: "conflict",
        422: "unprocessable",
        429: "rate-limited",
        500: "internal",
        503: "service-unavailable",
    }.get(status_code, f"http-{status_code}")


def _title_from_status(status_code):
    return {
        400: "Bad Request",
        401: "Authentication Required",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }.get(status_code, f"HTTP {status_code}")


def _problem_response(*, type_slug, title, status, detail=None, extra_headers=None):
    """Build an RFC 7807 problem+json response with a backward-compat
    `error` field that duplicates `detail`.
    """
    body = {
        "type": f"{PROBLEM_BASE_URI}/{type_slug}",
        "title": title,
        "status": status,
        "instance": request.path if request else None,
    }
    if detail is not None:
        body["detail"] = detail
        # Backward-compat: legacy clients (Graider's own React frontend, internal
        # scripts) read `response.error`. Keep it pointing at the same human
        # message as `detail`. Removing this field is a future breaking-change
        # PR coordinated with the frontend.
        body["error"] = detail
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Content-Type"] = "application/problem+json"
    if extra_headers:
        for k, v in extra_headers.items():
            resp.headers[k] = v
    return resp


def error_response(message, status_code=400, code=None):
    """Return a consistent JSON error response with proper HTTP status code.

    Backward-compatible signature — every existing caller continues to work.
    Internally emits RFC 7807 problem+json. The `code` arg (if provided)
    becomes the type slug AND a top-level extension field, per RFC 7807 § 3.2
    (which permits non-reserved members).
    """
    type_slug = code or _slug_from_status(status_code)
    resp = _problem_response(
        type_slug=type_slug,
        title=_title_from_status(status_code),
        status=status_code,
        detail=message,
    )
    if code:
        json_body = resp.get_json()
        json_body["code"] = code
        resp.set_data(jsonify(json_body).get_data())
    return resp


def handle_route_errors(f):
    """Decorator that catches unhandled exceptions and returns RFC 7807 problem+json.

    Specializes pybreaker.CircuitBreakerError → 503 with `Retry-After: 60`,
    matching the Phase 5b breaker-open HTTP contract.

    Logs the full traceback server-side but never exposes it to the client.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Circuit breaker open in %s: %s", f.__name__, e)
            resp = _problem_response(
                type_slug="breaker-open",
                title="Service Unavailable",
                status=503,
                detail="LLM provider temporarily unavailable — circuit breaker open",
                extra_headers={"Retry-After": "60"},
            )
            # Preserve the legacy retry_after_seconds field that older callers read
            json_body = resp.get_json()
            json_body["retry_after_seconds"] = 60
            resp.set_data(jsonify(json_body).get_data())
            return resp
        except Exception:
            logger.exception("Unhandled error in %s", f.__name__)
            return _problem_response(
                type_slug="internal",
                title="Internal Server Error",
                status=500,
                detail="Internal server error",
            )
    return wrapper
