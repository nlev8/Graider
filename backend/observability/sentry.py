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
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Module-level guard to prevent sentry_sdk.init() from running twice when
# backend.app is imported multiple times (common in test teardown/setup).
_initialized = False

# APM/tracing sample rate. 5% default — gives signal on slow routes,
# queue latency, and LLM call timing without blowing the BetterStack
# error-tracking quota (which is shared with traces on the free tier).
# Closes audit MAJOR #14 (Codex full-codebase audit 2026-05-06):
# previously hardcoded to 0.0, leaving latency regressions diagnostically
# blind. Operators can override per-environment via SENTRY_TRACES_SAMPLE_RATE
# (e.g., 0.0 to fully disable, 0.5 for high-fidelity tuning sprints).
def _resolve_traces_sample_rate() -> Optional[float]:
    """Resolve the traces_sample_rate kwarg for sentry_sdk.init().

    Codex audit round-1 of PR #222 noted: per Sentry docs,
    `traces_sample_rate=0.0` prevents NEW traces but continues incoming
    sampled traces (relevant for distributed tracing). `None` fully
    disables. Graider has no upstream propagator, so 0.0 is functionally
    equivalent to None — but pass None for explicitness so an operator
    setting `SENTRY_TRACES_SAMPLE_RATE=0.0` to "disable" actually does so
    in the Sentry-canonical way.
    """
    raw = os.getenv("SENTRY_TRACES_SAMPLE_RATE")
    if raw is None:
        return 0.05
    try:
        rate = float(raw)
    except ValueError:
        logger.warning(
            "SENTRY_TRACES_SAMPLE_RATE=%r is not a valid float; falling back to 0.05",
            raw,
        )
        return 0.05
    if not 0.0 <= rate <= 1.0:
        logger.warning(
            "SENTRY_TRACES_SAMPLE_RATE=%r out of range [0.0, 1.0]; falling back to 0.05",
            raw,
        )
        return 0.05
    # Map 0.0 → None for full disable per Sentry docs.
    return None if rate == 0.0 else rate

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


# Path pattern: 2+ url-safe segments. Conservative — redacts identifier
# routes (`/api/student-history/<student_id>`) AND non-identifier ones
# (`/api/healthz`) alike. The endpoint name in event["transaction"] is the
# safe replacement signal; we lose the path information from logentry but
# the FERPA risk of selective regex matching outweighs the diagnostic loss.
_LOG_PATH_PATTERN = re.compile(r"/[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)+")


def _redact_paths_in_string(text: Any) -> Any:
    """Return `text` with any path-like substrings replaced by [Filtered-path].

    Non-string inputs are returned unchanged so callers can apply this to
    arbitrary logentry param values (ints, dicts, etc.) without crashing.
    """
    if not isinstance(text, str):
        return text
    return _LOG_PATH_PATTERN.sub("[Filtered-path]", text)


def _scrub_logentry(event: dict) -> None:
    """Strip identifier-bearing paths from logentry.params + logentry.formatted.

    Sentry's logging integration captures `logger.exception(msg, *args)`
    calls as `event["logentry"]` with structure:
      - message:   format string ("Request failed: %s")
      - params:    list of args (the raw `request.path`)
      - formatted: rendered string ("Request failed: /api/...")

    `_scrub_request()` operates on `event["request"]` and never sees
    logentry. Codex audit MAJOR #14 round-3 CRITICAL: real Flask +
    Sentry SDK 2.58 simulation confirmed routes that
    `logger.exception("Request failed: %s", request.path)` leak the
    full ID-bearing path (student/class/submission IDs) into
    logentry.formatted and logentry.params. Two cited call sites:
    `backend/routes/student_account_routes.py:224` and
    `backend/routes/grading_routes.py:1260`.

    Defensive at the Sentry boundary: every Sentry event passes through
    before_send (or before_send_transaction); this scrub catches all
    logger.exception/error/warning calls with path-like params, present
    AND future, without requiring per-call-site fixes.

    The format-string in `logentry.message` is preserved (no PII) so
    debugging context is not fully lost.
    """
    le = event.get("logentry")
    if not isinstance(le, dict):
        return

    params = le.get("params")
    if isinstance(params, list):
        le["params"] = [_redact_paths_in_string(p) for p in params]
    elif isinstance(params, tuple):
        le["params"] = tuple(_redact_paths_in_string(p) for p in params)

    formatted = le.get("formatted")
    if isinstance(formatted, str):
        le["formatted"] = _redact_paths_in_string(formatted)


def _scrub_request(request: Optional[dict]) -> None:
    """Strip PII from the request dict on a Sentry event (in place)."""
    if not request:
        return

    # Drop body payloads entirely — they may contain student answers,
    # grading results, teacher notes, anything.
    for key in ("data", "json", "form", "cookies"):
        request.pop(key, None)

    # Drop the full URL — path params on FERPA-bearing routes
    # (`/api/student-history/<student_id>`, `/api/teacher/class/<class_id>/student/<student_id>/report-card`,
    # join codes, submission IDs, content IDs) leak directly into request.url
    # even with transaction_style="endpoint" (which only sets event.transaction,
    # not request.url). Codex audit MAJOR #14 round-2 CRITICAL: confirmed
    # via real Flask + Sentry SDK 2.58 simulation. The endpoint name carries
    # all routing info we need; URL adds nothing diagnostically that's worth
    # the FERPA risk.
    request.pop("url", None)

    # Redact auth-bearing + URL-leaking headers.
    headers = request.get("headers")
    if isinstance(headers, dict):
        for header_key in list(headers.keys()):
            lk = header_key.lower()
            if lk in ("authorization", "cookie"):
                headers[header_key] = "[Filtered]"
            elif lk == "referer":
                # Could leak prior page URL with IDs (e.g., browser navigated
                # from /api/student/submission/<id> to current request).
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
    _scrub_logentry(event)

    user = event.setdefault("user", {})
    if isinstance(user, dict):
        # Preserve an explicitly-set user.id when it already looks like our
        # scrubber format (12-char hex) — Celery workers set_user({"id": sha256(uid)[:12]})
        # before raising, and without this branch `_resolve_user_id()` would
        # overwrite with "anonymous" (no Flask context in the worker process),
        # losing task-level attribution.
        #
        # The format check (12 hex chars) is the guard: any non-matching value
        # still gets replaced, so raw emails / PII that somehow reached user.id
        # don't survive into Sentry Cloud.
        pre_set = user.get("id")
        if isinstance(pre_set, str) and len(pre_set) == 12 and all(c in "0123456789abcdef" for c in pre_set):
            pass  # keep the explicit hashed attribution
        else:
            user["id"] = _resolve_user_id()
        user.pop("email", None)
        user.pop("username", None)
        user.pop("ip_address", None)

    return event


def before_send_transaction(event: dict, hint: dict) -> Optional[dict]:
    """Sentry before_send_transaction hook — scrubs PII from APM transactions.

    Codex audit round-1 of PR #222 (audit MAJOR #14) flagged a CRITICAL gap:
    transaction events use a separate SDK pipeline that the `before_send`
    hook does NOT see. Without this scrubber, sentry-sdk 2.x captures
    request.url (with ID-bearing paths), query_string (potentially with
    secrets), and request body (potentially with FERPA-sensitive student
    data) on every sampled transaction.

    `max_request_body_size="never"` in init() is defense-in-depth that
    prevents body capture at the source. This hook is belt-and-suspenders:
    it strips request payload + secret-looking query params + auth headers
    + the full request.url (which carries identifier-bearing path params
    on FERPA-sensitive routes — the endpoint name in event["transaction"]
    is the safe replacement signal).

    User attribution caveat (Codex round-2 MINOR): the SDK fires this
    hook from a worker thread AFTER Flask request context teardown, so
    `_resolve_user_id()` typically resolves to "anonymous" because
    flask.g is no longer accessible. That is privacy-safe (no real
    user.id reaches Sentry from transactions) but means transaction
    events are NOT teacher-attributable. Error events still attribute
    correctly via the in-context `before_send` hook.

    Always returns the event (we want APM signal); only scrubs in place.
    """
    _scrub_request(event.get("request"))
    _scrub_logentry(event)

    user = event.setdefault("user", {})
    if isinstance(user, dict):
        pre_set = user.get("id")
        if isinstance(pre_set, str) and len(pre_set) == 12 and all(c in "0123456789abcdef" for c in pre_set):
            pass
        else:
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


def init_sentry(environment: str = 'web') -> None:
    """Initialize Sentry if SENTRY_DSN is set; hard no-op otherwise.

    Reads configuration from environment variables:
      - SENTRY_DSN                 — required to enable. If unset, this
                                     function returns immediately without
                                     initializing any client. Local dev,
                                     CI, and tests stay silent.
      - RAILWAY_GIT_COMMIT_SHA     — Railway build-time env var. Used as
                                     the Sentry release tag (short form).

    Args:
      environment: 'web' (default) uses FlaskIntegration — used by the
                   gunicorn web process on startup. 'worker' swaps in
                   CeleryIntegration instead — called from worker_process_init
                   in backend/celery_app.py so each forked worker gets the
                   right integration. All other Sentry behaviour is identical.

    Configuration (hardcoded — intentional, not env-driven):
      - environment="production"   — if/when staging is added, it gets
                                     its own separate DSN, not an env
                                     override here.
      - traces_sample_rate=0.05    — 5% APM sampling default. Closes audit
                                     MAJOR #14 (Codex 2026-05-06). Override
                                     via SENTRY_TRACES_SAMPLE_RATE env var
                                     (range [0.0, 1.0]; invalid values fall
                                     back to 0.05 with a warning). 0.0 maps
                                     to None for full disable per Sentry
                                     docs.
      - before_send_transaction    — APM transaction scrubber (round-1
                                     Codex CRITICAL fold). The error-event
                                     before_send hook does NOT see
                                     transactions; this hook does the same
                                     request/user scrubbing for them.
      - max_request_body_size="never" — defense-in-depth: prevents the
                                     Flask integration from capturing
                                     request bodies on transactions before
                                     before_send_transaction sees them.
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
        import werkzeug.exceptions as wex
        if environment == 'worker':
            from sentry_sdk.integrations.celery import CeleryIntegration
            integration = CeleryIntegration()
        else:
            from sentry_sdk.integrations.flask import FlaskIntegration
            integration = FlaskIntegration(transaction_style="endpoint")
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
            traces_sample_rate=_resolve_traces_sample_rate(),
            send_default_pii=False,
            # FERPA: drop all stack-frame locals from events. Without this,
            # Sentry's default is to include frame `vars` at capture time,
            # which leaks student names / SIS IDs / answers anywhere in the
            # grading and roster code paths (assistant_tools.py, portal_grading.py,
            # etc.). Scrubbing by allowlist is defense in depth on top of this.
            include_local_variables=False,
            integrations=[integration],
            before_send=before_send,
            before_send_transaction=before_send_transaction,
            # FERPA defense-in-depth: prevent the Flask integration from
            # capturing request bodies on transactions (audit MAJOR #14
            # Codex round-1 CRITICAL). before_send_transaction is the
            # primary scrub; this stops body capture at the source.
            max_request_body_size="never",
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
    logger.info("Sentry initialized (release=%s, environment=%s)", release, environment)
