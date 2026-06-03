# CLAUDE.md - Graider Development Guide

## Virtual Environment
The Python venv is at: `/Users/alexc/Downloads/Graider/venv/`
Activate with: `source venv/bin/activate`
Always use this venv for running Python commands, installing packages, and starting the backend.

## CRITICAL: Active Frontend

**The active frontend is `frontend/src/App.jsx`** (React + Vite, served via `backend/app.py`).

**`graider_app.py` is the LEGACY frontend** — it contains an old embedded React UI that is NOT in use.
**NEVER edit `graider_app.py` for UI changes.** All frontend work goes in `frontend/src/`.

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

- `Backend Tests` (pytest with `--cov-fail-under=70`; bumped 32→40 in PR #239 to match measured ~41%, then 40→48 on 2026-05-09 after PRs #266-#277 pushed measured global to 49.91%, then 48→60 on 2026-05-11 after PRs #310-#349 (gap-fill sprint + Gemini quality-review sweep) pushed measured global to 63.25%, then 60→70 on 2026-06-03 after PR #638 (166 behavioral tests on assignment_post_processing/response_extraction/grader_roster) pushed measured global to 70.50%. **Sprint target 50% per audit MAJOR #4 HIT 2026-05-09; 60% floor locked the post-sprint wins; 70% floor locks the 2026-06-03 hardening-sprint coverage.** Bump rule: raise floor only when measured global is at least 0.5% above the new floor. Continue raising as coverage grows.)
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
├── graider_app.py          # LEGACY - old embedded React UI, DO NOT EDIT for UI changes
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
- Factor accumulation: `backend/app.py` `file_ai_notes` built inline in grading thread
- Rubric formatting: `backend/app.py` `format_rubric_for_prompt()`
- Per-question grading: `assignment_grader.py` `grade_per_question()`
- Feedback generation: `assignment_grader.py` `generate_feedback()`
- Multipass orchestration: `assignment_grader.py` `grade_multipass()`
- Single-pass (Claude/Gemini): `assignment_grader.py` `grade_assignment()`

---

## Code Style

### JavaScript (Embedded React)

```javascript
// GOOD: Single-line style for inline JSX
<button onClick={() => doSomething()} style={{ padding: '10px' }}>Click</button>

// GOOD: Use String.fromCharCode(10) for newlines in strings
const nl = String.fromCharCode(10);
const text = 'Line 1' + nl + 'Line 2';

// BAD: Multi-line strings with \n (causes Babel parse errors)
const text = 'Line 1\nLine 2';  // NEVER DO THIS

// GOOD: String concatenation for complex strings
const html = '<h1>' + title + '</h1><p>' + content + '</p>';

// BAD: Template literals with backticks (can break in embedded context)
const html = `<h1>${title}</h1>`;  // AVOID
```

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

### JavaScript/React

1. **NO multi-line string literals**
   ```javascript
   // NEVER DO THIS - causes Babel syntax errors
   const str = 'line 1
   line 2';

   // DO THIS INSTEAD
   const nl = String.fromCharCode(10);
   const str = 'line 1' + nl + 'line 2';
   ```

2. **NO template literals with newlines**
   ```javascript
   // AVOID - can break in embedded context
   const html = `
     <div>
       ${content}
     </div>
   `;

   // DO THIS
   const html = '<div>' + content + '</div>';
   ```

3. **NO unclosed JSX tags**
   - Always verify matching opening/closing tags
   - Use React Fragments `<>...</>` for adjacent elements

4. **NO Icon components inside button onClick handlers**
   - Icons in buttons can block click events
   - Put Icon as child, not in onClick

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

## Best Practices

### State Management

```javascript
// Track loaded assignment by filename, not title
const [loadedAssignmentName, setLoadedAssignmentName] = useState('');

// Clear state when importing new document
setLoadedAssignmentName('');

// Compare using filename for highlighting
background: loadedAssignmentName === name ? 'selected' : 'default'
```

### API Endpoints

```python
@app.route('/api/endpoint', methods=['POST'])
def endpoint():
    try:
        data = request.json
        # Validate input
        if not data.get('required_field'):
            return jsonify({"error": "Missing required field"})

        # Process
        result = process(data)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"error": str(e)})
```

### File Operations

```python
# Always use expanduser for user config paths
config_path = os.path.expanduser("~/.graider_settings.json")

# Create directories if needed
os.makedirs(output_folder, exist_ok=True)

# Use Path for cross-platform compatibility
from pathlib import Path
filepath = Path(folder) / filename
```

### Grading Thread

```python
def run_grading_thread(folder, config):
    global grading_state
    grading_state["is_running"] = True

    try:
        # Do work
        for file in files:
            if grading_state.get("stop_requested"):
                break
            # Process file
            grading_state["log"].append(f"Processing {file}")
    finally:
        grading_state["is_running"] = False
```

---

## Common Issues & Fixes

### "Unterminated string constant" Error
**Cause**: Multi-line strings or escape characters in embedded JavaScript
**Fix**: Use `String.fromCharCode(10)` for newlines, string concatenation for multi-line

### "Adjacent JSX elements must be wrapped" Error
**Cause**: Two sibling elements without a parent wrapper
**Fix**: Wrap in `<div>` or `<>...</>` fragment

### Button onClick not working
**Cause**: Often Icon component or styling blocking clicks
**Fix**: Simplify button, test with just `onClick={() => alert('test')}`

### State not updating in UI
**Cause**: State reference not changing or stale closure
**Fix**: Spread operator for new object `{...oldState, newField: value}`

### Assignment config not matching files
**Cause**: Filename sanitization differs from title
**Fix**: Use `loadedAssignmentName` to track by filename, not title

---

## Testing Checklist

Before committing changes:

1. [ ] App starts without Babel errors: `python graider_app.py`
2. [ ] All tabs render (Home, Results, Builder, Planner, Settings)
3. [ ] Can import document in Builder
4. [ ] Can save/load assignment configs
5. [ ] Grading starts and produces results
6. [ ] No console errors in browser DevTools

---

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Run app
python graider_app.py
# Opens at http://localhost:3000
```

---

## API Reference

### Grading
- `POST /api/grade` - Start grading job
- `GET /api/status` - Get grading status/progress
- `POST /api/stop-grading` - Stop current grading

### Assignments
- `GET /api/list-assignments` - List saved configs
- `GET /api/load-assignment?name=X` - Load specific config
- `POST /api/save-assignment-config` - Save config
- `DELETE /api/delete-assignment?name=X` - Delete config

### Settings
- `GET /api/load-rubric` - Load rubric
- `POST /api/save-rubric` - Save rubric
- `GET /api/load-global-settings` - Load global AI notes
- `POST /api/save-global-settings` - Save global AI notes

### Documents
- `POST /api/parse-document` - Parse uploaded Word/PDF
- `POST /api/export-assignment` - Export to Word/PDF

### Lesson Planner
- `POST /api/get-standards` - Get curriculum standards
- `POST /api/generate-lesson-plan` - Generate AI lesson plan
- `POST /api/export-lesson-plan` - Export to Word

### Clever SSO & Roster
- `GET /api/clever/login-url` — Get Clever OAuth URL
- `GET /api/clever/callback` — OAuth callback (handles teachers + students)
- `GET /api/clever/session` — Check Clever session status
- `POST /api/clever/sync-roster` — Manual roster sync
- `POST /api/clever/apply-accommodations` — Apply IEP/ELL accommodations
- `GET /api/clever/district-keys` — Check district API key status
- `POST /api/clever/district-keys` — Save district API keys (admin only)
- `POST /api/clever/delete-data` — Delete all Clever-sourced data
- `POST /api/clever/logout` — Clear Clever session
- `POST /api/clever/student-token` — Exchange auth code for student session token
- `GET /api/clever/health` — Health check (config + connectivity status)

### ClassLink SSO
- `GET /api/classlink/login-url` — Get ClassLink OAuth URL
- `GET /api/classlink/callback` — OAuth callback (ClassLink redirects here)
- `GET /api/classlink/session` — Check ClassLink session status
- `POST /api/classlink/logout` — Clear ClassLink session

### OneRoster Integration (1EdTech)
- `GET /api/oneroster/config` — Check OneRoster configuration status
- `POST /api/oneroster/config` — Save OneRoster connection settings
- `POST /api/oneroster/test` — Test API connectivity
- `POST /api/oneroster/sync-roster` — Fetch and sync roster from OneRoster API
- `POST /api/oneroster/apply-accommodations` — Apply IEP/ELL presets from demographics
- `POST /api/oneroster/delete-data` — Delete all OneRoster-synced data

### LTI 1.3 Integration (1EdTech)
- `GET /api/lti/jwks` — Tool's public JWKS (for platform verification)
- `GET,POST /api/lti/login` — OIDC third-party login initiation
- `POST /api/lti/launch` — Launch callback (platform posts id_token)
- `GET /api/lti/config` — List registered LTI platforms
- `POST /api/lti/config` — Register an LTI platform
- `DELETE /api/lti/config` — Delete a platform registration
- `GET /api/lti/contexts` — List LTI course contexts with AGS endpoints and student counts
- `POST /api/lti/sync-grades` — Sync grades to LMS via AGS (auto-matches students by name)

### District Admin Setup
- `POST /api/district/auth` — Authenticate as district admin (password)
- `DELETE /api/district/auth` — Clear district admin session
- `POST /api/district/change-password` — Change district admin password
- `GET /api/district/config-status` — Public: check if SIS/AI keys configured
- `GET /api/district/config` — Load full district config (admin auth required)
- `POST /api/district/config` — Save SIS + AI key config (admin auth required)
- `POST /api/district/test-connection` — Test SIS connectivity (admin auth required)
- `POST /api/oneroster/teacher-id` — Save teacher's OneRoster sourcedId (teacher auth)

### School Admin (Principal)
- `GET /api/admin/status` — Check if current user is a school admin
- `POST /api/admin/claim` — Claim admin role with invite code
- `GET /api/admin/teachers` — List teachers at admin's school
- `GET /api/admin/overview` — School-wide aggregate stats
- `GET /api/admin/teacher/<id>/summary` — Per-teacher drill-down
- `GET /api/admin/activity` — Recent activity across admin's teachers
- `POST /api/district/admin-invite` — Create admin invite code (district admin)
- `GET /api/district/admins` — List current admins (district admin)
- `DELETE /api/district/admins` — Revoke admin (district admin)
- `GET /api/district/teacher-search` — Search teachers by name/email (district admin)

### Student Portal
- `POST /api/student/login` — Student login (email + class code)
- `GET /api/student/session` — Validate student session
- `GET /api/student/dashboard` — Get student's assigned work
- `GET /api/student/content/<id>` — Get assessment/assignment content
- `POST /api/student/class-submit/<content_id>` — Submit answers (class-based, authenticated via `X-Student-Token`)

### Classes
- `POST /api/classes` — Create a class
- `GET /api/classes` — List teacher's classes
- `GET /api/classes/<id>/students` — List enrolled students
- `POST /api/classes/<id>/sync-roster` — Sync roster via CSV
- `POST /api/publish-to-class` — Publish content to a class

### Portal (Join Code)
- `POST /api/publish-assessment` — Publish via join code (requires teacher auth)
- `GET /api/student/join/<code>` — Get assessment by join code
- `POST /api/student/submit/<code>` — Submit via join code
- `GET /api/teacher/assessments` — List teacher's published assessments
- `GET /api/teacher/assessment/<code>/results` — Get submissions for assessment
- `POST /api/teacher/assessment/<code>/toggle` — Activate/deactivate assessment
- `DELETE /api/teacher/assessment/<code>` — Delete assessment + submissions

### Resources (Assets)
- `POST /api/save-resource` — Auto-save generated content (requires teacher auth)
- `GET /api/list-resources` — List saved resources with optional type filter
- `POST /api/load-resource` — Load a saved resource by ID
- `POST /api/delete-resource` — Delete a saved resource

### Behavior Tracking
- `POST /api/behavior/session` — Start behavior tracking session
- `GET /api/behavior/data` — Get behavior data
- `GET /api/behavior/events` — Get behavior events
- `DELETE /api/behavior/data` — Clear behavior data

### Automations
- `GET /api/automations` — List automation workflows
- `POST /api/automations` — Create automation workflow
- `DELETE /api/automations/<id>` — Delete workflow
- `POST /api/automations/<id>/run` — Run a workflow

### Slide Deck Generation
- `POST /api/generate-slides` — Generate slide deck content + AI graphics from lesson plan
- `POST /api/export-slides` — Export generated slides as PowerPoint (.pptx)

### Surveys
- `POST /api/survey/create` — Create feedback survey
- `GET /api/survey/results` — Get survey results
- `GET /api/survey/list` — List surveys
- `POST /api/survey/<code>/submit` — Submit survey response

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

Long sessions degrade reasoning. `/compact` summarizes facts but inherits the *framing* of the prior conversation — including bad hypotheses and false trails. The fix is a clean handoff to a fresh agent.

**Write `handoff.md` at repo root BEFORE any of these:**

- Running `/clear` or `/compact` when there's an unresolved debug thread
- A scheduled autonomous loop that may run unattended >2 hours
- Stopping work mid-investigation to step away
- You've made **3+ failed attempts** at the same root cause

**The handoff MUST include** (in this order):

1. **Goal** — one sentence stating what we're trying to accomplish
2. **TL;DR** — 3-5 bullets: what's shipped, what works, what's blocked
3. **Current state** — files modified, PRs open/merged, follow-up issues filed
4. **Local repro** — exact shell commands a fresh agent runs to reproduce the failure
5. **Disproved hypotheses** — things tried that DIDN'T work, with brief reason each was ruled out
6. **Most likely remaining causes** — ranked
7. **Concrete next step** — specific code/PR sketch
8. **References** — PR numbers, issue numbers, CI run IDs, plan docs

Be honest about what you actually tried and what failed. **Do NOT sanitize the failures** — those are the most valuable part of the handoff. The next agent needs them to avoid re-trying the same dead ends.

**Self-trigger heuristic**: if you catch yourself thinking *"let me try X again with a slight variation"* on the same problem for the 3rd time, STOP, write `handoff.md`, and tell the user "I've hit a context-fatigue wall — handoff.md written; recommend `/clear` + fresh session."

**Or invoke explicitly**: `/handoff` slash command auto-generates the file from current session state. Use when the user (or you) recognize the wall before failure mode 3 hits.

`handoff.md` is committable when the handoff itself is documentation of an open investigation (e.g., what shipped tonight at audit MAJOR #5 Stage 3a). Default: leave uncommitted unless it serves as artifact.

### 13. Review Gates Before Auto-Merge (class the PR first)

Classify every PR **before opening it**, because the class determines whether auto-merge-on-green is safe:

- **Class A — behavior-preserving refactor:** the golden net (results) + prompt-snapshot net (wording) + AST byte-identity vs `main` *prove* behavior is unchanged. Green CI ≈ provably correct → squash-auto-merge on green is earned and fine.
- **Class B — net-new behavior, OR anything compliance / security / FERPA:** green CI only covers the cases you imagined to test. A code review is a **HARD pre-gate**, not a concurrent advisory.

For Class B the sequence is strict and removes the race structurally: **create PR → review → fix to clean → THEN merge.** Do NOT call `gh pr merge --auto` with a review in flight; for Class B, merge **manually** after the review returns clean. Never let a review run *alongside* an armed auto-merge — it can only catch issues after the merge has already fired.

The tell that forces the classification: **"am I adding logic, or just moving it?"** Adding/changing logic (especially regexes, scoring, redaction, auth) ⇒ Class B ⇒ review gates the merge. Moving code verbatim ⇒ Class A ⇒ nets gate the merge.

> Origin: 2026-05-24, PR #565 (FERPA prompt sanitization). Auto-merge was armed *concurrently* with the code review; the review caught a Critical over-redaction (common-word student names corrupting answers) but only *after* #565 had auto-merged on green. Fixed forward in #566. The error wasn't "no review" — it was that the review wasn't sequenced as a gate.

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

*Last updated: March 20, 2026*

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
