# Graider — Architecture & Developer Guide

A developer-oriented map of how Graider is built: what the pieces are, how they fit, where to find things, and how to run/test/ship. Pair this with [`API_REFERENCE.md`](./API_REFERENCE.md) (the 308-endpoint surface) and the root `CLAUDE.md` (contributor rules + the AI-grading factor list).

---

## 1. What Graider is

Graider is an AI-powered grading and lesson-planning assistant for educators: a Flask backend that serves a React (Vite) single-page app, uses OpenAI / Anthropic / Gemini for grading and content generation, and persists to Supabase (Postgres). Teachers grade student work, generate assessments and lesson plans, and publish them to students via two portals; districts integrate rosters via Clever / ClassLink / OneRoster / LTI 1.3.

## 2. Tech stack

| Layer | Tech |
|-------|------|
| Frontend | React 18, Vite, Vitest + React Testing Library (unit), Playwright (E2E) |
| Backend | Python / Flask, served via `backend/app.py`; pytest |
| AI | OpenAI, Anthropic, Gemini (multi-provider); Mathpix OCR; ElevenLabs / OpenAI TTS |
| Data | Supabase (Postgres) + local `~/.graider_*` config files |
| Infra | Railway (backend, auto-deploy on merge to `main`), Vercel (marketing landing) |

## 3. Repository layout

```
graider/
├── backend/
│   ├── app.py                 # Flask app entry: factory, error handlers, serves the built SPA from backend/static/
│   ├── routes/                # ~30 Flask blueprints, one per domain (see API_REFERENCE.md)
│   ├── services/              # ~40 domain service modules (Flask-free, unit-tested business logic)
│   ├── auth.py / clever.py    # JWT auth + Clever roster client
│   └── tasks/                 # background grading/enqueue tasks
├── assignment_grader.py       # Core grading engine (multipass pipeline, provider calls) — 5,344 LOC
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Teacher dashboard shell (state owner + routing + tab orchestration)
│   │   ├── tabs/              # 14 tab-level screens (BuilderTab, GradeTab, PlannerTab, ResultsTab, SettingsTab, AnalyticsTab…)
│   │   ├── components/        # 78 presentational components (incl. the extracted Settings*/Planner* sections, modals, Sidebar, AuthScreens)
│   │   └── hooks/             # 10 custom hooks (domain state/effects: useSubscription, useFocusPolling, useOutlookSendPolling, usePortalSubmissions, useSettingsAutoSave, useQuestionEditing, useConfig, useVoice, useBehavior*)
│   └── e2e/                   # 24 Playwright specs (flow + health-check)
├── tests/                     # 270 backend pytest files
├── landing/                   # Vercel marketing site (separate deploy)
└── docs/                      # this guide, API_REFERENCE, DEPLOYMENT, runbooks, FERPA, plans
```

**Critical:** the active frontend is `frontend/src/App.jsx` (Vite-built into `backend/static/`). The root `graider_app.py` is a **legacy embedded-React UI that is NOT in use** — never edit it for UI changes.

## 4. Frontend architecture

`App.jsx` is the **app shell**: it owns the cross-tab/shared React state, the auth gate, tab routing, and wires props down to the tab/screen components. The screens themselves live in `tabs/` and `components/`.

- **Auth gate** (`components/AuthScreens.jsx`): before the dashboard, App renders `AuthLoadingScreen` / `ApprovalCheckingScreen` / `NotApprovedScreen`, or `LoginScreen` / `PasswordResetScreen`.
- **Shell chrome**: `components/Sidebar.jsx` (tab navigation, collapse) + a top header.
- **Tabs** (`activeTab` switch): Grade, Results, Grading Setup (`BuilderTab`), Analytics, Planner, Script Builder (Automations), Assistant, Settings, Help. Each is its own component; large ones (Planner, Settings) are further decomposed into per-section components (`PlannerCalendar/Tools/Dashboard/Lesson/Assessment`, `SettingsGeneral/Grading/AI/Classroom/Privacy/Billing/Resources`).
- **Modals** are extracted presentational components (`ReviewModal`, `DocumentEditorModal`, `EmailPreviewModal`, `CurveModal`, …), rendered from App with their state forwarded.
- **Custom hooks** (`hooks/`) own self-contained domain state + effects that App previously held inline — e.g. `useSubscription` (billing status), `useFocusPolling` / `useOutlookSendPolling` / `usePortalSubmissions` (status pollers), `useSettingsAutoSave` (debounced config/rubric saves), `useQuestionEditing` (assessment question editing). App calls them and forwards the returned bundle.

> **Decomposition note:** `App.jsx`, `PlannerTab`, and `SettingsTab` were each god-files (6.5–7.4k LOC). They were decomposed behavior-preservingly into the focused tabs/components/hooks above. When adding state that one tab owns, declare it in that tab; reserve `App.jsx` for genuinely cross-tab state.

Two student-facing entry points share `components/StudentPortal.jsx`: the anonymous **join-code** path (`/join/CODE`) and the authenticated **class-based** path (`/student` via `StudentApp.jsx`).

## 5. Backend architecture

`backend/app.py` (673 LOC) is a thin entry: it builds the Flask app, mounts error handlers, and serves the built SPA from `backend/static/`. The domain **blueprints** are defined one-per-file in `backend/routes/` and registered centrally in `backend/routes/__init__.py`. Each route file is one domain (grading, planner, settings, student portal, clever, lti, district, …) — see `API_REFERENCE.md` for the full 308-endpoint map and auth requirements.

- **Services layer** (`backend/services/`, ~40 modules): Flask-free, independently unit-tested business logic extracted from the routes and the grading engine — e.g. `grading_service`, `portal_grading`, `response_extraction`, `planner_export/prompts/standards`, `document_generator`, `submission_repository` (the dual-publish-path abstraction), the `assistant_tools_*` family (AI tool implementations).
- **Grading engine** (`assignment_grader.py`): the multipass pipeline (`grade_multipass` → `grade_per_question` → `generate_feedback`) plus single-pass `grade_assignment`. It must account for **all** AI grading factors (rubric, grading style, IEP/504, history, expected answers, …) — see the "AI Grading Factors" section in `CLAUDE.md`; dropping a factor produces wrong scores. Grading runs in a background thread to keep routes non-blocking.
- **Auth**: JWT + Clever session resolution (`backend/auth.py`); route decorators `@require_teacher`, `@require_admin`, `@require_clever_session`.

### Two publish paths (important)
Graider has two parallel publishing systems, both using `StudentPortal.jsx` and the same grading functions:
1. **Join-code** (`published_assessments` + `submissions`): anonymous 6-char code, no enrollment.
2. **Class-based** (`published_content` + `student_submissions`): authenticated via SSO/email+code, supports due dates and tracking.

The write/grading layer is unified behind a `SubmissionRepository` abstraction (`backend/services/submission_repository.py`).

## 6. Persistence

- **Supabase tables**: `classes`, `students`, `class_students`, `student_sessions`, `published_assessments` / `submissions` (join-code), `published_content` / `student_submissions` (class-based), `teacher_data` (per-teacher KV: assignments/lessons/resources/settings/rubric), `audit_log` (FERPA trail).
- **Local config**: `~/.graider_rubric.json`, `~/.graider_settings.json`, `~/.graider_assignments/`.

## 7. Local development

```bash
# Backend (always use the repo venv)
source venv/bin/activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." >> .env          # plus SUPABASE_*, FLASK_SECRET_KEY (see CLAUDE.md env list)

# Frontend build → backend/static, then serve via Flask
cd frontend && npm install && npm run build
cd .. && FLASK_ENV=development python backend/app.py   # http://localhost:3000 (dev mode auto-auths a local teacher)
```

`FLASK_ENV=development` auto-authenticates a local-dev teacher, which is what the E2E suite relies on.

## 8. Testing

| Layer | Command | What it covers |
|-------|---------|----------------|
| Frontend unit | `cd frontend && npx vitest run` | 47 files — component smoke tests + hook `renderHook` characterization tests |
| Frontend E2E | `cd frontend && E2E_REUSE_BACKEND=1 npx playwright test` | 24 specs — live-app flows (dashboard nav, modals, sidebar, settings) + `health-check` |
| Backend | `pytest` (in the venv) | 270 files; CI gate `--cov-fail-under=70` |

The E2E `webServer` builds the frontend and spawns `backend/app.py`; `E2E_REUSE_BACKEND=1` reuses an already-running `:3000`. E2E is the safety net that catches integration regressions the unit tests structurally can't (e.g. a prop dropped at a call site).

## 9. CI/CD & deployment

All changes go through PRs. **Branch protection on `main` requires 9 status checks**: Backend Tests (`--cov-fail-under=70`), Frontend Build, Frontend E2E Smoke, Migrations Smoke, Lockfile Drift Check, Ruff Lint, Bandit SAST, Secret Scan (trufflehog), Mypy Strict (Critical Modules). Merging to `main` auto-deploys the backend (with the built SPA) to Railway. The marketing landing deploys separately to Vercel (`cd landing && npx vercel --prod`).

## 10. Conventions & gotchas

- **Never edit `graider_app.py`** for UI — it's legacy. UI work is in `frontend/src/`.
- **Never drop an AI grading factor** — see `CLAUDE.md`. The multipass pipeline threads ~18 factors; missing one silently corrupts scores.
- **FERPA**: student data is audited (`audit_log`); the two publish paths and the dual-table split exist for data-safety reasons. Don't log raw student PII.
- **No hardcoded secrets**; read from env (`os.getenv`). Use `.get()` for dict access.
- **Build artifacts** (`backend/static/`) are generated by `npm run build`; don't hand-edit, and discard stray build diffs before committing.
- **Post-processing pipeline** (`backend/routes/planner_routes.py`, `_post_process_assignment`) has 6 ordered phases — Phase 3c (quality checks) must not flag what Phase 5 (normalization) will fix.

---

*This guide reflects the codebase after the App.jsx / PlannerTab / SettingsTab decomposition. For the authoritative endpoint list see `API_REFERENCE.md`; for contributor rules and the full env-var list see `CLAUDE.md`.*
