# PR-3 Convergence Consensus (LOCKED 2026-06-05)

> Output of a two-engine convergence gate: **Claude (ultracode/superpowers)** — a 3-design tournament
> (byte-identity · readability · safety-sequencing priors) → 9 adversarial judges → synthesis — AND
> **Codex** — an independent F1-F8 review that fact-checked the brief against source. Both reasoned from
> `_pr3-ground-truth.md`. They AGREE on every load-bearing decision; the 4 divergences were cosmetic and
> resolved below. User ratified F1=a1 and authorized PR-3a.

## Locked decisions
| # | Decision | Rationale |
|---|---|---|
| **F1** | **a1 — thread the 7 import-bound names (6 grade fns + `ASSIGNMENT_NAME`) as keyword-only params.** Body byte-identical. | Strict byte-identity is the entire value of 3a. Module-level hoist BANNED (no-ops golden-net `patch('assignment_grader.*')`). Codex + 2/3 Claude candidates chose a1; user ratified. |
| **F2** | Identically-named **keyword-only params, no defaults**; **no** dataclass/context object. | A missing capture → loud `TypeError` at submit, never a silent default. Context object would touch ~200 refs, destroying the byte-identity proof. Unanimous. |
| **F3** | Build `gsf_kwargs = {…all captures by explicit name…}` before the executor loop; `executor.submit(grade_single_file, filepath, i+1, len(new_files), **gsf_kwargs)`. Not `partial`, not an opaque dict-param. | Greppable 1:1 audit vs the symtable free-var list; self-proving via the global-refs rail. |
| **F4** | Lift `find_matching_config` to module level: `(filename, all_configs, grading_state, file_content=None)`; update its 2 in-gsf call sites (L818, L826). Same commit as the gsf lift. | Sole caller is gsf; only free vars are `all_configs`+`grading_state`. Required for the orchestrator LOC math (1352−626−115=611). The 2 call-site edits are the ONE documented byte-identity exception. |
| **F5** | PR-3b: decompose into **5-8 module-level helpers** along the verified seams, individual named params, `ast.get_source_segment` extraction. Extract **`_build_file_ai_notes` (L964-1210, 247 LOC) FIRST** — it alone gets gsf <300. Thread `config_mismatch`/`config_mismatch_reason` (produced L836/872-877, consumed L1356/L1379-1380). | All seams are contiguous sub-blocks of the single try (L763-1386). Exact count set by keeping each helper <300. |
| **F6** | **PR-3a** (pure byte-identical lift + executor rewire) → **PR-3b** (decompose body). Two Class B PRs, spec-then-opus review, manual merge each. | Don't conflate a provable move with a restructure. 3a lands the scary executor wire in isolation; 3b gets the byte-identity-impossible decomposition its own focused diff. Unanimous. |
| **F7** | Pass the SAME `grading_state` dict **by reference** to gsf, lifted `find_matching_config`, and any logging sub-helper. NEVER `.copy()`/`dict(...)`. | Workers append to `grading_state['log']/['results']` unlocked (L808/874/878/1235) + read at L1145 (keep-higher). A copy ships GREEN (golden net asserts no worker log lines) but loses logs and can let a lower regrade overwrite a higher score. Add an `id()`-identity gate. |
| **F8** | Orchestrator decomposition (~611 LOC) → **deferred to PR-4** (out of PR-3 scope), filed with a seam sketch. | PR-3 scope is the two named giants. Folding in the orchestrator balloons the diff + mixes two Class B refactors. Unanimous. |

## Gate-fixes the convergence surfaced (verified against source — the brief/handoff MISSED these)
1. **WILL GO RED:** `tests/test_pipeline_safety_rails.py::test_baseline_deviation_failure_alerts_to_sentry`
   (L316) does `inspect.getsource(pipeline._run_grading_thread_inner)` + asserts `'detect_baseline_deviation'`
   present (call at L1326, moves into gsf). → **Re-point to `pipeline.grade_single_file`** in PR-3a.
   (Sibling `test_master_csv_load_failure_alerts_to_sentry` SURVIVES — its first `master_grades.csv` match is
   the orchestrator's L663 already-graded loader, which stays. VERIFY during 3a.)
2. **GO BLIND (pass but cover nothing):** `test_pipeline_lazy_imports_all_resolve` (`ast.walk(target_fn)`,
   L130) + `test_pipeline_global_refs_all_resolve` (`collect_global_refs(…__code__)` recursing `co_consts`,
   L237/242) currently cover gsf *because it's nested*. After the lift it falls out of both traversals.
   → **Extend both to also walk `pipeline.grade_single_file` + `pipeline.find_matching_config`** in PR-3a.
3. **PROMPT-SNAPSHOT NET (prereq for 3b):** the golden net mocks the grade fns and does NOT assert
   `file_ai_notes` content — so the 247-LOC `_build_file_ai_notes` seam can silently drop a grading factor.
   Add `tests/test_grading_prompt_snapshot.py` capturing the prompt string each grade fn receives.
4. **`ast.get_source_segment`, NOT naive dedent:** the gsf body has `file_ai_notes += """…"""` rubric blocks
   (L1004-1019/1025-1037/1052-1063/1092+) with continuation lines at column 0 — a min-indent/`textwrap.dedent`
   corrupts them. Use string-literal-aware extraction + a reversible re-indent assertion.
5. **SIS hazard is a PHANTOM:** count-floor of 3, currently 5 (see brief correction). No `(file,line)` re-pin.

## PR-3a step plan (executing now)
0. Baseline green (DONE: golden 10/10, sis+core 64/64).
1. **Prereq net:** add `tests/test_grading_prompt_snapshot.py` (covers the 3b seam; commit now).
2. **Lift `find_matching_config`** (L425-539) → module level, `+ all_configs, grading_state` params, via `ast.get_source_segment`.
3. **Lift `grade_single_file`** (L761-1386) → module level, keyword-only params (28 request + grading_state + all_configs + 7 import-bound under a1), byte-identical body, update 2 fmc call sites.
4. **Rewire** `executor.submit(..., **gsf_kwargs)` — same `grading_state`/`all_configs` refs, no copy.
5. **Re-point** `test_baseline_deviation_failure_alerts_to_sentry` → `grade_single_file`.
6. **Extend** the 2 blinded guards to walk the lifted functions.
7. **Verify:** full suite + cross-cutting grep + symtable 0-free-vars + byte-identity diff vs base + capture-count==5. Spec→opus review, manual merge. (gsf still 626 → CQ7 closes at 3b.)
