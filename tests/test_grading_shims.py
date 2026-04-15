"""Temporary shim guard for Phase 3a transition.

Pins that backend.app continues to re-export state helpers from
backend.grading.state during PR2 and PR3. Deleted in PR4 when all
consumers have migrated to the canonical import paths.
"""
import importlib
import sys


def test_backend_app_reexports_grading_state_helpers():
    """During Phase 3a transition, `from backend.app import _get_state, ...`
    must still resolve. Protects portal_grading.py, assistant_tools_student.py,
    email_routes.py."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        for name in (
            "_get_state", "_get_lock", "_update_state", "reset_state",
            "_create_default_state", "_grading_states", "_grading_locks",
            "load_saved_results", "save_results",
        ):
            assert hasattr(backend_app, name), f"backend.app must re-export {name!r}"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_grading_state_module_is_canonical():
    """Canonical import path for PR4 consumers."""
    sys.path.insert(0, "backend")
    try:
        from grading import state as grading_state
        for name in (
            "_get_state", "_get_lock", "_update_state", "reset_state",
            "_create_default_state", "_grading_states", "_grading_locks",
            "load_saved_results", "save_results",
        ):
            assert hasattr(grading_state, name), f"backend.grading.state must define {name!r}"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_backend_app_reexports_grading_thread_and_pipeline_helpers():
    """Phase 3a PR3: thread wrapper + inner pipeline live in
    backend.grading.thread / backend.grading.pipeline. app.py keeps
    re-export shim for both until PR4."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        for name in ("run_grading_thread", "_run_grading_thread_inner"):
            assert hasattr(backend_app, name), f"backend.app must re-export {name!r}"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_grading_thread_module_is_canonical():
    """Canonical path for thread wrapper."""
    sys.path.insert(0, "backend")
    try:
        from grading import thread as grading_thread
        assert hasattr(grading_thread, "run_grading_thread")
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_grading_pipeline_module_is_canonical():
    """Canonical path for inner pipeline."""
    sys.path.insert(0, "backend")
    try:
        from grading import pipeline as grading_pipeline
        assert hasattr(grading_pipeline, "_run_grading_thread_inner")
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


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
        # Use scores in [60, 100] (valid mean range) but bunched tight
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
