# Data Integrity → ~9/10 — Provable, Forward-Only Submission Dedup + Temporal Hardening

**Date:** 2026-05-16
**Status:** Design approved (user deferred to recommendation 2026-05-16). Next: writing-plans.
**Source:** Tier 1 of the dimension-roadmap. 3-model reconciled analysis (Codex + Gemini + Claude/orchestrator), each verified in-code at `main` `d045c93`.

## 1. Goal

Raise the **Data Integrity** scorecard dimension from a reconciled **7 → ~9** by converting submission deduplication from race-prone, unprovable application logic into a **provable, concurrency-safe, forward-only database guarantee**, and by removing the last 2 naive (tz-unaware) timestamps. CI must *prove* the guarantee exists (today it proves nothing).

## 2. Problem (precise diagnosis — corrects the earlier shorthand)

The earlier closing-re-score said "join-code dedup `UNIQUE(join_code, student_name)` unprovable." That mental model was imprecise. Ground truth (file:line-verified by all 3 models):

- **Join-code path** (`backend/routes/student_portal_routes.py:~1451-1505`, table `submissions`): double-submit is prevented *only* by a pre-insert `SELECT … ilike student_name` check, gated on `settings.allow_multiple_attempts`. Two concurrent requests both pass the SELECT (TOCTOU) → two rows. The insert uses a fresh per-request `uuid4()` `id` with `upsert(on_conflict='id')` — which only makes a *retried same request* idempotent, never two distinct requests.
- **Class-based path** (`backend/routes/student_account_routes.py:~1136-1207`, table `student_submissions`): computes `attempt_number = count(existing)+1` then upserts a fresh-uuid row. Concurrent submits both compute `attempt_number = 1` → duplicate "Attempt 1" rows. **Multiple attempts are an intentional product feature** (`attempt_number` is modeled and displayed), so the correct uniqueness key is `(student_id, content_id, attempt_number)` — NOT `(student_id, content_id)`.
- **The `23505` / "duplicate" catch in both paths is currently dead code**: no business-key UNIQUE exists in **any of the 17 in-repo `.sql` files** (only PRIMARY KEY on `id`). The catch can only fire on a statistically-impossible uuid4 PK collision.
- **Unprovable**: Alembic has one revision, `0001_baseline_existing_live_schema.py`, whose `upgrade()` is intentionally empty and does NOT replay the raw SQL. CI "Migrations Smoke" runs only `alembic upgrade head` against fresh `postgres:15-alpine` → it proves nothing about real constraints. The real schema is ~17 manually-applied raw SQL files. Provability gap: **0/17 SQL files + 0/1 Alembic revisions** declare the dedup constraint the code expects.

Net: the dedup the product relies on is racy, undocumented, and unreproducible in any fresh environment.

## 3. Design (chosen — forward-only, history untouched, reversible)

A plain unique index/constraint would still **fail to build** against any pre-existing duplicate rows in the live DB (state we cannot see from the repo). The mechanism that *guarantees* forward-only-ness:

### 3.1 New nullable dedup-key column + partial unique index
- Add nullable `dedup_key TEXT` to `submissions` and to `student_submissions`. **All existing rows have `dedup_key = NULL`.**
- `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS … WHERE dedup_key IS NOT NULL` on each table. Legacy rows (NULL) are **excluded by the partial predicate** → the index build cannot fail on historical duplicates, and **zero existing rows are read-modified**. Forward-only by construction.

### 3.2 Route writers populate `dedup_key` (only for new writes)
- **Join-code** (`student_portal_routes.py`): when `allow_multiple_attempts` is **False**, set `submission_row["dedup_key"] = f"{join_code}|{student_name.strip().lower()}"`; otherwise leave it unset/`None` (multi-attempt assessments are unaffected — key NULL → not in the unique index). `lower()`/`strip()` matches the existing case-insensitive `ilike` pre-check semantics — this *codifies the already-accepted business rule*, it introduces no new policy. The existing pre-insert SELECT stays (for the friendly message); the DB index closes the race.
- **Class-based** (`student_account_routes.py`): set `submission_row["dedup_key"] = f"{student_id}|{content_id}|{attempt_number}"` for every new write. Legitimate additional attempts still succeed (distinct `attempt_number` → distinct key); only true concurrent-duplicate "Attempt N" rows collide.

### 3.3 The `23505` catch becomes real
With the partial unique index in place, the existing `except … if '23505' in str(err) or 'duplicate' …` blocks in both paths now fire on a genuine constraint violation and return the existing friendly 400 ("You have already submitted…"). No new error path; the racy TOCTOU window is closed at the DB layer.

### 3.4 Migration shape
New `backend/migrations/versions/0002_submission_dedup_forward_only.py`:
- `upgrade()`: `ADD COLUMN IF NOT EXISTS dedup_key TEXT` (×2); `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS … WHERE dedup_key IS NOT NULL` (×2) inside `op.get_context().autocommit_block()` (CONCURRENTLY cannot run in a txn; `backend/migrations/env.py` wraps transactionally otherwise).
- `downgrade()`: drop the 2 indexes, drop the 2 columns. **Fully reversible.**
- Idempotent (`IF NOT EXISTS` throughout) so re-application is safe.

### 3.5 Temporal hardening
`backend/routes/survey_routes.py`: import `timezone`; lines 366 & 375 `datetime.utcnow().isoformat()` → `datetime.now(timezone.utc).isoformat()`. (Repo-wide non-test `utcnow()` count is exactly 2 — both here.)

### 3.6 CI provability (closes the "unprovable" gap)
Update the **Migrations Smoke** job (`.github/workflows/ci.yml`): before `alembic upgrade head`, apply the base raw schema in the same order `tests/test_schema_tightening_applies.py` uses; after `alembic upgrade head`, assert the 2 partial unique indexes and the 2 columns exist (fail the job otherwise). The dedup guarantee becomes reproducible and CI-enforced.

## 4. Testing (TDD)

- **Join-code, single-attempt:** seed an assessment with `allow_multiple_attempts=False`; submit twice as the same `(join_code, student_name)`; assert 2nd → HTTP 400 "already submitted" via the real unique violation (not the pre-check). Casing/whitespace variant collides (matches `ilike`).
- **Join-code, multi-attempt:** `allow_multiple_attempts=True` → `dedup_key` NULL → two submits both succeed (no regression).
- **Class-based:** same `(student_id, content_id, attempt_number)` twice → 2nd 400; a genuine new attempt (incremented `attempt_number`) → succeeds.
- **Schema/CI test:** after applying base schema + `alembic upgrade head`, assert both partial unique indexes + columns exist (parallels `tests/test_schema_tightening_applies.py`).
- **Migration reversibility:** `upgrade()` then `downgrade()` leaves no residue (column/index gone).

Each test written RED first, watched fail, minimal GREEN (per test-driven-development).

## 5. Scope

**In:** the 2 columns + 2 partial unique indexes (forward-only), route key population, the 23505 paths becoming real, 2 utcnow fixes, CI proof, tests.

**Out (explicitly):**
- Full raw-SQL → Alembic rebaseline (large, high-risk; the hollow baseline is a real **Operational Safety** item — note as a separate future task, do NOT bundle).
- Historical duplicate cleanup / rewriting existing rows (user chose forward-only; legacy rows stay NULL/untouched). An optional read-only preflight query to *count* historical dup groups may be documented but is not part of this change.
- Any non-Data-Integrity dimension.

## 6. Risks & handling

- **Live duplicate rows:** impossible to break the migration — partial index excludes all NULL legacy rows; nothing existing is read or written. (This is exactly why the column+partial-index mechanism was chosen over a plain UNIQUE.)
- **Student-name false collisions** (two distinct students, same typed name, same single-attempt assessment): this risk is **already accepted by current business logic** (the existing pre-check dedups by `ilike student_name`). The DB index only makes the *existing* rule reliable; it introduces no new policy. Documented, not changed.
- **Supabase vs raw Postgres:** the Alembic migration is the repo source-of-truth and the CI proof; production Supabase is migrated via its own flow — the plan will include a short operator note that this migration must also be applied to live (it is idempotent + reversible). Live constraints/triggers not in repo SQL remain an acknowledged unknown (§7).
- **`CREATE INDEX CONCURRENTLY` in Alembic:** must use `autocommit_block()`; covered in the migration shape.

## 7. Unknowns (and how the plan handles them)

- **Live DB actual constraints / duplicate counts:** not determinable from the repo. Handled by design: forward-only construction means correctness does not depend on live state, and the migration cannot fail regardless of it.
- **Manual Supabase-dashboard constraints/triggers:** assumed absent; repo is treated as source-of-truth. If a conflicting live constraint exists, the idempotent `IF NOT EXISTS` migration is still safe (no-op).

## 8. Rejected alternatives (3-model divergences, recorded)

- **Gemini — blanket `UNIQUE(assessment_id/join_code, student_name)`:** rejected — breaks every assessment with `allow_multiple_attempts=True` (legit retries become hard errors). The partial/`allow_multiple_attempts`-gated key is required.
- **Gemini — `DELETE FROM … WHERE id NOT IN (SELECT MAX(id) … GROUP BY …)` to clear dups before constraint:** rejected outright — irreversible deletion of student submission rows in a migration violates DB-safety. Forward-only (NULL legacy rows) avoids any cleanup entirely.
- **Codex — canonicalize/`row_number()`-renumber history then add a fully-validated constraint:** sound and non-destructive, but rewrites some existing `attempt_number` values (student-visible) and must read all history; the user chose the lower-risk forward-only variant, which needs none of that.
- **Full Alembic rebaseline:** correct long-term but out of scope (separate Operational-Safety task).

## 9. Effort

1 migration + ~6–10 lines across 2 route files + 1 CI step + ~2 test files. Bounded, low-risk, reversible.
