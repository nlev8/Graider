# Phase 1: Safety Net — Test Coverage + Exception Audit — Design Spec

**Status:** Draft — awaiting user + Codex approval before writing implementation plan.
**Author:** Alex + Claude (brainstorming 2026-04-12)
**Reviewers:** Codex GPT-5.4 (3 review passes: Section 1 scope, Section 2 test strategy, full spec review. 11 corrections total, all incorporated. Error-path status codes and schema column names verified against actual source code.)
**Roadmap item:** Phase 1 of the 5-phase codebase improvement roadmap (6.8 → 9.0+)
**Hard constraint:** Clever/ClassLink/OneRoster/LTI compliance maintained at all times.

---

## Goal

Build the safety net that enables Phase 2-5 refactoring without breaking SSO integrations, grading flows, or student data handling. Phase 1 is purely additive — no existing code is modified, no behavior changes, no refactoring. It produces tests and a report that make subsequent phases safe.

## Non-goals (explicitly deferred)

- **No exception handling fixes** — Phase 2 uses the D3 categorization report to fix the 778 broad catches. Phase 1 only categorizes them.
- **No code refactoring** — Phase 3 splits `app.py` (3517 lines) and `planner_routes.py` (8104 lines). Phase 1 only builds the tests that make that split safe.
- **No architecture changes** — Phase 4 extracts grading into a task queue and adds RLS. Phase 1 only pins the current behavior so Phase 4 regressions are caught.
- **No new features** — this is infrastructure work, invisible to teachers and students.
- **No live/network tests in CI** — all new tests use mocks. Live Supabase tests are marked `@pytest.mark.live` and run manually.

---

## Baseline metrics (measured 2026-04-12)

| Metric | Value |
|---|---|
| CI coverage floor | 20% (`--cov-fail-under=20` in `.github/workflows/ci.yml`) |
| Actual measured coverage | 27% (29,780 statements, 21,816 missed) |
| Test count | 1051 passing (1042 after deselecting `live`-marked tests) |
| Test files | 65 in `tests/` |
| Broad exception catches | 778 across `backend/` |

---

## Deliverables

### PR 1 — Tests (D1 + D2)

#### D1: Raise CI coverage floor from 20% → 35%

**Minimum acceptable: 32%.** If easy wins are exhausted at 32%, ship it and raise incrementally in later phases. The current 27% means ~8 percentage points of new coverage needed.

**Priority order for backfilling** (ranked by Phase 2-5 risk, not by current coverage):

| Priority | File | Current | Target | Why this file matters |
|---|---|---|---|---|
| 1 | `backend/services/portal_grading.py` | 23% | 45% | Owns the grading thread lifecycle and status transitions (`partial → graded \| grading_failed \| grading_deferred`). Phase 4 will extract this into a task queue — tests must pin the current state machine before that extraction. |
| 2 | `backend/routes/student_account_routes.py` | 17% | 45% | Student submissions, draft saves, the 4 UUID-idempotent upsert paths shipped in Tier 1 #2. 25 broad `except Exception` catches that Phase 2 will audit. |
| 3 | `backend/routes/student_portal_routes.py` | 32% | 50% | Join-code submissions, assessment publishing, portal grading thread spawning. 23 broad catches. |
| 4 | `backend/routes/settings_routes.py` | 16% | 35% | Teacher rubric, AI notes, global settings persistence. Low risk but low coverage. |
| 5 | `backend/routes/planner_routes.py` | 21% | 25% | 8104 lines — barely touch. Only cover the most critical assessment/lesson generation entry points. This file gets decomposed in Phase 3. |

**Files explicitly NOT backfilled in Phase 1:**
- `assistant_tools_reports.py` (4%, 1201 lines) — non-critical, Phase 3 decomposition target
- `visualization.py` (5%) — rendering code, low blast radius
- `elevenlabs_service.py` / `openai_tts_service.py` (0%) — external API wrappers, hard to test meaningfully with mocks
- `staging.py` (0%) — file manipulation, defer to Phase 3
- `stem_grading.py` (5%) — specialized grading, low usage

**Test style:** Flask `test_client()` + mocked Supabase via `MagicMock` chains. Follow the existing pattern in `tests/test_integration_workflows.py`. Don't introduce new test infrastructure.

**CI change:** update `.github/workflows/ci.yml` to `--cov-fail-under=35` (or 32 if we plateau). This is the hard enforcement — the floor can never drop below this on future PRs.

#### D2: SSO + auth contract test suite (~25 tests)

Mock-based tests pinning the exact HTTP contract surface of every SSO integration. These tests must be derived from **reading the actual route handler code**, not from assumptions about behavior. Codex review found 3 of 4 original contract specs were factually wrong against the code.

**Clever SSO (6 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | Teacher callback success | Valid OAuth code → Flask `session["clever_user"]` set, redirect to app | `backend/routes/clever_routes.py` |
| 2 | Student callback success | Valid OAuth code → `student_sessions` DB row created, auth code generated, redirect to `/student?clever=1&code=...` | `backend/routes/clever_routes.py` |
| 3 | `/api/clever/student-token` exchange | Auth code → returns `{"token": ...}` for student session | `backend/routes/clever_routes.py` |
| 4 | Callback with invalid/missing state | → HTTP 302 redirect to `/?clever_error=state_mismatch` (line 300-307), no session created | `backend/routes/clever_routes.py` |
| 5 | Callback with expired/invalid token | → HTTP 302 redirect to `/?clever_error=token_exchange_failed` (line 312-313) | `backend/routes/clever_routes.py` |
| 6 | Login URL returns correct redirect params | `client_id`, `redirect_uri`, `response_type` all present and correct | `backend/routes/clever_routes.py` |

**ClassLink SSO (4 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | Teacher callback success | → Flask `session["classlink_user"]` set, redirect to app | `backend/routes/classlink_routes.py` |
| 2 | Student callback success | → Flask `session["classlink_student"]` set | `backend/routes/classlink_routes.py` |
| 3 | Callback with invalid state | → HTTP 302 redirect to `/?classlink_error=state_mismatch` (line 199-201). Note: partial state validation allowed for "Instant Login" flow. | `backend/routes/classlink_routes.py` |
| 4 | Login URL returns correct redirect params | `client_id`, `redirect_uri`, `scope` all present | `backend/routes/classlink_routes.py` |

**OneRoster API (4 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | `/api/oneroster/sync-roster` success | Returns `{"status": "synced", "counts": {...}, "accommodation_suggestions": {...}}` — pin the full response shape | `backend/routes/oneroster_routes.py` |
| 2 | Sync with invalid credentials | → HTTP 502 with `{"error": "Failed to fetch roster from OneRoster API"}` (line 174-180, catches `httpx.HTTPStatusError` from token endpoint) | `backend/routes/oneroster_routes.py` |
| 3 | `/api/oneroster/apply-accommodations` success | Returns accommodation count in response | `backend/routes/oneroster_routes.py` |
| 4 | Sync idempotency | Running sync twice with same data produces same result (no duplicates) | `backend/routes/oneroster_routes.py` |

**LTI 1.3 (4 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | `/api/lti/login` OIDC initiation | Sets `session["lti_state"]`, `session["lti_nonce"]`, `session["lti_issuer"]`, redirects with correct params | `backend/routes/lti_routes.py` |
| 2 | `/api/lti/launch` with valid id_token | Session created, user context established | `backend/routes/lti_routes.py` |
| 3 | Launch with bad nonce | → HTTP 400 with `{"error": "Invalid nonce"}` (line 129-132) | `backend/routes/lti_routes.py` |
| 4 | `/api/lti/jwks` returns valid JWKS | Response has `keys` array with valid RSA key structure | `backend/routes/lti_routes.py` |

**Auth/session matrix (4 tests) — Codex-recommended addition:**

| # | Test | What it pins |
|---|---|---|
| 1 | Teacher JWT rejects student token header | `@require_teacher` decorated route returns 401 when `X-Student-Token` is passed instead of JWT |
| 2 | Student token rejects teacher JWT | Student-authenticated route returns 401 when Authorization Bearer JWT is passed |
| 3 | Flask session auth (Clever/ClassLink) can't escalate to teacher JWT-protected routes | Session-only auth doesn't grant access to `@require_teacher` routes |
| 4 | Expired session returns 401 not 500 | All SSO paths return clean 401 on expired/invalid sessions, never unhandled 500 |

**Grading state transition tests (3 tests) — Codex-recommended addition:**

| # | Test | What it pins |
|---|---|---|
| 1 | Submission starts as `partial` when multipass grading is needed | `run_portal_grading_thread` sets initial status correctly |
| 2 | Successful grading transitions `partial → graded` | Status + results updated atomically |
| 3 | Failed grading transitions `partial → grading_failed` | Status updated, results preserved from instant grading phase |

**Total: 25 new contract tests.**

### PR 2 — Audit (D3 + D4)

#### D3: Exception categorization report

**AST-based Python script** (`scripts/audit_exceptions.py`) that:

1. Walks all `.py` files under `backend/` using `ast.parse()` + `ast.walk()`
2. For each `ast.ExceptHandler` node, extracts:
   - File path
   - Line number
   - Exception type(s) caught (handles tuple catches like `except (TypeError, ValueError)`)
   - Whether the handler body contains: `pass`, `return None`, `logger.error/warning/info`, `raise`, or other statements
   - The parent function name (for context)
3. Outputs a markdown table to `docs/exception-audit-2026-04.md`

**Human categorization step:** after the script generates the raw table (~778 rows), each row is manually reviewed and assigned a `Category` column:

- **`INTENTIONAL`** — the broad catch is correct by design. Common reasons: SIS APIs (Clever/ClassLink/OneRoster) are genuinely flaky and the catch prevents a single API hiccup from crashing the entire sync. The handler includes logging or a fallback path.
- **`LEGACY`** — the broad catch should be replaced with a typed exception or removed. The handler is either `pass` (silent swallow), `return None` (hides failure from caller), or catches `Exception` when a specific exception type is known. Phase 2 fixes these.
- **`NEEDS_ALERT`** — the catch handles a real failure that should be observable via BetterStack but currently isn't. Phase 2 adds these to the `@critical_path` decorator list or creates new alert rules.

**Source files stay untouched.** No inline comments, no code changes. The report is the Phase 2 input document. Git blame stays clean.

**Why AST-based, not regex/grep:** the repo has tuple exception handlers (`except (ValueError, TypeError)`), nested `try/except` blocks (e.g., `backend/services/stem_grading.py`), multiline except clauses, and `except Exception as e:` patterns. Regex/grep is brittle on these. `ast.ExceptHandler` nodes handle all of them correctly and give us the parent function context for free.

#### D4: Database schema assertion tests (8-10 tests)

**Pin the Supabase table/column names that route handlers reference** so Phase 4's RLS changes can't silently break queries. PostgREST may silently ignore missing columns in `select()` queries rather than erroring, so we use `information_schema` queries instead of `SELECT ... LIMIT 0` (this pattern already exists in the repo's migration SQL).

**Tables to pin (8):** (column lists verified against `cloud_migration.sql` and `supabase_student_portal_schema.sql` on 2026-04-12)

- `student_submissions` — columns: `id`, `student_id`, `content_id`, `status`, `answers`, `results`, `score`, `percentage`, `attempt_number`, `time_taken_seconds`. **NOTE:** code also writes `draft_answers` and `is_late` which are NOT in the SQL schema — this is an active schema-drift bug that Phase 1 documents (see "Known bugs discovered" below). The D4 test should assert on the SQL-defined columns only, and document the drift.
- `published_assessments` — columns: `id`, `join_code`, `title`, `assessment`, `settings`, `teacher_name`, `teacher_email`, `is_active`, `submission_count`, `created_at`, `updated_at`. **NOTE:** NO `teacher_id` column exists (corrected from earlier draft which incorrectly listed it).
- `submissions` — columns: `id`, `assessment_id`, `join_code`, `student_name`, `answers`, `results`, `score`, `total_points`, `percentage`
- `published_content` — columns: `id`, `class_id`, `title`, `content`, `content_type`, `teacher_id`, `due_date`, `join_code`, `settings`, `is_active` (last three added per Codex review — heavily used but originally omitted)
- `classes` — columns: `id`, `name`, `join_code`, `teacher_id`
- `students` — columns: `id`, `first_name`, `last_name`, `email`, `student_id_number`, `accommodations`
- `class_students` — columns: `id`, `class_id`, `student_id`
- `student_sessions` — columns: `id`, `student_id`, `session_token`, `expires_at` (**corrected:** column is `session_token`, not `token_hash` — verified at `cloud_migration.sql` line 184)

**Test implementation:** each test queries `information_schema.columns` filtered by `table_name` and asserts the expected column names exist. Marked `@pytest.mark.live` (requires real Supabase connection, doesn't run in CI, run manually before major releases or Phase 4 RLS changes).

**Why `information_schema` instead of `SELECT ... LIMIT 0`:** Codex review found no in-repo evidence that PostgREST errors on missing columns in the select list (it may silently return `null`). The `information_schema` approach is proven — the repo already uses it in `backend/database/migration_2026_03_20_fk_constraints.sql`.

---

## Delivery plan

| PR | Contents | Size | Timeline |
|---|---|---|---|
| **PR 1** | D1 (coverage backfill ~40-60 tests) + D2 (SSO contract tests ~25 tests) | ~65-85 new tests | Days 1-7 |
| **PR 2** | D3 (AST-based exception audit script + categorized report) + D4 (schema assertion tests ~8-10 tests) | Script + report + ~10 tests | Days 8-12 |

**Total timeline:** ~2 weeks (12 working days). The D3 manual categorization for integration-critical files (~130 catches) is the timeline driver; remaining files are best-effort within the window.

**CI changes in PR 1:** update `.github/workflows/ci.yml` to raise `--cov-fail-under` from 20 to 35 (or 32 minimum).

---

## Success criteria

Phase 1 is complete when:

1. ✅ CI coverage floor is at least 32% and enforced (was 20%)
2. ✅ 25 new SSO/auth contract tests pass in CI, pinning Clever/ClassLink/OneRoster/LTI HTTP contracts + auth/session matrix + grading state transitions
3. ✅ `docs/exception-audit-2026-04.md` exists with integration-critical files fully categorized (clever_routes, classlink_routes, oneroster_routes, student_account_routes, student_portal_routes, portal_grading — ~130 catches). Remaining files categorized on best-effort basis within the timeline; uncategorized rows are marked `UNCATEGORIZED` and deferred to Phase 2 start.
4. ✅ 8-10 database schema assertion tests exist (marked `@pytest.mark.live`)
5. ✅ No existing tests broken, no existing code modified, no behavioral changes
6. ✅ All new tests are purely additive — Phase 1 introduces zero risk to Clever/ClassLink/OneRoster compliance

## What Phase 1 enables

- **Phase 2** (exception handling audit) can reference `docs/exception-audit-2026-04.md` to fix only `LEGACY` catches and add alerting to `NEEDS_ALERT` catches, with confidence that the D2 contract tests will catch any SSO regressions
- **Phase 3** (structural decomposition of `app.py` and `planner_routes.py`) can refactor freely because D1's coverage backfill + D2's contract tests will catch any routing, session, or state-transition regressions
- **Phase 4** (RLS + task queue) can add database constraints because D4's schema assertion tests pin the current column structure, and D2's grading state-transition tests pin the thread lifecycle that's being extracted

---

## Known bugs discovered during Phase 1 research

These bugs were found during the spec research (verifying column names and status values against actual schema). Phase 1 DOCUMENTS them via D4 tests but does NOT fix them — fixes belong in Phase 2 (exception audit) or Phase 4 (schema hardening).

### Bug: `student_submissions.status` CHECK constraint mismatch

**SQL CHECK constraint** (cloud_migration.sql lines 220-222) allows: `'in_progress'`, `'submitted'`, `'grading'`, `'graded'`, `'returned'`.

**Python code actually writes:** `'partial'` (student_account_routes.py:492), `'grading_deferred'` (portal_grading.py:240), `'grading_failed'` (portal_grading.py:554, app.py:202), `'draft'` (student_account_routes.py save_submission_draft).

**Impact:** If the CHECK constraint is enforced in Supabase, these INSERTs/UPDATEs will fail with a constraint violation. If it's NOT enforced (Supabase may have it disabled or the migration was applied without the constraint), the mismatch is latent — Phase 4's RLS hardening could activate it.

**Phase 1 action:** D4 adds a test that documents both the SQL-defined values AND the code-written values, flagged as a known discrepancy. Phase 4 resolves it by either expanding the CHECK constraint or normalizing the code's status values.

### Bug: `student_submissions.draft_answers` and `is_late` — code writes columns not in schema

**Code** writes `draft_answers` (student_account_routes.py save_submission_draft) and `is_late` (student_account_routes.py submit_student_work) to the `student_submissions` table. **Neither column exists** in the SQL schema files.

**Impact:** Either (a) the columns were added via Supabase dashboard without updating the migration files (schema drift), or (b) Supabase silently accepts writes to nonexistent columns (unlikely for PostgreSQL). Most likely (a) — the columns exist in production but not in the versioned schema SQL.

**Phase 1 action:** D4's `@pytest.mark.live` test against real Supabase will reveal whether these columns actually exist in production. Document the finding either way.

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Coverage plateau below 32% — some files are hard to test without major refactoring | Medium | Accept 32% minimum. The hard-to-test files (planner_routes.py, app.py) are Phase 3 decomposition targets — they'll become testable after the split. |
| Contract tests are wrong (pin incorrect behavior) | Low after Codex review | Every contract test must be written by reading the actual route handler code, not from documentation or memory. Codex caught 3 of 4 original specs were wrong. |
| Exception audit takes longer than expected for 778 catches | Medium | The AST script automates extraction. Manual categorization prioritizes integration-critical files first (~130 catches across clever_routes, classlink_routes, oneroster_routes, student_account_routes, student_portal_routes, portal_grading). These are the files Phase 2 will audit first. Remaining files are categorized best-effort; uncategorized rows ship as `UNCATEGORIZED` and Phase 2 categorizes them before fixing. This is consistent with the success criteria (which requires integration-critical files fully categorized, not all 778). |
| Schema assertion tests break because Supabase column names have drifted from what we expect | Low | Run the tests against the live Supabase instance before committing them. The test expectations come from the actual schema, not from documentation. |

---

*Last updated: April 12, 2026*
