# Assets Tab + Auto-Save Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Assets tab to the Planner that shows all generated content (assessments, assignments, lesson plans), auto-save every generated resource, and allow teachers to browse, manage, and republish past content.

**Architecture:** Auto-save generated content to Supabase on creation. New "Assets" tab in PlannerTab.jsx lists all saved resources with filter/search. Teachers can view, edit, republish, delete, and export from the Assets view. Uses existing storage patterns (teacher_id-scoped).

**Tech Stack:** Python/Flask, React, Supabase

**Spec:** `docs/superpowers/specs/2026-03-20-content-types-accommodations-assets-design.md`

---

## Current State

### How content is generated (3 paths)
1. **Lesson plan** — `PlannerTab.jsx:1166` sets `setLessonPlan(data.plan || data)` after `api.generateLessonPlan()` returns
2. **Assessment** — `PlannerTab.jsx:1400` sets `setGeneratedAssessment(data.assessment)` after `api.generateAssessment()` returns
3. **Assignment from lesson** — `PlannerTab.jsx:1800` sets `setGeneratedAssignment(data.assignment)` after `api.generateAssignmentFromLesson()` returns

### How content is currently saved
- **Assessments**: Manual save via `saveAssessmentHandler` (PlannerTab.jsx:1579) calls `api.saveAssessmentLocally()` which POSTs to `/api/save-assessment` in `student_portal_routes.py:110`. Saves to `~/.graider_saved_assessments/` as JSON files. No Supabase, no `storage.py` integration.
- **Lessons**: Manual save via `api.saveLessonPlan()` which POSTs to `/api/save-lesson` in `lesson_routes.py:47`. Uses `storage.py` pattern (dual-writes to local + Supabase). Key format: `lesson:{unit}:{title}`.
- **Assignments from lessons**: **No save endpoint exists.** Generated assignments live only in React state and are lost on navigation.

### Storage layer (`backend/storage.py`)
Uses a `teacher_data` Supabase table with `teacher_id` + `data_key` as composite key. Public API: `load()`, `save()`, `delete()`, `list_keys()`. Key patterns include `assignment:{title}`, `lesson:{unit}:{title}`, etc. Adding a new `resource:{id}` key pattern is straightforward.

### Planner tab bar (`PlannerTab.jsx:2064-2189`)
5 horizontal buttons: "Lesson Planning" (`lesson`), "Assessment Generator" (`assessment`), "Student Portal" (`dashboard`), "Calendar" (`calendar`), "Tools" (`tools`). State: `plannerMode` (line 815). Adding a 6th tab for "Assets" follows the exact same pattern.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/storage.py` | Modify | Add `resource:{id}` key mapping in `_key_to_filepath`, add `RESOURCES_DIR` |
| `backend/routes/lesson_routes.py` | Modify | Add `/api/save-resource`, `/api/list-resources`, `/api/load-resource`, `/api/delete-resource` endpoints |
| `frontend/src/services/api.js` | Modify | Add `saveResource()`, `listResources()`, `loadResource()`, `deleteResource()` API functions |
| `frontend/src/tabs/PlannerTab.jsx` | Modify | Add auto-save calls after generation, add "Assets" tab button + Assets view, add republish flow |
| `tests/test_assets.py` | Create | Tests for resource save/load/list/delete via storage |

---

### Task 1: Add `resource:` key support to storage.py and create backend endpoints

**Files:**
- Modify: `backend/storage.py` (add `resource:{id}` key mapping)
- Modify: `backend/routes/lesson_routes.py` (add 4 new endpoints)
- Create: `tests/test_assets.py`

The storage layer needs a new key pattern `resource:{id}` that maps to `~/.graider_data/resources/{id}.json` for local-dev, and uses the existing `teacher_data` Supabase table for production. The endpoints go in `lesson_routes.py` because it already imports and uses the storage abstraction layer.

- [ ] **Step 1: Write failing tests for resource storage**

Create `tests/test_assets.py`:

```python
"""Tests for the Assets / resource storage feature."""
import json
import pytest
import os
from unittest.mock import patch


class TestResourceStorage:
    """Test the resource: key pattern in storage.py."""

    def test_resource_key_maps_to_filepath(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('resource:abc-123')
        assert path is not None
        assert 'resources' in path
        assert 'abc-123.json' in path

    def test_resource_save_and_load_local(self):
        from backend.storage import save, load, delete
        test_data = {"title": "Test Assessment", "type": "assessment"}
        assert save('resource:test-asset-1', test_data, 'local-dev')
        loaded = load('resource:test-asset-1', 'local-dev')
        assert loaded is not None
        assert loaded['title'] == "Test Assessment"
        # Cleanup
        delete('resource:test-asset-1', 'local-dev')

    def test_resource_list_keys(self):
        from backend.storage import save, list_keys, delete
        save('resource:list-test-1', {"title": "A"}, 'local-dev')
        save('resource:list-test-2', {"title": "B"}, 'local-dev')
        keys = list_keys('resource:', 'local-dev')
        assert 'resource:list-test-1' in keys
        assert 'resource:list-test-2' in keys
        # Cleanup
        delete('resource:list-test-1', 'local-dev')
        delete('resource:list-test-2', 'local-dev')

    def test_resource_delete(self):
        from backend.storage import save, load, delete
        save('resource:del-test', {"title": "Delete Me"}, 'local-dev')
        assert delete('resource:del-test', 'local-dev')
        assert load('resource:del-test', 'local-dev') is None
```

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assets.py -x`
Expected: All 4 tests fail because `_key_to_filepath('resource:...')` returns `None`.

- [ ] **Step 2: Add `resource:{id}` key mapping to storage.py**

**File:** `backend/storage.py`

Add `RESOURCES_DIR` constant after line 37:

```python
RESOURCES_DIR = os.path.join(GRAIDER_DATA_DIR, "resources")
```

In `_key_to_filepath()`, add a new `elif` branch before the final `return None` at line 97. Insert after the `lesson:` handler (line 90-96):

```python
    elif data_key.startswith('resource:'):
        resource_id = data_key[len('resource:'):]
        return os.path.join(RESOURCES_DIR, f"{resource_id}.json")
```

In `_file_list_keys()`, add a new `elif` branch after the `period_meta:` handler (before line 199 `return sorted(keys)`):

```python
    elif prefix == 'resource:' or prefix.startswith('resource:'):
        if os.path.exists(RESOURCES_DIR):
            for f in os.listdir(RESOURCES_DIR):
                if f.endswith('.json'):
                    resource_id = f[:-5]  # Strip .json
                    keys.append(f"resource:{resource_id}")
```

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assets.py -x`
Expected: All 4 tests pass.

- [ ] **Step 3: Add resource CRUD endpoints to lesson_routes.py**

**File:** `backend/routes/lesson_routes.py`

Add these 4 endpoints at the end of the file (after the last existing route). They follow the exact same pattern as the existing `save_lesson` / `list_lessons` / `load_lesson` / `delete_lesson` endpoints already in this file.

```python
# ============ Resources (Assets) ============

@lesson_bp.route('/api/save-resource', methods=['POST'])
def save_resource():
    """Save a generated resource (assessment, assignment, lesson) for the Assets library."""
    data = request.json
    teacher_id = getattr(g, 'user_id', 'local-dev')

    content = data.get('content')
    content_type = data.get('content_type', 'assessment')  # assessment, assignment, lesson
    title = data.get('title', 'Untitled')
    resource_id = data.get('resource_id')

    if not content:
        return jsonify({"error": "No content provided"}), 400

    # Generate an ID if not provided (for auto-save on first creation)
    if not resource_id:
        import uuid
        resource_id = str(uuid.uuid4())[:8]

    # Build resource envelope
    resource = {
        "id": resource_id,
        "title": title,
        "content_type": content_type,
        "content": content,
        "created_at": data.get('created_at', datetime.now().isoformat()),
        "updated_at": datetime.now().isoformat(),
    }

    if storage_save:
        storage_save(f'resource:{resource_id}', resource, teacher_id)
    else:
        return jsonify({"error": "Storage not available"}), 500

    return jsonify({"success": True, "resource_id": resource_id})


@lesson_bp.route('/api/list-resources', methods=['GET'])
def list_resources():
    """List all saved resources for the teacher."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    content_type_filter = request.args.get('type')  # optional filter

    resources = []
    if storage_list_keys and storage_load:
        keys = storage_list_keys('resource:', teacher_id)
        for key in keys:
            data = storage_load(key, teacher_id)
            if data is None:
                continue
            # Apply type filter if specified
            if content_type_filter and data.get('content_type') != content_type_filter:
                continue
            resources.append({
                "id": data.get('id', key.split(':', 1)[1]),
                "title": data.get('title', 'Untitled'),
                "content_type": data.get('content_type', 'unknown'),
                "created_at": data.get('created_at', ''),
                "updated_at": data.get('updated_at', ''),
            })

    # Sort by updated_at descending (newest first)
    resources.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return jsonify({"resources": resources})


@lesson_bp.route('/api/load-resource', methods=['POST'])
def load_resource():
    """Load a saved resource by ID."""
    data = request.json
    resource_id = data.get('resource_id')
    teacher_id = getattr(g, 'user_id', 'local-dev')

    if not resource_id:
        return jsonify({"error": "No resource_id provided"}), 400

    if storage_load:
        resource = storage_load(f'resource:{resource_id}', teacher_id)
        if resource:
            return jsonify({"success": True, "resource": resource})
        return jsonify({"error": "Resource not found"}), 404

    return jsonify({"error": "Storage not available"}), 500


@lesson_bp.route('/api/delete-resource', methods=['POST'])
def delete_resource():
    """Delete a saved resource by ID."""
    data = request.json
    resource_id = data.get('resource_id')
    teacher_id = getattr(g, 'user_id', 'local-dev')

    if not resource_id:
        return jsonify({"error": "No resource_id provided"}), 400

    if storage_delete:
        storage_delete(f'resource:{resource_id}', teacher_id)
        return jsonify({"success": True})

    return jsonify({"error": "Storage not available"}), 500
```

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assets.py -x`
Expected: Still passes (endpoint tests are integration-level; the storage tests validate the core logic).

- [ ] **Step 4: Add endpoint tests**

Append to `tests/test_assets.py`:

```python
class TestResourceEndpoints:
    """Test the /api/*-resource endpoints via Flask test client."""

    @pytest.fixture
    def client(self):
        """Create a test client. Uses local-dev (no auth required)."""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_save_and_list(self, client):
        # Save a resource
        resp = client.post('/api/save-resource', json={
            'title': 'Test Quiz',
            'content_type': 'assessment',
            'content': {'sections': [], 'total_points': 100},
        })
        data = resp.get_json()
        assert data.get('success') is True
        resource_id = data.get('resource_id')
        assert resource_id

        # List resources
        resp = client.get('/api/list-resources')
        data = resp.get_json()
        ids = [r['id'] for r in data.get('resources', [])]
        assert resource_id in ids

        # Cleanup
        client.post('/api/delete-resource', json={'resource_id': resource_id})

    def test_load_resource(self, client):
        resp = client.post('/api/save-resource', json={
            'title': 'Load Test',
            'content_type': 'assignment',
            'content': {'sections': [{'name': 'Part 1'}]},
        })
        resource_id = resp.get_json().get('resource_id')

        resp = client.post('/api/load-resource', json={'resource_id': resource_id})
        data = resp.get_json()
        assert data.get('success') is True
        assert data['resource']['title'] == 'Load Test'
        assert data['resource']['content']['sections'][0]['name'] == 'Part 1'

        # Cleanup
        client.post('/api/delete-resource', json={'resource_id': resource_id})

    def test_delete_resource(self, client):
        resp = client.post('/api/save-resource', json={
            'title': 'Delete Me',
            'content_type': 'lesson',
            'content': {'days': []},
        })
        resource_id = resp.get_json().get('resource_id')

        resp = client.post('/api/delete-resource', json={'resource_id': resource_id})
        assert resp.get_json().get('success') is True

        # Verify deleted
        resp = client.post('/api/load-resource', json={'resource_id': resource_id})
        assert resp.status_code == 404

    def test_filter_by_type(self, client):
        # Save assessment and assignment
        r1 = client.post('/api/save-resource', json={
            'title': 'Quiz', 'content_type': 'assessment', 'content': {},
        }).get_json().get('resource_id')
        r2 = client.post('/api/save-resource', json={
            'title': 'HW', 'content_type': 'assignment', 'content': {},
        }).get_json().get('resource_id')

        # Filter by assessment
        resp = client.get('/api/list-resources?type=assessment')
        types = [r['content_type'] for r in resp.get_json().get('resources', [])]
        assert 'assignment' not in types

        # Cleanup
        client.post('/api/delete-resource', json={'resource_id': r1})
        client.post('/api/delete-resource', json={'resource_id': r2})
```

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assets.py -x -v`
Expected: All tests pass (storage + endpoint tests).

---

### Task 2: Add API client functions and auto-save on generation

**Files:**
- Modify: `frontend/src/services/api.js` (add 4 functions)
- Modify: `frontend/src/tabs/PlannerTab.jsx` (add auto-save calls after each generation path)

- [ ] **Step 1: Add API client functions**

**File:** `frontend/src/services/api.js`

Add after the existing "Saved Assessments" section (after line 778, the `deleteSavedAssessment` function):

```javascript
// ============ Resources (Assets Library) ============

export async function saveResource(content, contentType, title, resourceId) {
  return fetchApi('/api/save-resource', {
    method: 'POST',
    body: JSON.stringify({
      content,
      content_type: contentType,
      title: title || 'Untitled',
      resource_id: resourceId || undefined,
    }),
  })
}

export async function listResources(type) {
  const params = type ? '?type=' + encodeURIComponent(type) : '';
  return fetchApi('/api/list-resources' + params)
}

export async function loadResource(resourceId) {
  return fetchApi('/api/load-resource', {
    method: 'POST',
    body: JSON.stringify({ resource_id: resourceId }),
  })
}

export async function deleteResource(resourceId) {
  return fetchApi('/api/delete-resource', {
    method: 'POST',
    body: JSON.stringify({ resource_id: resourceId }),
  })
}
```

Also add these 4 functions to the default export object at the bottom of the file (around line 1336+):

```javascript
  // Resources (Assets)
  saveResource,
  listResources,
  loadResource,
  deleteResource,
```

- [ ] **Step 2: Add auto-save helper function to PlannerTab.jsx**

**File:** `frontend/src/tabs/PlannerTab.jsx`

Add a helper function after the existing `fetchSavedAssessments` function (after line 1632). This is a fire-and-forget save that runs silently in the background.

```javascript
  // Auto-save a generated resource to the Assets library (silent, no toast)
  const autoSaveResource = async (content, contentType) => {
    try {
      const title = content.title || content.name || 'Untitled';
      await api.saveResource(content, contentType, title);
    } catch (e) {
      console.warn('Auto-save failed:', e.message);
    }
  };
```

- [ ] **Step 3: Hook auto-save into lesson plan generation**

**File:** `frontend/src/tabs/PlannerTab.jsx`

At line 1166, after `setLessonPlan(data.plan || data);`, add the auto-save call:

Find this block (lines 1165-1167):
```javascript
      } else {
        setLessonPlan(data.plan || data);
      }
```

Replace with:
```javascript
      } else {
        setLessonPlan(data.plan || data);
        autoSaveResource(data.plan || data, 'lesson');
      }
```

Also handle lesson variations — when a teacher selects a variation (line 2814), it becomes the active lesson. Find this block (lines 2814-2816):
```javascript
                                      setLessonPlan(variation);
                                      setLessonVariations([]);
```

Replace with:
```javascript
                                      setLessonPlan(variation);
                                      setLessonVariations([]);
                                      autoSaveResource(variation, 'lesson');
```

- [ ] **Step 4: Hook auto-save into assessment generation**

**File:** `frontend/src/tabs/PlannerTab.jsx`

At line 1400, after `setGeneratedAssessment(data.assessment);`, add auto-save.

Find this block (lines 1400-1402):
```javascript
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({}); // Clear previous answers
        addToast("Assessment generated successfully!", "success");
```

Replace with:
```javascript
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({}); // Clear previous answers
        autoSaveResource(data.assessment, 'assessment');
        addToast("Assessment generated successfully!", "success");
```

- [ ] **Step 5: Hook auto-save into assignment-from-lesson generation**

**File:** `frontend/src/tabs/PlannerTab.jsx`

At line 1800, after `setGeneratedAssignment(data.assignment);`, add auto-save.

Find this block (lines 1800-1805):
```javascript
        setGeneratedAssignment(data.assignment);
        addToast(
          `${assignmentType.charAt(0).toUpperCase() + assignmentType.slice(1)} generated from lesson!`,
          "success",
        );
```

Replace with:
```javascript
        setGeneratedAssignment(data.assignment);
        autoSaveResource(data.assignment, 'assignment');
        addToast(
          `${assignmentType.charAt(0).toUpperCase() + assignmentType.slice(1)} generated from lesson!`,
          "success",
        );
```

Verify: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds with no errors.

---

### Task 3: Add Assets tab to the Planner

**Files:**
- Modify: `frontend/src/tabs/PlannerTab.jsx` (add tab button, state, Assets view)

This task adds the 6th tab button and the Assets list view. The view shows all saved resources with type badge, date, and action buttons.

- [ ] **Step 1: Add Assets state variables**

**File:** `frontend/src/tabs/PlannerTab.jsx`

After the existing `savedAssessments` state declarations (around line 812), add:

```javascript
  const [assets, setAssets] = useState([]);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetsFilter, setAssetsFilter] = useState('all'); // 'all', 'assessment', 'assignment', 'lesson'
  const [assetsSearch, setAssetsSearch] = useState('');
```

Add a fetch function after the `autoSaveResource` helper (from Task 2 Step 2):

```javascript
  // Fetch all resources for the Assets tab
  const fetchAssets = async () => {
    setAssetsLoading(true);
    try {
      const typeParam = assetsFilter === 'all' ? undefined : assetsFilter;
      const data = await api.listResources(typeParam);
      if (data.resources) {
        setAssets(data.resources);
      }
    } catch (e) {
      console.error('Error loading assets:', e);
    } finally {
      setAssetsLoading(false);
    }
  };

  // Delete a resource from Assets
  const deleteAsset = async (resourceId) => {
    if (!confirm('Delete this resource? This cannot be undone.')) return;
    try {
      await api.deleteResource(resourceId);
      addToast('Resource deleted', 'success');
      fetchAssets();
    } catch (e) {
      addToast('Error deleting resource: ' + e.message, 'error');
    }
  };

  // Load a resource from Assets into the active editor
  const loadAsset = async (resourceId, contentType) => {
    try {
      const data = await api.loadResource(resourceId);
      if (data.error) {
        addToast('Error loading resource: ' + data.error, 'error');
        return;
      }
      const content = data.resource.content;
      if (contentType === 'assessment') {
        setGeneratedAssessment(content);
        setAssessmentAnswers({});
        setPlannerMode('assessment');
        addToast('Assessment loaded into editor', 'success');
      } else if (contentType === 'assignment') {
        setGeneratedAssignment(content);
        setPlannerMode('lesson');
        addToast('Assignment loaded into editor', 'success');
      } else if (contentType === 'lesson') {
        setLessonPlan(content);
        setPlannerMode('lesson');
        addToast('Lesson plan loaded into editor', 'success');
      }
    } catch (e) {
      addToast('Error loading resource: ' + e.message, 'error');
    }
  };
```

- [ ] **Step 2: Add Assets tab button**

**File:** `frontend/src/tabs/PlannerTab.jsx`

After the "Tools" button (line 2188-2189, closing `</button>`), add the Assets tab button. Insert before the closing `</div>` of the tab bar (line 2190):

```jsx
                    <button
                      onClick={() => {
                        setPlannerMode("assets");
                        fetchAssets();
                      }}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "assets"
                            ? "linear-gradient(135deg, #e879f9, #c084fc)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "assets"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "assets" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="FolderOpen" size={18} />
                      Assets
                    </button>
```

Also update the `plannerMode` state comment at line 815 to include `"assets"`:

Find:
```javascript
  const [plannerMode, setPlannerMode] = useState("lesson"); // "lesson", "assessment", "dashboard", or "calendar"
```
Replace:
```javascript
  const [plannerMode, setPlannerMode] = useState("lesson"); // "lesson", "assessment", "dashboard", "calendar", "tools", or "assets"
```

- [ ] **Step 3: Add Assets view rendering**

**File:** `frontend/src/tabs/PlannerTab.jsx`

Find the last `plannerMode` conditional rendering block. The "Tools" mode block starts with `{plannerMode === "tools" && (`. After that entire block's closing `)}`, add the Assets view. This will be before the final closing tags of the component.

Search for the pattern to find the right insertion point: look for the closing of the tools mode block, which will be a `)}` followed by the closing of the outer container divs.

Add the Assets view block:

```jsx
                  {plannerMode === "assets" && (
                    <div style={{ padding: "0" }}>
                      {/* Filter bar */}
                      <div style={{
                        display: "flex",
                        gap: "10px",
                        marginBottom: "20px",
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}>
                        <input
                          type="text"
                          placeholder="Search by title..."
                          value={assetsSearch}
                          onChange={(e) => setAssetsSearch(e.target.value)}
                          style={{
                            padding: "8px 14px",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                            background: "var(--glass-bg)",
                            color: "var(--text-primary)",
                            flex: "1",
                            minWidth: "200px",
                          }}
                        />
                        {['all', 'assessment', 'assignment', 'lesson'].map(filterType => (
                          <button
                            key={filterType}
                            onClick={() => { setAssetsFilter(filterType); }}
                            style={{
                              padding: "6px 14px",
                              borderRadius: "8px",
                              border: assetsFilter === filterType ? "none" : "1px solid var(--glass-border)",
                              background: assetsFilter === filterType
                                ? "linear-gradient(135deg, #e879f9, #c084fc)"
                                : "var(--glass-bg)",
                              color: assetsFilter === filterType ? "#fff" : "var(--text-secondary)",
                              cursor: "pointer",
                              fontSize: "0.85rem",
                              fontWeight: 600,
                            }}
                          >
                            {filterType === 'all' ? 'All' : filterType.charAt(0).toUpperCase() + filterType.slice(1) + 's'}
                          </button>
                        ))}
                        <button
                          onClick={fetchAssets}
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px" }}
                        >
                          <Icon name="RefreshCw" size={16} />
                        </button>
                      </div>

                      {/* Assets list */}
                      {assetsLoading ? (
                        <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                          Loading assets...
                        </div>
                      ) : assets.filter(a => {
                        if (!assetsSearch.trim()) return true;
                        return (a.title || '').toLowerCase().includes(assetsSearch.toLowerCase());
                      }).length === 0 ? (
                        <div style={{
                          textAlign: "center",
                          padding: "60px 20px",
                          color: "var(--text-muted)",
                        }}>
                          <Icon name="FolderOpen" size={48} />
                          <p style={{ marginTop: "15px", fontSize: "1.1rem" }}>
                            {assets.length === 0
                              ? "No assets yet. Generated assessments, assignments, and lesson plans will appear here automatically."
                              : "No assets match your search."}
                          </p>
                        </div>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                          {assets
                            .filter(a => {
                              if (!assetsSearch.trim()) return true;
                              return (a.title || '').toLowerCase().includes(assetsSearch.toLowerCase());
                            })
                            .map(asset => {
                              const typeBadgeColors = {
                                assessment: { bg: "rgba(139,92,246,0.2)", text: "#a78bfa" },
                                assignment: { bg: "rgba(59,130,246,0.2)", text: "#60a5fa" },
                                lesson: { bg: "rgba(34,197,94,0.2)", text: "#4ade80" },
                              };
                              const badge = typeBadgeColors[asset.content_type] || { bg: "rgba(156,163,175,0.2)", text: "#9ca3af" };
                              const dateStr = asset.updated_at
                                ? new Date(asset.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                                : '';

                              return (
                                <div
                                  key={asset.id}
                                  style={{
                                    background: "var(--glass-bg)",
                                    border: "1px solid var(--glass-border)",
                                    borderRadius: "12px",
                                    padding: "15px 20px",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "15px",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <div style={{ flex: 1 }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                                      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{asset.title}</span>
                                      <span style={{
                                        padding: "2px 8px",
                                        borderRadius: "6px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        background: badge.bg,
                                        color: badge.text,
                                      }}>
                                        {asset.content_type}
                                      </span>
                                    </div>
                                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{dateStr}</span>
                                  </div>
                                  <div style={{ display: "flex", gap: "8px" }}>
                                    <button
                                      onClick={() => loadAsset(asset.id, asset.content_type)}
                                      className="btn btn-secondary"
                                      style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                                      title="Load into editor"
                                    >
                                      <Icon name="Edit" size={14} />
                                    </button>
                                    <button
                                      onClick={() => {
                                        loadAsset(asset.id, asset.content_type).then(() => {
                                          // Small delay to ensure content is loaded before opening publish modal
                                          setTimeout(() => publishAssessmentHandler(), 300);
                                        });
                                      }}
                                      className="btn"
                                      style={{
                                        padding: "6px 12px",
                                        fontSize: "0.8rem",
                                        background: "linear-gradient(135deg, #22c55e, #16a34a)",
                                        color: "#fff",
                                        border: "none",
                                      }}
                                      title="Publish to student portal"
                                    >
                                      <Icon name="Send" size={14} />
                                    </button>
                                    <button
                                      onClick={() => deleteAsset(asset.id)}
                                      className="btn btn-secondary"
                                      style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                                      title="Delete"
                                    >
                                      <Icon name="Trash2" size={14} />
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      )}
                    </div>
                  )}
```

- [ ] **Step 4: Refresh assets when filter changes**

**File:** `frontend/src/tabs/PlannerTab.jsx`

Add a `useEffect` near the other effects (around line 940-944 where the calendar effect is). Add after that block:

```javascript
  useEffect(() => {
    if (plannerMode === 'assets') {
      fetchAssets();
    }
  }, [assetsFilter]);
```

Verify: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds.

---

### Task 4: Republish from Assets

**Files:**
- Modify: `frontend/src/tabs/PlannerTab.jsx` (refine the load-then-publish flow)

The publish flow is already wired in Task 3 via `loadAsset` followed by `publishAssessmentHandler`. This task ensures the flow works correctly by making `loadAsset` return a Promise that resolves after state is set, so the publish modal opens with the correct content.

- [ ] **Step 1: Make loadAsset async-safe for publish chaining**

The `loadAsset` function from Task 3 Step 1 already sets the active content via `setGeneratedAssessment`, `setGeneratedAssignment`, or `setLessonPlan`. However, React state updates are asynchronous, so the `publishAssessmentHandler` call in the `setTimeout` (Task 3 Step 3) might fire before state has updated.

Fix: Instead of chaining publish after load on the Assets row, add a dedicated "Publish from Assets" flow. Update the publish button's `onClick` in the Assets list (from Task 3 Step 3).

Replace the publish button `onClick` in the Assets list with:

```javascript
                                    <button
                                      onClick={async () => {
                                        try {
                                          const data = await api.loadResource(asset.id);
                                          if (data.error) {
                                            addToast('Error loading resource: ' + data.error, 'error');
                                            return;
                                          }
                                          const content = data.resource.content;
                                          if (asset.content_type === 'assessment') {
                                            setGeneratedAssessment(content);
                                            setPlannerMode('assessment');
                                          } else if (asset.content_type === 'assignment') {
                                            setGeneratedAssignment(content);
                                            setPlannerMode('lesson');
                                          } else if (asset.content_type === 'lesson') {
                                            setLessonPlan(content);
                                            setPlannerMode('lesson');
                                          }
                                          // Open publish modal directly with the loaded content
                                          setPublishSettings({
                                            period: '',
                                            periodFilename: '',
                                            isMakeup: false,
                                            selectedStudents: [],
                                            timeLimit: content.time_limit || null,
                                            applyAccommodations: true,
                                          });
                                          setPublishModalStudents([]);
                                          setShowPublishModal(true);
                                        } catch (e) {
                                          addToast('Error: ' + e.message, 'error');
                                        }
                                      }}
                                      className="btn"
                                      style={{
                                        padding: "6px 12px",
                                        fontSize: "0.8rem",
                                        background: "linear-gradient(135deg, #22c55e, #16a34a)",
                                        color: "#fff",
                                        border: "none",
                                      }}
                                      title="Publish to student portal"
                                    >
                                      <Icon name="Send" size={14} />
                                    </button>
```

This eliminates the `setTimeout` race condition by loading the content, setting state, and opening the publish modal in one synchronous sequence (React will batch the state updates and render once).

- [ ] **Step 2: Add export buttons to Assets rows**

For DOCX export from Assets, add an export button next to the publish button in the Assets list row. Insert after the publish button, before the delete button:

```jsx
                                    <button
                                      onClick={async () => {
                                        try {
                                          const data = await api.loadResource(asset.id);
                                          if (data.error) { addToast('Error: ' + data.error, 'error'); return; }
                                          const content = data.resource.content;
                                          if (asset.content_type === 'assessment') {
                                            const exportData = await api.exportAssessment(content, false);
                                            if (exportData.error) addToast('Export error: ' + exportData.error, 'error');
                                            else addToast('Assessment exported!', 'success');
                                          } else if (asset.content_type === 'lesson') {
                                            const exportData = await api.exportLessonPlan(content);
                                            if (exportData.error) addToast('Export error: ' + exportData.error, 'error');
                                            else addToast('Lesson plan exported!', 'success');
                                          } else {
                                            addToast('Export not available for this content type', 'info');
                                          }
                                        } catch (e) {
                                          addToast('Export error: ' + e.message, 'error');
                                        }
                                      }}
                                      className="btn btn-secondary"
                                      style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                                      title="Export DOCX"
                                    >
                                      <Icon name="Download" size={14} />
                                    </button>
```

Verify: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds.

---

### Task 5: Build, test, verify

- [ ] **Step 1: Run backend tests**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assets.py -x -v
```

Expected: All tests pass (storage key mapping, CRUD endpoints, filter).

- [ ] **Step 2: Build frontend**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```

Expected: Build succeeds with no errors. Output goes to `backend/static/`.

- [ ] **Step 3: Start the app and verify manually**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python backend/app.py
```

Verify in browser:
1. Navigate to the Planner tab
2. Confirm 6 horizontal tabs appear: Lesson Planning, Assessment Generator, Student Portal, Calendar, Tools, **Assets**
3. Click Assets tab — should show empty state message: "No assets yet..."
4. Go to Assessment Generator, generate an assessment
5. After generation completes, go back to Assets tab — the assessment should appear in the list
6. Click the Edit (pencil) button — should load the assessment back into the Assessment Generator view
7. Click the Publish (send) button — should open the publish modal with the assessment pre-loaded
8. Click the Export (download) button — should trigger DOCX export
9. Click the Delete (trash) button — should remove the asset after confirmation
10. Go to Lesson Planning, generate a lesson plan — verify it appears in Assets
11. Generate an assignment from the lesson plan — verify it appears in Assets
12. Test the type filter buttons (All, Assessments, Assignments, Lessons)
13. Test the search box — type part of a title and verify filtering works

- [ ] **Step 4: Verify no regressions**

1. Existing manual save ("Save Assessment" in Student Portal tab) still works
2. Existing lesson save flow still works
3. Publish flow from Assessment Generator still works (unchanged)
4. All other Planner tabs render correctly

---

## Summary of Changes

| Area | What changes |
|------|-------------|
| `backend/storage.py` | New `RESOURCES_DIR`, `resource:{id}` key mapping in `_key_to_filepath` and `_file_list_keys` |
| `backend/routes/lesson_routes.py` | 4 new endpoints: save-resource, list-resources, load-resource, delete-resource |
| `frontend/src/services/api.js` | 4 new functions: saveResource, listResources, loadResource, deleteResource |
| `frontend/src/tabs/PlannerTab.jsx` | Auto-save calls at 3 generation points, Assets tab button, Assets view with list/filter/search/actions, republish flow |
| `tests/test_assets.py` | Storage + endpoint tests |

**What is NOT changed:**
- No new Supabase tables needed (uses existing `teacher_data` table via storage.py)
- No changes to the grading pipeline
- No changes to existing save/publish flows (they continue to work as before)
- No changes to `backend/app.py`
