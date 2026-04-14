# Phase 3a — backend/app.py Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `backend/app.py` from 3528 → ~1400 lines by extracting grading state + thread code into `backend/grading/` while establishing the Flask app-factory pattern. Zero behavior change. SIS compliance (Clever/ClassLink/OneRoster) stays green throughout.

**Architecture:** Four sequential PRs. PR1 introduces `create_app()` pattern with no code movement. PR2 extracts state + persistence helpers into `grading/state.py` with import shims in app.py. PR3 extracts thread + pipeline into `grading/thread.py` with shims. PR4 migrates consumers and removes shims.

**Tech Stack:** Python 3.14, Flask, pytest.

**Spec:** `docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md`

---

## File Structure

After all four PRs:

| File | Role | Size (approx) |
|---|---|---|
| `backend/app.py` | Factory (`create_app`), top-level middleware, error handlers, audit helpers, calibration helper, legacy route handlers not yet in blueprints | ~1400 LOC |
| `backend/grading/__init__.py` | Package marker + re-exports | ~20 LOC |
| `backend/grading/state.py` | `_grading_states`, `_grading_locks`, `_get_state`, `_get_lock`, `_update_state`, `reset_state`, `_create_default_state`, `load_saved_results`, `save_results` | ~220 LOC |
| `backend/grading/thread.py` | `run_grading_thread` (BYOK wrapper), `_run_grading_thread_inner` (with its nested `format_rubric_for_prompt` intact) | ~2100 LOC |
| `tests/test_app_boot.py` | Boot + route-count smoke tests (new) | ~40 LOC |
| `tests/test_grading_shims.py` | Verify backwards-compat shims work (temporary, deleted in PR4) | ~30 LOC |

## Hard constraints (enforced every PR)

- SIS compliance: 180/180 green at every step (`pytest tests/test_sso_contracts.py tests/test_clever_*.py tests/test_classlink_*.py tests/test_oneroster*.py tests/test_roster_sync.py tests/test_sis_alerting.py`).
- Coverage floor: CI fails below 32%.
- Boot: `python -c "import sys; sys.path.insert(0, 'backend'); from app import app; print(len(app.url_map._rules))"` returns an integer ≥ 250 every PR.
- Zero Clever / ClassLink / OneRoster / roster_sync / oneroster_gradebook file modifications (enforced via `git diff --name-only` in verification).
- Codex Gate 1 (plan preview) has already run; Codex Gate 3 (diff review) runs on each PR before merge.

---

## Task 1 (PR1): Introduce app-factory pattern — ZERO code movement to other files

**Files:**
- Modify: `backend/app.py` (restructure internally only; no extraction)
- Create: `tests/test_app_boot.py`

**Why:** Establishes `create_app()` entry point so later PRs have a clean seam for adding modules. Nothing is moved out of `app.py` in this PR — only internally reorganized.

- [ ] **Step 1.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr1-app-factory
```

- [ ] **Step 1.2: Write boot-check test FIRST (TDD)**

Create `/Users/alexc/Downloads/Graider/tests/test_app_boot.py`:

```python
"""Boot + route-count smoke tests for backend/app.py.

Phase 3a safety net: pin that the app still boots and has the expected
number of URL rules across the Phase 3a refactor. Line-shift-tolerant;
uses a floor rather than exact count.
"""
import importlib
import sys


def test_app_module_imports_cleanly():
    """Importing backend.app must not raise."""
    # Put backend/ on path (same as production entry point)
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        assert hasattr(backend_app, "app"), "Module must expose a Flask `app` instance"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_app_registers_expected_route_count():
    """Ensure the Flask app has at least 250 URL rules registered.
    This floors the count against accidental blueprint-registration regressions."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        rule_count = len(backend_app.app.url_map._rules)
        assert rule_count >= 250, f"Expected >= 250 rules, got {rule_count}"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_app_exposes_create_app_factory():
    """Phase 3a PR1 adds a create_app() factory. This test exists from PR1
    onward; before PR1 it would fail (function doesn't exist)."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        assert callable(backend_app.create_app), "create_app() must be callable"
        # The factory must be idempotent: calling it returns a Flask app
        # with registered routes.
        test_app = backend_app.create_app()
        assert len(test_app.url_map._rules) >= 250
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
```

- [ ] **Step 1.3: Run the new test — confirm the third test fails**

```bash
source venv/bin/activate
python -m pytest tests/test_app_boot.py -v
```

Expected: `test_app_module_imports_cleanly` and `test_app_registers_expected_route_count` PASS (app already boots and has routes). `test_app_exposes_create_app_factory` FAILS (create_app doesn't exist yet).

- [ ] **Step 1.4: Refactor app.py to introduce `create_app()` without moving code**

Open `/Users/alexc/Downloads/Graider/backend/app.py`.

Current state: `app = Flask(__name__, static_folder='static', static_url_path='')` at line 82, followed by top-level middleware / error handlers / function defs / state init / thread fns / blueprint registration at line 2055.

Goal: Wrap the Flask instantiation + middleware + blueprint registration inside `create_app()`. The function returns the same `app` instance. For backwards compatibility, keep `app = create_app()` at module level so `from backend.app import app` still works.

Conceptual shape after refactor (actual line numbers will differ):

```python
# ... all imports stay at top ...

def create_app():
    """Flask application factory.

    Returns the Flask app instance with middleware, error handlers, and
    route blueprints registered. Currently all code still lives in app.py;
    PRs 2-4 extract grading state and thread code into backend/grading/.
    """
    app = Flask(__name__, static_folder='static', static_url_path='')

    # Register middleware
    @app.after_request
    def set_security_headers(response):
        # ... existing body ...
        pass

    # Register error handlers
    @app.errorhandler(500)
    def handle_500(e):
        # ... existing body ...
        pass

    @app.errorhandler(404)
    def handle_404(e):
        # ... existing body ...
        pass

    # Register routes (blueprints)
    from routes import register_routes
    register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)

    # Register legacy route handlers that are still on app.py directly
    # (they must be moved INTO create_app's scope so they hit this app instance)
    _register_legacy_routes(app)

    return app


def _register_legacy_routes(app):
    """Legacy inline route handlers that haven't migrated to blueprints yet."""
    # All @app.route(...) defs currently at module level move here
    # ... exact bodies preserved ...
    pass


# Module-level app for backwards compat: `from backend.app import app` still works
app = create_app()


if __name__ == '__main__':
    # ... existing browser-open + app.run() ...
    app.run(host='0.0.0.0', port=3000, debug=False)
```

Key rule for this PR: ALL function bodies stay byte-for-byte identical. Only wrapping and call-order change. The state dict `_grading_states`, all state helper functions, `load_saved_results`, `save_results`, `run_grading_thread`, `_run_grading_thread_inner` stay at module level (unchanged). SIGTERM handler `_handle_sigterm` also stays at module level (it needs `_grading_states` which is module-level).

**Subtlety:** `@app.after_request`, `@app.errorhandler`, and `@app.route` decorators in the original code reference the module-level `app`. When we move these into `create_app()`, they now decorate the `app` that's in scope there (the local one). Because `create_app()` returns that same `app` instance and we assign `app = create_app()` at module level, the module-level `app` IS the one with all the decorators applied. No behavior change.

- [ ] **Step 1.5: Run the test — all three tests must now pass**

```bash
python -m pytest tests/test_app_boot.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 1.6: Run the full SIS compliance suite**

```bash
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_contract.py tests/test_classlink_sso_contract.py tests/test_clever_callback.py tests/test_clever_classes.py tests/test_clever_compliance.py tests/test_clever.py tests/test_clever_student_sso.py tests/test_classlink_sso.py tests/test_oneroster.py tests/test_oneroster_sync_grades.py tests/test_oneroster_gradebook.py tests/test_roster_sync.py tests/test_sis_alerting.py -q
```

Expected: **180 passed**.

- [ ] **Step 1.7: Run full backend test suite with coverage floor**

```bash
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x -m "not live" --cov=backend --cov-fail-under=32
```

Expected: all tests pass; coverage ≥ 32%.

- [ ] **Step 1.8: Manual boot smoke — start the dev server and verify SSO endpoints respond**

```bash
cd backend && source ../venv/bin/activate && python app.py &
sleep 3
curl -s http://localhost:3000/api/clever/login-url | head -c 200
curl -s http://localhost:3000/api/classlink/login-url | head -c 200
curl -s http://localhost:3000/api/oneroster/config | head -c 200
kill %1 2>/dev/null || pkill -f "python app.py"
cd ..
```

Expected: each curl returns a valid JSON response (not 404, not 500).

- [ ] **Step 1.9: Dispatch Codex Gate 3 diff review**

Ask Codex to review `git diff main...HEAD`. Requirements:
- Only `backend/app.py` and `tests/test_app_boot.py` changed.
- No Clever/ClassLink/OneRoster/roster_sync/oneroster_gradebook file in the diff.
- Function bodies inside the refactor are byte-identical to pre-refactor (no opportunistic fixes).

If Codex returns HOLD, address each finding and re-run steps 1.5-1.7 before re-sending.

- [ ] **Step 1.10: Commit, push, open PR**

```bash
git add backend/app.py tests/test_app_boot.py
git commit -m "$(cat <<'EOF'
refactor: introduce create_app() factory pattern (Phase 3a PR1)

Wraps Flask instantiation + middleware + error handlers + blueprint
registration inside create_app(). Module-level `app = create_app()`
preserves backwards-compat for `from backend.app import app`. Zero
code movement out of app.py; function bodies byte-identical.

Adds tests/test_app_boot.py pinning:
- Module imports cleanly
- URL rule count >= 250 (guards blueprint regression)
- create_app() factory is callable and returns a Flask app with routes

SIS compliance: 180/180 green. Coverage: unchanged.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr1-app-factory
gh pr create --title "refactor: introduce create_app() factory (Phase 3a PR1)" --body "Phase 3a PR1 of 4. Pure structural refactor; no code extraction yet. Establishes factory pattern for PR2-4."
```

Wait for CI green and user merge signoff.

---

## Task 2 (PR2): Extract state + persistence helpers to `backend/grading/state.py`

**Files:**
- Create: `backend/grading/__init__.py`
- Create: `backend/grading/state.py`
- Modify: `backend/app.py` (remove extracted code; add shim re-exports)
- Create: `tests/test_grading_shims.py` (temporary)

- [ ] **Step 2.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr2-state-extract
```

- [ ] **Step 2.2: Write the shim-guard test FIRST (TDD)**

Create `/Users/alexc/Downloads/Graider/tests/test_grading_shims.py`:

```python
"""Temporary shim guard for Phase 3a transition.

Pins that backend.app continues to re-export state helpers from
backend.grading.state during PR2 and PR3. Deleted in PR4 when all
consumers have migrated to the canonical import paths.
"""
import importlib
import sys


def test_backend_app_reexports_grading_state_helpers():
    """During Phase 3a transition, `from backend.app import _get_state, ...`
    must still resolve. This protects existing consumers at
    portal_grading.py, assistant_tools_student.py, email_routes.py."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        # Names that MUST remain importable from backend.app until PR4
        for name in (
            "_get_state", "_get_lock", "_update_state", "reset_state",
            "_create_default_state", "_grading_states", "_grading_locks",
            "load_saved_results", "save_results",
        ):
            assert hasattr(backend_app, name), f"backend.app must re-export {name!r} during PR2-3 transition"
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
```

- [ ] **Step 2.3: Run the test — both must fail (modules don't exist yet)**

```bash
source venv/bin/activate
python -m pytest tests/test_grading_shims.py -v
```

Expected: `test_grading_state_module_is_canonical` FAILS with ImportError. `test_backend_app_reexports_grading_state_helpers` currently PASSES (helpers still live in app.py) but we'll verify the shim still works after the move.

- [ ] **Step 2.4: Create the grading package**

```bash
mkdir -p backend/grading
```

- [ ] **Step 2.5: Create `backend/grading/__init__.py` (empty marker for now)**

Create `/Users/alexc/Downloads/Graider/backend/grading/__init__.py`:

```python
"""Graider grading package.

Extracted from backend/app.py during Phase 3a refactor.

- state.py: per-teacher grading state dict, locks, accessors, persistence
- thread.py: grading thread wrapper + inner pipeline (added in PR3)
"""
```

- [ ] **Step 2.6: Create `backend/grading/state.py` by moving code from `app.py`**

The code to move from `backend/app.py`:

- Lines 376–405: `load_saved_results()` function
- Lines 407–418: `save_results()` function
- Lines 420–421: `_grading_states = {}`, `_grading_locks = {}` module-level dicts
- Lines 423–424: `_state_registry_lock = threading.Lock()` (verify exact name; whatever lock protects the registry)
- Lines 425–443: `_create_default_state(teacher_id='local-dev')`
- Lines 445–453: `_get_state(teacher_id='local-dev')`
- Lines 455–459: `_get_lock(teacher_id='local-dev')`
- Lines 461–465: `_update_state(teacher_id='local-dev', **kwargs)`
- Lines 467–491: `reset_state(teacher_id='local-dev', clear_results=False)`

Create `/Users/alexc/Downloads/Graider/backend/grading/state.py` with a module docstring and ALL those symbols, byte-identical bodies. Carry any imports those functions rely on (e.g., `threading`, `json`, `os`, `pathlib.Path`, `datetime`, any `from backend.storage import ...` etc.). Copy the imports at the top of the file; don't remove them from app.py yet (PR2 leaves app.py's imports intact to keep the shim working).

Shape of `backend/grading/state.py`:

```python
"""Per-teacher grading state + persistence.

Extracted from backend/app.py in Phase 3a PR2. Keeps module-level dicts
and the thread-safe accessors exactly as they were at app.py head.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path

# ... any other imports the moved functions reference (storage, compliance, etc.) ...


def load_saved_results(teacher_id='local-dev'):
    """Exact body copied from backend/app.py:376-405."""
    # ... byte-identical to pre-refactor ...


def save_results(results, teacher_id='local-dev'):
    """Exact body copied from backend/app.py:407-418."""
    # ... byte-identical ...


# Module-level state dicts (moved from app.py:420-421)
_grading_states = {}
_grading_locks = {}
_state_registry_lock = threading.Lock()


def _create_default_state(teacher_id='local-dev'):
    """Exact body copied from backend/app.py:425-443."""
    # ... byte-identical ...


def _get_state(teacher_id='local-dev'):
    """Exact body copied from backend/app.py:445-453."""
    # ... byte-identical ...


def _get_lock(teacher_id='local-dev'):
    """Exact body copied from backend/app.py:455-459."""
    # ... byte-identical ...


def _update_state(teacher_id='local-dev', **kwargs):
    """Exact body copied from backend/app.py:461-465."""
    # ... byte-identical ...


def reset_state(teacher_id='local-dev', clear_results=False):
    """Exact body copied from backend/app.py:467-491."""
    # ... byte-identical ...
```

- [ ] **Step 2.7: Remove the moved code from app.py and add shim re-exports**

In `backend/app.py`:

1. Delete lines 376–491 (the functions and module-level dicts listed above) EXCEPT: keep any comments that aren't tied to the moved code.
2. At the same location, add a shim import line:

```python
# Phase 3a PR2: state moved to backend/grading/state.py
# Re-export for backwards compat until PR4 migrates consumers.
from grading.state import (
    load_saved_results,
    save_results,
    _grading_states,
    _grading_locks,
    _create_default_state,
    _get_state,
    _get_lock,
    _update_state,
    reset_state,
)
```

**Critical:** `register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)` at the former line 2055 still works because `_get_state` / `reset_state` / `_get_lock` are now imported into app.py's module namespace via the shim.

**Critical (SIGTERM):** The handler `_handle_sigterm` at the former line 2064-2069 walks `_grading_states` — that dict is now imported via shim, so the handler still sees it. No code change needed in the handler.

- [ ] **Step 2.8: Run shim-guard tests — both must now pass**

```bash
python -m pytest tests/test_grading_shims.py -v
```

Expected: both tests PASS.

- [ ] **Step 2.9: Run boot-check tests**

```bash
python -m pytest tests/test_app_boot.py -v
```

Expected: all 3 tests PASS (create_app still works, route count ≥ 250).

- [ ] **Step 2.10: Run SIS contract suite**

```bash
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_contract.py tests/test_classlink_sso_contract.py tests/test_clever_callback.py tests/test_clever_classes.py tests/test_clever_compliance.py tests/test_clever.py tests/test_clever_student_sso.py tests/test_classlink_sso.py tests/test_oneroster.py tests/test_oneroster_sync_grades.py tests/test_oneroster_gradebook.py tests/test_roster_sync.py tests/test_sis_alerting.py -q
```

Expected: **180 passed**.

- [ ] **Step 2.11: Run full backend suite with coverage floor**

```bash
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x -m "not live" --cov=backend --cov-fail-under=32
```

Expected: all pass, coverage ≥ 32%.

- [ ] **Step 2.12: Manual boot smoke — start server and hit /api/grade lightly**

```bash
cd backend && source ../venv/bin/activate && python app.py &
sleep 3
curl -s http://localhost:3000/api/status | head -c 300
curl -s http://localhost:3000/api/clever/login-url | head -c 200
kill %1 2>/dev/null || pkill -f "python app.py"
cd ..
```

Expected: `/api/status` returns a JSON state response (the state dict was correctly loaded via the shim path).

- [ ] **Step 2.13: Codex Gate 3 diff review**

Requirements:
- Only `backend/app.py`, `backend/grading/__init__.py`, `backend/grading/state.py`, `tests/test_grading_shims.py` changed.
- `backend/grading/state.py` function bodies are byte-identical to the deleted app.py lines.
- No Clever/ClassLink/OneRoster file modifications.
- `backend/app.py` re-export shim imports all 9 names.

- [ ] **Step 2.14: Commit, push, open PR**

```bash
git add backend/app.py backend/grading/__init__.py backend/grading/state.py tests/test_grading_shims.py
git commit -m "$(cat <<'EOF'
refactor: extract grading state + persistence to backend/grading/state.py (Phase 3a PR2)

Moves _grading_states, _grading_locks, _get_state, _get_lock,
_update_state, reset_state, _create_default_state, load_saved_results,
save_results from backend/app.py into backend/grading/state.py. Function
bodies byte-identical. backend/app.py keeps re-export shim for
backwards-compat with portal_grading, assistant_tools_student,
email_routes, register_routes injection, and SIGTERM handler.

Adds tests/test_grading_shims.py pinning both the canonical
backend.grading.state imports AND the transitional backend.app shim.

SIS compliance: 180/180 green. Coverage: >= 32%.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr2-state-extract
gh pr create --title "refactor: extract grading state to backend/grading/state.py (Phase 3a PR2)" --body "Phase 3a PR2 of 4. State + persistence extracted; shim in app.py keeps all existing consumers working."
```

Wait for CI + user merge signoff.

---

## Task 3 (PR3): Extract thread + inner pipeline to `backend/grading/thread.py`

**Files:**
- Create: `backend/grading/thread.py`
- Modify: `backend/app.py` (remove thread code; extend shim)

- [ ] **Step 3.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr3-thread-extract
```

- [ ] **Step 3.2: Extend `tests/test_grading_shims.py` to pin thread shim**

Add to `/Users/alexc/Downloads/Graider/tests/test_grading_shims.py`:

```python
def test_backend_app_reexports_grading_thread_helpers():
    """Phase 3a PR3: thread wrapper and inner pipeline live in
    backend.grading.thread. app.py keeps re-export shim until PR4."""
    import importlib
    import sys
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        for name in ("run_grading_thread", "_run_grading_thread_inner"):
            assert hasattr(backend_app, name), f"backend.app must re-export {name!r} during PR3 transition"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_grading_thread_module_is_canonical():
    """Canonical path for the thread wrapper + inner pipeline."""
    import sys
    sys.path.insert(0, "backend")
    try:
        from grading import thread as grading_thread
        for name in ("run_grading_thread", "_run_grading_thread_inner"):
            assert hasattr(grading_thread, name), f"backend.grading.thread must define {name!r}"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
```

- [ ] **Step 3.3: Run the new tests — both must fail**

```bash
python -m pytest tests/test_grading_shims.py::test_grading_thread_module_is_canonical -v
```

Expected: FAIL with ImportError (module doesn't exist yet).

- [ ] **Step 3.4: Create `backend/grading/thread.py`**

The code to move from `backend/app.py`:
- Lines 543–568: `run_grading_thread(...)` wrapper
- Lines 570–2053: `_run_grading_thread_inner(...)` (including its nested `format_rubric_for_prompt` at former line 587)
- All imports that `_run_grading_thread_inner` needs at the top of app.py (identify each one — e.g., `from backend.services.grading_service import ...`, `from backend.services.portal_grading import ...`, pandas, openpyxl, etc.)

Create `/Users/alexc/Downloads/Graider/backend/grading/thread.py`:

```python
"""Grading thread wrapper + inner pipeline.

Extracted from backend/app.py in Phase 3a PR3. The nested
format_rubric_for_prompt inside _run_grading_thread_inner moves along
with its parent. The ~2000-line inner function remains a single unit
(internal decomposition deferred per spec).
"""
# All imports _run_grading_thread_inner needs — copied from app.py top.
# Do NOT remove these imports from app.py yet; that happens in PR4.
import json
import os
import threading
from pathlib import Path

# Graider-internal imports that the grading thread uses:
from backend.grading.state import _get_state, _get_lock, save_results, _update_state
# ... all other service imports _run_grading_thread_inner references ...


def run_grading_thread(assignments_folder, output_folder, roster_file,
                       assignment_config=None, global_ai_notes='',
                       grading_period='Q3', grade_level='7',
                       subject='Social Studies', teacher_name='',
                       school_name='', selected_files=None,
                       ai_model='gpt-4o-mini', skip_verified=False,
                       class_period='', rubric=None, ensemble_models=None,
                       extraction_mode='structured', trusted_students=None,
                       grading_style='standard', teacher_id='local-dev',
                       user_api_keys=None):
    """Exact body from backend/app.py:543-568."""
    # ... byte-identical ...


def _run_grading_thread_inner(assignments_folder, output_folder, roster_file,
                              assignment_config=None, global_ai_notes='',
                              grading_period='Q3', grade_level='7',
                              subject='Social Studies', teacher_name='',
                              school_name='', selected_files=None,
                              ai_model='gpt-4o-mini', skip_verified=False,
                              class_period='', rubric=None, ensemble_models=None,
                              extraction_mode='structured', trusted_students=None,
                              grading_style='standard', teacher_id='local-dev'):
    """Exact body from backend/app.py:570-2053, including the nested
    format_rubric_for_prompt at former line 587."""
    # ... byte-identical, nested function and all ...
```

**Critical:** The body of `_run_grading_thread_inner` references `_get_state` — that now needs to come from `backend.grading.state`. The old code used the local module-level reference, which worked because `_get_state` was in app.py. Since we moved `_get_state` to `grading.state` in PR2, `thread.py` can import it directly. No behavior change.

**Critical (nested function):** The `def format_rubric_for_prompt` at former line 587 is local to `_run_grading_thread_inner`. It stays nested. It moves with its enclosing function. The `from backend.app import format_rubric_for_prompt` in `portal_grading.py:380` remains a pre-existing latent issue NOT fixed by this PR (the function was never at module level; that import has always failed when exercised). Document this in the PR body.

- [ ] **Step 3.5: Remove moved code from app.py; extend the shim**

In `backend/app.py`:

1. Delete lines 543–2053 (the two thread functions).
2. Extend the shim import (still at the same location PR2 introduced it):

```python
# Phase 3a: grading state + thread moved to backend/grading/.
# Re-export for backwards compat until PR4 migrates consumers.
from grading.state import (
    load_saved_results,
    save_results,
    _grading_states,
    _grading_locks,
    _create_default_state,
    _get_state,
    _get_lock,
    _update_state,
    reset_state,
)
from grading.thread import (
    run_grading_thread,
    _run_grading_thread_inner,
)
```

- [ ] **Step 3.6: Run the updated shim-guard tests**

```bash
python -m pytest tests/test_grading_shims.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 3.7: Run boot + SIS + full suite**

```bash
python -m pytest tests/test_app_boot.py -v
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_contract.py tests/test_classlink_sso_contract.py tests/test_clever_callback.py tests/test_clever_classes.py tests/test_clever_compliance.py tests/test_clever.py tests/test_clever_student_sso.py tests/test_classlink_sso.py tests/test_oneroster.py tests/test_oneroster_sync_grades.py tests/test_oneroster_gradebook.py tests/test_roster_sync.py tests/test_sis_alerting.py -q
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x -m "not live" --cov=backend --cov-fail-under=32
```

Expected: all pass; SIS 180/180; coverage ≥ 32%.

- [ ] **Step 3.8: Manual end-to-end smoke — trigger a grading run**

```bash
cd backend && source ../venv/bin/activate && python app.py &
sleep 3
# If a grading fixtures folder exists:
curl -s http://localhost:3000/api/status | python -m json.tool | head -20
kill %1 2>/dev/null || pkill -f "python app.py"
cd ..
```

Expected: `/api/status` returns a valid state dict with `is_running: false` initially. (Full end-to-end grading requires fixtures; this just confirms the state-thread plumbing still routes.)

- [ ] **Step 3.9: Codex Gate 3 review**

Requirements:
- Only `backend/app.py`, `backend/grading/thread.py`, `tests/test_grading_shims.py` changed.
- Function bodies in `grading/thread.py` are byte-identical to the deleted app.py lines (nested function included).
- No Clever/ClassLink/OneRoster file modifications.
- `portal_grading.py`, `assistant_tools_student.py`, `email_routes.py` NOT modified (those stay on the shim path until PR4).

- [ ] **Step 3.10: Commit, push, open PR**

```bash
git add backend/app.py backend/grading/thread.py tests/test_grading_shims.py
git commit -m "$(cat <<'EOF'
refactor: extract grading thread to backend/grading/thread.py (Phase 3a PR3)

Moves run_grading_thread + _run_grading_thread_inner (with nested
format_rubric_for_prompt intact) from backend/app.py into
backend/grading/thread.py. Function bodies byte-identical. Shim in
app.py re-exports both names so register_routes(...) injection and
SIGTERM handler continue to work unchanged.

Net app.py delta: ~-2100 LOC. grading/thread.py net ~+2100 LOC.

Pre-existing latent: portal_grading.py:380 imports format_rubric_for_prompt
from backend.app — that function is nested inside
_run_grading_thread_inner and has never been module-level importable.
Not fixed here; out of Phase 3a scope.

SIS compliance: 180/180 green. Coverage: >= 32%.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr3-thread-extract
gh pr create --title "refactor: extract grading thread to backend/grading/thread.py (Phase 3a PR3)" --body "Phase 3a PR3 of 4. Thread wrapper + ~2000-line inner pipeline extracted; shim maintains backwards-compat."
```

Wait for CI + user merge signoff.

---

## Task 4 (PR4): Migrate consumers, remove shims

**Files:**
- Modify: `backend/services/portal_grading.py` (lines 255, 380, 563)
- Modify: `backend/services/assistant_tools_student.py` (lines 515, 680)
- Modify: `backend/routes/email_routes.py` (line 1102)
- Modify: `backend/app.py` (remove shim imports; update `register_routes(...)` call; update `_handle_sigterm`)
- Delete: `tests/test_grading_shims.py` (temporary test no longer needed)
- Modify: `tests/test_app_boot.py` (remove the `create_app` test if it stays equivalent, or leave as-is)

- [ ] **Step 4.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr4-shim-cleanup
```

- [ ] **Step 4.2: Rewrite `portal_grading.py` imports**

In `/Users/alexc/Downloads/Graider/backend/services/portal_grading.py`:

- Line 255: change `from backend.app import save_results, load_saved_results, _get_lock` (or however it's phrased) → `from backend.grading.state import save_results, load_saved_results, _get_lock`
- Line 380: `from backend.app import format_rubric_for_prompt` → DELETE this line and the following `rubric_prompt = format_rubric_for_prompt(rubric)` call (the import was always broken — nested function never module-importable). Replace the block with inline rubric formatting or a stub — see note below.
- Line 563: same pattern as line 255.

**Decision for line 380:** Since `format_rubric_for_prompt` has NEVER been importable from `backend.app` (it's nested), `portal_grading.py:380` is dead code that would ImportError if reached. Two options:

(a) Delete lines 378–383 entirely (the `if rubric.get("categories"):` block that does the broken import).
(b) Inline a minimal rubric formatter here so the feature works. But this expands scope.

**Choose (a) in PR4.** Document the removal in the commit message. If rubric formatting from portal_grading turns out to be needed, a separate follow-up PR can add it with proper tests.

- [ ] **Step 4.3: Rewrite `assistant_tools_student.py` imports**

In `/Users/alexc/Downloads/Graider/backend/services/assistant_tools_student.py`:
- Line 515: `from backend.app import _get_state` → `from backend.grading.state import _get_state`
- Line 680: `from backend.app import save_results` → `from backend.grading.state import save_results`

- [ ] **Step 4.4: Rewrite `email_routes.py` imports**

In `/Users/alexc/Downloads/Graider/backend/routes/email_routes.py`:
- Line 1102: `from backend.app import _get_state` → `from backend.grading.state import _get_state`

- [ ] **Step 4.5: Update app.py — remove shim, fix register_routes + SIGTERM**

In `/Users/alexc/Downloads/Graider/backend/app.py`:

1. Delete the shim imports block introduced in PR2/PR3.
2. Replace the shim with direct imports ONLY for names that `app.py` ITSELF uses internally:
   ```python
   from grading.state import _get_state, _get_lock, reset_state, _grading_states
   from grading.thread import run_grading_thread
   ```
3. Update `register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)` — unchanged; still works because the names are imported into module scope.
4. Update `_handle_sigterm(...)` — it already uses `_grading_states`, which is now imported at the top.

- [ ] **Step 4.6: Delete `tests/test_grading_shims.py`**

```bash
rm tests/test_grading_shims.py
```

The shim guard served its transitional purpose.

- [ ] **Step 4.7: Run test suites**

```bash
source venv/bin/activate
python -m pytest tests/test_app_boot.py -v
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_contract.py tests/test_classlink_sso_contract.py tests/test_clever_callback.py tests/test_clever_classes.py tests/test_clever_compliance.py tests/test_clever.py tests/test_clever_student_sso.py tests/test_classlink_sso.py tests/test_oneroster.py tests/test_oneroster_sync_grades.py tests/test_oneroster_gradebook.py tests/test_roster_sync.py tests/test_sis_alerting.py -q
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x -m "not live" --cov=backend --cov-fail-under=32
```

Expected: all pass. SIS 180/180. Coverage ≥ 32%.

- [ ] **Step 4.8: Grep verification — no consumer still imports from `backend.app` for state/thread**

```bash
grep -rn "from backend.app import.*\(_get_state\|_get_lock\|_update_state\|reset_state\|_grading_states\|_grading_locks\|load_saved_results\|save_results\|run_grading_thread\|_run_grading_thread_inner\|_create_default_state\)" backend/ tests/
```

Expected: zero matches.

- [ ] **Step 4.9: Boot + route-count check**

```bash
cd backend && source ../venv/bin/activate && python -c "from app import app; print(len(app.url_map._rules))"
cd ..
```

Expected: prints same route count baseline as PR1/PR2/PR3.

- [ ] **Step 4.10: Codex Gate 3 review**

Requirements:
- Only `backend/app.py`, `backend/services/portal_grading.py`, `backend/services/assistant_tools_student.py`, `backend/routes/email_routes.py` modified. `tests/test_grading_shims.py` deleted.
- `portal_grading.py` lines 378–383 deletion is intentional (document broken-import removal).
- No Clever/ClassLink/OneRoster file modifications.
- Grep verification in Step 4.8 returned zero matches.

- [ ] **Step 4.11: Commit, push, open PR**

```bash
git add backend/app.py backend/services/portal_grading.py backend/services/assistant_tools_student.py backend/routes/email_routes.py tests/test_grading_shims.py
git commit -m "$(cat <<'EOF'
refactor: migrate consumers off app.py shim; remove shim (Phase 3a PR4)

- portal_grading.py (lines 255, 563): state imports now from
  backend.grading.state
- portal_grading.py (lines 378-383): DELETE broken format_rubric_for_prompt
  import block — the function has always been nested inside
  _run_grading_thread_inner and was never module-importable. Dead code
  removal.
- assistant_tools_student.py (lines 515, 680): state imports now from
  backend.grading.state
- email_routes.py (line 1102): _get_state import now from
  backend.grading.state
- app.py: shim block replaced with direct imports of only the names
  app.py itself needs (register_routes args + SIGTERM handler)
- tests/test_grading_shims.py DELETED (transitional; purpose served)

Net app.py size after Phase 3a: ~1400 LOC (down from 3528).

SIS compliance: 180/180 green. Coverage: >= 32%.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr4-shim-cleanup
gh pr create --title "refactor: migrate consumers + remove shim (Phase 3a PR4)" --body "Phase 3a PR4 of 4. All consumers migrated to canonical backend.grading.* paths. Shim removed. app.py down to ~1400 LOC."
```

Wait for CI + user merge signoff.

---

## After Task 4 — Phase 3a Complete

Update memory: `/Users/alexc/.claude/projects/-Users-alexc-Downloads-Graider/memory/project_phase3a_complete.md` with the final app.py size and Phase 3b handoff note.

---

## Self-review

**1. Spec coverage:**
- Spec Decision 1 (scope decomposition — 3a only) → enforced throughout by exclusion of planner_routes.py.
- Spec Decision 2 (c then b migration) → Task 1 (factory) → Tasks 2-4 (incremental extraction with shims).
- Spec Decision 3 (granularity: 2 files) → state.py (Task 2) + thread.py (Task 3); no pipeline.py.
- Gotcha #1 (persistence with state) → Task 2 Step 2.6 moves `load_saved_results` + `save_results` into state.py.
- Gotcha #2 (shim surface) → Tasks 2-4 maintain shim then remove it in Task 4.
- Gotcha #3 (format_rubric nested) → Task 3 Step 3.4 + Task 4 Step 4.2 handle the nested-function reality (moves with thread; broken import line in portal_grading deleted).
- Safety net (boot check, route-count, SIS, shim guard) → Task 1 Step 1.2 creates boot test; shim guard test lives through PR2-3 and deleted in PR4.
- 4-PR sequence → Tasks 1-4 map 1:1 to PR1-PR4.

**2. Placeholder scan:** No TBD/TODO remains. "exact body copied from backend/app.py:X-Y" is a delegation directive with concrete line anchors, not a placeholder. Manual smoke test commands are exact.

**3. Type consistency:** Function names (`_get_state`, `_get_lock`, `_update_state`, `reset_state`, `_create_default_state`, `load_saved_results`, `save_results`, `run_grading_thread`, `_run_grading_thread_inner`) used consistently across all 4 tasks.

**4. Risk callouts:**
- Task 1 risk: blueprint decorators move inside `create_app()`. If decorators reference the module-level `app` before the factory ran, they'd register on a different instance. Mitigation: test 1.2 asserts route count ≥ 250 after factory call.
- Task 3 risk: the 2000-line `_run_grading_thread_inner` is the biggest moving target. Mitigation: byte-identical copy enforced via Codex Gate 3; manual smoke check in 3.8 confirms /api/status still routes.
- Task 4 risk: the `format_rubric_for_prompt` dead-code removal in portal_grading.py. Mitigation: Step 4.2 documents the decision; if it turns out to be load-bearing (it shouldn't be, since it always failed), a follow-up PR adds the feature with tests.
