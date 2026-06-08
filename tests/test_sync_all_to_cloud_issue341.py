"""Regression tests for issue #341 — `sync_all_to_cloud` period CSV format
mismatch + blind success counters.

Pre-fix:
  A. Period CSVs were uploaded as `{"headers": ..., "rows": ...}` dicts,
     but `_file_load('period:foo.csv')` returns the raw CSV string.
     Round-tripping through `load` after sync gave callers the wrong type.
  B. Per-key loops (`assignment:`, `lesson:`, `period_meta:`, `resource:`,
     student_history) incremented their `synced_*` counters even when
     `_sb_save` returned `False`. The summary lied about partial failures.

These tests pin both contracts post-fix.
"""
from __future__ import annotations

import csv
import json
import os
from unittest.mock import patch

import pytest


MODULE = "backend.storage"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Same shape as `tests/test_storage_gaps.py::isolated_home`."""
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


class TestPeriodCsvFormat:
    """Issue #341 (A): period CSV must be synced as raw text, matching the
    `_file_load('period:*')` return shape."""

    def test_period_csv_synced_as_raw_string(self, isolated_home):
        from backend import storage as st
        from backend.storage import sync_all_to_cloud

        periods_dir = os.path.join(
            isolated_home, ".graider_data", "periods",
        )
        os.makedirs(periods_dir)
        csv_path = os.path.join(periods_dir, "P1.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["student_name", "id"])
            writer.writeheader()
            writer.writerow({"student_name": "Alice", "id": "1"})

        with open(csv_path, "r", encoding="utf-8") as f:
            expected_raw = f.read()

        with patch.object(
            st, "_sb_save", return_value=True,
        ) as mock_sb_save:
            sync_all_to_cloud("teach-1")

        csv_calls = [
            c for c in mock_sb_save.call_args_list
            if c.args and c.args[0] == "period:P1.csv"
        ]
        assert len(csv_calls) == 1, (
            "period:P1.csv was not synced exactly once"
        )
        payload = csv_calls[0].args[1]
        assert isinstance(payload, str), (
            f"period CSV synced as {type(payload).__name__}, "
            "expected raw string to match `_file_load('period:*')` contract"
        )
        assert payload == expected_raw, (
            "period CSV upload payload does not match the on-disk file"
        )

    def test_period_csv_roundtrips_through_file_load(self, isolated_home):
        """The synced payload must equal what `_file_load` returns for the
        same key — that's the contract `load()` callers rely on."""
        from backend import storage as st
        from backend.storage import _file_load, sync_all_to_cloud

        periods_dir = os.path.join(
            isolated_home, ".graider_data", "periods",
        )
        os.makedirs(periods_dir)
        csv_path = os.path.join(periods_dir, "P1.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["student_name", "id"])
            writer.writeheader()
            writer.writerow({"student_name": "Alice", "id": "1"})

        with patch.object(
            st, "_sb_save", return_value=True,
        ) as mock_sb_save:
            sync_all_to_cloud("teach-1")

        synced_payload = next(
            c.args[1] for c in mock_sb_save.call_args_list
            if c.args and c.args[0] == "period:P1.csv"
        )
        loaded = _file_load("period:P1.csv")
        assert type(synced_payload) is type(loaded), (
            f"sync uploaded {type(synced_payload).__name__} but "
            f"_file_load returns {type(loaded).__name__}"
        )
        assert synced_payload == loaded


class TestSyncCountersGateOnSbSaveResult:
    """Issue #341 (B): per-key loops must NOT increment `synced_*` when
    `_sb_save` returns False."""

    def _seed_one_of_each(self, isolated_home):
        # assignment
        assn_dir = os.path.join(isolated_home, ".graider_assignments")
        os.makedirs(assn_dir)
        with open(os.path.join(assn_dir, "Quiz1.json"), "w") as f:
            json.dump({"title": "Quiz1"}, f)

        # lesson (nested)
        lessons_dir = os.path.join(isolated_home, ".graider_lessons")
        os.makedirs(os.path.join(lessons_dir, "Unit1"))
        with open(
            os.path.join(lessons_dir, "Unit1", "Lesson1.json"), "w",
        ) as f:
            json.dump({"title": "Lesson1"}, f)

        # period meta (period_meta uses .meta.json filenames)
        periods_dir = os.path.join(
            isolated_home, ".graider_data", "periods",
        )
        os.makedirs(periods_dir)
        with open(
            os.path.join(periods_dir, "P1.csv.meta.json"), "w",
        ) as f:
            json.dump({"period_name": "Period 1"}, f)

        # resource
        resources_dir = os.path.join(
            isolated_home, ".graider_data", "resources",
        )
        os.makedirs(resources_dir)
        with open(
            os.path.join(resources_dir, "res-1.json"), "w",
        ) as f:
            json.dump({"title": "Resource 1"}, f)

        # student history — VB2b: sync now reads the teacher's TENANT dir, so
        # seed under teach-1's tenant shard (not the global dir).
        hist_dir = os.path.join(
            isolated_home, ".graider_tenants", "teach-1",
            ".graider_data", "student_history",
        )
        os.makedirs(hist_dir)
        with open(os.path.join(hist_dir, "sid-1.json"), "w") as f:
            json.dump({"assignments": [{"score": 80}]}, f)

    def test_sb_save_false_does_not_count_as_synced(self, isolated_home):
        from backend import storage as st
        from backend.storage import sync_all_to_cloud

        self._seed_one_of_each(isolated_home)

        with patch.object(
            st, "_sb_save", return_value=False,
        ), patch.object(
            st, "_sb_save_student_history", return_value=True,
        ):
            result = sync_all_to_cloud("teach-1")

        assert result["assignments"] == "0 synced", (
            "assignment loop counted a failed _sb_save as success"
        )
        assert result["lessons"] == "0 synced", (
            "lesson loop counted a failed _sb_save as success"
        )
        assert result["periods"] == "0 synced", (
            "period_meta loop counted a failed _sb_save as success"
        )
        assert result["resources"] == "0 synced", (
            "resource loop counted a failed _sb_save as success"
        )

    def test_student_history_sb_save_false_does_not_count(
        self, isolated_home,
    ):
        from backend import storage as st
        from backend.storage import sync_all_to_cloud

        self._seed_one_of_each(isolated_home)

        with patch.object(
            st, "_sb_save", return_value=True,
        ), patch.object(
            st, "_sb_save_student_history", return_value=False,
        ):
            result = sync_all_to_cloud("teach-1")

        assert result["student_history"] == "0 synced", (
            "student_history loop counted a failed save as success"
        )

    def test_sync_does_not_slurp_other_tenants_history(self, isolated_home):
        """VB2b (Codex-found): sync_all_to_cloud must upload ONLY the calling
        teacher's tenant history — never the global dir (which on a multi-tenant
        server holds other tenants' / pre-migration records)."""
        from backend import storage as st
        from backend.storage import sync_all_to_cloud

        # Another teacher's history lives in teach-A's tenant dir...
        other_dir = os.path.join(
            isolated_home, ".graider_tenants", "teach-A",
            ".graider_data", "student_history",
        )
        os.makedirs(other_dir)
        with open(os.path.join(other_dir, "victim.json"), "w") as f:
            json.dump({"assignments": [{"score": 99}]}, f)
        # ...and stale data sits in the legacy GLOBAL dir.
        global_dir = os.path.join(isolated_home, ".graider_data", "student_history")
        os.makedirs(global_dir)
        with open(os.path.join(global_dir, "global-leak.json"), "w") as f:
            json.dump({"assignments": [{"score": 1}]}, f)

        saved = []
        with patch.object(
            st, "_sb_save_student_history",
            side_effect=lambda tid, sid, hist: saved.append((tid, sid)) or True,
        ):
            sync_all_to_cloud("teach-B")

        # teach-B has no history → nothing uploaded; neither the other tenant's
        # "victim" nor the global "global-leak" record was touched.
        synced_ids = {sid for _tid, sid in saved}
        assert "victim" not in synced_ids, "sync leaked another tenant's history"
        assert "global-leak" not in synced_ids, "sync slurped the global dir"
