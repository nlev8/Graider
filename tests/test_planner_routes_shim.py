"""Phase 3b1 PR1+PR2 shim guard tests.

Verifies that:
1. All PR1 (8 functions + 3 constants) re-export correctly from planner_routes.
2. The canonical source (assignment_post_processing) exports PR1 names directly.
3. PR1 functions actually execute without NameError.
4. All LOAD_GLOBAL references in the service module resolve at import time.
5. All PR2 (25 functions + 9 constants) re-export correctly from planner_routes.
6. The canonical source exports PR2 names directly.
7. _classify_question_type (PR2 risk driver) executes without NameError.
"""
import types
import dis
import builtins


# ── Test 1: planner_routes re-exports all PR1 names ──────────────────────

def test_planner_routes_reexports_pr1_leaf_helpers():
    import backend.routes.planner_routes as pr

    # 8 functions
    assert callable(pr._extract_usage)
    assert callable(pr._record_planner_cost)
    assert callable(pr._validate_question)
    assert callable(pr._build_question_count_instruction)
    assert callable(pr._count_questions)
    assert callable(pr._enforce_question_count)
    assert callable(pr._merge_usage)
    assert callable(pr._normalize_points)

    # 3 constants
    assert isinstance(pr.PLANNER_COSTS_FILE, str)
    assert isinstance(pr._REQUIRED_FIELDS, dict)
    assert isinstance(pr._DEFAULT_POINTS, dict)


# ── Test 2: canonical source exports the same names ───────────────────────

def test_assignment_post_processing_module_is_canonical():
    import backend.services.assignment_post_processing as svc

    assert callable(svc._extract_usage)
    assert callable(svc._record_planner_cost)
    assert callable(svc._validate_question)
    assert callable(svc._build_question_count_instruction)
    assert callable(svc._count_questions)
    assert callable(svc._enforce_question_count)
    assert callable(svc._merge_usage)
    assert callable(svc._normalize_points)

    assert isinstance(svc.PLANNER_COSTS_FILE, str)
    assert isinstance(svc._REQUIRED_FIELDS, dict)
    assert isinstance(svc._DEFAULT_POINTS, dict)


# ── Test 3: functions actually execute without NameError ──────────────────

def test_pr1_helpers_execute_without_nameerror(tmp_path):
    from backend.services.assignment_post_processing import (
        _validate_question,
        _count_questions,
        _build_question_count_instruction,
        _enforce_question_count,
        _normalize_points,
        _merge_usage,
        _extract_usage,
        _record_planner_cost,
    )

    # _validate_question — passes through without downgrade (has no required fields)
    q = {"question_type": "short_answer", "question": "test"}
    _validate_question(q)
    assert q["question_type"] == "short_answer"

    # _count_questions — empty assignment
    assert _count_questions({}) == 0

    # _build_question_count_instruction — output contains the count
    result = _build_question_count_instruction({"totalQuestions": 5})
    assert "5" in result

    # _enforce_question_count — empty sections returns (dict, None)
    assignment = {"sections": []}
    out, extra = _enforce_question_count(assignment, 10)
    assert isinstance(out, dict)
    assert extra is None

    # _normalize_points — empty sections, returns silently
    _normalize_points({"sections": []})

    # _merge_usage — both None → None
    assert _merge_usage(None, None) is None

    # _extract_usage — None input → None
    assert _extract_usage(None) is None

    # _record_planner_cost — writes to tmp file, verify no NameError
    import backend.services.assignment_post_processing as svc
    original = svc.PLANNER_COSTS_FILE
    svc.PLANNER_COSTS_FILE = str(tmp_path / "planner_costs.json")
    try:
        _record_planner_cost({"input_tokens": 10, "output_tokens": 5, "cost": 0.001, "total_tokens": 15})
    finally:
        svc.PLANNER_COSTS_FILE = original


# ── Test 4: AST bound-name completeness ───────────────────────────────────

def test_service_module_global_refs_all_resolve():
    """Walk every function in assignment_post_processing via dis, verify all
    LOAD_GLOBAL instructions resolve to a name in the module's namespace or builtins."""
    import backend.services.assignment_post_processing as svc

    builtin_names = set(dir(builtins))
    module_names = set(vars(svc).keys())

    unresolved = []
    for attr_name in dir(svc):
        obj = getattr(svc, attr_name)
        if not callable(obj) or not isinstance(obj, types.FunctionType):
            continue
        for instr in dis.get_instructions(obj):
            if instr.opname == 'LOAD_GLOBAL':
                name = instr.argval
                if name not in module_names and name not in builtin_names:
                    unresolved.append((attr_name, name))

    assert unresolved == [], f"Unresolved LOAD_GLOBAL references: {unresolved}"


# ── Test 5: planner_routes re-exports all PR2 names ───────────────────────

def test_planner_routes_reexports_pr2_names():
    """All 25 PR2 functions + 9 PR2 constants must be importable via planner_routes."""
    import re as _re
    import backend.routes.planner_routes as pr

    # 25 functions
    functions = [
        '_classify_question_type',
        '_hydrate_question',
        '_hydrate_matching',
        '_hydrate_geometry',
        '_infer_editable_columns',
        '_hydrate_data_table',
        '_hydrate_box_plot',
        '_hydrate_dot_plot',
        '_hydrate_stem_and_leaf',
        '_hydrate_transformations',
        '_hydrate_fraction_model',
        '_hydrate_unit_circle',
        '_hydrate_protractor',
        '_hydrate_grid_match',
        '_hydrate_inline_dropdown',
        '_detect_primary_shape',
        '_detect_mode',
        '_is_identification_question',
        '_infer_shape_answer',
        '_looks_like_graphing_question',
        '_extract_equations_from_text',
        '_split_markdown_table',
        '_extract_dimensions_from_text',
        '_extract_pythagorean_sides',
        '_compute_geometry_answer',
    ]
    for name in functions:
        obj = getattr(pr, name, None)
        assert callable(obj), f"{name} not callable on planner_routes"

    # 9 constants
    assert isinstance(pr._TRUSTED_AI_TYPES, frozenset)
    assert isinstance(pr._ANALYSIS_PATTERN, _re.Pattern)
    assert isinstance(pr._CALC_KEYWORDS, _re.Pattern)
    assert isinstance(pr._FORMULA_RE, _re.Pattern)
    assert isinstance(pr._SHAPE_KEYWORDS, list)
    assert isinstance(pr._POLYGON_SIDES, dict)
    assert isinstance(pr._MODE_KEYWORDS, list)
    assert isinstance(pr._ALL_GEOMETRY_TYPES, set)
    assert isinstance(pr._GEOMETRY_DEFAULTS, dict)


# ── Test 6: canonical path exports same PR2 names ─────────────────────────

def test_pr2_canonical_path_importable():
    """All PR2 names must be importable directly from assignment_post_processing."""
    import re as _re
    import backend.services.assignment_post_processing as svc

    functions = [
        '_classify_question_type',
        '_hydrate_question',
        '_hydrate_matching',
        '_hydrate_geometry',
        '_infer_editable_columns',
        '_hydrate_data_table',
        '_hydrate_box_plot',
        '_hydrate_dot_plot',
        '_hydrate_stem_and_leaf',
        '_hydrate_transformations',
        '_hydrate_fraction_model',
        '_hydrate_unit_circle',
        '_hydrate_protractor',
        '_hydrate_grid_match',
        '_hydrate_inline_dropdown',
        '_detect_primary_shape',
        '_detect_mode',
        '_is_identification_question',
        '_infer_shape_answer',
        '_looks_like_graphing_question',
        '_extract_equations_from_text',
        '_split_markdown_table',
        '_extract_dimensions_from_text',
        '_extract_pythagorean_sides',
        '_compute_geometry_answer',
    ]
    for name in functions:
        obj = getattr(svc, name, None)
        assert callable(obj), f"{name} not callable on service module"

    # 9 constants
    assert isinstance(svc._TRUSTED_AI_TYPES, frozenset)
    assert isinstance(svc._ANALYSIS_PATTERN, _re.Pattern)
    assert isinstance(svc._CALC_KEYWORDS, _re.Pattern)
    assert isinstance(svc._FORMULA_RE, _re.Pattern)
    assert isinstance(svc._SHAPE_KEYWORDS, list)
    assert isinstance(svc._POLYGON_SIDES, dict)
    assert isinstance(svc._MODE_KEYWORDS, list)
    assert isinstance(svc._ALL_GEOMETRY_TYPES, set)
    assert isinstance(svc._GEOMETRY_DEFAULTS, dict)


# ── Test 7: PR2 risk driver _classify_question_type executes ──────────────

def test_pr2_classify_executes_without_nameerror():
    """Guard against the PR1 scope bug: _classify_question_type must resolve
    all its 5 callees (_is_identification_question, _detect_primary_shape,
    _detect_mode, _looks_like_graphing_question, _extract_equations_from_text)
    at runtime. This test would have caught the PR1 scope error if the function
    had been wrongly moved alone."""
    from backend.services.assignment_post_processing import _classify_question_type

    q = {"question": "Solve for x: 2x + 4 = 10", "answer": "3"}
    # Function mutates q in place and returns None; just verify it runs without error.
    result = _classify_question_type(q)
    assert result is None
    assert 'question_type' in q
