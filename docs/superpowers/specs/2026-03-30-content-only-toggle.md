# "Only Create Questions from Uploaded Content" Toggle — Proposed Code Edits

## Problem

When a teacher uploads resources AND selects standards, the AI generates questions to cover the full standard scope — including content the teacher may not have taught. Teachers want questions only from what they actually taught.

## Solution

A checkbox toggle: **"Only create questions from uploaded content"**
- Appears when both resources and standards are present
- When checked: AI uses standards for DOK levels and formatting, but every question must be answerable from the uploaded documents
- When unchecked: current behavior (standards-driven, resources supplementary)
- Available in both assignment and assessment generation flows

---

## Frontend Changes

### File: `frontend/src/tabs/PlannerTab.jsx`

**Step 1: Add state variable**

Find near existing state declarations (around line 455):
```javascript
const [contentOnlyMode, setContentOnlyMode] = useState(false);
```

**Step 2: Add checkbox in assignment flow (sidebar, near the Create button)**

Find the section categories area (before the Create button, around line 2640). Add after the document upload section, only visible when both docs and standards exist:

```jsx
{uploadedDocs.length > 0 && selectedStandards.length > 0 && (
  <label style={{
    display: "flex", alignItems: "center", gap: "8px",
    fontSize: "0.85rem", color: "var(--text-secondary)",
    padding: "8px 0", cursor: "pointer",
  }}>
    <input
      type="checkbox"
      checked={contentOnlyMode}
      onChange={(e) => setContentOnlyMode(e.target.checked)}
    />
    Only create questions from uploaded content
  </label>
)}
```

**Step 3: Pass flag in assignment generation**

Find `generateAssignmentFromLessonHandler` (around line 1180). Where it builds the config object for `api.generateAssignmentFromLesson`, add:

```javascript
contentOnly: contentOnlyMode && uploadedDocs.length > 0,
```

to the config object being sent.

**Step 4: Add checkbox in assessment flow**

Find the assessment configuration area (around line 4960, near the "Generate Assessment" button). Add the same checkbox:

```jsx
{(uploadedDocs.length > 0 || selectedSources.length > 0) && selectedStandards.length > 0 && (
  <label style={{
    display: "flex", alignItems: "center", gap: "8px",
    fontSize: "0.85rem", color: "var(--text-secondary)",
    padding: "8px 0", cursor: "pointer",
  }}>
    <input
      type="checkbox"
      checked={contentOnlyMode}
      onChange={(e) => setContentOnlyMode(e.target.checked)}
    />
    Only create questions from uploaded content
  </label>
)}
```

**Step 5: Pass flag in assessment generation**

Find `generateAssessmentHandler` (around line 1411). Where it calls `api.generateAssessment`, add `contentOnly: contentOnlyMode` to the config object.

**Step 6: Reset toggle when docs cleared**

Find where `uploadedDocs` is cleared (search for `setUploadedDocs([])`). Add `setContentOnlyMode(false)` alongside each clear.

---

## Backend Changes

### File: `backend/routes/planner_routes.py`

**Step 1: Assignment generation — read the flag and modify prompt**

Find `generate_assignment_from_lesson()` (around line 3266). After `reference_docs = config.get('referenceDocs', [])` (line 3285), add:

```python
content_only = config.get('contentOnly', False)
```

Then modify the `ref_docs_block` section (around line 3427). The current code already has two branches (standards active vs not). Add a third branch for `content_only`:

Replace the current ref_docs_block logic with:

```python
ref_docs_block = ""
if reference_docs:
    if content_only and config_standards:
        # Standards selected BUT teacher wants questions ONLY from their content
        ref_docs_block = "\n=== SOURCE DOCUMENTS (create ALL questions from this content) ===\n"
        ref_docs_block += "CRITICAL: The teacher has selected standards for structure and DOK levels, "
        ref_docs_block += "but wants ALL questions to come directly from the content in these documents. "
        ref_docs_block += "Every question must be answerable using ONLY information found in these documents. "
        ref_docs_block += "Use the standards to guide question format, rigor level (DOK), and cognitive demand — "
        ref_docs_block += "but do NOT create questions about topics not covered in the documents.\n\n"
        for doc in reference_docs:
            doc_name = doc.get('filename', 'Document')
            doc_text = doc.get('text', '')[:6000]
            ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
    elif config_standards:
        # Standards active, resources supplementary (current behavior)
        ref_docs_block = "\n=== REFERENCE DOCUMENTS (supplementary content for question context) ===\n"
        for doc in reference_docs:
            doc_name = doc.get('filename', 'Document')
            doc_text = doc.get('text', '')[:6000]
            ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
        ref_docs_block += "Use the content, vocabulary, examples, and concepts from these reference documents when creating questions, while aligning to the standards above.\n"
    else:
        # NO standards — create questions ONLY from the uploaded resources
        ref_docs_block = "\n=== SOURCE DOCUMENTS (create ALL questions from this content) ===\n"
        ref_docs_block += "CRITICAL: Since no curriculum standards are selected, generate ALL questions directly from the content in these documents. "
        ref_docs_block += "Every question must be answerable using information found in these documents. "
        ref_docs_block += "Do NOT create questions about topics not covered in the documents.\n\n"
        for doc in reference_docs:
            doc_name = doc.get('filename', 'Document')
            doc_text = doc.get('text', '')[:6000]
            ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
```

**Step 2: Assessment generation — read the flag and modify prompt**

Find `generate_assessment()` (around line 5390). After reading the config, add:

```python
content_only = config.get('contentOnly', False)
```

Find where the content sources are injected into the prompt. Add similar logic — if `content_only` is True and sources exist, instruct the AI to generate questions only from the source content while using standards for DOK/format.

---

## What Changes for the Teacher

| Scenario | Toggle | Behavior |
|----------|--------|----------|
| Resources + standards, toggle OFF | Unchecked | Current behavior — standards-driven, resources supplementary |
| Resources + standards, toggle ON | Checked | Questions only from documents, standards used for DOK/format |
| Resources only, no standards | N/A (hidden) | Already handled — questions only from documents |
| Standards only, no resources | N/A (hidden) | Already handled — standards-driven generation |

## No Database Changes

The `contentOnly` flag is sent per-request in the API call. It's not stored anywhere — it's a generation-time preference, not a persistent setting.
