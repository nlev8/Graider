# ClassLink Teacher UUID Identity Resolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every ClassLink SSO teacher to a real Supabase Auth UUID at login (link-or-create) so `g.user_id`/`g.teacher_id` is always a valid UUID, and harden the post-login roster sync against a missing config.

**Architecture:** A new `resolve_classlink_user_id` in `backend/auth.py` (mirroring Clever's link pattern, plus create-if-missing) is called from the ClassLink teacher callback; the resolved UUID is stored as `session['classlink_user']['user_id']`, which `auth.py:check_auth` already copies into `g.user_id`/`g.teacher_id`. Three downstream consumers are corrected for the GUID→UUID switch (frontend Bearer suppression, approval-status, delete-data), plus a `None`-config guard on roster sync.

**Tech Stack:** Python/Flask, Supabase (`supabase-py` admin API), pytest, React/Vite, vitest.

**Spec:** `docs/superpowers/specs/2026-05-30-classlink-teacher-uuid-identity-design.md` (v2)
**Class:** B (auth/identity) ⇒ opus code-quality review required before merge.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/auth.py` | identity resolution | + `load_classlink_links`, `save_classlink_link`, `resolve_classlink_user_id`, `import secrets`, `from backend.utils.supabase_users import list_all_users` |
| `backend/storage.py` | key→filepath for file backend | + `classlink_link:` prefix branch |
| `backend/routes/classlink_routes.py` | OAuth callback + roster sync + delete | teacher-branch wiring, Bug A guard, delete-data gate |
| `backend/routes/auth_routes.py` | approval status | SSO short-circuit |
| `frontend/src/services/api.js` | auth headers | key off `auth_source`, not `id` prefix |
| `frontend/src/App.jsx` | SSO session handlers | set `auth_source`, add `account_conflict` message |
| `tests/test_classlink_identity.py` | resolver unit tests | Create |
| `tests/test_classlink_sso.py` | callback + delete-data | Modify |
| `tests/test_auth_approval.py` | approval-status SSO | Create or extend existing auth test |

Tasks are ordered so each is independently committable. Task 1 (Bug A) ships value alone; Tasks 2–4 build the resolver + wiring; Tasks 5–7 fix the GUID→UUID consumers.

---

### Task 1: Bug A — guard `_run_classlink_roster_sync` against `None`/partial config

**Files:**
- Modify: `backend/routes/classlink_routes.py:258-261`
- Test: `tests/test_classlink_sso.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_classlink_sso.py`:

```python
def test_roster_sync_skips_when_no_oneroster_config(monkeypatch):
    """Bug A: get_oneroster_config returning None must not crash the sync."""
    import backend.routes.classlink_routes as clr
    # _run_classlink_roster_sync imports these locally at call time, so patching
    # the SOURCE module reaches the function without hoisting any imports.
    monkeypatch.setattr("backend.oneroster.get_oneroster_config", lambda tid: None)
    # Must return cleanly (no AttributeError), and never construct a client.
    clr._run_classlink_roster_sync("11111111-1111-1111-1111-111111111111", "2284")


def test_roster_sync_skips_when_partial_config(monkeypatch):
    """Bug A: a district config missing client_id/secret must be skipped."""
    import backend.routes.classlink_routes as clr
    monkeypatch.setattr("backend.oneroster.get_oneroster_config",
                        lambda tid: {"base_url": "https://x", "client_id": "", "client_secret": ""})
    def _boom(*a, **k):
        raise AssertionError("OneRosterClient should not be constructed")
    monkeypatch.setattr("backend.oneroster.OneRosterClient", _boom)
    clr._run_classlink_roster_sync("11111111-1111-1111-1111-111111111111", "2284")
```

Note: patching at the source module (`backend.oneroster`) works because the function does its `from backend.oneroster import ...` at call time — **no import hoisting needed**, so no lines shift and no `(file,line)` pins move.

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && pytest tests/test_classlink_sso.py::test_roster_sync_skips_when_no_oneroster_config -v`
Expected: FAIL — `AttributeError: 'NoneType' object has no attribute 'get'` (or AttributeError on patched name if not yet hoisted).

- [ ] **Step 3: Implement the guard**

In `backend/routes/classlink_routes.py`, change **only** the guard line inside
`_run_classlink_roster_sync` (leave the local `from backend.oneroster import ...` exactly
as-is — no hoisting, so no lines shift):

```python
    config = get_oneroster_config(teacher_id)
    if not config or not config.get('base_url') or not config.get('client_id') or not config.get('client_secret'):
        logger.info("No usable OneRoster config for %s, skipping post-login roster sync", teacher_id)
        return
```

This replaces the single line `if not config.get('base_url'):` — a one-line edit.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_sso.py::test_roster_sync_skips_when_no_oneroster_config tests/test_classlink_sso.py::test_roster_sync_skips_when_partial_config -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_sso.py
git commit -m "fix(classlink): guard post-login roster sync against None/partial OneRoster config (Bug A) [Class B]"
```

---

### Task 2: Link storage — `load_classlink_links` / `save_classlink_link` + storage prefix

**Files:**
- Modify: `backend/auth.py` (add helpers near the Clever pair at line ~19-56)
- Modify: `backend/storage.py:143-146` (add `classlink_link:` branch)
- Test: `tests/test_classlink_identity.py` (Create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_classlink_identity.py`:

```python
import backend.auth as auth


def test_save_and_load_classlink_link(monkeypatch):
    store = {}
    monkeypatch.setattr("backend.storage.save",
                        lambda key, data, scope: store.__setitem__((key, scope), data))
    monkeypatch.setattr("backend.storage.list_keys",
                        lambda prefix, scope: [k for (k, s) in store if k.startswith(prefix)])
    monkeypatch.setattr("backend.storage.load",
                        lambda key, scope: store.get((key, scope)))

    auth.save_classlink_link("classlink:2284:abc", "uuid-1")
    links = auth.load_classlink_links()
    assert links.get("classlink:2284:abc") == "uuid-1"


def test_storage_maps_classlink_link_prefix(tmp_path, monkeypatch):
    """File backend must route classlink_link: keys to a real path."""
    from backend.storage import _key_to_filepath
    path = _key_to_filepath("classlink_link:classlink:2284:abc", teacher_id="some-teacher")
    assert path is not None
    assert "classlink_links" in path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classlink_identity.py -v`
Expected: FAIL — `AttributeError: module 'backend.auth' has no attribute 'save_classlink_link'` and `_key_to_filepath` returns `None`.

- [ ] **Step 3: Implement helpers + storage branch**

In `backend/auth.py`, add `import secrets` to the imports, and add after `resolve_clever_user_id` (line ~62):

```python
def load_classlink_links():
    """Load all classlink_guid → supabase_user_id mappings."""
    try:
        from backend.storage import list_keys, load
        keys = list_keys('classlink_link:', 'system')
        links = {}
        for key in keys:
            data = load(key, 'system')
            if data and isinstance(data, dict):
                guid = key[len('classlink_link:'):]
                links[guid] = data.get('supabase_user_id', '')
        return links
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return {}


def save_classlink_link(guid, supabase_user_id):
    """Persist a classlink_guid → supabase_user_id link."""
    try:
        from backend.storage import save
        save(f'classlink_link:{guid}', {'supabase_user_id': supabase_user_id}, 'system')
    except Exception as e:
        sentry_sdk.capture_exception(e)
    logger.info("Linked ClassLink GUID to Supabase user %s", supabase_user_id)
```

In `backend/storage.py`, after the `clever_link:` branch (line ~145), add:

```python
    elif data_key.startswith('classlink_link:'):
        guid = data_key[len('classlink_link:'):]
        classlink_dir = os.path.join(graider_data, "classlink_links")
        safe = guid.replace('/', '_').replace(':', '_')
        return os.path.join(classlink_dir, f"{safe}.json")
```

(The `:`→`_` sanitization keeps the composite GUID a legal filename — colons are illegal on Windows.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_identity.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/storage.py tests/test_classlink_identity.py
git commit -m "feat(classlink): add classlink_link storage helpers + file-backend prefix [Class B]"
```

---

### Task 3: Core resolver — `resolve_classlink_user_id`

**Files:**
- Modify: `backend/auth.py` (add after `save_classlink_link`; add `list_all_users` import)
- Test: `tests/test_classlink_identity.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_classlink_identity.py`:

```python
class _FakeUser:
    def __init__(self, uid, email):
        self.id = uid
        self.email = email


class _FakeCreateResult:
    def __init__(self, uid):
        self.user = _FakeUser(uid, None)


def _patch_links(monkeypatch, initial=None):
    store = dict(initial or {})
    monkeypatch.setattr(auth, "load_classlink_links", lambda: dict(store))
    monkeypatch.setattr(auth, "save_classlink_link",
                        lambda guid, uid: store.__setitem__(guid, uid))
    return store


def test_resolve_missing_email_fails_closed(monkeypatch):
    _patch_links(monkeypatch)
    monkeypatch.setattr(auth, "_get_supabase", lambda: (_ for _ in ()).throw(AssertionError("no sb")))
    assert auth.resolve_classlink_user_id("classlink:2284:x", "", {"first": "A"}) is None


def test_resolve_returns_existing_link(monkeypatch):
    _patch_links(monkeypatch, {"classlink:2284:x": "uuid-existing"})
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") == "uuid-existing"


def test_resolve_single_email_match_links(monkeypatch):
    store = _patch_links(monkeypatch)
    sb = object()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    monkeypatch.setattr(auth, "list_all_users", lambda _sb: [_FakeUser("uuid-match", "A@B.com")])
    uid = auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com")
    assert uid == "uuid-match"
    assert store["classlink:2284:x"] == "uuid-match"


def test_resolve_multiple_matches_fails_closed(monkeypatch):
    _patch_links(monkeypatch)
    monkeypatch.setattr(auth, "_get_supabase", lambda: object())
    monkeypatch.setattr(auth, "list_all_users",
                        lambda _sb: [_FakeUser("u1", "a@b.com"), _FakeUser("u2", "a@b.com")])
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") is None


def test_resolve_creates_user_when_no_match(monkeypatch):
    store = _patch_links(monkeypatch)
    created = {}

    class _Admin:
        def create_user(self, attrs):
            created.update(attrs)
            return _FakeCreateResult("uuid-new")

    class _Auth:
        admin = _Admin()

    class _SB:
        auth = _Auth()

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    monkeypatch.setattr(auth, "list_all_users", lambda _sb: [])
    uid = auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com", {"first": "Jo", "last": "Lee"})
    assert uid == "uuid-new"
    assert store["classlink:2284:x"] == "uuid-new"
    assert created["email"] == "a@b.com"
    assert created["email_confirm"] is True
    assert created["user_metadata"]["approved"] is True
    assert created["user_metadata"]["auth_source"] == "classlink"


def test_resolve_create_race_recovers_by_email(monkeypatch):
    store = _patch_links(monkeypatch)
    calls = {"n": 0}

    def _users(_sb):
        # First call (pre-create): no match. After create raises, second call finds the winner.
        calls["n"] += 1
        return [] if calls["n"] == 1 else [_FakeUser("uuid-winner", "a@b.com")]

    class _Admin:
        def create_user(self, attrs):
            raise Exception("email address already registered")

    class _Auth:
        admin = _Admin()

    class _SB:
        auth = _Auth()

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    monkeypatch.setattr(auth, "list_all_users", _users)
    uid = auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com")
    assert uid == "uuid-winner"
    assert store["classlink:2284:x"] == "uuid-winner"


def test_resolve_no_supabase_fails_closed(monkeypatch):
    _patch_links(monkeypatch)
    monkeypatch.setattr(auth, "_get_supabase", lambda: None)
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_classlink_identity.py -v`
Expected: FAIL — `AttributeError: module 'backend.auth' has no attribute 'resolve_classlink_user_id'`.

- [ ] **Step 3: Implement the resolver**

Add `from backend.utils.supabase_users import list_all_users` to the imports in `backend/auth.py`, then add after `save_classlink_link`:

```python
def resolve_classlink_user_id(guid, email, name=None):
    """Resolve a ClassLink tenant-scoped GUID to a real Supabase Auth user UUID.

    Link-or-create. Returns:
      - a previously linked UUID, or
      - the UUID of the single Supabase user whose email matches (and links it), or
      - a freshly created Supabase user's UUID (approved, auth_source=classlink), or
      - None (fail closed) on missing email, ambiguous (>1) email match, no Supabase
        client, or create failure that cannot be deterministically recovered.
    """
    email = (email or "").strip()
    if not email:
        logger.warning("ClassLink resolve: missing email; failing closed")
        return None

    linked = load_classlink_links().get(guid)
    if linked:
        return linked

    name = name or {}
    try:
        sb = _get_supabase()
        if not sb:
            logger.warning("ClassLink resolve: no Supabase client; failing closed")
            return None

        def _email_matches():
            return [
                u for u in list_all_users(sb)
                if getattr(u, 'email', None) and u.email.lower() == email.lower()
            ]

        matches = _email_matches()
        if len(matches) == 1:
            save_classlink_link(guid, matches[0].id)
            return matches[0].id
        if len(matches) > 1:
            logger.warning("ClassLink resolve: %d users match email — failing closed", len(matches))
            return None

        try:
            res = sb.auth.admin.create_user({
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(32),
                "user_metadata": {
                    "approved": True,
                    "first_name": name.get('first', ''),
                    "last_name": name.get('last', ''),
                    "auth_source": "classlink",
                },
            })
            new_id = res.user.id
            save_classlink_link(guid, new_id)
            return new_id
        except Exception as create_err:
            # Concurrency: a parallel first-login may have created the user already.
            logger.warning("ClassLink resolve: create_user failed (%s); re-resolving by email", create_err)
            recheck = _email_matches()
            if len(recheck) == 1:
                save_classlink_link(guid, recheck[0].id)
                return recheck[0].id
            return None
    except Exception as e:
        logger.warning("ClassLink resolve failed (non-fatal): %s", e)
        sentry_sdk.capture_exception(e)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_identity.py -v`
Expected: PASS (all resolver tests green).

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py tests/test_classlink_identity.py
git commit -m "feat(classlink): resolve_classlink_user_id link-or-create resolver [Class B]"
```

---

### Task 4: Callback wiring — store UUID, pass to sync, account_conflict redirect

**Files:**
- Modify: `backend/routes/classlink_routes.py:611-628`
- Test: `tests/test_classlink_sso.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_classlink_sso.py` (adapt to the file's existing callback-test harness — it already builds a signed id_token via `tests/conftest_classlink.py`):

```python
def test_teacher_callback_stores_uuid_not_guid(monkeypatch, classlink_teacher_login):
    """The session user_id must be the resolved UUID, and sync must get the UUID."""
    import backend.routes.classlink_routes as clr
    monkeypatch.setattr(clr, "resolve_classlink_user_id",
                        lambda guid, email, name=None: "uuid-teacher")
    sync_args = {}
    monkeypatch.setattr(clr, "_trigger_roster_sync",
                        lambda tid, tenant: sync_args.update(tid=tid, tenant=tenant))

    resp, sess = classlink_teacher_login()  # helper drives the callback; returns response + session
    assert sess["classlink_user"]["user_id"] == "uuid-teacher"
    assert sess["classlink_user"]["classlink_id"]  # external identity retained
    assert sync_args["tid"] == "uuid-teacher"


def test_teacher_callback_account_conflict_when_resolver_none(monkeypatch, classlink_teacher_login):
    import backend.routes.classlink_routes as clr
    monkeypatch.setattr(clr, "resolve_classlink_user_id", lambda *a, **k: None)
    resp, _ = classlink_teacher_login()
    assert resp.status_code in (301, 302)
    assert "account_conflict" in resp.headers["Location"]
```

If `classlink_teacher_login` is not an existing fixture, build the callback invocation the same way the existing teacher-path tests in this file do (they already exercise `role == 'teacher'`); the two assertions are the new behavior. Inspect the file's existing teacher test to reuse its setup verbatim.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classlink_sso.py::test_teacher_callback_stores_uuid_not_guid -v`
Expected: FAIL — session `user_id` equals the GUID `classlink:...`, not `uuid-teacher`.

- [ ] **Step 3: Implement the wiring**

In `backend/routes/classlink_routes.py`, ensure the resolver is imported at top:

```python
from backend.auth import resolve_classlink_user_id
```

Replace the teacher branch (currently lines ~611-628) so it reads:

```python
    # Teacher/admin login
    session.clear()
    session.permanent = True

    # Resolve the tenant-scoped GUID to a real Supabase Auth UUID (link-or-create).
    graider_uuid = resolve_classlink_user_id(
        guid, email, {'first': first_name, 'last': last_name}
    )
    if not graider_uuid:
        return redirect("/?classlink_error=account_conflict")

    session['classlink_user'] = {
        'classlink_id': person_id,   # external identity (unchanged)
        'guid': guid,                # tenant-scoped GUID, kept for audit/debug
        'user_id': graider_uuid,     # real Supabase UUID → g.user_id / g.teacher_id
        'email': email,
        'name': {'first': first_name, 'last': last_name},
        'type': role or 'teacher',
        'tenant_id': tenant_id,
    }

    # Background roster sync (if OneRoster configured) — keyed by the UUID.
    _trigger_roster_sync(graider_uuid, tenant_id)

    audit_log("CLASSLINK_LOGIN", f"ClassLink SSO login: {redact_email(email)}",
              user="teacher", teacher_id=graider_uuid)
```

(`session.clear()` / `session.permanent = True` may already precede this block — keep them where they are; do not duplicate.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_sso.py -k "teacher_callback" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_sso.py
git commit -m "feat(classlink): wire teacher callback to resolved Supabase UUID + account_conflict [Class B]"
```

---

### Task 5: approval-status SSO short-circuit

**Files:**
- Modify: `backend/routes/auth_routes.py:101-133`
- Test: `tests/test_auth_approval.py` (Create, or extend an existing auth-route test file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_approval.py` (use the app/test-client fixture pattern from an existing route test, e.g. `tests/test_classlink_sso.py`'s client):

```python
def test_approval_status_short_circuits_for_classlink(client, monkeypatch):
    """A ClassLink session is district-approved by definition — no get_user_by_id call."""
    import backend.routes.auth_routes as ar
    def _boom():
        raise AssertionError("get_user_by_id must not be called for SSO sessions")
    monkeypatch.setattr(ar, "_get_supabase", _boom)

    # Simulate the auth middleware having set g.auth_source for a ClassLink cookie session.
    @client.application.before_request
    def _set_g():
        from flask import g
        g.user_id = "uuid-teacher"
        g.auth_source = "classlink"
        g.user_email = "t@d.org"

    resp = client.get("/api/auth/approval-status")
    assert resp.status_code == 200
    assert resp.get_json()["approved"] is True
```

If injecting `g` via `before_request` conflicts with the real `check_auth`, instead drive a real ClassLink session cookie (reuse the Task 4 login helper) and assert `approved is True` without patching `_get_supabase` to boom. The load-bearing assertion is **approved is True for a ClassLink session**.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_approval.py -v`
Expected: FAIL — handler calls `get_user_by_id` (raises) or returns `approved: False`.

- [ ] **Step 3: Implement the short-circuit**

In `backend/routes/auth_routes.py`, inside `approval_status`, immediately after the localhost/dev-shim bypass (the `if g.user_id == 'local-dev' or getattr(g, 'is_dev_shim', False):` block at line ~119), add:

```python
        # Clever/ClassLink sessions are district-approved by definition
        # (mirrors the middleware gate skip in backend/auth.py:247-248).
        if getattr(g, 'auth_source', None) in ('clever', 'classlink'):
            return jsonify({"approved": True, "email": getattr(g, 'user_email', '')})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_approval.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/auth_routes.py tests/test_auth_approval.py
git commit -m "fix(classlink): approval-status returns approved for SSO sessions [Class B]"
```

---

### Task 6: delete-data gate uses auth_source, not GUID prefix

**Files:**
- Modify: `backend/routes/classlink_routes.py:673-675`
- Test: `tests/test_classlink_sso.py` (or `tests/test_classlink_roster.py` which already calls `/api/classlink/delete-data`)

- [ ] **Step 1: Write the failing test**

Add (adapt to the existing delete-data test harness in `tests/test_classlink_roster.py:113-139`):

```python
def test_delete_data_allows_uuid_classlink_teacher(monkeypatch, classlink_session_client):
    """After the UUID switch, a ClassLink teacher (UUID teacher_id) must NOT get 403."""
    import backend.routes.classlink_routes as clr
    monkeypatch.setattr(clr, "delete_roster_data", lambda tid: {"classes": 1, "students": 2})
    # classlink_session_client sets a ClassLink cookie → g.auth_source='classlink',
    # g.teacher_id = a UUID
    resp = classlink_session_client.post("/api/classlink/delete-data")
    assert resp.status_code == 200
    assert resp.get_json()["counts"]["students"] == 2
```

Reuse the session-setup the existing delete-data tests use, but ensure the session's `user_id` is a UUID (the post-Task-4 reality) and `auth_source` resolves to `classlink`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classlink_roster.py -k delete_data_allows_uuid -v`
Expected: FAIL — 403 "Not a ClassLink user" because the UUID doesn't start with `classlink:`.

- [ ] **Step 3: Implement the gate fix**

In `backend/routes/classlink_routes.py`, in `classlink_delete_data`, replace:

```python
    teacher_id = g.teacher_id
    if not teacher_id.startswith("classlink:"):
        return jsonify({"error": "Not a ClassLink user"}), 403
```

with:

```python
    teacher_id = g.teacher_id
    if getattr(g, 'auth_source', None) != 'classlink':
        return jsonify({"error": "Not a ClassLink user"}), 403
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_roster.py -k delete -v`
Expected: PASS (the new test + the existing delete-data tests still green — update any existing test that relied on a `classlink:`-prefixed `teacher_id` to set `g.auth_source='classlink'` instead).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_roster.py
git commit -m "fix(classlink): delete-data gate keys off auth_source not GUID prefix [Class B]"
```

---

### Task 7: Frontend — Bearer suppression by auth_source + account_conflict message

**Files:**
- Modify: `frontend/src/services/api.js:15-26`
- Modify: `frontend/src/App.jsx:305` (Clever), `:347` (ClassLink), `:357-365` (error map)
- Test: `frontend/src/services/__tests__/getAuthHeaders.test.js` (Create) or nearest existing api test

- [ ] **Step 1: Write the failing test**

Create `frontend/src/services/__tests__/getAuthHeaders.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn(async () => ({ data: { session: { access_token: 'STALE' } } })) } },
}))

import { getAuthHeaders } from '../api'

describe('getAuthHeaders', () => {
  beforeEach(() => { window.__graiderUser = undefined })

  it('skips Bearer for a ClassLink UUID session via auth_source', async () => {
    window.__graiderUser = { id: '11111111-1111-1111-1111-111111111111', auth_source: 'classlink' }
    expect(await getAuthHeaders()).toEqual({})
  })

  it('skips Bearer for unlinked Clever via id prefix (fallback)', async () => {
    window.__graiderUser = { id: 'clever:abc' }
    expect(await getAuthHeaders()).toEqual({})
  })

  it('sends Bearer for a normal Supabase user', async () => {
    window.__graiderUser = { id: 'real-user' }
    expect(await getAuthHeaders()).toEqual({ Authorization: 'Bearer STALE' })
  })
})
```

Adjust the `vi.mock` path to the actual Supabase client module imported by `api.js` (check the import at the top of `frontend/src/services/api.js`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/services/__tests__/getAuthHeaders.test.js`
Expected: FAIL — first test sends `Bearer STALE` because the UUID id doesn't match the prefix check.

- [ ] **Step 3: Implement frontend changes**

In `frontend/src/services/api.js`, change the suppression condition in `getAuthHeaders`:

```js
  const currentUser = window.__graiderUser;
  const isSso = currentUser && (
    currentUser.auth_source === 'classlink' || currentUser.auth_source === 'clever' ||
    (currentUser.id && (currentUser.id.startsWith('clever:') || currentUser.id.startsWith('classlink:')))
  );
  if (isSso) {
    return {}
  }
```

In `frontend/src/App.jsx`, line ~305 (Clever handler) add `auth_source: 'clever'`:

```js
            window.__graiderUser = { id: 'clever:' + data.clever_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''), auth_source: 'clever' };
```

Line ~347 (ClassLink handler) add `auth_source: 'classlink'`:

```js
            window.__graiderUser = { id: data.user_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''), auth_source: 'classlink' };
```

In the `classlinkErrorMessages` map (line ~357), add:

```js
        'account_conflict': 'We could not match your ClassLink account to a Graider account. Please contact your administrator.',
```

- [ ] **Step 4: Run tests + build to verify**

Run: `cd frontend && npx vitest run src/services/__tests__/getAuthHeaders.test.js && npm run build`
Expected: vitest PASS (3 passed); build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.js frontend/src/App.jsx frontend/src/services/__tests__/getAuthHeaders.test.js
git commit -m "fix(classlink): suppress stale Bearer for SSO via auth_source + account_conflict msg [Class B]"
```

---

## Per-Branch Verification (before PR)

- [ ] Full backend suite: `source venv/bin/activate && pytest -q --ignore=tests/load` — green (or any failure proven pre-existing via `git checkout main -- <file>` protocol).
- [ ] Cross-cutting grep: `for f in backend/auth.py backend/storage.py backend/routes/classlink_routes.py backend/routes/auth_routes.py; do grep -rln "$f" tests/; done` — run every surfaced test.
- [ ] Line-shift pin scan: `grep -rn '"backend/routes/classlink_routes.py"' tests/` and `'"backend/auth.py"'` — verify `test_sis_alerting`-style `(file,line)` pins still fall in-window after the teacher-branch edits; update with documenting comments if shifted.
- [ ] Frontend: `cd frontend && npx vitest run && npm run build`.
- [ ] Lint/SAST on changed files: `ruff check backend/ && bandit -q -r backend/auth.py backend/routes/classlink_routes.py backend/routes/auth_routes.py backend/storage.py`.
- [ ] Spec reviewer ✅ then **opus** code-quality reviewer ✅ (Class B).
- [ ] GitNexus reindex: `npx gitnexus analyze --embeddings`.
- [ ] PR body: classify **Class B**, link spec + this plan, list the verification commands, note follow-up #(unlinked-Clever auto-create) per §8.

## Manual / Operator Verification (per-branch DoD, Hard Rule #8)

CI + reviewers cannot prove the live SSO path. After deploy, an operator logs in as ClassLink test teacher `T4957-0005` via the **cltest LaunchPad tile** and confirms: lands on the dashboard (not `account_conflict`, not a pending screen), no `invalid input syntax for type uuid` or `NoneType` errors in Sentry for the login, and a `students`/`classes` read succeeds. Re-run roster sync (§7 Action A of handoff.md) once a real OneRoster config is saved for the new UUID teacher.
