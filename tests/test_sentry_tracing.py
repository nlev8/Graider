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

    def test_env_override_zero_disables_tracing(self, monkeypatch):
        """Operators can fully disable via env without redeploying code."""
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")
        sentry_mod = _import_sentry_module()
        assert sentry_mod._resolve_traces_sample_rate() == 0.0

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
