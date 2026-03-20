# Simplify Create Assignment from Lesson Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the "Create Assignment" flow from lesson plans by removing the type dropdown (worksheet/quiz/homework/project/essay/lab), using a single "Create Assignment" button, passing reference documents and selected standards to the generation prompt, and ensuring the Publish button is visible on generated output.

**Architecture:** Remove the frontend dropdown and backend type_instructions branching. Use the section toggles to control format. Extend the backend prompt to include reference documents and standards. The Publish button already exists in the generated assignment section.

**Tech Stack:** Python/Flask, React

**Spec:** `docs/superpowers/specs/2026-03-20-content-types-accommodations-assets-design.md`

---

## Task 1: Remove the type dropdown from the frontend

**File:** `frontend/src/tabs/PlannerTab.jsx`

### Step 1.1: Remove the `assignmentType` state variable

- [ ] At line 455, delete the state declaration:
```javascript
const [assignmentType, setAssignmentType] = useState("worksheet");
```

### Step 1.2: Remove the `<select>` dropdown from the UI

- [ ] At lines 3202-3242, replace the `<div>` containing the `<select>` and button with just the button. The current code:
```jsx
<div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
  <select
    value={assignmentType}
    onChange={(e) =>
      setAssignmentType(e.target.value)
    }
    className="input"
    style={{
      padding: "8px 12px",
      minWidth: "120px",
    }}
  >
    <option value="worksheet">Worksheet</option>
    <option value="quiz">Quiz</option>
    <option value="homework">Homework</option>
    <option value="project">Project</option>
    <option value="essay">Essay</option>
    <option value="lab">Lab Activity</option>
  </select>
  <button
    onClick={generateAssignmentFromLessonHandler}
    className="btn btn-primary"
    disabled={assignmentLoading}
  >
    {assignmentLoading ? (
      <>
        <Icon
          name="Loader"
          size={16}
          className="spinning"
        />{" "}
        Generating...
      </>
    ) : (
      <>
        <Icon name="FileText" size={16} /> Create
        Assignment
      </>
    )}
  </button>
</div>
```
Replace with (remove the wrapping `<div>` and `<select>`, keep only the button):
```jsx
<button
  onClick={generateAssignmentFromLessonHandler}
  className="btn btn-primary"
  disabled={assignmentLoading}
>
  {assignmentLoading ? (
    <>
      <Icon
        name="Loader"
        size={16}
        className="spinning"
      />{" "}
      Generating...
    </>
  ) : (
    <>
      <Icon name="FileText" size={16} /> Create Assignment
    </>
  )}
</button>
```

### Step 1.3: Update the success toast message

- [ ] At line 1802, the toast uses `assignmentType` to display the type name:
```javascript
`${assignmentType.charAt(0).toUpperCase() + assignmentType.slice(1)} generated from lesson!`,
```
Replace with a static message:
```javascript
"Assignment generated from lesson!",
```

---

## Task 2: Update `generateAssignmentFromLessonHandler` to pass standards and reference docs

**File:** `frontend/src/tabs/PlannerTab.jsx`

### Step 2.1: Add `selectedStandards` and `uploadedDocs` to the API call

- [ ] At lines 1783-1795, the handler currently calls:
```javascript
const data = await api.generateAssignmentFromLesson(
  lessonPlan,
  {
    grade: config.grade_level,
    subject: config.subject,
    availableTools: config.availableTools || [],
    sectionCategories: assignmentSectionCategories,
    totalQuestions: unitConfig.totalQuestions,
    questionsPerSection: unitConfig.questionsPerSection,
    requirements: unitConfig.requirements || "",
  },
  assignmentType,
);
```
Replace with (remove `assignmentType` arg, add `standards` and `referenceDocs` to config):
```javascript
const fullStandards = selectedStandards.map((code) => {
  return standards.find((s) => s.code === code) || { code, benchmark: code };
});
const data = await api.generateAssignmentFromLesson(
  lessonPlan,
  {
    grade: config.grade_level,
    subject: config.subject,
    availableTools: config.availableTools || [],
    sectionCategories: assignmentSectionCategories,
    totalQuestions: unitConfig.totalQuestions,
    questionsPerSection: unitConfig.questionsPerSection,
    requirements: unitConfig.requirements || "",
    standards: fullStandards,
    referenceDocs: uploadedDocs,
    globalAINotes: globalAINotes,
  },
);
```
Note: `selectedStandards`, `standards`, `uploadedDocs`, and `globalAINotes` are all already in scope within PlannerTab.

### Step 2.2: Update the API service function signature

**File:** `frontend/src/services/api.js`

- [ ] At lines 340-345, update the function to remove the `assignmentType` parameter:
```javascript
export async function generateAssignmentFromLesson(lessonPlan, config, assignmentType = 'worksheet') {
  track('assignment_from_lesson_generated', { assignment_type: assignmentType })
  return fetchApi('/api/generate-assignment-from-lesson', {
    method: 'POST',
    body: JSON.stringify({ lessonPlan, config, assignmentType }),
  })
}
```
Replace with:
```javascript
export async function generateAssignmentFromLesson(lessonPlan, config) {
  track('assignment_from_lesson_generated')
  return fetchApi('/api/generate-assignment-from-lesson', {
    method: 'POST',
    body: JSON.stringify({ lessonPlan, config }),
  })
}
```

---

## Task 3: Update the backend to use standards, reference docs, and a single generic prompt

**File:** `backend/routes/planner_routes.py`

### Step 3.1: Accept new fields from the request

- [ ] At line 3143, remove the `assignment_type` extraction:
```python
assignment_type = data.get('assignmentType', 'worksheet')  # worksheet, quiz, project, homework
```
Delete this line entirely. Instead, after the existing `config` extraction at line 3142, add extraction for the new fields:
```python
config_standards = config.get('standards', [])
reference_docs = config.get('referenceDocs', [])
global_ai_notes = config.get('globalAINotes', '')
```

### Step 3.2: Remove the `type_instructions` dict and replace with a generic instruction

- [ ] At lines 3197-3206, delete the `type_instructions` dict and the `type_instruction` lookup:
```python
type_instructions = {
    'worksheet': "Create a practice worksheet with a MIX of question types: ...",
    'quiz': "Create a quiz with multiple choice, true/false, ...",
    'project': "Create a creative project assignment ...",
    'homework': "Create a homework assignment that reinforces ...",
    'essay': "Create an essay prompt with a clear thesis ...",
    'lab': "Create a lab activity or investigation ..."
}

type_instruction = type_instructions.get(assignment_type, type_instructions['worksheet'])
```
Replace with a single generic instruction:
```python
type_instruction = "Create an assignment with an appropriate mix of question types based on the section categories specified below. Use the section toggles to determine format — if multiple choice is enabled, include MC questions; if extended writing is enabled, include essay/written response questions; etc."
```

### Step 3.3: Update the STEM branch to not reference `type_instruction` dict

- [ ] At lines 3208-3209, the STEM check appends to `type_instruction`. This line remains unchanged — it still appends STEM-specific guidance to the generic instruction. No edit needed.

### Step 3.4: Build standards text block for the prompt

- [ ] After the `subject_boundary` call at line 3279-3280, add a standards block (following the same pattern used in the brainstorm handler at lines 2546-2548):
```python
# Build standards text block
standards_text = ""
if config_standards:
    standards_text = "\nSTANDARDS TO ASSESS (align questions to these standards):"
    for i, s in enumerate(config_standards, 1):
        if isinstance(s, dict):
            code = s.get('code', '')
            benchmark = s.get('benchmark', '')
            standards_text += f"\n{i}. {code}: {benchmark}"
        else:
            standards_text += f"\n{i}. {s}"
```

### Step 3.5: Build reference documents block for the prompt

- [ ] Immediately after the standards block from Step 3.4, add a reference docs block (following the same pattern used in the lesson plan handler at lines 2750-2758):
```python
# Build reference documents block
ref_docs_block = ""
if reference_docs:
    ref_docs_block = "\n=== REFERENCE DOCUMENTS (use this content to inform questions) ===\n"
    for doc in reference_docs:
        doc_name = doc.get('filename', 'Document')
        doc_text = doc.get('text', '')[:6000]
        ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
    ref_docs_block += "Use the content, vocabulary, examples, and concepts from these reference documents when creating questions.\n"
```

### Step 3.6: Insert standards and reference docs into the prompt

- [ ] In the prompt string (lines 3282-3476), add the standards and reference docs blocks. After the `{tools_instruction}` line (line 3284), insert:
```python
{standards_text}
{ref_docs_block}
```

### Step 3.7: Replace `assignment_type` references in the prompt template

- [ ] At line 3301, replace:
```python
ASSIGNMENT TYPE: {assignment_type.title()}
```
with:
```python
ASSIGNMENT TYPE: Assignment
```

- [ ] At line 3351, the JSON template has `"type": "{assignment_type}"`. Replace with:
```python
"type": "assignment",
```

### Step 3.8: Add globalAINotes to the prompt

- [ ] At lines 3470-3473, there is already a block for `config.get('globalAINotes')`. This will now be populated because we pass `globalAINotes` in the config from the frontend (Step 2.1). No backend edit needed here — the existing template already handles it.

### Step 3.9: Update the mock fallback to remove `assignment_type` references

- [ ] At line 3507, the mock fallback uses `assignment_type` in the title:
```python
"title": f"{assignment_type.title()} - {lesson_plan.get('title', 'Lesson')}",
```
Replace with:
```python
"title": f"Assignment - {lesson_plan.get('title', 'Lesson')}",
```

- [ ] At line 3508, the mock fallback sets `"type": assignment_type`. Replace with:
```python
"type": "assignment",
```

---

## Task 4: Verify Publish button works on generated assignment

**No code changes needed** — verification only.

### Step 4.1: Confirm `getActiveAssignment()` returns `generatedAssignment`

- [ ] At lines 1817-1818, `getActiveAssignment()` checks `generatedAssignment` first:
```javascript
const getActiveAssignment = () => {
    if (generatedAssignment) return generatedAssignment;
```
This means when a generated assignment exists, it will be returned to `publishAssessmentHandler` at line 1484. Confirmed working.

### Step 4.2: Confirm the Publish button is rendered for generated assignments

- [ ] At lines 3739-3748, the Publish button is rendered inside the `generatedAssignment` display section and calls `publishAssessmentHandler`. This button is already visible and functional. Confirmed working.

### Step 4.3: Manual test the full flow

- [ ] Generate a lesson plan with standards selected and reference docs uploaded
- [ ] Click "Create Assignment" (no dropdown)
- [ ] Verify the generated assignment includes content aligned to standards
- [ ] Verify the generated assignment uses reference doc content
- [ ] Click "Publish to Portal" on the generated assignment
- [ ] Verify the publish modal opens and functions correctly
- [ ] Submit as a student and verify grading works

---

## Task 5: Build, test, verify

### Step 5.1: Build the frontend

- [ ] Run `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
- [ ] Verify no build errors

### Step 5.2: Start the backend and test

- [ ] Run `source /Users/alexc/Downloads/Graider/venv/bin/activate && cd /Users/alexc/Downloads/Graider && python -m backend.app`
- [ ] Navigate to the Planner tab
- [ ] Verify the type dropdown is gone and only the "Create Assignment" button appears
- [ ] Verify the section category toggles (MC, Short Answer, etc.) still appear and function

### Step 5.3: Test assignment generation without standards/docs

- [ ] Generate a lesson plan, then click "Create Assignment"
- [ ] Verify it generates successfully with section categories controlling format
- [ ] Verify the success toast says "Assignment generated from lesson!"

### Step 5.4: Test assignment generation with standards and reference docs

- [ ] Upload a reference document in the Planner tab
- [ ] Select at least one standard
- [ ] Generate a lesson plan, then click "Create Assignment"
- [ ] Verify the generated assignment references content from the uploaded doc
- [ ] Verify questions align to the selected standards

### Step 5.5: Test Publish flow end-to-end

- [ ] On a generated assignment, click "Publish to Portal"
- [ ] Verify the publish modal opens with time limit pre-filled
- [ ] Publish and verify a join code is generated
- [ ] Open the join code URL and verify the assignment renders for students

---

## Summary of files changed

| File | Changes |
|------|---------|
| `frontend/src/tabs/PlannerTab.jsx` | Remove `assignmentType` state, remove `<select>` dropdown, pass `standards`/`referenceDocs`/`globalAINotes` in API call, update toast message |
| `frontend/src/services/api.js` | Remove `assignmentType` parameter from `generateAssignmentFromLesson()` |
| `backend/routes/planner_routes.py` | Remove `assignment_type` extraction and `type_instructions` dict, accept `standards`/`referenceDocs`/`globalAINotes`, add standards and reference docs to prompt, update mock fallback |
