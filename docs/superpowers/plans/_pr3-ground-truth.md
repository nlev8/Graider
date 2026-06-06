# PR-3 Ground Truth Brief — lift + split `grade_single_file`

> Authoritative facts derived via `symtable` (correct closure-scope analysis) + full source read on
> branch `refactor/cq7-grading-giants` @ today. **This SUPERSEDES the stale numbers/claims in
> `2026-06-05-grading-giants-split-plan.md`.** Both the Claude design workflow and Codex must reason
> from THIS file, not the older plan doc.

## Goal
Get `_run_grading_thread_inner` (currently 1352 LOC, L350-1701) and its nested closure
`grade_single_file` (626 LOC, L761-1386) in `backend/grading/pipeline.py` each under 300 LOC,
**behavior-preservingly**. This is the core grading-correctness path → Class B, highest stakes.
The golden net `tests/test_grading_thread_golden.py` (10 scenarios, mutation-tested FAITHFUL) is the
gate; it must stay green after every step.

## Authoritative scope facts (symtable, not the stale plan)
- `grade_single_file` positional params today: `(filepath, file_index, total_files)`.
- It has **38 free vars** (closure captures from the orchestrator), NOT 37. Full list below.
- Its body is a **single `try` block** spanning L763-1386 (one `except Exception` at L1384). All
  splits must extract helpers *called from inside* that try.

### CORRECTION to the plan doc (load-bearing — the plan is WRONG here)
The plan claims `grading_state` / `all_configs` / `grading_lock` are "module-level globals
(AST-confirmed)". **FALSE.** symtable proves:
- `grading_state` → **LOCAL** of `_run_grading_thread_inner` (`grading_state = _get_state(teacher_id)`),
  captured by `grade_single_file` ⇒ MUST become a param.
- `all_configs` → **LOCAL** of the orchestrator (`all_configs = {}`), captured ⇒ MUST become a param.
- `grading_lock` → LOCAL of the orchestrator, NOT captured by `grade_single_file` (irrelevant to PR-3).
None are module-level. Treating them as globals on lift = silent breakage.

### The 38 captures, categorized
**(a) 7 names imported at RUN-TIME inside the orchestrator (`from assignment_grader import ...`, L565-569):**
`grade_assignment, grade_multipass, grade_with_ensemble, grade_with_parallel_detection,
parse_filename, read_assignment_file` + the module constant `ASSIGNMENT_NAME` (= `''`, used in-gsf at L886
AND in the orchestrator at L1631/1635/1648 — so the L565 import keeps it regardless).
[CORRECTED: both engines flagged `ASSIGNMENT_NAME` was mis-bucketed under (d) request-scoped — it is import-bound.]

> ⚠️ **TRAP (the plan misses this):** these are imported *inside the function at run time*, which is
> exactly why the golden net + existing tests can `patch("assignment_grader.grade_with_parallel_detection")`
> and have it take effect. If you HOIST `from assignment_grader import ...` to pipeline.py module level,
> pipeline binds its own references at import time and **all that test patching silently breaks.**
> ⇒ The import MUST stay function-local. Module-level import is BANNED.
> Two viable options: **(a1)** thread the 6 as params from the orchestrator's run-time import
> (byte-identical body, 37 total params), or **(a2)** put one `from assignment_grader import (...)`
> at the top of the lifted `grade_single_file` body (31 params, +1 import line per call). Both keep
> patchability. Confirm a choice.

**(b) 2 orchestrator LOCALS → params:** `grading_state`, `all_configs`.
> `grading_state` is a shared mutable dict appended to from parallel executor threads (L808, 874, 878,
> 1145, 1235) WITHOUT the lock today. Preserve exactly: pass the SAME dict object by reference, never a copy.

**(c) 1 nested closure → must be reachable after lift:** `find_matching_config`
(its real signature is `(filename, file_content=None)`; it captures `all_configs` + `grading_state`).
Call sites inside `grade_single_file`: L818 `find_matching_config(filepath.name)` and
L826 `find_matching_config(filepath.name, file_text)`.

**(d) 28 request-scoped state values → keyword params named identically (byte-identity):**
`ai_model, assignment_config, class_period, ensemble_models, extraction_mode,
fallback_completion_only, fallback_custom_rubric, fallback_effort_points, fallback_exclude_markers,
fallback_imported_doc, fallback_markers, fallback_notes, fallback_rubric_type, fallback_sections,
fallback_use_section_points, global_ai_notes, grade_level, grading_style, output_folder,
period_class_level_map, resubmissions, roster, rubric_prompt, rubric_weights, student_period_map,
subject, teacher_id, trusted_students`.

**Module-level names already resolvable (stay as-is, NOT params):** `add_assignment_to_history,
build_accommodation_prompt, build_history_context, detect_baseline_deviation, sentry_sdk, _logger,
Path, os` + builtins. (Plus body-local imports kept as-is: `re` L859, `csv` L1155, `hashlib` L1337,
`build_correction_context` L974.)

## The load-bearing wire
`backend/grading/pipeline.py:1414`:
```python
future = executor.submit(grade_single_file, filepath, i + 1, len(new_files))
```
Inside `with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS=3)` (L1399). When `grade_single_file`
is lifted to module level with N keyword params, this submit MUST pass every capture. Wrong ⇒ parallel
grading silently breaks. Golden scenario `test_multiple_files_parallel_executor` (PARALLEL_WORKERS=3)
is the guard.

## Behavior the golden net pins (must survive)
5 early-return points + the 4-way dispatch:
1. completion-only early return (L941-962) — no AI call.
2. read-fail early return (L1215) — `{"success": False, "error": "Could not read file"}`.
3. no-config skip guard early return (L1236-1241) — `is_config_missing`.
4. API-error early return (L1311) — `grade_result['letter_grade']=='ERROR'`.
5. except → `{"success": False, "error": "Grading failed for this file"}` (L1385).
4-way dispatch (L1270-1307): `ensemble_models>=2`→ensemble · `is_trusted`→multipass ·
`skip_detection`(FITB)→grade_assignment · else→parallel_detection.

## Internal phase seams (for the split — all INSIDE the single try)
| Phase | Lines | ~LOC | Produces |
|--|--|--|--|
| roster match (parse + fuzzy) | 764-813 | 50 | student_name, student_info, parsed |
| config resolve (+content fallback +fallback bundle) | 815-894 | 80 | matched_config, file_markers/exclude/notes/sections, matched_title, is_completion_only, imported_doc, assignment_template_local, rubric_type, custom_rubric, use_section_points, marker_config, effort_points, config_mismatch(+reason) |
| rubric-type autodetect | 896-908 | 13 | rubric_type, is_completion_only |
| student period resolve | 910-937 | 28 | student_period |
| completion-only early return | 939-962 | 24 | (return) |
| build file_ai_notes (prompt assembly) | 964-1210 | 247 | file_ai_notes, history_context |
| read file + grade_data | 1212-1224 | 13 | file_data, grade_data |
| no-config skip guard | 1231-1241 | 11 | (return) |
| trust/FITB + rubric weights + 4-way dispatch | 1243-1307 | 65 | grade_result |
| API-error return | 1309-1312 | 4 | (return) |
| post-grade (marker status, baseline, history, log) + final assembly | 1314-1382 | 69 | new_result dict |

## Hazards
- ~~`tests/test_sis_alerting.py` pins `(file, line)` tuples in pipeline.py~~ **[CORRECTED — PHANTOM HAZARD]**
  Both engines verified: pipeline.py is NOT in the line-pinned `SIS_CAPTURES`; it is only a per-file COUNT
  FLOOR of 3 (`test_sis_alerting.py:250`). Actual count today is 5 (capture_exception at L680/1340/1349/1665/1693);
  the lift moves L1340/L1349 *inside* module-level gsf but they stay IN pipeline.py → count stays 5 ≥ 3.
  **No `(file,line)` re-pin, no window=8 task.** Just don't delete a capture.
- Byte-identity protocol (reuse PR #688 assistant-split scripts): anchor-extract block → de-indent →
  assert re-indent == original (reversible) → `ast.parse` → symtable free-var check → golden net.
- Class B → after each behavior-touching commit: 4-lens adversarial review + MANUAL merge (no auto-merge).

## The DECISIONS both engines must agree on (answer each)
- **F1 — the 6 assignment_grader fns:** option (a1) thread as params, or (a2) function-local import in
  the lifted fn? (Module-level hoist is BANNED — breaks patching.)
- **F2 — lift signature:** identically-named keyword params (byte-identical body) vs a context
  object/dataclass bundling the captures (cleaner, breaks byte-identity)? Recommend with reasoning.
- **F3 — executor.submit rewire:** `functools.partial(grade_single_file, **captures)` vs explicit
  kwargs vs a captures dict?
- **F4 — find_matching_config:** lift to module level (thread all_configs+grading_state, update 2 call
  sites) vs keep nested / pass as param?
- **F5 — split granularity:** how many sub-helpers, exact seam boundaries (from the table above), and
  how each sub-helper receives its many inputs (individual params vs shared context object)? All must
  be <300 LOC; prefer byte-identical bodies.
- **F6 — sequencing:** ONE PR-3, or split into 3a (pure lift to module level, provably byte-identical,
  golden-net-green, executor rewire) THEN 3b (decompose the 626-line body into <300 sub-helpers)?
- **F7 — confirm** grading_state passed by reference (same dict, no copy) preserves the current
  unlocked-parallel-append behavior exactly.
- **F8 — orchestrator (PR-4 preview):** after lifting gsf+find_matching_config out, the orchestrator is
  ~611 LOC, still >300. Is PR-4 (decompose orchestrator into phase helpers) in scope now or a separate
  follow-up?
