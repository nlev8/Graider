# Content Tagging — Design Spec

## Problem

Teachers have no way to organize published content (assessments, assignments, study materials) beyond the existing per-item "unit name" field on shared resources. Progress Learning's Assessment Bank uses a tag-based model where every item can carry multiple tags and teachers filter a flat list by tag. Our Student Portal tab currently shows 3 flat lists (Published Assessments / Published Assignments / Shared Resources) with no filtering and no tag UI on assessments or assignments. Matching Progress Learning's organization depth means generalizing the existing unit field into a tag system that works across all content types.

## Solution

Add a `tags` array to each published content item's existing `settings` JSONB. Keep `unit_name` as the "primary tag" used for student dashboard grouping. Expose a per-row inline tag UI with "+" dropdown plus a global tag filter at the top of the Student Portal tab that applies to all three lists simultaneously. No schema migration. Tags are per-teacher (global across their classes).

## Data Model

**No schema changes.** Tag storage lives in the existing `published_content.settings` JSONB column:

- `settings.unit_name` — existing string field. Continues to drive student dashboard unit grouping. Treated as the "primary tag" in the teacher UI.
- `settings.tags` — new optional array of strings. Additional tags beyond the primary unit.

Example:
```json
{
  "settings": {
    "unit_name": "Unit 4: The Road to the Civil War",
    "tags": ["Formative", "Review Ready"]
  }
}
```

Tags are plain strings. No separate table. No IDs. Dedup by string equality (case-sensitive initially).

## Backend

### New endpoints

**`POST /api/teacher/published-content/<content_id>/tags`** (`@require_teacher`)

Sets the complete `tags` array on a `published_content` row. Replaces existing tags wholesale.

Request:
```json
{ "tags": ["Formative", "Review Ready"] }
```

Behavior:
- Verify `published_content.teacher_id == g.teacher_id`
- Merge into `settings` JSONB: `settings['tags'] = request.tags`
- Update row
- Works for any `content_type` (assessment, assignment, study_guide, flashcards, slide_deck)

Response: `{ "success": true }`

**`GET /api/teacher/tags`** (`@require_teacher`)

Returns a deduped sorted list of all unique tag strings the teacher has across all their `published_content` rows. Includes both `unit_name` values and `tags` array values.

Response:
```json
{ "tags": ["Formative", "Unit 1: Colonial America", "Unit 4: The Road to the Civil War"] }
```

### Existing endpoint extension

**`POST /api/teacher/shared-resource/<id>/unit`** — extend to work for ANY `published_content` row, not just resource types. Drops the existing content-type filter. Becomes the unified "set primary unit" endpoint for assessments, assignments, and resources alike. Renamed conceptually but keeps the same route for backward compatibility.

### Files

- `backend/routes/student_portal_routes.py` — add the two new endpoints at the end, alongside other teacher endpoints
- `backend/routes/student_portal_routes.py` — modify `update_shared_resource_unit` to drop its content-type filter (if any)

## Frontend

### Teacher Student Portal tab layout

**Global filter bar** (new, sticky at the top of the tab above all 3 lists):

```
┌──────────────────────────────────────────────────────┐
│  Filter by tag:  [All content ▼]                     │
└──────────────────────────────────────────────────────┘
```

- Default: "All content" (no filtering)
- Dropdown options: "All content", then every unique tag from `GET /api/teacher/tags` (sorted alphabetically)
- Filter applies client-side to all 3 lists simultaneously
- An item matches if `settings.unit_name === selectedTag` OR `selectedTag in settings.tags`
- Filter state is component-local (not persisted across sessions)

**Per-row tag display** on Published Assessments, Published Assignments, and Shared Resources:

```
┌─────────────────────────────────────────────────────────┐
│ "The Road to the Civil War"                             │
│ Flashcards · Period 1 · Apr 10                          │
│ [📚 Unit 4: Civil War] [Formative] [+]            [🗑] │
└─────────────────────────────────────────────────────────┘
```

- **Unit pill** (if `unit_name` set) — styled with a folder icon, primary color
- **Tag pills** (for each entry in `tags` array) — smaller, muted pills
- **Muted "No unit" pill** (if `unit_name` not set) — click to open the same dropdown as "+", with "Set as unit" highlighted
- **"+" button** — opens the tag dropdown:
  - Header: "Add tag"
  - If this row has no `unit_name`, show "Set as unit: ..." option at top
  - List of all existing teacher tags (click to add to this item)
  - "Create new tag..." at bottom → opens the styled tag-name modal (reuses existing new-unit modal, relabeled)
- **Click a tag pill** (unit or regular) → removes it from the item, shows toast confirmation

### "+" dropdown behavior

1. Click "+" → dropdown opens
2. If hovered row has no `unit_name`, first section is "Set as unit" with existing tags listed (click to set as unit)
3. Second section: "Add tag" with existing tags listed (click to add to `tags` array; hide tags already on this item)
4. Bottom: "Create new tag..." → opens modal
5. In the modal, teacher types a name → "Create" creates AND assigns:
   - If the row has no `unit_name`, the new tag becomes the `unit_name`
   - Otherwise, it's added to `tags`

### Click a tag to remove

Clicking any pill (unit or regular) on a row removes that tag from that item. Shows a toast like `Removed "Formative"`. For unit removal, `unit_name` is cleared.

### New API helpers in `frontend/src/services/api.js`

```javascript
export async function getTeacherTags() { ... }
export async function setContentTags(contentId, tags) { ... }
```

The existing `updateSharedResourceUnit(id, unitName)` stays, but now works for any published content (backend change removes the filter).

### Files

- `frontend/src/services/api.js` — add `getTeacherTags` and `setContentTags` helpers
- `frontend/src/App.jsx`:
  - Add `allTeacherTags` state + fetch on Student Portal tab mount
  - Add `selectedTagFilter` state (default `'all'`)
  - Add global filter dropdown at top of Student Portal tab
  - Apply client-side filter to all 3 lists (`publishedAssessments`, split by type, and `sharedResources`)
  - Replace the existing "Assign unit..." dropdown on resources with the unified "+" tag dropdown
  - Add tag UI to assessment/assignment rows (same pattern)

## Student dashboard

**No changes.** Students still see content grouped by `unit_name` in collapsible sections via the existing Phase 2 layout. The new `tags` array is invisible to students.

Future enhancement (out of scope): surface tags as a student-facing filter.

## Compliance (Clever / ClassLink / OneRoster)

**Verified safe:**
- No changes to any SSO, roster, or grade-post code
- Tags are teacher-authored free-text strings stored in existing JSONB — not PII, not roster data, not standards codes
- No new outbound API calls
- No new database tables
- Ownership checks use existing `published_content.teacher_id == g.teacher_id` pattern

## Non-goals (deferred)

- **Tag Manager modal** (bulk rename/delete/merge tags)
- **Student-facing tag filter** in the student dashboard
- **Tag colors or icons** per tag
- **Shared tag library** across teachers in a school
- **Drag-drop reordering** of tag pills on a row
- **Per-class tag scoping** (tags are global per teacher)
- **Bulk tag operations** (tag multiple items at once from a checkbox list)
- **Tag autocomplete in the share modal at creation time** — tags are applied retroactively from the Student Portal tab only
- **Tag analytics** ("how many items in Unit 4?")
- **Case-insensitive tag dedup** — two tags differing only in case count as different for now
- **Tag length limits / validation** — accept any non-empty string up to a reasonable length (say 100 chars, enforced client-side)

## Testing

**Backend:**
- Unit test: `POST /api/teacher/published-content/<id>/tags` replaces tags and preserves other settings fields
- Unit test: `POST /api/teacher/published-content/<id>/tags` returns 403 when `teacher_id` mismatch
- Unit test: `GET /api/teacher/tags` returns union of unit_names and tags arrays, deduped and sorted
- Unit test: `GET /api/teacher/tags` returns only this teacher's tags, not others'

**Frontend (manual):**
- Open Student Portal tab → global filter shows "All content" + existing tags populated from API
- Click "+" on a resource without a unit → dropdown shows "Set as unit" section with existing tags
- Click "Create new tag..." → modal appears → type name → confirm → tag assigned
- Click existing tag pill on a row → tag removed, toast shows
- Pick a tag from global filter → only matching rows visible across all 3 lists
- Pick "All content" → all rows visible again
- Add a tag to an assessment and verify it shows in the global filter dropdown after refetch
