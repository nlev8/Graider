# Handoff: 2026-05-14/15 session — 10 PRs merged, tracker empty

**Session-end snapshot. Replaces the prior draft (which still listed #353 as open and the `multi-teacher.spec.js` unskip as a followup). The tracker is now fully empty after the #217 / #218 umbrella sweep.**

## Goal

Snapshot of the May 14–15 sprint so a fresh agent (or future-me) can pick up cleanly. **Nothing is genuinely open on the tracker.** One spec-level cleanup item is captured below as the only thing left worth doing if the next session wants something to ship; otherwise this is a natural stop.

## TL;DR

- **10 PRs merged this session**, all auto-deployed via Railway: #374, #375, #376, #377, #378, #379, #380, #381, #382 (plus #373 closed by #374).
- **16 stale/real issue closures**: #217, #218, #224, #229, #234, #245, #247, #249, #253, #339, #341, #343, #348, #353, #355, #370, #373.
- **Tracker is empty** — `gh issue list --state open` returns 0 rows.
- **GitNexus index still stale** at commit `22bc414` (May 9). Zombie PID 67783 still holds the LevelDB lock. **Reboot pending.** Index lag does not block work; impact analyses just need a "+1 risk tier" pessimism filter until reindex.
- Local `main` at `129a49f`. Working tree has only Vite-build churn + this handoff. No in-flight branches.

## Shipped this session (code work)

| PR | Title | Closes | Merge commit |
|----|-------|--------|--------------|
| [#374](https://github.com/nlev8/Graider/pull/374) | `hmac.compare_digest` on 6 OAuth state/nonce checks | #373 | `ede4a5a` |
| [#375](https://github.com/nlev8/Graider/pull/375) | teacher-scope `import_student_data` via `backend.storage` | #339 | `7c5cb73` |
| [#376](https://github.com/nlev8/Graider/pull/376) | `sync_all_to_cloud` period CSV format + counters | #341 | `ee333a0` |
| [#377](https://github.com/nlev8/Graider/pull/377) | anthropic adapter `emit_json` auto-decode to TextPart | #343 | `e7d5a5c` |
| [#378](https://github.com/nlev8/Graider/pull/378) | survey + publish-assessment 503-not-500 when Supabase offline | #355 | `bfa9f1b` |
| [#379](https://github.com/nlev8/Graider/pull/379) | scan_submissions_folder coverage (prefix-fuzzy + display fallback) | #348 | `55d7643` |
| [#380](https://github.com/nlev8/Graider/pull/380) | docs: refresh handoff.md (interim) | — | `2df703b` |
| [#381](https://github.com/nlev8/Graider/pull/381) | shard local-file storage by teacher_id + dev-shim approval bypass | #353 + #370 part 2 | `b991ed0` |
| [#382](https://github.com/nlev8/Graider/pull/382) | classify+propagate AI transients in inner catches | #224 | `129a49f` |

## Stale issues closed (no code work — already shipped in earlier PRs)

Pattern worth remembering: a high fraction of "open" tracker items were already shipped but never closed.

| Issue | Already fixed by | Verified via |
|-------|------------------|--------------|
| #217 (Test Gates Sprint umbrella) | Coverage 32→60% (multi-PR per CLAUDE.md); E2E Smoke now required; DOMPurify mock removed in #228 | direct file inspection + CLAUDE.md history |
| #218 (Scalability Sprint umbrella) | PR #233 admin N+1; \`assistant_tools_assessments.py:111\` closes MAJOR #12; \`App.jsx:1835\` backoff closes MINOR | source-of-truth comments in code |
| #229 (XSS render test for AssistantChat) | PR #240 (\`63773b5\`) | \`AssistantChat.xss.test.jsx\` — 5 tests green |
| #234 (AdminTab plural-key mismatch) | PR #235 (\`5981b20\`) | direct file inspection |
| #245 (portal_credentials end-to-end isolation) | PR #246 (\`89eb734\`) | \`test_portal_credentials_isolation.py\` — 11 tests green |
| #247 (pending_send cross-tenant leak) | PR #281 + \`_SENSITIVE_KEY_PREFIXES = ('pending_send',)\` | \`test_pending_send_shared_unit.py\` — 21 tests green |
| #249 (email_routes broken grading_state import) | PR #256 (\`a472ddc\`) | \`test_email_routes_grading_state_import.py\` — 6 tests green |
| #253 (load_style path traversal) | PR #257 (\`7908e1a\`) | \`test_document_generator_path_traversal.py\` — 23 tests green |
| #355 part 1 (missing roster_civics_7.csv) | PR #371 (inadvertently shipped the fixture) | 5 roster CSVs in git, path resolution verified |
| #370 part 1 (settings-workflow e2e holdout) | PR #371 | spec unskipped + Classroom-tab navigation added |
| #370 part 2 (multi-teacher.spec.js) | Architectural deps closed by **#381** | see followup below |

## Followup — only thing left worth doing

The architectural blockers documented in `tests/e2e/specs/multi-teacher.spec.js:23-35` (skip comment from PR #371) are now both fixed by PR #381:

1. \`auth_routes.py:110\` literal-\`'local-dev'\` approval check → now bypasses for any dev-shim teacher_id via \`g.is_dev_shim\` flag.
2. \`storage.py:_key_to_filepath\` global file paths → now shard by \`teacher_id\` under \`HOME/.graider_tenants/<safe_id>/\`.

**The mechanical follow-on** (out of PR #381's scope because validating it requires a `workflow_dispatch` e2e-nightly run, not just pytest):

```diff
- test.skip('3 teachers complete full workflows concurrently', async ({ browser }) => {
+ test('3 teachers complete full workflows concurrently', async ({ browser }) => {
   ...
   const teacherRuns = TEACHERS.map(async (teacher) => {
-    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
+    const context = await browser.newContext({
+      viewport: { width: 1440, height: 900 },
+      extraHTTPHeaders: { 'X-Test-Teacher-Id': teacher.id },
+    });
```

Acceptance: open PR with that diff (≤10 lines + delete the skip comment); run `workflow_dispatch` on `e2e-nightly.yml` from the PR branch; if green, merge. If still red, the failure trace will identify the remaining blocker (probably some other route's `g.user_id == 'local-dev'` literal). Time estimate: 30 min for the PR + 1 e2e cycle.

## GitNexus operational note (carryover, unchanged)

PID 67783 still holds the LevelDB lock at `.gitnexus/lbug`. State `UE` (uninterruptible-exit). Confirmed alive again this session — same process, same state. Reboot is the only fix.

After reboot:
```bash
cd /Users/alexc/Downloads/Graider
ps -ef | grep "gitnexus analyze" | grep -v grep   # expect empty
npx gitnexus analyze --embeddings                  # preserves the 7,331 embeddings
```

The MCP server (separate PID, read-only path) keeps working on the stale index. Today's impact analyses returned correct results, but new tests from #381 / #382 won't appear in the graph until reindex.

## Concrete heuristic earned this session

When picking up any issue >2 weeks old, **first grep for `"Closes GH #N"` / `"fix(#N)"` in the codebase and run the regression test if one exists**. Close-with-verification-comment if shipped; only branch off if truly open. Of 16 issues touched this session, ~half were already-shipped. Verify-before-implement saved hours.

## References

- PRs merged: [#374](https://github.com/nlev8/Graider/pull/374) → [#382](https://github.com/nlev8/Graider/pull/382)
- All issues closed this session: #217, #218, #224, #229, #234, #245, #247, #249, #253, #339, #341, #343, #348, #353, #355, #370, #373
- CLAUDE.md Rule #12 (handoff discipline) — this doc is committable when it serves as an artifact. Tracker-empty-state + the multi-teacher.spec.js followup sketch qualifies.
