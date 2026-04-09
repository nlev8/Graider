# Student Dashboard Resource Routing — Design Spec

## Problem

When a teacher shares flashcards (or study guides, slide decks) with a class via "Share with Class," the content appears in the student dashboard's "Your Assignments" section instead of the "Study Materials" section. Students see flashcards listed as assignments with "Not Started" status badges, which is confusing. Clicking them opens the assessment player instead of the interactive flashcard viewer.

## Solution

Filter resource-type content out of the assignments list and merge it into the Study Materials section. Use the existing `FlashcardView` component for interactive flashcard display.

## Changes

**File:** `frontend/src/components/StudentDashboard.jsx`

### 1. Filter assignments list

The `items` array from `/api/student/dashboard` contains all published content. Filter out resource types (`study_guide`, `flashcards`, `slide_deck`) from the "Your Assignments" rendering. Only `assessment` and `assignment` content types appear in that section.

### 2. Merge resource-type items into Study Materials

Resource-type items from the dashboard API get merged into the Study Materials section alongside resources from `/api/student/resources`. Deduplicate by ID to avoid showing the same item twice. Each merged item needs the shape `{ id, title, content_type }` to match the existing resource rendering.

### 3. Import FlashcardView

Import `FlashcardView` from `./FlashcardView` (already exists, used in `StudentPortal.jsx`).

### 4. Fetch content via correct endpoint

Existing resources use `/api/student/resource/:id`. Dashboard-sourced items use `/api/student/content/:id`. The click handler needs to detect which endpoint to use based on whether the item came from the dashboard or the resources API. Use a `_fromDashboard` flag on merged items.

### 5. Render flashcards interactively

When `selectedResource.content_type === 'flashcards'`, render using `FlashcardView` with the card data instead of the existing static resource viewer. The `FlashcardView` component accepts `cards` (array of `{term, definition}`) and handles flipping, navigation.

## Content type routing

| `content_type` | Section | Viewer |
|----------------|---------|--------|
| `assessment` | Your Assignments | Assessment player (existing) |
| `assignment` | Your Assignments | Assignment player (existing) |
| `flashcards` | Study Materials | `FlashcardView` (interactive) |
| `study_guide` | Study Materials | Existing section renderer |
| `slide_deck` | Study Materials | Existing resource viewer |

## Non-goals

- No backend changes
- No new API endpoints
- No changes to the teacher-facing share flow
- No changes to the join-code portal (already works)
