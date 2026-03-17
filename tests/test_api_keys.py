"""
Tests for the BYOK API key resolver, including district-level key support.
"""
import os
import tempfile
import json

import pytest

# Patch storage dirs before import
_tmpdir = tempfile.mkdtemp()

import backend.api_keys as api_keys


class TestDistrictKeys:
    """Test district-level API key resolution."""

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        """Clear the key cache before each test."""
        api_keys._cache.clear()
        yield
        api_keys._cache.clear()

    def test_load_district_keys_empty(self):
        assert api_keys._load_district_keys("") == {}
        assert api_keys._load_district_keys(None) == {}

    def test_save_and_load_district_keys(self, monkeypatch):
        """District keys round-trip through save/load."""
        # Use file-based storage (no Supabase in tests)
        storage_dir = os.path.join(_tmpdir, "district_storage")
        os.makedirs(storage_dir, exist_ok=True)
        keys_file = os.path.join(storage_dir, "district_test123_api_keys.json")

        # Mock storage.load and storage.save to use temp files
        saved = {}

        def mock_load(key, teacher_id):
            return saved.get(f"{teacher_id}:{key}")

        def mock_save(key, data, teacher_id):
            saved[f"{teacher_id}:{key}"] = data
            return True

        monkeypatch.setattr("backend.api_keys._load_user_keys",
                            lambda tid: {})
        import backend.storage
        monkeypatch.setattr(backend.storage, "load", mock_load)
        monkeypatch.setattr(backend.storage, "save", mock_save)

        # Save district keys
        ok = api_keys.save_district_keys("test123", {"openai": "sk-district-key"})
        assert ok is True

        # Clear cache to force reload
        api_keys._cache.clear()

        # Load should find the key
        keys = api_keys._load_district_keys("test123")
        assert keys.get("openai") == "sk-district-key"

    def test_save_district_keys_merges(self, monkeypatch):
        """Saving district keys merges with existing, doesn't overwrite."""
        saved = {}

        def mock_load(key, teacher_id):
            return saved.get(f"{teacher_id}:{key}")

        def mock_save(key, data, teacher_id):
            saved[f"{teacher_id}:{key}"] = data
            return True

        import backend.storage
        monkeypatch.setattr(backend.storage, "load", mock_load)
        monkeypatch.setattr(backend.storage, "save", mock_save)

        # Save openai key
        api_keys.save_district_keys("d1", {"openai": "sk-openai"})
        # Save anthropic key (should keep openai)
        api_keys.save_district_keys("d1", {"anthropic": "sk-ant"})

        api_keys._cache.clear()
        keys = api_keys._load_district_keys("d1")
        assert keys.get("openai") == "sk-openai"
        assert keys.get("anthropic") == "sk-ant"

    def test_save_district_keys_ignores_empty(self, monkeypatch):
        """Empty strings should not overwrite existing keys."""
        saved = {}

        def mock_load(key, teacher_id):
            return saved.get(f"{teacher_id}:{key}")

        def mock_save(key, data, teacher_id):
            saved[f"{teacher_id}:{key}"] = data
            return True

        import backend.storage
        monkeypatch.setattr(backend.storage, "load", mock_load)
        monkeypatch.setattr(backend.storage, "save", mock_save)

        api_keys.save_district_keys("d1", {"openai": "sk-real"})
        api_keys.save_district_keys("d1", {"openai": ""})  # should NOT clear

        api_keys._cache.clear()
        keys = api_keys._load_district_keys("d1")
        assert keys.get("openai") == "sk-real"

    def test_check_district_keys(self, monkeypatch):
        """check_district_keys returns booleans, never values."""
        saved = {"district:d1:api_keys": {"openai": "sk-secret", "anthropic": ""}}

        def mock_load(key, teacher_id):
            return saved.get(f"{teacher_id}:{key}")

        import backend.storage
        monkeypatch.setattr(backend.storage, "load", mock_load)

        result = api_keys.check_district_keys("d1")
        assert result["openai_configured"] is True
        assert result["anthropic_configured"] is False
        assert result.get("gemini_configured") is False
        # Values should never appear in result
        assert "sk-secret" not in str(result)


class TestResolutionOrder:
    """Test the full resolution hierarchy: teacher → district → env."""

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        api_keys._cache.clear()
        yield
        api_keys._cache.clear()

    def test_teacher_key_wins_over_district(self, monkeypatch):
        """Per-teacher key should take priority over district key."""
        monkeypatch.setattr(api_keys, "_load_user_keys",
                            lambda tid: {"openai": "sk-teacher"})
        monkeypatch.setattr(api_keys, "_load_district_keys",
                            lambda did: {"openai": "sk-district"})
        monkeypatch.setattr(api_keys, "_get_district_id", lambda: "d1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        assert api_keys.get_api_key("openai", "teacher1") == "sk-teacher"

    def test_district_key_wins_over_env(self, monkeypatch):
        """District key should take priority over environment variable."""
        monkeypatch.setattr(api_keys, "_load_user_keys",
                            lambda tid: {})
        monkeypatch.setattr(api_keys, "_load_district_keys",
                            lambda did: {"openai": "sk-district"})
        monkeypatch.setattr(api_keys, "_get_district_id", lambda: "d1")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")

        assert api_keys.get_api_key("openai", "teacher1") == "sk-district"

    def test_env_fallback_when_no_teacher_or_district(self, monkeypatch):
        """Environment variable used when no teacher or district key."""
        monkeypatch.setattr(api_keys, "_load_user_keys",
                            lambda tid: {})
        monkeypatch.setattr(api_keys, "_get_district_id", lambda: "")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

        assert api_keys.get_api_key("openai", "teacher1") == "sk-env"

    def test_resolve_keys_includes_district(self, monkeypatch):
        """resolve_keys_for_teacher should check district keys."""
        monkeypatch.setattr(api_keys, "_load_user_keys",
                            lambda tid: {"gemini": "gem-teacher"})
        monkeypatch.setattr(api_keys, "_load_district_keys",
                            lambda did: {"openai": "sk-district", "anthropic": "sk-ant-district"})
        monkeypatch.setattr(api_keys, "_get_district_id", lambda: "d1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        resolved = api_keys.resolve_keys_for_teacher("teacher1")
        assert resolved["openai"] == "sk-district"       # from district
        assert resolved["anthropic"] == "sk-ant-district"  # from district
        assert resolved["gemini"] == "gem-teacher"         # from teacher (overrides district)

    def test_check_user_keys_shows_district(self, monkeypatch):
        """check_user_keys should indicate which keys come from district."""
        monkeypatch.setattr(api_keys, "_load_user_keys",
                            lambda tid: {"openai": "sk-own"})
        monkeypatch.setattr(api_keys, "_load_district_keys",
                            lambda did: {"anthropic": "sk-ant-d"})
        monkeypatch.setattr(api_keys, "_get_district_id", lambda: "d1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        result = api_keys.check_user_keys("teacher1")
        assert result["openai_is_own"] is True
        assert result["openai_is_district"] is False
        assert result["anthropic_is_own"] is False
        assert result["anthropic_is_district"] is True
        assert result["gemini_configured"] is False
