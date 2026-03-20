# Content Type Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Assessment vs Assignment content type selector to the publish modal with different default grading policies (score visibility, retakes, timing model).

**Architecture:** Add a content_type selector to both publish modals (PlannerTab.jsx and App.jsx). Selection pre-fills default settings. Backend already supports content_type in published_content table; needs adding to published_assessments for join-code path. Frontend submission/results handling adapts based on content_type.

**Tech Stack:** Python/Flask, React, Supabase

**Spec:** `docs/superpowers/specs/2026-03-20-content-types-accommodations-assets-design.md`

---

## Default Settings by Content Type

| Setting | Assessment | Assignment |
|---------|-----------|------------|
| `show_score_immediately` | `false` (teacher approval) | `true` (MC/TF only; written still pending) |
| `show_correct_answers` | `false` (teacher approval) | `true` |
| `allow_multiple_attempts` | `false` (single attempt) | `true` (unlimited) |
| Time limit | Required field | Optional field |
| Timing model | Available window (`available_from` / `available_until`) | Due date (`due_date`) |
| Late submissions | Closed after window | Allowed, flagged late |
| Makeup/restricted | Available | Hidden (N/A) |

---

## Task 1: Add `contentType` to publishSettings state in both modals

**Files:** `frontend/src/tabs/PlannerTab.jsx`, `frontend/src/App.jsx`

### Step 1.1: Update publishSettings initial state in PlannerTab.jsx

- [ ] In `frontend/src/tabs/PlannerTab.jsx` at line 866, add `contentType`, `showScoreImmediately`, `showCorrectAnswers`, `allowMultipleAttempts`, `dueDate`, `availableFrom`, and `availableUntil` to the `publishSettings` state.

**Find (line 866-873):**
```javascript
const [publishSettings, setPublishSettings] = useState({
    period: '',
    periodFilename: '',
    isMakeup: false,
    selectedStudents: [],
    timeLimit: null,
    applyAccommodations: true,
  });
```

**Replace with:**
```javascript
const [publishSettings, setPublishSettings] = useState({
    period: '',
    periodFilename: '',
    isMakeup: false,
    selectedStudents: [],
    timeLimit: null,
    applyAccommodations: true,
    contentType: 'assessment',
    showScoreImmediately: false,
    showCorrectAnswers: false,
    allowMultipleAttempts: false,
    dueDate: '',
    availableFrom: '',
    availableUntil: '',
  });
```

### Step 1.2: Update publishSettings initial state in App.jsx

- [ ] In `frontend/src/App.jsx` at line 1974, add the same new fields.

**Find (line 1974-1981):**
```javascript
const [publishSettings, setPublishSettings] = useState({
    period: '',
    periodFilename: '',
    isMakeup: false,
    selectedStudents: [],
    timeLimit: null,
    applyAccommodations: true,
  });
```

**Replace with:**
```javascript
const [publishSettings, setPublishSettings] = useState({
    period: '',
    periodFilename: '',
    isMakeup: false,
    selectedStudents: [],
    timeLimit: null,
    applyAccommodations: true,
    contentType: 'assessment',
    showScoreImmediately: false,
    showCorrectAnswers: false,
    allowMultipleAttempts: false,
    dueDate: '',
    availableFrom: '',
    availableUntil: '',
  });
```

### Step 1.3: Add content type change handler in PlannerTab.jsx

- [ ] Add a `handleContentTypeChange` function near the `confirmPublishAssessment` function (around line 1522) that pre-fills defaults when the content type changes.

**Insert before `confirmPublishAssessment` (before line 1522):**
```javascript
// Pre-fill publish settings based on content type
const handleContentTypeChange = (type) => {
  if (type === 'assessment') {
    setPublishSettings(prev => ({
      ...prev,
      contentType: 'assessment',
      showScoreImmediately: false,
      showCorrectAnswers: false,
      allowMultipleAttempts: false,
      dueDate: '',
    }));
  } else {
    setPublishSettings(prev => ({
      ...prev,
      contentType: 'assignment',
      showScoreImmediately: true,
      showCorrectAnswers: true,
      allowMultipleAttempts: true,
      isMakeup: false,
      selectedStudents: [],
      availableFrom: '',
      availableUntil: '',
    }));
  }
};
```

### Step 1.4: Add content type change handler in App.jsx

- [ ] Add the same `handleContentTypeChange` function near the `confirmPublishAssessment` function (around line 4526) in App.jsx. Use identical logic to Step 1.3.

---

## Task 2: Add content type selector UI to both publish modals

**Files:** `frontend/src/tabs/PlannerTab.jsx`, `frontend/src/App.jsx`

### Step 2.1: Add content type selector to PlannerTab.jsx publish modal

- [ ] In `frontend/src/tabs/PlannerTab.jsx`, insert a content type toggle immediately after the modal header (after line 7708, before the Period Selection section at line 7710).

**Insert after line 7708 (`Publish Assessment</h2>`) and before line 7710 (`{/* Period Selection */}`):**
```jsx
{/* Content Type Selector */}
<div style={{ marginBottom: "20px" }}>
  <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
    Content Type
  </label>
  <div style={{ display: "flex", gap: "8px" }}>
    <button
      onClick={() => handleContentTypeChange('assessment')}
      style={{
        flex: 1,
        padding: "12px 16px",
        borderRadius: "8px",
        border: publishSettings.contentType === 'assessment' ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
        background: publishSettings.contentType === 'assessment' ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
        color: "var(--text-primary)",
        cursor: "pointer",
        textAlign: "center",
        fontWeight: publishSettings.contentType === 'assessment' ? 700 : 400,
      }}
    >
      <Icon name="ClipboardCheck" size={20} style={{ marginBottom: "4px" }} />
      <div>Assessment</div>
      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
        Timed, single attempt, scores after review
      </div>
    </button>
    <button
      onClick={() => handleContentTypeChange('assignment')}
      style={{
        flex: 1,
        padding: "12px 16px",
        borderRadius: "8px",
        border: publishSettings.contentType === 'assignment' ? "2px solid #22c55e" : "1px solid var(--glass-border)",
        background: publishSettings.contentType === 'assignment' ? "rgba(34, 197, 94, 0.2)" : "var(--glass-bg)",
        color: "var(--text-primary)",
        cursor: "pointer",
        textAlign: "center",
        fontWeight: publishSettings.contentType === 'assignment' ? 700 : 400,
      }}
    >
      <Icon name="FileText" size={20} style={{ marginBottom: "4px" }} />
      <div>Assignment</div>
      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
        Due date, retakes allowed, instant MC scores
      </div>
    </button>
  </div>
</div>
```

- [ ] Also update the modal header (line 7707) to be dynamic based on content type:

**Find (line 7705-7708):**
```jsx
<h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
  <Icon name="Share2" size={24} style={{ color: "var(--accent-primary)" }} />
  Publish Assessment
</h2>
```

**Replace with:**
```jsx
<h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
  <Icon name="Share2" size={24} style={{ color: "var(--accent-primary)" }} />
  {'Publish ' + (publishSettings.contentType === 'assessment' ? 'Assessment' : 'Assignment')}
</h2>
```

### Step 2.2: Add content type selector to App.jsx publish modal

- [ ] In `frontend/src/App.jsx`, insert the same content type toggle after the modal header (after line 15987, before the Class Selection at line 15989). Use the exact same JSX as Step 2.1.

### Step 2.3: Conditionally show/hide Makeup Exam toggle based on content type

- [ ] In `frontend/src/tabs/PlannerTab.jsx`, wrap the Makeup Exam toggle (lines 7745-7772) so it only shows for assessments.

**Find (line 7745):**
```jsx
{/* Makeup Exam Toggle */}
```

**Replace with:**
```jsx
{/* Makeup Exam Toggle — assessments only */}
{publishSettings.contentType === 'assessment' && (
```

**Find the closing `</div>` at line 7772 that ends the makeup section, and add a closing `)}`:**

After line 7772 (the `</div>` closing the Makeup Exam block), add:
```jsx
)}
```

- [ ] Apply the same conditional wrap in `frontend/src/App.jsx` for the Makeup Exam toggle (lines 16038-16065).

### Step 2.4: Add timing fields based on content type

- [ ] In `frontend/src/tabs/PlannerTab.jsx`, replace the current "Time Limit (Optional)" section (lines 7901-7925) with a content-type-aware timing section.

**Find (lines 7901-7925):**
```jsx
{/* Time Limit */}
<div style={{ marginBottom: "25px" }}>
  <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
    Time Limit (Optional)
  </label>
  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
    <input
      type="number"
      min="0"
      value={publishSettings.timeLimit || ''}
      onChange={(e) => setPublishSettings({ ...publishSettings, timeLimit: e.target.value ? parseInt(e.target.value) : null })}
      placeholder="No limit"
      style={{
        width: "120px",
        padding: "10px 12px",
        borderRadius: "8px",
        border: "1px solid var(--glass-border)",
        background: "var(--surface)",
        color: "var(--text-primary)",
        fontSize: "0.95rem",
      }}
    />
    <span style={{ color: "var(--text-secondary)" }}>minutes</span>
  </div>
</div>
```

**Replace with:**
```jsx
{/* Timing fields — differ by content type */}
{publishSettings.contentType === 'assessment' ? (
  <div style={{ marginBottom: "25px" }}>
    <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
      Time Limit <span style={{ color: "#ef4444" }}>*</span>
    </label>
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <input
        type="number"
        min="1"
        value={publishSettings.timeLimit || ''}
        onChange={(e) => setPublishSettings({ ...publishSettings, timeLimit: e.target.value ? parseInt(e.target.value) : null })}
        placeholder="Required"
        style={{
          width: "120px",
          padding: "10px 12px",
          borderRadius: "8px",
          border: "1px solid var(--glass-border)",
          background: "var(--surface)",
          color: "var(--text-primary)",
          fontSize: "0.95rem",
        }}
      />
      <span style={{ color: "var(--text-secondary)" }}>minutes</span>
    </div>
    <div style={{ display: "flex", gap: "15px", marginTop: "15px" }}>
      <div style={{ flex: 1 }}>
        <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Available From (Optional)
        </label>
        <input
          type="datetime-local"
          value={publishSettings.availableFrom}
          onChange={(e) => setPublishSettings({ ...publishSettings, availableFrom: e.target.value })}
          style={{
            width: "100%",
            padding: "8px 10px",
            borderRadius: "8px",
            border: "1px solid var(--glass-border)",
            background: "var(--surface)",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />
      </div>
      <div style={{ flex: 1 }}>
        <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Available Until (Optional)
        </label>
        <input
          type="datetime-local"
          value={publishSettings.availableUntil}
          onChange={(e) => setPublishSettings({ ...publishSettings, availableUntil: e.target.value })}
          style={{
            width: "100%",
            padding: "8px 10px",
            borderRadius: "8px",
            border: "1px solid var(--glass-border)",
            background: "var(--surface)",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />
      </div>
    </div>
  </div>
) : (
  <div style={{ marginBottom: "25px" }}>
    <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
      Time Limit (Optional)
    </label>
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <input
        type="number"
        min="0"
        value={publishSettings.timeLimit || ''}
        onChange={(e) => setPublishSettings({ ...publishSettings, timeLimit: e.target.value ? parseInt(e.target.value) : null })}
        placeholder="No limit"
        style={{
          width: "120px",
          padding: "10px 12px",
          borderRadius: "8px",
          border: "1px solid var(--glass-border)",
          background: "var(--surface)",
          color: "var(--text-primary)",
          fontSize: "0.95rem",
        }}
      />
      <span style={{ color: "var(--text-secondary)" }}>minutes</span>
    </div>
    <div style={{ marginTop: "15px" }}>
      <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
        Due Date (Optional)
      </label>
      <input
        type="datetime-local"
        value={publishSettings.dueDate}
        onChange={(e) => setPublishSettings({ ...publishSettings, dueDate: e.target.value })}
        style={{
          width: "100%",
          padding: "8px 10px",
          borderRadius: "8px",
          border: "1px solid var(--glass-border)",
          background: "var(--surface)",
          color: "var(--text-primary)",
          fontSize: "0.85rem",
        }}
      />
    </div>
  </div>
)}
```

- [ ] Apply the same replacement in `frontend/src/App.jsx` for the Time Limit section (lines 16194-16218).

### Step 2.5: Add assessment-only validation to Publish button

- [ ] In `frontend/src/tabs/PlannerTab.jsx`, update the Publish button disabled condition (line 7938) to require time limit for assessments.

**Find (line 7938):**
```jsx
disabled={publishingAssessment || (publishSettings.isMakeup && publishSettings.selectedStudents.length === 0)}
```

**Replace with:**
```jsx
disabled={publishingAssessment || (publishSettings.isMakeup && publishSettings.selectedStudents.length === 0) || (publishSettings.contentType === 'assessment' && !publishSettings.timeLimit)}
```

- [ ] Update the Publish button text (line 7946) to reflect content type:

**Find (line 7946):**
```jsx
{publishingAssessment ? "Publishing..." : "Publish Assessment"}
```

**Replace with:**
```jsx
{publishingAssessment ? "Publishing..." : 'Publish ' + (publishSettings.contentType === 'assessment' ? 'Assessment' : 'Assignment')}
```

- [ ] Apply the same disabled condition update in `frontend/src/App.jsx` (line 16231).

---

## Task 3: Update `confirmPublishAssessment` to pass new settings

**Files:** `frontend/src/tabs/PlannerTab.jsx`, `frontend/src/App.jsx`

### Step 3.1: Update PlannerTab.jsx confirmPublishAssessment

- [ ] In `frontend/src/tabs/PlannerTab.jsx`, update the `confirmPublishAssessment` function (lines 1547-1556) to use `publishSettings` values instead of hardcoded `true`.

**Find (lines 1547-1556):**
```javascript
const data = await api.publishAssessmentToPortal(contentToPublish, {
        teacher_name: config.teacher_name || "Teacher",
        teacher_email: config.teacher_email,
        show_correct_answers: true,
        show_score_immediately: true,
        period: publishSettings.period,
        restricted_students: restrictedStudents,
        student_accommodations: studentAccommodationsMap,
        time_limit_minutes: publishSettings.timeLimit,
      });
```

**Replace with:**
```javascript
const data = await api.publishAssessmentToPortal(contentToPublish, {
        teacher_name: config.teacher_name || "Teacher",
        teacher_email: config.teacher_email,
        content_type: publishSettings.contentType,
        show_correct_answers: publishSettings.showCorrectAnswers,
        show_score_immediately: publishSettings.showScoreImmediately,
        allow_multiple_attempts: publishSettings.allowMultipleAttempts,
        period: publishSettings.period,
        restricted_students: restrictedStudents,
        student_accommodations: studentAccommodationsMap,
        time_limit_minutes: publishSettings.timeLimit,
        due_date: publishSettings.dueDate || null,
        available_from: publishSettings.availableFrom || null,
        available_until: publishSettings.availableUntil || null,
      });
```

### Step 3.2: Update App.jsx confirmPublishAssessment (class-based path)

- [ ] In `frontend/src/App.jsx`, update the class-based publish path (lines 4552-4563) to use `publishSettings.contentType` instead of inferring from structure.

**Find (lines 4552-4563):**
```javascript
const contentType = contentToPublish.sections ? 'assignment' : 'assessment';
        const settings = {
          teacher_name: config.teacher_name || "Teacher",
          teacher_email: config.teacher_email,
          show_correct_answers: true,
          show_score_immediately: true,
          period: publishSettings.period,
          restricted_students: restrictedStudents,
          student_accommodations: studentAccommodationsMap,
          time_limit_minutes: publishSettings.timeLimit,
        };
        data = await api.publishToClass(publishClassId, contentToPublish, contentType, contentToPublish.title || 'Untitled', settings, null);
```

**Replace with:**
```javascript
const contentType = publishSettings.contentType;
        const settings = {
          teacher_name: config.teacher_name || "Teacher",
          teacher_email: config.teacher_email,
          show_correct_answers: publishSettings.showCorrectAnswers,
          show_score_immediately: publishSettings.showScoreImmediately,
          allow_multiple_attempts: publishSettings.allowMultipleAttempts,
          period: publishSettings.period,
          restricted_students: restrictedStudents,
          student_accommodations: studentAccommodationsMap,
          time_limit_minutes: publishSettings.timeLimit,
          available_from: publishSettings.availableFrom || null,
          available_until: publishSettings.availableUntil || null,
        };
        const dueDate = publishSettings.dueDate || null;
        data = await api.publishToClass(publishClassId, contentToPublish, contentType, contentToPublish.title || 'Untitled', settings, dueDate);
```

### Step 3.3: Update App.jsx confirmPublishAssessment (join-code path)

- [ ] In `frontend/src/App.jsx`, update the join-code publish path (lines 4565-4574) to use `publishSettings` values.

**Find (lines 4565-4574):**
```javascript
data = await api.publishAssessmentToPortal(contentToPublish, {
          teacher_name: config.teacher_name || "Teacher",
          teacher_email: config.teacher_email,
          show_correct_answers: true,
          show_score_immediately: true,
          period: publishSettings.period,
          restricted_students: restrictedStudents,
          student_accommodations: studentAccommodationsMap,
          time_limit_minutes: publishSettings.timeLimit,
        });
```

**Replace with:**
```javascript
data = await api.publishAssessmentToPortal(contentToPublish, {
          teacher_name: config.teacher_name || "Teacher",
          teacher_email: config.teacher_email,
          content_type: publishSettings.contentType,
          show_correct_answers: publishSettings.showCorrectAnswers,
          show_score_immediately: publishSettings.showScoreImmediately,
          allow_multiple_attempts: publishSettings.allowMultipleAttempts,
          period: publishSettings.period,
          restricted_students: restrictedStudents,
          student_accommodations: studentAccommodationsMap,
          time_limit_minutes: publishSettings.timeLimit,
          due_date: publishSettings.dueDate || null,
          available_from: publishSettings.availableFrom || null,
          available_until: publishSettings.availableUntil || null,
        });
```

---

## Task 4: Update backend to store and respect content_type for join-code path

**Files:** `backend/routes/student_portal_routes.py`

### Step 4.1: Store content_type in published_assessments insert

- [ ] In `backend/routes/student_portal_routes.py`, update the `publish_assessment` function (lines 62-83) to include `content_type` and timing fields in the database insert and settings.

**Find (lines 62-83):**
```python
# Prepare settings
        db_settings = {
            "time_limit_minutes": settings.get('time_limit_minutes'),
            "allow_multiple_attempts": settings.get('allow_multiple_attempts', False),
            "show_correct_answers": settings.get('show_correct_answers', True),
            "show_score_immediately": settings.get('show_score_immediately', True),
            "require_name": settings.get('require_name', True),
            "period": period,
            "restricted_students": restricted_students,
            "student_accommodations": student_accommodations,
            "is_makeup": len(restricted_students) > 0,
        }

        # Insert into Supabase
        result = db.table('published_assessments').insert({
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }).execute()
```

**Replace with:**
```python
# Determine content type
        content_type = settings.get('content_type', 'assessment')
        if content_type not in ('assessment', 'assignment'):
            content_type = 'assessment'

        # Prepare settings
        db_settings = {
            "time_limit_minutes": settings.get('time_limit_minutes'),
            "allow_multiple_attempts": settings.get('allow_multiple_attempts', False),
            "show_correct_answers": settings.get('show_correct_answers', True),
            "show_score_immediately": settings.get('show_score_immediately', True),
            "require_name": settings.get('require_name', True),
            "period": period,
            "restricted_students": restricted_students,
            "student_accommodations": student_accommodations,
            "is_makeup": len(restricted_students) > 0,
            "content_type": content_type,
            "available_from": settings.get('available_from'),
            "available_until": settings.get('available_until'),
            "due_date": settings.get('due_date'),
        }

        # Insert into Supabase
        insert_row = {
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }

        result = db.table('published_assessments').insert(insert_row).execute()
```

> **Note:** `content_type` is stored inside the `settings` JSON column, not as a top-level column on `published_assessments`. This avoids a Supabase migration since the `published_assessments` table has no `content_type` column. The submit handler already reads from `settings`, so it will pick up the value automatically.

### Step 4.2: Update join-code submit handler to respect show_score_immediately=false

- [ ] In `backend/routes/student_portal_routes.py`, update the submit response logic (lines 589-617) to handle the case where both `show_score_immediately` and `show_correct_answers` are `false` (assessment mode). When both are false, the student sees only a confirmation message with no scores.

**Find (lines 589-617):**
```python
# Prepare response based on settings
        response = {
            "success": True,
            "submission_id": submission_id,
            "student_name": student_name,
        }

        if results.get("grading_status") == "partial":
            # Mixed assignment: show MC scores but not percentage
            mc_correct = sum(1 for q in (results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("short_answer", "extended_response", "essay", "written"))
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = results["message"]
            if settings.get('show_correct_answers', True):
                response["detailed_results"] = [q for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching")]
        else:
            # MC-only: show full results
            if settings.get('show_score_immediately', True):
                response["score"] = results.get('score')
                response["total_points"] = results.get('total_points')
                response["percentage"] = results.get('percentage')
                response["feedback_summary"] = results.get('feedback_summary')
            if settings.get('show_correct_answers', True):
                response["detailed_results"] = results.get('questions')

        return jsonify(response)
```

**Replace with:**
```python
# Prepare response based on settings
        response = {
            "success": True,
            "submission_id": submission_id,
            "student_name": student_name,
            "content_type": settings.get('content_type', 'assessment'),
        }

        # Assessment mode: hide all scores until teacher approval
        if not settings.get('show_score_immediately', True) and not settings.get('show_correct_answers', True):
            response["grading_status"] = "pending_review"
            response["message"] = "Submitted! Your teacher will review and share your results."
        elif results.get("grading_status") == "partial":
            # Mixed content: show MC scores but not percentage
            mc_correct = sum(1 for q in (results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("short_answer", "extended_response", "essay", "written"))
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = results["message"]
            if settings.get('show_correct_answers', True):
                response["detailed_results"] = [q for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching")]
        else:
            # MC-only: show full results
            if settings.get('show_score_immediately', True):
                response["score"] = results.get('score')
                response["total_points"] = results.get('total_points')
                response["percentage"] = results.get('percentage')
                response["feedback_summary"] = results.get('feedback_summary')
            if settings.get('show_correct_answers', True):
                response["detailed_results"] = results.get('questions')

        return jsonify(response)
```

### Step 4.3: Update class-based submit handler to respect content_type settings

- [ ] In `backend/routes/student_account_routes.py`, update the submit response logic (lines 913-932) to check `show_score_immediately` and `show_correct_answers` from published content settings, same as the join-code path.

**Find (lines 913-932):**
```python
# Return instant results to student (MC scores immediately)
        response = {
            "success": True,
            "submission_id": submission_id,
        }
        if needs_multipass:
            mc_correct = sum(1 for q in (instant_results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (instant_results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (instant_results.get("questions") or []) if q.get("status") == "pending_review")
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = "Multiple choice graded. Written responses pending teacher review."
        else:
            response["message"] = "Submitted and graded successfully!"
            response["score"] = instant_results.get("score")
            response["percentage"] = instant_results.get("percentage")

        return jsonify(response)
```

**Replace with:**
```python
# Get content settings for visibility control
        content_settings = pc.data[0].get('settings', {}) if pc.data else {}

        # Return instant results to student (respecting content type settings)
        response = {
            "success": True,
            "submission_id": submission_id,
            "content_type": content_settings.get('content_type', pc.data[0].get('content_type', 'assessment') if pc.data else 'assessment'),
        }

        # Assessment mode: hide all scores until teacher approval
        if not content_settings.get('show_score_immediately', True) and not content_settings.get('show_correct_answers', True):
            response["grading_status"] = "pending_review"
            response["message"] = "Submitted! Your teacher will review and share your results."
        elif needs_multipass:
            mc_correct = sum(1 for q in (instant_results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (instant_results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (instant_results.get("questions") or []) if q.get("status") == "pending_review")
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = "Multiple choice graded. Written responses pending teacher review."
            if content_settings.get('show_correct_answers', True):
                response["detailed_results"] = [q for q in (instant_results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching")]
        else:
            if content_settings.get('show_score_immediately', True):
                response["message"] = "Submitted and graded successfully!"
                response["score"] = instant_results.get("score")
                response["percentage"] = instant_results.get("percentage")
            else:
                response["message"] = "Submitted! Your teacher will review and share your results."
            if content_settings.get('show_correct_answers', True):
                response["detailed_results"] = instant_results.get("questions")

        return jsonify(response)
```

---

## Task 5: Backend timing enforcement for submissions

**Files:** `backend/routes/student_portal_routes.py`, `backend/routes/student_account_routes.py`

This task enforces `available_from` / `available_until` windows on the join-code path (assessments) and `due_date` late-flagging on the class-based path (assignments). The `available_from` and `available_until` fields are already stored inside the `settings` dict in `published_assessments` (added in Task 4 Step 4.1). The `published_content` table already has a `due_date` column.

### Step 5.1: Enforce availability window in join-code submit handler

- [ ] In `backend/routes/student_portal_routes.py`, in the `submit_assessment` handler, after retrieving `assessment_data` and `settings` from the database, add a time-window check before processing the submission.

**Insert after getting `settings` from the assessment data (before grading logic begins):**
```python
# Enforce availability window (assessments)
available_from = settings.get('available_from')
available_until = settings.get('available_until')
now = datetime.now(timezone.utc).isoformat()
if available_from and now < available_from:
    return jsonify({"error": "This assessment is not yet available."}), 403
if available_until and now > available_until:
    return jsonify({"error": "This assessment is no longer accepting submissions."}), 403
```

> **Note:** ISO 8601 string comparison works correctly for UTC timestamps because the format is lexicographically sortable. Ensure `available_from` and `available_until` are stored as UTC ISO strings from the frontend (the datetime-local input values should be converted to UTC before saving).

### Step 5.2: Flag late submissions in class-based submit handler

- [ ] In `backend/routes/student_account_routes.py`, in the `submit_student_work` handler, after loading the `published_content` record (`pc`), check the `due_date` and flag the submission as late if past due.

**Insert after loading `published_content` (before building the submission row):**
```python
# Check for late submission (assignments)
due_date = pc.data[0].get('due_date')
is_late = False
if due_date:
    now = datetime.now(tz=timezone.utc).isoformat()
    if now > due_date:
        is_late = True
```

**Add to the submission row being inserted into Supabase:**
```python
submission_row['is_late'] = is_late
```

- [ ] Also include `is_late` in the response so the frontend can display a "Late" badge:

**In the response dict (from Task 4 Step 4.3), add:**
```python
response['is_late'] = is_late
```

### Step 5.3: Ensure `datetime` and `timezone` are imported

- [ ] In both files, verify that `datetime` and `timezone` are imported at the top:
```python
from datetime import datetime, timezone
```

If not present, add the import. `student_portal_routes.py` likely already has `datetime` imported for timestamp handling; just ensure `timezone` is included.

---

## Task 6: Update StudentPortal.jsx to handle `pending_review` grading status

**File:** `frontend/src/components/StudentPortal.jsx`

### Step 5.1: Handle `pending_review` status in submission response

- [ ] In `frontend/src/components/StudentPortal.jsx`, update the submission response handler (lines 206-223) to recognize the `pending_review` status.

**Find (lines 206-223):**
```javascript
if (data.grading_status === "partial") {
          setResults({
            grading_status: "partial",
            mc_correct: data.mc_correct,
            mc_total: data.mc_total,
            written_pending: data.written_pending,
            message: data.message,
            questions: data.detailed_results,
          });
        } else {
          setResults({
            score: data.score,
            total_points: data.total_points,
            percentage: data.percentage,
            feedback_summary: data.feedback_summary,
            questions: data.detailed_results,
          });
        }
```

**Replace with:**
```javascript
if (data.grading_status === "pending_review") {
          setResults({
            grading_status: "pending_review",
            message: data.message,
          });
        } else if (data.grading_status === "partial") {
          setResults({
            grading_status: "partial",
            mc_correct: data.mc_correct,
            mc_total: data.mc_total,
            written_pending: data.written_pending,
            message: data.message,
            questions: data.detailed_results,
          });
        } else {
          setResults({
            score: data.score,
            total_points: data.total_points,
            percentage: data.percentage,
            feedback_summary: data.feedback_summary,
            questions: data.detailed_results,
          });
        }
```

### Step 5.2: Add `pending_review` UI to results screen

- [ ] In `frontend/src/components/StudentPortal.jsx`, update the results screen (lines 713-763) to handle the `pending_review` status with a teacher-review-pending message.

**Find (lines 713-714):**
```javascript
var isPartial = results && results.grading_status === "partial";
    var percentage = results?.percentage || 0;
```

**Replace with:**
```javascript
var isPendingReview = results && results.grading_status === "pending_review";
    var isPartial = results && results.grading_status === "partial";
    var percentage = results?.percentage || 0;
```

- [ ] Update the Score Card section (lines 722-763) to show a pending review message when `isPendingReview` is true.

**Find (lines 723-725):**
```jsx
<Icon name={isPartial ? "Clock" : "Award"} size={50} />
            <h2 style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
              {isPartial ? "Submitted!" : (assessment?.sections ? "Assignment Complete!" : "Assessment Complete!")}
```

**Replace with:**
```jsx
<Icon name={(isPendingReview || isPartial) ? "Clock" : "Award"} size={50} />
            <h2 style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
              {(isPendingReview || isPartial) ? "Submitted!" : (assessment?.sections ? "Assignment Complete!" : "Assessment Complete!")}
```

- [ ] Add the pending review block before the existing `isPartial` conditional (after line 728, before line 729).

**Find (line 729):**
```jsx
{isPartial ? (
```

**Replace with:**
```jsx
{isPendingReview ? (
              <div>
                <div style={{
                  padding: "20px",
                  borderRadius: "12px",
                  background: "rgba(99, 102, 241, 0.15)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                  marginTop: "15px",
                }}>
                  <Icon name="CheckCircle" size={40} style={{ color: "#6366f1", marginBottom: "12px" }} />
                  <p style={{ fontSize: "1.1rem", fontWeight: 600, color: "#a5b4fc", marginBottom: "8px" }}>
                    Your response has been recorded
                  </p>
                  <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.9rem" }}>
                    {results.message || "Your teacher will review and share your results."}
                  </p>
                </div>
              </div>
            ) : isPartial ? (
```

---

## Task 7: Build, test, and verify

### Step 7.1: Build frontend

- [ ] Run `cd /Users/alexc/Downloads/Graider/frontend && npm run build` to compile the React app and verify no build errors.

### Step 7.2: Manual test — publish as Assessment

- [ ] Open the teacher dashboard, generate or load an assessment, click Publish.
- [ ] Verify the content type selector shows "Assessment" and "Assignment" buttons.
- [ ] Verify "Assessment" is selected by default.
- [ ] Verify time limit shows "Required" placeholder with red asterisk.
- [ ] Verify "Available From" and "Available Until" datetime fields appear.
- [ ] Verify Makeup Exam toggle is visible.
- [ ] Publish with a time limit, then take the assessment as a student.
- [ ] Verify the student sees "Submitted! Your teacher will review and share your results." with NO scores shown.

### Step 7.3: Manual test — publish as Assignment

- [ ] Switch to "Assignment" in the publish modal.
- [ ] Verify time limit changes to "Optional" placeholder (no asterisk).
- [ ] Verify "Due Date" datetime field appears instead of available window.
- [ ] Verify Makeup Exam toggle is hidden.
- [ ] Publish, then submit as a student.
- [ ] Verify MC/TF scores show immediately; written responses show "pending teacher review."

### Step 7.4: Test class-based publish path

- [ ] In App.jsx, publish to a class as Assessment — verify `content_type` is passed as `'assessment'` (not inferred from structure).
- [ ] Publish to a class as Assignment — verify `content_type` is `'assignment'` and `due_date` is passed.

### Step 7.5: Verify backward compatibility

- [ ] Existing published assessments (no `content_type` in settings) should continue to work with the current behavior (`show_score_immediately: true`, `show_correct_answers: true` defaults).
- [ ] The `published_assessments` table does NOT require a migration — `content_type` lives inside the `settings` JSON column.
