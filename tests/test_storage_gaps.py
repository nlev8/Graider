"""Gap-fill tests for backend/storage.py.

Audit MAJOR #4 sprint follow-up to PR #310. Targets the 83 uncovered
LOC (77.7% baseline → 95%+ goal):

* Lines 334-336: _file_save_student_history exception swallow
* Lines 355-357: _sb_load_student_history exception swallow
* Lines 375-377: _sb_save_student_history exception swallow
* Line 502: load_student_history Supabase-hit returns immediately
* Line 521: save_student_history Supabase-on path
* Lines 535-629: sync_all_to_cloud full orchestration

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: Codex rate-limited until
2026-05-12; Gemini quota exhausted. Merge on round-1 fold + green CI
per dual-rate-limit precedent (PRs #269/#270/#290+).
"""
from __future__ import annotations

import csv
import json
import os
from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.storage"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME so all `~/.graider_*` writes hit tmp_path.

    storage.py module-level paths (HOME, ASSIGNMENTS_DIR, etc.) are set
    at import time, so we monkeypatch them on the storage module.
    """
    from backend import storage as st

    monkeypatch.setenv("HOME", str(tmp_path))
    new_home = str(tmp_path)
    monkeypatch.setattr(st, "HOME", new_home)
    monkeypatch.setattr(
        st, "ASSIGNMENTS_DIR", os.path.join(new_home, ".graider_assignments"),
    )
    monkeypatch.setattr(
        st, "GRAIDER_DATA_DIR", os.path.join(new_home, ".graider_data"),
    )
    monkeypatch.setattr(
        st, "PERIODS_DIR",
        os.path.join(new_home, ".graider_data", "periods"),
    )
    monkeypatch.setattr(
        st, "ACCOMMODATIONS_DIR",
        os.path.join(new_home, ".graider_data", "accommodations"),
    )
    monkeypatch.setattr(
        st, "LESSONS_DIR", os.path.join(new_home, ".graider_lessons"),
    )
    monkeypatch.setattr(
        st, "STUDENT_HISTORY_DIR",
        os.path.join(new_home, ".graider_data", "student_history"),
    )
    monkeypatch.setattr(
        st, "RESOURCES_DIR",
        os.path.join(new_home, ".graider_data", "resources"),
    )
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# _file_save_student_history exception path
# ──────────────────────────────────────────────────────────────────


class TestFileSaveStudentHistoryException:
    def test_io_error_returns_false(self, isolated_home):
        from backend.storage import _file_save_student_history

        with patch("builtins.open", side_effect=OSError("disk full")):
            ok = _file_save_student_history("sid-1", {"assignments": []})
        assert ok is False


# ──────────────────────────────────────────────────────────────────
# _sb_load_student_history exception path
# ──────────────────────────────────────────────────────────────────


class TestSbLoadStudentHistoryException:
    def test_with_retry_raises_returns_none(self):
        from backend.storage import _sb_load_student_history

        with patch(f"{MODULE}.with_retry",
                   side_effect=RuntimeError("retry exhausted")):
            result = _sb_load_student_history("teach-1", "sid-1")
        assert result is None

    def test_no_supabase_client_returns_none(self):
        # When _get_supabase() returns None, the inner _op returns None
        # (covered without retry exception).
        from backend.storage import _sb_load_student_history

        with patch(f"{MODULE}._get_supabase", return_value=None):
            result = _sb_load_student_history("teach-1", "sid-1")
        assert result is None

    def test_no_data_returns_none(self):
        from backend.storage import _sb_load_student_history

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = _sb_load_student_history("teach-1", "sid-1")
        assert result is None

    def test_data_present_returns_history_field(self):
        from backend.storage import _sb_load_student_history

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"history": {"assignments": [1, 2]}}])
        )
        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = _sb_load_student_history("teach-1", "sid-1")
        assert result == {"assignments": [1, 2]}


# ──────────────────────────────────────────────────────────────────
# _sb_save_student_history exception path
# ──────────────────────────────────────────────────────────────────


class TestSbSaveStudentHistoryException:
    def test_with_retry_raises_returns_false(self):
        from backend.storage import _sb_save_student_history

        with patch(f"{MODULE}.with_retry",
                   side_effect=RuntimeError("retry exhausted")):
            result = _sb_save_student_history("teach-1", "sid-1", {})
        assert result is False

    def test_no_supabase_client_returns_false(self):
        # _get_supabase returns None → inner _op returns False
        from backend.storage import _sb_save_student_history

        with patch(f"{MODULE}._get_supabase", return_value=None):
            result = _sb_save_student_history("teach-1", "sid-1", {})
        assert result is False

    def test_happy_path_returns_true(self):
        from backend.storage import _sb_save_student_history

        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute = MagicMock()
        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = _sb_save_student_history(
                "teach-1", "sid-1", {"assignments": []},
            )
        assert result is True
        # Verify upsert was called with the right shape
        upsert_args = mock_sb.table.return_value.upsert.call_args.args[0]
        assert upsert_args["teacher_id"] == "teach-1"
        assert upsert_args["student_id"] == "sid-1"
        assert "updated_at" in upsert_args


# ──────────────────────────────────────────────────────────────────
# load_student_history with Supabase
# ──────────────────────────────────────────────────────────────────


class TestLoadStudentHistorySupabase:
    def test_supabase_returns_history_short_circuits(self, isolated_home):
        from backend.storage import load_student_history

        with patch(f"{MODULE}._use_supabase", return_value=True), \
             patch(f"{MODULE}._sb_load_student_history",
                   return_value={"from": "supabase"}) as mock_sb, \
             patch(f"{MODULE}._file_load_student_history") as mock_file:
            result = load_student_history(
                teacher_id="teach-1", student_id="sid-1",
            )
        assert result == {"from": "supabase"}
        mock_sb.assert_called_once_with("teach-1", "sid-1")
        # File fallback NOT called when Supabase returned data
        mock_file.assert_not_called()

    def test_supabase_returns_none_falls_back_to_file(self, isolated_home):
        from backend.storage import load_student_history

        with patch(f"{MODULE}._use_supabase", return_value=True), \
             patch(f"{MODULE}._sb_load_student_history",
                   return_value=None), \
             patch(f"{MODULE}._file_load_student_history",
                   return_value={"from": "file"}) as mock_file:
            result = load_student_history(
                teacher_id="teach-1", student_id="sid-1",
            )
        assert result == {"from": "file"}
        mock_file.assert_called_once_with("sid-1")


# ──────────────────────────────────────────────────────────────────
# save_student_history with Supabase
# ──────────────────────────────────────────────────────────────────


class TestSaveStudentHistorySupabase:
    def test_supabase_path_dual_writes(self, isolated_home):
        from backend.storage import save_student_history

        with patch(f"{MODULE}._use_supabase", return_value=True), \
             patch(f"{MODULE}._file_save_student_history",
                   return_value=True) as mock_file, \
             patch(f"{MODULE}._sb_save_student_history",
                   return_value=True) as mock_sb:
            ok = save_student_history(
                teacher_id="teach-1", student_id="sid-1",
                history={"assignments": []},
            )
        assert ok is True
        # File write always happens
        mock_file.assert_called_once_with("sid-1", {"assignments": []})
        # Supabase write happens too
        mock_sb.assert_called_once_with("teach-1", "sid-1", {"assignments": []})


# ──────────────────────────────────────────────────────────────────
# sync_all_to_cloud orchestration
# ──────────────────────────────────────────────────────────────────


class TestSyncAllToCloud:
    def test_no_teacher_id_returns_error(self, isolated_home):
        from backend.storage import sync_all_to_cloud

        result = sync_all_to_cloud("")
        assert "error" in result
        assert "valid teacher ID" in result["error"]

    def test_local_dev_teacher_id_returns_error(self, isolated_home):
        from backend.storage import sync_all_to_cloud

        result = sync_all_to_cloud("local-dev")
        assert "error" in result

    def test_no_local_data_returns_no_local_data_for_each_key(
        self, isolated_home,
    ):
        from backend.storage import sync_all_to_cloud
        from backend import storage as st

        with patch.object(st, "_sb_save", return_value=True):
            result = sync_all_to_cloud("teach-1")

        # All single-keys report "no local data"
        for k in [
            "settings", "rubric", "results", "accommodations",
            "accommodation_presets", "ell_students", "parent_contacts",
            "assistant_memory", "teaching_calendar", "pending_send",
            "automations",
        ]:
            assert result[k] == "no local data"
        # Empty dirs → 0 synced
        assert result["assignments"] == "0 synced"
        assert result["lessons"] == "0 synced"
        assert result["periods"] == "0 synced"
        assert result["resources"] == "0 synced"
        assert result["student_history"] == "0 synced"

    def test_full_orchestration_with_seeded_data(self, isolated_home):
        from backend.storage import sync_all_to_cloud
        from backend import storage as st

        # Seed each known location with realistic data
        # ── single-key data (settings.json) ──
        settings_path = os.path.join(isolated_home, ".graider_settings.json")
        with open(settings_path, "w") as f:
            json.dump({"global_ai_notes": "be lenient"}, f)

        # rubric.json
        rubric_path = os.path.join(isolated_home, ".graider_rubric.json")
        with open(rubric_path, "w") as f:
            json.dump({"categories": []}, f)

        # ── assignments dir ──
        assn_dir = os.path.join(isolated_home, ".graider_assignments")
        os.makedirs(assn_dir)
        with open(os.path.join(assn_dir, "Quiz1.json"), "w") as f:
            json.dump({"title": "Quiz1"}, f)

        # ── lessons dir (nested unit) ──
        lessons_dir = os.path.join(isolated_home, ".graider_lessons")
        os.makedirs(os.path.join(lessons_dir, "Unit1"))
        with open(
            os.path.join(lessons_dir, "Unit1", "Lesson1.json"), "w",
        ) as f:
            json.dump({"title": "Lesson1"}, f)

        # ── periods dir: real CSV + meta ──
        periods_dir = os.path.join(
            isolated_home, ".graider_data", "periods",
        )
        os.makedirs(periods_dir)
        csv_path = os.path.join(periods_dir, "P1.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["student_name", "id"])
            writer.writeheader()
            writer.writerow({"student_name": "Alice", "id": "1"})
        meta_path = os.path.join(periods_dir, "P1.csv.meta.json")
        with open(meta_path, "w") as f:
            json.dump({"period_name": "Period 1"}, f)

        # ── resources dir ──
        resources_dir = os.path.join(
            isolated_home, ".graider_data", "resources",
        )
        os.makedirs(resources_dir)
        with open(os.path.join(resources_dir, "res-1.json"), "w") as f:
            json.dump({"title": "Resource 1"}, f)

        # ── student_history ──
        hist_dir = os.path.join(
            isolated_home, ".graider_data", "student_history",
        )
        os.makedirs(hist_dir)
        with open(os.path.join(hist_dir, "sid-1.json"), "w") as f:
            json.dump({"assignments": [{"score": 80}]}, f)

        # Mock the Supabase saves so they always succeed
        with patch.object(
            st, "_sb_save", return_value=True,
        ) as mock_sb_save, patch.object(
            st, "_sb_save_student_history", return_value=True,
        ) as mock_sb_history:
            result = sync_all_to_cloud("teach-1")

        # Each populated single-key reports "synced"
        assert result["settings"] == "synced"
        assert result["rubric"] == "synced"
        # Empty single-keys still "no local data"
        assert result["results"] == "no local data"

        # Counts
        assert result["assignments"] == "1 synced"
        assert result["lessons"] == "1 synced"
        # period_meta + period CSV both go through, but `periods` summary
        # only includes the period_meta count
        assert result["periods"] == "1 synced"
        assert result["resources"] == "1 synced"
        assert result["student_history"] == "1 synced"

        # Issue #341: period CSV is synced as the RAW CSV string so it
        # round-trips through `_file_load('period:*')`. The old dict
        # shape (`{"headers": ..., "rows": ...}`) broke any downstream
        # `load('period:foo.csv')` caller that expected a string.
        csv_calls = [
            c for c in mock_sb_save.call_args_list
            if c.args[0] == "period:P1.csv"
        ]
        assert len(csv_calls) == 1
        payload = csv_calls[0].args[1]
        assert isinstance(payload, str)
        assert "student_name,id" in payload
        assert "Alice,1" in payload

        # Student history sync called once
        mock_sb_history.assert_called_once_with(
            "teach-1", "sid-1",
            {"assignments": [{"score": 80}]},
        )

    def test_period_csv_read_failure_swallowed(self, isolated_home):
        from backend.storage import sync_all_to_cloud
        from backend import storage as st

        # Seed an unreadable CSV
        periods_dir = os.path.join(
            isolated_home, ".graider_data", "periods",
        )
        os.makedirs(periods_dir)
        # Create the meta first so _file_list_keys('period:') matches
        # via the meta file? Actually period: prefix maps to direct
        # filename. Let's seed a CSV file plus its meta.
        csv_path = os.path.join(periods_dir, "Bad.csv")
        with open(csv_path, "w") as f:
            f.write("col1\nA\n")
        meta_path = os.path.join(periods_dir, "Bad.csv.meta.json")
        with open(meta_path, "w") as f:
            json.dump({"period_name": "Period Bad"}, f)

        # Patch open() to fail when reading the CSV during sync's
        # period: branch
        real_open = open

        def selective_open(path, *args, **kwargs):
            if str(path).endswith("Bad.csv") and "r" in (args[0] if args else kwargs.get("mode", "r")):
                raise OSError("read failure")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=selective_open), \
             patch.object(st, "_sb_save", return_value=True), \
             patch(f"{MODULE}.sentry_sdk.capture_exception"):
            result = sync_all_to_cloud("teach-1")

        # Function still returns a dict (didn't raise)
        assert isinstance(result, dict)
        # Periods meta still synced (the meta JSON read works)
        assert result["periods"] == "1 synced"

    def test_student_history_read_failure_swallowed(self, isolated_home):
        from backend.storage import sync_all_to_cloud
        from backend import storage as st

        # Seed an unreadable history file
        hist_dir = os.path.join(
            isolated_home, ".graider_data", "student_history",
        )
        os.makedirs(hist_dir)
        bad_path = os.path.join(hist_dir, "sid-bad.json")
        with open(bad_path, "w") as f:
            f.write("not valid json {{")

        # Don't mock open for the json.load — just let json fail
        with patch.object(st, "_sb_save", return_value=True), \
             patch.object(st, "_sb_save_student_history",
                          return_value=True) as mock_hist, \
             patch(f"{MODULE}.sentry_sdk.capture_exception"):
            result = sync_all_to_cloud("teach-1")

        # No history actually synced (parse failed)
        assert result["student_history"] == "0 synced"
        mock_hist.assert_not_called()

    def test_resource_returns_none_skipped(self, isolated_home):
        # _file_load returns None for empty/missing data — skip the save
        from backend.storage import sync_all_to_cloud
        from backend import storage as st

        # Resources dir present but file is malformed JSON → _file_load
        # returns None, which is falsy and the sync code skips it.
        resources_dir = os.path.join(
            isolated_home, ".graider_data", "resources",
        )
        os.makedirs(resources_dir)
        bad_path = os.path.join(resources_dir, "bad.json")
        with open(bad_path, "w") as f:
            f.write("not valid json")

        with patch.object(st, "_sb_save", return_value=True) as mock_save:
            result = sync_all_to_cloud("teach-1")

        # No resource synced (parse failed → _file_load → None → skipped)
        assert result["resources"] == "0 synced"
        # Verify _sb_save was never called for resource:bad
        for c in mock_save.call_args_list:
            assert c.args[0] != "resource:bad"
