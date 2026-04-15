"""Permanent safety rails for backend/grading/pipeline.py.

Carried forward from the transitional tests/test_grading_shims.py
(deleted in Phase 3a PR4). These 4 tests guard against bug classes we
actually hit during the Phase 3a refactor and will catch future
NameError / ImportError / branch-coverage regressions in pipeline.py
without needing real grading fixtures or API keys.
"""
import sys


def test_pipeline_runtime_smoke():
    """Regression guard: exercise the code paths that previously NameError'd
    at runtime because DOCUMENTS_DIR and _check_batch_calibration were only
    defined in backend/app.py, not in the extracted pipeline module.

    Module-import alone doesn't catch these — they only fire when a specific
    code path inside _run_grading_thread_inner actually executes. This test
    calls the helpers directly to verify name resolution.
    """
    sys.path.insert(0, "backend")
    try:
        from grading import pipeline
        # Module-level symbols that _run_grading_thread_inner needs at runtime
        assert hasattr(pipeline, "DOCUMENTS_DIR"), "pipeline.DOCUMENTS_DIR must exist"
        assert hasattr(pipeline, "_check_batch_calibration"), "pipeline._check_batch_calibration must exist"

        # Exercise load_support_documents_for_grading to prove DOCUMENTS_DIR
        # resolves without NameError when the function body reads it.
        result = pipeline.load_support_documents_for_grading("NonExistentSubject")
        assert isinstance(result, str)

        # Exercise _check_batch_calibration fast-path (empty results → early return)
        calib = pipeline._check_batch_calibration([])
        assert calib == {"calibrated": True, "concerns": []}
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_check_batch_calibration_branch_coverage():
    """Exercise every branch of _check_batch_calibration so future refactors
    can't silently break one without the test catching it."""
    sys.path.insert(0, "backend")
    try:
        from grading import pipeline
        fn = pipeline._check_batch_calibration

        # Fast path: < 5 graded results (after filtering ERROR/etc)
        short = [{"score": 85, "letter_grade": "B"} for _ in range(3)]
        assert fn(short) == {"calibrated": True, "concerns": []}

        # Excluded results don't count toward the 5-score threshold
        skipped = [{"score": 85, "letter_grade": "ERROR"}] * 10
        assert fn(skipped) == {"calibrated": True, "concerns": []}

        # Healthy distribution → calibrated
        normal = [{"score": s, "letter_grade": "B"} for s in [70, 75, 78, 82, 85, 88]]
        r = fn(normal)
        assert r["calibrated"] is True
        assert r["concerns"] == []
        assert r["ai_flagged_count"] == 0

        # Mean too high → concern
        high = [{"score": s, "letter_grade": "A"} for s in [96, 97, 98, 99, 100]]
        r = fn(high)
        assert r["calibrated"] is False
        assert any("unusually high" in c for c in r["concerns"])

        # Mean too low → concern
        low = [{"score": s, "letter_grade": "F"} for s in [40, 45, 50, 52, 54]]
        r = fn(low)
        assert r["calibrated"] is False
        assert any("unusually low" in c for c in r["concerns"])

        # Low stdev with 10+ scores → uniform-score concern
        uniform = [{"score": 80 + (i % 3), "letter_grade": "B"} for i in range(12)]
        r = fn(uniform)
        assert any("suspiciously uniform" in c for c in r["concerns"])

        # Elevated AI-flagged ratio → concern
        ai_heavy = [
            {"score": 80 + i, "letter_grade": "B",
             "ai_detection": {"flag": "likely"}}
            for i in range(6)
        ]
        r = fn(ai_heavy)
        assert r["ai_flagged_count"] == 6
        assert any("AI/plagiarism" in c for c in r["concerns"])

        # Score coercion from strings (AI sometimes returns "85")
        stringy = [{"score": "85", "letter_grade": "B"} for _ in range(5)]
        r = fn(stringy)
        assert r["calibrated"] is True or "unusually" not in "".join(r["concerns"])
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_pipeline_lazy_imports_all_resolve():
    """Safety rail: `_run_grading_thread_inner` performs ~20 lazy imports
    inside its body (e.g., `from assignment_grader import grade_multipass`).
    Module-level imports are already covered by the AST global-refs test;
    these INLINE imports only fire when a specific code path executes,
    so a broken import path could slip past unit tests and surface only
    during a real grading run.

    AST-walks every `Import` / `ImportFrom` node inside the function and
    every nested function, then uses importlib.util.find_spec to verify
    each referenced module is discoverable on the configured sys.path.
    """
    import ast
    import importlib.util

    sys.path.insert(0, "backend")
    try:
        from grading import pipeline

        source = open(pipeline.__file__).read()
        tree = ast.parse(source)

        # Find _run_grading_thread_inner
        target_fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_grading_thread_inner":
                target_fn = node
                break
        assert target_fn is not None, "_run_grading_thread_inner not found in pipeline.py"

        # Collect every module name referenced by Import/ImportFrom inside
        # the function (including nested functions).
        modules_to_resolve = set()
        for node in ast.walk(target_fn):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules_to_resolve.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    # Relative import (e.g., `from .foo import bar`) —
                    # skip; these are relative to the containing package.
                    continue
                if node.module:
                    modules_to_resolve.add(node.module)

        unresolved = []
        for mod in sorted(modules_to_resolve):
            try:
                spec = importlib.util.find_spec(mod)
                if spec is None:
                    unresolved.append(mod)
            except (ModuleNotFoundError, ValueError, ImportError):
                unresolved.append(mod)

        assert not unresolved, (
            f"pipeline._run_grading_thread_inner has lazy imports that don't "
            f"resolve on the current sys.path: {unresolved}\n"
            f"These would raise ImportError at runtime when the branch that "
            f"imports them executes (even though module-level imports pass)."
        )
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_rubric_formatter_extraction_smoke():
    """Phase 3a PR4 extracted format_rubric_for_prompt from pipeline.py's
    nested scope into backend/services/rubric_formatting.py. This test:

    1. Imports the function from its new canonical location (the same path
       portal_grading.py:380 now uses — this was a broken import on main
       since the function was always nested).
    2. Calls it with a sample rubric dict to confirm the extracted body
       still produces a formatted prompt string (no behavior drift from
       the dedent / extraction).
    3. Confirms None-return for empty rubric (the early-return branch).
    """
    sys.path.insert(0, "backend")
    try:
        # The exact import path portal_grading.py:380 uses post-PR4
        from backend.services.rubric_formatting import format_rubric_for_prompt

        # Empty rubric → None per the early-return branch
        assert format_rubric_for_prompt(None) is None
        assert format_rubric_for_prompt({}) is None
        assert format_rubric_for_prompt({"categories": []}) is None

        # Real rubric → formatted prompt string with key markers
        rubric = {
            "categories": [
                {"name": "Content", "weight": 40, "description": "Accuracy"},
                {"name": "Mechanics", "weight": 30, "description": "Grammar"},
                {"name": "Organization", "weight": 30, "description": "Structure"},
            ],
            "generous": True,
        }
        result = format_rubric_for_prompt(rubric)
        assert isinstance(result, str)
        assert "GRADING RUBRIC" in result
        assert "Total Points: 100" in result  # 40 + 30 + 30
        assert "CONTENT" in result  # name uppercased
        assert "ENCOURAGING and GENEROUS" in result  # generous=True branch

        # Strict mode flips the style line
        rubric_strict = {**rubric, "generous": False}
        strict_result = format_rubric_for_prompt(rubric_strict)
        assert "Grade strictly" in strict_result
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_pipeline_global_refs_all_resolve():
    """AST / bytecode completeness guard: every name referenced via LOAD_GLOBAL
    inside _run_grading_thread_inner (and its nested functions) must resolve
    either to a Python builtin or to a module-level symbol in pipeline.py.

    This catches the class of NameError bug where a function body references
    a name (e.g., DOCUMENTS_DIR, _check_batch_calibration) that used to live
    in backend/app.py but wasn't carried into the extracted module. Runs
    statically — no mocking or fixtures required.

    LOAD_GLOBAL is exactly the bytecode op that fires when Python can't find
    a name as a local, parameter, or closure — so every LOAD_GLOBAL target
    must be resolvable at the module or builtin level.
    """
    import builtins
    import dis

    sys.path.insert(0, "backend")
    try:
        from grading import pipeline

        def collect_global_refs(code):
            """Walk a code object and every nested code object, yielding
            LOAD_GLOBAL argvals."""
            refs = set()
            for inst in dis.get_instructions(code):
                if inst.opname == "LOAD_GLOBAL":
                    # argval is the name being loaded (strip any leading '+'
                    # that Python 3.11+ uses for NULL-push variants)
                    refs.add(inst.argval.lstrip("+ "))
            for const in code.co_consts:
                if hasattr(const, "co_code"):
                    refs.update(collect_global_refs(const))
            return refs

        needed = collect_global_refs(pipeline._run_grading_thread_inner.__code__)
        module_names = set(dir(pipeline))
        builtin_names = set(dir(builtins))

        # Pre-existing latent bugs on main (caught by try/except; out of
        # Phase 3a scope). If either gets fixed in a later PR, remove from
        # this allowlist so the test starts enforcing.
        PREEXISTING_LATENT = {"config", "logger"}

        unresolved = needed - module_names - builtin_names - PREEXISTING_LATENT

        assert not unresolved, (
            "pipeline._run_grading_thread_inner references names that don't "
            "resolve to pipeline.py's module scope or a Python builtin "
            "(these would NameError at runtime):\n  "
            + "\n  ".join(sorted(unresolved))
            + "\nFix: add the missing import/definition to pipeline.py, or if "
            "the reference is truly a pre-existing latent bug wrapped in "
            "try/except, add it to PREEXISTING_LATENT with a comment."
        )
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
