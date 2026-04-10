# Unit-Based Student Dashboard — Design Spec

## Problem

The student dashboard shows a flat list of assignments and study materials with no organizational structure. Students can't easily find content related to the unit they're currently studying. Teachers can't control how content is grouped.

## Solution

Group student dashboard content by unit in collapsible sections. Carry the unit name through the publish flow. Let teachers assign units to uncategorized content via a dropdown.

## Data Layer

Store `unit_name` in the existing `settings` JSONB column of `published_content`. No schema migration needed.

- `shareWithClass` passes `settings: { unit_name: "..." }` to `/api/publish-to-class`
- `/api/publish-to-class` already accepts and stores `settings`
- Dashboard/resource APIs return `unit_name` from `settings` in their responses

## Share Modal Changes

**File:** `frontend/src/App.jsx` (share modal section)

Add an editable "Unit" text input to the share modal:
- Auto-populated from `unitConfig.title` when the Planner has an active unit
- Editable so the teacher can override or set it for non-planner content
- Stored in `shareModalContent` alongside content, contentType, and title
- Passed as `settings.unit_name` in the `/api/publish-to-class` request body
- Single-class auto-share (1 class, no modal) also passes unit_name

## Teacher Portal: Unit Assignment

**File:** `backend/routes/student_portal_routes.py`

New endpoint: `POST /api/teacher/shared-resource/<id>/unit`
- Accepts `{ "unit_name": "..." }`
- Updates `settings` JSONB on the `published_content` row, merging `unit_name` into existing settings
- Verifies teacher ownership before updating

**File:** `frontend/src/App.jsx` (Shared Resources section)

- Display unit label per resource item (e.g., "Flashcards · Period 1 · Unit 4")
- Items without a unit get a subtle warning highlight
- Show a dropdown on uncategorized items with existing unit names + "New unit" option
- On selection, call the update endpoint and refresh the list

**File:** `frontend/src/services/api.js`

New helper: `updateSharedResourceUnit(id, unitName)`

## Student Dashboard: Collapsible Units

**File:** `frontend/src/components/StudentDashboard.jsx`

### Grouping Logic

After fetching `items` (from `/api/student/dashboard`) and `resources` (from `/api/student/resources`), plus merging dashboard resources:

1. Extract `unit_name` from each item's settings or root-level field
2. Group all items by `unit_name` — both assignments and resources go into the same unit
3. Sort units: most recent first (by newest item's `created_at` within the unit)
4. Items with no `unit_name` go into a "General" section at the bottom

### Rendering

Each unit renders as a collapsible section:

**Header (always visible):**
- Expand/collapse arrow (▼/▶)
- Unit name (e.g., "Unit 4: The Road to the Civil War")
- Summary: "3 assignments · 2 study materials"
- "Current" badge on the most recent unit
- "All graded ✓" indicator when all assignments in the unit are graded

**Body (expanded):**
- "Assignments" sub-header with assignment items (same card style as current, with status badges and due dates)
- "Study Materials" sub-header with resource items (grid of cards with type icons)

**Collapse behavior:**
- Most recent unit auto-expanded on load
- All other units collapsed
- Click header to toggle
- Multiple units can be expanded simultaneously

### API Changes

**`/api/student/dashboard`** — include `unit_name` in each item's response. Read from `published_content.settings->unit_name`.

**`/api/student/resources`** — include `unit_name` if available in the resource data.

## Files to Modify

| File | Changes |
|------|---------|
| `backend/routes/student_account_routes.py` | Pass `settings.unit_name` through in publish endpoint; return `unit_name` in dashboard items |
| `backend/routes/student_portal_routes.py` | Add unit update endpoint; include `unit_name` in shared resources list |
| `frontend/src/services/api.js` | Add `updateSharedResourceUnit` helper |
| `frontend/src/App.jsx` | Add unit field to share modal; add unit dropdown to Shared Resources; pass unit in share flow |
| `frontend/src/components/StudentDashboard.jsx` | Replace flat list with collapsible unit-based layout |

## Non-goals

- No drag-and-drop reordering (future enhancement)
- No unit management UI (units are created implicitly from the Planner or manually in the share modal/dropdown)
- No changes to the join-code portal (StudentPortal.jsx) — units only apply to class-based content
- No backend unit table — unit names are strings in the settings JSONB
