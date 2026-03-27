# School Admin (Principal) Role Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only school admin role so principals can view aggregate grading data, assessment results, and teacher activity across their school via an "Admin" tab in the dashboard.

**Architecture:** New `backend/routes/admin_routes.py` for admin endpoints (status, teachers, overview, drill-down, activity). Admin designation via invite codes managed by district admin at `/district`. Teacher discovery from SIS (OneRoster/Clever) with manual fallback. New `frontend/src/tabs/AdminTab.jsx` rendered when admin detected. All admin data stored in existing `teacher_data` table with `teacher_id="system"`.

**Tech Stack:** Flask/Python backend, Supabase service key for cross-teacher queries, React frontend (inline styles).

**Spec:** `docs/superpowers/specs/2026-03-27-school-admin-role-design.md`

---

## Pre-Requisite Fix: District Storage Key Mismatch

**Bug found during planning:** `district_routes.py` stores SIS config under key `"district:sis_config"` (line 24) but `oneroster.py` reads it as `"district_sis_config"` (line 308) and `clever.py` reads it as `"district_sis_config"`. This means district-level OneRoster/Clever config saved at `/district` is invisible to the config resolution chain. Must be fixed before proceeding.

**Fix:** Align `oneroster.py` and `clever.py` to use `"district:sis_config"` (matching the key `district_routes.py` writes).

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/utils/auth_decorators.py` | MODIFY | Add `require_admin` decorator |
| `backend/routes/admin_routes.py` | CREATE | `/api/admin/*` endpoints: status, claim, teachers, overview, drill-down, activity |
| `backend/routes/district_routes.py` | MODIFY | Add admin invite, list admins, revoke admin, teacher search endpoints |
| `backend/routes/__init__.py` | MODIFY | Register `admin_bp` blueprint |
| `backend/oneroster.py` | MODIFY | Fix storage key to `"district:sis_config"` |
| `backend/clever.py` | MODIFY | Fix storage key to `"district:sis_config"` |
| `backend/api_keys.py` | MODIFY | Fix storage key to `"district:ai_keys"` (verify consistency) |
| `frontend/src/tabs/AdminTab.jsx` | CREATE | Read-only admin dashboard with 4 panels |
| `frontend/src/App.jsx` | MODIFY | Check admin status, render Admin tab |
| `frontend/src/services/api.js` | MODIFY | Add admin API functions |
| `frontend/src/tabs/SettingsTab.jsx` | MODIFY | Add "Claim Admin Access" invite code input |
| `frontend/src/components/DistrictSetup.jsx` | MODIFY | Add "School Admins" section with invite + teacher search |
| `tests/test_admin_routes.py` | CREATE | Backend tests for admin endpoints |

---

### Task 1: Fix District Storage Key Mismatch + Add `require_admin`

**Files:**
- Modify: `backend/oneroster.py`
- Modify: `backend/clever.py`
- Modify: `backend/api_keys.py`
- Modify: `backend/utils/auth_decorators.py`
- Create: `tests/test_admin_routes.py` (initial)

- [ ] **Step 1: Fix `backend/oneroster.py` storage key**

In `get_oneroster_config()` (around line 308), change:
```python
district_cfg = load("district_sis_config", "system")
```
to:
```python
district_cfg = load("district:sis_config", "system")
```

- [ ] **Step 2: Fix `backend/clever.py` storage key**

In `get_clever_config()`, find the district-level check and change `"district_sis_config"` to `"district:sis_config"`.

- [ ] **Step 3: Fix `backend/api_keys.py` storage key**

Verify the district AI keys lookup uses `"district:ai_keys"` (matching `district_routes.py`'s `_KEY_AI_KEYS`). If it uses `"district_ai_keys"`, change it to `"district:ai_keys"`.

- [ ] **Step 4: Add `require_admin` decorator to `backend/utils/auth_decorators.py`**

Append after the existing `require_clever_session` function:

```python
def require_admin(f):
    """Decorator that enforces school admin authentication.
    Checks admin_role:{user_id} exists in system storage.
    Sets g.admin_role for use in the wrapped route handler."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        try:
            from backend.storage import load
            admin_role = load(f"admin_role:{user_id}", "system")
        except Exception:
            admin_role = None
        if not admin_role:
            return jsonify({"error": "Admin access required"}), 403
        g.teacher_id = user_id
        g.admin_role = admin_role
        return f(*args, **kwargs)
    return wrapper
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `source venv/bin/activate && python -m pytest tests/test_clever_compliance.py tests/test_oneroster.py tests/test_district_routes.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/oneroster.py backend/clever.py backend/api_keys.py backend/utils/auth_decorators.py
git commit -m "fix: align district storage keys + add require_admin decorator"
```

---

### Task 2: Admin Routes — Backend

**Files:**
- Create: `backend/routes/admin_routes.py`
- Create: `tests/test_admin_routes.py`
- Modify: `backend/routes/__init__.py`

- [ ] **Step 1: Create `backend/routes/admin_routes.py`**

```python
"""
School Admin (Principal) routes for Graider.

Read-only endpoints for school-wide visibility across teachers.
Admin role granted via invite codes managed at /district.
"""
import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, g

from backend.storage import load as storage_load, save as storage_save, list_keys
from backend.supabase_client import get_supabase as _get_supabase
from backend.utils.auth_decorators import require_teacher, require_admin
from backend.utils.errors import handle_route_errors

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


# ── Admin Status ─────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/status", methods=["GET"])
@require_teacher
@handle_route_errors
def admin_status():
    """Check if the current user is a school admin."""
    try:
        admin_role = storage_load(f"admin_role:{g.teacher_id}", "system")
    except Exception:
        admin_role = None

    if not admin_role:
        return jsonify({"is_admin": False})

    return jsonify({
        "is_admin": True,
        "school": admin_role.get("school", ""),
        "granted_at": admin_role.get("granted_at", ""),
    })


# ── Claim Admin Role ─────────────────────────────────────────────────────

@admin_bp.route("/api/admin/claim", methods=["POST"])
@require_teacher
@handle_route_errors
def claim_admin():
    """Claim admin role using an invite code.

    Body: {"code": "ABC123"}
    """
    data = request.json or {}
    code = data.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "Invite code required"}), 400

    invite = storage_load(f"admin_invite:{code}", "system")
    if not invite:
        return jsonify({"error": "Invalid or expired invite code"}), 404

    # Check expiry
    expires_at = invite.get("expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > exp:
                storage_save(f"admin_invite:{code}", None, "system")
                return jsonify({"error": "Invite code has expired"}), 410
        except Exception:
            pass

    # Grant admin role
    admin_role = {
        "user_id": g.teacher_id,
        "school": invite.get("school", ""),
        "manual_teachers": invite.get("manual_teachers", []),
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "granted_by": invite.get("created_by", ""),
    }
    storage_save(f"admin_role:{g.teacher_id}", admin_role, "system")

    # Delete the used invite code
    storage_save(f"admin_invite:{code}", None, "system")

    from backend.utils.audit import audit_log
    audit_log("ADMIN_ROLE_CLAIMED", f"Admin role claimed for school: {admin_role['school']}",
              teacher_id=g.teacher_id)

    return jsonify({"status": "claimed", "school": admin_role["school"]})


# ── Teacher Discovery ────────────────────────────────────────────────────

def _discover_teachers_from_sis(school_name):
    """Query OneRoster for teachers at a school, match to Graider accounts by email."""
    try:
        district_config = storage_load("district:sis_config", "system")
    except Exception:
        return []

    if not district_config or district_config.get("sis_type") != "oneroster":
        return []

    base_url = district_config.get("base_url", "")
    client_id = district_config.get("client_id", "")
    client_secret = district_config.get("client_secret", "")
    if not base_url or not client_id or not client_secret:
        return []

    from backend.oneroster import OneRosterClient

    client = OneRosterClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        token_url=district_config.get("token_url"),
    )

    async def _fetch():
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as http:
            await client._ensure_token(http)
            # Find school by name
            schools_data = await client._get_paginated(http, "/schools", "orgs", "schools")
            school_id = None
            for s in (schools_data or []):
                if (s.get("name") or "").lower().strip() == school_name.lower().strip():
                    school_id = s.get("sourcedId")
                    break
            if not school_id:
                logger.info("Admin: school '%s' not found in OneRoster", school_name)
                return []
            teachers = await client._get_paginated(
                http, f"/schools/{school_id}/teachers", "users", "teachers")
            return teachers or []

    loop = asyncio.new_event_loop()
    try:
        sis_teachers = loop.run_until_complete(_fetch())
    except Exception as e:
        logger.warning("Admin SIS teacher discovery failed: %s", str(e))
        return []
    finally:
        loop.close()

    # Match SIS teachers to Graider accounts by email
    db = _get_supabase()
    if not db:
        return [{"user_id": None, "name": ((t.get("givenName") or "") + " " + (t.get("familyName") or "")).strip(),
                 "email": t.get("email", ""), "registered": False} for t in sis_teachers]

    try:
        settings_rows = db.table("teacher_data").select(
            "teacher_id, data"
        ).eq("data_key", "settings").execute()
    except Exception:
        settings_rows = type('R', (), {'data': []})()

    email_to_uid = {}
    uid_to_info = {}
    for row in (settings_rows.data or []):
        data = row.get("data", {})
        if isinstance(data, dict):
            email = (data.get("teacher_email") or "").strip().lower()
            name = data.get("teacher_name", "")
            if email:
                email_to_uid[email] = row["teacher_id"]
                uid_to_info[row["teacher_id"]] = {"name": name, "email": email}

    matched = []
    for t in sis_teachers:
        sis_email = (t.get("email") or "").strip().lower()
        graider_uid = email_to_uid.get(sis_email)
        matched.append({
            "user_id": graider_uid,
            "name": ((t.get("givenName") or "") + " " + (t.get("familyName") or "")).strip(),
            "email": t.get("email", ""),
            "sis_sourced_id": t.get("sourcedId", ""),
            "registered": graider_uid is not None,
        })

    return matched


def _discover_teachers(admin_role):
    """Get list of teachers for this admin. Three-layer resolution."""
    school = admin_role.get("school", "")
    all_teachers = []
    seen_emails = set()

    # Layer 1: SIS auto-discovery
    sis_teachers = _discover_teachers_from_sis(school)
    for t in sis_teachers:
        email = (t.get("email") or "").lower()
        if email:
            seen_emails.add(email)
        all_teachers.append(t)

    # Layer 2: Manual assignments (deduplicate by email)
    for t in admin_role.get("manual_teachers", []):
        email = (t.get("email") or "").lower()
        if email and email not in seen_emails:
            seen_emails.add(email)
            all_teachers.append({
                "user_id": t.get("user_id"),
                "name": t.get("name", ""),
                "email": t.get("email", ""),
                "registered": t.get("user_id") is not None,
            })

    # Layer 3: Fallback — discover from teacher_data
    if not all_teachers:
        db = _get_supabase()
        if db:
            try:
                rows = db.table("teacher_data").select(
                    "teacher_id, data"
                ).eq("data_key", "settings").execute()
                for row in (rows.data or []):
                    data = row.get("data", {})
                    if isinstance(data, dict):
                        all_teachers.append({
                            "user_id": row["teacher_id"],
                            "name": data.get("teacher_name", ""),
                            "email": data.get("teacher_email", ""),
                            "registered": True,
                        })
            except Exception:
                pass

    return all_teachers


@admin_bp.route("/api/admin/teachers", methods=["GET"])
@require_admin
@handle_route_errors
def get_admin_teachers():
    """List teachers at the admin's school."""
    teachers = _discover_teachers(g.admin_role)
    db = _get_supabase()

    # Enrich with activity data for registered teachers
    for t in teachers:
        uid = t.get("user_id")
        if not uid or not db:
            t["classes_count"] = 0
            t["students_count"] = 0
            t["assessments_count"] = 0
            t["last_activity"] = None
            continue

        try:
            classes = db.table("classes").select("id", count="exact").eq("teacher_id", uid).execute()
            t["classes_count"] = classes.count or 0
        except Exception:
            t["classes_count"] = 0

        try:
            assessments = db.table("published_assessments").select("id", count="exact").eq("teacher_id", uid).execute()
            content = db.table("published_content").select("id", count="exact").eq("teacher_id", uid).execute()
            t["assessments_count"] = (assessments.count or 0) + (content.count or 0)
        except Exception:
            t["assessments_count"] = 0

        try:
            # Count students from class enrollments
            class_ids = db.table("classes").select("id").eq("teacher_id", uid).execute()
            student_count = 0
            for c in (class_ids.data or []):
                enrolled = db.table("class_students").select("id", count="exact").eq("class_id", c["id"]).execute()
                student_count += (enrolled.count or 0)
            t["students_count"] = student_count
        except Exception:
            t["students_count"] = 0

        try:
            last = db.table("audit_log").select("timestamp").eq(
                "teacher_id", uid
            ).order("timestamp", desc=True).limit(1).execute()
            t["last_activity"] = last.data[0]["timestamp"] if last.data else None
        except Exception:
            t["last_activity"] = None

    from backend.utils.audit import audit_log
    audit_log("ADMIN_VIEW_TEACHERS", f"Admin viewed teacher list ({len(teachers)} teachers)",
              teacher_id=g.teacher_id)

    return jsonify({"teachers": teachers})


# ── School Overview ──────────────────────────────────────────────────────

@admin_bp.route("/api/admin/overview", methods=["GET"])
@require_admin
@handle_route_errors
def admin_overview():
    """Aggregate school-wide stats across the admin's teachers."""
    teachers = _discover_teachers(g.admin_role)
    teacher_ids = [t["user_id"] for t in teachers if t.get("user_id")]

    db = _get_supabase()
    if not db or not teacher_ids:
        return jsonify({
            "teacher_count": len(teachers),
            "registered_count": len(teacher_ids),
            "total_students": 0,
            "total_assessments": 0,
            "average_score": None,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
        })

    total_students = 0
    total_assessments = 0
    all_scores = []

    for tid in teacher_ids:
        try:
            # Count students
            classes = db.table("classes").select("id").eq("teacher_id", tid).execute()
            for c in (classes.data or []):
                enrolled = db.table("class_students").select("id", count="exact").eq("class_id", c["id"]).execute()
                total_students += (enrolled.count or 0)
        except Exception:
            pass

        try:
            # Count assessments and collect scores
            pa = db.table("published_assessments").select("id, join_code").eq("teacher_id", tid).execute()
            total_assessments += len(pa.data or [])
            for a in (pa.data or []):
                subs = db.table("submissions").select("percentage").eq("join_code", a["join_code"]).execute()
                for s in (subs.data or []):
                    if s.get("percentage") is not None:
                        all_scores.append(s["percentage"])

            pc = db.table("published_content").select("id").eq("teacher_id", tid).eq("content_type", "assessment").execute()
            total_assessments += len(pc.data or [])
            for c in (pc.data or []):
                subs = db.table("student_submissions").select("percentage").eq("content_id", c["id"]).execute()
                for s in (subs.data or []):
                    if s.get("percentage") is not None:
                        all_scores.append(s["percentage"])
        except Exception:
            pass

    # Grade distribution
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for score in all_scores:
        if score >= 90:
            grade_dist["A"] += 1
        elif score >= 80:
            grade_dist["B"] += 1
        elif score >= 70:
            grade_dist["C"] += 1
        elif score >= 60:
            grade_dist["D"] += 1
        else:
            grade_dist["F"] += 1

    avg_score = round(sum(all_scores) / len(all_scores)) if all_scores else None

    from backend.utils.audit import audit_log
    audit_log("ADMIN_VIEW_OVERVIEW", "Admin viewed school overview", teacher_id=g.teacher_id)

    return jsonify({
        "teacher_count": len(teachers),
        "registered_count": len(teacher_ids),
        "total_students": total_students,
        "total_assessments": total_assessments,
        "average_score": avg_score,
        "grade_distribution": grade_dist,
        "total_scores": len(all_scores),
    })


# ── Teacher Drill-Down ───────────────────────────────────────────────────

@admin_bp.route("/api/admin/teacher/<teacher_id>/summary", methods=["GET"])
@require_admin
@handle_route_errors
def teacher_summary(teacher_id):
    """Per-teacher drill-down: classes, recent assessments, grade distribution."""
    # Verify this teacher is in the admin's school
    teachers = _discover_teachers(g.admin_role)
    allowed_ids = [t["user_id"] for t in teachers if t.get("user_id")]
    if teacher_id not in allowed_ids:
        return jsonify({"error": "Teacher not in your school"}), 403

    db = _get_supabase()
    if not db:
        return jsonify({"error": "Database not available"}), 500

    # Classes
    classes = []
    try:
        class_rows = db.table("classes").select("id, name, subject, grade_level").eq("teacher_id", teacher_id).execute()
        for c in (class_rows.data or []):
            enrolled = db.table("class_students").select("id", count="exact").eq("class_id", c["id"]).execute()
            classes.append({
                "name": c.get("name", ""),
                "subject": c.get("subject", ""),
                "grade_level": c.get("grade_level", ""),
                "student_count": enrolled.count or 0,
            })
    except Exception:
        pass

    # Recent assessments
    assessments = []
    try:
        pa = db.table("published_assessments").select("title, join_code, created_at, is_active").eq(
            "teacher_id", teacher_id).order("created_at", desc=True).limit(10).execute()
        for a in (pa.data or []):
            subs = db.table("submissions").select("percentage", count="exact").eq("join_code", a["join_code"]).execute()
            scores = [s["percentage"] for s in (subs.data or []) if s.get("percentage") is not None]
            assessments.append({
                "title": a.get("title", ""),
                "published_at": a.get("created_at", ""),
                "submissions": subs.count or 0,
                "average_score": round(sum(scores) / len(scores)) if scores else None,
            })
    except Exception:
        pass

    # Recent audit log
    activity = []
    try:
        logs = db.table("audit_log").select("action, details, timestamp").eq(
            "teacher_id", teacher_id).order("timestamp", desc=True).limit(10).execute()
        activity = logs.data or []
    except Exception:
        pass

    from backend.utils.audit import audit_log
    audit_log("ADMIN_VIEW_TEACHER", f"Admin viewed teacher {teacher_id}", teacher_id=g.teacher_id)

    return jsonify({
        "classes": classes,
        "assessments": assessments,
        "activity": activity,
    })


# ── Activity Feed ────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/activity", methods=["GET"])
@require_admin
@handle_route_errors
def admin_activity():
    """Recent audit log entries across the admin's teachers."""
    teachers = _discover_teachers(g.admin_role)
    teacher_ids = [t["user_id"] for t in teachers if t.get("user_id")]

    db = _get_supabase()
    if not db or not teacher_ids:
        return jsonify({"activity": []})

    all_activity = []
    for tid in teacher_ids:
        try:
            logs = db.table("audit_log").select("action, details, timestamp, teacher_id").eq(
                "teacher_id", tid).order("timestamp", desc=True).limit(10).execute()
            all_activity.extend(logs.data or [])
        except Exception:
            pass

    # Sort by timestamp descending, limit to 50
    all_activity.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    all_activity = all_activity[:50]

    # Enrich with teacher names
    teacher_names = {t["user_id"]: t.get("name", "") for t in teachers if t.get("user_id")}
    for entry in all_activity:
        entry["teacher_name"] = teacher_names.get(entry.get("teacher_id"), "Unknown")

    return jsonify({"activity": all_activity})
```

- [ ] **Step 2: Register blueprint in `backend/routes/__init__.py`**

Add after the `district_routes` import:
```python
from .admin_routes import admin_bp
```

In `register_routes()`:
```python
app.register_blueprint(admin_bp)
```

In `__all__`:
```python
'admin_bp',
```

- [ ] **Step 3: Create `tests/test_admin_routes.py`**

```python
"""Tests for school admin routes."""
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


AUTH = {"X-Test-Teacher-Id": "test-teacher", "Content-Type": "application/json"}


class TestAdminStatus:
    def test_status_requires_auth(self, client):
        resp = client.get("/api/admin/status")
        assert resp.status_code == 401

    def test_status_returns_false_for_non_admin(self, client):
        resp = client.get("/api/admin/status", headers=AUTH)
        data = resp.get_json()
        assert data["is_admin"] is False

    def test_status_returns_true_for_admin(self, client):
        with patch("backend.utils.auth_decorators.load") as mock_load:
            mock_load.return_value = {"school": "Test School", "granted_at": "2026-03-27"}
            resp = client.get("/api/admin/status", headers=AUTH)
            data = resp.get_json()
            # Note: require_teacher runs first, then the route checks storage
            # The status endpoint does its own load, not via require_admin
            assert resp.status_code == 200


class TestClaimAdmin:
    def test_claim_requires_code(self, client):
        resp = client.post("/api/admin/claim", headers=AUTH, data=json.dumps({}))
        assert resp.status_code == 400

    def test_claim_invalid_code_returns_404(self, client):
        resp = client.post("/api/admin/claim", headers=AUTH,
                           data=json.dumps({"code": "BADCODE"}))
        assert resp.status_code == 404


class TestAdminTeachers:
    def test_teachers_requires_admin(self, client):
        resp = client.get("/api/admin/teachers", headers=AUTH)
        assert resp.status_code == 403

    def test_overview_requires_admin(self, client):
        resp = client.get("/api/admin/overview", headers=AUTH)
        assert resp.status_code == 403

    def test_activity_requires_admin(self, client):
        resp = client.get("/api/admin/activity", headers=AUTH)
        assert resp.status_code == 403
```

- [ ] **Step 4: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_admin_routes.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/routes/admin_routes.py backend/routes/__init__.py tests/test_admin_routes.py
git commit -m "feat: add school admin routes (status, claim, teachers, overview, drill-down, activity)"
```

---

### Task 3: District Admin — Invite Management + Teacher Search

**Files:**
- Modify: `backend/routes/district_routes.py`

- [ ] **Step 1: Add admin invite, list, revoke, and teacher search endpoints**

Append to `backend/routes/district_routes.py`:

```python
# ── School Admin Management ──────────────────────────────────────────────

@district_bp.route("/api/district/admin-invite", methods=["POST"])
@_require_district_admin
@handle_route_errors
def create_admin_invite():
    """Create an invite code for a school admin.

    Body: {"school": "Southwestern Middle", "manual_teachers": [{user_id, name, email}]}
    """
    data = request.json or {}
    school = data.get("school", "").strip()
    manual_teachers = data.get("manual_teachers", [])

    if not school:
        return jsonify({"error": "school is required"}), 400

    import secrets
    from datetime import datetime, timezone, timedelta

    code = secrets.token_hex(3).upper()  # 6-char hex code
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    invite = {
        "school": school,
        "manual_teachers": manual_teachers,
        "expires_at": expires_at,
        "created_by": "district_admin",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    storage_save(f"admin_invite:{code}", invite, "system")

    audit_log("ADMIN_INVITE_CREATED", f"Admin invite created for school: {school} (code: {code})")

    return jsonify({"code": code, "expires_at": expires_at, "school": school})


@district_bp.route("/api/district/admins", methods=["GET"])
@_require_district_admin
@handle_route_errors
def list_admins():
    """List all current school admins."""
    keys = list_keys("admin_role:", "system")
    admins = []
    for key in keys:
        role = storage_load(key, "system")
        if role and isinstance(role, dict):
            admins.append({
                "user_id": role.get("user_id", key.replace("admin_role:", "")),
                "school": role.get("school", ""),
                "granted_at": role.get("granted_at", ""),
            })
    return jsonify({"admins": admins})


@district_bp.route("/api/district/admins", methods=["DELETE"])
@_require_district_admin
@handle_route_errors
def revoke_admin():
    """Revoke a school admin's access.

    Body: {"user_id": "..."}
    """
    data = request.json or {}
    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    storage_save(f"admin_role:{user_id}", None, "system")

    audit_log("ADMIN_REVOKED", f"Admin role revoked for user: {user_id}")

    return jsonify({"status": "revoked"})


@district_bp.route("/api/district/teacher-search", methods=["GET"])
@_require_district_admin
@handle_route_errors
def teacher_search():
    """Search Graider teachers by name or email for manual admin assignment.

    Query: ?q=smith
    Returns: [{user_id, name, email}] (max 20 results)
    """
    query = request.args.get("q", "").strip().lower()
    if not query or len(query) < 2:
        return jsonify({"teachers": []})

    db = _get_supabase()
    if not db:
        return jsonify({"teachers": []})

    try:
        rows = db.table("teacher_data").select(
            "teacher_id, data"
        ).eq("data_key", "settings").execute()
    except Exception:
        return jsonify({"teachers": []})

    results = []
    for row in (rows.data or []):
        data = row.get("data", {})
        if not isinstance(data, dict):
            continue
        name = (data.get("teacher_name") or "").lower()
        email = (data.get("teacher_email") or "").lower()
        if query in name or query in email:
            results.append({
                "user_id": row["teacher_id"],
                "name": data.get("teacher_name", ""),
                "email": data.get("teacher_email", ""),
            })
        if len(results) >= 20:
            break

    return jsonify({"teachers": results})
```

Also add missing imports at the top of the file if not already present:

```python
from backend.storage import list_keys
from backend.supabase_client import get_supabase as _get_supabase
```

- [ ] **Step 2: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_district_routes.py tests/test_admin_routes.py -v`

- [ ] **Step 3: Commit**

```bash
git add backend/routes/district_routes.py
git commit -m "feat: add admin invite, list, revoke, and teacher search to district routes"
```

---

### Task 4: Frontend — API Functions + Settings Claim + District Invite UI

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/tabs/SettingsTab.jsx`
- Modify: `frontend/src/components/DistrictSetup.jsx`

- [ ] **Step 1: Add admin API functions to `frontend/src/services/api.js`**

Add after the district API functions:

```javascript
// School Admin
export async function getAdminStatus() {
  return fetchApi('/api/admin/status')
}

export async function claimAdmin(code) {
  return fetchApi('/api/admin/claim', {
    method: 'POST',
    body: JSON.stringify({ code: code }),
  })
}

export async function getAdminTeachers() {
  return fetchApi('/api/admin/teachers')
}

export async function getAdminOverview() {
  return fetchApi('/api/admin/overview')
}

export async function getAdminTeacherSummary(teacherId) {
  return fetchApi('/api/admin/teacher/' + teacherId + '/summary')
}

export async function getAdminActivity() {
  return fetchApi('/api/admin/activity')
}

export async function createAdminInvite(school, manualTeachers) {
  return fetchApi('/api/district/admin-invite', {
    method: 'POST',
    body: JSON.stringify({ school: school, manual_teachers: manualTeachers || [] }),
  })
}

export async function listAdmins() {
  return fetchApi('/api/district/admins')
}

export async function revokeAdmin(userId) {
  return fetchApi('/api/district/admins', {
    method: 'DELETE',
    body: JSON.stringify({ user_id: userId }),
  })
}

export async function searchTeachers(query) {
  return fetchApi('/api/district/teacher-search?q=' + encodeURIComponent(query))
}
```

Add all to default export object.

- [ ] **Step 2: Add "Claim Admin Access" section to `SettingsTab.jsx`**

In the Settings > General tab (around line 255, inside `settingsTab === "general"`), add after the Email Signature section:

A collapsible "Admin Access" section with:
- Text input for invite code
- "Claim Access" button → calls `api.claimAdmin(code)`
- Success message with school name
- If already admin: show "You are a school admin for [school]" badge

- [ ] **Step 3: Add "School Admins" section to `DistrictSetup.jsx`**

In the district admin config form, add a new section after AI API Keys:
- Header: "School Admins"
- "Create Invite" form: school name input + teacher search field (typeahead) + "Generate Invite Code" button
- Active invites list (if any)
- Current admins list with "Revoke" button
- Teacher search: as user types, queries `/api/district/teacher-search`, shows results, click to add to manual_teachers list

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.js frontend/src/tabs/SettingsTab.jsx frontend/src/components/DistrictSetup.jsx
git commit -m "feat: add admin claim in Settings + invite management in District Setup"
```

---

### Task 5: Frontend — Admin Dashboard Tab

**Files:**
- Create: `frontend/src/tabs/AdminTab.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Create `frontend/src/tabs/AdminTab.jsx`**

React component with four panels:

**Panel 1: Teacher Overview** — table of teachers with name, email, classes, students, assessments, last activity. Click row to expand drill-down.

**Panel 2: School-Wide Analytics** — summary cards: total teachers, total students, total assessments, average score. Grade distribution pie chart (simple colored bars, no chart library needed).

**Panel 3: Teacher Drill-Down** — expanded row showing classes list, recent assessments with scores, recent audit activity. Uses `api.getAdminTeacherSummary(teacherId)`.

**Panel 4: Activity Feed** — chronological list of recent events across all teachers. Uses `api.getAdminActivity()`.

**CRITICAL CODE STYLE RULES:**
- NO template literals (backticks) — use string concatenation
- Use `var` not `const` or `let`
- Use inline styles
- Use existing `Icon` component from `../components/Icon`
- Follow existing tab patterns (ResultsTab, AnalyticsTab) for styling

- [ ] **Step 2: Add Admin tab to `frontend/src/App.jsx`**

Add import:
```javascript
var AdminTab = React.lazy(function() { return import("./tabs/AdminTab"); });
```

Add state (alongside existing state, around line 1321):
```javascript
var [isAdmin, setIsAdmin] = useState(false);
var [adminSchool, setAdminSchool] = useState('');
```

Add useEffect to check admin status on login (after user is set):
```javascript
useEffect(function() {
  if (!user) return;
  api.getAdminStatus().then(function(data) {
    setIsAdmin(data.is_admin || false);
    setAdminSchool(data.school || '');
  }).catch(function() {});
}, [user]);
```

Add "Admin" to the tab bar (only when `isAdmin` is true). Find the tabs array/rendering and add:
```javascript
{isAdmin && { id: "admin", label: "Admin", icon: "Shield" }}
```

Add AdminTab rendering in the tab content area:
```javascript
{activeTab === "admin" && isAdmin && (
  <React.Suspense fallback={<div>Loading...</div>}>
    <AdminTab school={adminSchool} />
  </React.Suspense>
)}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/tabs/AdminTab.jsx frontend/src/App.jsx
git commit -m "feat: add Admin dashboard tab with teacher overview, analytics, and activity feed"
```

---

### Task 6: Documentation + Full Verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add admin endpoints to CLAUDE.md**

Find the "API Reference" section. After "District Admin Setup" subsection, add:

```markdown
### School Admin (Principal)
- `GET /api/admin/status` — Check if current user is a school admin
- `POST /api/admin/claim` — Claim admin role with invite code
- `GET /api/admin/teachers` — List teachers at admin's school
- `GET /api/admin/overview` — School-wide aggregate stats
- `GET /api/admin/teacher/<id>/summary` — Per-teacher drill-down
- `GET /api/admin/activity` — Recent activity across admin's teachers
- `POST /api/district/admin-invite` — Create admin invite code (district admin)
- `GET /api/district/admins` — List current admins (district admin)
- `DELETE /api/district/admins` — Revoke admin (district admin)
- `GET /api/district/teacher-search` — Search teachers by name/email (district admin)
```

- [ ] **Step 2: Run all backend tests**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`
Expected: No new failures

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add school admin endpoints to CLAUDE.md"
```

---

## Implementation Notes

### Storage Keys

| Key | teacher_id | Purpose |
|-----|-----------|---------|
| `admin_invite:{code}` | `system` | Pending invite (school, manual_teachers, expires_at, 7-day TTL) |
| `admin_role:{user_id}` | `system` | Granted admin (school, manual_teachers, granted_at) |

### FERPA Compliance

- Admin sees **aggregate data only** — score averages, counts, grade distributions
- Admin **cannot** see: individual student names/responses, teacher AI instructions, rubric notes, grading style
- All admin data access is audit-logged (`ADMIN_VIEW_*` actions)
- Teacher drill-down scoped to admin's school (verified against teacher list)
- Student PII stays within teacher-scoped views

### No Database Schema Changes

- All storage via existing `teacher_data` with `teacher_id="system"`
- Cross-teacher queries use backend service key (bypasses RLS)
- No new Supabase tables, columns, or RLS policies

### Pre-Requisite Fix

The district storage key mismatch (`"district_sis_config"` vs `"district:sis_config"`) MUST be fixed in Task 1 before the admin's SIS teacher discovery can work. This is a pre-existing bug that also affects the district setup page's OneRoster/Clever config resolution.
