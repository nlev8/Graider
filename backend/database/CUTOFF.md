# backend/database/ is frozen

This directory holds Graider's pre-Alembic schema artifacts:

- `supabase_schema.sql`, `supabase_teacher_schema.sql`, etc. — base schema
- `migration_YYYY_MM_DD_*.sql` — hand-authored forward migrations
- `rollback_YYYY_MM_DD_*.sql` — corrective forward scripts (misleading name; see the spec)
- `verify_YYYY_MM_DD_*.sql` — post-apply health checks

**As of the commit that introduced `backend/migrations/` to `main`, this
directory is frozen.** No new files, no edits to existing files. All
forward schema changes are Alembic revisions under
`backend/migrations/versions/`.

**Why frozen and not deleted:** these files are the historical record of
live's current schema shape. Deleting them would make drift
investigations (like the 2026-04-18 Phase 4.2 audit) impossible.

**Enforcement:** `tests/test_cutoff_policy.py` fails CI if any file in
this directory is added, modified, or deleted on a branch.

**Design spec:**
`docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md`
