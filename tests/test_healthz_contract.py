"""Fail-closed /healthz contract tests.

Pins the contract introduced by Codex audit 2026-05-06 finding #6:
the route MUST return HTTP 503 when any required production dependency
is in an error/degraded state. Previously returned 200 with a body
flagging the failure, which broke Railway's load-balancer routing
(`backend/app.py:1838` → see GH issue #215).

Healthy states: "ok", "not configured" (latter only in dev/test where
the dep isn't wired). Anything else — "error", "degraded (status N)",
"drill_forced_failure" — must produce 503.
"""
import importlib
import os
import sys
from unittest.mock import MagicMock, patch


def _import_app():
    """Import backend.app freshly (mirrors test_app_boot pattern)."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        return backend_app
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def _client():
    return _import_app().app.test_client()


# ──────────────────────────────────────────────────────────────────
# Helpers — patch the two upstream calls /healthz makes (httpx + redis)
# ──────────────────────────────────────────────────────────────────


def _mock_httpx_response(status_code):
    """Return a fake httpx.Response object."""
    resp = MagicMock()
    resp.status_code = status_code
    return resp


# ──────────────────────────────────────────────────────────────────
# Healthy paths → 200
# ──────────────────────────────────────────────────────────────────


class TestHealthzHealthy:
    """Both deps healthy → 200 OK."""

    def test_both_ok_returns_200(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("FORCE_HEALTHZ_FAIL", raising=False)

        with patch("httpx.get", return_value=_mock_httpx_response(200)), \
             patch("redis.from_url") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            resp = _client().get("/healthz")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["app"] == "ok"
        assert body["supabase"] == "ok"
        assert body["redis"] == "ok"

    def test_not_configured_returns_200_hermetic(self):
        """`not configured` (dev/test where the dep isn't wired) is treated
        as healthy alongside `ok`. Hermetic: patches os.getenv directly
        so backend/app.py:30 load_dotenv(override=True) on reload cannot
        rehydrate stale .env values during the test (the round-1 review
        flagged the prior monkeypatch.setenv approach as env-dependent)."""
        # Drive os.getenv deterministically for the keys /healthz reads.
        # Other os.getenv calls still delegate to real env via the default.
        real_getenv = os.environ.get

        def fake_getenv(key, default=None):
            if key in (
                "SUPABASE_URL",
                "SUPABASE_SERVICE_KEY",
                "REDIS_URL",
                "FORCE_HEALTHZ_FAIL",
            ):
                return None
            return real_getenv(key, default)

        # Import freshly so the route binding is live; then patch os.getenv
        # in the backend.app module namespace (where the route reads it).
        backend_app = _import_app()
        with patch.object(backend_app.os, "getenv", side_effect=fake_getenv):
            resp = backend_app.app.test_client().get("/healthz")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["supabase"] == "not configured"
        assert body["redis"] == "not configured"


class TestHealthzLimiterExempt:
    """Round-2 fix for Codex MAJOR #1: /healthz must be exempt from
    Flask-Limiter so a Redis outage breaking the limiter's before_request
    storage call cannot turn a dependency check into a 500.

    Round-3 (Codex NIT fold): static-source pin + runtime simulation."""

    def test_route_decorated_with_limiter_exempt(self):
        """Static-source pin: the @limiter.exempt decorator must remain
        in place between @app.route('/healthz') and `def healthz`."""
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "backend/app.py"
        text = src.read_text()
        assert "@app.route('/healthz')\n@limiter.exempt\ndef healthz" in text, (
            "/healthz must be exempt from Flask-Limiter to avoid 500s "
            "when the limiter's Redis backend is down"
        )

    def test_route_returns_503_not_500_when_limiter_storage_raises(self):
        """Runtime simulation: even if Flask-Limiter's storage raises (Redis
        down), /healthz must still produce its own JSON 503, not a generic
        Flask 500. The @limiter.exempt decorator gates this — without it
        the limiter's before_request would crash before the route runs."""
        backend_app = _import_app()

        # Force the limiter's storage layer to raise on every call. If the
        # exempt decorator is working, the route still runs because the
        # limiter never tries to evaluate limits for /healthz.
        from backend.extensions import limiter

        # Force /healthz to take the unhealthy branch so we can verify the
        # route's own 503 path executes (rather than just trusting that 200
        # means the limiter was bypassed).
        real_getenv = os.environ.get

        def fake_getenv(key, default=None):
            if key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
                return None
            if key == "REDIS_URL":
                return "redis://localhost:6379/0"
            if key == "FORCE_HEALTHZ_FAIL":
                return None
            return real_getenv(key, default)

        with patch.object(limiter.limiter, "hit",
                          side_effect=Exception("limiter storage down")), \
             patch.object(limiter.limiter, "test",
                          side_effect=Exception("limiter storage down")), \
             patch.object(backend_app.os, "getenv", side_effect=fake_getenv), \
             patch("redis.from_url") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("redis down")
            resp = backend_app.app.test_client().get("/healthz")

        # Critical contract: route-owned 503 with structured JSON body,
        # NOT a generic Flask 500 from the limiter's failed before_request.
        assert resp.status_code == 503, (
            f"Expected route-owned 503, got {resp.status_code} "
            f"(body: {resp.data!r}) — limiter exemption may be broken"
        )
        body = resp.get_json()
        assert body is not None, "Response body must be valid JSON, not Flask 500 page"
        assert body["app"] == "ok"
        assert body["redis"] == "error"


# ──────────────────────────────────────────────────────────────────
# Unhealthy paths → 503 (the actual fix)
# ──────────────────────────────────────────────────────────────────


class TestHealthzFailClosed:
    """Any dependency error → 503."""

    def test_supabase_exception_returns_503(self, monkeypatch):
        """httpx raises (network error, DNS failure, etc.) → 503."""
        monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("FORCE_HEALTHZ_FAIL", raising=False)

        with patch("httpx.get", side_effect=Exception("connection refused")):
            resp = _client().get("/healthz")

        assert resp.status_code == 503
        body = resp.get_json()
        assert body["supabase"] == "error"

    def test_supabase_non_200_returns_503(self, monkeypatch):
        """Supabase responds with 500 → status reads 'degraded (...)' → 503."""
        monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("FORCE_HEALTHZ_FAIL", raising=False)

        with patch("httpx.get", return_value=_mock_httpx_response(500)):
            resp = _client().get("/healthz")

        assert resp.status_code == 503
        body = resp.get_json()
        assert body["supabase"].startswith("degraded")

    def test_redis_exception_returns_503(self, monkeypatch):
        """Redis ping raises → 503."""
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("FORCE_HEALTHZ_FAIL", raising=False)

        with patch("redis.from_url") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("redis down")
            resp = _client().get("/healthz")

        assert resp.status_code == 503
        body = resp.get_json()
        assert body["redis"] == "error"

    def test_supabase_ok_redis_error_returns_503(self, monkeypatch):
        """Mixed health — one bad dep is enough to fail closed."""
        monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("FORCE_HEALTHZ_FAIL", raising=False)

        with patch("httpx.get", return_value=_mock_httpx_response(200)), \
             patch("redis.from_url") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("down")
            resp = _client().get("/healthz")

        assert resp.status_code == 503
        body = resp.get_json()
        assert body["supabase"] == "ok"
        assert body["redis"] == "error"


# ──────────────────────────────────────────────────────────────────
# Regression coverage for the existing drill short-circuit
# ──────────────────────────────────────────────────────────────────


class TestHealthzDrill:
    """FORCE_HEALTHZ_FAIL=1 short-circuits to 503 without touching deps."""

    def test_drill_returns_503(self, monkeypatch):
        monkeypatch.setenv("FORCE_HEALTHZ_FAIL", "1")
        # Even with healthy deps configured, drill must short-circuit.
        monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")

        resp = _client().get("/healthz")

        assert resp.status_code == 503
        body = resp.get_json()
        assert body["supabase"] == "drill_forced_failure"

    def test_drill_only_triggers_on_exact_value(self):
        """FORCE_HEALTHZ_FAIL=0 / unset must NOT trigger the drill.

        Hermetic: patches os.getenv directly so the load_dotenv(override=True)
        on app reload cannot rehydrate SUPABASE_URL/REDIS_URL from .env
        (round-2 Codex review caught the prior monkeypatch.delenv pattern
        as env-dependent — this test was failing 1/9 in Codex's workspace
        because the rehydrated SUPABASE_URL pointed at an unreachable host)."""
        real_getenv = os.environ.get

        def fake_getenv(key, default=None):
            if key == "FORCE_HEALTHZ_FAIL":
                return "0"
            if key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "REDIS_URL"):
                return None
            return real_getenv(key, default)

        backend_app = _import_app()
        with patch.object(backend_app.os, "getenv", side_effect=fake_getenv):
            resp = backend_app.app.test_client().get("/healthz")

        assert resp.status_code == 200
        body = resp.get_json()
        assert "drill_forced_failure" not in str(body)
