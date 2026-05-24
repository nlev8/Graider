# Handoff: 2026-05-24 — Wave 7 (assignment_grader.py decomposition) PHASE B COMPLETE

Per CLAUDE.md §12. Read this, then
`docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (canonical scorecard)
and `docs/superpowers/specs/2026-05-24-wave7-phaseb-grader-golden-net.md` (Phase B design).

## 1. Goal

Decompose `assignment_grader.py` (the 5,344-LOC grading engine) into Flask-free
`backend/services/` modules — behavior-preserving under a heightened golden/characterization
net — to push **Code Quality 9 → 9.5+**. Overarching mandate: "this is a sprint, do not suggest
stopping; as close to 10/10 as possible. You decide and execute; use the 3 AIs at design forks."

## 2. TL;DR — Wave 7 COMPLETE (the grading core is fully decomposed)

- **`assignment_grader.py`: 5,344 → 658 LOC (−88%).** It is now a thin **facade**: CLI/email
  orchestration (`run_grading`, `save_emails_to_folder`, `create_outlook_drafts`,
  `log_pii_sanitization`) + re-export shims. NO LLM scoring code remains inline.
- **The entire LLM-coupled grading core now lives in `backend/services/`:**
  - `grading_models.py` — 9 Pydantic response schemas + `TokenTracker` + `MODEL_PRICING` (#543)
  - `grading_leaves.py` — `grade_per_question`, `detect_ai_plagiarism`, `generate_feedback`,
    `_translate_feedback` (#544)
  - `grading_pipeline.py` — `grade_multipass`, `grade_assignment`, `grade_with_ensemble`,
    `grade_with_parallel_detection` + `GRADING_RUBRIC` + `ASSIGNMENT_INSTRUCTIONS` (#545/#546/#547)
  - Earlier Wave-7 services: `writing_style`, `writing_profile`, `grader_text_prep`,
    `grading_prep`, `grader_json`, `submission_parsing`, `grader_export`, `grader_roster`.
- **THE GOLDEN NET (#541) is the keystone — `tests/grading_fakes.py` + `tests/test_grader_golden.py`.**
  It patches the 3 RAW SDK entrypoints (`openai.OpenAI`, `anthropic.Anthropic`,
  `google.generativeai.GenerativeModel`+`configure`) with provider-shaped, thread-safe,
  content-matched fakes; sets env API keys; keeps `with_retry` real. 12 goldens pin the EXACT
  scoring output (grade_multipass 88/B, grade_assignment 85/B, parallel detection, blank
  short-circuit, `.parsed`-None contrast, provider routing, token usage). It runs the REAL
  functions, so any behavior change during extraction flips a pin. **This is what made the
  whole Phase B safe.** Gemini goldens skip in this venv (it ships `google-genai`, not
  `google.generativeai` — the grader's gemini branch ImportErrors gracefully).
- **Wave 7 PRs (all merged): #520–#539** (pure helpers + file-reader cluster + roster/CSV export),
  **#540** (writing_profile), **#541** (golden net), **#542** (build_roster_from_periods),
  **#543** (grading_models), **#544** (grading_leaves), **#545** (grade_assignment),
  **#546** (grade_multipass), **#547** (entry points — Phase B complete).

## 3. The proven slice protocol (FOLLOW for any further grader work)

1. **Golden-char-test first**, baseline green BEFORE extraction (import via `assignment_grader`
   so the shim keeps it valid). For the LLM core, the SDK-fake golden net (#541) IS the net —
   leaf/orchestrator extractions need NO new test, just keep it green.
2. **Verbatim move** into `backend/services/<mod>.py`; `print()`→`_logger.info(`/`.warning(`
   (services/ is ruff-T20 scanned). The conversion is mechanical & exact — verify
   `AST print-call count == raw "print(" substring count` so a regex is safe.
3. **Re-export shim** in `assignment_grader.py`: `from backend.services.<mod> import <fn> as <fn>
   # noqa: F401`. ALWAYS the explicit `as` form (mypy no_implicit_reexport; pipeline.py is strict).
4. **Verify (scripted):** (a) AST function-source byte-identical vs `origin/main` modulo
   print→logger (+ any behavior-neutral dead-var removal); (b) `ruff check --select F821` → 0
   undefined names (catches missing imports up front, BEFORE test failures — this is gold for big
   moves); (c) `ruff check --select F401,F841`; (d) `ruff check`; (e) `bandit -q -ll`; (f) shim
   identity `g.<fn> is <imported fn>`; (g) no import cycle (`grep -c assignment_grader <service>`).
5. **Broad sweep:** `pytest tests/ -k "grad or grader or pipeline or writing or detection or
   feedback or multipass or portal_grading or factor or ensemble or roster or token or model or
   translate or transient or issue224 or rubric or text_prep or submission or json"
   --ignore=tests/load --ignore=tests/e2e`.
6. Commit explicit files (NEVER AGENTS.md/CLAUDE.md), PR, `gh pr merge N --squash --auto
   --delete-branch`, robust background watcher. STRICTLY SEQUENTIAL on `assignment_grader.py`.

## 4. HARD-WON LESSONS (Phase B)

- **Patch targets follow the function.** When a function moves to a service, tests that patch its
  INTERNAL seams break. Two failure modes seen:
  (a) **AttributeError** — `patch("assignment_grader._get_api_key")` after `_get_api_key` was
  pruned → repoint to where the function now resolves it (`grading_leaves`/`grading_pipeline`).
  (b) **SILENT VACUOUS PASS** — `patch("assignment_grader.grade_per_question")` when grade_multipass
  moved to grading_pipeline: the patch no longer intercepts, `mock_gpq` is never called, and
  loop-based assertions skip → test goes green while testing NOTHING. ALWAYS verify the mock was
  actually called (e.g. `len(mock.call_args_list) > 0`) after repointing. Fixed in
  test_transient_errors_issue224 (#544) and test_grading_pipeline (#545/#546).
- **Re-export detection MUST be AST-based, not single-line grep.** Tests import via multi-line
  `from assignment_grader import (\n  X,\n  Y,\n)` blocks that a `grep "import.*X"` misses. Use an
  `ast.ImportFrom` walk over tests/ + backend/ before pruning ANY "orphaned" import. Symbols found
  this way (MATH_SUBJECTS, sanitize_pii_for_ai, preprocess_for_ai_detection, build_section_rubric,
  _try_parse_json_fallback, compare_writing_styles, analyze_writing_style, _distribute_points,
  _is_math_subject, _parse_expected_answers) stay as explicit `as` re-exports.
- **`ruff --select F821`** statically catches undefined names after a move (missing imports, moved
  constants like GRADING_RUBRIC / ASSIGNMENT_INSTRUCTIONS) — run it instead of discovering them
  via runtime NameError in the golden net.
- **Ordering by call-dependency, not the consensus's tentative number.** grade_multipass CALLS
  grade_assignment (single-pass fallback), so grade_assignment had to be extracted FIRST and both
  live in the SAME module (grading_pipeline.py) → the call is intra-module, no back-import.
- **`backend/api_keys.get_api_key` env fallback** (`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/
  `GEMINI_API_KEY`) is the test seam — ThreadPoolExecutor workers see env, NOT contextvars, so the
  golden net sets env keys rather than patching `_get_api_key` (which moves on extraction).

## 5. State & what's next

- Wave 7 is DONE. `assignment_grader.py` (658 LOC) remaining functions are NON-LLM CLI/email:
  `run_grading` (the grading-thread entry, calls the now-service grading fns via shims),
  `save_emails_to_folder`, `create_outlook_drafts`, `log_pii_sanitization` (has a print; tiny stub).
  These are a possible FUTURE wave (CLI/email layer → `backend/services/grader_email.py` +
  `grader_runner.py`) but are NOT LLM scoring core and were out of Phase B scope.
- **CLOSEOUT DONE:** 3-model re-score reconciled **Code Quality 9.0 → 9.2** (Codex 9.2, Gemini 9.2,
  Claude 9.5 → conservative floor; both external models converged on 9.2 and on the same next lever).
  Appended to the scorecard spec. Reviewers' verdict: god-*module* eliminated, but `grade_assignment`
  (~1,138 LOC) is now a second-order god-*function*. **Path to 9.5 = split `grade_assignment` into
  named pipeline phases + extract the CLI/email layer out of the 658-LOC facade.** This is the clear
  next wave (Wave 8 candidate). gitnexus re-indexed at closeout. Lint hygiene the reviewers flagged
  is fixed (grading_leaves `TokenTracker` F821 ×4 + `focus_files` F841).
- **Pre-existing flaky e2e:** `tests/test_e2e_multi_teacher.py::...test_three_teachers_publish_and_grade`
  fails only under the big combined `-k` run (test-pollution); passes standalone + alongside the
  touched tests. NOT a Phase-B regression. A test-isolation cleanup candidate (unrelated).
- **Deferred (handoff §6 carryover):** `writing_style.py` 4 carried-over dead locals in
  analyze_writing_style (pre-existing; remove in a non-identity commit with golden confirmation).

## 5b. Wave 8 (grade_assignment internal decomposition → path to 9.5) — STARTED

The unanimous 3-model next lever. `grade_assignment` (~1,138 LOC in `grading_pipeline.py`) is a
second-order god-function mixing provider setup, extraction, prompt assembly, parse, scoring
caps, rubric weighting, ELL translation, writing-profile updates, audit, error recovery.

- **Slice 1 SHIPPED (#549):** extracted shared pure helpers `_letter_grade(score)` +
  `_completeness_cap_table(grading_style)` (+ `_COMPLETENESS_CAPS`) into `grading_pipeline.py`,
  deduping 9 inline sites across grade_assignment/grade_multipass/grade_with_ensemble.
  Boundary unit test `tests/test_grading_pipeline_helpers.py` + golden net + test_grading_factors.
- **Phase boundaries inside grade_assignment** (line refs pre-Slice-1, approximate): provider/
  client init (~159), blank short-circuit (~215), context build — custom instr/history/
  accommodation/FITB (~328–365), pre-extract responses + writing-style (~374–490), **prompt
  assembly (~534–769)**, LLM call + provider-branch parse (~772–1120), rubric-weights post-proc
  (~1122), completeness-caps post-proc (~1143), result/audit/token build (end). Suggested phase
  helpers (keep in grading_pipeline.py, called by grade_assignment as orchestration):
  `_resolve_grading_client`, `_build_grading_prompt`, `_parse_grading_response`,
  `_apply_single_pass_post_processing`.
- ⚠️ **CRITICAL SAFETY INSIGHT — the golden net does NOT pin prompt TEXT.** The SDK fakes route
  on `response_format` type + coarse content markers and return a canned result REGARDLESS of the
  exact prompt wording. So extracting `_build_grading_prompt` (or the per-question/feedback prompt
  builders) is NOT protected by the golden net against subtle prompt drift. **BEFORE any
  prompt-assembly extraction, add a prompt-SNAPSHOT test:** extend `tests/grading_fakes.py`'s
  CallBook to capture the full prompt text per call, then pin grade_assignment's (and
  grade_multipass per-question + generate_feedback) prompt for a fixture (hash + key substrings),
  baseline green, extract, re-assert unchanged. Without this, a prompt regression ships silently.
- The provider/parse/post-processing phase extractions ARE covered by the golden net (they affect
  the result dict). Order suggestion: post-processing first (lowest risk, result-pinned), then
  provider-resolution, then prompt-assembly LAST (after the snapshot net exists).

## 6. Standing constraints
- venv `/Users/alexc/Downloads/Graider/venv/`. CI = 9 checks; ruff selects ONLY T20 (root
  assignment_grader.py is print-allowed; services/ is not). Commit trailer
  `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`; PR trailer
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Active frontend
  `frontend/src/App.jsx`. Never commit AGENTS.md/CLAUDE.md (`git add` explicit files).
- Watcher pattern (run_in_background bash): poll `gh pr view N`, `gh pr update-branch` on BEHIND,
  exit MERGED/CHECK_FAILED. Each grader slice strictly sequential on assignment_grader.py.

## 7. References
- Scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
- Phase B design: `docs/superpowers/specs/2026-05-24-wave7-phaseb-grader-golden-net.md`.
- Golden net: `tests/grading_fakes.py`, `tests/test_grader_golden.py`.
- Wave 7 PRs #520–#547 (all merged).
