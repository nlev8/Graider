# Hardening Phase 2: Error Handling + Observability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adopt handle_route_errors decorator, add structured logging, request correlation IDs, and Supabase-based audit trail. Brings Error Handling from 7→9 and Observability from 5→8.

**Architecture:** Create a shared logging service, adopt existing error handler decorator, add correlation IDs to Flask request context.

---

## Task 1: Adopt handle_route_errors across all route files

**Files:** All route files in `backend/routes/`

### Step 1.1: Audit existing decorator

- [ ] Read `backend/utils/errors.py` and verify `handle_route_errors` works as expected. It should log exceptions and return a standard error response.

### Step 1.2: Apply to all route files

- [ ] For each route file, replace manual `try/except` blocks with the `@handle_route_errors` decorator where appropriate. Start with the smallest files first.

- [ ] Keep manual try/except only where specific error handling is needed (e.g., returning `previous_results` on duplicate submission).

---

## Task 2: Add request correlation IDs

**Files:**
- Modify: `backend/app.py` (before_request hook)
- Create: `backend/utils/logging_utils.py`

### Step 2.1: Generate correlation ID per request

- [ ] In `app.py` `before_request`, generate a UUID and store in `g.request_id`:
```python
import uuid
g.request_id = str(uuid.uuid4())[:8]
```

### Step 2.2: Include in all log messages

- [ ] Create a logging filter that automatically adds `request_id` to log records. Apply to all loggers.

---

## Task 3: Supabase-based audit logging

**Files:**
- Modify: `backend/app.py` (audit_log function)

### Step 3.1: Write audit events to Supabase

- [ ] Update `audit_log()` to write to a Supabase `audit_log` table in addition to the local file. Table: `(id, timestamp, teacher_id, action, details)`.

### Step 3.2: Audit key actions

- [ ] Add `audit_log()` calls to: publish, delete assessment, grade submission, accommodation changes, roster sync, data deletion.

---

## Task 4: Background thread error recovery

**Files:**
- Modify: `backend/services/portal_grading.py`

### Step 4.1: Update submission status on thread failure

- [ ] In `run_portal_grading_thread`, the outer `except` block (final catch-all) should update the Supabase submission record to `status: "grading_failed"` instead of leaving it in `partial`.

### Step 4.2: Add startup recovery

- [ ] On app startup, query for submissions with `status: "partial"` older than 30 minutes and mark them as `grading_failed`. This handles threads killed by deployment.

---

## Verification

- [ ] Run full test suite
- [ ] Verify audit events written to Supabase
- [ ] Verify request_id appears in log output

**Expected score improvement:**
- Error Handling: 7 → 9/10
- Debugging/Observability: 5 → 8/10
