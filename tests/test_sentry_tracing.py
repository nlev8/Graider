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
