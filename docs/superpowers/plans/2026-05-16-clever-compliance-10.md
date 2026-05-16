# Clever Compliance → 10/10 — Close the Two Verified Baseline Gaps

> **STATUS: Task A ✅ CLOSED (#395 `b9eff4e`) · Task B ✅ CLOSED (#397 `71e66de`) — but PLAN NOT CLOSED: Clever stayed 9/10.** The 2026-05-16 closing 3-model re-score (Codex 9 / Claude 9 / Gemini 10 → reconciled **9**) proved this plan's original premise WRONG: "the two items below are the *only* verified blockers" was **incomplete**. Tasks A & B closed their *planned scope* but verification found **three** in-code residuals (see **Task C**). A verified Clever 10/10 requires Task C. Honest lesson: the plan under-drew the scope; the 3-model verification is what caught it (a single-model pass would have shipped a false 10).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development per task and superpowers:executing-plans (or subagent-driven-development) to implement task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Raise the "Clever Compliance" scorecard dimension from 9/10 to a *code-verified* 10/10 by closing the two open March-baseline findings, both independently confirmed in-code by Claude + Gemini + direct inspection on 2026-05-16:

- **A. Multi-enrollment student-SSO disambiguation** — `_create_clever_student_session` does a first-row-wins lookup; a Clever student enrolled under multiple teachers can land in the wrong session.
- **B. Per-district token resolution** — roster sync reads the single `CLEVER_DISTRICT_TOKEN` env var instead of the per-district key store that already exists, so multi-district installs can't sync each district with its own token.

Clever Library certification (external) is *not* sufficient evidence for an internal 10/10 — it does not test either of these. Score stays 9 until A+B ship and are verified.

**Architecture:** Two independent fixes. **B is backend-only and lower-risk → ship first (PR 1).** **A touches a student-facing flow → ship second (PR 2)** so the disambiguation UI can be reviewed in isolation. Each task is TDD: write the failing test that demonstrates the current wrong behavior, watch it fail, write the minimal fix, watch it pass, commit.

**Tech Stack:** Python 3.12, Flask, Supabase client, pytest + `unittest.mock`. Frontend: existing `StudentPortal.jsx` / Clever callback handling (React/Vite). No new dependencies.

**Source findings (verified file:line, 2026-05-16):**
- A — `backend/routes/clever_routes.py:156-205` (`_create_clever_student_session`). The code self-documents the gap at `:177-184`: *"Not scoped by teacher_id … the first DB row wins … A fully correct fix would query class_students joined with students to find all enrollments, then let the student pick a class — but that requires a UI flow change."* Lookup at `:185` `sb.table("students").select("*").eq("student_id_number", clever_id)`; email fallback `:190`.
- B — `backend/routes/clever_routes.py:443` (post-login background sync) and `:506` (`clever_sync_roster`) both `os.getenv("CLEVER_DISTRICT_TOKEN")`; `backend/clever.py:204 async def sync_roster(district_token)`. Per-district key store **already exists**: `/api/clever/district-keys` GET/POST (`clever_routes.py:728-774`) → `backend/api_keys.py` `check_district_keys(district_id)` / `save_district_keys(district_id, keys)`; `district_id` derivation pattern at `clever_routes.py:739-740`.

---

## Task B: Per-district token resolution — ✅ CLOSED 2026-05-16 (PR #397, `71e66de`)

Shipped per spec (resolver in `api_keys.py` — documented deviation from "clever.py"; both `clever_routes.py` sync sites wired; 6 TDD tests; single-district byte-identical). **Closed-but-incomplete:** the closing re-score found Task B's per-district branch is unreachable end-to-end (no write path for `clever_district_token`) + a 3rd token site bypasses the resolver — folded into **Task C** below. Steps below kept for history (not re-flipped).

### Step 1 — Failing test
- [ ] Add `tests/test_clever_district_token_resolution.py`:
  - `test_resolver_prefers_per_district_key`: mock `api_keys.get_district_keys` to return a token for `district_id="D1"`; assert the resolver returns it (not the env var).
  - `test_resolver_falls_back_to_env_for_single_district`: no per-district key stored → resolver returns `CLEVER_DISTRICT_TOKEN`.
  - `test_sync_roster_path_uses_resolved_token`: patch `clever.sync_roster`; call `clever_sync_roster` with a teacher whose district has a stored key; assert `sync_roster` was awaited with the per-district token.
- [ ] Run; confirm RED (resolver doesn't exist yet; sync paths still read env directly).

### Step 2 — Implement
- [ ] Add `resolve_clever_district_token(district_id: str | None) -> str | None` in `backend/clever.py` (or a small `backend/services/clever_token.py`): look up `api_keys` by `district_id`; if absent/empty → fall back to `os.getenv("CLEVER_DISTRICT_TOKEN")`. `district_id=None` → env fallback (single-district installs unchanged).
- [ ] Thread `district_id` to the two call sites. Derive it the same way `/api/clever/district-keys` does (`clever_routes.py:739-740`); for the post-login path it's available from the Clever user identity resolved at `:444`. Replace `os.getenv("CLEVER_DISTRICT_TOKEN")` at `:443` and `:506` with `resolve_clever_district_token(district_id)`.
- [ ] Preserve the existing "no token → 503/skip" guards (`:507-510`).

### Step 3 — Verify
- [ ] Tests GREEN. `git grep -n 'getenv("CLEVER_DISTRICT_TOKEN")'` shows only the resolver (single source of truth).
- [ ] Regression: existing Clever tests still pass (single-district env path unchanged).
- [ ] Commit; PR 1; CI green; merge.

---

## Task A: Multi-enrollment student-SSO disambiguation — ✅ CLOSED 2026-05-16 (PR #395, `b9eff4e`)

Shipped FIRST (not "PR 2") — per the user's strategic call that A is the only actual *defect* (B is debt). Strict TDD: 3 backend RED→GREEN cycles + 1 frontend cycle.

### Step 1 — Failing test
- [x] Added `tests/test_clever_student_session_multi_enrollment.py` (9 backend tests) + `frontend/src/__tests__/StudentApp.cleverSelect.test.jsx` (2 tests). All watched RED first.

### Step 2 — Implement
- [x] Replaced the first-row lookup with full enrollment enumeration (dedupe by class_id). 0 → `None`; 1 → byte-identical to before; >1 → `{"status":"needs_class_selection","classes":[…],"selection_token":…}`, **no session minted**.
- [x] Finalize endpoint — **deviation:** plan said `POST` only; shipped **GET + POST** on `/api/clever/select-class`. Mid-impl design gap (caught per CLAUDE.md #8): the picker needs the candidate list, which the callback only forwarded as a token → added GET to list candidates (no-consume) + POST to finalize. Single-use on success only; bad class_id → 400 keeps token for retry.
- [x] OAuth caller now handles the new branch (was a latent `KeyError`/500 for exactly these users) → redirect `/student?clever_select=1&sel=…`.
- [x] Frontend — **deviation:** plan guessed `StudentPortal.jsx` + `var(--glass-bg)`; actual = **`StudentApp.jsx`** (the real Clever student callback handler) styled to **match that file's existing dark palette** (`#0f172a`/`#1e293b`). StudentApp uses literal colors, not `var(--*)`; matching surrounding code beats imposing an unused convention (CLAUDE.md "match surrounding style").
- [x] Selection-token store mirrors the existing `_pending_student_auth_codes` primitive (in-process/TTL/inline cleanup) — no DB/migration/dependency.
- [x] Shared `_mint_clever_student_session` helper extracted (no mint drift between single-enroll path and the endpoint).

### Step 3 — Verify
- [x] Backend 9 tests + frontend 2 tests GREEN; 221 clever/student-session + 871 sis/clever regression green; ruff clean; bundle rebuilt + committed (Railway/NIXPACKS serves committed `backend/static/`).
- [x] Single-enrollment path byte-identical (regression-guarded).
- [x] **Out-of-plan fix shipped in the same PR:** `test_sis_alerting.py` 3 clever_routes pins retracked (241→310, 286→353, 711→796) — Task A's ~85 inserted lines shifted the flagged SIS `except` blocks; `capture_exception` calls intact, only the manually-maintained pins needed updating (same pattern every prior shifting PR used). This was caught by CI (`-k` filter missed the meta-test) and fixed before merge.
- [x] Merged via `--auto --squash` after the 9 required checks (incl. Backend Tests w/ the pin fix) went green.

---

## Task C: Close the 3 residuals the closing re-score found (the real path to Clever 10)

> Discovered by the 2026-05-16 closing 3-model re-score (each verified in-code; all 3 orchestrator-confirmed). Tasks A+B fixed the common single-row/single-district cases; these three close the rest. **NOT STARTED.** TDD per item.

- [ ] **C1 — duplicate student rows across teachers** (`backend/routes/clever_routes.py:248`, Codex). `student_row = res.data[0]` is still first-row-wins when the same Clever ID exists under multiple teachers' rosters; Task A only disambiguated *enrollments for one row*. Enumerate across ALL matching `students` rows (and the email-fallback row), fold each (student_row × class) into the existing `needs_class_selection` candidate flow so the picker surfaces enough context (e.g. class/teacher) to choose correctly. **Also fix the now-stale comment at `:244-247`** (it claims the fix is not-done). RED test: same Clever ID → 2 student rows under different teachers → disambiguation, not first-row session.
- [ ] **C2 — periodic-cron token site** (`backend/routes/sync_routes.py:189`, Claude+Gemini). `config.get('district_token') or os.environ.get('CLEVER_DISTRICT_TOKEN')` bypasses `resolve_clever_district_token`. Route it through the resolver (derive `district_id` from the teacher's sync config / Clever identity; env fallback preserved → single-district unchanged). RED test mirrors `test_clever_district_token_resolution.py`'s integration test for the cron path.
- [ ] **C3 — write path for `clever_district_token`** (`backend/api_keys.py::save_district_keys`, Gemini). Provider filter `('openai','anthropic','gemini')` means the resolver's per-district key can never be persisted via any API → multi-district unreachable end-to-end. Allow persisting `clever_district_token` (extend the allowlist or a dedicated setter) and expose it via the `/api/clever/district-keys` admin path. RED test: save then `resolve_clever_district_token` returns it.

Acceptance: C1+C2+C3 shipped (TDD, CI green) → re-run §Verification. Only then does Clever → 10.

## Verification (dimension closure)

- [x] **2026-05-16 closing 3-model re-score RAN** (Codex 9 / Claude 9 / Gemini 10 → reconciled **9, NOT 10**). Result + the 3 residuals recorded in `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` ("2026-05-16 Closing Re-Score" section). Overall unchanged 7.7 (conservative floor).
- [x] Assessment doc updated with the dated section.
- [ ] **Plan does NOT close yet** — reopened with Task C. Re-run the re-score after C1+C2+C3; flip to fully CLOSED only if all models then verify Clever 10/10.

## Out-of-scope / risks

- **Single-district installs:** Task B must be a no-op for them (env fallback). The resolver default path is the regression guard.
- **`needs_class_selection` is an API contract change** for one Clever SSO branch only — single-enrollment (the overwhelming common case) is byte-identical. Document the new branch in CLAUDE.md API reference as part of PR 2.
- **DB join performance:** the all-enrollments query is keyed by `student_id_number`/`email` (indexed lookups) then a bounded `class_students` join — same access pattern as the existing post-lookup enrollment query at `clever_routes.py:202-205`, no new hot path.
- **NOT in scope:** consolidating the two publish paths, the broad-`except` cleanup, or any non-Clever dimension — those are separate scorecard items tracked elsewhere.
