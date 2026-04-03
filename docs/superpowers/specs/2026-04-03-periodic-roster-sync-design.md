# Periodic Roster Sync — Design Spec

## Problem

Rosters only sync when a teacher logs in via Clever/OneRoster or clicks "Sync Now." If a student transfers mid-semester, the teacher's roster is stale until the next manual action. For a pilot deployment at Volusia County, this means teachers could be grading students who are no longer enrolled, or missing new students entirely.

## Solution

A daily background sync triggered by GitHub Actions cron. Every 24 hours, a webhook hits the Graider backend, which iterates over recently active teachers and re-syncs their rosters from the appropriate SIS provider. Students no longer in the SIS are soft-deactivated (`is_active=False`), preserving their grades and history.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trigger mechanism | GitHub Actions cron | Free, no infrastructure, Railway has no native cron |
| Sync scope | Teachers active in last 30 days | Avoids burning API quota on inactive accounts |
| Auth | Shared secret header | Simple, prevents abuse |
| Removed students | Soft deactivate (`is_active=False`) | Preserves data, recoverable if SIS glitches |
| Parallelism | Sequential per teacher | Respects Clever 1,200 req/min rate limit |

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
    ├── Query Supabase: teachers with session in last 30 days
    │
    ├── For each teacher:
    │   ├── Determine provider (Clever or OneRoster) from stored config
    │   ├── Call existing sync functions:
    │   │   ├── Clever: sync_roster() → _sync_classes_to_db()
    │   │   └── OneRoster: OneRosterClient.fetch_roster() → normalize_roster() → sync_roster_to_db()
    │   ├── Deactivate students not in current roster
    │   └── Log result (success/failure/skip)
    │
    └── Return JSON summary
```

## Components

### 1. Webhook Endpoint (`backend/routes/sync_routes.py`)

New blueprint: `sync_bp` with single route `POST /api/sync/periodic-roster`.

**Auth:** Validates `Authorization: Bearer <token>` against `PERIODIC_SYNC_SECRET` env var. Returns 401 if missing/invalid.

**Logic:**
1. Query `student_sessions` table for distinct `teacher_id` values with `created_at` in last 30 days. This identifies teachers who have active students (and thus active SIS connections).
2. For each teacher, load their SIS config:
   - Check `district:sis_config` for provider type (`clever` or `oneroster`)
   - If no config, skip (manual-only teacher)
3. Call the appropriate sync function (reusing existing code — no new sync logic)
4. After sync, call deactivation step
5. Collect results per teacher: `{teacher_id, provider, status, counts, error}`

**Response:**
```json
{
  "synced": 5,
  "failed": 1,
  "skipped": 2,
  "total_teachers": 8,
  "details": [
    {"teacher_id": "t1", "provider": "clever", "status": "success", "classes": 3, "students": 75},
    {"teacher_id": "t2", "provider": "oneroster", "status": "failed", "error": "Connection timeout"}
  ]
}
```

**Error handling:** Each teacher sync is wrapped in try/except. One teacher failing doesn't stop the others. Failures are logged and reported in the response.

### 2. Student Deactivation (`roster_sync.py`)

New function: `deactivate_missing_students(teacher_id, current_student_external_ids)`

After `sync_roster_to_db()` upserts the current roster, this function:
1. Queries all `is_active=True` students for this teacher from Supabase
2. Compares their `student_id_number` against the set of external IDs just synced
3. Any student in the DB but NOT in the current roster gets `UPDATE students SET is_active=False WHERE id=X`
4. Returns count of deactivated students

**Safety:** Only deactivates — never deletes. If a student reappears in a future sync, `sync_roster_to_db()` already upserts with `is_active=True`, automatically reactivating them.

### 3. GitHub Actions Workflow (`.github/workflows/roster-sync.yml`)

```yaml
name: Periodic Roster Sync

on:
  schedule:
    - cron: '0 9 * * *'  # 4:00 AM ET (UTC-5) / 5:00 AM EDT (UTC-4)
  workflow_dispatch: {}    # Manual trigger for testing

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger roster sync
        run: |
          response=$(curl -s -w "\n%{http_code}" -X POST \
            https://app.graider.live/api/sync/periodic-roster \
            -H "Authorization: Bearer ${{ secrets.PERIODIC_SYNC_SECRET }}" \
            -H "Content-Type: application/json")
          http_code=$(echo "$response" | tail -1)
          body=$(echo "$response" | head -n -1)
          echo "$body" | jq . || echo "$body"
          if [ "$http_code" -ne 200 ]; then
            echo "::error::Roster sync failed with HTTP $http_code"
            exit 1
          fi
```

**Features:**
- Runs daily at 9:00 UTC (4 AM ET)
- `workflow_dispatch` allows manual trigger from GitHub Actions UI for testing
- Logs the full response body
- Fails the workflow if HTTP status is not 200 (triggers GitHub email notification)

### 4. Environment Configuration

| Variable | Where | Value |
|----------|-------|-------|
| `PERIODIC_SYNC_SECRET` | Railway env vars | Random 32-char token |
| `PERIODIC_SYNC_SECRET` | GitHub Actions secrets | Same token |

Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## What This Does NOT Include

- **No retry queue** — if a teacher's sync fails, the next day's run catches it
- **No sync status UI** — teachers don't see background syncs (they already have "Sync Now")
- **No Clever Events API** — that's incremental webhook-based sync, a future enhancement
- **No parallel syncing** — sequential is safer for rate limits
- **No accommodation re-application** — sync updates roster only; accommodations remain teacher-controlled

## Testing Strategy

- Unit tests for `deactivate_missing_students()` with mocked Supabase
- Unit tests for the webhook endpoint (auth validation, teacher discovery, error handling)
- Integration test calling the endpoint with mocked provider responses
- Manual test via `workflow_dispatch` after deployment

## FERPA Compliance

- Endpoint requires auth (shared secret) — no public access to student data
- All sync operations scoped by `teacher_id` — no cross-tenant data access
- Audit log entry for each periodic sync run
- Deactivation preserves records (no data deletion)
