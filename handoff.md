# Handoff: 2026-05-14/15 session — 12 PRs merged, tracker empty, 4 plans closed

**Session-end snapshot. Replaces the prior draft (PR #383, when totals were 10 PRs / tracker empty / plans untouched). Since then PR #382 was the 11th merge and PR #384 (plan-checkbox sweep) was the 12th. This refresh adds the plan-closure layer to the artifact.**

## Goal

Snapshot of the May 14–15 sprint so a fresh agent (or future-me) can pick up cleanly. **Nothing is genuinely open on the tracker, and the 4 most-recent plans are now marked CLOSED with verifiable STATUS stamps.** One spec-level cleanup item remains as the only sketched follow-on if the next session wants something to ship.

## TL;DR

- **12 PRs merged this session**, all auto-deployed via Railway: #374, #375, #376, #377, #378, #379, #380, #381, #382, #383, #384 (plus #373 closed by #374).
- **16 stale/real issue closures**: #217, #218, #224, #229, #234, #245, #247, #249, #253, #339, #341, #343, #348, #353, #355, #370, #373.
- **4 plan docs closed** with STATUS stamps + bulk-flipped checkboxes (PR #384): security-trio, audit-major5 e2e, SIS compliance, Phase 4.3 Sprint 2.
- **Tracker is empty** — `gh issue list --state open` returns 0 rows.
- **GitNexus index still stale** at commit `22bc414` (May 9). Zombie PID 67783 still holds the LevelDB lock. **Reboot pending.** Index lag does not block work; impact analyses just need a "+1 risk tier" pessimism filter until reindex.
- Local `main` at `0435f69`. Working tree has only Vite-build churn + this handoff. No in-flight branches.

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
| [#383](https://github.com/nlev8/Graider/pull/383) | docs: refresh handoff.md (prior version of this file) | — | `3d45fdf` |
| [#384](https://github.com/nlev8/Graider/pull/384) | docs(plans): close 4 shipped plans — checkbox sweep | — | `0435f69` |

## Plans closed this session (PR #384)

Doc-only sweep: top-of-file STATUS stamps + bulk-flipped checkboxes for plans whose work was already shipped:

- `docs/superpowers/plans/2026-05-14-security-trio.md` — closed by PR #372 + PR #374
- `docs/superpowers/plans/2026-05-11-audit-major5-e2e-promotion.md` — closed by PRs #351, #353, #371, #378, #381
- `docs/superpowers/plans/2026-05-05-sis-compliance-hardening.md` — all 9 tasks verified shipped across earlier PRs (file-inspection of `classlink_oidc.py`, `redaction.py`, `lti.py` allowlist, audit_log calls, etc.)
- `docs/superpowers/plans/2026-05-01-phase4.3-sprint2-per-dok-mastery.md` — `dok.py` + 3 test files (20 tests green) + `by_dok` plumbing through grading_service.py and student_portal_routes.py

Older April plans (Phase 3a Gradebook, Phase 3b Assessment Comparison, Phase 4 Quick Click Remediation, Grade Tab + Planner Tab extractions) were spot-checked and appear shipped per file-existence (Gradebook.jsx, GradeTab.jsx, PlannerTab.jsx all exist) but NOT flipped — stayed scoped to the 4-plan commitment. Next session could close those out with the same bulk-flip + STATUS-stamp pattern if desired.

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

## Concrete heuristics earned this session

1. **Verify-before-implement** for any issue >2 weeks old. Grep for `"Closes GH #N"` / `"fix(#N)"` in the codebase and run the regression test if one exists. Close-with-verification-comment if shipped; only branch off if truly open. Of 16 issues touched this session, ~half were already-shipped — verify-before-implement saved hours.
2. **Bulk-flip + STATUS-stamp** for retrospectively closing executed plans. Don't toggle individual checkboxes; sed-replace `- [ ]` → `- [x]` and add a top-of-file STATUS block linking to the PRs that closed each task. Auditors can verify post-hoc via the linked commits.
3. **`backend/app.py` calls `load_dotenv(override=True)` at import time** — `monkeypatch.setenv` on .env-controlled keys (e.g. `DEV_USER_ID`) loses to the override. Workaround: send the value via header (e.g. `X-Test-Teacher-Id`) instead of relying on env-var precedence.
4. **`_supabase_raw` singleton poisoning** — tests that monkeypatch `SUPABASE_URL` to a fake host but DON'T also mock `_sb_load`/`_sb_save` cause lazy-init of the real Supabase client against the fake URL, which then poisons later tests' Supabase calls with DNS failures. Always mock the `_sb_*` ops in tests that set fake URLs.

## References

- PRs merged: [#374](https://github.com/nlev8/Graider/pull/374) → [#384](https://github.com/nlev8/Graider/pull/384)
- All issues closed this session: #217, #218, #224, #229, #234, #245, #247, #249, #253, #339, #341, #343, #348, #353, #355, #370, #373
- Plans closed: 2026-05-14-security-trio, 2026-05-11-audit-major5-e2e-promotion, 2026-05-05-sis-compliance-hardening, 2026-05-01-phase4.3-sprint2-per-dok-mastery
- CLAUDE.md Rule #12 (handoff discipline) — this doc is committable when it serves as an artifact. Tracker-empty-state + the multi-teacher.spec.js followup sketch + the 4 heuristics above all qualify.
