# School Admin (Principal) Role — Design Spec

## Goal

Add a read-only school admin role so principals can view aggregate grading data, assessment results, and teacher activity across their school — without modifying any teacher's data.

## Scope

**In scope:**
- Admin designation via invite code (district admin creates, principal claims)
- Read-only dashboard tab showing school-wide overview
- Teacher discovery from SIS (OneRoster/Clever) with manual fallback
- Per-teacher drill-down (classes, results, analytics summary)
- Recent activity feed from audit log
- FERPA-compliant: admin scoped to their school's teachers only

**Out of scope:**
- Admin editing teacher settings, rubrics, or assignments
- Admin grading or modifying student scores
- Admin sending emails on behalf of teachers
- Admin accessing AI assistant as another teacher
- Multi-school admin (one admin = one school for Phase 1)
- Student-level data visibility (admin sees aggregate scores, not individual student names)

## Auth Model

### Admin Designation

District admin at `/district` creates an invite:
1. Enters a school name (e.g., "Southwestern Middle School")
2. Optionally assigns specific teacher user IDs (manual fallback)
3. System generates a short invite code (6 chars, expires in 7 days)
4. Stored in `teacher_data` with `teacher_id="system"`, key `admin_invite:{code}`

### Admin Claiming

Principal logs into Graider normally (Supabase email/password). Goes to Settings, enters the invite code. Backend:
1. Validates the invite code exists and hasn't expired
2. Creates `admin_role:{user_id}` in `teacher_data` with `teacher_id="system"`
3. Value: `{user_id, email, school, granted_at, manual_teachers: [...]}`
4. Deletes the used invite code

### Auth Check

On login, frontend calls `GET /api/admin/status`. Backend checks if `admin_role:{user_id}` exists in system storage. Returns `{is_admin: true/false, school: "..."}`. If admin, the "Admin" tab appears in the dashboard.

### `@require_admin` Decorator

New decorator for admin endpoints. Checks:
1. User is authenticated (has valid JWT via `g.user_id`)
2. `admin_role:{user_id}` exists in system storage
3. Returns 403 if not admin

## Teacher Discovery

### SIS-Connected (preferred)

When OneRoster/Clever is configured at the district level:
1. Load district SIS config from `district_sis_config` (system storage)
2. If OneRoster: query `/schools/{school_id}/teachers` to get all teachers at the admin's school
3. If Clever: query sections for the school, extract unique teacher IDs
4. Match SIS teacher records to Graider user IDs via `student_id_number` or email
5. Cache the teacher list (refresh on demand or daily)

### Manual Fallback

When no SIS is configured, or SIS doesn't have school-teacher mappings:
1. District admin assigns teacher user IDs to the admin invite at `/district`
2. These are stored in `admin_role:{user_id}.manual_teachers`
3. Admin dashboard shows only these teachers

### Resolution Order

1. If SIS configured → auto-discover teachers by school
2. Merge with any manually-assigned teachers
3. If no SIS and no manual assignments → admin sees empty dashboard with setup instructions

## Admin Dashboard

### Tab Location

New "Admin" tab in the main dashboard tab bar (alongside Grade, Results, Planner, Analytics, Settings). Only visible when `is_admin: true`.

### Panel 1: Teacher Overview

Table of teachers at the admin's school:
- Teacher name, email
- Number of classes
- Total students (from roster)
- Last grading activity (from audit log)
- Published assessments count
- Click row → expands Panel 3 drill-down

Data source: Teacher list from SIS/manual + per-teacher data from `teacher_data` (settings key for name/email) + `published_assessments`/`published_content` counts + audit log for last activity.

### Panel 2: School-Wide Analytics

Aggregate metrics across all teachers:
- Total students enrolled across all teachers
- Average assessment score (from `published_assessments` + `submissions` + `published_content` + `student_submissions`)
- Grade distribution pie chart (A/B/C/D/F across all assessments)
- Assessments published this week/month
- Completion rate (submissions / expected)

Data source: Direct Supabase queries via service key across the teacher IDs in the admin's school.

### Panel 3: Teacher Drill-Down

When admin clicks a teacher row, expands to show:
- Teacher's classes (from `classes` table filtered by teacher_id)
- Recent published assessments with submission counts and averages
- Grade distribution for this teacher
- Last 10 audit log entries for this teacher

This is a read-only subset of what the teacher sees in their own Results and Analytics tabs.

### Panel 4: Recent Activity Feed

Chronological feed of events across all teachers:
- "Mr. Smith published 'Ch 5 Quiz' (24 students)"
- "Ms. Jones completed grading 'Unit 3 Test' (avg: 82%)"
- "Mr. Smith synced roster (4 classes, 112 students)"

Data source: `audit_log` table filtered to the admin's teacher IDs, last 50 entries.

## Backend

### New File: `backend/routes/admin_routes.py`

Blueprint: `admin_bp` with prefix `/api/admin/`

Endpoints:
- `GET /api/admin/status` — is current user an admin? Returns `{is_admin, school}`
- `POST /api/admin/claim` — claim admin role with invite code. Body: `{code: "ABC123"}`
- `GET /api/admin/teachers` — list teachers at admin's school (SIS + manual)
- `GET /api/admin/overview` — aggregate school-wide stats
- `GET /api/admin/teacher/<teacher_id>/summary` — per-teacher drill-down
- `GET /api/admin/activity` — recent audit log across admin's teachers

### Additions to `backend/routes/district_routes.py`

New endpoints for invite management:
- `POST /api/district/admin-invite` — create invite code (body: `{school, manual_teachers: [{user_id, name, email}]}`)
- `GET /api/district/admins` — list current admins with their school and teacher count
- `DELETE /api/district/admins` — revoke an admin (body: `{user_id}`)
- `GET /api/district/teacher-search?q=smith` — search Graider teachers by name/email for manual assignment

### New Decorator: `backend/utils/auth_decorators.py`

```python
def require_admin(f):
    """Decorator that enforces school admin authentication."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        from backend.storage import load
        admin_role = load(f"admin_role:{user_id}", "system")
        if not admin_role:
            return jsonify({"error": "Admin access required"}), 403
        g.teacher_id = user_id
        g.admin_role = admin_role
        return f(*args, **kwargs)
    return wrapper
```

### Storage Keys

| Key | teacher_id | Purpose |
|-----|-----------|---------|
| `admin_invite:{code}` | `system` | Pending invite (school, manual_teachers, expires_at) |
| `admin_role:{user_id}` | `system` | Granted admin role (school, granted_at, manual_teachers) |

### Teacher Discovery Logic (in `admin_routes.py`)

Three-layer resolution: SIS auto-discover → manual assignment → all-teachers fallback.

**Layer 1: SIS Auto-Discovery (OneRoster/ClassLink)**

```python
def _discover_teachers_from_sis(school_name):
    """Query OneRoster for teachers at a school, match to Graider accounts.

    Steps:
    1. Load district SIS config (district_sis_config, system)
    2. Create OneRosterClient with district credentials
    3. Fetch /schools to find the school_id matching school_name
    4. Fetch /schools/{school_id}/teachers to get teacher records
    5. For each SIS teacher, extract: sourcedId, givenName, familyName, email
    6. Match to Graider user IDs by querying teacher_data for settings entries
       where teacher_email matches the SIS teacher email (case-insensitive)
    7. Return list of {user_id, name, email, sis_sourced_id}
    """
    from backend.storage import load
    from backend.supabase_client import get_supabase

    district_config = load("district_sis_config", "system")
    if not district_config or district_config.get("sis_type") != "oneroster":
        return []

    # Create client and fetch teachers for the school
    from backend.oneroster import OneRosterClient
    import asyncio

    client = OneRosterClient(
        base_url=district_config["base_url"],
        client_id=district_config["client_id"],
        client_secret=district_config["client_secret"],
        token_url=district_config.get("token_url"),
    )

    async def _fetch():
        async with __import__("httpx").AsyncClient(timeout=15.0) as http:
            await client._ensure_token(http)
            # Find school by name
            schools = await client._get_paginated(http, "/schools", "orgs", "schools")
            school_id = None
            for s in schools:
                if s.get("name", "").lower().strip() == school_name.lower().strip():
                    school_id = s.get("sourcedId")
                    break
            if not school_id:
                return []
            # Fetch teachers at this school
            teachers = await client._get_paginated(
                http, f"/schools/{school_id}/teachers", "users", "teachers")
            return teachers

    loop = asyncio.new_event_loop()
    try:
        sis_teachers = loop.run_until_complete(_fetch())
    finally:
        loop.close()

    if not sis_teachers:
        return []

    # Match SIS teachers to Graider accounts by email
    # Query all teacher_data settings entries to build email → user_id map
    db = get_supabase()
    if not db:
        return []

    settings_rows = db.table("teacher_data").select(
        "teacher_id, data"
    ).eq("data_key", "settings").execute()

    email_to_uid = {}
    for row in (settings_rows.data or []):
        data = row.get("data", {})
        if isinstance(data, dict):
            email = (data.get("teacher_email") or "").strip().lower()
            if email:
                email_to_uid[email] = row["teacher_id"]

    matched = []
    for t in sis_teachers:
        sis_email = (t.get("email") or "").strip().lower()
        graider_uid = email_to_uid.get(sis_email)
        matched.append({
            "user_id": graider_uid,  # None if not yet registered in Graider
            "name": (t.get("givenName", "") + " " + t.get("familyName", "")).strip(),
            "email": t.get("email", ""),
            "sis_sourced_id": t.get("sourcedId", ""),
            "registered": graider_uid is not None,
        })

    return matched
```

**Layer 2: Manual Assignment**

The `admin_role:{user_id}` record has `manual_teachers: [{user_id, name, email}]`. These are merged with SIS-discovered teachers, deduplicating by email.

**Layer 3: All-Teachers Fallback**

If both SIS and manual return empty, query `SELECT DISTINCT teacher_id FROM teacher_data WHERE data_key = 'settings'` and load each teacher's name/email from their settings. This is a last resort for deployments without SIS.

**Combined Resolution:**

```python
def _discover_teachers(admin_role):
    """Get list of teachers for this admin. Returns [{user_id, name, email, registered}]."""
    school = admin_role.get("school", "")
    all_teachers = []
    seen_emails = set()

    # 1. SIS auto-discovery
    sis_teachers = _discover_teachers_from_sis(school)
    for t in sis_teachers:
        email = (t.get("email") or "").lower()
        if email:
            seen_emails.add(email)
        all_teachers.append(t)

    # 2. Manual assignments (deduplicate by email)
    for t in admin_role.get("manual_teachers", []):
        email = (t.get("email") or "").lower()
        if email and email not in seen_emails:
            seen_emails.add(email)
            all_teachers.append(t)

    # 3. Fallback: discover from teacher_data if nothing found
    if not all_teachers:
        from backend.supabase_client import get_supabase
        db = get_supabase()
        if db:
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

    return all_teachers
```

### Teacher Lookup for Manual Assignment

The district admin at `/district` needs to assign teachers without knowing Graider UUIDs.

**New endpoint:** `GET /api/district/teacher-search?q=smith`

Queries `teacher_data` where `data_key = 'settings'` and the `data` JSON contains a matching `teacher_name` or `teacher_email` (case-insensitive). Returns `[{user_id, name, email}]`. Limited to 20 results. Requires district admin session.

**UI in DistrictSetup.jsx:** The "School Admins" section has a "Add teachers" search field. District admin types a name or email, sees matching teachers, clicks to add them to the invite's `manual_teachers` list.

## Frontend

### New File: `frontend/src/tabs/AdminTab.jsx`

React component rendered as a tab in the dashboard. Contains:
- Teacher overview table
- School-wide analytics summary
- Teacher drill-down (expandable rows)
- Activity feed

### Modifications

| File | Change |
|------|--------|
| `frontend/src/App.jsx` | Check admin status on login, add Admin tab when `is_admin` |
| `frontend/src/services/api.js` | Add admin API functions |
| `frontend/src/tabs/SettingsTab.jsx` | Add "Claim Admin Access" section with invite code input |
| `frontend/src/components/DistrictSetup.jsx` | Add "School Admins" section for invite management |

## FERPA Compliance

| Requirement | Implementation |
|-------------|---------------|
| Admin scoped to school | Teacher list filtered by SIS school or manual assignment |
| No cross-school visibility | Admin's `admin_role` record specifies school; queries filter by teacher list |
| Read-only access | No mutation endpoints; all admin routes are GET (except claim) |
| Audit logged | Admin data access logged via `audit_log("ADMIN_VIEW_*", ...)` |
| Student PII minimized | Admin sees aggregate scores and counts, not individual student names/responses |
| Teacher data protected | Admin cannot see teacher's AI instructions, rubric notes, or grading style |

## No Database Schema Changes

- Admin roles stored in existing `teacher_data` table with `teacher_id="system"`
- All cross-teacher queries use the backend service key (bypasses RLS)
- No new Supabase tables or columns
- No RLS policy changes

## Phase 2 (Future)

- Multi-school admin (one principal manages multiple schools)
- Department head role (sees only their department's teachers)
- Admin data export (PDF reports for school board)
- Real-time notifications (alert when assessment scores drop below threshold)
- Student-level visibility (with additional FERPA consent)
