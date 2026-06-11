"""ClassLink roster identity + shared-function safety."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

from backend.routes.classlink_routes import _classlink_roster_external_id


def test_key_is_tenant_scoped():
    assert _classlink_roster_external_id("dist-A", "s1") == "classlink:dist-A:s1"


def test_key_percent_encodes_colon_in_components():
    # a ':' inside a component must not create a colliding key
    assert _classlink_roster_external_id("a:b", "c:d") == "classlink:a%3Ab:c%3Ad"


def test_key_tolerates_empty_components():
    assert _classlink_roster_external_id("", "") == "classlink::"


def _deactivate_sb(active_rows, captured_deactivations):
    """Fake Supabase for deactivate_missing_students."""
    sb = MagicMock()

    def _table(name):
        q = MagicMock()
        if name == "students":
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=list(active_rows))

            def _update(payload):
                upd = MagicMock()

                def _eq(col, val):
                    eqd = MagicMock()
                    eqd.execute.return_value = MagicMock(data=[])
                    captured_deactivations.append(val)
                    return eqd

                upd.eq.side_effect = _eq
                return upd

            q.update.side_effect = _update
        return q

    sb.table.side_effect = _table
    return sb


def test_clever_sync_does_not_deactivate_classlink_rows():
    from backend import roster_sync
    rows = [
        {"id": "row-cl", "student_id_number": "classlink:dist-A:s1"},  # protected
        {"id": "row-cv", "student_id_number": "cv-123"},               # clever, eligible
    ]
    captured = []
    with patch.object(roster_sync, "_get_supabase", return_value=_deactivate_sb(rows, captured)):
        roster_sync.deactivate_missing_students("t1", set(), provider="clever")
    assert "row-cl" not in captured       # classlink row NOT deactivated
    assert "row-cv" in captured           # clever row deactivated


def test_roster_sync_writes_tenant_scoped_keys():
    from backend.routes import classlink_routes
    raw = {
        "classes": [{"sourcedId": "c1", "title": "Math", "subjects": ["Math"], "grades": ["9"]}],
        "students": [{"sourcedId": "s1", "givenName": "A", "familyName": "B", "email": "a@b.edu"}],
        "enrollments": [{"role": "student", "class": {"sourcedId": "c1"}, "user": {"sourcedId": "s1"}}],
        "demographics": [],
    }
    fake_client = MagicMock()
    fake_client.fetch_roster = AsyncMock(return_value=raw)
    captured = {}

    def _capture_sync(classes, students, enrollments, teacher_id, provider="manual"):
        captured["students"] = students
        captured["enrollments"] = enrollments
        captured["provider"] = provider
        return {"classes": 1, "students": 1, "enrollments": 1}

    with patch("backend.oneroster.get_oneroster_config",
               return_value={"base_url": "https://sis/x", "client_id": "i", "client_secret": "s"}), \
         patch("backend.oneroster.OneRosterClient", return_value=fake_client), \
         patch("backend.roster_sync.sync_roster_to_db", side_effect=_capture_sync):
        classlink_routes._run_classlink_roster_sync("classlink:dist-A:teach1", "dist-A")

    assert captured["provider"] == "classlink"
    assert captured["students"][0]["external_id"] == "classlink:dist-A:s1"
    assert captured["enrollments"][0] == ("classlink:dist-A:c1", "classlink:dist-A:s1")


import pytest


@pytest.fixture
def app_client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
        pass
    with app.test_client() as c:
        yield c


def test_delete_data_calls_roster_delete_for_classlink_teacher(app_client, monkeypatch):
    # Updated for Task 6: gate now checks g.auth_source (set by middleware when
    # session['classlink_user'] is present) instead of a GUID prefix.  Dev-mode
    # (X-Test-Teacher-Id) never sets g.auth_source, so we use a real session in
    # production mode — matching the post-Task-4 world where user_id is a UUID.
    import os as _os
    uuid_teacher = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    with patch.dict(_os.environ, {"FLASK_ENV": "production"}), \
         patch("backend.roster_sync.delete_roster_data",
               return_value={"classes": 1, "students": 2, "enrollments": 1}) as mock_del, \
         patch("backend.storage.save") as mock_save:
        with app_client.session_transaction() as sess:
            sess["classlink_user"] = {
                "user_id": uuid_teacher,
                "classlink_id": "cl-teach1",
                "email": "teach1@dist-A.edu",
                "type": "teacher",
                "tenant_id": "dist-A",
            }
            sess["sso_login_ts"] = time.time()  # VB8 #18 absolute-cap anchor
        r = app_client.post(
            "/api/classlink/delete-data",
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["counts"]["students"] == 2
        mock_del.assert_called_once_with(uuid_teacher)
        mock_save.assert_called_once_with("oneroster_config", None, uuid_teacher)


def test_oneroster_sync_does_not_deactivate_classlink_rows():
    from backend import roster_sync
    rows = [
        {"id": "row-cl", "student_id_number": "classlink:dist-A:s1"},   # protected
        {"id": "row-or", "student_id_number": "oneroster:abc"},          # oneroster, eligible
    ]
    captured = []
    with patch.object(roster_sync, "_get_supabase", return_value=_deactivate_sb(rows, captured)):
        roster_sync.deactivate_missing_students("t1", set(), provider="oneroster")
    assert "row-cl" not in captured        # classlink row NOT deactivated by oneroster sync
    assert "row-or" in captured             # oneroster row IS deactivated


def test_delete_data_rejects_non_classlink_teacher(app_client, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    with patch("backend.roster_sync.delete_roster_data") as mock_del:
        r = app_client.post(
            "/api/classlink/delete-data",
            headers={"X-Test-Teacher-Id": "clever:abc", "Content-Type": "application/json"},
        )
        assert r.status_code == 403
        mock_del.assert_not_called()


def test_delete_data_rejects_real_clever_session(app_client):
    """A Clever SSO session (auth_source='clever') must 403 on the ClassLink
    delete-data gate.  Clever has its own /api/clever/delete-data; a Clever
    teacher must never be able to trigger the ClassLink deleter."""
    import os as _os
    with patch.dict(_os.environ, {"FLASK_ENV": "production"}), \
         patch("backend.auth.resolve_clever_user_id", return_value="clever-uuid-1"), \
         patch("backend.roster_sync.delete_roster_data") as mock_del:
        with app_client.session_transaction() as sess:
            sess["clever_user"] = {
                "clever_id": "cl-1",
                "email": "t@d.edu",
                "district": "dist-A",
            }
            sess["sso_login_ts"] = time.time()  # VB8 #18 absolute-cap anchor
        r = app_client.post("/api/classlink/delete-data", content_type="application/json")
        assert r.status_code == 403, r.get_json()
        mock_del.assert_not_called()


def test_delete_data_allows_uuid_classlink_teacher(app_client, monkeypatch):
    """Gate keys off g.auth_source='classlink', not a GUID prefix.

    After Task 4 the session stores a real Supabase UUID in user_id, so
    teacher_id.startswith("classlink:") would always return 403.  This test
    pins the new behaviour: a ClassLink session whose user_id is a pure UUID
    must receive 200, not 403.

    The middleware (check_auth in backend/auth.py) sets g.auth_source='classlink'
    when session['classlink_user'] is present and no Bearer token is provided.
    We must NOT be in FLASK_ENV=development (dev mode short-circuits to
    X-Test-Teacher-Id and never reads the session), so we patch to production.
    """
    import os as _os
    uuid_teacher = "11111111-1111-1111-1111-111111111111"
    with patch.dict(_os.environ, {"FLASK_ENV": "production"}), \
         patch("backend.roster_sync.delete_roster_data",
               return_value={"classes": 1, "students": 2}) as mock_del, \
         patch("backend.storage.save") as mock_save:
        with app_client.session_transaction() as sess:
            sess["classlink_user"] = {
                "user_id": uuid_teacher,
                "classlink_id": "cl-guid-abc",
                "email": "teacher@school.edu",
                "name": {"first": "T", "last": "Eacher"},
                "type": "teacher",
                "tenant_id": "dist-A",
            }
            sess["sso_login_ts"] = time.time()  # VB8 #18 absolute-cap anchor
        r = app_client.post(
            "/api/classlink/delete-data",
            content_type="application/json",
        )
        assert r.status_code == 200, r.get_json()
        data = r.get_json()
        assert data["counts"]["students"] == 2
        mock_del.assert_called_once_with(uuid_teacher)
        mock_save.assert_called_once_with("oneroster_config", None, uuid_teacher)
