# Share with Class Modal — Design Spec

## Problem

The "Share with Class" action uses a browser `prompt()` dialog that only allows selecting one class by typing a number. Teachers can't share with multiple classes at once, and the UI is not production-quality.

## Solution

Replace `prompt()` with a modal component that supports multi-select with a "Select All" option. When sharing, loop through selected classes and call `/api/publish-to-class` once per class (separate `published_content` row per class).

## Modal UI

- Header: "Share with Class"
- "Select All" checkbox (toggles all classes on/off)
- Checkbox list of teacher's classes (name + student count from `teacherClasses`)
- Cancel button (closes modal, no action)
- Share button: disabled when no classes selected, label shows count ("Share with 3 classes")
- Loading state on Share button while publishing

## State

- `showShareModal` (boolean) — controls modal visibility
- `shareModalContent` (object) — `{ content, contentType, title }` stored when modal opens
- `shareModalSelected` (Set or array of class IDs) — tracks which classes are checked

## Behavior

1. `shareWithClass(content, contentType, title)` fetches classes if needed (existing lazy-fetch logic), then opens the modal instead of calling `prompt()`
2. If only 1 class exists, skip the modal — publish directly (no selection needed)
3. Teacher checks classes (or "Select All"), clicks Share
4. `executeShareWithClasses()` loops through selected class IDs, calls `/api/publish-to-class` for each
5. On success: toast "Shared [title] with N classes", close modal
6. On partial failure: toast with count of successes and failures
7. On all fail: error toast

## Changes

**File:** `frontend/src/App.jsx`

1. Add state variables (`showShareModal`, `shareModalContent`, `shareModalSelected`)
2. Modify `shareWithClass` to open modal instead of `prompt()` (keep lazy-fetch and single-class bypass)
3. Add `executeShareWithClasses` function that loops selected classes
4. Add modal JSX (follows existing modal patterns — overlay + glass-card)

## Non-goals

- No separate component file (follows existing App.jsx modal patterns)
- No backend changes
- No changes to `/api/publish-to-class` endpoint
- No due date picker or settings in this modal (can be added later)
