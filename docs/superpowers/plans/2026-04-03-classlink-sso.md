# ClassLink OAuth2 SSO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ClassLink OAuth2/OIDC SSO so teachers can click the Graider tile in their ClassLink LaunchPad and land in Graider already authenticated, with automatic account linking and roster sync.

**Architecture:** Mirror the existing Clever SSO pattern exactly. New `backend/routes/classlink_routes.py` blueprint with OAuth2 callback, user info fetch, session creation, and account linking. Frontend gets a "Login with ClassLink" button on the login screen. Reuses existing OneRoster roster sync after login. Same session management, CSRF protection, and auth resolution as Clever.

**Tech Stack:** Flask, OAuth2 (authorization code flow), ClassLink API, existing session/auth infrastructure

**Env vars (already set in Railway):**
- `CLASSLINK_CLIENT_ID` — `c177524789966949d15db46d6b805304b7f67492e40a`
- `CLASSLINK_CLIENT_SECRET` — `974f9dc57575f4d6d9cf75facaeb9c71`

**ClassLink OAuth endpoints:**
- Authorization: `https://launchpad.classlink.com/oauth2/v2/auth`
- Token: `https://launchpad.classlink.com/oauth2/v2/token`
- User info: `https://nodeapi.classlink.com/v2/my/info`

**Redirect URI:** `https://app.graider.live/api/classlink/callback`

**Scopes:** `profile oneroster email openid`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/classlink_routes.py` | **Create** | ClassLink SSO: login URL, OAuth callback, session, logout |
| `backend/routes/__init__.py` | **Modify** | Register `classlink_bp` blueprint |
| `backend/auth.py` | **Modify** | Add ClassLink session resolution (mirror Clever pattern) |
| `frontend/src/components/LoginScreen.jsx` | **Modify** | Add "Login with ClassLink" button |
| `tests/test_classlink_sso.py` | **Create** | OAuth callback tests: auth, session, account linking |
| `CLAUDE.md` | **Modify** | Add ClassLink env vars + API reference |

---

### Task 1: Create ClassLink routes blueprint

**Files:**
- Create: `backend/routes/classlink_routes.py`
- Create: `tests/test_classlink_sso.py`

- [ ] **Step 1: Write failing tests for the ClassLink OAuth flow**

Create `tests/test_classlink_sso.py`:

```python
"""Tests for ClassLink OAuth2/OIDC SSO flow."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from flask import Flask, session


def _make_app():
    """Create a minimal Flask app with ClassLink routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['RATELIMIT_ENABLED'] = False

    os.environ['CLASSLINK_CLIENT_ID'] = 'test-client-id'
    os.environ['CLASSLINK_CLIENT_SECRET'] = 'test-client-secret'

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.classlink_routes import classlink_bp
    app.register_blueprint(classlink_bp)
    return app


class TestClassLinkLoginURL:
    def test_returns_authorization_url(self):
        """Should return ClassLink OAuth authorization URL with state."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/login-url')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'url' in data
        assert 'launchpad.classlink.com/oauth2/v2/auth' in data['url']
        assert 'client_id=test-client-id' in data['url']
        assert 'state=' in data['url']

    def test_returns_error_when_not_configured(self):
        """Should return error when CLASSLINK_CLIENT_ID is not set."""
        app = _make_app()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CLASSLINK_CLIENT_ID', None)
            with app.test_client() as client:
                resp = client.get('/api/classlink/login-url')
        data = resp.get_json()
        assert 'error' in data or resp.status_code != 200


class TestClassLinkCallback:
    def test_rejects_missing_code(self):
        """Should redirect with error when no code parameter."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/callback')
        assert resp.status_code == 302
        assert 'classlink_error' in resp.location

    def test_rejects_oauth_error(self):
        """Should redirect with error when OAuth returns error param."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/callback?error=access_denied')
        assert resp.status_code == 302
        assert 'classlink_error=access_denied' in resp.location

    def test_successful_teacher_login(self):
        """Should create session and redirect on successful teacher login."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token"}

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-user-123",
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "jane.smith@school.edu",
            "Role": "teacher",
            "TenantId": "district-456",
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_oauth_state'] = 'valid-state'

            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes._link_classlink_account'), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get('/api/classlink/callback?code=auth-code-123&state=valid-state')

            assert resp.status_code == 302
            assert 'classlink_login=success' in resp.location

            with client.session_transaction() as sess:
                assert 'classlink_user' in sess
                assert sess['classlink_user']['email'] == 'jane.smith@school.edu'
                assert sess['classlink_user']['classlink_id'] == 'cl-user-123'

    def test_student_login_redirects_to_student_portal(self):
        """Should redirect students to /student path."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token"}

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-student-789",
            "FirstName": "Bob",
            "LastName": "Jones",
            "Email": "bob.jones@school.edu",
            "Role": "student",
            "TenantId": "district-456",
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_oauth_state'] = 'valid-state'

            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp):
                resp = client.get('/api/classlink/callback?code=auth-code-123&state=valid-state')

            assert resp.status_code == 302
            assert '/student' in resp.location

    def test_token_exchange_failure(self):
        """Should redirect with error when token exchange fails."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 400
        mock_token_resp.json.return_value = {"error": "invalid_grant"}
        mock_token_resp.text = "invalid_grant"

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_oauth_state'] = 'valid-state'

            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp):
                resp = client.get('/api/classlink/callback?code=bad-code&state=valid-state')

            assert resp.status_code == 302
            assert 'classlink_error' in resp.location


class TestClassLinkSession:
    def test_session_check_returns_status(self):
        """Should return session status."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/session')
        data = resp.get_json()
        assert data['authenticated'] is False

    def test_session_check_when_logged_in(self):
        """Should return user info when session exists."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_user'] = {
                    'classlink_id': 'cl-123',
                    'email': 'jane@school.edu',
                    'name': {'first': 'Jane', 'last': 'Smith'},
                    'type': 'teacher',
                    'tenant_id': 'district-456',
                }
            resp = client.get('/api/classlink/session')
        data = resp.get_json()
        assert data['authenticated'] is True
        assert data['email'] == 'jane@school.edu'


class TestClassLinkLogout:
    def test_logout_clears_session(self):
        """Should clear ClassLink session data."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_user'] = {'classlink_id': 'cl-123'}
            resp = client.post('/api/classlink/logout')
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert 'classlink_user' not in sess
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_classlink_sso.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.routes.classlink_routes'`

- [ ] **Step 3: Implement ClassLink routes blueprint**

Create `backend/routes/classlink_routes.py`:

```python
"""
ClassLink OAuth2/OIDC SSO Routes
=================================
Mirrors the Clever SSO pattern (clever_routes.py) for ClassLink LaunchPad.

Endpoints:
  GET  /api/classlink/login-url  — Get ClassLink OAuth authorization URL
  GET  /api/classlink/callback   — OAuth callback (ClassLink redirects here)
  GET  /api/classlink/session    — Check ClassLink session status
  POST /api/classlink/logout     — Clear ClassLink session
"""

import os
import logging
import secrets
import requests
from flask import Blueprint, request, redirect, jsonify, session, g
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

classlink_bp = Blueprint('classlink', __name__)

# ClassLink OAuth2 endpoints
CLASSLINK_AUTH_URL = 'https://launchpad.classlink.com/oauth2/v2/auth'
CLASSLINK_TOKEN_URL = 'https://launchpad.classlink.com/oauth2/v2/token'
CLASSLINK_USERINFO_URL = 'https://nodeapi.classlink.com/v2/my/info'

CLASSLINK_SCOPES = 'profile oneroster email openid'


def _get_classlink_config():
    """Get ClassLink OAuth config from environment."""
    client_id = os.environ.get('CLASSLINK_CLIENT_ID', '')
    client_secret = os.environ.get('CLASSLINK_CLIENT_SECRET', '')
    redirect_uri = os.environ.get(
        'CLASSLINK_REDIRECT_URI',
        'https://app.graider.live/api/classlink/callback'
    )
    return client_id, client_secret, redirect_uri


def _link_classlink_account(classlink_id, email):
    """Link ClassLink user to existing Graider account by email match.

    Same pattern as clever_routes.py account merging (lines 366-393).
    If a Supabase user exists with the same email, create a persistent
    classlink_id → supabase_user_id mapping.
    """
    try:
        from backend.storage import load as storage_load, save as storage_save

        links = storage_load('classlink_links', 'system') or {}
        if classlink_id in links:
            return  # Already linked

        from backend.supabase_client import get_supabase
        sb = get_supabase()
        if not sb or not email:
            return

        # Check if teacher_data has any entries with this email
        result = sb.table('teacher_data').select('teacher_id').eq(
            'data_key', 'settings'
        ).execute()

        for row in (result.data or []):
            tid = row.get('teacher_id', '')
            settings = storage_load('settings', tid)
            if settings and isinstance(settings, dict):
                config = settings.get('config', settings)
                if config.get('email', '').lower() == email.lower():
                    links[classlink_id] = tid
                    storage_save('classlink_links', links, 'system')
                    logger.info("Linked ClassLink user %s to teacher %s via email match",
                                classlink_id, tid)
                    return
    except Exception as e:
        logger.warning("ClassLink account linking failed: %s", e)


def _resolve_classlink_user_id(classlink_id):
    """Resolve ClassLink user ID to Graider teacher_id.

    Returns linked Supabase UUID if exists, otherwise 'classlink:{id}'.
    Same pattern as auth.py resolve_clever_user_id().
    """
    try:
        from backend.storage import load as storage_load
        links = storage_load('classlink_links', 'system') or {}
        return links.get(str(classlink_id), f"classlink:{classlink_id}")
    except Exception:
        return f"classlink:{classlink_id}"


def _trigger_roster_sync(teacher_id, tenant_id):
    """Trigger background OneRoster roster sync after ClassLink login.

    Uses existing OneRoster sync infrastructure — ClassLink's Roster Server
    exposes OneRoster 1.1 endpoints.
    """
    import threading

    def _bg_sync():
        try:
            from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config
            from backend.roster_sync import sync_roster_to_db

            config = get_oneroster_config(teacher_id)
            if not config.get('base_url'):
                logger.info("No OneRoster config for %s, skipping post-login roster sync", teacher_id)
                return

            import asyncio
            client = OneRosterClient(
                base_url=config['base_url'],
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                token_url=config.get('token_url'),
            )
            loop = asyncio.new_event_loop()
            try:
                raw = loop.run_until_complete(client.fetch_roster(
                    school_id=config.get('school_id'),
                    teacher_sourced_id=config.get('teacher_sourced_id'),
                ))
            finally:
                loop.close()

            normalized = normalize_roster(raw)
            sync_roster_to_db(
                normalized['classes'], normalized['students'],
                normalized['enrollments'], teacher_id, provider="classlink"
            )
            logger.info("Post-login ClassLink roster sync complete for %s", teacher_id)
        except Exception as e:
            logger.warning("Post-login ClassLink roster sync failed for %s: %s", teacher_id, e)

    thread = threading.Thread(target=_bg_sync, daemon=True)
    thread.start()


# ── GET /api/classlink/login-url ──────────────────────────────────────

@classlink_bp.route('/api/classlink/login-url', methods=['GET'])
def classlink_login_url():
    """Return ClassLink OAuth authorization URL with CSRF state token."""
    client_id, _, redirect_uri = _get_classlink_config()
    if not client_id:
        return jsonify({"error": "ClassLink SSO is not configured"}), 400

    state = secrets.token_urlsafe(32)
    session['classlink_oauth_state'] = state

    params = urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': CLASSLINK_SCOPES,
        'state': state,
    })
    return jsonify({"url": f"{CLASSLINK_AUTH_URL}?{params}"})


# ── GET /api/classlink/callback ───────────────────────────────────────

@classlink_bp.route('/api/classlink/callback', methods=['GET'])
def classlink_callback():
    """Handle ClassLink OAuth callback — exchange code for token, fetch user."""
    error = request.args.get('error')
    if error:
        return redirect(f"/?classlink_error={error}")

    code = request.args.get('code')
    if not code:
        return redirect("/?classlink_error=no_code")

    # Validate CSRF state
    state = request.args.get('state', '')
    expected_state = session.pop('classlink_oauth_state', '')
    if expected_state and state != expected_state:
        logger.warning("ClassLink OAuth state mismatch: got %s, expected %s", state, expected_state)
        return redirect("/?classlink_error=state_mismatch")

    client_id, client_secret, redirect_uri = _get_classlink_config()

    # Exchange code for token
    try:
        token_resp = requests.post(CLASSLINK_TOKEN_URL, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }, timeout=15)

        if token_resp.status_code != 200:
            logger.error("ClassLink token exchange failed: %s %s",
                         token_resp.status_code, token_resp.text[:200])
            return redirect("/?classlink_error=token_failed")

        access_token = token_resp.json().get('access_token')
        if not access_token:
            return redirect("/?classlink_error=no_token")

    except Exception as e:
        logger.exception("ClassLink token exchange error: %s", e)
        return redirect("/?classlink_error=token_error")

    # Fetch user info
    try:
        user_resp = requests.get(CLASSLINK_USERINFO_URL, headers={
            'Authorization': f'Bearer {access_token}',
        }, timeout=15)

        if user_resp.status_code != 200:
            logger.error("ClassLink user info failed: %s", user_resp.status_code)
            return redirect("/?classlink_error=userinfo_failed")

        user_data = user_resp.json()
    except Exception as e:
        logger.exception("ClassLink user info error: %s", e)
        return redirect("/?classlink_error=userinfo_error")

    classlink_id = str(user_data.get('UserId', ''))
    first_name = user_data.get('FirstName', '')
    last_name = user_data.get('LastName', '')
    email = user_data.get('Email', '')
    role = (user_data.get('Role') or '').lower()
    tenant_id = str(user_data.get('TenantId', ''))

    # Student login → redirect to student portal
    if role == 'student':
        session['classlink_student'] = {
            'classlink_id': classlink_id,
            'name': f"{first_name} {last_name}",
            'email': email,
            'tenant_id': tenant_id,
        }
        return redirect("/student?classlink_login=success")

    # Teacher/admin login
    session.clear()
    session.permanent = True

    session['classlink_user'] = {
        'classlink_id': classlink_id,
        'email': email,
        'name': {'first': first_name, 'last': last_name},
        'type': role or 'teacher',
        'tenant_id': tenant_id,
    }

    # Link to existing Graider account by email
    _link_classlink_account(classlink_id, email)

    # Resolve teacher_id for roster sync
    teacher_id = _resolve_classlink_user_id(classlink_id)

    # Background roster sync (if OneRoster configured)
    _trigger_roster_sync(teacher_id, tenant_id)

    from backend.utils.audit import audit_log
    audit_log("CLASSLINK_LOGIN", f"ClassLink SSO login: {email}",
              user="teacher", teacher_id=teacher_id)

    return redirect("/?classlink_login=success")


# ── GET /api/classlink/session ────────────────────────────────────────

@classlink_bp.route('/api/classlink/session', methods=['GET'])
def classlink_session():
    """Check ClassLink session status."""
    cl_user = session.get('classlink_user')
    if not cl_user:
        return jsonify({"authenticated": False})

    return jsonify({
        "authenticated": True,
        "classlink_id": cl_user.get('classlink_id'),
        "email": cl_user.get('email'),
        "name": cl_user.get('name'),
        "type": cl_user.get('type'),
        "tenant_id": cl_user.get('tenant_id'),
    })


# ── POST /api/classlink/logout ────────────────────────────────────────

@classlink_bp.route('/api/classlink/logout', methods=['POST'])
def classlink_logout():
    """Clear ClassLink session."""
    session.pop('classlink_user', None)
    session.pop('classlink_student', None)
    return jsonify({"status": "logged_out"})
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_classlink_sso.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/classlink_routes.py tests/test_classlink_sso.py
git commit -m "feat: add ClassLink OAuth2/OIDC SSO routes"
```

---

### Task 2: Register blueprint and add auth resolution

**Files:**
- Modify: `backend/routes/__init__.py`
- Modify: `backend/auth.py`

- [ ] **Step 1: Register the ClassLink blueprint**

In `backend/routes/__init__.py`, add the import after the Clever import:

```python
from .classlink_routes import classlink_bp
```

And add registration after the last `app.register_blueprint`:

```python
    app.register_blueprint(classlink_bp)
```

- [ ] **Step 2: Add ClassLink session resolution to auth.py**

In `backend/auth.py`, find the section where Clever sessions are resolved (search for `clever_user = session.get('clever_user')`). Add a similar block immediately after for ClassLink:

```python
    # ClassLink SSO session
    classlink_user = session.get('classlink_user')
    if classlink_user and not has_bearer:
        from backend.routes.classlink_routes import _resolve_classlink_user_id
        g.user_id = _resolve_classlink_user_id(classlink_user['classlink_id'])
        g.teacher_id = g.user_id
        g.user_email = classlink_user.get('email', '')
        g.auth_source = 'classlink'
        g.district_id = classlink_user.get('tenant_id', '')
        return None
```

- [ ] **Step 3: Verify the app starts**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -c "from backend.routes.classlink_routes import classlink_bp; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run all ClassLink + auth tests**

```bash
python -m pytest tests/test_classlink_sso.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/__init__.py backend/auth.py
git commit -m "feat: register ClassLink blueprint, add session resolution to auth"
```

---

### Task 3: Add "Login with ClassLink" button to frontend

**Files:**
- Modify: `frontend/src/components/LoginScreen.jsx`

- [ ] **Step 1: Find the Clever login button**

Search `LoginScreen.jsx` for the "Log in with Clever" button. It should look something like:

```javascript
<button onClick={async () => {
  const resp = await fetch('/api/clever/login-url');
  const data = await resp.json();
  if (data.url) window.location.href = data.url;
}}>
  Log in with Clever
</button>
```

- [ ] **Step 2: Add a ClassLink login button after the Clever button**

Add a similar button right after the Clever one:

```javascript
<button
  onClick={async () => {
    try {
      var resp = await fetch('/api/classlink/login-url');
      var data = await resp.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError('ClassLink login not configured');
      }
    } catch (err) {
      setError('Could not connect to ClassLink');
    }
  }}
  className="btn"
  style={{
    padding: "12px 24px",
    background: "linear-gradient(135deg, #1a73e8, #4285f4)",
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    justifyContent: "center",
    fontSize: "0.95rem",
    fontWeight: 600,
  }}
>
  Log in with ClassLink
</button>
```

- [ ] **Step 3: Handle ClassLink login success in the URL params**

Search for where `clever_login=success` is detected in the URL params (likely in `App.jsx` or `LoginScreen.jsx`). Add the same check for `classlink_login=success`:

```javascript
// Existing:
if (params.get('clever_login') === 'success') { ... }

// Add after:
if (params.get('classlink_login') === 'success') {
  // Same logic as clever_login success — set authenticated state
}
```

Also handle `classlink_error`:
```javascript
if (params.get('classlink_error')) {
  setError('ClassLink login failed: ' + params.get('classlink_error'));
}
```

- [ ] **Step 4: Build frontend**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```

Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/components/LoginScreen.jsx frontend/src/App.jsx
git commit -m "feat: add Login with ClassLink button to login screen"
```

---

### Task 4: Update documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add ClassLink env vars to CLAUDE.md**

In `CLAUDE.md`, find the `### Clever Integration` env vars section and add after it:

```markdown
### ClassLink SSO
- `CLASSLINK_CLIENT_ID` — OAuth client ID (from ClassLink developer portal)
- `CLASSLINK_CLIENT_SECRET` — OAuth client secret
- `CLASSLINK_REDIRECT_URI` — OAuth callback URL (defaults to `https://app.graider.live/api/classlink/callback`)
```

- [ ] **Step 2: Add ClassLink API endpoints to the API Reference**

Add to the API Reference section:

```markdown
### ClassLink SSO
- `GET /api/classlink/login-url` — Get ClassLink OAuth URL
- `GET /api/classlink/callback` — OAuth callback (ClassLink redirects here)
- `GET /api/classlink/session` — Check ClassLink session status
- `POST /api/classlink/logout` — Clear ClassLink session
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add ClassLink SSO endpoints and env vars to CLAUDE.md"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | ClassLink routes blueprint + 9 tests | Create `classlink_routes.py`, `test_classlink_sso.py` | Low — new files, mirrors Clever pattern |
| 2 | Blueprint registration + auth resolution | Modify `__init__.py`, `auth.py` | Low — append only |
| 3 | "Login with ClassLink" button | Modify `LoginScreen.jsx`, `App.jsx` | Low — adds button alongside Clever |
| 4 | Documentation | Modify `CLAUDE.md` | None |

**Total: 1 new blueprint, 4 endpoints, 9 tests, 1 login button.**

**Before:** Teachers in ClassLink districts can't SSO into Graider — they have to create a separate account.
**After:** Teacher clicks the Graider tile in ClassLink LaunchPad → lands in Graider authenticated with roster sync triggered.

**Post-deploy steps:**
1. Verify `CLASSLINK_CLIENT_ID` and `CLASSLINK_CLIENT_SECRET` are set in Railway
2. Test with sandbox account: log in at `https://launchpad.classlink.com/cltest` as T4957-0005
3. Click the Graider tile (needs to be added to the test LaunchPad)
4. Verify redirect to `app.graider.live` with session created
5. Verify `GET /api/classlink/session` returns authenticated=true

**Testing with the "Login with ClassLink" button (before LaunchPad tile is configured):**
1. Go to `app.graider.live`
2. Click "Login with ClassLink"
3. Redirects to ClassLink login page
4. Log in with test teacher account T4957-0005
5. Redirects back to Graider with session
