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

### File Structure
```
graider/
├── assignment_grader.py    # Core grading logic, file parsing, OpenAI calls
├── email_sender.py         # Email functionality for sending feedback
├── .env                    # API keys (never commit)
├── backend/
│   ├── app.py              # Main Flask app, grading state, results
│   ├── clever.py           # Clever API client, roster sync
│   ├── auth.py             # JWT auth, Clever session resolution
│   ├── routes/
│   │   ├── clever_routes.py             # Clever SSO, roster sync, class creation
│   │   ├── student_account_routes.py    # Student portal, classes, submissions
│   │   ├── student_portal_routes.py     # Join code portal, auto-grading
│   │   └── ...
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main app (teacher dashboard)
│   │   ├── components/
│   │   │   ├── StudentApp.jsx      # Student portal (authenticated)
│   │   │   ├── StudentLogin.jsx    # Student login form
│   │   │   ├── StudentPortal.jsx   # Join code portal
│   │   │   ├── LoginScreen.jsx     # Teacher login + Clever SSO
│   │   │   └── OnboardingWizard.jsx
│   │   └── tabs/
│   │       ├── PlannerTab.jsx
│   │       ├── SettingsTab.jsx
│   │       ├── ResultsTab.jsx
│   │       └── AnalyticsTab.jsx
│   └── ...
└── ~/.graider_*/           # User config files (rubric, assignments, settings)
```

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

> Note: the active frontend (`frontend/src/`) is a normal Vite/React project — template
> literals, multi-line strings, and `\n` are all fine. (The old embedded-React string-concat
> constraints no longer apply; that frontend was removed.)

### Python (Flask Backend)

```python
# GOOD: Use explicit imports
from dotenv import load_dotenv
import json
import os

# GOOD: Load .env with override
load_dotenv(os.path.join(app_dir, '.env'), override=True)

# GOOD: Thread-safe state management
grading_state = {
    "is_running": False,
    "log": [],
    "results": []
}

# BAD: Global mutable state without locks for critical sections
```

---

## Prohibited Patterns

### Python

1. **NO hardcoded API keys**
   ```python
   # NEVER
   api_key = "sk-..."

   # ALWAYS
   api_key = os.getenv("OPENAI_API_KEY")
   ```

2. **NO database operations in `__init__` methods**

3. **NO blocking operations in Flask routes**
   - Use threading for long-running tasks like grading

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

### Clever Integration
- `CLEVER_CLIENT_ID` — OAuth client ID
- `CLEVER_CLIENT_SECRET` — OAuth client secret
- `CLEVER_REDIRECT_URI` — OAuth callback URL
- `CLEVER_DISTRICT_TOKEN` — District app token (for Secure Sync)
- `CLEVER_API_VERSION` — API version (default: v3.0)

### ClassLink SSO
- `CLASSLINK_CLIENT_ID` — OAuth client ID (from ClassLink developer portal)
- `CLASSLINK_CLIENT_SECRET` — OAuth client secret
- `CLASSLINK_REDIRECT_URI` — OAuth callback URL (defaults to `https://app.graider.live/api/classlink/callback`)

### OneRoster Integration (1EdTech)
- `ONEROSTER_BASE_URL` — OneRoster API root (e.g., `https://sis.district.org/ims/oneroster/v1p1`)
- `ONEROSTER_CLIENT_ID` — OAuth 2.0 client ID
- `ONEROSTER_CLIENT_SECRET` — OAuth 2.0 client secret
- `ONEROSTER_TOKEN_URL` — OAuth token endpoint (optional, defaults to `{base_url}/token`)
- `ONEROSTER_SCHOOL_ID` — School sourcedId to scope roster fetch (optional)

### LTI 1.3 Integration
- `LTI_TOOL_URL` — Tool base URL for OIDC/launch callbacks (defaults to request host, set in production to `https://app.graider.live`)

### District Admin
- `DISTRICT_ADMIN_PASSWORD` — Initial district admin password (optional, can be set via /district first-time setup instead)

### Periodic Roster Sync
- `PERIODIC_SYNC_SECRET` — Shared secret for cron webhook auth (set in Railway + GitHub Actions secrets)

### Optional
- `OPENAI_API_KEY` — Default OpenAI key (fallback)
- `ANTHROPIC_API_KEY` — Default Anthropic key (fallback)
- `FLASK_ENV` — Set to "development" for dev mode
- `REDIS_URL` — Redis for session storage in production
- `GRAIDER_EXPORT_DIR` — Base directory for generated exports (docx/csv/etc.); defaults to `~/Downloads/Graider`; override to redirect all export output (the test suite sets it to a temp dir for isolation)

---

## Supabase Tables

### Authentication & Sessions
- `classes` — Teacher's classes (name, join_code, clever_section_id)
- `students` — Student records (name, email, student_id_number, accommodations)
- `class_students` — Enrollment junction (class_id, student_id)
- `student_sessions` — Hashed session tokens with expiry

### Content & Submissions
- `published_assessments` — Join-code published content (anonymous portal, has teacher_id)
- `published_content` — Class-based published content (Clever/roster, has class_id + content_type + due_date)
- `student_submissions` — Authenticated student submissions (class-based path)
- `submissions` — Anonymous join-code submissions

### Storage & Audit
- `teacher_data` — Key-value storage per teacher (assignments, lessons, resources, settings, rubric)
- `audit_log` — FERPA-compliant audit trail (action, teacher_id, timestamp, details)

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

### 1. Read Before Write
Understand context before changing code. Read the function, its callers, and related tests before modifying anything. Never propose changes to code you haven't read. For data-flow bugs, trace the full pipeline (generation → hydration → rendering) before patching one layer.

### 2. Simplicity First
Make every change as simple as possible. Minimum viable change, not minimum effort. Don't add features, refactor code, or make "improvements" beyond what was asked. Three similar lines of code is better than a premature abstraction. If a fix touches more than 3 files, pause and ask if there's a simpler way.

### 3. Programmatic Over Probabilistic
Fix bugs in code, not prompts. If the AI can generate bad data, write deterministic post-processing that catches and corrects it — don't rely on prompt wording to prevent it. Prompt improvements are layer 1; code validation is the safety net that actually matters.

### 4. Verify the User Flow
Unit tests aren't enough — test what the user actually sees. `npm run build` succeeding doesn't mean the feature works. After backend changes, generate a real assessment/assignment and verify the output. After frontend changes, check the rendered UI. "Build passes" is necessary but not sufficient.

### 5. Minimal Blast Radius
Understand what you're touching before you touch it. A one-object fix (domainNameMap) and a cross-cutting pipeline change (_infer_editable_columns) require different levels of caution. For multi-file changes, map the affected callers first. Never change a shared utility without checking all consumers.

### 6. Root Cause, Not Patch
Find and fix the actual problem. Empty data tables? Fix the hydration logic that blanks all cells, don't just tell the AI to try harder in the prompt. "N" and "P" buttons? The map is missing entries, not a CSS issue. Ask "why is this happening?" before "how do I hide it?"

### 7. Don't Flag What You Fix
If a deterministic pipeline phase corrects a problem (e.g., `_normalize_points` fixes point totals), don't also flag it as a warning in a separate validation phase. The user sees a confusing warning about a value that's already been corrected. Either fix silently or warn without fixing — never both.

### 8. Plan for Non-Trivial Tasks
Enter plan mode for any task requiring 3+ steps or architectural decisions. If something goes sideways, STOP and re-plan — don't keep pushing down a broken path. Write detailed specs upfront to reduce ambiguity. Use plan mode for verification steps, not just building.

### 9. Autonomous Bug Fixing
When given a bug report with a screenshot or clear description: just fix it. Read the relevant code, identify the root cause, implement the fix, test it. Don't ask "what would you like me to do?" when the answer is obviously "fix it." Zero context-switching required from the user.

### 10. Subagent Discipline
Use subagents when the task requires 3+ searches, parallel research across multiple files, or would pollute the main context with large outputs. Don't use them for simple greps or reading one file. One task per subagent for focused execution. Prefer direct Glob/Grep/Read for targeted lookups.

### 11. Every Error Is Yours to Fix
When you find a bug — silent failure, swallowed exception, broken import, latent NameError, dead-code path — the default action is **fix it**, not file-and-defer. "I'll track it as a follow-up" is an escape hatch that turns into rot. Filing a separate issue is reserved for genuinely cross-cutting refactors (different storage key + multi-file + SSE consumer audit, like GH #247) — not "this would be a 5-line fix but isn't strictly in PR scope."

If you can fix it in <15 minutes without touching unrelated code, fix it. Don't just label it MEDIUM and move on. Don't just write a comment that says "TODO." Fix it, add a regression test, ship it.

If the fix genuinely exceeds PR scope (3+ files of unrelated changes, requires architectural decisions, or would balloon the diff past 500 lines), then file a follow-up — but include the **specific fix sketch** and a **5-line repro** in the issue body so future-you (or another contributor) can land it without re-investigating. Filing without a fix sketch is deferring, not tracking.

### 12. Handoff Discipline (avoid context-fatigue dead-ends)

Before `/clear`, `/compact`, an unattended loop, or after 3+ failed attempts at the same root cause:
write `handoff.md` (or run `/handoff`). Be honest about what you tried and what *failed* — disproved
hypotheses are the most valuable part. Full required-sections list + self-trigger heuristic: see the
`/handoff` skill (it's the canonical spec; don't duplicate it here).

### 13. Review Gates Before Auto-Merge (class the PR first)

Classify every PR before opening it: **Class A** (behavior-preserving refactor, proven by nets) →
auto-merge on green is earned. **Class B** (net-new behavior OR compliance/security/FERPA) → code
review is a HARD pre-gate: **create PR → review → fix to clean → THEN merge manually** (never
`gh pr merge --auto` with a review in flight). The tell: *"am I adding logic, or just moving it?"* —
adding/changing logic (regexes, scoring, redaction, auth) ⇒ Class B. Full rationale + the PR #565
origin story: `.claude/rules/workflow.md` ("Class A vs Class B").

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

This project is indexed by GitNexus as **Graider** (19463 symbols, 48682 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/Graider/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Graider/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Graider/clusters` | All functional areas |
| `gitnexus://repo/Graider/processes` | All execution flows |
| `gitnexus://repo/Graider/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
