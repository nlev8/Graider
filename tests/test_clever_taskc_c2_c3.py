"""
Task C residuals C2 + C3 (closing-re-score findings).

C3 — `save_district_keys` filtered to AI providers only, so the
`clever_district_token` that `resolve_clever_district_token` reads had
NO write path → Task B's per-district branch was unreachable.

C2 — the periodic-cron path (`sync_routes._sync_one_teacher`) resolved
the token via `config.get('district_token') or os.environ[...]`,
bypassing `resolve_clever_district_token` entirely.

Only the unavoidable storage boundary is mocked (a dict keyed by the
storage cache_key); `_load_district_keys`/resolver run for real.
"""
from unittest.mock import patch

import backend.api_keys as ak
from backend.api_keys import save_district_keys, resolve_clever_district_token


def _storage_backed():
    """Return (load, save) fakes sharing one dict keyed by storage key."""
    blob = {}

    def _save(_ns, value, key):
        blob[key] = dict(value)
        return True

    def _load(_ns, key):
        return dict(blob[key]) if key in blob else None

    return _load, _save, blob


# --- C3: clever_district_token must be persistable + then resolvable -------

def test_save_district_keys_persists_clever_district_token(monkeypatch):
    monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
    _load, _save, blob = _storage_backed()
    with (
        patch("backend.storage.save", side_effect=_save),
        patch("backend.storage.load", side_effect=_load),
    ):
        ak._cache.clear()
        assert save_district_keys("district-D1", {"clever_district_token": "DT-secure"}) is True
    saved = next(iter(blob.values()))
    assert saved.get("clever_district_token") == "DT-secure", blob


def test_resolver_reads_persisted_clever_district_token(monkeypatch):
    """End-to-end write→read: what save_district_keys persists is what
    resolve_clever_district_token returns (the path the re-score found
    broken — resolver read a key nothing could write)."""
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-fallback")
    _load, _save, _ = _storage_backed()
    with (
        patch("backend.storage.save", side_effect=_save),
        patch("backend.storage.load", side_effect=_load),
    ):
        ak._cache.clear()
        save_district_keys("D9", {"clever_district_token": "DT-9"})
        assert resolve_clever_district_token("D9") == "DT-9"


def test_save_district_keys_still_persists_ai_providers(monkeypatch):
    """Regression: C3 must not break the existing AI-provider behavior."""
    _load, _save, blob = _storage_backed()
    with (
        patch("backend.storage.save", side_effect=_save),
        patch("backend.storage.load", side_effect=_load),
    ):
        ak._cache.clear()
        save_district_keys("D2", {"openai": "sk-x", "clever_district_token": "t"})
    saved = next(iter(blob.values()))
    assert saved.get("openai") == "sk-x" and saved.get("clever_district_token") == "t"


# --- C2: periodic-cron must resolve via resolve_clever_district_token -----

def test_periodic_sync_uses_resolver_not_direct_env(monkeypatch):
    """sync_routes._sync_one_teacher (clever) must route token resolution
    through resolve_clever_district_token so a per-district stored token
    is honored by the daily cron (not just the single env var)."""
    monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "env-token")
    from backend.routes import sync_routes

    captured = {}

    async def _fake_clever_sync(token):
        captured["token"] = token
        raise RuntimeError("stop-after-capture")

    teacher = {
        "teacher_id": "clever:t-1",
        "provider": "clever",
        "config": {"district_id": "D-cron"},  # no per-teacher district_token
    }
    with (
        patch("backend.api_keys._load_district_keys",
              return_value={"clever_district_token": "D-cron-token"}),
        patch("backend.clever.sync_roster", side_effect=_fake_clever_sync),
    ):
        sync_routes._sync_one_teacher(teacher)

    assert captured.get("token") == "D-cron-token", captured


def test_sync_routes_has_no_direct_district_token_env():
    """Plan acceptance: the cron path no longer reads
    CLEVER_DISTRICT_TOKEN directly (resolver owns the env fallback).
    Mirrors the test_sis_alerting static-pin convention."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "backend/routes/sync_routes.py").read_text()
    offenders = [
        ln.strip() for ln in src.splitlines()
        if "CLEVER_DISTRICT_TOKEN" in ln
        and ("os.environ" in ln or "os.getenv" in ln)
    ]
    assert offenders == [], (
        "sync_routes.py still reads CLEVER_DISTRICT_TOKEN directly: "
        + repr(offenders)
    )
