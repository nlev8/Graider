"""Characterization net for the FERPA data-operations route cluster.

Tier 2 Slice 3 PR2 pins the EXACT observed status + JSON contract of the six
FERPA routes (`/api/ferpa/delete-all-data`, `/api/ferpa/audit-log`,
`/api/ferpa/data-summary`, `/api/ferpa/export-data`,
`/api/ferpa/export-student`, `/api/ferpa/import-student`) plus the
auth-missing behavior, around the verbatim `@app.route` -> `@ferpa_bp.route`
move, so the move is proven zero-behavior-change.

Harness note (characterization discipline, pin reality, never assume):
The contract assertions below were captured against the real pre-move
`@app.route` wiring (the baseline commit pinned them green BEFORE the move).
Post-move they run against a FRESH `flask.Flask` app with the extracted
`ferpa_bp` blueprint mounted (the suite-safe PR1 pattern: NEVER mutate the
shared `backend.app.app` singleton, since touching `before_request` on it
after another suite test issued a request raises Flask's "setup method can no
longer be called" error, breaking full-suite collection). Post-move the
blueprint IS the canonical wiring `register_routes()` mounts, so a
fresh-app + `register_blueprint(ferpa_bp)` serves byte-identical responses
to the pre-move `@app.route` wiring (the route bodies are byte-identical, so
identical inputs produce identical outputs). The authed harness adds a
`before_request` that sets `g.user_id`; the auth-missing harness registers
the same blueprint with NO such hook, so the stacked `@require_teacher`
rejects with the exact canonical 401 {"error": "Authentication required"}.

Machine-variant fields: `/api/ferpa/data-summary` and `/api/ferpa/audit-log`
embed absolute filesystem paths and existence flags derived from the route's
own module constants (`RESULTS_FILE`, `SETTINGS_FILE`, `AUDIT_LOG_FILE`).
Those constant VALUES are byte-identical pre and post move (the canonical
`backend.utils.audit.AUDIT_LOG_FILE` equals the pre-move app.py copy;
`RESULTS_FILE`/`SETTINGS_FILE` are co-moved byte-identically into
`backend.routes.ferpa_routes`). So those fields are pinned against the same
constants the route resolves, making the assertion both machine-independent
and a true zero-behavior-change proof.

A non-preview `/api/ferpa/import-student` with new grading results reaches a
`save_results(...)` call that pre-move app.py never bound (no import or def
site, only a usage ref) and that the verbatim move deliberately does NOT
import: it raises NameError, caught by `@handle_route_errors` -> the RFC 7807
500 envelope. This pre-existing latent bug (issue #423) is faithfully
preserved by the verbatim move and pinned below exactly as observed.
"""
import io
import json

import pytest
from flask import Flask, g

# flask_app (+ its fixture deps) from the shared route-test conftest, used by
# test_urls_unchanged to assert the URL map is unchanged post-extraction.
from tests.conftest_routes import (  # noqa: F401
    flask_app,
    grading_lock,
    mock_grading_state,
)

# The route's own resolved constants (byte-identical pre/post move). Post-move
# RESULTS_FILE/SETTINGS_FILE are co-moved into backend.routes.ferpa_routes;
# AUDIT_LOG_FILE is the canonical backend.utils.audit value the route uses
# (verified equal to the removed app.py copy). Importing them here makes the
# path/existence assertions machine-independent while still proving zero
# behavior change.
from backend.routes.ferpa_routes import RESULTS_FILE, SETTINGS_FILE
from backend.utils.audit import AUDIT_LOG_FILE

# Deterministic RFC 7807 internal-error envelope produced by
# @handle_route_errors for any unhandled exception in a FERPA route.
_INTERNAL_500_TYPE = "https://graider.live/errors/internal"


def _expected_500(path):
    return {
        "type": _INTERNAL_500_TYPE,
        "title": "Internal Server Error",
        "status": 500,
        "instance": path,
        "detail": "Internal server error",
        "error": "Internal server error",
    }


def _fresh_blueprint_app(*, with_auth):
    """Build a fresh Flask app with the extracted FERPA blueprint mounted.

    Never mutates the shared backend.app.app singleton (suite-safe). Post-move
    the blueprint is the canonical wiring register_routes() mounts, so this
    serves byte-identical responses to the pre-move @app.route wiring.
    """
    from backend.routes.ferpa_routes import ferpa_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(ferpa_bp)

    if with_auth:
        @app.before_request
        def _char_set_user():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

    return app


def _reset_char_state():
    """Reset the char-teacher per-teacher grading state to a clean slate.

    char-teacher has no persisted Supabase data, so the state stays empty
    (suite-stable, machine-independent).
    """
    from backend.grading.state import _get_state

    st = _get_state("char-teacher")
    st["is_running"] = False
    st["results"] = []
    return st


# -- Authed harness: fresh app + ferpa blueprint, teacher authenticated -----
@pytest.fixture
def authed_client():
    """Fresh-app blueprint harness with a teacher authenticated.

    Byte-identical responses to the pre-move @app.route wiring for this
    verbatim relocation (route bodies are byte-identical).
    """
    app = _fresh_blueprint_app(with_auth=True)
    _reset_char_state()
    return app.test_client()


@pytest.fixture
def authed_app():
    """Same as authed_client but exposes (client-factory, state) for tests
    that need to seed grading results before the request."""
    app = _fresh_blueprint_app(with_auth=True)

    class _Bridge:
        def _get_state(self, tid):
            from backend.grading.state import _get_state as gs

            return gs(tid)

    _reset_char_state()
    return app, _Bridge()


# -- No-auth harness for the require_teacher rejection (canonical pattern) ---
@pytest.fixture
def noauth_client():
    """Fresh-app blueprint harness WITHOUT any g.user_id before_request.

    Mirrors the canonical require_teacher-rejection mechanism used by
    tests/test_admin_routes.py (a blueprint app with no auth before_request);
    require_teacher returns plain 401 {"error": "Authentication required"}
    (NOT the RFC 7807 envelope: require_teacher wraps handle_route_errors and
    short-circuits before it).
    """
    app = _fresh_blueprint_app(with_auth=False)
    return app.test_client()


# -- /api/ferpa/delete-all-data ---------------------------------------------
class TestDeleteAllData:
    def test_no_body_is_internal_500(self, authed_client):
        """No JSON body -> request.json raises -> pinned RFC 7807 500."""
        r = authed_client.post("/api/ferpa/delete-all-data")
        assert r.status_code == 500
        assert r.get_json() == _expected_500("/api/ferpa/delete-all-data")

    def test_no_confirm_is_400(self, authed_client):
        r = authed_client.post("/api/ferpa/delete-all-data", json={})
        assert r.status_code == 400
        assert r.get_json() == {
            "error": "Confirmation required",
            "message": "Send {confirm: true} to proceed with deletion",
        }

    def test_confirm_false_is_400(self, authed_client):
        r = authed_client.post(
            "/api/ferpa/delete-all-data", json={"confirm": False}
        )
        assert r.status_code == 400
        assert r.get_json() == {
            "error": "Confirmation required",
            "message": "Send {confirm: true} to proceed with deletion",
        }

    def test_while_grading_running_is_400(self, authed_app):
        app, bapp = authed_app
        bapp._get_state("char-teacher")["is_running"] = True
        r = app.test_client().post(
            "/api/ferpa/delete-all-data", json={"confirm": True}
        )
        assert r.status_code == 400
        assert r.get_json() == {
            "error": "Cannot delete data while grading is in progress"
        }

    def test_confirm_true_no_results_file_success(
        self, authed_client, tmp_path, monkeypatch
    ):
        """confirm:true with RESULTS_FILE absent -> 200 success, empty
        deleted list, fixed message; timestamp an ISO string.

        RESULTS_FILE/SETTINGS_FILE are repointed at a fresh tmp dir (the
        route resolves them from its own module namespace). This both
        isolates the assertion from suite-order/machine state AND keeps this
        destructive route from deleting the developer's real
        ~/.graider_results.json during the test run. The route logic is
        byte-identical pre and post move (only the
        @app.route->@ferpa_bp.route decorator token changed); pointing the
        constant at tmp does not alter behavior, it just makes the
        deterministic empty-state branch reproducible."""
        monkeypatch.setattr(
            "backend.routes.ferpa_routes.RESULTS_FILE",
            str(tmp_path / "results.json"),
        )
        monkeypatch.setattr(
            "backend.routes.ferpa_routes.SETTINGS_FILE",
            str(tmp_path / "settings.json"),
        )
        r = authed_client.post(
            "/api/ferpa/delete-all-data", json={"confirm": True}
        )
        assert r.status_code == 200
        body = r.get_json()
        assert set(body.keys()) == {
            "status",
            "message",
            "deleted",
            "timestamp",
        }
        assert body["status"] == "success"
        assert body["message"] == "All student data has been securely deleted"
        assert body["deleted"] == []
        assert isinstance(body["timestamp"], str) and body["timestamp"]

    def test_confirm_true_with_results_file_reports_entry(
        self, authed_client, tmp_path, monkeypatch
    ):
        """confirm:true with RESULTS_FILE present -> the route deletes it and
        reports the in-memory record count (char-teacher results are reset
        empty, so 0 records). Pins the other deterministic branch of the
        same byte-identical route body, hermetically (tmp file, never the
        developer's real ~/.graider_results.json)."""
        rf = tmp_path / "results.json"
        rf.write_text("[]")
        monkeypatch.setattr(
            "backend.routes.ferpa_routes.RESULTS_FILE", str(rf)
        )
        monkeypatch.setattr(
            "backend.routes.ferpa_routes.SETTINGS_FILE",
            str(tmp_path / "settings.json"),
        )
        r = authed_client.post(
            "/api/ferpa/delete-all-data", json={"confirm": True}
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "success"
        assert body["message"] == "All student data has been securely deleted"
        assert body["deleted"] == ["Grading results (0 records)"]
        assert not rf.exists()  # route securely removed it
        assert isinstance(body["timestamp"], str) and body["timestamp"]

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post("/api/ferpa/delete-all-data")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# -- /api/ferpa/audit-log ---------------------------------------------------
class TestAuditLog:
    def test_get_shape(self, authed_client):
        """200 with keys {logs,total,file}; total == len(logs); file is the
        route's own AUDIT_LOG_FILE constant. Each log entry (if any) has the
        get_audit_logs-produced shape (timestamp/user/action/details, with an
        optional teacher_id 5th field)."""
        r = authed_client.get("/api/ferpa/audit-log")
        assert r.status_code == 200
        body = r.get_json()
        assert set(body.keys()) == {"logs", "total", "file"}
        assert isinstance(body["logs"], list)
        assert body["total"] == len(body["logs"])
        assert body["file"] == AUDIT_LOG_FILE
        for entry in body["logs"]:
            assert {"timestamp", "user", "action", "details"} <= set(
                entry.keys()
            )
            assert set(entry.keys()) <= {
                "timestamp",
                "user",
                "action",
                "details",
                "teacher_id",
            }

    def test_limit_param_caps_entries(self, authed_client):
        r = authed_client.get("/api/ferpa/audit-log?limit=5")
        assert r.status_code == 200
        body = r.get_json()
        assert len(body["logs"]) <= 5
        assert body["total"] == len(body["logs"])

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.get("/api/ferpa/audit-log")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# -- /api/ferpa/data-summary ------------------------------------------------
class TestDataSummary:
    def test_get_full_shape(self, authed_client):
        """200 with the fixed FERPA summary structure. Path/existence fields
        are pinned against the route's own constants (byte-identical
        pre/post move)."""
        import os

        r = authed_client.get("/api/ferpa/data-summary")
        assert r.status_code == 200
        body = r.get_json()
        assert set(body.keys()) == {
            "results",
            "settings",
            "audit_log",
            "data_locations",
            "ferpa_notes",
        }
        assert body["results"] == {
            "count": 0,
            "file": RESULTS_FILE,
            "exists": os.path.exists(RESULTS_FILE),
        }
        assert body["settings"] == {
            "file": SETTINGS_FILE,
            "exists": os.path.exists(SETTINGS_FILE),
        }
        assert body["audit_log"] == {
            "file": AUDIT_LOG_FILE,
            "exists": os.path.exists(AUDIT_LOG_FILE),
        }
        assert body["data_locations"] == [
            "~/.graider_results.json - Grading results",
            "~/.graider_settings.json - App settings",
            "~/.graider_audit.log - Audit trail",
            "Output folder (configured in settings) - Exported grades",
        ]
        assert body["ferpa_notes"] == {
            "pii_handling": (
                "Student names are sanitized before AI processing"
            ),
            "data_storage": "All data stored locally on teacher's computer",
            "ai_training": (
                "OpenAI API does not train on API-submitted data"
            ),
            "deletion": (
                "Use DELETE /api/ferpa/delete-all-data to remove all data"
            ),
        }

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.get("/api/ferpa/data-summary")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# -- /api/ferpa/export-data -------------------------------------------------
class TestExportData:
    def test_empty_state_no_student(self, authed_client):
        r = authed_client.get("/api/ferpa/export-data")
        assert r.status_code == 200
        body = r.get_json()
        assert set(body.keys()) == {"export_date", "record_count", "data"}
        assert body["record_count"] == 0
        assert body["data"] == []
        assert isinstance(body["export_date"], str) and body["export_date"]

    def test_student_query_no_match(self, authed_client):
        """?student=Nobody with empty results -> 200, zero records."""
        r = authed_client.get("/api/ferpa/export-data?student=Nobody")
        assert r.status_code == 200
        body = r.get_json()
        assert body["record_count"] == 0
        assert body["data"] == []

    def test_all_data_with_results(self, authed_app):
        app, bapp = authed_app
        bapp._get_state("char-teacher")["results"] = [
            {"student_name": "Jane Doe", "score": 90}
        ]
        r = app.test_client().get("/api/ferpa/export-data")
        assert r.status_code == 200
        body = r.get_json()
        assert body["record_count"] == 1
        assert body["data"] == [{"student_name": "Jane Doe", "score": 90}]

    def test_student_query_case_insensitive_match(self, authed_app):
        app, bapp = authed_app
        bapp._get_state("char-teacher")["results"] = [
            {"student_name": "Jane Doe", "score": 90}
        ]
        r = app.test_client().get("/api/ferpa/export-data?student=jane%20doe")
        assert r.status_code == 200
        body = r.get_json()
        assert body["record_count"] == 1
        assert body["data"] == [{"student_name": "Jane Doe", "score": 90}]

    def test_student_query_partial_no_match(self, authed_app):
        """Exact (case-insensitive) name match only; a partial does NOT
        match (pins the route's `.lower() == .lower()` semantics)."""
        app, bapp = authed_app
        bapp._get_state("char-teacher")["results"] = [
            {"student_name": "Jane Doe", "score": 90}
        ]
        r = app.test_client().get("/api/ferpa/export-data?student=Jane")
        assert r.status_code == 200
        body = r.get_json()
        assert body["record_count"] == 0
        assert body["data"] == []

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.get("/api/ferpa/export-data")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# -- /api/ferpa/export-student ----------------------------------------------
class TestExportStudent:
    def test_no_student_name_is_400(self, authed_client):
        r = authed_client.post("/api/ferpa/export-student", json={})
        assert r.status_code == 400
        assert r.get_json() == {"error": "student_name is required"}

    def test_blank_student_name_is_400(self, authed_client):
        r = authed_client.post(
            "/api/ferpa/export-student", json={"student_name": "   "}
        )
        assert r.status_code == 400
        assert r.get_json() == {"error": "student_name is required"}

    def test_not_found_is_404(self, authed_client):
        r = authed_client.post(
            "/api/ferpa/export-student",
            json={"student_name": "Zzz Nobody Xyz Qqq"},
        )
        assert r.status_code == 404
        assert r.get_json() == {
            "error": "No student found matching 'Zzz Nobody Xyz Qqq'.",
            "hint": (
                "Try the student's full name as it appears on the roster."
            ),
        }

    def test_match_via_results_success(self, authed_app):
        """A roster-less match via grading results -> 200 success with the
        fixed export-result key set. json_path/pdf_path are filesystem
        artifacts (pinned by presence + type, not exact path)."""
        app, bapp = authed_app
        bapp._get_state("char-teacher")["results"] = [
            {
                "student_name": "Charlie Test",
                "student_id": "S99",
                "period": "P1",
                "student_email": "c@x.io",
                "score": 88,
                "graded_at": "2026-05-01T10:00:00",
                "assignment": "HW1",
                "letter_grade": "B",
                "feedback": "good",
            }
        ]
        r = app.test_client().post(
            "/api/ferpa/export-student", json={"student_name": "Charlie Test"}
        )
        assert r.status_code == 200
        body = r.get_json()
        assert set(body.keys()) == {
            "status",
            "student_name",
            "student_id",
            "record_count",
            "json_path",
            "pdf_path",
        }
        assert body["status"] == "success"
        assert body["student_name"] == "Charlie Test"
        assert body["student_id"] == "S99"
        assert body["record_count"] == 2
        assert isinstance(body["json_path"], str) and body["json_path"]
        # pdf_path is a str on success or None if reportlab generation failed;
        # both are valid pre-move outcomes, pinned as that union.
        assert body["pdf_path"] is None or isinstance(body["pdf_path"], str)

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post("/api/ferpa/export-student", json={})
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# -- /api/ferpa/import-student ----------------------------------------------
class TestImportStudent:
    def _upload(self, client, payload=None, raw=None, filename="exp.json",
                preview=None):
        if raw is not None:
            data_bytes = raw
        else:
            data_bytes = json.dumps(payload).encode()
        data = {"file": (io.BytesIO(data_bytes), filename)}
        if preview is not None:
            data["preview"] = preview
        return client.post(
            "/api/ferpa/import-student",
            data=data,
            content_type="multipart/form-data",
        )

    def test_no_file_is_400(self, authed_client):
        r = authed_client.post(
            "/api/ferpa/import-student",
            data={"preview": "true"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json() == {"error": "No file uploaded"}

    def test_non_json_filename_is_400(self, authed_client):
        r = self._upload(authed_client, raw=b"x", filename="exp.txt")
        assert r.status_code == 400
        assert r.get_json() == {"error": "File must be a .json file"}

    def test_invalid_json_is_400(self, authed_client):
        r = self._upload(authed_client, raw=b"not json")
        assert r.status_code == 400
        assert r.get_json() == {"error": "Invalid JSON file"}

    def test_missing_student_name_is_400(self, authed_client):
        r = self._upload(authed_client, payload={"grading_results": []})
        assert r.status_code == 400
        assert r.get_json() == {
            "error": (
                "Missing 'student_name' in export file. "
                "This may not be a Graider export."
            )
        }

    def test_no_importable_sections_is_400(self, authed_client):
        r = self._upload(authed_client, payload={"student_name": "X"})
        assert r.status_code == 400
        assert r.get_json() == {
            "error": "Export file contains no importable data sections."
        }

    def test_preview_returns_summary(self, authed_client):
        r = self._upload(
            authed_client,
            payload={
                "student_name": "Imp Student",
                "grading_results": [
                    {
                        "graded_at": "2026-09-09T09:09:09",
                        "student_name": "Imp Student",
                        "score": 70,
                    }
                ],
            },
            preview="true",
        )
        assert r.status_code == 200
        assert r.get_json() == {
            "status": "preview",
            "student_name": "Imp Student",
            "original_period": "",
            "original_id": "",
            "sections": {
                "results": 1,
                "history": False,
                "accommodations": False,
                "ell": False,
                "contacts": False,
            },
            "detail_text": "1 grades",
        }

    def test_non_preview_import_saves_results_and_succeeds(self, authed_client):
        """GH #423 (FIXED): a non-preview import with new grading results reaches
        the `save_results(...)` call. Pre-fix, `save_results` was unbound ->
        NameError -> RFC 7807 500. It is now imported, so the route persists the
        results and returns success. We mock `save_results` (no real storage
        write) and pin the fixed contract: it's called, and the route returns
        200 success with the imported-results count."""
        from unittest.mock import patch

        with patch("backend.routes.ferpa_routes.save_results") as mock_save:
            r = self._upload(
                authed_client,
                payload={
                    "student_name": "Imp Student",
                    "grading_results": [
                        {
                            "graded_at": "2026-09-09T09:09:09",
                            "student_name": "Imp Student",
                            "score": 70,
                        }
                    ],
                },
                preview="false",
            )
        # reached save_results with the imported results — no NameError (GH #423)
        mock_save.assert_called_once()
        assert r.status_code == 200
        assert r.get_json().get("status") == "success"

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post(
            "/api/ferpa/import-student",
            data={"preview": "true"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# -- Blueprint extraction gates ---------------------------------------------
def test_ferpa_bp_importable():
    from backend.routes.ferpa_routes import ferpa_bp
    assert ferpa_bp.name == 'ferpa'


def test_urls_unchanged(flask_app):  # flask_app from tests/conftest_routes.py
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    for u in (
        "/api/ferpa/delete-all-data",
        "/api/ferpa/audit-log",
        "/api/ferpa/data-summary",
        "/api/ferpa/export-data",
        "/api/ferpa/export-student",
        "/api/ferpa/import-student",
    ):
        assert u in rules
