"""
Task A — multi-enrollment Clever student-SSO disambiguation.

Defect (clever_routes.py:176-205, self-documented): the student lookup
+ `.limit(1)` enrollment query make "the first DB row wins" when a
Clever student is enrolled in multiple classes (or exists under
multiple teachers' rosters). A multi-enrolled student can be dropped
into the WRONG class session with no choice.

Fix: enumerate ALL enrollments. Exactly one → behave exactly as before
(regression-guarded separately). More than one → return a
`needs_class_selection` payload + short-lived selection token instead
of silently minting a session; a finalize endpoint exchanges the
token + chosen class_id for the real scoped session.

Zero network calls — Supabase is mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from flask import Flask

from backend.routes.clever_routes import _create_clever_student_session


def _make_app():
    from backend.routes.clever_routes import clever_bp
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.register_blueprint(clever_bp)
    return app


def _clever_student_user():
    return {
        "clever_id": "clever-abc",
        "email": "jane@school.edu",
        "name": {"first": "Jane", "last": "Doe"},
        "type": "student",
        "district": "district-xyz",
    }


def _make_sb(student_rows, enroll_rows, capture=None):
    """Mock Supabase wired for _create_clever_student_session.

    student_rows: list returned by the students lookup.
    enroll_rows : list returned by the class_students lookup.
    capture     : optional dict; records whether student_sessions.insert ran.
    """
    sb = MagicMock()

    def _table(name):
        if name == "students":
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=list(student_rows))
            return q
        if name == "class_students":
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.limit.return_value = q          # tolerate with/without .limit()
            q.execute.return_value = MagicMock(data=list(enroll_rows))
            return q
        if name == "student_sessions":
            q = MagicMock()

            def _insert(payload):
                if capture is not None:
                    capture["session_inserted"] = True
                    capture["session_payload"] = payload
                return q

            q.insert.side_effect = _insert
            q.execute.return_value = MagicMock(data=[{"id": "sess-001"}])
            return q
        return MagicMock()

    sb.table.side_effect = _table
    return sb


def test_multiple_enrollments_returns_needs_class_selection():
    """A student enrolled in 2 classes must NOT be silently dropped into
    the first one — return a disambiguation payload instead."""
    student_row = {
        "id": "db-stu-001",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@school.edu",
        "student_id_number": "clever-abc",
        "period": "3",
    }
    enroll_rows = [
        {"class_id": "cls-001", "classes": {"id": "cls-001", "name": "Math 9", "subject": "math"}},
        {"class_id": "cls-002", "classes": {"id": "cls-002", "name": "Science 9", "subject": "science"}},
    ]
    capture = {}
    sb = _make_sb([student_row], enroll_rows, capture)

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
        result = _create_clever_student_session("clever-abc", "jane@school.edu")

    assert result is not None
    assert result.get("status") == "needs_class_selection", result
    # both candidate classes offered, with display info
    names = sorted(c["name"] for c in result["classes"])
    assert names == ["Math 9", "Science 9"], result["classes"]
    ids = sorted(c["class_id"] for c in result["classes"])
    assert ids == ["cls-001", "cls-002"]
    # a usable short-lived selection token, NOT a real session
    assert isinstance(result.get("selection_token"), str) and len(result["selection_token"]) > 16
    assert "token" not in result, "no real session token until the student picks a class"
    assert capture.get("session_inserted") is not True, "no student_sessions row before selection"


# ---------------------------------------------------------------------------
# Cycle 2 — OAuth caller must not 500 on the new branch; finalize endpoint.
# ---------------------------------------------------------------------------

def test_callback_redirects_to_picker_on_needs_class_selection():
    """The OAuth callback must hand a multi-enrolled student to the picker
    (clever_select + sel token), NOT crash on student_session['token']."""
    app = _make_app()
    sel = {
        "status": "needs_class_selection",
        "classes": [
            {"class_id": "cls-001", "name": "Math 9", "subject": "math"},
            {"class_id": "cls-002", "name": "Science 9", "subject": "science"},
        ],
        "selection_token": "seltok-XYZ-1234567890",
    }
    with (
        patch("backend.routes.clever_routes.exchange_code_for_token",
              new=AsyncMock(return_value={"access_token": "t"})),
        patch("backend.routes.clever_routes.get_clever_user",
              new=AsyncMock(return_value=_clever_student_user())),
        patch("backend.routes.clever_routes._create_clever_student_session",
              return_value=sel),
    ):
        with app.test_client() as client:
            with client.session_transaction() as s:
                s["clever_oauth_state"] = "valid-state"
            resp = client.get("/api/clever/callback?code=abc&state=valid-state")

    assert resp.status_code == 302, resp.status_code
    assert "/student" in resp.location
    assert "clever_select=1" in resp.location
    assert "sel=seltok-XYZ-1234567890" in resp.location
    assert "code=" not in resp.location  # not the normal auth-code path


def test_select_class_finalizes_session_for_chosen_class():
    """POST /api/clever/select-class with a valid token + chosen class
    mints a real session scoped to that class."""
    from backend.routes import clever_routes

    student_row = {
        "id": "db-stu-001", "first_name": "Jane", "last_name": "Doe",
        "email": "jane@school.edu", "student_id_number": "clever-abc", "period": "3",
    }
    candidates = [
        {"class_id": "cls-001", "name": "Math 9", "subject": "math"},
        {"class_id": "cls-002", "name": "Science 9", "subject": "science"},
    ]
    clever_routes._pending_class_selections["seltok-1"] = {
        "student_row": student_row,
        "candidates": candidates,
        "expires": clever_routes._time.time() + 120,
    }
    capture = {}
    sb = _make_sb([student_row], [], capture)
    app = _make_app()

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
        with app.test_client() as client:
            resp = client.post("/api/clever/select-class",
                                json={"selection_token": "seltok-1", "class_id": "cls-002"})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert isinstance(body.get("token"), str) and len(body["token"]) > 20
    assert capture.get("session_inserted") is True
    assert capture["session_payload"]["class_id"] == "cls-002"
    # token is single-use
    assert "seltok-1" not in clever_routes._pending_class_selections


def test_select_class_rejects_unknown_token():
    app = _make_app()
    with app.test_client() as client:
        resp = client.post("/api/clever/select-class",
                            json={"selection_token": "nope", "class_id": "cls-001"})
    assert resp.status_code == 401


def test_select_class_rejects_class_not_in_candidates():
    from backend.routes import clever_routes
    clever_routes._pending_class_selections["seltok-2"] = {
        "student_row": {"id": "db-stu-001"},
        "candidates": [{"class_id": "cls-001", "name": "Math 9", "subject": "math"}],
        "expires": clever_routes._time.time() + 120,
    }
    app = _make_app()
    with app.test_client() as client:
        resp = client.post("/api/clever/select-class",
                            json={"selection_token": "seltok-2", "class_id": "cls-999"})
    assert resp.status_code == 400
    # rejected attempt must not consume the token
    assert "seltok-2" in clever_routes._pending_class_selections


def test_select_class_get_lists_candidates_without_consuming():
    """GET /api/clever/select-class?selection_token=… returns the candidate
    classes so the picker can render — and does NOT consume the token."""
    from backend.routes import clever_routes
    candidates = [
        {"class_id": "cls-001", "name": "Math 9", "subject": "math"},
        {"class_id": "cls-002", "name": "Science 9", "subject": "science"},
    ]
    clever_routes._pending_class_selections["seltok-3"] = {
        "student_row": {"id": "db-stu-001"},
        "candidates": candidates,
        "expires": clever_routes._time.time() + 120,
    }
    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/api/clever/select-class?selection_token=seltok-3")

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    names = sorted(c["name"] for c in body["classes"])
    assert names == ["Math 9", "Science 9"]
    assert "seltok-3" in clever_routes._pending_class_selections  # not consumed


def test_select_class_get_unknown_token_401():
    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/api/clever/select-class?selection_token=ghost")
    assert resp.status_code == 401
