"""Phase 3b1 PR5 — permanent service-module contract tests.

After PR5 the transitional shim in `backend/routes/planner_routes.py` is
removed; the post-processing pipeline lives entirely in
`backend/services/assignment_post_processing.py`.

The tests in this file are the permanent safety rails that outlive the
shim:

1. PR1 helpers execute at runtime — guards against silent NameError
   regressions from future rearrangement of the service module.
2. Every bound-name reference in every function defined in the service
   module resolves to a module-global or builtin — AST-level completeness
   guard that would have caught the PR1 scope bug.
3. `_auto_fix_flagged_questions` in the service module retains its
   explicit-context signature (`*, user_id, client`). Flask context
   extraction lives in `planner_routes._get_openai_context()` and is
   passed into `_post_process_assignment` at each route-handler call site.
"""
import types
import dis
import builtins


# ── Test 1: PR1 leaf helpers still execute cleanly via service module ────

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


# ── Test 2: AST bound-name completeness for the entire service module ────

def test_service_module_global_refs_all_resolve():
    """Walk every function defined in assignment_post_processing via dis, verify all
    LOAD_GLOBAL instructions resolve to a name in the module's namespace or builtins.

    Only functions whose __module__ matches the service module are inspected —
    imported helpers like `with_retry` reference names in *their* module's namespace,
    not ours, and would produce spurious failures.
    """
    import backend.services.assignment_post_processing as svc

    builtin_names = set(dir(builtins))
    module_names = set(vars(svc).keys())

    unresolved = []
    for attr_name in dir(svc):
        obj = getattr(svc, attr_name)
        if not callable(obj) or not isinstance(obj, types.FunctionType):
            continue
        # Skip functions imported from other modules — they resolve their globals
        # in their own module namespace, not ours.
        if getattr(obj, '__module__', None) != svc.__name__:
            continue
        for instr in dis.get_instructions(obj):
            if instr.opname == 'LOAD_GLOBAL':
                name = instr.argval
                if name not in module_names and name not in builtin_names:
                    unresolved.append((attr_name, name))

    assert unresolved == [], f"Unresolved LOAD_GLOBAL references: {unresolved}"


# ── Test 3: explicit-context contract for auto-fix + orchestrator ────────

def test_auto_fix_and_orchestrator_explicit_context_contract():
    """Service module exposes explicit-context kwargs; Flask extraction lives in routes."""
    import inspect
    from backend.services.assignment_post_processing import (
        _auto_fix_flagged_questions,
        _post_process_assignment,
    )
    from backend.routes.planner_routes import _get_openai_context

    # _auto_fix_flagged_questions: keyword-only user_id + client
    fix_sig = inspect.signature(_auto_fix_flagged_questions)
    assert fix_sig.parameters['user_id'].kind == inspect.Parameter.KEYWORD_ONLY
    assert fix_sig.parameters['client'].kind == inspect.Parameter.KEYWORD_ONLY

    # _post_process_assignment: keyword-only user_id + client pass-through
    pp_sig = inspect.signature(_post_process_assignment)
    assert pp_sig.parameters['user_id'].kind == inspect.Parameter.KEYWORD_ONLY
    assert pp_sig.parameters['client'].kind == inspect.Parameter.KEYWORD_ONLY

    # _get_openai_context is the route-side Flask extraction helper
    ctx_sig = inspect.signature(_get_openai_context)
    assert len(ctx_sig.parameters) == 0  # zero-arg helper returns (user_id, client)

    # Service module has NO Flask imports in _auto_fix_flagged_questions body
    import dis
    fix_globals = {
        instr.argval for instr in dis.get_instructions(_auto_fix_flagged_questions)
        if instr.opname == 'LOAD_GLOBAL'
    }
    assert 'g' not in fix_globals
    assert 'flask' not in fix_globals
