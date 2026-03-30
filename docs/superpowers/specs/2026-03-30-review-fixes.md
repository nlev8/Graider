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
