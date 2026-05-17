# assignment_grader.py Parsing/Extraction Service Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the pure text-parsing/extraction cluster (12 functions plus the `STUDENT_WORK_MARKERS` constant) out of `assignment_grader.py` into a new dependency-closed `backend/services/response_extraction.py`, with zero behavior change, behind an exhaustive characterization net.

**Architecture:** Verbatim byte-identical function moves into one network-free, I/O-free service module, mirroring the proven Slice 1 (`planner_routes.py`) pattern and the seven existing `backend/services/` modules carved from this area. A thin `# noqa: F401` re-export shim in `assignment_grader.py` keeps every caller resolving unchanged. Three sequenced PRs: leaf helpers first (proves the harness), then the large functions under an exhaustive characterization net pinned before the move, then shim/caller verification and slice closeout.

**Tech Stack:** Python 3.14, pytest (no network, no AI client, no file I/O in the new unit tests), ruff. venv at `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`).

**Spec:** `docs/superpowers/specs/2026-05-17-assignment-grader-extraction-design.md`. The §3 coupling-reduction rule governs every task: a function is extracted only if its new unit test runs with no network, no AI client, and no file I/O; if infeasible it stays and is recorded with the reason.

**Refactor-plan note:** moves are verbatim. Steps specify the exact source line ranges and destination plus the shim import and the full new test code. Moved bodies are NOT re-pasted (re-pasting unchanged code is error-prone); they are identified by exact location and verified byte-identical with `diff`.

**Environment note:** the repo's `tests/conftest.py` session fixture (merged in PR #412) redirects any `~/Downloads/Graider` write to a temp dir for the whole suite, so no test run can pollute a developer's Downloads. The extraction functions are pure and write nothing anyway. No `tests/load` runs are required by this plan; do not run them.

---

## File Structure

- **Create:** `backend/services/response_extraction.py`; the only new production file. Single responsibility: pure student-response text parsing and extraction. Imports stdlib only (`re`, `difflib`, `string`, etc. as the moved bodies require). Never imports from `assignment_grader` (one-directional shim only; an import cycle is a failure).
- **Modify:** `assignment_grader.py`; delete the 12 moved function definitions and the `STUDENT_WORK_MARKERS` constant; add one `# noqa: F401` shim import block re-exporting all moved names plus `STUDENT_WORK_MARKERS`.
- **Create:** `tests/test_response_extraction.py`; PR1: per-leaf no-network/no-I/O unit + characterization tests.
- **Create:** `tests/test_response_extraction_characterization.py`; PR2: the exhaustive net for the 4 large functions, pinned against pre-move code, required byte-identical after the move.

Functions that **stay** in `assignment_grader.py` per §3 (recorded, not moved): `extract_from_tables` (3242-3388, calls staying I/O `read_docx_file_structured`), `extract_from_graider_text` (3391-3552, calls `extract_from_tables`). PR3 records this.

---

## PR 1: leaf helpers → `backend/services/response_extraction.py`

Eight leaf functions, current line ranges in `assignment_grader.py`:
`is_question_or_prompt` (179-357), `filter_questions_from_response` (360-427), `_strip_template_lines` (430-527), `strip_emojis` (530-547), `fuzzy_find_marker` (550-625), `extract_fitb_by_template_comparison` (628-725), `parse_numbered_questions` (728-826), `parse_vocab_terms` (829-912).
Intra-cluster calls (all within this set, so the move is closed): `filter_questions_from_response` → `is_question_or_prompt`; `fuzzy_find_marker` → `strip_emojis`. No module-level constant dependencies. No network/AI/I/O.

### Task 1.1: Caller + import audit

**Files:** none (read-only).

- [ ] **Step 1: Record current callers**

Run: `git grep -nE "\b(is_question_or_prompt|filter_questions_from_response|_strip_template_lines|strip_emojis|fuzzy_find_marker|extract_fitb_by_template_comparison|parse_numbered_questions|parse_vocab_terms)\b" -- ':!docs' ':!tests'`
Expected: hits are the definitions in `assignment_grader.py`, internal call sites, and any `from assignment_grader import ...` consumers. Note every consuming file (the shim must keep them working).

- [ ] **Step 2: Confirm boundaries unchanged**

Run: `grep -nE "^(def|class) " assignment_grader.py | grep -E "is_question_or_prompt|filter_questions_from_response|_strip_template_lines|strip_emojis|fuzzy_find_marker|extract_fitb_by_template_comparison|parse_numbered_questions|parse_vocab_terms"`
Expected: starts at 179, 360, 430, 530, 550, 628, 728, 829. If any shifted, re-derive the exact body end (next top-level `def`/`class` minus trailing blank lines) before moving.

### Task 1.2: Failing unit test for the new module (no network, no I/O)

**Files:**
- Test: `tests/test_response_extraction.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from backend.services import response_extraction as rx


def test_module_is_pure_no_network_no_io():
    src = open(rx.__file__, encoding="utf-8").read()
    assert "from assignment_grader" not in src and "import assignment_grader" not in src
    for forbidden in ("import requests", "import openai", "import anthropic",
                       "from flask import", "OpenAI(", "Anthropic("):
        assert forbidden not in src, f"service must be network-free: found {forbidden}"


def test_strip_emojis_is_pure():
    assert rx.strip_emojis("hi \U0001F600 there") == "hi  there"


def test_is_question_or_prompt_returns_bool():
    assert isinstance(rx.is_question_or_prompt("What is 2+2?"), bool)
```

- [ ] **Step 2: Run, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_response_extraction.py -q`
Expected: FAIL; `ModuleNotFoundError: No module named 'backend.services.response_extraction'`.

### Task 1.3: Create the module by moving the 8 leaves verbatim

**Files:**
- Create: `backend/services/response_extraction.py`
- Modify: `assignment_grader.py`

- [ ] **Step 1: Create `backend/services/response_extraction.py`**

First line: the module docstring exactly `"""Pure student-response text parsing and extraction. No Flask, no network, no file I/O."""`. Then a blank line. Then the stdlib imports the moved bodies actually use (determine by reading the 8 bodies: at minimum `re`; include `difflib`/`string`/others only if a moved body references them; do not add unused imports, do not import from `assignment_grader`). Then the 8 functions pasted byte-identically from `assignment_grader.py` line ranges 179-357, 360-427, 430-527, 530-547, 550-625, 628-725, 728-826, 829-912. Preserve every character, blank line within each function, and the existing two-blank-line separation between functions.

- [ ] **Step 2: Delete the 8 definitions from `assignment_grader.py`**

Remove exactly lines 179-357, 360-427, 430-527, 530-547, 550-625, 628-725, 728-826, 829-912 (delete from the highest line range downward so earlier ranges do not shift). Leave surrounding two-blank-line spacing between the remaining module-level defs correct.

- [ ] **Step 3: Add the shim re-export to `assignment_grader.py`**

Place immediately before the first class/def in the file (`class GradingBreakdown` at original line 39), after the module's top import block. Exact block:

```python
# ── Tier 2 Slice 2 PR1: pure parsing/extraction leaves extracted to ─────────
# backend/services/response_extraction.py (no Flask, no network, no I/O).
# Re-exported here so existing `from assignment_grader import ...` callers
# keep resolving unchanged.
from backend.services.response_extraction import (  # noqa: F401
    _strip_template_lines,
    extract_fitb_by_template_comparison,
    filter_questions_from_response,
    fuzzy_find_marker,
    is_question_or_prompt,
    parse_numbered_questions,
    parse_vocab_terms,
    strip_emojis,
)
```

- [ ] **Step 4: Verbatim-integrity check**

Run:
```bash
git show HEAD:assignment_grader.py | sed -n '179,357p;360,427p;430,527p;530,547p;550,625p;628,725p;728,826p;829,912p' > /tmp/leaves_orig.txt
```
Then extract the same 8 function bodies from `backend/services/response_extraction.py` into `/tmp/leaves_new.txt` and `diff /tmp/leaves_orig.txt /tmp/leaves_new.txt`. Expected: no differences inside any function body (the module docstring/imports/blank-line separators are outside the compared ranges). Any in-body diff means the move was not verbatim; fix to byte-identical.

- [ ] **Step 5: Run unit test → GREEN + regression**

Run: `source venv/bin/activate && python -m pytest tests/test_response_extraction.py -q` → PASS.
Run: `python -m pytest tests/ -q -k "grading or extraction or pipeline or factors or portal or assignment or worksheet" 2>&1 | tail -3` → 0 failed (the 9 existing grading-pipeline test files are the behavior guard).
Run: `ruff check backend/services/response_extraction.py assignment_grader.py tests/test_response_extraction.py` → clean.
Run: `grep -n "assignment_grader" backend/services/response_extraction.py` → empty (no import cycle).

### Task 1.4: Characterization tests for the 8 leaves

**Files:**
- Test: `tests/test_response_extraction.py` (extend)

- [ ] **Step 1: Add per-leaf characterization tests**

For each of the 8 leaves, add a test that calls it with a realistic input and pins the ACTUAL observed return value. Probe first with a one-off `python -c` to observe the real output, then assert exactly that (characterization discipline: pin reality, never assume). Cover at least: `parse_numbered_questions` on a 3-question block; `parse_vocab_terms` on a 3-term block; `fuzzy_find_marker` exact-match and near-match; `extract_fitb_by_template_comparison` with one blank; `_strip_template_lines` removing a template line; `filter_questions_from_response` dropping a question line; `is_question_or_prompt` on a question vs an answer; `strip_emojis` on mixed text. No xfail/skip; assertions must be specific (not just `is not None`).

- [ ] **Step 2: Run → PASS**

Run: `source venv/bin/activate && python -m pytest tests/test_response_extraction.py -q` → all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/services/response_extraction.py assignment_grader.py tests/test_response_extraction.py
git commit -m "$(printf 'refactor(grader): extract parsing/extraction leaves to response_extraction (Tier 2 Slice 2 PR1)\n\nVerbatim byte-identical move of 8 pure leaf helpers into\nbackend/services/response_extraction.py. Thin noqa:F401 re-export shim\nkeeps callers resolving. Zero behavior change. No network/IO; new tests\nrun with neither.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

### Task 1.5: Open PR 1

- [ ] Push branch, open PR (verbatim-extraction framing, both review gates), 9 CI checks green, squash-merge, sync main.

---

## PR 2: large functions + `STUDENT_WORK_MARKERS` under the exhaustive net

Four large functions and one constant, current line ranges in `assignment_grader.py`:
`extract_student_responses` (915-1780, ~866 LOC), `extract_student_responses_legacy` (1783-2073), `format_extracted_for_grading` (2076-2197), `extract_student_work` (3656-3704), and the constant `STUDENT_WORK_MARKERS` (2434-2492, a list).
Intra-cluster calls (all to PR1-moved leaves, now in `response_extraction.py`): `extract_student_responses` → `_strip_template_lines`, `extract_fitb_by_template_comparison`, `filter_questions_from_response`, `fuzzy_find_marker`, `parse_numbered_questions`, `parse_vocab_terms`, `strip_emojis`; `extract_student_responses_legacy` → `filter_questions_from_response`, `is_question_or_prompt`; `format_extracted_for_grading` → `is_question_or_prompt`; `extract_student_work` → reads `STUDENT_WORK_MARKERS` only. `STUDENT_WORK_MARKERS` is also imported by `backend/grading/pipeline.py:564`, so the shim must re-export it.

### Task 2.1: Exhaustive characterization net BEFORE the move

**Files:**
- Test: `tests/test_response_extraction_characterization.py` (create)

- [ ] **Step 1: Build the net against the CURRENT (pre-move) code**

Import the four functions from their current location: `from assignment_grader import extract_student_responses, extract_student_responses_legacy, format_extracted_for_grading, extract_student_work`. Build a parametrized fixture matrix over the cross-product the spec §6 requires: **extraction_mode** {structured, legacy} × **document shape** {docx-table-derived text, graider-marked text, plain numbered, vocab-term, FITB, summary/written} × **subject/grade spread** {math gr5, ELA gr8, science gr10, social studies gr12}. For each cell, construct a representative literal input string (and `marker_config`/`template_text` where the signature needs them; read each function signature first), call the function, and pin the EXACT returned object with a strict equality assertion. Probe each cell with a one-off `python -c` to capture the real output before writing the assertion (characterization discipline: pin observed reality, never assume; if a cell raises today, pin that it raises; do not "fix" it here). Add a determinism assertion per representative cell (same input twice → equal output). Skeleton:

```python
import pytest
from assignment_grader import (
    extract_student_responses,
    extract_student_responses_legacy,
    format_extracted_for_grading,
    extract_student_work,
)

# Each entry: (id, callable, args_kwargs, expected): expected pinned from
# a real probe run against pre-move code (see Step 1 instructions).
CASES = [
    # ... one entry per (mode x shape x subject) cell; expand to the full
    # cross-product. Example shape (fill `expected` from the probe):
    # ("structured_numbered_math_g5", extract_student_responses,
    #   (("1. 2+2=?\nStudent: 4\n",), {"custom_markers": None}), {...}),
]

@pytest.mark.parametrize("cid,fn,argskw,expected", CASES, ids=[c[0] for c in CASES])
def test_extraction_contract(cid, fn, argskw, expected):
    args, kw = argskw
    assert fn(*args, **kw) == expected

@pytest.mark.parametrize("cid,fn,argskw,expected", CASES, ids=[c[0] for c in CASES])
def test_extraction_deterministic(cid, fn, argskw, expected):
    args, kw = argskw
    assert fn(*args, **kw) == fn(*args, **kw)
```

- [ ] **Step 2: Run the net against pre-move code → GREEN baseline**

Run: `source venv/bin/activate && python -m pytest tests/test_response_extraction_characterization.py -q` → all PASS (this is the pinned pre-move contract). Commit this net on the branch before moving anything.

### Task 2.2: Failing unit test for the large functions in the new module

**Files:**
- Test: `tests/test_response_extraction.py` (extend)

- [ ] **Step 1: Add failing import-from-new-location test**

```python
def test_large_fns_importable_from_service():
    from backend.services.response_extraction import (  # noqa: F401
        extract_student_responses,
        extract_student_responses_legacy,
        format_extracted_for_grading,
        extract_student_work,
        STUDENT_WORK_MARKERS,
    )
    assert isinstance(STUDENT_WORK_MARKERS, list) and STUDENT_WORK_MARKERS
```

- [ ] **Step 2: Run, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_response_extraction.py::test_large_fns_importable_from_service -q`
Expected: FAIL; ImportError (names not yet in the service module).

### Task 2.3: Move the 4 large functions + constant verbatim

**Files:**
- Modify: `backend/services/response_extraction.py`, `assignment_grader.py`

- [ ] **Step 1: Re-confirm boundaries**

Run: `grep -nE "^(def |STUDENT_WORK_MARKERS)" assignment_grader.py | grep -E "extract_student_responses|extract_student_responses_legacy|format_extracted_for_grading|extract_student_work|STUDENT_WORK_MARKERS"`
Expected starts: 915, 1783, 2076, 3656, and `STUDENT_WORK_MARKERS = [` at 2434 (closes at 2492). Re-derive exact ends (next top-level def minus trailing blanks) if shifted.

- [ ] **Step 2: Move into `response_extraction.py`**

Append, byte-identical: the `STUDENT_WORK_MARKERS = [ ... ]` block (2434-2492), then `extract_student_responses` (915-1780), `extract_student_responses_legacy` (1783-2073), `format_extracted_for_grading` (2076-2197), `extract_student_work` (3656-3704). Add any additional stdlib imports these bodies use that are not already in the module header (read the bodies; no `assignment_grader` import). Delete those exact ranges from `assignment_grader.py` (highest-to-lowest order so ranges do not shift). Extend the existing shim block in `assignment_grader.py` to also re-export `extract_student_responses`, `extract_student_responses_legacy`, `format_extracted_for_grading`, `extract_student_work`, `STUDENT_WORK_MARKERS` (keep the block sorted, all under the one `# noqa: F401` import).

- [ ] **Step 3: Verbatim-integrity check**

`git show HEAD:assignment_grader.py | sed -n '2434,2492p;915,1780p;1783,2073p;2076,2197p;3656,3704p' > /tmp/big_orig.txt`; extract the same five blocks from `response_extraction.py` into `/tmp/big_new.txt`; `diff /tmp/big_orig.txt /tmp/big_new.txt` → no in-body differences.

- [ ] **Step 4: Net stays GREEN unchanged + regression**

Repoint `tests/test_response_extraction_characterization.py`'s import from `from assignment_grader import ...` to `from backend.services.response_extraction import ...` (the ONLY change to that file; every pinned `expected` must still pass byte-identical; that equivalence is the zero-behavior-change proof).
Run: `source venv/bin/activate && python -m pytest tests/test_response_extraction_characterization.py tests/test_response_extraction.py -q` → all PASS.
Run: `python -m pytest tests/ -q -k "grading or extraction or pipeline or factors or portal or assignment or worksheet" 2>&1 | tail -3` → 0 failed.
Run: `ruff check backend/services/response_extraction.py assignment_grader.py tests/test_response_extraction_characterization.py` → clean.
Run: `grep -n "assignment_grader" backend/services/response_extraction.py` → empty.
Run: `git grep -nE "from assignment_grader import" -- ':!docs' | grep -E "extract_student_responses|STUDENT_WORK_MARKERS|format_extracted_for_grading"` → every hit resolves via the shim (no broken consumer; `backend/grading/pipeline.py:564` in particular).

- [ ] **Step 5: Commit**

```bash
git add backend/services/response_extraction.py assignment_grader.py tests/test_response_extraction.py tests/test_response_extraction_characterization.py
git commit -m "$(printf 'refactor(grader): extract large parsing/extraction fns to response_extraction (Tier 2 Slice 2 PR2)\n\nVerbatim byte-identical move of extract_student_responses (+legacy),\nformat_extracted_for_grading, extract_student_work, and the\nSTUDENT_WORK_MARKERS constant. Exhaustive characterization net pinned\npre-move stays green byte-identical post-move. Shim re-exports all.\nZero behavior change.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

### Task 2.4: Open PR 2

- [ ] Push, open PR (verbatim framing, net-pinned-pre-move evidence, both review gates), 9 CI checks green, squash-merge, sync main.

---

## Task 3: Close out the slice (PR 3)

**Files:** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`, `docs/superpowers/plans/2026-05-17-assignment-grader-extraction.md`

- [ ] **Step 1: Verify shim + caller integrity end to end**

Run: `git grep -nE "\b(is_question_or_prompt|filter_questions_from_response|_strip_template_lines|strip_emojis|fuzzy_find_marker|extract_fitb_by_template_comparison|parse_numbered_questions|parse_vocab_terms|extract_student_responses|extract_student_responses_legacy|format_extracted_for_grading|extract_student_work|STUDENT_WORK_MARKERS)\b" -- ':!docs' ':!tests'`
Confirm: the only definitions live in `backend/services/response_extraction.py`; every other production hit is a call site or the one shim re-export; `extract_from_tables`/`extract_from_graider_text` still defined in `assignment_grader.py` and still call the (re-exported) `extract_student_responses` fine.
Run: `source venv/bin/activate && python -m pytest tests/ -q -k "grading or extraction or pipeline or factors or portal or assignment or worksheet or response_extraction" 2>&1 | tail -3` → 0 failed. Record `wc -l assignment_grader.py backend/services/response_extraction.py`.

- [ ] **Step 2: Assessment-doc dated note**

Append a dated section to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (match the existing dated-section house style; no em-dashes; no AI-tell phrasing): Tier 2 Slice 2 shipped (PR numbers, assignment_grader.py LOC before/after, the new module LOC), a Code Quality / Architecture nudge, no multi-model re-score (mechanically test-guarded like Slice 1 / Data Integrity Tier 1), overall stays ~7.9 with Code Quality / Architecture trending up. Record the two functions left behind per §3 (`extract_from_tables`, `extract_from_graider_text`) and the exact reason (call staying I/O `read_docx_file_structured`; moving would create an import cycle).

- [ ] **Step 3: STATUS-stamp this plan CLOSED**

Add a `**Status:** CLOSED 2026-05-17; shipped via PR #<n1> (PR1 leaves), #<n2> (PR2 large), #<n3> (closeout). assignment_grader.py <before> → <after> LOC. Left behind per §3: extract_from_tables, extract_from_graider_text (call staying read_docx_file_structured).` line right after the **Goal:** line of this plan. Commit docs; open PR 3; 9 CI checks green; squash-merge; sync main.

---

## Self-Review

- **Spec coverage:** §1 goal → Goal + all tasks. §2 verified-purity facts → Task 1.1/2.1 audits + the no-network unit test. §3 coupling rule → the no-network/no-IO test in 1.2, the verbatim `diff` checks (1.3 Step 4, 2.3 Step 3), and the §3-stays recorded in File Structure + Task 3 Step 2. §4 target module + exact functions + shim → Tasks 1.3/2.3 with exact line ranges + the shim blocks. §5 sequencing → PR1/PR2/PR3. §6 exhaustive net → Task 2.1 cross-product matrix pinned pre-move, byte-identical post-move (2.3 Step 4). §7 approach → single dependency-closed module, sequenced. §8 scope in/out → moved set vs the recorded §3-stays + out-of-scope clusters untouched. §9 risks → net-before-move, no-IO test, import-cycle grep, full regression each PR. §10 success criteria → Task 3.
- **Placeholder scan:** no "TBD"/"add error handling"/vague steps; the only intentionally-templated content is the characterization `CASES` list, whose construction method (probe real output per cross-product cell, then pin exact equality) and skeleton are fully specified; the verbatim-move bodies are intentionally not re-pasted per the Refactor-plan note. PR numbers in Task 3 are `<n1..n3>` because they are assigned by GitHub at PR-open time; this is unavoidable and not a placeholder for engineer-authored content.
- **Type/name consistency:** the new module name (`backend/services/response_extraction.py`), the 12 function names, `STUDENT_WORK_MARKERS`, and the shim import blocks are identical across the spec, all tasks, and the self-review.
