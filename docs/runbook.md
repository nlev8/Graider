# Graider Operations Runbook

Production: `app.graider.live` (Railway) | Database: Supabase | Frontend: React (Vite) served by Flask

---

## 1. Grading Thread Hangs

**Symptoms**: UI stuck on "Grading...", progress stops updating, `/api/status` returns `is_running: true` indefinitely.

```bash
# Check grading status
curl https://app.graider.live/api/status

# Force stop the grading thread
curl -X POST https://app.graider.live/api/stop-grading

# If stop-grading doesn't respond, the worker is truly stuck — restart the Railway service
railway service restart
```

**Common causes**: Large files (>10MB) timing out on parse, OpenAI API hanging without timeout, malformed DOCX causing infinite loop in extraction.

**Recovery**: After restart, grading state resets (`is_running: false`). No data loss — partial results are written to `grading_state["results"]` incrementally. Students won't be affected; grading is teacher-side only.

---

## 2. Supabase Outage

**Symptoms**: 500 errors on student login, class creation, roster sync. Teacher-side grading (file-based) continues working.

```bash
# Verify Supabase connectivity
curl https://app.graider.live/healthz
curl https://app.graider.live/api/clever/health

# Check Supabase status page
# https://status.supabase.com

# Check directly (replace with your project URL)
curl "$SUPABASE_URL/rest/v1/" -H "apikey: $SUPABASE_SERVICE_KEY"
```

**What still works**: File-based grading, rubric/settings (saved to `~/.graider_*` files), lesson plan generation.

**What breaks**: Student portal, class management, published assessments, submissions, audit log writes, Clever roster sync.

**Recovery**: Supabase auto-recovers. No manual intervention needed. Queued audit log entries in `~/.graider_audit.log` persist locally regardless of Supabase status.

---

## 3. Railway Container Crash

```bash
# Check recent logs
railway logs --tail 100

# Or use the Railway dashboard:
# https://railway.app/dashboard → Graider project → Deployments → View Logs
```

**Common causes**:
- **ImportError**: Missing package — check `requirements.txt` matches what's imported.
- **Missing env var**: `FLASK_SECRET_KEY`, `SUPABASE_URL`, or `SUPABASE_SERVICE_KEY` not set. App will crash on startup.
- **Port binding**: Railway sets `PORT` automatically. App must bind to `0.0.0.0:$PORT`.
- **OOM kill**: Large file processing or too many concurrent grading threads. Check for `SIGKILL` in logs.

```bash
# Verify all required env vars are set
railway variables

# Redeploy from latest commit
railway up
```

---

## 4. Rate Limiting Triggered

**Symptoms**: 429 responses from the API, students getting "too many requests" errors.

```bash
# Check rate limit status from logs
railway logs --tail 50 | grep -i "rate"

# Test a specific endpoint
curl -v https://app.graider.live/api/student/join/TESTCODE 2>&1 | grep -E "429|X-RateLimit"
```

**Rate limits are configured in `backend/app.py`** via Flask-Limiter. Defaults apply per-IP.

```bash
# To adjust, update the limiter decorators in app.py, e.g.:
# @limiter.limit("30/minute") → @limiter.limit("60/minute")
```

**Redis is REQUIRED in production.** `backend/extensions.py:19` hard-fails the boot if `FLASK_ENV=production` and `REDIS_URL` is unset, because Flask-Limiter's per-worker fallback would let attackers bypass rate limits by routing requests across workers. (The explicit boot check only enforces presence. Unreachable URLs surface at first connection; some URL-format errors are rejected immediately by `redis.from_url` or Flask-Limiter storage parsing during initialization.) The earlier "Redis-less is functional" note in this runbook was incorrect for production deployments — only local dev runs without Redis. See `docs/DEPLOYMENT.md` for Railway provisioning.

---

## 5. Audit Log Review (FERPA)

**Local file** (always written, survives Supabase outages):

```bash
# On the Railway container or local dev
cat ~/.graider_audit.log | tail -50

# Search for a specific teacher or action
grep "teacher_id_here" ~/.graider_audit.log
grep "delete" ~/.graider_audit.log
```

**Supabase table** (`audit_log`):

```sql
-- Recent audit entries
SELECT action, teacher_id, timestamp, details
FROM audit_log
ORDER BY timestamp DESC
LIMIT 50;

-- All actions for a specific teacher
SELECT * FROM audit_log
WHERE teacher_id = 'TEACHER_ID'
ORDER BY timestamp DESC;

-- Data access events (for FERPA reporting)
SELECT * FROM audit_log
WHERE action IN ('view_student_data', 'export_data', 'delete_student')
ORDER BY timestamp DESC;
```

---

## 6. Student Data Deletion Request (FERPA Compliance)

When a parent/school requests deletion of a student's data:

```bash
# 1. Get a summary of all data held for the teacher/student
curl -H "Authorization: Bearer TEACHER_TOKEN" \
  https://app.graider.live/api/ferpa/data-summary

# 2. Delete Clever-sourced data (roster, accommodations, etc.)
curl -X POST -H "Authorization: Bearer TEACHER_TOKEN" \
  https://app.graider.live/api/clever/delete-data

# 3. Delete ALL student data (submissions, enrollments, sessions)
curl -X POST -H "Authorization: Bearer TEACHER_TOKEN" \
  https://app.graider.live/api/ferpa/delete-all-data
```

**Manual Supabase cleanup** (if API deletion is insufficient):

```sql
-- Remove specific student
DELETE FROM student_submissions WHERE student_id = 'STUDENT_ID';
DELETE FROM class_students WHERE student_id = 'STUDENT_ID';
DELETE FROM student_sessions WHERE student_id = 'STUDENT_ID';
DELETE FROM students WHERE id = 'STUDENT_ID';
```

**Post-deletion**: Verify via `audit_log` that deletion was recorded. Confirm with `GET /api/ferpa/data-summary` that no data remains.

---

## 7. Clever SSO Issues

```bash
# Check Clever integration health (config + API connectivity)
curl https://app.graider.live/api/clever/health
```

**Common problems**:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `redirect_uri_mismatch` | `CLEVER_REDIRECT_URI` doesn't match Clever dashboard | Update env var to match exactly |
| `invalid_client` | Wrong `CLEVER_CLIENT_ID` or `CLEVER_CLIENT_SECRET` | Verify in Clever dashboard → App Settings |
| Health returns `"clever_api": false` | `CLEVER_DISTRICT_TOKEN` expired or invalid | Regenerate in Clever dashboard |
| Students can't log in | District not connected or roster not synced | Run `POST /api/clever/sync-roster` |
| Missing IEP/ELL data | District on Clever Library (free tier) | IEP/ELL requires Clever Complete (paid) |

```bash
# Force a roster re-sync
curl -X POST -H "Authorization: Bearer TEACHER_TOKEN" \
  https://app.graider.live/api/clever/sync-roster

# Check Clever's own status
# https://status.clever.com
```

---

## 8. High Memory / CPU

**Symptoms**: Slow responses, Railway metrics showing high resource usage, gunicorn workers being killed.

**Common causes**:
- Large file parsing (Word docs >10MB with embedded images)
- Multiple concurrent grading threads
- Memory leak in long-running grading sessions

```bash
# Check Railway resource usage
# Railway dashboard → Graider → Metrics tab

# Check gunicorn worker status in logs
railway logs --tail 100 | grep -E "worker|SIGKILL|OOM|memory"
```

**Gunicorn config** (2 workers, 120s timeout, 30s graceful-timeout):
- Workers auto-recycle on timeout (120s). If a grading request exceeds this, the worker is killed and restarted.
- The 30s graceful-timeout gives in-flight requests time to finish during deploys.

**Mitigations**:
- Reject files >10MB at upload (`/api/parse-document`)
- Limit concurrent grading to 1 thread per teacher (enforced by `grading_state["is_running"]` check)
- If persistent OOM, increase Railway instance size or reduce worker count to 1

```bash
# Restart to reclaim memory
railway service restart
```
