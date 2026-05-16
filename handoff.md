# Handoff: 2026-05-14/16 session — 15 PRs merged, tracker empty, all followups shipped

> **State: GREEN / idle.** Nothing is failing, nothing is blocked, no spec is skipped for architectural reasons, the issue tracker is empty. This is a clean-slate handoff, not a stuck-investigation one. The most valuable parts for a fresh agent are the **Disproved hypotheses** (a real debug detour where the stack trace lied) and the **6 heuristics** at the bottom — read those before touching e2e or frontend deploy.

## 1. Goal

Run an autonomous issue-closing / PR-shipping sprint on Graider: clear the GitHub tracker, ship every fix through the 9 required CI checks, keep `handoff.md` an accurate artifact. **Achieved — tracker empty, all sketched follow-ons shipped + validated.**

## 2. TL;DR

- **15 PRs merged this session (#374–#388)**, all auto-deployed via Railway (plus #373 closed by #374, not merged). Breakdown: #374–#382 = issue-closure code work; #384 = plan-sweep doc; #380/#383/#385/#387 = handoff refreshes; #386 = multi-teacher e2e unskip + its regression fix; **#388 = light-mode UI fix (Portal Submissions panel)**.
- **16 issue closures** + **4 plan docs closed**. `gh issue list --state open` → **0 rows**.
- **multi-teacher.spec.js followup fully CLOSED** (#386): unskipped, header-injected, and the e2e regression it surfaced (OnboardingWizard modal) root-caused + fixed at the workflow-seed layer. RED→GREEN trail preserved in §5.
- **Light-mode bug fixed** (#388): `ResultsTab.jsx:1775` hardcoded a dark-only background; swapped to theme-aware `var(--glass-bg)`. Rebuilt Vite bundle committed (required — see heuristic #6).
- **GitNexus index REFRESHED** 2026-05-16 to HEAD `6e26b45` (17,586 nodes / 49,463 edges; embeddings 7,331→10,653 — preserved + grown via `--embeddings`). The earlier "zombie PID 67783 / reboot pending" note was a **misdiagnosis** propagated across handoff refreshes: no unkillable process ever existed; a plain `kill -TERM` stopped the MCP server and `npx gitnexus analyze` ran fine. MCP `gitnexus_*` tools dropped when the server stopped and resume **next session** (Claude Code relaunches it against the fresh index); unavailable for the rest of this one.
- Local `main` at **`879f8e7`** (PR #388 merge). Working tree: only Vite-build churn + `.claude/scheduled_tasks.lock` + `tests/reports/` (untracked, unrelated). No in-flight branches.

## 3. Current state

### PRs merged (code work)

| PR | Title | Closes | Merge |
|----|-------|--------|-------|
| [#374](https://github.com/nlev8/Graider/pull/374) | `hmac.compare_digest` on 6 OAuth state/nonce checks | #373 | `ede4a5a` |
| [#375](https://github.com/nlev8/Graider/pull/375) | teacher-scope `import_student_data` via `backend.storage` | #339 | `7c5cb73` |
| [#376](https://github.com/nlev8/Graider/pull/376) | `sync_all_to_cloud` period CSV format + counters | #341 | `ee333a0` |
| [#377](https://github.com/nlev8/Graider/pull/377) | anthropic adapter `emit_json` auto-decode to TextPart | #343 | `e7d5a5c` |
| [#378](https://github.com/nlev8/Graider/pull/378) | survey + publish-assessment 503-not-500 when Supabase offline | #355 | `bfa9f1b` |
| [#379](https://github.com/nlev8/Graider/pull/379) | scan_submissions_folder coverage | #348 | `55d7643` |
| [#381](https://github.com/nlev8/Graider/pull/381) | shard local-file storage by teacher_id + dev-shim approval bypass | #353 + #370 p2 | `b991ed0` |
| [#382](https://github.com/nlev8/Graider/pull/382) | classify+propagate AI transients in inner catches | #224 | `129a49f` |
| [#386](https://github.com/nlev8/Graider/pull/386) | unskip multi-teacher.spec.js + sharded-tenant onboarding seed fix | #370 p2 | `52b08c3` |
| [#388](https://github.com/nlev8/Graider/pull/388) | **fix(results): Portal Submissions panel unreadable in light mode** | (screenshot bug) | `879f8e7` |

Doc-only: #380 `2df703b`, #383 `3d45fdf`, #384 `0435f69` (plan sweep), #385 `2976292`, #387 `08ae9c3`.

### Plans closed (PR #384 — bulk-flip + STATUS-stamp)

`2026-05-14-security-trio` (PR #372+#374), `2026-05-11-audit-major5-e2e-promotion` (#351,#353,#371,#378,#381), `2026-05-05-sis-compliance-hardening` (file-verified across earlier PRs), `2026-05-01-phase4.3-sprint2-per-dok-mastery` (`dok.py` + 3 test files + `by_dok` plumbing). **Not flipped (optional next):** older April plans — Phase 3a Gradebook, Phase 3b Assessment Comparison, Phase 4 Quick Click Remediation, Grade/Planner Tab extractions. Spot-checked as shipped (Gradebook.jsx/GradeTab.jsx/PlannerTab.jsx exist) but left scoped to the 4-plan commitment.

### Stale issues closed (no code — already shipped, verified)

#217, #218 (umbrellas, code-comment + CLAUDE.md verified); #229→#240; #234→#235; #245→#246; #247→#281; #249→#256; #253→#257; #355 p1→#371; #370 p1→#371; **#370 p2→#386** (e2e run 25965070445 green). Each verified via the named regression test or direct file inspection.

### Follow-up issues filed

None. Nothing exceeded PR scope (CLAUDE.md Rule #11).

## 4. Local repro / verify-what-works

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull --ff-only          # expect HEAD = 879f8e7
gh issue list --state open --limit 50             # expect 0 rows
grep -rl "test.skip" tests/e2e/specs/             # expect: multi-teacher.spec.js ABSENT

# Backend (the sentry_sdk error users hit = wrong interpreter, NOT a bug):
source venv/bin/activate                          # venv exists, has all deps
python -m backend.app                             # run from repo root so `from backend...` resolves

# Frontend build (must commit the bundle — see heuristic #6):
cd frontend && npm run build                      # ~2s; outputs to ../backend/static/

# Re-validate the multi-teacher e2e (the only spec needing manual dispatch):
gh workflow run e2e-nightly.yml --ref main
gh run watch <id> --exit-status                   # expect: Multi-teacher results: 30 pass, 0 fail, 0 skip
```

Light-mode fix (#388) verification: switch the app to light mode → Results tab → Portal Submissions panel should be a clean white card with readable text (was dark slate box + invisible text).

## 5. Disproved hypotheses (the valuable part — do NOT re-try these)

**multi-teacher.spec.js RED run ([25964874545](https://github.com/nlev8/Graider/actions/runs/25964874545)), `12 pass / 3 fail`:**

- ❌ *"Unskipping just needs the `X-Test-Teacher-Id` header injection (the handoff sketch said ≤10 lines)."* — Wrong. The header was necessary but insufficient; it surfaced a second, hidden blocker.
- ❌ *"The failure is `locator.click` timing out → the Analytics nav button is missing / not rendered for sharded teachers."* — **The stack trace actively misled here.** The button *was* present; it was behind a modal backdrop. Reading the trace points you at the click site, not the cause.
- ❌ *"It's another `g.user_id == 'local-dev'` literal somewhere (the handoff predicted this)."* — Not the cause. The approval bypass (#381) was working fine.
- ✅ **Actual root cause, found only by looking at the Playwright failure SCREENSHOT** (`gh run download <id>` → `test-failed-1.png`): the OnboardingWizard "STEP 1 OF 8" modal was covering the dashboard. The 3 sharded teacher_ids route to `~/.graider_tenants/teacher-test-00N/.graider_settings.json` (storage.py `_tenant_home`, #381), but the workflow only seeded the *default* `$HOME/.graider_settings.json` → no `config.onboarding_completed` → wizard. Fixed at the workflow-seed layer (#386), NOT in app/storage (which would defeat the per-tenant isolation the test exists to prove). GREEN: [25965070445](https://github.com/nlev8/Graider/actions/runs/25965070445).

**sentry_sdk `ModuleNotFoundError` (user hit it running the backend):**

- ❌ *"Hard `import sentry_sdk` in `auth_decorators.py` should be guarded as optional."* — Rejected. `sentry-sdk[flask]==2.58.0` is a pinned dep and is installed in the venv; the error was the user launching with a non-venv Python. Guarding it would mask a misconfig and is a high-blast-radius change to a module `app.py` imports. Root cause was operational, not code.

## 6. Most likely remaining causes / latent risks (nothing failing — forward-looking only)

Ranked by likelihood of biting a future session:

1. **GitNexus `analyze` exits non-zero on a benign teardown crash.** The index is now fresh (rebuilt 2026-05-16, reflects HEAD). But `npx gitnexus analyze` prints `Repository indexed successfully`, writes `meta.json`, *then* crashes in shutdown with `libc++abi: … mutex lock failed: Invalid argument` → exit 1. **The index is good despite exit 1** — verify via `.gitnexus/meta.json` stats + data-file mtime, NOT the exit code. (`lastIndexedCommit` is always `None` in this gitnexus build — not a staleness signal.)
2. **~13 conditionally-skipped `frontend/e2e/*` specs** (student-*, teacher-publish-modal, automation-builder, resource-management, etc.) — UNVERIFIED whether these are intentional per-test skips or latent holdouts. Not in scope this session, not tracked in any issue/plan. If a future session wants more e2e coverage, triage these first.
3. **Frontend deploy footgun** — any frontend fix that doesn't commit the rebuilt `backend/static/` bundle will pass CI (CI rebuilds) but **not reach users** (Railway/NIXPACKS serves committed static, no build step at deploy). See heuristic #6.

## 7. Concrete next step

**There is no required next step — the sprint goal is met.** If a fresh agent wants productive work, in priority order:

1. **Close the older April plans** with the same bulk-flip + STATUS-stamp pattern (heuristic #2) — purely doc, low risk, ~30 min.
2. **Triage the ~13 skipped frontend/e2e specs** — read each `test.skip` reason; unskip + fix the genuinely-stale ones following the #386 RED→GREEN playbook (always check the failure screenshot first).

_(GitNexus reindex is DONE this session — index fresh at `6e26b45`. Procedure for when it goes stale again: `kill -TERM` the `gitnexus mcp` PIDs → `npx gitnexus analyze --embeddings` from repo root → ignore the benign exit-1 / `mutex lock failed` teardown crash → verify `.gitnexus/meta.json` stats + mtime. **No reboot, ever** — see heuristic #7.)_

Otherwise: await user direction. Do not invent work.

## 8. Heuristics earned (carry forward — these are the real deliverable)

1. **Verify-before-implement** for any issue >2 weeks old. Grep `"Closes GH #N"` / `"fix(#N)"` + run the regression test. ~half of 16 issues were already-shipped.
2. **Bulk-flip + STATUS-stamp** for retro-closing executed plans: sed `- [ ]` → `- [x]` + a top-of-file STATUS block linking the closing PRs.
3. **`backend/app.py` calls `load_dotenv(override=True)` at import** — `monkeypatch.setenv` on .env keys (e.g. `DEV_USER_ID`) loses. Pass via header (`X-Test-Teacher-Id`) instead.
4. **`_supabase_raw` singleton poisoning** — tests setting a fake `SUPABASE_URL` without also mocking `_sb_load`/`_sb_save` lazy-init the real client against the fake host and poison later tests. Always mock `_sb_*`.
5. **e2e per-tenant sharding needs a per-tenant onboarding seed.** A spec injecting `X-Test-Teacher-Id` shards to `~/.graider_tenants/<safe_id>/`; the global `$HOME/.graider_settings.json` seed doesn't cover it → OnboardingWizard modal silently blocks nav. **Symptom lies**: `locator.click` timeout on a present-but-obscured button, not a missing one. **Read the Playwright failure screenshot first**, not the stack trace.
6. **Frontend fixes must commit the rebuilt `backend/static/` bundle.** Railway/NIXPACKS deploy is gunicorn-only (no `npm run build` at deploy); the committed bundle is what's served. CI's Frontend Build rebuilds for verification but does NOT commit back. Workflow: edit `frontend/src/` → `cd frontend && npm run build` → `git add frontend/src/... backend/static/index.html backend/static/assets/` (this stages the hashed-bundle rename/delete/add set) → PR. Skipping the bundle = green CI, unchanged production. (Also: theme bugs are almost always a hardcoded color where a `var(--*)` belongs. `--card-bg-light` exists only in `:root`/dark, NOT in `[data-theme="light"]`; `--glass-bg` is the theme-aware panel background convention.)
7. **GitNexus needs no reboot — that belief was a multi-handoff misdiagnosis.** "Zombie PID holding the LevelDB lock, reboot pending" propagated across ≥4 handoff refreshes *unverified*. Reality: it was the normal client-spawned `gitnexus mcp` server; `kill -TERM` stops it instantly (a true zombie ignores TERM — that's the test). `npx gitnexus analyze --embeddings` then reindexes (~5 min) and **exits 1 with `libc++abi … mutex lock failed` AFTER printing "indexed successfully" + writing meta.json** — a teardown-only crash; trust `meta.json` stats + data-file mtime, never the exit code. Stopping the MCP server drops `gitnexus_*` tools until next session (Claude Code respawns it); do NOT manually relaunch (orphans a process nothing talks to). **General lesson: re-verify carried-over operational claims with a live check before repeating them in a handoff.**

## 9. References

- PRs: [#374](https://github.com/nlev8/Graider/pull/374) → [#388](https://github.com/nlev8/Graider/pull/388)
- Issues closed: #217, #218, #224, #229, #234, #245, #247, #249, #253, #339, #341, #343, #348, #353, #355, #370, #373
- Plans closed: 2026-05-14-security-trio, 2026-05-11-audit-major5-e2e-promotion, 2026-05-05-sis-compliance-hardening, 2026-05-01-phase4.3-sprint2-per-dok-mastery
- e2e debug runs: [25964874545](https://github.com/nlev8/Graider/actions/runs/25964874545) (RED, root-cause evidence) → [25965070445](https://github.com/nlev8/Graider/actions/runs/25965070445) (GREEN)
- Key files: `backend/storage.py:48-60` (`_tenant_home`), `.github/workflows/e2e-nightly.yml` (onboarding-seed steps), `frontend/src/styles/globals.css` (theme vars), `frontend/src/tabs/ResultsTab.jsx:1775` (#388 fix), `railway.json`/`nixpacks.toml`/`Procfile` (deploy = gunicorn only)
- GitNexus: index rebuilt 2026-05-16 (`.gitnexus/meta.json` — 17,586 nodes / 49,463 edges / 10,653 embeddings); `npx gitnexus analyze` exits 1 on a benign post-success teardown crash (see §6.1 / heuristic #7)
- CLAUDE.md Rule #12 — this doc is committable as an artifact (tracker-empty state + RED→GREEN record + GitNexus-reindex correction + 7 heuristics qualify).
