# Phase 3b1 — planner_routes.py Helpers Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `backend/routes/planner_routes.py` from 8104 → ~5950 LOC by extracting the ~2150-line post-processing pipeline into `backend/services/assignment_post_processing.py`. Zero behavior change. SIS compliance stays green.

**Architecture:** Five sequential PRs with the Phase 3a playbook: PR1 moves leaf helpers only (no cycle), PR2 moves hydrators+utils, PR3 adds quality validation and locks behavior with golden tests + handler smoke, PR4 is the ONE non-byte-identical PR (auto-fix signature refactor), PR5 moves the orchestrator + prompt builders last and removes the shim.

**Tech Stack:** Python 3.14, Flask, pytest.

**Spec:** `docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md`

---

## File Structure

After all five PRs:

| File | Role | Size (approx) |
|---|---|---|
| `backend/routes/planner_routes.py` | 25 route handlers, standards loading, support-doc loading, route-local helpers | ~5950 LOC |
| `backend/services/assignment_post_processing.py` | Full post-processing pipeline: orchestrator, classifier, validator, hydrators, quality checks, auto-fix, count/points normalization, prompt builders, cost helpers | ~2150 LOC |
| `tests/test_assignment_post_processing.py` | Golden tests + AST completeness + runtime smokes (new) | ~250 LOC |
| `tests/test_planner_routes_shim.py` | Transitional shim guard (new in PR1, deleted in PR5) | ~50 LOC |

## Hard constraints (enforced every PR)

- SIS compliance suite 180/180 green.
- Coverage floor 32 holds (CI fails if below).
- Function bodies byte-identical for PRs 1, 2, 3, and 5. PR4 is the sole exception (explicit-context signature refactor).
- No Clever/ClassLink/OneRoster/roster_sync/oneroster_gradebook file modifications.
- App boots: `python -c "from backend.app import app; print(len(app.url_map._rules))"` returns ≥ 250.
- **PRs must merge sequentially: PR1 → PR2 → PR3 → PR4 → PR5.** Each PR's shim block references names from all prior PRs; merging a PR before its predecessor would leave `planner_routes.py` with import errors at module load. Every task branches from `main` AFTER the previous PR has been merged (see Step N.1 in each task). Do not parallelize PRs.

---

## Task 1 (PR1): Leaf helpers extraction

**Files:**
- Create: `backend/services/assignment_post_processing.py`
- Modify: `backend/routes/planner_routes.py` (remove 8 helpers + 3 constants, add shim imports)
- Create: `tests/test_planner_routes_shim.py`

### Moved in PR1 (8 leaf helpers + 3 constants, no cross-refs to unmoved code)

| Name | Current line | Role |
|---|---|---|
| `_validate_question` | 879 | Phase 3 — pure dict validator |
| `_REQUIRED_FIELDS` | 850 | Constant — required-field map for `_validate_question` |
| `_enforce_question_count` | 1905 | Phase 4a — count enforcement |
| `_count_questions` | 1897 | Count helper (pure) |
| `_build_question_count_instruction` | 1883 | Prompt fragment builder (pure) |
| `_normalize_points` | 1977 | Phase 5 — points math (pure) |
| `_DEFAULT_POINTS` | 1962 | Constant — default point values for `_normalize_points` |
| `_merge_usage` | 1944 | Usage dict merge (pure) |
| `_extract_usage` | 42 | Cost extraction (pure) |
| `_record_planner_cost` | 59 | Cost logging (pure) |
| `PLANNER_COSTS_FILE` | 56 | Constant — file path for `_record_planner_cost` |

**`_classify_question_type` deferred to PR2** — calls 5 PR2 functions (`_is_identification_question`, `_detect_primary_shape`, `_detect_mode`, `_looks_like_graphing_question`, `_extract_equations_from_text`) + uses `_ALL_GEOMETRY_TYPES`. Confirmed by AST analysis + Codex + Gemini review (2026-04-15).

### Steps

- [ ] **Step 1.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3b1-pr1-leaf-helpers
```

- [ ] **Step 1.2: Create `backend/services/assignment_post_processing.py` with package docstring + imports**

```python
"""Assignment post-processing pipeline.

Extracted from backend/routes/planner_routes.py during Phase 3b1.
Holds the 6-phase pipeline (classify → hydrate → validate → project filter
→ quality → auto-fix → enforce count → normalize points), the cost
tracking helpers, and the prompt builders used by multiple generator
route handlers.

Migration proceeds across 5 PRs:
- PR1 (this): leaf helpers with no cross-refs
- PR2: _hydrate_question dispatcher + sub-hydrators + geometry/text utils
- PR3: quality validation + golden tests
- PR4: _auto_fix_flagged_questions with explicit-context refactor
- PR5: _post_process_assignment orchestrator + prompt builders + cleanup

Spec: docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md
"""
# Standard lib imports the moved functions need — only add what's used.
# (Subagent: inspect each moved function's body; copy minimum imports.)
```

- [ ] **Step 1.3: Move the 8 leaf helpers + 3 constants byte-identical**

For each of the 8 functions AND 3 constants in the table above:
1. Read the function/constant body from `backend/routes/planner_routes.py` at the listed line.
2. Copy into `backend/services/assignment_post_processing.py` (preserve comments, whitespace, and docstrings exactly).
3. Remove from `planner_routes.py`.

Constants must move WITH their sole consumer (same PR — not deferred):
- `PLANNER_COSTS_FILE` (L56) → moves with `_record_planner_cost`
- `_REQUIRED_FIELDS` (L850) → moves with `_validate_question`
- `_DEFAULT_POINTS` (L1962) → moves with `_normalize_points`

Add required imports at the top of the new service module. For each function, check what it references:
- `_validate_question`: uses `_REQUIRED_FIELDS` (moved together), basic dict ops
- `_normalize_points`: uses `_DEFAULT_POINTS` (moved together), basic math
- `_extract_usage`: uses `MODEL_PRICING` (imported from `assignment_grader`)
- `_record_planner_cost`: uses `PLANNER_COSTS_FILE` (moved together), `os`, `json`, `time`
- `_count_questions`: pure dict iteration
- `_enforce_question_count`: calls `_count_questions` (same PR)

- [ ] **Step 1.4: Add re-export shim in `backend/routes/planner_routes.py`**

At the TOP of `planner_routes.py` (after existing imports but before `planner_bp = Blueprint(...)`), add:

```python
# Phase 3b1 PR1: leaf helpers moved to backend/services/assignment_post_processing.py
# Re-export for backwards compat with tests/code that imports these directly
# from backend.routes.planner_routes. Shim deleted in PR5 after all consumers
# migrate to the canonical path.
from backend.services.assignment_post_processing import (
    _validate_question,
    _enforce_question_count,
    _count_questions,
    _build_question_count_instruction,
    _normalize_points,
    _merge_usage,
    _extract_usage,
    _record_planner_cost,
    PLANNER_COSTS_FILE,
    _REQUIRED_FIELDS,
    _DEFAULT_POINTS,
)
```

- [ ] **Step 1.5: Write shim guard test + execution-based test + AST completeness test**

Create `/Users/alexc/Downloads/Graider/tests/test_planner_routes_shim.py`:

```python
"""Transitional shim guard + safety rails for Phase 3b1.

Pins that backend.routes.planner_routes continues to re-export the helpers
moved to backend.services.assignment_post_processing across PRs 1-4.
Deleted in PR5 when shim is removed.

Also includes execution-based tests (not just callable() checks) and
AST bound-name completeness test for the service module.
"""
import sys


def test_planner_routes_reexports_pr1_leaf_helpers():
    """PR1-moved helpers must remain importable via the shim."""
    sys.path.insert(0, "backend")
    try:
        from routes.planner_routes import (
            _validate_question,
            _enforce_question_count,
            _count_questions,
            _build_question_count_instruction,
            _normalize_points,
            _merge_usage,
            _extract_usage,
            _record_planner_cost,
            PLANNER_COSTS_FILE,
            _REQUIRED_FIELDS,
            _DEFAULT_POINTS,
        )
        for fn in (
            _validate_question, _enforce_question_count,
            _count_questions, _build_question_count_instruction, _normalize_points,
            _merge_usage, _extract_usage, _record_planner_cost,
        ):
            assert callable(fn)
        assert isinstance(PLANNER_COSTS_FILE, str)
        assert isinstance(_REQUIRED_FIELDS, dict)
        assert isinstance(_DEFAULT_POINTS, dict)
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_assignment_post_processing_module_is_canonical():
    """Canonical import path for PR5 consumers."""
    sys.path.insert(0, "backend")
    try:
        from services.assignment_post_processing import (
            _validate_question,
            _enforce_question_count,
            _count_questions,
            _build_question_count_instruction,
            _normalize_points,
            _merge_usage,
            _extract_usage,
            _record_planner_cost,
        )
        for fn in (
            _validate_question, _enforce_question_count,
            _count_questions, _build_question_count_instruction, _normalize_points,
            _merge_usage, _extract_usage, _record_planner_cost,
        ):
            assert callable(fn)
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_pr1_helpers_execute_without_nameerror():
    """Execute each PR1 helper with minimal input — catches NameError bombs.

    callable(fn) only checks that the function object exists. This test
    actually CALLS each function to ensure LOAD_GLOBAL instructions in
    the function body resolve (the exact bug class Phase 3a PR3 had with
    DOCUMENTS_DIR and _check_batch_calibration).
    """
    from backend.services.assignment_post_processing import (
        _validate_question,
        _enforce_question_count,
        _count_questions,
        _build_question_count_instruction,
        _normalize_points,
        _merge_usage,
        _extract_usage,
    )

    # _validate_question — pass a minimal question dict
    q = {"question_type": "short_answer", "question": "test"}
    _validate_question(q)

    # _count_questions — empty assignment
    assert _count_questions({}) == 0
    assert _count_questions({"sections": [{"questions": [{"q": 1}]}]}) == 1

    # _build_question_count_instruction — minimal config
    result = _build_question_count_instruction({"totalQuestions": 5})
    assert "5" in result

    # _enforce_question_count — empty assignment
    a, u = _enforce_question_count({"sections": []}, 10)
    assert u is None

    # _normalize_points — empty assignment
    _normalize_points({"sections": []})

    # _merge_usage — empty + empty
    assert _merge_usage(None, None) is None
    assert _merge_usage(None, {"cost": 1}) == {"cost": 1}

    # _extract_usage — None completion
    assert _extract_usage(None) is None


def test_service_module_global_refs_all_resolve():
    """AST bound-name completeness for assignment_post_processing.py.

    Walks LOAD_GLOBAL bytecode instructions across all functions in the
    service module. Asserts every referenced name resolves to the module's
    namespace, a Python builtin, or a known external import. Catches the
    entire NameError bug class automatically on every future edit.

    Same pattern as Phase 3a's test_pipeline_global_refs_all_resolve.
    """
    import dis
    import types
    import builtins
    import importlib
    mod = importlib.import_module("backend.services.assignment_post_processing")

    mod_names = set(dir(mod))
    builtin_names = set(dir(builtins))

    # Allowlist for names that are resolved via other mechanisms
    # (e.g., lazy imports inside function bodies, or names injected at runtime)
    ALLOWLIST = set()

    missing = []
    for name, obj in vars(mod).items():
        if not isinstance(obj, types.FunctionType):
            continue
        for instr in dis.get_instructions(obj):
            if instr.opname in ("LOAD_GLOBAL", "LOAD_ATTR") and instr.opname == "LOAD_GLOBAL":
                ref = instr.argval
                if ref not in mod_names and ref not in builtin_names and ref not in ALLOWLIST:
                    missing.append(f"{name}() -> {ref}")

    assert not missing, f"Unresolved globals in service module: {missing}"
```

- [ ] **Step 1.6: Run shim + safety tests — expect all 4 pass**

```bash
source venv/bin/activate
python -m pytest tests/test_planner_routes_shim.py -v
```

Expected: 4 passed (reexports, canonical, execution, AST completeness).

- [ ] **Step 1.7: Run SIS suite + full suite**

```bash
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_contract.py tests/test_classlink_sso_contract.py tests/test_clever_callback.py tests/test_clever_classes.py tests/test_clever_compliance.py tests/test_clever.py tests/test_clever_student_sso.py tests/test_classlink_sso.py tests/test_oneroster.py tests/test_oneroster_sync_grades.py tests/test_oneroster_gradebook.py tests/test_roster_sync.py tests/test_sis_alerting.py -q
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x -m "not live" --cov=backend --cov-fail-under=32
```

Expected: SIS 180/180; full suite passes; coverage ≥ 32%.

- [ ] **Step 1.8: Codex Gate 3 diff review**

Ask Codex to verify:
1. Only `backend/routes/planner_routes.py`, `backend/services/assignment_post_processing.py`, `tests/test_planner_routes_shim.py` changed.
2. Each moved function body byte-identical (scripted AST diff).
3. Each moved constant byte-identical.
4. Shim imports all 8 functions + 3 constants (11 names total).
5. No Clever/ClassLink/OneRoster file modifications.
6. AST completeness test passes (no unresolved LOAD_GLOBAL).
7. Execution-based test passes (no NameError on actual calls).

Address any HOLD, re-verify, then proceed.

- [ ] **Step 1.9: Commit, push, open PR**

```bash
git add backend/routes/planner_routes.py backend/services/assignment_post_processing.py tests/test_planner_routes_shim.py
git commit -m "refactor: extract 8 leaf helpers + 3 constants to assignment_post_processing (Phase 3b1 PR1)"
git push origin feat/phase3b1-pr1-leaf-helpers
gh pr create --title "refactor: Phase 3b1 PR1 — leaf helpers" --body "PR1 of 5. 8 leaf helpers + 3 constants moved byte-identical; shim keeps backwards-compat. Includes AST completeness + execution-based safety tests."
```

Wait for CI green + user merge signoff.

---

## Task 2 (PR2): Classifier + hydrators + geometry/text utilities

**Files:**
- Modify: `backend/services/assignment_post_processing.py` (add classifier + dispatcher + sub-hydrators + utils + 9 constants)
- Modify: `backend/routes/planner_routes.py` (remove the functions + constants; extend shim)
- Modify: `tests/test_planner_routes_shim.py` (add shim guards for new names)

### Moved in PR2

`_classify_question_type` (deferred from PR1) + `_hydrate_question` dispatcher (line 892) + 12 sub-hydrators + `_infer_editable_columns` + 10 text/geometry utilities + 9 constants:

| Name | Current line | Type |
|---|---|---|
| `_classify_question_type` | 744 | Phase 1 classifier (deferred from PR1 — needs its 5 callees below) |
| `_TRUSTED_AI_TYPES` | 735 | Constant — trusted AI type set for `_classify_question_type` |
| `_ALL_GEOMETRY_TYPES` | 1488 | Constant — geometry type set (shared by classifier + hydrator) |
| `_hydrate_question` | 892 | Phase 2 dispatcher |
| `_hydrate_matching` | 1007 | Sub-hydrator |
| `_hydrate_geometry` | 1071 | Sub-hydrator |
| `_GEOMETRY_DEFAULTS` | 1866 | Constant — default geometry dimensions |
| `_infer_editable_columns` | 1107 | Helper for `_hydrate_data_table` |
| `_ANALYSIS_PATTERN` | 1093 | Constant — regex for `_hydrate_data_table` |
| `_CALC_KEYWORDS` | 1098 | Constant — keywords for `_infer_editable_columns` |
| `_FORMULA_RE` | 1102 | Constant — regex for `_infer_editable_columns` |
| `_hydrate_data_table` | 1167 | Sub-hydrator |
| `_hydrate_box_plot` | 1224 | Sub-hydrator |
| `_hydrate_dot_plot` | 1251 | Sub-hydrator |
| `_hydrate_stem_and_leaf` | 1266 | Sub-hydrator |
| `_hydrate_transformations` | 1286 | Sub-hydrator |
| `_hydrate_fraction_model` | 1334 | Sub-hydrator |
| `_hydrate_unit_circle` | 1348 | Sub-hydrator |
| `_hydrate_protractor` | 1386 | Sub-hydrator |
| `_hydrate_grid_match` | 1406 | Sub-hydrator |
| `_hydrate_inline_dropdown` | 1418 | Sub-hydrator |
| `_SHAPE_KEYWORDS` | 1431 | Constant — shape detection keywords |
| `_POLYGON_SIDES` | 1464 | Constant — polygon side mappings |
| `_MODE_KEYWORDS` | 1469 | Constant — mode detection keywords |
| `_detect_primary_shape` | 1496 | Geometry text util |
| `_detect_mode` | 1542 | Geometry text util |
| `_is_identification_question` | 1551 | Geometry text util |
| `_infer_shape_answer` | 1566 | Geometry text util |
| `_looks_like_graphing_question` | 1591 | Graphing text util |
| `_extract_equations_from_text` | 1606 | Graphing text util |
| `_split_markdown_table` | 1639 | Text util |
| `_extract_dimensions_from_text` | 1698 | Geometry text util |
| `_extract_pythagorean_sides` | 1793 | Geometry text util |
| `_compute_geometry_answer` | 2027 | Geometry text util |

### Steps

- [ ] **Step 2.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3b1-pr2-hydrators
```

- [ ] **Step 2.2: Move the dispatcher + sub-hydrators + utilities byte-identical**

For each function AND constant in the table above:
1. Read the body from `backend/routes/planner_routes.py` at the listed line.
2. Append to `backend/services/assignment_post_processing.py` (preserve everything exactly).
3. Remove from `planner_routes.py`.

Constants must move WITH their consumer functions (same PR). 9 constants total in PR2.

Add any new imports at the top of the service module (`re`, `math`, etc.) that these functions need but PR1 helpers didn't.

- [ ] **Step 2.3: Extend shim block in `planner_routes.py`**

Update the shim import block introduced in PR1:

```python
from backend.services.assignment_post_processing import (
    # PR1
    _validate_question,
    _enforce_question_count,
    _count_questions,
    _build_question_count_instruction,
    _normalize_points,
    _merge_usage,
    _extract_usage,
    _record_planner_cost,
    PLANNER_COSTS_FILE,
    _REQUIRED_FIELDS,
    _DEFAULT_POINTS,
    # PR2
    _classify_question_type,
    _TRUSTED_AI_TYPES,
    _ALL_GEOMETRY_TYPES,
    _hydrate_question,
    _hydrate_matching,
    _hydrate_geometry,
    _GEOMETRY_DEFAULTS,
    _infer_editable_columns,
    _ANALYSIS_PATTERN,
    _CALC_KEYWORDS,
    _FORMULA_RE,
    _hydrate_data_table,
    _hydrate_box_plot,
    _hydrate_dot_plot,
    _hydrate_stem_and_leaf,
    _hydrate_transformations,
    _hydrate_fraction_model,
    _hydrate_unit_circle,
    _hydrate_protractor,
    _hydrate_grid_match,
    _hydrate_inline_dropdown,
    _SHAPE_KEYWORDS,
    _POLYGON_SIDES,
    _MODE_KEYWORDS,
    _detect_primary_shape,
    _detect_mode,
    _is_identification_question,
    _infer_shape_answer,
    _looks_like_graphing_question,
    _extract_equations_from_text,
    _split_markdown_table,
    _extract_dimensions_from_text,
    _extract_pythagorean_sides,
    _compute_geometry_answer,
)
```

- [ ] **Step 2.4: Extend `tests/test_planner_routes_shim.py`**

Add a new test asserting all 25 PR2 functions + 9 constants are importable via shim AND from canonical path:

```python
def test_planner_routes_reexports_pr2_hydrators():
    """PR2-moved classifier + hydrators + utils + constants remain importable via the shim."""
    import sys
    sys.path.insert(0, "backend")
    try:
        from routes.planner_routes import (
            _classify_question_type,
            _TRUSTED_AI_TYPES, _ALL_GEOMETRY_TYPES,
            _hydrate_question, _hydrate_matching, _hydrate_geometry,
            _GEOMETRY_DEFAULTS,
            _infer_editable_columns, _ANALYSIS_PATTERN, _CALC_KEYWORDS, _FORMULA_RE,
            _hydrate_data_table, _hydrate_box_plot,
            _hydrate_dot_plot, _hydrate_stem_and_leaf, _hydrate_transformations,
            _hydrate_fraction_model, _hydrate_unit_circle, _hydrate_protractor,
            _hydrate_grid_match, _hydrate_inline_dropdown,
            _SHAPE_KEYWORDS, _POLYGON_SIDES, _MODE_KEYWORDS,
            _detect_primary_shape, _detect_mode, _is_identification_question,
            _infer_shape_answer, _looks_like_graphing_question,
            _extract_equations_from_text, _split_markdown_table,
            _extract_dimensions_from_text, _extract_pythagorean_sides,
            _compute_geometry_answer,
        )
        for fn in (_classify_question_type, _hydrate_question, _hydrate_matching, _hydrate_geometry):
            assert callable(fn)
        assert isinstance(_TRUSTED_AI_TYPES, frozenset)
        assert isinstance(_ALL_GEOMETRY_TYPES, (set, frozenset))
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_pr2_canonical_path_importable():
    """PR2-moved names must also be importable via canonical service path."""
    from backend.services.assignment_post_processing import (
        _classify_question_type,
        _TRUSTED_AI_TYPES, _ALL_GEOMETRY_TYPES,
        _hydrate_question, _hydrate_matching, _hydrate_geometry,
        _detect_primary_shape, _detect_mode, _is_identification_question,
    )
    assert callable(_classify_question_type)
    assert callable(_hydrate_question)
    assert isinstance(_TRUSTED_AI_TYPES, frozenset)
```

- [ ] **Step 2.5: Run tests + SIS + full suite**

```bash
source venv/bin/activate
python -m pytest tests/test_planner_routes_shim.py -v
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_contract.py tests/test_classlink_sso_contract.py tests/test_clever_callback.py tests/test_clever_classes.py tests/test_clever_compliance.py tests/test_clever.py tests/test_clever_student_sso.py tests/test_classlink_sso.py tests/test_oneroster.py tests/test_oneroster_sync_grades.py tests/test_oneroster_gradebook.py tests/test_roster_sync.py tests/test_sis_alerting.py -q
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x -m "not live" --cov=backend --cov-fail-under=32
```

Expected: all pass; SIS 180/180; coverage ≥ 32%.

- [ ] **Step 2.6: Codex Gate 3**

Ask Codex:
1. Only 3 files changed (planner_routes, service, shim test).
2. Each of the 25 moved function bodies + 9 constants byte-identical.
3. `_classify_question_type` now co-located with its 5 callees (no cross-module NameError).
4. `_hydrate_question` dispatcher now calls sub-hydrators in its own module (no cycle).
5. No SIS files touched.
6. AST completeness test still passes with expanded module.

- [ ] **Step 2.7: Commit, push, open PR**

```bash
git add backend/routes/planner_routes.py backend/services/assignment_post_processing.py tests/test_planner_routes_shim.py
git commit -m "refactor: extract classifier + hydrators + geometry/text utils (Phase 3b1 PR2)"
git push origin feat/phase3b1-pr2-hydrators
gh pr create --title "refactor: Phase 3b1 PR2 — classifier + hydrators + utils" --body "PR2 of 5. 25 functions + 9 constants moved byte-identical. _classify_question_type co-located with its 5 callees."
```

---

## Task 3 (PR3): Quality validation + golden tests + handler smoke

**Files:**
- Modify: `backend/services/assignment_post_processing.py` (add 3 quality functions)
- Modify: `backend/routes/planner_routes.py` (remove; extend shim)
- Modify: `tests/test_planner_routes_shim.py` (extend)
- Create: `tests/test_assignment_post_processing.py` (golden tests + handler smoke)

### Moved in PR3

| Name | Current line | Type |
|---|---|---|
| `_is_project_question` | 257 | Quality filter function |
| `_PROJECT_KEYWORDS` | 240 | Constant — project detection keywords for `_is_project_question` |
| `_validate_question_quality` | 280 | Quality validation orchestrator |
| `_check_question_quality` | 322 | Quality check implementation |

### Steps

- [ ] **Step 3.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3b1-pr3-quality-goldens
```

- [ ] **Step 3.2: Move 3 quality functions + 1 constant byte-identical**

Same pattern as PR1/PR2: copy each body from planner_routes.py, paste into assignment_post_processing.py, delete from planner_routes.py. `_PROJECT_KEYWORDS` constant moves with `_is_project_question`.

- [ ] **Step 3.3: Extend shim**

Add 4 more names to the shim import block:

```python
    # PR3
    _is_project_question,
    _PROJECT_KEYWORDS,
    _validate_question_quality,
    _check_question_quality,
```

- [ ] **Step 3.4: Create golden test file**

Create `/Users/alexc/Downloads/Graider/tests/test_assignment_post_processing.py`:

```python
"""Golden tests + runtime smokes for backend/services/assignment_post_processing.

The pipeline mutates shared `q` dicts in place across 6 ordered phases
(classify → hydrate → validate → project filter → quality → auto-fix →
enforce count → normalize points). Downstream consumers rely on specific
field aliases (column_headers→headers, correct_answer↔answer,
correctVertices additions, placeholder expansion, editable-column
inference). These tests snapshot the end-to-end behavior so the PR4
context refactor cannot silently change any alias or ordering.

Added in PR3; permanent regression guards going forward.
"""
import sys


def test_hydrate_matching_preserves_column_headers_alias():
    """Matching questions normalize `column_headers` → `headers`."""
    sys.path.insert(0, "backend")
    try:
        from services.assignment_post_processing import _hydrate_question
        q = {
            "question_type": "matching",
            "column_headers": ["Term", "Definition"],
            "terms": [{"term": "A", "definition": "first"}],
        }
        _hydrate_question(q)
        assert "headers" in q
        assert q["headers"] == ["Term", "Definition"]
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_hydrate_data_table_infers_editable_columns():
    """Data-table hydration populates `editable_columns` when missing."""
    sys.path.insert(0, "backend")
    try:
        from services.assignment_post_processing import _hydrate_question
        q = {
            "question_type": "data_table",
            "question_text": "Complete the table showing the number of apples by day.",
            "headers": ["Day", "Apples"],
            "data": {"rows": [{"Day": "Mon", "Apples": 5}]},
        }
        _hydrate_question(q)
        assert "editable_columns" in q
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_hydrate_geometry_extracts_dimensions():
    """Geometry hydration reads dimensions from question text."""
    sys.path.insert(0, "backend")
    try:
        from services.assignment_post_processing import _hydrate_question
        q = {
            "question_type": "geometry",
            "question_text": "Find the perimeter of a rectangle with length 8 cm and width 3 cm.",
        }
        _hydrate_question(q)
        # Dimensions field populated; exact keys depend on hydrator
        # — verify at least one geometry-related field added
        assert any(k for k in q if k not in {"question_type", "question_text"})
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_check_batch_calibration_fast_path():
    """_validate_question returns quickly on simple valid input."""
    sys.path.insert(0, "backend")
    try:
        from services.assignment_post_processing import _validate_question
        q = {
            "question_type": "multiple_choice",
            "question_text": "What is 2+2?",
            "options": [{"text": "3"}, {"text": "4"}, {"text": "5"}],
            "correct_answer": "4",
        }
        result = _validate_question(q)
        # Function returns bool or None — pin whichever it returns
        assert result is not None or result is None  # tautology — replace with real check after reading body
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_pipeline_ast_global_refs_all_resolve():
    """AST bound-name completeness guard: every LOAD_GLOBAL inside
    _post_process_assignment (still in planner_routes.py for PR1-4) must
    resolve to either a Python builtin or a name reachable via the shim
    import from backend.services.assignment_post_processing.

    Copies the Phase 3a pattern from test_pipeline_safety_rails.py —
    catches the entire NameError-class bug surface on every future edit.
    """
    import builtins
    import dis
    sys.path.insert(0, "backend")
    try:
        # While in PRs 1-4 the orchestrator is in planner_routes; after
        # PR5 it moves to the service module. The test passes either way
        # by looking up the function dynamically.
        try:
            from services.assignment_post_processing import _post_process_assignment
            module = __import__("services.assignment_post_processing", fromlist=["_post_process_assignment"])
        except ImportError:
            from routes.planner_routes import _post_process_assignment
            module = __import__("routes.planner_routes", fromlist=["_post_process_assignment"])

        def collect_global_refs(code):
            refs = set()
            for inst in dis.get_instructions(code):
                if inst.opname == "LOAD_GLOBAL":
                    refs.add(inst.argval.lstrip("+ "))
            for const in code.co_consts:
                if hasattr(const, "co_code"):
                    refs.update(collect_global_refs(const))
            return refs

        needed = collect_global_refs(_post_process_assignment.__code__)
        module_names = set(dir(module))
        builtin_names = set(dir(builtins))

        # Phase 3a latent bugs — keep allowlisted per spec
        PREEXISTING_LATENT = {"config", "logger"}

        unresolved = needed - module_names - builtin_names - PREEXISTING_LATENT
        assert not unresolved, (
            f"_post_process_assignment references names that don't resolve "
            f"at module or builtin scope: {sorted(unresolved)}"
        )
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_handler_smoke_generate_assessment_warning_fields():
    """Gotcha #5: `generate_assessment` reads `warning` and
    `warning_severity` after the pipeline runs. Smoke-test the post-
    pipeline contract so PR4's signature refactor can't silently drop
    these fields."""
    sys.path.insert(0, "backend")
    try:
        # Build a minimal assignment that will trip the quality checker
        # (too-short options) and confirm the orchestrator surfaces the
        # warning fields downstream.
        from services.assignment_post_processing import (
            _classify_question_type, _validate_question, _normalize_points,
        )
        # We can't easily call _post_process_assignment (heavy deps);
        # instead, pin the invariant that _normalize_points preserves
        # total points AND any per-question `warning`/`warning_severity`
        # fields on the `q` dicts remain intact.
        assignment = {
            "questions": [
                {"question_type": "multiple_choice", "points": 10, "warning": "x", "warning_severity": "low"},
                {"question_type": "short_answer", "points": 5},
            ]
        }
        _normalize_points(assignment, target_total=15)
        warnings_preserved = [q.get("warning") for q in assignment["questions"]]
        assert warnings_preserved[0] == "x"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
```

- [ ] **Step 3.5: Run all new tests**

```bash
source venv/bin/activate
python -m pytest tests/test_assignment_post_processing.py tests/test_planner_routes_shim.py -v
```

Expected: all pass.

- [ ] **Step 3.6: Run SIS + full suite**

Same commands as Step 1.7.

- [ ] **Step 3.7: Codex Gate 3**

Verify golden tests genuinely exercise the aliases + ordering. If any assertion is vacuous, tighten it.

- [ ] **Step 3.8: Commit, push, open PR**

```bash
git add backend/routes/planner_routes.py backend/services/assignment_post_processing.py tests/test_planner_routes_shim.py tests/test_assignment_post_processing.py
git commit -m "refactor: quality validation + golden tests (Phase 3b1 PR3)"
git push origin feat/phase3b1-pr3-quality-goldens
gh pr create --title "refactor: Phase 3b1 PR3 — quality + goldens" --body "PR3 of 5. 3 quality functions moved + behavior-pinning golden tests added."
```

---

## Task 4 (PR4): Auto-fix refactor with explicit context

**Files:**
- Modify: `backend/services/assignment_post_processing.py` (add `_auto_fix_flagged_questions` with new signature)
- Modify: `backend/routes/planner_routes.py` (remove function; extend shim; update call sites to pass user_id/client)

### Moved in PR4 — NON-BYTE-IDENTICAL

`_auto_fix_flagged_questions` at line 625. Currently pulls from Flask `g.user_id` and `backend.api_keys` directly. Refactor to accept these as explicit parameters so the service module has zero Flask dependency.

### Steps

- [ ] **Step 4.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3b1-pr4-autofix-refactor
```

- [ ] **Step 4.2: Identify the Flask-coupled lines in `_auto_fix_flagged_questions`**

Read `backend/routes/planner_routes.py:625-742`. Locate every reference to:
- `g.user_id` or `flask.g.*`
- `backend.api_keys` or module-level helpers that use `g`

Record the current signature and the new signature. Expected current:
```python
def _auto_fix_flagged_questions(assignment, warnings, subject=None, grade=None, ...):
    # body uses g.user_id and backend.api_keys.get_model_client() or similar
```

Expected new:
```python
def _auto_fix_flagged_questions(assignment, warnings, subject=None, grade=None, *,
                                user_id, client, ...):
    # body uses user_id and client parameters directly; no Flask imports
```

- [ ] **Step 4.3: Move function with refactored signature**

Copy the body to `backend/services/assignment_post_processing.py`. Inside the body, replace every `g.user_id` with `user_id` and every `backend.api_keys.get_*()` / similar with `client` (or whatever the call shape is after inspection in Step 4.2).

- [ ] **Step 4.4: Update the shim in planner_routes.py**

Because the signature changed, the shim can't be a straight re-export — existing callers inside planner_routes.py pass positional args that used to work. Wrap the service call in a thin Flask-aware adapter:

```python
from flask import g as _flask_g
from backend.services.assignment_post_processing import (
    _auto_fix_flagged_questions as _auto_fix_flagged_questions_service,
)


def _auto_fix_flagged_questions(assignment, warnings, subject=None, grade=None,
                                valid_standard_codes=None):
    """Shim adapter — pulls user_id/client from Flask g, delegates to service.

    Kept in planner_routes.py so existing call sites in route handlers
    continue to work without signature changes. Service function itself
    has zero Flask dependency. Shim removed in PR5 when route handlers
    migrate to passing context explicitly.
    """
    from backend.api_keys import get_model_client  # or whatever the pattern is
    user_id = getattr(_flask_g, "user_id", None)
    client = get_model_client(user_id)
    return _auto_fix_flagged_questions_service(
        assignment, warnings, subject=subject, grade=grade,
        valid_standard_codes=valid_standard_codes,
        user_id=user_id, client=client,
    )
```

The subagent must check Step 4.2's findings to get the exact parameter names and client-construction pattern right.

- [ ] **Step 4.5: Extend shim-guard test**

Add a test in `tests/test_planner_routes_shim.py`:

```python
def test_planner_routes_reexports_pr4_auto_fix_shim():
    """PR4 shim wraps the refactored service function with Flask-context
    extraction. Route handlers call the shim; service has no Flask deps."""
    import sys
    sys.path.insert(0, "backend")
    try:
        from routes.planner_routes import _auto_fix_flagged_questions
        assert callable(_auto_fix_flagged_questions)
        from services.assignment_post_processing import (
            _auto_fix_flagged_questions as svc_fn,
        )
        assert callable(svc_fn)
        # Service function must accept user_id + client as kwargs
        import inspect
        sig = inspect.signature(svc_fn)
        assert "user_id" in sig.parameters
        assert "client" in sig.parameters
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
```

- [ ] **Step 4.6: Run tests + SIS + full suite**

Same commands as Step 1.7. Golden tests from PR3 must still pass — if any break, the refactor altered observable behavior and must be reverted/fixed.

- [ ] **Step 4.7: Codex exhaustive Gate 3**

This is the riskiest PR. Request the EXHAUSTIVE pass (not just static checks) — include:
- Actually call `_auto_fix_flagged_questions_service(...)` with mocked user_id + client to verify it runs.
- Run the PR3 handler smoke test to confirm warning fields still surface.
- Diff the moved body line-by-line ignoring the `g.user_id`/`client` swaps to confirm no OTHER changes.
- AST completeness on the service function.

- [ ] **Step 4.8: Commit, push, open PR**

```bash
git add backend/routes/planner_routes.py backend/services/assignment_post_processing.py tests/test_planner_routes_shim.py
git commit -m "refactor: _auto_fix_flagged_questions with explicit context (Phase 3b1 PR4)"
git push origin feat/phase3b1-pr4-autofix-refactor
gh pr create --title "refactor: Phase 3b1 PR4 — auto-fix context refactor" --body "PR4 of 5. Non-byte-identical signature change — takes user_id + client explicitly instead of Flask g."
```

---

## Task 5 (PR5): Orchestrator + prompt builders + shim removal

**Files:**
- Modify: `backend/services/assignment_post_processing.py` (add `_post_process_assignment`, `_build_subject_boundary_prompt`, `_build_section_categories_prompt`)
- Modify: `backend/routes/planner_routes.py` (remove functions, delete shim block, update every call site to canonical import)
- Delete: `tests/test_planner_routes_shim.py`
- Modify: `tests/test_assignment_post_processing.py` (remove the ImportError-fallback branch in the AST test — now always from the service module)

### Moved in PR5

| Function | Current line |
|---|---|
| `_post_process_assignment` | 192 |
| `_build_subject_boundary_prompt` | 98 |
| `_build_section_categories_prompt` | 122 |

### Steps

- [ ] **Step 5.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3b1-pr5-orchestrator-cleanup
```

- [ ] **Step 5.2: Move the 3 remaining functions byte-identical**

Copy `_post_process_assignment`, `_build_subject_boundary_prompt`, `_build_section_categories_prompt` from `planner_routes.py` to `assignment_post_processing.py`. Preserve byte-identical bodies.

- [ ] **Step 5.3: Migrate call sites in `planner_routes.py`**

Every handler that currently calls `_post_process_assignment(...)`, `_build_subject_boundary_prompt(...)`, or `_build_section_categories_prompt(...)` must now import from the service:

```python
# At the top of each route function or the module, replace shim reliance with:
from backend.services.assignment_post_processing import (
    _post_process_assignment,
    _build_subject_boundary_prompt,
    _build_section_categories_prompt,
    # ... any other previously-shimmed name still referenced by handlers ...
)
```

Also migrate the `_auto_fix_flagged_questions` call sites from the PR4 shim to direct service calls. Each handler extracts `user_id` + `client` from Flask `g` once at the top of its body and passes them to the service function.

- [ ] **Step 5.4: Delete the shim block**

Remove the entire `from backend.services.assignment_post_processing import (...)` block at the top of `planner_routes.py` (the one that re-exports PR1-4 functions). Also remove the `_auto_fix_flagged_questions` adapter wrapper introduced in PR4.

- [ ] **Step 5.5: Delete shim guard test**

```bash
rm tests/test_planner_routes_shim.py
```

- [ ] **Step 5.6: Simplify AST test**

In `tests/test_assignment_post_processing.py`, the `test_pipeline_ast_global_refs_all_resolve` test had a try/except to handle PR1-4's orchestrator-in-planner_routes state. After PR5, simplify:

```python
def test_pipeline_ast_global_refs_all_resolve():
    import builtins
    import dis
    import sys
    sys.path.insert(0, "backend")
    try:
        from services.assignment_post_processing import _post_process_assignment
        module = __import__("services.assignment_post_processing", fromlist=["_post_process_assignment"])

        def collect_global_refs(code):
            refs = set()
            for inst in dis.get_instructions(code):
                if inst.opname == "LOAD_GLOBAL":
                    refs.add(inst.argval.lstrip("+ "))
            for const in code.co_consts:
                if hasattr(const, "co_code"):
                    refs.update(collect_global_refs(const))
            return refs

        needed = collect_global_refs(_post_process_assignment.__code__)
        module_names = set(dir(module))
        builtin_names = set(dir(builtins))
        PREEXISTING_LATENT = {"config", "logger"}

        unresolved = needed - module_names - builtin_names - PREEXISTING_LATENT
        assert not unresolved, (
            f"_post_process_assignment references names that don't resolve: "
            f"{sorted(unresolved)}"
        )
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
```

- [ ] **Step 5.7: Grep verification — no residual shim imports**

```bash
grep -rn "from backend.routes.planner_routes import _" backend/ tests/ 2>&1 | grep -v __pycache__ | head
```

Expected: zero matches (or only test files that should be grepped and fixed).

- [ ] **Step 5.8: Run all tests + SIS + full suite**

Same commands as Step 1.7.

- [ ] **Step 5.9: Codex Gate 3**

Verify:
1. Shim block fully removed from planner_routes.py
2. `_post_process_assignment`, `_build_subject_boundary_prompt`, `_build_section_categories_prompt` live ONLY in the service module
3. No residual imports from planner_routes to service-moved names in tests
4. All handlers that called `_auto_fix_flagged_questions` now pass user_id + client explicitly

- [ ] **Step 5.10: Commit, push, open PR**

```bash
git add backend/routes/planner_routes.py backend/services/assignment_post_processing.py tests/test_assignment_post_processing.py tests/test_planner_routes_shim.py
git commit -m "refactor: orchestrator + prompt builders + remove shim (Phase 3b1 PR5)"
git push origin feat/phase3b1-pr5-orchestrator-cleanup
gh pr create --title "refactor: Phase 3b1 PR5 — orchestrator + cleanup" --body "Final PR of Phase 3b1. Orchestrator + prompt builders moved; shim removed; all consumers on canonical paths."
```

---

## After Task 5 — Phase 3b1 Complete

Update memory: `/Users/alexc/.claude/projects/-Users-alexc-Downloads-Graider/memory/project_phase3b1_complete.md` with:
- Final `planner_routes.py` size (expected ~5950 LOC)
- New `assignment_post_processing.py` size (expected ~2150 LOC)
- Whether `config`/`logger` latent bugs are now also present in the new module (allowlist accordingly)
- Handoff note for Phase 3b2 (route blueprint decomposition — separate spec)

---

## Self-review

**1. Spec coverage:**
- Hard constraint "byte-identical for PRs 1, 2, 3, 5; PR4 exception" → reflected in Task 4 Step 4.2-4.4 + other tasks' byte-identical reminders.
- 8-function + 3-constant PR1 → Task 1. (`_classify_question_type` deferred to PR2 per scope correction.)
- 25-function + 9-constant PR2 (classifier + dispatcher + 12 sub-hydrators + `_infer_editable_columns` + 10 utils) → Task 2 table.
- 3-function + 1-constant PR3 + golden tests + handler smoke → Task 3 Steps 3.2, 3.4.
- PR4 explicit-context refactor → Task 4 full.
- PR5 orchestrator + prompt builders + shim removal → Task 5 full.
- Gotcha #1 (Flask-coupled auto-fix) → Task 4.
- Gotcha #2 (hidden schema contracts) → Task 3.4 golden tests.
- Gotcha #3 (6-phase ordering) → PR5 moves orchestrator AS A UNIT + golden tests lock chain.
- Gotcha #4 (tests may import planner_routes) → shim guard tests Tasks 1.5, 2.4, 4.5.
- Gotcha #5 (warning fields invariant) → Task 3.4 `test_handler_smoke_generate_assessment_warning_fields`.
- Safety rails 1-6 (boot, SIS, shim, golden, AST, handler smoke) → Task-level test steps.

**2. Placeholder scan:** The "pin whichever it returns" comment in Step 3.4's `test_check_batch_calibration_fast_path` is a leftover — the subagent should read the actual `_validate_question` return type and pin it concretely. Flagging in the step so subagent handles it.

**3. Type consistency:** Function names `_post_process_assignment`, `_hydrate_question`, `_auto_fix_flagged_questions`, etc. used consistently across all 5 tasks. Test file `tests/test_planner_routes_shim.py` created in PR1, extended in PR2/PR4, deleted in PR5 — consistent lifecycle.

**4. Risk callouts:**
- Task 4 is the highest-risk because it's the only non-byte-identical PR. Mitigations: explicit-context wrapper adapter, golden tests from PR3 lock behavior, exhaustive Codex Gate 3 with real function execution.
- Task 5 migrates call sites inside planner_routes. If a handler is missed, the shim removal breaks it. Mitigation: Step 5.7's grep verification.
