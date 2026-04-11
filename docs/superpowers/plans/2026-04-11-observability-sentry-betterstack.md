# Observability v1 Implementation Plan — Sentry + BetterStack

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Graider its first production observability layer — Sentry error tracking with PII-scrubbed capture, plus BetterStack uptime monitoring with a public status page — so operational failures become visible before districts notice.

**Architecture:** Two independent sub-projects shipped in one plan/PR but deployable and reversible separately. Sub-project A (Sentry) is all Python code in a new `backend/observability/` package, wired into the existing Flask app via `init_sentry()` at app startup and a `@critical_path` decorator on 5 high-risk entrypoints. Sub-project B (BetterStack) is pure runbook — web UI configuration plus one Vercel DNS record. Both sub-projects use the same Slack webhook + on-call policy for alert routing.

**Tech Stack:** Python 3.14, `sentry-sdk[flask]>=2.0`, existing Flask backend, BetterStack (Team tier, $10/mo), Slack webhook, Railway auto-deploy, Vercel DNS

**Feature branch:** `feat/observability-sentry` (already checked out)

**Spec:** `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md` (commits `d9e5767`, `a84b773`, `664b1fc`)

---

## Scope summary

This plan covers Tier 1 #3 sub-projects A and B from the district production reliability roadmap. It does NOT cover:

- **Performance monitoring / APM tracing** — disabled via `traces_sample_rate=0.0`, deferred to a future plan
- **Business metrics dashboards** — Tier 1 #3 sub-project C, separate plan
- **Structured logging migration** — Tier 1 #3 sub-project D, separate plan
- **Staging environment** — no staging exists today; if added later, a second Sentry DSN with `environment="staging"` is the path, not env-var override of the production DSN

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `sentry-sdk[flask]>=2.0` |
| `backend/observability/__init__.py` | Create | Re-export `init_sentry`, `critical_path` |
| `backend/observability/sentry.py` | Create | Core module: `_resolve_user_id`, `_scrub_request`, `_scrub_frame_locals`, `before_send`, `critical_path`, `init_sentry` |
| `tests/test_sentry_scrub.py` | Create | 11 unit tests pinning `before_send` contract |
| `tests/test_critical_path.py` | Create | 3 unit tests pinning decorator contract |
| `backend/app.py` | Modify | Call `init_sentry()` after app init (line 81); add `FORCE_HEALTHZ_FAIL` short-circuit at top of `/healthz` (line 3389); add `SENTRY_TEST_ROUTE_ENABLED` gated `/_debug/sentry-boom` route |
| `backend/services/portal_grading.py` | Modify | Import `critical_path`; decorate `run_portal_grading_thread` (line 207) |
| `backend/routes/student_account_routes.py` | Modify | Import `critical_path`; decorate `submit_student_work` (line 737) and `save_submission_draft` (line 1224) |
| `backend/routes/student_portal_routes.py` | Modify | Import `critical_path`; decorate `publish_assessment` (line 203) and `submit_assessment` (line 697) |
| `docs/observability.md` | Create | Runbook: alert routing, feature flags reference, post-rollout cleanup checklist, quarterly drill procedure, rollback, holiday override |

**Zero modifications to:** `backend/retry.py`, `backend/supabase_client.py`, `backend/supabase_resilient.py`, any grading engine, any other route file.

---

## Task 1: Add sentry-sdk dependency and scaffold the observability package

**Files:**
- Modify: `requirements.txt`
- Create: `backend/observability/__init__.py`
- Create: `backend/observability/sentry.py` (stub — will be filled in by Tasks 2 and 3)

- [ ] **Step 1: Add sentry-sdk to requirements.txt**

Append `sentry-sdk[flask]>=2.0` as a new line in `requirements.txt`. The file currently lists `flask>=2.0.0`, `flask-cors>=3.0.0`, `flask-wtf>=1.2.0`. Add the new line in the same Flask-related block.

Use Edit with `old_string` = `flask-wtf>=1.2.0` and `new_string` = `flask-wtf>=1.2.0\nsentry-sdk[flask]>=2.0`.

- [ ] **Step 2: Install the dependency into the venv**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && pip install "sentry-sdk[flask]>=2.0" 2>&1 | tail -5
```

Expected output: `Successfully installed sentry-sdk-2.x.x` (exact version may vary). If already installed, pip reports `Requirement already satisfied`.

- [ ] **Step 3: Verify the import works**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "import sentry_sdk; from sentry_sdk.integrations.flask import FlaskIntegration; print('OK', sentry_sdk.VERSION)"
```

Expected: `OK 2.x.x`.

- [ ] **Step 4: Create the package scaffold**

Create `backend/observability/__init__.py` with content:

```python
"""Observability package for Graider.

Currently provides Sentry error tracking with PII scrubbing and the
@critical_path decorator for tagging high-risk entrypoints.

See docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md
and docs/observability.md for the full design and runbook.
"""

from backend.observability.sentry import init_sentry, critical_path

__all__ = ["init_sentry", "critical_path"]
```

Create `backend/observability/sentry.py` with a minimal stub so the package imports cleanly:

```python
"""Sentry error tracking for Graider — PII-scrubbed, FERPA-safe.

This module is populated incrementally by subsequent plan tasks.
Tasks 2-3 fill in before_send and _resolve_user_id.
Task 4 fills in critical_path.
Task 5 fills in init_sentry.
"""


def init_sentry() -> None:
    """Stub — populated by Task 5."""
    pass


def critical_path(fn):
    """Stub — populated by Task 4."""
    return fn
```

- [ ] **Step 5: Verify the package imports**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "from backend.observability import init_sentry, critical_path; init_sentry(); print('OK')"
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt backend/observability/__init__.py backend/observability/sentry.py
git commit -m "$(cat <<'EOF'
feat: scaffold observability package (sentry-sdk dependency)

Task 1 of the observability v1 plan. Adds sentry-sdk[flask] to
requirements.txt and creates an empty backend/observability/ package
that will be filled in by subsequent tasks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Write failing tests for the PII scrubber

**Files:**
- Create: `tests/test_sentry_scrub.py`

This task writes all 11 scrubber tests. They will all fail because Task 1's stub `backend/observability/sentry.py` doesn't define `before_send` yet. Task 3 implements it and makes them pass.

- [ ] **Step 1: Create `tests/test_sentry_scrub.py`**

Create the file with this exact content:

```python
"""Tests for backend/observability/sentry.py — PII scrubbing contract.

These tests pin the contract that the Sentry before_send hook:
- Drops 4xx errors entirely
- Strips request bodies, cookies, auth headers, secret query params
- Replaces PII stack frame locals with "[PII-scrubbed]"
- Hashes the Flask g.user_id into a 12-char identifier
- Never crashes when called outside a Flask request context
  (the background grading thread is exactly such a context)
"""

import hashlib
import pytest


def _make_event(**kwargs):
    """Build a minimal Sentry-shaped event dict for testing."""
    event = {
        "exception": {"values": [{"type": "RuntimeError", "value": "test error"}]},
        "user": {},
    }
    event.update(kwargs)
    return event


class TestBeforeSend:
    """Tests for before_send PII scrubber."""

    def test_4xx_dropped(self):
        from backend.observability.sentry import before_send
        event = _make_event(exception={"values": [{"type": "BadRequest", "value": "bad"}]})
        assert before_send(event, {}) is None

    def test_request_data_stripped(self):
        from backend.observability.sentry import before_send
        event = _make_event(request={"data": "sensitive stuff", "method": "POST"})
        result = before_send(event, {})
        assert result is not None
        assert "data" not in result["request"]
        assert result["request"]["method"] == "POST"

    def test_authorization_header_redacted(self):
        from backend.observability.sentry import before_send
        event = _make_event(request={"headers": {"Authorization": "Bearer secret"}})
        result = before_send(event, {})
        assert result["request"]["headers"]["Authorization"] == "[Filtered]"

    def test_cookies_removed(self):
        from backend.observability.sentry import before_send
        event = _make_event(request={"cookies": {"session": "xxx"}})
        result = before_send(event, {})
        assert "cookies" not in result["request"]

    def test_query_token_stripped(self):
        from backend.observability.sentry import before_send
        event = _make_event(request={"query_string": "api_key=xxx&foo=bar"})
        result = before_send(event, {})
        query = result["request"]["query_string"]
        assert "api_key=[Filtered]" in query
        assert "foo=bar" in query

    def test_frame_locals_scrubbed(self):
        from backend.observability.sentry import before_send
        event = _make_event(exception={"values": [{
            "type": "RuntimeError",
            "value": "test",
            "stacktrace": {"frames": [{"vars": {
                "student_name": "Alice",
                "answers": {"q1": "yes"},
                "safe_value": 42,
            }}]},
        }]})
        result = before_send(event, {})
        frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        assert frame_vars["student_name"] == "[PII-scrubbed]"
        assert frame_vars["answers"] == "[PII-scrubbed]"
        assert frame_vars["safe_value"] == 42

    def test_frame_locals_non_pii_preserved(self):
        from backend.observability.sentry import before_send
        event = _make_event(exception={"values": [{
            "type": "RuntimeError",
            "value": "test",
            "stacktrace": {"frames": [{"vars": {
                "attempt_number": 2,
                "content_id": "abc",
                "teacher_id": "xyz",
            }}]},
        }]})
        result = before_send(event, {})
        frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        assert frame_vars["attempt_number"] == 2
        assert frame_vars["content_id"] == "abc"
        assert frame_vars["teacher_id"] == "xyz"

    def test_missing_request_context_ok(self):
        """Event with no request key — scrubber should not crash."""
        from backend.observability.sentry import before_send
        event = _make_event()  # no "request" key at all
        result = before_send(event, {"request": None})
        assert result is not None

    def test_teacher_id_hashed_when_present(self):
        from backend.observability.sentry import before_send
        from flask import Flask, g
        app = Flask(__name__)
        with app.test_request_context():
            g.user_id = "teacher-abc"
            event = _make_event()
            result = before_send(event, {})
        expected = hashlib.sha256(b"teacher-abc").hexdigest()[:12]
        assert result["user"]["id"] == expected

    def test_anonymous_user_when_gid_missing(self):
        from backend.observability.sentry import before_send
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            # No g.user_id set
            event = _make_event()
            result = before_send(event, {})
        assert result is not None
        assert result["user"]["id"] == "anonymous"

    def test_scrub_outside_request_context_does_not_crash(self):
        """Background grading thread case — no Flask context active.

        This test pins Codex's catch: touching flask.g without a request
        context raises RuntimeError, which would crash the scrubber on
        the very grading-worker failures we most need to capture.
        """
        from backend.observability.sentry import before_send
        # NO Flask app context / request context active here.
        event = _make_event()
        result = before_send(event, {})
        assert result is not None
        assert result["user"]["id"] == "anonymous"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sentry_scrub.py -v 2>&1 | tail -30
```

Expected: All 11 tests FAIL with `ImportError` or `AttributeError` on `before_send` — the stub `backend/observability/sentry.py` doesn't define it yet.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_sentry_scrub.py
git commit -m "$(cat <<'EOF'
test: failing scrubber tests for backend/observability/sentry.py

11 tests pinning the before_send PII contract. They fail against the
Task 1 stub; Task 3 will implement the scrubber and make them pass.

Includes test_scrub_outside_request_context_does_not_crash which
pins Codex's catch — the scrubber must never touch flask.g without
gating on has_request_context(), otherwise background grading
thread failures crash the hook and get silently dropped.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Implement the PII scrubber

**Files:**
- Modify: `backend/observability/sentry.py`

Replace the Task 1 stub with the full scrubber implementation. Task 2's tests should all pass after this task.

- [ ] **Step 1: Rewrite `backend/observability/sentry.py`**

Replace the full contents with:

```python
"""Sentry error tracking for Graider — PII-scrubbed, FERPA-safe.

Exposes:
  - before_send(event, hint)    → Sentry hook that scrubs PII
  - critical_path               → decorator (stub, populated in Task 4)
  - init_sentry()               → client init (stub, populated in Task 5)

See docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md.
"""

import hashlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# PII field names scrubbed from stack frame locals.
# Keep this list in sync with docs/observability.md § "Known noise sources".
_PII_LOCAL_NAMES = frozenset({
    "student_name", "student_email", "answers", "draft_answers",
    "student_id_number", "submission_row", "results", "feedback",
    "first_name", "last_name", "row", "s", "sdata", "assessment",
    "assessment_content", "student_row", "assessment_data",
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
    """Return True if the event represents a 4xx client error that should be dropped."""
    try:
        exceptions = event.get("exception", {}).get("values", [])
        for exc in exceptions:
            if exc.get("type", "") in _CLIENT_ERROR_TYPES:
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
    """Stub — populated by Task 4."""
    return fn


def init_sentry() -> None:
    """Stub — populated by Task 5."""
    pass
```

- [ ] **Step 2: Run the scrubber tests**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sentry_scrub.py -v 2>&1 | tail -30
```

Expected: All 11 tests PASS.

If any test fails, read the failure message carefully. Common issues:
- `test_scrub_outside_request_context_does_not_crash` fails with `RuntimeError: Working outside of application context` → the `_resolve_user_id` `has_request_context` gate is missing or not working.
- `test_teacher_id_hashed_when_present` fails → hash computation mismatch. Verify `hashlib.sha256(b"teacher-abc").hexdigest()[:12]` matches.
- `test_frame_locals_scrubbed` fails → the `_scrub_frame_locals` loop isn't mutating the frame vars in place. Check that the `.get("vars")` returns the actual dict reference.

- [ ] **Step 3: Commit**

```bash
git add backend/observability/sentry.py
git commit -m "$(cat <<'EOF'
feat: implement PII scrubber for Sentry before_send

Defines _resolve_user_id, _scrub_request, _scrub_frame_locals, and
before_send in backend/observability/sentry.py. All 11 tests from
Task 2 now pass.

_resolve_user_id is defensively guarded — it calls flask.g only
after has_request_context() returns True, and wraps the getattr in
try/except RuntimeError as a second belt. A crash in the scrubber
would cause Sentry to silently drop the event, which is the exact
opposite of what we want for background-thread failures.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Implement the @critical_path decorator

**Files:**
- Create: `tests/test_critical_path.py`
- Modify: `backend/observability/sentry.py` (replace the stub decorator with the real one)

- [ ] **Step 1: Write failing tests**

Create `tests/test_critical_path.py`:

```python
"""Tests for @critical_path decorator in backend/observability/sentry.py."""

from unittest.mock import patch, MagicMock
import pytest


class TestCriticalPath:
    def test_decorator_sets_severity_tag(self):
        """When a decorated fn raises, the Sentry scope should carry severity=critical."""
        from backend.observability.sentry import critical_path

        mock_scope = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_scope)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("sentry_sdk.push_scope", return_value=mock_ctx) as mock_push:
            @critical_path
            def boom():
                raise RuntimeError("test failure")

            with pytest.raises(RuntimeError, match="test failure"):
                boom()

        mock_push.assert_called_once()
        mock_scope.set_tag.assert_called_with("severity", "critical")

    def test_decorator_preserves_return_value(self):
        """Non-raising decorated fn returns its value unchanged."""
        from backend.observability.sentry import critical_path

        @critical_path
        def greet(name):
            return f"hello {name}"

        assert greet("world") == "hello world"

    def test_decorator_is_noop_when_sentry_uninitialized(self):
        """Decorator must not crash when Sentry has no configured client.

        sentry_sdk.push_scope() is safe to call with no active client —
        it returns a dummy Hub scope. This test verifies the decorator
        runs normally in that state (which is the local-dev / CI
        default because Task 1 tests never call init_sentry()).
        """
        from backend.observability.sentry import critical_path

        @critical_path
        def answer():
            return 42

        # No init_sentry() called anywhere in the test.
        assert answer() == 42
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_critical_path.py -v 2>&1 | tail -20
```

Expected: `test_decorator_sets_severity_tag` FAILS because the Task 1 stub `critical_path` just returns `fn` unchanged (no scope manipulation). The other two tests pass by accident because they don't actually verify scope behavior — that's fine, TDD lets them pass or fail as they will.

- [ ] **Step 3: Replace the stub decorator with the real implementation**

In `backend/observability/sentry.py`, find the stub at the bottom:

```python
def critical_path(fn):
    """Stub — populated by Task 4."""
    return fn
```

Replace it with:

```python
def critical_path(fn):
    """Decorator — tag escaping exceptions with severity=critical.

    Wraps the decorated callable in a Sentry scope that sets
    `severity=critical`. Any unhandled exception that escapes the
    function carries this tag, which the Sentry issue-alert rules
    use to trigger SMS/voice escalation via BetterStack.

    Apply only to outermost entrypoints — never to inner helpers
    called from within an already-decorated function. The 5 target
    functions are documented in docs/observability.md § "Critical-path
    tag convention".

    Safe when Sentry is uninitialized: sentry_sdk.push_scope() is a
    no-op on the default dummy hub, so local dev / CI / tests see
    this decorator as transparent.
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("severity", "critical")
            return fn(*args, **kwargs)

    return wrapper
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_critical_path.py -v 2>&1 | tail -20
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Run the full observability test suite together**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sentry_scrub.py tests/test_critical_path.py -v 2>&1 | tail -25
```

Expected: 14 tests pass (11 scrub + 3 decorator).

- [ ] **Step 6: Commit**

```bash
git add tests/test_critical_path.py backend/observability/sentry.py
git commit -m "$(cat <<'EOF'
feat: implement @critical_path decorator

Wraps a callable in a Sentry scope that sets severity=critical on any
escaping exception. Applied in Task 8 to the 5 high-risk entrypoints
(grading worker + 4 student-facing write routes).

Decorator is a no-op when Sentry is uninitialized — sentry_sdk's Hub
returns a dummy scope on the default uninitialized state, so local
dev, CI, and tests run transparently without needing a DSN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Implement init_sentry() and wire it into backend/app.py

**Files:**
- Modify: `backend/observability/sentry.py` (replace init_sentry stub)
- Modify: `backend/app.py` (add init_sentry call after app creation)

- [ ] **Step 1: Replace the init_sentry stub**

In `backend/observability/sentry.py`, find the stub:

```python
def init_sentry() -> None:
    """Stub — populated by Task 5."""
    pass
```

Replace it with:

```python
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
      - ignore_errors=[4xx]        — backstop for the rare case where
                                     code explicitly raises a Werkzeug
                                     HTTP exception inside a try/except
                                     (Flask's middleware normally converts
                                     these to responses before they
                                     reach Sentry).
    """
    import os

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("SENTRY_DSN not set; Sentry disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        import werkzeug.exceptions as wex
    except ImportError as exc:
        logger.warning("sentry-sdk unavailable; Sentry disabled: %s", exc)
        return

    release = os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown")[:7]

    sentry_sdk.init(
        dsn=dsn,
        environment="production",
        release=release,
        traces_sample_rate=0.0,
        send_default_pii=False,
        integrations=[FlaskIntegration(transaction_style="url")],
        before_send=before_send,
        ignore_errors=[
            wex.BadRequest,
            wex.Unauthorized,
            wex.Forbidden,
            wex.NotFound,
            wex.MethodNotAllowed,
        ],
    )
    logger.info("Sentry initialized (release=%s)", release)
```

- [ ] **Step 2: Wire init_sentry() into backend/app.py**

`backend/app.py` creates the Flask app on line 81:

```python
app = Flask(__name__, static_folder='static', static_url_path='')
```

Add the init call immediately after, before the CORS setup on line 83. Use Edit with `old_string`:

```python
app = Flask(__name__, static_folder='static', static_url_path='')
```

and `new_string`:

```python
app = Flask(__name__, static_folder='static', static_url_path='')

# Initialize Sentry error tracking. No-op if SENTRY_DSN is unset (local dev, CI).
from backend.observability import init_sentry
init_sentry()
```

- [ ] **Step 3: Verify the app still imports cleanly without a DSN**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import os
os.environ.pop('SENTRY_DSN', None)  # ensure it's unset
from backend.app import app
print('App imported OK, routes:', len(list(app.url_map.iter_rules())))
"
```

Expected: `App imported OK, routes: <some number>`. No errors, no Sentry init messages.

- [ ] **Step 4: Verify init_sentry is called on import (log check)**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import logging
logging.basicConfig(level=logging.INFO)
import os
os.environ.pop('SENTRY_DSN', None)
from backend.app import app
" 2>&1 | grep -i sentry
```

Expected: `INFO:backend.observability.sentry:SENTRY_DSN not set; Sentry disabled`.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -15
```

Expected: All tests pass (1028+ from the Tier 1 #2 work, plus the 14 new observability tests). If any test fails, read the failure carefully — it's likely because `init_sentry()` is being called during test collection and is doing something unexpected. The test suite should NEVER set `SENTRY_DSN`, so `init_sentry()` should return immediately.

- [ ] **Step 6: Commit**

```bash
git add backend/observability/sentry.py backend/app.py
git commit -m "$(cat <<'EOF'
feat: wire Sentry client init into Flask app startup

init_sentry() reads SENTRY_DSN from the environment and, if set,
configures the Sentry SDK with Flask integration, our PII scrubber
(before_send hook), and 4xx ignore list. If SENTRY_DSN is unset, the
function is a hard no-op — local dev, CI, and tests stay silent.

backend/app.py now calls init_sentry() immediately after creating the
Flask app and before CORS is installed. Railway production will read
SENTRY_DSN from its env vars after Task 11 configures them.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add the SENTRY_TEST_ROUTE_ENABLED debug route

**Files:**
- Modify: `backend/app.py`

This task adds a `/_debug/sentry-boom` route that deliberately raises exceptions for production verification. The route is **only registered** when the env var `SENTRY_TEST_ROUTE_ENABLED=1` is set at app startup. Without the env var, the route returns 404. This avoids the security risk of using Flask's `DEBUG=1` flag, which would enable the Werkzeug interactive debugger.

- [ ] **Step 1: Find a good insertion point**

The debug route should be added near the existing `/healthz` route for discoverability. `/healthz` is defined at `backend/app.py:3388`.

Use Read to look at lines 3385-3420 to see the surrounding context and pick an insertion point immediately after the `/healthz` function closes (around line 3432 based on the Tier 1 #2 work that just shipped).

- [ ] **Step 2: Add the debug route**

Use Edit with `old_string` being the last line of the `/healthz` function:

```python
    return jsonify(status)


# ══════════════════════════════════════════════════════════════
# STATIC FILE SERVING
```

and `new_string` being the same content with the debug route inserted between:

```python
    return jsonify(status)


# ══════════════════════════════════════════════════════════════
# SENTRY DEBUG ROUTE (guarded by SENTRY_TEST_ROUTE_ENABLED)
# ══════════════════════════════════════════════════════════════
# Used ONLY during post-deploy production verification of Sentry.
# The route is only registered when SENTRY_TEST_ROUTE_ENABLED=1 is set
# in the env at app startup. Unset (the default), it 404s.
#
# IMPORTANT: Do NOT use FLASK_DEBUG or DEBUG for this gate. Those env
# vars enable the Werkzeug interactive debugger, which allows anyone
# who hits an error page to execute arbitrary Python on the server —
# a severe production security hole. Use SENTRY_TEST_ROUTE_ENABLED,
# which only controls this single route.
#
# Post-rollout cleanup (see docs/observability.md): delete this block
# entirely in a follow-up PR within 7 days of sub-project A merging.
if os.getenv("SENTRY_TEST_ROUTE_ENABLED") == "1":
    from backend.observability import critical_path as _critical_path_for_debug

    @app.route('/_debug/sentry-boom')
    def _debug_sentry_boom():
        severity = request.args.get("severity", "normal")
        if severity == "critical":
            @_critical_path_for_debug
            def _raise():
                raise RuntimeError("sentry critical smoke test")
            _raise()
        else:
            raise RuntimeError("sentry normal smoke test")


# ══════════════════════════════════════════════════════════════
# STATIC FILE SERVING
```

- [ ] **Step 3: Verify the app still imports cleanly**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import os
os.environ.pop('SENTRY_TEST_ROUTE_ENABLED', None)
from backend.app import app
routes = [str(r) for r in app.url_map.iter_rules() if 'debug' in str(r).lower()]
print('debug routes (should be empty):', routes)
"
```

Expected: `debug routes (should be empty): []` — the route is not registered when the env var is unset.

- [ ] **Step 4: Verify the route is registered when the env var IS set**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import os
os.environ['SENTRY_TEST_ROUTE_ENABLED'] = '1'
# Force re-import of backend.app to pick up the env var
import importlib
import backend.app
importlib.reload(backend.app)
from backend.app import app
routes = [str(r) for r in app.url_map.iter_rules() if 'debug' in str(r).lower()]
print('debug routes (should include /_debug/sentry-boom):', routes)
"
```

Expected: `debug routes (should include /_debug/sentry-boom): ['/_debug/sentry-boom']`.

- [ ] **Step 5: Run the full test suite**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass. No test should trigger the debug route because the env var is not set in the test environment.

- [ ] **Step 6: Commit**

```bash
git add backend/app.py
git commit -m "$(cat <<'EOF'
feat: add SENTRY_TEST_ROUTE_ENABLED debug route

Adds /_debug/sentry-boom for post-deploy Sentry verification. The
route is only registered when SENTRY_TEST_ROUTE_ENABLED=1 is set in
the env at app startup — default production state is 404.

Uses a dedicated feature flag instead of FLASK_DEBUG / DEBUG. Those
env vars enable the Werkzeug interactive debugger, which is a remote
code execution vector if a user ever hits a 500. SENTRY_TEST_ROUTE_ENABLED
only controls the registration of this one route.

Post-rollout cleanup: delete this block entirely in a follow-up PR
within 7 days of sub-project A merging. The env-var gate means the
route is 404 without the flag even if the code is still present, so
the cleanup PR is about code hygiene, not security.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Add the FORCE_HEALTHZ_FAIL short-circuit to /healthz

**Files:**
- Modify: `backend/app.py`

This task adds a feature flag that makes `/healthz` return 503 without touching Supabase, used for safe alert drills. Student and teacher API calls go through `get_supabase()` directly, not `/healthz`, so this flag has **zero customer impact** while exercising the full BetterStack alert pipeline.

- [ ] **Step 1: Read the current /healthz implementation**

The `/healthz` route is at `backend/app.py:3388-3432` (approximately — may have shifted by Task 6). Use Read or Grep to find the current line range and confirm the function signature.

The current implementation (post Tier 1 #2) starts with:

```python
@app.route('/healthz')
def healthz():
    """General health check for Railway load balancer."""
    status = {"app": "ok"}
    # Supabase — raw httpx GET with a short timeout.
    # ...
```

- [ ] **Step 2: Add the short-circuit at the top of the function**

Use Edit with `old_string`:

```python
@app.route('/healthz')
def healthz():
    """General health check for Railway load balancer."""
    status = {"app": "ok"}
```

and `new_string`:

```python
@app.route('/healthz')
def healthz():
    """General health check for Railway load balancer."""
    # Alert-drill short-circuit — exercises the full BetterStack alert
    # pipeline without touching Supabase, so student/teacher API traffic
    # is unaffected during drills. See docs/observability.md § "Quarterly
    # drill procedure" for the full runbook.
    if os.getenv('FORCE_HEALTHZ_FAIL') == '1':
        return jsonify({"app": "ok", "supabase": "drill_forced_failure"}), 503

    status = {"app": "ok"}
```

- [ ] **Step 3: Verify the short-circuit fires when the env var is set**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import os
os.environ['FORCE_HEALTHZ_FAIL'] = '1'
from backend.app import app
with app.test_client() as c:
    resp = c.get('/healthz')
    print('STATUS:', resp.status_code)
    print('BODY:', resp.get_json())
"
```

Expected: `STATUS: 503` and `BODY: {"app":"ok","supabase":"drill_forced_failure"}`.

- [ ] **Step 4: Verify the short-circuit does NOT fire by default**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import os
os.environ.pop('FORCE_HEALTHZ_FAIL', None)
from dotenv import load_dotenv
load_dotenv('.env', override=True)
from backend.app import app
with app.test_client() as c:
    resp = c.get('/healthz')
    print('STATUS:', resp.status_code)
    print('BODY:', resp.get_json())
"
```

Expected: `STATUS: 200` and `BODY` contains `"supabase":"ok"` (or whatever the real Supabase status is). If Supabase is unreachable from the local machine, you may see `"supabase":"error"` — that's fine for this test, the point is the code didn't hit the drill short-circuit.

- [ ] **Step 5: Run the full test suite**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app.py
git commit -m "$(cat <<'EOF'
feat: add FORCE_HEALTHZ_FAIL short-circuit for safe alert drills

When FORCE_HEALTHZ_FAIL=1 is set in the env, /healthz returns 503
without touching Supabase. Used to exercise the BetterStack alert
pipeline during drills without affecting real student/teacher traffic
(which goes through get_supabase() directly, not /healthz).

Replaces the earlier draft spec's suggestion of corrupting SUPABASE_URL
during drills — that would have caused a real 3-15 minute outage for
every live district during each quarterly drill, which is unacceptable.
The feature flag gives the same alert signal with zero customer impact.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Apply @critical_path to the 5 target functions

**Files:**
- Modify: `backend/services/portal_grading.py` (1 decoration at line 207)
- Modify: `backend/routes/student_account_routes.py` (2 decorations at lines 737 and 1224)
- Modify: `backend/routes/student_portal_routes.py` (2 decorations at lines 203 and 697)

Each file gets the same two changes: an `import` at the top (grouped with existing `from backend.*` imports), and an `@critical_path` decorator above each target function.

- [ ] **Step 1: Decorate `run_portal_grading_thread` in `portal_grading.py`**

Add the import near the top of `backend/services/portal_grading.py`, alongside the other `from backend.*` imports. Use Read to find the import block, then Edit.

Then decorate the function. The function signature at line 207 is:

```python
def run_portal_grading_thread(submission_id, assessment, answers, student_info,
```

(Spans multiple lines for the parameter list.)

Use Edit with `old_string`:

```python
def run_portal_grading_thread(submission_id, assessment, answers, student_info,
```

and `new_string`:

```python
@critical_path
def run_portal_grading_thread(submission_id, assessment, answers, student_info,
```

- [ ] **Step 2: Decorate `submit_student_work` and `save_submission_draft` in `student_account_routes.py`**

Add `from backend.observability import critical_path` near the top of the file, grouped with the existing `from backend.*` imports.

Find `submit_student_work` at line 737. The line before the `def` will be an `@student_account_bp.route(...)` decorator. Add `@critical_path` immediately above the `def` (between the Flask route decorator and the function definition).

Use Edit with `old_string`:

```python
def submit_student_work(content_id):
```

and `new_string`:

```python
@critical_path
def submit_student_work(content_id):
```

**Note:** `@critical_path` must come AFTER the `@student_account_bp.route` and other Flask decorators in source order (so critical_path runs innermost, wrapping the actual function body). Don't place it above the `@student_account_bp.route` line.

Do the same for `save_submission_draft` at line 1224 (approximate; may shift after the first edit).

- [ ] **Step 3: Decorate `publish_assessment` and `submit_assessment` in `student_portal_routes.py`**

Add the same import. Find `publish_assessment` at line 203 and `submit_assessment` at line 697. Apply the same decorator pattern — `@critical_path` between the Flask route decorator and the `def` line.

- [ ] **Step 4: Verify all 5 decorations are in place**

```bash
cd /Users/alexc/Downloads/Graider && grep -B1 "^def run_portal_grading_thread\|^def submit_student_work\|^def save_submission_draft\|^def publish_assessment\|^def submit_assessment" backend/services/portal_grading.py backend/routes/student_account_routes.py backend/routes/student_portal_routes.py
```

Expected: Every match has `@critical_path` on the line immediately before the `def`.

- [ ] **Step 5: Verify the files still import cleanly**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
from backend.services.portal_grading import run_portal_grading_thread
from backend.routes.student_account_routes import submit_student_work, save_submission_draft
from backend.routes.student_portal_routes import publish_assessment, submit_assessment
print('All 5 functions import OK')
print('  run_portal_grading_thread:', run_portal_grading_thread.__name__)
print('  submit_student_work:', submit_student_work.__name__)
"
```

Expected: `All 5 functions import OK` plus the two name prints. The `@functools.wraps(fn)` inside `critical_path` means the wrapped function keeps its original `__name__`.

- [ ] **Step 6: Run the full test suite**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass. The decorators are no-ops when Sentry is uninitialized (which is always true in tests).

- [ ] **Step 7: Commit**

```bash
git add backend/services/portal_grading.py backend/routes/student_account_routes.py backend/routes/student_portal_routes.py
git commit -m "$(cat <<'EOF'
feat: tag 5 critical entrypoints with @critical_path

Applies the @critical_path decorator from backend/observability to the
5 high-risk entrypoints identified in the spec:

  - run_portal_grading_thread  (backend/services/portal_grading.py)
  - submit_student_work        (backend/routes/student_account_routes.py)
  - save_submission_draft      (backend/routes/student_account_routes.py)
  - publish_assessment         (backend/routes/student_portal_routes.py)
  - submit_assessment          (backend/routes/student_portal_routes.py)

Each tagged function causes any escaping exception to carry the
severity=critical Sentry tag, which triggers the BetterStack on-call
SMS/voice escalation (3+ events in 5 minutes, per spec alert rule #5).

Decorators are only applied to outermost entrypoints, never to inner
helpers called from within already-decorated functions. Notably,
grade_multipass is NOT decorated because it's called from within
run_portal_grading_thread — tagging it would be redundant.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Write the observability runbook

**Files:**
- Create: `docs/observability.md`

This is the single source of truth for on-call behavior. It's a runbook, not a design doc — future operators read it when an alert fires.

- [ ] **Step 1: Create `docs/observability.md`**

Create the file with this exact content:

```markdown
# Observability Runbook

Graider's production observability stack. This is the on-call document —
when an alert fires, start here.

**Stack:**
- **Sentry Cloud** (Developer / free tier) — error tracking with PII scrubbing
- **BetterStack** (Team tier, $10/mo) — uptime monitoring + public status page + on-call escalation
- **Slack** `#alerts` channel — real-time alert feed
- **Public status page:** https://status.graider.live

**Design spec:** `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md`

---

## Alert routing rules

| # | Source | Condition | Action | Channel | Severity |
|---|---|---|---|---|---|
| 1 | BetterStack | `/healthz` returns non-200 for **2 consecutive probes** (2 min) | Incident + alert | **Slack** 9am-6pm ET; **Slack → SMS after 5min → voice after 10min** outside business hours | Critical |
| 2 | BetterStack | SSL cert < 30 days to expiry | Email digest | Email only | Info |
| 3 | BetterStack | Domain < 30 days to expiry | Email digest | Email only | Info |
| 4 | Sentry | New issue type first seen | Issue alert | Slack only, any hour | Info |
| 5 | Sentry | Issue tagged `severity=critical` fires **≥3 events within 5 minutes** | Issue alert | **Slack + SMS + voice** via BetterStack on-call | Critical |
| 6 | Sentry | Any issue fires **≥25 events within 10 minutes** affecting **≥5 distinct users** | Issue alert | Slack during business hours; Slack + SMS after-hours | High |
| 7 | Sentry | 4xx errors (`BadRequest`, `Unauthorized`, `Forbidden`, `NotFound`, `MethodNotAllowed`) | **Dropped in `before_send`** — never sent | n/a | n/a |
| 8 | Sentry | Any event from `environment != production` | **Dropped** — local dev is silent | n/a | n/a |

**Business hours:** 09:00-18:00 America/New_York, Monday-Friday.

**Rule 5/6 user-grouping note:** Sentry groups events by `user.id`, which our scrubber sets to either a 12-char sha256 hash of `g.user_id` (when available) or the literal string `"anonymous"`. Anonymous events all bucket as a single user, so Rule 6's "≥5 distinct users" threshold will not fire for bugs that only affect unauthenticated paths. If a specific unauthenticated path needs direct paging, add it to the critical-path decorator list so it falls under Rule 5 instead.

---

## Critical-path tag convention

The `@critical_path` decorator from `backend/observability` tags any escaping exception with `severity=critical`, which is what Rule 5 above pages on. Currently decorated functions (5):

1. `run_portal_grading_thread` in `backend/services/portal_grading.py`
2. `submit_student_work` in `backend/routes/student_account_routes.py`
3. `save_submission_draft` in `backend/routes/student_account_routes.py`
4. `publish_assessment` in `backend/routes/student_portal_routes.py`
5. `submit_assessment` (join-code path) in `backend/routes/student_portal_routes.py`

**When to add a new critical path:**
- The function is an **outermost entrypoint** (Flask route handler or background worker entrypoint), not an inner helper.
- Failure in the function directly harms students (lost submissions, wrong grades) or loses teacher work (lost published content).
- Recovery requires a human — an auto-retry wouldn't fix it.

**When NOT to add a new critical path:**
- Inner helpers called from within an already-decorated function (they inherit the tag).
- Read-only routes (GET endpoints that just list data).
- Administrative routes that only affect the teacher, not students.
- Anything where silent failure is acceptable until the next deploy.

**How to add a new critical path:**
1. Import: `from backend.observability import critical_path`
2. Place `@critical_path` between the Flask route decorator and the `def` line (innermost position so it wraps the actual function body).
3. Update this list.

---

## Feature flags reference

All four env vars are default-off. Flip only when necessary, unset immediately after.

| Env var | Default | What it does | When to set it |
|---|---|---|---|
| `SENTRY_DSN` | Normally set in production | Enables Sentry. When unset, `init_sentry()` is a hard no-op — no client, no events sent. | Always set in Railway production. Unset to disable Sentry entirely. |
| `RAILWAY_GIT_COMMIT_SHA` | Auto-set by Railway | Used as the Sentry release tag (short form). Do not touch manually. | Never touch manually. |
| `SENTRY_TEST_ROUTE_ENABLED` | **Unset** | When `1`, registers `/_debug/sentry-boom` at app startup. Unset, the route is 404. | Temporarily during post-deploy production verification (step 3 of rollout). Always unset immediately after. **Do NOT confuse with `FLASK_DEBUG` / `DEBUG`** — those enable Werkzeug's interactive debugger and are a remote code execution vector. Never set them. |
| `FORCE_HEALTHZ_FAIL` | **Unset** | When `1`, `/healthz` returns 503 without touching Supabase. Used for alert drills. Student/teacher API traffic is unaffected because they call Supabase directly, not `/healthz`. | During alert drills. Always unset immediately after the drill completes. Safe to set during business hours — does not affect customer traffic. |

---

## Post-rollout cleanup checklist

The `/_debug/sentry-boom` route code block in `backend/app.py` is a temporary fixture for initial Sentry verification. It must be deleted in a follow-up PR within **7 days** of the observability v1 PR merging.

**Owner:** user
**Target date:** (merge date + 7 days)
**Cleanup PR title:** `chore: remove post-rollout sentry debug route`

The `FORCE_HEALTHZ_FAIL` short-circuit stays in place permanently — it's the drill mechanism and has zero customer impact when the flag is unset.

---

## Holiday / vacation override procedure

Before any multi-day absence, update the BetterStack on-call policy:

1. Log in to BetterStack → Policies → "Graider Solo"
2. Click "Schedule overrides"
3. Add an override for the absence window. Options:
   - **Suspend SMS/voice entirely** for the window (alerts still land in Slack, you check when you're back)
   - **Redirect to a backup contact** if you've arranged one (enter their phone + email)
4. Save. Overrides auto-revert at the end of the window.

**Who updates the schedule:** user (sole contact). No one else has access to BetterStack.

**If you forget to set an override and the pager fires during your absence:** the alert will attempt to call your phone. If unanswered, BetterStack logs the incident as "unacknowledged" but takes no further action. The incident persists in the BetterStack dashboard until you acknowledge it manually.

---

## Quarterly alert drill

Re-verify the alert pipeline on a calendar cadence: **first Monday of Jan, Apr, Jul, Oct.** This catches silent regressions like a disabled monitor, an expired Slack webhook, or a phone number change.

### Drill procedure (safe during business hours)

1. **Tell yourself you're starting a drill.** Post in `#alerts`: "Running quarterly alert drill — ignore incoming alerts for the next ~10 minutes." This prevents confusion if someone else is watching.
2. **Set the flag.** In Railway env vars, set `FORCE_HEALTHZ_FAIL=1`. Wait for Railway to auto-deploy (~60 seconds).
3. **Verify detection.** Within 3 minutes, BetterStack should observe 2 consecutive 503 responses from `/healthz` and create an incident. A Slack alert should land in `#alerts` immediately.
4. **Verify status page.** Visit `https://status.graider.live` and confirm the `/healthz` monitor shows as "down."
5. **(After-hours drill only) Verify SMS.** Wait 5 minutes after the Slack alert. If the drill is running outside business hours, SMS should arrive.
6. **(After-hours drill only) Verify voice.** Wait another 5 minutes (total 10 from the Slack alert). If unacknowledged, voice call should fire.
7. **Acknowledge the incident** in BetterStack.
8. **Unset the flag.** Remove `FORCE_HEALTHZ_FAIL` from Railway env vars (or set to `0`). Wait for auto-deploy.
9. **Verify recovery.** BetterStack should fire a "resolved" notification in Slack within 3 minutes of the auto-deploy completing.
10. **Log the drill.** Post in `#alerts`: "Drill complete. Detection: X minutes. Escalation: Y minutes. Recovery: Z minutes." Track any issues and fix them before the next quarterly drill.

**Customer impact during the drill: zero.** Student-facing and teacher-facing API routes call `get_supabase()` directly, which continues to work normally while `/healthz` is short-circuited.

---

## Rollback procedure

### Sub-project A (Sentry) — code-level

1. **Soft rollback (fastest):** remove `SENTRY_DSN` from Railway env vars. Wait for Railway to auto-deploy (~60 seconds). `init_sentry()` becomes a no-op and no more events are sent. The code stays in place.
2. **Hard rollback:** revert the merge PR via `gh pr revert <PR#>`. Auto-deploy removes all observability code. Zero residual state in the codebase. Sentry Cloud retains historical events but takes no further action.

### Sub-project B (BetterStack) — ops-level

1. **Disable monitors:** BetterStack UI → Monitors → disable each of the three monitors (`/healthz`, SSL cert, domain expiry). One click each.
2. **Delete status page subdomain:** remove the CNAME `status.graider.live` from Vercel DNS dashboard.
3. **Cancel subscription (optional):** BetterStack UI → Billing → cancel the Team tier plan to stop being billed.

No code changes are required to roll back Sub-project B — it's all configuration.

**DNS ownership note:** `graider.live` DNS is managed by **Vercel**, not Railway. The `status.graider.live` CNAME is added in the Vercel dashboard under the `graider.live` project. Do not touch the `app.graider.live` CNAME that points at Railway — that's a separate record and is production traffic.

---

## Known noise sources

Expected behavior that future operators should not waste time diagnosing:

- **4xx errors never reach Sentry.** The `before_send` scrubber drops them before they leave the app. If a teacher reports "I got a 400 error," that information is in Railway logs, not Sentry.
- **Anonymous events all bucket as one user.** Rule 6's "≥5 distinct users" threshold will never fire for bugs that only affect unauthenticated paths (the scrubber sets `user.id = "anonymous"` for all such events, so they collapse to one bucket). Fix: move the affected handler onto the critical-path list so Rule 5 catches it instead.
- **Non-production events are dropped.** Local dev and CI runs never hit Sentry because `init_sentry()` is a no-op when `SENTRY_DSN` is unset. If you're running locally and expect events to show up, they won't.
- **Frame locals named `assessment`, `row`, `s`, `sdata`, etc. are scrubbed.** The full list is in `backend/observability/sentry.py::_PII_LOCAL_NAMES`. If you're debugging a Sentry event and the locals look empty, they were scrubbed on purpose.

---

## Escalation contacts

**Primary on-call:** user (solo)
- Phone: (set in BetterStack on-call policy)
- Slack: (set in BetterStack on-call policy)
- Email: (set in BetterStack on-call policy)

**Backup contact:** none currently. If a backup is arranged in the future, update the BetterStack on-call policy AND this section.
```

- [ ] **Step 2: Verify the file renders cleanly**

```bash
cd /Users/alexc/Downloads/Graider && wc -l docs/observability.md && head -20 docs/observability.md
```

Expected: ~170 lines, first section is "Observability Runbook".

- [ ] **Step 3: Commit**

```bash
git add docs/observability.md
git commit -m "$(cat <<'EOF'
docs: observability runbook for on-call operators

Canonical source of truth for alert routing, critical-path tag
convention, feature flags reference, post-rollout cleanup, holiday
override procedure, quarterly drill procedure, and rollback.

Structured as a runbook (what to do when an alert fires), not a
design doc (why it's built this way) — the design is in the spec at
docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Run the full backend test suite and verify no regressions

**Files:** none (verification only)

- [ ] **Step 1: Run pytest against the full suite (excluding load/stress)**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -15
```

Expected: **1042+ tests pass** (1028 from previous work + 11 scrub tests + 3 decorator tests = 1042). Zero failures.

If any existing test fails, the root cause is almost always one of:
- A decorator application on `submit_student_work` / `save_submission_draft` / etc. broke an existing mock-based unit test that was introspecting the function's attributes. Fix: use `functools.wraps` (already in `critical_path`) and check whether the test introspects `.func` or similar.
- An import error in `backend/observability` prevented `backend/app.py` from loading. Fix: read the traceback carefully; likely a circular import or missing stub.
- The `init_sentry()` call on app load is somehow doing something unexpected. Fix: verify `SENTRY_DSN` is unset in the test environment — the no-op path should be the only one that runs.

- [ ] **Step 2: Spot-check the new tests ran**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sentry_scrub.py tests/test_critical_path.py -v 2>&1 | tail -20
```

Expected: 14 tests pass (11 scrub + 3 decorator), all listed by name.

- [ ] **Step 3: Verify the live `/healthz` endpoint still works against the real Supabase**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
import os
os.environ.pop('FORCE_HEALTHZ_FAIL', None)
os.environ.pop('SENTRY_TEST_ROUTE_ENABLED', None)
from dotenv import load_dotenv
load_dotenv('.env', override=True)
from backend.app import app
with app.test_client() as c:
    resp = c.get('/healthz')
    print('STATUS:', resp.status_code)
    print('BODY:', resp.get_json())
"
```

Expected: `STATUS: 200` and body contains `"supabase":"ok"`. This verifies that none of the observability changes broke the Tier 1 #2 fast-failing healthcheck.

- [ ] **Step 4: No commit needed** (verification step only — no file changes).

If everything passes, proceed to Task 11.

---

## Task 11: BetterStack manual setup (runbook — no code)

**Files:** none (configuration in BetterStack web UI + one Vercel DNS record)

This task is pure ops work — BetterStack account creation, monitor configuration, Slack webhook, DNS record. No Python, no git commits. Everything happens in web UIs.

> **Execution note:** if this plan is being executed by an agentic worker, **stop at this task and hand off to the human user.** The BetterStack account creation requires the user's email, payment info, and Slack workspace access — the agent cannot complete these steps autonomously. The user returns after finishing this task and tells the agent to proceed to Task 12.

- [ ] **Step 1: Create a BetterStack account**

Go to https://betterstack.com/users/sign-up and create an account using the user's primary email. Select the **Team tier ($10/mo)** during onboarding. (The free tier does not include SMS/voice escalation, which is a hard requirement.)

- [ ] **Step 2: Create the `/healthz` HTTPS monitor**

BetterStack dashboard → **Monitors** → **Create monitor** → **HTTPS**.

- **URL:** `https://app.graider.live/healthz`
- **Check interval:** 60 seconds
- **Regions:** accept the multi-region default
- **HTTP method:** GET
- **Expected status code:** 200
- **Response assertion:** response body must contain the string `"supabase":"ok"`
- **Failure condition:** alert after **2 consecutive failures**
- **Alert on SSL expiry:** enable, warn 30 days out
- **Monitor name:** `Graider app.graider.live /healthz`

Save.

- [ ] **Step 3: Create the SSL cert monitor**

BetterStack dashboard → **Monitors** → **Create monitor** → **SSL**.

- **Host:** `app.graider.live`
- **Port:** 443
- **Warn N days before expiry:** 30
- **Alert channel:** Email only (no Slack, no SMS — SSL expiry is an info-level alert)
- **Monitor name:** `Graider app.graider.live SSL cert`

Save.

- [ ] **Step 4: Create the domain expiry monitor**

BetterStack dashboard → **Monitors** → **Create monitor** → **Domain**.

- **Domain:** `graider.live`
- **Warn N days before expiry:** 30
- **Alert channel:** Email only
- **Monitor name:** `Graider graider.live domain`

Save.

- [ ] **Step 5: Create a Slack `#alerts` channel and webhook**

If Graider's Slack workspace doesn't already have an `#alerts` channel:
1. Slack → Channels → Create channel → `#alerts` → Public (or Private, user's choice)
2. Invite yourself.

Then create the webhook:
1. Slack → Apps → Search for "Incoming Webhooks" → Add to Slack
2. Select `#alerts` as the destination channel
3. Copy the Webhook URL (starts with `https://hooks.slack.com/services/...`)

- [ ] **Step 6: Wire the Slack webhook into BetterStack**

BetterStack dashboard → **Integrations** → **Slack** → paste the webhook URL → test.

Expected: a test message appears in `#alerts` within a few seconds.

- [ ] **Step 7: Create the "Graider Solo" on-call policy**

BetterStack dashboard → **On-call** → **Policies** → **Create policy**.

- **Name:** `Graider Solo`
- **Responders:** add user (email + phone + Slack)
- **Escalation chain:**
  1. Slack notification immediately (via the integration from step 6)
  2. SMS after 5 minutes if unacknowledged
  3. Voice call after 10 minutes if still unacknowledged
- **Active schedule:** outside business hours only
  - **Business hours definition:** 09:00-18:00 America/New_York, Mon-Fri
  - During business hours, only the Slack step fires (no SMS, no voice)
- **Default state when no override:** active

Save.

- [ ] **Step 8: Attach the on-call policy to the `/healthz` monitor**

BetterStack dashboard → Monitors → select the `/healthz` monitor → Edit → **Alert channel** → select "Graider Solo" policy → Save.

Verify the SSL cert and domain monitors are NOT using the on-call policy — they should be email-only. If they're not, edit each and set alert channel to "Email only".

- [ ] **Step 9: Add the `status.graider.live` CNAME in Vercel DNS**

Vercel dashboard → Projects → `graider.live` → **Domains** (or **DNS Records**, depending on project layout) → **Add record**.

- **Name:** `status`
- **Type:** `CNAME`
- **Value:** `status.betteruptime.com` (BetterStack will show you the exact target in its status-page setup flow — use their value if it differs)
- **TTL:** 3600 (or default)

Save. DNS propagation typically takes 1-5 minutes.

- [ ] **Step 10: Configure the public status page in BetterStack**

BetterStack dashboard → **Status pages** → **Create status page**.

- **Subdomain:** `status.graider.live` (matches the CNAME from step 9)
- **Visibility:** Public (no password)
- **Displayed monitors:** `/healthz` monitor only (do NOT display the SSL or domain monitors)
- **Branding:** "Graider" name, logo if available
- **Page title:** "Graider Status"

Save. Within 1-5 minutes, `https://status.graider.live` should render.

- [ ] **Step 11: Verify everything is green**

Check:
- BetterStack dashboard → all three monitors show "up" / green
- `curl -I https://status.graider.live` → HTTP 200, Content-Type text/html
- `dig status.graider.live` → shows a CNAME chain terminating at BetterStack
- Slack `#alerts` channel → test message from step 6 visible

- [ ] **Step 12: Hand back to the agentic worker (or proceed to Task 12 if manual)**

Sub-project B is complete. No code was changed. Proceed to Task 12 for the Sentry production verification and alert drill.

---

## Task 12: Open PR, production verification, alert drill, and cleanup PR

**Files:** none for the PR itself (Task 12 is ops workflow). A small cleanup PR at the end removes the `/_debug/sentry-boom` route code.

- [ ] **Step 1: Push the branch**

```bash
cd /Users/alexc/Downloads/Graider && git push -u origin feat/observability-sentry 2>&1
```

Expected: `[new branch] feat/observability-sentry -> feat/observability-sentry` and a PR-creation URL hint.

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "feat: observability v1 — Sentry + BetterStack" --body "$(cat <<'EOF'
## Summary

Tier 1 #3 sub-projects A + B combined. Adds Graider's first production observability layer: Sentry error tracking with PII-scrubbed capture, plus BetterStack uptime monitoring with a public status page at https://status.graider.live.

Closes Tier 1 #3A and #3B.

## Architecture

Two independent sub-projects in one PR. Sub-project A is all Python code in a new `backend/observability/` package with 14 unit tests. Sub-project B is pure BetterStack web UI configuration — see `docs/observability.md` for the runbook.

- **PII scrubber** — `before_send` hook strips request bodies, auth headers, cookies, secret query params, and known-PII stack frame locals; hashes `g.user_id` to a 12-char identifier when present; never crashes from background threads (Codex caught this — see spec for the `_resolve_user_id` defensive guard).
- **Critical-path tagging** — `@critical_path` decorator applied to 5 high-risk entrypoints (grading worker + 4 student-facing write routes). Tagged exceptions trigger SMS/voice escalation via BetterStack when they fire ≥3 times in 5 minutes.
- **Feature flags** — `SENTRY_TEST_ROUTE_ENABLED` gates a `/_debug/sentry-boom` route for post-deploy verification (dedicated flag, NOT `FLASK_DEBUG` which would enable the Werkzeug debugger and is a production RCE vector). `FORCE_HEALTHZ_FAIL` short-circuits `/healthz` to 503 for safe alert drills without touching Supabase.
- **Fail-fast `/healthz`** — the existing Tier 1 #2 healthcheck now also respects `FORCE_HEALTHZ_FAIL` for drills.

## Review history

This change went through:
1. **Brainstorming** (2026-04-11) — 6 questions answered, 2-section design presented, reviewed section-by-section by Codex and Gemini.
2. **Spec review by Codex** — caught three blockers: `flask.g` without context-safety guard, `FLASK_DEBUG` security risk, `SUPABASE_URL` corruption during drills. All three fixed in spec commits `a84b773` and `664b1fc` before this plan was written.
3. **Subagent-driven implementation** — each task went through the per-task spec + code-quality review.

## Test plan

- [x] 11 new unit tests in `tests/test_sentry_scrub.py` pass
- [x] 3 new unit tests in `tests/test_critical_path.py` pass
- [x] Full backend test suite (1042+ tests) passes locally
- [x] `init_sentry()` is a no-op when `SENTRY_DSN` is unset (verified via smoke test)
- [x] `/_debug/sentry-boom` returns 404 when `SENTRY_TEST_ROUTE_ENABLED` is unset
- [x] `/healthz` returns 503 when `FORCE_HEALTHZ_FAIL=1`, returns 200 when unset
- [x] All 5 `@critical_path` decorators applied and imports working
- [ ] CI green (this PR)
- [ ] Post-merge: production verification via `SENTRY_TEST_ROUTE_ENABLED=1` → hit debug route → verify scrubbed event in Sentry
- [ ] Post-merge: alert drill via `FORCE_HEALTHZ_FAIL=1` → verify BetterStack escalation chain fires
- [ ] Post-merge: cleanup PR to remove `/_debug/sentry-boom` route within 7 days

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: `https://github.com/nlev8/Graider/pull/<NUMBER>`.

- [ ] **Step 3: Enable auto-merge**

```bash
gh pr merge --auto --squash
```

The PR will wait for CI (Backend Tests + Frontend Build) to pass, then squash-merge itself and delete the branch.

- [ ] **Step 4: Wait for merge, then configure SENTRY_DSN in Railway**

Once CI passes and the PR auto-merges:

1. Railway dashboard → Graider project → Variables
2. Add `SENTRY_DSN` = (the DSN from the Sentry Cloud project you create — create it now if you haven't: https://sentry.io → New Project → Python / Flask → copy DSN)
3. Railway auto-deploys within ~60 seconds. Watch the deploy logs for the `Sentry initialized (release=<SHA>)` log line confirming the init succeeded.

- [ ] **Step 5: Production verification via `/_debug/sentry-boom`**

1. Railway dashboard → Variables → set `SENTRY_TEST_ROUTE_ENABLED=1`. Wait for auto-deploy (~60 seconds).
2. Hit the route twice:
   ```bash
   curl -s "https://app.graider.live/_debug/sentry-boom?severity=normal" ; echo
   curl -s "https://app.graider.live/_debug/sentry-boom?severity=critical" ; echo
   ```
   (Both should return HTTP 500 with an error page — that's expected, they're deliberately raising exceptions.)
3. In Sentry dashboard, verify within 60 seconds:
   - Both events arrived
   - The `?severity=critical` event has the `severity=critical` tag
   - Neither event contains `request.data`, `Authorization` header, or any frame locals from the PII list (look for `[PII-scrubbed]` sentinels in frame vars)
   - `user.id` is either a 12-char hex string or `"anonymous"`
4. **Unset** `SENTRY_TEST_ROUTE_ENABLED` in Railway (or set to `0`). Wait for auto-deploy. Confirm:
   ```bash
   curl -i https://app.graider.live/_debug/sentry-boom
   ```
   returns `HTTP/2 404`.

- [ ] **Step 6: Alert drill**

1. Railway dashboard → Variables → set `FORCE_HEALTHZ_FAIL=1`. Wait for auto-deploy (~60 seconds).
2. Within 3 minutes, BetterStack should observe 2 consecutive 503 responses from `/healthz` and fire a Slack alert in `#alerts`.
3. Status page `https://status.graider.live` should show the monitor as "down."
4. If running outside business hours, SMS should arrive within 5 minutes of the Slack alert.
5. **Acknowledge** the incident in BetterStack.
6. **Unset** `FORCE_HEALTHZ_FAIL` in Railway. Wait for auto-deploy.
7. Within 3 minutes, BetterStack should fire a "resolved" notification in Slack.
8. Post in `#alerts`: "Drill complete. All alerts routed successfully."

- [ ] **Step 7: Open the cleanup PR**

Within 7 days of this PR merging (ideally the same day, to avoid forgetting), delete the `/_debug/sentry-boom` route code from `backend/app.py`.

```bash
git checkout main
git pull
git checkout -b chore/remove-sentry-debug-route
```

Use Edit on `backend/app.py` to remove the entire `if os.getenv("SENTRY_TEST_ROUTE_ENABLED") == "1":` block plus its header comment.

```bash
# Verify the debug route section is fully removed
grep -n "sentry-boom\|SENTRY_TEST_ROUTE_ENABLED" backend/app.py
# Expected: no matches

git add backend/app.py
git commit -m "chore: remove post-rollout sentry debug route"
git push -u origin chore/remove-sentry-debug-route
gh pr create --title "chore: remove post-rollout sentry debug route" --body "Removes the /_debug/sentry-boom code block from backend/app.py. Production verification of Sentry completed successfully on <DATE>. The SENTRY_TEST_ROUTE_ENABLED env var is no longer referenced anywhere in the codebase. Per the observability runbook, this cleanup is mandatory within 7 days of observability v1 merging."
gh pr merge --auto --squash
```

- [ ] **Step 8: Mark observability v1 complete**

Once the cleanup PR auto-merges, Tier 1 #3 sub-projects A and B are done. Update the tier-1-production-reliability tracker (or memory entry) and proceed to Tier 1 #4 (grading thread watchdog) whenever ready.

---

## Summary

| Task | Files changed | Risk | What it accomplishes |
|---|---|---|---|
| 1 | `requirements.txt` + new `backend/observability/` package | Low — dependency add + empty module | Scaffolding |
| 2 | new: `tests/test_sentry_scrub.py` | None — test-only | Failing TDD tests for the scrubber |
| 3 | `backend/observability/sentry.py` | Low — isolated new module | PII scrubber implementation |
| 4 | new: `tests/test_critical_path.py` + `backend/observability/sentry.py` | Low | `@critical_path` decorator |
| 5 | `backend/observability/sentry.py` + `backend/app.py` | Medium — touches the Flask app init path | `init_sentry()` wiring |
| 6 | `backend/app.py` | Low — env-gated new route | `/_debug/sentry-boom` for verification |
| 7 | `backend/app.py` | Low — env-gated short-circuit | `FORCE_HEALTHZ_FAIL` for safe drills |
| 8 | 3 route/service files | Low — 5 decorator applications | Critical-path tagging |
| 9 | new: `docs/observability.md` | None | Runbook |
| 10 | none (verification) | None | Full suite regression check |
| 11 | none (BetterStack UI + Vercel DNS) | Low — reversible config | Uptime monitoring + status page |
| 12 | none (PR workflow) + cleanup PR | Low | Ship, verify, drill, cleanup |

**Before:** Graider had no error tracking, no external uptime probe, and no status page. Operational failures were visible only via Railway logs, discovered only when a district complained.

**After:** Every backend exception is captured and grouped in Sentry (with PII scrubbed). `/healthz` is probed every 60 seconds from multiple regions. Critical-path failures trigger SMS + voice escalation after-hours. A public status page at `https://status.graider.live` gives district IT a vendor-review-ready signal. Alert drills are safe to run during business hours without any customer impact.
