# Periodic Roster Sync — Design Spec

## Problem

Rosters only sync when a teacher logs in via Clever/OneRoster or clicks "Sync Now." If a student transfers mid-semester, the teacher's roster is stale until the next manual action. For a pilot deployment at Volusia County, this means teachers could be grading students who are no longer enrolled, or missing new students entirely.

## Solution

A daily background sync triggered by GitHub Actions cron. Every 24 hours, a webhook hits the Graider backend, which iterates over teachers with SIS connections and re-syncs their rosters from the appropriate provider. Students no longer in the SIS are soft-deactivated (`is_active=False`), preserving their grades and history.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trigger mechanism | GitHub Actions cron | Free, no infrastructure, Railway has no native cron. Repo is private (2,000 min/month free; this uses ~15 min/month). |
| Sync scope | Teachers with SIS config + activity in last 30 days | Avoids burning API quota on inactive accounts. Teachers on break whose students haven't logged in are skipped — their roster will sync on next login. |
| Auth | Shared secret header + rate limit | Simple, prevents abuse. Rate-limited to 1 req/5 min to prevent quota exhaustion if secret leaks. |
| Removed students | Soft deactivate (`is_active=False`) | Preserves data, recoverable if SIS glitches |
| Parallelism | Sequential, max 50 teachers per run | Respects Clever 1,200 req/min rate limit. 50-teacher cap ensures completion within GitHub's 6-hour job limit. |

## Architecture

```
GitHub Actions (cron 4 AM ET daily)
    │
    ▼
POST /api/sync/periodic-roster
    Authorization: Bearer <PERIODIC_SYNC_SECRET>
    │
    ▼
sync_routes.py — webhook handler
    │
    ├── Auth: validate secret + rate limit (1 req / 5 min)
    │
    ├── Discover teachers:
    │   ├── Primary: teachers with SIS config (district:sis_config)
    │   └── Filter: only those with session activity in last 30 days
    │   └── Cap: max 50 per run
    │
    ├── For each teacher (sequential):
    │   ├── Determine provider (Clever or OneRoster)
    │   ├── Call existing sync functions
    │   ├── Deactivate students not in current roster
    │   ├── Write audit_log entry to Supabase
    │   └── Collect result
    │
    └── Return JSON summary (fail workflow if any teacher failed)
```

## Components

### 1. Webhook Endpoint (`backend/routes/sync_routes.py`)

New blueprint: `sync_bp` with single route `POST /api/sync/periodic-roster`.

**Auth:** Validates `Authorization: Bearer <token>` against `PERIODIC_SYNC_SECRET` env var. Returns 401 if missing/invalid. Rate-limited to 1 request per 5 minutes via Flask-Limiter (prevents quota exhaustion if secret leaks).

**Teacher discovery:**
1. Query Supabase `teacher_data` for all rows with `data_key='district:sis_config'` — these are teachers with a SIS provider configured
2. Cross-reference against `student_sessions` for `created_at` in last 30 days to filter to active teachers
3. Cap at 50 teachers per run. If more exist, process the 50 most recently active and log a warning. The remaining will be picked up on subsequent runs.

**Per-teacher sync:**
1. Load SIS config to determine provider (`clever` or `oneroster`)
2. Call the appropriate sync function (reusing existing code)
3. Call `deactivate_missing_students()` with the synced external IDs
4. Write an `audit_log` entry: `action="PERIODIC_SYNC"`, `teacher_id`, `details={provider, counts, deactivated}`
5. Collect result: `{teacher_id, provider, status, counts, deactivated, error}`

**Response:**
```json
{
  "synced": 5,
  "failed": 1,
  "skipped": 2,
  "total_teachers": 8,
  "has_failures": true,
  "details": [
    {"teacher_id": "t1", "provider": "clever", "status": "success", "classes": 3, "students": 75, "deactivated": 2},
    {"teacher_id": "t2", "provider": "oneroster", "status": "failed", "error": "Connection timeout"}
  ]
}
```

**Error handling:** Each teacher sync is wrapped in try/except. One teacher failing doesn't stop the others. The `has_failures` flag is `true` if any teacher's status is `"failed"`.

### 2. Student Deactivation (`roster_sync.py`)

New function: `deactivate_missing_students(teacher_id, current_student_external_ids, provider)`

After `sync_roster_to_db()` upserts the current roster, this function:
1. Queries all `is_active=True` students for this teacher from Supabase
2. Compares their `student_id_number` against the set of external IDs just synced
3. Only compares students whose `student_id_number` matches the provider prefix:
   - Clever students have no prefix (raw Clever IDs)
   - OneRoster students are prefixed with `oneroster:`
   - Manual students are prefixed with `manual-`
   - This prevents deactivating manual students when syncing Clever, or vice versa
4. Any provider-matched student in the DB but NOT in the current roster gets `UPDATE students SET is_active=False`
5. Returns count of deactivated students

**Safety:**
- Only deactivates students from the same provider — manual students are never touched
- Never deletes — only sets `is_active=False`
- If a student reappears in a future sync, `sync_roster_to_db()` upserts with `is_active=True`, automatically reactivating them

**`student_id_number` field consistency:**
- Clever: set to the Clever user `id` (e.g., `"5f3c..."`) by `_sync_classes_to_db()` in `clever_routes.py`
- OneRoster: set to `"oneroster:{sourcedId}"` by `normalize_roster()` in `oneroster.py`
- Manual: set to `"manual-{uuid}"` by `add_student()` in `settings_routes.py`
- The provider prefix ensures deactivation only affects the correct provider's students

### 3. GitHub Actions Workflow (`.github/workflows/roster-sync.yml`)

```yaml
name: Periodic Roster Sync

on:
  schedule:
    - cron: '0 9 * * 1-5'  # 4:00 AM ET weekdays only (no sync Sat/Sun)
  workflow_dispatch: {}     # Manual trigger for testing

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 30     # Kill if stuck (50 teachers should finish in ~10 min)
    steps:
      - name: Trigger roster sync
        run: |
          response=$(curl -s -w "\n%{http_code}" -X POST \
            https://app.graider.live/api/sync/periodic-roster \
            -H "Authorization: Bearer ${{ secrets.PERIODIC_SYNC_SECRET }}" \
            -H "Content-Type: application/json" \
            --max-time 600)
          http_code=$(echo "$response" | tail -1)
          body=$(echo "$response" | head -n -1)
          echo "$body" | jq . || echo "$body"

          # Fail on HTTP error
          if [ "$http_code" -ne 200 ]; then
            echo "::error::Roster sync failed with HTTP $http_code"
            exit 1
          fi

          # Fail if any teacher sync failed (partial failure)
          has_failures=$(echo "$body" | jq -r '.has_failures // false')
          if [ "$has_failures" = "true" ]; then
            failed_count=$(echo "$body" | jq '.failed')
            echo "::warning::$failed_count teacher sync(s) failed — check details"
            exit 1
          fi
```

**Features:**
- Runs weekdays at 9:00 UTC (4 AM ET) — no point syncing on weekends
- `workflow_dispatch` allows manual trigger from GitHub Actions UI for testing
- 30-minute timeout — prevents runaway jobs from consuming Actions minutes
- `--max-time 600` on curl — 10 min HTTP timeout
- Fails on HTTP error OR partial teacher failures (triggers GitHub email notification)
- Logs full response body for debugging

**Monitoring:** GitHub sends email notifications on workflow failure by default. If the workflow hasn't run in 24 hours, GitHub's "stale workflow" notification will alert. For additional monitoring, the `audit_log` table in Supabase provides a queryable history of all sync runs.

### 4. Environment Configuration

| Variable | Where | Value |
|----------|-------|-------|
| `PERIODIC_SYNC_SECRET` | Railway env vars | Random 32-char token |
| `PERIODIC_SYNC_SECRET` | GitHub Actions secrets | Same token |

Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

**Secret rotation:** Rotate quarterly by generating a new token, updating Railway env var first, then GitHub secret. The old token is invalidated immediately when Railway's env var changes (Railway restarts the service).

### 5. Audit Logging

Every periodic sync run writes to the existing `audit_log` Supabase table:

```python
# Per-teacher entry
audit_log(
    action="PERIODIC_SYNC",
    teacher_id=teacher_id,
    details={
        "provider": "clever",
        "classes": 3,
        "students": 75,
        "deactivated": 2,
        "status": "success",
        "triggered_by": "cron",
    }
)
```

**Retention:** `audit_log` entries follow the existing retention policy (90 days per Florida Statute 1006.1494, implemented as a post-beta cleanup task). Sync audit entries use the same table and lifecycle as all other audit events.

## What This Does NOT Include

- **No retry queue** — if a teacher's sync fails, the next day's run catches it
- **No sync status UI** — teachers don't see background syncs (they already have "Sync Now")
- **No Clever Events API** — that's incremental webhook-based sync, a future enhancement
- **No parallel syncing** — sequential is safer for rate limits; 50-teacher cap keeps runtime under 10 min
- **No accommodation re-application** — sync updates roster only; accommodations remain teacher-controlled
- **No weekend syncs** — rosters don't change on weekends; saves Actions minutes

## Testing Strategy

- Unit tests for `deactivate_missing_students()` with mocked Supabase — verify provider-scoped deactivation, manual students untouched, reactivation on reappearance
- Unit tests for the webhook endpoint — auth validation (valid/invalid/missing secret), rate limiting, teacher discovery, per-teacher error isolation, `has_failures` flag
- Integration test calling the endpoint with mocked Clever/OneRoster responses — verify full flow from teacher discovery through deactivation
- YAML validation for the workflow file
- Manual test via `workflow_dispatch` after deployment

## FERPA Compliance

- Endpoint requires auth (shared secret) — no public access to student data
- Rate-limited to 1 req/5 min — prevents quota exhaustion attacks
- All sync operations scoped by `teacher_id` — no cross-tenant data access
- Every sync run logged to `audit_log` table with teacher_id, provider, counts, timestamp
- Audit entries retained per Florida Statute 1006.1494 (90-day minimum)
- Deactivation preserves records (no data deletion)
