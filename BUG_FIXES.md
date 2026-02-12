# Graider Bug Fix Log

Tracks all grading-related bug fixes to prevent regressions and identify patterns.

---

## BUG-001: Template stripping removes student answers on same line
**Date**: 2026-02-11
**File**: `assignment_grader.py` — `_strip_template_lines()` (lines 341-385)
**Symptom**: Summary section flagged as "unanswered" / "missing" despite student having written a response.
**Root Cause**: When a student types their answer on the same line as the template prompt (e.g., `"Explain how the Missouri Compromise... [student answer here]"`), the entire line was removed because `_strip_template_lines()` treated any line containing template text as fully template. It did not account for student content appended after the prompt on the same line.
**Fix**: Added partial-strip logic. When template text is found as a substring of a response line, only the template portion is stripped. If the remaining text after the template is >= 10 characters, it's preserved as the student's answer.
**Test**: Cornell Notes "Increasing Regional Tensions" — Summary section now correctly extracts student content.
**Regression risk**: Low. Only activates when template is a strict substring of a longer line with meaningful remaining content.

---

## BUG-002: Missing section detection too strict with multi-line/emoji markers
**Date**: 2026-02-11
**File**: `assignment_grader.py` — `extract_student_responses()` (lines 1023-1059)
**Symptom**: Sections with emoji markers (e.g., "📝 Essential Questions") falsely reported as "missing" even though they were found in the document.
**Root Cause**: `found_marker_names` set only stored the full marker text. When comparing against the config's marker list, multi-line markers or markers with emojis didn't match because the found version might be first-line-only or have different emoji encoding.
**Fix**: Added multi-representation matching. `found_marker_names` now stores four variants per marker: full text, first line only, emoji-stripped full text, emoji-stripped first line. Comparison checks all four representations.
**Test**: Markers like "✏️ Summary" correctly matched in both found set and config list.
**Regression risk**: Low. Broadens matching (fewer false "missing" flags), doesn't narrow it.

---

## BUG-003: Password reset redirecting to localhost
**Date**: 2026-02-11
**File**: `frontend/src/components/LoginScreen.jsx`
**Symptom**: Password reset email link redirected to `http://localhost:3000` instead of production.
**Root Cause**: `redirectTo` used `window.location.origin` which resolves to localhost during development.
**Fix**: Hardcoded `redirectTo: 'https://app.graider.live'`.
**Regression risk**: None for production. Dev password resets will redirect to production URL (acceptable).

---

## BUG-004: PASSWORD_RECOVERY event not caught reliably
**Date**: 2026-02-11
**File**: `frontend/src/App.jsx`
**Symptom**: After clicking password reset link, the "Set New Password" form didn't appear — user went straight to login or the main app.
**Root Cause**: Supabase JS SDK fires `PASSWORD_RECOVERY` event and consumes the URL hash tokens before the `onAuthStateChange` listener is registered. Race condition.
**Fix**: Synchronously check `window.location.hash` for `type=recovery` in the `useState` initializer (runs before any async code). This ensures the recovery state is captured before Supabase processes it.
**Regression risk**: Low. Hash check is read-only and only sets initial state.

---

## Template for new entries

```
## BUG-XXX: [Short description]
**Date**: YYYY-MM-DD
**File**: `filename` — `function_name()` (lines X-Y)
**Symptom**: What the user sees / reports.
**Root Cause**: Why it happens technically.
**Fix**: What was changed and why.
**Test**: How the fix was verified.
**Regression risk**: Low/Medium/High — what could break.
```
