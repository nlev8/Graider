# Export Output Directory Configurability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 19 hardcoded `os.path.expanduser("~/Downloads/Graider/...")` production sites with one call-time `backend/paths.py` resolver overridable via `GRAIDER_EXPORT_DIR`, default byte-identical, and converge test isolation onto that env var.

**Architecture:** A single call-time function `graider_export_dir(*subpath)` (no I/O, no dir creation, never bound to a module constant). All 19 sites call it; the 2 import-time module-level constants are removed in favor of call-time calls at their use sites. `tests/conftest.py` retires its brittle global `os.path.expanduser` monkeypatch for one session-autouse fixture that sets `GRAIDER_EXPORT_DIR` to a temp dir. Default behavior (env unset) is proven byte-identical per subdir; a grep gate and a zero-real-Downloads broad-suite check guard regressions.

**Tech Stack:** Python 3.14, pytest, ruff. venv at `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`). One PR.

**Spec:** `docs/superpowers/specs/2026-05-18-export-dir-config-design.md`.

**Refactor note:** site migration is a deterministic per-file literal-string replacement (each `os.path.expanduser("~/Downloads/Graider/<X>")` literal is unique and line-independent). The grep gate (Task 5) is the authoritative completeness check; line numbers below are indicative only.

**Environment note:** do NOT run `tests/load`; do not contact localhost:3000. Always `--ignore=tests/load` on pytest. The new conftest fixture (Task 4) makes the suite write to a temp dir; until Task 4 lands, the existing #412 fixture still protects real `~/Downloads`.

---

## File Structure

- **Create:** `backend/paths.py`: the only new production file. One responsibility: resolve the export base directory at call time. No I/O.
- **Create:** `tests/test_paths.py`: resolver unit + characterization tests (no network, no I/O, no dir creation).
- **Modify (12 production files, mechanical literal replace + one import each):** `backend/app.py`, `backend/routes/assignment_routes.py`, `backend/routes/grading_routes.py`, `backend/routes/analytics_routes.py`, `backend/routes/planner_routes.py`, `backend/routes/assistant_routes.py`, `backend/services/assistant_tools.py`, `backend/services/assistant_tools_grading.py`, `backend/services/assistant_tools_student.py`, `backend/services/assistant_tools_reports.py`, `backend/services/document_generator.py`, `backend/services/worksheet_generator.py`.
- **Modify:** `tests/conftest.py`: replace the #412 expanduser-monkeypatch fixture + helpers with the env-var session fixture.
- **Modify:** `CLAUDE.md`: document `GRAIDER_EXPORT_DIR` in the environment section.

---

## Task 1: The resolver + its tests (TDD)

**Files:**
- Create: `backend/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

`tests/test_paths.py`:
```python
import os
import pytest
from backend.paths import graider_export_dir


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("GRAIDER_EXPORT_DIR", raising=False)


def test_default_is_byte_identical_to_prior_expanduser():
    base = os.path.expanduser("~/Downloads/Graider")
    assert graider_export_dir() == base
    for sub in ("Results", "Assignments", "Documents", "Worksheets", "Exports"):
        assert graider_export_dir(sub) == os.path.join(base, sub)
    assert graider_export_dir("Results", "master_grades.csv") == os.path.join(
        base, "Results", "master_grades.csv"
    )


def test_env_var_overrides_base(monkeypatch, tmp_path):
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path))
    assert graider_export_dir() == str(tmp_path)
    assert graider_export_dir("Results") == os.path.join(str(tmp_path), "Results")


def test_resolved_fresh_each_call(monkeypatch, tmp_path):
    a = graider_export_dir("Results")
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path))
    b = graider_export_dir("Results")
    assert a != b and b == os.path.join(str(tmp_path), "Results")


def test_creates_no_directory(monkeypatch, tmp_path):
    target = tmp_path / "nope"
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(target))
    graider_export_dir("Results")
    assert not target.exists()
```

- [ ] **Step 2: Run, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_paths.py -q --ignore=tests/load`
Expected: FAIL, `ModuleNotFoundError: No module named 'backend.paths'`.

- [ ] **Step 3: Create `backend/paths.py`**

```python
import os


def graider_export_dir(*subpath: str) -> str:
    """Resolved export base, joined with optional subpath. Call-time only.

    ``GRAIDER_EXPORT_DIR`` overrides the base; default is the historical
    ``~/Downloads/Graider`` so behavior is byte-identical to the prior code
    when the variable is unset. Does not create directories.
    """
    base = os.environ.get("GRAIDER_EXPORT_DIR") or os.path.expanduser("~/Downloads/Graider")
    return os.path.join(base, *subpath)
```

- [ ] **Step 4: Run, confirm GREEN**

Run: `source venv/bin/activate && python -m pytest tests/test_paths.py -q --ignore=tests/load`
Expected: 4 passed.
Run: `ruff check backend/paths.py tests/test_paths.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add backend/paths.py tests/test_paths.py
git commit -m "feat(paths): call-time graider_export_dir resolver (GRAIDER_EXPORT_DIR, default byte-identical)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Migrate the 17 inline sites + the EXPORT_DIR local

**Files (modify):** `backend/app.py`, `backend/routes/grading_routes.py`, `backend/routes/assistant_routes.py`, `backend/services/assistant_tools.py`, `backend/routes/assignment_routes.py`, `backend/routes/planner_routes.py`, `backend/services/assistant_tools_grading.py`, `backend/routes/analytics_routes.py`, `backend/services/assistant_tools_student.py`, `backend/services/assistant_tools_reports.py`.

Per-file: (a) add `from backend.paths import graider_export_dir` next to the file's existing `from backend....` imports (these files already `import os`; keep `import os`, it is still used for `os.makedirs`/`os.path.join`); (b) replace each exact literal below (every occurrence in that file). Replacements are deterministic; the literal strings are unique.

- [ ] **Step 1: Apply the literal replacements**

| Exact literal (replace every occurrence in the listed files) | Replace with | Files (indicative line) |
|---|---|---|
| `os.path.expanduser("~/Downloads/Graider/Results")` | `graider_export_dir("Results")` | app.py (651, 702), grading_routes.py (135, 252), assistant_routes.py (671), assistant_tools.py (207) |
| `os.path.expanduser("~/Downloads/Graider/Assignments")` | `graider_export_dir("Assignments")` | assignment_routes.py (310), planner_routes.py (1992, 2085), assistant_tools_grading.py (844) |
| `os.path.expanduser("~/Downloads/Graider/Documents")` | `graider_export_dir("Documents")` | assignment_routes.py (552) |
| `os.path.expanduser("~/Downloads/Graider/Worksheets")` | `graider_export_dir("Worksheets")` | assignment_routes.py (566) |
| `os.path.expanduser("~/Downloads/Graider/Exports")` | `graider_export_dir("Exports")` | assignment_routes.py (580), assistant_tools_reports.py (1610, the `EXPORT_DIR = ...` local; keep the `EXPORT_DIR =` left-hand side, swap only the right-hand side) |
| `os.path.expanduser("~/Downloads/Graider/Results/master_grades.csv")` | `graider_export_dir("Results", "master_grades.csv")` | analytics_routes.py (40), assistant_tools_student.py (550) |
| `os.path.expanduser("~/Downloads/Graider")` | `graider_export_dir()` | planner_routes.py (1812) |

(`assignment_routes.py` and `planner_routes.py` each get one import line and multiple literal swaps. `document_generator.py` and `worksheet_generator.py` are Task 3, not here.)

- [ ] **Step 2: Verify each modified file imports the resolver and has no residual literal**

Run: `git grep -n "graider_export_dir" -- 'backend/*.py' ':!backend/paths.py'` (every modified file appears).
Run: `git grep -n 'os.path.expanduser("~/Downloads/Graider' -- 'backend/app.py' 'backend/routes/*.py' 'backend/services/assistant_tools.py' 'backend/services/assistant_tools_grading.py' 'backend/services/assistant_tools_student.py' 'backend/services/assistant_tools_reports.py'` → EMPTY (no residual hardcoded literal in the Task 2 files).

- [ ] **Step 3: Regression on the touched areas**

Run: `source venv/bin/activate && python -m pytest tests/ -q -k "grading or assignment or planner or analytics or assistant or export or paths" --ignore=tests/load 2>&1 | tail -3`
Expected: 0 failed.
Run: `ruff check backend/app.py backend/routes/assignment_routes.py backend/routes/grading_routes.py backend/routes/analytics_routes.py backend/routes/planner_routes.py backend/routes/assistant_routes.py backend/services/assistant_tools.py backend/services/assistant_tools_grading.py backend/services/assistant_tools_student.py backend/services/assistant_tools_reports.py` → clean.

- [ ] **Step 4: Commit**

```bash
git add backend/app.py backend/routes/assignment_routes.py backend/routes/grading_routes.py backend/routes/analytics_routes.py backend/routes/planner_routes.py backend/routes/assistant_routes.py backend/services/assistant_tools.py backend/services/assistant_tools_grading.py backend/services/assistant_tools_student.py backend/services/assistant_tools_reports.py
git commit -m "refactor(paths): route 17 inline export-dir sites through graider_export_dir

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Remove the 2 import-time module-level constants (call-time conversion)

**Files (modify):** `backend/services/document_generator.py`, `backend/services/worksheet_generator.py`
**Test:** `tests/test_paths.py` (extend)

- [ ] **Step 1: Write the failing characterization test**

Append to `tests/test_paths.py`:
```python
def test_document_and_worksheet_dirs_byte_identical_default():
    base = os.path.expanduser("~/Downloads/Graider")
    assert graider_export_dir("Documents") == os.path.join(base, "Documents")
    assert graider_export_dir("Worksheets") == os.path.join(base, "Worksheets")
    import backend.services.document_generator as dg
    import backend.services.worksheet_generator as wg
    assert not hasattr(dg, "DOCUMENTS_DIR"), "import-time DOCUMENTS_DIR must be removed"
    assert not hasattr(wg, "WORKSHEETS_DIR"), "import-time WORKSHEETS_DIR must be removed"
```

- [ ] **Step 2: Run, confirm RED**

Run: `source venv/bin/activate && python -m pytest tests/test_paths.py::test_document_and_worksheet_dirs_byte_identical_default -q --ignore=tests/load`
Expected: FAIL on the `not hasattr` assertions (the constants still exist).

- [ ] **Step 3: Convert `document_generator.py`**

- Delete the module-level line `DOCUMENTS_DIR = os.path.expanduser("~/Downloads/Graider/Documents")` (currently line 22).
- Add `from backend.paths import graider_export_dir` with the other `from backend....`/imports near the top (keep `import os`).
- Replace the makedirs ref (currently line 742) `os.makedirs(DOCUMENTS_DIR, exist_ok=True)` with `os.makedirs(graider_export_dir("Documents"), exist_ok=True)`.
- Replace the join ref (currently line 748) `os.path.join(DOCUMENTS_DIR, filename)` with `os.path.join(graider_export_dir("Documents"), filename)`.

- [ ] **Step 4: Convert `worksheet_generator.py`**

- Delete the module-level line `WORKSHEETS_DIR = os.path.expanduser("~/Downloads/Graider/Worksheets")` (currently line 27).
- Add `from backend.paths import graider_export_dir` near the top imports (keep `import os`).
- Replace the makedirs ref (currently line 627) `os.makedirs(WORKSHEETS_DIR, exist_ok=True)` with `os.makedirs(graider_export_dir("Worksheets"), exist_ok=True)`.
- Replace the join ref (currently line 635) `os.path.join(WORKSHEETS_DIR, filename)` with `os.path.join(graider_export_dir("Worksheets"), filename)`.

(Only two references per module, so no separate accessor function is warranted; the resolver call is the call-time form. Verify there are no other `DOCUMENTS_DIR`/`WORKSHEETS_DIR` references before deleting: `git grep -n "\bDOCUMENTS_DIR\b" backend/ ; git grep -n "\bWORKSHEETS_DIR\b" backend/` must show only the lines being changed and nothing else after.)

- [ ] **Step 5: Run, confirm GREEN + regression**

Run: `source venv/bin/activate && python -m pytest tests/test_paths.py -q --ignore=tests/load` → all pass.
Run: `python -m pytest tests/ -q -k "document or worksheet or generator or assignment or export or paths" --ignore=tests/load 2>&1 | tail -3` → 0 failed.
Run: `git grep -n "\bDOCUMENTS_DIR\b\|\bWORKSHEETS_DIR\b" -- 'backend/*.py'` → EMPTY (constants fully gone).
Run: `ruff check backend/services/document_generator.py backend/services/worksheet_generator.py tests/test_paths.py` → clean.

- [ ] **Step 6: Commit**

```bash
git add backend/services/document_generator.py backend/services/worksheet_generator.py tests/test_paths.py
git commit -m "refactor(paths): remove import-time DOCUMENTS_DIR/WORKSHEETS_DIR; resolve at call time

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Converge conftest onto the GRAIDER_EXPORT_DIR session fixture

**Files (modify):** `tests/conftest.py`

- [ ] **Step 1: Replace the #412 mechanism**

Remove entirely: the `_real_downloads_graider` module-level, the `_OUTPUT_SUBDIRS` frozenset, the `_is_output_path` function, the `_redirect_downloads_graider` fixture, AND the explanatory comment block above them that describes the expanduser-monkeypatch approach. Replace with this single fixture (place where `_redirect_downloads_graider` was):

```python
# ---------------------------------------------------------------------------
# Export-dir isolation: every ~/Downloads/Graider write resolves through
# backend.paths.graider_export_dir(), which honors GRAIDER_EXPORT_DIR. Setting
# that env var session-wide (before any test body runs) guarantees no test can
# write to a developer's real Downloads. Single mechanism; no global monkeypatch.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _redirect_graider_export_dir():
    prev = os.environ.get("GRAIDER_EXPORT_DIR")
    tmp = tempfile.mkdtemp(prefix="graider_test_exports_")
    os.environ["GRAIDER_EXPORT_DIR"] = tmp
    yield tmp
    if prev is None:
        os.environ.pop("GRAIDER_EXPORT_DIR", None)
    else:
        os.environ["GRAIDER_EXPORT_DIR"] = prev
    shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Remove now-dead imports**

After the removal, check whether `unittest.mock` is still used anywhere in `tests/conftest.py`: `grep -nE "unittest|mock\." tests/conftest.py`. If `import unittest.mock` (or `import unittest`) is now unused, delete that import line (do not strand a dead import). Confirm `os`, `tempfile`, `shutil`, `pytest` are still used (the new fixture uses all four) and keep them.

- [ ] **Step 3: Prove isolation holds (the check that caught the original incident)**

Run:
```bash
source venv/bin/activate
LP_b=$(ls ~/Downloads/Graider/Lesson_Plan_*.docx 2>/dev/null | wc -l | tr -d ' ')
RS_b=$(ls ~/Downloads/Graider/Results/*.csv 2>/dev/null | wc -l | tr -d ' ')
python -m pytest tests/ -q -k "export or paths or grading or assignment or planner or worksheet or document or analytics or assistant" --ignore=tests/load 2>&1 | tail -3
LP_a=$(ls ~/Downloads/Graider/Lesson_Plan_*.docx 2>/dev/null | wc -l | tr -d ' ')
RS_a=$(ls ~/Downloads/Graider/Results/*.csv 2>/dev/null | wc -l | tr -d ' ')
echo "real ~/Downloads/Graider Lesson_Plan $LP_b->$LP_a ; Results csv $RS_b->$RS_a (MUST be equal)"
```
Expected: 0 failed AND `LP_b==LP_a` AND `RS_b==RS_a` (zero new real-Downloads writes across a broad export-touching slice). Also confirm a `graider_test_exports_*` dir was created under the system temp dir (proves the redirect is active, not that nothing ran).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): converge export isolation onto GRAIDER_EXPORT_DIR; retire expanduser monkeypatch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Grep gate, docs, full regression, closeout

**Files (modify):** `CLAUDE.md`

- [ ] **Step 1: Grep gate (authoritative completeness check)**

Run: `git grep -n 'os.path.expanduser("~/Downloads/Graider' -- 'backend/**/*.py' 'backend/*.py' ':!backend/paths.py'`
Expected: EMPTY. The only allowed `os.path.expanduser("~/Downloads/Graider")` in production is the default inside `backend/paths.py`. If anything else prints, that site was missed; migrate it (literal rule from Task 2) before proceeding.
Run: `git grep -n "\bDOCUMENTS_DIR\b\|\bWORKSHEETS_DIR\b" -- 'backend/*.py'` → EMPTY.

- [ ] **Step 2: Document the env var in CLAUDE.md**

In `CLAUDE.md`, in the "Environment Variables" section under "### Optional" (or the nearest optional/dev subsection), add a line:
```
- `GRAIDER_EXPORT_DIR` — Base directory for generated exports (docx/csv/etc.). Defaults to `~/Downloads/Graider`. Override to redirect all export output (used by the test suite to isolate to a temp dir).
```
Match the exact bullet format of the surrounding entries in CLAUDE.md's Environment Variables section: those entries use ` term ` then a separator then the definition (the file uses an em-dash separator consistently across that whole list). Use whatever separator the adjacent entries already use so the new line is visually identical to its siblings; do not introduce a different style for this one entry. This is the one place an em-dash is acceptable, because it is matching an existing structured data-list convention in that file, not authored narrative prose.

- [ ] **Step 3: Full regression + lint**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load 2>&1 | tail -5`
Expected: 0 failed (the only acceptable pre-existing flaky failures are documented `tests/load` cases, which are excluded by `--ignore=tests/load`; if any non-load test fails, fix it before proceeding).
Run: `ruff check backend/ tests/test_paths.py tests/conftest.py 2>&1 | tail -2` → no new findings vs main (`backend/` has pre-existing T201s unrelated to this change; this change introduces none).
Run the grep gate (Step 1) once more to confirm still empty after the full run.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(env): document GRAIDER_EXPORT_DIR

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec coverage:** §1 goal → Goal + Task 1. §2 problem (19 sites/12 files, 2 import-time constants, EXPORT_DIR local) → Tasks 2+3 with the exact literal table and the 2-constant conversion. §3 resolver (call-time, no I/O, no dir creation) → Task 1 code + `test_creates_no_directory` + `test_resolved_fresh_each_call`. §4 migration + the 2 constants → Tasks 2 and 3. §5 conftest convergence (single env fixture, brittle patch removed, dead-import cleanup) → Task 4 incl. Step 2 (the #418 stranded-import lesson). §6 verification net (per-subdir default-equivalence, grep gate, regression, zero real-Downloads) → Task 1 tests + Task 4 Step 3 + Task 5 Steps 1/3. §8 scope (out: `_get_export_dir` untouched, no makedirs/behavior change) → no task touches `planner_export._get_export_dir`; makedirs calls left verbatim (Task 2/3 only swap the path expression). §9 risks → grep gate (missed site), Task 4 Step 3 (isolation regression), Task 3 (import-capture), per-subdir default proof (drift). §10 success criteria → Tasks 1-5.
- **Placeholder scan:** no TBD/TODO/"add error handling"/vague steps; every code/command step is concrete; the literal-replacement table gives exact strings; line numbers are explicitly indicative with the grep gate as authority (not placeholders).
- **Type/name consistency:** `graider_export_dir` (one name, identical signature everywhere), `GRAIDER_EXPORT_DIR` (one env var), `_redirect_graider_export_dir` (the new fixture), the removed names (`_redirect_downloads_graider`, `_is_output_path`, `_OUTPUT_SUBDIRS`, `_real_downloads_graider`, `DOCUMENTS_DIR`, `WORKSHEETS_DIR`) are consistent across the spec, all tasks, and this self-review.
