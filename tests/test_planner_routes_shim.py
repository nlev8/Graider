"""Phase 3b1 PR1 shim guard tests.

Verifies that:
1. All 8 functions + 3 constants re-export correctly from planner_routes.
2. The canonical source (assignment_post_processing) exports them directly.
3. Each function actually executes without NameError.
4. All LOAD_GLOBAL references in the service module resolve at import time.
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
