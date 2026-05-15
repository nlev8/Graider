# Handoff: 2026-05-15 security/correctness sprint — 7 PRs merged, 1 issue left

**Session-end snapshot. Replaces the mid-session draft. Tracker is now effectively clean: every open issue I touched is closed, with one architectural item (#353) deliberately deferred to fresh context.**

## Goal

Snapshot of the May 14–15 session so a fresh agent (or future-me) can pick up the one remaining tracker entry without re-investigating today's ground. Seven PRs landed. The only surviving open issue is scoped + reasoned at the bottom.

## TL;DR

- **7 PRs merged this session**, all auto-deployed via Railway: #374, #375, #376, #377, #378, #379 (plus #373 closed by #374).
- **8 stale-issue closures**: #247, #249, #253 were already fixed in prior PRs; #339, #341, #343, #348, #355, #370, #373 closed by today's PRs.
- **1 issue genuinely open**: **#353** — load-test multi-persona + multi-teacher e2e (architectural; also covers #370 part 2). Deferred to fresh context per the analysis below.
- **GitNexus index still stale** at commit `22bc414` (May 9). Zombie PID 67783 still holds the LevelDB lock. **Reboot pending.** Index lag does not block work; impact analyses just need a "+1 risk tier" pessimism filter until reindex.
- Local `main` at `55d7643`. Working tree has only Vite-build churn + this handoff. No in-flight branches.

## Shipped this session

| PR | Title | Closes | Merge commit |
|----|-------|--------|--------------|
| [#374](https://github.com/nlev8/Graider/pull/374) | `hmac.compare_digest` on 6 OAuth state/nonce checks | #373 | `ede4a5a` |
| [#375](https://github.com/nlev8/Graider/pull/375) | teacher-scope `import_student_data` via `backend.storage` | #339 | `7c5cb73` |
| [#376](https://github.com/nlev8/Graider/pull/376) | `sync_all_to_cloud` period CSV format + counters | #341 | `ee333a0` |
| [#377](https://github.com/nlev8/Graider/pull/377) | anthropic adapter `emit_json` auto-decode to TextPart | #343 | `e7d5a5c` |
| [#378](https://github.com/nlev8/Graider/pull/378) | survey + publish-assessment 503-not-500 when Supabase offline | #355 | `bfa9f1b` |
| [#379](https://github.com/nlev8/Graider/pull/379) | scan_submissions_folder coverage (prefix-fuzzy + display fallback) | #348 | `55d7643` |

## Issues triaged this session (no code work needed)

| Issue | Action | Reason |
|-------|--------|--------|
| #247 | Closed with verify comment | Already fixed by PR #281 + `_SENSITIVE_KEY_PREFIXES = ('pending_send',)`. 21 regression tests pass. |
| #249 | Closed with verify comment | Already fixed by PR #256. `email_routes.py:880,1233` uses `_get_state`/`_get_lock` factory. 6 regression tests pass. |
| #253 | Closed with verify comment | Already fixed by PR #257. `_safe_style_name` + `_path_inside_styles_dir` + `_resolve_style_path` in place. 23 regression tests pass. |
| #370 | Closed (consolidated) | Part 1 shipped via PR #371. Part 2 folded into #353 (same architectural fix). |

Pattern observed: 3 of 4 "HIGH severity" issues I picked up first were already shipped but the tracker entries had never been closed. Worth a verify-pass before sinking time into a fresh implementation on any future-dated issue.

## Genuinely-open work

### #353 — Load-test multi-persona + multi-teacher e2e (architectural)

**Now also covers #370 part 2** per the consolidation comment on #353. Two blockers documented:

1. `backend/routes/auth_routes.py:110` — approval-status bypass matches the literal string `'local-dev'` only. Any other dev-shim `teacher_id` injected via `X-Test-Teacher-Id` hits `sb.auth.admin.get_user_by_id` which 500s in CI (no Supabase configured). App stalls on approval-pending screen before the spec can do anything.
2. `backend/storage.py:115` — `_use_supabase` returns False when Supabase isn't configured, but `_key_to_filepath` uses hardcoded paths. `~/.graider_settings.json` (and siblings) are shared across all `teacher_id`s in local-dev mode regardless of which header was sent — so 3+ simulated teachers still race on the same file, which is the bug the load test was built to expose.

**Resolution B from #353's body:** shard `_key_to_filepath` by `teacher_id` when `X-Test-Teacher-Id` is present in dev-shim mode, and drop the `auth.py:110` literal-`'local-dev'` check.

**Touches:** `backend/storage.py` (we've touched this twice today — #375 and #376), `backend/routes/auth_routes.py`, audit of all `_key_to_filepath` callers, new tests. Estimated 200-400 LOC + tests.

**Follow-up after Resolution B lands:** remove `test.skip` on `tests/e2e/specs/multi-teacher.spec.js:22` and add `extraHTTPHeaders: { 'X-Test-Teacher-Id': teacher.id }` to each `browser.newContext(...)` call. The skip comment in the spec (added by PR #371) already documents both blockers — when they're fixed, deletion is mechanical.

**Why I deferred it from this session:** the skip comment is a flashing yellow light. Someone (= me on PR #371) already investigated and discovered the issue body's "1-line fix" framing is wrong. Architectural touches on `storage.py` after 6 other PRs land in the same session risk incoherent layered changes (CLAUDE.md Rule #5 minimal blast radius). Best landed first thing in a fresh session.

## Concrete next step

Pick up #353 in a fresh session. Brief sketch for the implementer:

1. **In `backend/storage.py`**: when `_use_supabase(teacher_id)` returns False AND the current request has a non-`'local-dev'` `teacher_id` (e.g. via `X-Test-Teacher-Id`), shard the file path by `teacher_id`. The cleanest knob is in `_key_to_filepath` — add a `teacher_id` parameter and route through it from `_file_load` / `_file_save` / `_file_delete` / `_file_list_keys`. Existing single-tenant local-dev usage (`teacher_id='local-dev'`) keeps the unsharded layout.
2. **In `backend/routes/auth_routes.py:110`**: change the literal-`'local-dev'` check to accept any dev-shim teacher_id (the existing dev-shim resolution at `backend/auth.py:184-190` already validates the header).
3. **Tests**:
   - Storage unit test: 2 teacher_ids → distinct file paths → no cross-contamination on save/load/list/delete
   - Auth route test: dev-shim with non-`'local-dev'` teacher_id no longer 500s on missing Supabase
   - E2E: unskip `multi-teacher.spec.js:22`, add `extraHTTPHeaders` per context

Watch for: existing `storage.py` callers that pass `teacher_id` positionally vs by keyword. There are several after today's #375 + #376 changes. `gitnexus_impact` (once index is fresh) will help here.

## GitNexus operational note (carryover, unchanged from 2026-05-14)

PID 67783 still holds the LevelDB lock at `.gitnexus/lbug`. State `UE` (uninterruptible-exit). 6 days elapsed, 49.59s CPU. SIGKILL ineffective. Confirmed alive again this session — same process, same state. Reboot is the only fix.

After reboot:
```bash
cd /Users/alexc/Downloads/Graider
ps -ef | grep "gitnexus analyze" | grep -v grep   # expect empty
npx gitnexus analyze --embeddings                  # preserves the 7,331 embeddings
```

The MCP server (separate PID, read-only path) keeps working on the stale index. Today's impact analyses returned correct results because affected symbols hadn't moved since May 9, but the new test files added in PR #375/#376/#377/#378/#379 won't appear in the graph until reindex.

## References

- PRs merged: [#374](https://github.com/nlev8/Graider/pull/374), [#375](https://github.com/nlev8/Graider/pull/375), [#376](https://github.com/nlev8/Graider/pull/376), [#377](https://github.com/nlev8/Graider/pull/377), [#378](https://github.com/nlev8/Graider/pull/378), [#379](https://github.com/nlev8/Graider/pull/379)
- Issues closed today: #247, #249, #253, #339, #341, #343, #348, #355, #370, #373
- Genuinely open: **#353** only
- Consolidation comment: [#353 (folding in #370 part 2)](https://github.com/nlev8/Graider/issues/353#issuecomment-4460476356)
- CLAUDE.md Rule #12 (handoff discipline) — this doc lives here, uncommitted by default since it's a session summary not an open-investigation artifact.
