# Audit MAJOR #5 — E2E + load/stress gating

**Source:** [GH #217](https://github.com/nlev8/Graider/issues/217) — "Audit 2026-05-06 Test Gates Sprint", MAJOR #5
**Status:** Plan, not yet started. Drafted 2026-05-11. Revised after Gemini review + direct verification of every claim.
**Author:** Claude Opus 4.7

> **Verification note:** Every claim below was checked against the actual codebase before this revision. Earlier draft conflated `frontend/e2e/` with `tests/e2e/`, treated `tests/stress/` as a real directory (it's not), and falsely equated the `migrations-smoke` Postgres container with a Supabase fixture. Those errors are corrected here.

## Background

Codex full-codebase audit (2026-05-06) flagged `.github/workflows/ci.yml:40-43` for explicitly excluding three test paths from the main CI gate:

```yaml
python -m pytest tests/ -q \
  --ignore=tests/load \
  --ignore=tests/stress \
  --ignore=tests/e2e \
```

### Current state — verified

The codebase actually contains **four** distinct test surfaces relevant to this audit item, not three:

| Path | Type | Specs / files | Currently in CI? |
|------|------|---------------|------------------|
| `frontend/e2e/` | Playwright (Node), uses `frontend/playwright.config.js` | 23 specs incl. health-check, api-endpoints, assistant-chat, automation-builder, behavior-tracking, clever-accommodations, publish-flow, plus extensive student/teacher flows | **Health-check only** runs via `frontend-e2e-smoke` job, `continue-on-error: true` (ci.yml:82-159). Other 22 specs are not run anywhere. |
| `tests/e2e/` | **Separate** Playwright project (Node), with own `package.json`, `playwright.config.js`, `node_modules/`, `pages/`, `fixtures/`. 6 specs: analytics-display, full-workflow, multi-teacher, planner-workflow, settings-workflow, smoke. Designed for 3 concurrent teacher workers (multi-tenant integration). | 6 specs | No (ignored by pytest via `--ignore=tests/e2e`, which is defensive — there's nothing for pytest to collect anyway since this is a Node project). |
| `tests/load/` | Python (pytest + asyncio/httpx) | `harness.py` + 9 persona-style scenario flows (analytics, assignment, assistant, behavior, calendar, extras, planner, settings, student_portal) + `test_load.py` containing pytest entry points | No (ignored). |
| `tests/stress/` | **Does not exist as a directory.** Stress test is a single function `test_stress_rapid_polling` at `tests/load/test_load.py:186`. The `--ignore=tests/stress` line in ci.yml is a legacy/vestigial path. | n/a | n/a (phantom path) |

### Branch protection — verified via `gh api`

`CLAUDE.md:43-44` claims only `Backend Tests` and `Frontend Build` are required. **The actual required-checks list on `main` has 8 contexts:**

```
Backend Tests
Frontend Build
Migrations Smoke
Lockfile Drift Check
Ruff Lint
Bandit SAST
Secret Scan (trufflehog, verified only, PR diff)
Mypy Strict (Critical Modules)
```

This documentation drift is itself a small fix that belongs in Phase 1.

### Stability evidence — verified

The last **15 consecutive `Frontend E2E Smoke` runs on `main`** all succeeded with all 15 job steps green (verified by inspecting per-step conclusions, not just job-level conclusion). The "Run E2E health-check smoke" step actually executed (not skipped) in each. Ready for promotion.

## Goals

1. Catch routing / backend smoke regressions on PR (already wired — just needs the seatbelt clicked in).
2. Add a load-test gate (load suite is the easiest unhandled test surface — runs against local Flask, no Supabase fixtures).
3. Add a nightly broader E2E job for the rest of `frontend/e2e/` and `tests/e2e/` (this is the heaviest piece — needs real Supabase fixtures).

## Non-goals

- Running the full Playwright suites on every PR (too slow + fixture-heavy for PR-gated checks).
- Making load/stress required (these are perf gates, not correctness gates — they should report regressions, not block merges).
- Adding new test coverage. Scope is *gating existing tests*, not writing new ones.

## Phases — REVISED ORDER

The original draft proposed 1 → 2 (broad E2E) → 3 (load). Gemini's review correctly noted that `tests/load/` is ready to run **right now** (configured for `LOAD_TEST_URL=http://localhost:3000`, no Supabase fixtures), while Phase 2 (broader E2E) is blocked on a Supabase fixture decision that needs design work. Reordered to land easy wins first.

---

### Phase 1 — Promote `frontend-e2e-smoke` + documentation cleanup (~45 min)

**Scope:** flip 1 line in CI workflow + update branch protection rule + reconcile CLAUDE.md with reality.

**Tasks:**

1. Remove `continue-on-error: true` from `.github/workflows/ci.yml:94`.
2. Update branch protection rule on `main` to add `Frontend E2E Smoke` to the required status-checks list (current list has 8 contexts; this would make 9). Use `gh api -X PATCH repos/nlev8/Graider/branches/main/protection/required_status_checks` with the full new list.
3. **Reconcile `CLAUDE.md:43-44`** with reality — currently lists 2 required checks; expand to all 9 (after Frontend E2E Smoke is added). Note: per CLAUDE.md "CI job names are locked" — flag that the same expansion belongs in any future ci.yml-edits guidance.
4. Remove the vestigial `--ignore=tests/stress \` line from `.github/workflows/ci.yml:42` (phantom path).
5. Run a PR to verify the rule update doesn't break merges.

**Risk:** Low. Job has 15 consecutive green runs on main with the actual e2e step executing each time. If Playwright is flaky in the wild, the existing health-check spec is narrow enough (single happy-path navigation) that flakes should be rare.

**Rollback:** Re-add `continue-on-error: true` and remove `Frontend E2E Smoke` from branch protection's contexts list. <5 min.

**Exit criteria:** PR status checks show `Frontend E2E Smoke` as required + blocking. CLAUDE.md accurately lists all 9 required contexts.

---

### Phase 2 — Weekly load-test job (~1-2 sessions)

**Scope:** new GitHub Actions workflow runs `tests/load/` on a cron schedule against a locally-spawned backend, surfaces throughput numbers.

> **NOTE — terminology cleanup**: prior draft said "Nightly" in headings + "weekly" in the cron + exit criteria. This is a **weekly** job (Sunday 10:00 UTC). Everywhere this plan says nightly for load, read weekly.

**Reality check — this is easy BUT not trivial.** `tests/load/config.py:7` defaults to `BASE_URL = os.getenv("LOAD_TEST_URL", "http://localhost:3000")`. `harness.py` is runnable via `python -m tests.load.harness` (no Supabase, no AI keys needed for non-`--live` scenarios). However, Codex's high-effort review surfaced several gotchas the prior draft missed — see Tasks 1-7 below.

**Tasks:**

1. **Survey what runs.** Read `tests/load/harness.py`, `tests/load/test_load.py`, and the 9 flow files in `tests/load/scenarios/`. Identify which scenarios are local-only (default) and which require `--live` (real OpenAI calls — gated by `bool(OPENAI_API_KEY)` per `tests/load/config.py:15`). Phase 2 runs only the local-only set.

2. **Confirm the stress function pattern + add @pytest.mark.stress.** `tests/load/test_load.py:186::test_stress_rapid_polling` is the single "stress" test referenced by the audit. Currently it has NO pytest marker — `pytest tests/load/test_load.py -m "not live"` will still execute it. Decide whether Phase 2 includes stress (default: yes), and EITHER add `@pytest.mark.stress` so it's explicitly markable AND register the marker in `pyproject.toml` / `pytest.ini`, OR run stress by explicit `-k` filter. Document the chosen approach.

3. **Address the false-green skip risk.** `tests/load/test_load.py:55` applies a module-level skip when `BASE_URL` is unavailable — if the workflow's backend spawn step succeeds but the server never actually listens, pytest exits 0 with "skipped" and the job goes green. **Required preflight:** add a workflow step `curl -fsS --max-time 5 http://localhost:3000/` (or hit a known health endpoint) BEFORE the pytest invocation. The preflight MUST fail-fast.

4. **CRITICAL — teacher isolation gotcha.** `backend/storage.py:115` and `:449` show that when Supabase is NOT configured, storage falls back to **shared local files** (rubric, settings, etc.). The load test sends `X-Test-Teacher-Id` per persona but the local-file fallback ignores it. So the headline claim "5 teachers concurrently" is concurrency theater under the no-Supabase default — all 5 personas read/write the same local rubric file.

   Three viable resolutions, pick before workflow lands:
   - **Resolution A (smallest)**: scope Phase 2 explicitly to "single-persona concurrency smoke" — run `harness --personas 1` only. Honest framing of what's actually being measured. Recommended for initial Phase 2.
   - **Resolution B**: scope local-file storage by teacher ID for load-test mode (read `X-Test-Teacher-Id` and shard files like `~/.graider_settings.{teacher_id}.json`). Production-relevant fix; modifies `backend/storage.py`. Per Rule #11 this could land if <15 min; otherwise file follow-up issue.
   - **Resolution C**: defer Phase 2 multi-persona to after Phase 3's Supabase fixture lands. Means Phase 2 only ships single-persona smoke until Phase 3 enables real isolation.

   Plan default: **Resolution A** for the first Phase 2 PR, with a deferred follow-up issue tracking B or C.

5. **DON'T set stub `OPENAI_API_KEY`.** The `frontend-e2e-smoke` job sets `OPENAI_API_KEY=sk-ci-stub` because the smoke spec doesn't exercise grading. But `tests/load/config.py:15` gates live-mode on `bool(OPENAI_API_KEY)` — setting the stub would ENABLE live AI calls (real money, real flake). For Phase 2: leave `OPENAI_API_KEY` unset, OR change the gate to `os.getenv("LOAD_TEST_LIVE") == "1"` (the harness already partially uses this signal at `tests/load/harness.py:294`).

6. **Install requirements-dev.txt.** The `frontend-e2e-smoke` job installs only `requirements.txt`. Phase 2 needs pytest (in `requirements-dev.txt:687`). Workflow must install BOTH.

7. **Choose harness vs pytest path explicitly for artifacts.** `JsonReporter` (at `tests/load/reporters/json_reporter.py`) is wired into `harness.py` only — `test_load.py` imports it but never calls `.record()` on it. So:
   - If using `python -m tests.load.harness`: JSON report at `tests/load/reports/*.json` is produced; upload as artifact.
   - If using `pytest`: only stdout summaries. No artifact unless we add a reporter fixture.
   Recommendation: **harness path for Phase 2** (gives observable metrics out of the box).

8. **Add `.github/workflows/load-weekly.yml`** with:
   - `schedule: - cron: '0 10 * * 0'` (Sunday 10:00 UTC, low-traffic window)
   - `workflow_dispatch:` for manual triggers
   - Backend-spawn pattern adapted from `frontend-e2e-smoke` (FLASK_ENV=development, PYTHON=python3) — but **no stub OPENAI_API_KEY** per Task 5
   - Preflight `curl -fsS http://localhost:3000/` step per Task 3
   - Install BOTH `requirements.txt` AND `requirements-dev.txt` per Task 6
   - Run `python -m tests.load.harness --personas 1` per Task 4 (single-persona until isolation is fixed)
   - Upload `tests/load/reports/` as artifact per Task 7

9. **Decide regression threshold.** Either (a) write to a baseline file checked into repo + fail if metric drops >20%, or (b) just report numbers in workflow logs for now and add the threshold gate in a follow-up. Recommendation: **(b) initially** — let CI run for 4-6 weeks to establish noise floor before adding pass/fail logic.

10. **Add Slack/email notification on failure** — Codex audit emphasized "CI green doesn't mean no real regressions"; silent weekly failures defeat the purpose. TODO: check if there is an existing notification pattern in the repo.

11. **Tighten the harness cross-contamination check** (optional / Rule #11 candidate). `tests/load/harness.py:126` and `:143` claim to verify cross-contamination but only check HTTP 200 on rubric fetch — they don't compare returned rubric to persona-expected. If <15 min: fix in scope (assert categories match `persona_data["expected_rubric"]`). Otherwise: file follow-up.

**Risk:** Low. With Resolution A (single-persona) the load test is honest about what it's measuring — no false-isolation claim. Preflight + correct OPENAI_API_KEY handling eliminate the false-green paths.

**Open questions:**
- Who owns the failure-alert channel?
- Does `tests/load/scenarios/` need state cleanup between runs (relevant for Resolution B/C, not A)?
- What's the budget for the `--live` path (OpenAI calls) if we eventually include it?

**Exit criteria:** Weekly run completes within 30 min, fails fast if backend doesn't come up, uploads a JSON report artifact, surfaces throughput numbers without false-isolation claims.

---

### Phase 3 — Nightly broader E2E (~2-3 sessions)

**Scope:** new GitHub Actions workflow runs additional Playwright specs from `frontend/e2e/` AND `tests/e2e/specs/` on a cron schedule. Concrete spec scope to be determined in Task 1 — earlier draft assumed all 22 non-health-check `frontend/e2e/` specs + all 6 `tests/e2e/specs/` would run; Codex review showed that's both too broad (some specs don't need Supabase) and too narrow (some need decisions about AI vs Auth fixtures).

**Why this is hard — corrected:** Some Playwright specs need a real Supabase API surface (PostgREST + Auth). NOT all of them. Codex's review found at least three specs that explicitly tolerate missing Supabase/API keys: `frontend/e2e/api-endpoints.spec.js:81`, `frontend/e2e/assistant-chat.spec.js:87`, `tests/e2e/specs/smoke.spec.js:51`. The fixture decision (Option A vs B) should be scoped to ONLY the specs that genuinely need it — running cheap specs needs no Supabase at all.

**Tasks:**

1. **Inventory ALL 29 specs by fixture need.** ✅ **COMPLETED 2026-05-12** (see table below).

   Methodology: for each spec, grep'd direct `/api/*` calls + auth fingerprints + tolerance patterns (e.g., `expect([200, 500]).toContain(...)`). Where direct API calls weren't present (UI-driven specs in `tests/e2e/specs/`), inspected helpers + page-objects to identify the backend surface exercised. Specs that explicitly tolerate Supabase 500 / missing-AI-key are tagged with **T**.

   Bucket legend:
   - **N** — No fixture; pure UI navigation. Candidate for PR-gated smoke promotion.
   - **L** — Local file-backed only (rubric/settings/assignments/resources/lessons/automations writing to `~/.graider_*`); works without Supabase.
   - **S** — Supabase-required (writes to `published_assessments`, `published_content`, `submissions`, `students`, `classes`, `behavior_events`, `surveys` tables via REST API).
   - **A** — AI-required (`/api/assistant/chat`, `/api/generate-*`, etc.).
   - **C** — Clever-required (`/api/clever/*` OAuth flows).
   - **T** — Tolerant of backend 500s (uses `expect([200, 500]).toContain(...)` or filters Supabase/AI errors).

   #### `frontend/e2e/` (23 specs)

   | # | Spec | Buckets | Notes |
   |---|------|---------|-------|
   | 1 | `api-endpoints.spec.js` | **T** | Exercises wide API surface. Already tolerant — uses `[200,500]` for Supabase-backed endpoints (`/api/classes`, etc.). Runnable today against local-backend workflow. |
   | 2 | `assessment-results.spec.js` | **L** | `/api/analytics`, `/api/assessment-results` read local CSV. No Supabase. |
   | 3 | `assistant-chat.spec.js` | **T + A** | `/api/assistant/chat` needs OpenAI key OR returns structured 500. Already tolerant. |
   | 4 | `automation-builder.spec.js` | **L** | `/api/automations*` reads/writes `~/.graider_automations/`. No Supabase. |
   | 5 | `behavior-tracking.spec.js` | **S** | `/api/behavior/{data,events,session}` uses Supabase `behavior_events` table. |
   | 6 | `clever-accommodations.spec.js` | **C** | `/api/clever/*` needs Clever OAuth credentials. |
   | 7 | `health-check.spec.js` | **N** | Already runs PR-gated as `frontend-e2e-smoke`. Excluded from Phase 3 to avoid duplication. |
   | 8 | `publish-flow.spec.js` | **N** | UI-only — verifies Publish button visibility on Planner tab. Does not actually publish. |
   | 9 | `resource-management.spec.js` | **L** | `/api/{save,list,load,delete}-resource` reads/writes `~/.graider_resources/`. No Supabase. |
   | 10 | `student-content-types.spec.js` | **S** | Drives student grading flows via `publishAssessment` helper → `/api/publish-assessment` writes to Supabase. |
   | 11 | `student-dashboard.spec.js` | **S** | Uses authenticated student session; reads `published_content` from Supabase. |
   | 12 | `student-error-states.spec.js` | **S** | Hits `/api/teacher/assessment/{code}` which reads from Supabase. |
   | 13 | `student-matching.spec.js` | **S** | `publishAssessment` helper → Supabase. |
   | 14 | `student-mc-grading.spec.js` | **S** | `publishAssessment` helper → Supabase. Grading itself is local but the test setup requires Supabase. |
   | 15 | `student-multi-subject.spec.js` | **S** | Same `publishAssessment` pattern. |
   | 16 | `student-portal.spec.js` | **S** | `/api/publish-assessment` + `/api/teacher/assessment/`. |
   | 17 | `student-short-answer.spec.js` | **S** | `publishAssessment` helper. |
   | 18 | `student-tf-grading.spec.js` | **S** | `publishAssessment` helper. |
   | 19 | `survey-endpoints.spec.js` | **S** | `/api/survey/*` (already failed in load test for this reason). |
   | 20 | `teacher-dashboard.spec.js` | **N** | UI-only — tests visibility of dashboard sections. |
   | 21 | `teacher-planner-interactions.spec.js` | **N** | UI-only — drag/drop, modal interactions. Backend untouched. |
   | 22 | `teacher-publish-modal.spec.js` | **S** | `/api/publish-assessment` + teacher assessment endpoints. |
   | 23 | `teacher-settings-save.spec.js` | **L** | `/api/save-rubric`, `/api/save-global-settings` → `~/.graider_*`. |

   #### `tests/e2e/specs/` (6 specs)

   | # | Spec | Buckets | Notes |
   |---|------|---------|-------|
   | 24 | `analytics-display.spec.js` | **L** | UI flow exercising `/api/analytics` (local CSV). |
   | 25 | `full-workflow.spec.js` | **L + T** | Tab traversal (Settings → Builder → Grade → Results → Analytics). UI tolerates backend failures. |
   | 26 | `multi-teacher.spec.js` | **L** | Codex finding: 3 browsers all hit backend as `local-dev` (NOT multi-tenant). Local-file storage. |
   | 27 | `planner-workflow.spec.js` | **L** | Planner UI; lesson/calendar writes to `~/.graider_*`. |
   | 28 | `settings-workflow.spec.js` | **L** | Settings UI; rubric/global-settings writes to `~/.graider_*`. |
   | 29 | `smoke.spec.js` | **T** | Tab traversal smoke. Explicitly filters Supabase/AI/500 errors at line 51. Already tolerant. |

   #### Bucket summary

   | Bucket | Count | Specs |
   |---|---|---|
   | **N** (no fixture, can run today) | 4 | health-check, publish-flow, teacher-dashboard, teacher-planner-interactions |
   | **L** (local file-backed, can run today) | 11 | assessment-results, automation-builder, resource-management, teacher-settings-save, analytics-display, full-workflow, multi-teacher, planner-workflow, settings-workflow + 2 more |
   | **T** (already tolerant, can run today) | 4 | api-endpoints, assistant-chat (also A), smoke, plus partial overlap with full-workflow |
   | **S** (Supabase-required) | 11 | behavior-tracking, student-content-types, student-dashboard, student-error-states, student-matching, student-mc-grading, student-multi-subject, student-portal, student-short-answer, student-tf-grading, survey-endpoints, teacher-publish-modal |
   | **A** (AI-required) | 1 (overlap with T) | assistant-chat |
   | **C** (Clever-required) | 1 | clever-accommodations |

   #### Phasing implication for Task 3 (Supabase fixture decision)

   **15 of 29 specs (52%)** are runnable **today** against a local-only backend (buckets N + L + T). The Phase 3 nightly job could ship in two stages:

   - **Stage 3a (no fixture commitment)**: run the 15 N/L/T specs nightly. Zero Supabase cost. Catches regressions in 52% of the e2e surface immediately. Excludes health-check (already in PR smoke).
   - **Stage 3b (after fixture decision)**: add the 11 S specs once Option A or B lands. The 1 Clever spec needs additional credentials decision (separate from Supabase). The 1 AI spec needs budget controls.

   This stage-3a→3b split lets us land Phase 3 value immediately and defer the Supabase $$ commitment until we've seen what the cheaper specs surface first.

2. **CRITICAL — `tests/e2e/playwright.config.js:27` webServer is commented out.** The plan's command `cd tests/e2e && npx playwright test specs/` would fail with no backend running. Three resolutions:
   - **Resolution A**: enable a working `webServer` block in `tests/e2e/playwright.config.js` (similar to `frontend/playwright.config.js:webServer` which auto-builds + spawns backend).
   - **Resolution B**: have the workflow start ONE backend job-level (before either Playwright project runs) and have both `playwright.config.js` files use `reuseExistingServer: true`. This avoids the two-server conflict described in Task 7 below.
   - Recommendation: **Resolution B** — single backend process shared by both projects is cheaper in CI minutes and avoids server-port collisions.

3. **Decide Supabase fixture strategy** (gated on Task 1 inventory). Three options:
   - **Option A — dedicated remote test Supabase project**: cheap pro tier (~$25/mo). Real PostgREST + Auth. Cleanest isolation. Cleanup via `truncate` between runs. Cost = monthly fee + GH Actions secrets (`E2E_SUPABASE_URL`, `E2E_SUPABASE_SERVICE_KEY`).
   - **Option B — `supabase start` local stack in CI**: Supabase CLI spawns a full local PostgREST + Auth + Postgres stack via Docker. **Not ready in this repo** — Codex confirmed via Supabase docs that `supabase start` requires `supabase/config.toml`, which does not exist here. Going this route requires upfront work: `supabase init`, migration wiring (existing alembic migrations need to be ported or replayed via `supabase db push`), seed data fixture, env export from `supabase status`. Estimate: at least one additional PR before Phase 3 can land.
   - ~~Option C — SQLite stub~~: **DROPPED.** Backend is tightly coupled to `supabase-py` (`backend/supabase_client.py:create_client(url, key)`). SQLite simulation would be a massive rewrite.
   - Recommendation pending Task 1: if the Supabase-required bucket is small, **Option A** is cheapest. If it's the majority of specs and you want zero monthly cost, factor in the Option B prerequisite PR.

4. **Correct the multi-teacher framing.** Earlier draft claimed `tests/e2e/specs/multi-teacher.spec.js` exercises "3 concurrent teacher workers / multi-tenant integration". Reality (Codex finding):
   - The test spawns 3 browser contexts but sets no per-teacher auth headers
   - `tests/e2e/pages/app.page.js:3` shows localhost auto-authenticates as `local-dev`
   - All 3 contexts hit the backend AS THE SAME TEACHER
   - It's "3 concurrent browser workflows", not multi-tenant
   To genuinely exercise multi-tenant: inject per-teacher auth/session state or route API calls with distinct `X-Test-Teacher-Id`. This is a separate "make multi-teacher.spec.js actually multi-tenant" follow-up issue, NOT in Phase 3 scope. Update the doc to describe what these specs actually do, not what their names imply.

5. **Resolve the conflicting webServer patterns.** `frontend/playwright.config.js:26` configures webServer to auto-build + spawn backend on port 3000; `tests/e2e/playwright.config.js:27` has webServer commented out (expects pre-running server). Phase 3 workflow needs ONE of:
   - Single job-level backend process + both configs use `reuseExistingServer: true` (preferred per Task 2 Resolution B)
   - Harmonize both configs to self-start (more duplication; risk of port collision)

6. **Add `.github/workflows/e2e-nightly.yml`** with:
   - `schedule: - cron: '0 8 * * *'` (08:00 UTC, off-hours US/EU)
   - `workflow_dispatch:` for manual triggers
   - Same Playwright cache + install pattern as the smoke job
   - Install BOTH `requirements.txt` AND `requirements-dev.txt`
   - Single backend-spawn step (per Task 5) — sets all needed env vars per Task 1's inventory of fixture requirements
   - Fixture secrets per Task 3's Option A choice (or local-stack init per Option B)
   - Run `npx playwright test e2e/ --grep-invert=health-check --reporter=list,html` against `frontend/e2e/` (assuming health-check stays in smoke)
   - Separate step for `tests/e2e/specs/` (only after Task 2 is resolved)
   - Upload artifacts on failure

7. **Add failure notification** (same channel as Phase 2).

8. **Document fixture seeding** so future contributors can reproduce locally.

**Risk:** Medium-High. Real Supabase = $ cost + flake risk. Real OpenAI = $ cost + budget controls. Two Playwright projects = double the maintenance. webServer config conflict (Task 5) needs careful resolution. Option B prerequisite PR adds time if chosen.

**Open questions:**
- Slack/email channel ownership for failure alerts?
- OpenAI budget cap (per-run + monthly)?
- Should we promote any specs from Phase 3 nightly to Phase 1 PR-gated as they prove stable?
- Should the "make multi-teacher.spec.js actually multi-tenant" issue be filed pre- or post-Phase 3?

**Exit criteria:** Nightly run completes within 45 min, reports green/red status, all specs in the inventory have been categorized AND either pass OR are explicitly excluded with a documented reason.

---

## Phase dependencies

- **Phase 1** is standalone — no blockers, can land immediately.
- **Phase 2** depends only on Phase 1 being in (so the load-test backend-spawn pattern matches what `frontend-e2e-smoke` uses).
- **Phase 3** depends on the Supabase fixture decision (Option A or B). Should brainstorm with the owner before committing budget or CLI infra.

## Closes issue

When all 3 phases ship, this issue is closeable:

- [x] Phase 1 — promote smoke to required + reconcile docs (shipped 2026-05-12, PR #351)
- [ ] Phase 2 — weekly load test
- [ ] Phase 3 — nightly broader E2E

→ then close [GH #217](https://github.com/nlev8/Graider/issues/217) as all 3 original items (MAJOR #4, MAJOR #5, MINOR DOMPurify) are landed.

## Estimated total effort

3-5 PRs across ~3-4 sessions, distributed over 1-2 weeks. Phase 1 ~45 min, Phase 2 ~1 session, Phase 3 ~2-3 sessions.

## Revision log

- **2026-05-11 initial draft** — had multiple unverified claims (conflated `frontend/e2e/` with `tests/e2e/`; treated `tests/stress/` as a real dir; falsely equated `migrations-smoke` psql with Supabase; claimed CLAUDE.md required-checks list was complete at 2 entries).
- **2026-05-11 revision 1** — every claim verified against actual codebase + Gemini cross-review. Phase order swapped (load before broader E2E). Option B (SQLite stub) dropped. Stress-test reality (single function, not directory) documented. CLAUDE.md docs-drift folded into Phase 1.
- **2026-05-11 revision 2** — fixed 2 residual factual errors caught during self-verification: stress test at `tests/load/test_load.py:186` (not :149); 9 (not 10) persona-style flow files in `tests/load/scenarios/`.
- **2026-05-12 revision 4** — Phase 2 shipped (PRs #354 + #356). Phase 3 Task 1 spec inventory completed: 15 of 29 specs (N/L/T buckets) are runnable today without Supabase fixtures; 11 specs need Supabase (S bucket); 1 needs Clever OAuth; 1 needs AI key with budget controls. Plan now proposes a Stage 3a → 3b split so the 15 cheap specs ship nightly immediately, deferring the Supabase fixture commitment until we've seen what they surface.
- **2026-05-12 revision 3** — Phase 1 shipped (PR #351). Codex high-effort review of Phase 2 and Phase 3 surfaced 2 CRITICAL + 8 MAJOR + 2 MINOR + 1 NIT findings. Folded all of them:
  - Phase 2 expanded from 5 tasks to 11. Added preflight to prevent false-green skip. Removed stub `OPENAI_API_KEY` (would have enabled live AI calls). Documented teacher-isolation gotcha (local-file storage ignores X-Test-Teacher-Id; default Resolution A = single-persona smoke). Added `@pytest.mark.stress` task. Added `requirements-dev.txt` install. Chose harness path explicitly (only one with JSON reporter wired). Optional Rule #11 fix for vacuous cross-contamination check.
  - Phase 3 expanded from 6 tasks to 8. Added spec-inventory-first task (no blanket "needs Supabase" claim). CRITICAL fix: `tests/e2e/playwright.config.js` webServer is commented out — added Resolution B (single job-level backend) preference. Option B (`supabase start`) marked as requiring prerequisite PR (no `supabase/config.toml` in repo). Corrected the "multi-teacher 3-workers" framing to "3 concurrent browser workflows" (no per-teacher auth). Added webServer-conflict-resolution task. Fixture cost analysis remains.
  - Closeout checklist: Phase 2/3 unchecked (only Phase 1 has shipped).
  - Terminology: "Nightly" → "Weekly" for Phase 2 throughout.
