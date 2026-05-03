# Graider Disaster Recovery

This document describes what data is at risk in a Graider deployment, where it lives, what is backed up, and how to recover from common failure modes. It is the answer to the district-procurement question "what is your DR plan?"

> **Status:** Initial draft. Sections marked **`[VERIFY]`** require confirmation against the production Supabase project's settings — not yet validated end-to-end.

---

## 1. What's at risk

| Data | Where | Loss-tolerance |
|---|---|---|
| Teacher accounts (`auth.users`) | Supabase Auth | Zero — full user-account loss is unrecoverable without restore |
| Classes, students, enrollments (`classes`, `students`, `class_students`) | Supabase Postgres | Zero — losing class structure breaks teacher-student linkage |
| Submissions and grades (`student_submissions`, `submissions`, `published_assessments`, `published_content`) | Supabase Postgres | Zero — student work, cannot be regenerated |
| Audit log (`audit_log`) | Supabase Postgres + local file (`~/.graider_audit.log`) | Compliance-relevant — FERPA requires retention |
| Teacher-stored config (`teacher_data`: rubric, settings, assignments, lessons, resources) | Supabase Postgres | Recoverable from Git (lessons/assignments) but rubric/settings are user-edited |
| Locally cached files (`~/.graider_*` on the Railway pod or local dev) | Railway ephemeral disk / dev machine | Tolerable — these are caches, not source of truth |
| Static frontend bundle (`backend/static/`) | Railway disk via build artifact | Zero risk — rebuild from `npm run build` |

**Source of truth:** Supabase. Everything else is either rebuilt from Git or considered cache.

---

## 2. Supabase backup configuration **`[VERIFY]`**

Run a one-time audit to fill in the table below.

| Setting | Status |
|---|---|
| Plan tier (Free / Pro / Team / Enterprise) | **`[VERIFY]`** — check Supabase dashboard → Project Settings → Subscription |
| Daily automated backups | **`[VERIFY]`** — Pro+ tier required |
| Backup retention window | **`[VERIFY]`** — Pro: 7 days; Team: 14 days; Enterprise: customizable |
| Point-in-time recovery (PITR) | **`[VERIFY]`** — PITR is a separate add-on (~$100/mo). Pro tier ≠ PITR. |
| PITR window if enabled | **`[VERIFY]`** — typically 7 / 14 / 28 days |

**Action:** After verifying, update this section with the actual values.

If Supabase tier is **Free**, there are no automated backups — you must implement off-site backup before district deployment. See §6.

---

## 3. Recovery scenarios

### 3.1 Single-table accidental DELETE

**Example:** A bug or misuse drops or wipes a row from `students` or `student_submissions`.

1. Open Supabase dashboard → Database → Backups.
2. Identify the most recent daily backup BEFORE the deletion timestamp.
3. **If PITR is enabled:** Use PITR to restore to a few seconds before the deletion. This avoids losing data written after the affected row.
4. **If only daily backups:** Restore the daily backup to a NEW Supabase project (not in-place — restoring in-place wipes everything written after the backup).
5. Use `pg_dump` against the restored project to extract the affected table only.
6. `pg_restore` (or manual INSERT) the missing rows back into production.

> **Important:** Never restore a backup over the live database. Always restore to a temporary project, then selectively migrate the rows you need.

### 3.2 Full-database loss

**Example:** Supabase project corrupted, accidentally deleted, or compromised.

1. Provision a new Supabase project on the same plan tier.
2. Restore the most recent backup into the new project (Supabase support can do this for Pro+; for Free tier, fall back to off-site backup — see §6).
3. Update Railway env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET` to point at the new project.
4. Trigger a Railway redeploy.
5. Run the Alembic migration smoke test (`backend/migrations`) to confirm schema parity.
6. Verify with the FERPA audit query: `SELECT count(*) FROM audit_log WHERE timestamp > now() - interval '7 days';` — should be non-empty if working.
7. Notify users via the operational channel that historical data may be at most 24h stale (assuming daily backups).

**Recovery Time Objective (RTO):** ~1 hour (Supabase restore + Railway redeploy).
**Recovery Point Objective (RPO):** Up to 24 hours without PITR; under 1 minute with PITR.

### 3.3 Compromised teacher account mass-deletes content

**Example:** A teacher's credentials are stolen and the attacker deletes published content / classes.

1. Disable the teacher's account immediately (Supabase Auth → Users → ban).
2. Audit `audit_log` for the teacher_id around the incident window:
   ```sql
   SELECT * FROM audit_log
   WHERE teacher_id = '<id>'
     AND timestamp > '<incident_start>'
   ORDER BY timestamp;
   ```
3. Use PITR (if enabled) to restore to just before the incident, in a temporary project.
4. Selectively re-insert the affected rows.
5. Force a password reset for the affected teacher (Supabase Auth → password recovery).

**This is the strongest argument for enabling PITR before district deployment.**

### 3.4 Railway pod disk loss

**Example:** Railway pod restart wipes ephemeral disk.

Local files (`~/.graider_*` cache, `~/.graider_audit.log`, `~/.graider_data/*` rosters) are **not durable** on Railway. Already mitigated:
- `audit_log` dual-writes to Supabase (permanent).
- `teacher_data` table holds rubric/settings/assignments (permanent).
- Roster CSVs are uploaded per-class via `/api/classes/<id>/sync-roster` and persisted in Supabase.

**No recovery action needed** — the next request reads from Supabase. The local file paths exist only to support legacy local-dev workflows.

---

## 4. Backup verification drill

Run quarterly. Goal: prove the recovery procedure actually works before you need it under pressure.

1. Pick a recent daily Supabase backup.
2. Restore it to a temporary Supabase project (not production).
3. Connect Railway *staging* (or local dev with overridden env vars) to the temporary project.
4. Spot-check 5 things:
   - Teacher can log in.
   - A known class exists with the expected join code.
   - A known submission has the expected score and feedback.
   - The audit log contains entries from the backup window.
   - Alembic schema matches (run `alembic current` in the smoke env).
5. Tear down the temporary project.
6. Log the drill outcome (date, success/failure, time to restore) in `docs/operations/dr-drills.md` (create if missing).

---

## 5. RTO / RPO targets

| Metric | Target | Current capability |
|---|---|---|
| Recovery Time Objective (RTO) | < 2 hours from incident detection | ~1 hour with Supabase Pro restore + Railway redeploy |
| Recovery Point Objective (RPO) | < 1 hour | 24h without PITR; <1 min with PITR |
| Detection time | < 5 minutes | BetterStack `/healthz` polling (see `docs/observability.md`) |

If district contracts require tighter RPO (say <15 min), enable Supabase PITR before signing.

---

## 6. Off-site backup (recommended for district deployment)

Supabase backups live within Supabase. A Supabase-side billing or platform incident could in theory affect both the live DB and its backups. For a district-grade DR posture, add an off-site nightly export.

### Option A: Nightly `pg_dump` to S3

A Railway cron or GitHub Actions schedule runs `pg_dump` against the Supabase Postgres connection and uploads to an S3 bucket with object-lock enabled (so a compromised teacher account cannot delete the backups).

**Estimated cost:** $5/month (S3 storage of ~5GB compressed dumps × 30 days retention).

### Option B: Supabase → external Postgres replica

For higher RPO requirements, set up a logical replication slot from Supabase to an external Postgres instance (e.g. Neon or RDS). Real-time streaming, near-zero RPO, but ~$30/month and more operational complexity.

**Recommendation for v1 district deployment:** Option A is sufficient. Add Option B if a district contract specifically requires <15 min RPO.

---

## 7. What's NOT covered here

- Supabase Auth user account recovery if a user truly deletes their own account (Supabase handles this via their own tooling).
- LLM API provider outages (Anthropic / OpenAI / Gemini) — not data loss, see `docs/runbook.md` §Supabase Outage for the analogous pattern.
- Frontend asset CDN — the bundle is served from Railway's disk; rebuilding from `main` is the recovery.

---

## 8. Owner

The on-call engineer is responsible for executing recovery. Update `docs/observability.md` with current on-call rotation. After any real DR event, write a postmortem in `docs/operations/postmortems/<date>.md`.
