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
