import pytest
from flask import Flask

import backend.routes.district_routes as dr


@pytest.fixture
def client():
    app = Flask(__name__); app.config["TESTING"] = True; app.config["SECRET_KEY"] = "t"
    from backend.routes.district_routes import district_bp
    app.register_blueprint(district_bp)
    return app.test_client()


def _as_district_admin(client):
    with client.session_transaction() as s:
        s["district_admin"] = True


@pytest.fixture(autouse=True)
def _clear_analytics_cache():
    dr._district_analytics_cache_clear()
    yield


def test_analytics_requires_district_admin(client):
    assert client.get("/api/district/analytics").status_code in (401, 403)


def test_analytics_returns_rollup(client, monkeypatch):
    monkeypatch.setattr(dr, "_get_supabase", lambda: object())
    monkeypatch.setattr(dr, "_district_teacher_ids", lambda sb: {"uuid-1", "clever:abc"})
    import backend.routes.admin_routes as ar
    monkeypatch.setattr(ar, "compute_overview",
                        lambda ids: {"total_students": 5, "total_assessments": 3, "average_score": 88.0,
                                     "grade_distribution": {"A": 2, "B": 1, "C": 0, "D": 0, "F": 0},
                                     "scored_count": 3, "hit_hard_cap": True})
    monkeypatch.setattr(dr, "_district_teacher_rows", lambda ids, sb: [{"user_id": "uuid-1", "name": "T", "email": "t@x"}])
    _as_district_admin(client)
    body = client.get("/api/district/analytics").get_json()
    assert body["overview"]["total_teachers"] == 2
    assert body["overview"]["average_score"] == 88.0
    assert body["approximate"] is True
    assert set(body["overview"].keys()) == {"total_teachers", "total_students", "total_assessments",
                                            "average_score", "grade_distribution"}
    assert body["teachers"][0]["name"] == "T"


def test_analytics_cache_serves_within_ttl(client, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(dr, "_get_supabase", lambda: object())
    def _count_ids(sb): calls["n"] += 1; return set()
    monkeypatch.setattr(dr, "_district_teacher_ids", _count_ids)
    _as_district_admin(client)
    client.get("/api/district/analytics")
    client.get("/api/district/analytics")
    assert calls["n"] == 1


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._served = False

    def select(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def execute(self):
        rows = [] if self._served else self._rows
        self._served = True
        return type("R", (), {"data": rows})()


class _FakeSB:
    def __init__(self, by_table):
        self._by_table = by_table

    def table(self, name):
        return _FakeQuery(self._by_table.get(name, []))


def test_district_teacher_ids_unions_and_includes_clever(monkeypatch):
    sb = _FakeSB({
        "classes": [{"teacher_id": "uuid-1"}, {"teacher_id": "uuid-1"}],
        "published_content": [{"teacher_id": "uuid-2"}],
        "published_assessments": [{"teacher_id": "clever:abc"}, {"teacher_id": "uuid-1"}],
    })
    ids = dr._district_teacher_ids(sb)
    assert ids == {"uuid-1", "uuid-2", "clever:abc"}


def test_district_teacher_ids_empty(monkeypatch):
    assert dr._district_teacher_ids(_FakeSB({})) == set()


def test_district_teacher_ids_no_sb():
    assert dr._district_teacher_ids(None) == set()
