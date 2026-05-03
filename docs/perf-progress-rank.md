# Progress-Rank Endpoint Performance

The class-scoped `GET /api/teacher/class/<class_id>/progress-rank` endpoint aggregates `standards_mastery` across every graded submission in the class. For small classes (≤30 students × ≤10 standards), the existing in-memory aggregation is fine. For district-scale (150+ students × 6 periods × 40 standards × multiple attempts), the same code path returns thousands of rows from `student_submissions` and grinds through them in a Python loop, producing 2–5 second responses.

This doc captures the current state and the planned path forward.

---

## Current state (2026-05-03)

### What ships now

PR #176 adds a **30-second TTL cache** keyed by `(teacher_id, class_id, attempt_mode)`:

- Auth check stays OUTSIDE the cache (a teacher who loses access still hits 403 within one TTL window).
- Per-process, in-memory (`backend/utils/ttl_cache.py`).
- Cache is populated on first miss; subsequent polls within 30 seconds return immediately.

### Why this is the right interim fix

- Dashboard auto-refresh polling is the dominant traffic pattern, and 30-second-stale data is acceptable for a teacher-facing analytics view.
- Zero schema work — ships in one PR.
- Buys weeks of headroom while the durable fix is designed.

### What this fix does NOT solve

- The first request in each TTL window still pays the full Python-loop cost.
- Cache is per-Railway-pod; horizontally scaling means duplicated computation across pods.
- A teacher refreshing immediately after a new submission lands sees up to 30 seconds of stale data.

For all of these, see the durable fix below.

---

## Durable fix: `student_standards_mastery` materialized rollup

### Design

Add a new table that pre-aggregates per-student per-standard mastery, updated incrementally on each grading completion.

```sql
CREATE TABLE student_standards_mastery (
  student_id    UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  class_id      UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  standard_code TEXT NOT NULL,
  -- Pre-aggregated fields produced by the existing
  -- _aggregate_mastery_for_student helper for a single student/standard:
  percentage          NUMERIC NOT NULL,
  total_questions     INT     NOT NULL,
  total_correct       INT     NOT NULL,
  attempt_mode_latest JSONB,   -- snapshot under "latest" mode
  attempt_mode_best   JSONB,   -- snapshot under "best" mode
  attempt_mode_avg    JSONB,   -- snapshot under "average" mode
  by_dok              JSONB,   -- {1:..., 2:..., 3:..., 4:...}
  last_submission_at  TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (student_id, class_id, standard_code)
);

CREATE INDEX idx_ssm_class_standard ON student_standards_mastery(class_id, standard_code);
CREATE INDEX idx_ssm_class_updated ON student_standards_mastery(class_id, updated_at DESC);
```

### Write path

1. After `student_submissions.results` is finalized (grading thread completion in `backend/grading/`):
   - Compute the student's mastery for every standard touched by that submission.
   - `INSERT ... ON CONFLICT (student_id, class_id, standard_code) DO UPDATE SET ...` for each.
2. Backfill: one-time job runs `_aggregate_mastery_for_student` for every (student, class) pair currently in the system and writes to the new table.
3. Recall path: when a remediation is recalled, recompute from remaining submissions and update the rollup.

### Read path swap

`get_class_progress_rank` becomes:

```python
rows = (
    db.table('student_standards_mastery')
      .select('student_id, standard_code, percentage, by_dok, attempt_mode_' + mode)
      .eq('class_id', class_id)
      .execute()
)
```

Then a single Python loop pivots `(student_id, standard_code)` → `mastery[standard_code]`. No more bulk submission fetch + per-row sanitize + per-student aggregate.

Expected response time: ~50–200 ms regardless of class size.

### Migration order

1. Schema migration adds the table empty (Alembic).
2. Write hook ships behind a feature flag.
3. Backfill job runs once in production with the flag off (data populates without affecting reads).
4. Read-path swap merges; flag flipped on.
5. After 1 week of green, remove flag and the in-memory aggregation code.

Each step is its own PR.

### RLS

The new table inherits the same RLS policy as `student_submissions`: a teacher can read rows where the row's `class_id` belongs to a class the teacher owns. Mirror the existing `classes`-based policy from Phase 4.2.

### Effort estimate

~2 days for the full sprint per the original district-readiness plan: schema migration (0.5d), write hook + tests (0.5d), backfill (0.5d), read-path swap + observation window (0.5d).

---

## When to actually build it

Trigger conditions for the durable fix:
- A district contract is signed where `100+` students × `30+` standards is realistic.
- p99 response time on `/api/teacher/class/<id>/progress-rank` exceeds 1 second (tracked via observability — see `docs/observability.md`).
- Cache hit rate drops below 70% (indicates teachers are actively waiting on cache misses).

Until any of those triggers fire, the 30-second TTL cache is sufficient.
