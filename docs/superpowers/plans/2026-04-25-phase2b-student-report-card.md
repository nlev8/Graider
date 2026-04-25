# Phase 2b — Student Report Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-student drill-down opened from the Phase 2 Progress Rank grid — clicking a student row slides in a side drawer with that student's mastery trajectory and per-standard breakdown.

**Architecture:** New backend endpoint `GET /api/teacher/class/<class_id>/student/<student_id>/report-card` reusing the existing `_select_submissions_by_mode` and `_aggregate_mastery_for_student` helpers in `backend/routes/student_portal_routes.py`, with bridge code to convert their dict output to an array and enrich `contributing_submissions`. New `StudentReportCard.jsx` drawer rendered inside the existing `ProgressRankGrid.jsx` at z-index 9500 (below the existing cell popover modal at 9999).

**Tech Stack:** Flask + Supabase + recharts. Reuses Phase 1's `standards_mastery` rollup and Phase 2's helpers without modification.

**Spec:** `docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md` at HEAD `38e6f8a` on branch `spec/phase2b-student-report-card`. APPROVED after 2 rounds of Codex review.

**Single-PR scope:** All work lands on one branch `phase2b/student-report-card` opened off `main` (after this docs PR merges).

---

## File Structure

**Files created:**
- `frontend/src/tabs/StudentReportCard.jsx` — drawer component (~200 LOC)
- `tests/test_student_report_card.py` — 20 cases total: 12 endpoint cases per spec § Testing + 4 unit tests for `_build_standards_breakdown_for_student` + 4 unit tests for `_build_trajectory_for_student`

**Files modified:**
- `backend/routes/student_portal_routes.py` — add 1 new route handler `get_student_report_card` + 1 helper `_build_standards_breakdown_for_student`
- `frontend/src/tabs/ProgressRankGrid.jsx` — add `selectedStudent` state, `openReportCard` helper, click handler on student-name `<td>`, render the drawer
- `frontend/src/services/api.js` — add `getStudentReportCard(classId, studentId, attemptMode)` client

**Files NOT touched:**
- Clever / ClassLink / OneRoster contracts (199 SIS tests protect)
- `backend/services/grading_service.py` — `_build_standards_mastery` already does what we need from Phase 1
- `mypy.ini` / `.github/workflows/ci.yml` / `setup.cfg` / `requirements*.{in,txt}`
- `get_class_progress_rank` — its raw `jsonify({"error":...}), 403` pattern is pre-existing and out of scope for this PR; new code uses `error_response(...)` instead.

---

## Branching

After this docs PR (containing the spec + plan) merges, create the implementation branch:

```bash
git checkout main && git pull
git checkout -b phase2b/student-report-card
```

All implementation tasks below land on `phase2b/student-report-card`.

---

## Task 1: Backend bridge helper (pure function, TDD)

The existing `_aggregate_mastery_for_student` returns a `dict[code → mastery]` and its `contributing_submissions` entries omit `submitted_at` and `percentage`. We need a small pure helper that takes that dict and produces the spec's `standards_breakdown` array (sorted worst-first) with enriched `contributing_submissions`.

Doing this as a pure helper keeps it independently testable and avoids tangling it with the route handler.

**Files:**
- Modify: `backend/routes/student_portal_routes.py` (add helper near line 230, after `_aggregate_mastery_for_student`)
- Test: `tests/test_student_report_card.py` (new file — first test goes here)

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_student_report_card.py`:

```python
"""Tests for the student report card endpoint and bridge helper.

Spec: docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Bridge helper unit tests ============

class TestBuildStandardsBreakdownForStudent:
    """_build_standards_breakdown_for_student: dict → sorted array + enrichment."""

    def test_empty_input_returns_empty_array(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        result = _build_standards_breakdown_for_student({}, {})
        assert result == []

    def test_single_standard_passes_through_with_code(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {
                "percentage": 75,
                "points_earned": 15,
                "points_possible": 20,
                "question_count": 4,
                "contributing_submissions": [
                    {"submission_id": "sub-1", "title": "Quiz 1",
                     "points_earned": 15, "points_possible": 20, "attempt_number": 1},
                ],
            },
        }
        submission_lookup = {
            "sub-1": {"submitted_at": "2026-04-12T15:30:00Z", "percentage": 70},
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)
        assert len(result) == 1
        assert result[0]["code"] == "MA.6.AR.1.1"
        assert result[0]["percentage"] == 75
        assert result[0]["points_earned"] == 15
        # contributing_submission enriched with submitted_at + percentage
        cs = result[0]["contributing_submissions"][0]
        assert cs["submission_id"] == "sub-1"
        assert cs["submitted_at"] == "2026-04-12T15:30:00Z"
        assert cs["percentage"] == 75.0  # 15/20 * 100

    def test_multiple_standards_sorted_worst_first(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {"percentage": 90, "points_earned": 18, "points_possible": 20,
                            "question_count": 4, "contributing_submissions": []},
            "MA.6.AR.2.1": {"percentage": 50, "points_earned": 5, "points_possible": 10,
                            "question_count": 2, "contributing_submissions": []},
            "MA.6.AR.3.1": {"percentage": 75, "points_earned": 15, "points_possible": 20,
                            "question_count": 4, "contributing_submissions": []},
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, {})
        # ASC by percentage (worst first)
        assert [r["code"] for r in result] == ["MA.6.AR.2.1", "MA.6.AR.3.1", "MA.6.AR.1.1"]

    def test_contributing_submission_missing_in_lookup_keeps_existing_fields(self):
        """If submission_lookup doesn't have an entry for a contributor, the
        contributor still appears with its original fields (no submitted_at/
        percentage enrichment, but not dropped)."""
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {
                "percentage": 75, "points_earned": 15, "points_possible": 20,
                "question_count": 4,
                "contributing_submissions": [
                    {"submission_id": "sub-missing", "title": "Quiz 1",
                     "points_earned": 15, "points_possible": 20, "attempt_number": 1},
                ],
            },
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, {})
        cs = result[0]["contributing_submissions"][0]
        assert cs["submission_id"] == "sub-missing"
        # No submitted_at because lookup miss; percentage still computed
        assert "submitted_at" not in cs or cs["submitted_at"] is None
        assert cs["percentage"] == 75.0  # 15/20 — computed from points, not lookup
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
source venv/bin/activate
pytest tests/test_student_report_card.py::TestBuildStandardsBreakdownForStudent -v
```
Expected: 4 FAIL — `_build_standards_breakdown_for_student` doesn't exist yet.

- [ ] **Step 1.3: Implement the helper**

Edit `backend/routes/student_portal_routes.py`. After the existing `_aggregate_mastery_for_student` function (which ends around line 232 with `return result`), add:

```python
def _build_standards_breakdown_for_student(mastery_by_code, submission_lookup):
    """Convert _aggregate_mastery_for_student's dict output to the
    standards_breakdown array shape required by the report-card endpoint.

    - Sorts ASC by percentage (worst-first) per Phase 2b spec.
    - Enriches each contributing_submission with `submitted_at` and
      `percentage` (computed from points_earned / points_possible).
      Pulls `submitted_at` from `submission_lookup` (a dict keyed by
      submission_id). Keeps the existing 10-cap from the upstream helper.

    Args:
        mastery_by_code: dict from _aggregate_mastery_for_student
        submission_lookup: dict[submission_id -> submission row] for enrichment
    Returns:
        list[dict] sorted by percentage ASC; each dict has
        {code, percentage, points_earned, points_possible, question_count,
         contributing_submissions: [...]} with each contributing_submission
        having submission_id, title, attempt_number, points_earned,
        points_possible, percentage, submitted_at.
    """
    rows = []
    for code, m in mastery_by_code.items():
        enriched_contribs = []
        for c in m.get("contributing_submissions", []):
            pts_poss = c.get("points_possible") or 0
            pts_earned = c.get("points_earned") or 0
            pct = round((pts_earned / pts_poss) * 100, 1) if pts_poss > 0 else 0
            sub_row = submission_lookup.get(c.get("submission_id")) or {}
            enriched_contribs.append({
                "submission_id": c.get("submission_id"),
                "title": c.get("title", ""),
                "attempt_number": c.get("attempt_number"),
                "points_earned": pts_earned,
                "points_possible": pts_poss,
                "percentage": pct,
                "submitted_at": sub_row.get("submitted_at"),
            })
        rows.append({
            "code": code,
            "percentage": m.get("percentage", 0),
            "points_earned": m.get("points_earned", 0),
            "points_possible": m.get("points_possible", 0),
            "question_count": m.get("question_count", 0),
            "contributing_submissions": enriched_contribs,
        })
    rows.sort(key=lambda r: r["percentage"])  # ASC = worst-first
    return rows
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
pytest tests/test_student_report_card.py::TestBuildStandardsBreakdownForStudent -v
```
Expected: 4 PASS.

- [ ] **Step 1.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_student_report_card.py
git commit -m "feat(report-card): bridge helper _build_standards_breakdown_for_student"
```

---

## Task 2: Trajectory builder (pure function, TDD)

Same TDD pattern as Task 1: a pure helper that takes a list of submissions and produces the chronological `trajectory` array. Null `submitted_at` sorts to the END per spec § Trajectory null-ordering.

**Files:**
- Modify: `backend/routes/student_portal_routes.py` (add second helper near the first one)
- Modify: `tests/test_student_report_card.py` (extend with new test class)

- [ ] **Step 2.1: Write the failing test**

Append to `tests/test_student_report_card.py`:

```python
class TestBuildTrajectoryForStudent:
    """_build_trajectory_for_student: list[submission] → chronological list."""

    def test_empty_input_returns_empty_array(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        assert _build_trajectory_for_student([], {}) == []

    def test_orders_ascending_by_submitted_at(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s2", "content_id": "c1", "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 80, "attempt_number": 1, "results": {"points_earned": 8, "points_possible": 10}},
            {"id": "s1", "content_id": "c1", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 60, "attempt_number": 1, "results": {"points_earned": 6, "points_possible": 10}},
            {"id": "s3", "content_id": "c1", "submitted_at": "2026-04-20T10:00:00Z",
             "percentage": 90, "attempt_number": 2, "results": {"points_earned": 9, "points_possible": 10}},
        ]
        content_titles = {"c1": "Quiz 1"}
        result = _build_trajectory_for_student(subs, content_titles)
        assert [r["submission_id"] for r in result] == ["s1", "s2", "s3"]
        assert result[0]["title"] == "Quiz 1"
        assert result[0]["percentage"] == 60
        assert result[0]["points_earned"] == 6
        assert result[0]["points_possible"] == 10

    def test_null_submitted_at_sorted_to_end(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s_null", "content_id": "c1", "submitted_at": None,
             "percentage": 50, "attempt_number": 1, "results": {}},
            {"id": "s_dated", "content_id": "c1", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 70, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {"c1": "Q"})
        # Null sorts to END
        assert [r["submission_id"] for r in result] == ["s_dated", "s_null"]

    def test_missing_content_title_uses_empty_string(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s1", "content_id": "c-missing", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 70, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {})
        assert result[0]["title"] == ""
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
pytest tests/test_student_report_card.py::TestBuildTrajectoryForStudent -v
```
Expected: 4 FAIL — `_build_trajectory_for_student` doesn't exist yet.

- [ ] **Step 2.3: Implement the helper**

Edit `backend/routes/student_portal_routes.py`. After `_build_standards_breakdown_for_student`, add:

```python
def _build_trajectory_for_student(submissions, content_titles):
    """Build the chronological trajectory array for the report card.

    Sorted ASC by submitted_at; submissions with null submitted_at are
    appended at the END (we treat them as the "most recent" since their
    real position is unknown, and we'd rather not pollute the early-trend
    reading).

    Args:
        submissions: list of submission rows (id, content_id, submitted_at,
                     percentage, attempt_number, results.points_earned/possible).
        content_titles: dict[content_id -> title] for the title field.
    Returns:
        list[dict] of {submission_id, content_id, title, submitted_at,
                       percentage, attempt_number, points_earned,
                       points_possible}.
    """
    def sort_key(s):
        ts = s.get("submitted_at")
        # None sorts last: tuple key (1, "") for null, (0, ts) for non-null
        return (0, ts) if ts else (1, "")

    sorted_subs = sorted(submissions, key=sort_key)
    out = []
    for s in sorted_subs:
        results = s.get("results") or {}
        out.append({
            "submission_id": s.get("id"),
            "content_id": s.get("content_id"),
            "title": content_titles.get(s.get("content_id"), ""),
            "submitted_at": s.get("submitted_at"),
            "percentage": s.get("percentage"),
            "attempt_number": s.get("attempt_number"),
            "points_earned": results.get("points_earned"),
            "points_possible": results.get("points_possible"),
        })
    return out
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
pytest tests/test_student_report_card.py::TestBuildTrajectoryForStudent -v
```
Expected: 4 PASS.

- [ ] **Step 2.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_student_report_card.py
git commit -m "feat(report-card): trajectory builder _build_trajectory_for_student"
```

---

## Task 3: Route handler — auth/authz (TDD)

Land the route skeleton with auth + ownership + student-in-class checks. Happy path and edge cases follow in Tasks 4-5.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_student_report_card.py`

- [ ] **Step 3.1: Write the failing test**

Append to `tests/test_student_report_card.py` (above the helper test classes is fine, but for ease keep appending):

```python
# ============ Route handler tests ============

@pytest.fixture
def app():
    """Create Flask app in test mode."""
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher_headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def _make_chain(execute_data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=execute_data if execute_data is not None else [])
    return chain


def _multi_table_sb(table_map):
    """Mock supabase that returns different chains per table name."""
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


class TestReportCardAuthz:
    """Auth + class-ownership + student-in-class checks."""

    def test_unauthenticated_returns_401(self, client):
        # No X-Test-Teacher-Id header → require_teacher rejects
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        # Class belongs to a different teacher
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        # RFC 7807 envelope (Phase 5d PR 1)
        assert body.get('type') == 'https://graider.live/errors/forbidden'
        assert body.get('status') == 403
        # Backward-compat error field still present
        assert 'error' in body

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_student_not_in_class_returns_404(self, mock_sb_fn, client, teacher_headers):
        # Class is owned but class_students has no enrollment for stu-X
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [],  # not enrolled
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-X/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 404
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/not-found'
        assert body.get('status') == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_orphan_enrollment_returns_404(self, mock_sb_fn, client, teacher_headers):
        # class_students lists the student but students row is gone
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-orphan'}],
            'students': [],  # row missing
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-orphan/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 404
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest tests/test_student_report_card.py::TestReportCardAuthz -v
```
Expected: 4 FAIL — endpoint doesn't exist (404 from Flask routing or 405 from method-not-allowed).

- [ ] **Step 3.3: Implement the route handler skeleton**

Edit `backend/routes/student_portal_routes.py`. Find `get_class_progress_rank` (around line 1203). Just AFTER its closing brace (around line 1316), add the new endpoint. Imports: `error_response` is in `backend.utils.errors` — find the existing import block at the top of the file and add `from backend.utils.errors import error_response, handle_route_errors` (the second import is likely already present; verify and only add what's missing).

Add the new route:

```python
@student_portal_bp.route('/api/teacher/class/<class_id>/student/<student_id>/report-card', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_report_card(class_id, student_id):
    """Return per-student report card: trajectory + standards breakdown.

    Class-scoped view of a single student's mastery within ONE class.
    Reuses _select_submissions_by_mode + _aggregate_mastery_for_student
    + bridge helpers to assemble the response.

    Spec: docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md
    """
    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Student-in-class check
    enrollment = db.table('class_students').select('student_id').eq(
        'class_id', class_id
    ).eq('student_id', student_id).execute()
    if not enrollment.data:
        return error_response("Student not in class", 404)

    # 3) Fetch student name (orphan-enrollment guard)
    student_row = db.table('students').select(
        'id, first_name, last_name'
    ).eq('id', student_id).execute()
    if not student_row.data:
        return error_response("Student not in class", 404)
    student_name = (
        (student_row.data[0].get('first_name') or '') + ' ' +
        (student_row.data[0].get('last_name') or '')
    ).strip()

    # Skeleton: empty arrays. Happy-path data fetch + aggregation lands in Task 4.
    return jsonify({
        "student_id": student_id,
        "student_name": student_name,
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "trajectory": [],
        "standards_breakdown": [],
    })
```

- [ ] **Step 3.4: Run tests to verify they pass**

```bash
pytest tests/test_student_report_card.py::TestReportCardAuthz -v
```
Expected: 4 PASS.

- [ ] **Step 3.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_student_report_card.py
git commit -m "feat(report-card): route handler skeleton + authz checks"
```

---

## Task 4: Route handler — happy path data fetch (TDD)

Land the data fetch + aggregation. Happy path returns trajectory + standards_breakdown populated.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_student_report_card.py`

- [ ] **Step 4.1: Write the failing test**

Append to `tests/test_student_report_card.py`:

```python
class TestReportCardHappyPath:
    """Happy-path data assembly: trajectory + breakdown."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_happy_path_returns_trajectory_and_breakdown(self, mock_sb_fn, client, teacher_headers):
        # Two assessments, two submissions for our student
        mastery_a = {
            "MA.6.AR.1.1": {"points_earned": 8, "points_possible": 10, "question_count": 2},
        }
        mastery_b = {
            "MA.6.AR.1.1": {"points_earned": 5, "points_possible": 10, "question_count": 2},
            "MA.6.AR.2.1": {"points_earned": 2, "points_possible": 10, "question_count": 2},
        }
        subs = [
            {"id": "sub-1", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 80, "results": {"standards_mastery": mastery_a,
                                            "points_earned": 8, "points_possible": 10},
             "status": "graded"},
            {"id": "sub-2", "student_id": "stu-1", "content_id": "ct-2",
             "attempt_number": 1, "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 35, "results": {"standards_mastery": mastery_b,
                                            "points_earned": 7, "points_possible": 20},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'Jane', 'last_name': 'Doe'}],
            'published_content': [
                {'id': 'ct-1', 'title': 'Quiz 1', 'content_type': 'assessment'},
                {'id': 'ct-2', 'title': 'Quiz 2', 'content_type': 'assessment'},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['student_id'] == 'stu-1'
        assert body['student_name'] == 'Jane Doe'
        assert body['class_id'] == 'cls-1'
        assert body['class_name'] == 'Period 3'
        assert body['attempt_mode'] == 'latest'
        # Trajectory is ASC by submitted_at (oldest first)
        assert [t['submission_id'] for t in body['trajectory']] == ['sub-1', 'sub-2']
        # Each trajectory entry includes full shape per spec
        assert body['trajectory'][0]['title'] == 'Quiz 1'
        assert body['trajectory'][0]['percentage'] == 80
        # standards_breakdown sorted worst-first
        codes = [s['code'] for s in body['standards_breakdown']]
        assert codes[0] == 'MA.6.AR.2.1'  # 20% — worst
        # contributing_submissions enriched with submitted_at + percentage + submission_id
        cs = body['standards_breakdown'][0]['contributing_submissions'][0]
        assert cs['submission_id'] == 'sub-2'
        assert cs['submitted_at'] == '2026-04-15T10:00:00Z'
        assert 'percentage' in cs

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_no_submissions_returns_empty_arrays_with_200(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'Jane', 'last_name': 'Doe'}],
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['trajectory'] == []
        assert body['standards_breakdown'] == []
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
pytest tests/test_student_report_card.py::TestReportCardHappyPath -v
```
Expected: 1 FAIL (`test_returns_trajectory_and_breakdown` — skeleton returns empty arrays). The empty-state test passes already by accident; rerunning after Task 4.3 should keep it green.

- [ ] **Step 4.3: Replace the skeleton route's return with full data fetch**

In `backend/routes/student_portal_routes.py`, replace the `return jsonify({... empty arrays ...})` at the end of `get_student_report_card` with the data-fetch logic:

```python
    # 4) Fetch all class assessments/assignments
    content_rows = db.table('published_content').select(
        'id, title, content_type'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()
    content_ids = [c['id'] for c in (content_rows.data or [])]
    content_titles = {c['id']: c.get('title', '') for c in (content_rows.data or [])}

    if not content_ids:
        return jsonify({
            "student_id": student_id,
            "student_name": student_name,
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "trajectory": [],
            "standards_breakdown": [],
        })

    # 5) Fetch all non-draft submissions for this student in those contents
    subs_rows = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
    ).eq('student_id', student_id).in_('content_id', content_ids).neq(
        'status', 'draft'
    ).execute()
    submissions = subs_rows.data or []

    # 6) Build trajectory from ALL submissions chronologically
    trajectory = _build_trajectory_for_student(submissions, content_titles)

    # 7) Build standards_breakdown via existing helpers + bridge code
    from collections import defaultdict
    subs_by_content = defaultdict(list)
    for s in submissions:
        cid = s.get('content_id')
        if cid:
            subs_by_content[cid].append(s)
    selected = _select_submissions_by_mode(subs_by_content, attempt_mode)
    mastery_by_code = _aggregate_mastery_for_student(selected, content_titles, attempt_mode)
    submission_lookup = {s.get('id'): s for s in submissions if s.get('id')}
    standards_breakdown = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)

    return jsonify({
        "student_id": student_id,
        "student_name": student_name,
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "trajectory": trajectory,
        "standards_breakdown": standards_breakdown,
    })
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
pytest tests/test_student_report_card.py -v
```
Expected: ALL pass (10 from prior tasks + 2 new = 12).

- [ ] **Step 4.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_student_report_card.py
git commit -m "feat(report-card): happy-path data fetch + aggregation"
```

---

## Task 5: Route handler — attempt_mode + edge cases (TDD)

Lock down attempt_mode variations, malformed mastery handling, null `submitted_at`, and invalid mode fallback.

**Files:**
- Modify: `backend/routes/student_portal_routes.py` (defensive malformed handling)
- Modify: `tests/test_student_report_card.py`

- [ ] **Step 5.1: Write the failing tests**

Append to `tests/test_student_report_card.py`:

```python
class TestReportCardAttemptModes:
    """Verify attempt_mode latest/best/average are honored end-to-end."""

    def _setup_three_attempts(self, mock_sb_fn):
        """One assessment, three attempts: 50%, 90%, 70%."""
        masteries = [
            {"MA.6.AR.1.1": {"points_earned": 5, "points_possible": 10, "question_count": 2}},
            {"MA.6.AR.1.1": {"points_earned": 9, "points_possible": 10, "question_count": 2}},
            {"MA.6.AR.1.1": {"points_earned": 7, "points_possible": 10, "question_count": 2}},
        ]
        subs = []
        for i, (pct, mast) in enumerate(zip([50, 90, 70], masteries), start=1):
            subs.append({
                "id": f"sub-{i}", "student_id": "stu-1", "content_id": "ct-1",
                "attempt_number": i, "submitted_at": f"2026-04-{10+i}T10:00:00Z",
                "percentage": pct, "results": {"standards_mastery": mast,
                                                "points_earned": pct/10,
                                                "points_possible": 10},
                "status": "graded",
            })
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_latest_picks_most_recent_per_content(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=latest',
            headers=teacher_headers,
        )
        body = resp.get_json()
        # Latest attempt #3 had 70% on the standard (7/10)
        assert body['standards_breakdown'][0]['percentage'] == 70.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_best_picks_highest_per_content(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=best',
            headers=teacher_headers,
        )
        body = resp.get_json()
        # Best attempt #2 had 90% on the standard (9/10)
        assert body['standards_breakdown'][0]['percentage'] == 90.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_average_aggregates_attempts(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=average',
            headers=teacher_headers,
        )
        body = resp.get_json()
        # Average across 50/90/70 = 70.0
        assert body['standards_breakdown'][0]['percentage'] == 70.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_invalid_attempt_mode_falls_back_to_latest(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=garbage',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # Should behave as 'latest'
        assert body['attempt_mode'] == 'latest'
        assert body['standards_breakdown'][0]['percentage'] == 70.0


class TestReportCardEdgeCases:
    """Malformed mastery, null submitted_at, etc."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_standards_mastery_skips_submission(self, mock_sb_fn, client, teacher_headers, caplog):
        # results.standards_mastery is a list (not dict) — should NOT 500
        import logging
        caplog.set_level(logging.WARNING, logger="backend.routes.student_portal_routes")
        subs = [
            {"id": "sub-good", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 80,
             "results": {"standards_mastery": {"MA.6.AR.1.1": {"points_earned": 8, "points_possible": 10, "question_count": 2}},
                         "points_earned": 8, "points_possible": 10},
             "status": "graded"},
            {"id": "sub-bad", "student_id": "stu-1", "content_id": "ct-2",
             "attempt_number": 1, "submitted_at": "2026-04-12T10:00:00Z", "percentage": 60,
             "results": {"standards_mastery": ["malformed", "list"],  # WRONG TYPE
                         "points_earned": 6, "points_possible": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [
                {'id': 'ct-1', 'title': 'Q1', 'content_type': 'assessment'},
                {'id': 'ct-2', 'title': 'Q2', 'content_type': 'assessment'},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Both submissions in trajectory (trajectory uses submitted_at + percentage,
        # not standards_mastery — so malformed mastery doesn't drop them here).
        assert {t['submission_id'] for t in body['trajectory']} == {'sub-good', 'sub-bad'}
        # Only sub-good's mastery contributes to breakdown — sub-bad's
        # malformed standards_mastery sanitized to empty.
        assert len(body['standards_breakdown']) == 1
        assert body['standards_breakdown'][0]['code'] == 'MA.6.AR.1.1'
        # WARNING was logged with the submission id
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('malformed standards_mastery' in r.getMessage() and 'sub-bad' in r.getMessage()
                   for r in warnings), \
            "expected a WARNING log mentioning malformed standards_mastery and sub-bad"

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_latest_malformed_does_not_fall_back_to_older_mastery(self, mock_sb_fn, client, teacher_headers):
        """attempt_mode=latest must still pick the genuinely latest attempt
        even when its mastery is malformed (sanitized to empty), NOT silently
        revert to an older attempt's good mastery."""
        good_mastery = {"MA.6.AR.1.1": {"points_earned": 9, "points_possible": 10, "question_count": 2}}
        subs = [
            # Earlier attempt with GOOD mastery
            {"id": "sub-old", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 90,
             "results": {"standards_mastery": good_mastery,
                         "points_earned": 9, "points_possible": 10},
             "status": "graded"},
            # LATEST attempt with malformed mastery
            {"id": "sub-latest", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 2, "submitted_at": "2026-04-15T10:00:00Z", "percentage": 30,
             "results": {"standards_mastery": "broken",  # WRONG TYPE
                         "points_earned": 3, "points_possible": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=latest',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # 'latest' selected sub-latest (attempt 2), whose mastery sanitized
        # to {}; therefore standards_breakdown is EMPTY — NOT showing the
        # older attempt's 90% mastery on MA.6.AR.1.1.
        assert body['standards_breakdown'] == []
        # Both submissions still appear in trajectory
        assert len(body['trajectory']) == 2

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_individual_malformed_standard_value_skipped(self, mock_sb_fn, client, teacher_headers, caplog):
        """A submission whose standards_mastery dict is well-formed at the
        outer level but has a non-dict value for one entry: that one entry
        is dropped, the rest of the dict is preserved."""
        import logging
        caplog.set_level(logging.WARNING, logger="backend.routes.student_portal_routes")
        mixed = {
            "MA.6.AR.1.1": {"points_earned": 8, "points_possible": 10, "question_count": 2},
            "MA.6.AR.2.1": "not-a-dict-broken",  # WRONG TYPE on this entry
        }
        subs = [{
            "id": "sub-mixed", "student_id": "stu-1", "content_id": "ct-1",
            "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 80,
            "results": {"standards_mastery": mixed, "points_earned": 8, "points_possible": 10},
            "status": "graded",
        }]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Only the well-formed standard appears
        codes = [s['code'] for s in body['standards_breakdown']]
        assert codes == ['MA.6.AR.1.1']
        # WARNING mentions the malformed entry's code
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('MA.6.AR.2.1' in r.getMessage() for r in warnings), \
            "expected a WARNING mentioning the malformed entry's standard code"

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_null_submitted_at_sorted_to_end_of_trajectory(self, mock_sb_fn, client, teacher_headers):
        subs = [
            {"id": "sub-null", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": None, "percentage": 50,
             "results": {"standards_mastery": {}, "points_earned": 5, "points_possible": 10},
             "status": "graded"},
            {"id": "sub-dated", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 2, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 70,
             "results": {"standards_mastery": {}, "points_earned": 7, "points_possible": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Null submitted_at must be LAST in trajectory
        assert [t['submission_id'] for t in body['trajectory']] == ['sub-dated', 'sub-null']
```

- [ ] **Step 5.2: Run tests to verify which pass and which fail**

```bash
pytest tests/test_student_report_card.py -v
```
Expected:
- Most attempt_mode tests will pass (the underlying `_select_submissions_by_mode` already supports them).
- `test_malformed_standards_mastery_skips_submission` will FAIL: the existing `_aggregate_mastery_for_student` calls `mastery.items()` on the list and raises `AttributeError` → 500.
- `test_null_submitted_at_sorted_to_end` will PASS (already handled by `_build_trajectory_for_student`'s sort key).

- [ ] **Step 5.3: Add defensive malformed handling (sanitize-in-place, NOT drop)**

The naive approach — filter whole submissions out before `_select_submissions_by_mode` — breaks attempt-mode semantics: if a student's LATEST attempt has malformed mastery and an EARLIER attempt has good mastery, dropping the latest would make `attempt_mode=latest` silently fall back to the earlier attempt and report stale mastery. Wrong outcome.

The correct approach is to sanitize each submission's `standards_mastery` IN PLACE: replace missing/non-dict mastery with `{}` (empty contribution but the submission is still selected by attempt_mode), and drop individual non-dict mastery values within an otherwise-valid dict. Log a WARNING per malformed entry.

Add a small helper INSIDE `get_student_report_card` (or near it as a module-level helper — your choice). Then sanitize submissions BEFORE building `subs_by_content`.

Replace this section (in step 4.3's added code):
```python
    # 6) Build trajectory from ALL submissions chronologically
    trajectory = _build_trajectory_for_student(submissions, content_titles)

    # 7) Build standards_breakdown via existing helpers + bridge code
    from collections import defaultdict
    subs_by_content = defaultdict(list)
    for s in submissions:
        cid = s.get('content_id')
        if cid:
            subs_by_content[cid].append(s)
```

With:
```python
    # 6) Build trajectory from ALL submissions chronologically
    # (trajectory tolerates missing standards_mastery — only uses
    # submitted_at + percentage from the row.)
    trajectory = _build_trajectory_for_student(submissions, content_titles)

    # 7) Sanitize standards_mastery IN PLACE so attempt-mode selection
    # still sees every submission. A malformed-mastery submission stays
    # selectable (so 'latest' picks the truly latest attempt), but its
    # mastery contribution is empty.
    def _sanitize_standards_mastery(sub):
        results = sub.get('results') or {}
        raw = results.get('standards_mastery')
        if raw is None:
            results['standards_mastery'] = {}
            sub['results'] = results
            return
        if not isinstance(raw, dict):
            _logger.warning(
                "malformed standards_mastery (type=%s) in submission %s — treating as empty",
                type(raw).__name__, sub.get('id'),
            )
            results['standards_mastery'] = {}
            sub['results'] = results
            return
        # Valid dict at the outer level; drop individual non-dict values.
        cleaned = {}
        for code, m in raw.items():
            if isinstance(m, dict):
                cleaned[code] = m
            else:
                _logger.warning(
                    "malformed standards_mastery entry (code=%s, type=%s) in submission %s — skipping entry",
                    code, type(m).__name__, sub.get('id'),
                )
        results['standards_mastery'] = cleaned
        sub['results'] = results

    for s in submissions:
        _sanitize_standards_mastery(s)

    # 8) Build standards_breakdown via existing helpers + bridge code
    from collections import defaultdict
    subs_by_content = defaultdict(list)
    for s in submissions:
        cid = s.get('content_id')
        if cid:
            subs_by_content[cid].append(s)
```

(The downstream `_select_submissions_by_mode` and `_aggregate_mastery_for_student` calls don't change — they operate on the sanitized submissions, which always have a `dict` at `results['standards_mastery']`.)

- [ ] **Step 5.4: Run tests to verify all pass**

```bash
pytest tests/test_student_report_card.py -v
```
Expected: ALL pass (12 from prior tasks + 8 new in this task = 20).

- [ ] **Step 5.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_student_report_card.py
git commit -m "feat(report-card): attempt_mode + malformed-mastery handling"
```

---

## Task 6: Frontend API client

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 6.1: Add the client function**

Edit `frontend/src/services/api.js`. Find `getClassProgressRank` (around line 1648). Just AFTER it, add:

```javascript
export async function getStudentReportCard(classId, studentId, attemptMode) {
  var mode = attemptMode || 'latest';
  var params = new URLSearchParams({ attempt_mode: mode });
  return fetchApi(
    '/api/teacher/class/' + encodeURIComponent(classId) +
    '/student/' + encodeURIComponent(studentId) +
    '/report-card?' + params.toString()
  );
}
```

- [ ] **Step 6.2: Verify no existing imports break**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds (Vite reports green output and writes `backend/static/`). No new errors. The new export doesn't change the module's other behavior.

- [ ] **Step 6.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/services/api.js
git commit -m "feat(report-card): frontend API client getStudentReportCard"
```

---

## Task 7: StudentReportCard component

**Files:**
- Create: `frontend/src/tabs/StudentReportCard.jsx`

- [ ] **Step 7.1: Create the component**

Create `frontend/src/tabs/StudentReportCard.jsx`:

```javascript
import React, { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import * as api from "../services/api";

function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: "—" };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    var d = new Date(iso);
    return (d.getMonth() + 1) + "/" + d.getDate();
  } catch (e) {
    return "—";
  }
}

export default function StudentReportCard({ classId, studentId, attemptMode, onClose }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [expandedStandard, setExpandedStandard] = useState(null);

  useEffect(function() {
    if (!classId || !studentId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getStudentReportCard(classId, studentId, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load report card');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load report card');
      })
      .finally(function() {
        if (!cancelled) setLoading(false);
      });
    return function() { cancelled = true; };
  }, [classId, studentId, attemptMode]);

  // Drawer (z-index 9500, BELOW cell popover at 9999)
  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        zIndex: 9500, display: "flex", justifyContent: "flex-end",
      }}
      onClick={onClose}
    >
      {/* Backdrop */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)" }} />

      {/* Drawer panel */}
      <div
        className="glass-card"
        style={{
          position: "relative", width: "min(600px, 100vw)", height: "100%",
          background: "var(--card-bg)", borderLeft: "1px solid var(--glass-border)",
          boxShadow: "-4px 0 20px rgba(0,0,0,0.2)", padding: "24px",
          overflowY: "auto",
        }}
        onClick={function(e) { e.stopPropagation(); }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{data ? data.student_name : 'Student'}</h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              {data ? data.class_name : ''} {String.fromCharCode(8226)} attempt mode: {attemptMode || 'latest'}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.4rem" }}
          >
            {String.fromCharCode(10005)}
          </button>
        </div>

        {loading && (
          <div style={{ textAlign: "center", padding: "60px" }}>
            <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading...</p>
          </div>
        )}

        {error && (
          <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>{error}</div>
        )}

        {data && !loading && !error && (
          <div>
            {/* Trajectory chart */}
            <div style={{ marginBottom: "24px" }}>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Mastery trajectory</h4>
              {data.trajectory.length === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  This student hasn{String.fromCharCode(8217)}t submitted anything in this class yet.
                </p>
              ) : (
                <div style={{ width: "100%", height: "200px" }}>
                  <ResponsiveContainer>
                    <LineChart data={data.trajectory.map(function(t) {
                      return {
                        name: formatDate(t.submitted_at),
                        percentage: t.percentage,
                        title: t.title,
                        attempt_number: t.attempt_number,
                      };
                    })}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={function(val, _key, ctx) {
                          var p = ctx && ctx.payload || {};
                          return [val + '%', p.title + ' (attempt ' + p.attempt_number + ')'];
                        }}
                      />
                      <ReferenceLine y={70} stroke="var(--warning)" strokeDasharray="3 3" />
                      <ReferenceLine y={85} stroke="var(--success)" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="percentage" stroke="var(--accent-primary)" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Standards breakdown */}
            <div>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Standards (worst first)</h4>
              {data.standards_breakdown.length === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>No graded standards yet.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {data.standards_breakdown.map(function(s) {
                    var color = masteryColor(s.percentage);
                    var isExpanded = expandedStandard === s.code;
                    return (
                      <div key={s.code} style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "10px 12px", background: color.bg }}>
                        <div
                          onClick={function() { setExpandedStandard(isExpanded ? null : s.code); }}
                          style={{ display: "flex", justifyContent: "space-between", cursor: "pointer", alignItems: "center" }}
                        >
                          <div>
                            <div style={{ fontFamily: "monospace", fontSize: "0.85rem", fontWeight: 700, color: color.text }}>
                              {s.code}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                              {s.points_earned}/{s.points_possible} pts {String.fromCharCode(8226)} {s.question_count} questions
                            </div>
                          </div>
                          <div style={{ fontWeight: 700, color: color.text, fontSize: "1rem" }}>{color.label}</div>
                        </div>
                        {isExpanded && (
                          <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: "1px solid var(--glass-border)", display: "flex", flexDirection: "column", gap: "6px" }}>
                            {s.contributing_submissions.map(function(c, i) {
                              return (
                                <div key={i} style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                                  <strong style={{ color: "var(--text-primary)" }}>{c.title}</strong>
                                  {' '}{String.fromCharCode(8212)}{' '}
                                  {c.points_earned}/{c.points_possible} pts ({c.percentage}%)
                                  {' '}{String.fromCharCode(8226)}{' '}
                                  attempt {c.attempt_number} {String.fromCharCode(8226)} {formatDate(c.submitted_at)}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7.2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds. recharts is already a dependency (verified — used in AnalyticsTab.jsx).

- [ ] **Step 7.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/StudentReportCard.jsx
git commit -m "feat(report-card): StudentReportCard drawer component"
```

---

## Task 8: Wire into ProgressRankGrid

**Files:**
- Modify: `frontend/src/tabs/ProgressRankGrid.jsx`

- [ ] **Step 8.1: Add the import + state + helper**

Edit `frontend/src/tabs/ProgressRankGrid.jsx`. At the top, after the existing imports (line 3 currently has `import * as api from "../services/api";`), add the StudentReportCard import:

```javascript
import StudentReportCard from "./StudentReportCard";
```

Inside the `ProgressRankGrid` function body, find the existing state declarations (lines 13-18 — `data`, `loading`, `error`, `attemptMode`, `strugglingOnly`, `selectedCell`). Add a new state line after `selectedCell`:

```javascript
  var [selectedStudent, setSelectedStudent] = useState(null);
```

Then, AFTER the existing state declarations (but before the `useEffect` block), add the helper:

```javascript
  function openReportCard(student) {
    setSelectedCell(null);          // close any open cell popover (z-index 9999)
    setSelectedStudent(student);    // drawer opens at z-index 9500
  }
```

- [ ] **Step 8.2: Wire the click handler on the student-name cell**

Find the existing student-name `<td>` (around lines 146-148):

```javascript
<td style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)" }}>
  {student.student_name}
</td>
```

Replace with (add `onClick` and `cursor: 'pointer'`):

```javascript
<td
  onClick={function() { openReportCard(student); }}
  style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)", cursor: "pointer" }}
>
  {student.student_name}
</td>
```

- [ ] **Step 8.3: Render the drawer**

Find the existing cell popover render block (starts around line 183 with `{selectedCell && (`). AFTER its closing `)}` (around line 227, just before the final `</div>` of the component's outer wrapper), insert:

```javascript
      {/* Student Report Card drawer (Phase 2b) */}
      {selectedStudent && (
        <StudentReportCard
          classId={classId}
          studentId={selectedStudent.student_id}
          attemptMode={attemptMode}
          onClose={function() { setSelectedStudent(null); }}
        />
      )}
```

- [ ] **Step 8.4: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds.

- [ ] **Step 8.5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/ProgressRankGrid.jsx
git commit -m "feat(report-card): wire drawer into ProgressRankGrid"
```

---

## Task 9: Manual smoke test

**Files:** none modified.

- [ ] **Step 9.1: Start the backend**

```bash
source venv/bin/activate
python -m backend.app
```
Expected: Flask starts on `http://localhost:3000`. Leave running.

- [ ] **Step 9.2: Build + serve frontend**

In a second terminal:
```bash
cd frontend && npm run build
```
Expected: Vite writes assets to `backend/static/`. Backend serves them.

- [ ] **Step 9.3: Open the dashboard**

In a browser, go to `http://localhost:3000`. Sign in (use a teacher account that has at least one class with submitted assessments — pick one from the dashboard's class list).

- [ ] **Step 9.4: Verify the drawer opens and shows real data**

1. Navigate to the Analytics tab.
2. Pick a class from the new "All Classes" dropdown that's not "All Classes".
3. The Progress Rank grid renders.
4. Click any student's name (the leftmost sticky column).
5. Drawer slides in from the right.
6. Verify:
   - [ ] Header shows the student name + class name + attempt mode.
   - [ ] Trajectory chart renders (if the student has at least 2 submissions). Reference lines at 70% and 85% are visible.
   - [ ] Standards list is sorted worst-first; colors match the grid (≥85 green, 70-84 yellow, <70 red).
   - [ ] Click a standard row → contributing_submissions expand inline.
   - [ ] Click outside the drawer or the `×` button → drawer closes.
   - [ ] Switch the grid's attempt mode (Latest / Best / Average) and reopen a student → drawer reflects the new mode.
   - [ ] Student with NO submissions → drawer shows the empty-state message in both sections.

- [ ] **Step 9.5: If any failure, fix + commit**

Each fix gets its own commit (`fix(report-card): <what>`).

If everything passes, no commit needed.

---

## Task 10: Push branch + open PR

**Files:** none modified.

- [ ] **Step 10.1: Push branch**

```bash
git push -u origin phase2b/student-report-card
```

- [ ] **Step 10.2: Open PR**

```bash
gh pr create --title "Phase 2b — Student Report Card (drawer + trajectory + standards breakdown)" --body "$(cat <<'EOF'
## Summary

Adds a per-student drill-down opened from the Phase 2 Progress Rank grid. Clicking a student row slides in a side drawer with that student's mastery trajectory chart and per-standard breakdown.

### Changes
- \`backend/routes/student_portal_routes.py\` — new \`GET /api/teacher/class/<class_id>/student/<student_id>/report-card?attempt_mode=...\` endpoint, plus 2 pure helpers (\`_build_standards_breakdown_for_student\`, \`_build_trajectory_for_student\`). Reuses the existing Phase 2 helpers \`_select_submissions_by_mode\` and \`_aggregate_mastery_for_student\`.
- \`tests/test_student_report_card.py\` (new) — 18 tests covering bridge helpers, authz, happy path, attempt modes, malformed mastery, null timestamps.
- \`frontend/src/tabs/StudentReportCard.jsx\` (new, ~250 LOC) — drawer at z-index 9500 with recharts trajectory + worst-first standards list.
- \`frontend/src/tabs/ProgressRankGrid.jsx\` — clickable student-name cell + drawer render.
- \`frontend/src/services/api.js\` — \`getStudentReportCard\` client.

### Spec
\`docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md\` (APPROVED after 2 rounds of Codex review).

### Compliance
Reads only from \`classes\`, \`class_students\`, \`students\`, \`published_content\`, \`student_submissions\`. Zero SSO / Clever / ClassLink / OneRoster surface changes.

### Test plan
- [x] \`pytest tests/test_student_report_card.py -v\` — 18/18 green
- [x] \`cd frontend && npm run build\` — green
- [x] Manual smoke test passes (drawer opens, trajectory + standards render, attempt-mode switch reflected)
- [ ] CI (8 jobs)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 10.3: Merge after CI green.**

After merge:
```bash
git checkout main && git pull
```

---

## Sequencing + dependencies

**Single PR, sequential tasks:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10.

Tasks 1, 2, 3, 4, 5 are pure backend (TDD). Tasks 6, 7, 8 are pure frontend (build-verified). Task 9 is the integration smoke. Task 10 ships.

Tasks 1+2 (pure helpers) could theoretically run in parallel — both touch only the helper section of `student_portal_routes.py` and add separate test classes. Keep sequential for review-load smoothing.

---

## Testing strategy

- 20 backend tests covering authz (4), happy path (2), all 3 attempt modes + invalid fallback (4), malformed mastery handling (3 — list-shape, latest-malformed-no-fallback, individual-entry-malformed), null timestamps (1), plus 8 helper unit tests for `_build_standards_breakdown_for_student` (4) and `_build_trajectory_for_student` (4).
- Frontend: build verification only (consistent with how Phase 2 shipped). No new unit tests; manual smoke test covers the integration.
- Existing 1671+ unit tests must still pass on each commit.
- The 8 CI jobs (Backend Tests, Frontend Build, Mypy Strict, Migrations Smoke, Lockfile Drift, Ruff Lint, Bandit SAST, Secret Scan) must all pass.
- Routes are NOT in mypy strict scope (Phase 5d only typed `backend/grading/*` + 5 small modules). The new route handler does not need annotations to satisfy CI.

---

## Self-Review

**1. Spec coverage:** Each spec section maps to a plan task.

| Spec section | Plan task |
|---|---|
| New endpoint definition + auth/authz | Task 3 |
| Bridge code (dict→array, contributing_submissions enrichment) | Task 1 |
| Trajectory build (chronological, null-to-end) | Task 2 |
| Happy path data fetch (content + submissions) | Task 4 |
| Attempt mode (latest/best/average) | Task 5 |
| Malformed standards_mastery handling (log + skip) | Task 5 |
| Null submitted_at sorted to end | Task 2 + Task 5 (test) |
| Orphan enrollment 404 | Task 3 |
| Empty state 200 + empty arrays | Task 4 |
| Frontend API client (URLSearchParams + encodeURIComponent) | Task 6 |
| Frontend component (drawer, z-index 9500, trajectory, breakdown) | Task 7 |
| Wire-up (openReportCard helper closes selectedCell) | Task 8 |
| Manual smoke test | Task 9 |
| 12 endpoint test cases from spec § Testing | Tasks 3-5 cover all 12 + 8 helper / extra-edge tests (added per Codex review: latest-malformed-no-fallback + individual-entry-malformed) |

**2. Placeholder scan:** No TBD/TODO/FIXME markers. Every code step has complete code.

**3. Type consistency:**
- `_build_standards_breakdown_for_student(mastery_by_code, submission_lookup)` — same signature in Task 1 + Task 4.
- `_build_trajectory_for_student(submissions, content_titles)` — same signature in Task 2 + Task 4.
- Endpoint URL `/api/teacher/class/<class_id>/student/<student_id>/report-card?attempt_mode=...` — same in Task 3 (handler), Task 4 (no change), Task 6 (client), Tasks 3-5 (tests).
- Response field names: `student_id`, `student_name`, `class_id`, `class_name`, `attempt_mode`, `trajectory`, `standards_breakdown` — consistent across spec, route handler, tests, and component reads.

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-25-phase2b-student-report-card.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks (spec compliance + code quality), Codex cross-check on the final code, fast iteration.

**2. Inline Execution** — Execute tasks in this session via executing-plans, batch with checkpoints.

**Which approach?**
