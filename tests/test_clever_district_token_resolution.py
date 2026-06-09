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


def _clear_dtoken_cache():
    """Drop any cached auto-discovered district tokens so tests are isolated."""
    from backend import api_keys
    with api_keys._cache_lock:
        for k in [k for k in api_keys._cache if k.startswith("clever_dtoken:")]:
            del api_keys._cache[k]


def test_no_token_anywhere_returns_empty(monkeypatch):
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens", return_value=[]):
        assert resolve_clever_district_token("district-D1") == ""


# --- Cycle 3: auto-discovery via Clever /oauth/tokens -----------------------

def test_autodiscovers_token_when_no_stored_or_env(monkeypatch):
    """No stored token, no env → discover from Clever /oauth/tokens by id."""
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens",
               return_value=[{"district_id": "D1", "access_token": "auto-D1"}]):
        assert resolve_clever_district_token("D1") == "auto-D1"


def test_autodiscovery_matches_the_requested_district(monkeypatch):
    """With several districts' tokens, return the one matching district_id."""
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    tokens = [
        {"district_id": "D1", "access_token": "tok-D1"},
        {"district_id": "D2", "access_token": "tok-D2"},
    ]
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens", return_value=tokens):
        assert resolve_clever_district_token("D2") == "tok-D2"


def test_autodiscovery_no_match_returns_empty(monkeypatch):
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens",
               return_value=[{"district_id": "OTHER", "access_token": "x"}]):
        assert resolve_clever_district_token("D1") == ""


def test_autodiscovery_caches_success(monkeypatch):
    """A discovered token is cached — the second resolve doesn't re-fetch."""
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens",
               return_value=[{"district_id": "D1", "access_token": "auto-D1"}]) as m:
        assert resolve_clever_district_token("D1") == "auto-D1"
        assert resolve_clever_district_token("D1") == "auto-D1"
    assert m.call_count == 1, "second resolve should hit the cache, not /oauth/tokens"


def test_stored_token_skips_autodiscovery(monkeypatch):
    """A stored per-district token short-circuits before any network call."""
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys",
               return_value={"clever_district_token": "stored-D1"}), \
         patch("backend.clever.fetch_district_tokens") as m:
        assert resolve_clever_district_token("D1") == "stored-D1"
        m.assert_not_called()


def test_env_token_skips_autodiscovery(monkeypatch):
    """The env var (single-district installs) short-circuits discovery too."""
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens") as m:
        assert resolve_clever_district_token("D1") == "env-token"
        m.assert_not_called()


# --- Cycle 4: clever.fetch_district_tokens parses /oauth/tokens --------------

def _http_resp(status, json_data):
    from unittest.mock import MagicMock
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    return r


def test_fetch_district_tokens_returns_only_district_owned():
    import backend.clever as clever
    payload = {"data": [
        {"owner": {"type": "district", "id": "D1"}, "access_token": "tok-D1"},
        {"owner": {"type": "school", "id": "S9"}, "access_token": "tok-S9"},
        {"owner": {"type": "district", "id": "D2"}, "access_token": "tok-D2"},
        {"owner": {"type": "district", "id": "D3"}},  # no token → skipped
    ]}
    with patch("backend.clever.get_clever_config",
               return_value={"client_id": "c", "client_secret": "s", "redirect_uri": "u"}), \
         patch("backend.clever.httpx.get", return_value=_http_resp(200, payload)):
        out = clever.fetch_district_tokens()
    assert out == [
        {"district_id": "D1", "access_token": "tok-D1"},
        {"district_id": "D2", "access_token": "tok-D2"},
    ]


def test_fetch_district_tokens_no_config_returns_empty():
    import backend.clever as clever
    with patch("backend.clever.get_clever_config", return_value=None), \
         patch("backend.clever.httpx.get") as m:
        assert clever.fetch_district_tokens() == []
        m.assert_not_called()  # never hit the network without app creds


def test_fetch_district_tokens_non_200_returns_empty():
    import backend.clever as clever
    with patch("backend.clever.get_clever_config",
               return_value={"client_id": "c", "client_secret": "s", "redirect_uri": "u"}), \
         patch("backend.clever.httpx.get", return_value=_http_resp(401, {})):
        assert clever.fetch_district_tokens() == []


def test_fetch_district_tokens_http_error_returns_empty():
    import httpx
    import backend.clever as clever
    with patch("backend.clever.get_clever_config",
               return_value={"client_id": "c", "client_secret": "s", "redirect_uri": "u"}), \
         patch("backend.clever.httpx.get", side_effect=httpx.HTTPError("boom")):
        assert clever.fetch_district_tokens() == []


def test_autodiscovery_failure_not_cached_retries(monkeypatch):
    """An empty/failed discovery is NOT cached — the next sync retries, so a
    district that connects LATER is picked up without a 5-minute stale empty."""
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens", return_value=[]) as m:
        assert resolve_clever_district_token("D1") == ""
        assert resolve_clever_district_token("D1") == ""
    assert m.call_count == 2, "empty discovery must not be cached"


def test_autodiscovery_isolates_fetch_exception(monkeypatch):
    """If discovery raises, the resolver degrades to '' rather than crashing
    the login / roster-sync path."""
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _clear_dtoken_cache()
    with patch("backend.api_keys._load_district_keys", return_value={}), \
         patch("backend.clever.fetch_district_tokens", side_effect=RuntimeError("boom")):
        assert resolve_clever_district_token("D1") == ""


def test_fetch_district_tokens_sends_basic_auth_and_owner_type_param():
    import backend.clever as clever
    captured = {}

    def _fake_get(url, **kw):
        captured["url"] = url
        captured["params"] = kw.get("params")
        captured["headers"] = kw.get("headers") or {}
        return _http_resp(200, {"data": []})

    with patch("backend.clever.get_clever_config",
               return_value={"client_id": "cid", "client_secret": "sec", "redirect_uri": "u"}), \
         patch("backend.clever.httpx.get", side_effect=_fake_get):
        clever.fetch_district_tokens()
    assert captured["url"] == clever.CLEVER_TOKEN_URL
    assert captured["params"] == {"owner_type": "district"}
    assert captured["headers"].get("Authorization", "").startswith("Basic ")


def test_fetch_district_tokens_malformed_json_returns_empty():
    import backend.clever as clever
    from unittest.mock import MagicMock
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"data": "not-a-list"}  # malformed shape
    with patch("backend.clever.get_clever_config",
               return_value={"client_id": "c", "client_secret": "s", "redirect_uri": "u"}), \
         patch("backend.clever.httpx.get", return_value=r):
        assert clever.fetch_district_tokens() == []


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
