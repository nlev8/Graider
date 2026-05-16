"""Gap-fill unit tests for backend/services/assistant_tools_student.py.

Audit MAJOR #4 sprint follow-up to PR #309. Companion to existing
test_assistant_tools_student*.py files. Targets the 411 uncovered LOC
(38% baseline → 65%+ goal).

Functions covered (uncovered before this file):
* `export_student_data` (lines 818-898): full happy + variants
* `import_student_data` (lines 912-1094): validation + 5 import sections
* `_delete_student_supabase` (lines 406-451): teacher_id + Supabase paths
* `_find_all_student_files` exception path (line 360-362)

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: Codex rate-limited until
2026-05-12; Gemini also rate-limited. Merge on round-1 fold + green CI
per the dual-rate-limit precedent (PRs #269/#270/#290+).
"""
from __future__ import annotations

import base64
import csv
import json
import os
from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_student"


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME so all `~/.graider_*` writes hit tmp_path.

    Issue #339 (2026-05-14): `backend.storage` captures `HOME = str(Path.home())`
    at module-import time, so monkeypatching only the HOME env var leaves
    the storage layer pointing at the real home directory. After
    `import_student_data` moved to `backend.storage.{save,save_student_history}`,
    we also redirect the storage module's path constants here.
    """
    monkeypatch.setenv("HOME", str(tmp_path))

    import backend.storage as storage
    graider_data_dir = str(tmp_path / ".graider_data")
    # Force the file backend regardless of dev-machine Supabase env vars —
    # the tests below assert on file-backend behavior; per-tenant cloud
    # routing is covered by tests/test_import_student_data_issue339.py.
    monkeypatch.setattr(storage, "_is_supabase_configured", lambda: False)
    monkeypatch.setattr(storage, "HOME", str(tmp_path))
    monkeypatch.setattr(
        storage, "ASSIGNMENTS_DIR", str(tmp_path / ".graider_assignments"),
    )
    monkeypatch.setattr(storage, "GRAIDER_DATA_DIR", graider_data_dir)
    monkeypatch.setattr(
        storage, "PERIODS_DIR", str(tmp_path / ".graider_data" / "periods"),
    )
    monkeypatch.setattr(
        storage, "ACCOMMODATIONS_DIR",
        str(tmp_path / ".graider_data" / "accommodations"),
    )
    monkeypatch.setattr(
        storage, "LESSONS_DIR", str(tmp_path / ".graider_lessons"),
    )
    monkeypatch.setattr(
        storage, "STUDENT_HISTORY_DIR",
        str(tmp_path / ".graider_data" / "student_history"),
    )
    monkeypatch.setattr(
        storage, "RESOURCES_DIR",
        str(tmp_path / ".graider_data" / "resources"),
    )

    return tmp_path


# ──────────────────────────────────────────────────────────────────
# export_student_data
# ──────────────────────────────────────────────────────────────────


class TestExportStudentData:
    def test_empty_student_name_returns_error(self, isolated_home):
        from backend.services.assistant_tools_student import (
            export_student_data,
        )

        result = export_student_data(student_name="", teacher_id="local-dev")
        assert result == {"error": "student_name is required."}

    def test_no_match_returns_error(self, isolated_home):
        from backend.services.assistant_tools_student import (
            export_student_data,
        )

        with patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = export_student_data(
                student_name="Ghost", teacher_id="local-dev",
            )
        assert "error" in result
        assert "No student found" in result["error"]
        assert "hint" in result

    def test_match_in_roster_full_export(self, isolated_home):
        from backend.services.assistant_tools_student import (
            export_student_data,
        )

        roster = [{
            "student_name": "Alice Smith", "student_id": "sid-1",
            "period": "P1", "email": "alice@example.com",
        }]
        results = [
            {"student_name": "Alice Smith", "score": 80, "graded_at": "2026-01"},
            {"student_name": "Other", "score": 50},  # filtered out
        ]
        history = [
            {"student_name": "Alice Smith", "assignment": "Q1", "score": 80},
        ]
        accommodations = {
            "sid-1": {"presets": ["extended_time"], "notes": "n"},
        }
        settings = {
            "ell_students": {
                "sid-1": {"language": "Spanish", "level": "intermediate"}
            }
        }
        contacts = {
            "sid-1": {"parent_email": "p@example.com", "phone": "555"},
        }

        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch(f"{MODULE}._load_results", return_value=results), \
             patch(f"{MODULE}._load_master_csv", return_value=history), \
             patch(f"{MODULE}._load_accommodations",
                   return_value=accommodations), \
             patch(f"{MODULE}._load_settings", return_value=settings), \
             patch(f"{MODULE}._load_parent_contacts", return_value=contacts):
            result = export_student_data(
                student_name="Alice", teacher_id="teach-1",
            )

        assert result["status"] == "success"
        assert result["student_name"] == "Alice Smith"
        assert result["student_id"] == "sid-1"
        assert result["filename"] == "Alice_Smith_data.json"
        # record_count = 1 result + 1 history + 1 acc + 1 ell + 1 contacts
        assert result["record_count"] == 5

        # Decode the base64 to verify shape
        decoded = json.loads(base64.b64decode(result["data_base64"]).decode())
        assert decoded["student_name"] == "Alice Smith"
        assert decoded["student_id"] == "sid-1"
        assert decoded["period"] == "P1"
        assert decoded["email"] == "alice@example.com"
        assert len(decoded["grading_results"]) == 1
        assert decoded["accommodations"] == {
            "presets": ["extended_time"], "notes": "n"
        }
        assert decoded["ell_data"] == {
            "language": "Spanish", "level": "intermediate"
        }
        assert decoded["parent_contacts"] == {
            "parent_email": "p@example.com", "phone": "555"
        }
        assert decoded["student_history"] == {"assignments": history}

    def test_falls_back_to_master_csv_when_roster_misses(self, isolated_home):
        from backend.services.assistant_tools_student import (
            export_student_data,
        )

        master = [{
            "student_name": "Bob Jones", "student_id": "sid-2",
            "period": "P2",
        }]
        with patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch(f"{MODULE}._load_results", return_value=[]), \
             patch(f"{MODULE}._load_master_csv", return_value=master), \
             patch(f"{MODULE}._load_accommodations", return_value={}), \
             patch(f"{MODULE}._load_settings", return_value={}), \
             patch(f"{MODULE}._load_parent_contacts", return_value={}):
            result = export_student_data(
                student_name="Bob", teacher_id="teach-1",
            )

        assert result["status"] == "success"
        assert result["student_name"] == "Bob Jones"
        assert result["student_id"] == "sid-2"
        # No history (master_csv had only 1 row, which is now in
        # student_history NOT grading_results)
        decoded = json.loads(base64.b64decode(result["data_base64"]).decode())
        assert decoded["student_history"] == {"assignments": master}

    def test_no_history_records_yields_none(self, isolated_home):
        from backend.services.assistant_tools_student import (
            export_student_data,
        )

        roster = [{"student_name": "Alice", "student_id": "sid-1"}]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch(f"{MODULE}._load_results", return_value=[]), \
             patch(f"{MODULE}._load_master_csv", return_value=[]), \
             patch(f"{MODULE}._load_accommodations", return_value={}), \
             patch(f"{MODULE}._load_settings", return_value={}), \
             patch(f"{MODULE}._load_parent_contacts", return_value={}):
            result = export_student_data(
                student_name="Alice", teacher_id="local-dev",
            )
        decoded = json.loads(base64.b64decode(result["data_base64"]).decode())
        assert decoded["student_history"] is None
        assert result["record_count"] == 0

    def test_filename_strips_special_chars(self, isolated_home):
        from backend.services.assistant_tools_student import (
            export_student_data,
        )

        # Name with chars that the regex strips: punctuation
        roster = [{"student_name": "Mary-Jane O'Brien", "student_id": "sid-x"}]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match", return_value=True), \
             patch(f"{MODULE}._load_results", return_value=[]), \
             patch(f"{MODULE}._load_master_csv", return_value=[]), \
             patch(f"{MODULE}._load_accommodations", return_value={}), \
             patch(f"{MODULE}._load_settings", return_value={}), \
             patch(f"{MODULE}._load_parent_contacts", return_value={}):
            result = export_student_data(
                student_name="Mary", teacher_id="local-dev",
            )
        # Apostrophe stripped, hyphen kept (regex r'[^\w\s-]')
        assert result["filename"] == "Mary-Jane_OBrien_data.json"


# ──────────────────────────────────────────────────────────────────
# import_student_data
# ──────────────────────────────────────────────────────────────────


class TestImportStudentData:
    def test_empty_file_path_returns_error(self, isolated_home):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        result = import_student_data(file_path="", teacher_id="local-dev")
        assert result == {"error": "file_path is required."}

    def test_file_not_found_returns_error(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        result = import_student_data(
            file_path=str(tmp_path / "nope.json"), teacher_id="local-dev",
        )
        assert "File not found" in result["error"]

    def test_non_json_extension_returns_error(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        bad = tmp_path / "bad.txt"
        bad.write_text("not json")
        result = import_student_data(file_path=str(bad), teacher_id="local-dev")
        assert "must be a .json file" in result["error"]

    def test_invalid_json_returns_error(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        result = import_student_data(file_path=str(bad), teacher_id="local-dev")
        assert "Invalid JSON" in result["error"]

    def test_missing_student_name_returns_error(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        path = tmp_path / "nostudent.json"
        path.write_text(json.dumps({"grading_results": []}))
        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert "Missing 'student_name'" in result["error"]

    def test_no_data_sections_returns_error(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"student_name": "Alice"}))
        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert "no importable data sections" in result["error"]

    def test_imports_grading_results(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export = {
            "student_name": "Alice Smith",
            "student_id": "sid-1",
            "grading_results": [
                {"student_name": "Alice Smith",
                 "score": 80, "graded_at": "2026-01-01"},
                {"student_name": "Alice Smith",
                 "score": 90, "graded_at": "2026-02-01"},
            ],
        }
        path = tmp_path / "alice.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["status"] == "success"
        assert result["student_name"] == "Alice Smith"
        assert result["imported_sections"]["results"] == 2

        # Verify file persisted
        results_file = isolated_home / ".graider_results.json"
        assert results_file.exists()
        saved = json.loads(results_file.read_text())
        assert len(saved) == 2

    def test_dedupes_grading_results_by_graded_at(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        # Pre-seed the results file with one Alice record
        results_file = isolated_home / ".graider_results.json"
        results_file.write_text(json.dumps([
            {"student_name": "Alice Smith",
             "score": 80, "graded_at": "2026-01-01"},
        ]))

        export = {
            "student_name": "Alice Smith",
            "grading_results": [
                # Duplicate (same graded_at) → skipped
                {"student_name": "Alice Smith",
                 "score": 80, "graded_at": "2026-01-01"},
                # New
                {"student_name": "Alice Smith",
                 "score": 95, "graded_at": "2026-02-01"},
            ],
        }
        path = tmp_path / "alice.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["imported_sections"]["results"] == 1  # only the new one

        saved = json.loads(results_file.read_text())
        assert len(saved) == 2  # 1 pre-seed + 1 new

    def test_imports_student_history_fresh(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export = {
            "student_name": "Bob Jones",
            "student_id": "sid-2",
            "student_history": {
                "assignments": [
                    {"date": "2026-01-01", "assignment": "Q1", "score": 80},
                ],
                "skill_scores": {"reading": 85},
            },
        }
        path = tmp_path / "bob.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["imported_sections"]["history"] is True

        # File persisted with student_id key derived from student_id field
        history_dir = isolated_home / ".graider_data" / "student_history"
        files = list(history_dir.glob("*.json"))
        assert len(files) == 1
        loaded = json.loads(files[0].read_text())
        assert loaded["student_id"] == "sid-2"
        assert "last_updated" in loaded
        assert len(loaded["assignments"]) == 1

    def test_imports_student_history_merges_with_existing(
        self, isolated_home, tmp_path,
    ):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        # Pre-seed history with one assignment
        history_dir = isolated_home / ".graider_data" / "student_history"
        history_dir.mkdir(parents=True)
        # Issue #339: post-refactor uses `backend.storage.save_student_history`,
        # which sanitizes only `/` and `\`, so "sid-1" → "sid-1.json"
        # (was "sid_1.json" under the old re.sub-based normalization).
        existing_path = history_dir / "sid-1.json"
        existing_path.write_text(json.dumps({
            "student_id": "sid-1",
            "assignments": [
                {"date": "2026-01-01", "assignment": "Q1", "score": 70},
            ],
            "skill_scores": {"reading": 70},
        }))

        export = {
            "student_name": "Alice Smith",
            "student_id": "sid-1",
            "student_history": {
                "assignments": [
                    # Duplicate by (date, assignment) → skipped
                    {"date": "2026-01-01", "assignment": "Q1", "score": 80},
                    # New
                    {"date": "2026-02-01", "assignment": "Q2", "score": 90},
                ],
                "skill_scores": {
                    "reading": 95,  # already exists, NOT overridden
                    "writing": 88,  # new
                },
            },
        }
        path = tmp_path / "alice.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["imported_sections"]["history"] is True

        merged = json.loads(existing_path.read_text())
        # 1 existing + 1 new (the duplicate was skipped)
        assert len(merged["assignments"]) == 2
        # Existing skill score not clobbered
        assert merged["skill_scores"]["reading"] == 70
        # New skill score added
        assert merged["skill_scores"]["writing"] == 88

    def test_imports_accommodations(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export = {
            "student_name": "Carol Davis",
            "student_id": "sid-3",
            "accommodations": {
                "presets": ["extended_time", "calculator"],
                "notes": "needs quiet room",
            },
        }
        path = tmp_path / "carol.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["imported_sections"]["accommodations"] is True

        accomm_file = (
            isolated_home / ".graider_data"
            / "accommodations" / "student_accommodations.json"
        )
        loaded = json.loads(accomm_file.read_text())
        assert "sid-3" in loaded
        assert loaded["sid-3"]["presets"] == ["extended_time", "calculator"]
        assert "updated" in loaded["sid-3"]

    def test_imports_ell_data(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export = {
            "student_name": "Dan Eaton",
            "student_id": "sid-4",
            "ell_data": {"language": "Spanish", "level": "beginner"},
        }
        path = tmp_path / "dan.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["imported_sections"]["ell"] is True

        ell_file = isolated_home / ".graider_data" / "ell_students.json"
        loaded = json.loads(ell_file.read_text())
        assert loaded["sid-4"]["language"] == "Spanish"

    def test_imports_parent_contacts(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export = {
            "student_name": "Eve Adams",
            "student_id": "sid-5",
            "parent_contacts": {
                "parent_email": "p@example.com",
                "phone": "555-0100",
            },
        }
        path = tmp_path / "eve.json"
        path.write_text(json.dumps(export))

        result = import_student_data(file_path=str(path), teacher_id="local-dev")
        assert result["imported_sections"]["contacts"] is True

        contacts_file = isolated_home / ".graider_data" / "parent_contacts.json"
        loaded = json.loads(contacts_file.read_text())
        assert loaded["sid-5"]["parent_email"] == "p@example.com"

    def test_student_id_override(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )

        export = {
            "student_name": "Frank Miller",
            "student_id": "OLD_ID",
            "accommodations": {"presets": []},
        }
        path = tmp_path / "frank.json"
        path.write_text(json.dumps(export))

        result = import_student_data(
            file_path=str(path),
            student_id="NEW_ID",
            teacher_id="local-dev",
        )
        assert result["student_id"] == "NEW_ID"

        accomm_file = (
            isolated_home / ".graider_data" / "accommodations"
            / "student_accommodations.json"
        )
        loaded = json.loads(accomm_file.read_text())
        # Stored under override id, not original
        assert "NEW_ID" in loaded
        assert "OLD_ID" not in loaded

    def test_adds_to_period_roster(self, isolated_home, tmp_path):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )
        from backend.services import assistant_tools_student as mod

        # Pre-create a period CSV in the PERIODS_DIR location (which the
        # import tool reads). Patch PERIODS_DIR to a temp dir for safety.
        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        period_csv = period_dir / "P1.csv"
        with open(period_csv, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["student_name", "student_id", "email"],
            )
            writer.writeheader()
            writer.writerow({
                "student_name": "Existing Student", "student_id": "sid-existing",
                "email": "existing@example.com",
            })

        export = {
            "student_name": "New Student",
            "student_id": "sid-new",
            "email": "new@example.com",
            "accommodations": {"presets": []},  # so has_data passes
        }
        path = tmp_path / "new.json"
        path.write_text(json.dumps(export))

        with patch.object(mod, "PERIODS_DIR", str(period_dir)):
            result = import_student_data(
                file_path=str(path),
                period="P1.csv",
                teacher_id="local-dev",
            )

        assert result["status"] == "success"
        # Verify the new student was appended to the CSV
        with open(period_csv) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        names = [r["student_name"] for r in rows]
        assert "Existing Student" in names
        assert "New Student" in names

    def test_adds_to_period_skips_when_already_present(
        self, isolated_home, tmp_path,
    ):
        from backend.services.assistant_tools_student import (
            import_student_data,
        )
        from backend.services import assistant_tools_student as mod

        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        period_csv = period_dir / "P1.csv"
        with open(period_csv, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["student_name"],
            )
            writer.writeheader()
            writer.writerow({"student_name": "Already Here"})

        export = {
            "student_name": "Already Here",
            "accommodations": {"presets": []},
        }
        path = tmp_path / "dup.json"
        path.write_text(json.dumps(export))

        with patch.object(mod, "PERIODS_DIR", str(period_dir)):
            result = import_student_data(
                file_path=str(path),
                period="P1.csv",
                teacher_id="local-dev",
            )

        # Still status=success but the roster doesn't grow
        assert result["status"] == "success"
        with open(period_csv) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1


# ──────────────────────────────────────────────────────────────────
# _delete_student_supabase
# ──────────────────────────────────────────────────────────────────


class TestDeleteStudentSupabase:
    def test_no_teacher_id_returns_empty(self):
        # When `g.user_id` is missing AND DEV_USER_ID env var is not set,
        # the helper short-circuits with empty string.
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )

        # Provide a fresh Flask app context with no user_id, and clear
        # DEV_USER_ID so the helper truly has no teacher_id.
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context(), \
             patch.dict(os.environ, {}, clear=False) as _:
            os.environ.pop("DEV_USER_ID", None)
            result = _delete_student_supabase("Alice Smith")
        assert result == ""

    def test_no_supabase_client_returns_empty(self):
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context(), \
             patch("flask.g") as mock_g:
            # g.user_id present but get_supabase returns None
            mock_g.user_id = "teach-1"
            with patch("backend.supabase_client.get_supabase",
                       return_value=None):
                result = _delete_student_supabase("Alice")
        assert result == ""

    def test_no_data_returns_empty(self):
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask

        app = Flask(__name__)
        # Build a Supabase client mock returning empty
        mock_sb = MagicMock()
        execute_result = MagicMock()
        execute_result.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            execute_result
        )

        with app.test_request_context():
            from flask import g
            g.user_id = "teach-1"
            with patch("backend.supabase_client.get_supabase",
                       return_value=mock_sb):
                result = _delete_student_supabase("Alice")
        assert result == ""

    def test_dev_user_id_fallback(self, monkeypatch):
        # If g.user_id is local-dev, helper falls back to DEV_USER_ID.
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask
        app = Flask(__name__)

        monkeypatch.setenv("DEV_USER_ID", "dev-tenant-1")
        mock_sb = MagicMock()
        execute_result = MagicMock()
        execute_result.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            execute_result
        )
        with app.test_request_context():
            from flask import g
            g.user_id = "local-dev"
            with patch("backend.supabase_client.get_supabase",
                       return_value=mock_sb):
                _delete_student_supabase("Alice")
        # Confirm the eq() was called with "dev-tenant-1"
        eq_calls = mock_sb.table.return_value.select.return_value.eq.call_args_list
        assert any(
            c.args == ("teacher_id", "dev-tenant-1") for c in eq_calls
        )

    def test_match_triggers_cascade_delete(self):
        # Found matching student → deletes from behavior_events,
        # class_students, students.
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask
        app = Flask(__name__)

        mock_sb = MagicMock()
        execute_result = MagicMock()
        execute_result.data = [
            {"id": "uuid-1", "first_name": "Alice", "last_name": "Smith"},
            {"id": "uuid-2", "first_name": "Bob", "last_name": "Jones"},
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            execute_result
        )
        # Each delete().eq().execute() chain on its own
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute = MagicMock()

        with app.test_request_context():
            from flask import g
            g.user_id = "teach-1"
            with patch("backend.supabase_client.get_supabase",
                       return_value=mock_sb), \
                 patch(f"{MODULE}._fuzzy_name_match",
                       side_effect=lambda q, n: q.lower() in n.lower()):
                result = _delete_student_supabase("Alice")

        # Only Alice matched (lowercase substring "alice")
        assert "Deleted from Supabase" in result
        assert "Alice Smith" in result

        # Gemini quality-review (CRITICAL fold): verify the cascade
        # actually fires across all 3 tables. Pre-fix the test only
        # checked the message string — production could silently
        # delete from the wrong tables (or skip the cascade) and
        # this test would still pass.
        table_calls = [c.args[0] for c in mock_sb.table.call_args_list]
        assert "behavior_events" in table_calls
        assert "class_students" in table_calls
        assert "students" in table_calls
        # Verify the deletes used the matched student_id (uuid-1),
        # not the unmatched Bob (uuid-2)
        delete_eq_calls = (
            mock_sb.table.return_value.delete.return_value
            .eq.call_args_list
        )
        eq_args = [c.args for c in delete_eq_calls]
        assert ("student_id", "uuid-1") in eq_args, (
            f"Expected delete().eq('student_id', 'uuid-1') "
            f"for Alice; got: {eq_args}"
        )
        # Bob (unmatched) must NOT be deleted
        assert not any(
            args == ("student_id", "uuid-2") for args in eq_args
        ), "Unmatched student (Bob) was deleted — fuzzy match broken"

    def test_no_match_no_delete_cascade(self):
        # Symmetric pin: if NO students match, no delete chains
        # should fire (only the SELECT for the lookup).
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask
        app = Flask(__name__)

        mock_sb = MagicMock()
        execute_result = MagicMock()
        execute_result.data = [
            {"id": "uuid-1", "first_name": "Alice", "last_name": "Smith"},
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            execute_result
        )

        with app.test_request_context():
            from flask import g
            g.user_id = "teach-1"
            with patch("backend.supabase_client.get_supabase",
                       return_value=mock_sb), \
                 patch(f"{MODULE}._fuzzy_name_match", return_value=False):
                result = _delete_student_supabase("NoSuchStudent")

        assert result == ""
        # delete().eq() should NEVER have been called
        delete_chain = mock_sb.table.return_value.delete
        assert delete_chain.call_count == 0
        assert "Bob Jones" not in result

    def test_supabase_exception_swallowed(self):
        # Any exception → return empty string, no raise
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask
        app = Flask(__name__)

        with app.test_request_context():
            from flask import g
            g.user_id = "teach-1"
            with patch("backend.supabase_client.get_supabase",
                       side_effect=RuntimeError("db down")), \
                 patch(f"{MODULE}.sentry_sdk.capture_exception"):
                result = _delete_student_supabase("Alice")
        assert result == ""

    def test_empty_student_name_returns_empty(self):
        # Defensive: empty name → return empty (parts list empty short-circuit)
        from backend.services.assistant_tools_student import (
            _delete_student_supabase,
        )
        from flask import Flask
        app = Flask(__name__)
        mock_sb = MagicMock()

        with app.test_request_context():
            from flask import g
            g.user_id = "teach-1"
            with patch("backend.supabase_client.get_supabase",
                       return_value=mock_sb):
                result = _delete_student_supabase("   ")
        assert result == ""


# ──────────────────────────────────────────────────────────────────
# _find_all_student_files exception path
# ──────────────────────────────────────────────────────────────────


class TestFindAllStudentFilesException:
    def test_unreadable_csv_caught(self, tmp_path):
        # Open a file that csv.DictReader can't iterate (not a CSV).
        # The helper catches the exception and continues.
        from backend.services.assistant_tools_student import (
            _find_all_student_files,
        )

        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        # Write a CSV path but make the file unreadable / invalid.
        # The csv module is permissive — easier to force exception with
        # a binary mode trigger by patching `open`.
        bad = period_dir / "broken.csv"
        bad.write_text("col1\nrow1\n")

        with patch("builtins.open",
                   side_effect=OSError("read error")), \
             patch(f"{MODULE}.sentry_sdk.capture_exception"):
            results = _find_all_student_files(
                "Anyone", [(str(period_dir), "periods")],
            )
        assert results == []

    def test_finds_in_first_dir_then_skips_dup_filepath(self, tmp_path):
        # The seen_files dedupe guard skips identical filepath if it
        # already matched. Hard to trigger via two separate (dir, label)
        # pairs because directories differ — but the same dir listed
        # twice would dedupe.
        from backend.services.assistant_tools_student import (
            _find_all_student_files,
        )

        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        with open(period_dir / "p1.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Student"])
            writer.writeheader()
            writer.writerow({"Student": "Smith, Alice"})

        with patch(f"{MODULE}._fuzzy_name_match", return_value=True):
            results = _find_all_student_files(
                "Alice",
                [
                    (str(period_dir), "periods"),
                    (str(period_dir), "periods"),  # dup → second pass dedupes
                ],
            )
        # Only one match because seen_files skipped the second pass
        assert len(results) == 1
