"""Gap-fill tests for backend/observability/sentry.py.

Audit MAJOR #4 sprint follow-up to PR #326. Companion to existing
`tests/test_sentry_scrub.py`, `test_sentry_pii_hardening.py`,
`test_sentry_tracing.py`. Targets a subset of the 24 missing LOC:

* `_resolve_user_id`: has_request_context RuntimeError fallback,
  g.user_id getattr RuntimeError fallback (lines 139-145)
* `_is_client_error`: outer-except defensive swallow (line 110-113)
* `_scrub_event_paths`: tuple params branch (lines 206-207),
  breadcrumbs non-dict-crumb skip (line 224), spans non-dict-span
  skip (line 239)
* `_scrub_frame_locals`: outer-except defensive swallow (lines 330-332)
* `_strip_secret_query_params`: param without = (line 308)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


MODULE = "backend.observability.sentry"


# ──────────────────────────────────────────────────────────────────
# _resolve_user_id fallback paths
# ──────────────────────────────────────────────────────────────────


class TestResolveUserIdFallbacks:
    def test_no_request_context_returns_anonymous(self):
        from backend.observability.sentry import _resolve_user_id
        # Outside of any Flask request → has_request_context returns False
        assert _resolve_user_id() == "anonymous"

    def test_has_request_context_runtime_error_returns_anonymous(self):
        # Force has_request_context to raise RuntimeError
        from backend.observability.sentry import _resolve_user_id

        def boom():
            raise RuntimeError("flask context broken")

        with patch("flask.has_request_context", side_effect=boom):
            assert _resolve_user_id() == "anonymous"

    def test_with_request_context_no_user_id_returns_anonymous(self):
        from backend.observability.sentry import _resolve_user_id
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context():
            # No g.user_id set → "anonymous"
            assert _resolve_user_id() == "anonymous"

    def test_with_user_id_returns_hash(self):
        from backend.observability.sentry import _resolve_user_id
        from flask import Flask, g

        app = Flask(__name__)
        with app.test_request_context():
            g.user_id = "teach-1"
            result = _resolve_user_id()
        # 12-char sha256 hash
        assert result != "anonymous"
        assert len(result) == 12


# ──────────────────────────────────────────────────────────────────
# _is_client_error defensive swallow
# ──────────────────────────────────────────────────────────────────


class TestIsClientErrorEventDefensive:
    def test_malformed_event_returns_false_not_raise(self):
        # If event has unexpected shape (e.g., exception is not a dict),
        # the function returns False without raising.
        from backend.observability.sentry import _is_client_error
        # event with non-dict at exception → exception.get raises AttributeError
        bad_event = {"exception": "not a dict"}
        assert _is_client_error(bad_event) is False

    def test_known_client_error_returns_true(self):
        from backend.observability.sentry import _is_client_error
        event = {
            "exception": {
                "values": [{"type": "BadRequest", "value": "x"}],
            }
        }
        assert _is_client_error(event) is True

    def test_dotted_type_strips_to_bare_name(self):
        from backend.observability.sentry import _is_client_error
        event = {
            "exception": {
                "values": [{"type": "werkzeug.exceptions.NotFound"}],
            }
        }
        assert _is_client_error(event) is True

    def test_non_client_error_type_returns_false(self):
        from backend.observability.sentry import _is_client_error
        event = {
            "exception": {
                "values": [{"type": "DatabaseError"}],
            }
        }
        assert _is_client_error(event) is False


# ──────────────────────────────────────────────────────────────────
# _scrub_event_paths edge branches
# ──────────────────────────────────────────────────────────────────


class TestScrubEventPathsEdges:
    def test_tuple_params_redacted_as_tuple(self):
        # logentry.params can be a tuple → redaction preserves tuple type
        from backend.observability.sentry import _scrub_event_paths

        event = {
            "logentry": {
                "params": ("/api/users/abc123", "no-path-here"),
            }
        }
        _scrub_event_paths(event)
        result = event["logentry"]["params"]
        assert isinstance(result, tuple)
        assert "[Filtered-path]" in result[0]
        assert result[1] == "no-path-here"

    def test_breadcrumb_non_dict_skipped(self):
        from backend.observability.sentry import _scrub_event_paths

        event = {
            "breadcrumbs": {
                "values": [
                    "not a dict",  # Should be skipped, not crash
                    {"message": "/api/students/abc123"},
                ]
            }
        }
        _scrub_event_paths(event)
        # Dict crumb message redacted
        crumbs = event["breadcrumbs"]["values"]
        assert "[Filtered-path]" in crumbs[1]["message"]
        # Non-dict left untouched
        assert crumbs[0] == "not a dict"

    def test_breadcrumbs_as_bare_list(self):
        # SDK can pass breadcrumbs as a bare list (not dict)
        from backend.observability.sentry import _scrub_event_paths

        event = {
            "breadcrumbs": [
                {"message": "GET /api/students/abc123"},
            ]
        }
        _scrub_event_paths(event)
        assert "[Filtered-path]" in event["breadcrumbs"][0]["message"]

    def test_span_non_dict_skipped(self):
        from backend.observability.sentry import _scrub_event_paths

        event = {
            "spans": [
                "not a dict",  # Skipped
                {"description": "GET /api/users/abc123"},
            ]
        }
        _scrub_event_paths(event)
        # Dict span description redacted
        assert "[Filtered-path]" in event["spans"][1]["description"]
        # Non-dict left
        assert event["spans"][0] == "not a dict"

    def test_breadcrumb_data_field_redacted(self):
        from backend.observability.sentry import _scrub_event_paths

        event = {
            "breadcrumbs": {
                "values": [
                    {"message": "ok",
                     "data": {"path": "/api/students/abc123"}},
                ]
            }
        }
        _scrub_event_paths(event)
        assert (
            "[Filtered-path]"
            in event["breadcrumbs"]["values"][0]["data"]["path"]
        )

    def test_span_data_field_redacted(self):
        from backend.observability.sentry import _scrub_event_paths

        event = {
            "spans": [
                {"description": "ok",
                 "data": {"http.url": "/api/students/abc123"}},
            ]
        }
        _scrub_event_paths(event)
        assert (
            "[Filtered-path]"
            in event["spans"][0]["data"]["http.url"]
        )


# ──────────────────────────────────────────────────────────────────
# _scrub_frame_locals defensive swallow
# ──────────────────────────────────────────────────────────────────


class TestScrubFrameLocalsDefensive:
    def test_malformed_event_no_raise(self):
        from backend.observability.sentry import _scrub_frame_locals

        # Bad event shape — exception is not a dict
        bad = {"exception": "not a dict"}
        # Should not raise
        _scrub_frame_locals(bad)

    def test_pii_local_replaced_with_sentinel(self):
        from backend.observability.sentry import _scrub_frame_locals

        event = {
            "exception": {
                "values": [{
                    "stacktrace": {
                        "frames": [
                            {"vars": {
                                "student_name": "Alice Smith",
                                "safe_var": "ok",
                            }},
                        ]
                    }
                }]
            }
        }
        _scrub_frame_locals(event)
        frame_vars = event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        # PII replaced
        assert frame_vars["student_name"] == "[PII-scrubbed]"
        # Non-PII preserved
        assert frame_vars["safe_var"] == "ok"

    def test_frame_without_vars_dict_skipped(self):
        from backend.observability.sentry import _scrub_frame_locals

        event = {
            "exception": {
                "values": [{
                    "stacktrace": {
                        "frames": [
                            {"vars": "not a dict"},  # skipped
                            {"vars": {"student_name": "Alice"}},
                        ]
                    }
                }]
            }
        }
        _scrub_frame_locals(event)
        # Non-dict frame's vars unchanged
        frames = event["exception"]["values"][0]["stacktrace"]["frames"]
        assert frames[0]["vars"] == "not a dict"
        # Dict frame's PII replaced
        assert frames[1]["vars"]["student_name"] == "[PII-scrubbed]"


# ──────────────────────────────────────────────────────────────────
# query string scrubbing (via before_send full path)
# ──────────────────────────────────────────────────────────────────


class TestQueryStringScrubbing:
    def test_query_param_without_equals_passed_through(self):
        # Manually build event with `query_string` containing param w/o "="
        from backend.observability.sentry import before_send

        event = {
            "request": {
                "query_string": "no_equals_marker&token=secret123",
            }
        }
        result = before_send(event, {})
        # Token redacted; bare param preserved (no = means treated as name)
        assert "token=[Filtered]" in result["request"]["query_string"]
        # The bare "no_equals_marker" is preserved as-is (since "no_equals"
        # may or may not match secret markers — depends on impl)
        assert "no_equals_marker" in result["request"]["query_string"]
