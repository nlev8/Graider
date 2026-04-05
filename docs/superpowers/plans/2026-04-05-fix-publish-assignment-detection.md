# Fix: Publish Assignment Detection

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the publish modal showing "Publish Assessment" with assessment-only fields (Formative/Summative, Time Limit required) when publishing an assignment.

**Root Cause:** The auto-detection at line 4479-4481 checks `content.type` to determine if the content is an assignment. But AI-generated assignments don't always set `type: 'assignment'` — they might use `type: 'quiz'`, `type: undefined`, or other values. The detection fails and defaults to `'assessment'`.

**The real fix:** Don't rely on `content.type`. Instead, check **which state variable** holds the content:
- `generatedAssignment` → always assignment
- `generatedAssessment` → always assessment
- `lessonPlan` with sections → assignment

This is deterministic — no AI-generated field to parse.

---

## Fix

**File:** `frontend/src/App.jsx`

- [ ] **Step 1: Fix the content type detection in publishAssessmentHandler**

Find (~line 4472-4493):

```javascript
  const publishAssessmentHandler = () => {
    var content = getActiveAssignment();
    if (!content) {
      addToast("No content to publish", "warning");
      return;
    }
    // Auto-detect content type from the generated content
    var detectedType = 'assessment';
    if (content.type === 'assignment' || content.type === 'project' || content.type === 'essay') {
      detectedType = 'assignment';
    }
    // Reset publish settings, pre-fill time limit from content
    setPublishSettings({
      period: '',
      periodFilename: '',
      isMakeup: false,
      selectedStudents: [],
      timeLimit: detectedType === 'assignment' ? null : (content.time_limit || null),
      applyAccommodations: true,
      contentType: detectedType,
      assessmentCategory: 'formative',
    });
```

Replace with:

```javascript
  const publishAssessmentHandler = () => {
    var content = getActiveAssignment();
    if (!content) {
      addToast("No content to publish", "warning");
      return;
    }
    // Detect content type from which state variable holds the content
    // generatedAssignment → assignment, generatedAssessment → assessment
    var detectedType = 'assessment';
    if (generatedAssignment || (lessonPlan && lessonPlan.sections && !lessonPlan.days)) {
      detectedType = 'assignment';
    }
    // Reset publish settings, pre-fill time limit from content
    setPublishSettings({
      period: '',
      periodFilename: '',
      isMakeup: false,
      selectedStudents: [],
      timeLimit: detectedType === 'assignment' ? null : (content.time_limit || null),
      applyAccommodations: true,
      contentType: detectedType,
      assessmentCategory: 'formative',
    });
```

- [ ] **Step 2: Build frontend**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Verify**

1. Generate an assignment → click "Publish to Portal" → modal should say "Publish Assignment" (no Formative/Summative, no required time limit)
2. Generate an assessment → click "Publish to Portal" → modal should say "Publish Assessment" (with Formative/Summative, time limit required)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx backend/static/
git commit -m "fix: detect assignment type from state variable, not AI-generated content.type"
```
