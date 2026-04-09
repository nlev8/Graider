# Student Dashboard Resource Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route flashcards, study guides, and slide decks from the student dashboard's "Your Assignments" section to the "Study Materials" section, and render flashcards using the interactive `FlashcardView` component.

**Architecture:** Filter `items` array by content type to separate assignments from resources. Merge resource-type dashboard items into the Study Materials section with a `_fromDashboard` flag. Use different fetch endpoints based on source. Replace the static flashcard grid with `FlashcardView`.

**Tech Stack:** React (JSX), existing `FlashcardView` component

**Spec:** `docs/superpowers/specs/2026-04-09-student-dashboard-resources-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/components/StudentDashboard.jsx` | **Modify** | Filter items, merge resources, import FlashcardView, update viewer |

---

### Task 1: Filter assignments and merge resource items into Study Materials

**Files:**
- Modify: `frontend/src/components/StudentDashboard.jsx`

- [ ] **Step 1: Add FlashcardView import**

At the top of `frontend/src/components/StudentDashboard.jsx`, after line 2 (`import StudentPortal from "./StudentPortal";`), add:

```javascript
import FlashcardView from "./FlashcardView";
```

- [ ] **Step 2: Add resource type constant**

After the imports (after the new FlashcardView import), add:

```javascript
var RESOURCE_TYPES = ['study_guide', 'flashcards', 'slide_deck'];
```

- [ ] **Step 3: Compute filtered lists**

Inside the component function, after `const token = localStorage.getItem("student_token");` (line 12), add:

```javascript
  // Split dashboard items into assignments vs resources
  var assignmentItems = items.filter(function(i) { return RESOURCE_TYPES.indexOf(i.content_type) === -1; });
  var dashboardResources = items.filter(function(i) { return RESOURCE_TYPES.indexOf(i.content_type) !== -1; }).map(function(i) {
    return { id: i.content_id, title: i.title, content_type: i.content_type, _fromDashboard: true, content_id: i.content_id };
  });
  // Merge dashboard resources into resources list, deduplicating by ID
  var resourceIds = resources.map(function(r) { return r.id; });
  var allResources = resources.concat(dashboardResources.filter(function(dr) { return resourceIds.indexOf(dr.id) === -1; }));
```

- [ ] **Step 4: Replace `items` with `assignmentItems` in the assignments section**

Find line 124 (the empty-state check):
```javascript
        ) : items.length === 0 ? (
```

Change to:
```javascript
        ) : assignmentItems.length === 0 ? (
```

Find line 137 (the items map):
```javascript
            {items.map((item) => {
```

Change to:
```javascript
            {assignmentItems.map((item) => {
```

- [ ] **Step 5: Replace `resources` with `allResources` in the Study Materials section**

Find line 182:
```javascript
        {resources.length > 0 && (
```

Change to:
```javascript
        {allResources.length > 0 && (
```

Find line 189:
```javascript
              {resources.map(function(res) {
```

Change to:
```javascript
              {allResources.map(function(res) {
```

- [ ] **Step 6: Update click handler for resource items**

Find the existing resource click handler (around line 201-212):
```javascript
                    onClick={function() {
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
                    }}
```

Replace with:
```javascript
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
```

- [ ] **Step 7: Replace static flashcard grid with FlashcardView**

Find the flashcard rendering block in the resource viewer modal (around line 279-340). It starts with:
```javascript
              {selectedResource.content_type === 'flashcards' && selectedResource.content && (
                <div>
                  <p style={{ fontSize: "0.8rem", color: "#64748b", marginBottom: "12px", textAlign: "center" }}>
                    Click a card to flip it
                  </p>
                  <div style={{ display: "grid", ...
```

Replace the entire `{selectedResource.content_type === 'flashcards' && selectedResource.content && (...)}` block with:
```javascript
              {selectedResource.content_type === 'flashcards' && selectedResource.content && (
                <FlashcardView data={selectedResource.content} />
              )}
```

- [ ] **Step 8: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 9: Manual test**

1. Go to `localhost:3000/student`, log in as `test@graider.live` / `NEE4K3`
2. "Your Assignments" should show assignments only (no flashcard entries)
3. "Study Materials" section should appear with the shared flashcards
4. Click a flashcard — modal should open with interactive `FlashcardView` (one card at a time, click to flip, arrow keys to navigate)

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/StudentDashboard.jsx
git commit -m "feat: route resource content to Study Materials with interactive FlashcardView"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Filter items, merge resources, update click handler, replace flashcard renderer | Low — one file, frontend only, no backend changes |

**Total: 1 modified file, 1 commit.**

**Before:** Flashcards shared via "Share with Class" appear in "Your Assignments" as broken entries.
**After:** Flashcards appear in "Study Materials" with interactive flip-card viewer. Assignments section shows only assessments and assignments.
