# Handoff: 2026-05-14/16 session — 18 PRs merged, tracker empty, GitNexus reindexed

> **State: GREEN / idle.** Nothing failing, nothing blocked, no spec architecturally skipped, tracker empty, working tree clean, GitNexus index fresh. The single most valuable thing here for a fresh agent is **§5 Disproved hypotheses** — especially the GitNexus "must reboot" myth that survived ≥4 unverified handoff refreshes. Read §5 and §8 before touching e2e, frontend deploy, or GitNexus.

## 1. Goal

Autonomous issue/PR sprint on Graider: clear the tracker, ship every fix through the 9 required CI checks, keep `handoff.md` an accurate artifact. **Achieved** — tracker empty, all sketched follow-ons shipped + validated, and a false carried-over operational claim corrected at the root.

## 2. TL;DR

- **18 PRs merged this session (#374–#391)**, all auto-deployed via Railway (plus #373 closed by #374, not merged). Code work: #374–#382, #386 (e2e), #388 (UI). Docs: #380/#383/#385/#387/#389 (handoff refreshes), #384 (plan sweep), #390 (GitNexus correction), #391 (gitnexus stat block).
- **16 issue closures + 4 plan docs closed.** `gh issue list --state open` → **0 rows**.
- **GitNexus index REINDEXED + fresh** (the "reboot needed" claim was a misdiagnosis — see §5.A). 17,586 nodes / 49,463 edges / 10,653 embeddings, at HEAD. MCP `gitnexus_*` tools resume next session (server stopped this session; do not hand-relaunch).
- **Working tree clean** — only untracked `.claude/scheduled_tasks.lock` + `tests/reports/`. No tracked-file dirt, no in-flight branches.
- Local `main` at **`a886610`**.

## 3. Current state

### PRs merged — code work

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
| [#388](https://github.com/nlev8/Graider/pull/388) | fix(results): Portal Submissions panel unreadable in light mode | (screenshot bug) | `879f8e7` |

Docs: #380 `2df703b`, #383 `3d45fdf`, #384 `0435f69`, #385 `2976292`, #387 `08ae9c3`, #389 `6e26b45`, **#390 `19eae6c`** (GitNexus correction), **#391 `a886610`** (gitnexus stat block: CLAUDE.md 13553→17586, AGENTS.md 4880→17586).

### Plans closed (PR #384)

`2026-05-14-security-trio`, `2026-05-11-audit-major5-e2e-promotion`, `2026-05-05-sis-compliance-hardening`, `2026-05-01-phase4.3-sprint2-per-dok-mastery` — bulk-flip + STATUS-stamp. **Optional next:** older April plans (Phase 3a Gradebook, 3b Assessment Comparison, Phase 4 Quick Click, Grade/Planner Tab extractions) — spot-checked shipped, not flipped, scoped out.

### Stale issues closed (verified already-shipped)

#217, #218 (umbrellas); #229→#240; #234→#235; #245→#246; #247→#281; #249→#256; #253→#257; #355 p1→#371; #370 p1→#371; #370 p2→#386 (e2e run 25965070445 green).

### Follow-up issues filed

None. Nothing exceeded PR scope.

## 4. Local repro / verify-what-works

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull --ff-only            # expect HEAD = a886610
git status --short                                  # expect ONLY: .claude/scheduled_tasks.lock, tests/reports/
gh issue list --state open --limit 50               # expect 0 rows
grep -rl "test.skip" tests/e2e/specs/               # expect multi-teacher.spec.js ABSENT

# Backend (sentry_sdk error users hit = WRONG INTERPRETER, not a bug):
source venv/bin/activate                            # venv at ./venv exists, has all deps
python -m backend.app                               # run from repo root

# Frontend (MUST commit rebuilt bundle — heuristic #6):
cd frontend && npm run build                        # ~2s -> ../backend/static/

# Multi-teacher e2e (only spec needing manual dispatch; green at a886610):
gh workflow run e2e-nightly.yml --ref main
gh run watch <id> --exit-status                     # expect: Multi-teacher results: 30 pass, 0 fail, 0 skip

# GitNexus health (index is FRESH — do NOT reboot):
python3 -c "import json;d=json.load(open('.gitnexus/meta.json'));print(d['stats'])"
# expect ~ {'nodes':17586,'edges':49463,'embeddings':10653}; mtime 2026-05-16
```

## 5. Disproved hypotheses (READ THIS — the highest-value section)

### A. "GitNexus needs a laptop reboot — zombie PID 67783 holds the LevelDB lock" — **FALSE, propagated ≥4 handoffs unverified**

- ❌ *"PID 67783 is an unkillable `UE`-state zombie holding `.gitnexus/lbug`."* — Live check: **PID 67783 does not exist**; zero processes in `U` state anywhere; `.gitnexus/lbug` is the **131 MB DB data file**, not a lock (no `LOCK` file). The premise was a misdiagnosis copied forward across refreshes (including by me in #389) **without anyone re-checking**.
- ❌ *"A reboot is the only way to clear it."* — Nothing to clear. It was the normal client-spawned `gitnexus mcp` server (state `S+`). `kill -TERM` stopped it **in 3 seconds** — a true zombie ignores TERM; that *is* the disproving test.
- ✅ **Resolution:** stopped MCP server, `npx gitnexus analyze --embeddings` → reindexed ~5 min (17,586 nodes; embeddings 7,331→10,653, preserved+grown). Corrected at root in #390 (handoff) + #391 (stat block). **Lesson → heuristic #7.**
- ⚠️ Gotcha: `npx gitnexus analyze` **exits 1** with `libc++abi … mutex lock failed` — but **after** "Repository indexed successfully" + `meta.json` write. Benign teardown crash. Trust `meta.json` stats + mtime, **never the exit code**. (`lastIndexedCommit` is always `None` in this build — not a staleness signal.)

### B. multi-teacher.spec.js RED run ([25964874545](https://github.com/nlev8/Graider/actions/runs/25964874545), `12 pass / 3 fail`)

- ❌ *"Unskipping just needs the `X-Test-Teacher-Id` header (sketch said ≤10 lines)."* — Necessary but insufficient; surfaced a hidden second blocker.
- ❌ *"`locator.click` timeout → Analytics nav button missing for sharded teachers."* — **Stack trace actively misled.** Button present, behind a modal backdrop. Trace points at the click site, not the cause.
- ❌ *"Another `g.user_id == 'local-dev'` literal (handoff predicted this)."* — Not it; #381's bypass worked fine.
- ✅ **Root cause found only via the Playwright failure SCREENSHOT** (`gh run download <id>` → `test-failed-1.png`): OnboardingWizard "STEP 1 OF 8" modal. Sharded teacher_ids route to `~/.graider_tenants/teacher-test-00N/.graider_settings.json` (storage.py `_tenant_home`, #381) but the workflow only seeded the default `$HOME/.graider_settings.json`. Fixed at the workflow-seed layer (#386), NOT app/storage. GREEN: [25965070445](https://github.com/nlev8/Graider/actions/runs/25965070445).

### C. sentry_sdk `ModuleNotFoundError`

- ❌ *"Guard `import sentry_sdk` in `auth_decorators.py` as optional."* — Rejected. `sentry-sdk[flask]==2.58.0` is pinned + installed in the venv; the user ran with a non-venv Python. Guarding masks a misconfig and is high-blast-radius (`app.py` imports it). Root cause operational, not code.

## 6. Most likely remaining risks (nothing failing — forward-looking)

1. **~13 conditionally-skipped `frontend/e2e/*` specs** (student-*, teacher-publish-modal, automation-builder, resource-management, …). UNVERIFIED whether intentional per-test skips or latent holdouts. Not tracked anywhere. Triage first if expanding e2e coverage.
2. **Frontend deploy footgun** — a frontend fix not committing the rebuilt `backend/static/` bundle passes CI but never reaches users (Railway/NIXPACKS = gunicorn only, no deploy build). See heuristic #6.
3. **GitNexus doc-commit churn** — `gitnexus analyze` re-dirties the `<!-- gitnexus:start -->` block in CLAUDE.md/AGENTS.md every reindex. PostToolUse hook auto-reindexes after commit/merge; if it leaves those dirty, commit the stat-only delta (like #391) — don't fight it, don't reindex manually for doc-only commits.

## 7. Concrete next step

**None required — sprint goal met, everything green.** If a fresh agent wants work, priority order:

1. **Close older April plans** (heuristic #2 bulk-flip + STATUS-stamp) — doc-only, ~30 min.
2. **Triage the ~13 skipped frontend/e2e specs** — read each `test.skip` reason; unskip + fix genuinely-stale ones via the #386 RED→GREEN playbook (**screenshot first, not stack trace**).

Otherwise await user direction. Do not invent work. `gitnexus_*` MCP tools are down this session (server stopped); they auto-return next session against the fresh index — a new session is the cleanest continuation point.

## 8. Heuristics earned (carry forward — the real deliverable)

1. **Verify-before-implement** for issues >2 weeks old: grep `"Closes GH #N"`/`"fix(#N)"` + run the regression test. ~half of 16 were already-shipped.
2. **Bulk-flip + STATUS-stamp** to retro-close executed plans: sed `- [ ]`→`- [x]` + top-of-file STATUS block linking closing PRs.
3. **`backend/app.py` does `load_dotenv(override=True)` at import** — `monkeypatch.setenv` on .env keys loses. Pass via header (`X-Test-Teacher-Id`).
4. **`_supabase_raw` singleton poisoning** — tests setting a fake `SUPABASE_URL` without mocking `_sb_load`/`_sb_save` lazy-init the real client against the fake host, poisoning later tests. Always mock `_sb_*`.
5. **e2e per-tenant sharding needs a per-tenant onboarding seed.** A spec injecting `X-Test-Teacher-Id` shards to `~/.graider_tenants/<safe_id>/`; the global `$HOME/.graider_settings.json` seed doesn't cover it → OnboardingWizard modal silently blocks nav. **Symptom lies** (timeout on a present-but-obscured button). **Read the Playwright failure screenshot first.**
6. **Frontend fixes must commit the rebuilt `backend/static/` bundle.** Railway/NIXPACKS deploy is gunicorn-only; the committed bundle is what's served; CI rebuilds but never commits back. Edit `frontend/src/` → `npm run build` → `git add frontend/src/... backend/static/index.html backend/static/assets/` → PR. Skipping = green CI, unchanged prod. (Theme bugs: usually a hardcoded color where a `var(--*)` belongs — `--card-bg-light` is dark-only; `--glass-bg` is the theme-aware panel bg.)
7. **GitNexus needs no reboot — that was a multi-handoff misdiagnosis.** `kill -TERM` the `gitnexus mcp` PIDs (true zombie ignores TERM = the test) → `npx gitnexus analyze --embeddings` → ignore the benign post-success `exit 1`/`mutex lock failed` → verify `.gitnexus/meta.json`. `gitnexus_*` tools drop until next session; don't hand-relaunch (orphans a process). **Re-verify carried-over operational claims with a live check before repeating them.**
8. **`gh pr merge --auto` does NOT arm when the PR is already fully green** (no pending→green transition); it silently leaves `autoMerge=false` and the PR sits `MERGEABLE/CLEAN` unmerged. Checks pending → `--auto` works. Already green → direct `gh pr merge --squash`. After a base PR merges, a stacked PR goes `BEHIND` (branch-protection wants up-to-date) — `gh pr update-branch <n>` to unstick.

## 9. References

- PRs: [#374](https://github.com/nlev8/Graider/pull/374) → [#391](https://github.com/nlev8/Graider/pull/391)
- Issues closed: #217, #218, #224, #229, #234, #245, #247, #249, #253, #339, #341, #343, #348, #353, #355, #370, #373
- Plans closed: 2026-05-14-security-trio, 2026-05-11-audit-major5-e2e-promotion, 2026-05-05-sis-compliance-hardening, 2026-05-01-phase4.3-sprint2-per-dok-mastery
- e2e debug runs: [25964874545](https://github.com/nlev8/Graider/actions/runs/25964874545) (RED) → [25965070445](https://github.com/nlev8/Graider/actions/runs/25965070445) (GREEN)
- GitNexus: index rebuilt 2026-05-16 (`.gitnexus/meta.json` 17,586/49,463/10,653); `analyze` exits 1 on benign teardown (§5.A / heuristic #7); `.gitnexus/` is gitignored (local only)
- Key files: `backend/storage.py:48-60` (`_tenant_home`), `.github/workflows/e2e-nightly.yml` (onboarding-seed steps), `frontend/src/styles/globals.css` (theme vars), `frontend/src/tabs/ResultsTab.jsx:1775` (#388), `railway.json`/`nixpacks.toml`/`Procfile` (deploy = gunicorn only)
- CLAUDE.md Rule #12 — committable artifact (tracker-empty + RED→GREEN + GitNexus correction + 8 heuristics qualify).
