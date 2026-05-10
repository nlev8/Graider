"""Gap-fill unit tests for backend/routes/clever_routes.py.

Audit MAJOR #4 sprint follow-up to PR #296. Companion to existing
test_clever_*.py files (callback, classes, compliance, sso_contract,
student_sso, unit). Targets the remaining 189 uncovered LOC (54%
baseline) by exercising the post-callback teacher endpoints:

* GET  /api/clever/session          (last_sync_time happy + glob fail)
* POST /api/clever/sync-roster      (no-token / sync-fail / full happy)
* POST /api/clever/apply-accommodations
* POST /api/clever/delete-data      (not-clever / happy / supabase fail)
* GET  /api/clever/district-keys    (no district / happy)
* POST /api/clever/district-keys    (non-admin / no district / no keys
                                     / happy / save fail)
* POST /api/clever/student-token    (invalid code / expired / happy)
* GET  /api/clever/health           (configured / unconfigured)
* POST /api/clever/logout           (happy)
* exchange_student_auth_code helper indirectly + auth code expiry sweep

Strategy: minimal Flask app + register_blueprint (mirrors
test_clever_callback.py). `clever_user` injected via session_transaction.
External services (sync_roster, persist_*, supabase, accommodations,
district_keys) all mocked.
"""
from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask


def _make_app():
    from backend.routes.clever_routes import clever_bp
    from flask import g, session as flask_session
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.register_blueprint(clever_bp)

    # Mimic the production global auth middleware: when a clever_user
    # exists in the session, set g.user_id to "clever:{id}" so that
    # @require_clever_session's fallback in `g.teacher_id =
    # getattr(g, 'user_id', clever_user.get('clever_id', ''))` lands
    # on the prefixed form (matching what auth.py does in production
    # via resolve_clever_user_id()).
    @app.before_request
    def _populate_clever_g():
        cu = flask_session.get("clever_user")
        if cu and "clever_id" in cu:
            g.user_id = f"clever:{cu['clever_id']}"

    return app


def _logged_in_session(client, role="teacher"):
    """Pre-populate the test client's session with a Clever user."""
    with client.session_transaction() as sess:
        sess["clever_user"] = {
            "clever_id": "clever-teacher-001",
            "email": "teacher@school.edu",
            "name": {"first": "Ada", "last": "Lovelace"},
            "type": role,
            "district": "district-xyz",
        }


# ──────────────────────────────────────────────────────────────────
# /api/clever/session — last_sync_time branches
# ──────────────────────────────────────────────────────────────────


class TestSessionCheck:
    def test_no_session_returns_unauthenticated(self):
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/clever/session")
        assert resp.get_json() == {"authenticated": False}

    def test_authenticated_with_no_roster_files(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch("glob.glob", return_value=[]):
                resp = client.get("/api/clever/session")
        body = resp.get_json()
        assert body["authenticated"] is True
        assert body["clever_id"] == "clever-teacher-001"
        assert body["last_sync"] is None
        assert body["account_linked"] is False  # resolves to clever:{id}

    def test_authenticated_with_roster_file_returns_mtime(self, tmp_path):
        app = _make_app()
        # Create a real roster file in tmp_path; getmtime returns its
        # actual mtime.
        roster_dir = tmp_path / "rosters"
        roster_dir.mkdir()
        f = roster_dir / "clever_roster_clever-teacher-001.csv"
        f.write_text("name,email\n")
        expected_mtime = f.stat().st_mtime

        with app.test_client() as client:
            _logged_in_session(client)
            with patch("glob.glob", return_value=[str(f)]):
                resp = client.get("/api/clever/session")
        body = resp.get_json()
        assert body["last_sync"] == expected_mtime

    def test_glob_exception_swallowed(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch("glob.glob", side_effect=RuntimeError("fs err")):
                resp = client.get("/api/clever/session")
        body = resp.get_json()
        assert body["authenticated"] is True
        assert body["last_sync"] is None


# ──────────────────────────────────────────────────────────────────
# /api/clever/sync-roster
# ──────────────────────────────────────────────────────────────────


class TestSyncRoster:
    def test_no_district_token_returns_503(self, monkeypatch):
        monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            resp = client.post("/api/clever/sync-roster")
        assert resp.status_code == 503
        assert "District token" in resp.get_json()["error"]

    def test_sync_failure_returns_502(self, monkeypatch):
        monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "tok")
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes._run_async",
                side_effect=RuntimeError("clever api dead"),
            ):
                resp = client.post("/api/clever/sync-roster")
        assert resp.status_code == 502
        assert "Failed to sync" in resp.get_json()["error"]

    def test_happy_path_with_section_filter(self, monkeypatch):
        monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "tok")
        app = _make_app()
        # Roster has 2 sections, one for our teacher + one for someone
        # else. Server-side filter keeps only our sections, then the
        # selected_section_ids body filter narrows further.
        roster = {
            "sections": [
                {"data": {
                    "id": "sec-mine-1", "name": "Math",
                    "teachers": ["clever-teacher-001"],
                    "students": ["stu-1"],
                }},
                {"data": {
                    "id": "sec-others", "name": "Science",
                    "teachers": [{"id": "clever-other"}],
                    "students": ["stu-2"],
                }},
            ],
            "students": [
                {"data": {"id": "stu-1", "name": {"first": "A"}}},
                {"data": {"id": "stu-2", "name": {"first": "B"}}},
            ],
            "teachers": [{"data": {"id": "clever-teacher-001"}}],
            "contacts": [{"id": "c1"}],
        }

        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes._run_async",
                return_value=roster,
            ), patch(
                "backend.routes.clever_routes.persist_roster_as_csv",
            ), patch(
                "backend.routes.clever_routes.persist_sections_as_periods",
            ), patch(
                "backend.routes.clever_routes.extract_parent_contacts",
                return_value={"stu-1": "parent@example.com"},
            ), patch(
                "backend.routes.clever_routes.persist_parent_contacts",
            ), patch(
                "backend.routes.clever_routes.extract_student_accommodations",
                return_value=[{"student_id": "stu-1", "iep": True}],
            ), patch(
                "backend.routes.clever_routes._sync_classes_to_db",
            ), patch(
                "backend.routes.clever_routes.map_sections_to_periods",
                return_value=[
                    {"section_id": "sec-mine-1", "period_label": "P1"},
                    {"section_id": "sec-others", "period_label": "P2"},
                ],
            ):
                resp = client.post(
                    "/api/clever/sync-roster",
                    json={"section_ids": ["sec-mine-1"]},
                )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["status"] == "synced"
        # Only OUR section made it through both filters
        assert body["counts"]["sections"] == 1
        # And only stu-1 (the only student in sec-mine-1)
        assert body["counts"]["students"] == 1
        assert body["counts"]["parent_contacts"] == 1
        assert body["counts"]["students_with_accommodations"] == 1
        # available_sections returns ALL sections (pre-filter) for UI
        assert len(body["available_sections"]) == 2

    def test_no_section_filter_keeps_all_own_sections(self, monkeypatch):
        monkeypatch.setenv("CLEVER_DISTRICT_TOKEN", "tok")
        app = _make_app()
        roster = {
            "sections": [
                {"data": {
                    "id": "sec-1", "teachers": ["clever-teacher-001"],
                    "students": ["stu-1"],
                }},
            ],
            "students": [{"data": {"id": "stu-1"}}],
            "teachers": [],
            "contacts": [],
        }
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes._run_async",
                return_value=roster,
            ), patch(
                "backend.routes.clever_routes.persist_roster_as_csv",
            ), patch(
                "backend.routes.clever_routes.persist_sections_as_periods",
            ), patch(
                "backend.routes.clever_routes.extract_student_accommodations",
                return_value=[],
            ), patch(
                "backend.routes.clever_routes._sync_classes_to_db",
            ), patch(
                "backend.routes.clever_routes.map_sections_to_periods",
                return_value=[],
            ):
                # No section_ids body → keep all teacher-owned sections
                resp = client.post("/api/clever/sync-roster")
        body = resp.get_json()
        assert body["counts"]["sections"] == 1


# ──────────────────────────────────────────────────────────────────
# /api/clever/apply-accommodations
# ──────────────────────────────────────────────────────────────────


class TestApplyAccommodations:
    def test_applies_each_accommodation_with_ell_note(self):
        app = _make_app()
        accomm = {
            "stu-1": {
                "name": "Ada",
                "suggested_presets": ["simplified_language"],
                "custom_notes": "Note",
                "ell_status": True,
                "home_language": "Spanish",
            },
            "stu-2": {
                "name": "Babbage",
                "suggested_presets": [],
                "custom_notes": "",
            },
        }
        set_mock = MagicMock(return_value=True)
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.set_student_accommodation",
                set_mock,
            ):
                resp = client.post(
                    "/api/clever/apply-accommodations",
                    json={"accommodations": accomm},
                )
        body = resp.get_json()
        assert body["applied"] == 2
        assert body["total"] == 2
        # First call should have ELL note appended
        first_call = set_mock.call_args_list[0]
        notes = first_call.kwargs["custom_notes"]
        assert "Home language: Spanish" in notes
        assert "Note" in notes

    def test_set_returns_false_records_error(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.set_student_accommodation",
                return_value=False,
            ):
                resp = client.post(
                    "/api/clever/apply-accommodations",
                    json={"accommodations": {
                        "stu-1": {"name": "X", "suggested_presets": []},
                    }},
                )
        body = resp.get_json()
        assert body["applied"] == 0
        assert body["errors"]
        assert "Failed to save" in body["errors"][0]

    def test_set_raises_records_error(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.set_student_accommodation",
                side_effect=RuntimeError("db down"),
            ):
                resp = client.post(
                    "/api/clever/apply-accommodations",
                    json={"accommodations": {
                        "stu-1": {"name": "X", "suggested_presets": []},
                    }},
                )
        body = resp.get_json()
        assert body["applied"] == 0
        assert "Error for" in body["errors"][0]


# ──────────────────────────────────────────────────────────────────
# /api/clever/delete-data
# ──────────────────────────────────────────────────────────────────


class TestDeleteData:
    def test_non_clever_user_returns_403(self):
        # Build an app whose before_request sets g.user_id to a Supabase
        # UUID (account is linked, so teacher_id no longer carries the
        # "clever:" prefix). Production's `if not teacher_id.startswith(
        # "clever:")` then short-circuits the deletion with 403.
        from backend.routes.clever_routes import clever_bp
        from flask import g, session as flask_session
        app = Flask(__name__)
        app.secret_key = "test-secret-key"
        app.register_blueprint(clever_bp)

        @app.before_request
        def _set_linked_uid():
            if flask_session.get("clever_user"):
                g.user_id = "supabase-uuid-1"  # Linked, no "clever:" prefix

        with app.test_client() as client:
            _logged_in_session(client)
            resp = client.post("/api/clever/delete-data")
        assert resp.status_code == 403
        assert "Not a Clever user" in resp.get_json()["error"]

    def test_happy_path_deletes_files_and_supabase_data(self):
        app = _make_app()
        # Build a Supabase mock that returns class IDs / content / students
        sb = MagicMock()
        # classes select.eq.execute → 2 classes
        # published_content select.in_.execute → 1 content item
        # students_res select.eq.execute → 2 students

        def execute_dispatcher(*args, **kwargs):
            return MagicMock(data=[])

        # Build chain stubs per-table
        classes_chain = MagicMock()
        classes_chain.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": "cls-1"}, {"id": "cls-2"}])
        )
        classes_chain.delete.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )

        published_content_chain = MagicMock()
        published_content_chain.select.return_value.in_.return_value.execute.return_value = (
            MagicMock(data=[{"id": "content-1"}])
        )
        published_content_chain.delete.return_value.in_.return_value.execute.return_value = (
            MagicMock(data=[])
        )

        student_subs_chain = MagicMock()
        student_subs_chain.delete.return_value.in_.return_value.execute.return_value = (
            MagicMock(data=[])
        )

        class_students_chain = MagicMock()
        class_students_chain.delete.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )

        students_chain = MagicMock()
        students_chain.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": "s1"}, {"id": "s2"}])
        )
        students_chain.delete.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )

        student_sessions_chain = MagicMock()
        student_sessions_chain.delete.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )

        def table_side_effect(name):
            return {
                "classes": classes_chain,
                "published_content": published_content_chain,
                "student_submissions": student_subs_chain,
                "class_students": class_students_chain,
                "students": students_chain,
                "student_sessions": student_sessions_chain,
            }.get(name, MagicMock())

        sb.table.side_effect = table_side_effect

        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.delete_clever_data",
                return_value={"local_files": 5},
            ), patch(
                "backend.routes.clever_routes._get_supabase_safe",
                return_value=sb,
            ):
                resp = client.post("/api/clever/delete-data")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["status"] == "deleted"
        # supabase_deleted populated with class + student counts
        assert body["deleted"]["supabase_deleted"]["classes"] == 2
        assert body["deleted"]["supabase_deleted"]["students"] == 2

    def test_supabase_failure_records_partial_error(self):
        app = _make_app()
        # _get_supabase_safe returns a sb whose first .table() call raises
        sb = MagicMock()
        sb.table.side_effect = RuntimeError("supabase down")

        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.delete_clever_data",
                return_value={"local_files": 3},
            ), patch(
                "backend.routes.clever_routes._get_supabase_safe",
                return_value=sb,
            ):
                resp = client.post("/api/clever/delete-data")
        body = resp.get_json()
        assert body["status"] == "deleted"
        assert "supabase_error" in body["deleted"]
        assert "Partial deletion" in body["deleted"]["supabase_error"]

    def test_no_supabase_returns_local_only(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.delete_clever_data",
                return_value={"local_files": 2},
            ), patch(
                "backend.routes.clever_routes._get_supabase_safe",
                return_value=None,
            ):
                resp = client.post("/api/clever/delete-data")
        body = resp.get_json()
        assert body["status"] == "deleted"
        # No supabase_deleted key (sb was None, branch skipped)
        assert "supabase_deleted" not in body["deleted"]

    def test_outer_exception_returns_500(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.routes.clever_routes.delete_clever_data",
                side_effect=RuntimeError("local fs gone"),
            ):
                resp = client.post("/api/clever/delete-data")
        assert resp.status_code == 500
        assert "internal error" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# /api/clever/district-keys (GET + POST)
# ──────────────────────────────────────────────────────────────────


class TestDistrictKeys:
    def test_status_no_district_returns_400(self):
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["clever_user"] = {
                    "clever_id": "c-1", "type": "teacher", "district": "",
                }
            resp = client.get("/api/clever/district-keys")
        assert resp.status_code == 400
        assert "No district" in resp.get_json()["error"]

    def test_status_returns_keys_payload(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            with patch(
                "backend.api_keys.check_district_keys",
                return_value={"openai": True, "anthropic": False},
            ):
                resp = client.get("/api/clever/district-keys")
        body = resp.get_json()
        assert body["district_id"] == "district-xyz"
        assert body["keys"]["openai"] is True

    def test_save_non_admin_returns_403(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client, role="teacher")  # not district_admin
            resp = client.post(
                "/api/clever/district-keys",
                json={"openai": "sk-x"},
            )
        assert resp.status_code == 403
        assert "Only district administrators" in resp.get_json()["error"]

    def test_save_no_district_returns_400(self):
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["clever_user"] = {
                    "clever_id": "c-1", "type": "district_admin",
                    "district": "",
                }
            resp = client.post(
                "/api/clever/district-keys",
                json={"openai": "sk-x"},
            )
        assert resp.status_code == 400

    def test_save_no_keys_returns_400(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client, role="district_admin")
            # Empty / whitespace values are stripped → no keys
            resp = client.post(
                "/api/clever/district-keys",
                json={"openai": "  ", "anthropic": ""},
            )
        assert resp.status_code == 400
        assert "No API keys provided" in resp.get_json()["error"]

    def test_save_happy_path(self):
        app = _make_app()
        save_mock = MagicMock(return_value=True)
        with app.test_client() as client:
            _logged_in_session(client, role="district_admin")
            with patch(
                "backend.api_keys.save_district_keys", save_mock,
            ):
                resp = client.post(
                    "/api/clever/district-keys",
                    json={
                        "openai": "sk-openai",
                        "anthropic": "sk-ant",
                        "gemini": "  ",  # whitespace ignored
                    },
                )
        body = resp.get_json()
        assert body["status"] == "saved"
        assert body["district_id"] == "district-xyz"
        save_mock.assert_called_once()
        keys_arg = save_mock.call_args.args[1]
        assert keys_arg["openai"] == "sk-openai"
        assert keys_arg["anthropic"] == "sk-ant"
        assert "gemini" not in keys_arg

    def test_save_failure_returns_500(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client, role="district_admin")
            with patch(
                "backend.api_keys.save_district_keys",
                return_value=False,
            ):
                resp = client.post(
                    "/api/clever/district-keys",
                    json={"openai": "sk-x"},
                )
        assert resp.status_code == 500
        assert "Failed to save" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# /api/clever/student-token (auth-code exchange)
# ──────────────────────────────────────────────────────────────────


class TestStudentTokenExchange:
    def test_no_code_returns_401(self):
        app = _make_app()
        with app.test_client() as client:
            resp = client.post("/api/clever/student-token", json={})
        assert resp.status_code == 401

    def test_invalid_code_returns_401(self):
        app = _make_app()
        with app.test_client() as client:
            resp = client.post(
                "/api/clever/student-token",
                json={"code": "not-in-pending"},
            )
        assert resp.status_code == 401

    def test_expired_code_returns_401(self):
        from backend.routes.clever_routes import (
            _create_student_auth_code, _pending_student_auth_codes,
        )
        # Create then make stale by overwriting expires
        code = _create_student_auth_code("token-1")
        _pending_student_auth_codes[code]["expires"] = time.time() - 1
        app = _make_app()
        with app.test_client() as client:
            resp = client.post(
                "/api/clever/student-token",
                json={"code": code},
            )
        assert resp.status_code == 401
        assert "expired" in resp.get_json()["error"].lower()

    def test_happy_path_returns_token(self):
        from backend.routes.clever_routes import _create_student_auth_code
        code = _create_student_auth_code("test-session-token")
        app = _make_app()
        with app.test_client() as client:
            resp = client.post(
                "/api/clever/student-token",
                json={"code": code},
            )
        assert resp.get_json()["token"] == "test-session-token"


# ──────────────────────────────────────────────────────────────────
# /api/clever/health
# ──────────────────────────────────────────────────────────────────


class TestHealth:
    def test_unconfigured_returns_503(self, monkeypatch):
        for k in ("CLEVER_CLIENT_ID", "CLEVER_CLIENT_SECRET",
                  "CLEVER_REDIRECT_URI", "CLEVER_DISTRICT_TOKEN",
                  "CLEVER_API_VERSION"):
            monkeypatch.delenv(k, raising=False)
        app = _make_app()
        with app.test_client() as client:
            with patch(
                "backend.routes.clever_routes.get_clever_config",
                return_value=None,
            ), patch(
                "backend.routes.clever_routes._get_supabase_safe",
                return_value=None,
            ):
                resp = client.get("/api/clever/health")
        assert resp.status_code == 503
        body = resp.get_json()
        assert body["configured"] is False
        assert body["client_id_set"] is False
        assert body["supabase_available"] is False

    def test_configured_returns_200(self, monkeypatch):
        for k, v in [
            ("CLEVER_CLIENT_ID", "cid"),
            ("CLEVER_CLIENT_SECRET", "csec"),
            ("CLEVER_REDIRECT_URI", "https://example/cb"),
            ("CLEVER_DISTRICT_TOKEN", "dtok"),
        ]:
            monkeypatch.setenv(k, v)
        app = _make_app()
        with app.test_client() as client:
            with patch(
                "backend.routes.clever_routes.get_clever_config",
                return_value={"client_id": "cid"},
            ), patch(
                "backend.routes.clever_routes._get_supabase_safe",
                return_value=MagicMock(),
            ):
                resp = client.get("/api/clever/health")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["configured"] is True
        assert body["client_id_set"] is True
        assert body["supabase_available"] is True


# ──────────────────────────────────────────────────────────────────
# /api/clever/logout
# ──────────────────────────────────────────────────────────────────


class TestLogout:
    def test_clears_session(self):
        app = _make_app()
        with app.test_client() as client:
            _logged_in_session(client)
            resp = client.post("/api/clever/logout")
        assert resp.status_code == 200
        # Session pop happened — subsequent /session check returns False
        with app.test_client() as client2:
            resp2 = client2.get("/api/clever/session")
        assert resp2.get_json() == {"authenticated": False}
