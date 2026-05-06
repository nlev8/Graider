"""Tests for @critical_path decorator in backend/observability/sentry.py."""

from unittest.mock import patch, MagicMock
import pytest


class TestCriticalPath:
    def test_decorator_sets_severity_tag_before_reraise(self):
        """When a decorated fn raises, sentry_sdk.set_tag must be called
        with ('severity', 'critical') on the current isolation scope
        BEFORE the exception propagates out of the wrapper.

        This is the production bug pin: the previous implementation used
        `with sentry_sdk.push_scope() as scope: scope.set_tag(...)` which
        works in sentry-sdk 1.x but silently fails in 2.x because the
        forked scope is popped on exception exit before Flask's
        integration captures the event. Verified broken in production
        on 2026-04-11 via /_debug/sentry-boom?severity=critical — the
        event arrived at BetterStack without the tag despite the unit
        tests passing (they mocked push_scope and asserted set_tag was
        called on the MOCK, which said nothing about whether the tag
        reached a real event).

        This test explicitly mocks `sentry_sdk.set_tag` at the module
        level and asserts it was called as part of the exception-handling
        path, which is what the 2.x-compatible fix actually does.
        """
        from backend.observability.sentry import critical_path

        with patch("sentry_sdk.set_tag") as mock_set_tag:
            @critical_path
            def boom():
                raise RuntimeError("test failure")

            with pytest.raises(RuntimeError, match="test failure"):
                boom()

        # set_tag must be called exactly once, with the correct args,
        # as part of the exception-handling path of the decorator.
        mock_set_tag.assert_called_once_with("severity", "critical")

    def test_decorator_does_not_set_tag_on_success(self):
        """Non-raising fn must NOT touch the scope — we only tag failures."""
        from backend.observability.sentry import critical_path

        with patch("sentry_sdk.set_tag") as mock_set_tag:
            @critical_path
            def happy():
                return "ok"

            assert happy() == "ok"
            mock_set_tag.assert_not_called()

    def test_decorator_preserves_return_value(self):
        """Non-raising decorated fn returns its value unchanged."""
        from backend.observability.sentry import critical_path

        @critical_path
        def greet(name):
            return f"hello {name}"

        assert greet("world") == "hello world"

    def test_decorator_is_noop_when_sentry_uninitialized(self):
        """Decorator must not crash when Sentry has no configured client.

        sentry_sdk.set_tag() is safe to call with no active client —
        it's a no-op on the default uninitialized hub. This test
        verifies the decorator runs normally in that state (which is
        the local-dev / CI default because tests never call
        init_sentry()).
        """
        from backend.observability.sentry import critical_path

        # No init_sentry() called anywhere in the test. Not mocking
        # sentry_sdk.set_tag either — let the real SDK handle it.
        @critical_path
        def answer():
            return 42

        assert answer() == 42

    def test_decorator_propagates_original_exception_unchanged(self):
        """The decorator must re-raise the ORIGINAL exception without
        wrapping or replacing it. Observability layer must never mask
        the production bug it's trying to report.
        """
        from backend.observability.sentry import critical_path

        sentinel = ValueError("original production bug")

        @critical_path
        def broken():
            raise sentinel

        with pytest.raises(ValueError) as exc_info:
            broken()

        # Must be the EXACT same exception instance (identity, not just equality),
        # with message preserved.
        assert exc_info.value is sentinel
        assert str(exc_info.value) == "original production bug"

    def test_decorator_survives_broken_sentry_sdk(self):
        """If sentry_sdk.set_tag itself raises for any reason, the
        decorator must STILL re-raise the original exception rather
        than masking it with the observability failure. A broken
        scrubber/observer should never eat production errors.
        """
        from backend.observability.sentry import critical_path

        with patch("sentry_sdk.set_tag", side_effect=RuntimeError("sentry broken")):
            @critical_path
            def real_bug():
                raise ValueError("real production issue")

            # The ValueError (original bug) must propagate, NOT the
            # RuntimeError from the broken sentry_sdk call.
            with pytest.raises(ValueError, match="real production issue"):
                real_bug()


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
        # Pin SENTRY_TRACES_SAMPLE_RATE to default so this test isn't
        # coupled to whatever the operator may have set in .env.
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

        from unittest.mock import patch
        with patch("sentry_sdk.init") as mock_init:
            mod.init_sentry()
            mock_init.assert_called_once()
            kwargs = mock_init.call_args.kwargs
            assert kwargs["dsn"] == "https://fake@fake.ingest.sentry.io/1234567"
            assert kwargs["environment"] == "production"
            assert kwargs["release"] == "unknown"
            # Audit MAJOR #14 (Codex 2026-05-06) closure: tracing baseline
            # is 5%, not 0.0. Override via SENTRY_TRACES_SAMPLE_RATE env.
            assert kwargs["traces_sample_rate"] == 0.05
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
