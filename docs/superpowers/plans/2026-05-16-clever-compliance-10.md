# Clever Compliance → 10/10 — Close the Two Verified Baseline Gaps

> **STATUS: NOT STARTED** — Scoped 2026-05-16 from the 3-model dimensional re-score (Claude 8.1 / Gemini 7.8 reconciled; Clever Compliance held at **9/10**). The two items below are the *only* verified blockers to a true 10/10. Periodic roster sync (3rd baseline item) is already DONE (`.github/workflows/roster-sync.yml`).

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

## Task B: Per-district token resolution (PR 1 — backend only)

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

## Task A: Multi-enrollment student-SSO disambiguation (PR 2 — backend + minimal UI)

### Step 1 — Failing test
- [ ] Add `tests/test_clever_student_session_multi_enrollment.py`:
  - `test_single_enrollment_unchanged`: one matching student row, one class → returns `{token, student, class}` exactly as today (no regression).
  - `test_multiple_enrollments_returns_disambiguation`: same Clever student enrolled in 2 classes (under different teachers) → returns a `needs_class_selection` payload listing both candidate classes + a short-lived selection token, NOT a silently-picked session.
  - `test_finalize_with_selected_class_issues_session`: posting the selection token + chosen class_id → issues the real session scoped to that class.
- [ ] Run; confirm RED (current code returns first-row session, no disambiguation).

### Step 2 — Implement
- [ ] Replace the `:185` first-row lookup with a `students` ⋈ `class_students` ⋈ `classes` query enumerating **all** enrollments for the Clever id (email fallback preserved).
- [ ] 0 matches → `None` (unchanged). 1 → issue session as today (unchanged path). >1 → return `{"status": "needs_class_selection", "classes": [...], "selection_token": <short-lived hashed token>}`.
- [ ] Add finalize endpoint (e.g. `POST /api/clever/select-class`) that validates the selection token + class_id and issues the scoped session via the existing token-mint path.
- [ ] Frontend: in the Clever student callback handler (`StudentPortal.jsx` / wherever the callback resolves), if `needs_class_selection` → render a minimal class-picker that POSTs the choice to the finalize endpoint. Reuse existing card/list styling (theme-aware `var(--glass-bg)` — see handoff heuristic #6; do NOT hardcode colors).

### Step 3 — Verify
- [ ] Tests GREEN. Manual: simulate a 2-teacher Clever student → picker appears → chosen class yields correct scoped session.
- [ ] Single-enrollment students see **no** behavior change (the common case).
- [ ] Commit; PR 2; CI green; merge.

---

## Verification (dimension closure)

- [ ] After both PRs merge: re-run the 3-model dimensional re-score (Codex + Claude + Gemini) per the established reconcile process. Clever Compliance moves 9 → **10** only if all models verify both items closed in-code.
- [ ] Update `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` with the new dated row.
- [ ] Flip this plan's STATUS to CLOSED with the PR numbers (bulk-flip + STATUS-stamp, handoff heuristic #2).

## Out-of-scope / risks

- **Single-district installs:** Task B must be a no-op for them (env fallback). The resolver default path is the regression guard.
- **`needs_class_selection` is an API contract change** for one Clever SSO branch only — single-enrollment (the overwhelming common case) is byte-identical. Document the new branch in CLAUDE.md API reference as part of PR 2.
- **DB join performance:** the all-enrollments query is keyed by `student_id_number`/`email` (indexed lookups) then a bounded `class_students` join — same access pattern as the existing post-lookup enrollment query at `clever_routes.py:202-205`, no new hot path.
- **NOT in scope:** consolidating the two publish paths, the broad-`except` cleanup, or any non-Clever dimension — those are separate scorecard items tracked elsewhere.
