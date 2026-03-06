# Codebase Quality Improvements Plan

## Context

GitNexus MCP analysis of the Graider codebase identified 5 structural issues: duplicate Supabase client implementations, unprotected grading thread writes, legacy checkpoint files in the repo, oversized `assistant_tools.py`, and a monolithic 27K-line `App.jsx`. This plan addresses all five, ordered by risk (lowest first).

---

## Step 1: Gitignore Checkpoint Files (trivial)

**Problem:** `graider_app_checkpoint_1769361776.py` (legacy backup) sits in the project root, untracked but not gitignored. Could accidentally be committed.

**Changes:**
- `.gitignore`: Add `*_checkpoint_*.py` under the `GRAIDER SPECIFIC` section (line ~210)
- Delete `graider_app_checkpoint_1769361776.py` from disk

---

## Step 2: Consolidate `_get_supabase()` (low risk)

**Problem:** 6 duplicate lazy-init Supabase client implementations across 6 files, all doing the same thing with minor variations.

| File | Function name | Error handling | Call sites |
|---|---|---|---|
| `backend/storage.py:27` | `_get_supabase()` | Lenient (returns None) | 6 |
| `backend/auth.py:14` | `_get_supabase()` | Lenient (returns None) | 1 |
| `backend/routes/auth_routes.py:20` | `_get_supabase()` | Strict (raises Exception) | 3 |
| `backend/routes/stripe_routes.py:16` | `_get_supabase()` | Strict (raises Exception) | 3 |
| `backend/routes/student_account_routes.py:36` | `_get_supabase()` | Strict (type-hinted, raises) | 15 |
| `backend/routes/student_portal_routes.py:22` | `get_supabase()` | Strict (raises Exception) | many |

**Approach:** Create `backend/supabase_client.py` with a single canonical implementation. Provide both lenient and strict variants:

```python
# backend/supabase_client.py
_supabase = None

def get_supabase():
    """Returns Supabase client or None if not configured."""
    global _supabase
    if _supabase is None:
        from supabase import create_client
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase = create_client(url, key)
    return _supabase

def get_supabase_or_raise():
    """Returns Supabase client. Raises if not configured."""
    client = get_supabase()
    if client is None:
        raise Exception("Supabase credentials not configured. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    return client
```

**File-by-file changes:**
- `backend/supabase_client.py` — **NEW**, canonical client with lazy init
- `backend/storage.py` — Delete local `_get_supabase()` (lines 24-36), add `from backend.supabase_client import get_supabase as _get_supabase`
- `backend/auth.py` — Delete local `_get_supabase()` (lines 13-22), add `from backend.supabase_client import get_supabase as _get_supabase`
- `backend/routes/auth_routes.py` — Delete local `_get_supabase()` (lines 19-27), add `from backend.supabase_client import get_supabase_or_raise as _get_supabase`
- `backend/routes/stripe_routes.py` — Delete local `_get_supabase()` (lines 15-23), add `from backend.supabase_client import get_supabase_or_raise as _get_supabase`
- `backend/routes/student_account_routes.py` — Delete local `_get_supabase()` (lines 35-45), add `from backend.supabase_client import get_supabase_or_raise as _get_supabase`
- `backend/routes/student_portal_routes.py` — Delete local `get_supabase()` (lines 21-31) and global `supabase = None`, add `from backend.supabase_client import get_supabase_or_raise as get_supabase`

**Note:** Using `import ... as _get_supabase` preserves existing call sites — no need to rename 30+ callers.

---

## Step 3: Add Threading Lock to Grading Thread (medium risk)

**Problem:** `grading_lock = threading.Lock()` exists at `backend/app.py:282` and is used by route handlers in `backend/routes/grading_routes.py` for reading `grading_state`. However, `run_grading_thread()` (`app.py` lines 360-1867) writes to `grading_state` 50+ times without ever acquiring the lock. ThreadPoolExecutor workers (3 concurrent) also append results without synchronization.

**Race conditions:**
- Route reads `grading_state["results"]` via `/api/status` while a worker appends a new result → potential partial read
- Route reads `grading_state["is_running"]` while thread sets it to False → minor but inconsistent
- `grading_state["graded_count"] += 1` from multiple workers → lost updates

**Approach:** Wrap critical mutations with the existing lock. NOT every write — just the ones that race with route reads:

### What to protect (wrap with `with grading_lock:`)
- **State transitions**: `is_running = True/False`, `complete = True`, `stop_requested` checks
- **Results mutations**: `results.append(result)`, `results = sorted_results`
- **Counter updates**: `total = N`, `graded_count += 1`

### What to leave unlocked
- **Log appends**: `grading_state["log"].append(msg)` — list.append is GIL-atomic on CPython, log is read-only via snapshot in routes, and wrapping 50+ log calls would add noise with no safety benefit

### Implementation

Create a helper at module scope in `app.py`:

```python
def _update_grading_state(**kwargs):
    """Thread-safe grading_state update."""
    with grading_lock:
        grading_state.update(kwargs)
```

**Key mutation sites to protect in `run_grading_thread()`:**

| Line(s) | Mutation | Protection |
|---|---|---|
| ~370 | `grading_state["is_running"] = True` | `_update_grading_state(is_running=True)` |
| ~975 | `grading_state["total"] = len(new_files)` | `_update_grading_state(total=len(new_files))` |
| ~982 | `is_running=False, complete=True` | `_update_grading_state(is_running=False, complete=True)` |
| ThreadPoolExecutor callback | `results.append(result)` | `with grading_lock: grading_state["results"].append(result)` |
| ThreadPoolExecutor callback | `graded_count += 1` | `with grading_lock: grading_state["graded_count"] = grading_state.get("graded_count", 0) + 1` |
| ~1860 | `is_running=False, complete=True` | `_update_grading_state(is_running=False, complete=True)` |
| Final sort | `results = sorted_results` | `with grading_lock: grading_state["results"] = sorted_results` |

**Files changed:**
- `backend/app.py` — Add `_update_grading_state()` helper, wrap ~10-15 critical mutations

---

## Step 4: Split `assistant_tools.py` (medium risk)

**Problem:** `backend/services/assistant_tools/__init__.py` is 4,382 lines with 66 functions. 8 submodules have already been extracted using a proven lazy-loading pattern (`_merge_submodules()`).

**Existing submodules (proven pattern):**
- `edtech_tools`, `analytics_tools`, `planning_tools`, `communication_tools`
- `student_tools`, `ai_tools`, `stem_tools`, `automation_tools`

**Proposed new submodules** (grouping remaining functions by domain):

### `data_tools.py` (~400 lines) — Data load/save helpers
Functions to move:
- `_load_results()`, `_load_settings()`, `_load_roster()`
- `_load_master_csv()`, `_load_saved_assignments()`
- `_load_accommodations()`, `_load_parent_contacts()`
- `_load_memories()`, `_save_memories()`
- `_load_calendar()`, `_save_calendar()`

### `grading_tools.py` (~500 lines) — Grade manipulation
Functions to move:
- `_regrade_student()`, `_update_grade()`, `_get_grading_status()`
- `_run_batch_regrade()`
- Related tool definitions in `get_tools()` / `get_handlers()`

### `report_tools.py` (~300 lines) — Reports and exports
Functions to move:
- `_generate_report()`, `_export_data()`, `_build_summary()`
- Related tool definitions

**Pattern to follow** (from existing submodules like `edtech_tools.py`):
```python
# Each new submodule exports:
def get_tools():
    """Return list of tool definitions."""
    return [...]

def get_handlers():
    """Return dict of tool_name -> handler function."""
    return {"tool_name": handler_fn, ...}
```

**Files changed:**
- `backend/services/assistant_tools/data_tools.py` — **NEW**
- `backend/services/assistant_tools/grading_tools.py` — **NEW**
- `backend/services/assistant_tools/report_tools.py` — **NEW**
- `backend/services/assistant_tools/__init__.py` — Add 3 new submodules to `_merge_submodules()`, remove moved functions

---

## Step 5: Extract App.jsx Tab Panels (high risk, incremental)

**Problem:** `frontend/src/App.jsx` is 27,385 lines. Contains 9 tab panels with inline render logic. 42+ smaller components already extracted to separate files.

**Approach:** Extract the 3 largest tab render blocks into separate component files. Pass state as props + callbacks for mutations. Each extraction is a self-contained step tested independently.

### Priority order (by estimated size, largest first):

| Tab | Estimated lines | New file |
|---|---|---|
| Builder (Tab 3) | ~4,000 | `frontend/src/tabs/BuilderTab.jsx` |
| Results (Tab 2) | ~3,500 | `frontend/src/tabs/ResultsTab.jsx` |
| Settings (Tab 5) | ~3,000 | `frontend/src/tabs/SettingsTab.jsx` |

### Extraction pattern:

```jsx
// frontend/src/tabs/BuilderTab.jsx
export default function BuilderTab({
  assignment, setAssignment,
  importedDoc, setImportedDoc,
  customMarkers, setCustomMarkers,
  // ... other needed state + callbacks
}) {
  // Entire tab 3 render block moves here
  return (
    <div>...</div>
  );
}

// In App.jsx, replace ~4000 lines with:
import BuilderTab from './tabs/BuilderTab';
// ...
{activeTab === 3 && <BuilderTab assignment={assignment} ... />}
```

### Risk mitigation:
- Extract ONE tab at a time, `npm run build` + manual test after each
- Start with BuilderTab (fewest cross-tab state dependencies)
- Keep all `useState` declarations in App.jsx — tabs receive as props
- If a tab uses a callback that modifies state from another tab, keep that callback in App.jsx and pass as prop

**Files changed:**
- `frontend/src/tabs/BuilderTab.jsx` — **NEW** (~4,000 lines)
- `frontend/src/tabs/ResultsTab.jsx` — **NEW** (~3,500 lines)
- `frontend/src/tabs/SettingsTab.jsx` — **NEW** (~3,000 lines)
- `frontend/src/App.jsx` — Replace 3 inline tab blocks with component imports (~10,500 lines removed)

---

## Verification

| Step | Test |
|---|---|
| 1 (gitignore) | `git status` — checkpoint file gone, `.gitignore` updated |
| 2 (supabase) | `python -c "from backend.supabase_client import get_supabase; print('OK')"` — no import errors. Start app, verify login works. |
| 3 (threading) | Start app, grade a test assignment, verify no crashes. Hit `/api/status` during grading — clean JSON response. |
| 4 (tools split) | Start app, open AI assistant, ask it to load grades/calendar/accommodations. All tools respond correctly. |
| 5 (tabs split) | `cd frontend && npm run build` succeeds. Open app, click all 5 tabs — no blank tabs, no missing UI, no console errors. |

## Execution Order

Steps 1-3 can be done in sequence quickly (< 30 min total). Step 4 requires careful function-by-function migration. Step 5 is the riskiest and should be done last, one tab at a time with testing between each.
