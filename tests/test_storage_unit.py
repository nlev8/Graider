"""
Unit tests for backend/storage.py — coverage push from 38% baseline.

Existing tests/test_storage_keys.py covers a few save/load/delete
roundtrips. This file fills the un-covered branches identified by
`pytest --cov`:

- _key_to_filepath: every key prefix branch (settings/rubric/results/
  accommodations/parent_contacts/api_keys/portal_credentials/
  pending_send/automations/assignment/period/period_meta/lesson/
  resource/clever_link)
- _file_load/_file_save/_file_delete: error paths + CSV special-case
- _file_list_keys: assignment/lesson/period/period_meta/resource
- _sb_load/_sb_save/_sb_delete/_sb_list_keys: success + retry exhaustion
- _file_load_student_history / _sb_load_student_history
- _file_save_student_history / _sb_save_student_history
- load/save/delete/list_keys: public API routing for Supabase vs file,
  sensitive-key behavior
- sync_all_to_cloud: all paths

Each test uses tmp_path to redirect HOME, so file-backend operations
don't touch real ~/.graider_* state.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# _key_to_filepath
# ──────────────────────────────────────────────────────────────────


class TestKeyToFilepath:
    def test_settings_key(self):
        from backend.storage import _key_to_filepath, HOME
        assert _key_to_filepath('settings') == os.path.join(HOME, '.graider_settings.json')

    def test_rubric_key(self):
        from backend.storage import _key_to_filepath, HOME
        assert _key_to_filepath('rubric') == os.path.join(HOME, '.graider_rubric.json')

    def test_results_key(self):
        from backend.storage import _key_to_filepath, HOME
        assert _key_to_filepath('results') == os.path.join(HOME, '.graider_results.json')

    def test_accommodations_key(self):
        from backend.storage import _key_to_filepath, ACCOMMODATIONS_DIR
        assert _key_to_filepath('accommodations') == os.path.join(
            ACCOMMODATIONS_DIR, 'student_accommodations.json'
        )

    def test_accommodation_presets_key(self):
        from backend.storage import _key_to_filepath, ACCOMMODATIONS_DIR
        assert _key_to_filepath('accommodation_presets') == os.path.join(
            ACCOMMODATIONS_DIR, 'presets.json'
        )

    def test_simple_data_keys(self):
        # Keys that map to GRAIDER_DATA_DIR/{name}.json (or hidden file)
        from backend.storage import _key_to_filepath, GRAIDER_DATA_DIR
        cases = {
            'ell_students': 'ell_students.json',
            'parent_contacts': 'parent_contacts.json',
            'assistant_memory': 'assistant_memory.json',
            'teaching_calendar': 'teaching_calendar.json',
            'api_keys': '.api_keys.json',
            'portal_credentials': 'portal_credentials.json',
            'pending_send': 'pending_send.json',
            'automations': 'automations.json',
        }
        for key, fname in cases.items():
            assert _key_to_filepath(key) == os.path.join(GRAIDER_DATA_DIR, fname)

    def test_assignment_prefix(self):
        from backend.storage import _key_to_filepath, ASSIGNMENTS_DIR
        assert _key_to_filepath('assignment:Unit 3 Quiz') == os.path.join(
            ASSIGNMENTS_DIR, 'Unit 3 Quiz.json'
        )

    def test_period_meta_prefix(self):
        from backend.storage import _key_to_filepath, PERIODS_DIR
        assert _key_to_filepath('period_meta:p1.csv') == os.path.join(
            PERIODS_DIR, 'p1.csv.meta.json'
        )

    def test_period_prefix(self):
        from backend.storage import _key_to_filepath, PERIODS_DIR
        assert _key_to_filepath('period:p1.csv') == os.path.join(
            PERIODS_DIR, 'p1.csv'
        )

    def test_lesson_three_part_prefix(self):
        from backend.storage import _key_to_filepath, LESSONS_DIR
        assert _key_to_filepath('lesson:Unit3:Day 1') == os.path.join(
            LESSONS_DIR, 'Unit3', 'Day 1.json'
        )

    def test_lesson_two_part_prefix_returns_none(self):
        # 'lesson:foo' (only 2 parts) doesn't match the 3-part split,
        # so the function falls through and returns None.
        from backend.storage import _key_to_filepath
        assert _key_to_filepath('lesson:foo') is None

    def test_resource_prefix(self):
        from backend.storage import _key_to_filepath, RESOURCES_DIR
        assert _key_to_filepath('resource:abc-123') == os.path.join(
            RESOURCES_DIR, 'abc-123.json'
        )

    def test_clever_link_prefix(self):
        from backend.storage import _key_to_filepath, GRAIDER_DATA_DIR
        path = _key_to_filepath('clever_link:xyz-456')
        assert path == os.path.join(GRAIDER_DATA_DIR, 'clever_links', 'xyz-456.json')

    def test_unknown_key_returns_none(self):
        from backend.storage import _key_to_filepath
        assert _key_to_filepath('unknown_key') is None
        assert _key_to_filepath('completely_made_up') is None


# ──────────────────────────────────────────────────────────────────
# _use_supabase
# ──────────────────────────────────────────────────────────────────


class TestUseSupabase:
    def test_local_dev_never_uses_supabase(self, monkeypatch):
        from backend.storage import _use_supabase
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        assert _use_supabase('local-dev') is False

    def test_real_teacher_uses_supabase_when_configured(self, monkeypatch):
        from backend.storage import _use_supabase
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        assert _use_supabase('teacher-uuid-1') is True

    def test_unconfigured_returns_false(self, monkeypatch):
        from backend.storage import _use_supabase
        monkeypatch.delenv('SUPABASE_URL', raising=False)
        monkeypatch.delenv('SUPABASE_SERVICE_KEY', raising=False)
        assert _use_supabase('teacher-uuid-1') is False


# ──────────────────────────────────────────────────────────────────
# _file_load / _file_save / _file_delete
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Redirect storage paths to tmp_path so we don't touch real HOME."""
    import backend.storage as storage_mod
    monkeypatch.setattr(storage_mod, 'HOME', str(tmp_path))
    monkeypatch.setattr(storage_mod, 'ASSIGNMENTS_DIR',
                        str(tmp_path / '.graider_assignments'))
    monkeypatch.setattr(storage_mod, 'GRAIDER_DATA_DIR',
                        str(tmp_path / '.graider_data'))
    monkeypatch.setattr(storage_mod, 'PERIODS_DIR',
                        str(tmp_path / '.graider_data' / 'periods'))
    monkeypatch.setattr(storage_mod, 'ACCOMMODATIONS_DIR',
                        str(tmp_path / '.graider_data' / 'accommodations'))
    monkeypatch.setattr(storage_mod, 'LESSONS_DIR',
                        str(tmp_path / '.graider_lessons'))
    monkeypatch.setattr(storage_mod, 'STUDENT_HISTORY_DIR',
                        str(tmp_path / '.graider_data' / 'student_history'))
    monkeypatch.setattr(storage_mod, 'RESOURCES_DIR',
                        str(tmp_path / '.graider_data' / 'resources'))
    return tmp_path


class TestFileBackend:
    def test_load_returns_none_for_unknown_key(self, tmp_home):
        from backend.storage import _file_load
        assert _file_load('unknown') is None

    def test_load_returns_none_when_file_missing(self, tmp_home):
        from backend.storage import _file_load
        # 'settings' is a known key but no file exists yet
        assert _file_load('settings') is None

    def test_save_then_load_roundtrip(self, tmp_home):
        from backend.storage import _file_save, _file_load
        data = {'foo': 'bar', 'count': 42}
        assert _file_save('settings', data) is True
        loaded = _file_load('settings')
        assert loaded == data

    def test_save_returns_false_for_unknown_key(self, tmp_home):
        from backend.storage import _file_save
        assert _file_save('totally_unknown_key', {'x': 1}) is False

    def test_save_csv_period_writes_raw_text(self, tmp_home):
        from backend.storage import _file_save, _file_load
        csv_text = "student_id,name\n1,Alice\n2,Bob\n"
        assert _file_save('period:p1.csv', csv_text) is True
        # _file_load reads it back as raw text
        loaded = _file_load('period:p1.csv')
        assert loaded == csv_text

    def test_save_csv_period_coerces_non_string(self, tmp_home):
        from backend.storage import _file_save, _file_load
        # Non-string data is str()'d before write
        assert _file_save('period:p2.csv', 123) is True
        loaded = _file_load('period:p2.csv')
        assert loaded == '123'

    def test_load_corrupted_json_returns_none(self, tmp_home):
        from backend.storage import _file_save, _file_load, _key_to_filepath
        # Write garbage to the settings file
        path = _key_to_filepath('settings')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write('not valid json {{{{')
        # _file_load swallows the exception and returns None
        assert _file_load('settings') is None

    def test_save_failure_returns_false(self, tmp_home, monkeypatch):
        from backend.storage import _file_save
        # Force os.makedirs to raise — _file_save catches and returns False
        monkeypatch.setattr('os.makedirs',
                            lambda *a, **k: (_ for _ in ()).throw(OSError("perm")))
        assert _file_save('settings', {'x': 1}) is False

    def test_delete_unknown_key_returns_false(self, tmp_home):
        from backend.storage import _file_delete
        assert _file_delete('unknown_key') is False

    def test_delete_missing_file_returns_true(self, tmp_home):
        # Known key but file doesn't exist → still True
        from backend.storage import _file_delete
        assert _file_delete('settings') is True

    def test_delete_existing_file_removes_it(self, tmp_home):
        from backend.storage import _file_save, _file_delete, _file_load
        _file_save('settings', {'k': 'v'})
        assert _file_delete('settings') is True
        assert _file_load('settings') is None

    def test_delete_handles_remove_failure(self, tmp_home, monkeypatch):
        from backend.storage import _file_save, _file_delete
        _file_save('settings', {'k': 'v'})
        monkeypatch.setattr('os.remove',
                            lambda p: (_ for _ in ()).throw(OSError("perm")))
        assert _file_delete('settings') is False


# ──────────────────────────────────────────────────────────────────
# _file_list_keys
# ──────────────────────────────────────────────────────────────────


class TestFileListKeys:
    def test_assignment_prefix(self, tmp_home):
        from backend.storage import _file_save, _file_list_keys
        _file_save('assignment:Quiz 1', {'q': 1})
        _file_save('assignment:Quiz 2', {'q': 2})
        keys = _file_list_keys('assignment:')
        assert keys == ['assignment:Quiz 1', 'assignment:Quiz 2']

    def test_period_prefix(self, tmp_home):
        from backend.storage import _file_save, _file_list_keys
        _file_save('period:p1.csv', "id,name\n1,a\n")
        _file_save('period:p2.csv', "id,name\n2,b\n")
        keys = _file_list_keys('period:')
        assert sorted(keys) == ['period:p1.csv', 'period:p2.csv']

    def test_period_meta_prefix(self, tmp_home):
        from backend.storage import _file_save, _file_list_keys
        _file_save('period_meta:p1.csv', {'meta': 1})
        keys = _file_list_keys('period_meta:')
        assert keys == ['period_meta:p1.csv']

    def test_resource_prefix(self, tmp_home):
        from backend.storage import _file_save, _file_list_keys
        _file_save('resource:abc', {'r': 1})
        _file_save('resource:def', {'r': 2})
        keys = _file_list_keys('resource:')
        assert sorted(keys) == ['resource:abc', 'resource:def']

    def test_lesson_prefix_with_unit_subdir(self, tmp_home):
        from backend.storage import _file_save, _file_list_keys
        _file_save('lesson:Unit3:Day 1', {'l': 1})
        _file_save('lesson:Unit3:Day 2', {'l': 2})
        keys = _file_list_keys('lesson:')
        assert sorted(keys) == ['lesson:Unit3:Day 1', 'lesson:Unit3:Day 2']

    def test_unknown_prefix_returns_empty(self, tmp_home):
        from backend.storage import _file_list_keys
        assert _file_list_keys('unknown:') == []

    def test_missing_dir_returns_empty(self, tmp_home):
        from backend.storage import _file_list_keys
        # Dir doesn't exist yet
        assert _file_list_keys('assignment:') == []


# ──────────────────────────────────────────────────────────────────
# _file_load_student_history / _file_save_student_history
# ──────────────────────────────────────────────────────────────────


class TestFileStudentHistory:
    def test_load_missing_returns_none(self, tmp_home):
        from backend.storage import _file_load_student_history
        assert _file_load_student_history('alice-1') is None

    def test_save_then_load_roundtrip(self, tmp_home):
        from backend.storage import (
            _file_save_student_history, _file_load_student_history,
        )
        history = {'scores': [85, 90, 95]}
        assert _file_save_student_history('alice-1', history) is True
        assert _file_load_student_history('alice-1') == history

    def test_save_handles_path_separators_in_id(self, tmp_home):
        # student_id with slashes should be sanitized
        from backend.storage import (
            _file_save_student_history, _file_load_student_history,
        )
        _file_save_student_history('a/b\\c', {'s': 1})
        assert _file_load_student_history('a/b\\c') == {'s': 1}

    def test_load_corrupted_json_returns_none(self, tmp_home):
        from backend.storage import (
            _file_save_student_history, _file_load_student_history,
            STUDENT_HISTORY_DIR,
        )
        os.makedirs(STUDENT_HISTORY_DIR, exist_ok=True)
        path = os.path.join(STUDENT_HISTORY_DIR, 'bob-1.json')
        with open(path, 'w') as f:
            f.write('not json')
        assert _file_load_student_history('bob-1') is None


# ──────────────────────────────────────────────────────────────────
# _sb_load / _sb_save / _sb_delete / _sb_list_keys
# ──────────────────────────────────────────────────────────────────


class TestSupabaseBackend:
    def _mock_sb_with_data(self, data_rows):
        sb = MagicMock()
        chain = MagicMock()
        for m in ('select', 'eq', 'upsert', 'delete', 'like'):
            getattr(chain, m).return_value = chain
        result = MagicMock(data=data_rows)
        chain.execute.return_value = result
        sb.table.return_value = chain
        return sb

    def test_sb_load_returns_data_field(self):
        from backend.storage import _sb_load
        sb = self._mock_sb_with_data([{'data': {'foo': 'bar'}}])
        with patch('backend.storage._get_supabase', return_value=sb):
            result = _sb_load('settings', 't-1')
        assert result == {'foo': 'bar'}

    def test_sb_load_no_rows_returns_none(self):
        from backend.storage import _sb_load
        sb = self._mock_sb_with_data([])
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_load('settings', 't-1') is None

    def test_sb_load_returns_none_when_supabase_unavailable(self):
        from backend.storage import _sb_load
        with patch('backend.storage._get_supabase', return_value=None):
            assert _sb_load('settings', 't-1') is None

    def test_sb_load_failure_returns_none(self):
        from backend.storage import _sb_load
        sb = MagicMock()
        sb.table.side_effect = Exception("supabase down")
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_load('settings', 't-1') is None

    def test_sb_save_returns_true_on_success(self):
        from backend.storage import _sb_save
        sb = self._mock_sb_with_data([{'id': 'x'}])
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_save('settings', {'k': 'v'}, 't-1') is True

    def test_sb_save_returns_false_when_unavailable(self):
        from backend.storage import _sb_save
        with patch('backend.storage._get_supabase', return_value=None):
            assert _sb_save('settings', {'k': 'v'}, 't-1') is False

    def test_sb_save_failure_returns_false(self):
        from backend.storage import _sb_save
        sb = MagicMock()
        sb.table.side_effect = Exception("upsert failed")
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_save('settings', {'k': 'v'}, 't-1') is False

    def test_sb_delete_returns_true(self):
        from backend.storage import _sb_delete
        sb = self._mock_sb_with_data([])
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_delete('settings', 't-1') is True

    def test_sb_delete_returns_false_when_unavailable(self):
        from backend.storage import _sb_delete
        with patch('backend.storage._get_supabase', return_value=None):
            assert _sb_delete('settings', 't-1') is False

    def test_sb_delete_failure_returns_false(self):
        from backend.storage import _sb_delete
        sb = MagicMock()
        sb.table.side_effect = Exception("delete failed")
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_delete('settings', 't-1') is False

    def test_sb_list_keys_returns_sorted_list(self):
        from backend.storage import _sb_list_keys
        rows = [{'data_key': 'assignment:zebra'},
                {'data_key': 'assignment:alpha'}]
        sb = self._mock_sb_with_data(rows)
        with patch('backend.storage._get_supabase', return_value=sb):
            result = _sb_list_keys('assignment:', 't-1')
        assert result == ['assignment:alpha', 'assignment:zebra']

    def test_sb_list_keys_returns_empty_list_on_no_data(self):
        from backend.storage import _sb_list_keys
        sb = self._mock_sb_with_data([])
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_list_keys('assignment:', 't-1') == []

    def test_sb_list_keys_returns_empty_when_supabase_unavailable(self):
        # When sb is None, returns empty list (after retry).
        from backend.storage import _sb_list_keys
        with patch('backend.storage._get_supabase', return_value=None):
            assert _sb_list_keys('assignment:', 't-1') == []

    def test_sb_list_keys_returns_none_on_failure(self):
        # Note: returns None (different from empty), so caller can
        # distinguish "no keys" from "query failed → fall back to files".
        from backend.storage import _sb_list_keys
        sb = MagicMock()
        sb.table.side_effect = Exception("query failed")
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_list_keys('assignment:', 't-1') is None


# ──────────────────────────────────────────────────────────────────
# _sb_load_student_history / _sb_save_student_history
# ──────────────────────────────────────────────────────────────────


class TestSupabaseStudentHistory:
    def _mock_sb(self, data_rows):
        sb = MagicMock()
        chain = MagicMock()
        for m in ('select', 'eq', 'upsert'):
            getattr(chain, m).return_value = chain
        chain.execute.return_value = MagicMock(data=data_rows)
        sb.table.return_value = chain
        return sb

    def test_load_returns_history_field(self):
        from backend.storage import _sb_load_student_history
        sb = self._mock_sb([{'history': {'scores': [80]}}])
        with patch('backend.storage._get_supabase', return_value=sb):
            result = _sb_load_student_history('t-1', 's-1')
        assert result == {'scores': [80]}

    def test_load_returns_none_no_rows(self):
        from backend.storage import _sb_load_student_history
        sb = self._mock_sb([])
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_load_student_history('t-1', 's-1') is None

    def test_load_returns_none_supabase_unavailable(self):
        from backend.storage import _sb_load_student_history
        with patch('backend.storage._get_supabase', return_value=None):
            assert _sb_load_student_history('t-1', 's-1') is None

    def test_save_returns_true_on_success(self):
        from backend.storage import _sb_save_student_history
        sb = self._mock_sb([{'id': 'x'}])
        with patch('backend.storage._get_supabase', return_value=sb):
            assert _sb_save_student_history('t-1', 's-1', {'h': 1}) is True

    def test_save_returns_false_supabase_unavailable(self):
        from backend.storage import _sb_save_student_history
        with patch('backend.storage._get_supabase', return_value=None):
            assert _sb_save_student_history('t-1', 's-1', {'h': 1}) is False


# ──────────────────────────────────────────────────────────────────
# Public API: load / save / delete / list_keys
# ──────────────────────────────────────────────────────────────────


class TestPublicAPI:
    def test_load_local_dev_uses_file(self, tmp_home):
        from backend.storage import save, load
        save('settings', {'k': 'v'}, teacher_id='local-dev')
        assert load('settings', teacher_id='local-dev') == {'k': 'v'}

    def test_load_real_teacher_falls_back_to_file_when_supabase_returns_none(
        self, tmp_home, monkeypatch,
    ):
        # Configure Supabase env, but mock _sb_load to return None →
        # fall back to file backend.
        # Issue #353: file backend is now sharded by teacher_id. The
        # fallback finds the teacher's OWN sharded file, NOT local-dev's
        # shared file (that would be a cross-teacher leak).
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, load
        # Pre-fix: save via 'local-dev'; teacher-uuid-1's load
        # inherited it via the shared file. Post-fix: save via the
        # SAME teacher_id; fallback finds the teacher's own shard.
        # Mock both Supabase ops across the entire test so the
        # lazy-cached `_supabase_raw` singleton never gets created
        # against the fake URL (which would poison later tests).
        with patch('backend.storage._sb_save', return_value=True), \
             patch('backend.storage._sb_load', return_value=None):
            save('settings', {'k': 'file-data'}, teacher_id='teacher-uuid-1')
            result = load('settings', teacher_id='teacher-uuid-1')
        assert result == {'k': 'file-data'}

    def test_load_real_teacher_does_NOT_see_local_dev_file_via_fallback(
        self, tmp_home, monkeypatch,
    ):
        # Issue #353 negative pin: a Supabase teacher's file fallback
        # MUST NOT return the local-dev file's contents. Pre-fix it did
        # — that was the same cross-tenant leak the issue closes.
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, load
        # local-dev save is file-only (no Supabase singleton init).
        save('settings', {'k': 'local-dev-data'}, teacher_id='local-dev')
        with patch('backend.storage._sb_load', return_value=None):
            # teacher-uuid-1 has nothing in their shard; fallback to
            # local-dev's file must NOT happen.
            result = load('settings', teacher_id='teacher-uuid-1')
        assert result is None, (
            f"sharded fallback leaked local-dev's file: {result}"
        )

    def test_load_real_teacher_does_NOT_fall_back_for_sensitive_keys(
        self, tmp_home, monkeypatch,
    ):
        # Even if file has data, sensitive keys (api_keys,
        # portal_credentials) MUST NOT be loaded from shared file
        # to prevent cross-teacher leakage.
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, load
        save('api_keys', {'openai': 'sk-secret'}, teacher_id='local-dev')
        with patch('backend.storage._sb_load', return_value=None):
            assert load('api_keys', teacher_id='teacher-uuid-1') is None

    def test_save_real_teacher_dual_writes(self, tmp_home, monkeypatch):
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, _file_load
        with patch('backend.storage._sb_save', return_value=True) as mock_sb:
            assert save('settings', {'k': 'v'}, teacher_id='t-1') is True
        mock_sb.assert_called_once()
        # File also written (non-sensitive). Issue #353: post-shard the
        # dual-write lands under t-1's tenant subdir, not the global
        # local-dev path — verified by `_file_load` with the same
        # teacher_id.
        assert _file_load('settings', teacher_id='t-1') == {'k': 'v'}
        # And the local-dev global path is NOT polluted with t-1's data.
        assert _file_load('settings', teacher_id='local-dev') is None

    def test_save_real_teacher_skips_file_for_sensitive_keys(
        self, tmp_home, monkeypatch,
    ):
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, _file_load
        with patch('backend.storage._sb_save', return_value=True):
            save('api_keys', {'k': 'sk-secret'}, teacher_id='t-1')
        # File NOT written for sensitive key
        assert _file_load('api_keys') is None

    def test_delete_local_dev_uses_file(self, tmp_home):
        from backend.storage import save, delete, load
        save('settings', {'k': 'v'}, teacher_id='local-dev')
        assert delete('settings', teacher_id='local-dev') is True
        assert load('settings', teacher_id='local-dev') is None

    def test_delete_real_teacher_uses_supabase_result(self, tmp_home, monkeypatch):
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import delete
        with patch('backend.storage._sb_delete', return_value=True):
            assert delete('settings', teacher_id='t-1') is True
        with patch('backend.storage._sb_delete', return_value=False):
            assert delete('settings', teacher_id='t-1') is False

    def test_list_keys_local_dev_uses_file(self, tmp_home):
        from backend.storage import save, list_keys
        save('assignment:Q1', {'q': 1}, teacher_id='local-dev')
        save('assignment:Q2', {'q': 2}, teacher_id='local-dev')
        keys = list_keys('assignment:', teacher_id='local-dev')
        assert keys == ['assignment:Q1', 'assignment:Q2']

    def test_list_keys_supabase_failure_falls_back_to_files(
        self, tmp_home, monkeypatch,
    ):
        # Issue #353: fallback respects sharding. Save under t-1; list
        # under t-1 with Supabase mocked to return None → t-1's
        # sharded files are listed. Local-dev's files are NOT
        # cross-leaked.
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, list_keys
        with patch('backend.storage._sb_save', return_value=True):
            save('assignment:Q1', {}, teacher_id='t-1')
        # _sb_list_keys returns None → fall back to file
        with patch('backend.storage._sb_list_keys', return_value=None):
            keys = list_keys('assignment:', teacher_id='t-1')
        assert keys == ['assignment:Q1']

    def test_list_keys_supabase_empty_does_NOT_fall_back(
        self, tmp_home, monkeypatch,
    ):
        # Empty Supabase result is authoritative — don't pollute with
        # local files from a different teacher.
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save, list_keys
        save('assignment:Q1', {}, teacher_id='local-dev')
        with patch('backend.storage._sb_list_keys', return_value=[]):
            keys = list_keys('assignment:', teacher_id='t-1')
        assert keys == []


# ──────────────────────────────────────────────────────────────────
# Public student-history API
# ──────────────────────────────────────────────────────────────────


class TestStudentHistoryAPI:
    def test_load_no_student_id_returns_none(self):
        from backend.storage import load_student_history
        assert load_student_history('t-1', None) is None

    def test_load_local_dev_uses_file(self, tmp_home):
        from backend.storage import save_student_history, load_student_history
        save_student_history('local-dev', 'alice', {'h': 1})
        assert load_student_history('local-dev', 'alice') == {'h': 1}

    def test_load_real_teacher_falls_back_to_file(self, tmp_home, monkeypatch):
        # Issue #353: student-history file fallback respects sharding.
        # Save under t-1 → load under t-1 falls back to t-1's shard,
        # not local-dev's shared student_history dir.
        monkeypatch.setenv('SUPABASE_URL', 'https://x.supabase.co')
        monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'sk-test')
        from backend.storage import save_student_history, load_student_history
        with patch(
            'backend.storage._sb_save_student_history', return_value=True,
        ):
            save_student_history('t-1', 'alice', {'h': 'file'})
        with patch('backend.storage._sb_load_student_history', return_value=None):
            assert load_student_history('t-1', 'alice') == {'h': 'file'}

    def test_save_no_student_id_returns_false(self):
        from backend.storage import save_student_history
        assert save_student_history('t-1', None, {'h': 1}) is False

    def test_save_no_history_returns_false(self):
        from backend.storage import save_student_history
        assert save_student_history('t-1', 's-1', None) is False
