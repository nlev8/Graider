# Phase 3a — backend/app.py Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `backend/app.py` from 3528 → ~1400 lines by extracting grading state + thread code into `backend/grading/` while establishing the Flask app-factory pattern. Zero behavior change. SIS compliance (Clever/ClassLink/OneRoster) stays green throughout.

**Architecture:** Four sequential PRs. PR1 introduces `init_app(app)` initializer (module-level `app` and `@app.route` decorators stay put). PR2 extracts state + persistence helpers into `grading/state.py` with import shims in app.py. PR3 extracts thread wrapper to `grading/thread.py` and pipeline to `grading/pipeline.py` (3-file split). PR4 migrates consumers, extracts `format_rubric_for_prompt` to `services/rubric_formatting.py`, and removes shims.

**Tech Stack:** Python 3.14, Flask, pytest.

**Spec:** `docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md`

---

## File Structure

After all four PRs:

| File | Role | Size (approx) |
|---|---|---|
| `backend/app.py` | Module-level `app = Flask(...)`, `init_app(app)` initializer, module-level `@app.route` decorators (legacy handlers not yet in blueprints), audit helpers, calibration helper | ~1400 LOC |
| `backend/grading/__init__.py` | Package marker | ~20 LOC |
| `backend/grading/state.py` | `_grading_states`, `_grading_locks`, `_get_state`, `_get_lock`, `_update_state`, `reset_state`, `_create_default_state`, `load_saved_results`, `save_results` | ~220 LOC |
| `backend/grading/thread.py` | `run_grading_thread` BYOK wrapper (thread lifecycle only; imports pipeline) | ~70 LOC |
| `backend/grading/pipeline.py` | `_run_grading_thread_inner` business-logic pipeline (moved byte-identical in PR3; nested `format_rubric_for_prompt` extracted in PR4) | ~2000 LOC |
| `backend/services/rubric_formatting.py` | `format_rubric_for_prompt` (extracted from pipeline's nested scope in PR4) | ~40 LOC |
| `tests/test_app_boot.py` | Boot + route-snapshot smoke tests (new) | ~60 LOC |
| `tests/test_grading_shims.py` | Verify backwards-compat shims work (temporary, deleted in PR4) | ~50 LOC |

## Hard constraints (enforced every PR)

- SIS compliance: 180/180 green at every step (`pytest tests/test_sso_contracts.py tests/test_clever_*.py tests/test_classlink_*.py tests/test_oneroster*.py tests/test_roster_sync.py tests/test_sis_alerting.py`).
- Coverage floor: CI fails below 32%.
- Boot: `python -c "import sys; sys.path.insert(0, 'backend'); from app import app; print(len(app.url_map._rules))"` returns an integer ≥ 250 every PR.
- Zero Clever / ClassLink / OneRoster / roster_sync / oneroster_gradebook file modifications (enforced via `git diff --name-only` in verification).
- Codex Gate 1 (plan preview) has already run; Codex Gate 3 (diff review) runs on each PR before merge.

---

## Task 1 (PR1): Introduce `init_app(app)` initializer — ZERO code movement to other files

**Files:**
- Modify: `backend/app.py` (restructure internally only; no extraction)
- Create: `tests/test_app_boot.py`

**Why:** Establishes `init_app(app)` as a well-defined initialization seam. Module-level `app = Flask(...)` and all module-level `@app.route` decorators STAY PUT (Codex/Gemini tie-break: full `create_app()` factory would require moving every `@app.route` inside the factory scope or converting all to blueprints — both are scope creep for Phase 3a). Only middleware / error-handler registration, `register_routes(...)` call, and SIGTERM setup move into the initializer.

- [ ] **Step 1.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr1-app-factory
```

- [ ] **Step 1.2: Write boot + route-snapshot tests FIRST (TDD)**

Create `/Users/alexc/Downloads/Graider/tests/test_app_boot.py`:

```python
"""Boot + route-snapshot smoke tests for backend/app.py.

Phase 3a safety net: pin that the app still boots, has the expected
minimum URL rules, and no existing endpoint silently changed path or
methods across the refactor. Per Codex/Gemini tie-break, snapshot
captures endpoint → (rule, methods) not just count.
"""
import importlib
import sys


def _import_app():
    """Fresh import of backend.app with backend/ on sys.path.
    Matches production entry point."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        return backend_app
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_app_module_imports_cleanly():
    """Importing backend.app must not raise."""
    backend_app = _import_app()
    assert hasattr(backend_app, "app"), "Module must expose a Flask `app` instance"


def test_app_registers_expected_route_count():
    """Floor check: at least 250 URL rules registered.
    Guards against accidental blueprint-registration regressions."""
    backend_app = _import_app()
    rule_count = len(backend_app.app.url_map._rules)
    assert rule_count >= 250, f"Expected >= 250 rules, got {rule_count}"


def test_app_exposes_init_app_initializer():
    """Phase 3a PR1 adds init_app(app). This test exists from PR1 onward;
    before PR1 it would fail (function doesn't exist)."""
    backend_app = _import_app()
    assert callable(backend_app.init_app), "init_app(app) must be callable"


def test_app_route_snapshot_has_no_silent_drift():
    """Pin endpoint → (rule, methods) so a silent path/method change in any
    refactor step surfaces as a failed assertion.

    Collects current snapshot and asserts the KEY endpoints used by Clever,
    ClassLink, and OneRoster SSO still exist with their original rules +
    HTTP methods. This is the SIS-compliance safety rail.
    """
    backend_app = _import_app()
    snapshot = {
        rule.endpoint: (rule.rule, sorted(rule.methods - {"HEAD", "OPTIONS"}))
        for rule in backend_app.app.url_map.iter_rules()
    }
    # Pin critical SIS endpoints. If an endpoint is renamed or its methods
    # change, this test fails and the refactor is blocked.
    required = {
        # Clever
        "clever_routes.clever_login_url":       ("/api/clever/login-url",       ["GET"]),
        "clever_routes.clever_callback":        ("/api/clever/callback",        ["GET"]),
        "clever_routes.clever_session":         ("/api/clever/session",         ["GET"]),
        # ClassLink
        "classlink_routes.classlink_login_url": ("/api/classlink/login-url",    ["GET"]),
        "classlink_routes.classlink_callback":  ("/api/classlink/callback",     ["GET"]),
        # OneRoster
        "oneroster_routes.oneroster_config":    ("/api/oneroster/config",       ["GET", "POST"]),
    }
    missing = {k: v for k, v in required.items() if k not in snapshot}
    mismatched = {
        k: (snapshot[k], v)
        for k, v in required.items()
        if k in snapshot and snapshot[k] != v
    }
    assert not missing, f"SIS-critical endpoints missing from snapshot: {missing}"
    assert not mismatched, f"SIS-critical endpoint path/method drift: {mismatched}"
```

**Before writing the test, verify the exact endpoint names by running:**

```bash
cd backend && source ../venv/bin/activate && python -c "
from app import app
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if '/api/clever' in rule.rule or '/api/classlink' in rule.rule or '/api/oneroster' in rule.rule:
        methods = sorted(rule.methods - {'HEAD', 'OPTIONS'})
        print(f'{rule.endpoint!r:60} {rule.rule!r:45} {methods}')
" 2>&1 | head -30
cd ..
```

Replace the `required = {...}` dict with the EXACT endpoint names printed. If endpoint names differ from the guesses above, use the actual printed values. The test must represent REAL current state before refactor.

- [ ] **Step 1.3: Run the new tests — confirm `test_app_exposes_init_app_initializer` fails**

```bash
source venv/bin/activate
python -m pytest tests/test_app_boot.py -v
```

Expected: `test_app_module_imports_cleanly`, `test_app_registers_expected_route_count`, and `test_app_route_snapshot_has_no_silent_drift` PASS. `test_app_exposes_init_app_initializer` FAILS (init_app doesn't exist yet). This failing test is the TDD driver for Step 1.4.

- [ ] **Step 1.4: Refactor app.py to introduce `init_app(app)` initializer (module-level `app` stays put)**

Open `/Users/alexc/Downloads/Graider/backend/app.py`.

Current state: `app = Flask(__name__, static_folder='static', static_url_path='')` at line 82; module-level `@app.after_request` / `@app.errorhandler` / multiple `@app.route` decorators scattered throughout; `register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)` at line 2055; `signal.signal(signal.SIGTERM, _handle_sigterm)` registration also at module level.

Goal: Extract ONLY the imperative initialization calls (`register_routes` + SIGTERM registration) into `init_app(app)`. Leave every decorator and every function definition at module level so their scope doesn't change.

Conceptual shape after refactor:

```python
# Imports at top (unchanged)
from flask import Flask, request, jsonify, ...
import signal, threading, ...

# Module-level Flask instance — STAYS HERE so decorators keep attaching
app = Flask(__name__, static_folder='static', static_url_path='')


# Middleware (STAYS at module level, body byte-identical)
@app.after_request
def set_security_headers(response):
    # ... existing body, BYTE-IDENTICAL ...
    return response


# Error handlers (STAY at module level, body byte-identical)
@app.errorhandler(500)
def handle_500(e):
    # ... existing body, BYTE-IDENTICAL ...
    ...


@app.errorhandler(404)
def handle_404(e):
    # ... existing body, BYTE-IDENTICAL ...
    ...


# All module-level functions STAY WHERE THEY ARE (unchanged in PR1):
# load_saved_results, save_results, _grading_states, _create_default_state,
# _get_state, _get_lock, _update_state, reset_state,
# run_grading_thread, _run_grading_thread_inner, _handle_sigterm, plus every
# module-level @app.route(...) handler at former lines 2359/2898/etc.


def init_app(app):
    """Imperative initialization wiring for the Flask app.

    Called exactly once at module load (below) AFTER all decorators have
    attached. Factored out as a named function so Phase 3a PR2+ can reason
    about the initialization seam and Phase 3b+ can eventually evolve this
    into a full create_app() factory once module-level @app.route handlers
    migrate to blueprints.
    """
    # Lazy imports preserved from original code
    from routes import register_routes
    register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)

    # SIGTERM registration (the _handle_sigterm function body itself stays
    # at module level; only the signal.signal() call moves here)
    signal.signal(signal.SIGTERM, _handle_sigterm)


# Run initializer ONCE at module load, AFTER all decorators have attached.
init_app(app)


if __name__ == '__main__':
    # ... existing browser-open + app.run() ...
    app.run(host='0.0.0.0', port=3000, debug=False)
```

Key rules for this PR:
1. **Module-level `app = Flask(...)` stays.** So does every `@app.after_request`, `@app.errorhandler`, and `@app.route` decorator + decorated function.
2. **Function bodies are byte-identical** to pre-refactor. The ONLY diff is: extract the `register_routes(...)` line + `signal.signal(...)` line into `init_app()`, and add a single `init_app(app)` call at the bottom.
3. **The `_handle_sigterm` function body stays at module level** — only its `signal.signal(...)` registration moves.
4. `from routes import register_routes` stays INSIDE `init_app` (lazy import preserves the original pattern).

- [ ] **Step 1.5: Run the test — all four tests must now pass**

```bash
python -m pytest tests/test_app_boot.py -v
```

Expected: all 4 tests PASS, including `test_app_exposes_init_app_initializer` and `test_app_route_snapshot_has_no_silent_drift`.

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
refactor: introduce init_app(app) initializer (Phase 3a PR1)

Extracts the imperative initialization wiring (register_routes call +
SIGTERM signal registration) into an init_app(app) function. Module-level
`app = Flask(...)` stays in place so all module-level @app.after_request
/ @app.errorhandler / @app.route decorators continue to attach correctly
(Codex/Gemini tie-break: full create_app() factory would require moving
every route decorator and was deemed Phase 3a scope creep).

Adds tests/test_app_boot.py pinning:
- Module imports cleanly
- URL rule count >= 250 (guards blueprint regression)
- init_app(app) initializer is callable
- SIS-critical endpoints (Clever/ClassLink/OneRoster) exist with their
  exact path + HTTP methods — route-snapshot drift guard

Function bodies byte-identical. SIS compliance: 180/180 green.
Coverage: unchanged.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr1-app-factory
gh pr create --title "refactor: introduce init_app(app) initializer (Phase 3a PR1)" --body "Phase 3a PR1 of 4. Pure structural refactor; no code extraction yet. Establishes init_app seam for PR2-4; full create_app factory deferred to Phase 3b+ after module-level route handlers migrate to blueprints."
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

## Task 3 (PR3): Extract thread wrapper to `backend/grading/thread.py` AND pipeline to `backend/grading/pipeline.py`

**Files:**
- Create: `backend/grading/thread.py` (~70 LOC — wrapper only)
- Create: `backend/grading/pipeline.py` (~2000 LOC — inner pipeline)
- Modify: `backend/app.py` (remove thread + pipeline code; extend shim)

**Why 3 files, not 2 (rev 2 change):** Codex + Gemini tie-break — putting a 2000-line business-logic pipeline in a file named `thread.py` conflates lifecycle/concurrency with business logic. Splitting to `thread.py` (orchestration wrapper) + `pipeline.py` (business logic) is still a pure byte-identical move per the Phase 3a constraint ("no internal decomposition"), just split across 2 target files. Paves the road for Phase 3b unit-testing the pipeline in isolation.

- [ ] **Step 3.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr3-thread-extract
```

- [ ] **Step 3.2: Extend `tests/test_grading_shims.py` to pin thread AND pipeline shims**

Add to `/Users/alexc/Downloads/Graider/tests/test_grading_shims.py`:

```python
def test_backend_app_reexports_grading_thread_and_pipeline_helpers():
    """Phase 3a PR3: thread wrapper lives in backend.grading.thread;
    inner pipeline lives in backend.grading.pipeline. app.py keeps
    re-export shim for both until PR4."""
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
    """Canonical path for the thread wrapper."""
    import sys
    sys.path.insert(0, "backend")
    try:
        from grading import thread as grading_thread
        assert hasattr(grading_thread, "run_grading_thread"), "backend.grading.thread must define run_grading_thread"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_grading_pipeline_module_is_canonical():
    """Canonical path for the inner pipeline."""
    import sys
    sys.path.insert(0, "backend")
    try:
        from grading import pipeline as grading_pipeline
        assert hasattr(grading_pipeline, "_run_grading_thread_inner"), "backend.grading.pipeline must define _run_grading_thread_inner"
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")
```

- [ ] **Step 3.3: Run the new tests — both module-canonical tests must fail**

```bash
python -m pytest tests/test_grading_shims.py::test_grading_thread_module_is_canonical tests/test_grading_shims.py::test_grading_pipeline_module_is_canonical -v
```

Expected: both FAIL with ImportError (modules don't exist yet).

- [ ] **Step 3.4a: Create `backend/grading/pipeline.py`**

The code to move from `backend/app.py`:
- Lines 570–2053: `_run_grading_thread_inner(...)` (including its nested `format_rubric_for_prompt` at former line 587 — stays nested in this PR; extracted out in PR4)
- All module-level imports that `_run_grading_thread_inner` needs (copy them to the top of pipeline.py — do NOT remove from app.py yet; shim keeps app.py imports intact until PR4)

Create `/Users/alexc/Downloads/Graider/backend/grading/pipeline.py`:

```python
"""Grading business-logic pipeline.

Extracted from backend/app.py in Phase 3a PR3. Byte-identical move —
no internal decomposition. The nested format_rubric_for_prompt at
former line 587 stays nested here in PR3; it moves out to
backend/services/rubric_formatting.py in PR4.
"""
# All imports _run_grading_thread_inner needs — copied from app.py top.
import json
import os
import threading
from pathlib import Path
from datetime import datetime

# Graider-internal imports the pipeline needs (enumerate EVERY one that
# _run_grading_thread_inner references at runtime — grading_service,
# portal_grading helpers, assignment_grader, plagiarism_detector,
# writing_style, handwriting_fallback, extractors, storage, compliance,
# and any others. Use grep to confirm completeness):
from backend.grading.state import _get_state, _get_lock, save_results, _update_state
# ... etc. ...


def _run_grading_thread_inner(assignments_folder, output_folder, roster_file,
                              assignment_config=None, global_ai_notes='',
                              grading_period='Q3', grade_level='7',
                              subject='Social Studies', teacher_name='',
                              school_name='', selected_files=None,
                              ai_model='gpt-4o-mini', skip_verified=False,
                              class_period='', rubric=None, ensemble_models=None,
                              extraction_mode='structured', trusted_students=None,
                              grading_style='standard', teacher_id='local-dev'):
    """Exact body from backend/app.py:570-2053 (BYTE-IDENTICAL), including
    the nested format_rubric_for_prompt at former line 587."""
    # ... byte-identical copy ...
```

**Critical (imports completeness):** Before creating pipeline.py, scan `_run_grading_thread_inner` for every external name it references. Use:
```bash
cd backend && source ../venv/bin/activate && python -c "
import ast
tree = ast.parse(open('app.py').read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_run_grading_thread_inner':
        names = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                names.add(n.value.id)
        for name in sorted(names):
            print(name)
        break
" | sort -u
cd ..
```
Every name in that list that's not defined WITHIN the function must be importable in pipeline.py.

- [ ] **Step 3.4b: Create `backend/grading/thread.py`**

The code to move from `backend/app.py`:
- Lines 543–568: `run_grading_thread(...)` wrapper (BYOK context manager + call to `_run_grading_thread_inner`)

Create `/Users/alexc/Downloads/Graider/backend/grading/thread.py`:

```python
"""Grading thread lifecycle wrapper.

Extracted from backend/app.py in Phase 3a PR3. Handles BYOK (bring your
own key) context management then delegates to the pipeline module for
the actual grading logic. Thin wrapper (~70 LOC) — lifecycle concerns
ONLY; business logic lives in backend.grading.pipeline.
"""
from backend.grading.pipeline import _run_grading_thread_inner


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
    """Exact body from backend/app.py:543-568 (BYTE-IDENTICAL). Wraps
    _run_grading_thread_inner with BYOK user_api_keys context.
    """
    # ... byte-identical copy ...
```

**Critical (format_rubric_for_prompt in PR3):** The nested `format_rubric_for_prompt` inside `_run_grading_thread_inner` stays nested in pipeline.py for this PR. It moves to `backend/services/rubric_formatting.py` in PR4.

**Critical (latent import bug unchanged by PR3):** `portal_grading.py:380` does `from backend.app import format_rubric_for_prompt`. That import has always raised ImportError when exercised (the function has always been nested). PR3 does NOT fix this — PR4 does. Document in the PR body.

- [ ] **Step 3.5: Remove moved code from app.py; extend the shim**

In `backend/app.py`:

1. Delete lines 543–2053 (the two thread functions: `run_grading_thread` and `_run_grading_thread_inner`).
2. Extend the shim import (still at the same location PR2 introduced it) to re-export from BOTH modules:

```python
# Phase 3a: grading state + thread + pipeline moved to backend/grading/.
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
from grading.thread import run_grading_thread
from grading.pipeline import _run_grading_thread_inner
```

**Note:** `register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)` inside `init_app(app)` still works unchanged — `run_grading_thread` is in module namespace via the shim.

- [ ] **Step 3.6: Run the updated shim-guard tests**

```bash
python -m pytest tests/test_grading_shims.py -v
```

Expected: all 5 tests PASS (the PR2 pair + 3 new PR3 tests: reexport check, thread canonical, pipeline canonical).

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
- Only `backend/app.py`, `backend/grading/thread.py`, `backend/grading/pipeline.py`, `tests/test_grading_shims.py` changed.
- Function bodies in `grading/thread.py` and `grading/pipeline.py` are byte-identical to the deleted app.py lines (nested `format_rubric_for_prompt` still nested inside pipeline's `_run_grading_thread_inner`).
- Import chain: `grading/thread.py` imports `_run_grading_thread_inner` from `grading.pipeline`; `grading/pipeline.py` imports state helpers from `grading.state`; no circular deps.
- No Clever/ClassLink/OneRoster file modifications.
- `portal_grading.py`, `assistant_tools_student.py`, `email_routes.py` NOT modified (those stay on the shim path until PR4).

- [ ] **Step 3.10: Commit, push, open PR**

```bash
git add backend/app.py backend/grading/thread.py backend/grading/pipeline.py tests/test_grading_shims.py
git commit -m "$(cat <<'EOF'
refactor: extract grading thread + pipeline (Phase 3a PR3)

Splits the 3-file extraction per Codex/Gemini tie-break:
- backend/grading/thread.py (~70 LOC): run_grading_thread BYOK wrapper.
  Lifecycle concerns only; imports the pipeline.
- backend/grading/pipeline.py (~2000 LOC): _run_grading_thread_inner
  business-logic pipeline. Byte-identical move from app.py. Nested
  format_rubric_for_prompt stays nested here in PR3 (moves out in PR4).

Import chain: thread → pipeline → state (no cycles).
Shim in app.py re-exports run_grading_thread and
_run_grading_thread_inner so register_routes(...) injection and all
existing consumers continue to work unchanged.

Net app.py delta: ~-2100 LOC.

Pre-existing latent (not fixed here; PR4 fixes it):
portal_grading.py:380 imports format_rubric_for_prompt from
backend.app — that function is nested inside _run_grading_thread_inner
and has never been module-level importable.

SIS compliance: 180/180 green. Coverage: >= 32%.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr3-thread-extract
gh pr create --title "refactor: extract grading thread + pipeline (Phase 3a PR3)" --body "Phase 3a PR3 of 4. 3-file split: thread.py (lifecycle wrapper) + pipeline.py (~2000 LOC business logic). Shim maintains backwards-compat; PR4 does final consumer migration."
```

Wait for CI + user merge signoff.

---

## Task 4 (PR4): Extract `format_rubric_for_prompt`, migrate consumers, remove shims

**Files:**
- Create: `backend/services/rubric_formatting.py` (~40 LOC — new home for the extracted nested function)
- Modify: `backend/grading/pipeline.py` (remove nested def; import from new module; update call site)
- Modify: `backend/services/portal_grading.py` (lines 255, 380, 563 — all three imports updated, NOT deleted)
- Modify: `backend/services/assistant_tools_student.py` (lines 515, 680)
- Modify: `backend/routes/email_routes.py` (line 1102)
- Modify: `backend/app.py` (replace shim block with direct imports of only the names app.py itself needs)
- Delete: `tests/test_grading_shims.py` (temporary test no longer needed)

- [ ] **Step 4.1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/phase3a-pr4-shim-cleanup
```

- [ ] **Step 4.2a: Extract `format_rubric_for_prompt` to `backend/services/rubric_formatting.py`**

Codex verified the nested function at former `app.py:587` (now inside `backend/grading/pipeline.py._run_grading_thread_inner`) does NOT close over enclosing state — it only uses its `rubric_data` parameter. Safe to extract.

Create `/Users/alexc/Downloads/Graider/backend/services/rubric_formatting.py`:

```python
"""Rubric prompt formatting — shared by grading pipeline + portal grading.

Extracted from the nested scope inside
backend/grading/pipeline.py:_run_grading_thread_inner as part of
Phase 3a PR4. Pure function; no side effects; no closure dependencies.
"""


def format_rubric_for_prompt(rubric_data):
    """Convert rubric dict to a formatted prompt string.

    Body BYTE-IDENTICAL to the nested definition formerly at
    backend/app.py:587 (moved to backend/grading/pipeline.py in PR3,
    now extracted here).
    """
    if not rubric_data or not rubric_data.get('categories'):
        return None

    categories = rubric_data.get('categories', [])
    generous = rubric_data.get('generous', True)

    lines = []
    lines.append("GRADING RUBRIC (from teacher's custom settings):")
    lines.append("")

    total_weight = sum(c.get('weight', 0) for c in categories)
    # ... BYTE-IDENTICAL continuation from the nested version ...
```

Verify: open `backend/grading/pipeline.py`, locate `def format_rubric_for_prompt(rubric_data):` inside `_run_grading_thread_inner`, copy the ENTIRE function body into `backend/services/rubric_formatting.py`. Keep indentation corrected (go from nested 4 spaces to module-level 0 spaces). No body changes.

- [ ] **Step 4.2b: Update pipeline.py to import from rubric_formatting instead of nesting**

In `/Users/alexc/Downloads/Graider/backend/grading/pipeline.py`:

1. At the top of the file, add:
   ```python
   from backend.services.rubric_formatting import format_rubric_for_prompt
   ```
2. Delete the nested `def format_rubric_for_prompt(rubric_data):` block inside `_run_grading_thread_inner` entirely (all ~40 lines).
3. Leave the CALL site unchanged: `rubric_prompt = format_rubric_for_prompt(rubric)` (now resolves to the imported module-level function).

- [ ] **Step 4.2c: Rewrite `portal_grading.py` imports — FIX the broken :380 import**

In `/Users/alexc/Downloads/Graider/backend/services/portal_grading.py`:

- Line 255 (whatever specific names are there): change `from backend.app import save_results, load_saved_results, _get_lock` → `from backend.grading.state import save_results, load_saved_results, _get_lock`.
- Line 380: change `from backend.app import format_rubric_for_prompt` → `from backend.services.rubric_formatting import format_rubric_for_prompt`. Leave the `rubric_prompt = format_rubric_for_prompt(rubric)` call exactly as it was. The pre-existing latent ImportError is now FIXED — the import resolves correctly, the feature actually works.
- Line 563: same pattern as line 255.

**Rationale for fixing (not deleting) line 380:** Codex + Gemini tie-break — the function is pure, narrow blast radius, and belongs in a dedicated formatting module. Deleting the block (rev 1 plan) would have silently removed rubric-formatting behavior from the portal grading path. The rev 2 approach makes the feature actually work.

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
- Only `backend/app.py`, `backend/grading/pipeline.py`, `backend/services/rubric_formatting.py` (new), `backend/services/portal_grading.py`, `backend/services/assistant_tools_student.py`, `backend/routes/email_routes.py` modified. `tests/test_grading_shims.py` deleted.
- `backend/services/rubric_formatting.py` body is byte-identical to the nested definition it replaces (indentation normalized to module level).
- `backend/grading/pipeline.py` has the import at the top AND the nested def removed (no duplicate definition).
- `portal_grading.py:380` import now points to `backend.services.rubric_formatting` — previously-broken import is now working, feature restored.
- No Clever/ClassLink/OneRoster file modifications.
- Grep verification in Step 4.8 returned zero matches (no consumer still imports from `backend.app` for state/thread helpers).

- [ ] **Step 4.11: Commit, push, open PR**

```bash
git add backend/app.py backend/grading/pipeline.py backend/services/rubric_formatting.py backend/services/portal_grading.py backend/services/assistant_tools_student.py backend/routes/email_routes.py tests/test_grading_shims.py
git commit -m "$(cat <<'EOF'
refactor: extract rubric formatter + migrate consumers + remove shim (Phase 3a PR4)

Rubric formatter extraction (new file):
- Create backend/services/rubric_formatting.py with format_rubric_for_prompt
  extracted byte-identical from pipeline.py's nested scope
- pipeline.py: remove nested def; import from rubric_formatting
- portal_grading.py:380: fix latent ImportError — import now points
  to backend.services.rubric_formatting (feature newly functional)

Consumer migration (shim removal):
- portal_grading.py (lines 255, 563): state imports now from
  backend.grading.state
- assistant_tools_student.py (lines 515, 680): state imports now from
  backend.grading.state
- email_routes.py (line 1102): _get_state import now from
  backend.grading.state
- app.py: shim block replaced with direct imports of only the names
  app.py itself needs (register_routes args + SIGTERM handler)
- tests/test_grading_shims.py DELETED (transitional purpose served)

Net app.py size after Phase 3a: ~1400 LOC (down from 3528).

SIS compliance: 180/180 green. Coverage: >= 32%.

Spec: docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md
Codex Gate 3: GREEN.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin feat/phase3a-pr4-shim-cleanup
gh pr create --title "refactor: extract rubric formatter + remove shim (Phase 3a PR4)" --body "Phase 3a PR4 of 4. New backend/services/rubric_formatting.py; all consumers migrated to canonical backend.grading.* paths; shim removed; portal_grading:380 latent ImportError fixed. app.py down to ~1400 LOC."
```

Wait for CI + user merge signoff.

---

## After Task 4 — Phase 3a Complete

Update memory: `/Users/alexc/.claude/projects/-Users-alexc-Downloads-Graider/memory/project_phase3a_complete.md` with the final app.py size and Phase 3b handoff note.

---

## Self-review (rev 2)

**1. Spec coverage:**
- Spec Decision 1 (scope decomposition — 3a only) → enforced throughout by exclusion of planner_routes.py.
- Spec Decision 2 (init_app + incremental with shims) → Task 1 (init_app, no code movement) → Tasks 2-4 (incremental extraction with shims).
- Spec Decision 3 (3-file granularity: state + thread + pipeline) → state.py (Task 2), thread.py wrapper (Task 3.4b), pipeline.py (Task 3.4a).
- Gotcha #1 (persistence with state) → Task 2 Step 2.6 moves `load_saved_results` + `save_results` into state.py.
- Gotcha #2 (shim surface) → Tasks 2-3 maintain shim; Task 4 removes it.
- Gotcha #3 (format_rubric nested) → Task 3 keeps it nested inside pipeline.py (byte-identical move from app.py); Task 4.2a extracts to services/rubric_formatting.py; Task 4.2c fixes portal_grading.py:380 to use the new location.
- Safety net (boot check, route snapshot with methods, SIS, shim guard) → Task 1 Step 1.2 creates boot + route-snapshot tests with SIS-critical endpoint assertions; shim guard test grows through PR2-3 and deletes in PR4.
- 4-PR sequence → Tasks 1-4 map 1:1 to PR1-PR4.

**2. Placeholder scan:** No TBD/TODO remains. "exact body copied from backend/app.py:X-Y" is a delegation directive with concrete line anchors, not a placeholder. Manual smoke test commands are exact.

**3. Type consistency:** Function names (`_get_state`, `_get_lock`, `_update_state`, `reset_state`, `_create_default_state`, `load_saved_results`, `save_results`, `run_grading_thread`, `_run_grading_thread_inner`, `format_rubric_for_prompt`, `init_app`) used consistently across all 4 tasks.

**4. Risk callouts:**
- Task 1 risk: the initializer must be called AFTER all decorators have attached — the `init_app(app)` call MUST be at the bottom of the module (after every `@app.route` / `@app.after_request` / `@app.errorhandler` definition). Mitigation: route-snapshot test catches any missing registration; boot test catches import-time crashes.
- Task 3 risk: the 2000-line `_run_grading_thread_inner` is the biggest moving target. Every runtime-referenced name must be importable in pipeline.py. Mitigation: Step 3.4a's AST scan enumerates every external reference; Codex Gate 3 enforces byte-identical body; manual smoke check 3.8 confirms /api/status still routes.
- Task 4 risk: extracting `format_rubric_for_prompt` requires byte-identical body copy with dedent. Mitigation: Codex verified no closure dependencies; Step 4.10 Codex Gate 3 enforces byte-identity minus indentation normalization.
