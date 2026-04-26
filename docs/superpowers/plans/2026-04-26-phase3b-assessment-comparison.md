# Phase 3b — Assessment Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a class-scoped Assessment Comparison sub-tab in Analytics. Teacher picks 2-6 assessments via clickable chips → backend returns per-assessment distribution stats + standards-coverage matrix → frontend renders side-by-side box plots + standards heatmap.

**Architecture:** One new GET endpoint in `backend/routes/student_portal_routes.py` reusing Phase 2's `_select_submissions_by_mode` (line 125), Phase 2's `_aggregate_mastery_for_student` (line 159), Phase 2b's `_sanitize_standards_mastery` (line 338), and Phase 3a's `_coalesce` (line 84). One local helper (`_safe_percentage`) for numeric coercion. Frontend adds one component (`AssessmentComparison.jsx`) and a third sub-tab in `AnalyticsTab.jsx`'s switcher.

**Tech Stack:** Flask + Supabase + plain React (no chart libraries — custom SVG box plot, since recharts has no native box-plot component).

**Spec:** `docs/superpowers/specs/2026-04-26-phase3b-assessment-comparison-design.md` at HEAD `045cac1` on branch `spec/phase3b-assessment-comparison`. APPROVED after Codex round 1 (3 MAJOR + 2 MINOR + 1 NIT all reconciled).

**Single-PR scope:** All work lands on `phase3b/assessment-comparison` branched off `main` after this docs PR merges.

---

## File Structure

**Files created:**
- `frontend/src/tabs/AssessmentComparison.jsx` — sub-tab component (~280 LOC).
- `tests/test_assessment_comparison.py` — 12 backend test cases.

**Files modified:**
- `backend/routes/student_portal_routes.py` — add `get_class_assessment_comparison` route handler with a local `_safe_percentage` closure. NO new module-level helpers.
- `frontend/src/tabs/AnalyticsTab.jsx` — add 3rd sub-tab button + 3-way conditional render.
- `frontend/src/services/api.js` — add `getClassAssessmentComparison` client.

**Files NOT touched:**
- Clever / ClassLink / OneRoster contracts (199 SIS tests protect).
- Existing helpers (`_select_submissions_by_mode`, `_aggregate_mastery_for_student`, `_sanitize_standards_mastery`, `_coalesce`, `_parse_ts`, `_build_*` from Phase 2b) — used as-is.
- `mypy.ini` / `.github/workflows/ci.yml` / `setup.cfg` / `requirements*.{in,txt}`.
- `frontend/src/components/InteractiveBoxPlot.jsx` — borrowable math reference but NOT modified or imported.

---

## Branching

After the docs PR (this spec + plan) merges, create the implementation branch:

```bash
git checkout main && git pull
git checkout -b phase3b/assessment-comparison
```

All implementation tasks below land on `phase3b/assessment-comparison`.

---

## Task 1: Route handler scaffold + validation (TDD)

Land the route skeleton with auth + class-ownership + content_ids validation. Returns empty arrays initially.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Create: `tests/test_assessment_comparison.py`

- [ ] **Step 1.1: Create the test file with fixtures + validation tests**

Create `tests/test_assessment_comparison.py`:

```python
"""Tests for the assessment comparison endpoint.

Spec: docs/superpowers/specs/2026-04-26-phase3b-assessment-comparison-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Test fixtures ============

@pytest.fixture
def app():
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


@pytest.fixture
def client_no_auth():
    """Minimal Flask app WITHOUT the dev-mode before_request hook so
    require_teacher can return 401."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    """Filter-aware Supabase mock — applies .eq() / .in_() / .neq() filters at .execute() time.

    Required: tests must observe `.in_()` (used for student_id/content_id IN ...) and
    `.neq()` (used for status != 'draft'). A no-op mock would mask draft-exclusion bugs.
    """
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.range.return_value = chain
    filters = []

    def _eq(field, value):
        filters.append(('eq', field, value))
        return chain
    chain.eq.side_effect = _eq

    def _in(field, values):
        filters.append(('in', field, list(values)))
        return chain
    chain.in_.side_effect = _in

    def _neq(field, value):
        filters.append(('neq', field, value))
        return chain
    chain.neq.side_effect = _neq

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
            elif op == 'in':
                result = [r for r in result if r.get(field) in value]
            elif op == 'neq':
                result = [r for r in result if r.get(field) != value]
        filters.clear()
        return MagicMock(data=result)
    chain.execute.side_effect = _execute
    return chain


def _multi_table_sb(table_map):
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


CLS_OWNED = [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}]


# ============ Validation tests ============

class TestAssessmentComparisonValidation:
    """Auth + content_ids validation."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/class/cls-1/compare?content_ids=a,b')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER'}],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_content_ids_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.get('/api/teacher/class/cls-1/compare', headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'content_ids is required' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_one_content_id_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111', headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'at least 2' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_seven_content_ids_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        seven = ','.join('1' * 8 + '-' + '1' * 4 + '-' + '1' * 4 + '-' + '1' * 4 + '-' + '1' * 12 for _ in range(7))
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=' + seven, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'at most 6' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_uuid_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=not-a-uuid,11111111-1111-1111-1111-111111111111', headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'Invalid content_id' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_content_id_outside_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        # Both ids are valid UUIDs, but only one is in this class.
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],
            'students': [],
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                # 22222222... is NOT in this class
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_content_id_is_assignment_not_assessment_returns_403(self, mock_sb_fn, client, teacher_headers):
        """Both ids exist in this class, but one has content_type='assignment'.
        Comparison is assessment-only — assignments must be rejected even if owned."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],
            'students': [],
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': '22222222-2222-2222-2222-222222222222', 'title': 'HW1',
                 'class_id': 'cls-1', 'content_type': 'assignment', 'max_points': 10},
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 403
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
source venv/bin/activate
pytest tests/test_assessment_comparison.py::TestAssessmentComparisonValidation -v
```
Expected: 8 FAIL — endpoint doesn't exist (404 from Flask routing).

- [ ] **Step 1.3: Add the route handler scaffold + validation**

Edit `backend/routes/student_portal_routes.py`. Find `get_student_submission_detail` (Phase 3a endpoint). AFTER its closing line, add:

```python
@student_portal_bp.route('/api/teacher/class/<class_id>/compare', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_assessment_comparison(class_id):
    """Compare 2-6 assessments side-by-side (class-scoped).

    Spec: docs/superpowers/specs/2026-04-26-phase3b-assessment-comparison-design.md
    """
    import uuid as _uuid

    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Parse content_ids CSV
    raw = request.args.get('content_ids', '').strip()
    if not raw:
        return error_response("content_ids is required", 400)
    content_ids = [cid.strip() for cid in raw.split(',') if cid.strip()]

    # 3) UUID validation — catch malformed before Postgres errors out as 500
    for cid in content_ids:
        try:
            _uuid.UUID(cid)
        except (ValueError, TypeError):
            return error_response("Invalid content_id", 400)

    # 4) Count bounds
    if len(content_ids) < 2:
        return error_response("Pick at least 2 assessments to compare", 400)
    if len(content_ids) > 6:
        return error_response("Compare at most 6 assessments at once", 400)

    # 5) Fetch published_content rows scoped to this class
    content_rows = db.table('published_content').select(
        'id, title, content_type, max_points'
    ).in_('id', content_ids).eq('class_id', class_id).execute()
    raw_found = content_rows.data or []
    # Reject anything that isn't an assessment — assignments must not be comparable here.
    found = [r for r in raw_found if r.get('content_type') == 'assessment']
    if len(found) < len(content_ids):
        # One or more content_ids isn't in this class OR isn't an assessment — cross-class/type injection guard.
        return error_response("Not authorized", 403)

    # Skeleton: empty data. Happy-path lands in Tasks 2-5.
    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "class_roster_size": 0,
        "assessments": [],
        "standards_matrix": {"standards": [], "cells": {}},
    })
```

- [ ] **Step 1.4: Run tests**

```bash
pytest tests/test_assessment_comparison.py::TestAssessmentComparisonValidation -v
```
Expected: 8 PASS.

- [ ] **Step 1.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_assessment_comparison.py
git commit -m "feat(compare): route handler scaffold + validation (auth, count, UUID, scope)"
```

---

## Task 2: Roster filtering + submission fetch (TDD)

Replace the skeleton's empty-arrays return with the valid-roster + submission fetch. Distribution + standards bridge land in Tasks 3-5.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_assessment_comparison.py`

- [ ] **Step 2.1: Append roster + happy-path skeleton tests**

Append to `tests/test_assessment_comparison.py`:

```python
class TestAssessmentComparisonRoster:
    """Valid-roster definition + orphan handling."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_class_roster_size_skips_orphan_enrollments(self, mock_sb_fn, client, teacher_headers):
        # class_students has 2 ids; students table has only 1 (orphan = stu-orphan).
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-orphan'}],
            'students': [{'id': 'stu-1'}],  # stu-orphan missing
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': '22222222-2222-2222-2222-222222222222', 'title': 'Q2',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Orphan dropped — roster size = 1
        assert body['class_roster_size'] == 1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_class_returns_zero_roster(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],
            'students': [],
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': '22222222-2222-2222-2222-222222222222', 'title': 'Q2',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['class_roster_size'] == 0
        # Both assessments should still appear with n=0
        assert len(body['assessments']) == 2
        assert all(a['n'] == 0 for a in body['assessments'])
        assert all(a['submission_rate'] == 0.0 for a in body['assessments'])

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_former_student_with_submission_excluded(self, mock_sb_fn, client, teacher_headers):
        """A submission from a student_id NOT in the current valid roster (former student
        whose enrollment was removed but whose submission row still exists) must not
        affect distribution stats — class roster scoping is the source of truth.
        Tests that the route's `for sid in valid_student_ids` iteration drops orphan submissions."""
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Roster: stu-1 only. ex-stu submitted Q1 but is no longer enrolled.
        subs = [
            {'id': 'sub-current', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 90,
             'results': {'standards_mastery': {}, 'score': 9, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-former', 'student_id': 'ex-stu', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 30,  # Would drag the mean down if included.
             'results': {'standards_mastery': {}, 'score': 3, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        # Only stu-1's 90 must count; ex-stu's 30 must NOT affect distribution.
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 90
        assert 30 not in a_q1['percentages']
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
pytest tests/test_assessment_comparison.py::TestAssessmentComparisonRoster -v
```
Expected: 3 FAIL — `class_roster_size` is 0 in the skeleton (matches one test by coincidence) but `assessments` array is empty (so the empty-class assertion `len(...) == 2` fails); former-student test fails because skeleton returns no distribution.

- [ ] **Step 2.3: Replace the skeleton's return with full data fetch**

In `backend/routes/student_portal_routes.py`, replace the `return jsonify({...empty...})` block at the end of `get_class_assessment_comparison` (added in Task 1.3) with:

```python
    # 6) Resolve valid roster (skip orphans matching Phase 3a pattern)
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    enrolled_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    valid_student_ids = []
    if enrolled_ids:
        students_rows = db.table('students').select('id').in_('id', enrolled_ids).execute()
        existing = {s['id'] for s in (students_rows.data or []) if s.get('id')}
        valid_student_ids = [sid for sid in enrolled_ids if sid in existing]
        if len(existing) < len(enrolled_ids):
            _logger.debug(
                "Orphan enrollments in class %s: %d students missing from students table",
                class_id, len(enrolled_ids) - len(existing),
            )

    class_roster_size = len(valid_student_ids)

    # 7) Fetch non-draft submissions for these students × these contents (paginated)
    submissions = []
    if valid_student_ids:
        page_size = 1000
        start = 0
        while True:
            page = db.table('student_submissions').select(
                'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
            ).in_('student_id', valid_student_ids).in_('content_id', content_ids).neq(
                'status', 'draft'
            ).range(start, start + page_size - 1).execute()
            rows = page.data or []
            submissions.extend(rows)
            if len(rows) < page_size:
                break
            start += page_size

    # 8) Sanitize-in-place
    for s in submissions:
        _sanitize_standards_mastery(s)

    # 9) Build per-(content) skeleton response. Distribution + standards-matrix come in Tasks 3-5.
    assessments_out = []
    for cid in content_ids:
        match = next((c for c in found if c.get('id') == cid), None)
        max_points = _coalesce(match.get('max_points') if match else None, default=0)
        assessments_out.append({
            "content_id": cid,
            "title": match.get('title', '') if match else '',
            "max_points": max_points,
            "n": 0,
            "submission_rate": 0.0,
            "mean": 0,
            "median": 0,
            "min": 0,
            "max": 0,
            "q1": 0,
            "q3": 0,
            "percentages": [],
        })

    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "class_roster_size": class_roster_size,
        "assessments": assessments_out,
        "standards_matrix": {"standards": [], "cells": {}},
    })
```

- [ ] **Step 2.4: Run tests**

```bash
pytest tests/test_assessment_comparison.py -v
```
Expected: 11 PASS (8 validation + 3 roster).

- [ ] **Step 2.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_assessment_comparison.py
git commit -m "feat(compare): roster filtering + submission fetch (skip orphans)"
```

---

## Task 3: `_safe_percentage` + distribution stats (TDD)

Define the local numeric sanitizer and replace the zero distribution stats with real per-content distributions.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_assessment_comparison.py`

- [ ] **Step 3.1: Append distribution tests**

Append to `tests/test_assessment_comparison.py`:

```python
class TestAssessmentComparisonDistribution:
    """Distribution stats: n, mean, median, quartiles, min, max."""

    def _make_subs(self, content_pcts):
        """Build student_submissions list. content_pcts: dict[content_id, list[(student_id, percentage)]]."""
        subs = []
        sub_id = 0
        for cid, entries in content_pcts.items():
            for student_id, pct in entries:
                sub_id += 1
                subs.append({
                    'id': f'sub-{sub_id}', 'student_id': student_id, 'content_id': cid,
                    'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
                    'percentage': pct,
                    'results': {'standards_mastery': {}, 'score': pct / 10, 'total_points': 10},
                    'status': 'graded',
                })
        return subs

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_happy_path_two_assessments_returns_full_response(self, mock_sb_fn, client, teacher_headers):
        # Class roster: 4 students. Q1 has 4 submissions; Q2 has 3 (one student absent).
        student_ids = [f'stu-{i}' for i in range(1, 5)]
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = self._make_subs({
            cid_q1: [(student_ids[0], 50), (student_ids[1], 70), (student_ids[2], 80), (student_ids[3], 90)],
            cid_q2: [(student_ids[0], 60), (student_ids[1], 75), (student_ids[2], 85)],
        })
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': sid} for sid in student_ids],
            'students': [{'id': sid} for sid in student_ids],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['class_roster_size'] == 4
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        a_q2 = next(a for a in body['assessments'] if a['content_id'] == cid_q2)
        # Q1: 4 submissions, mean 72.5, median 75, min 50, max 90
        assert a_q1['n'] == 4
        assert a_q1['submission_rate'] == 1.0
        assert a_q1['mean'] == 72.5
        assert a_q1['median'] == 75.0
        assert a_q1['min'] == 50
        assert a_q1['max'] == 90
        # Q2: 3 submissions, submission_rate = 0.75 (3/4)
        assert a_q2['n'] == 3
        assert a_q2['submission_rate'] == 0.75
        assert a_q2['mean'] == round((60 + 75 + 85) / 3, 2) or a_q2['mean'] == round((60 + 75 + 85) / 3, 1)

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_zero_submissions_assessment_returns_zero_stats(self, mock_sb_fn, client, teacher_headers):
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Only Q1 has submissions; Q2 has none.
        subs = self._make_subs({cid_q1: [('stu-1', 80)]})
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        body = resp.get_json()
        a_q2 = next(a for a in body['assessments'] if a['content_id'] == cid_q2)
        assert a_q2['n'] == 0
        assert a_q2['mean'] == 0
        assert a_q2['median'] == 0
        assert a_q2['q1'] == 0
        assert a_q2['q3'] == 0
        assert a_q2['percentages'] == []

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_average_uses_mean_per_student(self, mock_sb_fn, client, teacher_headers):
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Single student, 2 attempts at Q1: 50% and 90% → mean 70%
        subs = [
            {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 50,
             'results': {'standards_mastery': {}, 'score': 5, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-2', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 2, 'submitted_at': '2026-04-12T10:00:00Z',
             'percentage': 90,
             'results': {'standards_mastery': {}, 'score': 9, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-3', 'student_id': 'stu-1', 'content_id': cid_q2,
             'attempt_number': 1, 'submitted_at': '2026-04-15T10:00:00Z',
             'percentage': 80,
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}&attempt_mode=average', headers=teacher_headers)
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        # n=1 (one student); mean of [70.0] = 70.0
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 70.0
        # n==1 → q1==q3==70.0
        assert a_q1['q1'] == 70.0
        assert a_q1['q3'] == 70.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_non_numeric_percentage_skipped(self, mock_sb_fn, client, teacher_headers, caplog):
        """Submission with string percentage is skipped from distribution; warning logged."""
        import logging
        caplog.set_level(logging.WARNING, logger='backend.routes.student_portal_routes')
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = [
            {'id': 'sub-good', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 80,
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-bad', 'student_id': 'stu-2', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-11T10:00:00Z',
             'percentage': 'not-a-number',
             'results': {'standards_mastery': {}, 'score': 0, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-2'}],
            'students': [{'id': 'stu-1'}, {'id': 'stu-2'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        # Only the good submission counted; n=1 for Q1
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 80
        # Warning logged
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('non-numeric percentage' in r.getMessage() for r in warnings)

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_numeric_string_percentage_coerced(self, mock_sb_fn, client, teacher_headers):
        """percentage='80' (numeric string) must be coerced to 80.0, not skipped.
        Some grading paths historically wrote percentage as a string — _safe_percentage
        must treat numeric strings as valid input."""
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = [
            {'id': 'sub-string', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': '80',  # string, not int — must coerce, not skip.
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 80.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_draft_submissions_excluded_from_distribution(self, mock_sb_fn, client, teacher_headers):
        """Submissions with status='draft' must be filtered out by `.neq('status', 'draft')`
        on the SQL query — they must not affect n / mean / median / percentages.
        Without proper SQL exclusion, the filter-aware `_make_chain` would include them
        and this test would fail."""
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = [
            {'id': 'sub-graded', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 80,
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-draft', 'student_id': 'stu-2', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 0,  # Would drag the mean to 40 if included.
             'results': {'standards_mastery': {}, 'score': 0, 'total_points': 10},
             'status': 'draft'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-2'}],
            'students': [{'id': 'stu-1'}, {'id': 'stu-2'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        # Only the graded submission counts.
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 80
        assert 0 not in a_q1['percentages']
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest tests/test_assessment_comparison.py::TestAssessmentComparisonDistribution -v
```
Expected: 6 FAIL — distribution still hardcoded to zero.

- [ ] **Step 3.3: Implement `_safe_percentage` + distribution computation**

In `backend/routes/student_portal_routes.py`, find the `get_class_assessment_comparison` function. Inside it (after the `class_roster_size = len(valid_student_ids)` line, before the `submissions = []` block), define the local helper:

```python
    # Local numeric sanitizer — coerce percentage to float or None.
    # Use this instead of `or` because legitimate 0 must not fall through.
    def _safe_percentage(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            _logger.warning(
                "non-numeric percentage value (type=%s, value=%r) — skipping",
                type(val).__name__, val,
            )
            return None
```

Then replace the placeholder `assessments_out = []` block (Task 2.3's last addition) with the real distribution computation:

```python
    # 9) Group submissions by (student_id, content_id)
    from collections import defaultdict
    import statistics as _stats
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)

    assessments_out = []
    # Keep selected_per_content for the standards-matrix bridge in Task 4.
    selected_per_content_per_student = {}
    for cid in content_ids:
        match = next((c for c in found if c.get('id') == cid), None)
        max_points = _coalesce(match.get('max_points') if match else None, default=0)
        title = match.get('title', '') if match else ''

        percentages = []
        selected_for_this_content = {}
        for sid in valid_student_ids:
            student_subs = subs_by_student_content.get(sid, {}).get(cid, [])
            if not student_subs:
                continue
            selected = _select_submissions_by_mode({cid: student_subs}, attempt_mode).get(cid, [])
            if attempt_mode == 'average':
                # Mean across attempts for this student
                attempt_pcts = [_safe_percentage(s.get('percentage')) for s in student_subs]
                attempt_pcts = [p for p in attempt_pcts if p is not None]
                if not attempt_pcts:
                    continue
                student_pct = sum(attempt_pcts) / len(attempt_pcts)
            else:
                # latest/best modes — _select_submissions_by_mode picks one submission per
                # (student, content). NOTE: best mode ranks raw `percentage` values; if any
                # are non-numeric strings, _select_submissions_by_mode could TypeError before
                # _safe_percentage runs. Production data is always numeric (int/float per
                # grading_service.py), so this assumption is safe; if best-mode TypeErrors
                # are ever observed in logs, normalize percentages on `student_subs` before
                # calling _select_submissions_by_mode.
                if not selected:
                    continue
                student_pct = _safe_percentage(selected[0].get('percentage'))
                if student_pct is None:
                    continue
            percentages.append(student_pct)
            selected_for_this_content[sid] = selected

        selected_per_content_per_student[cid] = selected_for_this_content

        n = len(percentages)
        if n >= 2:
            sorted_pcts = sorted(percentages)
            mean_v = round(sum(sorted_pcts) / n, 2)
            median_v = _stats.median(sorted_pcts)
            quartiles = _stats.quantiles(sorted_pcts, n=4, method='inclusive')
            q1_v, q3_v = round(quartiles[0], 2), round(quartiles[2], 2)
            min_v, max_v = sorted_pcts[0], sorted_pcts[-1]
        elif n == 1:
            mean_v = median_v = q1_v = q3_v = min_v = max_v = round(percentages[0], 2)
        else:
            mean_v = median_v = q1_v = q3_v = min_v = max_v = 0

        submission_rate = round(n / class_roster_size, 2) if class_roster_size > 0 else 0.0

        assessments_out.append({
            "content_id": cid,
            "title": title,
            "max_points": max_points,
            "n": n,
            "submission_rate": submission_rate,
            "mean": mean_v,
            "median": median_v,
            "min": min_v,
            "max": max_v,
            "q1": q1_v,
            "q3": q3_v,
            "percentages": [round(p, 2) for p in percentages],
        })

    # Standards matrix bridge — Task 4 fills this in.
    standards_matrix = {"standards": [], "cells": {}}

    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "class_roster_size": class_roster_size,
        "assessments": assessments_out,
        "standards_matrix": standards_matrix,
    })
```

(Remove the placeholder `assessments_out` loop from Task 2.3 — it's replaced by the loop above.)

- [ ] **Step 3.4: Run tests**

```bash
pytest tests/test_assessment_comparison.py -v
```
Expected: 17 PASS (8 validation + 3 roster + 6 distribution).

- [ ] **Step 3.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_assessment_comparison.py
git commit -m "feat(compare): _safe_percentage + distribution stats (n, mean, median, quartiles)"
```

---

## Task 4: Standards-matrix bridge (TDD)

The endpoint's last data piece: per-(content, standard) class-mean cells. Local bridge code that inverts `_aggregate_mastery_for_student`'s per-student rollup into per-(content, standard) cells.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_assessment_comparison.py`

- [ ] **Step 4.1: Append standards-matrix tests**

Append to `tests/test_assessment_comparison.py`:

```python
class TestAssessmentComparisonStandardsMatrix:
    """standards_matrix.standards (sorted union) + cells (class-mean per standard)."""

    def _subs_with_mastery(self, entries):
        """entries: list of (sub_id, student_id, content_id, percentage, mastery_dict)."""
        out = []
        for sub_id, sid, cid, pct, mastery in entries:
            out.append({
                'id': sub_id, 'student_id': sid, 'content_id': cid,
                'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
                'percentage': pct,
                'results': {
                    'standards_mastery': mastery,
                    'score': pct / 10, 'total_points': 10,
                },
                'status': 'graded',
            })
        return out

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_standards_matrix_union_and_cells_correct(self, mock_sb_fn, client, teacher_headers):
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Q1 covers MA.6.AR.1.1, MA.6.AR.1.2; Q2 covers MA.6.AR.1.2, MA.6.AR.1.3.
        # Union: [1.1, 1.2, 1.3] sorted alphabetically.
        m_q1 = {
            'MA.6.AR.1.1': {'points_earned': 8, 'points_possible': 10, 'question_count': 2},
            'MA.6.AR.1.2': {'points_earned': 6, 'points_possible': 10, 'question_count': 2},
        }
        m_q2 = {
            'MA.6.AR.1.2': {'points_earned': 9, 'points_possible': 10, 'question_count': 2},
            'MA.6.AR.1.3': {'points_earned': 5, 'points_possible': 10, 'question_count': 2},
        }
        # 2 students, both submit both
        subs = self._subs_with_mastery([
            ('s-1a', 'stu-1', cid_q1, 70, m_q1),
            ('s-1b', 'stu-1', cid_q2, 70, m_q2),
            ('s-2a', 'stu-2', cid_q1, 70, m_q1),
            ('s-2b', 'stu-2', cid_q2, 70, m_q2),
        ])
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-2'}],
            'students': [{'id': 'stu-1'}, {'id': 'stu-2'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        body = resp.get_json()
        sm = body['standards_matrix']
        # Sorted union
        assert sm['standards'] == ['MA.6.AR.1.1', 'MA.6.AR.1.2', 'MA.6.AR.1.3']
        # Q1 covers 1.1, 1.2 — both at 80 / 60 mastery (same for both students)
        assert sm['cells'][cid_q1]['MA.6.AR.1.1']['percentage'] == 80
        assert sm['cells'][cid_q1]['MA.6.AR.1.2']['percentage'] == 60
        assert 'MA.6.AR.1.3' not in sm['cells'][cid_q1]
        # Q2 covers 1.2, 1.3
        assert sm['cells'][cid_q2]['MA.6.AR.1.2']['percentage'] == 90
        assert sm['cells'][cid_q2]['MA.6.AR.1.3']['percentage'] == 50
        assert 'MA.6.AR.1.1' not in sm['cells'][cid_q2]
        # students_assessed = 2 for every cell (both students completed both)
        for cid in [cid_q1, cid_q2]:
            for code in sm['cells'][cid]:
                assert sm['cells'][cid][code]['students_assessed'] == 2

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_standards_mastery_does_not_500(self, mock_sb_fn, client, teacher_headers):
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # One submission has list-shape mastery — would 500 without _sanitize_standards_mastery.
        good = {'MA.6.AR.1.1': {'points_earned': 8, 'points_possible': 10, 'question_count': 2}}
        subs = [
            {'id': 's-good', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z', 'percentage': 80,
             'results': {'standards_mastery': good, 'score': 8, 'total_points': 10},
             'status': 'graded'},
            {'id': 's-bad', 'student_id': 'stu-2', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-11T10:00:00Z', 'percentage': 60,
             'results': {'standards_mastery': ['malformed'], 'score': 6, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-2'}],
            'students': [{'id': 'stu-1'}, {'id': 'stu-2'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        # Endpoint 200s — sanitize replaced the list with {} so the rest of the pipeline works.
        assert resp.status_code == 200
        body = resp.get_json()
        # Distribution for Q1 still includes both students (sanitize doesn't drop submissions)
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        assert a_q1['n'] == 2
        # standards_matrix only has the standard from sub-good
        assert body['standards_matrix']['standards'] == ['MA.6.AR.1.1']
        # The malformed submission contributed nothing to mastery, so students_assessed = 1
        assert body['standards_matrix']['cells'][cid_q1]['MA.6.AR.1.1']['students_assessed'] == 1
```

- [ ] **Step 4.2: Run tests**

```bash
pytest tests/test_assessment_comparison.py::TestAssessmentComparisonStandardsMatrix -v
```
Expected: 2 FAIL (`standards_matrix` is still empty).

- [ ] **Step 4.3: Implement the standards-matrix bridge**

In `backend/routes/student_portal_routes.py`, replace this line (added in Task 3.3):

```python
    # Standards matrix bridge — Task 4 fills this in.
    standards_matrix = {"standards": [], "cells": {}}
```

With:

```python
    # 10) Standards-matrix bridge: invert per-student mastery rollups into
    # per-(content_id, standard_code) class-mean cells.
    cells_accumulator: dict = {}  # cid -> standard_code -> list[float]
    content_titles = {c['id']: c.get('title', '') for c in found}
    for cid in content_ids:
        cells_accumulator[cid] = {}
        for sid, selected in selected_per_content_per_student.get(cid, {}).items():
            if not selected:
                continue
            mastery_by_code = _aggregate_mastery_for_student(
                {cid: selected}, content_titles, attempt_mode,
            )
            for code, m in mastery_by_code.items():
                pct = _safe_percentage(m.get('percentage'))
                if pct is None:
                    continue
                cells_accumulator[cid].setdefault(code, []).append(pct)

    cells_out: dict = {}
    all_standards: set = set()
    for cid, by_code in cells_accumulator.items():
        cells_out[cid] = {}
        for code, pct_list in by_code.items():
            students_assessed = len(pct_list)
            cells_out[cid][code] = {
                "percentage": round(sum(pct_list) / students_assessed, 1) if students_assessed > 0 else 0,
                "students_assessed": students_assessed,
            }
            all_standards.add(code)

    standards_matrix = {
        "standards": sorted(all_standards),
        "cells": cells_out,
    }
```

- [ ] **Step 4.4: Run tests**

```bash
pytest tests/test_assessment_comparison.py -v
```
Expected: 19 PASS (8 validation + 3 roster + 6 distribution + 2 standards).

- [ ] **Step 4.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_assessment_comparison.py
git commit -m "feat(compare): standards-matrix bridge (per-content, per-standard class-means)"
```

---

## Task 5: Frontend API client

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 5.1: Add the client function**

Edit `frontend/src/services/api.js`. Find `getClassGradebook` (added in Phase 3a). After it, add:

```javascript
export async function getClassAssessmentComparison(classId, contentIds, attemptMode) {
  var mode = attemptMode || 'latest';
  var params = new URLSearchParams({
    content_ids: contentIds.join(','),
    attempt_mode: mode,
  });
  return fetchApi(
    '/api/teacher/class/' + encodeURIComponent(classId) +
    '/compare?' + params.toString()
  );
}
```

- [ ] **Step 5.2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 5.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/services/api.js
git commit -m "feat(compare): frontend API client getClassAssessmentComparison"
```

---

## Task 6: AssessmentComparison component (~280 LOC)

**Files:**
- Create: `frontend/src/tabs/AssessmentComparison.jsx`

- [ ] **Step 6.1: Create the component**

Create `frontend/src/tabs/AssessmentComparison.jsx`:

```javascript
import React, { useState, useEffect } from "react";
import * as api from "../services/api";

function gradeColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

// Custom SVG box plot — recharts has no native box plot.
// This is a FIVE-NUMBER-SUMMARY plot (min/Q1/median/Q3/max). No outlier treatment;
// whiskers extend to absolute min/max (NOT 1.5×IQR fences). If outlier display is
// ever requested by teachers, port the IQR-fence math from
// frontend/src/components/InteractiveBoxPlot.jsx (which is the input widget — never
// modify or import it from here; this read-only component owns its own math).
function BoxPlotRow({ assessments }) {
  var width = Math.max(600, assessments.length * 110);
  var height = 200;
  var pad = { top: 16, right: 24, bottom: 40, left: 48 };
  var plotH = height - pad.top - pad.bottom;
  var boxW = 60;
  var slotW = (width - pad.left - pad.right) / Math.max(assessments.length, 1);

  function yFor(pct) {
    return pad.top + plotH - (pct / 100) * plotH;
  }

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {/* Y axis ticks at 0, 25, 50, 70, 85, 100 */}
      {[0, 25, 50, 70, 85, 100].map(function(t) {
        var y = yFor(t);
        var stroke = (t === 70 || t === 85) ? (t === 85 ? "var(--success)" : "var(--warning)") : "var(--glass-border)";
        var dash = (t === 70 || t === 85) ? "3 3" : undefined;
        return (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke={stroke} strokeDasharray={dash} />
            <text x={pad.left - 8} y={y + 4} fontSize="10" textAnchor="end" fill="var(--text-secondary)">{t}</text>
          </g>
        );
      })}
      {/* Box per assessment */}
      {assessments.map(function(a, i) {
        if (a.n === 0) {
          return (
            <g key={a.content_id}>
              <text x={pad.left + slotW * i + slotW / 2} y={yFor(50)} fontSize="11" textAnchor="middle" fill="var(--text-muted)">no data</text>
              <text x={pad.left + slotW * i + slotW / 2} y={height - pad.bottom + 16} fontSize="10" textAnchor="middle" fill="var(--text-secondary)">{a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}</text>
            </g>
          );
        }
        var color = gradeColor(a.mean);
        var cx = pad.left + slotW * i + slotW / 2;
        var x0 = cx - boxW / 2;
        var yMin = yFor(a.min);
        var yMax = yFor(a.max);
        var yQ1 = yFor(a.q1);
        var yQ3 = yFor(a.q3);
        var yMed = yFor(a.median);
        return (
          <g key={a.content_id}>
            {/* Whiskers */}
            <line x1={cx} x2={cx} y1={yMin} y2={yQ1} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx} x2={cx} y1={yQ3} y2={yMax} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx - 12} x2={cx + 12} y1={yMin} y2={yMin} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx - 12} x2={cx + 12} y1={yMax} y2={yMax} stroke={color.text} strokeWidth="1.5" />
            {/* Box */}
            <rect x={x0} y={yQ3} width={boxW} height={Math.max(yQ1 - yQ3, 1)} fill={color.bg} stroke={color.text} strokeWidth="1.5" />
            {/* Median line */}
            <line x1={x0} x2={x0 + boxW} y1={yMed} y2={yMed} stroke={color.text} strokeWidth="2" />
            {/* X-axis label */}
            <text x={cx} y={height - pad.bottom + 16} fontSize="10" textAnchor="middle" fill="var(--text-secondary)">
              {a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}
            </text>
            <title>{a.title + ": median " + a.median + "%, IQR " + a.q1 + "-" + a.q3 + ", n=" + a.n}</title>
          </g>
        );
      })}
    </svg>
  );
}

export default function AssessmentComparison({ classId }) {
  var [available, setAvailable] = useState([]);
  var [bootstrapLoading, setBootstrapLoading] = useState(true);
  var [bootstrapError, setBootstrapError] = useState(null);
  var [selectedContentIds, setSelectedContentIds] = useState([]);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(false);
  var [error, setError] = useState(null);
  var [searchQuery, setSearchQuery] = useState('');

  // Bootstrap: fetch the list of class assessments via the gradebook endpoint.
  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setBootstrapLoading(true);
    setBootstrapError(null);
    setSelectedContentIds([]);
    setData(null);
    api.getClassGradebook(classId, 'latest')
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setBootstrapError((res && res.error) || 'Failed to load assessments');
          setAvailable([]);
        } else {
          // Gradebook returns both assessments and assignments. The compare endpoint
          // also enforces content_type='assessment' as a 403 guard, but we filter
          // client-side so non-assessments never appear in the picker.
          // (If the gradebook response omits content_type on a row, fall through —
          // the backend guard will catch it.)
          var assessmentsOnly = (res.assessments || []).filter(function(a) {
            return !a.content_type || a.content_type === 'assessment';
          });
          setAvailable(assessmentsOnly);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setBootstrapError((e && e.message) || 'Failed to load assessments');
      })
      .finally(function() { if (!cancelled) setBootstrapLoading(false); });
    return function() { cancelled = true; };
  }, [classId]);

  // Comparison fetch when selection is valid.
  useEffect(function() {
    if (selectedContentIds.length < 2 || selectedContentIds.length > 6) {
      setData(null);
      return;
    }
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassAssessmentComparison(classId, selectedContentIds, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load comparison');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load comparison');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [classId, selectedContentIds, attemptMode]);

  function toggleSelection(contentId) {
    if (selectedContentIds.indexOf(contentId) >= 0) {
      setSelectedContentIds(selectedContentIds.filter(function(id) { return id !== contentId; }));
    } else if (selectedContentIds.length < 6) {
      setSelectedContentIds(selectedContentIds.concat([contentId]));
    }
  }

  var btnStyle = function(active) {
    return {
      padding: "6px 14px", borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
    };
  };

  if (bootstrapLoading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <p style={{ color: "var(--text-secondary)" }}>Loading assessments...</p>
      </div>
    );
  }
  if (bootstrapError) {
    return <div className="glass-card" style={{ padding: "40px", color: "var(--danger)", textAlign: "center" }}>{bootstrapError}</div>;
  }

  var filteredAvailable = available.filter(function(a) {
    return !searchQuery || a.title.toLowerCase().indexOf(searchQuery.toLowerCase()) >= 0;
  });

  var orderedSelected = selectedContentIds.map(function(cid) {
    return available.find(function(a) { return a.content_id === cid; });
  }).filter(Boolean);

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Compare Assessments
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {selectedContentIds.length} of 6 selected {String.fromCharCode(8226)} pick 2-6 assessments
      </p>

      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
      </div>

      {/* Picker */}
      {available.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>
          No assessments published to this class yet.
        </p>
      ) : (
        <div style={{ marginBottom: "20px" }}>
          <input
            type="text"
            value={searchQuery}
            onChange={function(e) { setSearchQuery(e.target.value); }}
            placeholder="Search assessments..."
            className="input"
            style={{ width: "100%", maxWidth: "400px", marginBottom: "10px" }}
          />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {filteredAvailable.map(function(a) {
              var isSelected = selectedContentIds.indexOf(a.content_id) >= 0;
              var atCap = !isSelected && selectedContentIds.length >= 6;
              return (
                <button
                  key={a.content_id}
                  onClick={function() { toggleSelection(a.content_id); }}
                  disabled={atCap}
                  style={{
                    padding: "6px 12px", borderRadius: "16px",
                    border: "1px solid " + (isSelected ? "var(--accent-primary)" : "var(--glass-border)"),
                    background: isSelected ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
                    color: isSelected ? "var(--accent-primary)" : (atCap ? "var(--text-muted)" : "var(--text-primary)"),
                    fontSize: "0.8rem", fontWeight: 500,
                    cursor: atCap ? "not-allowed" : "pointer",
                    opacity: atCap ? 0.5 : 1,
                  }}
                  title={atCap ? "Maximum 6 assessments" : a.title}
                >
                  {a.title}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Comparison output */}
      {selectedContentIds.length < 2 ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>
          Pick at least 2 assessments to compare.
        </p>
      ) : loading ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>Loading comparison...</p>
      ) : error ? (
        <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>{error}</div>
      ) : data ? (
        <div>
          {/* Stat cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px", marginBottom: "20px" }}>
            {data.assessments.map(function(a) {
              var color = gradeColor(a.n > 0 ? a.mean : null);
              var ratePct = Math.round((a.submission_rate || 0) * 100);
              return (
                <div key={a.content_id} style={{ padding: "12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: color.bg }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 700, color: color.text, marginBottom: "4px" }}>{a.title}</div>
                  {a.n > 0 ? (
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: color.text }}>
                      {a.mean}%
                    </div>
                  ) : (
                    <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-muted)" }}>
                      No submissions yet
                    </div>
                  )}
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    {a.n} of {data.class_roster_size} {String.fromCharCode(8226)} {ratePct}% submitted
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    Max points: {a.max_points}
                    {a.n > 0 ? " " + String.fromCharCode(8226) + " median " + a.median + "%" : ""}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Box plot row */}
          <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Score distribution</h4>
          <div style={{ overflowX: "auto", marginBottom: "20px", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "8px" }}>
            <BoxPlotRow assessments={orderedSelected.map(function(o) {
              return data.assessments.find(function(a) { return a.content_id === o.content_id; }) || o;
            })} />
          </div>

          {/* Standards heatmap */}
          <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Standards coverage</h4>
          {data.standards_matrix.standards.length === 0 ? (
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              No standards-tagged questions on these assessments.
            </p>
          ) : (
            <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <thead>
                  <tr>
                    <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", padding: "10px 14px", textAlign: "left", fontSize: "0.75rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)" }}>Standard</th>
                    {orderedSelected.map(function(a) {
                      return (
                        <th key={a.content_id} style={{ padding: "10px 8px", fontSize: "0.7rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", minWidth: "100px", textAlign: "center" }}>
                          {a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {data.standards_matrix.standards.map(function(code) {
                    return (
                      <tr key={code}>
                        <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", padding: "8px 14px", fontFamily: "monospace", fontSize: "0.75rem", borderBottom: "1px solid var(--glass-border)" }}>{code}</td>
                        {orderedSelected.map(function(a) {
                          var cell = (data.standards_matrix.cells[a.content_id] || {})[code];
                          var color = gradeColor(cell ? cell.percentage : null);
                          return (
                            <td key={a.content_id} title={cell ? code + " on " + a.title + ": " + cell.percentage + "% (" + cell.students_assessed + " students)" : "Not covered"}
                                style={{ padding: "8px", textAlign: "center", borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", background: color.bg, color: color.text, fontSize: "0.75rem", fontWeight: 600 }}>
                              {color.label}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 6.2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 6.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/AssessmentComparison.jsx
git commit -m "feat(compare): AssessmentComparison component with picker + box plot + heatmap"
```

---

## Task 7: AnalyticsTab wire-up — 3rd sub-tab button + 3-way render

**Files:**
- Modify: `frontend/src/tabs/AnalyticsTab.jsx`

- [ ] **Step 7.1: Add the import**

Edit `frontend/src/tabs/AnalyticsTab.jsx`. After the existing `import Gradebook from "./Gradebook";` at line 28, add:

```javascript
import AssessmentComparison from "./AssessmentComparison";
```

- [ ] **Step 7.2: Update the classView state comment**

Find the state declaration at line ~2388:

```javascript
  var [classView, setClassView] = useState('progressRank'); // 'progressRank' | 'gradebook'
```

Change the comment:

```javascript
  var [classView, setClassView] = useState('progressRank'); // 'progressRank' | 'gradebook' | 'compare'
```

- [ ] **Step 7.3: Add the third sub-tab button**

Find the second sub-tab button (the Gradebook button, around lines 2576-2589). AFTER its closing `</button>`, add a third button with the same style pattern:

```javascript
                      <button
                        onClick={function() { setClassView('compare'); }}
                        style={{
                          padding: "8px 16px",
                          borderRadius: "8px",
                          border: "1px solid " + (classView === 'compare' ? "var(--accent-primary)" : "var(--glass-border)"),
                          background: classView === 'compare' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
                          color: classView === 'compare' ? "var(--accent-primary)" : "var(--text-secondary)",
                          fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
                        }}>
                        Compare
                      </button>
```

- [ ] **Step 7.4: Update the conditional render to 3-way**

Find the existing `{classView === 'progressRank' ? ... : <Gradebook ... />}` ternary (around lines 2590-2594). Replace with a nested ternary:

```javascript
                    {classView === 'progressRank' ? (
                      <ProgressRankGrid classId={selectedClassForGrid} />
                    ) : classView === 'gradebook' ? (
                      <Gradebook classId={selectedClassForGrid} />
                    ) : (
                      <AssessmentComparison classId={selectedClassForGrid} />
                    )}
```

- [ ] **Step 7.5: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 7.6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/AnalyticsTab.jsx
git commit -m "feat(analytics): 3rd sub-tab (Compare) with conditional unmount"
```

---

## Task 8: Manual smoke test

**Files:** none modified.

- [ ] **Step 8.1: Start backend**

```bash
source venv/bin/activate
python -m backend.app
```
Backend serves at `http://localhost:3000`. Leave running.

- [ ] **Step 8.2: Build frontend**

In another terminal:
```bash
cd frontend && npm run build
```

- [ ] **Step 8.3: Open dashboard**

Visit `http://localhost:3000`. Sign in as a teacher with at least one class containing 3+ assessments and submissions.

- [ ] **Step 8.4: Verify the Compare sub-tab**

1. Navigate to Analytics → pick a class → see the 3-way sub-tab switcher.
2. Click "Compare" — picker renders with all class assessments as chips.
3. Type in the search field — chips filter.
4. Click 2 chips → comparison renders (stat cards + box plot + heatmap).
5. Click a 3rd chip → comparison re-fetches and re-renders.
6. Try to click a 7th chip → button is disabled / muted (max 6).
7. Click an already-selected chip → deselect; comparison re-fetches.
8. Drop below 2 → "Pick at least 2 assessments" message returns.
9. Toggle attempt mode (Latest / Best / Average) — distributions update.
10. Hover a heatmap cell → tooltip with % + students_assessed.
11. Hover a box → tooltip with median + IQR + n.
12. Switch to "Progress Rank" sub-tab → AssessmentComparison unmounts.
13. Switch back to "Compare" → state resets (selection empty); re-pick.
14. Switch class via the class selector → classView resets to "Progress Rank" (Phase 3a behavior preserved).

- [ ] **Step 8.5: If any failure, fix + commit**

Each fix gets its own commit (`fix(compare): <what>`).

---

## Task 9: Push branch

**Files:** none modified.

- [ ] **Step 9.1: Push**

```bash
git push -u origin phase3b/assessment-comparison
```

The controller (subagent-driven-development controller) opens the PR after Codex full-PR cross-check.

---

## Sequencing + dependencies

**Single PR, sequential tasks:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.

Tasks 1-4 are pure backend (TDD). Task 5 is frontend API client. Task 6 is the heavy frontend component. Task 7 is AnalyticsTab wire-up. Task 8 is manual smoke. Task 9 ships.

---

## Testing strategy

- 19 backend tests covering validation (8), roster (3), distribution (6), standards matrix (2). All pass on each commit.
- Frontend: build verification only (consistent with Phase 2 / 2b / 3a).
- All 8 CI jobs must pass.
- Routes are NOT in mypy strict scope — no annotations required.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| Validation order (auth → parse → UUID → ≥2 → ≤6 → in-class assessment) | Task 1 |
| Class-ownership 403 + cross-class injection guard | Task 1 |
| Assignment-vs-assessment guard (`content_type='assessment'`) | Task 1 (impl + test) |
| Roster filtering (class_students JOIN students; skip orphans) | Task 2 |
| Pagination via `.range()` | Task 2 |
| Status filter (`status != 'draft'`) on submission fetch | Task 2 (impl) + Task 3 (test) |
| Former-student-with-submission exclusion (`student_id IN valid_student_ids` semantics) | Task 2 (impl) + Task 2 (test) |
| `_safe_percentage` local helper (None / non-numeric → skip + warn) | Task 3 |
| Numeric string percentage coercion (`'80'` → 80.0) | Task 3 (impl + test) |
| Distribution stats (n, mean, median, q1, q3, min, max) + quartile semantics for n<2 | Task 3 |
| Submission rate denominator = valid roster size | Task 3 |
| Attempt mode latest/best/average + invalid fallback | Tasks 1 (parse) + 3 (avg path) |
| Standards-matrix bridge (per-student rollup → per-(content, std) class-mean) | Task 4 |
| Sanitize-in-place for malformed mastery | Task 2 (sanitize call) + Task 4 (test) |
| Frontend API client (URLSearchParams + encodeURIComponent + comma-join) | Task 5 |
| AssessmentComparison.jsx (chip picker + 3-tier color + box plot + heatmap) | Task 6 |
| Bootstrap-fetch reuse of getClassGradebook + client-side assessment filter | Task 6 |
| Stat cards: title, mean (or "No submissions yet"), submission rate, max points, median | Task 6 |
| Custom SVG box plot — declared as five-number-summary, no outlier treatment | Task 6 |
| AnalyticsTab 3-way switcher with conditional unmount | Task 7 |
| Manual smoke checklist | Task 8 |

**2. Placeholder scan:** No TBD/TODO/FIXME markers. Every code step has complete code blocks.

**3. Type consistency:**
- `get_class_assessment_comparison(class_id)` — same name in handler + tests + spec.
- Endpoint URL `/api/teacher/class/<class_id>/compare?content_ids=<csv>&attempt_mode=...` — same in spec, handler, client, tests.
- Response top-level fields: `class_id, class_name, attempt_mode, class_roster_size, assessments[], standards_matrix{standards[], cells{}}` — consistent.
- Per-assessment: `content_id, title, max_points, n, submission_rate, mean, median, min, max, q1, q3, percentages` — consistent.
- `_safe_percentage(val)` — same signature throughout the route (None pass-through, str-numeric coerce, non-numeric → None + warn).

**4. Test mock fidelity:**
- `_make_chain` records `.eq()`, `.in_()`, `.neq()` filters and applies them at `.execute()` time. Required because:
  - `.in_('student_id', valid_student_ids)` is the SQL filter that excludes former-student submissions.
  - `.in_('content_id', content_ids)` is the SQL filter that scopes submissions to picked assessments.
  - `.neq('status', 'draft')` is the ONLY exclusion for draft submissions (no Python-side fallback).
- A no-op mock for `.neq()` would silently mask draft-inclusion bugs in the test suite.

**5. Edge cases tested:**
- Auth: 401 unauth, 403 wrong teacher, 403 cross-class injection, 403 assignment-not-assessment.
- Validation: missing content_ids (400), 1 (400), 7 (400), malformed UUID (400).
- Roster: empty class (n=0), orphan enrollments dropped, former student with submission dropped.
- Distribution: n=1 quartile (q1=q3=val), n=0 stats (all 0), draft submissions excluded, non-numeric percentage logged + skipped, numeric string percentage coerced.
- Standards matrix: union sorting, per-cell mean across students, malformed mastery sanitized.

**6. Known limitations (deferred / not blockers):**
- Box plot has no outlier treatment (whiskers = absolute min/max, not 1.5×IQR fences). If teachers ask for outlier display, port the IQR-fence math from `InteractiveBoxPlot.jsx`.
- `max_points` is read only from the row column. If a future migration moves it into a JSON field on `published_content`, swap to `_coalesce(row.max_points, row.json_col.max_points, default=0)` — `_coalesce` already wraps the read site.
- Best-mode ranking still compares raw `percentage` values via `_select_submissions_by_mode`; non-numeric values would TypeError before `_safe_percentage` runs. Production data is always numeric (per `grading_service.py`), so this assumption is safe.

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-26-phase3b-assessment-comparison.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task bundle, two-stage review between bundles, Codex full-PR cross-check before merge. Same workflow as Phase 2b / 3a.

**2. Inline Execution** — execute tasks here in this session via executing-plans, batched with checkpoints.

**Which approach?**
