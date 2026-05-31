import pytest
from flask import Flask


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "t"
    from backend.routes.district_routes import district_bp
    app.register_blueprint(district_bp)
    return app.test_client()


def _as_district_admin(client):
    with client.session_transaction() as s:
        s["district_admin"] = True


def _patch_store(monkeypatch):
    store = {}
    import backend.routes.district_routes as dr
    monkeypatch.setattr(dr, "storage_save", lambda k, d, s: store.__setitem__((k, s), d))
    monkeypatch.setattr(dr, "storage_load", lambda k, s: store.get((k, s)))
    monkeypatch.setattr(dr, "list_keys", lambda prefix, s: [k for (k, sc) in store if sc == s and k.startswith(prefix)])
    from backend import storage as _sm
    monkeypatch.setattr(_sm, "delete", lambda k, s: store.pop((k, s), None))
    return store


def test_add_school_designation(client, monkeypatch):
    store = _patch_store(monkeypatch)
    _as_district_admin(client)
    r = client.post("/api/district/sso-admins",
                    json={"email": "A@B.com", "tier": "school", "school": "Lincoln"})
    assert r.status_code == 200
    assert store[("sso_admin_designation:a@b.com", "system")]["tier"] == "school"
    assert store[("sso_admin_designation:a@b.com", "system")]["school"] == "Lincoln"


def test_add_requires_school_for_school_tier(client, monkeypatch):
    _patch_store(monkeypatch)
    _as_district_admin(client)
    r = client.post("/api/district/sso-admins", json={"email": "a@b.com", "tier": "school"})
    assert r.status_code == 400


def test_add_rejects_bad_tier(client, monkeypatch):
    _patch_store(monkeypatch)
    _as_district_admin(client)
    r = client.post("/api/district/sso-admins", json={"email": "a@b.com", "tier": "superuser"})
    assert r.status_code == 400


def test_list_and_delete(client, monkeypatch):
    store = _patch_store(monkeypatch)
    _as_district_admin(client)
    client.post("/api/district/sso-admins", json={"email": "a@b.com", "tier": "district"})
    r = client.get("/api/district/sso-admins")
    assert any(a["email"] == "a@b.com" and a["tier"] == "district" for a in r.get_json()["admins"])
    import backend.routes.district_routes as dr
    monkeypatch.setattr(dr, "_revoke_designated_admin_by_email", lambda email: None)
    r2 = client.delete("/api/district/sso-admins", json={"email": "a@b.com"})
    assert r2.status_code == 200
    assert ("sso_admin_designation:a@b.com", "system") not in store


def test_requires_district_admin(client, monkeypatch):
    _patch_store(monkeypatch)
    r = client.get("/api/district/sso-admins")
    assert r.status_code in (401, 403)
