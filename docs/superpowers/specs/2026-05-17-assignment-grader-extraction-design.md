# assignment_grader.py Parsing/Extraction Service Extraction: Design

**Date:** 2026-05-17
**Status:** Design approved (user approved 2026-05-17). Next: writing-plans.
**Context:** Tier 2 (Code Quality / Architecture decomposition) of the dimension roadmap, Slice 2. Slice 1 (planner_routes.py service extraction, PRs #406 to #410) shipped and closed; its methodology is the proven precedent. The user selected `assignment_grader.py` parsing/extraction as Slice 2, scope A (parsing/extraction only), characterization net breadth B (exhaustive).

## 1. Goal

Move the pure text-parsing/extraction cluster out of `assignment_grader.py` (7,444 LOC) into a focused, network-free, dependency-closed `backend/services/response_extraction.py` so each unit has one responsibility and is unit-testable with no network, no AI client, and no file I/O. This raises Code Quality and Architecture with zero behavior change, behind an exhaustive characterization net.

## 2. Problem

`assignment_grader.py` is the largest backend file: 58 top-level defs/classes in 7,444 lines, mixing pure text parsing, writing-style analysis, PII handling, file readers, AI-calling grading orchestration, and output/export. The single largest component is the text-parsing/extraction cluster (`extract_student_responses` alone is roughly 868 lines). That cluster is pure and deterministic but lives inside a file dominated by network-coupled grading code, so it cannot be reasoned about or unit-tested in isolation. `backend/services/` already holds seven modules carved from this area (`assignment_post_processing.py`, `grading_service.py`, `stem_grading.py`, `portal_grading.py`, `worksheet_generator.py`, `assistant_tools_grading.py`, `oneroster_gradebook.py`); imports are one-directional. That established pattern is the precedent and must not be redone. This slice carves the next, largest, purest cluster.

The cluster's purity and call-graph were verified before this design:

- `assignment_grader.py` has no `flask` import; the relevant coupling in this file is network/AI plus file I/O, not Flask.
- `extract_student_responses` (915 to 1782) calls only seven pure cluster helpers (`_strip_template_lines`, `extract_fitb_by_template_comparison`, `filter_questions_from_response`, `fuzzy_find_marker`, `parse_numbered_questions`, `parse_vocab_terms`, `strip_emojis`). It calls no network, AI, `backend.*`, or Flask code. The only `http` occurrences are `startswith('http')` string guards, not network calls.
- The cluster's pure call-graph closes within itself, so a dependency-closed module is possible with no import cycle.
- Caller blast radius is small: only `extract_student_responses` (2 external import sites), `extract_from_tables` (1), and `extract_from_graider_text` (1) are imported elsewhere from `assignment_grader`. The leaf helpers are internal-only.

## 3. The coupling-reduction rule (adapted from Slice 1 §3)

This is the defining constraint, retargeted from Slice 1's Flask focus to this file's real coupling.

- A function is "extracted" only if its new unit test runs with **no network, no AI client, and no file I/O**. The test imports the service module and calls the function directly. The cluster is already verified pure, so this is expected to hold for every function in scope.
- If a function turns out to be network or I/O coupled on closer inspection, that is not a reason to move it blindly. It stays in `assignment_grader.py` and is recorded as out-of-scope with the reason. Do not force a bad extraction.
- Moves are **verbatim byte-identical**: no logic edits, no renames, no reordering. The new test is the evidence the cluster was actually isolated; LOC reduction in `assignment_grader.py` is a side effect, not the objective.
- Zero behavior change. The nine existing grading-pipeline test files stay green unchanged. Each moved function gets new tests that exercise it directly with no network or I/O.
- Any genuine bug the characterization net surfaces (the Slice 1 `unit_circle` situation) ships as a **separate immediate follow-up PR**, never folded into the verbatim-move PR. This discipline worked in Slice 1 and is carried forward.

## 4. Target module (exact functions, by current line)

`backend/services/response_extraction.py`. Pure functions; imports only stdlib and, if genuinely needed, sibling service modules; never imports from `assignment_grader` (one-directional shim only; an import cycle is a failure).

**Leaf helpers (PR 1, lowest risk, proves the harness):**
`is_question_or_prompt` (179), `filter_questions_from_response` (360), `_strip_template_lines` (430), `strip_emojis` (530), `fuzzy_find_marker` (550), `extract_fitb_by_template_comparison` (628), `parse_numbered_questions` (728), `parse_vocab_terms` (829).

**Large (PR 2, biggest LOC and Code-Quality win):**
`extract_student_responses` (915, roughly 866 LOC), `extract_student_responses_legacy` (1783), `format_extracted_for_grading` (2076), `extract_student_work` (3656), plus the module-level constant `STUDENT_WORK_MARKERS` (2434 to 2492) which `extract_student_work` reads and which an external consumer (`backend/grading/pipeline.py:564`) imports.

**Stays per §3 (discovered during planning, recorded here):** `extract_from_tables` (3242) and `extract_from_graider_text` (3391). `extract_from_tables` calls `read_docx_file_structured`, a file-reading I/O function that is explicitly out of scope and stays; moving `extract_from_tables` would require importing a staying I/O function back into the service, creating an import cycle. `extract_from_graider_text` calls `extract_from_tables`, so it is transitively bound and also stays. Twelve functions move; these two stay with this reason, exactly as the §3 escape hatch intends (the Slice 1 analogue was `_save_grading_config_for_export`).

A thin `# noqa: F401` shim in `assignment_grader.py` re-exports every moved name plus `STUDENT_WORK_MARKERS` so all callers keep resolving with no call-site changes. Only a few external import sites exist, but all moved names are re-exported (the Slice 1 pattern) so no path can break.

## 5. Sequencing and PR structure

Three sequenced PRs, in order 1 then 2 then 3, mirroring Slice 1's standards then export then prompts shape (small and pure first to prove the methodology and the no-network test harness, then the larger entangled move under the net).

- **PR 1:** move the 8 leaf helpers; add the shim re-export; add focused unit plus characterization tests for each leaf; keep all existing tests green; full regression plus the 9 required CI checks.
- **PR 2:** build the exhaustive characterization net for the 4 large functions and pin it against pre-move code first, then move the 4 functions plus `STUDENT_WORK_MARKERS` verbatim under that net; extend the shim; full regression plus 9 CI checks.
- **PR 3:** verify shim and caller integrity; slice closeout (dated note in the assessment doc, plan STATUS CLOSED, any functions left behind per §3 recorded with reason).

Each PR runs through subagent-driven-development with continuous execution and two-stage review (spec-compliance first, then code-quality), the same as Slice 1.

## 6. Characterization strategy (exhaustive, user choice B)

Before PR 2's move, pin the real observed output of each large function across the cross-product of:

- **extraction_mode:** structured, legacy.
- **document shape:** docx-table-derived text, graider-marked text, plain numbered, vocab-term, FITB, summary/written.
- **subject and grade spread:** math, ELA, science, social studies; elementary through high school.

Assertions pin the exact returned dict/tuple structure and values. The output is deterministic (no AI in the cluster), so equality is exact. The net is built and proven against pre-move code, then required byte-identical after the verbatim move. Leaf helpers each get focused unit plus characterization tests in PR 1. This is the deliberate latent-bug net; the equivalent net in Slice 1 caught a real cross-subject production bug.

## 7. Approaches considered

- **Dependency-closed single module, sequenced small to big PRs (chosen).** Genuine isolation of a cohesive call-graph, reviewable PRs, risk front-loaded out, exact mirror of the proven Slice 1 shape.
- **One big-bang PR with the whole cluster plus net.** Rejected: roughly 2.5k LOC including an 868-line function in one reviewable PR is the anti-pattern Slice 1's design rejected; too much regression surface at once.
- **Split into multiple sub-modules** (`marker_matching.py` / `question_parsing.py` / `response_extraction.py`). Rejected for now: the call-graph is tightly cohesive (the large function depends on seven leaves), so splitting risks an inter-module import web for marginal single-responsibility gain. A finer split can be a later slice if warranted.

## 8. Scope

**In:** the one `response_extraction.py` module; the 12 movable functions (8 leaves plus `extract_student_responses`, `extract_student_responses_legacy`, `format_extracted_for_grading`, `extract_student_work`) moved verbatim, plus the `STUDENT_WORK_MARKERS` constant; the thin shim; per-function no-network/no-I/O unit tests; the exhaustive characterization net for the 4 large functions before their move.

**Out (explicitly):** `extract_from_tables` and `extract_from_graider_text` (stay per §3, recorded above: I/O-coupled via `read_docx_file_structured`, moving them would create an import cycle); the writing-style cluster (`analyze_writing_style`, `compare_writing_styles`, `update_writing_profile`, `get_writing_profile`); the PII cluster (`sanitize_pii_for_ai`, `log_pii_sanitization`, `preprocess_for_ai_detection`); the pure grading helpers (`_parse_expected_answers`, `_distribute_points`, `_is_math_subject`, `build_section_rubric`, `_try_parse_json_fallback`); all AI-calling orchestration (`grade_with_ensemble`, `grade_with_parallel_detection`, `grade_per_question`, `generate_feedback`, `grade_multipass`, `grade_assignment`, `detect_ai_plagiarism`, `_translate_feedback`); the file-reading I/O functions (`read_docx_file`, `read_docx_file_structured`, `read_image_file`, `read_assignment_file`, `load_roster`, `build_roster_from_periods`, `parse_filename`); the output/email/export functions; any behavior change; redoing the already-extracted service modules. These are candidates for later slices.

## 9. Risks and handling

- **`extract_student_responses` entanglement (868 LOC, many branches).** The exhaustive net is pinned against pre-move code before the move; the nine existing grading-pipeline test files stay as the behavior guard.
- **Hidden non-purity in a helper.** Handled by the §3 rule: the unit test must run with no network or I/O; if a function violates that, it stays and is recorded with the reason.
- **Import cycle** (`assignment_grader` to new module to a sibling and back). The new module imports only stdlib or siblings, never `assignment_grader`. The shim is one-directional. Verified at each PR.
- **Caller drift.** Only four external import sites; the shim re-exports all moved names; each PR runs full regression plus the 9 CI checks.

## 10. Success criteria

`assignment_grader.py` is materially smaller for the moved cluster. One single-responsibility `backend/services/response_extraction.py` exists with tests that run with no network and no I/O. The exhaustive characterization net is green both before and after the move (byte-identical output). Full local regression and all 9 required CI checks are green on every PR. No behavior change is observable in the nine existing grading-pipeline test files. The reconciled effect is recorded in the assessment doc after PR 3 (a Code Quality / Architecture nudge; no multi-model re-score, since the change is mechanically test-guarded like Slice 1 and Data Integrity Tier 1).
