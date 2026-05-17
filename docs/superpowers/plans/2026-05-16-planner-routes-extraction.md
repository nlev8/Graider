# planner_routes.py Service Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move pure logic out of `backend/routes/planner_routes.py` (6,050 LOC) into three focused `backend/services/planner_*.py` modules, each unit-testable without Flask, zero behavior change.

**Architecture:** Verbatim function moves into responsibility-split service modules, mirroring the existing `backend/services/assignment_post_processing.py` pattern. Each moved function is re-imported into `planner_routes.py` as a thin shim so route handlers and any external callers keep working unchanged. The proof of decoupling is a new unit test per module that imports the service directly and runs with no Flask app/test client. Three sequenced PRs: standards, then export, then prompts.

**Tech Stack:** Python 3.12, Flask, pytest (no Flask client in the new unit tests), ruff.

**Spec:** `docs/superpowers/specs/2026-05-16-planner-routes-extraction-design.md`. The §3 coupling-reduction rule governs every task: a function is extracted only if its new unit test runs without a Flask context; if that is infeasible the function stays and is recorded with the reason.

**Refactor-plan note:** moves are verbatim. Steps specify the exact source lines and destination plus the shim import and the full new test code. Moved bodies are not re-pasted (that would be error-prone for unchanged code); they are identified by exact location.

---

## PR 1 — `backend/services/planner_standards.py`

Functions (current lines in `planner_routes.py`): `_get_openai_context` (81), `load_support_documents_for_planning` (104), `_extract_grade_from_code` (175), `_grade_matches` (212), `_get_standards_map` (236), `_load_standards_file` (249), `load_standards` (263).

### Task 1.1: External-caller + import audit

**Files:** none modified (investigation that the next task depends on).

- [ ] **Step 1: Find every importer of these names from planner_routes**

Run: `git grep -nE "from backend.routes.planner_routes import|planner_routes\.(load_standards|_get_standards_map|_load_standards_file|_extract_grade_from_code|_grade_matches|load_support_documents_for_planning|_get_openai_context)" -- ':!docs'`
Expected: a list (possibly empty). Record every file. These callers must keep working via the shim in Task 1.3 (the shim re-exports the names from `planner_routes`, so existing `from backend.routes.planner_routes import load_standards` keeps resolving).

- [ ] **Step 2: List the imports the moved functions use**

Run: `sed -n '1,80p' backend/routes/planner_routes.py` and read the module's import block. Note which imports the seven functions reference (e.g. `os`, `json`, `logging`, glob, the LLM adapter for `_get_openai_context`). The new module must import exactly those.

### Task 1.2: Failing unit test for the new module

**Files:**
- Test: `tests/test_planner_standards.py` (create)

- [ ] **Step 1: Write the failing test (targets the desired end-state import path; no Flask client)**

```python
"""planner_standards service — runs with NO Flask app/test client.
The import itself is the decoupling proof: these functions must be
callable outside the route module."""
import pytest

from backend.services import planner_standards as ps


def test_extract_grade_from_code_pulls_grade_digits():
    # _extract_grade_from_code parses a grade out of a standards code.
    assert ps._extract_grade_from_code("MATH.5.NBT.1") == "5" or \
        ps._extract_grade_from_code("5.NBT.1") == "5"


def test_grade_matches_is_symmetric_on_equal_grades():
    assert ps._grade_matches("5", "5") is True
    assert ps._grade_matches("5", "7") is False


def test_module_has_no_flask_import():
    src = open(ps.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src, \
        "planner_standards must not depend on Flask (coupling-reduction rule)"
```

- [ ] **Step 2: Run it, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_standards.py -q`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'backend.services.planner_standards'`.

### Task 1.3: Create the module by moving the functions

**Files:**
- Create: `backend/services/planner_standards.py`
- Modify: `backend/routes/planner_routes.py` (remove the 7 defs at lines 81–~338; add a shim import near the existing `from backend.services.assignment_post_processing import (...)` block around line 40)

- [ ] **Step 1: Create `backend/services/planner_standards.py`**

  - Add a module docstring: `"""Standards loading + matching for the planner. Pure logic extracted from planner_routes.py (no Flask)."""`
  - Add only the imports the seven functions actually use (from Task 1.1 Step 2).
  - Move the seven function definitions verbatim from `planner_routes.py` (current lines: `_get_openai_context` 81, `load_support_documents_for_planning` 104, `_extract_grade_from_code` 175, `_grade_matches` 212, `_get_standards_map` 236, `_load_standards_file` 249, `load_standards` 263) into this file, preserving order and bodies exactly. Do not edit logic.
  - Coupling-reduction check for `_get_openai_context`: if its body reads Flask `request`/`g` or app config, change its signature to take that value as a parameter and update callers in `planner_routes.py` to pass it. If a clean signature is infeasible, leave `_get_openai_context` in `planner_routes.py`, do not move it, and add a one-line comment in the spec's §7 "Out" via a follow-up note in the PR description. Move the other six regardless.

- [ ] **Step 2: Replace the defs in `planner_routes.py` with a shim import**

  - Delete the moved function bodies from `planner_routes.py`.
  - Near line 40 (next to the existing `assignment_post_processing` import), add:

```python
from backend.services.planner_standards import (  # noqa: F401  (re-exported for callers)
    _extract_grade_from_code,
    _get_standards_map,
    _grade_matches,
    _load_standards_file,
    load_standards,
    load_support_documents_for_planning,
)
```

  (Include `_get_openai_context` in this import only if it was moved in Step 1.) `# noqa: F401` keeps ruff quiet about the re-export; existing `from backend.routes.planner_routes import load_standards` callers found in Task 1.1 keep resolving through this shim.

- [ ] **Step 3: Run the new unit test → GREEN**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_standards.py -q`
Expected: PASS (3 passed).

- [ ] **Step 4: Regression — route + planner suites unchanged**

Run: `source venv/bin/activate && python -m pytest tests/ -q -k "planner or standards or lesson or assignment_post" 2>&1 | tail -2`
Expected: 0 failed. Then `ruff check backend/services/planner_standards.py backend/routes/planner_routes.py` → All checks passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_standards.py backend/routes/planner_routes.py tests/test_planner_standards.py
git commit -m "refactor(planner): extract standards logic to planner_standards service (Tier 2 PR1)"
```

### Task 1.4: Open PR 1

- [ ] Push branch `feature/planner-extraction`, open PR, all 9 required checks green, squash-merge. PR body notes any function left behind per the coupling rule.

---

## PR 2 — `backend/services/planner_export.py`

Functions: `_save_grading_config_for_export` (2150), `_question_to_visual_dict` (2282), `_export_assignment_docx_graider` (2346), `_create_visual_for_question` (3103), `parse_template_structure` (4482), `generate_qti_xml` (4814), `_get_export_dir` (5528).

### Task 2.1: Characterization tests for `_create_visual_for_question` BEFORE moving it

**Files:**
- Test: `tests/test_planner_export_characterization.py` (create)

- [ ] **Step 1: Write characterization tests pinning current output (import from current location)**

```python
"""Pin _create_visual_for_question output for representative question
types BEFORE the move, so the extraction provably changes nothing.
Imports from the CURRENT location (planner_routes) on purpose."""
from backend.routes.planner_routes import _create_visual_for_question

_CASES = [
    {"question_type": "multiple_choice", "question": "2+2?",
     "options": ["3", "4", "5"], "correct_answer": "4"},
    {"question_type": "short_answer", "question": "Define osmosis."},
    {"question_type": "data_table", "question": "Fill the table",
     "data_table": {"headers": ["x", "y"], "rows": [["1", "2"]]}},
]


def test_visual_output_is_stable_per_type():
    for case in _CASES:
        out = _create_visual_for_question(dict(case), show_answer=False)
        # Pin the shape: a dict/None contract that must not change on move.
        assert out is None or isinstance(out, (dict, str)), (case, type(out))
        # Determinism: same input twice -> identical output.
        assert _create_visual_for_question(dict(case), show_answer=False) == out
```

- [ ] **Step 2: Run, confirm GREEN against current code**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_export_characterization.py -q`
Expected: PASS. This is the safety net; it must still pass after the move (Task 2.3 Step 4) with the import path changed.

### Task 2.2: Failing unit test for the new module

**Files:**
- Test: `tests/test_planner_export.py` (create)

- [ ] **Step 1: Write the failing test (no Flask client)**

```python
import pytest
from backend.services import planner_export as pe


def test_get_export_dir_returns_path_like():
    d = pe._get_export_dir()
    assert isinstance(d, str) and len(d) > 0


def test_module_has_no_flask_import():
    src = open(pe.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src
```

- [ ] **Step 2: Run, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_export.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.planner_export'`.

### Task 2.3: Create the module by moving the functions

**Files:**
- Create: `backend/services/planner_export.py`
- Modify: `backend/routes/planner_routes.py` (remove the 7 defs; add shim import)

- [ ] **Step 1: Caller + import audit**

Run: `git grep -nE "from backend.routes.planner_routes import|planner_routes\.(_save_grading_config_for_export|_question_to_visual_dict|_export_assignment_docx_graider|_create_visual_for_question|parse_template_structure|generate_qti_xml|_get_export_dir)" -- ':!docs'`
Record callers. Note the inline `from backend.services.worksheet_generator import ...` imports already used inside `_export_assignment_docx_graider`/export routes — keep those as-is (already a service dependency).

- [ ] **Step 2: Create `backend/services/planner_export.py`**

  - Docstring: `"""Document / visual / platform-export rendering for the planner. Pure logic extracted from planner_routes.py (no Flask)."""`
  - Import only what the seven functions use (docx libs, the `worksheet_generator` imports they reference, `os`, etc.).
  - Move the seven functions verbatim (lines listed above), bodies unchanged.
  - Coupling check per §3: if any reads `request`/`g`/app config, parameterize it and update callers. If infeasible for a specific one, leave it and note in the PR.

- [ ] **Step 3: Shim import in `planner_routes.py`**

Replace the deleted defs with, near line 40:

```python
from backend.services.planner_export import (  # noqa: F401
    _create_visual_for_question,
    _export_assignment_docx_graider,
    _get_export_dir,
    _question_to_visual_dict,
    _save_grading_config_for_export,
    generate_qti_xml,
    parse_template_structure,
)
```

- [ ] **Step 4: Both test files GREEN, characterization unchanged**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_export.py tests/test_planner_export_characterization.py -q`
Expected: all PASS. The characterization test passing post-move is the zero-behavior-change proof.

- [ ] **Step 5: Regression + ruff**

Run: `source venv/bin/activate && python -m pytest tests/ -q -k "planner or export or assessment or worksheet" 2>&1 | tail -2` → 0 failed; `ruff check backend/services/planner_export.py backend/routes/planner_routes.py` → clean.

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_export.py backend/routes/planner_routes.py tests/test_planner_export.py tests/test_planner_export_characterization.py
git commit -m "refactor(planner): extract export rendering to planner_export service (Tier 2 PR2)"
```

### Task 2.4: Open PR 2 — 9 checks green, squash-merge.

---

## PR 3 — `backend/services/planner_prompts.py`

Functions: `_build_assignment_prompt` (1298), `_build_period_differentiation_block` (3692).

### Task 3.1: Failing unit test

**Files:**
- Test: `tests/test_planner_prompts.py` (create)

- [ ] **Step 1: Write the failing test (no Flask client)**

```python
from backend.services import planner_prompts as pp


def test_period_block_is_string_and_pure():
    out = pp._build_period_differentiation_block("Honors")
    assert isinstance(out, str)
    src = open(pp.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src


def test_assignment_prompt_includes_config_signal():
    prompt = pp._build_assignment_prompt(
        {"title": "L1", "objectives": ["o1"]},
        {"num_questions": 5},
        assignment_type="assignment",
    )
    assert isinstance(prompt, str) and len(prompt) > 0
```

- [ ] **Step 2: Run, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_prompts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.planner_prompts'`.

### Task 3.2: Create the module by moving the functions

**Files:**
- Create: `backend/services/planner_prompts.py`
- Modify: `backend/routes/planner_routes.py`

- [ ] **Step 1: Caller audit**

Run: `git grep -nE "_build_assignment_prompt|_build_period_differentiation_block" -- ':!docs'`

- [ ] **Step 2: Create `backend/services/planner_prompts.py`** with docstring `"""Prompt construction for the planner. Pure string building (no Flask)."""`, the imports the two functions use, and the two functions moved verbatim (lines 1298, 3692).

- [ ] **Step 3: Shim import** near line 40 of `planner_routes.py`:

```python
from backend.services.planner_prompts import (  # noqa: F401
    _build_assignment_prompt,
    _build_period_differentiation_block,
)
```

- [ ] **Step 4: GREEN + regression**

Run: `source venv/bin/activate && python -m pytest tests/test_planner_prompts.py -q` → PASS; `python -m pytest tests/ -q -k "planner or lesson or assignment or assessment" 2>&1 | tail -2` → 0 failed; `ruff check backend/services/planner_prompts.py backend/routes/planner_routes.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_prompts.py backend/routes/planner_routes.py tests/test_planner_prompts.py
git commit -m "refactor(planner): extract prompt builders to planner_prompts service (Tier 2 PR3)"
```

### Task 3.3: Open PR 3 — 9 checks green, squash-merge.

---

## Task 4: Close out the slice

- [ ] **Step 1:** `source venv/bin/activate && python -m pytest tests/ -q -k "planner or lesson or assessment or assignment or export or standards or prompts or worksheet" 2>&1 | tail -3` → 0 failed.
- [ ] **Step 2:** `ruff check backend/` → All checks passed; `wc -l backend/routes/planner_routes.py` (record the reduced LOC).
- [ ] **Step 3:** Append a dated "Tier 2 slice 1 — planner_routes extraction shipped" note to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (Code Quality / Architecture nudge; no multi-model re-score — mechanically test-guarded like Data Integrity Tier 1) and STATUS-stamp this plan CLOSED. List any functions left behind per the coupling rule and why.

---

## Self-Review

- **Spec coverage:** §3 coupling rule → enforced in every "no Flask import" test + the parameterize-or-leave step in 1.3/2.3 Step 2. §4.1/4.2/4.3 modules → PR1/PR2/PR3. §5 sequencing (standards→export→prompts) → PR order. §8 `_create_visual_for_question` entanglement → Task 2.1 characterization tests before the move. §8 import cycles → new modules import only stdlib/siblings, never `planner_routes` (shim is one-directional). §9 success criteria → Task 4.
- **Placeholder scan:** moves specified by exact source line + destination + full shim code; all new test code shown in full; no "TBD"/"add error handling"/vague steps. The verbatim-move bodies are intentionally not re-pasted (refactor-plan note in the header explains why — re-pasting unchanged code is error-prone, not a placeholder).
- **Type/name consistency:** module names (`planner_standards`/`planner_export`/`planner_prompts`), the seven/seven/two function names, and the shim import blocks are identical across the tasks and the spec.
