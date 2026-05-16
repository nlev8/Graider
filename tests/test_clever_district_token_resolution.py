"""
Task B — per-district Clever Secure-Sync token resolution.

Defect/limitation: roster sync reads the single `CLEVER_DISTRICT_TOKEN`
env var, so a multi-district install can't sync each district with its
own token. The per-district key store already exists
(`_load_district_keys`); the sync path just never consumed it for the
Clever roster token.

Fix: `resolve_clever_district_token(district_id)` — per-district stored
`clever_district_token` wins; otherwise the env var (single-district
installs byte-identical).

No network/storage — `_load_district_keys` is mocked.
"""
from unittest.mock import patch

from backend.api_keys import resolve_clever_district_token


def test_per_district_stored_token_wins_over_env(monkeypatch):
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")
    with patch("backend.api_keys._load_district_keys",
               return_value={"clever_district_token": "district-D1-token"}):
        assert resolve_clever_district_token("district-D1") == "district-D1-token"


def test_falls_back_to_env_when_no_per_district_token(monkeypatch):
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")
    # district has only AI provider keys, no clever_district_token
    with patch("backend.api_keys._load_district_keys",
               return_value={"openai": "sk-xxx"}):
        assert resolve_clever_district_token("district-D1") == "env-token"


def test_none_district_uses_env(monkeypatch):
    """Single-district installs (no district scoping) — unchanged."""
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")
    assert resolve_clever_district_token(None) == "env-token"


def test_no_token_anywhere_returns_empty(monkeypatch):
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    with patch("backend.api_keys._load_district_keys", return_value={}):
        assert resolve_clever_district_token("district-D1") == ""


# --- Cycle 2: the sync paths must consume the resolver ----------------------

def _app():
    from flask import Flask
    from backend.routes.clever_routes import clever_bp
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(clever_bp)
    return app


def test_sync_roster_endpoint_uses_per_district_token(monkeypatch):
    """/api/clever/sync-roster must pass the per-district stored token
    (not the single env var) to clever.sync_roster."""
    from unittest.mock import AsyncMock
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")

    captured = {}

    async def _fake_sync_roster(token):
        captured["token"] = token
        raise RuntimeError("stop-after-capture")  # short-circuit downstream

    app = _app()
    with (
        patch("backend.api_keys._load_district_keys",
              return_value={"clever_district_token": "D1-secure-sync"}),
        patch("backend.routes.clever_routes.sync_roster",
              new=AsyncMock(side_effect=_fake_sync_roster)),
    ):
        with app.test_client() as client:
            with client.session_transaction() as s:
                s["clever_user"] = {
                    "clever_id": "c-1", "type": "teacher",
                    "district": "district-D1", "email": "t@s.edu",
                }
            client.post("/api/clever/sync-roster", json={})

    assert captured.get("token") == "D1-secure-sync", captured


def test_clever_routes_has_no_direct_district_token_getenv():
    """Single source of truth: clever_routes.py must not read
    CLEVER_DISTRICT_TOKEN directly for the sync paths — it routes
    through resolve_clever_district_token. (Plan Task B Step 3
    acceptance; mirrors the static-pin convention of
    test_sis_alerting.py.) The /health presence-bool is exempt — it
    only reports configuration, never selects a token."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "backend/routes/clever_routes.py").read_text()
    offenders = [
        ln for ln in src.splitlines()
        if 'os.getenv("CLEVER_DISTRICT_TOKEN")' in ln
        and "district_token_set" not in ln  # /health presence bool, exempt
    ]
    assert offenders == [], (
        "clever_routes.py still selects CLEVER_DISTRICT_TOKEN directly "
        "instead of via resolve_clever_district_token: " + repr(offenders)
    )
