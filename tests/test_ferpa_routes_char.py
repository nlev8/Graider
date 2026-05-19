"""Characterization net for the FERPA data-operations route cluster.

Tier 2 Slice 3 PR2 pins the EXACT observed status + JSON contract of the six
FERPA routes (`/api/ferpa/delete-all-data`, `/api/ferpa/audit-log`,
`/api/ferpa/data-summary`, `/api/ferpa/export-data`,
`/api/ferpa/export-student`, `/api/ferpa/import-student`) plus the
auth-missing behavior, BEFORE the verbatim `@app.route` ->
`@ferpa_bp.route` move, so the move can be proven zero-behavior-change.

Harness note (characterization discipline, pin reality, never assume):
The six routes are currently wired via bare `@app.route` decorators on the
`backend.app.app` object. The `client` fixture in tests/conftest_routes.py
builds its app from `register_routes(...)`, which (pre-move) does NOT include
this cluster, so that fixture returns 404 for these paths pre-move and real
responses post-move, i.e. it is NOT byte-identical across the move and
therefore cannot characterize a zero-behavior-change relocation.

The only harness that yields byte-identical status+JSON both before and after
the verbatim move is the real `backend.app.app` object, because:
  * pre-move the cluster is registered there via `@app.route`;
  * post-move the cluster is registered there via the blueprint that
    `register_routes()` mounts (app.py calls register_routes on the same app);
  * the route bodies are byte-identical, so the responses are identical.
So the contract assertions below run against `backend.app.app` with a
`before_request` that authenticates a teacher (the "current @app.route
wiring" Task 2.1 Step 1 names). This mirrors the exact pre-move baseline
harness PR1 used; Task 2.2 rewrites this file to the suite-safe
`_fresh_blueprint_app` pattern once the blueprint exists. The auth-missing
case reuses the canonical existing pattern (see tests/test_admin_routes.py):
the real app with NO g.user_id before_request, so the stacked
`@require_teacher` decorator rejects with 401. Both yield byte-identical
401 JSON pre and post move.

Machine-variant fields: `/api/ferpa/data-summary` and `/api/ferpa/audit-log`
embed absolute filesystem paths and existence flags derived from the route's
own module constants (`RESULTS_FILE`, `SETTINGS_FILE`, `AUDIT_LOG_FILE`).
Those constant VALUES are byte-identical pre and post move (the canonical
`backend.utils.audit.AUDIT_LOG_FILE` equals the pre-move app.py copy;
`RESULTS_FILE`/`SETTINGS_FILE` are co-moved byte-identically). So those
fields are pinned against the same constants the route resolves, making the
assertion both machine-independent and a true zero-behavior-change proof.

A non-preview `/api/ferpa/import-student` with new grading results reaches an
app.py `save_results(...)` call that pre-move app.py never bound (no import
or def site, only a usage ref): it raises NameError, caught by
`@handle_route_errors` -> the RFC 7807 500 envelope. This pre-existing latent
bug (issue #423) is faithfully preserved by the verbatim move and pinned
below exactly as observed.
"""
import io
import json

import pytest
from flask import g

# The route's own resolved constants (byte-identical pre/post move). Pre-move
# all three live on backend.app; AUDIT_LOG_FILE is the canonical
# backend.utils.audit value the route uses post-move (verified equal to the
# pre-move app.py copy). Importing them here makes path/existence assertions
# machine-independent while still proving zero behavior change.
from backend.app import RESULTS_FILE, SETTINGS_FILE
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


# -- Authed harness: the real backend.app.app, teacher authenticated --------
@pytest.fixture
def authed_client():
    """Real backend.app.app with a teacher authenticated.

    This is the "current @app.route wiring" pre-move and the
    register_routes-mounted blueprint post-move, byte-identical responses
    either way for a verbatim relocation. char-teacher has no persisted
    Supabase data, so the per-teacher grading state stays a clean slate
    (suite-stable, machine-independent).
    """
    import backend.app as bapp

    app = bapp.app
    app.config["TESTING"] = True

    # Idempotent: only attach the auth before_request once.
    if not getattr(app, "_char_ferpa_authed_hook", False):
        @app.before_request
        def _char_set_user():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

        app._char_ferpa_authed_hook = True

    # Reset this teacher's grading state to a clean slate per test.
    st = bapp._get_state("char-teacher")
    st["is_running"] = False
    st["results"] = []

    return app.test_client()


@pytest.fixture
def authed_app():
    """Same as authed_client but exposes the app for direct state mutation."""
    import backend.app as bapp

    app = bapp.app
    app.config["TESTING"] = True
    if not getattr(app, "_char_ferpa_authed_hook", False):
        @app.before_request
        def _char_set_user():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

        app._char_ferpa_authed_hook = True
    st = bapp._get_state("char-teacher")
    st["is_running"] = False
    st["results"] = []
    return app, bapp


# -- No-auth harness for the require_teacher rejection (canonical pattern) ---
@pytest.fixture
def noauth_client():
    """Real backend.app.app WITHOUT any g.user_id before_request.

    require_teacher returns plain 401 {"error": "Authentication required"}
    (NOT the RFC 7807 envelope: require_teacher wraps handle_route_errors and
    short-circuits before it).
    """
    import backend.app as bapp

    # A separate process-shared singleton would already have the authed hook
    # from another test; require_teacher only rejects when g.user_id is unset.
    # The canonical pattern (tests/test_admin_routes.py) uses a minimal app
    # with NO auth hook. Build one here mounting the same view functions so
    # the stacked @require_teacher decorator is exercised identically.
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.add_url_rule(
        "/api/ferpa/delete-all-data",
        view_func=bapp.delete_all_student_data,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/ferpa/audit-log", view_func=bapp.get_audit_log, methods=["GET"]
    )
    app.add_url_rule(
        "/api/ferpa/data-summary",
        view_func=bapp.get_data_summary,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/ferpa/export-data",
        view_func=bapp.export_student_data,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/ferpa/export-student",
        view_func=bapp.export_individual_student_data,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/ferpa/import-student",
        view_func=bapp.import_individual_student_data,
        methods=["POST"],
    )
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

    def test_confirm_true_empty_state_success(self, authed_client):
        """confirm:true with empty state -> 200 success, empty deleted list.

        timestamp is a wall-clock ISO string (the only non-deterministic
        field); pinned by shape, the rest pinned exactly.
        """
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

    def test_non_preview_save_results_nameerror_is_500(self, authed_client):
        """ISSUE #423: a non-preview import with new grading results reaches
        an app.py `save_results(...)` call that pre-move app.py never bound
        (no import or def site, only a usage ref) -> NameError -> caught by
        @handle_route_errors -> the RFC 7807 500 envelope. This pre-existing
        latent bug is faithfully preserved by the verbatim move and pinned
        here exactly as observed pre-move."""
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
        assert r.status_code == 500
        assert r.get_json() == _expected_500("/api/ferpa/import-student")

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post(
            "/api/ferpa/import-student",
            data={"preview": "true"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}
