"""Sentry APM/tracing baseline contract tests.

Closes audit MAJOR #14 (Codex full-codebase audit 2026-05-06): tracing
was hardcoded off (`traces_sample_rate=0.0`), leaving latency
regressions in critical paths (grading, portal-submit, SIS sync, LLM
calls) diagnostically blind.

Pins:
- The default sample rate is non-zero (currently 0.05).
- Operators can override via `SENTRY_TRACES_SAMPLE_RATE` env var.
- Out-of-range or non-numeric values fall back to the default.
"""
import importlib
import sys
from unittest.mock import patch


def _import_sentry_module():
    """Re-import backend.observability.sentry so the module-level
    `_resolve_traces_sample_rate()` re-evaluates env vars."""
    sys.path.insert(0, "backend")
    try:
        from backend.observability import sentry as sentry_mod
        importlib.reload(sentry_mod)
        return sentry_mod
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


class TestTracesSampleRateResolution:
    """The _resolve_traces_sample_rate() helper drives the init kwarg."""

    def test_default_is_non_zero(self, monkeypatch):
        """No env override → 5% baseline (audit MAJOR #14 closure)."""
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.05

    def test_env_override_zero_returns_none_for_full_disable(self, monkeypatch):
        """Codex round-1 MEDIUM fold: per Sentry docs, `0.0` prevents NEW
        traces but continues incoming sampled ones. `None` is the
        Sentry-canonical full disable. We map 0.0 → None so an operator
        setting SENTRY_TRACES_SAMPLE_RATE=0.0 to "disable" actually does."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() is None

    def test_empty_string_falls_back(self, monkeypatch):
        """Round-1 Codex MINOR: empty SENTRY_TRACES_SAMPLE_RATE="" must
        fall back, not crash. float('') raises ValueError."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.05

    def test_invalid_float_emits_warning(self, monkeypatch, caplog):
        """Round-1 Codex MINOR: warning log must accompany the fallback."""
        import logging
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-float")
        sentry_mod = _import_sentry_module()
        with caplog.at_level(logging.WARNING, logger=sentry_mod.logger.name):
            sentry_mod._resolve_traces_sample_rate()
        assert any(
            "not a valid float" in record.message
            for record in caplog.records
        ), f"Expected 'not a valid float' warning; got: {[r.message for r in caplog.records]}"

    def test_out_of_range_emits_warning(self, monkeypatch, caplog):
        """Round-1 Codex MINOR: out-of-range must log a distinguishable
        warning so operators can grep production logs for misconfig."""
        import logging
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "2.0")
        sentry_mod = _import_sentry_module()
        with caplog.at_level(logging.WARNING, logger=sentry_mod.logger.name):
            sentry_mod._resolve_traces_sample_rate()
        assert any(
            "out of range" in record.message
            for record in caplog.records
        ), f"Expected 'out of range' warning; got: {[r.message for r in caplog.records]}"

    def test_env_override_bumps_for_tuning(self, monkeypatch):
        """During a tuning sprint, operator can raise the sample rate."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.5

    def test_invalid_float_falls_back(self, monkeypatch):
        """Typo'd env var (e.g., '0.05x') must not crash sentry init."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-float")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.05

    def test_out_of_range_falls_back_high(self, monkeypatch):
        """Sentry rejects rates > 1.0 — clamp before reaching SDK."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "2.0")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.05

    def test_out_of_range_falls_back_negative(self, monkeypatch):
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "-0.1")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.05

    def test_boundary_one_accepted(self, monkeypatch):
        """100% sampling is the valid upper bound."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 1.0


class TestSentryInitPassesTracesSampleRate:
    """The init call must wire the resolved rate through to sentry_sdk."""

    def test_init_call_uses_resolver(self, monkeypatch):
        """init_sentry() must pass _resolve_traces_sample_rate() (not 0.0)."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123456")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")

        sentry_mod = _import_sentry_module()
        sentry_mod._initialized = False  # force re-init

        with patch("sentry_sdk.init") as mock_init:
            sentry_mod.init_sentry(environment="web")

        assert mock_init.called, "sentry_sdk.init should have been called"
        kwargs = mock_init.call_args.kwargs
        assert kwargs["traces_sample_rate"] == 0.25, (
            f"Expected 0.25 (from env), got {kwargs.get('traces_sample_rate')!r}"
        )

    def test_init_call_default_baseline_when_env_unset(self, monkeypatch):
        """Default baseline is 5% — closes the actual audit finding."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123456")
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

        sentry_mod = _import_sentry_module()
        sentry_mod._initialized = False

        with patch("sentry_sdk.init") as mock_init:
            sentry_mod.init_sentry(environment="web")

        kwargs = mock_init.call_args.kwargs
        assert kwargs["traces_sample_rate"] == 0.05

    def test_init_registers_before_send_transaction(self, monkeypatch):
        """Round-1 Codex CRITICAL fold: APM transactions use a separate
        SDK pipeline; before_send does NOT see them. Without
        before_send_transaction, sentry-sdk 2.x captures request URL,
        query string, and request body on every sampled transaction —
        a FERPA regression. Registration must be present at HEAD."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123456")
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

        sentry_mod = _import_sentry_module()
        sentry_mod._initialized = False

        with patch("sentry_sdk.init") as mock_init:
            sentry_mod.init_sentry(environment="web")

        kwargs = mock_init.call_args.kwargs
        assert "before_send_transaction" in kwargs, (
            "before_send_transaction must be registered to scrub PII from "
            "APM transaction events (audit MAJOR #14 round-1 CRITICAL)"
        )
        assert kwargs["before_send_transaction"] is sentry_mod.before_send_transaction

    def test_init_sets_max_request_body_size_to_never(self, monkeypatch):
        """Round-1 Codex CRITICAL fold: defense-in-depth against the Flask
        integration's default request-body capture. `never` blocks body
        capture at the source so before_send_transaction's scrub becomes
        belt-and-suspenders rather than the only line of defense."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123456")
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

        sentry_mod = _import_sentry_module()
        sentry_mod._initialized = False

        with patch("sentry_sdk.init") as mock_init:
            sentry_mod.init_sentry(environment="web")

        kwargs = mock_init.call_args.kwargs
        assert kwargs.get("max_request_body_size") == "never", (
            "max_request_body_size must be 'never' to prevent the Flask "
            "integration from capturing request bodies on transactions"
        )


class TestBeforeSendTransactionScrubbing:
    """The transaction scrubber must strip PII the same way before_send does."""

    def test_request_body_stripped(self):
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "request": {
                "url": "https://app.graider.live/api/student/submission/abc/draft",
                "method": "POST",
                "data": {"student_name": "Alice", "answers": {"q1": "A"}},
                "json": {"student_name": "Alice", "answers": {"q1": "A"}},
                "form": {},
                "cookies": {"session": "secret"},
                "headers": {"Authorization": "Bearer token", "User-Agent": "x"},
                "query_string": "api_key=secret&foo=bar",
            },
        }
        out = sentry_mod.before_send_transaction(event, {})

        assert out is not None  # transactions are forwarded, not dropped
        req = out["request"]
        # Body fields stripped
        assert "data" not in req
        assert "json" not in req
        assert "form" not in req
        assert "cookies" not in req
        # Auth header redacted
        assert req["headers"]["Authorization"] == "[Filtered]"
        # User-Agent preserved (not auth)
        assert req["headers"]["User-Agent"] == "x"

    def test_request_url_dropped(self):
        """Round-2 Codex CRITICAL fold: request.url leaks identifier-bearing
        path params on FERPA-sensitive routes. transaction_style='endpoint'
        only sets event.transaction, NOT request.url — so routes like
        /api/student-history/<student_id> would otherwise leak the literal
        student_id value. The endpoint name carries the diagnostic signal."""
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "transaction": "student_portal_routes.report_card",
            "request": {
                "url": "https://app.graider.live/api/teacher/class/c123/student/s456/report-card",
                "method": "GET",
                "headers": {},
            },
        }
        out = sentry_mod.before_send_transaction(event, {})
        req = out["request"]
        assert "url" not in req, (
            "request.url must be dropped — path params leak student/class/"
            "submission identifiers on FERPA-sensitive routes"
        )
        # Endpoint name (the safe replacement signal) is preserved.
        assert out["transaction"] == "student_portal_routes.report_card"

    def test_referer_header_filtered(self):
        """Round-2 Codex CRITICAL fold: Referer header could leak the
        previous page URL (which itself carries identifier path params)."""
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "request": {
                "headers": {
                    "Referer": "https://app.graider.live/api/student/submission/abc123",
                    "User-Agent": "Mozilla/5.0",
                },
            },
        }
        out = sentry_mod.before_send_transaction(event, {})
        headers = out["request"]["headers"]
        assert headers["Referer"] == "[Filtered]"
        # Other safe headers preserved
        assert headers["User-Agent"] == "Mozilla/5.0"

    def test_request_url_scrubbed_on_error_events_too(self):
        """Same _scrub_request helper runs on error events via before_send.
        Verify URL scrubbing applies there too — error events also leak
        path params on the same FERPA-sensitive routes."""
        sentry_mod = _import_sentry_module()
        event = {
            "exception": {"values": [{"type": "RuntimeError", "value": "boom"}]},
            "request": {
                "url": "https://app.graider.live/api/student-history/abc123",
                "method": "GET",
                "headers": {},
            },
        }
        out = sentry_mod.before_send(event, {})
        assert out is not None
        assert "url" not in out["request"]


class TestLogentryScrubbing:
    """Round-3 Codex CRITICAL fold: Sentry logging integration captures
    `logger.exception(msg, *args)` calls as event['logentry']. The args
    (params) and rendered string (formatted) carry raw request.path
    values from real call sites. _scrub_logentry redacts path-like
    substrings at the Sentry boundary."""

    def test_logentry_params_with_path_redacted(self):
        sentry_mod = _import_sentry_module()
        event = {
            "exception": {"values": [{"type": "RuntimeError", "value": "boom"}]},
            "logentry": {
                "message": "Request failed: %s",
                "params": ["/api/student-history/abc123"],
                "formatted": "Request failed: /api/student-history/abc123",
            },
        }
        out = sentry_mod.before_send(event, {})
        le = out["logentry"]
        assert le["params"] == ["[Filtered-path]"]
        assert "/api/student-history/abc123" not in le["formatted"]
        assert "[Filtered-path]" in le["formatted"]
        # Format string preserved — non-PII, useful for debugging.
        assert le["message"] == "Request failed: %s"

    def test_logentry_non_path_params_preserved(self):
        """Counts, error codes, and other non-path values must survive."""
        sentry_mod = _import_sentry_module()
        event = {
            "exception": {"values": [{"type": "RuntimeError", "value": "boom"}]},
            "logentry": {
                "message": "Synced %d records in %.2fs",
                "params": [42, 3.14],
                "formatted": "Synced 42 records in 3.14s",
            },
        }
        out = sentry_mod.before_send(event, {})
        le = out["logentry"]
        assert le["params"] == [42, 3.14]
        assert le["formatted"] == "Synced 42 records in 3.14s"

    def test_logentry_mixed_params_only_paths_redacted(self):
        sentry_mod = _import_sentry_module()
        event = {
            "exception": {"values": [{"type": "RuntimeError", "value": "boom"}]},
            "logentry": {
                "message": "GET %s returned %d in %dms",
                "params": ["/api/teacher/class/c123/student/s456/report-card", 500, 1234],
                "formatted": "GET /api/teacher/class/c123/student/s456/report-card returned 500 in 1234ms",
            },
        }
        out = sentry_mod.before_send(event, {})
        le = out["logentry"]
        assert le["params"][0] == "[Filtered-path]"
        assert le["params"][1] == 500
        assert le["params"][2] == 1234
        # Path string itself replaced in the formatted output
        assert "c123" not in le["formatted"]
        assert "s456" not in le["formatted"]
        # Non-path numeric content preserved in the formatted output
        assert "500" in le["formatted"]
        assert "1234ms" in le["formatted"]

    def test_logentry_scrubbed_on_transactions_too(self):
        """before_send_transaction shares the same logentry scrubber."""
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "logentry": {
                "message": "slow %s",
                "params": ["/api/student-history/abc123"],
                "formatted": "slow /api/student-history/abc123",
            },
        }
        out = sentry_mod.before_send_transaction(event, {})
        le = out["logentry"]
        assert le["params"] == ["[Filtered-path]"]
        assert "abc123" not in le["formatted"]

    def test_logentry_missing_field_no_op(self):
        """Most events don't have logentry — scrubber must not crash."""
        sentry_mod = _import_sentry_module()
        event = {"exception": {"values": [{"type": "RuntimeError", "value": "boom"}]}}
        out = sentry_mod.before_send(event, {})
        assert out is not None
        assert "logentry" not in out

    def test_redact_paths_in_string_helper(self):
        """Direct unit test of the regex redactor."""
        sentry_mod = _import_sentry_module()
        # 2+ segments redacted
        assert sentry_mod._redact_paths_in_string("/api/student/abc") == "[Filtered-path]"
        assert sentry_mod._redact_paths_in_string("hit /api/x/y/z then more") == "hit [Filtered-path] then more"
        # Single-segment paths NOT redacted (no clear PII surface)
        assert sentry_mod._redact_paths_in_string("/healthz") == "/healthz"
        # Non-string passthrough
        assert sentry_mod._redact_paths_in_string(42) == 42
        assert sentry_mod._redact_paths_in_string(None) is None


class TestEventBoundaryPathScrubbing:
    """Round-4 Codex CRITICAL fold: paths leak through multiple Sentry event
    surfaces beyond logentry.params/formatted. Generalized boundary scrubber
    catches them all."""

    def test_top_level_message_scrubbed(self):
        """capture_message(f'... {request.path}') sets event['message']
        directly, bypassing logentry. Cited site: grading_tasks.py:141."""
        sentry_mod = _import_sentry_module()
        event = {
            "message": "grade_portal_submission: failed at /api/teacher/class/c123/student/s456/report-card",
        }
        out = sentry_mod.before_send(event, {})
        assert "/api/teacher" not in out["message"]
        assert "[Filtered-path]" in out["message"]

    def test_logentry_message_format_string_scrubbed(self):
        """logger.error(f'failed at {request.path}') leaves the rendered
        path in logentry.message (the format string), with empty params."""
        sentry_mod = _import_sentry_module()
        event = {
            "logentry": {
                "message": "failed at /api/student-history/abc123",
                "params": [],
                "formatted": "failed at /api/student-history/abc123",
            },
        }
        out = sentry_mod.before_send(event, {})
        le = out["logentry"]
        assert "abc123" not in le["message"]
        assert "abc123" not in le["formatted"]

    def test_extra_dict_paths_scrubbed(self):
        """logger.error(..., extra={'path': '/api/...'}) puts raw paths in event.extra."""
        sentry_mod = _import_sentry_module()
        event = {
            "extra": {
                "request_path": "/api/student/abc/draft",
                "count": 42,
                "non_path_string": "hello",
            },
        }
        out = sentry_mod.before_send(event, {})
        assert out["extra"]["request_path"] == "[Filtered-path]"
        assert out["extra"]["count"] == 42  # non-string preserved
        assert out["extra"]["non_path_string"] == "hello"  # non-path string preserved

    def test_breadcrumbs_dict_form_scrubbed(self):
        """Sentry breadcrumbs use {'values': [...]} envelope shape."""
        sentry_mod = _import_sentry_module()
        event = {
            "breadcrumbs": {
                "values": [
                    {"message": "GET /api/teacher/class/c1/student/s2", "category": "http"},
                    {"data": {"url": "/api/student-history/abc123", "method": "GET"}},
                ],
            },
        }
        out = sentry_mod.before_send(event, {})
        crumbs = out["breadcrumbs"]["values"]
        assert "[Filtered-path]" in crumbs[0]["message"]
        assert crumbs[1]["data"]["url"] == "[Filtered-path]"

    def test_breadcrumbs_bare_list_form_scrubbed(self):
        """Some SDK versions pass breadcrumbs as a bare list."""
        sentry_mod = _import_sentry_module()
        event = {
            "breadcrumbs": [
                {"message": "GET /api/x/y/z", "category": "http"},
            ],
        }
        out = sentry_mod.before_send(event, {})
        # Defensive: bare-list form is handled the same way
        assert "[Filtered-path]" in out["breadcrumbs"][0]["message"]

    def test_transactions_share_full_boundary_scrubber(self):
        """before_send_transaction must use the same generalized scrubber."""
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "message": "transaction message with /api/x/y/z",
            "extra": {"path": "/api/student/abc"},
        }
        out = sentry_mod.before_send_transaction(event, {})
        assert "/api/x/y" not in out["message"]
        assert out["extra"]["path"] == "[Filtered-path]"

    def test_missing_fields_no_crash(self):
        """All boundary fields are optional — scrubber must not raise on
        any combination of missing/wrong-type fields."""
        sentry_mod = _import_sentry_module()
        # All missing
        sentry_mod.before_send({}, {})
        # Wrong types
        out = sentry_mod.before_send(
            {"message": 42, "extra": "not-a-dict", "breadcrumbs": "bare-string"},
            {},
        )
        assert out is not None  # no crash, no client-error short-circuit


class TestCallSiteIdHashing:
    """Round-4 Codex CRITICAL: bare submission_id values leak through
    capture_message and logger params. Static-source pin tests for the
    4 cited sites — fixed to hash before logging.

    Boundary scrubber alone can't catch bare IDs (they aren't paths).
    Call-site discipline is required."""

    def test_grading_tasks_no_assessment_uses_hashed_id(self):
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "backend/tasks/grading_tasks.py"
        text = src.read_text()
        # New: hash precomputed before both logger and capture_message use it
        assert "sub_hash = hashlib.sha256(str(submission_id).encode()).hexdigest()[:8]" in text
        # Old leak pattern must be gone
        assert "no assessment for submission {submission_id}" not in text

    def test_portal_grading_fetch_failures_hash_id(self):
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "backend/services/portal_grading.py"
        text = src.read_text()
        # 3 round-4 sites + 1 round-5 site (_safe_update_submission) must hash.
        assert text.count("hashlib.sha256(str(submission_id).encode()).hexdigest()[:8]") >= 4, (
            "Expected ≥4 hashed-submission-id call sites in portal_grading.py "
            "(round-4: 3 sites + round-5: _safe_update_submission)"
        )

    def test_safe_update_submission_runtime_no_raw_id(self, capsys):
        """Round-5 Codex CRITICAL fold: _safe_update_submission with sb=None
        previously formatted raw submission_id into both logger.error and
        capture_message. Now the format string receives only the hash."""
        from unittest.mock import patch

        # Import via the project path to match how the module is normally used.
        import sys
        if "backend" in sys.path:
            sys.path.remove("backend")  # ensure consistent import
        from backend.services import portal_grading

        captured = {}

        def fake_capture(msg, level=None):
            captured["msg"] = msg
            captured["level"] = level

        with patch("backend.services.portal_grading.sentry_sdk.capture_message",
                   side_effect=fake_capture):
            portal_grading._safe_update_submission(
                sb=None,
                submission_id="test-raw-id-abc123-XYZ",
                update_fields={"status": "failed"},
            )

        # Raw submission_id must not appear in either the captured Sentry
        # message or, by extension, the logger.error formatted output.
        assert "msg" in captured, "capture_message should have been called"
        assert "test-raw-id-abc123-XYZ" not in captured["msg"], (
            f"Raw submission_id leaked into Sentry: {captured['msg']!r}"
        )
        # The hash should be present (8 hex chars) so debugging is still possible.
        import re
        assert re.search(r"\b[0-9a-f]{8}\b", captured["msg"]), (
            f"Expected an 8-hex-char hash in the message; got: {captured['msg']!r}"
        )


class TestEventBoundaryAPMSurfaces:
    """Round-5 Codex MAJOR fold: spans/contexts/tags weren't scrubbed.
    A transaction event with /api/.../<id> in those fields survived
    before_send_transaction. Now they're walked too."""

    def test_spans_description_scrubbed(self):
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "spans": [
                {"description": "GET /api/student-history/abc123", "op": "http.client"},
                {"description": "psql SELECT * FROM students"},  # no path → preserved
            ],
        }
        out = sentry_mod.before_send_transaction(event, {})
        assert "abc123" not in out["spans"][0]["description"]
        assert "[Filtered-path]" in out["spans"][0]["description"]
        # Non-path span description preserved
        assert out["spans"][1]["description"] == "psql SELECT * FROM students"

    def test_spans_data_scrubbed(self):
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "spans": [
                {"data": {"http.url": "/api/teacher/class/c1/student/s2", "method": "GET"}},
            ],
        }
        out = sentry_mod.before_send_transaction(event, {})
        assert out["spans"][0]["data"]["http.url"] == "[Filtered-path]"
        assert out["spans"][0]["data"]["method"] == "GET"

    def test_contexts_trace_scrubbed(self):
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "contexts": {
                "trace": {
                    "op": "http.server",
                    "description": "/api/student-history/abc123",
                    "url": "https://app.graider.live/api/teacher/class/c1/student/s2",
                },
                "runtime": {"name": "Python", "version": "3.12"},  # untouched
            },
        }
        out = sentry_mod.before_send_transaction(event, {})
        trace = out["contexts"]["trace"]
        assert "abc123" not in trace["description"]
        assert "/api/teacher" not in trace["url"]
        # Non-PII context preserved
        assert out["contexts"]["runtime"]["name"] == "Python"

    def test_tags_scrubbed(self):
        sentry_mod = _import_sentry_module()
        event = {
            "type": "transaction",
            "tags": {
                "route": "/api/student-history/abc123",
                "method": "GET",
                "status": "500",
            },
        }
        out = sentry_mod.before_send_transaction(event, {})
        assert out["tags"]["route"] == "[Filtered-path]"
        assert out["tags"]["method"] == "GET"
        assert out["tags"]["status"] == "500"

    def test_apm_surfaces_also_scrubbed_on_errors(self):
        """Same boundary scrubber runs on errors via before_send. Verify
        spans/contexts/tags are scrubbed there too even though spans are
        unusual on error events."""
        sentry_mod = _import_sentry_module()
        event = {
            "exception": {"values": [{"type": "RuntimeError", "value": "boom"}]},
            "tags": {"route": "/api/student-history/abc123"},
        }
        out = sentry_mod.before_send(event, {})
        assert out["tags"]["route"] == "[Filtered-path]"

    def test_user_id_resolved_to_hash_outside_request_context(self):
        """Outside Flask request context, user.id falls back to 'anonymous'."""
        sentry_mod = _import_sentry_module()
        event = {"type": "transaction", "user": {"email": "raw@x.com"}}
        out = sentry_mod.before_send_transaction(event, {})
        assert out["user"]["id"] == "anonymous"
        assert "email" not in out["user"]

    def test_pre_set_hashed_user_id_preserved(self):
        """Celery worker pattern: pre-hashed 12-char hex id must survive."""
        sentry_mod = _import_sentry_module()
        hashed = "abcdef012345"  # exactly 12 hex chars
        event = {"type": "transaction", "user": {"id": hashed}}
        out = sentry_mod.before_send_transaction(event, {})
        assert out["user"]["id"] == hashed
