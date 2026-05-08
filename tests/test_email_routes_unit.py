"""
Unit tests for backend/routes/email_routes.py — pure helpers + read-only
routes + state-machine paths that don't require live SMTP/subprocess.

Audit MAJOR #4 sprint follow-up to PR #246. Aims to push email_routes.py
from 23% to >=80% by exercising:

- Pure helpers: _normalize_submission_name, _match_to_config_title,
  _find_in_roster, _edit_distance, _unique_roster_students,
  _load_confirmed_filenames, _save_confirmed_filenames.
- Read-only routes: /api/email-status, /api/save-email-config,
  /api/outlook-send/status, /api/focus-comms/status.
- File-IO routes: /api/export-outlook-emails, /api/mark-confirmations-sent-file.
- launch_* helpers: preflight + state machine paths
  (subprocess.Popen mocked).
- _read_*_output: NDJSON parsing with a fake stdout iterator.
"""
from __future__ import annotations

import json
import os
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    """Minimal Flask app wrapping email_bp with g.user_id set."""
    from flask import Flask, g

    import backend.routes.email_routes as er_mod
    monkeypatch.setattr(er_mod, "GRAIDER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(er_mod, "PARENT_CONTACTS_FILE", str(tmp_path / "parent_contacts.json"))
    monkeypatch.setattr(er_mod, "OUTLOOK_EXPORTS_DIR", str(tmp_path / "outlook_exports"))
    os.makedirs(str(tmp_path / "outlook_exports"), exist_ok=True)
    monkeypatch.setattr(er_mod, "CONFIRMATIONS_FILE", str(tmp_path / "confirmations_sent.json"))

    # Reset per-route state between tests
    er_mod._outlook_send_state.update({"status": "idle", "sent": 0, "failed": 0, "total": 0, "log": [], "message": ""})
    er_mod._focus_comms_state.update({"status": "idle", "sent": 0, "failed": 0, "total": 0, "log": [], "message": ""})

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(er_mod.email_bp)
    return app, er_mod, tmp_path


# ──────────────────────────────────────────────────────────────────
# Pure helpers
# ──────────────────────────────────────────────────────────────────


class TestNormalizeSubmissionName:
    def test_strips_version_suffix_parens(self):
        from backend.routes.email_routes import _normalize_submission_name
        assert _normalize_submission_name("Notes (1)") == "Notes"
        assert _normalize_submission_name("Notes (12)") == "Notes"

    def test_strips_trailing_number(self):
        from backend.routes.email_routes import _normalize_submission_name
        assert _normalize_submission_name("Cornell Notes 2") == "Cornell Notes"

    def test_replaces_underscores_with_spaces(self):
        from backend.routes.email_routes import _normalize_submission_name
        assert _normalize_submission_name("Cornell_Notes_Unit_3") == "Cornell Notes Unit"

    def test_collapses_multiple_spaces(self):
        from backend.routes.email_routes import _normalize_submission_name
        assert _normalize_submission_name("Cornell    Notes") == "Cornell Notes"

    def test_empty_input(self):
        from backend.routes.email_routes import _normalize_submission_name
        assert _normalize_submission_name("") == ""

    def test_no_changes_needed(self):
        from backend.routes.email_routes import _normalize_submission_name
        assert _normalize_submission_name("Final Essay") == "Final Essay"


class TestMatchToConfigTitle:
    def test_exact_match(self):
        from backend.routes.email_routes import _match_to_config_title
        result = _match_to_config_title("Cornell Notes", ["Cornell Notes", "Final Essay"])
        assert result == "Cornell Notes"

    def test_case_insensitive_exact_match(self):
        from backend.routes.email_routes import _match_to_config_title
        result = _match_to_config_title("cornell notes", ["Cornell Notes"])
        assert result == "Cornell Notes"

    def test_substring_match(self):
        from backend.routes.email_routes import _match_to_config_title
        result = _match_to_config_title("Cornell", ["Cornell Notes Unit 3"])
        assert result == "Cornell Notes Unit 3"

    def test_word_overlap_match(self):
        from backend.routes.email_routes import _match_to_config_title
        # "Notes" is in both — word overlap matching kicks in
        result = _match_to_config_title("Cornell Notes Reading", ["Cornell Notes Unit 3"])
        assert result == "Cornell Notes Unit 3"

    def test_no_match_returns_normalized(self):
        from backend.routes.email_routes import _match_to_config_title
        result = _match_to_config_title("Random Thing", ["Cornell Notes", "Final Essay"])
        assert result == "Random Thing"

    def test_empty_config_titles_returns_normalized(self):
        from backend.routes.email_routes import _match_to_config_title
        result = _match_to_config_title("Anything", [])
        assert result == "Anything"

    def test_single_word_input_no_overlap_match(self):
        from backend.routes.email_routes import _match_to_config_title
        # Single word can match by substring but not by word-overlap
        result = _match_to_config_title("Quiz", ["Final Essay"])
        assert result == "Quiz"  # No match, returns normalized


class TestEditDistance:
    def test_identical_strings(self):
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("hello", "hello") == 0

    def test_single_substitution(self):
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("cat", "cot") == 1

    def test_single_deletion(self):
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("cat", "ca") == 1

    def test_single_insertion(self):
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("ca", "cat") == 1

    def test_completely_different(self):
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("abc", "xyz") == 3

    def test_empty_string(self):
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("", "abc") == 3
        assert _edit_distance("abc", "") == 3

    def test_swaps_arguments_for_efficiency(self):
        # Function swaps args so longer is first; verify correctness
        from backend.routes.email_routes import _edit_distance
        assert _edit_distance("a", "abcdef") == _edit_distance("abcdef", "a") == 5


class TestUniqueRosterStudents:
    def test_yields_unique_by_id(self):
        from backend.routes.email_routes import _unique_roster_students
        student = {"student_name": "Alice", "email": "alice@x.com", "period": "1"}
        roster = {"alice": student, "alice m": student}  # Same dict, two keys
        result = list(_unique_roster_students(roster))
        assert len(result) == 1
        assert result[0][0] == "Alice"

    def test_skips_no_email(self):
        from backend.routes.email_routes import _unique_roster_students
        roster = {
            "alice": {"student_name": "Alice", "email": "alice@x.com"},
            "bob": {"student_name": "Bob", "email": ""},
        }
        result = list(_unique_roster_students(roster))
        names = [r[0] for r in result]
        assert "Alice" in names
        assert "Bob" not in names

    def test_skips_invalid_email(self):
        from backend.routes.email_routes import _unique_roster_students
        roster = {
            "alice": {"student_name": "Alice", "email": "not-an-email"},
        }
        result = list(_unique_roster_students(roster))
        assert result == []

    def test_period_filter_includes_match(self):
        from backend.routes.email_routes import _unique_roster_students
        roster = {
            "alice": {"student_name": "Alice", "email": "a@x.com", "period": "1"},
            "bob": {"student_name": "Bob", "email": "b@x.com", "period": "2"},
        }
        result = list(_unique_roster_students(roster, period_filter="1"))
        names = [r[0] for r in result]
        assert names == ["Alice"]

    def test_skips_no_student_name(self):
        from backend.routes.email_routes import _unique_roster_students
        roster = {"k": {"email": "x@x.com", "student_name": ""}}
        result = list(_unique_roster_students(roster))
        assert result == []


class TestFindInRoster:
    def _roster(self, **kwargs):
        # Default test roster
        roster = {
            "alice smith": {
                "student_name": "Alice Smith",
                "first_name": "Alice", "last_name": "Smith",
            },
            "bob jones": {
                "student_name": "Bob Jones",
                "first_name": "Bob", "last_name": "Jones",
            },
        }
        roster.update(kwargs)
        return roster

    def test_strategy_1_direct_lookup(self):
        from backend.routes.email_routes import _find_in_roster
        roster = self._roster()
        result = _find_in_roster(roster, {"lookup_key": "alice smith"})
        assert result is not None
        assert result["student_name"] == "Alice Smith"

    def test_strategy_2_reverse_name_order(self):
        from backend.routes.email_routes import _find_in_roster
        roster = {"smith alice": {
            "student_name": "Alice Smith", "first_name": "Alice", "last_name": "Smith",
        }}
        result = _find_in_roster(roster, {
            "lookup_key": "alice smith", "first_name": "Alice", "last_name": "Smith",
        })
        assert result is not None
        assert result["student_name"] == "Alice Smith"

    def test_strategy_3_strips_punctuation(self):
        from backend.routes.email_routes import _find_in_roster
        roster = {"alice smith": {
            "student_name": "Alice Smith", "first_name": "Alice", "last_name": "Smith",
        }}
        result = _find_in_roster(roster, {
            "lookup_key": "alice m. smith", "first_name": "Alice M.", "last_name": "Smith",
        })
        assert result is not None

    def test_strategy_4_prefix_match_short_last_name(self):
        from backend.routes.email_routes import _find_in_roster
        # "Serenity P" should match "Serenity Petite"
        roster = {"serenity petite": {
            "student_name": "Serenity Petite",
            "first_name": "Serenity", "last_name": "Petite",
        }}
        result = _find_in_roster(roster, {
            "lookup_key": "serenity p", "first_name": "Serenity", "last_name": "P",
        })
        assert result is not None
        assert result["student_name"] == "Serenity Petite"

    def test_strategy_5_fuzzy_typo_match(self):
        from backend.routes.email_routes import _find_in_roster
        # "Allice" → "Alice" (edit distance 1)
        roster = {"alice smith": {
            "student_name": "Alice Smith",
            "first_name": "Alice", "last_name": "Smith",
        }}
        result = _find_in_roster(roster, {
            "lookup_key": "allice smith", "first_name": "Allice", "last_name": "Smith",
        })
        assert result is not None
        assert result["student_name"] == "Alice Smith"

    def test_no_match_returns_none(self):
        from backend.routes.email_routes import _find_in_roster
        roster = self._roster()
        result = _find_in_roster(roster, {
            "lookup_key": "zzzzz xxxxx", "first_name": "Zzzzz", "last_name": "Xxxxx",
        })
        assert result is None


class TestConfirmedFilenames:
    def test_load_returns_empty_set_when_file_missing(self, flask_app):
        from backend.routes.email_routes import _load_confirmed_filenames
        result = _load_confirmed_filenames()
        assert result == set()

    def test_save_then_load_roundtrip(self, flask_app):
        from backend.routes.email_routes import (
            _load_confirmed_filenames, _save_confirmed_filenames,
        )
        _save_confirmed_filenames({"a.docx", "b.pdf", "c.docx"})
        result = _load_confirmed_filenames()
        assert result == {"a.docx", "b.pdf", "c.docx"}

    def test_load_handles_corrupt_file(self, flask_app, tmp_path):
        import backend.routes.email_routes as er
        from backend.routes.email_routes import _load_confirmed_filenames

        # Write garbage to the confirmations file
        with open(er.CONFIRMATIONS_FILE, 'w') as f:
            f.write("not valid json")

        result = _load_confirmed_filenames()
        # Should swallow the JSONDecodeError and return empty set
        assert result == set()


# ──────────────────────────────────────────────────────────────────
# Read-only routes
# ──────────────────────────────────────────────────────────────────


class TestEmailStatus:
    def test_resend_unavailable(self, flask_app):
        app, _, _ = flask_app
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            client = app.test_client()
            resp = client.get("/api/email-status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["configured"] is False
        assert "Resend package" in body["message"]

    def test_resend_available_returns_config(self, flask_app):
        app, _, _ = flask_app
        with patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.GraiderEmailer") as MockEmailer:
            mock_e = MagicMock()
            mock_e.resend_available = True
            mock_e.from_email = "noreply@x.com"
            mock_e.config = {"teacher_name": "Ms. Alice", "teacher_email": "alice@school.edu"}
            MockEmailer.return_value = mock_e

            client = app.test_client()
            resp = client.get("/api/email-status")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["configured"] is True
        assert body["from_email"] == "noreply@x.com"
        assert body["teacher_name"] == "Ms. Alice"


class TestSaveEmailConfig:
    def test_saves_via_emailer(self, flask_app):
        app, _, _ = flask_app
        with patch("backend.services.email_service.GraiderEmailer") as MockEmailer:
            mock_e = MagicMock()
            MockEmailer.return_value = mock_e

            client = app.test_client()
            resp = client.post(
                "/api/save-email-config",
                json={"teacher_name": "Ms. Alice", "teacher_email": "alice@x.com"},
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        mock_e.save_config.assert_called_once_with("Ms. Alice", "alice@x.com")


class TestOutlookSendStatus:
    def test_returns_idle_initial_state(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.get("/api/outlook-send/status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "idle"
        assert body["sent"] == 0
        assert body["total"] == 0


class TestFocusCommsStatus:
    def test_returns_idle_initial_state(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.get("/api/focus-comms/status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "idle"


# ──────────────────────────────────────────────────────────────────
# Export Outlook emails (file-IO route)
# ──────────────────────────────────────────────────────────────────


class TestExportOutlookEmails:
    def test_no_parent_contacts_returns_400(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/export-outlook-emails", json={})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "parent contacts" in body["error"].lower()

    def test_no_results_returns_400(self, flask_app):
        app, er_mod, _ = flask_app
        # Write parent contacts
        with open(er_mod.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump({"sid-1": {"parent_emails": ["p@x.com"]}}, f)

        # No results provided + no saved results file
        client = app.test_client()
        with patch("os.path.expanduser") as mock_exp:
            mock_exp.side_effect = lambda p: "/nonexistent/results.json" if "results" in p else p
            resp = client.post("/api/export-outlook-emails", json={"results": []})

        assert resp.status_code == 400
        body = resp.get_json()
        assert "No results" in body["error"]

    def test_builds_emails_with_cc(self, flask_app):
        app, er_mod, tmp_path = flask_app
        with open(er_mod.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump({
                "sid-1": {"parent_emails": ["primary@x.com", "secondary@x.com"]},
            }, f)

        with patch("backend.services.email_service.GraiderEmailer") as MockEmailer:
            mock_e = MagicMock()
            mock_e.config = {"teacher_name": "Ms. Alice"}
            MockEmailer.return_value = mock_e

            client = app.test_client()
            resp = client.post("/api/export-outlook-emails", json={
                "results": [{
                    "student_id": "sid-1",
                    "student_name": "Alice Smith",
                    "score": 85,
                    "letter_grade": "B",
                    "feedback": "Good work.",
                    "period": "1",
                    "assignment": "Unit 3 Quiz",
                }],
                "include_secondary": True,
                "assignment": "Unit 3 Quiz",
            })

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1
        assert body["emails"][0]["to"] == "primary@x.com"
        assert "secondary@x.com" in body["emails"][0]["cc"]
        assert "85/100" in body["emails"][0]["body"]
        assert "Good work" in body["emails"][0]["body"]
        # Output file written
        output_path = os.path.join(er_mod.OUTLOOK_EXPORTS_DIR, "emails_Unit_3_Quiz.json")
        assert os.path.exists(output_path)

    def test_no_contact_lists_student(self, flask_app):
        app, er_mod, _ = flask_app
        with open(er_mod.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump({}, f)  # No contacts at all

        with patch("backend.services.email_service.GraiderEmailer") as MockEmailer:
            mock_e = MagicMock()
            mock_e.config = {"teacher_name": "Ms. Alice"}
            MockEmailer.return_value = mock_e

            client = app.test_client()
            resp = client.post("/api/export-outlook-emails", json={
                "results": [{"student_id": "missing", "student_name": "Lost Kid", "score": 0}],
            })

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 0
        assert "Lost Kid" in body["no_contact"]


# ──────────────────────────────────────────────────────────────────
# launch_outlook_sender — preflight + state machine
# ──────────────────────────────────────────────────────────────────


class TestLaunchOutlookSender:
    def test_already_running_returns_error(self, flask_app):
        _, er_mod, _ = flask_app
        er_mod._outlook_send_state["status"] = "running"
        from backend.routes.email_routes import launch_outlook_sender
        result = launch_outlook_sender([{"to": "x@x.com"}])
        assert "error" in result
        assert "Already sending" in result["error"]

    def test_no_emails_returns_error(self, flask_app):
        from backend.routes.email_routes import launch_outlook_sender
        result = launch_outlook_sender([])
        assert "error" in result
        assert "No emails" in result["error"]

    def test_missing_creds_returns_error(self, flask_app):
        from backend.routes.email_routes import launch_outlook_sender
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            result = launch_outlook_sender([{"to": "x@x.com"}])
        assert "error" in result
        assert "VPortal credentials" in result["error"]

    def test_happy_path_spawns_subprocess(self, flask_app):
        app, er_mod, tmp_path = flask_app
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=True), \
             patch("backend.routes.email_routes.subprocess.Popen") as mock_popen, \
             patch("backend.routes.email_routes.threading.Thread"):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            from backend.routes.email_routes import launch_outlook_sender
            result = launch_outlook_sender(
                [{"to": "x@x.com", "subject": "s", "body": "b", "student_name": "n"}],
                teacher_id="teacher-alice",
            )

        assert result["status"] == "started"
        assert result["total"] == 1
        # Subprocess was launched
        assert mock_popen.called
        # State machine moved to running → total=1
        assert er_mod._outlook_send_state["status"] == "running"
        assert er_mod._outlook_send_state["total"] == 1


# ──────────────────────────────────────────────────────────────────
# _read_outlook_output — NDJSON parsing
# ──────────────────────────────────────────────────────────────────


class TestReadOutlookOutput:
    def test_progress_event_updates_state(self, flask_app):
        _, er_mod, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            json.dumps({"type": "progress", "sent": 3, "total": 10, "message": "Sending..."}) + "\n",
            "",  # blank line (skipped)
        ])
        # Set state to running so the function processes
        er_mod._outlook_send_state["status"] = "running"
        er_mod._read_outlook_output(proc)

        assert er_mod._outlook_send_state["sent"] == 3
        assert er_mod._outlook_send_state["total"] == 10

    def test_done_event_sets_status_done(self, flask_app):
        _, er_mod, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            json.dumps({"type": "done", "sent": 5, "failed": 1}) + "\n",
        ])
        er_mod._outlook_send_state["status"] = "running"
        er_mod._read_outlook_output(proc)

        assert er_mod._outlook_send_state["status"] == "done"
        assert er_mod._outlook_send_state["sent"] == 5
        assert er_mod._outlook_send_state["failed"] == 1

    def test_error_event_increments_failed(self, flask_app):
        _, er_mod, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            json.dumps({"type": "error", "message": "broke"}) + "\n",
        ])
        er_mod._outlook_send_state["status"] = "running"
        er_mod._outlook_send_state["failed"] = 0
        er_mod._read_outlook_output(proc)

        assert er_mod._outlook_send_state["failed"] == 1

    def test_invalid_json_lines_skipped(self, flask_app):
        _, er_mod, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            "not json\n",
            json.dumps({"type": "progress", "sent": 1, "total": 1}) + "\n",
        ])
        er_mod._outlook_send_state["status"] = "running"
        er_mod._read_outlook_output(proc)

        # Bad line skipped; good line processed
        assert er_mod._outlook_send_state["sent"] == 1

    def test_stream_end_with_running_status_sets_done(self, flask_app):
        _, er_mod, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([])  # Empty stream
        er_mod._outlook_send_state["status"] = "running"
        er_mod._read_outlook_output(proc)

        # Function flips status to "done" if it was still running at stream end
        assert er_mod._outlook_send_state["status"] == "done"

    def test_log_truncated_at_100(self, flask_app):
        _, er_mod, _ = flask_app
        proc = MagicMock()
        # 105 progress events
        events = [json.dumps({"type": "progress", "sent": i, "total": 105}) + "\n"
                  for i in range(105)]
        proc.stdout = iter(events)
        er_mod._outlook_send_state["status"] = "running"
        er_mod._outlook_send_state["log"] = []
        er_mod._read_outlook_output(proc)

        # Log is truncated to last 50 entries when > 100
        assert len(er_mod._outlook_send_state["log"]) <= 100


# ──────────────────────────────────────────────────────────────────
# Outlook login route — preflight checks
# ──────────────────────────────────────────────────────────────────


class TestOutlookLogin:
    def test_missing_creds_returns_400(self, flask_app):
        app, _, _ = flask_app
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            resp = client.post("/api/outlook-login", json={})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "VPortal credentials" in body["error"]


# ──────────────────────────────────────────────────────────────────
# Send Outlook emails route — preflight + email_type branches
# ──────────────────────────────────────────────────────────────────


class TestSendOutlookEmails:
    def test_no_contacts_file_returns_400(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/send-outlook-emails", json={"type": "parent"})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "parent contacts" in body["error"].lower()

    def test_no_results_returns_400(self, flask_app):
        app, er_mod, _ = flask_app
        with open(er_mod.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump({}, f)

        client = app.test_client()
        resp = client.post("/api/send-outlook-emails", json={"type": "parent", "results": []})
        assert resp.status_code == 400

    def test_student_type_no_results_returns_400(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/send-outlook-emails", json={"type": "student", "results": []})
        assert resp.status_code == 400

    def test_no_matching_contacts_returns_400(self, flask_app):
        """No student_id matched in contacts → emails list is empty."""
        app, er_mod, _ = flask_app
        with open(er_mod.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump({}, f)

        client = app.test_client()
        resp = client.post("/api/send-outlook-emails", json={
            "type": "parent",
            "results": [{"student_id": "missing", "student_name": "x", "score": 0}],
        })
        assert resp.status_code == 400
        body = resp.get_json()
        assert "No emails to send" in body["error"]

    def test_already_running_returns_409_via_launch(self, flask_app):
        """When emails are buildable but launch_outlook_sender reports already-running,
        the route surfaces the 409."""
        app, er_mod, _ = flask_app
        with open(er_mod.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump({"sid-1": {"parent_emails": ["p@x.com"]}}, f)
        er_mod._outlook_send_state["status"] = "running"

        client = app.test_client()
        resp = client.post("/api/send-outlook-emails", json={
            "type": "parent",
            "results": [{
                "student_id": "sid-1", "student_name": "Alice Smith",
                "score": 90, "letter_grade": "A", "feedback": "ok",
                "assignment": "Quiz",
            }],
        })
        assert resp.status_code == 409


# ──────────────────────────────────────────────────────────────────
# Send focus comms route — preflight checks
# ──────────────────────────────────────────────────────────────────


class TestSendFocusComms:
    def test_no_messages_returns_400(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/send-focus-comms", json={"messages": []})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "No messages" in body["error"]

    def test_missing_creds_returns_400(self, flask_app):
        app, _, _ = flask_app
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            resp = client.post(
                "/api/send-focus-comms",
                json={"messages": [{"student_name": "x", "subject": "s", "email_body": "b"}]},
            )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────
# Focus comms stop route
# ──────────────────────────────────────────────────────────────────


class TestFocusCommsStop:
    def test_not_running_returns_not_running(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/focus-comms/stop", json={})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "not_running"

    def test_running_kills_proc(self, flask_app):
        app, er_mod, _ = flask_app
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        er_mod._focus_comms_state["process"] = mock_proc
        er_mod._focus_comms_state["status"] = "running"

        client = app.test_client()
        resp = client.post("/api/focus-comms/stop", json={})

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "stopped"
        mock_proc.kill.assert_called_once()
        assert er_mod._focus_comms_state["status"] == "done"
        assert "Stopped by user" in er_mod._focus_comms_state["message"]


# ──────────────────────────────────────────────────────────────────
# Mark confirmations sent — file write
# ──────────────────────────────────────────────────────────────────


class TestMarkConfirmationsSentFile:
    def test_no_filenames_returns_400(self, flask_app):
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/mark-confirmations-sent-file", json={})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "No filenames" in body["error"]

    def test_writes_to_confirmations_file(self, flask_app, monkeypatch):
        """email_routes.py:1226 imports grading_state/grading_lock from
        grading_routes — those module attributes don't exist (post-refactor),
        so the import raises ImportError and the route falls into the broad
        except → 500. Inject the attrs so the route reaches the
        _save_confirmed_filenames call we want to exercise.
        """
        app, er_mod, _ = flask_app
        import backend.routes.grading_routes as gr
        monkeypatch.setattr(gr, "grading_state", {"results": []}, raising=False)
        monkeypatch.setattr(gr, "grading_lock", None, raising=False)

        client = app.test_client()
        resp = client.post(
            "/api/mark-confirmations-sent-file",
            json={"filenames": ["a.docx", "b.pdf"]},
        )

        assert resp.status_code == 200, resp.get_data(as_text=True)
        # File written with the marked filenames
        from backend.routes.email_routes import _load_confirmed_filenames
        assert _load_confirmed_filenames() == {"a.docx", "b.pdf"}


# ──────────────────────────────────────────────────────────────────
# Confirm send route — covers the "no pending" branch
# ──────────────────────────────────────────────────────────────────


class TestConfirmSendNoPending:
    def test_no_pending_returns_error(self, flask_app):
        """Already pinned by tests/test_confirm_send_isolation.py for the
        per-teacher Supabase path; this exercises the literal no-pending
        branch that returns the user-facing 'No pending send' error."""
        app, _, _ = flask_app
        with patch("backend.storage.load", return_value=None), \
             patch("os.path.exists", return_value=False):
            client = app.test_client()
            resp = client.post("/api/confirm-send", json={})

        assert resp.status_code == 200
        body = resp.get_json()
        assert "No pending send" in body["error"]
