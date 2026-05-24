# Planner Routes De-concentration Implementation Plan (Wave 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De-concentrate `backend/routes/planner_routes.py` (4,611 LOC), behavior-preservingly, into focused `backend/services/` modules to move Code Quality 8.5 → 9.

**Architecture:** Each slice moves cohesive logic into a `backend/services/` module (new or extended) verbatim, then re-imports the names back into the route module ("re-export shim"). Existing call sites + the existing pytest suite stay green (the characterization net). New per-service unit tests pin the moved behavior. For route-body handlers: route keeps auth/parse/jsonify/send_file/error_response; service does the assembly/AI/render.

**Tech Stack:** Python / Flask, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-24-planner-routes-deconcentration-design.md` (read its §5 Landmines before every slice).

---

## File Structure

| File | Slice | Responsibility |
|------|-------|----------------|
| `backend/services/planner_export.py` (extend) | 1, 3 | render/export: the pure `_export_*` helpers (1) + export-builder bodies (3) |
| `tests/test_planner_export_service.py` (new) | 1 | direct unit tests for the moved render helpers |
| `backend/services/openai_context.py` (new) | 2 | pure `build_openai_context(user_id)` |
| `backend/routes/planner_routes.py` (modify) | all | loses moved bodies; gains re-import shims |
| `backend/routes/student_portal_routes.py` (modify) | 2 | repoint `_get_openai_context` imports to the pure helper |
| `backend/services/planner_content_tools.py` (new) | 4 (sketch) | reading-level, extract-text |
| `backend/services/planner_study_aids.py` (new) | 5 (sketch) | study-guide/flashcard/slide generation |
| `backend/services/planner_assessments.py` (new) | 6, 8 (sketch) | grade/regen + generate_assessment |
| `backend/services/planner_generation.py` (new) | 7, 8 (sketch) | brainstorm + generate_assignment_from_lesson + generate_lesson_plan |

**Convention:** branch each slice off freshly-merged `main` (`git checkout -b refactor/planner-slice-N origin/main`); line numbers shift between slices — re-audit with grep before moving.

---

## Task 1 (Slice 1): Move the pure render helpers into `planner_export.py`

**Files:**
- Modify: `backend/services/planner_export.py` (append 4 functions)
- Modify: `backend/routes/planner_routes.py` (remove 4 defs at lines ~4097, ~4151, ~4346, ~4416; add re-import shim)
- Create: `tests/test_planner_export_service.py`

**The 4 functions to move (verbatim):** `_export_study_guide_docx`, `_export_study_guide_pdf`, `_export_flashcards_pdf`, `_export_flashcards_docx`. All are pure file writers — every `docx`/`reportlab` import is already in-function, so they move with zero new module-level imports. They reference no `planner_routes` module globals.

> **Landmine L5 (verified):** `tests/test_flashcards.py` and `tests/test_study_guide.py` patch `_get_export_dir` on the *route* module and call the export ENDPOINTS — those endpoints call these helpers via the route-module name, so the re-export shim must keep all 4 names bound on `planner_routes`.

- [ ] **Step 1: Re-audit on fresh main**

```bash
git checkout -b refactor/planner-export-helpers origin/main
grep -nE "^def (_export_study_guide_docx|_export_study_guide_pdf|_export_flashcards_pdf|_export_flashcards_docx)\b" backend/routes/planner_routes.py
```
Expected: 4 lines. Note current line numbers.

- [ ] **Step 2: Write the failing service unit test**

Create `tests/test_planner_export_service.py`:

```python
"""Direct-import tests for the render helpers moved into planner_export (Wave 6 Slice 1)."""
import os
import tempfile


def test_export_study_guide_docx_writes_file():
    from backend.services.planner_export import _export_study_guide_docx
    sg = {"title": "Photosynthesis", "sections": [{"heading": "Intro", "content": "Plants make food."}]}
    path = os.path.join(tempfile.mkdtemp(), "sg.docx")
    _export_study_guide_docx(sg, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def test_export_study_guide_pdf_writes_file():
    from backend.services.planner_export import _export_study_guide_pdf
    sg = {"title": "Photosynthesis", "sections": [{"heading": "Intro", "content": "Plants make food."}]}
    path = os.path.join(tempfile.mkdtemp(), "sg.pdf")
    _export_study_guide_pdf(sg, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def test_export_flashcards_pdf_writes_file():
    from backend.services.planner_export import _export_flashcards_pdf
    cards = {"title": "Vocab", "cards": [{"front": "cat", "back": "feline"}]}
    path = os.path.join(tempfile.mkdtemp(), "fc.pdf")
    _export_flashcards_pdf(cards, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def test_export_flashcards_docx_writes_file():
    from backend.services.planner_export import _export_flashcards_docx
    cards = {"title": "Vocab", "cards": [{"front": "cat", "back": "feline"}]}
    path = os.path.join(tempfile.mkdtemp(), "fc.docx")
    _export_flashcards_docx(cards, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0
```

- [ ] **Step 3: Run to verify failure**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && pytest tests/test_planner_export_service.py -q`
Expected: FAIL — `ImportError: cannot import name '_export_study_guide_docx' from 'backend.services.planner_export'`.

- [ ] **Step 4: Move the 4 functions verbatim into `planner_export.py`**

Append the 4 function bodies **exactly** as they appear in `planner_routes.py` (keep the in-function `from docx import ...` / `from reportlab... import ...` lines verbatim) to the end of `backend/services/planner_export.py`. Add nothing at module level.

- [ ] **Step 5: Run the new service test to verify it passes**

Run: `pytest tests/test_planner_export_service.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Remove the 4 defs from the route + add the re-export shim**

Delete the 4 function definitions from `planner_routes.py`. Where the first one was, add:

```python
# Wave 6 Slice 1: study-aid render helpers extracted to
# backend/services/planner_export.py. Re-imported here so the export route
# bodies and the tests that patch _get_export_dir on this module keep working.
from backend.services.planner_export import (  # noqa: F401  (re-export shim)
    _export_study_guide_docx,
    _export_study_guide_pdf,
    _export_flashcards_pdf,
    _export_flashcards_docx,
)
```

- [ ] **Step 7: Leftover scan + import check**

```bash
grep -nE "^def (_export_study_guide_docx|_export_study_guide_pdf|_export_flashcards_pdf|_export_flashcards_docx)\b" backend/routes/planner_routes.py
python -c "import backend.routes.planner_routes as m; [getattr(m,n) for n in ('_export_study_guide_docx','_export_study_guide_pdf','_export_flashcards_pdf','_export_flashcards_docx')]; print('4 re-exported OK')"
```
Expected: grep prints nothing; python prints `4 re-exported OK`.

- [ ] **Step 8: Run the export characterization net (must stay green)**

Run: `pytest tests/test_study_guide.py tests/test_flashcards.py tests/test_planner_export.py tests/test_planner_export_characterization.py tests/test_planner_export_service.py -q`
Expected: PASS (all). The endpoint tests exercise the helpers via the re-export shim; the new tests via the service module.

- [ ] **Step 9: ruff + commit + PR + auto-merge**

```bash
ruff check backend/services/planner_export.py backend/routes/planner_routes.py
git add backend/services/planner_export.py backend/routes/planner_routes.py tests/test_planner_export_service.py
git commit -m "refactor(planner): move study-aid render helpers into planner_export service (Wave 6 slice 1)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin refactor/planner-export-helpers
gh pr create --title "refactor(planner): study-aid render helpers → planner_export (Wave 6 slice 1)" --body "Behavior-preserving; pure file writers moved verbatim; re-export shim keeps _get_export_dir-patching tests green; new direct service tests. Spec: docs/superpowers/specs/2026-05-24-planner-routes-deconcentration-design.md"
gh pr merge --squash --auto --delete-branch
```

---

## Task 2 (Slice 2): Pure `openai_context` + break the cross-route cycle

**Files:**
- Create: `backend/services/openai_context.py`
- Create: `tests/test_openai_context.py`
- Modify: `backend/routes/planner_routes.py` (`_get_openai_context` becomes a compat shim)
- Modify: `backend/routes/student_portal_routes.py` (repoint the 2 imports)

> **Landmine L1 (verified):** `planner_routes._get_openai_context()` reads `g.user_id` (fallback `'local-dev'`) and returns `(user_id, None)`. `student_portal_routes.py` imports it twice (the circular-import surface). `tests/test_planner_routes_shim.py` asserts `_get_openai_context` is reachable on the route module — so the route shim must stay.

- [ ] **Step 1: Re-audit on fresh main**

```bash
git checkout -b refactor/planner-openai-context origin/main
grep -n "_get_openai_context" backend/routes/student_portal_routes.py backend/routes/planner_routes.py
```
Expected: definition + shim test references in planner_routes; 2 import + 2 call sites in student_portal_routes.

- [ ] **Step 2: Write the failing test**

Create `tests/test_openai_context.py`:

```python
"""Direct tests for the pure openai_context helper (Wave 6 Slice 2)."""


def test_build_openai_context_returns_user_id_and_none_client():
    from backend.services.openai_context import build_openai_context
    assert build_openai_context("teacher-123") == ("teacher-123", None)
    assert build_openai_context("local-dev") == ("local-dev", None)
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_openai_context.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.openai_context'`.

- [ ] **Step 4: Create the pure service module**

Create `backend/services/openai_context.py`:

```python
"""Pure OpenAI-context helper for the post-processing pipeline.

Wave 6 Slice 2 - extracted from planner_routes._get_openai_context to remove the
cross-route circular-import surface (student_portal_routes imported the route
helper directly). Flask-free: the caller reads g.user_id and passes it in.
"""


def build_openai_context(user_id):
    """Return the (user_id, client) tuple the post-processing pipeline expects.

    The client slot is intentionally None (kept for call-site compatibility;
    _auto_fix_flagged_questions builds its own LLM adapter internally).
    """
    return user_id, None
```

- [ ] **Step 5: Run the new test to verify it passes**

Run: `pytest tests/test_openai_context.py -q`
Expected: PASS.

- [ ] **Step 6: Make `planner_routes._get_openai_context` a compat shim**

In `backend/routes/planner_routes.py`, add `from backend.services.openai_context import build_openai_context` near the top imports, and replace the body of `_get_openai_context` (keep the function — the shim test depends on it):

```python
def _get_openai_context():
    """Extract user_id for the post-processing pipeline.

    Compat shim (Wave 6 Slice 2): reads Flask g and delegates to the pure
    backend.services.openai_context.build_openai_context. Returns (user_id, None).
    """
    try:
        user_id = getattr(g, 'user_id', 'local-dev')
        return build_openai_context(user_id)
    except Exception as e:
        _logger.warning("OpenAI context unavailable (non-fatal): %s", e)
        return None, None
```

- [ ] **Step 7: Repoint `student_portal_routes.py` at the pure helper**

In `backend/routes/student_portal_routes.py`, replace BOTH `from backend.routes.planner_routes import _get_openai_context` import lines and their call sites. Each call site currently looks like `_ctx_uid, _ctx_client = _get_openai_context()` — change to:

```python
from backend.services.openai_context import build_openai_context
...
_ctx_uid, _ctx_client = build_openai_context(getattr(g, 'user_id', 'local-dev'))
```

This reads `g` in student_portal's own request thread (equivalent to before) and removes the `backend.routes.planner_routes` import (cycle gone).

- [ ] **Step 8: Verify cycle gone + shim intact + tests green**

```bash
grep -n "from backend.routes.planner_routes import" backend/routes/student_portal_routes.py   # expect: none (or no _get_openai_context)
python -c "import backend.routes.planner_routes as m; print(m._get_openai_context)"  # shim still present
pytest tests/test_planner_routes_shim.py tests/test_remediation.py tests/test_remediation_perstudent.py tests/test_openai_context.py -q
ruff check backend/services/openai_context.py backend/routes/planner_routes.py backend/routes/student_portal_routes.py
```
Expected: no planner_routes import remains in student_portal_routes; shim present; tests PASS; ruff clean.

- [ ] **Step 9: Commit + PR + auto-merge**

```bash
git add backend/services/openai_context.py tests/test_openai_context.py backend/routes/planner_routes.py backend/routes/student_portal_routes.py
git commit -m "refactor(planner): extract pure openai_context + break cross-route cycle (Wave 6 slice 2)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin refactor/planner-openai-context
gh pr create --title "refactor(planner): pure openai_context + kill student_portal->planner_routes cycle (Wave 6 slice 2)" --body "Adds backend/services/openai_context.build_openai_context; planner_routes._get_openai_context becomes a compat shim (shim test stays green); student_portal_routes repointed at the pure helper. Spec: docs/superpowers/specs/2026-05-24-planner-routes-deconcentration-design.md"
gh pr merge --squash --auto --delete-branch
```

---

## Task 3 (Slice 3, scope-sketch): export builders → `planner_export.py`

**Detailed in full when reached (re-audit off fresh main).** Move the render/assembly bodies of `export_assessment`, `export_assessment_for_platform`, `export_generated_assignment` (PDF), `export_lesson_plan` (DOCX) into `planner_export.py`. The route keeps request parse, `send_file`/`jsonify`, the `_get_export_dir` resolution, and `_save_grading_config_for_export` (Landmine L2 — Flask-`g`-bound, stays route-side). Gate: `test_planner_export.py` + `test_bubble_export.py` + `test_export_content_guard.py` + new service tests + route-contract char tests.

## Task 4 (Slice 4, scope-sketch): content tools

Move `adjust_reading_level`, `extract_text_from_file` assembly → new `backend/services/planner_content_tools.py`; `align_document_to_standards`, `rewrite_for_alignment` → extend `planner_standards.py`. Gate: `test_standards.py` + existing route tests + new service tests. These are LLM-light/text helpers — adapter-mocked where needed.

## Task 5 (Slice 5, scope-sketch): study-aid generation

Move `generate_study_guide`, `generate_flashcards`, `generate_slides` generation bodies → new `backend/services/planner_study_aids.py` (render helpers already in planner_export from Slice 1). Gate: `test_study_guide.py`, `test_flashcards.py`, `test_slide_generator.py` (which already mock Gemini) + new service tests.

## Task 6 (Slice 6, scope-sketch): assessment grade/regen

Move `grade_assessment_answers`, `regenerate_questions` → new `backend/services/planner_assessments.py`. Adapter-mocked char tests via `test_assessment_*.py` + new service tests.

## Task 7 (Slice 7, scope-sketch): generation — assignment

Move `brainstorm_lesson_ideas`, `generate_assignment_from_lesson` → new `backend/services/planner_generation.py` (prompt blocks → `planner_prompts.py`). Route keeps `request.json`, `getattr(g,'user_id','local-dev')`, api_key lookup + "Missing API key" error, `jsonify`; service does prompt build + adapter call + parse + `_post_process_assignment` + usage merge. **Landmine L3:** preserve `generate_assignment_from_lesson`'s essay/project early-return that omits `usage`. Gate: `test_planner_routes.py` + `test_lesson_routes_unit.py` (adapter-mocked) + new service tests + route-contract char tests pinning the response shape byte-identical.

## Task 8 (Slice 8, scope-sketch): generation — assessment + lesson (largest, last)

Move `generate_assessment` → `planner_assessments.py`, then `generate_lesson_plan` → `planner_generation.py`. **Landmine L3:** preserve `generate_lesson_plan`'s mock-fallback response shape and `generate_assessment`'s discarded post-process extra usage (`_post_process_assignment(..., _)`). Same route/service boundary as Slice 7. Gate: `test_planner_routes.py` (adapter-mocked) + new service tests + route-contract char tests.

---

## Post-wave step: 3-model re-score

After Slices 1–8 land, run a 3-model reconciled re-score (Claude controller first-hand + `codex exec` + `gemini -p`, conservative floor) weighing whether Code Quality moves 8.5 → 9, appended as a dated section to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`. Honest expectation (Codex caveat): completing the last route god-file is the path to 9, but the off-limits 5,344-LOC `assignment_grader.py` may hold the conservative floor at 8.8–8.9.
