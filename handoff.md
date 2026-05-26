# Handoff: 2026-05-26 — ClassLink Roster Server cert-parity SHIPPED, awaiting one live verification

> **Note on triggering context:** This handoff is being written at the **end** of a clean-ship session, not in a context-fatigue dead-end. All three PRs from this session are merged to `main`; the only open work is a **live external action** (run a diagnostic against the ClassLink test tenant). A fresh agent does NOT need `/clear` — they can pick up here directly. But if you `/clear` for any reason, **read this file first.**

---

## 1. Goal

Ship **ClassLink Roster Server certification parity ("Option A2", cert-minimum scope)**, then verify the **live SourcedId contract** in the ClassLink test tenant before scheduling the Roster Server certification call.

This was the fast-follow deferred from the prior session's ClassLink SSO certification work (PRs #582 / #585 / #586 / #587 — all merged + live before this session started).

## 2. TL;DR

- **All three of this session's PRs are SHIPPED + MERGED to `main`.** Don't redo any of it.
  - **#588** (Class B — auth/identity/FERPA) — ClassLink Roster Server cert-parity. Squash commit `2b1390a`. Railway auto-deployed to `app.graider.live`.
  - **#589** (Class A — docs) — `.claude/rules/workflow.md` workflow rulebook + a CLAUDE.md pointer + a prior-handoff rewrite. Squash commit `6520119`.
  - **#590** (Class A — tooling) — `scripts/verify_classlink_sourcedid_contract.py` diagnostic CLI. Squash commit `7a28a27`.
- **`main` HEAD is `7a28a27`.** All three branches deleted on origin.
- **The single open action is LIVE:** run the diagnostic script (or do a manual SSO test) against the ClassLink test tenant with a known-rostered student. Exit 0 → schedule cert call. Exit 1 → escalate to ClassLink with the printed diff.
- **Workflow rulebook is now canonical** at `.claude/rules/workflow.md`, auto-discoverable via a top-of-file pointer in `CLAUDE.md`. It codifies per-task checklist + 7 hard rules + anti-patterns + 4-layer verification loop + universal DoD. Read it before any future multi-task subagent execution.
- **One near-miss caught this session — the SIS_CAPTURES misclassification** (see §5). It's the founding entry in the rulebook's "Lessons From Incidents" appendix. Not a regression — caught + corrected before push — but the lesson cost us a debug detour that the rulebook's Hard Rule #1 ("pre-existing failure" claims require git-checkout proof) now prevents from recurring.

## 3. Current state

### `main` HEAD and recent commits
```
7a28a27  scripts: classlink SourcedId contract diagnostic CLI (#590)
6520119  docs(workflow): codify per-task discipline in .claude/rules/workflow.md (#589)
2b1390a  feat(classlink): Roster Server certification parity — tenant-scoped identity + student SSO + delete (Class B) (#588)
111caef  build(deploy): pin NIXPACKS build to Node 20 (#587)    ← session start was here
```

### Files added or modified by this session (now on main)

**Production code:**
- `backend/oneroster.py` — `normalize_roster(raw, external_id_for=None)` default-preserving builder. All 5 external_id sites use the builder. Default lambda keeps OneRoster + Clever byte-identical.
- `backend/roster_sync.py` —
  - Added `_PROVIDER_PREFIXES["classlink"] = "classlink:"` (protects classlink rows from Clever/OneRoster deactivation by default).
  - Removed the now-redundant hardcoded Clever guard (subsumed by the general `other_prefixes` check).
  - Restructured `delete_roster_data` so student-row + `student_sessions` deletion is **always run** (no longer gated on `if class_ids:`) — fixes FERPA-incomplete deletion of orphan students. Still teacher_id-scoped; benefits OneRoster + Clever + ClassLink equally.
- `backend/routes/classlink_routes.py` — +337 lines:
  - `_classlink_roster_external_id(tenant_id, sourced_id)` — the shared key helper used on BOTH the roster-write side (`_run_classlink_roster_sync`) AND the SSO read side (`_create_classlink_student_session`). Same `urllib.parse.quote(..., safe="")` encoding as `_classlink_guid`.
  - In-memory `_pending_classlink_student_auth_codes` (60s TTL) + `_pending_classlink_class_selections` (120s TTL), each with inline cleanup. Same pattern as Clever.
  - `_mint_classlink_student_session(sb, student_row, chosen)` — duplicated from Clever (not shared) for Class B blast-radius discipline.
  - `_create_classlink_student_session(tenant_id, person_id)` — tenant-scoped lookup, fail-closed (NO email fallback), multi-enrollment picker.
  - Extracted `_run_classlink_roster_sync` from `_trigger_roster_sync` (makes it unit-testable; thread wrapper unchanged).
  - Rewrote the `role == 'student'` branch of `classlink_callback` — redirects with `?classlink=1&code=…` (single) or `?classlink_select=1&sel=…` (multi), or fail-closed `?classlink_error=not_provisioned` with a PII-free audit log (`tenant + sha256(person_id)[:8]`).
  - Removed the now-dead `session['classlink_student']` write (and the harmless `pop` in `classlink_logout`).
  - New routes: `POST /api/classlink/student-token`, `GET/POST /api/classlink/select-class`, `POST /api/classlink/delete-data`.
- `frontend/src/components/StudentApp.jsx` — generalized the Clever-specific URL handlers to a provider param (`"clever"|"classlink"|null`), so one code path serves both. Clever path provably unchanged — `frontend/src/__tests__/StudentApp.cleverSelect.test.jsx` runs unmodified and passes.

**Tests:**
- New: `tests/test_normalize_roster_builder.py`, `tests/test_classlink_roster.py`, `tests/test_classlink_student_sso.py`, `tests/test_roster_sync_delete_orphan.py`, `frontend/src/__tests__/StudentApp.classlink.test.jsx`.
- Extended: `tests/test_classlink_sso.py` (added `TestClassLinkStudentCallback`), `tests/test_sis_alerting.py` (re-pinned shifted captures + added new pin for the Task-5 capture).

**Docs and tooling:**
- `docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md` — the design spec.
- `docs/superpowers/plans/2026-05-25-classlink-roster-certification-parity.md` — the 9-task TDD plan.
- `.claude/rules/workflow.md` — the canonical workflow rulebook (per-task checklist + 7 hard rules + anti-patterns + verification loop + DoD + incident log).
- `CLAUDE.md` — added a "Workflow Discipline" pointer section near the top.
- `scripts/verify_classlink_sourcedid_contract.py` — the live SourcedId-contract diagnostic CLI (see §7).

### Open / closed PRs
- **Open from prior sessions** (not touched here, may need triage someday): #367, #115, #103, #90, #42, #40.
- **No open PRs from this session.** All three merged.

### Working-tree noise (predates this session, NEVER committed)
`AGENTS.md` (modified), `handoff.md` (being overwritten by this file), `.claude/scheduled_tasks.lock`, `flask_session/` (untracked dir), `tests/reports/` (untracked dir). These have been visible the entire session and are intentionally outside every commit's scope per the rulebook's "commit scope clean" rule.

### GitNexus index
Stale by 1 commit at the moment this handoff was written (last indexed `ee5bf18`; main is `7a28a27`). Refresh with `npx gitnexus analyze --embeddings` — there's a PostToolUse hook that nudges after each commit; trivial to run before any code work begins.

## 4. Local repro / verification

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate

# Pull main + confirm we're at the post-merge state
git checkout main && git pull --ff-only
git log --oneline -3
#   expected: 7a28a27 (#590), 6520119 (#589), 2b1390a (#588)

# Local CI mirror — all gates should be green on main
pytest -q --ignore=tests/load               # expect: ~5469 passed, ~16 skipped
ruff check backend/                         # CI scope; expect: clean (scripts/ is out of scope by design)
bandit -q -r backend/routes/classlink_routes.py backend/roster_sync.py backend/oneroster.py
                                            # expect: 1 pre-existing Low/Med on CLASSLINK_TOKEN_URL (false positive)
cd frontend && npx vitest run               # expect: 237 passed across 48 files
cd frontend && npm run build                # expect: success
cd ..

# Spot-check the design-critical properties (sanity-grep)
grep -n "_classlink_roster_external_id" backend/routes/classlink_routes.py
#   expected: 1 def + 2 call sites (read in _create_classlink_student_session, write in _run_classlink_roster_sync)
grep -nE "\.eq\(\"email\"" backend/routes/classlink_routes.py
#   expected: NO matches in _create_classlink_student_session — confirms fail-closed-no-email-fallback

# Open PRs from this session — all should be closed/merged
gh pr list --state merged --search "merged:>=2026-05-25"

# Production smoke (deployed via Railway after #588 merged)
curl -fsS https://app.graider.live/healthz
curl -fsS https://app.graider.live/api/classlink/login-url | jq .
#   expected: {"url": "https://launchpad.classlink.com/oauth2/v2/auth?..."} with non-empty url
```

### The live verification (the one open action)

```bash
# 1. Obtain the test user's userinfo SourcedId.
#    EITHER: have a test student log in via ClassLink SSO and read the
#    CLASSLINK_LOGIN audit event from Sentry/Railway logs (or, on failure,
#    the CLASSLINK_STUDENT_NOT_PROVISIONED event's person_hash — which is
#    SHA-256-truncated and non-reversible; for raw value you'd need a
#    one-shot debug log added temporarily to _create_classlink_student_session).
#    OR: hit https://nodeapi.classlink.com/v2/my/info directly with the
#    user's ClassLink access token and read the "SourcedId" field.

# 2. Get the test tenant's OneRoster Roster Server credentials from the
#    ClassLink developer portal.

# 3. Run the diagnostic:
python scripts/verify_classlink_sourcedid_contract.py \
    --base-url https://<tenant>.classlink-os.com/ims/oneroster/v1p1 \
    --client-id "$OR_CLIENT_ID" --client-secret "$OR_CLIENT_SECRET" \
    --userinfo-sourced-id "<SourcedId from step 1>" \
    --lookup-email <test student's email>

# Exit 0 → contract holds, green-light the Roster Server cert call.
# Exit 1 → contract broken, escalate to ClassLink with the printed diff.
# Exit 2 → operational (auth/network) error, fix the inputs.
```

## 5. Disproved hypotheses (do NOT re-try)

- **Bare `classlink:{sourcedId}` namespace (the original handoff's recommended Approach 2).** REJECTED by the 3-AI consult: both Codex `gpt-5.5`-high and Gemini independently flagged this as a cross-tenant FERPA hole — the Clever-style student-SSO lookup queries `student_id_number` globally, and two tenants sharing a sourcedId would surface each other's classes in the picker. **Replaced with tenant-scoped Approach 2:** `classlink:{quote(tenant)}:{quote(sourcedId)}` produced by a single shared helper used on both write and read sides. (See `docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md` §3 for the consult outcome.)

- **Approach 1 (ClassLink lives in the `oneroster:` namespace, do nothing to `normalize_roster`).** REJECTED for the same reason: ClassLink SSO lookup with `oneroster:{sourcedId}` could collide with real OneRoster rows on the global lookup.

- **Gemini's email fallback (prefix-validated).** REJECTED in favor of Codex's stricter no-email-fallback. For a Class B FERPA path, a global email lookup is exactly the cross-tenant match we're eliminating. Decision is documented inline in `_create_classlink_student_session` (`backend/routes/classlink_routes.py:171-227`).

- **Sharing `_mint_*_student_session` between Clever and ClassLink.** REJECTED. The mint is duplicated, not extracted to a shared helper, deliberately — Class B blast-radius discipline keeps the certified Clever path byte-identical. The duplicated docstring documents this.

- **"SIS_CAPTURES test failure is pre-existing on main" (claim made by the T9 cleanup subagent).** DISPROVED via `git checkout 111caef -- <files>; pytest tests/test_sis_alerting -q` against main's versions of the changed files — main was green, our branch was red. The Tasks 3+4 line shifts moved captures outside the test's `window=8` search range. **Fixed in commit `3ac5aba` (re-pinned) + commit `2f14b73` (corrected a meaning-drift in the re-pin).** This near-miss is the founding case study in `.claude/rules/workflow.md`'s "Lessons From Incidents" appendix.

- **SIS pin re-target: pointing pin to `classlink_routes.py:223` for the `_bg_sync` capture.** DISPROVED by the final whole-branch reviewer. Line 223 actually covers the `_create_classlink_student_session` except block (new in Task 5), NOT `_bg_sync` (whose capture moved to line 295/297 because Task 5 inserted helpers above `_trigger_roster_sync`). **Final fix in commit `2f14b73`:** the `_bg_sync` pin moved to line 295; a NEW pin was added at line 223 for the Task-5 capture. Paranoia-checked: removing either capture independently fails the test with the correct pin in the failure list.

- **Per-task verification scoped to "named test files only" (the pattern that hid the SIS regression).** DISPROVED as sufficient. The workflow rulebook (Hard Rule #2) now mandates `pytest -q --ignore=tests/load` as the floor for per-task verification; cross-cutting tests like `test_sis_alerting.py` that pin `(file, line)` tuples are invisible to scoped review.

- **Trusting subagent reports without spot-checks.** Specifically the cleanup subagent's misclassification. DISPROVED — the workflow rulebook's Hard Rule #5 now requires evidence-bearing subagent reports (test counts, lint output tails — actual stdout, not vibes), and Hard Rule #1 specifically requires the `git checkout <base>` proof protocol for "pre-existing failure" claims.

## 6. Most likely remaining causes / open risks (ranked)

These are the live risks that could still bite — none are debug-thread open. Ranked by likelihood and impact.

1. **(highest) The live ClassLink SourcedId contract may be broken in the test tenant.** This is the WHOLE reason the diagnostic script exists. If userinfo `SourcedId` ≠ Roster Server `sourcedId` for the same person in the cert-test tenant, every ClassLink student in that tenant hits `/student?classlink_error=not_provisioned`. Production behavior is fail-closed (no security incident), but the cert call can't proceed. **Mitigation:** run the diagnostic (§4 last block) before scheduling.
2. **(medium) `_extract_person_id` may fall back to `UserId` for the test user.** If userinfo lacks `SourcedId` entirely, we use `UserId` (with a warning logged). `UserId` is not guaranteed to equal the OneRoster `sourcedId`, so SSO would fail closed. **Mitigation:** watch Sentry for the `"ClassLink userinfo has no SourcedId; using UserId as person id"` warning during the live test.
3. **(low) In-memory auth-code + selection-token stores are not multi-worker safe.** A student whose auth code was minted on worker A but exchanged on worker B gets 401. Same parity-bound limitation Clever has shipped with. Filed as a follow-up in PR #588's body — Redis-backed shared store would fix both providers in one shot.
4. **(low) Duplicated `_mint_classlink_student_session` could drift from `_mint_clever_student_session` over time.** Intentional duplication, but no parity test enforcing field-shape equivalence. Filed as follow-up.
5. **(low) `delete_roster_data` orphan fix changes delete ordering for OneRoster + Clever paths.** Children before parents, FK-safe per the opus reviewer's check against `backend/database/migration_2026_03_20_fk_constraints.sql`, and all per-teacher tests stayed green. Risk is low but if a downstream consumer relies on the old ordering, it would surface here. Mitigation: 5469 passed including all OneRoster/Clever roster-deletion tests.

## 7. Concrete next step

**Run the diagnostic script in the live ClassLink test tenant.** This is the only blocker before scheduling the Roster Server cert call.

Sketch:

```bash
git checkout main && git pull --ff-only
source venv/bin/activate

# Assume you have the test tenant's Roster Server OAuth2 creds + a test
# student's userinfo SourcedId from a prior SSO log or a userinfo API call.
python scripts/verify_classlink_sourcedid_contract.py \
    --base-url https://<tenant>.classlink-os.com/ims/oneroster/v1p1 \
    --client-id "$OR_CLIENT_ID" --client-secret "$OR_CLIENT_SECRET" \
    --userinfo-sourced-id "$USERINFO_SID" \
    --lookup-email "$TEST_STUDENT_EMAIL"
```

Then either:
- **Exit 0**: schedule the ClassLink Roster Server cert call.
- **Exit 1 + same person found with different sourcedId**: escalate to ClassLink support with both values + the person's email/name. The diagnostic prints both clearly.
- **Exit 1 + user not found**: confirm you have the right tenant + base URL + that the test user is actually provisioned in this Roster Server.

If the diagnostic itself can't be run (no Roster Server creds at hand), an alternative is the **observable-behavior test**: have the rostered test student log in via ClassLink SSO at `app.graider.live`. Landing at the portal = contract holds; landing at `/student?classlink_error=not_provisioned` = broken. Then pull Sentry for the `CLASSLINK_STUDENT_NOT_PROVISIONED` audit event.

**Follow-ups worth filing eventually** (in priority order):
1. End-to-end tenant-isolation direct test (see PR #588 body — strengthens the byte-identity argument with an explicit assertion).
2. Redis-backed shared auth-code + selection stores (benefits both Clever and ClassLink).
3. Mint-parity test asserting `_mint_classlink_student_session` and `_mint_clever_student_session` field shapes match.

## 8. References

### PRs from this session (all merged to `main`)
- **#588** — `feat(classlink): Roster Server certification parity — tenant-scoped identity + student SSO + delete (Class B)` — squash `2b1390a`, 17 commits + 9 TDD tasks + 4 cleanups + 2 SIS pin updates.
- **#589** — `docs(workflow): codify per-task discipline in .claude/rules/workflow.md` — squash `6520119`, includes the rulebook + CLAUDE.md pointer + the prior handoff rewrite.
- **#590** — `scripts: classlink SourcedId contract diagnostic CLI` — squash `7a28a27`.

### PRs from prior session (already merged + live)
- **#582** `feat(classlink): SSO certification-readiness — tenant-scoped fail-closed identity` (the predecessor that made ClassLink SSO cert-ready).
- **#583** interim bundle rebuild (superseded by #585).
- **#585** `build(deploy): build frontend at deploy` (Railway/NIXPACKS frontend build).
- **#586** `build(deploy): fail-loud guard for VITE_ Supabase vars`.
- **#587** `build(deploy): pin NIXPACKS build to Node 20`.

### Specs + plans
- `docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md` — design spec (this session).
- `docs/superpowers/plans/2026-05-25-classlink-roster-certification-parity.md` — 9-task TDD plan (this session).
- `docs/superpowers/specs/2026-05-25-classlink-sso-certification-readiness-design.md` — SSO spec (prior session, foundation for this work).

### Key code locations (on `main` HEAD `7a28a27`)
- `backend/routes/classlink_routes.py:83-93` — `_classlink_roster_external_id` (shared key helper).
- `backend/routes/classlink_routes.py:97-167` — auth-code + selection stores + mint.
- `backend/routes/classlink_routes.py:171-227` — `_create_classlink_student_session` (SSO read side, fail-closed, no email fallback).
- `backend/routes/classlink_routes.py:248-296` — `_run_classlink_roster_sync` + `_trigger_roster_sync` (roster write side, builder closure at line 279).
- `backend/routes/classlink_routes.py:535-561` — rewritten callback student branch (fail-closed audit + redirect).
- `backend/routes/classlink_routes.py:611-687` — three new endpoints (delete-data, student-token, select-class).
- `backend/oneroster.py:298-397` — `normalize_roster(raw, external_id_for=None)` with default-preserving lambda.
- `backend/roster_sync.py:26-31` — `_PROVIDER_PREFIXES` with classlink entry.
- `backend/roster_sync.py:254-303` — `delete_roster_data` with orphan fix.
- `frontend/src/components/StudentApp.jsx` — provider-generalized handlers.
- `scripts/verify_classlink_sourcedid_contract.py` — the diagnostic CLI.

### Workflow rulebook
- `.claude/rules/workflow.md` — per-task checklist + 7 hard rules + anti-patterns + verification loop + DoD + incident log.
- `CLAUDE.md` — "Workflow Discipline" pointer section near the top makes it auto-discoverable on every session.
- **Read this before any future multi-task subagent execution.** Hard Rule #1 ("pre-existing failure" claims require git-checkout proof) is the rule that would have prevented the SIS misclassification cleanly the first time.

### Consult artifacts (may be ephemeral)
- `/tmp/classlink_roster_consult.md` — the 3-AI consult prompt.
- `/tmp/codex_roster_out.md` + `/tmp/gemini_roster_out.md` — Codex and Gemini outputs. Both AIs independently converged on tenant-scoped Approach 2.

---

*Status: clean ship. No open investigations, no debug threads, no failed attempts. One LIVE external action open (§7); the design fails closed if that contract breaks, so even an "exit 1" outcome is not a security incident — it's a "schedule the support escalation, not the cert call" outcome.*
