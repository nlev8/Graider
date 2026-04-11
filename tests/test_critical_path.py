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


class TestInitSentry:
    """Tests for init_sentry() startup wiring.

    These tests exercise the guard paths in init_sentry (no-op when
    unset, error-swallow on bad DSN, idempotency) using mocks — they
    must not actually connect to Sentry Cloud.
    """

    def test_noop_when_dsn_unset(self, monkeypatch):
        """When SENTRY_DSN is unset, init_sentry returns without touching the SDK."""
        import backend.observability.sentry as mod

        # Reset the module-level guard so we actually execute the function.
        monkeypatch.setattr(mod, "_initialized", False)
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        # Patch sentry_sdk.init so we can assert it was NOT called.
        from unittest.mock import patch
        with patch("sentry_sdk.init") as mock_init:
            mod.init_sentry()
            mock_init.assert_not_called()

        assert mod._initialized is True

    def test_init_called_with_expected_kwargs(self, monkeypatch):
        """When SENTRY_DSN is set, init_sentry calls sentry_sdk.init with the right config."""
        import backend.observability.sentry as mod

        monkeypatch.setattr(mod, "_initialized", False)
        monkeypatch.setenv("SENTRY_DSN", "https://fake@fake.ingest.sentry.io/1234567")
        monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)

        from unittest.mock import patch
        with patch("sentry_sdk.init") as mock_init:
            mod.init_sentry()
            mock_init.assert_called_once()
            kwargs = mock_init.call_args.kwargs
            assert kwargs["dsn"] == "https://fake@fake.ingest.sentry.io/1234567"
            assert kwargs["environment"] == "production"
            assert kwargs["release"] == "unknown"
            assert kwargs["traces_sample_rate"] == 0.0
            assert kwargs["send_default_pii"] is False
            # before_send hook is our scrubber
            assert kwargs["before_send"] is mod.before_send
            # CRITICAL: transaction_style must be "endpoint", NOT "url".
            # URL grouping explodes cardinality on ID-bearing routes
            # like /api/student/submission/<id>/draft. This assertion
            # prevents silent regression back to "url".
            from sentry_sdk.integrations.flask import FlaskIntegration
            integrations = kwargs["integrations"]
            assert any(isinstance(i, FlaskIntegration) for i in integrations), \
                "FlaskIntegration missing from integrations list"
            flask_integration = next(i for i in integrations if isinstance(i, FlaskIntegration))
            assert flask_integration.transaction_style == "endpoint", \
                f"transaction_style must be 'endpoint', got {flask_integration.transaction_style!r}"

            # ignore_errors must include the 5 werkzeug 4xx classes
            import werkzeug.exceptions as wex
            assert wex.BadRequest in kwargs["ignore_errors"]
            assert wex.Unauthorized in kwargs["ignore_errors"]
            assert wex.Forbidden in kwargs["ignore_errors"]
            assert wex.NotFound in kwargs["ignore_errors"]
            assert wex.MethodNotAllowed in kwargs["ignore_errors"]

        assert mod._initialized is True

    def test_malformed_dsn_does_not_crash(self, monkeypatch):
        """If sentry_sdk.init raises BadDsn (typo'd env var), app startup must continue.

        Uses the actual sentry_sdk.utils.BadDsn exception, not a generic
        Exception, so the test fails if the except clause is accidentally
        narrowed to exclude BadDsn.
        """
        import backend.observability.sentry as mod
        from sentry_sdk.utils import BadDsn

        monkeypatch.setattr(mod, "_initialized", False)
        monkeypatch.setenv("SENTRY_DSN", "not-a-real-dsn")

        from unittest.mock import patch
        with patch("sentry_sdk.init", side_effect=BadDsn("malformed DSN")) as mock_init:
            # Should NOT raise — the init wrapper swallows BadDsn specifically.
            mod.init_sentry()
            mock_init.assert_called_once()

        # After a transient init failure, _initialized should NOT be set —
        # a later call (e.g., after the env var is fixed) should retry.
        assert mod._initialized is False, \
            "_initialized should remain False after bad-DSN failure to allow retry"

    def test_idempotent_when_called_twice(self, monkeypatch):
        """Second call to init_sentry is a no-op thanks to the _initialized guard."""
        import backend.observability.sentry as mod

        monkeypatch.setattr(mod, "_initialized", False)
        monkeypatch.setenv("SENTRY_DSN", "https://fake@fake.ingest.sentry.io/1234567")

        from unittest.mock import patch
        with patch("sentry_sdk.init") as mock_init:
            mod.init_sentry()
            mod.init_sentry()
            # sentry_sdk.init should have been called exactly ONCE despite two init_sentry calls
            assert mock_init.call_count == 1

    def test_unexpected_init_error_propagates(self, monkeypatch):
        """Non-DSN exceptions (e.g., TypeError from a wrong kwarg) must NOT be swallowed.

        The hardening in init_sentry only catches (ValueError, BadDsn) — real
        programming errors like a wrong kwarg or a future SDK regression
        should surface loudly so CI / staging catches them before production.
        """
        import backend.observability.sentry as mod

        monkeypatch.setattr(mod, "_initialized", False)
        monkeypatch.setenv("SENTRY_DSN", "https://fake@fake.ingest.sentry.io/1234567")

        from unittest.mock import patch
        with patch("sentry_sdk.init", side_effect=TypeError("unexpected kwarg")):
            with pytest.raises(TypeError, match="unexpected kwarg"):
                mod.init_sentry()

        # After an unexpected failure, _initialized should also NOT be set.
        assert mod._initialized is False
