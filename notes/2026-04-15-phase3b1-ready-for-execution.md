# Phase 3b1 — Ready for Execution

**Date:** 2026-04-15
**Status:** Spec + plan complete; Codex Gate 1 GREEN across 8 review rounds; awaiting execution in a fresh session.

## What this is

Phase 3b of the codebase improvement roadmap splits `backend/routes/planner_routes.py` (8104 LOC). Phase 3b1 is scoped to **helpers extraction only** — the ~2150-line post-processing pipeline moves into a new `backend/services/assignment_post_processing.py`. Phase 3b2+ (route decomposition into feature blueprints) is deferred to a separate spec.

## Key artifacts

- **Branch:** `spec/phase3b1-planner-helpers` (pushed to remote)
- **Spec:** `docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md`
- **Plan:** `docs/superpowers/plans/2026-04-15-phase3b1-planner-helpers.md`

## Design

**Scope:** helpers-only (option a). Codex endorsed over routes-only (b) and both (c).

**Migration:** 5-PR sequence (MUST merge sequentially):
1. **PR1** — 9 leaf helpers (no cross-refs to unmoved code)
2. **PR2** — `_hydrate_question` dispatcher + 12 sub-hydrators + `_infer_editable_columns` + 10 text/geometry utils
3. **PR3** — 3 quality functions + golden tests + handler smoke
4. **PR4** — `_auto_fix_flagged_questions` explicit-context signature refactor (sole non-byte-identical PR)
5. **PR5** — `_post_process_assignment` orchestrator + prompt builders + shim removal

**Target module:** `backend/services/assignment_post_processing.py` (~2150 LOC after all 5 PRs).

**Cycle avoidance:** The orchestrator `_post_process_assignment` moves LAST (PR5) after all its callees have migrated. PR1 ships leaf helpers only.

## Codex review history (8 rounds)

| Round | Finding | Outcome |
|---|---|---|
| Scope decomposition | Chose (a) over (b)/(c) | GREEN + 5-PR sequence |
| Spec rev 1 | 4 issues: hydrator count, cost tracking, PR1 sequencing, Gotcha #5 | HOLD → fixed |
| Spec rev 2 | 4 stale references | HOLD → fixed |
| Spec rev 2 fixup | | GREEN |
| Spec rev 3 deep review | 6 issues: hard constraint contradiction, PR1 cycle, golden test timing, safety rail #6, allowlist wording, summary table | HOLD → fixed |
| Spec rev 3 fixup | 1 stale Gotcha #3 ref | HOLD → fixed |
| Spec final | | GREEN |
| Plan Gate 1 | 1 issue: sequential merge constraint note | HOLD → fixed |
| Plan final | | GREEN |

**Total substantive HOLDs resolved: 5 across 8 rounds.**

## Hard constraints (per PR)

- Function bodies byte-identical for PRs 1, 2, 3, 5. PR4 is the sole exception (explicit-context signature refactor).
- **PRs must merge sequentially** — each PR's shim block references prior PRs' moved symbols.
- SIS compliance 180/180 green (tests/test_sso_contracts.py + Clever/ClassLink/OneRoster suites).
- Coverage floor 32 holds (CI enforces).
- No Clever/ClassLink/OneRoster/roster_sync/oneroster_gradebook file modifications.

## Known gotchas (documented in spec)

1. `_auto_fix_flagged_questions` pulls Flask `g.user_id` + `backend.api_keys` → PR4 refactors to explicit kwargs, with shim adapter in planner_routes.py keeping existing route callers unchanged.
2. Hidden schema aliases (`column_headers`→`headers`, `correct_answer`↔`answer`, `correctVertices`, placeholder expansion, editable-column inference) → golden tests in PR3 pin them.
3. 6-phase ordering is behaviorally significant → orchestrator moves byte-identical in PR5; golden tests exercise the full chain.
4. Tests may import planner_routes directly → shim keeps green until PR5 removes it.
5. `generate_assessment` reads `warning`/`warning_severity` after pipeline → PR3 handler smoke test pins the contract. `regenerate_questions` does NOT run the full pipeline (classify/hydrate/validate only).
6. Pre-existing `config`/`logger` latent bugs from Phase 3a → allowlist-and-proceed pattern applies.

## Safety rails per PR

- Boot check (route count ≥ 250)
- SIS contract suite (180/180)
- Shim guard test (transitional, deleted PR5)
- Golden tests (created PR3, permanent)
- AST bound-name completeness (permanent — Phase 3a pattern)
- Handler smoke test (created PR3, permanent)

## Next session pickup instructions

1. Check out `spec/phase3b1-planner-helpers` OR verify spec+plan merged to main
2. Read `docs/superpowers/plans/2026-04-15-phase3b1-planner-helpers.md` (full 5-task plan)
3. Invoke `superpowers:subagent-driven-development` for the execution sequence
4. First action: merge the spec branch to main as a docs-only PR (follow Phase 3a pattern from PR #65)
5. Then branch PR1 from main, dispatch implementer for leaf helpers
6. Per Phase 3a learning: **run Codex exhaustive Gate 3 (not just static) on PR3/PR4** — the static pass missed the DOCUMENTS_DIR + _check_batch_calibration NameError bombs last phase

## Branch state at time of handoff

```
spec/phase3b1-planner-helpers
  ed99875 spec rev 1
  149d7bc spec rev 2 Codex fixes
  70415d9 spec rev 2 fixup (stale refs)
  78a8c58 spec rev 3 Codex deep review fixes
  310185a spec fixup (Gotcha #3)
  884569c plan commit
  7b155e3 plan sequential-merge note
```

All pushed to origin.

## Related memory

- `project_phase3a_complete.md` — precedent (app.py extraction) with process learnings
- `project_codebase_improvement_roadmap.md` — full 5-phase plan
- `feedback_always_recommit_after_review.md` — recommit plan files after each review
- `feedback_always_branch_for_new_work.md` — never commit to main
