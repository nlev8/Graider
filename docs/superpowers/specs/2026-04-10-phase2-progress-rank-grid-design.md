# Phase 2 — Progress Rank Grid Design Spec

## Problem

Graider's Analytics tab shows cross-class charts and trends, but teachers have no way to see a single class's mastery on a per-student, per-standard basis. Progress Learning's Progress Rank report is their most-used mastery tool: a grid where rows are students, columns are standards, and cells are color-coded by mastery. Without this view, teachers can't quickly identify which students are struggling on which specific standards.

## Solution

Build a Progress Rank grid view inside the existing Analytics tab. Add a class selector at the top of the tab: "All Classes" preserves current Analytics content; selecting a specific class shows the new Progress Rank grid. The grid reads existing `standards_mastery` rollups from `student_submissions.results` (shipped in Phase 1) and aggregates on-demand per student per standard.

## Architecture

### Where it lives

- **Analytics tab** gains a new class selector dropdown at the top
- **"All Classes" (default)** → renders existing Analytics content unchanged
- **Specific class selected** → renders new `ProgressRankGrid` component, hiding existing content
- **No new top-level tab**
- **No new sub-tabs** — class hub sub-tabs (Overview, Students, Gradebook) deferred to later phases

### Data source

- On-demand aggregation from `student_submissions.results.standards_mastery` JSONB
- No new precomputed table
- Scoped by `classes.teacher_id == g.teacher_id` for ownership
- Reads via `class_students` junction for roster (provider-agnostic — works for Clever, ClassLink, OneRoster, CSV)

## Backend

### New endpoint

**`GET /api/teacher/class/<class_id>/progress-rank?attempt_mode=latest|best|average`**

**Query params:**
- `attempt_mode` — `latest` (default) | `best` | `average`

**Auth:** `@require_teacher`. Verify `classes.teacher_id == g.teacher_id` before returning.

**Response shape:**
```json
{
  "class_id": "uuid",
  "class_name": "Period 1",
  "attempt_mode": "latest",
  "standards": ["SS.8.A.1.1", "SS.8.A.1.2", "SS.8.A.1.3"],
  "students": [
    {
      "student_id": "uuid",
      "student_name": "Christian Almazan",
      "mastery": {
        "SS.8.A.1.1": {
          "percentage": 92,
          "points_earned": 11,
          "points_possible": 12,
          "question_count": 5,
          "contributing_submissions": [
            {
              "submission_id": "uuid",
              "title": "Unit 4 Quiz",
              "points_earned": 6,
              "points_possible": 6,
              "attempt_number": 1
            }
          ]
        },
        "SS.8.A.1.2": { "percentage": 75, "points_earned": 3, "points_possible": 4, "question_count": 2, "contributing_submissions": [...] },
        "SS.8.A.1.3": null
      }
    }
  ]
}
```

- `mastery[code] = null` means no data for that student on that standard (renders as gray dash)
- `standards` array is the union of all standards assessed across any submission in the class, sorted alphabetically

### Aggregation logic

1. Fetch class from `classes` (verify ownership)
2. Fetch student roster from `class_students` joined with `students`
3. Fetch all `published_content` for this class where `content_type in ('assessment', 'assignment')` — resource types excluded
4. Fetch all `student_submissions` for those content_ids where `status != 'draft'`
5. For each student, group submissions by `content_id`
6. Apply attempt mode filter per (student, content_id):
   - `latest` → highest `attempt_number` or most recent `submitted_at`
   - `best` → highest `percentage`
   - `average` → average across all attempts
7. For each selected submission, read `results.standards_mastery` and accumulate per-standard totals across all content
8. Compute final percentage per (student, standard) = `points_earned / points_possible * 100`
9. Build the `standards` array from all standards seen across the aggregation
10. Return the grid

### Contributing submissions

For each (student, standard) cell, `contributing_submissions` lists the submissions that contributed points to that cell. Used by the frontend cell-click popover. Limit to 10 most recent to bound response size.

### File

Add the endpoint at the END of `backend/routes/student_portal_routes.py`, alongside the other `/api/teacher/*` endpoints.

## Frontend

### New component

**`frontend/src/tabs/ProgressRankGrid.jsx`**

**Props:**
- `classId: string` — the selected class UUID

**State:**
- `attemptMode: 'latest' | 'best' | 'average'` — default `'latest'`
- `strugglingOnly: boolean` — default `false`
- `data: null | ProgressRankResponse` — fetched from the API
- `loading: boolean`
- `selectedCell: { studentId, standard } | null` — for popover

**Fetch:**
- On mount and whenever `classId` or `attemptMode` changes, fetch `GET /api/teacher/class/<classId>/progress-rank?attempt_mode=<mode>`

**UI structure:**
```
┌────────────────────────────────────────────────────┐
│ Progress Rank — Period 1                           │
│                                                    │
│ [Latest] [Best] [Average]  [All] [Struggling Only] │
├────────────────────────────────────────────────────┤
│          │ SS.8.A.1.1 │ SS.8.A.1.2 │ SS.8.A.1.3 │..│
│ Student  │────────────┼────────────┼────────────┼──│
│ Christian│ 🟢 92%     │ 🟡 75%     │ ⬜ —       │  │
│ Marcus   │ 🟢 100%    │ 🟢 89%     │ 🟡 70%     │  │
│ Sarah    │ 🟢 95%     │ 🟢 91%     │ 🟢 87%     │  │
└────────────────────────────────────────────────────┘
```

**Mastery color mapping:**
- `>= 85` → green (`var(--success)` background)
- `70-84` → yellow (`var(--warning)` background)
- `< 70` → red (`var(--danger)` background)
- `null` → gray dash (`var(--text-muted)`)

**Layout:**
- Sticky first column (student names) on horizontal scroll
- Sticky header row (standard codes) on vertical scroll
- Minimum cell width so standards codes don't wrap
- Horizontal scroll for wide grids (more than ~8 standards)

### Struggling filter

`strugglingOnly` hides students whose `mastery` dict has zero entries with `percentage < 70`. Applied client-side after fetch (no additional endpoint).

### Cell click popover

When a cell with data is clicked:
1. Set `selectedCell = { studentId, standard }`
2. Render a small popover near the cell showing:
   - Student name + standard code
   - List of contributing submissions (title, attempt #, points earned / points possible)
   - Close button (X)

No navigation away from the grid. No fetch required — data comes from the original response.

### Student row click

Clicking the student name column cell:
- Currently no-op (Phase 2b will wire it to Student Report Card)
- Render as styled button with `cursor: pointer` but no handler yet, OR add a tooltip "Student Report Card coming soon"

### Changes to AnalyticsTab.jsx

1. Import `ProgressRankGrid` and `api.listClasses`
2. Add state: `var [selectedClassId, setSelectedClassId] = useState('all');` and `var [classesForFilter, setClassesForFilter] = useState([]);`
3. Fetch classes on mount via `api.listClasses()`
4. Render a class selector dropdown at the top of the tab (label: "Class", options: "All Classes" + each class)
5. Conditional render:
   - `selectedClassId === 'all'` → render existing Analytics content (wrapped in a fragment — no content deleted)
   - Else → render `<ProgressRankGrid classId={selectedClassId} />`

### Frontend API helper

Add to `frontend/src/services/api.js`:

```javascript
export async function getClassProgressRank(classId, attemptMode) {
  var mode = attemptMode || 'latest';
  return fetchApi('/api/teacher/class/' + classId + '/progress-rank?attempt_mode=' + mode);
}
```

## Compliance (Clever / ClassLink / OneRoster)

**Verified safe:**
- New endpoint reads only internal Supabase tables (`classes`, `class_students`, `students`, `published_content`, `student_submissions`)
- No outbound calls to any SSO or roster API
- No changes to `backend/routes/clever_routes.py`, `classlink_routes.py`, `oneroster_routes.py`, `backend/roster_sync.py`
- No changes to OneRoster grade push (`backend/services/oneroster_gradebook.py`)
- No new PII fields exposed — standards codes are public curriculum identifiers
- Class ownership verified via `classes.teacher_id` (existing pattern used by all teacher endpoints)
- `class_students` junction is populated identically by all 4 roster sources, so the grid works provider-agnostically with zero per-provider branching
- Student filtering happens via existing tables — no new data storage

## Non-goals (explicitly deferred to later phases)

- **Student Report Card** — Phase 2b (next)
- **Gradebook sub-tab** — Phase 3
- **Overview sub-tab** — later
- **Column header click → class-wide standard drill-down** — later
- **Teacher-configurable mastery thresholds** — later (if requested)
- **Date range filter** — later
- **Export to CSV / print** — later
- **Mobile layout** — later (Graider is desktop-only)
- **Quick-click remediation** — Phase 4 (biggest differentiator vs Progress Learning)
- **Engagement metrics / time per question reports** — Phase 5
- **Caching / precomputed mastery table** — only if performance becomes an issue
- **"Best attempt" tracking across assessment boundaries** — best attempt is per-assessment only

## Testing

**Backend:**
- Unit test for aggregation helper with fixture data covering: no submissions, one student one standard, multiple attempts with different attempt modes, mixed null and present standards_mastery
- Endpoint integration test: verify teacher ownership check, verify 403 on unauthorized class, verify shape of response

**Frontend:**
- Manual: navigate to Analytics tab, pick a class, verify grid renders with existing data
- Manual: toggle attempt mode, verify grid recalculates
- Manual: toggle struggling filter, verify non-struggling students hidden
- Manual: click a cell, verify popover shows contributing submissions
- Manual: pick "All Classes" again, verify original Analytics content returns

## Migration plan

No schema changes. Ship backend + frontend together. Existing Analytics users see:
1. A new "Class" dropdown at the top of the Analytics tab
2. Default "All Classes" preserves their current experience exactly
3. Picking a class shows the new grid
