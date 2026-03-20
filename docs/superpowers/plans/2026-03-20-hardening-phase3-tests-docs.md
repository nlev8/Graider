# Hardening Phase 3: Test Coverage + Documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add tests for all untested routes, fix failing tests, update CLAUDE.md. Brings Test Coverage from 6→9 and Documentation from 7→9.

---

## Task 1: Fix the 5 failing tests

**Files:** `tests/test_document_routes.py`

- [ ] Read the failing tests, identify root cause, fix or remove if obsolete (dead folder-based code).

---

## Task 2: Add tests for student portal routes

**Files:** Create `tests/test_student_portal_routes.py`

Test these endpoints:
- `POST /api/publish-assessment` — auth required, content_type stored, settings preserved
- `GET /api/teacher/assessments` — filtered by teacher_id
- `GET /api/teacher/assessment/<code>/results` — scoped to teacher
- `POST /api/teacher/assessment/<code>/toggle` — scoped to teacher
- `DELETE /api/teacher/assessment/<code>` — ownership verified
- `GET /api/student/join/<code>` — returns sanitized assessment (no answers)
- `POST /api/student/submit/<code>` — grading works, duplicate prevention, availability window enforcement
- `grade_instant_only()` — MC/TF/matching scoring
- `grade_student_submission()` — full grading including AI path (mocked)

---

## Task 3: Add tests for student account routes

**Files:** Create `tests/test_student_account_routes.py`

Test these endpoints:
- `POST /api/student/login` — email + class code, rate limiting, session creation
- `GET /api/student/dashboard` — returns correct items for enrolled student
- `GET /api/student/content/<id>` — answer keys stripped, type normalized
- `POST /api/student/submit/<content_id>` — grading, late flagging, pending_review
- `POST /api/grade-portal-submission` — teacher regrade

---

## Task 4: Add tests for storage.py

**Files:** Create `tests/test_storage.py`

Test:
- `save()` / `load()` / `delete()` for each key pattern (assignment, lesson, resource, etc.)
- `list_keys()` for each prefix
- `sync_all_to_cloud()` key coverage
- Supabase fallback behavior (when unavailable)
- Retry logic on transient errors
- `_key_to_filepath()` for all key patterns

---

## Task 5: Add path traversal tests

**Files:** Add to existing test files or create `tests/test_security.py`

Test:
- Download endpoints reject `../` in filename
- Assignment load rejects `../../etc/passwd` in name
- Saved assessment load/delete reject traversal attempts

---

## Task 6: Update CLAUDE.md

- [ ] Add missing API endpoints (behavior_routes, automation_routes, notebooklm_routes, survey_routes, assignment_player_routes)
- [ ] Add missing Supabase tables (teacher_data, student_history, student_sessions, submission_confirmations)
- [ ] Document the two publish paths and when each is used
- [ ] Update "Last updated" date

---

## Verification

- [ ] Run full test suite — all must pass (0 failures)
- [ ] Coverage report: `python -m pytest tests/ --cov=backend --cov-report=term-missing`

**Expected score improvement:**
- Test Coverage: 6 → 9/10
- Documentation: 7 → 9/10
