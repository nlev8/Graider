# Clever Integration Guide — Graider

## Overview

Clever provides SSO and roster syncing for 100,000+ K-12 schools. Integrating Clever gives Graider:

1. **District SSO** — Teachers log in via Clever (one-click, no separate password)
2. **Secure Sync** — Student rosters, class periods, IEP/504 status, and ELL status auto-sync from the district's Student Information System (SIS)

Both certifications are submitted together. Review takes 1-2 weeks after submission.

**Cost:** Free for app partners. Clever charges districts, not apps.

---

## What Changes vs. What Stays

### Unchanged (entire product)
- Grading engine, AI pipeline, all 18 grading factors
- Assessment/lesson/unit plan generation
- Builder, Planner, Results, Analytics, Settings tabs
- Accommodation presets and grading behavior
- Student portal (publish, join, submit, grade)
- Calendar, automations, exports
- Stripe billing
- Supabase auth (remains as fallback for non-Clever schools)

### New/Modified

| File | Change |
|------|--------|
| `backend/clever.py` | **NEW** — Clever OAuth + API client (~250 lines) |
| `backend/routes/clever_routes.py` | **NEW** — Clever auth + sync + roster persistence (~200 lines) |
| `backend/routes/__init__.py` | Register `clever_bp` in `register_routes()` (~3 lines) |
| `backend/auth.py` | Add Clever session validation + public prefix + approval gate fix (~25 lines) |
| `backend/routes/stripe_routes.py` | Guard Supabase admin calls from Clever user IDs (~15 lines) |
| `backend/app.py` | Add `Flask-Session` config for Redis in production (~10 lines) |
| `frontend/src/services/api.js` | Add Clever methods + guard `getAuthHeaders` for Clever users (~50 lines) |
| `frontend/src/components/LoginScreen.jsx` | Add "Log in with Clever" button (~25 lines) |
| `frontend/src/App.jsx` | Handle Clever OAuth redirect (~20 lines) |
| `requirements.txt` | Add `Flask-Session`, `redis` |
| `.env` | Add Clever credentials (dev + prod) |

**Total: ~560 lines of new code, ~90 lines of edits to existing files (across 7 files).**

---

## Caveats Addressed

This plan addresses every concern from the architecture review:

### 1. Blueprint Registration
`clever_bp` is registered via `backend/routes/__init__.py` → `register_routes()`, the same pattern as all 18 existing blueprints. NOT in `app.py` directly.

### 2. Session Store (Production)
Flask's default cookie-based sessions won't survive multiple Railway workers. The plan uses `Flask-Session` with Redis in production (Railway provides Redis add-on). Cookie sessions remain for local dev.

### 3. Supabase Coexistence (5 integration points identified)

The frontend ONLY uses Supabase for auth (`supabase.auth.*`) — no direct DB/storage/realtime calls. All data flows through `fetchApi` → Flask. **RLS is a non-issue.** But these 5 backend/frontend patterns need Clever-awareness:

**3a. `api.js` `getAuthHeaders()` (line 14-19)** — Calls `supabase.auth.getSession()` on every request. For Clever users, returns null → empty headers → backend relies on session cookie instead. But the 401 retry logic could fire and dispatch `auth-expired`. **Fix:** Check `user.id.startsWith('clever:')` before retrying Supabase auth.

**3b. `auth.py` approval gate (line 142-162)** — Calls `sb.auth.admin.get_user_by_id(g.user_id)`. For Clever users, `g.user_id` is `clever:abc123` (not a Supabase UUID) → crash. **Fix:** Skip approval gate entirely for Clever users — they're district-approved by definition.

**3c. `stripe_routes.py` `_get_user_metadata` (line 31-37)** — Same `get_user_by_id` crash. **Fix:** Add `_is_clever_user()` check alongside existing `_is_local_dev()` check.

**3d. `stripe_routes.py` `_get_or_create_customer` (line 48)** — Stripe needs a real customer. Clever users who want billing need a Supabase account linked. **Fix:** For now, return 503 "Stripe not available for Clever accounts" — district billing is handled differently (invoiced, not per-teacher Stripe).

**3e. `storage.py` teacher_id keying** — Uses `g.user_id` as key. `clever:abc123` works as a string key in both file and Supabase backends. No change needed, but worth noting the key format differs.

**Frontend:** User object shape matches Supabase's `{ id, email, user_metadata: { name, approved } }` so all existing components work.

### 4. Roster Persistence
`clever_sync_roster` doesn't just return JSON — it writes students to `ROSTERS_DIR` as CSV (same format as manual upload) and sections to `PERIODS_DIR` as JSON (same format as manual period creation). Existing roster/period consumers see no difference.

### 5. District Token Management
`CLEVER_DISTRICT_TOKEN` is per-district. For multi-district support (future), tokens are stored in Supabase keyed by district ID. For the demo/single-district pilot, a single env var suffices.

### 6. Frontend API Consistency
Clever methods are added to `api.js` using the existing `fetchApi` wrapper — not a separate `clever.js` file. This ensures auth headers, error handling, 401 retry logic, and the `account-not-approved` flow all work consistently.

### 7. Environment Parity
`.env` has separate redirect URIs for dev vs prod. `CLEVER_CLIENT_ID` and `CLEVER_CLIENT_SECRET` are the same across environments (Clever allows multiple redirect URIs per app). `CLEVER_DISTRICT_TOKEN` differs per district/environment.

---

## Clever API Reference

### Endpoints

| Purpose | URL |
|---------|-----|
| Authorization | `https://clever.com/oauth/authorize` |
| Token exchange | `https://clever.com/oauth/tokens` |
| OpenID discovery | `https://clever.com/.well-known/openid-configuration` |
| User info (OIDC) | `https://api.clever.com/userinfo` |
| Current user | `https://api.clever.com/v3.1/me` |
| Users | `https://api.clever.com/v3.1/users` |
| Schools | `https://api.clever.com/v3.1/schools` |
| Sections | `https://api.clever.com/v3.1/sections` |

### Student Data Fields (from Secure Sync)

Standard fields:
- `id` — Clever user ID (primary identifier)
- `name.first`, `name.last`
- `email`
- `roles.student.grade`
- `roles.student.school`, `roles.student.schools`
- `roles.student.sis_id`, `roles.student.student_number`

**Sensitive fields (require Secure Sync + opt-in in Clever dashboard):**
- `roles.student.iep_status` — IEP flag (yes/no)
- `roles.student.ell_status` — English Language Learner status
- `roles.student.frl_status` — Free/Reduced Lunch status
- `roles.student.home_language` — Home language (ISO 639-3)
- `roles.student.race`, `roles.student.hispanic_ethnicity`

### OAuth Flow

1. Redirect teacher to: `https://clever.com/oauth/authorize?response_type=code&redirect_uri={URI}&client_id={ID}&state={CSRF_TOKEN}`
2. Clever redirects back with `?code=AUTH_CODE&state={CSRF_TOKEN}`
3. Backend validates state, exchanges code for access token via POST to `https://clever.com/oauth/tokens` (Basic auth: base64 client_id:client_secret)
4. Use token to call `/v3.1/me` → get user identity (Clever ID, type, district)
5. Use token to call `/v3.1/users/{id}` → get full profile (name, email, roles)
6. Use district-app token (from Clever dashboard) for roster sync via `/v3.1/users` + `/v3.1/sections`

---

## Precise Code Edits

### 1. NEW FILE: `backend/clever.py`

```python
"""
Clever OAuth + API client for Graider.
Handles SSO authentication and Secure Sync roster/IEP data.
"""
import csv
import io
import json
import os
import logging
from urllib.parse import urlencode
from base64 import b64encode

import httpx

logger = logging.getLogger(__name__)

CLEVER_AUTH_URL = "https://clever.com/oauth/authorize"
CLEVER_TOKEN_URL = "https://clever.com/oauth/tokens"
CLEVER_API_BASE = "https://api.clever.com"
CLEVER_API_VERSION = "v3.1"

# Graider data directories (same as settings_routes.py)
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
ROSTERS_DIR = os.path.join(GRAIDER_DATA_DIR, "rosters")
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")


def get_clever_config():
    """Return Clever credentials from environment."""
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


def get_authorize_url(state=None):
    """Build the Clever OAuth authorization URL."""
    config = get_clever_config()
    if not config:
        return None
    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
    }
    if state:
        params["state"] = state
    return f"{CLEVER_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code):
    """Exchange an authorization code for an access token.

    Returns dict with 'access_token' or None on failure.
    """
    config = get_clever_config()
    if not config:
        return None

    # Clever requires Basic auth: base64(client_id:client_secret)
    credentials = b64encode(
        f"{config['client_id']}:{config['client_secret']}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                CLEVER_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                },
                json={
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": config["redirect_uri"],
                },
            )
            if resp.status_code != 200:
                logger.error("Clever token exchange failed: %s %s", resp.status_code, resp.text)
                return None
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Clever token exchange error: %s", str(e))
            return None


async def get_clever_user(access_token):
    """Fetch the current user's identity from Clever.

    Returns dict with user info: {clever_id, type, name, email, district} or None.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # Step 1: Get user identity from /me
            resp = await client.get(
                f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error("Clever /me failed: %s", resp.status_code)
                return None
            me_data = resp.json().get("data", {})

            user_id = me_data.get("id")
            user_type = me_data.get("type")  # "teacher", "student", "district_admin"

            # Step 2: Get full user profile
            resp2 = await client.get(
                f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/users/{user_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp2.status_code != 200:
                logger.error("Clever user fetch failed: %s", resp2.status_code)
                return None
            user_data = resp2.json().get("data", {})

            return {
                "clever_id": user_id,
                "type": user_type,
                "name": user_data.get("name", {}),
                "email": user_data.get("email", ""),
                "district": user_data.get("district", ""),
                "roles": user_data.get("roles", {}),
            }
        except httpx.HTTPError as e:
            logger.error("Clever user fetch error: %s", str(e))
            return None


async def sync_roster(district_token):
    """Sync full roster from Clever using a district-app token.

    Returns dict: { "teachers": [...], "students": [...], "sections": [...] }
    """
    headers = {"Authorization": f"Bearer {district_token}"}
    result = {"teachers": [], "students": [], "sections": []}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch all users (paginated)
        for user_type in ["teachers", "students"]:
            url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/users?role={user_type[:-1]}"
            while url:
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        logger.error("Clever roster fetch (%s) failed: %s", user_type, resp.status_code)
                        break
                    body = resp.json()
                    result[user_type].extend(body.get("data", []))
                    # Pagination: follow 'next' link
                    url = _next_page_url(body)
                except httpx.HTTPError as e:
                    logger.error("Clever roster fetch error (%s): %s", user_type, str(e))
                    break

        # Fetch sections (class periods)
        url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/sections"
        while url:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    break
                body = resp.json()
                result["sections"].extend(body.get("data", []))
                url = _next_page_url(body)
            except httpx.HTTPError as e:
                logger.error("Clever sections fetch error: %s", str(e))
                break

    logger.info(
        "Clever roster sync: %d teachers, %d students, %d sections",
        len(result["teachers"]), len(result["students"]), len(result["sections"]),
    )
    return result


def _next_page_url(body):
    """Extract the next page URL from a Clever API response."""
    for link in body.get("links", []):
        if link.get("rel") == "next":
            url = link.get("uri")
            if url and not url.startswith("http"):
                return f"{CLEVER_API_BASE}{url}"
            return url
    return None


def extract_student_accommodations(students):
    """Convert Clever student data into Graider accommodation mappings.

    Returns dict keyed by Clever student ID:
    {
        "abc123": {
            "name": "First Last",
            "iep_status": True,
            "ell_status": True,
            "home_language": "Spanish",
            "suggested_presets": ["simplified_language", "ell_support", ...],
        }
    }
    """
    accommodations = {}

    for student in students:
        data = student.get("data", student)  # Handle both wrapped and unwrapped
        roles = data.get("roles", {})
        student_role = roles.get("student", {})
        name = data.get("name", {})
        student_id = data.get("id", "")

        iep_status = student_role.get("iep_status", "")
        ell_status = student_role.get("ell_status", "")
        home_language = student_role.get("home_language", "")

        has_iep = str(iep_status).strip().lower() in ("y", "yes", "true", "active")
        has_ell = str(ell_status).strip().lower() in ("y", "yes", "true", "active")

        if not has_iep and not has_ell:
            continue

        # Suggest default presets based on flags
        suggested = []
        if has_iep:
            suggested.extend(["simplified_language", "modified_expectations", "extra_encouragement"])
        if has_ell:
            suggested.append("ell_support")

        accommodations[student_id] = {
            "name": f"{name.get('first', '')} {name.get('last', '')}".strip(),
            "iep_status": has_iep,
            "ell_status": has_ell,
            "home_language": home_language,
            "suggested_presets": suggested,
        }

    return accommodations


def map_sections_to_periods(sections):
    """Convert Clever sections into Graider class periods.

    Returns list of period dicts matching existing period format.
    """
    periods = []
    for section in sections:
        data = section.get("data", section)
        periods.append({
            "clever_section_id": data.get("id", ""),
            "name": data.get("name", ""),
            "subject": data.get("subject", ""),
            "grade": data.get("grade", ""),
            "teacher_clever_ids": data.get("teachers", []),
            "student_clever_ids": data.get("students", []),
            "period": data.get("period", ""),
            "term_id": data.get("term_id", ""),
        })
    return periods


def persist_roster_as_csv(students, teacher_id="local-dev"):
    """Write Clever students to ROSTERS_DIR as CSV, matching manual upload format.

    Creates a file named 'clever_roster_{teacher_id}.csv' with columns:
    student_id, first_name, last_name, email, grade, iep_status, ell_status
    """
    os.makedirs(ROSTERS_DIR, exist_ok=True)
    filename = f"clever_roster_{teacher_id}.csv"
    filepath = os.path.join(ROSTERS_DIR, filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "first_name", "last_name", "email", "grade", "iep_status", "ell_status"])
        for student in students:
            data = student.get("data", student)
            name = data.get("name", {})
            roles = data.get("roles", {})
            sr = roles.get("student", {})
            writer.writerow([
                data.get("id", ""),
                name.get("first", ""),
                name.get("last", ""),
                data.get("email", ""),
                sr.get("grade", ""),
                sr.get("iep_status", ""),
                sr.get("ell_status", ""),
            ])

    # Write metadata file (same format as manual upload)
    metadata = {
        "filename": filename,
        "filepath": filepath,
        "headers": ["student_id", "first_name", "last_name", "email", "grade", "iep_status", "ell_status"],
        "row_count": len(students),
        "source": "clever",
        "column_mapping": {
            "student_id": "student_id",
            "first_name": "first_name",
            "last_name": "last_name",
        },
    }
    meta_path = os.path.join(ROSTERS_DIR, f"{filename}.meta.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Persisted Clever roster: %s (%d students)", filepath, len(students))
    return filepath


def persist_sections_as_periods(sections, teacher_id="local-dev"):
    """Write Clever sections to PERIODS_DIR as JSON, matching manual period format.

    Creates one JSON file per section in the same format as manual period creation.
    """
    os.makedirs(PERIODS_DIR, exist_ok=True)
    periods = map_sections_to_periods(sections)

    for period in periods:
        section_id = period.get("clever_section_id", "unknown")
        filename = f"clever_{section_id}.json"
        filepath = os.path.join(PERIODS_DIR, filename)

        # Build student list for this section
        student_names = []  # Populated during apply step when teacher confirms
        period_data = {
            "name": period.get("name", f"Period {period.get('period', '?')}"),
            "subject": period.get("subject", ""),
            "grade": period.get("grade", ""),
            "source": "clever",
            "clever_section_id": section_id,
            "students": period.get("student_clever_ids", []),
        }

        with open(filepath, "w") as f:
            json.dump(period_data, f, indent=2)

        # Write metadata
        meta = {
            "filename": filename,
            "filepath": filepath,
            "headers": ["name"],
            "row_count": len(period.get("student_clever_ids", [])),
            "source": "clever",
        }
        meta_path = os.path.join(PERIODS_DIR, f"{filename}.meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    logger.info("Persisted %d Clever sections as periods", len(periods))
    return periods
```

---

### 2. NEW FILE: `backend/routes/clever_routes.py`

```python
"""
Clever SSO and Secure Sync routes.
"""
import os
import asyncio
import logging
import secrets

from flask import Blueprint, request, jsonify, redirect, session, g

from backend.clever import (
    get_clever_config,
    get_authorize_url,
    exchange_code_for_token,
    get_clever_user,
    sync_roster,
    extract_student_accommodations,
    persist_roster_as_csv,
    persist_sections_as_periods,
)
from backend.accommodations import set_student_accommodation

logger = logging.getLogger(__name__)

clever_bp = Blueprint("clever", __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@clever_bp.route("/api/clever/login-url", methods=["GET"])
def clever_login_url():
    """Return the Clever OAuth authorization URL."""
    config = get_clever_config()
    if not config:
        return jsonify({"error": "Clever not configured"}), 503

    state = secrets.token_urlsafe(32)
    session["clever_oauth_state"] = state
    url = get_authorize_url(state=state)
    return jsonify({"url": url})


@clever_bp.route("/api/clever/callback", methods=["GET"])
def clever_callback():
    """Handle the OAuth redirect from Clever.

    Exchanges the authorization code for a token, fetches the user
    profile, and creates a Graider session.
    """
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        logger.warning("Clever OAuth error: %s", error)
        return redirect(f"/?clever_error={error}")

    if not code:
        return redirect("/?clever_error=missing_code")

    # Validate state parameter (CSRF protection)
    expected_state = session.pop("clever_oauth_state", None)
    if expected_state and state != expected_state:
        logger.warning("Clever OAuth state mismatch")
        return redirect("/?clever_error=state_mismatch")

    # Exchange code for token
    token_data = _run_async(exchange_code_for_token(code))
    if not token_data or "access_token" not in token_data:
        return redirect("/?clever_error=token_exchange_failed")

    access_token = token_data["access_token"]

    # Fetch user identity
    clever_user = _run_async(get_clever_user(access_token))
    if not clever_user:
        return redirect("/?clever_error=user_fetch_failed")

    # Only allow teachers and district admins
    if clever_user["type"] not in ("teacher", "district_admin", "staff"):
        return redirect("/?clever_error=students_use_portal")

    # Store Clever session info
    session["clever_user"] = {
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user["type"],
        "district": clever_user.get("district", ""),
        # Do NOT store access_token in session — it's short-lived
        # and only needed for the initial user fetch
    }

    logger.info("Clever SSO login: %s (%s)", clever_user.get("email"), clever_user["type"])
    return redirect("/?clever_login=success")


@clever_bp.route("/api/clever/session", methods=["GET"])
def clever_session_check():
    """Return current Clever session info (if logged in via Clever)."""
    clever_user = session.get("clever_user")
    if not clever_user:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user.get("type", ""),
        "district": clever_user.get("district", ""),
    })


@clever_bp.route("/api/clever/sync-roster", methods=["POST"])
def clever_sync_roster():
    """Trigger a roster sync from Clever.

    Pulls students and sections, persists them to ROSTERS_DIR and PERIODS_DIR
    (same format as manual CSV upload), and returns accommodation suggestions.
    """
    district_token = os.getenv("CLEVER_DISTRICT_TOKEN")
    if not district_token:
        return jsonify({"error": "District token not configured"}), 503

    teacher_id = getattr(g, "user_id", "local-dev")

    roster = _run_async(sync_roster(district_token))

    # Persist roster to CSV (same location as manual upload)
    students = roster.get("students", [])
    if students:
        persist_roster_as_csv(students, teacher_id)

    # Persist sections as periods (same location as manual period creation)
    sections = roster.get("sections", [])
    if sections:
        persist_sections_as_periods(sections, teacher_id)

    # Extract accommodation suggestions (teacher reviews before applying)
    accomm_data = extract_student_accommodations(students)

    return jsonify({
        "status": "synced",
        "counts": {
            "teachers": len(roster.get("teachers", [])),
            "students": len(students),
            "sections": len(sections),
            "students_with_accommodations": len(accomm_data),
        },
        "accommodation_suggestions": accomm_data,
    })


@clever_bp.route("/api/clever/apply-accommodations", methods=["POST"])
def clever_apply_accommodations():
    """Apply Clever-sourced IEP/ELL flags as Graider accommodation presets.

    The teacher has reviewed and optionally modified the suggestions.
    Body: {
        "accommodations": {
            "student_clever_id": {
                "name": "Jane Doe",
                "suggested_presets": ["simplified_language", "ell_support"],
                "custom_notes": "",
                "home_language": "Spanish",
            },
            ...
        }
    }
    """
    data = request.json or {}
    accommodations = data.get("accommodations", {})
    teacher_id = getattr(g, "user_id", "local-dev")

    applied = 0
    errors = []

    for student_id, info in accommodations.items():
        preset_ids = info.get("suggested_presets", [])
        name = info.get("name", "")
        custom_notes = info.get("custom_notes", "")

        if info.get("ell_status") and info.get("home_language"):
            custom_notes += f"\nHome language: {info['home_language']}"

        try:
            success = set_student_accommodation(
                student_id=student_id,
                preset_ids=preset_ids,
                custom_notes=custom_notes.strip(),
                student_name=name,
                teacher_id=teacher_id,
            )
            if success:
                applied += 1
            else:
                errors.append(f"Failed to save for {student_id}")
        except Exception as e:
            logger.error("Error applying accommodation for %s: %s", student_id, str(e))
            errors.append(f"Error for {student_id}: {str(e)}")

    return jsonify({
        "applied": applied,
        "total": len(accommodations),
        "errors": errors if errors else None,
    })


@clever_bp.route("/api/clever/logout", methods=["POST"])
def clever_logout():
    """Clear the Clever session."""
    session.pop("clever_user", None)
    return jsonify({"status": "logged_out"})
```

---

### 3. EDIT: `backend/routes/__init__.py`

**Add clever_bp import and registration (same pattern as all other blueprints):**

```python
# --- ADD to imports (after line 29, with the other imports) ---
from .clever_routes import clever_bp

# --- ADD inside register_routes() (after line 58, with the other registrations) ---
    app.register_blueprint(clever_bp)

# --- ADD to __all__ list ---
    'clever_bp',
```

---

### 4. EDIT: `backend/auth.py`

**Add `/api/clever/` to PUBLIC_PREFIXES (line 18):**

```python
# --- REPLACE existing PUBLIC_PREFIXES ---
PUBLIC_PREFIXES = [
    '/api/student/',       # Student portal (public, students don't have accounts)
    '/api/clever/',        # Clever OAuth flow (callback must be unauthenticated)
]
```

**Add Clever session validation to `check_auth()` (after line 118, before `# Skip non-API routes`):**

```python
# --- EXISTING (line 113-118) ---
        is_dev = os.getenv('FLASK_ENV', '').lower() in ('development', 'dev')
        if is_dev and host in ('localhost', '127.0.0.1') and not has_bearer:
            g.user_id = request.headers.get('X-Test-Teacher-Id',
                                            os.getenv('DEV_USER_ID', 'local-dev'))
            g.user_email = os.getenv('DEV_EMAIL', 'dev@localhost')
            return None

# --- ADD THIS BLOCK (after line 118) ---
        # Clever SSO session (cookie-based, set during OAuth callback)
        clever_user = session.get('clever_user') if hasattr(session, 'get') else None
        if clever_user and not has_bearer:
            g.user_id = f"clever:{clever_user['clever_id']}"
            g.user_email = clever_user.get('email', '')
            g.auth_source = 'clever'
            return None

# --- EXISTING (line 120) ---
        # Skip non-API routes (static files, index.html, etc.)
```

**Add `session` import at the top of the file:**

```python
# --- ADD to imports (line 10) ---
from flask import request, jsonify, g, session
```

**Fix approval gate to skip Clever users (line 142-162). The approval gate calls `sb.auth.admin.get_user_by_id(g.user_id)` which crashes for Clever IDs:**

```python
# --- REPLACE the approval gate block (line 142-162) ---
        # Approval gate — skip for the approval-status endpoint itself
        if request.path != '/api/auth/approval-status':
            # Clever users are district-approved by definition — skip gate
            if getattr(g, 'auth_source', None) == 'clever':
                return None

            user_meta = payload.get('user_metadata', {})
            if not user_meta.get('approved'):
                # JWT metadata may be stale — check Supabase admin API as fallback
                try:
                    sb = _get_supabase()
                    if sb:
                        res = sb.auth.admin.get_user_by_id(g.user_id)
                        fresh_meta = (res.user.user_metadata or {}) if res and res.user else {}
                        if fresh_meta.get('approved'):
                            logger.info("User %s approved via admin API fallback (stale JWT)", g.user_email)
                            return None  # Allow request
                except Exception as e:
                    logger.warning("Admin API approval fallback failed: %s", str(e))

                return jsonify({
                    'error': 'Account pending approval',
                    'code': 'NOT_APPROVED',
                }), 403
```

---

### 4b. EDIT: `backend/routes/stripe_routes.py`

**Guard Supabase admin API calls from Clever user IDs. These functions call `sb.auth.admin.get_user_by_id(user_id)` which crashes if `user_id` starts with `clever:`.**

```python
# --- ADD helper function after _is_local_dev() (line 28) ---
def _is_clever_user():
    """Check if the current user is authenticated via Clever (not Supabase)."""
    return getattr(g, 'user_id', '').startswith('clever:')


# --- MODIFY _get_user_metadata (line 31-37) ---
def _get_user_metadata(user_id):
    """Fetch user_metadata from Supabase auth.users for the given user."""
    if _is_local_dev() or _is_clever_user():
        return {}
    sb = _get_supabase()
    res = sb.auth.admin.get_user_by_id(user_id)
    return res.user.user_metadata or {}


# --- MODIFY _update_user_metadata (line 40-45) ---
def _update_user_metadata(user_id, metadata_update):
    """Merge metadata_update into the user's user_metadata."""
    if _is_local_dev() or _is_clever_user():
        return
    sb = _get_supabase()
    sb.auth.admin.update_user_by_id(user_id, {"user_metadata": metadata_update})


# --- MODIFY subscription_status() to handle Clever users (line 72-105) ---
# Add at the top of the function body:
    if _is_clever_user():
        return jsonify({
            "status": "district",
            "message": "District-managed account (billing handled by district)",
        })
```

---

### 4c. EDIT: `frontend/src/services/api.js`

**Prevent `getAuthHeaders()` from triggering Supabase session checks for Clever users. The 401 retry logic and `auth-expired` event can log out Clever users.**

```javascript
// --- REPLACE getAuthHeaders (lines 14-20) ---
/**
 * Get authorization headers with current session token.
 * Returns empty headers for Clever users (auth is via session cookie).
 */
export async function getAuthHeaders() {
  // Clever users don't have Supabase sessions — skip entirely
  // (the browser sends the session cookie automatically)
  const currentUser = window.__graiderUser;
  if (currentUser && currentUser.id && currentUser.id.startsWith('clever:')) {
    return {}
  }
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    return { 'Authorization': 'Bearer ' + session.access_token }
  }
  return {}
}
```

**Also in App.jsx, store user reference on window so api.js can check it:**

```javascript
// --- In App.jsx, inside the setUser wrapper function (line 766-773) ---
// ADD after _setUser(u):
  function setUser(u) {
    if (u == null && !logoutIntentRef.current) {
      console.warn('Blocked automatic setUser(null)');
      return;
    }
    logoutIntentRef.current = false;
    _setUser(u);
    window.__graiderUser = u;  // ← ADD THIS LINE — lets api.js detect Clever users
  }
```

**And prevent `auth-expired` from firing for Clever users (in the 401 handling, ~line 59-61):**

```javascript
// --- REPLACE the auth-expired dispatch (line 59-61) ---
      // Still no valid session after waiting — truly expired
      // Don't fire for Clever users (they don't use Supabase sessions)
      if (!(currentUser && currentUser.id && currentUser.id.startsWith('clever:'))) {
        window.dispatchEvent(new Event('auth-expired'))
      }
      throw new Error('Session expired. Please log in again.')
```

---

### 5. EDIT: `backend/app.py`

**Add Flask-Session configuration for production (near app creation, before `init_auth`):**

```python
# --- ADD after app = Flask(...) and before init_auth(app) ---

# Session configuration — Redis in production, filesystem locally
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-in-production')
if os.getenv('REDIS_URL'):
    # Production: server-side sessions via Redis (survives multi-worker)
    from flask_session import Session
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_KEY_PREFIX'] = 'graider:'
    import redis
    app.config['SESSION_REDIS'] = redis.from_url(os.getenv('REDIS_URL'))
    Session(app)
else:
    # Local dev: default cookie-based sessions (fine for single worker)
    pass
```

**Do NOT register clever_bp in app.py — it's registered via `register_routes()` in `routes/__init__.py`.**

---

### 6. EDIT: `frontend/src/services/api.js`

**Add Clever methods at the end of the file, using the existing `fetchApi` wrapper:**

```javascript
// ── Clever SSO & Sync ──────────────────────────────────────

/** Get the Clever OAuth login URL. */
export async function getCleverLoginUrl() {
  return fetchApi('/api/clever/login-url')
}

/** Check if user has an active Clever session. */
export async function getCleverSession() {
  return fetchApi('/api/clever/session')
}

/** Trigger a roster sync from Clever. Returns counts + accommodation suggestions. */
export async function syncCleverRoster() {
  return fetchApi('/api/clever/sync-roster', { method: 'POST' })
}

/** Apply teacher-reviewed accommodation suggestions from Clever sync. */
export async function applyCleverAccommodations(accommodations) {
  return fetchApi('/api/clever/apply-accommodations', {
    method: 'POST',
    body: JSON.stringify({ accommodations }),
  })
}

/** Log out of Clever session. */
export async function cleverLogout() {
  return fetchApi('/api/clever/logout', { method: 'POST' })
}
```

---

### 7. EDIT: `frontend/src/components/LoginScreen.jsx`

**Add "Log in with Clever" button after the Microsoft OAuth button (after line 316, before `</>`):**

```jsx
{/* --- EXISTING: closing </div> of social auth buttons (line 316) --- */}
          </div>

{/* --- ADD THIS BLOCK --- */}
          {/* Clever SSO */}
          <button onClick={async () => {
            setError('');
            try {
              const resp = await fetch('/api/clever/login-url');
              const data = await resp.json();
              if (data.url) {
                window.location.href = data.url;
              } else {
                setError('Clever login not configured for this server');
              }
            } catch (err) {
              setError('Could not connect to Clever');
            }
          }}
            style={{
              width: '100%',
              marginTop: '12px',
              padding: '12px',
              borderRadius: '12px',
              border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
              background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              color: isDark ? 'white' : '#1e293b',
              fontSize: '0.9rem',
              fontWeight: 500,
              fontFamily: 'inherit',
            }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="#4274F6"/>
              <path d="M15.5 8.5L12 12l-3.5-3.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
              <path d="M12 12v5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Log in with Clever
          </button>

{/* --- EXISTING: </> closing fragment (line 318) --- */}
```

---

### 8. EDIT: `frontend/src/App.jsx`

**Handle Clever OAuth redirect. Add inside the `useEffect` at line 790 (the auth init effect), BEFORE the `if (isLocalhost)` block:**

```javascript
  // Check for Clever login redirect (before localhost check — works everywhere)
  const urlParams = new URLSearchParams(window.location.search);
  const cleverLogin = urlParams.get('clever_login');
  const cleverError = urlParams.get('clever_error');

  if (cleverLogin === 'success') {
    // Clever OAuth completed — fetch session and set user
    fetch('/api/clever/session')
      .then(function(r) { return r.json() })
      .then(function(data) {
        if (data.authenticated) {
          // Shape matches Supabase user object so existing components work
          _setUser({
            id: 'clever:' + data.clever_id,
            email: data.email,
            user_metadata: {
              name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''),
              approved: true,  // Clever users are district-approved by definition
            },
          });
          setAuthLoading(false);
        }
      })
      .catch(function(err) { console.error('Clever session check failed:', err) });
    window.history.replaceState({}, '', '/');
    return; // Skip normal Supabase auth init
  }
  if (cleverError) {
    console.error('Clever login error:', cleverError);
    window.history.replaceState({}, '', '/');
    // Fall through to normal login screen
  }

  // --- EXISTING: if (isLocalhost) { ... } ---
```

**Also update the logout function to clear Clever session (find the existing logout handler):**

```javascript
// --- Inside the existing logout/handleLogout function, ADD before Supabase signOut: ---
  // Clear Clever session if present
  if (user && user.id && user.id.startsWith('clever:')) {
    fetch('/api/clever/logout', { method: 'POST' }).catch(function() {});
  }
```

---

### 9. EDIT: `.env`

```bash
# ── Clever Integration ────────────────────────────────────
# Get credentials from https://apps.clever.com/dashboard

CLEVER_CLIENT_ID=
CLEVER_CLIENT_SECRET=

# Dev redirect URI (localhost)
CLEVER_REDIRECT_URI=http://localhost:3000/api/clever/callback

# District-app token (created when a district shares data with your app)
# Per-district — get from sandbox for testing, production for live
CLEVER_DISTRICT_TOKEN=

# Flask session secret (CSRF protection for OAuth state)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
FLASK_SECRET_KEY=

# Redis URL for production sessions (Railway provides this)
# Leave blank for local dev (uses cookie sessions)
# REDIS_URL=redis://...
```

**Production `.env` (Railway):**

```bash
CLEVER_REDIRECT_URI=https://app.graider.live/api/clever/callback
REDIS_URL=redis://...  # From Railway Redis add-on
FLASK_SECRET_KEY=<generated-secret>
```

---

### 10. EDIT: `requirements.txt`

**Add (verify httpx already present):**

```
Flask-Session>=0.5.0
redis>=5.0.0
```

---

## Certification Checklist

### Pre-Submission Requirements

- [ ] Sign up at [https://apps.clever.com](https://apps.clever.com)
- [ ] Complete Clever Academy training (free, online)
- [ ] Configure app in Clever dashboard:
  - Set redirect URI(s): `http://localhost:3000/api/clever/callback` + `https://app.graider.live/api/clever/callback`
  - Set supported user types: Teachers, District Admins, Staff
  - Enable sensitive data scopes (IEP status, ELL status) in Data Access tab
- [ ] Get sandbox district credentials for testing

### District SSO Requirements

- [ ] OAuth authorization grant flow with CSRF state parameter
- [ ] Use Clever ID as primary user identifier
- [ ] Support UTF-8 characters in names (ñ, é, etc.)
- [ ] Handle shared devices (override existing session on new auth)
- [ ] Show clear indication of logged-in account
- [ ] Show friendly error screen on login failure (redirect with `clever_error`)
- [ ] Provide "Log Out" button that clears Clever session
- [ ] HTTPS on redirect URI (production)
- [ ] Test in Chrome, Firefox, Safari, Mobile Safari, Mobile Chrome

### Secure Sync Requirements

- [ ] Use Clever ID as primary identifier for all data types
- [ ] Use API v3.1
- [ ] Roster persisted to ROSTERS_DIR as CSV (same format as manual upload)
- [ ] Sections persisted to PERIODS_DIR as JSON (same format as manual periods)
- [ ] Archive records when data is unshared/deleted in Clever
- [ ] Restore records if Clever ID reappears
- [ ] Preserve student-teacher associations via sections
- [ ] Handle missing (non-required) data fields gracefully (`.get()` everywhere)
- [ ] Support co-teachers (multiple teacher IDs per section)
- [ ] Test against Certification ISD dataset (5 schools with edge cases)

### Submission

District SSO + Secure Sync submit together:
1. Contact your Clever Application Success Manager
2. They respond within 5 business days
3. Review takes 1-2 weeks after submission

---

## Data Flow After Integration

```
District SIS (PowerSchool, Infinite Campus, etc.)
    ↓ (automatic nightly sync)
Clever Platform
    ↓ (Secure Sync API — district-app token)
backend/clever.py → sync_roster()
    ↓
┌──────────────────────────────────────────────────────┐
│ Students → ROSTERS_DIR/clever_roster_{id}.csv        │
│            (same format as manual CSV upload)         │
│                                                       │
│ Sections → PERIODS_DIR/clever_{section_id}.json      │
│            (same format as manual period creation)    │
│                                                       │
│ IEP/ELL  → accommodation_suggestions (returned JSON) │
│            Teacher reviews → apply-accommodations     │
│            → existing set_student_accommodation()     │
└──────────────────────────────────────────────────────┘
    ↓
Existing Graider systems (no changes needed)
    ↓
Grading pipeline uses accommodations as before
```

**Key design decisions:**
1. Clever roster writes to the same directories as manual CSV upload — existing roster consumers see no difference.
2. Accommodation suggestions require teacher review before applying — FERPA compliant, teacher stays in control.
3. Clever session coexists with Supabase auth — user object shape is compatible.
4. Production uses Redis-backed sessions — survives Railway multi-worker deployment.

---

## Testing Plan

### New Tests (~45 total)

**Unit tests for `backend/clever.py` (~20):**
- `test_get_clever_config_missing_env` — returns None when env vars not set
- `test_get_clever_config_present` — returns dict with all fields
- `test_get_authorize_url` — correct URL with client_id, redirect_uri, state
- `test_exchange_code_success` — mock httpx, verify token returned
- `test_exchange_code_failure` — mock 400 response, returns None
- `test_exchange_code_network_error` — mock HTTPError, returns None
- `test_get_clever_user_success` — mock /me + /users, verify parsed output
- `test_get_clever_user_teacher` — verify teacher type detected
- `test_get_clever_user_api_error` — mock 500, returns None
- `test_sync_roster_pagination` — mock 3 pages, verify all fetched
- `test_sync_roster_error_midway` — mock error on page 2, returns partial data
- `test_extract_accommodations_iep` — iep_status="Y" → suggested presets
- `test_extract_accommodations_ell` — ell_status="Y" → ell_support preset
- `test_extract_accommodations_both` — IEP+ELL → combined presets
- `test_extract_accommodations_none` — no flags → empty dict
- `test_extract_accommodations_varied_formats` — "yes", "Y", "true", "Active" all work
- `test_map_sections_to_periods` — sections correctly mapped
- `test_persist_roster_as_csv` — file written to ROSTERS_DIR, metadata exists
- `test_persist_sections_as_periods` — files written to PERIODS_DIR
- `test_next_page_url_relative` — prepends CLEVER_API_BASE
- `test_next_page_url_absolute` — returns as-is
- `test_next_page_url_none` — no next link returns None

**Route tests for `backend/routes/clever_routes.py` (~13):**
- `test_login_url_returns_url` — GET /api/clever/login-url returns valid URL
- `test_login_url_not_configured` — returns 503 when env vars missing
- `test_callback_success` — mock token exchange + user fetch, verify redirect to /?clever_login=success
- `test_callback_error_param` — error in query string redirects with clever_error
- `test_callback_missing_code` — redirects with clever_error=missing_code
- `test_callback_state_mismatch` — CSRF protection rejects mismatched state
- `test_callback_rejects_students` — student login → clever_error=students_use_portal
- `test_session_authenticated` — returns user info when session exists
- `test_session_unauthenticated` — returns {authenticated: false}
- `test_sync_roster_persists_csv` — verify CSV written after sync
- `test_sync_roster_no_token` — returns 503 when CLEVER_DISTRICT_TOKEN missing
- `test_apply_accommodations` — verify set_student_accommodation called correctly
- `test_logout_clears_session` — session cleared

**Integration tests (~10):**
- `test_clever_session_passes_auth_middleware` — Clever session → g.user_id set
- `test_clever_public_routes_skip_auth` — /api/clever/* don't require JWT
- `test_supabase_auth_still_works` — no regression on existing JWT auth
- `test_clever_user_shape_compatible` — user object works with existing components
- `test_roster_csv_readable_by_existing_upload` — CSV matches manual upload format
- `test_approval_gate_skipped_for_clever_users` — Clever users bypass approval (they're district-approved)
- `test_approval_gate_still_works_for_supabase` — no regression on Supabase approval flow
- `test_stripe_metadata_returns_empty_for_clever` — `_get_user_metadata` returns {} for Clever users
- `test_stripe_subscription_returns_district_for_clever` — subscription-status returns "district" for Clever
- `test_getAuthHeaders_returns_empty_for_clever` — frontend doesn't try Supabase session for Clever users

**All tests mock Clever API responses — no real API calls in CI.**

---

## Timeline

| Day | Task |
|-----|------|
| 1 | Sign up at apps.clever.com, complete Clever Academy, get sandbox |
| 2-3 | Implement `clever.py` + `clever_routes.py` + `__init__.py` + `auth.py` edits |
| 4 | Implement frontend (LoginScreen + App.jsx + api.js), add Flask-Session |
| 5 | Write all 40 tests, test against Clever sandbox |
| 6-7 | Fix edge cases, test all browsers, handle error states, verify roster persistence |
| 8 | Submit for certification |
| 9-11 | Buffer / prep for demo while certification is reviewed |

**At the demo (day 11):** "We've completed Clever integration and submitted for certification. Once approved, your district's roster and IEP/504 data sync automatically — teachers don't enter anything manually."

---

## Future Enhancements (post-certification)

1. **Multi-district token management** — Store district tokens in Supabase keyed by district ID instead of single env var
2. ~~**Scheduled sync**~~ — ✅ **Shipped.** Cron webhook at `/api/sync/periodic-roster` (`backend/routes/sync_routes.py:269`) re-syncs daily via the `.github/workflows/roster-sync.yml` workflow. PERIODIC_SYNC_SECRET-gated.
3. **Delta sync via Events API** — Instead of full roster pull, subscribe to Clever Events for real-time changes
4. **Student SSO** — ✅ Shipped (auth-code flow with 60s TTL — see Student SSO section above)
5. **Clever Library certification** — For individual teacher discovery (lower priority than district SSO)
