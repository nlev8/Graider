# "Submitted" Files in Results Tab

## Context

The teacher submits assignments via SharePoint (OneDrive-synced folder). Currently, to find ungraded submissions they have to manually browse the SharePoint folder. The Results tab only shows files *after* grading. We need a "Submitted" section that scans the assignments folder and lists ungraded files with student names — so the teacher sees what's waiting without leaving Graider.

There's already a `/api/check-new-files` endpoint that counts ungraded files, but it only returns counts and 5 filenames. We need to extend this to return all ungraded files with parsed student/assignment info.

## Plan

### 1. Backend — New endpoint `/api/submitted-files`

**File:** `backend/routes/grading_routes.py`

Add a new endpoint that:
- Takes `folder` (assignments folder) and `output_folder` from request body
- Scans folder for supported file types (`.docx`, `.txt`, `.jpg`, `.jpeg`, `.png`)
- Filters out already-graded files (from `master_grades.csv` + `grading_state["results"]`)
- Parses student name from each filename using `parse_filename()` from `assignment_grader.py`
- Returns array of `{filename, student_name, assignment, file_size, modified_at}` for each ungraded file

Reuses: `parse_filename()` from `assignment_grader.py` (line ~2670), same graded-file detection logic from existing `/api/check-new-files`.

### 2. Frontend — "Submitted" filter option

**File:** `frontend/src/App.jsx`

- Add `const [submittedFiles, setSubmittedFiles] = useState([])`
- Add useEffect to fetch `/api/submitted-files` every 30s (same pattern as portal submissions), passing current `assignmentsFolder` and `outputFolder` from config state
- Add `"submitted"` option to the results filter `<select>` dropdown (line ~8925): `<option value="submitted">Submitted ({submittedFiles.length})</option>`

### 3. Frontend — "Submitted" section in Results tab

**File:** `frontend/src/App.jsx`

Add a collapsible section above the results table (same pattern as the Portal Submissions section) that:
- Shows when `submittedFiles.length > 0` AND `resultsFilter === "all"` or `resultsFilter === "submitted"`
- Renders each file as a row: student name, assignment name, file modified date, file size
- Yellow/amber styling (consistent with "pending" visual language)
- Header: "Submitted ({count})" with Inbox icon

### Key files
- `backend/routes/grading_routes.py` — new endpoint
- `frontend/src/App.jsx` — state, useEffect, filter option, section render
- `assignment_grader.py` — reuse `parse_filename()` (read-only)

### Verification
1. `npm run build` passes
2. Results tab shows "Submitted" section with ungraded files from assignments folder
3. "Submitted" filter option appears in dropdown with count
4. Files disappear from "Submitted" after grading completes
5. Refreshes every 30 seconds to pick up new SharePoint syncs
