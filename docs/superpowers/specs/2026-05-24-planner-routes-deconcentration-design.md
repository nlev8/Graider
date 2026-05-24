# Planner Routes De-concentration — Wave 6 (Code Quality 8.5 → 9)

**Status:** Design approved (standing sprint authorization; user: "do planner_routes.py next"). Brainstormed via `superpowers:brainstorming` with 3-model consultation (Claude controller first-hand + Codex + Gemini, unanimous on shape + slice order). Next: `superpowers:writing-plans`.

**Goal:** De-concentrate the LAST backend route god-file, `backend/routes/planner_routes.py` (4,611 LOC), behavior-preservingly, into the established `backend/services/` pattern — the unanimous next lever from the 2026-05-24 Post-Wave-5 re-score (Code Quality 8.5, next lever `planner_routes.py`).

**Architecture:** Same proven Wave 5 pattern. Each slice moves cohesive logic into a `backend/services/` module (new or extended), then **re-imports the names back into the route module** ("re-export shim") so existing call sites and tests stay green. For route-BODY handlers: the route keeps auth + request parse + `jsonify`/`send_file` + `error_response`; the assembly/AI/render logic moves to a Flask-free service taking explicit params.

**Tech Stack:** Python / Flask, pytest. No new dependencies.

---

## 1. Why this file, why now

The 2026-05-24 re-score put Code Quality at **8.5** and named `planner_routes.py` (4,611 LOC) the unanimous next lever — it is the last backend route god-file. `assignment_grader.py` (5,344) is OFF-LIMITS (grading engine; separate user-gated lever). The post-processing pipeline `_post_process_assignment` is already a service (`backend/services/assignment_post_processing.py`). Several planner services already exist (`planner_export`, `planner_prompts`, `planner_standards`, `document_generator`, `slide_generator`, `worksheet_generator`) — Wave 6 extends them and adds focused new ones.

The 4,611 LOC is dominated by **9 large AI-heavy route handlers** (>150 LOC each, ~2,938 LOC total): `generate_lesson_plan` (507), `generate_assignment_from_lesson` (504), `generate_assessment` (501), `export_generated_assignment` (438), `export_assessment_for_platform` (227), `grade_assessment_answers` (213), `export_lesson_plan` (205), `export_assessment` (177), `brainstorm_lesson_ideas` (166).

## 2. The extraction pattern (the gate)

Identical to Wave 5 (see `docs/superpowers/specs/2026-05-23-backend-route-deconcentration-design.md`):
1. Create/extend a `backend/services/` module; move the target logic **verbatim** (byte-identical bodies — never "improve" during a move; preserve latent quirks/warts exactly).
2. Re-import the moved names back into `planner_routes.py` (re-export shim) so existing imports and `patch('backend.routes.planner_routes.<name>')` keep working. (planner_routes already uses this pattern — see `tests/test_planner_routes_shim.py`.)
3. Add new direct unit tests against the service module.
4. Gate per slice: free-variable scan = zero; byte-identical/behavior-equivalent body; existing test net green (the characterization net — `test_planner_routes.py`, `test_planner_export.py`, `test_study_guide.py`, `test_flashcards.py`, `test_slide_generator.py`, `test_standards.py`, `test_lesson_routes_unit.py`, `test_assessment_*.py`); new service unit tests green; the 9 CI checks; two-stage subagent review (spec-compliance then code-quality) per PR.

## 3. Service module boundaries

- **`backend/services/planner_export.py` (extend):** all document/visual render + export logic — the pure helpers `_export_study_guide_docx/pdf`, `_export_flashcards_docx/pdf`, plus the render bodies of `export_lesson_plan`, `export_assessment`, `export_assessment_for_platform`, `export_generated_assignment`. Routes keep validation, `send_file`/`jsonify`, and `_save_grading_config_for_export` (Flask-`g`-bound — stays route-side).
- **`backend/services/planner_prompts.py` (extend):** prompt-builder blocks pulled from the generate_* handlers (it already owns `_build_assignment_prompt`, `_build_period_differentiation_block`).
- **`backend/services/planner_standards.py` (extend):** the assembly of `align_document_to_standards`, `rewrite_for_alignment`.
- **`backend/services/planner_generation.py` (new):** orchestration for `brainstorm_lesson_ideas`, `generate_lesson_plan`, `generate_assignment_from_lesson` (prompt build + adapter call + JSON parse + `_post_process_assignment` + usage merge/record).
- **`backend/services/planner_assessments.py` (new):** `generate_assessment`, `grade_assessment_answers`, `regenerate_questions`.
- **`backend/services/planner_study_aids.py` (new):** study-guide + flashcard *generation* (the Gemini calls). Render stays in `planner_export.py`.
- **`backend/services/planner_content_tools.py` (new):** `adjust_reading_level`, `extract_text_from_file` assembly.
- **`backend/services/openai_context.py` (new):** pure `build_openai_context(user_id) -> (user_id, None)`. See Landmine L1.

## 4. Slices (safest-first)

1. **Pure render helpers** → `planner_export.py`: `_export_study_guide_docx/pdf`, `_export_flashcards_docx/pdf` (pure file writers; tested via `test_study_guide.py` / `test_flashcards.py`). Cleanest first.
2. **`openai_context.py` + cycle break** (L1): add the pure helper; keep `planner_routes._get_openai_context()` as a compat shim; repoint `student_portal_routes.py`'s two imports at the pure helper. Removes the cross-route circular-import surface.
3. **Export builders** → `planner_export.py`: `export_assessment`, `export_assessment_for_platform`, `export_generated_assignment` (PDF), `export_lesson_plan` (DOCX). Route keeps `send_file` + `_save_grading_config_for_export`.
4. **Content tools** → `planner_content_tools.py`: `adjust_reading_level`, `extract_text_from_file`; and standards alignment (`align_document_to_standards`, `rewrite_for_alignment`) → `planner_standards.py`.
5. **Study-aid generation** → `planner_study_aids.py`: `generate_study_guide`, `generate_flashcards`, `generate_slides`.
6. **Assessment grade/regen** → `planner_assessments.py`: `grade_assessment_answers`, `regenerate_questions`.
7. **Generation: assignment** → `planner_generation.py`: `brainstorm_lesson_ideas`, `generate_assignment_from_lesson`.
8. **Generation: assessment + lesson** → `planner_assessments.py` / `planner_generation.py`: `generate_assessment`, then `generate_lesson_plan` (largest, last).

Later slices re-audit boundaries off freshly-merged main (line numbers shift). Slices 1–2 are detailed in full in the plan; 3–8 scope-sketched and planned in full when reached.

## 5. Landmines (verified first-hand; carry into every slice)

- **L1 — `_get_openai_context` cross-route cycle.** `planner_routes._get_openai_context()` reads `g.user_id`, returns `(user_id, None)`; `student_portal_routes.py` imports it twice (the circular-import surface). Fix: pure `openai_context.build_openai_context(user_id)`; route shim stays (preserves `test_planner_routes_shim.py`); student_portal repoints to the pure helper passing `getattr(g, 'user_id', 'local-dev')`. Services must NEVER `import backend.routes.*`.
- **L2 — `_save_grading_config_for_export` is Flask-`g`-bound** — stays route-side; do not force into a service.
- **L3 — preserve generation warts verbatim:** `generate_lesson_plan` mock-fallback response shape; `generate_assignment_from_lesson` essay/project early-return that omits `usage`; `generate_assessment` discards post-process extra usage (`_post_process_assignment(..., _)`). Do NOT "fix" these during extraction.
- **L4 — no `send_file` in the generation handlers; no DB writes** in the generate_* bodies — don't invent `db` params.
- **L5 — export tests patch `_get_export_dir`** on the route module — keep `_get_export_dir` reachable on `planner_routes` (re-export if moved).
- **L6 — AI handlers acquire `api_key` via `get_api_key` + build the adapter.** The service takes `api_key` (or an adapter/context) as a param; the route keeps the key lookup + the "Missing API key" error shape.

## 6. Scope / non-goals

- **In scope:** Slices 1–8 on `planner_routes.py`. Each a separate PR off fresh main, merged before the next.
- **Out of scope:** `assignment_grader.py` (off-limits); any schema/behavior change; `_post_process_assignment` (already a service); the assistant/other route files.

## 7. Success criteria

- `planner_routes.py` reduced to thin route adapters; AI/render orchestration relocated to focused Flask-free services.
- Every existing test green throughout (byte-identical behavior) + new per-service unit tests; all 9 CI checks green per PR.
- A post-wave 3-model reconciled re-score judges whether Code Quality moves 8.5 → 9. Honest expectation (Codex caveat): completing the last route god-file is the path to 9, but the off-limits 5,344-LOC grader may hold the conservative floor at 8.8–8.9; the re-score decides.

---

*Execution: subagent-driven with two-stage review per PR; controller-run assertion-guarded edits where the moved block is large (the generation trio). Spec + plan ship as one docs PR, then impl PRs follow.*
