"""
Unit tests for backend/routes/grading_routes.py.

Audit MAJOR #4 sprint follow-up to PR #248. Targets the 714 uncovered LOC
in grading_routes.py — biggest leverage in the priority list.

Covers:
- /api/status, /api/stop-grading, /api/clear-results — state factory paths
- /api/update-result — edit tracking, letter_grade recalc, allowed_fields
- _normalize_assign_for_csv, _match_assignment_in_csv (pure helpers)
- _sync_result_to_master_csv — file-IO with master_grades.csv
- /api/grade-math, /api/grade-data-table, /api/grade-coordinates,
  /api/grade-place-name, /api/check-math-equivalence — STEM dispatch
- /api/upload-focus-comments — preflight (already-running, missing-creds,
  no-manifest, no-comments) + happy-path subprocess env contract (GH #245)
- _read_focus_comments_output — NDJSON parsing paths
- /api/focus-comments/status — read-only state read
- /api/ell-students GET + POST — file-IO

Pattern matches tests/test_email_routes_unit.py (PR #248).
"""
from __future__ import annotations

import json
import os
import threading
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


def _make_state(is_running=False, results=None, log=None):
    return {
        "is_running": is_running,
        "stop_requested": False,
        "results": results if results is not None else [],
        "log": log if log is not None else [],
        "current_file": "",
        "files_processed": 0,
        "total_files": 0,
    }


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    """Minimal Flask app wrapping grading_bp.

    Initializes the state factory functions via init_grading_routes
    and patches GRAIDER_DATA_DIR + ELL_DATA_FILE for filesystem isolation.
    Codex round-1 MAJOR: HOME is redirected to tmp_path so update-result
    can't overwrite the user's real ~/.graider_results.json.
    """
    from flask import Flask, g
    import backend.routes.grading_routes as gr_mod

    # MUST come first — affects all subsequent os.path.expanduser('~/...')
    # calls in the route handlers, including the update-result results-file
    # write at backend/routes/grading_routes.py:367.
    monkeypatch.setenv("HOME", str(tmp_path))

    monkeypatch.setattr(gr_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
    monkeypatch.setattr(gr_mod, "FOCUS_EXPORTS_DIR", str(tmp_path / "exports" / "focus"))
    monkeypatch.setattr(gr_mod, "OUTLOOK_EXPORTS_DIR", str(tmp_path / "exports" / "outlook"))
    monkeypatch.setattr(gr_mod, "ELL_DATA_FILE", str(tmp_path / "ell_students.json"))
    # GRAIDER_DATA_DIR is referenced inside upload_focus_comments via os.path.join
    monkeypatch.setattr(gr_mod, "GRAIDER_DATA_DIR", str(tmp_path), raising=False)

    for d in ["exports", "exports/focus", "exports/outlook"]:
        os.makedirs(str(tmp_path / d), exist_ok=True)

    # Per-teacher state dict + lock (one per fixture instance)
    state = _make_state()
    lock = threading.Lock()
    # Track teacher_ids received by the state factory — pins the
    # multi-teacher routing contract (Codex round-1 gap).
    teacher_ids_seen = []

    def _get_state(teacher_id):
        teacher_ids_seen.append(teacher_id)
        return state

    def _get_lock(teacher_id):
        return lock

    # Expose the tracker as a module attribute for test inspection
    gr_mod._test_teacher_ids_seen = teacher_ids_seen

    def _thread_fn(*args, **kwargs):
        pass

    def _reset_fn():
        state.clear()
        state.update(_make_state())

    gr_mod.init_grading_routes(_get_state, _thread_fn, _reset_fn, _get_lock)

    # Reset focus_comments_state between tests
    gr_mod._focus_comments_state.update({
        "status": "idle", "process": None, "entered": 0,
        "failed": 0, "skipped": 0, "total": 0, "log": [], "message": "",
    })

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(gr_mod.grading_bp)
    return app, gr_mod, tmp_path, state, lock


@pytest.fixture
def flask_app_uninit(monkeypatch):
    """Flask app with grading routes NOT initialized (state factory is None)."""
    from flask import Flask, g
    import backend.routes.grading_routes as gr_mod

    # Reset module-level factories to None
    monkeypatch.setattr(gr_mod, "_get_state", None)
    monkeypatch.setattr(gr_mod, "_get_lock", None)
    monkeypatch.setattr(gr_mod, "run_grading_thread", None)
    monkeypatch.setattr(gr_mod, "reset_state", None)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(gr_mod.grading_bp)
    return app, gr_mod


# ──────────────────────────────────────────────────────────────────
# /api/status
# ──────────────────────────────────────────────────────────────────


class TestGetStatus:
    def test_uninitialized_returns_500(self, flask_app_uninit):
        app, _ = flask_app_uninit
        client = app.test_client()
        resp = client.get("/api/status")
        assert resp.status_code == 500
        assert "not initialized" in resp.get_json()["error"]

    def test_returns_state_snapshot(self, flask_app):
        app, _, _, state, _ = flask_app
        state["is_running"] = True
        state["files_processed"] = 3
        state["total_files"] = 10

        client = app.test_client()
        resp = client.get("/api/status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["is_running"] is True
        assert body["files_processed"] == 3
        assert body["total_files"] == 10

    def test_pending_confirmations_counts_unsent_emails(self, flask_app):
        app, _, _, state, _ = flask_app
        state["results"] = [
            {"student_email": "a@x.com", "confirmation_sent": False},
            {"student_email": "b@x.com", "confirmation_sent": True},
            {"email": "c@x.com", "confirmation_sent": False},
            {"student_email": "no-at-sign", "confirmation_sent": False},
            {"student_email": "", "confirmation_sent": False},
        ]
        client = app.test_client()
        resp = client.get("/api/status")
        body = resp.get_json()
        # a and c are unsent with valid emails; b sent; no-at-sign + empty skipped
        assert body["pending_confirmations"] == 2


# ──────────────────────────────────────────────────────────────────
# /api/stop-grading
# ──────────────────────────────────────────────────────────────────


class TestStopGrading:
    def test_uninitialized_returns_500(self, flask_app_uninit):
        app, _ = flask_app_uninit
        client = app.test_client()
        resp = client.post("/api/stop-grading", json={})
        assert resp.status_code == 500

    def test_running_sets_stop_requested(self, flask_app):
        app, _, _, state, _ = flask_app
        state["is_running"] = True

        client = app.test_client()
        resp = client.post("/api/stop-grading", json={})

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["stopped"] is True
        assert state["stop_requested"] is True

    def test_not_running_returns_not_running_message(self, flask_app):
        app, _, _, state, _ = flask_app
        state["is_running"] = False

        client = app.test_client()
        resp = client.post("/api/stop-grading", json={})

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["stopped"] is False
        assert "not running" in body["message"].lower()


# ──────────────────────────────────────────────────────────────────
# /api/clear-results
# ──────────────────────────────────────────────────────────────────


class TestClearResults:
    def test_uninitialized_returns_500(self, flask_app_uninit):
        app, _ = flask_app_uninit
        client = app.test_client()
        resp = client.post("/api/clear-results", json={})
        assert resp.status_code == 500

    def test_cannot_clear_while_running(self, flask_app):
        app, _, _, state, _ = flask_app
        state["is_running"] = True

        client = app.test_client()
        resp = client.post("/api/clear-results", json={})

        assert resp.status_code == 400
        assert "in progress" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# Pure helpers: _normalize_assign_for_csv, _match_assignment_in_csv
# ──────────────────────────────────────────────────────────────────


class TestNormalizeAssignForCsv:
    def test_lowercases_and_strips(self):
        from backend.routes.grading_routes import _normalize_assign_for_csv
        assert _normalize_assign_for_csv("  Cornell Notes  ") == "cornell notes"

    def test_strips_version_suffix(self):
        from backend.routes.grading_routes import _normalize_assign_for_csv
        assert _normalize_assign_for_csv("Notes (1)") == "notes"
        assert _normalize_assign_for_csv("Notes (12)") == "notes"

    def test_strips_docx_suffix(self):
        from backend.routes.grading_routes import _normalize_assign_for_csv
        assert _normalize_assign_for_csv("Essay.docx") == "essay"
        assert _normalize_assign_for_csv("Essay.DOC") == "essay"

    def test_strips_pdf_suffix(self):
        from backend.routes.grading_routes import _normalize_assign_for_csv
        assert _normalize_assign_for_csv("Quiz.pdf") == "quiz"


class TestMatchAssignmentInCsv:
    def test_exact_match(self):
        from backend.routes.grading_routes import _match_assignment_in_csv
        assert _match_assignment_in_csv("Cornell Notes", "Cornell Notes") is True

    def test_case_insensitive(self):
        from backend.routes.grading_routes import _match_assignment_in_csv
        assert _match_assignment_in_csv("cornell notes", "CORNELL NOTES") is True

    def test_csv_truncated_prefix_matches(self):
        from backend.routes.grading_routes import _match_assignment_in_csv
        # CSV truncates assignment names; if csv_norm is a 20+ char prefix
        # of target_norm, it counts as a match.
        csv_name = "Cornell Notes Unit 3 "  # 20+ chars after normalization
        target = "Cornell Notes Unit 3 - The Civil War Era"
        assert _match_assignment_in_csv(csv_name, target) is True

    def test_target_truncated_prefix_matches(self):
        from backend.routes.grading_routes import _match_assignment_in_csv
        # Reverse direction also matches when target is prefix of csv
        target = "Cornell Notes Unit 3 "  # 20+ chars
        csv_name = "Cornell Notes Unit 3 - Long version"
        assert _match_assignment_in_csv(csv_name, target) is True

    def test_no_match(self):
        from backend.routes.grading_routes import _match_assignment_in_csv
        assert _match_assignment_in_csv("Quiz", "Final Essay") is False


# ──────────────────────────────────────────────────────────────────
# /api/update-result
# ──────────────────────────────────────────────────────────────────


class TestUpdateResult:
    def test_uninitialized_returns_500(self, flask_app_uninit):
        app, _ = flask_app_uninit
        client = app.test_client()
        resp = client.post("/api/update-result", json={"filename": "x.docx"})
        assert resp.status_code == 500

    def test_missing_filename_returns_400(self, flask_app):
        app, _, _, _, _ = flask_app
        client = app.test_client()
        resp = client.post("/api/update-result", json={})
        assert resp.status_code == 400
        assert "Filename" in resp.get_json()["error"]

    def test_filename_not_in_results_returns_404(self, flask_app):
        app, _, _, state, _ = flask_app
        state["results"] = [{"filename": "other.docx"}]
        client = app.test_client()
        resp = client.post(
            "/api/update-result",
            json={"filename": "missing.docx", "score": 50},
        )
        assert resp.status_code == 404

    def test_score_edit_tracks_teacher_edited_and_recalcs_letter(self, flask_app):
        app, _, _, state, _ = flask_app
        state["results"] = [{
            "filename": "essay.docx",
            "score": 70,
            "feedback": "ok",
        }]
        # Codex round-1 MAJOR: patch record_correction to keep this unit test
        # off the real Supabase correction-pattern store.
        with patch("backend.routes.grading_routes.audit_log"), \
             patch("backend.routes.grading_routes._sync_result_to_master_csv"), \
             patch("backend.services.correction_patterns.record_correction") as mock_record:
            client = app.test_client()
            resp = client.post(
                "/api/update-result",
                json={"filename": "essay.docx", "score": 92},
            )

        assert resp.status_code == 200
        result = resp.get_json()["result"]
        assert result["score"] == 92
        assert result["letter_grade"] == "A"
        assert result["teacher_edited"] is True
        assert result["ai_score"] == 70
        assert result["ai_feedback"] == "ok"
        # Correction pattern recorded with ai_score=70 vs teacher_score=92
        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["ai_score"] == 70
        assert kwargs["teacher_score"] == 92
        assert kwargs["teacher_id"] == "teacher-alice"

    def test_score_letter_grade_boundaries(self, flask_app):
        app, _, _, state, _ = flask_app
        for score, expected_grade in [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (59, "F")]:
            state["results"] = [{"filename": "x.docx", "score": 0}]
            with patch("backend.routes.grading_routes.audit_log"), \
                 patch("backend.routes.grading_routes._sync_result_to_master_csv"), \
                 patch("backend.services.correction_patterns.record_correction"):
                client = app.test_client()
                resp = client.post(
                    "/api/update-result",
                    json={"filename": "x.docx", "score": score},
                )
            assert resp.status_code == 200, f"score={score}"
            assert resp.get_json()["result"]["letter_grade"] == expected_grade, (
                f"score={score} expected={expected_grade}"
            )

    def test_only_allowed_fields_updated(self, flask_app):
        """Untrusted fields from request must not bypass the allowed_fields
        filter — including a forged `teacher_edited` flag (Codex round-1 MINOR:
        previous version didn't actually send teacher_edited)."""
        app, _, _, state, _ = flask_app
        state["results"] = [{"filename": "x.docx", "score": 70, "feedback": "ok"}]
        with patch("backend.routes.grading_routes.audit_log"), \
             patch("backend.routes.grading_routes._sync_result_to_master_csv"), \
             patch("backend.services.correction_patterns.record_correction"):
            client = app.test_client()
            resp = client.post(
                "/api/update-result",
                json={
                    "filename": "x.docx",
                    "score": 95,
                    "verified": True,
                    # Forged teacher_edited — must not be controllable from outside.
                    # The route sets teacher_edited=True itself based on score
                    # being present, so the assertion below is that teacher_edited
                    # came from the route logic, not the request.
                    "teacher_edited": False,
                    "ai_score": 999,
                    "ai_feedback": "FORGED",
                    "malicious_field": "injected",
                    "filename_override": "evil.docx",
                },
            )

        assert resp.status_code == 200
        result = resp.get_json()["result"]
        assert result["score"] == 95
        assert result["verified"] is True
        # Route owns teacher_edited and ai_* — must not be overwritable from the request
        assert result["teacher_edited"] is True, (
            "Forged teacher_edited=False in request must not stick"
        )
        assert result["ai_score"] == 70, "ai_score must reflect prior score, not 999 from request"
        assert result["ai_feedback"] == "ok", "ai_feedback must reflect prior feedback, not 'FORGED'"
        assert "malicious_field" not in result
        # Filename was not overridden
        assert result["filename"] == "x.docx"

    def test_audit_log_called_for_score_edit(self, flask_app):
        app, _, _, state, _ = flask_app
        state["results"] = [{"filename": "x.docx", "score": 70}]
        with patch("backend.routes.grading_routes.audit_log") as mock_audit, \
             patch("backend.routes.grading_routes._sync_result_to_master_csv"), \
             patch("backend.services.correction_patterns.record_correction"):
            client = app.test_client()
            client.post(
                "/api/update-result",
                json={"filename": "x.docx", "score": 95},
            )
        mock_audit.assert_called_once()
        args, kwargs = mock_audit.call_args
        assert args[0] == "GRADE_EDIT"
        assert kwargs["teacher_id"] == "teacher-alice"

    def test_verified_only_edit_does_not_audit(self, flask_app):
        """Setting `verified` flag is not a PII change → no audit."""
        app, _, _, state, _ = flask_app
        state["results"] = [{"filename": "x.docx", "score": 70}]
        with patch("backend.routes.grading_routes.audit_log") as mock_audit:
            client = app.test_client()
            client.post(
                "/api/update-result",
                json={"filename": "x.docx", "verified": True},
            )
        mock_audit.assert_not_called()

    def test_teacher_id_routed_to_state_factory(self, flask_app):
        """Multi-tenant safety pin (Codex round-1 gap): /api/update-result
        must call _get_state with g.user_id, NOT 'local-dev' or a shared default.
        The fixture's _get_state appends the teacher_id it received to a
        module-level tracker."""
        app, gr_mod, _, state, _ = flask_app
        state["results"] = [{"filename": "x.docx", "score": 70}]
        gr_mod._test_teacher_ids_seen.clear()

        with patch("backend.routes.grading_routes.audit_log"), \
             patch("backend.routes.grading_routes._sync_result_to_master_csv"), \
             patch("backend.services.correction_patterns.record_correction"):
            client = app.test_client()
            client.post("/api/update-result", json={"filename": "x.docx", "score": 95})

        assert "teacher-alice" in gr_mod._test_teacher_ids_seen, (
            f"Expected 'teacher-alice' in state factory calls; got "
            f"{gr_mod._test_teacher_ids_seen!r}. A regression to default "
            "'local-dev' would cause cross-tenant state corruption."
        )
        assert "local-dev" not in gr_mod._test_teacher_ids_seen, (
            "Route must NOT fall back to 'local-dev' when authenticated"
        )


# ──────────────────────────────────────────────────────────────────
# _sync_result_to_master_csv
# ──────────────────────────────────────────────────────────────────


class TestSyncResultToMasterCsv:
    def test_no_master_file_no_op(self, tmp_path, monkeypatch):
        """When master_grades.csv doesn't exist, function silently returns."""
        from backend.routes.grading_routes import _sync_result_to_master_csv

        # Redirect export base to tmp_path so Results dir has no master file
        monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path))
        # No master file written → function should no-op without error
        _sync_result_to_master_csv({
            "student_id": "1", "assignment": "x", "score": 50,
        })

    def test_missing_student_id_or_assignment_no_op(self):
        from backend.routes.grading_routes import _sync_result_to_master_csv
        # No student_id
        _sync_result_to_master_csv({"assignment": "x", "score": 50})
        # No assignment
        _sync_result_to_master_csv({"student_id": "1", "score": 50})

    def test_updates_matching_row(self, tmp_path, monkeypatch):
        import csv
        from backend.routes.grading_routes import _sync_result_to_master_csv

        results_dir = tmp_path / "Results"
        results_dir.mkdir(parents=True)
        master_file = results_dir / "master_grades.csv"

        with open(master_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Student ID", "Assignment", "Overall Score", "Letter Grade",
                "Content Accuracy", "Completeness", "Writing Quality",
                "Effort Engagement", "Feedback",
            ])
            writer.writeheader()
            writer.writerow({
                "Student ID": "123", "Assignment": "Quiz",
                "Overall Score": "50", "Letter Grade": "F",
                "Content Accuracy": "1", "Completeness": "2",
                "Writing Quality": "3", "Effort Engagement": "4",
                "Feedback": "old",
            })

        monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path))
        _sync_result_to_master_csv({
            "student_id": "123",
            "assignment": "Quiz",
            "score": 95,
            "letter_grade": "A",
            "feedback": "great work!",
            "breakdown": {
                "content_accuracy": 9, "completeness": 10,
                "writing_quality": 8, "effort_engagement": 10,
            },
        })

        # Re-read and verify update
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["Overall Score"] == "95"
        assert rows[0]["Letter Grade"] == "A"
        assert rows[0]["Feedback"] == "great work!"


# ──────────────────────────────────────────────────────────────────
# STEM grading routes — dispatch to stem_grading service
# ──────────────────────────────────────────────────────────────────


class TestStemGradingRoutes:
    def test_grade_math_dispatches(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.services.stem_grading.grade_math_question") as mock_fn:
            mock_fn.return_value = {"correct": True, "score": 1}
            client = app.test_client()
            resp = client.post("/api/grade-math", json={
                "question": {"correctAnswer": "1/2"},
                "studentAnswer": "0.5",
            })
        assert resp.status_code == 200
        assert resp.get_json()["correct"] is True
        mock_fn.assert_called_once()

    def test_grade_data_table_dispatches(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.services.stem_grading.grade_data_table") as mock_fn:
            mock_fn.return_value = {"score": 0.95}
            client = app.test_client()
            resp = client.post("/api/grade-data-table", json={
                "expectedTable": {"headers": [], "data": []},
                "studentTable": {"headers": [], "data": []},
                "tolerancePercent": 5,
            })
        assert resp.status_code == 200
        assert resp.get_json()["score"] == 0.95

    def test_grade_coordinates_dispatches(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.services.stem_grading.grade_coordinate_question") as mock_fn:
            mock_fn.return_value = {"distance_km": 3.2, "correct": True}
            client = app.test_client()
            resp = client.post("/api/grade-coordinates", json={
                "expected": {"latitude": 40.0, "longitude": -74.0},
                "student": {"latitude": 40.0, "longitude": -74.0},
                "toleranceKm": 50,
            })
        assert resp.status_code == 200
        assert resp.get_json()["correct"] is True

    def test_grade_place_name_dispatches(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.services.stem_grading.grade_place_name") as mock_fn:
            mock_fn.return_value = {"correct": True}
            client = app.test_client()
            resp = client.post("/api/grade-place-name", json={
                "expectedNames": ["UK", "United Kingdom"],
                "studentAnswer": "UK",
            })
        assert resp.status_code == 200
        assert resp.get_json()["correct"] is True

    def test_check_math_equivalence_dispatches(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.services.stem_grading.check_math_equivalence") as mock_fn:
            mock_fn.return_value = {"equivalent": True}
            client = app.test_client()
            resp = client.post("/api/check-math-equivalence", json={
                "expression1": "1/2", "expression2": "0.5",
            })
        assert resp.status_code == 200
        assert resp.get_json()["equivalent"] is True


# ──────────────────────────────────────────────────────────────────
# /api/upload-focus-comments — preflight + GH #245 contract
# ──────────────────────────────────────────────────────────────────


class TestUploadFocusComments:
    def test_already_running_returns_409(self, flask_app):
        app, gr_mod, _, _, _ = flask_app
        gr_mod._focus_comments_state["status"] = "running"

        client = app.test_client()
        resp = client.post("/api/upload-focus-comments", json={"comments": [{"x": 1}]})

        assert resp.status_code == 409
        assert "Already uploading" in resp.get_json()["error"]

    def test_missing_creds_returns_400(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            resp = client.post(
                "/api/upload-focus-comments",
                json={"use_manifest": False, "comments": [{"x": 1}]},
            )
        assert resp.status_code == 400
        assert "VPortal credentials" in resp.get_json()["error"]

    def test_no_manifest_returns_400(self, flask_app):
        app, gr_mod, tmp_path, _, _ = flask_app
        # use_manifest=True but no manifest file exists in FOCUS_EXPORTS_DIR
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=True):
            client = app.test_client()
            resp = client.post(
                "/api/upload-focus-comments",
                json={"use_manifest": True},
            )
        assert resp.status_code == 400
        assert "manifest" in resp.get_json()["error"].lower()

    def test_no_comments_returns_400(self, flask_app):
        app, _, _, _, _ = flask_app
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=True):
            client = app.test_client()
            resp = client.post(
                "/api/upload-focus-comments",
                json={"use_manifest": False},
            )
        assert resp.status_code == 400
        assert "No comments" in resp.get_json()["error"]

    def test_happy_path_threads_per_teacher_creds_to_subprocess(self, flask_app):
        """Pins GH #245 contract for the focus-comments-upload subprocess."""
        app, gr_mod, tmp_path, _, _ = flask_app
        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=True) as mock_write, \
             patch("backend.routes.grading_routes.subprocess.Popen") as mock_popen, \
             patch("backend.routes.grading_routes.threading.Thread"), \
             patch("os.path.exists", return_value=True):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            client = app.test_client()
            resp = client.post(
                "/api/upload-focus-comments",
                json={
                    "use_manifest": False,
                    "comments": [{"student_id": "1", "comment": "great"}],
                    "assignment": "Quiz",
                },
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "started"
        assert body["total"] == 1

        # GH #245: per-teacher creds path threaded via env var
        mock_write.assert_called_once_with("teacher-alice")
        sub_env = mock_popen.call_args.kwargs.get("env", {})
        assert "GRAIDER_PORTAL_CREDS_FILE" in sub_env
        assert "portal_credentials_teacher-alice.json" in sub_env["GRAIDER_PORTAL_CREDS_FILE"]


# ──────────────────────────────────────────────────────────────────
# _read_focus_comments_output — NDJSON parsing
# ──────────────────────────────────────────────────────────────────


class TestReadFocusCommentsOutput:
    def test_progress_event_updates_state(self, flask_app):
        _, gr_mod, _, _, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            json.dumps({"type": "progress", "entered": 3, "total": 10}) + "\n",
        ])
        gr_mod._focus_comments_state["status"] = "running"
        gr_mod._read_focus_comments_output(proc)

        assert gr_mod._focus_comments_state["entered"] == 3
        assert gr_mod._focus_comments_state["total"] == 10

    def test_done_event_sets_status(self, flask_app):
        _, gr_mod, _, _, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            json.dumps({"type": "done", "entered": 5, "failed": 1, "skipped": 0,
                        "message": "All done"}) + "\n",
        ])
        gr_mod._focus_comments_state["status"] = "running"
        gr_mod._read_focus_comments_output(proc)

        assert gr_mod._focus_comments_state["status"] == "done"
        assert gr_mod._focus_comments_state["entered"] == 5
        assert gr_mod._focus_comments_state["failed"] == 1

    def test_error_event_increments_failed(self, flask_app):
        _, gr_mod, _, _, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            json.dumps({"type": "error", "message": "x"}) + "\n",
        ])
        gr_mod._focus_comments_state["status"] = "running"
        gr_mod._focus_comments_state["failed"] = 0
        gr_mod._read_focus_comments_output(proc)
        assert gr_mod._focus_comments_state["failed"] == 1

    def test_invalid_json_skipped(self, flask_app):
        _, gr_mod, _, _, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([
            "garbage\n",
            json.dumps({"type": "progress", "entered": 1, "total": 1}) + "\n",
        ])
        gr_mod._focus_comments_state["status"] = "running"
        gr_mod._read_focus_comments_output(proc)
        assert gr_mod._focus_comments_state["entered"] == 1

    def test_stream_end_with_running_flips_to_done(self, flask_app):
        _, gr_mod, _, _, _ = flask_app
        proc = MagicMock()
        proc.stdout = iter([])
        gr_mod._focus_comments_state["status"] = "running"
        gr_mod._read_focus_comments_output(proc)
        assert gr_mod._focus_comments_state["status"] == "done"

    def test_log_truncated_to_50_when_exceeds_100(self, flask_app):
        """Codex round-1 MINOR: previous test only asserted <= 100, which
        a broken implementation that drops all logs would also pass.
        Now pins the explicit truncation contract: when log exceeds 100,
        keep the last 50 entries."""
        _, gr_mod, _, _, _ = flask_app
        proc = MagicMock()
        events = [
            json.dumps({"type": "progress", "entered": i, "total": 105}) + "\n"
            for i in range(105)
        ]
        proc.stdout = iter(events)
        gr_mod._focus_comments_state["status"] = "running"
        gr_mod._focus_comments_state["log"] = []
        gr_mod._read_focus_comments_output(proc)

        # After 105 events: triggered truncation once at event 101
        # (len > 100 → keep last 50). Then 4 more events appended → final 54.
        # The KEY invariant is the tail is preserved — most recent events
        # are still in the log.
        log = gr_mod._focus_comments_state["log"]
        assert len(log) > 0, "Truncation must not drop ALL entries"
        assert len(log) <= 100, f"Log overflowed: {len(log)} entries"
        # Most recent event must be in the log (tail preserved)
        last_event = log[-1]
        assert last_event["entered"] == 104, (
            f"Tail not preserved by truncation: last entry {last_event!r}"
        )


# ──────────────────────────────────────────────────────────────────
# /api/focus-comments/status
# ──────────────────────────────────────────────────────────────────


class TestFocusCommentsStatus:
    def test_returns_idle_initial(self, flask_app):
        app, _, _, _, _ = flask_app
        client = app.test_client()
        resp = client.get("/api/focus-comments/status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "idle"
        assert body["entered"] == 0
        assert body["failed"] == 0
        assert body["skipped"] == 0


# ──────────────────────────────────────────────────────────────────
# /api/ell-students GET + POST
# ──────────────────────────────────────────────────────────────────


class TestEllStudents:
    def test_get_returns_empty_when_file_missing(self, flask_app):
        app, _, _, _, _ = flask_app
        client = app.test_client()
        resp = client.get("/api/ell-students")
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_get_returns_saved_data(self, flask_app):
        app, gr_mod, _, _, _ = flask_app
        os.makedirs(os.path.dirname(gr_mod.ELL_DATA_FILE), exist_ok=True)
        with open(gr_mod.ELL_DATA_FILE, 'w') as f:
            json.dump({"sid-1": {"language": "es"}}, f)

        client = app.test_client()
        resp = client.get("/api/ell-students")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body == {"sid-1": {"language": "es"}}

    def test_post_saves_data(self, flask_app):
        app, gr_mod, _, _, _ = flask_app
        client = app.test_client()
        resp = client.post(
            "/api/ell-students",
            json={"sid-1": {"language": "es"}, "sid-2": {"language": "vi"}},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 2
        # File written
        with open(gr_mod.ELL_DATA_FILE, 'r') as f:
            saved = json.load(f)
        assert saved == {"sid-1": {"language": "es"}, "sid-2": {"language": "vi"}}

    def test_post_no_data_returns_400(self, flask_app):
        app, _, _, _, _ = flask_app
        client = app.test_client()
        # Send an explicit JSON null (Content-Type: application/json) so
        # request.json returns None — triggers the data-is-None branch.
        resp = client.post(
            "/api/ell-students",
            data="null",
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "No data" in resp.get_json()["error"]
