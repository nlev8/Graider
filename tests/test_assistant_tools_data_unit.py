"""
Unit tests for backend/services/assistant_tools_data.py.

Audit MAJOR #4 sprint follow-up to PR #260. Targets 65 uncovered LOC
(23% baseline) — small + safe target with storage + file-fallback
patterns proven in PR #254 (assistant_tools.py).

Note: this module duplicates several helper names from assistant_tools.py
(_load_memories, _save_memories, _load_calendar, _save_calendar,
_load_email_config). The duplication is intentional — it's a
service-layer-specific copy. The tests here cover this module's
copies, not the shared helpers.

Strategy:
- HOME redirect from `isolated_dirs` fixture for file-fallback paths.
- Patch storage_load/storage_save to None or specific values to
  exercise both branches.
- save_memory tests: dup detection, max cap, error path.
- require_teacher_id contract pin for save_memory.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest


TID = "teacher-alice"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect HOME + module path constants for file-fallback tests."""
    import backend.services.assistant_tools_data as atd

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(atd, "MEMORY_FILE",
                        str(tmp_path / ".graider_data" / "assistant_memory.json"))
    monkeypatch.setattr(atd, "CALENDAR_FILE",
                        str(tmp_path / ".graider_data" / "teaching_calendar.json"))
    return tmp_path, atd


# ──────────────────────────────────────────────────────────────────
# _load_memories (storage hit + file fallback)
# ──────────────────────────────────────────────────────────────────


class TestLoadMemories:
    def test_storage_list_passes_teacher_id(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "storage_load", return_value=["fact1", "fact2"]) as m:
            result = atd._load_memories(TID)
        assert result == ["fact1", "fact2"]
        m.assert_called_once_with("assistant_memory", TID)

    def test_storage_non_list_returns_empty(self, isolated_dirs):
        """Type guard: non-list storage value treated as empty."""
        _, atd = isolated_dirs
        with patch.object(atd, "storage_load", return_value={"not": "a list"}):
            assert atd._load_memories(TID) == []

    def test_no_storage_no_file_returns_empty(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "storage_load", return_value=None):
            assert atd._load_memories(TID) == []

    def test_file_fallback_list(self, isolated_dirs):
        tmp, atd = isolated_dirs
        os.makedirs(os.path.dirname(atd.MEMORY_FILE), exist_ok=True)
        with open(atd.MEMORY_FILE, 'w') as f:
            json.dump(["a", "b", "c"], f)
        with patch.object(atd, "storage_load", return_value=None):
            assert atd._load_memories(TID) == ["a", "b", "c"]

    def test_corrupt_file_returns_empty(self, isolated_dirs):
        tmp, atd = isolated_dirs
        os.makedirs(os.path.dirname(atd.MEMORY_FILE), exist_ok=True)
        with open(atd.MEMORY_FILE, 'w') as f:
            f.write("garbage")
        with patch.object(atd, "storage_load", return_value=None):
            assert atd._load_memories(TID) == []

    def test_storage_unavailable_falls_through_to_file(self, isolated_dirs):
        tmp, atd = isolated_dirs
        os.makedirs(os.path.dirname(atd.MEMORY_FILE), exist_ok=True)
        with open(atd.MEMORY_FILE, 'w') as f:
            json.dump(["from-file"], f)
        # storage_load is None (import failed)
        with patch.object(atd, "storage_load", None):
            assert atd._load_memories(TID) == ["from-file"]


# ──────────────────────────────────────────────────────────────────
# _save_memories
# ──────────────────────────────────────────────────────────────────


class TestSaveMemories:
    def test_uses_storage_when_available(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "storage_save") as m:
            atd._save_memories(["m1"], TID)
        m.assert_called_once_with("assistant_memory", ["m1"], TID)

    def test_file_fallback_when_no_storage(self, isolated_dirs):
        tmp, atd = isolated_dirs
        with patch.object(atd, "storage_save", None):
            atd._save_memories(["x", "y"], TID)
        with open(atd.MEMORY_FILE) as f:
            assert json.load(f) == ["x", "y"]


# ──────────────────────────────────────────────────────────────────
# save_memory (public tool)
# ──────────────────────────────────────────────────────────────────


class TestSaveMemory:
    def test_empty_fact_returns_error(self, isolated_dirs):
        _, atd = isolated_dirs
        result = atd.save_memory("", teacher_id=TID)
        assert "error" in result
        assert "No fact" in result["error"]

    def test_whitespace_only_fact_returns_error(self, isolated_dirs):
        _, atd = isolated_dirs
        result = atd.save_memory("   ", teacher_id=TID)
        assert "error" in result

    def test_first_save_returns_status_saved(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "_load_memories", return_value=[]), \
             patch.object(atd, "_save_memories") as mock_save:
            result = atd.save_memory("Period 3 is honors", teacher_id=TID)

        assert result["status"] == "saved"
        assert result["fact"] == "Period 3 is honors"
        assert result["total_memories"] == 1
        # _save_memories called with the new entry list and the teacher_id
        save_args = mock_save.call_args.args
        assert save_args[1] == TID
        new_entries = save_args[0]
        # Latest entry is the saved one
        assert any(
            (e.get("fact") if isinstance(e, dict) else e) == "Period 3 is honors"
            for e in new_entries
        )

    def test_duplicate_fact_returns_already_saved(self, isolated_dirs):
        """Case-insensitive dup check on existing entries."""
        _, atd = isolated_dirs
        existing = [{"fact": "Period 3 is honors", "saved_at": "2026-01-01"}]
        with patch.object(atd, "_load_memories", return_value=existing), \
             patch.object(atd, "_save_memories") as mock_save:
            result = atd.save_memory("period 3 is honors", teacher_id=TID)

        assert result["status"] == "already_saved"
        assert "already saved" in result["message"]
        # _save_memories NOT called (no write since already present)
        mock_save.assert_not_called()

    def test_dup_check_works_against_legacy_string_entries(self, isolated_dirs):
        """Older memory format stored bare strings, not dicts. Dup check
        must handle both."""
        _, atd = isolated_dirs
        existing = ["Period 3 is honors"]  # legacy string format
        with patch.object(atd, "_load_memories", return_value=existing), \
             patch.object(atd, "_save_memories") as mock_save:
            result = atd.save_memory("period 3 is honors", teacher_id=TID)

        assert result["status"] == "already_saved"
        mock_save.assert_not_called()

    def test_caps_at_max_memories(self, isolated_dirs):
        """When existing memories + new entry > MAX_MEMORIES, oldest are dropped."""
        _, atd = isolated_dirs
        # Fill to MAX_MEMORIES (50)
        existing = [{"fact": f"old fact {i}"} for i in range(atd.MAX_MEMORIES)]
        with patch.object(atd, "_load_memories", return_value=existing), \
             patch.object(atd, "_save_memories") as mock_save:
            result = atd.save_memory("new fact", teacher_id=TID)

        assert result["status"] == "saved"
        # total_memories caps at MAX_MEMORIES
        assert result["total_memories"] == atd.MAX_MEMORIES
        saved_list = mock_save.call_args.args[0]
        # Exactly MAX_MEMORIES entries
        assert len(saved_list) == atd.MAX_MEMORIES
        # New fact is the LAST entry (oldest dropped from front)
        last = saved_list[-1]
        assert (last.get("fact") if isinstance(last, dict) else last) == "new fact"
        # Oldest entry ("old fact 0") was dropped
        all_facts = [
            (e.get("fact") if isinstance(e, dict) else e)
            for e in saved_list
        ]
        assert "old fact 0" not in all_facts

    def test_strips_whitespace_from_fact(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "_load_memories", return_value=[]), \
             patch.object(atd, "_save_memories") as mock_save:
            result = atd.save_memory("  Period 3 is honors  ", teacher_id=TID)

        assert result["fact"] == "Period 3 is honors"
        # The saved entry's fact field is trimmed too
        saved_list = mock_save.call_args.args[0]
        last = saved_list[-1]
        assert last.get("fact") == "Period 3 is honors"

    def test_saved_entry_has_timestamp(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "_load_memories", return_value=[]), \
             patch.object(atd, "_save_memories") as mock_save:
            atd.save_memory("test", teacher_id=TID)

        saved_list = mock_save.call_args.args[0]
        last = saved_list[-1]
        assert "saved_at" in last
        # ISO format string
        assert isinstance(last["saved_at"], str)
        assert "T" in last["saved_at"]


# ──────────────────────────────────────────────────────────────────
# _load_calendar / _save_calendar
# ──────────────────────────────────────────────────────────────────


class TestLoadCalendar:
    def test_storage_hit_passes_teacher_id(self, isolated_dirs):
        _, atd = isolated_dirs
        cal = {"scheduled_lessons": [{"id": 1}], "holidays": [], "school_days": {}}
        with patch.object(atd, "storage_load", return_value=cal) as m:
            assert atd._load_calendar(TID) == cal
        m.assert_called_once_with("teaching_calendar", TID)

    def test_default_when_no_storage_no_file(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "storage_load", return_value=None):
            result = atd._load_calendar(TID)
        assert result == {"scheduled_lessons": [], "holidays": [], "school_days": {}}

    def test_file_fallback(self, isolated_dirs):
        tmp, atd = isolated_dirs
        os.makedirs(os.path.dirname(atd.CALENDAR_FILE), exist_ok=True)
        with open(atd.CALENDAR_FILE, 'w') as f:
            json.dump({"scheduled_lessons": [{"id": 99}]}, f)
        with patch.object(atd, "storage_load", return_value=None):
            result = atd._load_calendar(TID)
        assert result == {"scheduled_lessons": [{"id": 99}]}

    def test_corrupt_file_returns_default(self, isolated_dirs):
        tmp, atd = isolated_dirs
        os.makedirs(os.path.dirname(atd.CALENDAR_FILE), exist_ok=True)
        with open(atd.CALENDAR_FILE, 'w') as f:
            f.write("garbage")
        with patch.object(atd, "storage_load", return_value=None):
            result = atd._load_calendar(TID)
        # Falls back to default
        assert result == {"scheduled_lessons": [], "holidays": [], "school_days": {}}


class TestSaveCalendar:
    def test_uses_storage_when_available(self, isolated_dirs):
        _, atd = isolated_dirs
        with patch.object(atd, "storage_save") as m:
            atd._save_calendar({"x": 1}, TID)
        m.assert_called_once_with("teaching_calendar", {"x": 1}, TID)

    def test_file_fallback_when_no_storage(self, isolated_dirs):
        tmp, atd = isolated_dirs
        with patch.object(atd, "storage_save", None):
            atd._save_calendar({"k": "v"}, TID)
        with open(atd.CALENDAR_FILE) as f:
            assert json.load(f) == {"k": "v"}


# ──────────────────────────────────────────────────────────────────
# _load_email_config
# ──────────────────────────────────────────────────────────────────


class TestLoadEmailConfig:
    def test_returns_empty_when_missing(self, isolated_dirs):
        _, atd = isolated_dirs
        # tmp_path home → ~/.graider_email_config.json doesn't exist
        assert atd._load_email_config() == {}

    def test_reads_from_home_path(self, isolated_dirs):
        tmp, atd = isolated_dirs
        config_path = tmp / ".graider_email_config.json"
        with open(config_path, 'w') as f:
            json.dump({"teacher_name": "Ms. Alice", "teacher_email": "a@x.com"}, f)
        result = atd._load_email_config()
        assert result == {"teacher_name": "Ms. Alice", "teacher_email": "a@x.com"}

    def test_corrupt_file_returns_empty(self, isolated_dirs):
        tmp, atd = isolated_dirs
        config_path = tmp / ".graider_email_config.json"
        with open(config_path, 'w') as f:
            f.write("not json")
        # Falls back to empty silently
        assert atd._load_email_config() == {}


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract pin
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    def test_save_memory_empty_raises(self):
        from backend.services.assistant_tools_data import save_memory
        with pytest.raises(ValueError, match="teacher_id is required"):
            save_memory("a fact", teacher_id="")
