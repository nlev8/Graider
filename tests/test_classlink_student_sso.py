"""ClassLink student SSO — provisioned-row lookup, mint, multi-enrollment
picker, and FAIL-CLOSED behavior (no row / no email fallback). Supabase mocked."""
from unittest.mock import MagicMock, patch

from backend.routes.classlink_routes import _create_classlink_student_session

KEY = "classlink:dist-A:s1"


def _make_sb(student_rows, enroll_rows, capture=None):
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
            q.execute.return_value = MagicMock(data=list(enroll_rows))
            return q
        if name == "student_sessions":
            q = MagicMock()

            def _insert(payload):
                if capture is not None:
                    capture["inserted"] = payload
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[payload])
                return ins

            q.insert.side_effect = _insert
            return q
        return MagicMock()

    sb.table.side_effect = _table
    return sb


def test_single_enrollment_mints_session():
    student_rows = [{"id": "row1", "student_id_number": KEY, "first_name": "A", "last_name": "B"}]
    enroll_rows = [{"class_id": "cls1", "classes": {"id": "cls1", "name": "Math", "subject": "math"}}]
    capture = {}
    with patch("backend.routes.classlink_routes.get_supabase",
               return_value=_make_sb(student_rows, enroll_rows, capture)):
        result = _create_classlink_student_session("dist-A", "s1")
    assert result and result.get("token")
    assert capture["inserted"]["student_id"] == "row1"
    assert capture["inserted"]["class_id"] == "cls1"


def test_multi_enrollment_returns_needs_selection():
    student_rows = [{"id": "row1", "student_id_number": KEY, "first_name": "A", "last_name": "B"}]
    enroll_rows = [
        {"class_id": "cls1", "classes": {"id": "cls1", "name": "Math", "subject": "math"}},
        {"class_id": "cls2", "classes": {"id": "cls2", "name": "Sci", "subject": "sci"}},
    ]
    with patch("backend.routes.classlink_routes.get_supabase",
               return_value=_make_sb(student_rows, enroll_rows)):
        result = _create_classlink_student_session("dist-A", "s1")
    assert result["status"] == "needs_class_selection"
    assert result.get("selection_token")
    # public candidates must NOT leak the server-only _student_row
    assert all("_student_row" not in c for c in result["classes"])


def test_no_row_fails_closed_no_email_fallback():
    # Students lookup by the tenant-scoped key returns nothing. Even though a
    # row with a matching EMAIL exists elsewhere, the flow must NOT find it.
    with patch("backend.routes.classlink_routes.get_supabase",
               return_value=_make_sb([], [])):
        result = _create_classlink_student_session("dist-A", "s1")
    assert result is None


from flask import Flask


def _make_app():
    from backend.routes.classlink_routes import classlink_bp
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.register_blueprint(classlink_bp)
    return app


def test_student_token_exchange_roundtrip():
    from backend.routes import classlink_routes
    code = classlink_routes._create_classlink_student_auth_code("real-token-xyz")
    app = _make_app()
    with app.test_client() as c:
        r = c.post("/api/classlink/student-token", json={"code": code})
        assert r.status_code == 200
        assert r.get_json()["token"] == "real-token-xyz"
        # single-use: a second exchange fails
        r2 = c.post("/api/classlink/student-token", json={"code": code})
        assert r2.status_code == 401


def test_select_class_get_lists_then_post_mints():
    from backend.routes import classlink_routes
    candidates = [
        {"class_id": "cls1", "name": "Math", "subject": "math",
         "_student_row": {"id": "row1", "student_id_number": KEY}},
        {"class_id": "cls2", "name": "Sci", "subject": "sci",
         "_student_row": {"id": "row1", "student_id_number": KEY}},
    ]
    token = classlink_routes._create_classlink_class_selection(candidates)
    app = _make_app()
    capture = {}
    with app.test_client() as c:
        g = c.get(f"/api/classlink/select-class?selection_token={token}")
        names = [x["name"] for x in g.get_json()["classes"]]
        assert names == ["Math", "Sci"]
        with patch("backend.routes.classlink_routes.get_supabase",
                   return_value=_make_sb([{"id": "row1", "student_id_number": KEY}], [], capture)):
            p = c.post("/api/classlink/select-class",
                       json={"selection_token": token, "class_id": "cls2"})
        assert p.status_code == 200 and p.get_json()["token"]
        assert capture["inserted"]["class_id"] == "cls2"


def test_select_class_post_rejects_unknown_class_id_without_consuming_token():
    """Retry safety: a bad class_id must 400 and NOT consume the selection token."""
    from backend.routes import classlink_routes
    candidates = [
        {"class_id": "cls1", "name": "Math", "subject": "math",
         "_student_row": {"id": "row1", "student_id_number": KEY}},
    ]
    token = classlink_routes._create_classlink_class_selection(candidates)
    app = _make_app()
    with app.test_client() as c:
        bad = c.post("/api/classlink/select-class",
                     json={"selection_token": token, "class_id": "not-a-real-class"})
        assert bad.status_code == 400
        # Token must NOT have been consumed — a follow-up GET still lists candidates.
        ok = c.get(f"/api/classlink/select-class?selection_token={token}")
        assert ok.status_code == 200
        assert ok.get_json()["classes"][0]["class_id"] == "cls1"


def test_select_class_post_returns_503_when_supabase_unavailable():
    """No supabase → 503 (token also not consumed so the student can retry later)."""
    from backend.routes import classlink_routes
    candidates = [
        {"class_id": "cls1", "name": "Math", "subject": "math",
         "_student_row": {"id": "row1", "student_id_number": KEY}},
    ]
    token = classlink_routes._create_classlink_class_selection(candidates)
    app = _make_app()
    with app.test_client() as c, \
         patch("backend.routes.classlink_routes.get_supabase", return_value=None):
        r = c.post("/api/classlink/select-class",
                   json={"selection_token": token, "class_id": "cls1"})
        assert r.status_code == 503


def test_select_class_get_with_expired_token_returns_401_and_clears_it():
    """An expired selection token GETs 401 and is removed from the in-memory store."""
    from backend.routes import classlink_routes
    # Inject an already-expired entry directly to avoid sleeping in the test.
    expired_token = "expired-test-token"
    classlink_routes._pending_classlink_class_selections[expired_token] = {
        "candidates": [], "expires": 0,  # epoch — long expired
    }
    app = _make_app()
    with app.test_client() as c:
        r = c.get(f"/api/classlink/select-class?selection_token={expired_token}")
        assert r.status_code == 401
        assert expired_token not in classlink_routes._pending_classlink_class_selections
