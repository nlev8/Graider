# CQ7 grading-giants split — execution plan (`_run_grading_thread_inner` + `grade_single_file`)

> The last 2 of 18 in the Code Quality 6→7 campaign
> (`docs/superpowers/plans/2026-06-04-code-quality-7-function-split-campaign.md`).
> This doc is the recon + execution plan so the split can run efficiently (ideally a fresh dedicated
> session, per the campaign plan). **Recon DONE; no grading code changed yet.**

## Goal
Get the last 2 backend functions >300 LOC under 300, behavior-preservingly, to flip Code Quality 6→7.
File: `backend/grading/pipeline.py`. This is the **core grading-correctness path** → Class B, highest stakes.

## TL;DR
- The pair: `_run_grading_thread_inner` (L207-1698, **1492 LOC**) contains a nested closure `grade_single_file`
  (L758-1383, **626 LOC**) submitted to a `ThreadPoolExecutor` (L1396-1415).
- **No full-thread characterization net exists** — true "netless giant." Golden net is the mandated PR-1.
- `grade_single_file` has **37 closure captures** — the crux. Most are request-scoped state; 6 are module fns; 2 are module globals.
- 3 nested helpers are **pure (0 captures)** → trivial module-level lifts. 2 more capture only module globals.
- **Golden net FIRST (own PR)**, then the split (likely PR-2 small lifts, PR-3 grade_single_file, PR-4 orchestrator).

## Why it's hard (the executor + captures)
`executor.submit(grade_single_file, filepath, i+1, len(new_files))` at **pipeline.py:1411**. When
`grade_single_file` is lifted to module level it gains ~29 keyword-only params (the captures) → the submit MUST
become `executor.submit(grade_single_file, filepath, i+1, len(new_files), **captures)` (or `functools.partial`).
**This is the single load-bearing wiring change.** Wrong → parallel grading silently breaks. Cover it with a
multi-file golden scenario (PARALLEL_WORKERS=3).

## Structure map (re-validate line #s before editing — they drift each merge)
| Symbol | Lines | LOC | Captures from outer | Lift difficulty |
|--|--|--|--|--|
| `_run_grading_thread_inner` | 207-1698 | 1492 | (orchestrator) | decompose into phases (PR-4) |
| `_update_state` | 233-235 | 3 | `grading_lock`,`grading_state` (module globals) | trivial |
| `extract_content_fingerprints` | 282-310 | 29 | **0 (pure)** | trivial |
| `fuzzy_match_score` | 312-355 | 44 | **0 (pure)** | trivial |
| `find_matching_config` | 357-471 | 115 | `all_configs`,`grading_state` (module globals) | easy |
| `calculate_late_penalty` | 473-536 | 64 | **0 (pure)** | trivial |
| `grade_single_file` | 758-1383 | 626 | **37** (below) | HARD (PR-3) |

`grading_state` / `grading_lock` / `all_configs` are **module-level globals** (AST-confirmed: `module-level=True`,
no `global` decl in the outer fn). Lifted helpers resolve them as globals — no param needed.

### grade_single_file's 37 captures, categorized
- **6 module functions** (imported at `pipeline.py:562` `from assignment_grader import (...)`):
  `grade_assignment, grade_multipass, grade_with_ensemble, grade_with_parallel_detection, parse_filename, read_assignment_file`.
  → On lift: add a module-level import (or keep a local import inside the lifted fn). NOT params.
- **2 module globals:** `grading_state`, `all_configs` → globals, NOT params.
- **~29 request-scoped state** → keyword-only params named identically to preserve byte-identity:
  `ASSIGNMENT_NAME, ai_model, assignment_config, class_period, ensemble_models, extraction_mode,
  fallback_completion_only, fallback_custom_rubric, fallback_effort_points, fallback_exclude_markers,
  fallback_imported_doc, fallback_markers, fallback_notes, fallback_rubric_type, fallback_sections,
  fallback_use_section_points, global_ai_notes, grade_level, grading_style, output_folder,
  period_class_level_map, resubmissions, roster, rubric_prompt, rubric_weights, student_period_map,
  subject, teacher_id, trusted_students`.

## Phased split plan (each phase verified by golden net + full suite + free-var check)
**PR-1 — Golden net (own PR, additive).** Design below. Proves current behavior before any move.

**PR-2 — Lift the 5 small nested helpers to module level** (Class B, low risk).
Order: pure first (`extract_content_fingerprints`, `fuzzy_match_score`, `calculate_late_penalty`), then
module-global-capturing (`_update_state`, `find_matching_config`). Bodies byte-identical via the anchor-extract
script + reversibility proof (reuse from the assistant_chat/generate split, PR #688). Removes ~255 LOC from the
orchestrator; internal call sites stay identical (names unchanged).

**PR-3 — Lift + split `grade_single_file`** (the hard PR):
1. Lift to module level: ~29 keyword-only params (byte-identical body) + module import for the 6 fns.
2. **Update `executor.submit` at L1411** to pass captures (kwargs/partial) — the load-bearing change.
3. Split the 626-line body into <300 sub-helpers along natural seams:
   - roster-lookup + config-match (≈L760-900),
   - extraction + marker/template build (≈L900-1240, the ~420-line middle — likely 2 sub-helpers),
   - grade-dispatch + detection + return assembly (≈L1240-1383; dispatch at L1267-1304).

**PR-4 — Decompose the orchestrator** so `_run_grading_thread_inner` <300:
after PR-2/PR-3 it's still ~611 LOC. Extract phases: setup/state-init (L207-282),
config/roster/file-discovery (≈L536-758), per-result assembly inside the executor loop (L1437-1602 →
`_assemble_result(...)`).

## Golden net design (PR-1) — drive the REAL thread, mock only AI + IO
Entry: `run_grading_thread(...)` in `backend/grading/thread.py`. Inspect via
`from backend.grading.state import _get_state; _get_state(teacher_id)["results"]`.

Patch targets (verified — grade fns imported from `assignment_grader` at pipeline.py:562, patch at source):
```python
patch("assignment_grader.grade_with_parallel_detection", side_effect=fake_grade)  # default path
patch("assignment_grader.grade_multipass", side_effect=fake_grade)                # trusted students
patch("assignment_grader.grade_assignment", side_effect=fake_grade)               # FITB / skip_detection
patch("assignment_grader.grade_with_ensemble", side_effect=fake_grade)            # ensemble (>=2 models)
patch("backend.student_history.detect_baseline_deviation", return_value={"flag":"normal","reasons":[],"details":{}})
patch("backend.student_history.add_assignment_to_history")
# parse_filename / read_assignment_file: prefer REAL on tmp fixtures; patch on assignment_grader if format fiddly.
```
4-way dispatch (pipeline.py:1267-1304): `ensemble_models>=2`→ensemble; `is_trusted`→multipass;
`is_fitb`(rubric_type=='fill-in-blank')/skip→grade_assignment; else→parallel_detection.

`fake_grade(**kw)` must return at least: `score, letter_grade, feedback,
breakdown{content_accuracy,completeness,writing_quality,effort_engagement}, student_responses,
unanswered_questions, ai_detection, plagiarism_detection, skills_demonstrated, token_usage`.

Fixtures: tmp dir with N student files (filename satisfying `parse_filename` → first/last/lookup_key), a roster
file matching the filenames, an assignment config. Iterate against real errors — the extraction/marker middle
(L900-1240) runs on real content, so fixture content must flow through it.

Result shape to pin (the `new_result` dict, pipeline.py:1543-1574): student_name/id/email, filename, filepath,
assignment, period, **score** (post-late-penalty), letter_grade, feedback, breakdown, student_responses,
unanswered_questions, ai_detection, plagiarism_detection, baseline_deviation, skills_demonstrated, marker_status,
is_resubmission, previous_score, kept_higher, token_usage, original_score, late_penalty.

Scenarios: default path · trusted→multipass · FITB→grade_assignment · ensemble · late-penalty
(`calculate_late_penalty`) · resubmission kept-higher (L1499-1538) · missing-config skip · `stop_requested`
short-circuit (L1400-1404) · API-error stop (`letter_grade=='ERROR'`, L1307).

## Hazards
- **`executor.submit` wiring (L1411)** — load-bearing; multi-file golden scenario required.
- **`tests/test_sis_alerting.py` pins `(file,line)` tuples in pipeline.py** — line-shift hazard (the SIS_CAPTURES
  incident). Grep + re-pin after every move; verify each capture stays in its window.
- Byte-identity: reuse the assistant-split scripts (anchor-extract → de-indent → prove reversible → ast.parse → free-var check).
- `grading_state`/`grading_lock` are shared mutable globals under the lock — lifted helpers must keep using the same module globals (no shadow).
- Class B → after each behavior-touching PR: 4-lens adversarial workflow + manual merge (no auto-merge).

## Local repro (current state — nothing broken)
```bash
source venv/bin/activate
python - <<'PY'
import ast,os
t=ast.parse(open("backend/grading/pipeline.py").read())
for n in ast.walk(t):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.end_lineno-n.lineno+1>300:
    print(n.end_lineno-n.lineno+1, n.name)   # expect ONLY _run_grading_thread_inner, grade_single_file
PY
pytest tests/test_grading_pipeline.py tests/test_grading_pipeline_helpers.py \
       tests/test_pipeline_safety_rails.py tests/test_grading_factors.py tests/test_sis_alerting.py -q
```

## References
- Campaign plan: `docs/superpowers/plans/2026-06-04-code-quality-7-function-split-campaign.md`.
- Precedent: assistant_chat/generate split (PR #688) — same lift+extract+byte-proof protocol.
- Discipline: `.claude/rules/workflow.md`. Entry: `backend/grading/thread.py`; state: `backend/grading/state.py` `_get_state`.
