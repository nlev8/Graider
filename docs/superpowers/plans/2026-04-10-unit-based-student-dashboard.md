# Unit-Based Student Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group student dashboard content by unit in collapsible sections, carry unit name through the publish flow, and let teachers assign units to uncategorized content.

**Architecture:** Store `unit_name` in the existing `settings` JSONB on `published_content`. Pass it through the share flow (modal + API). Return it in dashboard/resource APIs. Refactor `StudentDashboard.jsx` to group items by unit and render collapsible sections. Add a unit-update endpoint for teacher reassignment.

**Tech Stack:** Python/Flask (backend), React JSX (frontend), Supabase (`published_content.settings` JSONB)

**Spec:** `docs/superpowers/specs/2026-04-10-unit-based-student-dashboard-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/student_account_routes.py` | **Modify** | Return `unit_name` in dashboard items (line ~655-668) |
| `backend/routes/student_portal_routes.py` | **Modify** | Add unit-update endpoint; include `unit_name` and `settings` in shared resources list |
| `frontend/src/services/api.js` | **Modify** | Add `updateSharedResourceUnit` helper |
| `frontend/src/App.jsx` | **Modify** | Add unit field to share modal; pass `settings.unit_name` in publish requests; add unit dropdown to Shared Resources |
| `frontend/src/components/StudentDashboard.jsx` | **Modify** | Refactor to group by unit, render collapsible sections |

---

### Task 1: Backend — Return unit_name in dashboard items + add unit-update endpoint

**Files:**
- Modify: `backend/routes/student_account_routes.py:655-668`
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add unit_name to dashboard items**

In `backend/routes/student_account_routes.py`, find the dashboard item builder (around line 655-668). The current code builds items without `unit_name`:

```python
      items.append({
          'content_id': c['id'],
          'title': c['title'],
          'content_type': c['content_type'],
          'due_date': c.get('due_date'),
          ...
      })
```

Add `unit_name` to each item by reading from `settings`:

```python
          'unit_name': c.get('settings', {}).get('unit_name', ''),
```

Add this line after the `'content_type'` line inside the `items.append({...})` dict.

- [ ] **Step 2: Add unit_name to shared resources list**

In `backend/routes/student_portal_routes.py`, find `list_shared_resources` (around line 703). Update the select to include `settings`:

Change:
```python
        result = db.table('published_content').select(
            'id, title, content_type, class_id, created_at, is_active'
        )
```

To:
```python
        result = db.table('published_content').select(
            'id, title, content_type, class_id, created_at, is_active, settings'
        )
```

And add `unit_name` to the returned resources dict (around line 724-732):

```python
            "unit_name": r.get('settings', {}).get('unit_name', ''),
```

Add this line after the `"is_active"` line.

- [ ] **Step 3: Add unit-update endpoint**

At the end of `backend/routes/student_portal_routes.py`, after the `delete_shared_resources_bulk` function, add:

```python
@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>/unit', methods=['POST'])
@require_teacher
@handle_route_errors
def update_shared_resource_unit(resource_id):
    """Update the unit_name in a shared resource's settings."""
    try:
        db = get_supabase()
        data = request.json
        unit_name = data.get('unit_name', '').strip()

        # Verify ownership
        check = db.table('published_content').select('id, settings').eq(
            'id', resource_id
        ).eq('teacher_id', g.teacher_id).execute()
        if not check.data:
            return jsonify({"error": "Resource not found"}), 404

        # Merge unit_name into existing settings
        existing_settings = check.data[0].get('settings') or {}
        existing_settings['unit_name'] = unit_name

        db.table('published_content').update({
            'settings': existing_settings
        }).eq('id', resource_id).execute()

        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Update shared resource unit error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 4: Run backend tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/routes/student_account_routes.py backend/routes/student_portal_routes.py
git commit -m "feat: return unit_name in dashboard items, add unit-update endpoint"
```

---

### Task 2: Frontend — Pass unit_name through the share flow

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add API helper for unit update**

In `frontend/src/services/api.js`, after the `deleteSharedResourcesBulk` function (around line 737), add:

```javascript
export async function updateSharedResourceUnit(id, unitName) {
  return fetchApi('/api/teacher/shared-resource/' + id + '/unit', {
    method: 'POST',
    body: JSON.stringify({ unit_name: unitName }),
  })
}
```

- [ ] **Step 2: Add unitName to shareModalContent state**

In `frontend/src/App.jsx`, find where `shareWithClass` sets the modal content (around line 1697):

```javascript
    setShareModalContent({ content: content, contentType: contentType, title: title });
```

Change to:
```javascript
    setShareModalContent({ content: content, contentType: contentType, title: title, unitName: unitConfig.title || '' });
```

- [ ] **Step 3: Pass settings with unit_name in single-class publish**

In `shareWithClass`, find the single-class POST body (around line 1678):

```javascript
          body: JSON.stringify({
            class_id: classes[0].id,
            content: content,
            content_type: contentType,
            title: title,
          }),
```

Change to:
```javascript
          body: JSON.stringify({
            class_id: classes[0].id,
            content: content,
            content_type: contentType,
            title: title,
            settings: { unit_name: unitConfig.title || '' },
          }),
```

- [ ] **Step 4: Pass settings with unit_name in multi-class publish**

In `executeShareWithClasses`, find the POST body (around line 1712):

```javascript
          body: JSON.stringify({
            class_id: shareModalSelected[i],
            content: shareModalContent.content,
            content_type: shareModalContent.contentType,
            title: shareModalContent.title,
          }),
```

Change to:
```javascript
          body: JSON.stringify({
            class_id: shareModalSelected[i],
            content: shareModalContent.content,
            content_type: shareModalContent.contentType,
            title: shareModalContent.title,
            settings: { unit_name: shareModalContent.unitName || '' },
          }),
```

- [ ] **Step 5: Add unit input field to share modal JSX**

In the share modal JSX (around line 16810), find the title display paragraph:

```jsx
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
              {shareModalContent ? '"' + shareModalContent.title + '"' : ''}
            </p>
```

AFTER that paragraph and BEFORE the "Select All" label, add:

```jsx
            {/* Unit field */}
            <div style={{ marginBottom: "16px" }}>
              <label style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                Unit
              </label>
              <input
                type="text"
                value={shareModalContent ? (shareModalContent.unitName || '') : ''}
                onChange={function(e) {
                  setShareModalContent(function(prev) {
                    return prev ? Object.assign({}, prev, { unitName: e.target.value }) : prev;
                  });
                }}
                placeholder="e.g. Unit 4: The Road to the Civil War"
                className="input"
                style={{ width: "100%", padding: "8px 12px", fontSize: "0.9rem" }}
              />
              {shareModalContent && shareModalContent.unitName && (
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "2px", display: "block" }}>Auto-filled from Planner</span>
              )}
            </div>
```

- [ ] **Step 6: Add unit dropdown to Shared Resources section**

In the Shared Resources section (in the teacher portal tab), find the resource list render. For each resource item, after the existing subtitle line showing type/class/date, update the rendering to include unit info and a dropdown for uncategorized items.

Find the subtitle div inside the shared resources map:
```javascript
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                      </div>
```

Replace with:
```javascript
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                        {res.unit_name ? (' ' + String.fromCharCode(8226) + ' ' + res.unit_name) : ''}
                                      </div>
                                      {!res.unit_name && (
                                        <select
                                          onChange={async function(e) {
                                            var val = e.target.value;
                                            if (val === '__new__') {
                                              val = prompt('Enter unit name:');
                                              if (!val) { e.target.value = ''; return; }
                                            }
                                            if (!val) return;
                                            try {
                                              var data = await api.updateSharedResourceUnit(res.id, val);
                                              if (data.success) {
                                                setSharedResources(function(prev) {
                                                  return prev.map(function(r) { return r.id === res.id ? Object.assign({}, r, { unit_name: val }) : r; });
                                                });
                                                addToast('Assigned to ' + val, 'success');
                                              }
                                            } catch (err) { addToast('Failed to assign unit', 'error'); }
                                          }}
                                          style={{ padding: "3px 8px", borderRadius: "6px", background: "var(--input-bg)", border: "1px solid var(--warning-border)", color: "var(--text-primary)", fontSize: "0.7rem", cursor: "pointer" }}
                                          defaultValue=""
                                        >
                                          <option value="" disabled>Assign unit...</option>
                                          {Array.from(new Set(sharedResources.filter(function(r) { return r.unit_name; }).map(function(r) { return r.unit_name; }))).map(function(u) {
                                            return <option key={u} value={u}>{u}</option>;
                                          })}
                                          <option value="__new__">+ New unit</option>
                                        </select>
                                      )}
```

- [ ] **Step 7: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 8: Manual test**

1. Go to Planner, set a unit title (e.g., "Unit 4: The Road to the Civil War")
2. Generate flashcards, click "Share with Class"
3. Verify the Unit field is pre-filled in the share modal
4. Share to a class — verify the resource appears with the unit name in the Shared Resources section
5. Share something without a unit — verify it shows the dropdown to assign one

- [ ] **Step 9: Commit**

```bash
git add frontend/src/services/api.js frontend/src/App.jsx
git commit -m "feat: pass unit_name through share flow, add unit assignment dropdown"
```

---

### Task 3: Student Dashboard — Collapsible unit-based layout

**Files:**
- Modify: `frontend/src/components/StudentDashboard.jsx`

This is the largest task. The current flat layout is replaced with grouped, collapsible unit sections.

- [ ] **Step 1: Add expanded units state**

In `StudentDashboard.jsx`, after the existing state declarations (after `var [lightMode, setLightMode] = ...`), add:

```javascript
  var [expandedUnits, setExpandedUnits] = useState({});
```

- [ ] **Step 2: Build grouped units from items and resources**

After the existing `allResources` computation (around line 24), add the grouping logic:

```javascript
  // Group all content by unit_name
  var unitGroups = {};
  assignmentItems.forEach(function(item) {
    var unit = item.unit_name || '';
    if (!unitGroups[unit]) unitGroups[unit] = { assignments: [], resources: [], newestDate: '' };
    unitGroups[unit].assignments.push(item);
    if (item.created_at > unitGroups[unit].newestDate) unitGroups[unit].newestDate = item.created_at;
  });
  allResources.forEach(function(res) {
    var unit = res.unit_name || '';
    if (!unitGroups[unit]) unitGroups[unit] = { assignments: [], resources: [], newestDate: '' };
    unitGroups[unit].resources.push(res);
    if (res.created_at && res.created_at > unitGroups[unit].newestDate) unitGroups[unit].newestDate = res.created_at;
  });

  // Sort units: most recent first, "General" (empty unit) always last
  var sortedUnits = Object.keys(unitGroups).sort(function(a, b) {
    if (!a) return 1;  // empty unit name goes last
    if (!b) return -1;
    return unitGroups[b].newestDate.localeCompare(unitGroups[a].newestDate);
  });

  // Auto-expand most recent unit on first render
  React.useEffect(function() {
    if (sortedUnits.length > 0 && Object.keys(expandedUnits).length === 0) {
      var first = sortedUnits[0];
      setExpandedUnits(function(prev) { var next = Object.assign({}, prev); next[first] = true; return next; });
    }
  }, [sortedUnits.length]);
```

- [ ] **Step 3: Replace the assignments and Study Materials sections with unit-based rendering**

Replace everything from the `<h2>Your Assignments</h2>` line through the end of the Study Materials section (before the `{/* Resource Viewer Modal */}` comment) with:

```jsx
        {loading ? (
          <p style={{ color: "var(--text-secondary)" }}>Loading...</p>
        ) : sortedUnits.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "60px 20px",
            background: "var(--card-bg-light)", borderRadius: "12px",
            border: "1px solid var(--glass-border)",
          }}>
            <p style={{ color: "var(--text-secondary)", fontSize: "1.1rem" }}>No content yet</p>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Your teacher will publish assignments and study materials here
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {sortedUnits.map(function(unitName, unitIdx) {
              var group = unitGroups[unitName];
              var isExpanded = expandedUnits[unitName] || false;
              var displayName = unitName || 'General';
              var assignmentCount = group.assignments.length;
              var resourceCount = group.resources.length;
              var allGraded = assignmentCount > 0 && group.assignments.every(function(a) { return a.status === 'graded'; });
              var isMostRecent = unitIdx === 0 && unitName;

              return (
                <div key={unitName || '__general__'} style={{ borderRadius: "12px", border: "1px solid var(--glass-border)", overflow: "hidden" }}>
                  {/* Unit Header — click to toggle */}
                  <div
                    onClick={function() {
                      setExpandedUnits(function(prev) {
                        var next = Object.assign({}, prev);
                        next[unitName] = !prev[unitName];
                        return next;
                      });
                    }}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "14px 18px", cursor: "pointer",
                      background: isExpanded ? "rgba(99,102,241,0.06)" : "var(--card-bg)",
                      transition: "background 0.15s",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontSize: "1rem", transition: "transform 0.2s", transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)" }}>
                        {String.fromCharCode(9654)}
                      </span>
                      <div>
                        <div style={{ fontSize: "1rem", fontWeight: 700 }}>{displayName}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                          {assignmentCount > 0 ? assignmentCount + ' assignment' + (assignmentCount === 1 ? '' : 's') : ''}
                          {assignmentCount > 0 && resourceCount > 0 ? ' ' + String.fromCharCode(183) + ' ' : ''}
                          {resourceCount > 0 ? resourceCount + ' study material' + (resourceCount === 1 ? '' : 's') : ''}
                          {allGraded ? ' ' + String.fromCharCode(183) + ' All graded ' + String.fromCharCode(10003) : ''}
                        </div>
                      </div>
                    </div>
                    {isMostRecent && (
                      <span style={{ fontSize: "0.7rem", padding: "3px 10px", background: "rgba(99,102,241,0.12)", borderRadius: "10px", color: "var(--accent-primary)", fontWeight: 600 }}>
                        Current
                      </span>
                    )}
                  </div>

                  {/* Unit Body — expanded content */}
                  {isExpanded && (
                    <div style={{ padding: "16px 18px", background: "var(--card-bg-light)" }}>
                      {/* Assignments sub-section */}
                      {assignmentCount > 0 && (
                        <div style={{ marginBottom: resourceCount > 0 ? "16px" : "0" }}>
                          <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: "8px" }}>
                            Assignments
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                            {group.assignments.map(function(item) {
                              var st = statusColors[item.status] || statusColors.not_started;
                              var isClickable = item.status !== 'graded';
                              return (
                                <div
                                  key={item.content_id}
                                  onClick={function() { if (isClickable) openContent(item); }}
                                  style={{
                                    display: "flex", alignItems: "center", justifyContent: "space-between",
                                    padding: "10px 14px", borderRadius: "8px",
                                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                    cursor: isClickable ? "pointer" : "default",
                                    transition: "border-color 0.2s",
                                  }}
                                >
                                  <div>
                                    <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{item.title}</div>
                                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                      {item.content_type === 'assessment' ? 'Assessment' : 'Assignment'}
                                      {item.due_date ? ' ' + String.fromCharCode(8226) + ' Due ' + new Date(item.due_date).toLocaleDateString() : ''}
                                    </div>
                                  </div>
                                  <div style={{ textAlign: "right" }}>
                                    <span style={{
                                      padding: "3px 10px", borderRadius: "16px", fontSize: "0.7rem",
                                      fontWeight: 600, background: st.bg, color: st.text,
                                    }}>
                                      {st.label}
                                    </span>
                                    {item.score != null && (
                                      <div style={{ fontSize: "0.85rem", fontWeight: 600, marginTop: "4px" }}>
                                        {item.percentage != null ? Math.round(item.percentage) + '%' : item.score}
                                        {item.letter_grade ? ' (' + item.letter_grade + ')' : ''}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Study Materials sub-section */}
                      {resourceCount > 0 && (
                        <div>
                          <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: "8px" }}>
                            Study Materials
                          </div>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "8px" }}>
                            {group.resources.map(function(res) {
                              var icon = res.content_type === 'study_guide' ? String.fromCharCode(128214)
                                : res.content_type === 'flashcards' ? String.fromCharCode(128196)
                                : res.content_type === 'slide_deck' ? String.fromCharCode(128253)
                                : String.fromCharCode(128196);
                              var typeLabel = res.content_type === 'study_guide' ? 'Study Guide'
                                : res.content_type === 'flashcards' ? 'Flashcards'
                                : res.content_type === 'slide_deck' ? 'Slide Deck'
                                : res.content_type;
                              return (
                                <div
                                  key={res.id}
                                  onClick={function() {
                                    if (res._fromDashboard) {
                                      fetch('/api/student/content/' + res.content_id, {
                                        headers: { 'X-Student-Token': token }
                                      })
                                        .then(function(r) { return r.json(); })
                                        .then(function(data) {
                                          if (data.content) {
                                            setSelectedResource({ id: res.content_id, title: res.title, content_type: res.content_type, content: data.content });
                                            setFlippedCards({});
                                          }
                                        })
                                        .catch(function() {});
                                    } else {
                                      fetch('/api/student/resource/' + res.id, {
                                        headers: { 'X-Student-Token': token }
                                      })
                                        .then(function(r) { return r.json(); })
                                        .then(function(data) {
                                          if (data.resource) {
                                            setSelectedResource(data.resource);
                                            setFlippedCards({});
                                          }
                                        })
                                        .catch(function() {});
                                    }
                                  }}
                                  style={{
                                    padding: "12px 14px", borderRadius: "8px",
                                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                    cursor: "pointer", transition: "transform 0.1s",
                                  }}
                                >
                                  <div style={{ fontSize: "1.3rem", marginBottom: "4px" }}>{icon}</div>
                                  <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{res.title}</div>
                                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", marginTop: "2px" }}>{typeLabel}</div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
```

- [ ] **Step 4: Update dashboardResources to include unit_name**

In the existing `dashboardResources` computation (around line 19-21), update the map to include `unit_name`:

Find:
```javascript
  var dashboardResources = items.filter(function(i) { return RESOURCE_TYPES.indexOf(i.content_type) !== -1; }).map(function(i) {
    return { id: i.content_id, title: i.title, content_type: i.content_type, _fromDashboard: true, content_id: i.content_id };
  });
```

Replace with:
```javascript
  var dashboardResources = items.filter(function(i) { return RESOURCE_TYPES.indexOf(i.content_type) !== -1; }).map(function(i) {
    return { id: i.content_id, title: i.title, content_type: i.content_type, _fromDashboard: true, content_id: i.content_id, unit_name: i.unit_name || '', created_at: i.created_at || '' };
  });
```

- [ ] **Step 5: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 6: Manual test**

1. Log in as student `test@graider.live` / `NEE4K3` at `localhost:3000/student`
2. Content should be grouped by unit — items with `unit_name` in their own sections, items without in "General"
3. Most recent unit should be expanded, others collapsed
4. Click a collapsed unit header — should expand
5. Click an assignment — should open in the assessment player
6. Click a flashcard — should open in FlashcardView

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/StudentDashboard.jsx
git commit -m "feat: collapsible unit-based student dashboard layout"
```

---

## Summary

| Task | What | Files | Complexity |
|------|------|-------|-----------|
| 1 | Backend: return unit_name + unit-update endpoint | `student_account_routes.py`, `student_portal_routes.py` | Low |
| 2 | Frontend: pass unit through share flow + unit dropdown | `api.js`, `App.jsx` | Medium |
| 3 | Student dashboard: collapsible unit-based layout | `StudentDashboard.jsx` | Medium-High |

**Total: 5 modified files, 3 commits.**

**Before:** Flat list of assignments and study materials with no organization.
**After:** Content grouped by unit in collapsible sections. Unit name carried through the share flow. Teachers can assign units to uncategorized content. Most recent unit auto-expanded.
