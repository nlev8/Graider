# Handoff: 2026-05-25 — Wave 8 (grade_assignment + grade_multipass decomposition) + FERPA fix

## 1. Goal
Continue Wave 8: decompose the two large grader functions in
`backend/services/grading_pipeline.py` into small pure module-level `_helper`s under STRICT
behavior-preservation (golden + prompt-snapshot + AST-byte-identity nets). Overarching mandate:
"sprint, do not stop; as close to 10/10 as possible; you decide and execute; use the 3 AIs
(Claude superpowers + Codex 5.5-high + Gemini, advisory) at genuine design forks."

## 2. TL;DR — shipped this session (all merged to main)
- **FERPA PII fix (#565 + review follow-up #566):** new content-preserving
  `sanitize_grading_prompt_for_ai()` applied at ALL 6 LLM send boundaries (4 leaves +
  pipeline paths + portal + assignment_player route). Preserves naked numbers/dates (answers).
  Common-word-name over-redaction (Grace/May/Mark…) fixed in #566.
- **Principle #13 added to CLAUDE.md (#567):** "Review Gates Before Auto-Merge" — class A
  (behavior-preserving refactor, nets gate, auto-merge OK) vs class B (net-new / compliance /
  security → code review is a HARD pre-gate; no `--auto` with a review in flight).
- **Wave 8 — 7 grade_assignment/grade_multipass slices (#568–#574):**
  | # | helper | fn | LOC |
  |---|--------|-----|-----|
  | 568 | `_detect_blank_submission` | grade_assignment | 711->605 |
  | 569 | `_analyze_submission_writing_style` (3-tuple) | grade_assignment | 605->573 |
  | 570 | `_detect_fitb_assignment` | grade_assignment | 573->559 |
  | 571 | `_pre_extract_responses` (4-tuple, **3-AI consult**) | grade_assignment | 559->450 |
  | 572 | `_load_ell_language` | grade_assignment | 450->438 |
  | 573 | `_finalize_grading_result` (kwargs, **3-AI consult**) | grade_assignment | 438->405 |
  | 574 | `_apply_vocab_leniency` (in-place) | grade_multipass | 432->404 |
  | 575 | `_multipass_perform_extraction` (2-tuple, **3-AI consult**) | grade_multipass | 404->361 |
  - **grade_assignment: 711 -> 405 LOC (-43%).** grade_multipass: 432 -> 361 (-16%).
  - Every slice: AST byte-identical to origin block, golden + prompt-snapshot nets unchanged,
    +unit tests in `tests/test_grading_pipeline_helpers.py` (now ~25 helper tests). Broad
    sweeps green throughout.

## 3. Current state
- main HEAD = #575. GitNexus index fresh. No open PRs.
- No open PRs. Working tree clean except always-uncommitted AGENTS.md/CLAUDE.md + local noise
  (.claude/scheduled_tasks.lock, flask_session/, tests/reports/).

## 4. grade_assignment is at its SAFE FLOOR (405 LOC) — do NOT extract further
Remaining blocks are the irreducible dispatch core, confirmed unsafe by the 3-AI consult:
- **provider dispatch** sets `response_text`, which the `except json.JSONDecodeError` handler
  needs (preview + debug temp-file + regex recovery) — extracting it forces restructuring the
  handler = behavior risk.
- **message-building** has a conditional-`full_prompt` coupling (only set on the text path,
  rebuilt in the image-dispatch path) — subtle undefined-var risk if naively moved.

## 5. Next Wave 8 targets (grade_multipass, 361 LOC) — each a design fork, CONSULT FIRST
DONE: vocab leniency (#574), EXTRACTION block (#575). Remaining:
1. **AGGREGATE SCORES / PASS-3 / result tail** (~150 lines, biggest win -> ~270 LOC): effort calc
   + completeness cap + final_score/letter_grade + breakdown + custom rubric weights, feeding the
   PASS-3 `generate_feedback` call + result assembly. Many interwoven outputs -> CONSULT on the
   split; likely a kwargs `_finalize_multipass_result(...)` mirroring `_finalize_grading_result`.
2. **PASS-2 parallel per-question grading** (~80 lines): ThreadPoolExecutor + the 3 question-index
   matching strategies + sympy pre-check. Complex/coupled to question_results collection.
3. **Filtering-dedup**: the filter-question-text block in grade_multipass (~18 lines) is
   near-identical to one already inside `_pre_extract_responses`. DRY opportunity — but it's a
   cross-cutting change (2 call sites); verify the blocks are truly identical first.
## 5b. CLI/email facade split — ✅ COMPLETE (Code Quality 9.5 reached)
SHIPPED (PRs #577 pt.1, #578 pt.2a, #579 pt.2b): `save_emails_to_folder`+`create_outlook_drafts`→
`grader_export.py`, `log_pii_sanitization`→`grader_text_prep.py`, `ASSIGNMENT_NAME`→`grading_models.py`,
`run_grading`+3 CLI path constants→new `grader_cli.py` (verbatim, T20-exempt, no cycle). **`assignment_grader.py`
658→332 LOC with ZERO top-level functions** — a pure re-export-shim layer + `__main__`. 3-model unanimous
re-score: **Code Quality 9.4→9.5 (first 9.5, #580)**. `run_grading` is the CLI `__main__` + test route-callback
(`conftest_routes`/`test_grading_routes`) — kept importable via shim; `backend/grading/pipeline.py` imports
of save_emails/ASSIGNMENT_NAME preserved via re-exports.

## 5c. Path 9.5 → 10 (unanimous next lever): PROVIDER ADAPTERS
Both Codex + Gemini named the same step. Extract the per-provider execution + response normalization
(the OpenAI/Anthropic/Gemini switch-blocks + structured/text parse + JSON-fallback + error recovery)
out of `grade_assignment` (~406 LOC) and `grade_per_question` into provider-specific grading adapters
behind ONE interface, so those functions become orchestration + policy/post-processing only. This is
the dispatch core the Wave-8 consult deliberately left in place (the response_text→except coupling) —
the adapter interface is the clean way to finally extract it. Then: typed request/result objects instead
of wide dicts; retire the re-export shims (migrate internal callers to `backend.services.*`); live/contract
SDK smoke tests behind markers. Also still open: grade_multipass AGGREGATE/PASS-3 tail + PASS-2 block;
per-branch parse.

## 6. The proven slice protocol (FOLLOW exactly)
1. Locate block by content markers (Python, not fragile line numbers).
2. Move verbatim into a module-level `_helper` (Python line-range edit handles emoji/regex/f-strings
   safely; the Edit tool mangles unicode escapes — use Python for those).
3. Caller: replace block with the helper call (early-return helpers return dict-or-None or a tuple
   with an `early_result` slot; in-place mutators return None like `_apply_single_pass_post_processing`).
4. **Verify (all must pass):** `python -c "import ast; ast.parse(...)"`; `ruff --select F821,F401,F841`;
   AST byte-identity of helper body vs `git show HEAD:...` origin block; then
   `pytest tests/test_grading_pipeline_helpers.py tests/test_grader_golden.py
   tests/test_grader_prompt_snapshots.py`; then a broad `-k` grading sweep.
5. Add unit tests for the now-testable helper.
6. **Sequential discipline (same file):** ONE PR in flight at a time. Prep next slice locally on
   the current branch, commit, record SHA; when the open PR merges, `git checkout -b ... origin/main`
   + `git cherry-pick <SHA>` (squash-merge makes plain rebase messy — cherry-pick onto fresh main).
7. PR -> `gh pr merge N --squash --auto`; branch protection is **strict** (must be up-to-date) so the
   watcher must `gh pr update-branch N` when BEHIND. 9 required checks; Backend Tests is the ~4min pole.

## 7. 3-AI consult mechanics
- Codex: `codex exec -c model_reasoning_effort="high" "$(cat /tmp/prompt.md)" < /dev/null`
  (the `< /dev/null` avoids the stdin hang).
- Gemini (ADVISORY ONLY): `gemini -p "$(cat /tmp/prompt.md)" --skip-trust` — `--skip-trust` runs
  untrusted (NO file tools) = safe. NEVER `--yolo` (it auto-approved edits and clobbered 4 files
  earlier; reverted). Inline the code block in the prompt so Gemini needs no file access.
- Reconcile on the conservative floor (lowest behavior-preservation risk wins).

## 8. Path to 9.5 (Wave 8 goal) — re-score pending
Caps/weights dedup (`_letter_grade`/`_completeness_cap_table`) shipped earlier (#549). After the
grade_multipass forks land, run the 3-model Code Quality re-score (was 9.2 after Wave 7) to measure
9.5. Canonical scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.

## 9. References
- PRs: #565-#574. Spec: `docs/superpowers/specs/2026-05-24-ferpa-pii-sanitization-fix.md`.
- Golden net: `tests/grading_fakes.py` + `tests/test_grader_golden.py`; prompt snapshots:
  `tests/test_grader_prompt_snapshots.py`; helper units: `tests/test_grading_pipeline_helpers.py`.
