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

    def test_supabase_not_configured_redis_ok_returns_200(self, monkeypatch):
        """`not configured` (dev/test where the dep isn't wired) is treated
        as healthy alongside `ok`. monkeypatch.delenv on REDIS_URL is
        unreliable here because backend/app.py:30 calls load_dotenv with
        override=True on reload, so we test the SUPABASE side which the
        route guards before httpx — the env-load doesn't shortcut the
        early `if not supabase_url` check."""
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("FORCE_HEALTHZ_FAIL", raising=False)

        with patch("redis.from_url") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            resp = _client().get("/healthz")

        assert resp.status_code == 200
        body = resp.get_json()
        # supabase env may be re-loaded from .env via override=True; the
        # important contract is that 'not configured' OR 'ok' both → 200.
        assert body["supabase"] in ("not configured", "ok")
        assert body["redis"] == "ok"


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

    def test_drill_only_triggers_on_exact_value(self, monkeypatch):
        """FORCE_HEALTHZ_FAIL=0 / unset must NOT trigger the drill."""
        monkeypatch.setenv("FORCE_HEALTHZ_FAIL", "0")
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)

        resp = _client().get("/healthz")

        assert resp.status_code == 200
        body = resp.get_json()
        assert "drill_forced_failure" not in str(body)
