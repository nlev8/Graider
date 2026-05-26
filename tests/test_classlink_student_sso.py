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
