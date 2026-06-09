# CLAUDE.md - Graider Development Guide

## Virtual Environment
The Python venv is at: `/Users/alexc/Downloads/Graider/venv/`
Activate with: `source venv/bin/activate`
Always use this venv for running Python commands, installing packages, and starting the backend.

## Active Frontend

**The active frontend is `frontend/src/App.jsx`** (React + Vite). All frontend work goes in `frontend/src/`.

- Backend entry point: `backend/app.py` (serves the Vite-built frontend from `backend/static/`)
- Frontend source: `frontend/src/App.jsx` and `frontend/src/` directory

## Workflow Discipline

**Before any multi-task subagent-driven execution, read `.claude/rules/workflow.md`.** It
codifies the per-task checklist (full-suite pytest, cross-cutting test grep, line-shift pin
scan), hard rules (e.g., "pre-existing failure" claims require `git checkout <base>` proof),
anti-patterns, the four-layer verification loop, and the universal definition of done
(per-task + per-branch). The "Lessons From Incidents" appendix records what each rule is
there to prevent — read it once so the rules read as protection, not bureaucracy.

CI is the **final** safety net (the nine status checks below). The workflow file is the
**first** safety net — local guardrails that catch issues seconds-fast instead of
red-PR-slow. The two are complementary; running both is the standard.

## Deployment

- **Backend (app.graider.live)**: Railway — auto-deploys when PRs merge to `main`. Direct pushes to main are blocked by branch protection.
- **Landing page (graider.live)**: Vercel — deploy with `cd landing && npx vercel --prod`. Separate Vercel project.
- **Frontend**: Built **at deploy** by Railway/NIXPACKS (`nixpacks.toml` `[phases.build]` runs `cd frontend && npm run build` → `backend/static/`). `backend/static/` is **gitignored** (no longer committed). Requires `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` set as Railway build variables. For local dev, run `cd frontend && npm run build` to populate `backend/static/`, or use `npm run dev` (Vite dev server, port 5180, proxies `/api`).
- **Non-web Railway services** (worker, Celery beat, etc.) share this `nixpacks.toml` but don't serve the SPA. Set `SKIP_FRONTEND_BUILD=true` on those services — the build-phase guard makes each cmd a no-op (Docker RUN exits 0). Without that flag the frontend build runs uniformly, wastes time, and *requires* the `VITE_*` env vars to be set on every service. See `nixpacks.toml` header comment for details.

### CI/CD Pipeline

All changes go through Pull Requests:

1. Create branch: `git checkout -b feature/my-change`
2. Push: `git push -u origin feature/my-change`
3. Create PR: `gh pr create --title "..." --body "..."`
4. CI runs automatically (backend tests + frontend build)
5. Merge when CI passes → Railway auto-deploys

**Branch protection on `main` requires 9 status checks (verified via `gh api repos/nlev8/Graider/branches/main/protection/required_status_checks`):**

- `Backend Tests` (pytest with `--cov-fail-under=70`; measured global ~70.5% as of 2026-06-03. **Bump rule:** raise the floor only when measured global is ≥0.5% above the new floor. Full bump history lives in git log / the cicd-pipeline plan doc.)
- `Frontend Build` (Vite build succeeds + frontend test count ≥ floor)
- `Frontend E2E Smoke` (Playwright `health-check.spec.js` against locally-spawned backend; promoted from `continue-on-error` to required on 2026-05-11 after 15 consecutive green runs — closes audit MAJOR #5 Phase 1)
- `Migrations Smoke` (Alembic upgrades cleanly against raw `postgres:15-alpine`)
- `Lockfile Drift Check` (pip-compile output matches committed `requirements*.txt`)
- `Ruff Lint`
- `Bandit SAST`
- `Secret Scan (trufflehog, verified only, PR diff)`
- `Mypy Strict (Critical Modules)`

**Emergency bypass:** Repo admins can merge without CI if `enforce_admins` is false. Use only for critical hotfixes — fix CI immediately after.

**CI job names are locked:** The branch protection rule references the 9 jobs above by exact name. If you rename a job in `.github/workflows/ci.yml`, update the branch protection rule too or merges will be blocked. See `docs/superpowers/plans/2026-04-02-cicd-pipeline.md` Task 3 for the update command.

## Project Overview

Graider is an AI-powered grading assistant for educators. It's a Flask application with a React frontend that uses OpenAI's GPT-4 API to grade student assignments.

## Architecture

> File layout drifts; the codebase is the source of truth. Use
> `grep -rnE "@[a-z_]+\.route\(" backend` or GitNexus to locate things. The
> components below are the stable, load-bearing pieces.

### Key Components

1. **Flask Backend** (`backend/app.py`)
   - Serves the Vite-built React frontend from `backend/static/`
   - REST API endpoints under `/api/*`
   - Grading runs in background thread

2. **React Frontend** (`frontend/src/`)
   - Teacher dashboard (`App.jsx`) — grading, planner, settings, results
   - Student portal (`StudentApp.jsx`) — authenticated class-based path at `/student`
   - Join code portal (`StudentPortal.jsx`) — anonymous path at `/join/CODE`
   - Built with Vite; output goes to `backend/static/`

3. **Grading Engine** (`assignment_grader.py`)
   - Parses Word docs, PDFs, images
   - Extracts student work using markers
   - Calls OpenAI API for grading

4. **Student Workflow**
   - Students complete assignments in the browser portal, not via local file folders
   - Assignments are published via join codes or class-based publishing
   - Two portal paths: anonymous join code (`/join/CODE`) and authenticated class-based (`/student`)

5. **Persistence**
   - Supabase — student records, classes, submissions, published content
   - `~/.graider_rubric.json` - Rubric settings
   - `~/.graider_settings.json` - Global AI notes
   - `~/.graider_assignments/` - Saved assignment configs

---

## AI Grading Factors (CRITICAL — Never Drop Any Factor)

The multipass grading pipeline (`grade_multipass` → `grade_per_question` → `generate_feedback`) must account for ALL of these factors. Dropping any factor produces incorrect scores or generic feedback.

### How factors flow through the pipeline:
- **`file_ai_notes`** (built in `app.py`): Accumulates global AI instructions, assignment grading notes, rubric type overrides, IEP/504 accommodations, student history, class period differentiation into ONE string. Passed as `custom_ai_instructions` → `teacher_instructions`.
- **`rubric_prompt`** (from Settings): Teacher's custom rubric categories/weights. Appended to `effective_instructions` in `grade_multipass()` so per-question graders see it.
- **`grading_style`** (lenient/standard/strict): Included in `grade_per_question()` prompt AND used for score caps in `grade_multipass()`.

### Complete factor list:
1. **Global AI Instructions** — Teacher's global notes from Settings
2. **Assignment Grading Notes** — Per-assignment expected answers, vocab definitions, summary key points
3. **Custom Rubric** — Categories, weights, descriptions from Settings
4. **Rubric Type Override** — cornell-notes, fill-in-blank, standard (per assignment)
5. **Grading Style** — lenient/standard/strict (affects AI prompt + score caps)
6. **IEP/504 Accommodations** — Per-student modified expectations
7. **Student History** — Past scores, streaks, improvement trends
8. **Class Period Differentiation** — Honors vs regular expectations
9. **Expected Answers** — Matched by question number, text, term, or index
10. **Grade Level & Subject** — Age-appropriate expectations
11. **Section Type** — vocab_term, numbered_question, fitb, summary, written
12. **Section Name & Points** — Marker section + per-question point allocation
13. **Student Actual Answers** — Literal text for specific feedback
14. **ELL Language** — Feedback translation for ELL students
15. **Effort Points & Completeness Caps** — Missing sections cap max score
16. **Assignment Template** — Strips prompt text from extracted responses
17. **FITB Exemption** — Fill-in-blank exempt from AI/plagiarism detection
18. **Writing Style Profile** — Historical patterns for detection

### Key code locations:
- Factor accumulation: `backend/grading/pipeline.py` `file_ai_notes` built inline in the grading thread
- Rubric formatting: `backend/services/rubric_formatting.py` `format_rubric_for_prompt()`
- Per-question grading: `assignment_grader.py` `grade_per_question()`
- Feedback generation: `assignment_grader.py` `generate_feedback()`
- Multipass orchestration: `assignment_grader.py` `grade_multipass()`
- Single-pass (Claude/Gemini): `assignment_grader.py` `grade_assignment()`

---

## Code Style

- Active frontend (`frontend/src/`) is a normal Vite/React project — template literals, multi-line strings, `\n` are all fine (the old embedded-React string-concat constraints are gone).
- Python: explicit imports; load `.env` with `load_dotenv(..., override=True)`; guard shared mutable state (e.g. `grading_state`) with locks in critical sections; use `.get()` for dict access.
- **Never**: hardcode API keys (always `os.getenv(...)`); do DB operations in `__init__`; run blocking work in a Flask route (thread long tasks like grading).

---

## Environment Setup

```bash
# Backend
source venv/bin/activate
pip install -r requirements.txt
python backend/app.py            # serves the built SPA from backend/static/

# Frontend (dev)
cd frontend && npm install
npm run dev                      # Vite dev server on :5180, proxies /api
# or: npm run build              # populates backend/static/ for the Flask server
```

Required env: see **Environment Variables** below (`FLASK_SECRET_KEY`, `SUPABASE_*` at minimum).
Verification/testing discipline lives in `.claude/rules/workflow.md`, not here.

---

## API Reference

~270 `/api/*` routes are registered across `backend/routes/*.py` (plus `backend/app.py`).
This file no longer hand-maintains the endpoint list (it drifted to ~32% coverage). To get
the live, authoritative list:

```bash
grep -rnE "@[a-z_]+\.route\(" backend --include='*.py'
```

Or ask GitNexus: `gitnexus_query({query: "<feature> endpoint"})`. Route handlers are grouped
by domain in `backend/routes/` (clever_routes, classlink_routes, oneroster, lti, district,
admin, student_account_routes, student_portal_routes, assistant_routes, planner_routes, …).

---

## Environment Variables

### Required
- `FLASK_SECRET_KEY` — Session signing key (MUST be set in production)
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_KEY` — Supabase service role key
- `SUPABASE_JWT_SECRET` — JWT secret for token validation

### Integration-specific (Clever, ClassLink, OneRoster, LTI 1.3, District Admin, Periodic Sync)
The full var list + descriptions live in **`.env.example`** (the canonical reference; ~16 vars
across these six integrations — `CLEVER_*`, `CLASSLINK_*`, `ONEROSTER_*`, `LTI_TOOL_URL`,
`DISTRICT_ADMIN_PASSWORD`, `PERIODIC_SYNC_SECRET`). Each integration reads its own vars in its own
module, so grep there when wiring one up:
`grep -rn 'os.getenv' backend/clever.py backend/routes/classlink_routes.py backend/oneroster.py backend/routes/lti_routes.py`.

### Optional
- `OPENAI_API_KEY` — Default OpenAI key (fallback)
- `ANTHROPIC_API_KEY` — Default Anthropic key (fallback)
- `FLASK_ENV` — Set to "development" for dev mode
- `REDIS_URL` — Redis for session storage in production
- `GRAIDER_EXPORT_DIR` — Base directory for generated exports (docx/csv/etc.); defaults to `~/Downloads/Graider`; override to redirect all export output (the test suite sets it to a temp dir for isolation)

---

## Supabase Tables

Core tables (columns drift — the Supabase schema is authoritative; verify field names before any DB change):
`classes`, `students`, `class_students`, `student_sessions` (auth/sessions); `published_assessments` +
`submissions` (anonymous join-code path), `published_content` + `student_submissions` (authenticated
class-based path); `teacher_data` (per-teacher key-value: assignments/lessons/settings/rubric);
`audit_log` (FERPA audit trail). The load-bearing distinction is the two publish paths:

### Two Publish Paths
Graider has two parallel publishing systems:
1. **Join-code** (`published_assessments` + `submissions`): Anonymous access via 6-char code. No enrollment required. Used for quick sharing, makeup exams. Teacher endpoints require `@require_teacher`.
2. **Class-based** (`published_content` + `student_submissions`): Authenticated access via Clever SSO or email+code login. Requires class enrollment. Supports due dates, content types, student tracking.

Both paths use the same grading functions (`grade_instant_only`, `grade_student_submission`, `run_portal_grading_thread`) and the same `StudentPortal.jsx` component for the student-facing UI.

---

## Performance Notes

- Grading runs in background thread to keep UI responsive
- Auto-save rubric uses 500ms debounce
- Status polling every 500ms during grading
- Large files (>10MB) may timeout on parse

---

## Development Principles

**Golden rules — apply to every change, no exceptions:**

1. **Verify before AND after every file write.** Read the file (plus its callers/tests) before editing; after writing, confirm the change landed as intended and run the relevant test / lint / build before moving on. An unverified write is a guess.
2. **Read before write, root-cause before patch.** Never change code you haven't read; trace the full data flow before fixing one layer.
3. **Smallest correct change.** Minimum viable change, not minimum effort — no unrequested refactors or features.
4. **Tests are the gate.** New or changed behavior ships with a test that is red before and green after; run the full suite (`pytest -q`), not just the file you touched.
5. **Leave the tree clean.** Commit only the files the task intended — no incidental noise.

**The 13 working principles** (the four-layer verification loop + Class A/B rationale + incident history live in `.claude/rules/workflow.md`):

1. **Read before write.** Read the function, its callers, and tests before changing anything; for data-flow bugs trace the full pipeline (generation → hydration → rendering) before patching one layer.
2. **Simplicity first.** Minimum viable change, not minimum effort — no unrequested refactors/features. >3 files touched ⇒ pause and look for a simpler way.
3. **Programmatic over probabilistic.** Fix bad AI output with deterministic post-processing, not prompt wording. Prompts are layer 1; code validation is the safety net that matters.
4. **Verify the user flow.** `npm run build` passing ≠ the feature works. After backend changes generate a real assignment and check the output; after frontend changes check the rendered UI.
5. **Minimal blast radius.** Map affected callers before changing a shared utility; check all consumers first.
6. **Root cause, not patch.** Ask "why is this happening?" before "how do I hide it?" — fix the hydration/data bug, not the symptom.
7. **Don't flag what you fix.** If a pipeline phase corrects something (e.g. `_normalize_points`), don't also warn about it. Fix silently OR warn-without-fixing — never both.
8. **Plan for non-trivial tasks.** 3+ steps or architectural decisions ⇒ plan first; if it goes sideways, STOP and re-plan instead of pushing down a broken path.
9. **Autonomous bug fixing.** A clear bug report ⇒ just fix it (read code → root-cause → fix → test). Don't ask "what would you like me to do?" when it's obviously "fix it."
10. **Subagent discipline.** Use subagents for 3+ searches / parallel research / large-output isolation; not for a single grep or file read. One task per subagent.
11. **Every error is yours to fix.** <15 min + no unrelated files ⇒ fix it now, with a regression test. Defer only genuinely cross-cutting work, and only WITH a fix sketch + 5-line repro in the issue body (filing without a sketch is deferring, not tracking).
12. **Handoff discipline.** Before `/clear`/`/compact`/unattended loops, or after 3+ failed attempts at the same root cause: write `handoff.md` (the `/handoff` skill is the canonical spec). Disproved hypotheses are the most valuable part — don't sanitize them.
13. **Review gates before auto-merge.** Classify every PR: Class A (behavior-preserving, proven by nets) earns auto-merge on green; Class B (net-new logic / compliance / security / FERPA) ⇒ create PR → review → fix to clean → merge manually (never `--auto` with a review in flight). Tell: *"am I adding logic, or just moving it?"*

---

## Post-Processing Pipeline (planner_routes.py)

The assessment/assignment generation pipeline has 6 phases in `_post_process_assignment()`. Changes to any phase must consider ordering and side effects:

1. **Phase 1**: `_classify_question_type` — assigns question_type from text/structure
2. **Phase 2**: `_hydrate_question` — populates fields (geometry dims, data_table initial_data, etc.)
3. **Phase 3**: `_validate_question` — structural validation (options present, terms present)
4. **Phase 3c**: `_validate_question_quality` — 14 deterministic quality checks + AI auto-fix
5. **Phase 4**: `_enforce_question_count` — trim/pad to target count (if specified)
6. **Phase 5**: `_normalize_points` — ensure points sum to target total (always runs)

Key rule: **Phase 3c should not flag issues that Phase 5 will fix.** Don't warn about point values that normalization will correct.

---

*Last updated: June 4, 2026*

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This repo is indexed by GitNexus; use the `mcp__gitnexus__*` tools to navigate
and assess impact. Full tool reference + per-task guides: `.claude/skills/gitnexus/`.

**Must:**
- `impact({target, direction:"upstream"})` before editing a symbol; warn on
  HIGH/CRITICAL. d=1 = will break.
- `detect_changes()` before committing (scope check).
- `rename({dry_run:true})` first — never find-and-replace.
- After committing the index goes stale; refresh with
  `npx gitnexus analyze --embeddings --skip-agents-md`
  (`--skip-agents-md` keeps this compact block; `--embeddings` preserves search).

When stuck: `query({query})` for flows, `context({name})` for a symbol's callers/callees.
<!-- gitnexus:end -->
