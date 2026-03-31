# "Only Create Questions from Uploaded Content" Toggle — SHIPPED

**Status:** Implemented and deployed (commit `ed1656f`)

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

Find the section categories area (before the Create button, around line 2640). Add after the document upload section. Visible whenever docs exist — behavior changes based on whether standards are also selected:

```jsx
{uploadedDocs.length > 0 && (
  <label style={{
    display: "flex", alignItems: "center", gap: "8px",
    fontSize: "0.85rem", color: "var(--text-secondary)",
    padding: "8px 0", cursor: selectedStandards.length > 0 ? "pointer" : "default",
    opacity: selectedStandards.length > 0 ? 1 : 0.7,
  }}>
    <input
      type="checkbox"
      checked={selectedStandards.length === 0 ? true : contentOnlyMode}
      onChange={(e) => setContentOnlyMode(e.target.checked)}
      disabled={selectedStandards.length === 0}
    />
    {selectedStandards.length === 0
      ? "Questions will come from uploaded content (no standards selected)"
      : "Only create questions from uploaded content"}
  </label>
)}
```

When no standards are selected: checkbox is checked and disabled with explanatory text — the teacher can see that content-only mode is automatic. When standards ARE selected: checkbox is interactive.

**Step 3: Pass flag in assignment generation (gated on docs AND sources)**

Both assignment and assessment payloads use identical gating:

```javascript
contentOnly: contentOnlyMode && (uploadedDocs.length > 0 || selectedSources.length > 0),
```

This is already shipped in both lines 1224 and 1464 of `PlannerTab.jsx`.

**Step 4: Add checkbox in assessment flow**

Find the assessment configuration area (around line 4960, near the "Generate Assessment" button). Add the same checkbox:

```jsx
{(uploadedDocs.length > 0 || selectedSources.length > 0) && (
  <label style={{
    display: "flex", alignItems: "center", gap: "8px",
    fontSize: "0.85rem", color: "var(--text-secondary)",
    padding: "8px 0", cursor: selectedStandards.length > 0 ? "pointer" : "default",
    opacity: selectedStandards.length > 0 ? 1 : 0.7,
  }}>
    <input
      type="checkbox"
      checked={selectedStandards.length === 0 ? true : contentOnlyMode}
      onChange={(e) => setContentOnlyMode(e.target.checked)}
      disabled={selectedStandards.length === 0}
    />
    {selectedStandards.length === 0
      ? "Questions will come from uploaded content (no standards selected)"
      : "Only create questions from uploaded content"}
  </label>
)}
```

**Step 5: Pass flag in assessment generation (gated)**

Find `generateAssessmentHandler` (around line 1411). Where it calls `api.generateAssessment`, add the flag **gated on actual content existing**:

```javascript
contentOnly: contentOnlyMode && (uploadedDocs.length > 0 || selectedSources.length > 0),
```

This prevents sending `contentOnly: true` when all sources have been removed.

**Step 6: Reset toggle when docs OR sources OR standards cleared**

Reset `contentOnlyMode` to `false` in ALL of these scenarios:
- `setUploadedDocs([])` — when uploaded docs are cleared
- `setSelectedSources([])` — when selected sources are cleared
- `setSelectedStandards([])` — when standards are cleared/deselected to zero
- Any handler that removes the last source or last standard

Search for every instance of `setUploadedDocs([])`, `setSelectedSources([])`, and places where `selectedStandards` is emptied. Add `setContentOnlyMode(false)` alongside each.

Also add a useEffect guard so the toggle auto-resets when docs are removed. Note: we do NOT reset when standards disappear because the checkbox stays visible (disabled+checked) in that case — content-only is implicit when no standards exist.

```javascript
// Auto-reset content-only toggle when docs removed OR standards cleared.
// When standards go to zero, the checkbox becomes disabled+checked (implicit),
// so the user's manual choice is no longer relevant — reset to avoid stale state
// when they re-add standards later.
useEffect(function() {
  var hasDocs = uploadedDocs.length > 0 || selectedSources.length > 0;
  var hasStandards = selectedStandards.length > 0;
  if (!hasDocs || !hasStandards) {
    setContentOnlyMode(false);
  }
}, [uploadedDocs.length, selectedSources.length, selectedStandards.length]);
```

This covers every code path: bulk clear via `setUploadedDocs([])`, individual removal, and one-by-one deselection of sources. The dependency array watches `.length` so it fires on any change to the count.

**Step 7: Gate the assignment flag the same way**

In Step 3, change the assignment config from:
```javascript
contentOnly: contentOnlyMode && uploadedDocs.length > 0,
```
To:
```javascript
contentOnly: contentOnlyMode && (uploadedDocs.length > 0 || selectedSources.length > 0),
```

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

---

## Backend — Post-Generation Tagging

### File: `backend/routes/planner_routes.py`

**Step 1: Tag the response when content-only mode was used**

In both `generate_assignment_from_lesson()` and `generate_assessment()`, after the AI returns the generated content, add a `content_only_mode` flag to the response:

```python
# In the return jsonify block:
"content_only_mode": content_only,
```

This lets the frontend show a notice: "Questions were generated from your uploaded content. Review to ensure accuracy — AI may occasionally reference general knowledge."

**Step 2: Frontend notice when content_only_mode is true**

After generation completes and the assignment/assessment is displayed, check the response flag and show a small info banner:

```jsx
{generatedAssignment && generatedAssignment.content_only_mode && (
  <div style={{
    padding: "8px 12px", marginBottom: "10px",
    background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.2)",
    borderRadius: "8px", fontSize: "0.8rem", color: "#93c5fd",
    display: "flex", alignItems: "center", gap: "6px",
  }}>
    <Icon name="Info" size={14} />
    Questions generated from your uploaded content. Review to ensure all questions are answerable from your materials.
  </div>
)}
```

This is transparent — the teacher knows the toggle was active and is reminded to review. We don't claim deterministic enforcement because LLM behavior can't be programmatically guaranteed.

---

## Limitations (documented, not hidden)

- The "content-only" constraint is enforced via prompt instructions, not programmatic validation
- The LLM may occasionally generate questions that reference general knowledge beyond the documents
- The post-generation notice reminds teachers to review

## Follow-Up: Post-Generation Validation (Future)

A semantic similarity checker could compare each generated question against the uploaded document content and flag questions that don't have a strong match. This would require:
1. Embedding the document text (chunk by paragraph)
2. Embedding each generated question
3. Computing cosine similarity between question and document chunks
4. Flagging questions below a threshold (e.g., < 0.6 similarity)

This is a significant project — estimated 1-2 weeks. Not needed for the Volusia pilot. The prompt-based enforcement + teacher review notice is sufficient for launch.

---

---

## What Was Actually Shipped (commit `ed1656f`)

### Frontend (`frontend/src/tabs/PlannerTab.jsx`)

1. **State:** `const [contentOnlyMode, setContentOnlyMode] = useState(false)`

2. **Auto-reset useEffect:**
```javascript
useEffect(function() {
  var hasDocs = uploadedDocs.length > 0 || selectedSources.length > 0;
  var hasStandards = selectedStandards.length > 0;
  if (!hasDocs || !hasStandards) {
    setContentOnlyMode(false);
  }
}, [uploadedDocs.length, selectedSources.length, selectedStandards.length]);
```

3. **Checkbox (identical in both assignment and assessment flows):**
- Visible when `uploadedDocs.length > 0` or `selectedSources.length > 0`
- No standards → `checked={true} disabled={true}` with text "Questions will come from uploaded content"
- Standards selected → interactive with text "Only create questions from uploaded content"

4. **Payload gating:**
- Assignment: `contentOnly: contentOnlyMode && (uploadedDocs.length > 0 || selectedSources.length > 0)`
- Assessment: same gating in the config object

### Backend (`backend/routes/planner_routes.py`)

1. **Assignment generation** (`generate_assignment_from_lesson`):
- Reads `content_only = config.get('contentOnly', False)`
- Three-branch `ref_docs_block`:
  - `content_only and config_standards` → "ALL questions from documents, standards for DOK/format only"
  - `config_standards` → "supplementary content" (default)
  - no standards → "ALL questions from documents"
- Response includes `"content_only_mode": content_only`

2. **Assessment generation** (`generate_assessment`):
- Reads `content_only = config.get('contentOnly', False)`
- Modifies `source_content` instruction when `content_only` is True
- Same three-tier prompt logic

## No Database Changes

The `contentOnly` flag is sent per-request in the API call. It's not stored anywhere — it's a generation-time preference, not a persistent setting.
