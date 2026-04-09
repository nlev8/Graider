# Share with Class Modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the browser `prompt()` class picker with a proper multi-select modal supporting "Select All" and sharing to multiple classes at once.

**Architecture:** Add state for modal visibility and selection, modify `shareWithClass` to open the modal instead of `prompt()`, add `executeShareWithClasses` to loop publish calls, and add modal JSX following the existing overlay + glass-card pattern in App.jsx.

**Tech Stack:** React (JSX), existing App.jsx modal patterns

**Spec:** `docs/superpowers/specs/2026-04-09-share-with-class-modal-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/App.jsx` | **Modify** | Add state, modify shareWithClass, add executeShareWithClasses, add modal JSX |

---

### Task 1: Add state and modify shareWithClass to open modal

**Files:**
- Modify: `frontend/src/App.jsx:1657-1701` (shareWithClass function)
- Modify: `frontend/src/App.jsx:2061` (state declarations near publishingAssessment)

- [ ] **Step 1: Add state variables**

In `frontend/src/App.jsx`, find the state declarations near line 2061 (where `teacherClasses` is declared). After the `publishedAssessmentModal` state (around line 2063), add:

```javascript
  // Share-with-class modal state
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareModalContent, setShareModalContent] = useState(null); // { content, contentType, title }
  const [shareModalSelected, setShareModalSelected] = useState([]); // array of class IDs
  const [shareModalSharing, setShareModalSharing] = useState(false);
```

- [ ] **Step 2: Replace shareWithClass function body**

In `frontend/src/App.jsx`, replace the entire `shareWithClass` function (lines 1657-1701) with:

```javascript
  async function shareWithClass(content, contentType, title) {
    var classes = teacherClasses;
    if (!classes || classes.length === 0) {
      try {
        var data = await api.listClasses();
        if (data.classes && data.classes.length > 0) {
          classes = data.classes;
          setTeacherClasses(classes);
        }
      } catch (e) { /* fall through to check below */ }
    }
    if (!classes || classes.length === 0) {
      addToast('No classes found. Sync your roster first.', 'warning');
      return;
    }
    // Single class: publish directly, no modal needed
    if (classes.length === 1) {
      try {
        var resp = await fetch('/api/publish-to-class', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: classes[0].id,
            content: content,
            content_type: contentType,
            title: title,
          }),
        });
        var result = await resp.json();
        if (result.error) {
          addToast(result.error, 'error');
        } else {
          addToast('Shared "' + title + '" with ' + classes[0].name, 'success');
        }
      } catch (err) {
        addToast('Failed to share: ' + err.message, 'error');
      }
      return;
    }
    // Multiple classes: open modal
    setShareModalContent({ content: content, contentType: contentType, title: title });
    setShareModalSelected([]);
    setShowShareModal(true);
  }
```

- [ ] **Step 3: Add executeShareWithClasses function**

Immediately after the `shareWithClass` function, add:

```javascript
  async function executeShareWithClasses() {
    if (!shareModalContent || shareModalSelected.length === 0) return;
    setShareModalSharing(true);
    var successes = 0;
    var failures = 0;
    for (var i = 0; i < shareModalSelected.length; i++) {
      try {
        var resp = await fetch('/api/publish-to-class', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: shareModalSelected[i],
            content: shareModalContent.content,
            content_type: shareModalContent.contentType,
            title: shareModalContent.title,
          }),
        });
        var result = await resp.json();
        if (result.error) {
          failures++;
        } else {
          successes++;
        }
      } catch (err) {
        failures++;
      }
    }
    setShareModalSharing(false);
    setShowShareModal(false);
    if (failures === 0) {
      addToast('Shared "' + shareModalContent.title + '" with ' + successes + ' class' + (successes === 1 ? '' : 'es'), 'success');
    } else if (successes > 0) {
      addToast('Shared with ' + successes + ' class' + (successes === 1 ? '' : 'es') + ', ' + failures + ' failed', 'warning');
    } else {
      addToast('Failed to share with any classes', 'error');
    }
  }
```

- [ ] **Step 4: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds (modal JSX not yet added, but functions are valid)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add share modal state and multi-class publish logic"
```

---

### Task 2: Add modal JSX

**Files:**
- Modify: `frontend/src/App.jsx` (add modal JSX near other modals, after the publish settings modal)

- [ ] **Step 1: Find insertion point**

In `frontend/src/App.jsx`, search for the closing `)}` of the `showPublishModal` block. The pattern is:

```
      {showPublishModal && (
        ...
      )}
```

After that block's closing `)}`, add the share modal JSX.

- [ ] **Step 2: Add modal JSX**

Insert after the publish modal's closing `)}`:

```jsx
      {/* Share with Class Modal */}
      {showShareModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px",
          }}
          onClick={() => { if (!shareModalSharing) setShowShareModal(false); }}
        >
          <div
            className="glass-card"
            style={{
              width: "100%",
              maxWidth: "440px",
              padding: "28px",
              borderRadius: "16px",
            }}
            onClick={function(e) { e.stopPropagation(); }}
          >
            <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "6px", display: "flex", alignItems: "center", gap: "10px" }}>
              <Icon name="Share2" size={22} />
              Share with Class
            </h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
              {shareModalContent ? '"' + shareModalContent.title + '"' : ''}
            </p>

            {/* Select All */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 14px",
                borderRadius: "10px",
                background: "var(--hover-bg)",
                cursor: "pointer",
                marginBottom: "8px",
                fontWeight: 600,
                fontSize: "0.9rem",
              }}
            >
              <input
                type="checkbox"
                checked={shareModalSelected.length === teacherClasses.length && teacherClasses.length > 0}
                onChange={function(e) {
                  if (e.target.checked) {
                    setShareModalSelected(teacherClasses.map(function(c) { return c.id; }));
                  } else {
                    setShareModalSelected([]);
                  }
                }}
                style={{ width: "18px", height: "18px", accentColor: "var(--primary-500)" }}
              />
              Select All ({teacherClasses.length} classes)
            </label>

            {/* Class list */}
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "300px", overflowY: "auto", marginBottom: "20px" }}>
              {teacherClasses.map(function(cls) {
                var isChecked = shareModalSelected.indexOf(cls.id) !== -1;
                var studentCount = cls.class_students && cls.class_students[0] ? cls.class_students[0].count : 0;
                return (
                  <label
                    key={cls.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      padding: "10px 14px",
                      borderRadius: "10px",
                      background: isChecked ? "rgba(99, 102, 241, 0.1)" : "transparent",
                      cursor: "pointer",
                      transition: "background 0.15s",
                      fontSize: "0.9rem",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={function() {
                        if (isChecked) {
                          setShareModalSelected(shareModalSelected.filter(function(id) { return id !== cls.id; }));
                        } else {
                          setShareModalSelected(shareModalSelected.concat([cls.id]));
                        }
                      }}
                      style={{ width: "18px", height: "18px", accentColor: "var(--primary-500)" }}
                    />
                    <span style={{ flex: 1 }}>{cls.name}</span>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{studentCount} students</span>
                  </label>
                );
              })}
            </div>

            {/* Actions */}
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                onClick={function() { setShowShareModal(false); }}
                className="btn btn-secondary"
                style={{ padding: "10px 20px" }}
                disabled={shareModalSharing}
              >
                Cancel
              </button>
              <button
                onClick={executeShareWithClasses}
                className="btn btn-primary"
                style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
                disabled={shareModalSelected.length === 0 || shareModalSharing}
              >
                {shareModalSharing ? (
                  React.createElement(React.Fragment, null,
                    React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }), " Sharing...")
                ) : (
                  React.createElement(React.Fragment, null,
                    React.createElement(Icon, { name: "Share2", size: 16 }),
                    " Share with " + shareModalSelected.length + " class" + (shareModalSelected.length === 1 ? "" : "es"))
                )}
              </button>
            </div>
          </div>
        </div>
      )}
```

- [ ] **Step 3: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 4: Manual test**

1. Generate flashcards (or any content with a "Share with Class" button)
2. Click "Share with Class"
3. Modal should appear with all 6 periods listed with checkboxes
4. Check "Select All" — all boxes should check, button should say "Share with 6 classes"
5. Uncheck one — "Select All" unchecks, button updates to "Share with 5 classes"
6. Click Share — should publish to all selected classes with success toast
7. Click outside modal or Cancel — should close without sharing

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: share-with-class multi-select modal replacing prompt()"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | State + shareWithClass logic + executeShareWithClasses | Low — replaces prompt() with modal open, single-class bypass preserved |
| 2 | Modal JSX with checkboxes, Select All, Share button | Low — follows existing modal pattern, no backend changes |

**Total: 1 modified file, 2 commits.**

**Before:** Browser `prompt()` dialog, single class only, no multi-select.
**After:** Proper modal with checkboxes, "Select All", multi-class publish with success/failure toasts.
