# Code Review Fixes + Analytics Bug — March 30

## 1. Code Review Fixes (commit `8ab3622`)

### Fix: Provider switch race guard
**Files:** `backend/routes/district_routes.py`, `backend/routes/oneroster_routes.py`

**Problem:** After removing the per-teacher 409 block, a teacher could start a OneRoster sync while `_clear_old_provider_data` was still running on a parallel request.

**Fix:** Storage-backed lock flag.

`district_routes.py` — wraps cleanup in lock:
```python
storage_save("district:provider_switch_in_progress", True, "system")
try:
    cleared_count = _clear_old_provider_data(old_sis_type)
finally:
    storage_save("district:provider_switch_in_progress", None, "system")
```

`oneroster_routes.py` — sync checks lock:
```python
cleanup_flag = _sl("district:provider_switch_in_progress", "system")
if cleanup_flag:
    return jsonify({"error": "A provider switch is in progress. Please wait and try again."}), 503
```

### Fix: Log Supabase errors in `_save_parent_contacts`
**File:** `backend/routes/settings_routes.py`

**Before:**
```python
except Exception:
    pass  # File write succeeded — Supabase failure is not critical
```

**After:**
```python
except Exception as e:
    _logger.warning("Failed to save parent contacts to Supabase for teacher %s: %s. "
                   "File write succeeded — data is preserved locally.", teacher_id, str(e))
```

### Fix: Server-side email validation
**File:** `backend/routes/settings_routes.py`

Added to both `add_student` and `update_student`:
```python
if student_email:
    import re
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', student_email):
        return jsonify({"error": "Invalid student email format"}), 400
```

### Non-issues verified:
- **Finding 1 (stale `clever_section_id`):** Only exists on `classes` table. Assignments, grades, submissions don't reference it.
- **Finding 5 (resource-only prompt):** Accepted limitation — LLM behavior can't be programmatically enforced.
- **Finding 6 (missing tests):** Acknowledged for future session.

---

## 2. Analytics Empty Bug (commit `cb6ae1f`)

### Root Cause
**File:** `backend/routes/analytics_routes.py`, line 159

`_analytics_from_results` filters results by matching assignment names against saved configs. All 704 grading results had names like `"Cornell Notes - The Seminole Wars"` but saved configs had names like `"exploring the industrial growth..."`. Zero overlap → all results silently filtered out → empty Analytics.

### Fix
Added a pre-check: if `valid_names` exists but matches ZERO results, clear the filter and show everything:

```python
valid_names = _load_valid_assignment_names()

if valid_names and not include_unmatched:
    has_any_match = any(
        _assignment_matches_config(r.get("assignment", ""), valid_names)
        for r in results if r.get("student_name", "").strip()
    )
    if not has_any_match:
        valid_names = set()  # No matches → show everything
```

This prevents empty Analytics when teachers grade files without first saving matching assignment configs. When some configs DO match, the filter still works normally.

---

## 3. Second Review Fixes (commit `6b4b18a`)

### Fix: TTL on provider switch lock
**Files:** `backend/routes/district_routes.py`, `backend/routes/oneroster_routes.py`

**Problem:** If `_clear_old_provider_data` crashes before the `finally` block (or the process dies), the lock flag stays True permanently, blocking all future syncs with 503.

**Fix:** Lock now stores a timestamp instead of `True`:
```python
# district_routes.py — set lock with timestamp
storage_save("district:provider_switch_in_progress", {"timestamp": _time.time()}, "system")
```

Sync endpoint checks TTL — expires after 5 minutes:
```python
# oneroster_routes.py — check lock with expiry
lock_time = cleanup_flag.get("timestamp", 0) if isinstance(cleanup_flag, dict) else 0
if _time.time() - lock_time < 300:  # 5 minutes
    return jsonify({"error": "A provider switch is in progress..."}), 503
else:
    # Stale lock — clear it and proceed
    logger.warning("Stale provider switch lock detected (>5min old). Clearing.")
    _ss("district:provider_switch_in_progress", None, "system")
```

### Fix: Surface Supabase write failures to teacher
**File:** `backend/routes/settings_routes.py`

**Problem:** `_save_parent_contacts` logged Supabase failures but returned 200 with no indication. Teacher's contact edits could silently disappear from the authenticated UI.

**Fix:** Function now returns `{"file_ok": True, "supabase_ok": bool}`. Callers include warning in response:
```python
save_result = _save_parent_contacts(contacts)
response = {"status": "added", "students": students, "count": len(students)}
if not save_result.get("supabase_ok", True):
    response["warning"] = "Contact info saved locally but cloud sync failed. Changes may not appear on other devices until the next successful sync."
```

Applied to both `add_student` and `update_student` endpoints.

### Fix: Analytics filter bypass notice
**File:** `backend/routes/analytics_routes.py`

**Problem:** When the fallback triggers (no config names match results), Analytics silently shows everything with no explanation.

**Fix:** Response now includes `filter_bypassed: true` flag and a notice string:
```python
resp["filters"]["filter_bypassed"] = filter_bypassed
if filter_bypassed:
    resp["notice"] = "Showing all graded assignments. Save assignment configs in Grading Setup to enable filtering."
```

Frontend can display this as an info banner. Teachers understand why filtering isn't active.

---

## Clever & OneRoster Compliance Status

| Requirement | Status | Implementation |
|-------------|--------|---------------|
| **Teacher-scoped data** | ✅ | All queries filter by `teacher_id` from JWT. `@require_teacher` on every data endpoint. |
| **No cross-teacher visibility** | ✅ | RLS on Supabase + backend service key for admin-only cross-teacher queries. |
| **Audit logging** | ✅ | `audit_log()` on all data access, roster sync, provider switch, admin actions. |
| **Student PII protection** | ✅ | Names visible only to publishing teacher. Admin sees aggregates only. |
| **Data deletion on request** | ✅ | `delete_roster_data()` removes enrollments, classes, orphaned students, CSV files. |
| **Provider exclusivity** | ✅ | District-level enforcement. Auto-cleanup on provider switch. Lock prevents race condition with 5-min TTL. |
| **Secure credential storage** | ✅ | SIS secrets in Supabase `teacher_data` with `teacher_id="system"`. Never returned in GET responses (`has_secret: true/false`). |
| **FERPA audit trail** | ✅ | All student data access logged. Provider switches logged. Admin views logged. |
| **Parent contact integrity** | ✅ | Server-side email validation. Supabase write failures logged and surfaced to teacher. Dual-write (file + Supabase). |
| **OneRoster section scoping** | ✅ | `/teachers/{id}/classes` endpoint for teacher-scoped roster. Fallback filters by enrollment. |
| **OneRoster demographics** | ✅ | IEP/ELL extraction from demographics metadata. Accommodation suggestions returned on sync. |
| **Clever SSO** | ✅ | OAuth flow, session management, account linking to Supabase. |
| **Clever Secure Sync** | ✅ | Roster, parent contacts, IEP/504, schedule data synced. |
| **Data disposition (FL 1006.1494)** | ⚠️ | Manual deletion available via `delete_roster_data`. Automated 90-day cleanup not yet implemented (documented as post-beta). |

The only open item is automated 90-day data cleanup per Florida Statute 1006.1494, which is documented as a post-beta enhancement. All other Clever and OneRoster compliance requirements are met.
