# Graider Refactoring Plan - Production Architecture

> **Last Updated:** January 25, 2026
> **Status:** Phase 2 COMPLETE - Incremental refactoring in progress

## Current Approach: Keep Original Working

The original `graider_app.py` remains the **production app** while we incrementally port features to the new modular structure.

### To Run the App (Original - Full Features):
```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python graider_app.py
# Opens at http://localhost:3000
```

### To Run the Refactored Version (Partial - Missing Builder/Planner):
```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python backend/app.py
# Opens at http://localhost:3000
```

---

## Current State Assessment

### File Structure (As-Is)
```
graider/
├── graider_app.py              # 4,238 lines - Flask + ALL frontend JSX
├── assignment_grader.py        # 1,310 lines - Grading logic (extracted)
├── email_sender.py             #   303 lines - Email logic (extracted)
├── sharepoint_watcher.py       #   455 lines - File watching (extracted)
├── requirements.txt
├── .env
├── CLAUDE.md                   # Development guidelines
├── User_Manual.md
└── Results/                    # Output folder
```

### What's Already Extracted
| Service | File | Lines | Status |
|---------|------|-------|--------|
| Grading Logic | `assignment_grader.py` | 1,310 | Done |
| Email Sending | `email_sender.py` | 303 | Done |
| File Watching | `sharepoint_watcher.py` | 455 | Done |

### What Remains in graider_app.py (4,238 lines)
| Section | Lines | Description |
|---------|-------|-------------|
| HTML_TEMPLATE (Frontend) | ~2,500 | React JSX embedded as Python string |
| Flask Routes (API) | ~600 | 22 API endpoints |
| Standards Data | ~800 | Hardcoded FL/TX standards |
| Helper Functions | ~300 | Misc utilities |

### Current Features (6 Tabs)
1. **Grade** - Start grading, auto-grade mode, progress log
2. **Results** - Graded assignments table, review modal
3. **Settings** - Folders, API key, email config, grading period
4. **Builder** - Import documents, mark sections, AI notes
5. **Analytics** - Charts, student progress, period filtering
6. **Planner** - Lesson plan generator with state standards

### API Endpoints (22 total)
```
Core:           /, /api/status, /api/browse
Grading:        /api/grade, /api/stop-grading, /api/check-new-files
Documents:      /api/parse-document, /api/open-folder
Email:          /api/send-emails
Rubric:         /api/save-rubric, /api/load-rubric
Settings:       /api/save-global-settings, /api/load-global-settings
Assignments:    /api/save-assignment-config, /api/list-assignments,
                /api/load-assignment, /api/delete-assignment, /api/export-assignment
Analytics:      /api/analytics
Standards:      /api/get-standards
Planner:        /api/generate-lesson-plan, /api/export-lesson-plan
```

---

## Target Architecture (Production)

```
graider/
├── backend/
│   ├── app.py                      # Flask app entry (~150 lines)
│   ├── config.py                   # Configuration management
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── grading_routes.py       # Grading API endpoints
│   │   ├── document_routes.py      # Document parsing endpoints
│   │   ├── assignment_routes.py    # Assignment config endpoints
│   │   ├── analytics_routes.py     # Analytics endpoints
│   │   ├── planner_routes.py       # Lesson planner endpoints
│   │   └── settings_routes.py      # Settings endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── grading_service.py      # (existing assignment_grader.py)
│   │   ├── email_service.py        # (existing email_sender.py)
│   │   ├── document_service.py     # Document parsing logic
│   │   ├── standards_service.py    # Standards database
│   │   └── lesson_service.py       # Lesson plan generation
│   ├── data/
│   │   ├── standards_fl.json       # Florida standards
│   │   └── standards_tx.json       # Texas standards
│   └── static/                     # Built frontend (from Vite)
│       ├── index.html
│       └── assets/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── styles/
│       │   └── globals.css
│       ├── components/
│       │   ├── Layout/
│       │   │   ├── Header.jsx
│       │   │   └── TabNav.jsx
│       │   ├── GradeTab/
│       │   │   ├── GradeTab.jsx
│       │   │   ├── GradingProgress.jsx
│       │   │   └── AutoGradeToggle.jsx
│       │   ├── ResultsTab/
│       │   │   ├── ResultsTab.jsx
│       │   │   └── ReviewModal.jsx
│       │   ├── SettingsTab/
│       │   │   └── SettingsTab.jsx
│       │   ├── BuilderTab/
│       │   │   ├── BuilderTab.jsx
│       │   │   ├── DocumentEditor.jsx
│       │   │   └── SavedAssignments.jsx
│       │   ├── AnalyticsTab/
│       │   │   ├── AnalyticsTab.jsx
│       │   │   ├── StatsCards.jsx
│       │   │   ├── Charts.jsx
│       │   │   └── StudentProgress.jsx
│       │   ├── PlannerTab/
│       │   │   ├── PlannerTab.jsx
│       │   │   ├── StandardsBrowser.jsx
│       │   │   └── LessonPlanDisplay.jsx
│       │   └── shared/
│       │       ├── Icon.jsx
│       │       ├── Button.jsx
│       │       └── Modal.jsx
│       ├── hooks/
│       │   ├── useApi.js
│       │   └── useConfig.js
│       └── services/
│           └── api.js
│
├── requirements.txt
├── package.json                    # Root scripts for dev/build
├── .env
└── README.md
```

---

## Migration Phases

### Phase 1: Backend Restructure (Foundation)
**Goal:** Clean backend, keep frontend working as-is
**Risk:** Low
**Estimated Time:** 2-3 hours

#### Tasks:
1. Create `backend/` folder structure
2. Move `graider_app.py` to `backend/app.py`
3. Create `backend/routes/` and split API endpoints into separate files:
   - `grading_routes.py` - /api/grade, /api/stop-grading, /api/check-new-files, /api/status
   - `document_routes.py` - /api/parse-document, /api/open-folder, /api/browse
   - `assignment_routes.py` - /api/save-assignment-config, /api/list-assignments, etc.
   - `analytics_routes.py` - /api/analytics
   - `planner_routes.py` - /api/get-standards, /api/generate-lesson-plan, /api/export-lesson-plan
   - `settings_routes.py` - /api/save-rubric, /api/load-rubric, /api/save-global-settings, etc.
4. Move existing services:
   - `assignment_grader.py` → `backend/services/grading_service.py`
   - `email_sender.py` → `backend/services/email_service.py`
5. Extract standards data to JSON files in `backend/data/`
6. Create `backend/config.py` for configuration management

#### Result:
```
backend/
├── app.py                    # ~200 lines (entry point + HTML_TEMPLATE)
├── config.py
├── routes/                   # ~400 lines total (split from app.py)
└── services/                 # Existing extracted services
```

**Frontend continues to work unchanged** (HTML_TEMPLATE still in app.py)

---

### Phase 2: Frontend Build Setup
**Goal:** Proper React development environment
**Risk:** Medium (requires careful migration)
**Estimated Time:** 3-4 hours

#### Tasks:
1. Create `frontend/` folder with Vite setup
2. Create `package.json` with dependencies:
   ```json
   {
     "dependencies": {
       "react": "^18.2.0",
       "react-dom": "^18.2.0",
       "recharts": "^2.12.7",
       "lucide-react": "^0.263.1"
     }
   }
   ```
3. Create `vite.config.js` with proxy to Flask API
4. Extract CSS from HTML_TEMPLATE to `src/styles/globals.css`
5. Extract React code from HTML_TEMPLATE to `src/App.jsx`
6. Update Flask to serve built static files
7. Remove HTML_TEMPLATE from backend

#### Result:
- Frontend runs on Vite dev server (port 5173) with hot reload
- API calls proxy to Flask (port 3000)
- Production build outputs to `backend/static/`

---

### Phase 3: Component Extraction
**Goal:** Maintainable, testable React components
**Risk:** Low (incremental)
**Estimated Time:** 4-6 hours

#### Tasks:
1. Extract shared components:
   - `Icon.jsx` - Lucide icon wrapper
   - `Button.jsx` - Styled button component
   - `Modal.jsx` - Reusable modal

2. Extract tab components (one at a time):
   - `GradeTab.jsx` (~200 lines)
   - `ResultsTab.jsx` (~150 lines)
   - `SettingsTab.jsx` (~200 lines)
   - `BuilderTab.jsx` (~400 lines)
   - `AnalyticsTab.jsx` (~350 lines)
   - `PlannerTab.jsx` (~500 lines)

3. Create custom hooks:
   - `useApi.js` - API call wrapper with loading/error states
   - `useConfig.js` - Config state management

4. Create API service:
   - `services/api.js` - Centralized API client

#### Result:
- App.jsx reduced to ~100 lines (routing + layout only)
- Each tab is self-contained component
- Shared logic in hooks
- Easy to test and maintain

---

### Phase 4: Production Hardening (Optional)
**Goal:** Production-ready deployment
**Risk:** Low
**Estimated Time:** 2-3 hours

#### Tasks:
1. Add error boundaries to React
2. Add loading states and skeleton screens
3. Add offline detection
4. Implement proper logging (backend)
5. Add health check endpoint
6. Create Docker configuration
7. Create deployment scripts

---

## Development Workflow (After Refactor)

### Development Mode
```bash
# Terminal 1: Backend
cd backend
python app.py                    # Runs on localhost:3000

# Terminal 2: Frontend (hot reload)
cd frontend
npm run dev                      # Runs on localhost:5173
```

### Production Build
```bash
# Build frontend
cd frontend
npm run build                    # Outputs to backend/static/

# Run production
cd backend
python app.py                    # Serves everything on localhost:3000
```

### Root package.json Scripts
```json
{
  "scripts": {
    "dev": "concurrently \"npm run dev:backend\" \"npm run dev:frontend\"",
    "dev:backend": "cd backend && python app.py",
    "dev:frontend": "cd frontend && npm run dev",
    "build": "cd frontend && npm run build",
    "start": "cd backend && python app.py"
  }
}
```

---

## File Size Targets

| File | Current | Target |
|------|---------|--------|
| backend/app.py | 4,238 lines | ~150 lines |
| backend/routes/* (total) | - | ~500 lines |
| backend/services/* (total) | ~2,068 lines | ~2,200 lines |
| frontend/src/App.jsx | - | ~100 lines |
| frontend/src/components/* | - | ~1,800 lines |

---

## Execution Checklist

### Phase 1: Backend Restructure ✅ COMPLETE
- [x] Create backend/ folder
- [x] Create backend/routes/ folder
- [x] Extract grading_routes.py
- [x] Extract document_routes.py
- [x] Extract assignment_routes.py
- [x] Extract analytics_routes.py
- [x] Extract planner_routes.py
- [x] Extract settings_routes.py
- [x] Move assignment_grader.py to services/ (kept in root, imports work)
- [x] Move email_sender.py to services/ (kept in root, imports work)
- [x] Extract standards to JSON files (backend/data/standards_fl_*.json)
- [x] Create config.py
- [x] Update imports in app.py
- [x] Test all endpoints work

### Phase 2: Frontend Build Setup ✅ COMPLETE
- [x] Create frontend/ folder
- [x] Initialize Vite project (package.json)
- [x] Install dependencies (react, recharts, lucide-react)
- [x] Configure vite.config.js with API proxy
- [x] Extract CSS to globals.css
- [x] Extract React code to App.jsx
- [x] Configure Flask to serve static files
- [x] Remove HTML_TEMPLATE (new backend/app.py serves static)
- [x] Test dev mode works
- [x] Test production build works

### Phase 3: Component Extraction (NEXT)
- [x] Create shared/Icon.jsx
- [ ] Create shared/Button.jsx
- [ ] Create shared/Modal.jsx
- [ ] Extract GradeTab.jsx
- [ ] Extract ResultsTab.jsx
- [ ] Extract SettingsTab.jsx
- [ ] Extract BuilderTab.jsx (currently placeholder)
- [ ] Extract AnalyticsTab.jsx
- [ ] Extract PlannerTab.jsx (currently placeholder)
- [x] Create useApi.js hook
- [x] Create useConfig.js hook
- [x] Create services/api.js
- [ ] Update App.jsx to use components

---

## Quick Start Commands

### Development Mode (Hot Reload Frontend)
```bash
# Terminal 1: Backend
source venv/bin/activate
python backend/app.py            # Runs on localhost:3000

# Terminal 2: Frontend (hot reload)
cd frontend
npm run dev                      # Runs on localhost:5173 (proxies API to :3000)
```

### Production Mode (Single Server)
```bash
# Build frontend first
cd frontend && npm run build     # Outputs to backend/static/

# Run production
source venv/bin/activate
python backend/app.py            # Serves everything on localhost:3000
```

---

## Current File Structure (After Phase 2)

```
graider/
├── backend/
│   ├── app.py                   # ~320 lines - Flask entry + grading thread
│   ├── config.py                # Configuration management
│   ├── routes/
│   │   ├── __init__.py          # Route registration
│   │   ├── grading_routes.py    # /api/status, /api/stop-grading, etc.
│   │   ├── document_routes.py   # /api/browse, /api/parse-document
│   │   ├── assignment_routes.py # /api/save-assignment-config, etc.
│   │   ├── analytics_routes.py  # /api/analytics
│   │   ├── planner_routes.py    # /api/get-standards, /api/generate-lesson-plan
│   │   ├── settings_routes.py   # /api/save-rubric, /api/save-global-settings
│   │   └── email_routes.py      # /api/send-emails
│   ├── data/
│   │   ├── standards_fl_history.json
│   │   └── standards_fl_civics.json
│   └── static/                  # Built React frontend
│       ├── index.html
│       └── assets/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              # Working Grade, Results, Settings, Analytics tabs
│       ├── styles/globals.css
│       ├── components/Icon.jsx
│       ├── hooks/useConfig.js
│       └── services/api.js
│
├── graider_app.py               # Original (can be removed after testing)
├── assignment_grader.py         # Grading logic
├── email_sender.py              # Email sending
├── requirements.txt
├── venv/                        # Python virtual environment
└── .env
```

---

## Next Steps: Phase 3

Ready to extract React components into separate files for better maintainability:
- GradeTab, ResultsTab, SettingsTab, AnalyticsTab
- Full Builder tab implementation (currently placeholder)
- Full Planner tab implementation (currently placeholder)
