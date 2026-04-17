"""Sentry error tracking for Graider — PII-scrubbed, FERPA-safe.

Exposes:
  - before_send(event, hint)    → Sentry hook that scrubs PII
  - critical_path               → decorator (stub, populated in Task 4)
  - init_sentry()               → client init (stub, populated in Task 5)

See docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md.
"""

import hashlib
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Module-level guard to prevent sentry_sdk.init() from running twice when
# backend.app is imported multiple times (common in test teardown/setup).
_initialized = False

# PII field names scrubbed from stack frame locals.
# Keep this list in sync with docs/observability.md § "Known noise sources".
#
# Primary defense against PII leakage in Sentry events is `include_local_variables=False`
# in sentry_sdk.init() (below) — when disabled, frames carry no vars at all, so this
# allowlist becomes belt-and-suspenders for any future flag flip. Keep it comprehensive
# anyway: if someone re-enables local var capture for a debugging session, these names
# still get scrubbed.
_PII_LOCAL_NAMES = frozenset({
    # Originals (Phase 1 observability work)
    "student_name", "student_email", "answers", "draft_answers",
    "student_id_number", "submission_row", "results", "feedback",
    "first_name", "last_name", "row", "s", "sdata", "assessment",
    "assessment_content", "student_row", "assessment_data",
    # Roster + assistant tool locals (assistant_tools.py:705-728, assistant_tools_student.py:498-528)
    "first", "last", "display_name", "student_id", "grade",
    "matched_name", "matched_id", "safe_id", "roster", "grading_state",
    "rname", "entry", "eml", "name", "student",
})

# Query-param name fragments whose presence indicates a secret.
_SECRET_PARAM_MARKERS = ("token", "key", "secret", "password")

# Exception type names that represent client-side 4xx errors.
# These are dropped entirely — no point paging the developer about a
# garbage request body or an expired session.
_CLIENT_ERROR_TYPES = frozenset({
    "BadRequest", "Unauthorized", "Forbidden", "NotFound",
    "MethodNotAllowed", "UnprocessableEntity", "TooManyRequests",
})


def _is_client_error(event: dict) -> bool:
    """Return True if the event represents a 4xx client error that should be dropped.

    Sentry's event format emits the exception type as either a bare class
    name ("BadRequest") or a fully-qualified dotted path
    ("werkzeug.exceptions.BadRequest"), depending on the capturing
    integration and Python version. Check both forms by comparing the
    rightmost dotted segment of the type string.
    """
    try:
        exceptions = event.get("exception", {}).get("values", [])
        for exc in exceptions:
            exc_type = exc.get("type", "") or ""
            # Match both "BadRequest" and "werkzeug.exceptions.BadRequest"
            bare_name = exc_type.rsplit(".", 1)[-1]
            if bare_name in _CLIENT_ERROR_TYPES:
                return True
    except Exception:
        # Defensive: never let the scrubber crash — a broken scrubber
        # swallows events silently.
        pass
    return False


def _resolve_user_id() -> str:
    """Return a stable user identifier that is safe for PII-free correlation.

    Returns a 12-char sha256 hash of the Flask g.user_id when inside a
    Flask request context with a teacher attached; returns "anonymous"
    otherwise.

    MUST NOT raise. The Sentry before_send hook runs in many contexts
    (Flask request, background grading thread, Sentry SDK's own worker
    thread flushing events, import-time errors). Touching flask.g
    outside a request context raises RuntimeError, which would crash
    the scrubber and cause Sentry to drop the event entirely — the
    opposite of what we want. Every access to g is guarded.
    """
    try:
        from flask import has_request_context, g
    except ImportError:
        return "anonymous"

    try:
        if not has_request_context():
            return "anonymous"
    except RuntimeError:
        return "anonymous"

    try:
        uid = getattr(g, "user_id", None)
    except RuntimeError:
        return "anonymous"

    if not uid:
        return "anonymous"

    return hashlib.sha256(str(uid).encode()).hexdigest()[:12]


def _scrub_request(request: Optional[dict]) -> None:
    """Strip PII from the request dict on a Sentry event (in place)."""
    if not request:
        return

    # Drop body payloads entirely — they may contain student answers,
    # grading results, teacher notes, anything.
    for key in ("data", "json", "form", "cookies"):
        request.pop(key, None)

    # Redact auth-bearing headers.
    headers = request.get("headers")
    if isinstance(headers, dict):
        for header_key in list(headers.keys()):
            if header_key.lower() in ("authorization", "cookie"):
                headers[header_key] = "[Filtered]"

    # Strip query params whose names look like secrets.
    query = request.get("query_string")
    if isinstance(query, str) and query:
        parts = []
        for param in query.split("&"):
            if "=" in param:
                name, _value = param.split("=", 1)
            else:
                name = param
            if any(marker in name.lower() for marker in _SECRET_PARAM_MARKERS):
                parts.append(f"{name}=[Filtered]")
            else:
                parts.append(param)
        request["query_string"] = "&".join(parts)


def _scrub_frame_locals(event: dict) -> None:
    """Walk every stack frame and replace PII locals with a sentinel (in place)."""
    try:
        exceptions = event.get("exception", {}).get("values", [])
        for exc in exceptions:
            stacktrace = exc.get("stacktrace") or {}
            frames = stacktrace.get("frames", [])
            for frame in frames:
                frame_vars = frame.get("vars")
                if not isinstance(frame_vars, dict):
                    continue
                for name in list(frame_vars.keys()):
                    if name in _PII_LOCAL_NAMES:
                        frame_vars[name] = "[PII-scrubbed]"
    except Exception:
        # Defensive: never let the scrubber crash.
        pass


def before_send(event: dict, hint: dict) -> Optional[dict]:
    """Sentry before_send hook — scrubs PII and drops 4xx errors.

    Returning None drops the event entirely. Returning the (mutated)
    event forwards it to Sentry Cloud.
    """
    if _is_client_error(event):
        return None

    _scrub_request(event.get("request"))
    _scrub_frame_locals(event)

    user = event.setdefault("user", {})
    if isinstance(user, dict):
        user["id"] = _resolve_user_id()
        user.pop("email", None)
        user.pop("username", None)
        user.pop("ip_address", None)

    return event


def critical_path(fn):
    """Decorator — tag escaping exceptions with severity=critical.

    Wraps the decorated callable so that any unhandled exception
    escaping it is tagged `severity=critical` on the current Sentry
    isolation scope. BetterStack's alert routing (Rule 3) uses this
    tag to trigger iOS Critical Alert escalation on sustained
    critical-path failures.

    Apply only to outermost entrypoints — never to inner helpers
    called from within an already-decorated function. The 5 target
    functions are documented in docs/observability.md § "Critical-path
    tag convention".

    Safe when Sentry is uninitialized: sentry_sdk.set_tag() is a
    no-op on the default uninitialized hub, so local dev / CI /
    tests see this decorator as transparent.

    Why not `with sentry_sdk.push_scope()`:
        In sentry-sdk 2.x, `push_scope()` creates a forked scope
        that is popped when the `with` block exits — INCLUDING when
        it exits via exception propagation. When the wrapped fn
        raises, the scope is popped BEFORE Flask's integration
        captures the exception, so any tag set on the forked scope
        is gone by the time the event is built. (We verified this
        in production: 2026-04-11, both debug events arrived at
        BetterStack with the scrubber-set user.id but no
        severity=critical tag on the critical event.) The SDK's
        deprecation warning was the signal that this pattern no
        longer works.

    The correct pattern in SDK 2.x is to call `sentry_sdk.set_tag`
    on the current isolation scope AFTER catching the exception
    but BEFORE re-raising it. Flask's FlaskIntegration captures
    the exception in its own error hook AFTER this line runs, and
    reads the current scope state at capture time — which now
    includes our tag.
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            # Attach the tag to the current isolation scope just
            # before the exception propagates to Flask's error
            # handler. Wrapped in an inner try/except so a broken
            # observability layer can never mask the original
            # production error.
            try:
                import sentry_sdk
                sentry_sdk.set_tag("severity", "critical")
            except Exception:
                pass
            raise

    return wrapper


def init_sentry() -> None:
    """Initialize Sentry if SENTRY_DSN is set; hard no-op otherwise.

    Reads configuration from environment variables:
      - SENTRY_DSN                 — required to enable. If unset, this
                                     function returns immediately without
                                     initializing any client. Local dev,
                                     CI, and tests stay silent.
      - RAILWAY_GIT_COMMIT_SHA     — Railway build-time env var. Used as
                                     the Sentry release tag (short form).

    Configuration (hardcoded — intentional, not env-driven):
      - environment="production"   — if/when staging is added, it gets
                                     its own separate DSN, not an env
                                     override here.
      - traces_sample_rate=0.0     — APM off. Separate Sentry billing
                                     axis, can be enabled later with no
                                     code change needed.
      - send_default_pii=False     — belt + suspenders with our before_send
                                     scrubber.
      - before_send=before_send    — the PII scrubber from Task 3.
      - transaction_style="endpoint" — Flask route function name, not URL.
                                     URL grouping would explode cardinality
                                     on ID-bearing routes like
                                     /api/student/submission/<id>/draft.
      - ignore_errors=[4xx]        — backstop for the rare case where
                                     code explicitly raises a Werkzeug
                                     HTTP exception inside a try/except.

    Idempotent: calling this function twice is safe. The second call
    short-circuits via the module-level _initialized flag.

    Failure-resilient: if sentry_sdk.init() raises (e.g., malformed DSN
    from a Railway env-var typo), the exception is caught and logged as
    a warning. The app continues booting with Sentry disabled — a solo
    founder can still reach the backend to fix the typo.
    """
    global _initialized
    if _initialized:
        return

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("SENTRY_DSN not set; Sentry disabled")
        _initialized = True
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        import werkzeug.exceptions as wex
    except ImportError as exc:
        logger.warning("sentry-sdk unavailable; Sentry disabled: %s", exc)
        _initialized = True
        return

    sha = os.getenv("RAILWAY_GIT_COMMIT_SHA")
    release = sha[:7] if sha else "unknown"

    try:
        from sentry_sdk.utils import BadDsn
    except ImportError:
        BadDsn = ValueError  # type: ignore[misc,assignment]

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment="production",
            release=release,
            traces_sample_rate=0.0,
            send_default_pii=False,
            # FERPA: drop all stack-frame locals from events. Without this,
            # Sentry's default is to include frame `vars` at capture time,
            # which leaks student names / SIS IDs / answers anywhere in the
            # grading and roster code paths (assistant_tools.py, portal_grading.py,
            # etc.). Scrubbing by allowlist is defense in depth on top of this.
            include_local_variables=False,
            integrations=[FlaskIntegration(transaction_style="endpoint")],
            before_send=before_send,
            ignore_errors=[
                wex.BadRequest,
                wex.Unauthorized,
                wex.Forbidden,
                wex.NotFound,
                wex.MethodNotAllowed,
            ],
        )
    except (BadDsn, ValueError) as exc:
        # DSN is syntactically invalid — log and continue booting with
        # Sentry disabled so the solo founder can still reach the app
        # to fix the env var. Other exceptions (TypeError from a wrong
        # kwarg, a future SDK regression, etc.) are deliberately NOT
        # caught — they represent real bugs that should surface loudly
        # via CI / staging before hitting production.
        logger.warning("sentry_sdk.init() failed with invalid DSN; Sentry disabled: %s", exc)
        return

    _initialized = True
    logger.info("Sentry initialized (release=%s)", release)
