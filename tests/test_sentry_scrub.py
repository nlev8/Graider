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
