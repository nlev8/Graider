# Content Tagging — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the existing `unit_name` field into a tag system that works across all published content types (join-code assessments, class-based content, and resources), with a global tag filter and per-row inline tag management.

**Architecture:** Tags live in the existing `settings` JSONB on both `published_assessments` and `published_content` rows (no schema migration). Two new teacher endpoints list and set tags. The Student Portal tab gains a global tag filter and per-row tag pills with a "+" dropdown. Client-side filtering; no per-filter network calls.

**Tech Stack:** Python/Flask (backend), React/JSX (frontend), Supabase (Postgres JSONB)

**Spec:** `docs/superpowers/specs/2026-04-10-content-tagging-design.md`

**Scope note:** The spec mentions `published_content`, but in practice the Teacher Student Portal tab also shows `published_assessments` (join-code based). Tags must work for both. The backend helpers accept a content ID and probe both tables to find the row.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/student_portal_routes.py` | **Modify** | Add `GET /api/teacher/tags` and `POST /api/teacher/published-content/<id>/tags` endpoints |
| `frontend/src/services/api.js` | **Modify** | Add `getTeacherTags` and `setContentTags` helpers |
| `frontend/src/App.jsx` | **Modify** | Global tag filter, per-row tag pills, "+" dropdown, reuse new-unit modal for new tags |

---

### Task 1: Backend tag endpoints

**Files:**
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add helper to find a content row across both tables**

Near the top of `backend/routes/student_portal_routes.py`, after `generate_join_code()` and `_parse_ts()` helpers, add:

```python
def _find_content_row(db, content_id, teacher_id):
    """Locate a published content row by ID in either published_assessments
    or published_content, verifying teacher ownership.

    Returns (table_name, row_dict) or (None, None) if not found.
    """
    # Try published_assessments first (join-code based)
    pa = db.table('published_assessments').select('id, settings, teacher_id').eq(
        'id', content_id
    ).execute()
    if pa.data:
        row = pa.data[0]
        if row.get('teacher_id') != teacher_id:
            return (None, None)
        return ('published_assessments', row)

    # Then class-based content
    pc = db.table('published_content').select('id, settings, teacher_id').eq(
        'id', content_id
    ).execute()
    if pc.data:
        row = pc.data[0]
        if row.get('teacher_id') != teacher_id:
            return (None, None)
        return ('published_content', row)

    return (None, None)
```

- [ ] **Step 2: Add `GET /api/teacher/tags` endpoint**

At the END of `backend/routes/student_portal_routes.py`, after the last endpoint, add:

```python
@student_portal_bp.route('/api/teacher/tags', methods=['GET'])
@require_teacher
@handle_route_errors
def list_teacher_tags():
    """Return all unique tags across the teacher's published content (both tables),
    including unit_name values and tags array values.
    """
    try:
        db = get_supabase()
        teacher_id = g.teacher_id

        tag_set = set()

        # Collect from published_assessments (join-code)
        pa = db.table('published_assessments').select('settings').eq(
            'teacher_id', teacher_id
        ).execute()
        for row in pa.data or []:
            s = row.get('settings') or {}
            unit = s.get('unit_name')
            if unit and isinstance(unit, str) and unit.strip():
                tag_set.add(unit.strip())
            for t in (s.get('tags') or []):
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())

        # Collect from published_content (class-based)
        pc = db.table('published_content').select('settings').eq(
            'teacher_id', teacher_id
        ).execute()
        for row in pc.data or []:
            s = row.get('settings') or {}
            unit = s.get('unit_name')
            if unit and isinstance(unit, str) and unit.strip():
                tag_set.add(unit.strip())
            for t in (s.get('tags') or []):
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())

        return jsonify({"tags": sorted(tag_set)})
    except Exception as e:
        _logger.exception("List teacher tags error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 3: Add `POST /api/teacher/published-content/<id>/tags` endpoint**

Immediately after, add:

```python
@student_portal_bp.route('/api/teacher/published-content/<content_id>/tags', methods=['POST'])
@require_teacher
@handle_route_errors
def set_content_tags(content_id):
    """Replace the tags array on a published content row (either table).

    Request: { "tags": [str, ...] }
    Preserves all other settings fields.
    """
    try:
        db = get_supabase()
        data = request.json or {}
        raw_tags = data.get('tags')
        if not isinstance(raw_tags, list):
            return jsonify({"error": "tags must be an array"}), 400

        # Sanitize: strip, drop empties, dedupe preserving order
        seen = set()
        clean_tags = []
        for t in raw_tags:
            if not isinstance(t, str):
                continue
            s = t.strip()
            if not s or s in seen:
                continue
            if len(s) > 100:
                s = s[:100]
            seen.add(s)
            clean_tags.append(s)

        table_name, row = _find_content_row(db, content_id, g.teacher_id)
        if not row:
            return jsonify({"error": "Content not found"}), 404

        existing_settings = row.get('settings') or {}
        existing_settings['tags'] = clean_tags

        db.table(table_name).update({'settings': existing_settings}).eq('id', content_id).execute()
        return jsonify({"success": True, "tags": clean_tags})
    except Exception as e:
        _logger.exception("Set content tags error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 4: Extend existing unit update endpoint to work across both tables**

Find `update_shared_resource_unit` (around line 929). Its current implementation queries `published_content` only. Replace the body to use `_find_content_row`:

```python
@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>/unit', methods=['POST'])
@require_teacher
@handle_route_errors
def update_shared_resource_unit(resource_id):
    """Update the unit_name in a published content row's settings.
    Works for both published_assessments and published_content tables.
    """
    try:
        db = get_supabase()
        data = request.json
        unit_name = data.get('unit_name', '').strip()

        table_name, row = _find_content_row(db, resource_id, g.teacher_id)
        if not row:
            return jsonify({"error": "Resource not found"}), 404

        existing_settings = row.get('settings') or {}
        existing_settings['unit_name'] = unit_name

        db.table(table_name).update({
            'settings': existing_settings
        }).eq('id', resource_id).execute()

        return jsonify({"success": True})
    except Exception as e:
        _logger.exception("Update unit error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 5: Ensure `list_published_assessments` returns unit_name and tags**

Find `list_published_assessments` (around line 415). It currently returns a subset of `settings` fields. Add `unit_name` and `tags` to the returned dict:

Change:
```python
        assessments = [{
            "id": a.get('id'),
            "join_code": a.get('join_code'),
            "title": a.get('title'),
            "created_at": a.get('created_at'),
            "submission_count": a.get('submission_count', 0),
            "is_active": a.get('is_active', True),
            "content_type": a.get('settings', {}).get('content_type', 'assessment'),
            "period": a.get('settings', {}).get('period', ''),
            "is_makeup": a.get('settings', {}).get('is_makeup', False),
            "restricted_students": a.get('settings', {}).get('restricted_students', []),
        } for a in result.data]
```

To:
```python
        assessments = [{
            "id": a.get('id'),
            "join_code": a.get('join_code'),
            "title": a.get('title'),
            "created_at": a.get('created_at'),
            "submission_count": a.get('submission_count', 0),
            "is_active": a.get('is_active', True),
            "content_type": a.get('settings', {}).get('content_type', 'assessment'),
            "period": a.get('settings', {}).get('period', ''),
            "is_makeup": a.get('settings', {}).get('is_makeup', False),
            "restricted_students": a.get('settings', {}).get('restricted_students', []),
            "unit_name": a.get('settings', {}).get('unit_name', ''),
            "tags": a.get('settings', {}).get('tags', []),
        } for a in result.data]
```

- [ ] **Step 6: Ensure `list_shared_resources` returns tags**

Find `list_shared_resources` (it already returns `unit_name` from Phase 1). Add `tags` to its returned dict by appending after the `unit_name` line:

```python
            "tags": r.get('settings', {}).get('tags', []),
```

- [ ] **Step 7: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "feat: add tag endpoints and include unit_name/tags in teacher listings"
```

---

### Task 2: Frontend API helpers

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Add helpers**

At the end of `frontend/src/services/api.js`, add:

```javascript
export async function getTeacherTags() {
  return fetchApi('/api/teacher/tags');
}

export async function setContentTags(contentId, tags) {
  return fetchApi('/api/teacher/published-content/' + contentId + '/tags', {
    method: 'POST',
    body: JSON.stringify({ tags: tags }),
  });
}
```

- [ ] **Step 2: Build**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add getTeacherTags and setContentTags API helpers"
```

---

### Task 3: Global tag filter state and fetch

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add state**

Near the other student-portal-related state (search for `const [sharedResources, setSharedResources]`), add:

```javascript
  const [allTeacherTags, setAllTeacherTags] = useState([]);
  const [selectedTagFilter, setSelectedTagFilter] = useState('all');
```

- [ ] **Step 2: Add fetchTeacherTags function**

Near the existing `fetchSharedResources` function, add:

```javascript
  const fetchTeacherTags = async () => {
    try {
      const data = await api.getTeacherTags();
      if (data && data.tags) setAllTeacherTags(data.tags);
    } catch (e) {
      console.error('Error loading teacher tags:', e);
    }
  };
```

- [ ] **Step 3: Call fetchTeacherTags alongside fetchSharedResources**

Find every call site of `fetchSharedResources()`. After each one, add `fetchTeacherTags();` on the next line.

- [ ] **Step 4: Add helper function to check if an item matches the current filter**

Near the top of the App function body (near other helpers), add:

```javascript
  var itemMatchesTagFilter = function(item) {
    if (selectedTagFilter === 'all') return true;
    if (item.unit_name && item.unit_name === selectedTagFilter) return true;
    var tags = item.tags || [];
    return tags.indexOf(selectedTagFilter) !== -1;
  };
```

- [ ] **Step 5: Commit state scaffolding**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add tag filter state and fetchTeacherTags"
```

---

### Task 4: Global tag filter bar UI

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add the filter bar JSX above the published content lists**

Find the comment `{/* Published Content Lists — separated by content type */}` around line 13835. Insert BEFORE that comment (and before the `.map` that follows):

```jsx
                      {/* Global tag filter (Phase 2.5: Content Tagging) */}
                      <div className="glass-card" style={{ padding: "12px 16px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                        <Icon name="Tag" size={16} style={{ color: "var(--text-secondary)" }} />
                        <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Filter by tag:</label>
                        <select
                          value={selectedTagFilter}
                          onChange={function(e) { setSelectedTagFilter(e.target.value); }}
                          className="input"
                          style={{ padding: "6px 12px", fontSize: "0.85rem", minWidth: "220px" }}
                        >
                          <option value="all">All content ({allTeacherTags.length} tags)</option>
                          {allTeacherTags.map(function(t) {
                            return <option key={t} value={t}>{t}</option>;
                          })}
                        </select>
                        {selectedTagFilter !== 'all' && (
                          <button
                            onClick={function() { setSelectedTagFilter('all'); }}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Clear
                          </button>
                        )}
                      </div>
```

- [ ] **Step 2: Apply filter to assessments/assignments**

Find the `sectionItems` computation around line 13840:

```javascript
var sectionItems = publishedAssessments.filter(function(a) { return (a.content_type || "assessment") === section.type; });
```

Change to:

```javascript
var sectionItems = publishedAssessments.filter(function(a) {
  return (a.content_type || "assessment") === section.type && itemMatchesTagFilter(a);
});
```

- [ ] **Step 3: Apply filter to shared resources**

Find the Shared Resources map in the teacher portal. Look for `sharedResources.map(` inside the Shared Resources rendering. Wrap with filter:

Change:
```javascript
{sharedResources.map(function(res) {
```

To:
```javascript
{sharedResources.filter(itemMatchesTagFilter).map(function(res) {
```

- [ ] **Step 4: Build**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add global tag filter bar to Student Portal tab"
```

---

### Task 5: Tag pills + "+" dropdown on rows

**Files:**
- Modify: `frontend/src/App.jsx`

This task adds the tag display and management UI to each row across all 3 lists. The approach: create a reusable inline component and use it in each row.

- [ ] **Step 1: Add tag row state**

Near the other state declarations, add:

```javascript
  const [tagDropdownOpenFor, setTagDropdownOpenFor] = useState(null); // content_id or null
```

- [ ] **Step 2: Add helper functions for tag operations**

Near the other helper functions in the App component, add:

```javascript
  var handleSetUnit = async function(contentId, unitName, onSuccess) {
    try {
      var data = await api.updateSharedResourceUnit(contentId, unitName);
      if (data && data.success) {
        if (onSuccess) onSuccess(unitName);
        addToast('Set unit to "' + unitName + '"', 'success');
        fetchTeacherTags();
      }
    } catch (e) {
      addToast('Failed to set unit: ' + (e.message || 'unknown'), 'error');
    }
  };

  var handleSetTags = async function(contentId, tags, onSuccess) {
    try {
      var data = await api.setContentTags(contentId, tags);
      if (data && data.success) {
        if (onSuccess) onSuccess(data.tags || tags);
        fetchTeacherTags();
      }
    } catch (e) {
      addToast('Failed to update tags: ' + (e.message || 'unknown'), 'error');
    }
  };

  var handleAddTag = function(contentId, existingTags, newTag, onSuccess) {
    var tags = (existingTags || []).slice();
    if (tags.indexOf(newTag) !== -1) return; // already present
    tags.push(newTag);
    handleSetTags(contentId, tags, function(saved) {
      if (onSuccess) onSuccess(saved);
      addToast('Added tag "' + newTag + '"', 'success');
    });
  };

  var handleRemoveTag = function(contentId, existingTags, tagToRemove, onSuccess) {
    var tags = (existingTags || []).filter(function(t) { return t !== tagToRemove; });
    handleSetTags(contentId, tags, function(saved) {
      if (onSuccess) onSuccess(saved);
      addToast('Removed tag "' + tagToRemove + '"', 'success');
    });
  };
```

- [ ] **Step 3: Create a reusable TagRow function component inside App.jsx**

Near the top of the App component body (after the state declarations but before the return), add:

```javascript
  // Phase 2.5: reusable tag row UI for published content
  var renderTagRow = function(item, onUpdate) {
    // item: { id (or join_code for assessments), unit_name, tags }
    // onUpdate: function(updatedFields) to patch local state after server update
    var itemId = item.id || item.content_id;
    if (!itemId) return null;
    var isDropdownOpen = tagDropdownOpenFor === itemId;
    var unitName = item.unit_name || '';
    var tags = item.tags || [];
    var availableTags = allTeacherTags.filter(function(t) {
      return t !== unitName && tags.indexOf(t) === -1;
    });

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", marginTop: "8px", position: "relative" }}>
        {unitName ? (
          <span
            onClick={function(e) {
              e.stopPropagation();
              handleSetUnit(itemId, '', function() { onUpdate({ unit_name: '' }); });
            }}
            style={{
              display: "inline-flex", alignItems: "center", gap: "4px",
              padding: "3px 10px", borderRadius: "12px",
              background: "rgba(99,102,241,0.15)", color: "var(--accent-primary)",
              fontSize: "0.72rem", fontWeight: 600, cursor: "pointer",
              border: "1px solid rgba(99,102,241,0.3)",
            }}
            title="Click to remove unit"
          >
            <Icon name="Folder" size={11} />
            {unitName}
          </span>
        ) : (
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic" }}>
            No unit
          </span>
        )}
        {tags.map(function(t) {
          return (
            <span
              key={t}
              onClick={function(e) {
                e.stopPropagation();
                handleRemoveTag(itemId, tags, t, function(saved) { onUpdate({ tags: saved }); });
              }}
              style={{
                padding: "3px 8px", borderRadius: "10px",
                background: "var(--glass-bg)", color: "var(--text-secondary)",
                fontSize: "0.7rem", cursor: "pointer",
                border: "1px solid var(--glass-border)",
              }}
              title="Click to remove tag"
            >
              {t}
            </span>
          );
        })}
        <button
          onClick={function(e) {
            e.stopPropagation();
            setTagDropdownOpenFor(isDropdownOpen ? null : itemId);
          }}
          style={{
            padding: "2px 8px", borderRadius: "10px",
            background: "var(--glass-bg)", color: "var(--text-secondary)",
            fontSize: "0.75rem", cursor: "pointer",
            border: "1px dashed var(--glass-border)",
          }}
          title="Add tag"
        >
          + Tag
        </button>
        {isDropdownOpen && (
          <div
            onClick={function(e) { e.stopPropagation(); }}
            style={{
              position: "absolute", top: "100%", left: 0, marginTop: "4px",
              background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)",
              borderRadius: "10px", padding: "8px", minWidth: "220px", maxHeight: "280px",
              overflowY: "auto", zIndex: 50,
              boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
            }}
          >
            {!unitName && allTeacherTags.length > 0 && (
              <div style={{ marginBottom: "6px" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", padding: "4px 8px", letterSpacing: "0.05em" }}>Set as unit</div>
                {allTeacherTags.slice(0, 5).map(function(t) {
                  return (
                    <div
                      key={'u-' + t}
                      onClick={function() {
                        setTagDropdownOpenFor(null);
                        handleSetUnit(itemId, t, function() { onUpdate({ unit_name: t }); });
                      }}
                      style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
                      onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
                      onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <Icon name="Folder" size={12} style={{ color: "var(--accent-primary)" }} />
                      {t}
                    </div>
                  );
                })}
                <div style={{ height: "1px", background: "var(--glass-border)", margin: "6px 0" }} />
              </div>
            )}
            <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", padding: "4px 8px", letterSpacing: "0.05em" }}>
              {availableTags.length > 0 ? 'Add existing tag' : 'No other tags'}
            </div>
            {availableTags.map(function(t) {
              return (
                <div
                  key={'t-' + t}
                  onClick={function() {
                    setTagDropdownOpenFor(null);
                    handleAddTag(itemId, tags, t, function(saved) { onUpdate({ tags: saved }); });
                  }}
                  style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer" }}
                  onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
                  onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
                >
                  {t}
                </div>
              );
            })}
            <div style={{ height: "1px", background: "var(--glass-border)", margin: "6px 0" }} />
            <div
              onClick={function() {
                setTagDropdownOpenFor(null);
                setNewUnitModal({ resourceId: itemId, value: '', mode: unitName ? 'tag' : 'unit', existingTags: tags });
              }}
              style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer", color: "var(--accent-primary)", fontWeight: 600 }}
              onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
              onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
            >
              + Create new tag...
            </div>
          </div>
        )}
      </div>
    );
  };
```

- [ ] **Step 4: Update the existing new-unit modal to support "tag" mode**

Find the existing new-unit modal (search for `newUnitModal &&`). The current modal only creates a unit. Change the modal to branch on `newUnitModal.mode`:

Find:
```jsx
                if (e.key === 'Enter' && newUnitModal.value.trim()) {
                  var val = newUnitModal.value.trim();
                  var rid = newUnitModal.resourceId;
                  setNewUnitModal(null);
                  try {
                    var data = await api.updateSharedResourceUnit(rid, val);
                    if (data.success) {
                      setSharedResources(function(prev) {
                        return prev.map(function(r) { return r.id === rid ? Object.assign({}, r, { unit_name: val }) : r; });
                      });
                      addToast('Assigned to ' + val, 'success');
                    }
                  } catch (err) { addToast('Failed to assign unit', 'error'); }
                }
```

Replace with:
```jsx
                if (e.key === 'Enter' && newUnitModal.value.trim()) {
                  var val = newUnitModal.value.trim();
                  var rid = newUnitModal.resourceId;
                  var mode = newUnitModal.mode || 'unit';
                  var existing = newUnitModal.existingTags || [];
                  setNewUnitModal(null);
                  try {
                    if (mode === 'tag') {
                      var data = await api.setContentTags(rid, existing.concat([val]));
                      if (data.success) {
                        setSharedResources(function(prev) {
                          return prev.map(function(r) { return r.id === rid ? Object.assign({}, r, { tags: data.tags || existing.concat([val]) }) : r; });
                        });
                        setPublishedAssessments(function(prev) {
                          return prev.map(function(a) { return (a.id === rid || a.join_code === rid) ? Object.assign({}, a, { tags: data.tags || existing.concat([val]) }) : a; });
                        });
                        addToast('Added tag "' + val + '"', 'success');
                        fetchTeacherTags();
                      }
                    } else {
                      var data2 = await api.updateSharedResourceUnit(rid, val);
                      if (data2.success) {
                        setSharedResources(function(prev) {
                          return prev.map(function(r) { return r.id === rid ? Object.assign({}, r, { unit_name: val }) : r; });
                        });
                        setPublishedAssessments(function(prev) {
                          return prev.map(function(a) { return (a.id === rid || a.join_code === rid) ? Object.assign({}, a, { unit_name: val }) : a; });
                        });
                        addToast('Set unit to "' + val + '"', 'success');
                        fetchTeacherTags();
                      }
                    }
                  } catch (err) { addToast('Failed: ' + (err.message || 'unknown'), 'error'); }
                }
```

Apply the same modification to the "Create Unit" button click handler in the modal (a few lines below) so both Enter-key and click behave identically. Also change the modal title from "New Unit" to `newUnitModal.mode === 'tag' ? 'New Tag' : 'New Unit'` and the placeholder from "Unit 4: ..." to `newUnitModal.mode === 'tag' ? 'e.g. Review, Formative, Civil War' : 'e.g. Unit 4: The Road to the Civil War'`. Change the button label from "Create Unit" to `newUnitModal.mode === 'tag' ? 'Create Tag' : 'Create Unit'`.

- [ ] **Step 5: Insert `renderTagRow` into the assessment/assignment rows**

Find the assessment row JSX inside the `.map((assessment) => ...)` loop (around line 13875-13942). After the closing `</div>` of the row's status badge area but before the row's outer closing `</div>`, insert:

```jsx
                                    {renderTagRow(assessment, function(updates) {
                                      setPublishedAssessments(function(prev) {
                                        return prev.map(function(a) {
                                          if (a.join_code === assessment.join_code || a.id === assessment.id) return Object.assign({}, a, updates);
                                          return a;
                                        });
                                      });
                                    })}
```

Place it at the end of the row just before its closing tag, so the tag bar appears at the bottom of each row.

- [ ] **Step 6: Insert `renderTagRow` into the Shared Resources rows**

Find the Shared Resources `.map(function(res) {` loop. Replace the existing "Assign unit..." dropdown-only UI with `renderTagRow`. Find the block that contains:

```jsx
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                        {res.unit_name ? (' ' + String.fromCharCode(8226) + ' ' + res.unit_name) : ''}
                                      </div>
                                      {!res.unit_name && (
                                        <select ...>
```

Replace the `{!res.unit_name && <select ...>}` block through its closing `</select>` with:

```jsx
                                      {renderTagRow(res, function(updates) {
                                        setSharedResources(function(prev) {
                                          return prev.map(function(r) { return r.id === res.id ? Object.assign({}, r, updates) : r; });
                                        });
                                      })}
```

Also remove the inline `res.unit_name ? ' • ' + res.unit_name : ''` from the subtitle since the unit is now shown in the tag row.

- [ ] **Step 7: Build**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 8: Manual test**

1. Go to Student Portal tab
2. Verify global filter bar appears at top with "All content" default
3. Verify each assessment/assignment row has a tag row at the bottom
4. Click "+ Tag" on a row with no unit → dropdown shows "Set as unit" section with existing tags + "Create new tag..." option
5. Click "Create new tag..." → modal opens with "New Unit" title (since item has no unit yet)
6. Type a name → hit Enter → unit assigned, row updates, filter dropdown gains the new tag
7. On the same row, click "+ Tag" again → this time dropdown shows only "Add existing tag" and "Create new tag..." (no unit section)
8. Create a new tag → it's added to `tags` array, shown as a smaller pill
9. Click a tag pill → it's removed
10. Pick a specific tag from global filter → all 3 lists filter to matching items only
11. Click "Clear" → back to all content

- [ ] **Step 9: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: inline tag pills and dropdown on published content rows"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Backend: tag endpoints + unit endpoint generalization + listing changes | Medium — touches 3 endpoints |
| 2 | Frontend API helpers | Low — mechanical |
| 3 | Global tag filter state + helper | Low — additive state |
| 4 | Global tag filter bar UI | Low — new JSX block |
| 5 | Tag pills + "+" dropdown + new-tag modal extension | Medium — reusable component + modal branching |

**Total: 3 modified files, 5 commits.**

**Before:** Unit assignment exists only on shared resources via a one-shot dropdown. No cross-list filtering, no tags.
**After:** Global tag filter bar at top of Student Portal tab, inline tag pills and "+" dropdown on every published content row, unified "New Tag" modal for creating both units and tags, teacher-global tag list fetched from server.
