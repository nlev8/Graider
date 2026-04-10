# Teacher Shared Resources Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers view and delete shared resources (flashcards, study guides, slide decks) from the Student Portal tab.

**Architecture:** Add 3 backend endpoints to `student_portal_routes.py` (list, delete single, delete bulk). Add frontend state, fetch function, and a "Shared Resources" section in the Student Portal tab of `App.jsx`, after the existing published assessments grid.

**Tech Stack:** Python/Flask (backend), React JSX (frontend), Supabase (`published_content` table)

**Spec:** `docs/superpowers/specs/2026-04-09-teacher-shared-resources-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/student_portal_routes.py` | **Modify** | Add 3 endpoints: list, delete, bulk delete |
| `frontend/src/services/api.js` | **Modify** | Add API helper functions |
| `frontend/src/App.jsx` | **Modify** | Add state, fetch, and UI for shared resources section |

---

### Task 1: Add backend endpoints for shared resources

**Files:**
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add list endpoint**

At the end of `backend/routes/student_portal_routes.py` (after the last function, around line 356), add:

```python
RESOURCE_CONTENT_TYPES = ('study_guide', 'flashcards', 'slide_deck')


@student_portal_bp.route('/api/teacher/shared-resources', methods=['GET'])
@require_teacher
@handle_route_errors
def list_shared_resources():
    """List all shared resources (flashcards, study guides, slide decks) for the teacher."""
    try:
        db = get_supabase()

        result = db.table('published_content').select(
            'id, title, content_type, class_id, created_at, is_active'
        ).eq('teacher_id', g.teacher_id).in_(
            'content_type', list(RESOURCE_CONTENT_TYPES)
        ).order('created_at', desc=True).execute()

        # Fetch class names for display
        class_ids = list(set(r.get('class_id') for r in result.data if r.get('class_id')))
        class_names = {}
        if class_ids:
            classes_result = db.table('classes').select('id, name').in_('id', class_ids).execute()
            class_names = {c['id']: c['name'] for c in classes_result.data}

        resources = [{
            "id": r.get('id'),
            "title": r.get('title'),
            "content_type": r.get('content_type'),
            "class_id": r.get('class_id'),
            "class_name": class_names.get(r.get('class_id'), 'Unknown'),
            "created_at": r.get('created_at'),
            "is_active": r.get('is_active', True),
        } for r in result.data]

        return jsonify({"resources": resources})

    except Exception as e:
        _logger.exception("List shared resources error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_shared_resource(resource_id):
    """Delete a single shared resource."""
    try:
        db = get_supabase()

        # Verify ownership
        check = db.table('published_content').select('id').eq(
            'id', resource_id
        ).eq('teacher_id', g.teacher_id).execute()
        if not check.data:
            return jsonify({"error": "Resource not found"}), 404

        db.table('published_content').delete().eq('id', resource_id).execute()
        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Delete shared resource error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/delete-shared-resources-bulk', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_shared_resources_bulk():
    """Delete all shared resources matching a title for this teacher."""
    try:
        db = get_supabase()
        data = request.json
        title = data.get('title', '').strip()

        if not title:
            return jsonify({"error": "Title is required"}), 400

        result = db.table('published_content').delete().eq(
            'teacher_id', g.teacher_id
        ).eq('title', title).in_(
            'content_type', list(RESOURCE_CONTENT_TYPES)
        ).execute()

        deleted = len(result.data) if result.data else 0
        return jsonify({"success": True, "deleted": deleted})

    except Exception as e:
        _logger.exception("Bulk delete shared resources error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 2: Run backend tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "feat: add teacher shared resources list/delete/bulk-delete endpoints"
```

---

### Task 2: Add API helpers and frontend UI

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add API helper functions**

In `frontend/src/services/api.js`, after the `deletePublishedAssessment` function (around line 720), add:

```javascript
export async function getSharedResources() {
  return fetchApi('/api/teacher/shared-resources')
}

export async function deleteSharedResource(id) {
  return fetchApi('/api/teacher/shared-resource/' + id, {
    method: 'DELETE',
  })
}

export async function deleteSharedResourcesBulk(title) {
  return fetchApi('/api/teacher/delete-shared-resources-bulk', {
    method: 'POST',
    body: JSON.stringify({ title: title }),
  })
}
```

- [ ] **Step 2: Add state variables in App.jsx**

In `frontend/src/App.jsx`, find the existing portal state declarations (around line 2121, near `publishedAssessments`). After `const [loadingResults, setLoadingResults] = useState(false);`, add:

```javascript
  const [sharedResources, setSharedResources] = useState([]);
  const [loadingSharedResources, setLoadingSharedResources] = useState(false);
```

- [ ] **Step 3: Add fetch function in App.jsx**

After the existing `fetchPublishedAssessments` function (around line 4823), add:

```javascript
  const fetchSharedResources = async () => {
    setLoadingSharedResources(true);
    try {
      const data = await api.getSharedResources();
      if (data.resources) {
        setSharedResources(data.resources);
      }
    } catch (e) {
      console.error("Error loading shared resources:", e);
    } finally {
      setLoadingSharedResources(false);
    }
  };
```

- [ ] **Step 4: Call fetchSharedResources alongside fetchPublishedAssessments**

Find where `fetchPublishedAssessments` is called on tab load. Search for the useEffect that triggers it. It's likely called when the portal/results tab activates. Find that call and add `fetchSharedResources();` right after it.

Search for `fetchPublishedAssessments()` calls and add `fetchSharedResources();` after each one.

- [ ] **Step 5: Add delete handlers**

After the `fetchSharedResources` function, add:

```javascript
  const handleDeleteSharedResource = async (id, title) => {
    try {
      var data = await api.deleteSharedResource(id);
      if (data.success) {
        setSharedResources(function(prev) { return prev.filter(function(r) { return r.id !== id; }); });
        addToast('Deleted "' + title + '"', 'success');
      } else {
        addToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      addToast('Failed to delete: ' + e.message, 'error');
    }
  };

  const handleDeleteAllSharedResources = async (title) => {
    try {
      var data = await api.deleteSharedResourcesBulk(title);
      if (data.success) {
        setSharedResources(function(prev) { return prev.filter(function(r) { return r.title !== title; }); });
        addToast('Deleted "' + title + '" from ' + data.deleted + ' class' + (data.deleted === 1 ? '' : 'es'), 'success');
      } else {
        addToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      addToast('Failed to delete: ' + e.message, 'error');
    }
  };
```

- [ ] **Step 6: Add Shared Resources UI section**

In `frontend/src/App.jsx`, find the end of the published assessments/assignments grid. Search for the line:

```javascript
                        {/* Submissions Detail Panel */}
```

BEFORE that line, add:

```jsx
                        {/* Shared Resources Section */}
                        <div className="glass-card" style={{ padding: "20px", marginBottom: "16px", gridColumn: selectedAssessmentResults ? "1" : "1" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="BookOpen" size={20} />
                            Shared Resources
                          </h3>
                          {loadingSharedResources ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Loading...</p>
                          ) : sharedResources.length === 0 ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                              No shared resources yet. Use "Share with Class" on flashcards, study guides, or slide decks to share them with students.
                            </p>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {sharedResources.map(function(res) {
                                var typeIcon = res.content_type === 'flashcards' ? 'Layers'
                                  : res.content_type === 'study_guide' ? 'FileText'
                                  : res.content_type === 'slide_deck' ? 'Monitor'
                                  : 'File';
                                var typeLabel = res.content_type === 'flashcards' ? 'Flashcards'
                                  : res.content_type === 'study_guide' ? 'Study Guide'
                                  : res.content_type === 'slide_deck' ? 'Slide Deck'
                                  : res.content_type;
                                var sameTitle = sharedResources.filter(function(r) { return r.title === res.title; });
                                var isFirst = sameTitle[0] && sameTitle[0].id === res.id;
                                return (
                                  <div key={res.id} style={{
                                    display: "flex", alignItems: "center", gap: "12px",
                                    padding: "10px 14px", borderRadius: "10px",
                                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                  }}>
                                    <Icon name={typeIcon} size={18} style={{ color: "var(--accent-primary)", flexShrink: 0 }} />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: "0.9rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                        {res.title}
                                      </div>
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                      </div>
                                    </div>
                                    <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                                      {isFirst && sameTitle.length > 1 && (
                                        <button
                                          onClick={function() { if (confirm('Delete "' + res.title + '" from all ' + sameTitle.length + ' classes?')) handleDeleteAllSharedResources(res.title); }}
                                          className="btn btn-secondary"
                                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                                          title="Delete from all classes"
                                        >
                                          Delete All ({sameTitle.length})
                                        </button>
                                      )}
                                      <button
                                        onClick={function() { handleDeleteSharedResource(res.id, res.title + ' (' + res.class_name + ')'); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--danger)", padding: "4px" }}
                                        title={"Delete from " + res.class_name}
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
```

- [ ] **Step 7: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 8: Manual test**

1. Go to `localhost:3000`, navigate to the Student Portal tab
2. "Shared Resources" section should appear below the published assessments/assignments
3. Should show the flashcards you shared earlier (e.g., "The Road to the Civil War" × 6 classes)
4. Click the trash icon on one — it should delete from that class and show a toast
5. Click "Delete All (N)" on a multi-class entry — should delete from all classes after confirmation

- [ ] **Step 9: Commit**

```bash
git add frontend/src/services/api.js frontend/src/App.jsx
git commit -m "feat: add shared resources section to teacher Student Portal tab"
```

---

## Summary

| Task | What | Files | Complexity |
|------|------|-------|-----------|
| 1 | Backend endpoints (list, delete, bulk delete) | `student_portal_routes.py` | Low |
| 2 | Frontend state, fetch, delete handlers, UI section | `api.js`, `App.jsx` | Medium |

**Total: 3 modified files, 2 commits.**

**Before:** Shared resources invisible to teachers after publishing — no way to view or delete them.
**After:** "Shared Resources" section in Student Portal tab shows all shared content with per-class and bulk delete options.
