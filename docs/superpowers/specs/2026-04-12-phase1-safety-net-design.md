# Phase 1: Safety Net — Test Coverage + Exception Audit — Design Spec

**Status:** Draft — awaiting user + Codex approval before writing implementation plan.
**Author:** Alex + Claude (brainstorming 2026-04-12)
**Reviewers:** Codex GPT-5.4 (reviewed Section 1 scope + Section 2 test strategy, provided 5 corrections all incorporated)
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
| 4 | Callback with invalid state | → HTTP 401, no session created | `backend/routes/clever_routes.py` |
| 5 | Callback with expired/invalid token | → HTTP 401 | `backend/routes/clever_routes.py` |
| 6 | Login URL returns correct redirect params | `client_id`, `redirect_uri`, `response_type` all present and correct | `backend/routes/clever_routes.py` |

**ClassLink SSO (4 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | Teacher callback success | → Flask `session["classlink_user"]` set, redirect to app | `backend/routes/classlink_routes.py` |
| 2 | Student callback success | → Flask `session["classlink_student"]` set | `backend/routes/classlink_routes.py` |
| 3 | Callback with invalid state | → HTTP 401 | `backend/routes/classlink_routes.py` |
| 4 | Login URL returns correct redirect params | `client_id`, `redirect_uri`, `scope` all present | `backend/routes/classlink_routes.py` |

**OneRoster API (4 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | `/api/oneroster/sync-roster` success | Returns `{"status": "synced", "counts": {...}, "accommodation_suggestions": {...}}` — pin the full response shape | `backend/routes/oneroster_routes.py` |
| 2 | Sync with invalid credentials | → HTTP 401 | `backend/routes/oneroster_routes.py` |
| 3 | `/api/oneroster/apply-accommodations` success | Returns accommodation count in response | `backend/routes/oneroster_routes.py` |
| 4 | Sync idempotency | Running sync twice with same data produces same result (no duplicates) | `backend/routes/oneroster_routes.py` |

**LTI 1.3 (4 tests):**

| # | Test | What it pins | Source file |
|---|---|---|---|
| 1 | `/api/lti/login` OIDC initiation | Sets `session["lti_state"]`, `session["lti_nonce"]`, `session["lti_issuer"]`, redirects with correct params | `backend/routes/lti_routes.py` |
| 2 | `/api/lti/launch` with valid id_token | Session created, user context established | `backend/routes/lti_routes.py` |
| 3 | Launch with bad nonce | → HTTP 401 | `backend/routes/lti_routes.py` |
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

**Tables to pin (8):**
- `student_submissions` — columns: `id`, `student_id`, `content_id`, `status`, `answers`, `results`, `draft_answers`, `score`, `percentage`, `attempt_number`, `is_late`, `time_taken_seconds`
- `published_assessments` — columns: `id`, `join_code`, `title`, `assessment`, `settings`, `teacher_id`, `teacher_name`, `is_active`
- `submissions` — columns: `id`, `assessment_id`, `join_code`, `student_name`, `answers`, `results`, `score`, `total_points`, `percentage`
- `published_content` — columns: `id`, `class_id`, `title`, `content`, `content_type`, `teacher_id`, `due_date`
- `classes` — columns: `id`, `name`, `join_code`, `teacher_id`
- `students` — columns: `id`, `first_name`, `last_name`, `email`, `student_id_number`, `accommodations`
- `class_students` — columns: `id`, `class_id`, `student_id`
- `student_sessions` — columns: `id`, `student_id`, `token_hash`, `expires_at`

**Test implementation:** each test queries `information_schema.columns` filtered by `table_name` and asserts the expected column names exist. Marked `@pytest.mark.live` (requires real Supabase connection, doesn't run in CI, run manually before major releases or Phase 4 RLS changes).

**Why `information_schema` instead of `SELECT ... LIMIT 0`:** Codex review found no in-repo evidence that PostgREST errors on missing columns in the select list (it may silently return `null`). The `information_schema` approach is proven — the repo already uses it in `backend/database/migration_2026_03_20_fk_constraints.sql`.

---

## Delivery plan

| PR | Contents | Size | Timeline |
|---|---|---|---|
| **PR 1** | D1 (coverage backfill ~40-60 tests) + D2 (SSO contract tests ~25 tests) | ~65-85 new tests | Days 1-7 |
| **PR 2** | D3 (AST-based exception audit script + categorized report) + D4 (schema assertion tests ~8-10 tests) | Script + report + ~10 tests | Days 8-10 |

**Total timeline:** ~1.5 weeks (10 working days)

**CI changes in PR 1:** update `.github/workflows/ci.yml` to raise `--cov-fail-under` from 20 to 35 (or 32 minimum).

---

## Success criteria

Phase 1 is complete when:

1. ✅ CI coverage floor is at least 32% and enforced (was 20%)
2. ✅ 25 new SSO/auth contract tests pass in CI, pinning Clever/ClassLink/OneRoster/LTI HTTP contracts + auth/session matrix + grading state transitions
3. ✅ `docs/exception-audit-2026-04.md` exists with all 778 catches categorized as INTENTIONAL/LEGACY/NEEDS_ALERT
4. ✅ 8-10 database schema assertion tests exist (marked `@pytest.mark.live`)
5. ✅ No existing tests broken, no existing code modified, no behavioral changes
6. ✅ All new tests are purely additive — Phase 1 introduces zero risk to Clever/ClassLink/OneRoster compliance

## What Phase 1 enables

- **Phase 2** (exception handling audit) can reference `docs/exception-audit-2026-04.md` to fix only `LEGACY` catches and add alerting to `NEEDS_ALERT` catches, with confidence that the D2 contract tests will catch any SSO regressions
- **Phase 3** (structural decomposition of `app.py` and `planner_routes.py`) can refactor freely because D1's coverage backfill + D2's contract tests will catch any routing, session, or state-transition regressions
- **Phase 4** (RLS + task queue) can add database constraints because D4's schema assertion tests pin the current column structure, and D2's grading state-transition tests pin the thread lifecycle that's being extracted

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Coverage plateau below 32% — some files are hard to test without major refactoring | Medium | Accept 32% minimum. The hard-to-test files (planner_routes.py, app.py) are Phase 3 decomposition targets — they'll become testable after the split. |
| Contract tests are wrong (pin incorrect behavior) | Low after Codex review | Every contract test must be written by reading the actual route handler code, not from documentation or memory. Codex caught 3 of 4 original specs were wrong. |
| Exception audit takes longer than 2-3 days for 778 catches | Medium | The AST script automates extraction. Manual categorization can be done in batches — categorize the integration files (clever_routes, classlink_routes, oneroster_routes) first, then the rest. If the full 778 takes too long, ship the integration-file categorization and defer the rest. |
| Schema assertion tests break because Supabase column names have drifted from what we expect | Low | Run the tests against the live Supabase instance before committing them. The test expectations come from the actual schema, not from documentation. |

---

*Last updated: April 12, 2026*
