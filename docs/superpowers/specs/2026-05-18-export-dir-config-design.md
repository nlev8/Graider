# Export Output Directory Configurability: Design

**Date:** 2026-05-18
**Status:** Design approved (user approved 2026-05-18). Next: writing-plans.
**Context:** Production-side root-cause fix for the defect class behind the docx-spam incident. The export routes hardcode `os.path.expanduser("~/Downloads/Graider/...")` at 19 sites across 12 files; #412 only bandaged the test side (a conftest `os.path.expanduser` monkeypatch). This makes the export base overridable via one env var, with byte-identical behavior for real users when the variable is unset, and converges test isolation onto a single mechanism.

## 1. Goal

Replace the hardcoded `os.path.expanduser("~/Downloads/Graider/...")` at all 19 production sites with a single call-time resolver in a new `backend/paths.py`, so the export base is overridable via `GRAIDER_EXPORT_DIR`, default behavior unchanged for real users, and the brittle global test monkeypatch is retired. This raises Operational Safety and Code Quality with no behavior change for real users.

## 2. Problem

19 production sites across 12 files compute output paths as `os.path.expanduser("~/Downloads/Graider/<Subdir>")` (subdirs `Results`, `Assignments`, `Documents`, `Worksheets`, `Exports`, the bare root, and `Results/master_grades.csv`). Two of these are import-time module-level constants that capture the path at import (`backend/services/document_generator.py:22 DOCUMENTS_DIR`, `backend/services/worksheet_generator.py:27 WORKSHEETS_DIR`); the rest are inline in functions, including `backend/services/assistant_tools_reports.py:1610 EXPORT_DIR` which is a function-local variable (resolved at call time already, so it migrates as a normal site, not as an import-time constant). This was verified during planning. The path is not configurable, which caused real damage: a stale dev server plus the test suite spammed a developer's real Downloads with junk docx (the docx-spam incident). PR #412 fixed only the test side, with a brittle global `os.path.expanduser` monkeypatch in `tests/conftest.py` (`_redirect_downloads_graider` plus an `_is_output_path` allowlist). The production hardcoding remains the root cause, and the test-isolation story is two parallel mechanisms.

The separate helper `_get_export_dir()` in `backend/services/planner_export.py` (a `tempfile.gettempdir()/graider_exports` path for ephemeral study-guide and flashcard output) is a different semantic and is out of scope; it is not touched.

## 3. The resolver: `backend/paths.py` (new)

A single call-time function, no I/O, no directory creation, never bound to a module-level constant:

```python
import os

def graider_export_dir(*subpath: str) -> str:
    """Resolved export base, joined with optional subpath. Call-time only.

    GRAIDER_EXPORT_DIR overrides the base; default is the historical
    ~/Downloads/Graider so behavior is byte-identical to the prior code
    when the variable is unset. Does not create directories.
    """
    base = os.environ.get("GRAIDER_EXPORT_DIR") or os.path.expanduser("~/Downloads/Graider")
    return os.path.join(base, *subpath)
```

`graider_export_dir("Results")` returns `<base>/Results`; `graider_export_dir()` returns the bare base (the `planner_routes.py` lesson-plan case); `graider_export_dir("Results", "master_grades.csv")` returns the csv path. The base is read on every call, so the value can change between calls (this is what makes the session-scoped test fixture work and prevents import-time capture).

## 4. Migration of the 19 sites and the 2 import-time constants

Every `os.path.expanduser("~/Downloads/Graider/<X>")` becomes `graider_export_dir("<X>")`, one line each, mechanical. Existing `os.makedirs(..., exist_ok=True)` calls at each site are left exactly as they are (the resolver returns a path only and creates nothing), so directory-creation behavior is unchanged.

The two module-level constants are the one non-mechanical part. `DOCUMENTS_DIR` (`document_generator.py:22`) and `WORKSHEETS_DIR` (`worksheet_generator.py:27`) are evaluated at import time, which would capture the path before the session test fixture sets the env var. Each module has exactly two internal references to its constant (an `os.makedirs(...)` and an `os.path.join(...)`). Each constant is removed and both reference sites call `graider_export_dir("<Subdir>")` directly (only two call sites per module, so a separate accessor function is unnecessary scope; the resolver call is the call-time form). `assistant_tools_reports.py:1610 EXPORT_DIR` is a function-local variable, already resolved at call time, so it is migrated as a normal site (its `os.path.expanduser(...)` right-hand side is swapped to `graider_export_dir("Exports")`; the local name stays). Each converted module gets a characterization check confirming the resolved value with no env var is byte-identical to the prior constant value.

The 19 sites (file:line, current): `backend/app.py:651`, `backend/app.py:702`, `backend/routes/assignment_routes.py:310`, `backend/routes/assignment_routes.py:552`, `backend/routes/assignment_routes.py:566`, `backend/routes/assignment_routes.py:580`, `backend/routes/grading_routes.py:135`, `backend/routes/grading_routes.py:252`, `backend/routes/analytics_routes.py:40`, `backend/routes/planner_routes.py:1812`, `backend/routes/planner_routes.py:1992`, `backend/routes/planner_routes.py:2085`, `backend/routes/assistant_routes.py:671`, `backend/services/assistant_tools_student.py:550`, `backend/services/assistant_tools_reports.py:1610`, `backend/services/assistant_tools_grading.py:844`, `backend/services/document_generator.py:22`, `backend/services/worksheet_generator.py:27`, `backend/services/assistant_tools.py:207`. Line numbers are re-derived at implementation time before editing (they may shift); the grep gate in section 6 is the authoritative completeness check.

## 5. Test isolation convergence (conftest)

Replace #412's `_redirect_downloads_graider` fixture and its `_is_output_path` allowlist helper with one session-scoped autouse fixture that sets `os.environ["GRAIDER_EXPORT_DIR"]` to a fresh `tempfile.mkdtemp(prefix="graider_test_exports_")`, and restores the prior environment plus removes the temp tree on teardown. The brittle global `os.path.expanduser` monkeypatch is removed. Because section 4 guarantees the base is resolved only at call time and the fixture is session-autouse (it runs before any test body), no site can resolve to a real Downloads during the suite. The fixture (or a dedicated test) asserts the real `~/Downloads/Graider` received zero new files across the run, the same check that caught the original incident.

## 6. Behavior-preservation guarantee and verification net

Default behavior with `GRAIDER_EXPORT_DIR` unset must be byte-identical to the prior code.

- `tests/test_paths.py`: with no env var, `graider_export_dir(s)` equals the prior `os.path.expanduser("~/Downloads/Graider/" + s)` for each subdir, the bare root, and the `Results/master_grades.csv` path; with the env var set, it equals `<env>/<subpath>`; the base is resolved fresh on each call (mutating the env between two calls changes the result).
- Grep gate: zero remaining `os.path.expanduser("~/Downloads/Graider"` in `backend/` or root `*.py`, excluding the resolver's own default line and tests. Any residual hardcoded site fails review.
- Full regression including `tests/test_export_content_guard.py` and the planner, grading, and assignment suites stays green.
- Broad-suite before-and-after count of files in the real `~/Downloads/Graider` is zero (the check that caught the original incident).

## 7. Approaches considered

- **One call-time function in a new `backend/paths.py` (chosen).** Single responsibility, no I/O, call-time so the import-capture bug class cannot exist, default byte-identical, one test mechanism, smallest uniform per-site change.
- **Add the resolver to an existing util module.** Avoids a new file but no current util module owns filesystem or output paths; bolting it on muddies responsibilities for marginal benefit.
- **Introduce a Settings or config object.** Over-engineered. The codebase has no central config layer and reads env vars inline; a config framework for one variable is unjustified scope.

## 8. Scope

**In:** the `backend/paths.py` resolver; migration of all 19 sites; removal of the 2 import-time module-level constants in favor of call-time resolver calls at their use sites; the conftest convergence (single env-var fixture, brittle monkeypatch removed); `tests/test_paths.py`; documenting `GRAIDER_EXPORT_DIR` in CLAUDE.md's environment section.

**Out (explicitly):** the `_get_export_dir()` temp-dir helper in `planner_export.py` (different ephemeral semantic, untouched); any change to what is exported or to directory-creation behavior (existing `os.makedirs` calls stay verbatim); any unrelated path or config refactor; a central config framework.

## 9. Risks and handling

- **Import-time capture reintroducing pollution.** Section 4 removes both module-level import-time constants in favor of call-time resolver calls; the grep gate proves no residual import-time `expanduser` of the base.
- **Conftest convergence regressing isolation.** The broad-suite before-and-after real-Downloads count must be zero (section 6); the new fixture is session-autouse so it precedes all test bodies.
- **A missed site.** The grep gate (section 6) fails review if any hardcoded base remains.
- **Behavior drift.** The resolver returns a path only and creates nothing; existing `os.makedirs` calls are untouched; the default equals the prior `expanduser` value, proven per subdir.

## 10. Success criteria

One `backend/paths.py` resolver. All 19 sites resolve at call time through it and the 2 import-time module-level constants are removed in favor of call-time resolver calls. Zero hardcoded `~/Downloads/Graider` base remains in production code. The conftest uses the single `GRAIDER_EXPORT_DIR` mechanism and the brittle `os.path.expanduser` monkeypatch is removed. Default behavior is byte-identical for real users, proven per subdir. The broad suite is green with zero writes to the real `~/Downloads/Graider`. `GRAIDER_EXPORT_DIR` is documented in CLAUDE.md's environment section. One PR, subagent-driven with two-stage review. The reconciled effect is recorded as an Operational Safety and Code Quality nudge, mechanically test-guarded, no multi-model re-score (consistent with the Tier 2 slices and Data Integrity Tier 1).
