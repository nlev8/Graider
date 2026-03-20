# Clever Student SSO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow students to click the Graider tile in their Clever Portal and land directly in their student dashboard with assignments, bypassing the email + class code login.

**Architecture:** In the Clever OAuth callback, detect student role → look up their enrollment in the `students` table by Clever ID → find their class via `class_students` → create a student session token → redirect to `/student?clever=1`. The StudentApp frontend checks for Clever student session on mount and auto-logs in.

**Tech Stack:** Python/Flask (backend), React (frontend), Supabase (database)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/routes/clever_routes.py` | Modify | Accept student role in callback, create student session, redirect to `/student` |
| `frontend/src/components/StudentApp.jsx` | Modify | Check for Clever student session on mount via URL param |
| `frontend/src/components/LoginScreen.jsx` | Modify | Add "I'm a student" link |
| `tests/test_clever_student_sso.py` | Create | Tests for student Clever SSO flow |

---

### Task 1: Accept student role in Clever callback and create student session

**Files:**
- Modify: `backend/routes/clever_routes.py:240-242` (the student rejection block)
- Create: `tests/test_clever_student_sso.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_clever_student_sso.py`:

```python
"""Tests for Clever student SSO login flow."""
import pytest
from unittest.mock import patch, MagicMock


def test_clever_student_login_creates_session():
    """Verify that a student logging in via Clever gets a session and redirect to /student."""
    from backend.routes.clever_routes import _create_clever_student_session

    mock_db = MagicMock()
    # Student found in students table
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "stu_uuid_1", "first_name": "Jane", "last_name": "Doe"}
    ]
    # Class enrollment found
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"class_id": "cls_uuid_1", "student_id": "stu_uuid_1"}
    ]
    # Session insert succeeds
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{"id": "session_1"}]

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=mock_db):
        result = _create_clever_student_session("clever_stu_001", "jane@school.edu")

    assert result is not None
    assert "token" in result
    assert "student" in result


def test_clever_student_login_not_enrolled():
    """Verify that a student not in the database returns None."""
    from backend.routes.clever_routes import _create_clever_student_session

    mock_db = MagicMock()
    # Student NOT found
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=mock_db):
        result = _create_clever_student_session("clever_unknown", "nobody@school.edu")

    assert result is None


def test_clever_student_login_no_supabase():
    """Verify graceful handling when Supabase is not configured."""
    from backend.routes.clever_routes import _create_clever_student_session

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=None):
        result = _create_clever_student_session("clever_stu_001", "jane@school.edu")

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_clever_student_sso.py -v`
Expected: FAIL with `ImportError: cannot import name '_create_clever_student_session'`

- [ ] **Step 3: Write `_create_clever_student_session` function**

Add to `backend/routes/clever_routes.py`, after the existing imports and before `_background_roster_sync`:

```python
def _create_clever_student_session(clever_id, email):
    """Create a student session for a Clever-authenticated student.

    Looks up the student by clever_id (stored as student_id_number during sync),
    finds their class enrollment, and creates a session token.

    Returns dict with token + student info, or None if student not found.
    """
    import secrets as _secrets
    import hashlib
    from datetime import datetime, timezone, timedelta

    sb = _get_supabase_safe()
    if not sb:
        return None

    try:
        # Find student by clever_id (stored as student_id_number during class sync)
        stu_result = sb.table("students").select("id, first_name, last_name, email, teacher_id").eq(
            "student_id_number", clever_id
        ).execute()

        if not stu_result.data:
            # Try by email as fallback
            if email:
                stu_result = sb.table("students").select("id, first_name, last_name, email, teacher_id").eq(
                    "email", email.lower()
                ).execute()
            if not stu_result.data:
                logger.warning("Clever student %s not found in students table", clever_id)
                return None

        student = stu_result.data[0]
        student_id = student["id"]

        # Find class enrollment
        enrollment = sb.table("class_students").select(
            "class_id, classes(id, name, join_code, subject)"
        ).eq("student_id", student_id).execute()

        if not enrollment.data:
            logger.warning("Clever student %s has no class enrollment", clever_id)
            return None

        class_data = enrollment.data[0].get("classes", {})
        class_id = enrollment.data[0]["class_id"]

        # Create session token
        raw_token = _secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires = datetime.now(tz=timezone.utc) + timedelta(hours=8)

        sb.table("student_sessions").insert({
            "student_id": student_id,
            "class_id": class_id,
            "session_token": token_hash,
            "expires_at": expires.isoformat(),
        }).execute()

        return {
            "token": raw_token,
            "student": {
                "id": student_id,
                "first_name": student.get("first_name", ""),
                "last_name": student.get("last_name", ""),
                "email": student.get("email", ""),
            },
            "class": {
                "id": class_id,
                "name": class_data.get("name", ""),
                "join_code": class_data.get("join_code", ""),
                "subject": class_data.get("subject", ""),
            },
        }

    except Exception as e:
        logger.warning("Failed to create Clever student session: %s", str(e))
        return None
```

- [ ] **Step 4: Update the callback to handle students**

In `backend/routes/clever_routes.py`, replace the student rejection block (line ~240-242):

```python
    # Only allow teachers and district admins
    if clever_user["type"] not in ("teacher", "district_admin", "staff"):
        return redirect("/?clever_error=students_use_portal")
```

With:

```python
    # Handle student login — create student session and redirect to portal
    if clever_user["type"] == "student":
        student_session = _create_clever_student_session(
            clever_user["clever_id"],
            clever_user.get("email", ""),
        )
        if student_session:
            # Store token in a short-lived query param for the frontend to pick up
            from urllib.parse import urlencode
            params = urlencode({
                "clever": "1",
                "token": student_session["token"],
            })
            return redirect(f"/student?{params}")
        else:
            return redirect("/?clever_error=student_not_enrolled")

    # Reject unknown roles (contact, etc.)
    if clever_user["type"] not in ("teacher", "district_admin", "staff"):
        return redirect("/?clever_error=unsupported_role")
```

- [ ] **Step 5: Add `student_not_enrolled` error message to frontend**

In `frontend/src/App.jsx`, find the `cleverErrorMessages` object (around line 820) and add:

```javascript
'student_not_enrolled': 'Your account was not found. Ask your teacher to sync the class roster.',
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_clever_student_sso.py tests/test_clever.py tests/test_clever_classes.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/routes/clever_routes.py tests/test_clever_student_sso.py frontend/src/App.jsx
git commit -m "feat: accept Clever student SSO login, create session and redirect to portal"
```

---

### Task 2: Frontend — auto-login student from Clever redirect

**Files:**
- Modify: `frontend/src/components/StudentApp.jsx`

- [ ] **Step 1: Update StudentApp to check for Clever token in URL**

In `frontend/src/components/StudentApp.jsx`, update the `useEffect` to check for `?clever=1&token=...` URL params on mount. If present, store the token and fetch student info, bypassing the login form.

Replace the existing useEffect (lines 11-37) with:

```javascript
useEffect(() => {
    // Check for Clever SSO redirect (token in URL)
    var params = new URLSearchParams(window.location.search);
    var cleverToken = params.get("token");
    var isClever = params.get("clever");

    if (isClever && cleverToken) {
        // Clean URL (remove token from browser bar for security)
        window.history.replaceState({}, "", "/student");

        // Validate the token and fetch session
        fetch("/api/student/session", {
            headers: { "X-Student-Token": cleverToken },
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.valid) {
                localStorage.setItem("student_token", cleverToken);
                localStorage.setItem("student_info", JSON.stringify(data.student || {}));
                localStorage.setItem("student_class", JSON.stringify(data.class_info || {}));
                setStudentInfo(data.student || {});
                setClassInfo(data.class_info || {});
                setLoggedIn(true);
            } else {
                // Token invalid — show login form
                setChecking(false);
            }
        })
        .catch(function() { setChecking(false); })
        .finally(function() { setChecking(false); });
        return;
    }

    // Normal flow: check for existing session in localStorage
    var token = localStorage.getItem("student_token");
    var savedStudent = localStorage.getItem("student_info");
    var savedClass = localStorage.getItem("student_class");

    if (token && savedStudent) {
        fetch("/api/student/session", {
            headers: { "X-Student-Token": token },
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.valid) {
                setStudentInfo(JSON.parse(savedStudent));
                setClassInfo(JSON.parse(savedClass || "{}"));
                setLoggedIn(true);
            } else {
                localStorage.removeItem("student_token");
                localStorage.removeItem("student_info");
                localStorage.removeItem("student_class");
            }
        })
        .catch(function() {})
        .finally(function() { setChecking(false); });
    } else {
        setChecking(false);
    }
}, []);
```

- [ ] **Step 2: Check what `/api/student/session` returns**

The existing session endpoint needs to return student and class info for the Clever flow. Read `backend/routes/student_account_routes.py` to verify the `/api/student/session` response includes `student` and `class_info` fields. If not, the frontend can use what localStorage has (set from the login response).

- [ ] **Step 3: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StudentApp.jsx
git commit -m "feat: auto-login students from Clever SSO redirect token"
```

---

### Task 3: Add "I'm a Student" link to teacher login page

**Files:**
- Modify: `frontend/src/components/LoginScreen.jsx`

- [ ] **Step 1: Add student link**

In `frontend/src/components/LoginScreen.jsx`, find the bottom of the login form and add a link below the "Sign Up" or "Forgot Password" section:

```jsx
<div style={{ textAlign: "center", marginTop: "16px", borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: "16px" }}>
    <a href="/student" style={{ color: "#94a3b8", fontSize: "0.85rem", textDecoration: "none" }}>
        I'm a student — go to Student Portal
    </a>
</div>
```

- [ ] **Step 2: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LoginScreen.jsx
git commit -m "feat: add student portal link to teacher login page"
```

---

### Task 4: Full end-to-end verification

- [ ] **Step 1: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_clever.py tests/test_clever_classes.py tests/test_clever_student_sso.py -v`
Expected: All tests pass (40 + 16 + 3 = 59 minimum)

- [ ] **Step 2: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Clean build

- [ ] **Step 3: Verify backend imports**

Run: `cd /Users/alexc/Downloads/Graider/backend && source ../venv/bin/activate && python -c "from app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Manual test flow**

1. Start backend: `python backend/app.py`
2. Go to `localhost:3000` — verify teacher login still works
3. Verify "I'm a student" link appears on login page
4. Click it — should go to `localhost:3000/student` (student login form)
5. Verify Clever callback handles student role (check logs when a student OAuth redirects)

- [ ] **Step 5: Verify no Clever regression**

1. Teacher Clever login still works
2. Account merging still works
3. Roster sync still creates classes
4. Publish to class still works
5. Student portal login with email + class code still works
