"""ClassLink roster identity + shared-function safety."""
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
    except Exception:
        pass
    with app.test_client() as c:
        yield c


def test_delete_data_calls_roster_delete_for_classlink_teacher(app_client, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    with patch("backend.roster_sync.delete_roster_data",
               return_value={"classes": 1, "students": 2, "enrollments": 1}) as mock_del, \
         patch("backend.storage.save") as mock_save:
        r = app_client.post(
            "/api/classlink/delete-data",
            headers={"X-Test-Teacher-Id": "classlink:dist-A:teach1", "Content-Type": "application/json"},
        )
        assert r.status_code == 200
        assert r.get_json()["counts"]["students"] == 2
        mock_del.assert_called_once_with("classlink:dist-A:teach1")
        mock_save.assert_called_once_with("oneroster_config", None, "classlink:dist-A:teach1")


def test_delete_data_rejects_non_classlink_teacher(app_client, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    r = app_client.post(
        "/api/classlink/delete-data",
        headers={"X-Test-Teacher-Id": "clever:abc", "Content-Type": "application/json"},
    )
    assert r.status_code == 403
