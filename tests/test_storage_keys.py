"""Tests for storage.py key patterns."""
import pytest
import os


class TestKeyToFilepath:
    """Test _key_to_filepath maps all key patterns correctly."""

    def test_assignment_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('assignment:Test Quiz')
        assert path is not None
        assert 'assignments' in path
        assert 'Test Quiz.json' in path

    def test_rubric_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('rubric')
        assert path is not None

    def test_settings_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('settings')
        assert path is not None

    def test_results_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('results')
        assert path is not None

    def test_resource_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('resource:abc-123')
        assert path is not None
        assert 'resources' in path

    def test_clever_link_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('clever_link:xyz')
        assert path is not None
        assert 'clever_links' in path

    def test_lesson_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('lesson:unit1:topic')
        assert path is not None
        assert 'lessons' in path

    def test_unknown_key_returns_none(self):
        from backend.storage import _key_to_filepath
        assert _key_to_filepath('unknown:key') is None

    def test_period_key(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('period:Period 1')
        assert path is not None


class TestSaveLoadDelete:
    """Test save/load/delete cycle for resource keys."""

    def test_resource_roundtrip(self):
        from backend.storage import save, load, delete
        data = {"title": "Test", "content": {"sections": []}}
        assert save('resource:test-roundtrip', data, 'local-dev')
        loaded = load('resource:test-roundtrip', 'local-dev')
        assert loaded['title'] == 'Test'
        delete('resource:test-roundtrip', 'local-dev')
        assert load('resource:test-roundtrip', 'local-dev') is None

    def test_clever_link_roundtrip(self, monkeypatch):
        # Issue #731: with a configured .env this test used to take the
        # Supabase branch and write/delete a LIVE teacher_data row
        # (teacher_id='system'). Pin it to the file backend — the same path
        # CI exercises (no SUPABASE_URL there) — so the roundtrip contract
        # is tested without touching production.
        import backend.storage as storage
        monkeypatch.setattr(storage, "_is_supabase_configured", lambda: False)
        from backend.storage import save, load, delete
        data = {"supabase_user_id": "uid-123"}
        assert save('clever_link:test-link', data, 'system')
        loaded = load('clever_link:test-link', 'system')
        assert loaded['supabase_user_id'] == 'uid-123'
        delete('clever_link:test-link', 'system')
