# OneRoster Grade Passback — Design Spec

## Problem

After grading student work, teachers have to manually export CSV files and import them into their SIS gradebook. The Focus SIS browser automation path is fragile. There's no direct API-based grade sync.

## Solution

Add OneRoster Gradebook API support (lineItems + results) so teachers can push scores and feedback comments to any OneRoster-compliant SIS with one click. Covers ~80-90% of US school districts (PowerSchool, Infinite Campus, Focus, Skyward, Aeries, Tyler).

## Scope

- Portal submissions only (class-based `student_submissions` + join-code `submissions`). Students already have OneRoster sourcedIds from roster sync.
- Manual sync only — teacher clicks "Sync to SIS" in the Export Grades dropdown after reviewing/approving grades.
- Create-once-then-update — first sync creates a lineItem (assignment) in the SIS, subsequent syncs update scores on the same lineItem.
- Feedback comments included — `feedback_summary` from grading results sent as the OneRoster `comment` field on each result.

## What This Does NOT Include

- No file-based grading sync (no guaranteed student ID linkage)
- No auto-sync after grading (manual button only)
- No grade deletion/retraction from SIS
- No fetching existing SIS grades for comparison
- No vendor-specific APIs (OneRoster standard only)

## Data Flow

```
Teacher clicks "Sync to SIS" in Export Grades dropdown
        |
Frontend: POST /api/oneroster/sync-grades
  { assessment_code OR content_id,
    scores: [{student_id, score, total_points, comment}] }
        |
Backend: oneroster_routes.py -> oneroster_gradebook.py
  1. Load OneRoster config (base_url, credentials)
  2. Look up lineItem mapping for this assessment
  3. If no mapping -> POST /lineItems to create assignment in SIS
  4. Store lineItem sourcedId -> assessment mapping in teacher_data
  5. For each student score:
     a. Look up student's OneRoster sourcedId from student_id_number
     b. POST /lineItems/{id}/results with score + comment
  6. Return { synced: N, skipped: N, failed: N, errors: [...] }
        |
Frontend: Toast with result count
```

## Backend Components

### 1. Low-level client methods — `backend/oneroster.py` (modify)

Add three methods to the existing `OneRosterClient` class:

- `create_line_item(data)` — POST to `/lineItems`
- `get_line_items(class_sourced_id)` — GET `/lineItems?filter=classSourcedId='{id}'`
- `create_result(line_item_id, data)` — POST to `/lineItems/{id}/results`

These follow the same pattern as existing methods (OAuth token management, retry with backoff, error handling).

### 2. Gradebook service — `backend/services/oneroster_gradebook.py` (create)

Two functions:

`ensure_line_item(client, teacher_id, assessment_id, title, total_points, class_sourced_id)`
- Checks `teacher_data` for existing lineItem mapping (key: `oneroster_line_items`)
- If found, returns the stored lineItem sourcedId
- If not, calls `client.create_line_item()` with title, max score, class reference
- Stores the mapping and returns the new lineItem sourcedId

`post_results(client, line_item_id, scores)`
- Takes list of `{student_sourced_id, score, max_score, comment}`
- Calls `client.create_result()` for each
- Collects successes, failures, and skipped (missing sourcedId)
- Returns `{synced, skipped, failed, errors}`

### 3. Route — `backend/routes/oneroster_routes.py` (modify)

New endpoint: `POST /api/oneroster/sync-grades`
- Requires teacher auth (`@require_teacher`)
- Accepts: `{assessment_code, content_id, title, total_points, class_sourced_id, scores}`
- `scores` array: `[{student_id, score, total_points, comment}]`
- Loads OneRoster config, creates client
- Calls `ensure_line_item()` then `post_results()`
- Returns JSON result with sync counts

### LineItem Mapping Storage

Stored in `teacher_data` with key `oneroster_line_items`:

```json
{
  "assessment_abc123": {
    "line_item_id": "li-xyz-789",
    "class_sourced_id": "cls-456",
    "title": "US History Assessment",
    "created_at": "2026-04-05T22:00:00Z"
  }
}
```

Lookup key is either `assessment_code` (join-code path) or `content_id` (class-based path).

### Student Matching

Students synced via OneRoster have `student_id_number = "oneroster:{sourcedId}"` in the `students` table. The service strips the `oneroster:` prefix to get the raw sourcedId for posting results. Students without this prefix are skipped and included in the `skipped` count.

### OneRoster Result Payload

```json
{
  "sourcedId": "<generated-uuid>",
  "lineItemSourcedId": "li-xyz-789",
  "studentSourcedId": "stu-abc-123",
  "scoreStatus": "fully graded",
  "score": 85.0,
  "scoreDate": "2026-04-05",
  "comment": "Strong analysis of primary sources. Consider expanding your comparison..."
}
```

The `comment` field carries the `feedback_summary` from Graider's grading results.

## Frontend Components

### ExportGradesDropdown — `frontend/src/tabs/ResultsTab.jsx` (modify)

Add a new dropdown item, gated on OneRoster being configured:

```
{config.sis_type === 'oneroster' && (
  <DropdownItem onClick={handleOneRosterSync} icon="RefreshCw" label="Sync to SIS" />
)}
```

`handleOneRosterSync`:
- Collects filtered results (same pattern as existing export handlers)
- Maps each result to `{student_id, score, total_points, comment: feedback_summary}`
- Calls `api.syncOneRosterGrades()`
- Shows toast: "Synced N grades to SIS" or "Synced N grades, M skipped (no SIS match)"

### API function — `frontend/src/services/api.js` (modify)

```javascript
export async function syncOneRosterGrades(data) {
  return fetchApi('/api/oneroster/sync-grades', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
```

## Error Handling

- **OAuth token expired**: Auto-refresh (existing behavior in `oneroster.py`)
- **SIS rejects a score**: Collect error, continue syncing remaining students, report failures in response
- **No OneRoster config**: Button doesn't appear (gated on `config.sis_type`)
- **Student missing sourcedId**: Skip, include in `skipped` count with student name
- **LineItem creation fails**: Return error immediately (can't post scores without it)
- **Network/timeout**: Retry with backoff (existing `with_retry` utility)

## Testing

- Unit tests for `oneroster_gradebook.py`: mock the OneRoster client, verify lineItem creation, result posting, error collection
- Unit tests for the route: mock the gradebook service, verify request validation and response format
- Integration: manual test against Focus SIS sandbox (Volusia)
