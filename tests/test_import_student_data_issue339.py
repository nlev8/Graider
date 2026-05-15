"""Regression tests for issue #339 — `import_student_data` cross-tenant IDOR.

Pre-fix, `import_student_data` wrote directly to hardcoded `~/.graider_*`
paths regardless of `teacher_id`, so two teachers in the same SaaS
deployment shared the same files. These tests pin the fix: every write
must go through `backend.storage.{save,save_student_history}` with the
caller's `teacher_id`, so the storage layer routes to a per-teacher
Supabase row in production.

Mocks the storage layer rather than asserting on filesystem paths so
the contract — `teacher_id` is threaded into every persistent write —
is enforced regardless of whether Supabase or file backend is active.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


MODULE = "backend.services.assistant_tools_student"


@pytest.fixture
def export_file(tmp_path):
    """Build an export file with every supported section populated."""
    export = {
        "student_name": "Alice Smith",
        "student_id": "sid-alice",
        "grading_results": [
            {"student_name": "Alice Smith",
             "score": 85, "graded_at": "2026-05-01T10:00:00"},
        ],
        "student_history": {
            "assignments": [
                {"date": "2026-05-01", "assignment": "Q1", "score": 85},
            ],
            "skill_scores": {"reading": 88},
        },
        "accommodations": {"presets": ["extended_time"], "notes": ""},
        "ell_data": {"language": "Spanish", "level": "intermediate"},
        "parent_contacts": {
            "parent_email": "p@example.com", "phone": "555-0100",
        },
    }
    path = tmp_path / "alice-export.json"
    path.write_text(json.dumps(export))
    return str(path)


class TestImportStudentDataTeacherScoping:
    """Every persistent write must carry the caller's `teacher_id`."""

    def test_grading_results_save_passes_teacher_id(self, export_file):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        with patch("backend.storage.load", return_value=None) as mock_load, \
             patch("backend.storage.save", return_value=True) as mock_save, \
             patch("backend.storage.save_student_history", return_value=True):
            result = import_student_data(
                file_path=export_file, teacher_id="teach-A",
            )

        assert result["status"] == "success"

        # The 'results' key must be saved with teacher_id="teach-A"
        results_calls = [
            c for c in mock_save.call_args_list
            if c.args and c.args[0] == "results"
        ]
        assert results_calls, (
            "backend.storage.save was not called with key='results'"
        )
        for call in results_calls:
            tid_kw = call.kwargs.get("teacher_id")
            tid_pos = call.args[2] if len(call.args) >= 3 else None
            assert (tid_kw or tid_pos) == "teach-A", (
                f"results save lost teacher_id (kwargs={call.kwargs}, "
                f"args={call.args})"
            )

        # And the matching load must also have been teacher-scoped
        results_loads = [
            c for c in mock_load.call_args_list
            if c.args and c.args[0] == "results"
        ]
        assert results_loads, (
            "backend.storage.load was not called with key='results'"
        )
        for call in results_loads:
            tid_kw = call.kwargs.get("teacher_id")
            tid_pos = call.args[1] if len(call.args) >= 2 else None
            assert (tid_kw or tid_pos) == "teach-A", (
                "results load lost teacher_id"
            )

    def test_accommodations_save_passes_teacher_id(self, export_file):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        with patch("backend.storage.load", return_value=None), \
             patch("backend.storage.save", return_value=True) as mock_save, \
             patch("backend.storage.save_student_history", return_value=True):
            import_student_data(
                file_path=export_file, teacher_id="teach-A",
            )

        accomm_calls = [
            c for c in mock_save.call_args_list
            if c.args and c.args[0] == "accommodations"
        ]
        assert accomm_calls, (
            "backend.storage.save was not called with key='accommodations'"
        )
        for call in accomm_calls:
            tid = call.kwargs.get("teacher_id") or (
                call.args[2] if len(call.args) >= 3 else None
            )
            assert tid == "teach-A"

    def test_ell_students_save_passes_teacher_id(self, export_file):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        with patch("backend.storage.load", return_value=None), \
             patch("backend.storage.save", return_value=True) as mock_save, \
             patch("backend.storage.save_student_history", return_value=True):
            import_student_data(
                file_path=export_file, teacher_id="teach-A",
            )

        ell_calls = [
            c for c in mock_save.call_args_list
            if c.args and c.args[0] == "ell_students"
        ]
        assert ell_calls, (
            "backend.storage.save was not called with key='ell_students'"
        )
        for call in ell_calls:
            tid = call.kwargs.get("teacher_id") or (
                call.args[2] if len(call.args) >= 3 else None
            )
            assert tid == "teach-A"

    def test_parent_contacts_save_passes_teacher_id(self, export_file):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        with patch("backend.storage.load", return_value=None), \
             patch("backend.storage.save", return_value=True) as mock_save, \
             patch("backend.storage.save_student_history", return_value=True):
            import_student_data(
                file_path=export_file, teacher_id="teach-A",
            )

        contact_calls = [
            c for c in mock_save.call_args_list
            if c.args and c.args[0] == "parent_contacts"
        ]
        assert contact_calls, (
            "backend.storage.save was not called with key='parent_contacts'"
        )
        for call in contact_calls:
            tid = call.kwargs.get("teacher_id") or (
                call.args[2] if len(call.args) >= 3 else None
            )
            assert tid == "teach-A"

    def test_student_history_save_passes_teacher_id(self, export_file):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        with patch("backend.storage.load", return_value=None), \
             patch("backend.storage.save", return_value=True), \
             patch(
                 "backend.storage.load_student_history", return_value=None,
             ) as mock_load_h, \
             patch(
                 "backend.storage.save_student_history", return_value=True,
             ) as mock_save_h:
            import_student_data(
                file_path=export_file, teacher_id="teach-A",
            )

        assert mock_save_h.called, (
            "backend.storage.save_student_history was not called"
        )
        # save_student_history(teacher_id=..., student_id=..., history=...)
        for call in mock_save_h.call_args_list:
            tid = call.kwargs.get("teacher_id") or (
                call.args[0] if call.args else None
            )
            assert tid == "teach-A"
        for call in mock_load_h.call_args_list:
            tid = call.kwargs.get("teacher_id") or (
                call.args[0] if call.args else None
            )
            assert tid == "teach-A"


class TestImportStudentDataNoCrossTenantLeak:
    """Two teachers importing different students hit isolated storage rows."""

    def test_two_teachers_write_distinct_storage_rows(self, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export_a = tmp_path / "alice.json"
        export_a.write_text(json.dumps({
            "student_name": "Alice", "student_id": "sid-A",
            "grading_results": [{"student_name": "Alice", "score": 80,
                                 "graded_at": "2026-01-01"}],
        }))
        export_b = tmp_path / "bob.json"
        export_b.write_text(json.dumps({
            "student_name": "Bob", "student_id": "sid-B",
            "grading_results": [{"student_name": "Bob", "score": 70,
                                 "graded_at": "2026-01-02"}],
        }))

        # Simulate a per-teacher backend: each teacher_id is a separate row.
        store: dict[tuple[str, str], object] = {}

        def fake_load(key, teacher_id="local-dev"):
            return store.get((teacher_id, key))

        def fake_save(key, data, teacher_id="local-dev"):
            store[(teacher_id, key)] = data
            return True

        with patch("backend.storage.load", side_effect=fake_load), \
             patch("backend.storage.save", side_effect=fake_save), \
             patch("backend.storage.save_student_history", return_value=True), \
             patch(
                 "backend.storage.load_student_history", return_value=None,
             ):
            import_student_data(
                file_path=str(export_a), teacher_id="teach-A",
            )
            import_student_data(
                file_path=str(export_b), teacher_id="teach-B",
            )

        results_a = store.get(("teach-A", "results"))
        results_b = store.get(("teach-B", "results"))

        assert results_a is not None, "teacher A has no results row"
        assert results_b is not None, "teacher B has no results row"

        names_a = [r.get("student_name") for r in results_a]
        names_b = [r.get("student_name") for r in results_b]
        assert "Alice" in names_a and "Bob" not in names_a, (
            f"teacher A leaked teacher B's data: {names_a}"
        )
        assert "Bob" in names_b and "Alice" not in names_b, (
            f"teacher B leaked teacher A's data: {names_b}"
        )
