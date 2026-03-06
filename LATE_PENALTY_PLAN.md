# Due Dates & Late Submission Penalties

## Context

Teachers need to set due dates on assignments and have late submissions automatically penalized. Currently there is no due date field anywhere in the assignment config, and no penalty logic in the grading pipeline. The penalty policy should be teacher-configurable per assignment (points/day, percent/day, or tiered brackets). Penalties auto-apply during grading but teachers can override them in Results.

---

## Step 1: Add fields to assignment state

**File:** `frontend/src/App.jsx` (line 1248)

Add to the `assignment` useState:
```javascript
dueDate: "",              // ISO datetime string e.g. "2026-03-15T23:59"
latePenalty: {
  enabled: false,
  type: "points_per_day",  // "points_per_day" | "percent_per_day" | "tiered"
  amount: 10,
  tiers: [
    { daysLate: 1, penalty: 10 },
    { daysLate: 3, penalty: 25 },
    { daysLate: 7, penalty: 50 },
  ],
  maxPenalty: 50,
  gracePeriodHours: 0,
},
```

Also update the load-assignment restore code (~line 4016) to include `dueDate` and `latePenalty` with defaults.

No persistence changes needed — the merge-save pattern in `backend/routes/assignment_routes.py` (line 40) auto-persists new fields.

---

## Step 2: Add list-assignments metadata

**File:** `backend/routes/assignment_routes.py` (line ~70)

Add to the `assignment_data[name]` dict:
```python
"dueDate": data.get("dueDate", ""),
"latePenalty": data.get("latePenalty", {}),
```

Needed so Grade tab and Results tab can see due dates without loading full configs.

---

## Step 3: Builder UI — Due Date & Late Policy section

**File:** `frontend/src/App.jsx`, after the assignment details grid (~line 17135)

Add a new section "Due Date & Late Policy":
- `<input type="datetime-local">` for due date + Clear button
- Checkbox: "Enable late penalty"
- When enabled: dropdown for policy type (Points/day, Percent/day, Tiered), amount input, max penalty input, grace period input
- For tiered: editable list of tier rows with daysLate + penalty + delete, plus "Add tier" button
- Wire to `setAssignment({ ...assignment, dueDate: ..., latePenalty: {...} })`

---

## Step 4: Grade tab — Bulk due date setting

**File:** `frontend/src/App.jsx`, in the saved assignments list (~line 7411)

Add a `<input type="date">` next to each assignment name in the assignment rows. On change:
1. Update local `savedAssignmentData` state
2. Load full config via `api.loadAssignment(name)`, merge the new dueDate, save via `api.saveAssignmentConfig()`
3. Time defaults to 23:59 when set via bulk date picker
4. Show date in amber/red if past due

---

## Step 5: Backend penalty calculation

**File:** `backend/app.py`

### 5a: Add helper function (near line 700)

```python
def calculate_late_penalty(filepath, matched_config):
    """Returns penalty info dict or None."""
```

Logic:
- Read `dueDate` and `latePenalty` from `matched_config`
- If not enabled or no due date, return `None`
- Get file modification time via `filepath.stat().st_mtime`
- Apply grace period hours
- Calculate `days_late` (partial days round up)
- Calculate `penalty_percent` based on type:
  - `points_per_day`: `min(days_late * amount, maxPenalty)`
  - `percent_per_day`: `min(days_late * amount, maxPenalty)`
  - `tiered`: find matching tier bracket, cap at maxPenalty
- Return `{"is_late": bool, "days_late": int, "penalty_percent": float, ...}`

### 5b: Apply penalty at score finalization (~line 1569)

After `new_score` is computed, before storing in results:
```python
late_info = calculate_late_penalty(filepath, matched_config) if matched_config else None
original_score = new_score
if late_info and late_info.get('is_late'):
    if penalty_type == 'points_per_day':
        new_score = max(0, new_score - penalty_points)
    else:
        new_score = max(0, new_score - round(original_score * penalty_percent / 100))
```

### 5c: Add fields to result dict (~line 1601)

```python
"original_score": original_score if late else None,
"late_penalty": {"days_late": N, "penalty_applied": N, ...} if late else None,
```

---

## Step 6: Results display

**File:** `frontend/src/App.jsx`

### 6a: Score column (~line 10348)

When `r.late_penalty` exists, show: ~~original~~ penalized [clock icon], with tooltip explaining the deduction.

### 6b: Review modal (~line 5951)

Add a late penalty info card (amber background) showing days late, original score, penalty amount. Include a "Remove Penalty" button that:
- Calls `updateGrade(index, "score", r.original_score)`
- Calls `updateGrade(index, "late_penalty", null)`
- Calls `updateGrade(index, "penalty_overridden", true)`

The existing `updateGrade()` function already handles arbitrary field updates, so no changes needed there.

---

## Key Files

| File | Changes |
|------|---------|
| `frontend/src/App.jsx` | Assignment state fields, Builder UI section, Grade tab bulk dates, Results score display, Review modal penalty card |
| `backend/app.py` | `calculate_late_penalty()` helper, apply penalty at line ~1569, add fields to result dict |
| `backend/routes/assignment_routes.py` | Add `dueDate`/`latePenalty` to list-assignments metadata |

---

## Verification

1. Set due date to yesterday on an assignment in Builder, enable penalty (10 pts/day)
2. Grade a student file → score should be reduced by 10, log shows "Late penalty: -10 pts (1 day late)"
3. Results table shows strikethrough original + penalized score with clock icon
4. Open review modal → see late penalty card → click "Remove Penalty" → score restores
5. Set due date to tomorrow → grade same file → no penalty applied
6. Test tiered: set tiers, grade a file 4 days late → correct tier applied
7. Bulk set due date from Grade tab → verify it persists
8. New teacher signs up → onboarding wizard shows Focus export step
9. Help icon next to "Upload Roster" shows the quick guide
10. `cd frontend && npm run build` passes

---

## Step 7: Focus Roster Export Tutorial

Teachers need guidance on exporting their class roster from Focus SIS into a CSV that Graider accepts. Add in two places:

### 7a: Onboarding wizard step

**File:** `frontend/src/components/OnboardingWizard.jsx`

Add a step (after class creation, before "you're all set") that walks through:
1. In Focus: **Reports > Student Listings > Class Roster** (or Grades > Export)
2. Select the class/period
3. Include columns: Student ID, First Name, Last Name, Email
4. Export as CSV
5. Upload to Graider using the upload button

Include a visual example of what the CSV should look like:
```
Student ID, First Name, Last Name, Email
12345, Maria, Santos, maria.santos@school.edu
12346, James, Wilson, james.wilson@school.edu
```

Note: Graider auto-detects column names flexibly — `student_id`, `StudentID`, `Student ID` all work. Combined name columns like `Student Name` with "Last, First" format are also supported.

### 7b: Persistent help tooltip in Classes UI

**File:** `frontend/src/App.jsx`, near the roster upload button in Settings/Classes

Add a help icon (CircleHelp) next to "Upload Roster" that shows a popover/tooltip with:
- "Export from Focus: Reports > Student Listings > CSV"
- Required columns: Student ID, First Name, Last Name, Email
- "Column names are detected automatically"
