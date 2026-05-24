# Handoff: 2026-05-24 — Wave 7 (assignment_grader.py decomposition) IN PROGRESS

Per CLAUDE.md §12, at a deep-session/compaction boundary. Read this, then
`docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (canonical
scorecard; the Wave 6 closeout re-score is the last dated section).

## 1. Goal

Decompose `assignment_grader.py` (the 5,344-LOC grading engine) into Flask-free
`backend/services/` modules — behavior-preserving under a heightened golden/characterization
net — to push **Code Quality 9 → 9.5+**. This is the lever the unanimous Post-Wave-6
re-score named as the path beyond 9. **The user explicitly OPENED THE GRADER GATE this
session** (it was previously off-limits) after I recommended it with a heightened safety
protocol. Overarching mandate: "this is a sprint, do not suggest stopping; as close to
10/10 as possible. You decide and execute; use the 3 AIs at design forks."

## 2. TL;DR

- **Wave 6 COMPLETE & SHIPPED.** `planner_routes.py` 4,611 → 2,154 LOC (−53%), all 5
  generation handlers + the standards/content/export/study-aid/assessment helpers into
  Flask-free `backend/services/planner_*`. **Code Quality 8.5 → 9.0, unanimous 3-model
  (Claude/Codex/Gemini) — the first 9 in the program** (re-score #519). gitnexus re-indexed.
- **Wave 7 IN PROGRESS — clean pure-extraction phase COMPLETE (7 slices shipped #520-#526).**
  New Flask-free service modules carved from the grading engine: `writing_style` (analyze/compare,
  #520), `grader_text_prep` (sanitize_pii_for_ai + preprocess_for_ai_detection; log_pii_sanitization
  stayed — has a print, #521), `grading_prep` (_parse_expected_answers + _distribute_points +
  _is_math_subject + MATH_SUBJECTS + build_section_rubric; swept dead `import hashlib`, #522/#523),
  `grader_json` (_try_parse_json_fallback, #524), `submission_parsing` (parse_filename, #525),
  `grader_export` (generate_email_content, #526), #527 golden-net hardening + dead-code cleanup.
- **Wave 7 file-reader cluster STARTED via the print→logger pattern (VALIDATED by review #528):**
  `read_image_file` (#528) + `read_docx_file` (#529, in CI) → `submission_parsing`. These are NOT
  byte-identical — the grader (a former CLI tool) is print-heavy and `backend/services/` is ruff-T20
  scanned, so diagnostic `print()` calls become `_logger.*` (RETURN VALUES unchanged + golden-tested;
  the #528 reviewer confirmed nothing depends on the stdout). Each slice: golden return-value char tests
  baselined first (generate a real .docx via python-docx; write image bytes to a tmp .png), verify the
  ONLY diff vs origin/main is the print→logger lines (+ any dead-import sweep), explicit `as` shim,
  bandit+ruff+mypy clean, full grading sweep green.
  **REMAINING (the complex part — careful, fresh context advised):**
  (1) the 3 big Graider parsers — `read_docx_file_structured` (~153 LOC), `extract_from_tables` (~149),
  `extract_from_graider_text` (~164) → `submission_parsing`. Each is intricate Graider-table/marker
  parsing with MANY prints; needs golden tests on REAL Graider-formatted inputs (understand the
  GRAIDER_* marker + table format first — see how the planner GENERATES them + how these PARSE them).
  (2) `read_assignment_file` (the dispatcher; imported by grading/pipeline.py → STRICT, needs explicit
  `as` shim) — move LAST, after its callees. (3) roster (load_roster, build_roster_from_periods) +
  CSV/report file-write (export_focus_csv, save_to_master_csv, export_detailed_report) → `grader_export`
  (also print-heavy → logger). (4) **Phase B: LLM-coupled scoring core** (grade_per_question,
  generate_feedback, grade_multipass, grade_assignment, detect_ai_plagiarism, grade_with_ensemble,
  _translate_feedback) — build the full 3-SDK-stub (openai/anthropic/genai, raw clients — NOT
  llm_adapter) golden net FIRST. assignment_grader.py now ~4,300 LOC (from 5,344).
- **3 LINTER LESSONS (backend/services/ is ruff-T20 + Bandit + Mypy-Strict scanned; root grader was NOT) —
  PRE-CHECK locally per slice** with `bandit -q <file>`, `ruff check <file>`, `ruff check --select F401,F841 <file>`,
  AND the CI mypy command if a `backend/grading/` module imports the symbol:
  (a) ruff **T20**/flake8-print → don't move functions with `print()` into services (kept log_pii_sanitization
  in the grader); (b) **Bandit** → `hashlib.md5` needs `usedforsecurity=False` (B324; identical digest) — #521;
  (c) **Mypy Strict `no_implicit_reexport`** → if a `backend/grading/` strict module imports the symbol from
  assignment_grader (pipeline.py imports `load_roster, parse_filename, read_assignment_file`), the re-export
  shim MUST be the explicit `from backend.services.X import fn as fn  # noqa: F401` form — #525 fixed
  parse_filename; **load_roster + read_assignment_file slices will need it too.** RULE: always use the
  explicit `as` form for grader shims. CI mypy cmd: `mypy backend/utils/auth_decorators.py
  backend/utils/redaction.py backend/utils/errors.py backend/utils/ttl_cache.py backend/utils/logging_utils.py
  backend/observability/events.py backend/supabase_client.py backend/supabase_resilient.py backend/retry.py
  backend/grading/`.

## 3. The heightened grader protocol (FOLLOW THIS — it's a live scoring engine)

A grading bug silently mis-grades real student work, so the route-slice protocol isn't
enough. Per slice:
1. **Char-test-first with GOLDEN outputs.** Capture the function's EXACT output on fixed
   inputs (run it, hardcode the result), pin via `assert == golden`. Baseline green BEFORE
   extraction. Import the function via `assignment_grader` (so the test stays valid through
   the re-export shim).
2. **Full grading-suite green before AND after.** Broad sweep:
   `pytest tests/ -k "grad or grader or pipeline or writing or detection or feedback or
   multipass or portal_grading or factor or ensemble" --ignore=tests/load --ignore=tests/e2e`
   (~770 tests, ~2 min). Must stay green.
3. **Re-export shim** (same pattern as Waves 5/6): move the function verbatim into
   `backend/services/<name>.py`, replace the def in the grader with
   `from backend.services.<name> import <fn>`. Internal AND external callers keep working.
4. **Verify:** AST function-source byte-identical vs origin/main; ruff (+ manual
   `--select F401,F841`); no import cycle (the service must not import assignment_grader);
   shim identity (`g.<fn> is <imported fn>`).
5. Two-stage review (spec first-hand + superpowers:code-reviewer), squash-auto-merge, watcher.

⚠️ **The grader does NOT use `backend.services.llm_adapter`** — it calls the raw
`openai`/`anthropic`/`genai` SDKs inline (`OpenAI(...).beta.chat.completions.parse()`,
`.chat.completions.create()`, anthropic `.messages.create()`, gemini `.generate_content()`).
So a FULL-pipeline golden net (for the LLM-coupled scoring core, Phase B) needs stubbing 3
SDKs with exact response shapes (the existing suite avoided this). **Phase A = pure helpers
only** (no scores affected → per-function golden tests suffice). Build the full SDK-stub
golden net before touching `grade_per_question`/`generate_feedback`/`grade_multipass`/
`grade_assignment`/`detect_ai_plagiarism`.
⚠️ The single LLM key seam: `from backend.api_keys import get_api_key as _get_api_key`
(grader line ~428) — all providers build clients with it.

## 4. Concrete next step (fresh session)

`/tmp/apply_*.py` scripts from earlier slices are GONE (don't survive a fresh session) and not
needed — all those slices shipped. The remaining work is described procedurally below (§5) and
in §2. Start: `git checkout main && git pull`, re-read §2 + §3 (protocol) + §6 (linter lessons),
then take the next complex Graider parser (`read_docx_file_structured`) — build its golden char
test on a REAL Graider-generated .docx first (understand the GRAIDER_* marker/table format), then
extract with the print→logger pattern (§2). The GitNexus index is fresh (re-indexed post-#529).

## 5. Remaining Wave 7 (ranked)

Pure helpers + the 2 simple file-readers are DONE (slices 1-9, #520-#529). Remaining:
- **The 3 complex Graider parsers → `submission_parsing`** (the hard part — print-heavy + intricate):
  `read_docx_file_structured`, `extract_from_tables`,
  `extract_from_graider_text`, then `read_assignment_file` (dispatcher; LAST). Needs real fixture
  files — generate a .docx via python-docx (like the Wave 6 extract_text slice); mock pdfplumber
  for pdf or rely on byte-identical for that branch; image→base64. Do with FRESH context (meaty).
- roster (`load_roster`, `build_roster_from_periods`) + writing-profile
  persistence (`update_writing_profile`/`get_writing_profile` — file I/O to ~/.graider_data,
  char-test with tmp dirs) + CSV/email export (`export_focus_csv`, `save_to_master_csv`,
  `export_detailed_report`, `generate_email_content`) → a `grader_export` service.
- **Phase B (LAST, max care):** the LLM-coupled scoring core (`grade_per_question`,
  `generate_feedback`, `grade_multipass`, `grade_assignment`, `detect_ai_plagiarism`,
  `grade_with_ensemble`, `_translate_feedback`) — needs the full SDK-stub golden net first.

After Wave 7 (or a meaningful chunk): 3-model re-score (CQ 9 → 9.5?), gitnexus re-index.

## 6. Cleanup owed (deferred, recorded by the slice-1 reviewer)
- `backend/services/writing_style.py`: 4 carried-over dead locals in `analyze_writing_style`
  (`potential_misspellings`, `common_misspelled`, `proper_caps`, `all_caps`) — pre-existing,
  kept byte-identical in slice 1; remove in a SEPARATE non-identity commit (golden tests
  confirm output unchanged). Plus 2-3 uncovered `compare_writing_styles` branches
  (minor/likely) + an un-capped-complexity analyze golden — add to harden the net.
- Wave 6 route-side dead vars (`global_ai_notes` @ planner_routes ~492, ~40 `except ... as e`)
  — CI-invisible (ruff=T20). One final cleanup PR.

## 7. Standing constraints
- venv `/Users/alexc/Downloads/Graider/venv/`. CI ignores tests/load + tests/e2e. Commit
  trailer `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`; PR trailer
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Active frontend
  `frontend/src/App.jsx` (never graider_app.py). Branch protection = 9 checks. Never commit
  AGENTS.md/CLAUDE.md (GitNexus index noise) — `git add` explicit files.
- Robust watcher pattern (run_in_background bash): poll `gh pr view N`, `gh pr update-branch`
  on BEHIND, exit on MERGED/CHECK_FAILED; squash-auto-merge `gh pr merge N --squash --auto
  --delete-branch`. Each grader slice is strictly sequential on the same file (~10 min CI).
- AST-aware dedent (Wave 6 lesson): when moving a body that contains multi-line strings,
  skip string-interior lines during dedent (venv is Python 3.14 → f-strings tokenize as
  FSTRING_* not STRING; use AST node spans, not tokenize). Grader pure helpers are
  module-level (0-indent) so verbatim move, no dedent needed.

## 8. References
- Scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`
  (Wave 6 closeout re-score = last section).
- Wave 6 PRs #502–#519 (all merged). Wave 7 PRs #520–#529 (all merged): #520 writing_style,
  #521 grader_text_prep, #522/#523 grading_prep, #524 grader_json, #525 submission_parsing
  (parse_filename), #526 grader_export, #527 hardening, #528 read_image_file, #529 read_docx_file.
  Spec/plan for Wave 6: #501.
- No Wave 7 spec/plan doc yet (proven pattern from Waves 5/6; brainstorm was skipped per
  the user's "you decide and execute" + the established cadence). Consider a brief Wave 7
  spec if a fresh agent wants the anchor.
