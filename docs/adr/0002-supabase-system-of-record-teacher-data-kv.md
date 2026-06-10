# ADR 0002 — Supabase as system of record; per-teacher key-value `teacher_data` with a file fallback

- **Status:** Accepted (retrospective record)
- **Date recorded:** 2026-06-10 (decision predates this record)

## Context

Graider began as a single-teacher local desktop tool that persisted settings,
rubrics, assignments, and lessons to `~/.graider_*` files. Moving to a hosted
multi-tenant product required a real database, but most teacher state is
document-shaped (assignment configs, lesson plans, rubric JSON, settings
blobs) whose shape changes with nearly every feature — normalizing each into
relational tables would have made every feature a migration.

## Decision

1. **Supabase (Postgres) is the system of record** for all hosted data:
   identity/roster tables (`classes`, `students`, `class_students`,
   `student_sessions`), the two publish-path table families (ADR 0001), and
   the FERPA `audit_log`.
2. **Teacher document state lives in a per-teacher key-value table,
   `teacher_data`** (keys like assignments/lessons/settings/rubric, JSON
   values) rather than normalized relational settings tables.
3. **A storage abstraction keeps the legacy file backend alive**
   (`backend/storage.py`): `USE_SUPABASE` is detected at call time from
   `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`; `teacher_id == 'local-dev'` always
   uses files. This is what lets the test suite, local dev, and E2E runs
   operate with zero cloud dependencies.

## Consequences

- Feature velocity: new teacher-scoped document types need no migration —
  they are a new key in `teacher_data`.
- Queryability is sacrificed for KV blobs: anything that must be filtered or
  joined in SQL (rosters, submissions, audit) gets a real table; this split
  is intentional and the boundary should be respected when adding state.
- The file backend means every storage call has two code paths; `storage.py`
  is the single choke point, and per-tenant sharding for non-`local-dev` IDs
  without Supabase (Issue #353 Resolution B) is handled there too.
- Column drift is real: the live Supabase schema is authoritative, and field
  names must be verified before any DB change (CLAUDE.md "Supabase Tables").

## Evidence

- `backend/storage.py` (module docstring: file vs Supabase backends,
  detection rule, `local-dev` carve-out)
- `CLAUDE.md` § "Supabase Tables", § "Persistence"
- `docs/ARCHITECTURE.md` § 6 (Persistence)
- `backend/supabase_client.py` (`get_supabase()` canonical client)
