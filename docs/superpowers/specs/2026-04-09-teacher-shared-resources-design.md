# Teacher Shared Resources Management — Design Spec

## Problem

When a teacher shares flashcards, study guides, or slide decks with classes via "Share with Class," there's no way to view or delete those shared resources from the teacher side. The Student Portal tab only shows join-code assessments, not class-based published content.

## Solution

Add a "Shared Resources" section to the teacher's Student Portal tab showing all resource-type `published_content` entries. Teachers can delete resources from individual classes or from all classes at once.

## Backend

### New endpoints

**`GET /api/teacher/shared-resources`** (require_teacher)

Query `published_content` where `teacher_id` matches and `content_type` is in (`study_guide`, `flashcards`, `slide_deck`). Join with `classes` to get class name. Return:

```json
{
  "resources": [
    {
      "id": "uuid",
      "title": "The Road to the Civil War",
      "content_type": "flashcards",
      "class_name": "Period 1",
      "class_id": "uuid",
      "created_at": "2026-04-09T...",
      "is_active": true
    }
  ]
}
```

**`DELETE /api/teacher/shared-resource/<id>`** (require_teacher)

Delete a single `published_content` row. Verify `teacher_id` matches before deleting. Returns `{ "success": true }`.

**`POST /api/teacher/delete-shared-resources-bulk`** (require_teacher)

Accepts `{ "title": "..." }`. Deletes all `published_content` rows matching `teacher_id` + `title` + resource content types. Returns `{ "success": true, "deleted": N }`.

### File

All three endpoints go in `backend/routes/student_account_routes.py` alongside the existing teacher portal endpoints (`/api/teacher/assessments`, etc.).

## Frontend

### Location

In `App.jsx`, in the Student Portal tab section, after the existing published assessments list. Same visual style — glass card with a header and list.

### Display

- Section header: "Shared Resources" with a resource icon
- Each row shows: content type icon (flashcards/study guide/slide deck), title, class name, date shared
- Delete button (trash icon) per row — deletes from that specific class
- When multiple rows share the same title (shared to multiple classes), show a "Delete from All Classes" link/button that calls the bulk endpoint
- Empty state: "No shared resources yet"

### Data flow

- Fetch `GET /api/teacher/shared-resources` when the Student Portal tab loads (alongside existing assessments fetch)
- Store in `sharedResources` state array
- On delete: call the endpoint, remove from local state, show toast
- On bulk delete: call bulk endpoint, remove all matching items from local state, show toast

## Non-goals

- No editing of shared resources (title, content)
- No re-sharing or moving between classes
- No student submission tracking for resources (they're view-only)
- No changes to the student-facing portal
