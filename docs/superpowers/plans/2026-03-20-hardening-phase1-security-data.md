# Hardening Phase 1: Security + Data Integrity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all critical security vulnerabilities and data integrity issues. Brings Security from 5→8 and Data Integrity from 5→8.

**Architecture:** Targeted fixes — no structural refactoring. Each task is independent and can be deployed individually.

**Tech Stack:** Python/Flask, Supabase

---

## Task 1: Path traversal protection on all file endpoints

**Files:**
- Modify: `backend/routes/assignment_routes.py`
- Modify: `backend/routes/student_portal_routes.py`

### Step 1.1: Add secure_filename to download endpoints

- [ ] In `backend/routes/assignment_routes.py`, find the 4 download endpoints (`/api/download-document/<filename>`, `/api/download-worksheet/<filename>`, `/api/download-csv/<filename>`, `/api/download-export/<filename>`). Add `from werkzeug.utils import secure_filename` at the top of the file. In each endpoint, sanitize the filename parameter:

```python
filename = secure_filename(filename)
if not filename:
    return jsonify({"error": "Invalid filename"}), 400
```

### Step 1.2: Sanitize assignment name parameter

- [ ] In `backend/routes/assignment_routes.py`, find the assignment load (`/api/load-assignment`) and delete (`/api/delete-assignment`) endpoints. The `name` query parameter is used in `os.path.join()`. Add validation:

```python
import re
name = request.args.get('name', '')
if not name or not re.match(r'^[\w\s\-\.]+$', name):
    return jsonify({"error": "Invalid assignment name"}), 400
```

### Step 1.3: Verify saved assessment endpoints

- [ ] In `backend/routes/student_portal_routes.py`, verify that `load_saved_assessment` and `delete_saved_assessment` already have path traversal protection (they were fixed in a prior session). If not, add `secure_filename()`.

- [ ] Run: `python -m pytest tests/ -q --ignore=tests/load`

- [ ] Commit: `git commit -m "security: path traversal protection on file endpoints"`

---

## Task 2: Narrow PUBLIC_PREFIXES in auth middleware

**Files:**
- Modify: `backend/auth.py`

### Step 2.1: Replace broad prefix with explicit paths

- [ ] In `backend/auth.py`, find `PUBLIC_PREFIXES` (around line 47-50). Currently includes `/api/student/` which makes ALL student endpoints skip JWT auth. Replace with explicit public paths:

```python
PUBLIC_PREFIXES = (
    '/api/clever/',
    '/api/student/join/',      # Anonymous join-code portal
    '/api/student/submit/',    # Anonymous submission (join-code)
)

PUBLIC_EXACT = (
    '/api/clever/health',
    '/api/clever/callback',
    '/api/clever/login-url',
    '/api/clever/student-token',
    '/api/student/login',      # Student email+code login
    '/api/student/session',    # Session validation
)
```

The authenticated student endpoints (`/api/student/dashboard`, `/api/student/content/<id>`) validate their own session tokens via `X-Student-Token` header, so they don't need JWT but also shouldn't be in PUBLIC_PREFIXES. Add them to PUBLIC_EXACT or let them through with a note:

```python
# Student endpoints use X-Student-Token (not JWT) for auth
'/api/student/dashboard',
'/api/student/content/',
```

### Step 2.2: Test that Clever SSO still works

- [ ] Run: `python -m pytest tests/ -k "clever" -q`
- [ ] Verify student portal endpoints are accessible without JWT

- [ ] Commit: `git commit -m "security: narrow PUBLIC_PREFIXES to explicit student endpoints"`

---

## Task 3: Fix error detail leakage

**Files:**
- Modify: `backend/routes/assignment_player_routes.py`

### Step 3.1: Replace str(e) with generic messages

- [ ] Search `assignment_player_routes.py` for `str(e)` in JSON responses. Replace each with `"An internal error occurred"`. Keep the `_logger.exception()` call for server-side logging.

- [ ] Commit: `git commit -m "security: stop leaking error details to client"`

---

## Task 4: Fix submission race condition

**Supabase migration required.**

### Step 4.1: Add unique constraint

- [ ] Run this SQL in Supabase SQL editor:

```sql
-- Prevent duplicate submissions for same student on same assessment
CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_unique_student
ON submissions(join_code, student_name)
WHERE student_name IS NOT NULL;

-- Prevent duplicate submissions for class-based (authenticated) path
CREATE UNIQUE INDEX IF NOT EXISTS idx_student_submissions_unique
ON student_submissions(student_id, content_id)
WHERE attempt_number = 1;
```

### Step 4.2: Handle constraint violation in submit handlers

- [ ] In `student_portal_routes.py` submit handler, wrap the insert in a try/except that catches the unique constraint violation and returns the "already submitted" response.

- [ ] In `student_account_routes.py` submit handler, same pattern.

- [ ] Commit: `git commit -m "data: unique constraints prevent duplicate submissions"`

---

## Task 5: Fix deprecated datetime usage

**Files:**
- Modify: `backend/storage.py`

### Step 5.1: Replace datetime.utcnow()

- [ ] Search `storage.py` for `datetime.utcnow()`. Replace with `datetime.now(tz=timezone.utc)`. Add `from datetime import timezone` if not already imported.

- [ ] Commit: `git commit -m "data: replace deprecated datetime.utcnow()"`

---

## Task 6: Move Clever links to Supabase

**Files:**
- Modify: `backend/auth.py`

### Step 6.1: Use storage.py instead of local JSON

- [ ] Replace `_CLEVER_LINKS_PATH` file-based storage with `storage.save('clever_link:{clever_id}', data, teacher_id)` and `storage.load('clever_link:{clever_id}', teacher_id)`. This makes Clever account links persist across Railway deployments and work with multiple workers.

- [ ] Add `clever_link:` key mapping to `storage.py:_key_to_filepath()`.

- [ ] Commit: `git commit -m "security: move Clever links from filesystem to Supabase"`

---

## Task 7: Shared require_teacher decorator

**Files:**
- Create: `backend/utils/auth_decorators.py`
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `backend/routes/student_account_routes.py`
- Modify: `backend/routes/lesson_routes.py`

### Step 7.1: Create shared module

- [ ] Create `backend/utils/auth_decorators.py`:

```python
"""Shared authentication decorators for route handlers."""
import functools
from flask import g, jsonify


def require_teacher(f):
    """Decorator that enforces teacher authentication.
    Sets g.teacher_id for use in the wrapped route handler.
    Returns 401 if no authenticated teacher session exists."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        teacher_id = getattr(g, 'user_id', None)
        if not teacher_id:
            return jsonify({"error": "Authentication required"}), 401
        g.teacher_id = teacher_id
        return f(*args, **kwargs)
    return wrapper
```

### Step 7.2: Replace local definitions

- [ ] In each of the 3 route files, replace the local `require_teacher` definition with:
```python
from backend.utils.auth_decorators import require_teacher
```

- [ ] Remove the local `functools` import if no longer needed.

- [ ] Run: `python -m pytest tests/ -q --ignore=tests/load`

- [ ] Commit: `git commit -m "quality: shared require_teacher decorator"`

---

## Verification

- [ ] Run full test suite: `python -m pytest tests/ -q --ignore=tests/load`
- [ ] Build frontend: `cd frontend && npm run build`
- [ ] Verify Clever SSO flow works (manual test or existing tests)
- [ ] Push to Railway

**Expected score improvement:**
- Security: 5 → 8/10
- Data Integrity: 5 → 8/10
- Code Quality: 5 → 6/10 (shared decorator)
