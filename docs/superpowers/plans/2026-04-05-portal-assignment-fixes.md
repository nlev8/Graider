# Student Portal Assignment Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three bugs: (1) assignments showing blank screen in student portal, (2) button text showing "Assessment" for assignments, (3) publish modal text too dark.

**Root Cause Analysis:**

**Bug 1 (blank screen):** Backend `student_portal_routes.py` line 455 checks `if content_type and content_type != 'assessment'` — this catches assignments too (`content_type: 'assignment'`), routing them to the material response format (no sections, no questions). The student portal receives data without sections, QuestionPlayer has no questions, renders null → blank screen.

**Bug 2 (wrong button text):** Frontend `StudentPortal.jsx` line 434 checks `assessment?.sections` to decide button text, but since the backend returns the material format for assignments (no sections field), the check fails and it shows "Start Assessment." Also, the name stage button (line 434) and assessment stage should use `content_type` to differentiate, not the presence of sections.

**Bug 3 (modal contrast):** Publish modal uses hardcoded dark background `#1a1a2e` with form elements styled for dark theme. Labels and inputs are unreadable.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/student_portal_routes.py` | **Modify** | Fix content_type routing + include content_type in response |
| `frontend/src/components/StudentPortal.jsx` | **Modify** | Fix button text, handle content_type properly |
| `frontend/src/App.jsx` | **Modify** | Fix publish modal colors |

---

### Task 1: Fix backend routing — assignments should return sections, not material format

**Files:**
- Modify: `backend/routes/student_portal_routes.py:454-455`

**The fix:** Change line 455 to only route actual study material types to the material response. Assignments (and any other gradable content) should fall through to the sections response.

- [ ] **Step 1: Fix the content_type routing**

In `backend/routes/student_portal_routes.py`, find line 454-455:

```python
        content_type = settings.get('content_type') or assessment.get('content_type')
        if content_type and content_type != 'assessment':
```

Replace with:

```python
        content_type = settings.get('content_type') or assessment.get('content_type')
        # Only study materials get the material response format.
        # Assignments and assessments both get the sections/questions format.
        material_types = ('study_guide', 'flashcards', 'slide_deck', 'mind_map',
                          'audio_overview', 'video_overview', 'infographic', 'data_table')
        if content_type and content_type in material_types:
```

- [ ] **Step 2: Include content_type in the sections response**

In the same file, find line 502-517 (the return jsonify block for assessments). Add `content_type` to the settings:

Change:
```python
            "settings": {
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
                "is_makeup": is_makeup,
                "restricted_students": restricted_students,
                "period": settings.get('period', ''),
            },
```

To:
```python
            "settings": {
                "content_type": content_type or 'assessment',
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
                "is_makeup": is_makeup,
                "restricted_students": restricted_students,
                "period": settings.get('period', ''),
            },
```

- [ ] **Step 3: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "fix: assignments return sections format, not material format in student portal"
```

---

### Task 2: Fix frontend — button text and content type handling

**Files:**
- Modify: `frontend/src/components/StudentPortal.jsx`

- [ ] **Step 1: Fix the name stage button text (line 434)**

Find:
```javascript
              {assessment?.sections ? "Start Assignment" : "Start Assessment"} <Icon name="ArrowRight" />
```

Replace with:
```javascript
              {(assessment?.settings?.content_type === 'assignment') ? "Start Assignment" : "Start Assessment"} <Icon name="ArrowRight" />
```

- [ ] **Step 2: Build and test**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/StudentPortal.jsx
git commit -m "fix: button text uses content_type to show Start Assignment vs Start Assessment"
```

---

### Task 3: Fix publish modal contrast

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Make publish modal background white with dark text**

Find the publish modal container style (search for `showPublishModal`). The modal `<div>` inner container should use:

```javascript
background: "#ffffff",
color: "#1e293b",
border: "1px solid #e2e8f0",
boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.3)",
```

- [ ] **Step 2: Fix toggle button colors for light background**

The Assessment/Assignment toggle buttons use dark-theme colors (`var(--glass-border)`, `var(--glass-bg)`, light purple/green text). Replace with light-background colors:

Assessment button (selected):
```javascript
border: "2px solid #8b5cf6"
background: "rgba(139, 92, 246, 0.1)"
color: "#7c3aed"
```

Assessment button (unselected):
```javascript
border: "1px solid #e2e8f0"
background: "#f8fafc"
color: "#64748b"
```

Assignment button (selected):
```javascript
border: "2px solid #22c55e"
background: "rgba(34, 197, 94, 0.1)"
color: "#16a34a"
```

Formative button (selected):
```javascript
border: "2px solid #22c55e"
background: "rgba(34, 197, 94, 0.1)"
color: "#16a34a"
```

Summative button (selected):
```javascript
border: "2px solid #ef4444"
background: "rgba(239, 68, 68, 0.1)"
color: "#dc2626"
```

All unselected buttons:
```javascript
border: "1px solid #e2e8f0"
background: "#f8fafc"
color: "#64748b"
```

- [ ] **Step 3: Fix label colors**

Find the `Publish to Class (optional)` label and other labels in the modal. The `className="label"` should work on a white background. If any labels use inline `color` styles with dark-theme values, change them to `#374151`.

- [ ] **Step 4: Build and test**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "fix: publish modal uses light background with readable text contrast"
```

---

## Verification

After all fixes:

1. Publish an ASSIGNMENT via join code
2. Go to `/join/CODE` in incognito
3. Should see title + "Start Assignment" button (not "Start Assessment")
4. Click Start → should show questions (not blank screen)
5. Publish an ASSESSMENT via join code → should still say "Start Assessment" and work normally
6. Open publish modal → all text should be readable on white background

Run: `python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -m "not live"` — should pass with 0 failures.

---

## Summary

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Blank screen | Backend routes `content_type: 'assignment'` to material format (no sections) | Whitelist material types instead of blacklisting 'assessment' |
| Wrong button text | Checks `sections` existence instead of `content_type` | Use `settings.content_type` |
| Dark modal text | Hardcoded `#1a1a2e` background with dark-theme form elements | White background + light-theme colors |
