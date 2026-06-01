# Graider-Managed SSO Admin Designation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a password-authed district admin designate ClassLink SSO users as district or school admins by email; on SSO login Graider email-matches the designation list and routes the user to `/district` or the in-app Admin tab — with no dependency on ClassLink role data.

**Architecture:** A district-managed `sso_admin_designation:{email}` list (system storage). A provider-agnostic `apply_sso_admin_designation(email, uuid, session)` helper runs after the ClassLink callback resolves the Supabase UUID: district → revoke stale grant + set `session["district_admin"]` + redirect `/district`; school → upsert a `source="sso_designated"` `admin_role`; none → revoke any stale SSO grant. Grants are source-tagged so SSO never clobbers an invite-claimed admin.

**Tech Stack:** Python/Flask, Supabase, pytest, React/Vite, vitest.

**Spec:** `docs/superpowers/specs/2026-05-31-classlink-admin-designation-design.md` (v2)
**Class:** B (auth/identity/privilege) ⇒ opus code-quality review per task.
**Branch:** `feature/classlink-admin-designation` (fresh off `main`; the role-claim branch is abandoned).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/routes/admin_routes.py` | source-tagged grant/revoke of `admin_role` | + `_grant_sso_school_admin`, `_sync_sso_admin_revocation` |
| `backend/routes/sso_admin.py` | runtime designation match (provider-agnostic) | Create |
| `backend/routes/district_routes.py` | district-managed designation CRUD + immediate revoke | + 3 endpoints, `_revoke_designated_admin_by_email` |
| `backend/routes/classlink_routes.py` | callback wiring; probe revert | call helper + tier branch; − #605 probe |
| `frontend/src/components/DistrictSetup.jsx` | "SSO Admin Access" console section | + section |
| `frontend/src/services/api.js` | endpoint wrappers | + 3 wrappers |
| tests | unit + integration + vitest | Create/modify |

Order: grant/revoke helpers → match helper → endpoints → callback → frontend → probe revert. Each task is independently committable.

---

### Task 1: Source-tagged grant/revoke helpers (`admin_routes.py`)

**Files:**
- Modify: `backend/routes/admin_routes.py` (two module-level helpers after `admin_claim`)
- Test: `tests/test_sso_admin_designation.py` (Create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sso_admin_designation.py`:

```python
import backend.routes.admin_routes as admin_routes


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && pytest tests/test_sso_admin_designation.py -v`
Expected: FAIL — `AttributeError: ... has no attribute '_grant_sso_school_admin'`.

- [ ] **Step 3: Implement the helpers**

In `backend/routes/admin_routes.py`, add after `admin_claim` (module-level; `datetime`/`timezone` already imported):

```python
def _grant_sso_school_admin(teacher_id, school):
    """Idempotently grant SSO-designated school-admin status for `teacher_id`.

    Upserts admin_role:{teacher_id} with source='sso_designated' and the school
    from the designation. NEVER overwrites a district-issued (invite-claimed)
    grant, which has no 'source' key.
    """
    existing = storage_load(f"admin_role:{teacher_id}", "system")
    if (existing and isinstance(existing, dict)
            and existing.get("source") != "sso_designated"):
        return  # invite-claimed grant — leave authoritative record untouched
    storage_save(
        f"admin_role:{teacher_id}",
        {
            "school": school or "",
            "source": "sso_designated",
            "granted_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        "system",
    )


def _sync_sso_admin_revocation(teacher_id):
    """Revoke a stale SSO-designated school-admin grant. Invite-claimed grants
    are never auto-revoked.
    """
    existing = storage_load(f"admin_role:{teacher_id}", "system")
    if (existing and isinstance(existing, dict)
            and existing.get("source") == "sso_designated"):
        from backend.storage import delete as storage_delete  # call-time: resolves the test monkeypatch
        storage_delete(f"admin_role:{teacher_id}", "system")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sso_admin_designation.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/admin_routes.py tests/test_sso_admin_designation.py
git commit -m "feat(sso-admin): source-tagged grant/revoke helpers (sso_designated) [Class B]"
```

---

### Task 2: Runtime match helper (`sso_admin.py`)

**Files:**
- Create: `backend/routes/sso_admin.py`
- Test: `tests/test_sso_admin_designation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sso_admin_designation.py`:

```python
import backend.routes.sso_admin as sso_admin


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sso_admin_designation.py -k apply -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routes.sso_admin'`.

- [ ] **Step 3: Implement**

Create `backend/routes/sso_admin.py`:

```python
"""Provider-agnostic SSO admin designation match.

Run after an SSO callback has resolved a Supabase UUID. Routes the user by the
district-managed `sso_admin_designation:{email}` list — independent of any IdP
role claim. Currently wired into the ClassLink callback only (Clever is a
one-line add later).
"""

import logging

from backend.storage import load as storage_load
from backend.routes.admin_routes import _grant_sso_school_admin, _sync_sso_admin_revocation

logger = logging.getLogger(__name__)


def _normalize_email(email):
    return str(email or "").strip().lower()


def apply_sso_admin_designation(email, teacher_id, session):
    """Apply the district-managed admin designation for a resolved SSO login.

    Returns the applied tier: 'district' | 'school' | 'none'. Side effects:
      - district → revoke any stale SSO-designated school grant, then set
        session['district_admin'] = True
      - school   → upsert a source='sso_designated' admin_role (school from the designation)
      - none     → revoke any stale source='sso_designated' grant (self-heal)
    Never grants without a designation match.
    """
    norm = _normalize_email(email)
    rec = storage_load(f"sso_admin_designation:{norm}", "system") if norm else None

    if isinstance(rec, dict) and rec.get("tier") == "district":
        # Promotion school→district must not strand the old school grant.
        _sync_sso_admin_revocation(teacher_id)
        session["district_admin"] = True
        return "district"

    if isinstance(rec, dict) and rec.get("tier") == "school":
        _grant_sso_school_admin(teacher_id, rec.get("school", ""))
        return "school"

    _sync_sso_admin_revocation(teacher_id)
    return "none"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sso_admin_designation.py -v`
Expected: PASS (9 passed). Then confirm no circular import: `python -c "import backend.app" && echo OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/sso_admin.py tests/test_sso_admin_designation.py
git commit -m "feat(sso-admin): apply_sso_admin_designation match helper [Class B]"
```

---

### Task 3: Designation endpoints + immediate revoke (`district_routes.py`)

**Files:**
- Modify: `backend/routes/district_routes.py` (3 endpoints + helper)
- Test: `tests/test_district_sso_admins.py` (Create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_district_sso_admins.py`. Inspect an existing `district_routes` test (e.g. how a test client authenticates as district admin via `session["district_admin"]=True` in `session_transaction`); reuse that mechanism. Skeleton:

```python
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
    # delete (no Supabase configured in test → immediate-revoke is a no-op, must not error)
    import backend.routes.district_routes as dr
    monkeypatch.setattr(dr, "_revoke_designated_admin_by_email", lambda email: None)
    r2 = client.delete("/api/district/sso-admins", json={"email": "a@b.com"})
    assert r2.status_code == 200
    assert ("sso_admin_designation:a@b.com", "system") not in store


def test_requires_district_admin(client, monkeypatch):
    _patch_store(monkeypatch)
    # no _as_district_admin → not authed
    r = client.get("/api/district/sso-admins")
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_district_sso_admins.py -v`
Expected: FAIL — 404 (endpoints not registered).

- [ ] **Step 3: Implement**

In `backend/routes/district_routes.py`, add the helper + three endpoints (place near the existing `admin-invite`/`admins` endpoints; `_require_district_admin`, `storage_save/load/list_keys`, `datetime/timezone`, `audit_log`, `handle_route_errors`, `logger`, `sentry_sdk` are all already in this module). Add `logger = logging.getLogger(__name__)` if not present near the top (it imports `logging`):

```python
_VALID_SSO_TIERS = ("district", "school")


def _revoke_designated_admin_by_email(email):
    """Best-effort immediate revoke: if the email is linked to a Supabase user,
    drop their SSO-designated admin grant now (not just on next login)."""
    try:
        from backend.supabase_client import get_supabase
        from backend.utils.supabase_users import list_all_users
        from backend.routes.admin_routes import _sync_sso_admin_revocation
        sb = get_supabase()
        if not sb:
            return
        norm = str(email or "").strip().lower()
        matches = [u for u in list_all_users(sb)
                   if getattr(u, "email", None) and u.email.lower() == norm]
        if len(matches) == 1:
            _sync_sso_admin_revocation(matches[0].id)
    except Exception as e:
        logger.warning("Immediate SSO admin revoke failed (non-fatal): %s", type(e).__name__)


@district_bp.route("/api/district/sso-admins", methods=["GET"])
@_require_district_admin
@handle_route_errors
def district_list_sso_admins():
    """List SSO admin designations (email → tier/school)."""
    keys = list_keys("sso_admin_designation:", "system") or []
    admins = []
    for key in keys:
        rec = storage_load(key, "system")
        if rec and isinstance(rec, dict):
            admins.append({
                "email": key[len("sso_admin_designation:"):],
                "tier": rec.get("tier", ""),
                "school": rec.get("school", ""),
                "created_at": rec.get("created_at", ""),
            })
    return jsonify({"admins": admins})


@district_bp.route("/api/district/sso-admins", methods=["POST"])
@_require_district_admin
@handle_route_errors
def district_add_sso_admin():
    """Designate an email as a district or school SSO admin."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    tier = str(data.get("tier", "")).strip().lower()
    school = str(data.get("school", "")).strip()
    if not email:
        return jsonify({"error": "email is required"}), 400
    if tier not in _VALID_SSO_TIERS:
        return jsonify({"error": "tier must be 'district' or 'school'"}), 400
    if tier == "school" and not school:
        return jsonify({"error": "school is required for a school admin"}), 400
    storage_save(
        f"sso_admin_designation:{email}",
        {
            "tier": tier,
            "school": school if tier == "school" else "",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "created_by": "district_admin",
        },
        "system",
    )
    audit_log("DISTRICT_SSO_ADMIN_DESIGNATED", f"tier={tier} school={school or '-'}",
              user="district_admin", teacher_id="system")
    return jsonify({"status": "saved", "email": email, "tier": tier})


@district_bp.route("/api/district/sso-admins", methods=["DELETE"])
@_require_district_admin
@handle_route_errors
def district_delete_sso_admin():
    """Remove an SSO admin designation + best-effort immediate revoke."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400
    from backend.storage import delete as storage_delete
    storage_delete(f"sso_admin_designation:{email}", "system")
    _revoke_designated_admin_by_email(email)
    audit_log("DISTRICT_SSO_ADMIN_REMOVED", "designation removed",
              user="district_admin", teacher_id="system")
    return jsonify({"status": "removed", "email": email})
```

If `logger` is not already defined in the module, add `logger = logging.getLogger(__name__)` after the imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_district_sso_admins.py -v` (expect 5 passed). Then `pytest tests/ -k district -q` (existing district tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/district_routes.py tests/test_district_sso_admins.py
git commit -m "feat(sso-admin): district endpoints to manage SSO admin designations + immediate revoke [Class B]"
```

---

### Task 4: ClassLink callback wiring

**Files:**
- Modify: `backend/routes/classlink_routes.py` (teacher/admin block tail)
- Test: `tests/test_classlink_sso.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_classlink_sso.py` (the module autouse fixture patches `resolve_classlink_user_id` to a fixed UUID). Model the request on `test_successful_teacher_login` (~lines 216-265):

```python
def _drive_designation_callback(designation_tier):
    """Drive a ClassLink callback; patch apply_sso_admin_designation to return the tier."""
    app = _make_app()
    priv, pub = _make_rsa_keypair()
    id_token = make_id_token(priv, aud="test-client-id", sub="cl-1",
                             email="a@school.edu", given_name="A", family_name="B", role="teacher")
    tok = MagicMock(status_code=200); tok.json.return_value = {"access_token": "t", "id_token": id_token}
    usr = MagicMock(status_code=200)
    usr.json.return_value = {"UserId": "cl-1", "SourcedId": "cl-1", "FirstName": "A",
                             "LastName": "B", "Email": "a@school.edu", "Role": "teacher", "TenantId": "d-456"}

    def _fake_apply(email, uuid, session):
        if designation_tier == "district":
            session["district_admin"] = True
        return designation_tier

    with app.test_client() as client:
        with client.session_transaction() as s:
            s['classlink_oauth_state'] = 'valid-state'
        with patch('backend.routes.classlink_routes.requests.post', return_value=tok), \
             patch('backend.routes.classlink_routes.requests.get', return_value=usr), \
             patch('backend.routes.classlink_routes.get_classlink_oidc_config', return_value=_mock_oidc_config()), \
             patch('backend.routes.classlink_routes.get_classlink_jwks_client', return_value=_mock_jwks_client(pub)), \
             patch('backend.routes.classlink_routes._trigger_roster_sync'), \
             patch('backend.routes.classlink_routes.apply_sso_admin_designation', side_effect=_fake_apply):
            resp = client.get('/api/classlink/callback?code=c&state=valid-state')
        with client.session_transaction() as s:
            return resp, dict(s)


def test_designated_district_redirects_to_district():
    resp, sess = _drive_designation_callback("district")
    assert resp.status_code in (301, 302)
    assert resp.location.endswith("/district")
    assert sess.get("district_admin") is True


def test_designated_school_lands_in_app():
    resp, sess = _drive_designation_callback("school")
    assert "classlink_login=success" in resp.location
    assert sess.get("district_admin") is None


def test_non_designated_lands_in_app():
    resp, sess = _drive_designation_callback("none")
    assert "classlink_login=success" in resp.location
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_classlink_sso.py -k "designated or non_designated" -v`
Expected: FAIL — district lands at `classlink_login=success` (no `/district` redirect; `apply_sso_admin_designation` not imported/called).

- [ ] **Step 3: Implement**

In `backend/routes/classlink_routes.py`, add the top-level import (with other `backend.routes` imports):

```python
from backend.routes.sso_admin import apply_sso_admin_designation
```

Replace the teacher/admin block tail — currently:
```python
    # Background roster sync (if OneRoster configured) — keyed by the UUID.
    _trigger_roster_sync(graider_uuid, tenant_id)

    audit_log("CLASSLINK_LOGIN", f"ClassLink SSO login: {redact_email(email)}",
              user="teacher", teacher_id=graider_uuid)

    return redirect("/?classlink_login=success")
```
with:
```python
    applied = apply_sso_admin_designation(email, graider_uuid, session)

    if applied == "district":
        audit_log("CLASSLINK_DISTRICT_ADMIN_LOGIN",
                  f"ClassLink district admin SSO login: {redact_email(email)}",
                  user="district_admin", teacher_id=graider_uuid)
        return redirect("/district")

    # Background roster sync (if OneRoster configured) — keyed by the UUID.
    _trigger_roster_sync(graider_uuid, tenant_id)

    audit_log(
        "CLASSLINK_SCHOOL_ADMIN_LOGIN" if applied == "school" else "CLASSLINK_LOGIN",
        (f"ClassLink school admin SSO login: {redact_email(email)}" if applied == "school"
         else f"ClassLink SSO login: {redact_email(email)}"),
        user=("admin" if applied == "school" else "teacher"), teacher_id=graider_uuid)

    return redirect("/?classlink_login=success")
```

(`session`, `redirect`, `audit_log`, `redact_email`, `_trigger_roster_sync`, `email`, `graider_uuid`, `tenant_id` are already in scope. The `account_conflict` guard above this is unchanged, so no grant without a resolved UUID.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_sso.py -k "designated or non_designated" -v`. Then the whole file `pytest tests/test_classlink_sso.py -q`. Then SIS pins `pytest tests/test_sis_alerting.py -v` — if a `(file,line)` capture pin shifted, re-point it to the same `_bg_sync` capture with a dated comment. Then `python -c "import backend.app" && echo OK` (no circular import).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_sso.py
git commit -m "feat(sso-admin): wire ClassLink callback to designation match [Class B]"
```

---

### Task 5: District console UI + api wrappers

**Files:**
- Modify: `frontend/src/services/api.js` (3 wrappers)
- Modify: `frontend/src/components/DistrictSetup.jsx` ("SSO Admin Access" section in the post-auth `ConfigForm`)
- Test: `frontend/src/__tests__/DistrictSsoAdmins.test.jsx` (Create)

- [ ] **Step 1: Write the failing test**

READ `frontend/src/components/DistrictSetup.jsx` (the `ConfigForm` sub-component and its sections) and an existing frontend test to match conventions. Create `frontend/src/__tests__/DistrictSsoAdmins.test.jsx` that mocks `../services/api` and asserts the section renders the list and calls `addSsoAdmin` on submit. Minimum:

```jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../services/api', () => ({
  __esModule: true,
  listSsoAdmins: vi.fn(async () => ({ admins: [{ email: 'a@b.com', tier: 'school', school: 'Lincoln' }] })),
  addSsoAdmin: vi.fn(async () => ({ status: 'saved' })),
  removeSsoAdmin: vi.fn(async () => ({ status: 'removed' })),
  // include any other api exports DistrictSetup imports so the mock is complete
}))

import * as api from '../services/api'
import { SsoAdminSection } from '../components/DistrictSetup'  // export the section for testability

describe('SsoAdminSection', () => {
  beforeEach(() => vi.clearAllMocks())
  it('lists existing designations', async () => {
    render(<SsoAdminSection isDark={true} />)
    await waitFor(() => expect(screen.getByText(/a@b.com/)).toBeInTheDocument())
  })
  it('adds a designation', async () => {
    render(<SsoAdminSection isDark={true} />)
    fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: 'x@y.com' } })
    fireEvent.click(screen.getByText(/add/i))
    await waitFor(() => expect(api.addSsoAdmin).toHaveBeenCalled())
  })
})
```

Adapt prop/placeholder names to your implementation. If extracting a testable `SsoAdminSection` export is impractical, instead unit-test the three api.js wrappers (mock `fetchApi`) and render-test the section inline — but a focused exported section is cleaner.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/DistrictSsoAdmins.test.jsx`
Expected: FAIL — `SsoAdminSection`/api wrappers don't exist.

- [ ] **Step 3: Implement**

In `frontend/src/services/api.js`, add three wrappers (match the file's existing `fetchApi` style and export list):
```js
export async function listSsoAdmins() {
  return fetchApi('/api/district/sso-admins')
}
export async function addSsoAdmin(email, tier, school) {
  return fetchApi('/api/district/sso-admins', { method: 'POST', body: JSON.stringify({ email, tier, school }) })
}
export async function removeSsoAdmin(email) {
  return fetchApi('/api/district/sso-admins', { method: 'DELETE', body: JSON.stringify({ email }) })
}
```
(and add `listSsoAdmins, addSsoAdmin, removeSsoAdmin` to the file's default-export object if it has one).

In `frontend/src/components/DistrictSetup.jsx`, add an `SsoAdminSection` component (exported) and render it inside the authenticated `ConfigForm`. It: loads the list on mount (`listSsoAdmins`), shows an email input + tier `<select>` (District Admin / School Admin) + school input (shown when tier=school) + Add button (`addSsoAdmin`), lists entries with a Remove button (`removeSsoAdmin`), and refreshes after add/remove. Follow the file's `React.createElement` + style-object conventions (it does not use JSX). Keep it consistent with the existing config sections' look.

- [ ] **Step 4: Run tests + build**

Run: `cd frontend && npx vitest run src/__tests__/DistrictSsoAdmins.test.jsx` (expect pass), then `npx vitest run` (full frontend suite, no regression), then `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.js frontend/src/components/DistrictSetup.jsx frontend/src/__tests__/DistrictSsoAdmins.test.jsx
git commit -m "feat(sso-admin): district console SSO Admin Access section [Class B]"
```

---

### Task 6: Revert the #605 role probe

**Files:**
- Modify: `backend/routes/classlink_routes.py` (remove the `DEBUG_CLASSLINK_ROLE_PROBE` block)
- Modify: `tests/test_classlink_sso.py` (remove `test_role_probe_captures_raw_role_verbatim`)

- [ ] **Step 1: Remove the probe block**

In `backend/routes/classlink_routes.py`, delete the temporary probe block: the comment `# DEBUG (REVERT BEFORE NEXT FEATURE): capture the raw ClassLink Role claim …` through the `sentry_sdk.capture_message(_role_probe, level="info")` line (it sits between the `guid = _classlink_guid(...)` guard and the `# Student login →` comment). Leave the surrounding code clean.

- [ ] **Step 2: Remove the probe test**

In `tests/test_classlink_sso.py`, delete the `test_role_probe_captures_raw_role_verbatim` function entirely.

- [ ] **Step 3: Verify nothing references it**

Run: `grep -rn "DEBUG_CLASSLINK_ROLE_PROBE\|_role_probe\|role_probe_captures" backend/ tests/`
Expected: no matches. Confirm `sentry_sdk`/`hashlib` are still used elsewhere in the file (they are — `capture_exception` + `sha256`), so no dead imports.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_classlink_sso.py -q && pytest tests/test_sis_alerting.py -q && ruff check backend/routes/classlink_routes.py`
Expected: green; ruff clean. (Deleting lines shifts the `_bg_sync` capture UP — confirm the SIS pin still resolves; re-point with a comment if it moved out of window.)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_sso.py
git commit -m "revert: remove DEBUG_CLASSLINK_ROLE_PROBE (captured; superseded by designation routing) [Class A]"
```

---

## Per-Branch Verification (before PR)

- [ ] Full backend suite: `source venv/bin/activate && pytest -q --ignore=tests/load` — green (any failure proven pre-existing via `git checkout main -- <file>`).
- [ ] Cross-cutting grep: `for f in backend/routes/admin_routes.py backend/routes/district_routes.py backend/routes/classlink_routes.py backend/routes/sso_admin.py; do grep -rln "$f" tests/; done` — run every surfaced test.
- [ ] Line-shift pin scan: `grep -rn '"backend/routes/classlink_routes.py"' tests/` — `test_sis_alerting` pins resolve after the callback edit + probe revert.
- [ ] **Clever non-regression (compliance gate):** `pytest tests/test_clever_compliance.py tests/test_clever_callback.py -q` — green (Clever is untouched; this proves it).
- [ ] `ruff check backend/routes/admin_routes.py backend/routes/district_routes.py backend/routes/classlink_routes.py backend/routes/sso_admin.py`; `bandit -q -r` the same.
- [ ] `cd frontend && npx vitest run && npm run build`.
- [ ] No circular import: `python -c "import backend.app" && echo OK`.
- [ ] Spec reviewer ✅ then **opus** code-quality reviewer ✅ (Class B).
- [ ] GitNexus reindex: `npx gitnexus analyze --embeddings`.
- [ ] PR body: Class B; spec + plan refs; single-district invariant; deferred follow-ups (Clever hook one-liner; `/api/district/admins` `source` enrichment).

## Manual / Operator Verification (per-branch DoD, Hard Rule #8)

After deploy: in `/district` (password), designate your test email as **District Admin**; log in via the cltest LaunchPad tile as that account → lands on the `/district` console (no password prompt). Re-designate as **School Admin** + a school → next tile login lands in the app with the **Admin tab** visible. Remove the designation → next login lands as a plain teacher (admin gone). Confirm a normal (non-designated) ClassLink teacher login is unchanged and no `uuid`/`NoneType` Sentry errors.
