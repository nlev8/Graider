# ClassLink SSO Certification-Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix ClassLink SSO identity to a tenant-scoped, fail-closed GUID (`classlink:{tenant}:{person}`) so the OAuth2/OIDC connection passes ClassLink partner certification, eliminating the cross-tenant identity collision.

**Architecture:** ClassLink identity is formed **once** in the `/api/classlink/callback` handler from the userinfo `TenantId` + `SourcedId` (fail-closed if either is absent), stored in the Flask session as a canonical `user_id`, and read verbatim by `auth.py` per-request and by the React frontend. Email auto-linking is removed entirely (clean break — no live users, no migration).

**Tech Stack:** Python 3 / Flask (backend), pytest (tests), React + Vite (frontend), PyJWT + cryptography (OIDC test harness).

**Spec:** `docs/superpowers/specs/2026-05-25-classlink-sso-certification-readiness-design.md`

**⚠️ PR classification (CLAUDE.md Principle #13): Class B — this changes auth/identity logic.** Code review is a HARD pre-gate before merge. Do NOT arm `gh pr merge --auto` with a review in flight; merge manually after the review returns clean.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `backend/routes/classlink_routes.py` | ClassLink SSO routes + identity helpers | Add `_classlink_guid` + `_extract_person_id`; rework callback identity block; delete `_link_classlink_account` + `_resolve_classlink_user_id`; add `user_id` to `/session` |
| `backend/auth.py` | Per-request identity resolution | Read `g.user_id`/`g.teacher_id` from session `user_id`; drop the `_resolve_classlink_user_id` import |
| `frontend/src/App.jsx` | Teacher auth bootstrap | Use canonical `data.user_id` from `/session` instead of reconstructing `'classlink:' + classlink_id` |
| `tests/test_classlink_sso.py` | SSO flow tests | Drop deleted-function patch; add tenant-scoping/fail-closed/role/student-parity tests |
| `tests/test_classlink_routes_gaps.py` | Helper unit tests | Remove tests for deleted functions; add helper tests |

No new files. Helpers live in `classlink_routes.py` (the file is ~459 LOC and the helpers belong with the callback that uses them).

---

## Task 1: Identity helpers (`_classlink_guid`, `_extract_person_id`)

**Files:**
- Modify: `backend/routes/classlink_routes.py` (add two module-level helpers near the existing `_resolve_classlink_user_id` at line 111)
- Test: `tests/test_classlink_routes_gaps.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_classlink_routes_gaps.py`:

```python
class TestClasslinkGuid:
    def test_assembles_prefixed_composite(self):
        from backend.routes.classlink_routes import _classlink_guid
        assert _classlink_guid("2284", "abc") == "classlink:2284:abc"

    def test_encodes_colon_in_components_to_prevent_collision(self):
        from backend.routes.classlink_routes import _classlink_guid
        # ("a:b","c") and ("a","b:c") must NOT collide
        assert _classlink_guid("a:b", "c") == "classlink:a%3Ab:c"
        assert _classlink_guid("a", "b:c") == "classlink:a:b%3Ac"
        assert _classlink_guid("a:b", "c") != _classlink_guid("a", "b:c")

    def test_returns_none_on_empty_component(self):
        from backend.routes.classlink_routes import _classlink_guid
        assert _classlink_guid("", "abc") is None
        assert _classlink_guid("2284", "") is None
        assert _classlink_guid("  ", "abc") is None


class TestExtractPersonId:
    def test_prefers_sourcedid(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"SourcedId": "s1", "UserId": "u1"}) == "s1"

    def test_accepts_lowercase_sourcedid(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"sourcedId": "s2"}) == "s2"

    def test_falls_back_to_userid(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"UserId": "u1"}) == "u1"

    def test_none_when_no_person_field(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"Email": "x@y.z"}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_classlink_routes_gaps.py::TestClasslinkGuid tests/test_classlink_routes_gaps.py::TestExtractPersonId -v`
Expected: FAIL with `ImportError`/`AttributeError: cannot import name '_classlink_guid'`.

- [ ] **Step 3: Implement the helpers**

In `backend/routes/classlink_routes.py`, add `import urllib.parse` to the top imports (alongside `from urllib.parse import urlencode` at line 23 — add a separate `import urllib.parse`), then add these two helpers immediately above `_resolve_classlink_user_id` (line 111):

```python
def _classlink_guid(tenant_id, person_id):
    """Build the tenant-scoped ClassLink identity GUID.

    Format: ``classlink:{tenant}:{person}`` with each component percent-encoded
    so a literal ':' inside a component cannot create an ambiguous (colliding)
    GUID. Mirrors ClassLink's recommended TenantId+SourcedId globally-unique id.

    Returns None if either component is empty (caller MUST fail closed).
    """
    tenant = str(tenant_id or "").strip()
    person = str(person_id or "").strip()
    if not tenant or not person:
        return None
    return (
        "classlink:"
        + urllib.parse.quote(tenant, safe="")
        + ":"
        + urllib.parse.quote(person, safe="")
    )


def _extract_person_id(user_data):
    """Resolve the person component of the GUID from the ClassLink userinfo body.

    Precedence: OneRoster ``SourcedId`` (preferred — reconciles with rostering),
    then ``UserId``. NEVER falls back to the OIDC ``sub`` alone, which is not
    guaranteed to equal the OneRoster sourcedId. Returns None if absent (caller
    fails closed). When falling back to UserId, logs a warning (not silent).
    """
    sourced = str(user_data.get("SourcedId") or user_data.get("sourcedId") or "").strip()
    if sourced:
        return sourced
    user_id = str(user_data.get("UserId") or "").strip()
    if user_id:
        logger.warning("ClassLink userinfo has no SourcedId; using UserId as person id")
        return user_id
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_classlink_routes_gaps.py::TestClasslinkGuid tests/test_classlink_routes_gaps.py::TestExtractPersonId -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_routes_gaps.py
git commit -m "feat(classlink): add tenant-scoped GUID + person-id helpers"
```

---

## Task 2: Rework the callback identity block (tenant-scoped, fail-closed) + delete `_link_classlink_account`

**Files:**
- Modify: `backend/routes/classlink_routes.py` (callback identity block, currently lines ~380-429; delete `_link_classlink_account` at lines 57-108)
- Test: `tests/test_classlink_sso.py`, `tests/test_classlink_routes_gaps.py`

- [ ] **Step 1: Write the failing tests**

Add this shared helper + test class to `tests/test_classlink_sso.py` (it reuses `_make_app`, `_make_rsa_keypair`, `_mock_jwks_client`, `_mock_oidc_config`, `make_id_token` already in the file):

```python
def _run_callback(client, priv, pub, userinfo, sub="cl-sub", nonce=None):
    """Drive a LaunchPad-permissive callback (no initiated_by_us marker) with a
    given userinfo body. Returns the Flask response."""
    id_token = make_id_token(
        priv, aud="test-client-id", sub=sub, nonce=nonce,
        email=userinfo.get("Email", ""), given_name=userinfo.get("FirstName", ""),
        family_name=userinfo.get("LastName", ""), role=userinfo.get("Role", "teacher"),
    )
    mock_token_resp = MagicMock(); mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "tok", "id_token": id_token}
    mock_user_resp = MagicMock(); mock_user_resp.status_code = 200
    mock_user_resp.json.return_value = userinfo
    with client.session_transaction() as sess:
        sess['classlink_oauth_state'] = 'valid-state'
    with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
         patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
         patch('backend.routes.classlink_routes.get_classlink_oidc_config', return_value=_mock_oidc_config()), \
         patch('backend.routes.classlink_routes.get_classlink_jwks_client', return_value=_mock_jwks_client(pub)), \
         patch('backend.routes.classlink_routes._trigger_roster_sync'):
        return client.get('/api/classlink/callback?code=c&state=valid-state')


class TestClassLinkTenantScopedIdentity:
    BASE = {"FirstName": "A", "LastName": "B", "Email": "a@school.edu", "Role": "teacher"}

    def test_teacher_guid_is_tenant_scoped(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub,
                                 {**self.BASE, "SourcedId": "p1", "TenantId": "dist-A"})
            assert 'classlink_login=success' in resp.location
            with client.session_transaction() as sess:
                assert sess['classlink_user']['user_id'] == "classlink:dist-A:p1"

    def test_same_person_different_tenants_distinct_guids(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as c1:
            _run_callback(c1, priv, pub, {**self.BASE, "SourcedId": "same", "TenantId": "dist-A"})
            with c1.session_transaction() as s1:
                guid_a = s1['classlink_user']['user_id']
        with app.test_client() as c2:
            _run_callback(c2, priv, pub, {**self.BASE, "SourcedId": "same", "TenantId": "dist-B"})
            with c2.session_transaction() as s2:
                guid_b = s2['classlink_user']['user_id']
        assert guid_a == "classlink:dist-A:same"
        assert guid_b == "classlink:dist-B:same"
        assert guid_a != guid_b

    def test_missing_tenant_rejected_fail_closed(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub, {**self.BASE, "SourcedId": "p1"})  # no TenantId
            assert 'classlink_error=missing_tenant' in resp.location
            with client.session_transaction() as sess:
                assert 'classlink_user' not in sess

    def test_missing_person_id_rejected_fail_closed(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub, {**self.BASE, "TenantId": "dist-A"})  # no SourcedId/UserId
            assert 'classlink_error=missing_identity' in resp.location

    def test_userinfo_sub_mismatch_rejected(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            # id_token sub = "cl-sub"; userinfo carries a conflicting sub
            resp = _run_callback(client, priv, pub,
                                 {**self.BASE, "SourcedId": "p1", "TenantId": "dist-A", "sub": "OTHER"})
            assert 'classlink_error=identity_mismatch' in resp.location

    def test_role_as_list_resolves_student(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub,
                                 {**self.BASE, "Role": ["student"], "SourcedId": "p1", "TenantId": "dist-A"})
            assert '/student?classlink_login=success' in resp.location

    def test_student_path_gets_tenant_scoped_guid(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            _run_callback(client, priv, pub,
                          {**self.BASE, "Role": "student", "SourcedId": "stu1", "TenantId": "dist-A"})
            with client.session_transaction() as sess:
                assert sess['classlink_student']['user_id'] == "classlink:dist-A:stu1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_classlink_sso.py::TestClassLinkTenantScopedIdentity -v`
Expected: FAIL — e.g. `KeyError: 'user_id'` (session has no `user_id` yet) and `missing_tenant`/`missing_identity`/`identity_mismatch` not in location.

- [ ] **Step 3: Implement — replace the callback identity block**

In `backend/routes/classlink_routes.py`, replace the entire block from `# Prefer id_token claims as source of truth...` (line ~380) through the final `return redirect("/?classlink_login=success")` (line ~429) with:

```python
    # OIDC Core: if userinfo carries a `sub`, it MUST equal the id_token `sub`
    # before we trust any other userinfo claim.
    userinfo_sub = str(user_data.get('sub', '') or '')
    if userinfo_sub and userinfo_sub != str(id_claims.get('sub', '') or ''):
        logger.warning("ClassLink userinfo sub does not match id_token sub")
        return redirect("/?classlink_error=identity_mismatch")

    # Standard OIDC fields prefer the signed id_token; ClassLink-specific fields
    # (TenantId, SourcedId, Role) come from userinfo.
    first_name = id_claims.get('given_name') or user_data.get('FirstName', '')
    last_name = id_claims.get('family_name') or user_data.get('LastName', '')
    email = id_claims.get('email') or user_data.get('Email', '')

    # Role may arrive as a string, a comma-separated string, or a list.
    raw_role = id_claims.get('Role') or user_data.get('Role') or ''
    if isinstance(raw_role, (list, tuple)):
        raw_role = raw_role[0] if raw_role else ''
    role = str(raw_role).split(',')[0].strip().lower()

    # Tenant-scoped identity (fail closed — never a non-scoped fallback).
    tenant_id = str(user_data.get('TenantId', '') or '').strip()
    if not tenant_id:
        logger.warning("ClassLink login rejected: userinfo missing TenantId")
        return redirect("/?classlink_error=missing_tenant")

    person_id = _extract_person_id(user_data)
    if not person_id:
        logger.warning("ClassLink login rejected: userinfo missing SourcedId/UserId")
        return redirect("/?classlink_error=missing_identity")

    guid = _classlink_guid(tenant_id, person_id)
    if not guid:
        return redirect("/?classlink_error=missing_identity")

    # Student login → redirect to student portal
    if role == 'student':
        # Clear OAuth-flow markers (single-use enforcement on success).
        session.pop('classlink_oauth_state', None)
        session.pop('classlink_oauth_nonce', None)
        session.pop('classlink_oauth_initiated_by_us', None)
        session['classlink_student'] = {
            'classlink_id': person_id,
            'user_id': guid,
            'name': f"{first_name} {last_name}",
            'email': email,
            'tenant_id': tenant_id,
        }
        return redirect("/student?classlink_login=success")

    # Teacher/admin login
    session.clear()
    session.permanent = True

    session['classlink_user'] = {
        'classlink_id': person_id,
        'user_id': guid,
        'email': email,
        'name': {'first': first_name, 'last': last_name},
        'type': role or 'teacher',
        'tenant_id': tenant_id,
    }

    # Background roster sync (if OneRoster configured) — keyed by the GUID.
    _trigger_roster_sync(guid, tenant_id)

    audit_log("CLASSLINK_LOGIN", f"ClassLink SSO login: {redact_email(email)}",
              user="teacher", teacher_id=guid)

    return redirect("/?classlink_login=success")
```

Then **delete** `_link_classlink_account` entirely (lines 57-108, the whole `def _link_classlink_account(...)` function and its docstring).

- [ ] **Step 4: Remove the now-broken references to the deleted function**

In `tests/test_classlink_sso.py`, delete the line `patch('backend.routes.classlink_routes._link_classlink_account'), \` from `test_successful_teacher_login` (line ~134). Add `"SourcedId": "cl-user-123",` to that test's `mock_user_resp.json.return_value` dict so it has an explicit person id.

In `tests/test_classlink_routes_gaps.py`, delete the entire `TestLinkClasslinkAccount` class (the class testing `_link_classlink_account`, ~lines 70-195).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_classlink_sso.py::TestClassLinkTenantScopedIdentity tests/test_classlink_sso.py::TestClassLinkCallback -v`
Expected: PASS (new class + existing callback tests).
Run: `python -c "import backend.routes.classlink_routes"` — Expected: no error (no dangling `_link_classlink_account` reference).

- [ ] **Step 6: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_sso.py tests/test_classlink_routes_gaps.py
git commit -m "feat(classlink): tenant-scoped fail-closed identity in callback; drop email auto-link"
```

---

## Task 3: Delete `_resolve_classlink_user_id`; resolve identity from session in `auth.py`

**Files:**
- Modify: `backend/routes/classlink_routes.py` (delete `_resolve_classlink_user_id`, lines ~111-122)
- Modify: `backend/auth.py:208-216`
- Test: `tests/test_classlink_sso.py`, `tests/test_classlink_routes_gaps.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_classlink_sso.py`:

```python
class TestClassLinkAuthResolution:
    def test_teacher_id_resolved_from_session_user_id(self):
        import os as _os
        from flask import Flask, g, jsonify
        from backend.auth import init_auth
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        init_auth(app)

        @app.route('/api/_whoami')
        def _whoami():
            return jsonify({
                "teacher_id": getattr(g, 'teacher_id', None),
                "user_id": getattr(g, 'user_id', None),
                "auth_source": getattr(g, 'auth_source', None),
                "district_id": getattr(g, 'district_id', None),
            })

        with patch.dict(_os.environ, {'FLASK_ENV': 'production'}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['classlink_user'] = {
                        'user_id': 'classlink:dist-A:p1',
                        'classlink_id': 'p1',
                        'email': 'a@school.edu',
                        'tenant_id': 'dist-A',
                    }
                data = client.get('/api/_whoami').get_json()
        assert data['teacher_id'] == 'classlink:dist-A:p1'
        assert data['user_id'] == 'classlink:dist-A:p1'
        assert data['auth_source'] == 'classlink'
        assert data['district_id'] == 'dist-A'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classlink_sso.py::TestClassLinkAuthResolution -v`
Expected: FAIL — `teacher_id` is the old `classlink:p1` (from `_resolve_classlink_user_id(classlink_id)`), not `classlink:dist-A:p1`.

- [ ] **Step 3: Implement — rewire `auth.py`**

In `backend/auth.py`, replace lines 208-216 (the ClassLink SSO session block) with:

```python
        # ClassLink SSO session — identity GUID was formed (tenant-scoped) at
        # the OAuth callback and stored as `user_id`; read it verbatim.
        classlink_user = session.get('classlink_user') if hasattr(session, 'get') else None
        if classlink_user and not has_bearer:
            g.user_id = classlink_user.get('user_id', '')
            g.teacher_id = g.user_id
            g.user_email = classlink_user.get('email', '')
            g.auth_source = 'classlink'
            g.district_id = classlink_user.get('tenant_id', '')
            return None
```

(This removes the `from backend.routes.classlink_routes import _resolve_classlink_user_id` import line and the call.)

- [ ] **Step 4: Delete `_resolve_classlink_user_id`**

In `backend/routes/classlink_routes.py`, delete the entire `def _resolve_classlink_user_id(classlink_id):` function (lines ~111-122).

In `tests/test_classlink_routes_gaps.py`, delete the entire `TestResolveClasslinkUserId` class (~lines 196-227).

- [ ] **Step 5: Verify no dangling references**

Run: `grep -rn "_resolve_classlink_user_id" backend/ tests/`
Expected: NO output (zero references remain).
Run: `python -c "import backend.auth, backend.routes.classlink_routes"`
Expected: no error.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_classlink_sso.py::TestClassLinkAuthResolution -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/auth.py backend/routes/classlink_routes.py tests/test_classlink_routes_gaps.py tests/test_classlink_sso.py
git commit -m "refactor(classlink): resolve identity from session GUID; remove _resolve_classlink_user_id"
```

---

## Task 4: `/api/classlink/session` returns canonical `user_id`; frontend consumes it

**Files:**
- Modify: `backend/routes/classlink_routes.py` (`classlink_session`, line ~434)
- Modify: `frontend/src/App.jsx:340,347`
- Test: `tests/test_classlink_sso.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_classlink_sso.py`:

```python
class TestClassLinkSessionEndpoint:
    def test_session_returns_canonical_user_id(self):
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_user'] = {
                    'user_id': 'classlink:dist-A:p1',
                    'classlink_id': 'p1',
                    'email': 'a@school.edu',
                    'name': {'first': 'A', 'last': 'B'},
                    'type': 'teacher',
                    'tenant_id': 'dist-A',
                }
            data = client.get('/api/classlink/session').get_json()
        assert data['authenticated'] is True
        assert data['user_id'] == 'classlink:dist-A:p1'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classlink_sso.py::TestClassLinkSessionEndpoint -v`
Expected: FAIL — `KeyError: 'user_id'` (endpoint doesn't return it yet).

- [ ] **Step 3: Implement — add `user_id` to the session response**

In `backend/routes/classlink_routes.py`, in `classlink_session` (line ~441), add the `user_id` field to the returned JSON:

```python
    return jsonify({
        "authenticated": True,
        "user_id": cl_user.get('user_id'),
        "classlink_id": cl_user.get('classlink_id'),
        "email": cl_user.get('email'),
        "name": cl_user.get('name'),
        "type": cl_user.get('type'),
        "tenant_id": cl_user.get('tenant_id'),
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classlink_sso.py::TestClassLinkSessionEndpoint -v`
Expected: PASS.

- [ ] **Step 5: Update the frontend to use `user_id`**

In `frontend/src/App.jsx`, change line 340 from:

```javascript
              id: 'classlink:' + data.classlink_id,
```
to:
```javascript
              id: data.user_id,
```

And line 347 from:
```javascript
            window.__graiderUser = { id: 'classlink:' + data.classlink_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || '') };
```
to:
```javascript
            window.__graiderUser = { id: data.user_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || '') };
```

- [ ] **Step 6: Verify the frontend builds**

Run: `cd frontend && npm run build`
Expected: build succeeds (output to `backend/static/`).

- [ ] **Step 7: Commit**

```bash
git add backend/routes/classlink_routes.py frontend/src/App.jsx
git commit -m "feat(classlink): /session returns canonical user_id; frontend uses it verbatim"
```

---

## Task 5: Full-suite verification + PR

**Files:** none (verification only)

- [ ] **Step 1: Run the full ClassLink + auth suites**

Run: `pytest tests/test_classlink_sso.py tests/test_classlink_sso_contract.py tests/test_classlink_routes_gaps.py -v`
Expected: ALL PASS (no references to deleted functions; new tenant-scoping/fail-closed/auth/session tests green).

- [ ] **Step 2: Lint + import sanity**

Run: `ruff check backend/routes/classlink_routes.py backend/auth.py`
Expected: clean (no F401 unused-import for the removed `_resolve_classlink_user_id` import, no F821).
Run: `grep -rn "_link_classlink_account\|_resolve_classlink_user_id" backend/ tests/`
Expected: NO output.

- [ ] **Step 3: Broader regression (catch any cross-module identity assumptions)**

Run: `pytest -k "classlink or auth" -q`
Expected: PASS.

- [ ] **Step 4: Re-index GitNexus (code changed)**

Run: `npx gitnexus analyze --embeddings`
Expected: completes; index no longer stale.

- [ ] **Step 5: Push branch + open PR (Class B — review gates the merge)**

```bash
git push -u origin docs/classlink-sso-cert-readiness-spec
gh pr create --title "feat(classlink): SSO certification-readiness — tenant-scoped fail-closed identity" \
  --body "Implements docs/superpowers/specs/2026-05-25-classlink-sso-certification-readiness-design.md. Class B (auth/identity) — review is a HARD pre-gate; do NOT auto-merge with a review in flight."
```

- [ ] **Step 6: Request code review, fix to clean, THEN merge manually**

Per CLAUDE.md Principle #13 (Class B): create PR → review → fix to clean → merge manually. Do not arm `--auto`.

---

## Self-Review (completed during plan authoring)

- **Spec coverage:** D1-D4 + consult amendments A1-A6 each map to a task — A1/A2 (fail-closed, no `sub`) → Task 1+2; A3 (URL-encode) → Task 1; A4 (sub-match) → Task 2; A5 (role list) → Task 2; A6 (frontend double-prefix) → Task 4. Identity format (§5.1) → Task 1. Error table (§5.4) → Task 2. Student parity → Task 2. Out-of-scope roster items correctly excluded.
- **Placeholder scan:** none — every code/test step has complete code.
- **Type/name consistency:** `_classlink_guid(tenant_id, person_id)`, `_extract_person_id(user_data)`, session key `user_id`, error codes `missing_tenant`/`missing_identity`/`identity_mismatch` used identically across all tasks.
- **Non-code dependency (spec §7):** the live-account confirmation that the userinfo person field == OneRoster `sourcedId` is OUTSIDE this plan (it's a cert-call prerequisite); the code accepts `SourcedId`→`UserId` and logs the fallback so the test account works regardless.
