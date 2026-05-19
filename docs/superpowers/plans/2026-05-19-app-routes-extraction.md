# app.py Route God-Module Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the 16 domain API routes (grading-results CRUD, FERPA data, student-history/roster) out of `backend/app.py` (1,935 LOC) into three responsibility-named Flask Blueprints, with zero behavior change, behind an exhaustive route-level characterization net.

**STATUS: CLOSED 2026-05-19** -> shipped via PR1 #424, PR2 #425, PR3 (this PR). app.py 1935 -> 585 LOC; 16 routes extracted into grading_results_routes / ferpa_routes / roster_routes; only the SPA/factory shell remains.

**Architecture:** Verbatim `@app.route` to `@bp.route` moves into `backend/routes/{grading_results,ferpa,roster}_routes.py`, each a `Blueprint` registered through the existing `backend/routes/__init__.py` `register_routes()` aggregator (one import line plus one `app.register_blueprint(...)` line per PR, no `url_prefix`, byte-identical paths and decorator stacks). Three sequenced PRs small to big, mirroring the proven Slice 1 and 2 shape. The SPA/static shell and factory stay in `app.py`.

**Tech Stack:** Python 3.14, Flask Blueprints, pytest with the existing `tests/conftest_routes.py` authed `client` fixture, ruff. venv `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`). One slice, three PRs.

**Spec:** `docs/superpowers/specs/2026-05-19-app-routes-extraction-design.md`. The section 3 coupling rule governs every task: a route is extracted only if its blueprint imports with no cycle back into `backend.app`; if a clean move is infeasible the route stays and is recorded.

**Refactor-plan note:** moves are verbatim. Steps specify exact source ranges, the blueprint skeleton, the registration lines, and the full new test code. Moved route/helper bodies are NOT re-pasted (re-pasting unchanged code is error-prone); they are identified by exact location and verified byte-identical with `diff`. Line numbers below are current-state and shift as earlier PRs land; each task re-derives them and the URL-map equality test plus the per-cluster grep are the authoritative gates.

**Environment note:** do NOT run `tests/load`; always `--ignore=tests/load`; do not contact :3000. The merged `GRAIDER_EXPORT_DIR` conftest fixture keeps the suite from writing to real `~/Downloads`.

---

## File Structure

- **Create:** `backend/routes/grading_results_routes.py` (PR1), `backend/routes/ferpa_routes.py` (PR2), `backend/routes/roster_routes.py` (PR3). Each: one Blueprint, the routes for its cluster, cluster-internal helpers, only the imports the moved bodies use; never imports `backend.app`.
- **Modify:** `backend/routes/__init__.py`. Add one `from .X_routes import X_bp` line + one `app.register_blueprint(X_bp)` line per PR.
- **Modify:** `backend/app.py`. Delete the moved routes/helpers and the imports left unused after each cluster leaves; PR2 also removes the dead `AUDIT_LOG_FILE` module constant (line ~243) once the FERPA cluster no longer references it.
- **Create:** `tests/test_grading_results_routes_char.py` (PR1), `tests/test_ferpa_routes_char.py` (PR2), `tests/test_roster_routes_char.py` (PR3). These are the exhaustive route-level characterization nets.
- **Modify:** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` and this plan (PR3 closeout).

Stays in `app.py` (out of scope): `/`, `/join*`, `/student*`, `/district*`, `/<path:path>`, `/healthz`, `/api/user-manual`, `set_security_headers`, `handle_404`/`handle_500`, `_handle_sigterm`, `init_app`, the `Flask(static_folder=...)` setup.

---

## Shared context for all three PRs

**The authed test client.** `tests/conftest_routes.py` exposes a `client` fixture: it builds an app, calls `from backend.routes import register_routes; register_routes(app, get_state, run_grading, reset, get_lock)`, and sets `g.user_id = 'test-teacher'` via `before_request`, so requests are authenticated as a teacher and grading state is mocked (`mock_grading_state`). A net test does `from tests.conftest_routes import client` (pytest fixture) and `client.post(...)`/`client.get(...)`. For the auth-missing case, reuse the exact pattern an existing route test already uses to exercise a `@require_teacher` rejection (grep `tests/` for a test that asserts 401 or 403 on a `@require_teacher` route, e.g. in `tests/test_grading_routes.py` or `tests/test_assignment_routes_unit.py`, and copy that mechanism; do not invent a new auth bypass).

**Blueprint skeleton** (mirrors `backend/routes/grading_routes.py`): first line a module docstring; then the imports the moved bodies actually use (determine by reading them; expect a subset of `import logging, os, csv, json, sys, subprocess, threading`, `from datetime import datetime`, `from flask import Blueprint, request, jsonify, g`, `from backend.utils.auth_decorators import require_teacher`, `from backend.utils.errors import handle_route_errors`, `from backend.grading.state import _get_state, _get_lock, reset_state, _grading_states, _states_meta_lock`, `from backend.grading.thread import run_grading_thread`, `from backend.paths import graider_export_dir`, `import sentry_sdk`); then `X_bp = Blueprint('<name>', __name__)` and `_logger = logging.getLogger(__name__)`; then the moved routes and helpers verbatim. No `url_prefix`. Never `import backend.app` or `from backend.app import ...`.

**Registration** (`backend/routes/__init__.py`): add `from .grading_results_routes import grading_results_bp` (etc.) to the import block (after the existing `from .X_routes import X_bp` lines) and `app.register_blueprint(grading_results_bp)` (etc.) inside `register_routes()` next to the other `app.register_blueprint(...)` calls.

**Verbatim move mechanics:** for each route, the only change is the decorator token `@app.route(` -> `@bp.route(` (path string and `methods=[...]` byte-identical), and relocation; the full stacked decorator list (`@require_teacher`, `@handle_route_errors`, any rate-limit, in original order) and the function body are byte-identical. Cluster-internal helpers (defined inside the moved range, called only by moved routes) move with the cluster unchanged. After moving a cluster, delete it from `app.py` and remove any `app.py` import/constant left unused solely because the cluster left (verify with a usage grep before deleting).

---

## PR 1: grading-results CRUD -> `backend/routes/grading_results_routes.py`

Routes (current lines; re-derive before editing): `/api/grade-individual` (deco 480, def `grade_individual` 484), `/api/delete-result` (deco 759, def `delete_single_result` 762), `/api/update-approval` (deco 810, def `update_approval` 813), `/api/update-approvals-bulk` (deco 845, def `update_approvals_bulk` 848). Cluster-internal helpers co-moved: `_remove_from_master_csv` (def 649), `_sync_approval_to_master_csv` (def 700); both sit between `grade_individual` and `delete_single_result` and are called only by these routes (verify with `grep -n "_remove_from_master_csv\|_sync_approval_to_master_csv" backend/app.py`; if any caller outside the four routes exists, STOP and report).

### Task 1.1: Caller/coupling audit + branch

- [ ] **Step 1:** `git checkout main && git pull origin main && git checkout -b feature/slice3-pr1-grading-results`.
- [ ] **Step 2:** Confirm the 4 route decorators and 2 helper defs by content (`grep -nE "^@app\.route\('/api/(grade-individual|delete-result|update-approval|update-approvals-bulk)'" backend/app.py` and `grep -nE "^def (grade_individual|delete_single_result|update_approval|update_approvals_bulk|_remove_from_master_csv|_sync_approval_to_master_csv)\b" backend/app.py`). Record exact `def`-to-next-`def` body ranges including the full decorator stack above each route `def`.
- [ ] **Step 3:** Coupling check. `python3` scan: for the 4 route bodies + 2 helper bodies, list every called name that is an `app.py` module-level `def` NOT in this cluster. Expected empty (shared state is imported from `backend.grading.state`). If non-empty, that route stays and is recorded (section 3 escape hatch); report it before proceeding.

### Task 1.2: Exhaustive net pinned against current wiring

**Files:** `tests/test_grading_results_routes_char.py` (create)

- [ ] **Step 1: Write the net** covering each of the 4 routes times {happy path, auth-missing, invalid/empty input}, plus for `/api/delete-result` and `/api/update-approvals-bulk` the not-found / empty-state / partial-match branches and the exact response JSON. Use the `client` fixture from `tests/conftest_routes.py`. Probe the real response with a one-off `python -c`/`pytest -q` first and pin the EXACT observed status + JSON (characterization discipline: pin reality, never assume; if a path raises today, pin that). Skeleton:

```python
from tests.conftest_routes import client  # noqa: F401  (pytest fixture)


def test_grade_individual_happy(client):
    resp = client.post('/api/grade-individual', json={...})  # fill from a real probe
    assert resp.status_code == 200          # pin the real observed code
    assert resp.get_json() == {...}         # pin the real observed body


def test_delete_result_not_found(client):
    resp = client.post('/api/delete-result', json={'filename': '__does_not_exist__'})
    assert resp.status_code == ...          # pin real
    assert resp.get_json() == {...}         # pin real
# ... happy/auth-missing/invalid for all 4 routes; not-found/empty/partial + exact body
# for delete-result and update-approvals-bulk. Auth-missing: reuse the existing
# require_teacher-rejection test mechanism (see Shared context).
```

- [ ] **Step 2:** Run `source venv/bin/activate && python -m pytest tests/test_grading_results_routes_char.py -q --ignore=tests/load` -> ALL PASS (this pins the pre-move contract against the current `@app.route` wiring). Commit just this net: `git add tests/test_grading_results_routes_char.py && git commit -m "test(routes): pin grading-results route contract pre-move (Slice 3 PR1)"`. Report case count.

### Task 1.3: Create blueprint, verbatim-move, register, delete from app.py

**Files:** create `backend/routes/grading_results_routes.py`; modify `backend/routes/__init__.py`, `backend/app.py`

- [ ] **Step 1: RED unit test.** Append to the char file:
```python
def test_blueprint_importable():
    from backend.routes.grading_results_routes import grading_results_bp
    assert grading_results_bp.name == 'grading_results'
```
Run it -> FAIL (ModuleNotFoundError).
- [ ] **Step 2:** Create `backend/routes/grading_results_routes.py` with the docstring, the imports the 4 routes + 2 helpers actually use (read the bodies; no `backend.app` import), `grading_results_bp = Blueprint('grading_results', __name__)`, `_logger = logging.getLogger(__name__)`, then the 2 helpers and 4 routes pasted byte-identically with `@app.route(` -> `@grading_results_bp.route(` (path + methods unchanged; full decorator stack preserved).
- [ ] **Step 3:** In `backend/routes/__init__.py`: add `from .grading_results_routes import grading_results_bp` to the import block and `app.register_blueprint(grading_results_bp)` inside `register_routes()` next to the others.
- [ ] **Step 4:** Delete the 4 routes + 2 helpers from `backend/app.py`. Then grep `app.py` for each import used only by the removed code (e.g. a now-unused `from ... import ...`) and remove only those proven-unused lines (verify each with `grep -n`). Do NOT remove imports still used by remaining `app.py` code.
- [ ] **Step 5: Verbatim-integrity check.** `git show HEAD:backend/app.py | sed -n '<each range>p' > /tmp/o.txt`; extract the same bodies from `grading_results_routes.py` -> `/tmp/n.txt`; `diff` must show only the `@app.route(`->`@grading_results_bp.route(` decorator token change per route and nothing else in any body. Report the diff.
- [ ] **Step 6: GREEN + URL-map + regression.**
  - Re-point the net's import if needed; `python -m pytest tests/test_grading_results_routes_char.py -q --ignore=tests/load` -> ALL PASS unchanged (zero-behavior-change proof).
  - URL-map gate: a test asserting the moved URLs still resolve to the same rule. Add to the char file:
    ```python
    def test_urls_unchanged(flask_app):  # flask_app from conftest_routes
        rules = {r.rule for r in flask_app.url_map.iter_rules()}
        for u in ('/api/grade-individual', '/api/delete-result',
                  '/api/update-approval', '/api/update-approvals-bulk'):
            assert u in rules
    ```
  - `python -m pytest tests/ -q -k "grading or result or approval or route or paths" --ignore=tests/load 2>&1 | tail -3` -> 0 failed.
  - `git grep -nE "^@app\.route\('/api/(grade-individual|delete-result|update-approval|update-approvals-bulk)'" backend/app.py` -> EMPTY (moved). `grep -n "backend.app" backend/routes/grading_results_routes.py` -> EMPTY (no cycle).
  - `ruff check backend/routes/grading_results_routes.py backend/routes/__init__.py backend/app.py tests/test_grading_results_routes_char.py` -> clean / no new findings.
- [ ] **Step 7: Commit**
```bash
git add backend/routes/grading_results_routes.py backend/routes/__init__.py backend/app.py tests/test_grading_results_routes_char.py
git commit -m "$(printf 'refactor(routes): extract grading-results CRUD to grading_results_routes blueprint (Tier 2 Slice 3 PR1)\n\nVerbatim @app.route->@bp.route move of 4 routes + 2 cluster-internal\nCSV-sync helpers, registered via register_routes. Exhaustive route-level\nnet pinned pre-move stays byte-identical post-move; URL map unchanged.\nZero behavior change.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

### Task 1.4: Open PR 1: 9 checks green, squash-merge, sync main. (Controller opens/merges; two-stage review first.)

---

## PR 2: FERPA -> `backend/routes/ferpa_routes.py`

Routes (current; re-derive): `/api/ferpa/delete-all-data` (def `delete_all_student_data` 880), `/api/ferpa/audit-log` (def `get_audit_log` 940), `/api/ferpa/data-summary` (def `get_data_summary` 958), `/api/ferpa/export-data` (def `export_student_data` 1002), `/api/ferpa/export-student` (def `export_individual_student_data` 1033), `/api/ferpa/import-student` (def `import_individual_student_data` 1301). Co-move `get_audit_logs` (def 254, OUTSIDE the cluster, sole production caller is `get_audit_log`; verify with `grep -rn "get_audit_logs" backend/ --include=*.py | grep -v test`).

### Task 2.1: Net pinned pre-move

**Files:** `tests/test_ferpa_routes_char.py` (create)

- [ ] **Step 1:** `git checkout main && git pull && git checkout -b feature/slice3-pr2-ferpa`. Build the exhaustive net for the 6 FERPA routes times {happy, auth-missing, invalid/empty}, and for the destructive/PII routes (`delete-all-data`, `export-data`, `export-student`) the not-found / empty-state / partial-match branches plus the EXACT serialized body (probe real output first; pin reality including the audit-log shape from `get_audit_logs`). `from tests.conftest_routes import client`.
- [ ] **Step 2:** `source venv/bin/activate && python -m pytest tests/test_ferpa_routes_char.py -q --ignore=tests/load` -> ALL PASS. Commit baseline: `git commit -am "test(routes): pin FERPA route contract pre-move (Slice 3 PR2)"`. Report case count.

### Task 2.2: RED + verbatim-move + get_audit_logs co-move + dead-constant removal

- [ ] **Step 1:** RED: `def test_ferpa_bp_importable(): from backend.routes.ferpa_routes import ferpa_bp; assert ferpa_bp.name == 'ferpa'` -> FAIL.
- [ ] **Step 2:** Create `backend/routes/ferpa_routes.py` (docstring; imports the 6 routes + `get_audit_logs` use; note `get_audit_logs` reads `AUDIT_LOG_FILE`: import it as `from backend.utils.audit import AUDIT_LOG_FILE` (the canonical module), NOT a local copy; no `backend.app` import; `ferpa_bp = Blueprint('ferpa', __name__)`). Paste the 6 routes verbatim with `@app.route(`->`@ferpa_bp.route(`, and `get_audit_logs` verbatim except its `AUDIT_LOG_FILE` reference now resolves via the `backend.utils.audit` import (the value is byte-identical: `os.path.expanduser("~/.graider_audit.log")` in all copies; confirm equality before relying on it).
- [ ] **Step 3:** Register `ferpa_bp` in `backend/routes/__init__.py` (import line + `app.register_blueprint`).
- [ ] **Step 4:** Delete the 6 routes + `get_audit_logs` from `app.py`. Then run `grep -n "AUDIT_LOG_FILE" backend/app.py`: if zero references remain (the FERPA routes were its only users; confirm), delete the `AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")` module constant (~line 243) as a dead-constant cleanup. If any `app.py` code still uses it, leave it and report. Remove any other import left unused only by the departed FERPA code (verify each).
- [ ] **Step 5:** Verbatim-integrity `diff` (the only allowed per-route diff is the decorator token; for `get_audit_logs` the only allowed diff is the `AUDIT_LOG_FILE` now coming from the import; confirm the function logic bytes are otherwise identical).
- [ ] **Step 6:** GREEN: net byte-identical pass; URL-map test for the 6 `/api/ferpa/*` URLs; `python -m pytest tests/ -q -k "ferpa or audit or export or route or paths" --ignore=tests/load 2>&1 | tail -3` -> 0 failed; `grep -n "backend.app" backend/routes/ferpa_routes.py` -> EMPTY; `git grep -nE "^@app\.route\('/api/ferpa/" backend/app.py` -> EMPTY; ruff clean on the changed files.
- [ ] **Step 7: Commit**
```bash
git add backend/routes/ferpa_routes.py backend/routes/__init__.py backend/app.py tests/test_ferpa_routes_char.py
git commit -m "$(printf 'refactor(routes): extract FERPA data routes to ferpa_routes blueprint (Tier 2 Slice 3 PR2)\n\nVerbatim move of 6 FERPA routes; get_audit_logs co-moved (sole caller is\nthe ferpa audit-log route) using the canonical backend/utils/audit\nAUDIT_LOG_FILE; the now-dead app.py AUDIT_LOG_FILE constant removed.\nExhaustive net pinned pre-move stays byte-identical; URL map unchanged.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

### Task 2.3: Open PR 2: 9 checks green, squash-merge, sync main. (Two-stage review first.)

---

## PR 3: student-history/roster -> `backend/routes/roster_routes.py` + slice closeout

Routes (current; re-derive): `/api/student-history/<student_id>` (def `get_student_history_api` 1521), `/api/student-baseline/<student_id>` (def `get_student_baseline_api` 1536), `/api/retranslate-feedback` (def `retranslate_feedback` 1551), `/api/extract-student-from-image` (def `extract_student_from_image` 1587), `/api/add-student-to-roster` (def `add_student_to_roster` 1659), `/api/list-periods` (def `list_periods` 1734).

### Task 3.1: Net pinned pre-move

- [ ] **Step 1:** `git checkout main && git pull && git checkout -b feature/slice3-pr3-roster`. Create `tests/test_roster_routes_char.py` covering the 6 routes times {happy, auth-missing, invalid/empty} (probe + pin real). `python -m pytest tests/test_roster_routes_char.py -q --ignore=tests/load` -> ALL PASS. Commit baseline. Report case count.

### Task 3.2: RED + verbatim-move + register + delete

- [ ] **Step 1:** RED `test_roster_bp_importable` -> FAIL.
- [ ] **Step 2:** Create `backend/routes/roster_routes.py` (docstring; only the imports the 6 bodies use, read them; no `backend.app`; `roster_bp = Blueprint('roster', __name__)`). Paste the 6 routes verbatim with `@app.route(`->`@roster_bp.route(` (note two carry a `<student_id>` path param, preserve the path string and the `def f(student_id)` signature exactly).
- [ ] **Step 3:** Register `roster_bp` in `backend/routes/__init__.py`.
- [ ] **Step 4:** Delete the 6 routes from `app.py`; remove imports left unused only by them (verify each).
- [ ] **Step 5:** Verbatim-integrity `diff` (only the decorator token differs per route).
- [ ] **Step 6:** GREEN: net byte-identical; URL-map test for the 6 URLs (including the two `<student_id>` rules); `python -m pytest tests/ -q -k "roster or student_history or baseline or retranslate or route or paths" --ignore=tests/load 2>&1 | tail -3` -> 0 failed; no `backend.app` import in the new module; `git grep` confirms the 6 routes gone from `app.py`; ruff clean.
- [ ] **Step 7: Commit** (`refactor(routes): extract student-history/roster routes to roster_routes blueprint (Tier 2 Slice 3 PR3)`, with the standard trailer).

### Task 3.3: Slice closeout

**Files:** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`, this plan

- [ ] **Step 1:** Final gates: `git grep -nE "^@app\.route\('/api/(grade-individual|delete-result|update-approval|update-approvals-bulk|ferpa/|student-history|student-baseline|retranslate-feedback|extract-student-from-image|add-student-to-roster|list-periods)" backend/app.py` -> EMPTY (all 16 gone). Record `wc -l backend/app.py` (target ~650). Full regression `python -m pytest tests/ -q --ignore=tests/load 2>&1 | tail -5` -> 0 failed. The 9 existing route/integration suites green. `ruff check backend/ -q` no new findings.
- [ ] **Step 2:** Append a dated section to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (house style; NO em-dash U+2014; no AI-tells): Slice 3 shipped (PR numbers, `app.py` before/after LOC, the 3 blueprints + route counts, the `get_audit_logs` co-move + canonical `AUDIT_LOG_FILE` + dead-constant removal, recorded out-of-scope: the 4x AUDIT_LOG_FILE dup, dual publish-path, PlannerTab.jsx). State that a 3-model reconciled re-score follows (Architecture 7->8 is a judgment call) and will be its own dated section.
- [ ] **Step 3:** STATUS-stamp this plan CLOSED right after the `**Goal:**` line (PR numbers, app.py LOC delta). Commit docs. Open PR 3 (two-stage review first); 9 checks; squash-merge; sync main.

### Task 3.4: Post-slice 3-model reconciled re-score (judgment work, separate from the verbatim PRs)

- [ ] After PR3 merges: Codex + Gemini + Claude independently re-score vs the 2026-05-18 baseline (does Architecture move 7->8 now the `app.py` god-module is gone?), conservative-floor reconcile, append the dated section. This is the established post-slice judgment step, not part of the mechanical extraction.

---

## Self-Review

- **Spec coverage:** §1 goal -> Goal + all PRs. §2 (16 routes, SPA shell stays, state already in backend/grading) -> File Structure + Shared context. §3 coupling rule -> Task 1.1 Step 3 audit, the no-`backend.app`-import grep gate per PR, the `get_audit_logs`+canonical-`AUDIT_LOG_FILE`+dead-constant handling in PR2 Task 2.2 Steps 2/4. §4 exact route lists -> PR1/PR2/PR3 route tables. §5 sequencing -> 3 sequenced PRs small->big, net pinned pre-move per cluster. §6 exhaustive net -> Task X.1 + X.2 with the cross-product and the destructive/PII extra branches and the authed `client` fixture. §7 approach -> 3 responsibility blueprints. §8 scope (SPA/factory stays; 4x dup + dual-path + PlannerTab out) -> File Structure "stays" list + closeout recorded out-of-scope. §9 risks -> verbatim diff check (decorator-token-only), URL-map gate, no-cycle grep, full regression. §10 success criteria -> Task 3.3 + 3.4.
- **Placeholder scan:** no TBD/vague steps; the char-net `{...}` placeholders are explicitly "probe the real response and pin exactly", which is the characterization method, not an unfilled blank; verbatim bodies intentionally not re-pasted per the Refactor-plan note; PR numbers assigned at open time (unavoidable, not a content placeholder).
- **Type/name consistency:** blueprint names (`grading_results_bp`/'grading_results', `ferpa_bp`/'ferpa', `roster_bp`/'roster'), module paths (`backend/routes/{grading_results,ferpa,roster}_routes.py`), the 16 route paths, the co-moved `get_audit_logs`, and the `register_routes` wiring are identical across the spec, all tasks, and this self-review.
