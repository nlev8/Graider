# Submission Confirmation Emails via Outlook (Queue + Batch) — Revised

## Context

Students need confirmation emails after submitting portal assignments to prevent double-submissions. Resend (`noreply@graider.live`) gets blocked by school district email filters. Queue pending confirmations in Supabase and let the teacher batch-send them via existing Playwright/Outlook automation — emails arrive from the teacher's district address.

The confirmation email also lists assignments the student has NOT yet submitted, so they know what's still outstanding.

## Plan

### 1. SQL — New `submission_confirmations` table

```sql
CREATE TABLE IF NOT EXISTS submission_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES student_submissions(id) ON DELETE CASCADE UNIQUE,
    teacher_id UUID NOT NULL,
    student_email TEXT NOT NULL,
    student_name TEXT NOT NULL,
    assignment_title TEXT NOT NULL,
    attempt_number INTEGER DEFAULT 1,
    missing_assignments JSONB DEFAULT '[]',
    submitted_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'sent', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_confirmations_status ON submission_confirmations(status);
CREATE INDEX IF NOT EXISTS idx_confirmations_teacher ON submission_confirmations(teacher_id, status);
```

Key safeguards:
- `UNIQUE` on `submission_id` — prevents duplicate queue rows for same submission
- `teacher_id` column — scopes queries so teachers only see their own
- `processing` status — for safe Playwright handoff
- `missing_assignments` JSONB — array of assignment titles the student hasn't submitted yet

### 2. Backend — Queue confirmation on submission

**File:** `backend/routes/student_account_routes.py` — `submit_student_work()`

Replace the Resend email block (lines 751-776) with:
- Add `teacher_id` to student select: `'first_name, last_name, student_id_number, period, email, teacher_id'`
- Fetch `published_content.title` for the submitted assignment
- Look up all active `published_content` for the student's `class_id`
- Look up all `student_submissions` for this student across those content IDs
- Compute missing = published titles that have no submission from this student
- Insert into `submission_confirmations` with status `'pending'` and `missing_assignments` JSON array
- UNIQUE constraint prevents duplicates; wrap insert in try/except to skip gracefully on conflict
- Remove `import threading` (no longer needed)

### 3. Backend — New endpoints (teacher-authenticated)

**File:** `backend/routes/student_account_routes.py`

**`POST /api/send-submission-confirmations`** — teacher-only:
- Auth via `_get_teacher_id()`
- Fetch all `submission_confirmations` where `status = 'pending'` AND `teacher_id = teacher_id`
- Mark them as `'processing'` immediately
- Build Outlook email array: `{to, cc:"", subject, body, student_name}`
- Subject: `"Submission Confirmed — {assignment_title}"`
- Body template:
  ```
  Hi {first_name},

  Your submission for "{assignment_title}" was received successfully.

  Attempt: #{attempt}
  Submitted: {timestamp}

  [If attempt > 1:]
  This is attempt #{attempt}. Your previous submission(s) are also on file.

  [If missing_assignments is not empty:]
  Assignments still due:
  - {title1}
  - {title2}

  — {teacher_name}
  ```
- Import and call `launch_outlook_sender(emails)` from `backend.routes.email_routes`
- On launch success: return `{status: "started", total: N, confirmation_ids: [...]}`
- On launch failure: revert all to `'pending'`, return error

**`POST /api/mark-confirmations-sent`** — called after Outlook send completes:
- Mark successful IDs as `'sent'` with `sent_at = now()`
- Mark failed IDs as `'pending'` (retryable)

### 4. Backend — Piggyback count on portal submissions

**File:** `backend/routes/student_account_routes.py` — `get_portal_submissions()`

Add `pending_confirmations` count to existing response. No separate poll endpoint.

### 5. Frontend — "Send Confirmations" button

**File:** `frontend/src/App.jsx`

- New state: `pendingConfirmations`
- Extract count from portal submissions response
- Button in Portal Submissions header: "Send Confirmations (N)" with Mail icon
- Disabled when: count is 0, Outlook sending, or no VPortal creds
- onClick: confirm → POST → start Outlook polling → mark sent after completion
- Reuses existing `outlookSendPolling` and `outlookSendStatus`

**File:** `frontend/src/services/api.js` — 2 new API functions

### Key files
- `supabase_student_portal_schema.sql` — add table DDL
- `backend/routes/student_account_routes.py` — modify submit + portal-submissions, add 2 endpoints
- `frontend/src/App.jsx` — state + button (~20 new lines)
- `frontend/src/services/api.js` — 2 new API functions
- `backend/routes/email_routes.py` — read-only, import `launch_outlook_sender`

### Verification
1. Run SQL in Supabase to create `submission_confirmations` table
2. Student submits → row in `submission_confirmations` with status `pending` and `missing_assignments` populated
3. Results tab shows "Send Confirmations (N)" button with count
4. Teacher clicks → Outlook opens, sends from district email
5. Email includes submitted assignment confirmation + list of still-due assignments
6. After send → confirmations marked `sent`, count drops to 0
7. Re-submission → UNIQUE prevents duplicate queue row
8. Student with no email → no row queued, submission succeeds
9. Playwright failure → unsent confirmations revert to `pending`
10. `npm run build` passes
