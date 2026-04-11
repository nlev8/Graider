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
