# Handoff: 2026-05-25 — ClassLink Roster Server Certification Parity SHIPPED + Workflow Rulebook

## 1. Goal

Build **ClassLink Roster Server certification parity** (cert-minimum scope) so a rostered
ClassLink **teacher and student** both land in their provisioned accounts and the integration can
be certified for rostering. This was the deferred fast-follow from the SSO-certification session
documented in the previous handoff.

It does NOT block ClassLink **SSO** certification (already done in PR #582). It DOES gate the
Roster Server cert call once #588 merges.

## 2. TL;DR

- **PR #588 — ClassLink Roster Server cert-parity (Class B): OPEN + CLEAN, all 9 CI checks green
  on the first run.** Awaiting human code review per Class B discipline (no auto-merge with a
  review in flight). 17 commits on `feature/classlink-roster-cert-parity`.
- **PR #589 — `.claude/rules/workflow.md` (Class A docs): OPEN, mergeable.** Codifies the
  per-task discipline lessons surfaced during PR #588 (specifically the SIS_CAPTURES
  misclassification near-miss). Includes a CLAUDE.md pointer for discoverability.
- **The design fork** in the previous handoff (`oneroster:` vs `classlink:` namespace) was
  resolved via a Codex `gpt-5.5`-high + Gemini consult. Both AIs independently converged on
  **tenant-scoped Approach 2**: `classlink:{quote(tenant)}:{quote(sourcedId)}` produced by one
  shared helper (`_classlink_roster_external_id`) used on **both** the roster-write side and the
  student-SSO read side. This closes the cross-tenant student-lookup FERPA hole (#1 risk) that
  bare `classlink:{sourcedId}` would have left open.
- **No email fallback** in `_create_classlink_student_session` (Codex's stricter call, chosen over
  Gemini's prefix-validated-fallback). Fail-closed audit log uses a hashed person_id, no PII.
- **`backend/routes/clever_routes.py` was NOT in the diff** — Class B blast-radius discipline.
  The student-session mint is duplicated (not shared) to keep the certified Clever path
  byte-identical.
- **Shared `delete_roster_data` orphan-students bug fixed** as part of this work (was leaving
  orphan student rows when a teacher had no class rows — incomplete FERPA right-to-delete).
  Strictly more-complete deletion for all three providers (OneRoster + Clever + ClassLink), still
  teacher_id-scoped.
- **Frontend** generalized via provider-parameterized handlers in `StudentApp.jsx`. Clever path
  provably unchanged — existing `StudentApp.cleverSelect.test.jsx` is the regression net and
  passed unmodified.

## 3. Current state (what SHIPPED + what's open)

### Spec + plan (committed to PR #588)
- `docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md` (`3d7a667`)
- `docs/superpowers/plans/2026-05-25-classlink-roster-certification-parity.md` (`903eec9`)

### Code + tests (PR #588, branch `feature/classlink-roster-cert-parity`)
17 commits total: 2 docs + 8 TDD implementation tasks (each: red test → green → commit) + 4
cleanups from per-task reviews + 2 SIS pin updates from the final whole-branch review. HEAD =
`2f14b73`. Key code commits:

- `fbe089f` T1: `normalize_roster` builder param (default-preserving)
- `3602a3a` T2: tenant-scoped key helper + `_PROVIDER_PREFIXES["classlink"]`
- `14b9482` T3: tenant-scoped roster-sync wiring (extracted `_run_classlink_roster_sync`)
- `490395e` T4: `delete_roster_data` orphan-students fix (shared)
- `1a7543a` T5: student-session core — lookup, mint, picker, fail-closed
- `8bddbd6` T6: student SSO endpoints + fail-closed callback hand-off
- `f36102a` + `48dfca7` T7: `/api/classlink/delete-data` (+ guard regression test hardening)
- `405fad7` T8: frontend provider generalization

### Workflow rulebook (PR #589, branch `docs/workflow-discipline-rules`)
- `cd7d4df` `.claude/rules/workflow.md` + CLAUDE.md pointer.
- This handoff lives here too (appended via a follow-up commit on this branch).

### PR status (as of session end)
- **#588 — OPEN, MERGEABLE, mergeStateStatus: CLEAN.** 9/9 status checks SUCCESS on first run.
  0 unresolved review threads, 0 issue comments. Awaiting human Class B review.
- **#589 — OPEN, MERGEABLE.** Docs only; standard CI.

### Working-tree noise (predates session — never committed)
`AGENTS.md`, `handoff.md` (being rewritten on #589), `.claude/scheduled_tasks.lock`,
`flask_session/`, `tests/reports/`. None are part of any commit in this session.

## 4. Local repro / verification

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate

# Backend gate (mirrors CI)
pytest -q --ignore=tests/load                     # expect: 5469 passed, 16 skipped
ruff check backend/ tests/                        # 117 pre-existing repo-wide; 0 on changed files
bandit -q -r backend/routes/classlink_routes.py backend/roster_sync.py backend/oneroster.py
                                                  # 1 pre-existing Low/Med (CLASSLINK_TOKEN_URL false-positive)

# Frontend gate
cd frontend && npx vitest run                     # 237 passed, 48 files
cd frontend && npm run build                      # success

# Spot-check the design-critical properties
grep -n "_classlink_roster_external_id" backend/routes/classlink_routes.py
                                                  # one helper, two call sites (write + read)
grep -n "email" backend/routes/classlink_routes.py | grep -i fallback
                                                  # zero hits — confirms no email fallback
grep -nE "@classlink_bp\.route" backend/routes/classlink_routes.py
                                                  # 6 routes (login-url, callback, session, logout,
                                                  # student-token, select-class, delete-data)

# PR status
gh pr view 588 --json mergeable,mergeStateStatus,statusCheckRollup --jq '.'
```

## 5. Concrete next steps (in priority order)

1. **Human code review on PR #588 (Class B gate).** Recommended review focus, in order:
   (a) `_create_classlink_student_session` (`backend/routes/classlink_routes.py:171-224`) — confirm
   no email fallback path. (b) `_classlink_roster_external_id` (`:79-91`) used identically on both
   write and read sides. (c) `delete_roster_data` restructure (`backend/roster_sync.py:254-303`)
   — every `.delete()` is teacher_id/class_id/student_id-scoped. (d) The callback's fail-closed
   branch + PII-free audit log.
2. **Merge PR #588 manually after review returns clean.** Do NOT arm `gh pr merge --auto`
   (Class B Hard Rule #7 in `.claude/rules/workflow.md`).
3. **Merge PR #589** at your convenience (docs-only, low risk).
4. **Pre-cert live dependency to verify** (carries over from PR #582 / SSO spec):
   confirm that the ClassLink userinfo `SourcedId` used as `person_id` equals the OneRoster Roster
   Server `sourcedId` for the same person in the live ClassLink test tenant. The design
   fails-closed if they diverge (T5 `test_no_row_fails_closed`, T6
   `test_unprovisioned_student_fails_closed`), but the happy path needs the contract to hold.
5. **Schedule the ClassLink Roster Server cert call** once #588 is merged + deployed.

## 6. Known follow-ups (filed in the PR body, not blocking)

1. **End-to-end tenant-isolation direct test** — seed `students` with
   `student_id_number = "classlink:dist-B:s1"`, call
   `_create_classlink_student_session("dist-A", "s1")`, assert None. The shared-helper byte-identity
   argument is convincing by construction; an explicit assertion would close the door on a future
   refactor that diverges the two call sites.
2. **Per-process in-memory auth-code + selection-token stores** — parity with Clever; would need
   Redis/DB backing for multi-worker production. One fix benefits both providers.
3. **`_classlink_roster_external_id` docstring** could note the deliberate divergence from
   `_classlink_guid` (string-tolerant of empty components vs None-returning) to satisfy
   `normalize_roster` upstream's always-a-string semantics.

## 7. Lessons captured this session

The session shipped **17 implementation commits across 9 TDD tasks under subagent-driven review**
plus a **whole-branch opus final review** — but a cross-cutting test failure
(`test_sis_alerting.py`, pinning `(file, line)` tuples in files Tasks 3 and 4 shifted) slipped past
**five** review passes and a cleanup-subagent nearly misclassified it as "pre-existing on main."

Root causes — and the rules they produced in `.claude/rules/workflow.md`:

- **Per-task verification was scoped to "named test files."** Cross-cutting consumers were
  invisible to scoped review. → **Per-task checklist** now requires
  `pytest -q --ignore=tests/load` (full suite) and
  `grep -rln '<modified file>' tests/` (cross-cutting test grep).
- **"Pre-existing failure" was accepted on instinct, not evidence.** → **Hard Rule #1**: such
  claims require `git checkout <base> -- <files>; pytest <test>` proof; 10 seconds of work that
  saves a red CI round-trip.
- **Line-shifting refactors require pin-test grep.** → **Hard Rule #3**, codified.
- **Full-suite gate was deferred to T9.** → **Hard Rule #2**: `pytest -q` is the floor, not the
  ceiling, of per-task verification.

The "Lessons From Incidents" appendix in `workflow.md` records the SIS_CAPTURES near-miss as the
founding case study. Future incidents go above that entry (newest first).

## 8. References

### PRs from this session
- **#588** — ClassLink Roster Server cert-parity (Class B) — open + clean.
- **#589** — workflow discipline rulebook (Class A docs) — open.
- **#582 / #583 / #585 / #586 / #587** (previous session) — ClassLink SSO + deploy work, all merged
  and live on `app.graider.live`.

### Key files
- `backend/oneroster.py:298-397` — `normalize_roster(raw, external_id_for=…)` (T1).
- `backend/routes/classlink_routes.py:58-91` — `_classlink_guid` + `_classlink_roster_external_id`.
- `backend/routes/classlink_routes.py:120-167` — auth-code + selection stores + mint.
- `backend/routes/classlink_routes.py:171-224` — `_create_classlink_student_session`
  (the read side of the tenant-scoped key).
- `backend/routes/classlink_routes.py:294-310` — `_trigger_roster_sync` + `_run_classlink_roster_sync`
  (the write side).
- `backend/routes/classlink_routes.py:` — student-token endpoint, select-class endpoint,
  delete-data endpoint.
- `backend/roster_sync.py:26-31` — `_PROVIDER_PREFIXES` with the new classlink entry.
- `backend/roster_sync.py:254-303` — `delete_roster_data` with the orphan fix.
- `frontend/src/components/StudentApp.jsx` — provider-generalized SSO handlers.

### Specs + plans
- `docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md`
- `docs/superpowers/plans/2026-05-25-classlink-roster-certification-parity.md`
- `docs/superpowers/specs/2026-05-25-classlink-sso-certification-readiness-design.md`
  (prior session, foundation for this work)

### Consult artifacts
- `/tmp/classlink_roster_consult.md` — the 3-AI consult prompt.
- Codex + Gemini outputs were captured in-session at `/tmp/codex_roster_out.md` +
  `/tmp/gemini_roster_out.md`. Both AIs independently converged on tenant-scoped Approach 2.

### Workflow rulebook
- `.claude/rules/workflow.md` — the codified per-task discipline.
- `CLAUDE.md` (top) — pointer section pointing readers to the rulebook.

---

*Status: clean ship. No open investigations, no failed attempts, no debug threads. Two PRs await
human action; nothing autonomous needed. Next agent: read `.claude/rules/workflow.md` first
(per the CLAUDE.md pointer) — it codifies what you already know but spells out the verification
gates that catch silent failures.*
