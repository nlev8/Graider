# District Admin Setup Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a password-protected `/district` setup page where district IT admins configure SIS credentials (Clever or OneRoster/ClassLink) and AI API keys in one place, eliminating the need for env vars and simplifying the teacher OneRoster experience to a single "SIS Teacher ID" field.

**Architecture:** New `backend/routes/district_routes.py` for admin auth + config endpoints. New `frontend/src/components/DistrictSetup.jsx` standalone page. Modify `get_oneroster_config()` and `get_clever_config()` to check district-level storage between per-teacher and env vars. Simplify `SettingsTab.jsx` OneRoster section when district config detected. All config stored in existing `teacher_data` table with `teacher_id="system"`.

**Tech Stack:** Flask/Python backend, `werkzeug.security` for password hashing, Flask sessions for admin auth, React frontend (inline styles), Supabase `teacher_data` for persistence.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/routes/district_routes.py` | CREATE | `/api/district/*` endpoints: auth, config CRUD, connection test, public status |
| `backend/routes/__init__.py` | MODIFY | Register `district_bp` blueprint |
| `backend/auth.py` | MODIFY | Add `/api/district/` to `PUBLIC_PREFIXES` |
| `backend/oneroster.py` | MODIFY | Add district-level config to resolution chain in `get_oneroster_config()` |
| `backend/clever.py` | MODIFY | Add district-level config to resolution chain in `get_clever_config()` |
| `backend/api_keys.py` | MODIFY | Add district storage fallback to `_load_district_keys()` |
| `backend/app.py` | MODIFY | Add `/district` SPA route |
| `frontend/src/components/DistrictSetup.jsx` | CREATE | Standalone district admin setup page |
| `frontend/src/App.jsx` | MODIFY | Route `/district` to DistrictSetup component |
| `frontend/src/tabs/SettingsTab.jsx` | MODIFY | Simplified OneRoster UI when district config detected |
| `frontend/src/services/api.js` | MODIFY | Add district API functions |
| `tests/test_district_routes.py` | CREATE | Backend tests for district endpoints |

---

## Task 1: District Routes — Backend

**Files:**
- Create: `backend/routes/district_routes.py`
- Create: `tests/test_district_routes.py`
- Modify: `backend/routes/__init__.py`
- Modify: `backend/auth.py`
- Modify: `backend/app.py`

- [ ] **Step 1: Create `backend/routes/district_routes.py`**

```python
"""
District admin setup routes for Graider.

Provides a password-protected configuration interface for district IT admins
to set up SIS credentials (Clever or OneRoster/ClassLink) and AI API keys.

All district config is stored in teacher_data with teacher_id="system".
Auth uses Flask sessions — no Supabase account needed for district admin.
"""
import logging
import os

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from backend.utils.errors import handle_route_errors

logger = logging.getLogger(__name__)

district_bp = Blueprint("district", __name__)

SYSTEM_TEACHER_ID = "system"


def _require_district_admin(f):
    """Decorator that enforces district admin session."""
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("district_admin"):
            return jsonify({"error": "District admin authentication required"}), 401
        return f(*args, **kwargs)

    return wrapper


def _get_district_password_hash():
    """Load the stored district admin password hash, or None if not set.

    If DISTRICT_ADMIN_PASSWORD env var is set but no hash is stored yet,
    persist the hash from the env var so the admin can later change/rotate
    the password via the UI without keeping the env var.
    """
    try:
        from backend.storage import load, save
        data = load("district_password", SYSTEM_TEACHER_ID)
        if data and isinstance(data, dict) and data.get("hash"):
            return data["hash"]
    except Exception:
        pass

    # Bootstrap from env var — persist hash so UI can rotate it later
    env_pw = os.getenv("DISTRICT_ADMIN_PASSWORD")
    if env_pw:
        hashed = generate_password_hash(env_pw)
        try:
            from backend.storage import save
            save("district_password", {"hash": hashed}, SYSTEM_TEACHER_ID)
            logger.info("Persisted district admin password from env var")
        except Exception:
            pass
        return hashed
    return None


# ── Auth ─────────────────────────────────────────────────────────────────

@district_bp.route("/api/district/auth", methods=["POST"])
@handle_route_errors
def district_auth():
    """Authenticate as district admin.

    Body: {"password": "..."}
    On first use (no password set): {"password": "...", "setup": true} creates the password.
    """
    data = request.json or {}
    password = data.get("password", "")

    if not password:
        return jsonify({"error": "Password required"}), 400

    stored_hash = _get_district_password_hash()

    # First-time setup: no password exists yet
    if stored_hash is None:
        if data.get("setup"):
            if len(password) < 8:
                return jsonify({"error": "Password must be at least 8 characters"}), 400
            from backend.storage import save
            save("district_password", {"hash": generate_password_hash(password)}, SYSTEM_TEACHER_ID)
            session["district_admin"] = True
            logger.info("District admin password created")

            from backend.utils.audit import audit_log
            audit_log("DISTRICT_SETUP", "District admin password created")

            return jsonify({"status": "created", "authenticated": True})
        else:
            return jsonify({"needs_setup": True, "authenticated": False})

    # Validate password
    if check_password_hash(stored_hash, password):
        session["district_admin"] = True
        logger.info("District admin authenticated")
        return jsonify({"authenticated": True})

    return jsonify({"error": "Invalid password"}), 403


@district_bp.route("/api/district/auth", methods=["DELETE"])
def district_logout():
    """Clear district admin session."""
    session.pop("district_admin", None)
    return jsonify({"status": "logged_out"})


@district_bp.route("/api/district/change-password", methods=["POST"])
@_require_district_admin
@handle_route_errors
def change_password():
    """Change the district admin password.

    Body: {"current_password": "...", "new_password": "..."}
    """
    data = request.json or {}
    current = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not current or not new_pw:
        return jsonify({"error": "current_password and new_password required"}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    stored_hash = _get_district_password_hash()
    if not stored_hash or not check_password_hash(stored_hash, current):
        return jsonify({"error": "Current password is incorrect"}), 403

    from backend.storage import save
    save("district_password", {"hash": generate_password_hash(new_pw)}, SYSTEM_TEACHER_ID)

    from backend.utils.audit import audit_log
    audit_log("DISTRICT_PASSWORD_CHANGED", "District admin password changed")

    return jsonify({"status": "changed"})


# ── Public status (no auth) ─────────────────────────────────────────────

@district_bp.route("/api/district/config-status", methods=["GET"])
@handle_route_errors
def district_config_status():
    """Public endpoint: returns what SIS provider is configured (no secrets).

    Teachers check this to know whether to show simplified OneRoster UI.
    """
    try:
        from backend.storage import load
        sis_config = load("district_sis_config", SYSTEM_TEACHER_ID)
        ai_keys = load("district_ai_keys", SYSTEM_TEACHER_ID)
    except Exception:
        sis_config = None
        ai_keys = None

    sis_provider = None
    if sis_config and isinstance(sis_config, dict):
        sis_provider = sis_config.get("sis_type")

    return jsonify({
        "sis_provider": sis_provider,
        "has_ai_keys": bool(ai_keys and any(ai_keys.get(k) for k in ("openai", "anthropic", "gemini"))),
    })


# ── Config (requires district admin) ────────────────────────────────────

@district_bp.route("/api/district/config", methods=["GET"])
@_require_district_admin
@handle_route_errors
def get_district_config():
    """Load full district config (SIS + AI keys). Never returns raw secrets."""
    from backend.storage import load

    sis_config = load("district_sis_config", SYSTEM_TEACHER_ID) or {}
    ai_keys = load("district_ai_keys", SYSTEM_TEACHER_ID) or {}

    # Mask secrets
    safe_sis = {
        "sis_type": sis_config.get("sis_type"),
    }

    sis_type = sis_config.get("sis_type")
    if sis_type == "oneroster":
        safe_sis["base_url"] = sis_config.get("base_url", "")
        safe_sis["client_id"] = sis_config.get("client_id", "")
        safe_sis["has_secret"] = bool(sis_config.get("client_secret"))
        safe_sis["token_url"] = sis_config.get("token_url", "")
        safe_sis["school_id"] = sis_config.get("school_id", "")
    elif sis_type == "clever":
        safe_sis["client_id"] = sis_config.get("client_id", "")
        safe_sis["has_secret"] = bool(sis_config.get("client_secret"))
        safe_sis["redirect_uri"] = sis_config.get("redirect_uri", "")
        safe_sis["has_district_token"] = bool(sis_config.get("district_token"))

    safe_ai = {
        "has_openai": bool(ai_keys.get("openai")),
        "has_anthropic": bool(ai_keys.get("anthropic")),
        "has_gemini": bool(ai_keys.get("gemini")),
    }

    return jsonify({"sis": safe_sis, "ai_keys": safe_ai})


@district_bp.route("/api/district/config", methods=["POST"])
@_require_district_admin
@handle_route_errors
def save_district_config():
    """Save district SIS config and/or AI keys.

    Body: {
        "sis": {
            "sis_type": "oneroster" | "clever",
            // OneRoster fields:
            "base_url": "...", "client_id": "...", "client_secret": "...",
            "token_url": "...", "school_id": "...",
            // Clever fields:
            "client_id": "...", "client_secret": "...",
            "redirect_uri": "...", "district_token": "..."
        },
        "ai_keys": {
            "openai": "sk-...", "anthropic": "sk-ant-...", "gemini": "AI..."
        }
    }
    """
    from backend.storage import load, save
    data = request.json or {}

    # Save SIS config
    sis_data = data.get("sis")
    if sis_data:
        sis_type = sis_data.get("sis_type", "")
        if sis_type not in ("clever", "oneroster"):
            return jsonify({"error": "sis_type must be 'clever' or 'oneroster'"}), 400

        # Merge: keep existing secret if new one is blank
        existing = load("district_sis_config", SYSTEM_TEACHER_ID) or {}
        config = {"sis_type": sis_type}

        # Secret merge rules:
        # - Non-empty string: overwrite with new value
        # - Empty string "": keep existing value (no change)
        # - Explicit null: clear the field (set to "")
        def _merge_secret(new_val, existing_val):
            if new_val is None:
                return ""  # Explicit null = clear
            val = new_val.strip() if isinstance(new_val, str) else ""
            return val if val else existing_val

        if sis_type == "oneroster":
            config["base_url"] = sis_data.get("base_url", "").strip()
            config["client_id"] = sis_data.get("client_id", "").strip()
            config["client_secret"] = _merge_secret(sis_data.get("client_secret"), existing.get("client_secret", ""))
            config["token_url"] = sis_data.get("token_url", "").strip()
            config["school_id"] = sis_data.get("school_id", "").strip()

            if not config["base_url"] or not config["client_id"]:
                return jsonify({"error": "base_url and client_id are required"}), 400
            if not config["client_secret"]:
                return jsonify({"error": "client_secret is required (send null to clear)"}), 400

        elif sis_type == "clever":
            config["client_id"] = sis_data.get("client_id", "").strip()
            config["client_secret"] = _merge_secret(sis_data.get("client_secret"), existing.get("client_secret", ""))
            config["redirect_uri"] = sis_data.get("redirect_uri", "").strip()
            config["district_token"] = _merge_secret(sis_data.get("district_token"), existing.get("district_token", ""))

            if not config["client_id"]:
                return jsonify({"error": "client_id is required"}), 400
            if not config["client_secret"]:
                return jsonify({"error": "client_secret is required (send null to clear)"}), 400

        save("district_sis_config", config, SYSTEM_TEACHER_ID)

    # Save AI keys (merge — blank strings are ignored, explicit null deletes)
    # To clear a key: send {"ai_keys": {"openai": null}}
    # To leave unchanged: omit the key or send empty string
    ai_data = data.get("ai_keys")
    if ai_data:
        existing_ai = load("district_ai_keys", SYSTEM_TEACHER_ID) or {}
        for provider in ("openai", "anthropic", "gemini"):
            if provider not in ai_data:
                continue
            val = ai_data[provider]
            if val is None:
                # Explicit null = delete this key
                existing_ai.pop(provider, None)
            elif isinstance(val, str) and val.strip():
                existing_ai[provider] = val.strip()
            # Empty string = no change (keep existing)
        save("district_ai_keys", existing_ai, SYSTEM_TEACHER_ID)

    from backend.utils.audit import audit_log
    audit_log("DISTRICT_CONFIG_SAVED", "District configuration updated")

    return jsonify({"status": "saved"})


# ── Connection test ──────────────────────────────────────────────────────

@district_bp.route("/api/district/test-connection", methods=["POST"])
@_require_district_admin
@handle_route_errors
def test_district_connection():
    """Test SIS connectivity with saved district credentials."""
    from backend.storage import load

    sis_config = load("district_sis_config", SYSTEM_TEACHER_ID)
    if not sis_config:
        return jsonify({"error": "No SIS configured"}), 400

    sis_type = sis_config.get("sis_type")

    if sis_type == "oneroster":
        from backend.oneroster import OneRosterClient
        import asyncio

        client = OneRosterClient(
            base_url=sis_config["base_url"],
            client_id=sis_config["client_id"],
            client_secret=sis_config["client_secret"],
            token_url=sis_config.get("token_url"),
        )

        async def _test():
            async with __import__("httpx").AsyncClient(timeout=15.0) as http:
                await client._ensure_token(http)
                body = await client._get_with_retry(
                    http,
                    f"{client.base_url}/classes?limit=1&offset=0",
                    "test",
                )
                return body is not None

        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(_test())
        finally:
            loop.close()

        if success:
            return jsonify({"status": "connected", "sis_type": "oneroster"})
        return jsonify({"error": "Could not reach OneRoster API"}), 502

    elif sis_type == "clever":
        # Test Clever by checking if the credentials can get a token
        import httpx
        from base64 import b64encode

        try:
            auth_str = b64encode(
                f"{sis_config['client_id']}:{sis_config['client_secret']}".encode()
            ).decode()
            # We can't fully test Clever without an auth code,
            # but we can verify the credentials format is valid
            return jsonify({
                "status": "configured",
                "sis_type": "clever",
                "note": "Clever credentials saved. Teachers can now use 'Log in with Clever'.",
            })
        except Exception as e:
            return jsonify({"error": f"Invalid Clever credentials: {e}"}), 400

    return jsonify({"error": f"Unknown SIS type: {sis_type}"}), 400
```

- [ ] **Step 2: Register blueprint in `backend/routes/__init__.py`**

Add after the `lti_routes` import:

```python
from .district_routes import district_bp
```

In `register_routes()`:

```python
app.register_blueprint(district_bp)
```

In `__all__`:

```python
'district_bp',
```

- [ ] **Step 3: Add district routes to public prefixes in `backend/auth.py`**

Add to `PUBLIC_PREFIXES` list (around line 65-69):

```python
'/api/district/',          # District admin setup (own auth via session password)
```

- [ ] **Step 4: Add `/district` SPA route in `backend/app.py`**

Add before the catch-all `/<path:path>` route (around line 3417):

```python
@app.route('/district')
@app.route('/district/')
def serve_district_setup():
    """Serve React app for district admin setup."""
    return send_from_directory(app.static_folder, 'index.html')
```

- [ ] **Step 5: Create `tests/test_district_routes.py`**

```python
"""Tests for district admin setup routes."""
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    import sys
    sys.path.insert(0, '.')
    from backend.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestDistrictAuth:
    def test_auth_without_password_returns_400(self, client):
        resp = client.post("/api/district/auth",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_auth_needs_setup_when_no_password_exists(self, client):
        with patch("backend.routes.district_routes._get_district_password_hash", return_value=None):
            resp = client.post("/api/district/auth",
                               data=json.dumps({"password": "test123"}),
                               content_type="application/json")
            data = resp.get_json()
            assert data.get("needs_setup") is True

    def test_auth_rejects_wrong_password(self, client):
        from werkzeug.security import generate_password_hash
        mock_hash = generate_password_hash("correct-password")
        with patch("backend.routes.district_routes._get_district_password_hash", return_value=mock_hash):
            resp = client.post("/api/district/auth",
                               data=json.dumps({"password": "wrong-password"}),
                               content_type="application/json")
            assert resp.status_code == 403


class TestDistrictConfigStatus:
    def test_config_status_is_public(self, client):
        resp = client.get("/api/district/config-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sis_provider" in data
        assert "has_ai_keys" in data

    def test_config_status_returns_null_when_unconfigured(self, client):
        resp = client.get("/api/district/config-status")
        data = resp.get_json()
        assert data["sis_provider"] is None


class TestDistrictConfig:
    def test_get_config_requires_admin(self, client):
        resp = client.get("/api/district/config")
        assert resp.status_code == 401

    def test_save_config_requires_admin(self, client):
        resp = client.post("/api/district/config",
                           data=json.dumps({"sis": {"sis_type": "oneroster"}}),
                           content_type="application/json")
        assert resp.status_code == 401

    def test_save_config_validates_sis_type(self, client):
        with client.session_transaction() as sess:
            sess["district_admin"] = True
        resp = client.post("/api/district/config",
                           data=json.dumps({"sis": {"sis_type": "invalid"}}),
                           content_type="application/json")
        assert resp.status_code == 400
```

- [ ] **Step 6: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_district_routes.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/routes/district_routes.py backend/routes/__init__.py backend/auth.py backend/app.py tests/test_district_routes.py
git commit -m "feat: add district admin setup routes (auth, config, SIS test, public status)"
```

---

## Task 2: Config Resolution — Wire District Storage into Existing Providers

**Files:**
- Modify: `backend/oneroster.py`
- Modify: `backend/clever.py`
- Modify: `backend/api_keys.py`

- [ ] **Step 1: Add district-level fallback to `get_oneroster_config()` in `backend/oneroster.py`**

Find `get_oneroster_config` (line 279). Between the per-teacher check and the env var fallback, add district-level storage check:

```python
def get_oneroster_config(teacher_id=None):
    """Load OneRoster configuration.

    Resolution order:
    1. Per-teacher config (from Supabase storage)
    2. District-level config (from district admin setup page)
    3. Environment variables

    Returns dict with base_url, client_id, client_secret, token_url, school_id
    or None if not configured.
    """
    # 1. Try per-teacher config from storage
    if teacher_id:
        try:
            from backend.storage import load
            stored = load("oneroster_config", teacher_id)
            if stored and stored.get("base_url") and stored.get("client_id"):
                return {
                    "base_url": stored.get("base_url"),
                    "client_id": stored.get("client_id"),
                    "client_secret": stored.get("client_secret"),
                    "token_url": stored.get("token_url"),
                    "school_id": stored.get("school_id"),
                    "teacher_sourced_id": stored.get("teacher_sourced_id"),
                }
        except Exception as e:
            logger.debug("Could not load per-teacher OneRoster config: %s", e)

    # 2. Try district-level config (set by district admin at /district)
    try:
        from backend.storage import load
        district_sis = load("district_sis_config", "system")
        if district_sis and district_sis.get("sis_type") == "oneroster":
            if district_sis.get("base_url") and district_sis.get("client_id"):
                # District config provides credentials; teacher_sourced_id comes from
                # the teacher's own settings (they only enter this one field).
                teacher_sourced_id = None
                if teacher_id:
                    try:
                        teacher_sis = load("oneroster_teacher_id", teacher_id)
                        if teacher_sis and isinstance(teacher_sis, dict):
                            teacher_sourced_id = teacher_sis.get("teacher_sourced_id")
                    except Exception:
                        pass
                return {
                    "base_url": district_sis.get("base_url"),
                    "client_id": district_sis.get("client_id"),
                    "client_secret": district_sis.get("client_secret"),
                    "token_url": district_sis.get("token_url"),
                    "school_id": district_sis.get("school_id"),
                    "teacher_sourced_id": teacher_sourced_id,
                    "_source": "district",
                }
    except Exception as e:
        logger.debug("Could not load district OneRoster config: %s", e)

    # 3. Fall back to environment variables
    base_url = os.getenv("ONEROSTER_BASE_URL")
    client_id = os.getenv("ONEROSTER_CLIENT_ID")
    client_secret = os.getenv("ONEROSTER_CLIENT_SECRET")

    if not base_url or not client_id or not client_secret:
        return None

    return {
        "base_url": base_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": os.getenv("ONEROSTER_TOKEN_URL"),
        "school_id": os.getenv("ONEROSTER_SCHOOL_ID"),
        "teacher_sourced_id": None,
    }
```

- [ ] **Step 2: Add district-level fallback to `get_clever_config()` in `backend/clever.py`**

Replace the existing `get_clever_config` function (line 33):

```python
def get_clever_config():
    """Return Clever credentials.

    Resolution order:
    1. District-level config (from district admin setup page)
    2. Environment variables
    """
    # 1. Try district-level config
    try:
        from backend.storage import load
        district_sis = load("district_sis_config", "system")
        if district_sis and district_sis.get("sis_type") == "clever":
            client_id = district_sis.get("client_id")
            client_secret = district_sis.get("client_secret")
            redirect_uri = district_sis.get("redirect_uri") or os.getenv("CLEVER_REDIRECT_URI")
            if client_id and client_secret and redirect_uri:
                return {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "district_token": district_sis.get("district_token", ""),
                }
    except Exception:
        pass

    # 2. Fall back to environment variables
    client_id = os.getenv("CLEVER_CLIENT_ID")
    client_secret = os.getenv("CLEVER_CLIENT_SECRET")
    redirect_uri = os.getenv("CLEVER_REDIRECT_URI")
    if not all([client_id, client_secret, redirect_uri]):
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
```

- [ ] **Step 3: Add district storage fallback to `api_keys.py`**

In `backend/api_keys.py`, modify the `get_api_key` function. After the district_id check (step 3, around line 75) and before the env var fallback (step 4), add:

```python
    # 3b. Check district-level keys from district admin setup page
    try:
        from backend.storage import load as _storage_load
        district_ai = _storage_load("district_ai_keys", "system")
        if district_ai:
            val = district_ai.get(provider, '')
            if val:
                return val
    except Exception:
        pass
```

Also update `resolve_keys_for_teacher` (line 101) similarly — add after `district_keys` lookup and before env var:

```python
    # District admin setup keys
    try:
        from backend.storage import load as _storage_load
        district_admin_keys = _storage_load("district_ai_keys", "system") or {}
    except Exception:
        district_admin_keys = {}

    resolved = {}
    for provider, env_var in _ENV_MAP.items():
        resolved[provider] = (
            user_keys.get(provider, '')
            or district_keys.get(provider, '')
            or district_admin_keys.get(provider, '')
            or os.getenv(env_var, '')
        )
    return resolved
```

- [ ] **Step 4: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_clever_compliance.py tests/test_oneroster.py tests/test_roster_sync.py -v`
Expected: All pass (no regressions)

- [ ] **Step 5: Commit**

```bash
git add backend/oneroster.py backend/clever.py backend/api_keys.py
git commit -m "feat: wire district-level config into OneRoster, Clever, and API key resolution"
```

---

## Task 3: Frontend — District Setup Page

**Files:**
- Create: `frontend/src/components/DistrictSetup.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Add API functions in `frontend/src/services/api.js`**

Add after the LTI API functions:

```javascript
// District Admin Setup
export async function districtAuth(password, setup) {
  return fetchApi('/api/district/auth', {
    method: 'POST',
    body: JSON.stringify({ password: password, setup: setup || false }),
  })
}

export async function districtLogout() {
  return fetchApi('/api/district/auth', { method: 'DELETE' })
}

export async function getDistrictConfig() {
  return fetchApi('/api/district/config')
}

export async function saveDistrictConfig(config) {
  return fetchApi('/api/district/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function testDistrictConnection() {
  return fetchApi('/api/district/test-connection', { method: 'POST' })
}

export async function getDistrictConfigStatus() {
  return fetchApi('/api/district/config-status')
}
```

Add all six to the default export object.

- [ ] **Step 2: Create `frontend/src/components/DistrictSetup.jsx`**

Standalone page — NOT part of the teacher dashboard. Centered card with Graider logo.

**Structure:**
1. **Login gate**: password field. If no password exists (`needs_setup: true`), show "Create District Admin Password" with confirm field. Otherwise show "Enter District Admin Password".
2. **After auth — three sections in one scrollable card:**

**Section 1: SIS Provider**
- Toggle: "Clever" / "OneRoster" radio buttons
- **Clever selected**: Client ID, Client Secret (password field), Redirect URI, District Token (optional)
- **OneRoster selected**: Base URL, Client ID, Client Secret (password field), Token URL (optional), School ID (optional)
- Preset buttons for OneRoster: "ClassLink", "PowerSchool", "Infinite Campus" — pre-fill base URL patterns
- "Test Connection" button (OneRoster only — Clever can't be tested without a user)
- Status badge: "Connected" / "Not configured"

**Section 2: AI API Keys (optional)**
- OpenAI, Anthropic, Gemini key fields (password type, show/hide toggle)
- Helper text: "Teachers can override with their own keys"
- Show "Saved" badge for each key that has a stored value

**Section 3: Done**
- Summary of what's configured
- "Teachers can now log in and sync their roster from Settings > Classroom"
- "Log Out" button (clears district admin session)

**CRITICAL CODE STYLE RULES:**
- NO template literals (backticks) — use string concatenation
- Use `var` not `const` or `let`
- Use inline styles
- Use `useState`, `useEffect` from React

- [ ] **Step 3: Add `/district` route to `frontend/src/App.jsx`**

In the `App()` function, add before the existing `/student` check (around line 750):

```javascript
  if (window.location.pathname.startsWith("/district")) {
    return <DistrictSetup />;
  }
```

Add import at the top of the file:

```javascript
import DistrictSetup from "./components/DistrictSetup";
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DistrictSetup.jsx frontend/src/App.jsx frontend/src/services/api.js
git commit -m "feat: add district admin setup page at /district with SIS + AI key config"
```

---

## Task 4: Simplified Teacher OneRoster UI

**Files:**
- Modify: `frontend/src/tabs/SettingsTab.jsx`

- [ ] **Step 1: Add district config status detection**

Add state variable alongside existing OneRoster state (around line 143):

```javascript
var [districtSisProvider, setDistrictSisProvider] = useState(null);
```

In the existing classroom useEffect (where OneRoster config loads), add:

```javascript
api.getDistrictConfigStatus().then(function(data) {
  setDistrictSisProvider(data.sis_provider || null);
}).catch(function() {});
```

- [ ] **Step 2: Add simplified OneRoster view when district config exists**

In the OneRoster Integration Section (around line 1832), wrap the existing full form in a conditional. When `districtSisProvider === 'oneroster'`, show the simplified view instead:

**Simplified view:**
- Header: "Roster Sync" with green "District configured" badge
- Helper text: "Your district has set up OneRoster. Enter your SIS Teacher ID to sync your roster."
- **One field**: "SIS Teacher ID" — text input with placeholder "Ask your school admin for your OneRoster teacher sourcedId"
- **"Sync Roster" button** — saves teacher_sourced_id via `api.saveOneRosterConfig({teacher_sourced_id: value})` then calls `api.syncOneRosterRoster()`
- On success: shows class/student/enrollment counts

**The save for the simplified view** uses a new lightweight endpoint or reuses existing. The teacher_sourced_id is saved via:
```javascript
api.saveOneRosterConfig({ teacher_sourced_id: teacherSisId })
```
But since district config provides the credentials, `saveOneRosterConfig` needs to accept just the teacher_sourced_id. Actually, we should use a dedicated save for just this field:

In `api.js`, add:
```javascript
export async function saveOneRosterTeacherId(teacherSourcedId) {
  return fetchApi('/api/oneroster/teacher-id', {
    method: 'POST',
    body: JSON.stringify({ teacher_sourced_id: teacherSourcedId }),
  })
}
```

In `backend/routes/oneroster_routes.py`, add a new endpoint:
```python
@oneroster_bp.route("/api/oneroster/teacher-id", methods=["POST"])
@require_teacher
@handle_route_errors
def save_teacher_id():
    """Save just the teacher's OneRoster sourcedId (used with district-level config)."""
    data = request.json or {}
    teacher_sourced_id = data.get("teacher_sourced_id", "").strip()
    if not teacher_sourced_id:
        return jsonify({"error": "teacher_sourced_id is required"}), 400

    from backend.storage import save
    save("oneroster_teacher_id", {"teacher_sourced_id": teacher_sourced_id}, g.teacher_id)
    return jsonify({"status": "saved"})
```

**When no district config** (`districtSisProvider !== 'oneroster'`): show the existing full 6-field form unchanged.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Run all tests**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tabs/SettingsTab.jsx frontend/src/services/api.js backend/routes/oneroster_routes.py
git commit -m "feat: simplified OneRoster teacher UI when district config exists (one field)"
```

---

## Task 5: Documentation & Full Verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add district endpoints to CLAUDE.md**

Find the "API Reference" section. After "LTI 1.3 Integration" subsection, add:

```markdown
### District Admin Setup
- `POST /api/district/auth` — Authenticate as district admin (password)
- `DELETE /api/district/auth` — Clear district admin session
- `GET /api/district/config-status` — Public: check if SIS/AI keys configured
- `GET /api/district/config` — Load full district config (admin auth required)
- `POST /api/district/config` — Save SIS + AI key config (admin auth required)
- `POST /api/district/test-connection` — Test SIS connectivity (admin auth required)
- `POST /api/oneroster/teacher-id` — Save teacher's OneRoster sourcedId (teacher auth)
```

Find "Environment Variables" section. After "LTI 1.3 Integration" subsection, add:

```markdown
### District Admin
- `DISTRICT_ADMIN_PASSWORD` — Initial district admin password (optional, can be set via /district first-time setup instead)
```

- [ ] **Step 2: Run full backend test suite**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`
Expected: No new failures

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 4: Run full Playwright E2E suite**

Run: `cd frontend && npx playwright test --reporter=dot --workers=1`
Expected: All existing tests pass

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add district admin endpoints and env vars to CLAUDE.md"
```

---

## Implementation Notes

### Storage Keys

| Key | teacher_id | Purpose |
|-----|-----------|---------|
| `district_password` | `system` | Hashed admin password |
| `district_sis_config` | `system` | SIS type + credentials (Clever or OneRoster) |
| `district_ai_keys` | `system` | District-level API keys |
| `oneroster_teacher_id` | `{teacher_uuid}` | Teacher's OneRoster sourcedId only |

### Config Resolution Chain

**OneRoster:** per-teacher config → district SIS config + teacher sourcedId → env vars
**Clever:** district SIS config → env vars
**API Keys:** per-teacher → Clever district keys → district admin keys → env vars

### No Conflict with Existing Systems

- District config uses `teacher_id="system"` — no overlap with per-teacher storage
- Existing env var fallbacks still work (backward compatible)
- Clever districts already using env vars continue working
- Teachers who configured OneRoster manually (full 6-field form) keep their per-teacher config (it takes priority over district config)

### Security

- Password hashed with `werkzeug.security.generate_password_hash` (bcrypt-based)
- Admin session via Flask cookie (encrypted by `FLASK_SECRET_KEY`, expires with browser)
- SIS credentials never returned in plaintext from GET endpoints (`has_secret: true/false`)
- `/api/district/config-status` is intentionally public but reveals only SIS type, no secrets
- All config changes audit-logged
