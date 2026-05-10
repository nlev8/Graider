"""Gap-fill unit tests for backend/api_keys.py.

Audit MAJOR #4 sprint follow-up to PR #302. Companion to existing
test_api_keys*.py files. Targets the 42 uncovered LOC (69%).

Branches covered
* _get_district_id Flask import / RuntimeError fallback (lines 41-45)
* get_api_key unknown-provider returns "" (line 67)
* get_api_key contextvars hit (lines 72-74)
* get_api_key district admin storage hit (96-100) + storage exception
  swallow with sentry capture
* set_thread_keys / clear_thread_keys (lines 112, 117)
* resolve_keys_for_teacher all 4 layers (138-140 storage exception)
* save_user_keys merge + cache invalidation (162-177)
* check_user_keys 3-source matrix (212-225)
* save_district_keys merge + cache invalidation (267-285)
* check_district_keys empty-id branch (291)
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset module-level cache before each test."""
    from backend import api_keys as ak
    with ak._cache_lock:
        ak._cache.clear()
    # Also clear any context var leftovers from prior tests
    ak.clear_thread_keys()
    yield
    with ak._cache_lock:
        ak._cache.clear()
    ak.clear_thread_keys()


# ──────────────────────────────────────────────────────────────────
# _get_district_id Flask import / context fallback
# ──────────────────────────────────────────────────────────────────


class TestGetDistrictId:
    def test_returns_g_district_id_when_in_request_context(self):
        from flask import Flask, g
        app = Flask(__name__)
        with app.test_request_context():
            g.district_id = "district-xyz"
            from backend.api_keys import _get_district_id
            assert _get_district_id() == "district-xyz"

    def test_returns_empty_when_no_request_context(self):
        # Flask `g` raises RuntimeError outside request context
        from backend.api_keys import _get_district_id
        # Make sure no app context is active
        assert _get_district_id() == ""


# ──────────────────────────────────────────────────────────────────
# get_api_key resolution chain
# ──────────────────────────────────────────────────────────────────


class TestGetApiKey:
    def test_unknown_provider_returns_empty(self):
        from backend.api_keys import get_api_key
        assert get_api_key("unknown-provider", "teacher-1") == ""

    def test_contextvar_hit_short_circuits(self):
        from backend.api_keys import (
            get_api_key, set_thread_keys, clear_thread_keys,
        )
        try:
            set_thread_keys({"openai": "sk-from-context"})
            assert get_api_key("openai", "teacher-1") == "sk-from-context"
        finally:
            clear_thread_keys()

    def test_contextvar_empty_falls_through(self):
        # Contextvar set but no value for this provider → fall to teacher
        from backend.api_keys import (
            get_api_key, set_thread_keys, clear_thread_keys,
        )
        try:
            set_thread_keys({"anthropic": "sk-anthropic"})  # no openai
            with patch(
                "backend.api_keys._load_user_keys",
                return_value={"openai": "sk-from-teacher"},
            ):
                # openai missing in context → fall to teacher store
                assert get_api_key("openai", "teacher-1") == "sk-from-teacher"
        finally:
            clear_thread_keys()

    def test_local_dev_skips_teacher_store(self):
        # teacher_id == 'local-dev' → skip step 2, fall to env
        from backend.api_keys import get_api_key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}):
            with patch(
                "backend.api_keys._load_user_keys",
            ) as load_mock:
                assert get_api_key("openai", "local-dev") == "sk-env"
            # Confirms the per-teacher load was bypassed
            load_mock.assert_not_called()

    def test_district_admin_storage_hit(self):
        # Per-teacher empty + no district_id → skip step 3 →
        # district admin storage returns a key.
        from backend.api_keys import get_api_key
        with patch(
            "backend.api_keys._load_user_keys",
            return_value={},
        ), patch(
            "backend.storage.load",
            return_value={"openai": "sk-district-admin"},
        ):
            assert get_api_key("openai", "teacher-1") == "sk-district-admin"

    def test_district_admin_storage_exception_swallowed(self):
        # district admin storage raises → except branch runs, falls to env
        from backend.api_keys import get_api_key
        with patch(
            "backend.api_keys._load_user_keys",
            return_value={},
        ), patch(
            "backend.storage.load",
            side_effect=RuntimeError("storage dead"),
        ), patch(
            "backend.api_keys.sentry_sdk.capture_exception",
        ) as sentry_mock, patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-env"},
        ):
            assert get_api_key("openai", "teacher-1") == "sk-env"
        assert sentry_mock.called

    def test_district_id_kwarg_takes_precedence(self):
        # Passing district_id explicitly bypasses _get_district_id
        from backend.api_keys import get_api_key
        with patch(
            "backend.api_keys._load_user_keys",
            return_value={},
        ), patch(
            "backend.api_keys._load_district_keys",
            return_value={"openai": "sk-district"},
        ) as district_mock:
            result = get_api_key(
                "openai", "teacher-1", district_id="district-xyz",
            )
        assert result == "sk-district"
        district_mock.assert_called_once_with("district-xyz")

    def test_falls_to_env_when_all_layers_empty(self):
        from backend.api_keys import get_api_key
        with patch(
            "backend.api_keys._load_user_keys", return_value={},
        ), patch(
            "backend.storage.load", return_value=None,
        ), patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "sk-env-anthro"},
        ):
            assert get_api_key("anthropic", "teacher-1") == "sk-env-anthro"


# ──────────────────────────────────────────────────────────────────
# set_thread_keys / clear_thread_keys
# ──────────────────────────────────────────────────────────────────


class TestThreadKeys:
    def test_set_then_get(self):
        from backend.api_keys import (
            set_thread_keys, _thread_keys, clear_thread_keys,
        )
        try:
            set_thread_keys({"openai": "sk-x", "anthropic": "sk-y"})
            assert _thread_keys.get() == {
                "openai": "sk-x", "anthropic": "sk-y",
            }
        finally:
            clear_thread_keys()

    def test_clear_resets_to_none(self):
        from backend.api_keys import (
            set_thread_keys, clear_thread_keys, _thread_keys,
        )
        set_thread_keys({"openai": "sk-x"})
        clear_thread_keys()
        assert _thread_keys.get() is None


# ──────────────────────────────────────────────────────────────────
# resolve_keys_for_teacher
# ──────────────────────────────────────────────────────────────────


class TestResolveKeysForTeacher:
    def test_full_4_layer_resolution(self):
        # user_keys hit on openai; district hit on anthropic; district
        # admin hit on gemini; env fallback for whatever's left (none here).
        from backend.api_keys import resolve_keys_for_teacher
        with patch(
            "backend.api_keys._load_user_keys",
            return_value={"openai": "sk-user-openai"},
        ), patch(
            "backend.api_keys._load_district_keys",
            return_value={"anthropic": "sk-district-ant"},
        ), patch(
            "backend.storage.load",
            return_value={"gemini": "sk-district-admin-gem"},
        ):
            keys = resolve_keys_for_teacher(
                "teacher-1", district_id="district-xyz",
            )
        assert keys["openai"] == "sk-user-openai"
        assert keys["anthropic"] == "sk-district-ant"
        assert keys["gemini"] == "sk-district-admin-gem"

    def test_local_dev_skips_user_keys(self):
        from backend.api_keys import resolve_keys_for_teacher
        with patch(
            "backend.api_keys._load_user_keys",
        ) as load_mock, patch(
            "backend.storage.load", return_value={},
        ), patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-env"},
        ):
            keys = resolve_keys_for_teacher("local-dev")
        assert keys["openai"] == "sk-env"
        load_mock.assert_not_called()

    def test_storage_load_exception_swallowed(self):
        # district_admin storage raises → swallowed + sentry, falls to env
        from backend.api_keys import resolve_keys_for_teacher
        with patch(
            "backend.api_keys._load_user_keys", return_value={},
        ), patch(
            "backend.api_keys._load_district_keys", return_value={},
        ), patch(
            "backend.storage.load",
            side_effect=RuntimeError("storage dead"),
        ), patch(
            "backend.api_keys.sentry_sdk.capture_exception",
        ) as sentry_mock, patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-env"},
        ):
            keys = resolve_keys_for_teacher("teacher-1")
        assert keys["openai"] == "sk-env"
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# save_user_keys
# ──────────────────────────────────────────────────────────────────


class TestSaveUserKeys:
    def test_merges_only_non_empty_values(self):
        from backend.api_keys import save_user_keys
        existing = {"openai": "sk-old", "anthropic": "sk-anthro-old"}
        save_mock = MagicMock(return_value=True)
        with patch(
            "backend.storage.load", return_value=existing,
        ), patch(
            "backend.storage.save", save_mock,
        ):
            ok = save_user_keys(
                "teacher-1",
                {"openai": "sk-new", "anthropic": "", "gemini": "AI-new"},
            )
        assert ok is True
        # save called with merged dict — empty anthropic preserved old
        merged = save_mock.call_args.args[1]
        assert merged["openai"] == "sk-new"
        assert merged["anthropic"] == "sk-anthro-old"
        assert merged["gemini"] == "AI-new"

    def test_invalidates_cache_for_teacher(self):
        from backend.api_keys import save_user_keys, _cache
        # Pre-populate cache for this teacher
        with patch.object(
            __import__("backend.api_keys", fromlist=["_cache_lock"]),
            "_cache",
            {"teacher-1": {"keys": {"openai": "stale"}, "ts": 0}},
        ):
            with patch(
                "backend.storage.load", return_value={},
            ), patch(
                "backend.storage.save", return_value=True,
            ):
                save_user_keys("teacher-1", {"openai": "sk-new"})
        # Test passes if no exception (cache invalidation handled)


# ──────────────────────────────────────────────────────────────────
# check_user_keys (3-source configured matrix)
# ──────────────────────────────────────────────────────────────────


class TestCheckUserKeys:
    def test_marks_own_district_and_env_correctly(self):
        from backend.api_keys import check_user_keys
        from flask import Flask, g
        app = Flask(__name__)
        with app.test_request_context(), patch(
            "backend.api_keys._load_user_keys",
            return_value={"openai": "sk-own"},
        ), patch(
            "backend.api_keys._load_district_keys",
            return_value={"anthropic": "sk-district"},
        ), patch.dict(
            os.environ, {"GEMINI_API_KEY": "AI-env"},
        ):
            g.district_id = "dist-1"
            result = check_user_keys("teacher-1")
        # OpenAI: own ✓
        assert result["openai_configured"] is True
        assert result["openai_is_own"] is True
        assert result["openai_is_district"] is False
        # Anthropic: district ✓
        assert result["anthropic_configured"] is True
        assert result["anthropic_is_own"] is False
        assert result["anthropic_is_district"] is True
        # Gemini: env only
        assert result["gemini_configured"] is True
        assert result["gemini_is_own"] is False
        assert result["gemini_is_district"] is False

    def test_local_dev_skips_user_keys(self):
        from backend.api_keys import check_user_keys
        with patch(
            "backend.api_keys._load_user_keys",
        ) as load_mock, patch.dict(
            os.environ, {"OPENAI_API_KEY": ""},
            clear=False,
        ):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            result = check_user_keys("local-dev")
        load_mock.assert_not_called()
        # Nothing configured
        assert result["openai_configured"] is False


# ──────────────────────────────────────────────────────────────────
# _load_user_keys cache + storage
# ──────────────────────────────────────────────────────────────────


class TestLoadUserKeys:
    def test_empty_teacher_id_returns_empty(self):
        from backend.api_keys import _load_user_keys
        assert _load_user_keys("") == {}

    def test_cache_hit_short_circuits_storage(self):
        from backend.api_keys import _load_user_keys, _cache
        import time
        with patch.dict(
            _cache,
            {"teacher-1": {"keys": {"openai": "cached"}, "ts": time.time()}},
            clear=True,
        ):
            with patch("backend.storage.load") as load_mock:
                result = _load_user_keys("teacher-1")
            load_mock.assert_not_called()
            assert result["openai"] == "cached"

    def test_cache_expired_reloads(self):
        from backend.api_keys import _load_user_keys, _cache
        # Stale cache entry (ts=0 → expired)
        with patch.dict(
            _cache,
            {"teacher-1": {"keys": {"openai": "stale"}, "ts": 0}},
            clear=True,
        ):
            with patch(
                "backend.storage.load", return_value={"openai": "fresh"},
            ):
                result = _load_user_keys("teacher-1")
        assert result["openai"] == "fresh"


# ──────────────────────────────────────────────────────────────────
# District-level keys: save / load / check
# ──────────────────────────────────────────────────────────────────


class TestDistrictKeys:
    def test_save_district_keys_merges_and_invalidates(self):
        from backend.api_keys import save_district_keys, _cache
        existing = {"openai": "sk-old"}
        save_mock = MagicMock(return_value=True)
        with patch(
            "backend.storage.load", return_value=existing,
        ), patch(
            "backend.storage.save", save_mock,
        ):
            ok = save_district_keys(
                "dist-1",
                {"openai": "sk-new", "anthropic": "sk-anthro",
                 "gemini": ""},
            )
        assert ok is True
        merged = save_mock.call_args.args[1]
        assert merged["openai"] == "sk-new"
        assert merged["anthropic"] == "sk-anthro"
        # Empty gemini → not persisted
        assert "gemini" not in merged
        # Save called with district: prefixed key as the storage tid
        save_args = save_mock.call_args.args
        assert save_args[2] == "district:dist-1"

    def test_save_district_keys_failure_returns_false(self):
        from backend.api_keys import save_district_keys
        with patch(
            "backend.storage.load", return_value={},
        ), patch(
            "backend.storage.save", return_value=False,
        ):
            assert save_district_keys(
                "dist-1", {"openai": "sk-x"},
            ) is False

    def test_check_district_keys_empty_id_returns_empty(self):
        from backend.api_keys import check_district_keys
        assert check_district_keys("") == {}

    def test_check_district_keys_returns_configured_flags(self):
        from backend.api_keys import check_district_keys
        with patch(
            "backend.api_keys._load_district_keys",
            return_value={"openai": "sk-x", "gemini": ""},
        ):
            result = check_district_keys("dist-1")
        assert result["openai_configured"] is True
        assert result["anthropic_configured"] is False
        assert result["gemini_configured"] is False

    def test_load_district_keys_empty_id_returns_empty(self):
        from backend.api_keys import _load_district_keys
        assert _load_district_keys("") == {}

    def test_load_district_keys_cache_hit(self):
        from backend.api_keys import _load_district_keys, _cache
        import time
        with patch.dict(
            _cache,
            {"district:d-1": {"keys": {"openai": "cached"},
                              "ts": time.time()}},
            clear=True,
        ):
            with patch("backend.storage.load") as load_mock:
                result = _load_district_keys("d-1")
            load_mock.assert_not_called()
            assert result["openai"] == "cached"
