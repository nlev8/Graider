import backend.routes.admin_routes as admin_routes
import backend.routes.sso_admin as sso_admin


def _patch_admin_storage(monkeypatch):
    store = {}
    monkeypatch.setattr(admin_routes, "storage_load",
                        lambda key, scope: store.get((key, scope)))
    monkeypatch.setattr(admin_routes, "storage_save",
                        lambda key, data, scope: store.__setitem__((key, scope), data))
    from backend import storage as _storage_mod
    monkeypatch.setattr(_storage_mod, "delete",
                        lambda key, scope: store.pop((key, scope), None))
    return store


def test_grant_writes_sso_designated(monkeypatch):
    store = _patch_admin_storage(monkeypatch)
    admin_routes._grant_sso_school_admin("uuid-1", "Lincoln High")
    rec = store[("admin_role:uuid-1", "system")]
    assert rec["school"] == "Lincoln High"
    assert rec["source"] == "sso_designated"
    assert rec.get("granted_at")


def test_grant_does_not_overwrite_invite_claim(monkeypatch):
    store = _patch_admin_storage(monkeypatch)
    store[("admin_role:uuid-1", "system")] = {"school": "Manual", "claimed_at": "x"}  # no source key
    admin_routes._grant_sso_school_admin("uuid-1", "SSO School")
    assert store[("admin_role:uuid-1", "system")]["school"] == "Manual"  # untouched


def test_grant_refreshes_existing_sso_grant(monkeypatch):
    store = _patch_admin_storage(monkeypatch)
    store[("admin_role:uuid-1", "system")] = {"school": "Old", "source": "sso_designated"}
    admin_routes._grant_sso_school_admin("uuid-1", "New")
    assert store[("admin_role:uuid-1", "system")]["school"] == "New"


def test_revoke_removes_sso_grant(monkeypatch):
    store = _patch_admin_storage(monkeypatch)
    store[("admin_role:uuid-1", "system")] = {"school": "X", "source": "sso_designated"}
    admin_routes._sync_sso_admin_revocation("uuid-1")
    assert ("admin_role:uuid-1", "system") not in store


def test_revoke_preserves_invite_claim(monkeypatch):
    store = _patch_admin_storage(monkeypatch)
    store[("admin_role:uuid-1", "system")] = {"school": "X", "claimed_at": "y"}  # no source
    admin_routes._sync_sso_admin_revocation("uuid-1")
    assert ("admin_role:uuid-1", "system") in store  # untouched


def _patch_helper(monkeypatch):
    calls = {"grant": [], "revoke": []}
    monkeypatch.setattr(sso_admin, "_grant_sso_school_admin",
                        lambda tid, school: calls["grant"].append((tid, school)))
    monkeypatch.setattr(sso_admin, "_sync_sso_admin_revocation",
                        lambda tid: calls["revoke"].append(tid))
    return calls


def test_apply_district_revokes_then_sets_flag(monkeypatch):
    calls = _patch_helper(monkeypatch)
    monkeypatch.setattr(sso_admin, "storage_load",
                        lambda key, scope: {"tier": "district"} if key == "sso_admin_designation:a@b.com" else None)
    sess = {}
    assert sso_admin.apply_sso_admin_designation("A@B.com", "uuid-1", sess) == "district"
    assert sess["district_admin"] is True
    assert calls["revoke"] == ["uuid-1"]      # stale school grant cleared first
    assert calls["grant"] == []


def test_apply_school_grants(monkeypatch):
    calls = _patch_helper(monkeypatch)
    monkeypatch.setattr(sso_admin, "storage_load",
                        lambda key, scope: {"tier": "school", "school": "Lincoln"})
    sess = {}
    assert sso_admin.apply_sso_admin_designation("a@b.com", "uuid-1", sess) == "school"
    assert calls["grant"] == [("uuid-1", "Lincoln")]
    assert sess.get("district_admin") is None


def test_apply_none_revokes(monkeypatch):
    calls = _patch_helper(monkeypatch)
    monkeypatch.setattr(sso_admin, "storage_load", lambda key, scope: None)
    sess = {}
    assert sso_admin.apply_sso_admin_designation("a@b.com", "uuid-1", sess) == "none"
    assert calls["revoke"] == ["uuid-1"]
    assert sess.get("district_admin") is None


def test_apply_missing_email_is_none(monkeypatch):
    calls = _patch_helper(monkeypatch)
    monkeypatch.setattr(sso_admin, "storage_load", lambda key, scope: None)
    assert sso_admin.apply_sso_admin_designation("", "uuid-1", {}) == "none"
