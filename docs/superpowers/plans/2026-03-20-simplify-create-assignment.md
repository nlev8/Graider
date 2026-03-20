# Simplify Create Assignment from Lesson Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the "Create Assignment" flow from lesson plans by reducing the type dropdown from 6 options (worksheet/quiz/homework/project/essay/lab) to 3 meaningful options (Assignment/Project/Essay), passing reference documents and selected standards to the generation prompt, and ensuring the Publish button is visible on generated output.

**Architecture:** Simplify the frontend dropdown to 3 options and backend `type_instructions` to match. Remove redundant types (worksheet=Assignment, quiz=redundant, homework=redundant, lab=can't grade in portal). Use the section toggles to control format within each type. Extend the backend prompt to include reference documents and standards. The Publish button already exists in the generated assignment section.

**Tech Stack:** Python/Flask, React

**Spec:** `docs/superpowers/specs/2026-03-20-content-types-accommodations-assets-design.md`

---

## Task 1: Simplify the type dropdown to 3 options

**File:** `frontend/src/tabs/PlannerTab.jsx`

### Step 1.1: Update the `assignmentType` state default

- [ ] At line 455, change the default from `"worksheet"` to `"assignment"`:
```javascript
const [assignmentType, setAssignmentType] = useState("assignment");
```

### Step 1.2: Reduce the `<select>` dropdown to 3 options

- [ ] At lines 3202-3242, keep the `<div>` containing the `<select>` and button, but reduce the options from 6 to 3. Remove worksheet (redundant with Assignment), quiz (redundant), homework (redundant), and lab (can't grade in portal).

**Find the `<select>` options:**
```jsx
    <option value="worksheet">Worksheet</option>
    <option value="quiz">Quiz</option>
    <option value="homework">Homework</option>
    <option value="project">Project</option>
    <option value="essay">Essay</option>
    <option value="lab">Lab Activity</option>
```

**Replace with:**
```jsx
    <option value="assignment">Assignment</option>
    <option value="project">Project</option>
    <option value="essay">Essay</option>
```

### Step 1.3: Update the success toast message

- [ ] At line 1802, the toast uses `assignmentType` to display the type name. This still works with the 3 remaining types, but update the fallback:
```javascript
`${assignmentType.charAt(0).toUpperCase() + assignmentType.slice(1)} generated from lesson!`,
```
No change needed — the existing code works with "assignment", "project", and "essay" values.

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
Replace with (keep `assignmentType` arg, add `standards` and `referenceDocs` to config):
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
  assignmentType,
);
```
Note: `selectedStandards`, `standards`, `uploadedDocs`, and `globalAINotes` are all already in scope within PlannerTab.

### Step 2.2: Update the API service function default value

**File:** `frontend/src/services/api.js`

- [ ] At lines 340-345, update the function to change the default `assignmentType` from `'worksheet'` to `'assignment'`:
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
export async function generateAssignmentFromLesson(lessonPlan, config, assignmentType = 'assignment') {
  track('assignment_from_lesson_generated', { assignment_type: assignmentType })
  return fetchApi('/api/generate-assignment-from-lesson', {
    method: 'POST',
    body: JSON.stringify({ lessonPlan, config, assignmentType }),
  })
}
```

---

## Task 3: Update the backend to use standards, reference docs, and simplified type instructions

**File:** `backend/routes/planner_routes.py`

### Step 3.1: Update `assignment_type` default and accept new fields

- [ ] At line 3143, update the default from `'worksheet'` to `'assignment'`:
```python
assignment_type = data.get('assignmentType', 'assignment')  # assignment, project, essay
```
After the existing `config` extraction at line 3142, add extraction for the new fields:
```python
config_standards = config.get('standards', [])
reference_docs = config.get('referenceDocs', [])
global_ai_notes = config.get('globalAINotes', '')
```

### Step 3.2: Reduce the `type_instructions` dict to 3 entries

- [ ] At lines 3197-3206, replace the 6-entry `type_instructions` dict with 3 entries matching the simplified dropdown:
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
Replace with:
```python
type_instructions = {
    'assignment': "Create an assignment with a MIX of question types based on the section categories specified below. Use the section toggles to determine format — if multiple choice is enabled, include MC questions; if extended writing is enabled, include essay/written response questions; etc.",
    'project': "Create a multi-day project assignment with clear requirements, milestones, and a rubric. Include specific deliverables and evaluation criteria.",
    'essay': "Create an essay prompt with a clear thesis question, required length, and grading criteria. Include pre-writing guidance and evaluation rubric."
}

type_instruction = type_instructions.get(assignment_type, type_instructions['assignment'])
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

### Step 3.7: Keep `assignment_type` references in the prompt template

No changes needed — the prompt template at line 3301 (`ASSIGNMENT TYPE: {assignment_type.title()}`) and line 3351 (`"type": "{assignment_type}"`) will now correctly use the 3 valid values: "assignment", "project", or "essay".

### Step 3.8: Add globalAINotes to the prompt

- [ ] At lines 3470-3473, there is already a block for `config.get('globalAINotes')`. This will now be populated because we pass `globalAINotes` in the config from the frontend (Step 2.1). No backend edit needed here — the existing template already handles it.

### Step 3.9: Keep the mock fallback references

No changes needed — the mock fallback at line 3507 (`"title": f"{assignment_type.title()} - ..."`) and line 3508 (`"type": assignment_type`) will correctly use the 3 valid values.

---

## Task 4: Verify Publish button works on generated assignment and preserve conditional guard

**Mostly verification** — one important constraint to preserve.

### Step 4.0: Preserve the conditional guard around Create button

- [ ] **IMPORTANT:** The `{(!lessonPlan.sections || lessonPlan.days) && !lessonPlan.phases && (...)}` wrapper around the Create Assignment button (and dropdown) MUST remain in place. This guard ensures the Create button only appears for appropriate lesson plan types. Do NOT remove this wrapper when simplifying the dropdown in Task 1 Step 1.2.

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

## Task 5: Address `assignmentType` references in App.jsx

**File:** `frontend/src/App.jsx`

### Step 5.1: Audit `assignmentType` references in App.jsx

- [ ] Search for `assignmentType` in `frontend/src/App.jsx` (known at lines 1540, 4816, 4824, 10850). Determine whether these are:
  - **Dead code** — PlannerTab.jsx is the active component and App.jsx may have legacy duplicates from before the tab was extracted. If so, remove the dead references.
  - **Active code** — If App.jsx still has an active assignment generation flow, update the dropdown options and default to match the simplified 3-option set (`assignment`, `project`, `essay`).

### Step 5.2: Update or remove based on audit

- [ ] If the references are in active code paths (e.g., App.jsx has its own `assignmentType` state and dropdown for a non-Planner flow):
  - Update `useState("worksheet")` to `useState("assignment")`
  - Update any `<select>` options to match the 3 simplified options
  - Update any `type_instructions` or label references

- [ ] If the references are dead code (duplicated from before PlannerTab extraction):
  - Remove the `assignmentType` state declaration
  - Remove any `<select>` dropdown that uses it
  - Remove any handler references to it
  - Verify the build still passes after removal

---

## Task 6: Build, test, verify

### Step 6.1: Build the frontend

- [ ] Run `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
- [ ] Verify no build errors

### Step 6.2: Start the backend and test

- [ ] Run `source /Users/alexc/Downloads/Graider/venv/bin/activate && cd /Users/alexc/Downloads/Graider && python -m backend.app`
- [ ] Navigate to the Planner tab
- [ ] Verify the type dropdown shows 3 options: "Assignment", "Project", "Essay"
- [ ] Verify "Assignment" is selected by default
- [ ] Verify the section category toggles (MC, Short Answer, etc.) still appear and function

### Step 6.3: Test assignment generation without standards/docs

- [ ] Generate a lesson plan, then click "Create Assignment"
- [ ] Verify it generates successfully with section categories controlling format
- [ ] Verify the success toast says "Assignment generated from lesson!"

### Step 6.4: Test assignment generation with standards and reference docs

- [ ] Upload a reference document in the Planner tab
- [ ] Select at least one standard
- [ ] Generate a lesson plan, then click "Create Assignment"
- [ ] Verify the generated assignment references content from the uploaded doc
- [ ] Verify questions align to the selected standards

### Step 6.5: Test Publish flow end-to-end

- [ ] On a generated assignment, click "Publish to Portal"
- [ ] Verify the publish modal opens with time limit pre-filled
- [ ] Publish and verify a join code is generated
- [ ] Open the join code URL and verify the assignment renders for students

---

## Summary of files changed

| File | Changes |
|------|---------|
| `frontend/src/tabs/PlannerTab.jsx` | Simplify `assignmentType` state default to `"assignment"`, reduce `<select>` dropdown to 3 options, pass `standards`/`referenceDocs`/`globalAINotes` in API call |
| `frontend/src/services/api.js` | Update `assignmentType` default from `'worksheet'` to `'assignment'` in `generateAssignmentFromLesson()` |
| `frontend/src/App.jsx` | Audit and update/remove `assignmentType` references (lines 1540, 4816, 4824, 10850) — dead code removal or update to match simplified options |
| `backend/routes/planner_routes.py` | Update `assignment_type` default, reduce `type_instructions` dict to 3 entries, accept `standards`/`referenceDocs`/`globalAINotes`, add standards and reference docs to prompt |
