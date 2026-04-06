# Question Mix UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the on/off section toggles with per-type question count inputs so teachers can specify exactly how many of each question type they want.

**Architecture:** Change the `assignmentSectionCategories` state from boolean map to number map. Replace the checkbox UI with number inputs per type + an assigned/total counter. Update `_build_section_categories_prompt()` in the backend to include exact counts in the AI prompt. Same change applied to both Assignment mode (lesson planner sidebar) and Assessment Generator tab.

**Tech Stack:** React (frontend), Python/Flask (backend prompt builder)

**Spec:** `docs/superpowers/specs/2026-04-05-question-mix-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/App.jsx` | **Modify** | Replace section toggles with count inputs, update state, derive sectionCategories |
| `backend/routes/planner_routes.py` | **Modify** | Update `_build_section_categories_prompt()` to include per-type counts |
| `tests/test_question_mix.py` | **Create** | Tests for backend prompt builder with counts |

---

### Task 1: Backend — add per-type counts to prompt builder

**Files:**
- Modify: `backend/routes/planner_routes.py:122-185`
- Create: `tests/test_question_mix.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_question_mix.py`:

```python
"""Tests for question mix — per-type count instructions in prompt."""

import pytest


class TestBuildSectionCategoriesPromptWithCounts:
    def test_includes_exact_count_per_type(self):
        """When questionTypeCounts provided, prompt should say 'exactly N' per type."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True, "short_answer": True, "true_false": True}
        counts = {"multiple_choice": 4, "short_answer": 2, "true_false": 1}

        prompt = _build_section_categories_prompt(categories, subject="US History", question_type_counts=counts)

        assert "exactly 4" in prompt.lower() or "4 multiple choice" in prompt.lower()
        assert "exactly 2" in prompt.lower() or "2 short answer" in prompt.lower()
        assert "exactly 1" in prompt.lower() or "1 true" in prompt.lower()

    def test_no_counts_uses_existing_behavior(self):
        """Without counts, should use existing behavior (no exact count instructions)."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True, "short_answer": True}

        prompt = _build_section_categories_prompt(categories, subject="Math")

        assert "Multiple Choice" in prompt
        assert "Short Answer" in prompt
        # Should NOT have exact count instructions
        assert "exactly" not in prompt.lower()

    def test_zero_count_type_not_included(self):
        """Types with count=0 should not appear in the prompt."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True, "short_answer": False}
        counts = {"multiple_choice": 5, "short_answer": 0}

        prompt = _build_section_categories_prompt(categories, subject="Science", question_type_counts=counts)

        assert "Multiple Choice" in prompt
        # short_answer has count 0 and is False in categories — should not appear in enabled list

    def test_empty_counts_dict(self):
        """Empty counts dict should use existing behavior."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True}

        prompt = _build_section_categories_prompt(categories, subject="ELA", question_type_counts={})

        assert "Multiple Choice" in prompt
        assert "exactly" not in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_question_mix.py -v`
Expected: FAIL (function signature doesn't accept `question_type_counts` yet)

- [ ] **Step 3: Update `_build_section_categories_prompt()` to accept and use counts**

In `backend/routes/planner_routes.py`, modify the function signature and body at line 122:

Change:
```python
def _build_section_categories_prompt(categories, subject=''):
```

To:
```python
def _build_section_categories_prompt(categories, subject='', question_type_counts=None):
```

Then modify line 172-174 to include counts:

Change:
```python
    enabled = [k for k, v in categories.items() if v]
    lines = [f"ALLOWED section types (use ONLY the ones relevant to the topic/standards):"]
    for i, key in enumerate(enabled, 1):
        info = section_map.get(key, {})
        lines.append(f"  - {info.get('name', key)}: {info.get('instruction', '')}")
```

To:
```python
    enabled = [k for k, v in categories.items() if v]
    lines = ["ALLOWED section types (use ONLY the ones relevant to the topic/standards):"]
    for i, key in enumerate(enabled, 1):
        info = section_map.get(key, {})
        count = (question_type_counts or {}).get(key, 0)
        if count and count > 0:
            lines.append("  - " + info.get('name', key) + " (EXACTLY " + str(count) + " questions): " + info.get('instruction', ''))
        else:
            lines.append("  - " + info.get('name', key) + ": " + info.get('instruction', ''))
```

- [ ] **Step 4: Pass counts through to the prompt builder**

Find where `_build_section_categories_prompt` is called. There are two call sites:

1. In `generate_assignment_from_lesson` (~line 3372):
```python
section_prompt = _build_section_categories_prompt(section_categories, config.get('subject', ''))
```
Change to:
```python
section_prompt = _build_section_categories_prompt(
    section_categories, config.get('subject', ''),
    question_type_counts=config.get('questionTypeCounts'),
)
```

2. Search for any other call sites and update similarly.

- [ ] **Step 5: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_question_mix.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/routes/planner_routes.py tests/test_question_mix.py
git commit -m "feat: backend prompt includes exact per-type question counts"
```

---

### Task 2: Frontend — replace section toggles with count inputs (Assignment mode)

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Change `assignmentSectionCategories` from booleans to numbers**

Find (~line 1622):
```javascript
  const [assignmentSectionCategories, setAssignmentSectionCategories] = useState({
    multiple_choice: true, short_answer: true, math_computation: false,
    geometry_visual: false, graphing: false, data_analysis: false,
    extended_writing: true, vocabulary: false, true_false: false, florida_fast: false,
  });
```

Replace with:
```javascript
  const [assignmentQuestionCounts, setAssignmentQuestionCounts] = useState({
    multiple_choice: 4, short_answer: 2, math_computation: 0,
    geometry_visual: 0, graphing: 0, data_analysis: 0,
    extended_writing: 1, vocabulary: 0, true_false: 0, florida_fast: 0,
  });
```

- [ ] **Step 2: Derive sectionCategories from counts at send time**

Find where `assignmentSectionCategories` is sent to the API. There are two places:

1. Lesson plan generation (~line 4224):
```javascript
sectionCategories: unitConfig.type === "Assignment" ? assignmentSectionCategories : undefined,
```
Change to:
```javascript
sectionCategories: unitConfig.type === "Assignment" ? Object.fromEntries(Object.entries(assignmentQuestionCounts).map(function(e) { return [e[0], e[1] > 0]; })) : undefined,
questionTypeCounts: unitConfig.type === "Assignment" ? assignmentQuestionCounts : undefined,
```

2. Assignment from lesson generation (~line 4845):
```javascript
sectionCategories: assignmentSectionCategories,
```
Change to:
```javascript
sectionCategories: Object.fromEntries(Object.entries(assignmentQuestionCounts).map(function(e) { return [e[0], e[1] > 0]; })),
questionTypeCounts: assignmentQuestionCounts,
```

- [ ] **Step 3: Replace the Sections toggle UI with count inputs**

Find the Sections dropdown content (~lines 10066-10118). Replace the checkbox-based layout with number inputs:

Replace the entire `{assignmentSectionsOpen && (` block (lines 10066-10117) with:

```javascript
                              {assignmentSectionsOpen && (
                                <div style={{ padding: "10px 14px", borderTop: "1px solid var(--glass-border)" }}>
                                  {(() => {
                                    var totalAssigned = Object.values(assignmentQuestionCounts).reduce(function(a, b) { return a + b; }, 0);
                                    var totalTarget = unitConfig.totalQuestions || 10;
                                    var statusColor = totalAssigned === totalTarget ? "#22c55e" : totalAssigned > totalTarget ? "#ef4444" : "#f59e0b";
                                    return (
                                      <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "8px", color: statusColor }}>
                                        {totalAssigned + "/" + totalTarget + " assigned"}
                                        {totalAssigned < totalTarget ? " — AI will distribute " + (totalTarget - totalAssigned) + " remaining" : ""}
                                        {totalAssigned > totalTarget ? " — exceeds total by " + (totalAssigned - totalTarget) : ""}
                                      </div>
                                    );
                                  })()}
                                  {[
                                    { key: "multiple_choice", label: "Multiple Choice", group: "core" },
                                    { key: "short_answer", label: "Short Answer", group: "core" },
                                    { key: "math_computation", label: "Math Computation", group: "stem" },
                                    { key: "geometry_visual", label: "Geometry", group: "stem" },
                                    { key: "graphing", label: "Graphing", group: "stem" },
                                    { key: "data_analysis", label: "Data Analysis", group: "stem" },
                                    { key: "extended_writing", label: "Extended Writing", group: "optional" },
                                    { key: "vocabulary", label: "Vocabulary", group: "optional" },
                                    { key: "true_false", label: "True / False", group: "optional" },
                                    { key: "florida_fast", label: "FL FAST Items", group: "optional" },
                                  ].map(function(cat, idx, arr) {
                                    var prevGroup = idx > 0 ? arr[idx - 1].group : null;
                                    var showDivider = cat.group !== prevGroup;
                                    var groupLabels = { core: "Core", stem: "STEM", optional: "Optional" };
                                    var groupColors = { core: "#22c55e", stem: "#6366f1", optional: "var(--text-muted)" };
                                    var count = assignmentQuestionCounts[cat.key] || 0;
                                    return (
                                      React.createElement('div', { key: cat.key },
                                        showDivider ? React.createElement('div', {
                                          style: { fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase",
                                            letterSpacing: "0.05em", color: groupColors[cat.group],
                                            marginTop: idx > 0 ? "4px" : 0, marginBottom: "2px" }
                                        }, groupLabels[cat.group]) : null,
                                        React.createElement('div', {
                                          style: { display: "flex", alignItems: "center", justifyContent: "space-between",
                                            padding: "4px 8px", borderRadius: "6px", fontSize: "0.82rem",
                                            background: count > 0 ? "rgba(99,102,241,0.1)" : "transparent" }
                                        },
                                          React.createElement('span', { style: { color: count > 0 ? "var(--text-primary)" : "var(--text-muted)" } }, cat.label),
                                          React.createElement('input', {
                                            type: "number",
                                            min: 0,
                                            max: unitConfig.totalQuestions || 50,
                                            value: count,
                                            onChange: function(e) {
                                              var val = parseInt(e.target.value) || 0;
                                              var updated = Object.assign({}, assignmentQuestionCounts);
                                              updated[cat.key] = Math.max(0, val);
                                              setAssignmentQuestionCounts(updated);
                                            },
                                            style: { width: "50px", padding: "3px 6px", borderRadius: "6px",
                                              border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                                              color: "var(--text-primary)", fontSize: "0.82rem", textAlign: "center" }
                                          })
                                        )
                                      )
                                    );
                                  })}
                                </div>
                              )}
```

- [ ] **Step 4: Remove "Per Section (0 = auto)" field**

Find (~line 9914-9925):
```javascript
                              <div>
                                <label className="label">Per Section (0 = auto)</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={unitConfig.questionsPerSection}
                                  onChange={(e) =>
                                    setUnitConfig({
                                      ...unitConfig,
                                      questionsPerSection: parseInt(e.target.value) || 0,
                                    })
```

Remove this entire `<div>` block. Change the grid from `gridTemplateColumns: "1fr 1fr"` to `gridTemplateColumns: "1fr"` (single column for just Total Questions).

- [ ] **Step 5: Update the Sections header count**

Find (~line 10060-10061):
```javascript
                                    ({Object.values(assignmentSectionCategories).filter(Boolean).length} active)
```

Change to:
```javascript
                                    ({Object.values(assignmentQuestionCounts).filter(function(v) { return v > 0; }).length} types)
```

- [ ] **Step 6: Build and test**

```bash
cd frontend && npm run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: replace assignment section toggles with per-type question count inputs"
```

---

### Task 3: Frontend — apply same change to Assessment Generator

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Find the Assessment Generator section categories UI**

Search for the assessment config section categories. It's in the Assessment Generator tab, not the lesson planner sidebar. Find where `assessmentConfig.sectionCategories` is rendered as toggles.

- [ ] **Step 2: Apply the same count input pattern**

Replace the assessment section category toggles with the same number input layout used in Task 2. The state is `assessmentConfig.sectionCategories` — change the values from booleans to numbers.

Update `assessmentConfig` default state (~line 1747):
```javascript
sectionCategories: {
  multiple_choice: 6,
  short_answer: 4,
  math_computation: 3,
  geometry_visual: 2,
  graphing: 2,
  data_analysis: 2,
  extended_writing: 0,
  vocabulary: 0,
  true_false: 0,
  florida_fast: 0,
},
```

Derive boolean categories at send time (same pattern as Task 2).

- [ ] **Step 3: Pass `questionTypeCounts` in the assessment generation API call**

Find the assessment generation call (~line 4356) and add `questionTypeCounts`:
```javascript
questionTypeCounts: Object.fromEntries(
  Object.entries(assessmentConfig.sectionCategories).filter(function(e) { return e[1] > 0; })
),
```

- [ ] **Step 4: Build and test**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: apply per-type question counts to Assessment Generator tab"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Backend: add counts to prompt builder + 4 tests | Modify `planner_routes.py`, create `test_question_mix.py` | Low — additive change, backward compatible |
| 2 | Frontend: replace assignment section toggles with count inputs | Modify `App.jsx` | Medium — UI replacement |
| 3 | Frontend: apply same to Assessment Generator | Modify `App.jsx` | Medium — UI replacement |

**Total: 1 backend function update, 2 UI replacements, 4 tests.**

**Before:** Teacher toggles "Multiple Choice" and "Short Answer" on, AI decides how many of each.
**After:** Teacher sets "4 Multiple Choice, 2 Short Answer, 1 True/False" — AI generates exactly that mix.
