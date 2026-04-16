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
3. The adapter/service pair for `_auto_fix_flagged_questions` keeps its
   expected shape (service has explicit-context signature; adapter in
   planner_routes has the Flask-coupled signature).
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


# ── Test 3: adapter/service pair for _auto_fix_flagged_questions ─────────

def test_pr4_auto_fix_has_service_and_adapter():
    """Service module has explicit-context signature; planner_routes has Flask adapter."""
    import inspect
    from backend.services.assignment_post_processing import (
        _auto_fix_flagged_questions as service_fn,
    )
    from backend.routes.planner_routes import (
        _auto_fix_flagged_questions as adapter_fn,
    )

    # Service function: keyword-only user_id + client params
    service_sig = inspect.signature(service_fn)
    assert 'user_id' in service_sig.parameters
    assert 'client' in service_sig.parameters
    assert service_sig.parameters['user_id'].kind == inspect.Parameter.KEYWORD_ONLY
    assert service_sig.parameters['client'].kind == inspect.Parameter.KEYWORD_ONLY

    # Adapter function: NO user_id/client in signature (pulls from Flask g internally)
    adapter_sig = inspect.signature(adapter_fn)
    assert 'user_id' not in adapter_sig.parameters
    assert 'client' not in adapter_sig.parameters

    # They are NOT the same object — adapter wraps service
    assert service_fn is not adapter_fn
