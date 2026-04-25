# Phase 3a — Gradebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a class-scoped Gradebook sub-tab in Analytics + a SubmissionDetail drawer that opens when a teacher clicks any cell.

**Architecture:** Two new GET endpoints in `backend/routes/student_portal_routes.py` (class gradebook + per-submission detail) reusing Phase 2's `_select_submissions_by_mode` and Phase 2b's `_sanitize_standards_mastery` helpers without modification. Frontend adds two components (`Gradebook.jsx`, `SubmissionDetail.jsx`) and a sub-tab switcher inside `AnalyticsTab.jsx` that conditionally unmounts the inactive sub-tab so drawers can't collide.

**Tech Stack:** Flask + Supabase + recharts. Reuses Phase 1's `student_submissions.results` shape, Phase 2's helpers, Phase 5d's `error_response` + `@handle_route_errors`.

**Spec:** `docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md` at HEAD `329c4d5` on branch `spec/phase3a-gradebook`. APPROVED after 2 rounds of Codex review.

**Single-PR scope:** All work lands on one branch `phase3a/gradebook` opened off `main` (after this docs PR merges).

---

## File Structure

**Files created:**
- `frontend/src/tabs/Gradebook.jsx` — gradebook table component (~220 LOC)
- `frontend/src/tabs/SubmissionDetail.jsx` — submission-detail side drawer (~250 LOC)
- `tests/test_gradebook.py` — 13 backend test cases
- `tests/test_submission_detail.py` — 7 backend test cases

**Files modified:**
- `backend/routes/student_portal_routes.py` — add `_coalesce` module-level helper + 2 new route handlers (`get_class_gradebook`, `get_student_submission_detail`)
- `frontend/src/tabs/AnalyticsTab.jsx` — add sub-tab switcher inside the class-scoped section
- `frontend/src/services/api.js` — add `getClassGradebook` + `getSubmissionDetail` clients

**Files NOT touched:**
- Clever / ClassLink / OneRoster contracts (199 SIS tests protect)
- Existing helpers (`_select_submissions_by_mode`, `_aggregate_mastery_for_student`, `_sanitize_standards_mastery`, `_build_*` from Phase 2b) — used as-is
- `mypy.ini` / `.github/workflows/ci.yml` / `setup.cfg` / `requirements*.{in,txt}`
- `backend/services/grading_service.py` — read-only research only

---

## Branching

After this docs PR merges, create the implementation branch:

```bash
git checkout main && git pull
git checkout -b phase3a/gradebook
```

All implementation tasks below land on `phase3a/gradebook`.

---

## Task 1: `_coalesce` helper (TDD, 4 unit tests)

A first-non-None coalescing helper. Used everywhere the route handlers need to pick a value with fallback chains, because Python's `or` short-circuits on falsy (0, "", False) — corrupting grades when the legitimate value is 0.

**Files:**
- Modify: `backend/routes/student_portal_routes.py` (add helper near `_parse_ts` at the top)
- Create: `tests/test_gradebook.py` (first test goes here)

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_gradebook.py`:

```python
"""Tests for the gradebook endpoint and the _coalesce helper.

Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ _coalesce helper unit tests ============

class TestCoalesce:
    """_coalesce: first-non-None semantics (NOT `or`-truthiness)."""

    def test_returns_first_non_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, "fallback", "later") == "fallback"

    def test_returns_default_when_all_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, None, default=42) == 42

    def test_zero_is_kept_not_treated_as_falsy(self):
        """The whole reason this helper exists: legitimate 0 must not fall through."""
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(0, 999, default=-1) == 0

    def test_empty_string_is_kept_not_treated_as_falsy(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce("", "fallback", default="default") == ""
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
source venv/bin/activate
pytest tests/test_gradebook.py::TestCoalesce -v
```
Expected: 4 FAIL — `_coalesce` doesn't exist yet.

- [ ] **Step 1.3: Implement `_coalesce`**

Edit `backend/routes/student_portal_routes.py`. Find `_parse_ts` near line 72 (it's a small helper near the top of the module). After `_parse_ts`'s closing line, add:

```python
def _coalesce(*vals, default=None):
    """Return the first non-None value among `vals`, or `default` if all are None.

    Use this instead of Python's `or` for fallback chains where 0 / "" / False
    are legitimate values. `or` short-circuits on falsy, corrupting numeric/text
    fallbacks (e.g., a legitimate `points_earned = 0` would silently become the
    fallback's value).
    """
    for v in vals:
        if v is not None:
            return v
    return default
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
pytest tests/test_gradebook.py::TestCoalesce -v
```
Expected: 4 PASS.

- [ ] **Step 1.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_gradebook.py
git commit -m "feat(routes): _coalesce first-non-None helper"
```

---

## Task 2: Gradebook endpoint scaffold + authz (TDD)

Lands the route skeleton with auth + class-ownership check. Returns empty arrays.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_gradebook.py`

- [ ] **Step 2.1: Append the test fixtures + authz tests**

Append to `tests/test_gradebook.py`:

```python
# ============ Test fixtures ============

@pytest.fixture
def app():
    """Flask app in test mode."""
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
    require_teacher can return 401. Mirrors tests/test_sso_contracts.py."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


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


# ============ Authz tests ============

class TestGradebookAuthz:
    """Auth + class-ownership checks."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/class/cls-1/gradebook')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/forbidden'
        assert body.get('status') == 403
        assert 'error' in body
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
pytest tests/test_gradebook.py::TestGradebookAuthz -v
```
Expected: 2 FAIL — endpoint doesn't exist (404 from Flask routing).

- [ ] **Step 2.3: Add the route handler scaffold**

Edit `backend/routes/student_portal_routes.py`. Find `get_student_report_card` (Phase 2b endpoint). AFTER its closing brace, add:

```python
@student_portal_bp.route('/api/teacher/class/<class_id>/gradebook', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_gradebook(class_id):
    """Return per-(student, assessment) canonical grades for a class.

    Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
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

    # Skeleton: empty arrays. Happy-path data fetch lands in Task 3.
    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "students": [],
        "assessments": [],
        "grades": {},
    })
```

Confirm `error_response` is imported at the top of the file (added in Phase 2b).

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
pytest tests/test_gradebook.py::TestGradebookAuthz -v
```
Expected: 2 PASS.

- [ ] **Step 2.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_gradebook.py
git commit -m "feat(gradebook): route handler scaffold + authz checks"
```

---

## Task 3: Gradebook happy-path data fetch + attempt modes (TDD)

Replaces the skeleton's empty arrays with full data assembly. Covers `attempt_mode` latest/best/average + invalid fallback.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_gradebook.py`

- [ ] **Step 3.1: Append the happy-path tests**

Append to `tests/test_gradebook.py`:

```python
class TestGradebookHappyPath:
    """Happy-path data assembly: students × assessments × grades."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_returns_full_grid(self, mock_sb_fn, client, teacher_headers):
        # 2 students × 2 assessments. stu-1 submitted both; stu-2 only the first.
        subs = [
            {"id": "sub-1-A", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 80, "results": {"standards_mastery": {}, "score": 8, "total_points": 10},
             "status": "graded"},
            {"id": "sub-1-B", "student_id": "stu-1", "content_id": "ct-2",
             "attempt_number": 1, "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 70, "results": {"standards_mastery": {}, "score": 14, "total_points": 20},
             "status": "graded"},
            {"id": "sub-2-A", "student_id": "stu-2", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-11T10:00:00Z",
             "percentage": 60, "results": {"standards_mastery": {}, "score": 6, "total_points": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-2'}],
            'students': [
                {'id': 'stu-1', 'first_name': 'Alice', 'last_name': 'Anderson'},
                {'id': 'stu-2', 'first_name': 'Bob', 'last_name': 'Brown'},
            ],
            'published_content': [
                {'id': 'ct-1', 'title': 'Quiz 1', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z', 'due_date': None},
                {'id': 'ct-2', 'title': 'Quiz 2', 'content_type': 'assessment',
                 'publish_date': '2026-04-08T00:00:00Z', 'due_date': None},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Students sorted alphabetically
        assert [s['student_id'] for s in body['students']] == ['stu-1', 'stu-2']
        # Assessments sorted by publish_date ASC
        assert [a['content_id'] for a in body['assessments']] == ['ct-1', 'ct-2']
        # Grades populated for the 3 (student, content) pairs
        assert body['grades']['stu-1']['ct-1']['percentage'] == 80
        assert body['grades']['stu-1']['ct-2']['percentage'] == 70
        assert body['grades']['stu-2']['ct-1']['percentage'] == 60
        # stu-2 has no submission for ct-2 → absent from map
        assert 'ct-2' not in body['grades'].get('stu-2', {})
        # total_attempts = 1 for each (each was a single attempt)
        assert body['grades']['stu-1']['ct-1']['total_attempts'] == 1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_class_returns_empty_arrays(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [],
            'students': [],
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['students'] == []
        assert body['assessments'] == []
        assert body['grades'] == {}

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_class_with_no_assessments_returns_empty_assessments(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['students']) == 1
        assert body['assessments'] == []
        assert body['grades'] == {}

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_assessments_sorted_by_publish_date_asc(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [
                # Inserted out-of-order on purpose
                {'id': 'ct-late', 'title': 'Z-Late', 'content_type': 'assessment',
                 'publish_date': '2026-04-20T00:00:00Z'},
                {'id': 'ct-early', 'title': 'A-Early', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z'},
                {'id': 'ct-mid', 'title': 'M-Mid', 'content_type': 'assessment',
                 'publish_date': '2026-04-10T00:00:00Z'},
            ],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Sorted ASC by publish_date
        assert [a['content_id'] for a in body['assessments']] == ['ct-early', 'ct-mid', 'ct-late']


class TestGradebookAttemptModes:
    """attempt_mode: latest / best / average / invalid fallback."""

    def _setup_three_attempts(self, mock_sb_fn):
        """One student × one assessment, 3 attempts: 50%, 90%, 70%."""
        subs = [
            {"id": "sub-1", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-11T10:00:00Z", "percentage": 50,
             "results": {"standards_mastery": {}, "score": 5, "total_points": 10},
             "status": "graded"},
            {"id": "sub-2", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 2, "submitted_at": "2026-04-12T10:00:00Z", "percentage": 90,
             "results": {"standards_mastery": {}, "score": 9, "total_points": 10},
             "status": "graded"},
            {"id": "sub-3", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 3, "submitted_at": "2026-04-13T10:00:00Z", "percentage": 70,
             "results": {"standards_mastery": {}, "score": 7, "total_points": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment',
                                    'publish_date': '2026-04-10T00:00:00Z'}],
            'student_submissions': subs,
        })

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_latest_picks_most_recent_per_pair(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=latest',
            headers=teacher_headers,
        )
        body = resp.get_json()
        cell = body['grades']['stu-1']['ct-1']
        assert cell['submission_id'] == 'sub-3'
        assert cell['percentage'] == 70
        assert cell['attempt_number'] == 3
        assert cell['total_attempts'] == 3

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_best_picks_highest_per_pair(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=best',
            headers=teacher_headers,
        )
        body = resp.get_json()
        cell = body['grades']['stu-1']['ct-1']
        assert cell['submission_id'] == 'sub-2'  # 90% is best
        assert cell['percentage'] == 90
        assert cell['attempt_number'] == 2

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_average_aggregates(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=average',
            headers=teacher_headers,
        )
        body = resp.get_json()
        cell = body['grades']['stu-1']['ct-1']
        # Average of 50, 90, 70 = 70.0
        assert cell['percentage'] == 70.0
        # submission_id anchor = LATEST (sub-3) so drilldown opens most recent
        assert cell['submission_id'] == 'sub-3'
        assert cell['attempt_number'] == 3
        assert cell['total_attempts'] == 3

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_invalid_attempt_mode_falls_back_to_latest(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=garbage',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['attempt_mode'] == 'latest'
        cell = body['grades']['stu-1']['ct-1']
        assert cell['submission_id'] == 'sub-3'
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
pytest tests/test_gradebook.py::TestGradebookHappyPath tests/test_gradebook.py::TestGradebookAttemptModes -v
```
Expected: most FAIL (skeleton returns empty arrays).

- [ ] **Step 3.3: Replace the skeleton's empty-arrays return with full data assembly**

In `backend/routes/student_portal_routes.py`, replace the skeleton's `return jsonify({...empty arrays...})` block in `get_class_gradebook` with:

```python
    # 2) Fetch class roster: enrollments + students. Skip orphans silently.
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    student_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    student_records = []
    if student_ids:
        students_rows = db.table('students').select(
            'id, first_name, last_name'
        ).in_('id', student_ids).execute()
        seen = {s['id']: s for s in (students_rows.data or []) if s.get('id')}
        for sid in student_ids:
            sdata = seen.get(sid)
            if sdata is None:
                _logger.debug("Orphan enrollment in class %s: student_id=%s missing from students table", class_id, sid)
                continue
            student_records.append({
                'student_id': sid,
                'student_name': ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip(),
            })
        student_records.sort(key=lambda s: s['student_name'].lower())

    if not student_records:
        return jsonify({
            "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
            "students": [], "assessments": [], "grades": {},
        })

    # 3) Fetch all class assessments/assignments. Sort ASC by publish_date.
    content_rows = db.table('published_content').select(
        'id, title, content_type, publish_date, due_date'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

    assessments = sorted(
        (content_rows.data or []),
        key=lambda c: (c.get('publish_date') or '', c.get('id') or ''),
    )
    content_titles = {c['id']: c.get('title', '') for c in assessments}

    if not assessments:
        return jsonify({
            "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
            "students": [{'student_id': s['student_id'], 'student_name': s['student_name']} for s in student_records],
            "assessments": [], "grades": {},
        })

    # 4) Fetch non-draft submissions for these students × these contents
    student_id_set = [s['student_id'] for s in student_records]
    content_id_set = [c['id'] for c in assessments]
    subs_rows = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
    ).in_('student_id', student_id_set).in_('content_id', content_id_set).neq(
        'status', 'draft'
    ).execute()
    submissions = subs_rows.data or []

    # 5) Sanitize results.standards_mastery in place (defensive)
    for s in submissions:
        _sanitize_standards_mastery(s)

    # 6) Group by (student_id, content_id) and build the canonical-grade map
    from collections import defaultdict
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)

    grades = {}
    for sid, by_content in subs_by_student_content.items():
        per_student = {}
        for cid, subs in by_content.items():
            if not subs:
                continue
            total_attempts = len(subs)
            selected = _select_submissions_by_mode({cid: subs}, attempt_mode).get(cid, [])
            if attempt_mode == 'average':
                # mean percentage across attempts; drilldown anchor = latest
                pcts = [s.get('percentage') or 0 for s in subs]
                mean_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0
                latest = max(subs, key=lambda s: (s.get('attempt_number') or 0, _parse_ts(s.get('submitted_at'))))
                per_student[cid] = {
                    'submission_id': latest.get('id'),
                    'percentage': mean_pct,
                    'attempt_number': latest.get('attempt_number'),
                    'submitted_at': latest.get('submitted_at'),
                    'total_attempts': total_attempts,
                }
            else:
                if not selected:
                    continue
                chosen = selected[0]
                per_student[cid] = {
                    'submission_id': chosen.get('id'),
                    'percentage': chosen.get('percentage'),
                    'attempt_number': chosen.get('attempt_number'),
                    'submitted_at': chosen.get('submitted_at'),
                    'total_attempts': total_attempts,
                }
        if per_student:
            grades[sid] = per_student

    return jsonify({
        "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
        "students": [{'student_id': s['student_id'], 'student_name': s['student_name']} for s in student_records],
        "assessments": [
            {'content_id': c['id'], 'title': c.get('title', ''), 'content_type': c.get('content_type'),
             'publish_date': c.get('publish_date'), 'due_date': c.get('due_date')}
            for c in assessments
        ],
        "grades": grades,
    })
```

- [ ] **Step 3.4: Run tests to verify they pass**

```bash
pytest tests/test_gradebook.py -v
```
Expected: all pass (4 coalesce + 2 authz + 4 happy path + 4 attempt modes = 14 tests).

- [ ] **Step 3.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_gradebook.py
git commit -m "feat(gradebook): happy-path data fetch + attempt modes + sanitize"
```

---

## Task 4: Gradebook edge cases — orphan enrollment + missing-pair + malformed mastery (TDD)

**Files:**
- Modify: `tests/test_gradebook.py` (Task 3's implementation already handles these — Task 4 just adds tests to lock the behavior in)

- [ ] **Step 4.1: Append edge-case tests**

Append to `tests/test_gradebook.py`:

```python
class TestGradebookEdgeCases:
    """Orphan enrollment, missing pairs, malformed mastery."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_orphan_enrollment_skipped_silently(self, mock_sb_fn, client, teacher_headers):
        # class_students lists stu-orphan but students table doesn't have that row
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-orphan'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            # NO row for stu-orphan
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Orphan dropped; only stu-1 appears
        assert [s['student_id'] for s in body['students']] == ['stu-1']

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_pair_absent_from_grades_map(self, mock_sb_fn, client, teacher_headers):
        # stu-1 submits ct-1 only; stu-2 submits nothing.
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}, {'student_id': 'stu-2'}],
            'students': [
                {'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'},
                {'id': 'stu-2', 'first_name': 'C', 'last_name': 'D'},
            ],
            'published_content': [
                {'id': 'ct-1', 'title': 'Q1', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z'},
                {'id': 'ct-2', 'title': 'Q2', 'content_type': 'assessment',
                 'publish_date': '2026-04-08T00:00:00Z'},
            ],
            'student_submissions': [
                {"id": "sub-1", "student_id": "stu-1", "content_id": "ct-1",
                 "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 80,
                 "results": {"standards_mastery": {}, "score": 8, "total_points": 10},
                 "status": "graded"},
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        # stu-1 has ct-1 only; ct-2 absent from inner map
        assert 'ct-1' in body['grades']['stu-1']
        assert 'ct-2' not in body['grades']['stu-1']
        # stu-2 absent from outer map entirely
        assert 'stu-2' not in body['grades']

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_standards_mastery_does_not_500(self, mock_sb_fn, client, teacher_headers):
        # One submission has a list-shape standards_mastery — would 500
        # without _sanitize_standards_mastery.
        subs = [
            {"id": "sub-bad", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 60,
             "results": {"standards_mastery": ["malformed"], "score": 6, "total_points": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [
                {'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z'},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        # 200 not 500. The sanitize step replaced the list with {} so the rest of
        # the pipeline works. The student's grade is still populated.
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['grades']['stu-1']['ct-1']['percentage'] == 60
```

- [ ] **Step 4.2: Run all tests**

```bash
pytest tests/test_gradebook.py -v
```
Expected: 17 passed.

- [ ] **Step 4.3: Commit**

```bash
git add tests/test_gradebook.py
git commit -m "test(gradebook): edge cases — orphan, missing-pair, malformed-mastery"
```

---

## Task 5: SubmissionDetail endpoint scaffold + authz (TDD)

The second backend endpoint. Returns submission metadata + per-question breakdown + sibling attempts list.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Create: `tests/test_submission_detail.py`

- [ ] **Step 5.1: Create the test file with authz tests**

Create `tests/test_submission_detail.py`:

```python
"""Tests for the submission detail endpoint.

Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


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
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=execute_data if execute_data is not None else [])
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


class TestSubmissionDetailAuthz:
    """Auth + ownership chain checks."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/submission/sub-1/detail')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_submission_not_found_returns_404(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/submission/missing-id/detail', headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_submission_content_deleted_returns_404(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-deleted',
                 'attempt_number': 1, 'percentage': 80, 'submitted_at': '2026-04-10T10:00:00Z',
                 'results': {'questions': [], 'score': 8, 'total_points': 10}, 'status': 'graded'},
            ],
            'published_content': [],  # content row missing
        })
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_submission_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 1, 'percentage': 80, 'submitted_at': '2026-04-10T10:00:00Z',
                 'results': {'questions': [], 'score': 8, 'total_points': 10}, 'status': 'graded'},
            ],
            'published_content': [
                {'id': 'ct-1', 'title': 'Q', 'class_id': 'cls-other'},
            ],
            'classes': [{'id': 'cls-other', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/forbidden'
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
pytest tests/test_submission_detail.py -v
```
Expected: 4 FAIL.

- [ ] **Step 5.3: Add the route handler**

Edit `backend/routes/student_portal_routes.py`. After `get_class_gradebook`, add:

```python
@student_portal_bp.route('/api/teacher/submission/<submission_id>/detail', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_submission_detail(submission_id):
    """Return per-submission detail: metadata + per-question breakdown + sibling attempts.

    Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
    """
    db = _get_teacher_supabase()

    # 1) Look up the submission
    sub_row = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status, score, total_points'
    ).eq('id', submission_id).execute()
    if not sub_row.data:
        return error_response("Submission not found", 404)
    sub = sub_row.data[0]

    # 2) Look up the content
    content_id = sub.get('content_id')
    content_row = db.table('published_content').select(
        'id, title, class_id'
    ).eq('id', content_id).execute()
    if not content_row.data:
        return error_response("Submission's content no longer exists", 404)
    content = content_row.data[0]

    # 3) Verify class ownership
    class_row = db.table('classes').select('id, teacher_id').eq('id', content.get('class_id')).execute()
    if not class_row.data or class_row.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)

    # 4) Look up the student
    student_id = sub.get('student_id')
    student_row = db.table('students').select(
        'id, first_name, last_name'
    ).eq('id', student_id).execute()
    if not student_row.data:
        return error_response("Student not found", 404)
    sdata = student_row.data[0]
    student_name = ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip()

    # 5) Sibling attempts (same student × same content)
    siblings_row = db.table('student_submissions').select(
        'id, attempt_number, submitted_at, percentage'
    ).eq('student_id', student_id).eq('content_id', content_id).execute()
    siblings = sorted(
        siblings_row.data or [],
        key=lambda s: (s.get('attempt_number') or 0, _parse_ts(s.get('submitted_at'))),
    )

    # 6) Top-level score with row + results fallback. Use _coalesce so legitimate 0 isn't lost.
    results = sub.get('results') or {}
    points_earned = _coalesce(results.get('score'), sub.get('score'), default=0)
    points_possible = _coalesce(results.get('total_points'), sub.get('total_points'), default=0)

    # 7) Per-question breakdown — full implementation lands in Task 6
    questions = []  # placeholder for Task 6

    return jsonify({
        "submission_id": sub.get('id'),
        "student_id": student_id,
        "student_name": student_name,
        "content_id": content_id,
        "content_title": content.get('title', ''),
        "attempt_number": sub.get('attempt_number'),
        "total_attempts": len(siblings),
        "submitted_at": sub.get('submitted_at'),
        "percentage": sub.get('percentage'),
        "points_earned": points_earned,
        "points_possible": points_possible,
        "questions": questions,
        "sibling_attempts": [
            {"submission_id": s.get('id'), "attempt_number": s.get('attempt_number'),
             "submitted_at": s.get('submitted_at'), "percentage": s.get('percentage')}
            for s in siblings
        ],
    })
```

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
pytest tests/test_submission_detail.py -v
```
Expected: 4 PASS.

- [ ] **Step 5.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_submission_detail.py
git commit -m "feat(submission-detail): route handler + authz chain + scaffold"
```

---

## Task 6: SubmissionDetail per-question normalization (TDD)

Replace the empty `questions = []` placeholder with the per-question breakdown using the spec's fallback rules. Use `_coalesce` for first-non-None semantics.

**Files:**
- Modify: `backend/routes/student_portal_routes.py`
- Modify: `tests/test_submission_detail.py`

- [ ] **Step 6.1: Append happy-path + fallback tests**

Append to `tests/test_submission_detail.py`:

```python
class TestSubmissionDetailHappyPath:
    """Per-question normalization + sibling attempts."""

    def _setup_with_submission(self, mock_sb_fn, results):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 2, 'percentage': 80, 'submitted_at': '2026-04-12T10:00:00Z',
                 'results': results, 'status': 'graded',
                 'score': results.get('score'), 'total_points': results.get('total_points')},
                # Sibling attempt 1
                {'id': 'sub-0', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 1, 'percentage': 60, 'submitted_at': '2026-04-10T10:00:00Z',
                 'results': {}, 'status': 'graded'},
            ],
            'published_content': [
                {'id': 'ct-1', 'title': 'Quiz 1', 'class_id': 'cls-1'},
            ],
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
            'students': [{'id': 'stu-1', 'first_name': 'Alice', 'last_name': 'Anderson'}],
        })

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_questions_normalized_with_fallback_keys(self, mock_sb_fn, client, teacher_headers):
        # Mix of grader-shapes: one entry uses `question`, one uses `question_text`,
        # one uses `feedback`, one uses `reasoning`.
        results = {
            "score": 8, "total_points": 10,
            "questions": [
                {"question": "What is 2+2?", "type": "multiple_choice", "answer": "4",
                 "correct_answer": "4", "is_correct": True, "feedback": "Correct.",
                 "points_earned": 5, "points_possible": 5},
                {"question_text": "Discuss photosynthesis.", "question_type": "written",
                 "student_answer": "Plants convert light to energy.", "correct_answer": None,
                 "is_correct": None, "reasoning": "Mostly correct but lacks chlorophyll mention.",
                 "points": 5, "score": 3},
            ],
        }
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Top-level
        assert body['submission_id'] == 'sub-1'
        assert body['student_name'] == 'Alice Anderson'
        assert body['content_title'] == 'Quiz 1'
        assert body['attempt_number'] == 2
        assert body['total_attempts'] == 2  # sub-0 + sub-1
        assert body['points_earned'] == 8
        assert body['points_possible'] == 10
        # Per-question normalization
        qs = body['questions']
        assert len(qs) == 2
        assert qs[0]['question_text'] == 'What is 2+2?'
        assert qs[0]['question_type'] == 'multiple_choice'
        assert qs[0]['student_answer'] == '4'
        assert qs[0]['ai_feedback'] == 'Correct.'
        assert qs[0]['points_earned'] == 5
        assert qs[0]['points_possible'] == 5
        # Second question uses fallback keys
        assert qs[1]['question_text'] == 'Discuss photosynthesis.'
        assert qs[1]['question_type'] == 'written'
        assert qs[1]['student_answer'] == 'Plants convert light to energy.'
        assert qs[1]['ai_feedback'] == 'Mostly correct but lacks chlorophyll mention.'
        assert qs[1]['points_earned'] == 3  # falls back to `score`
        assert qs[1]['points_possible'] == 5  # falls back to `points`
        assert qs[1]['correct_answer'] is None
        assert qs[1]['is_correct'] is None

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_zero_score_not_falsy_treated(self, mock_sb_fn, client, teacher_headers):
        """Legitimate 0 must not fall through to row.score fallback."""
        results = {
            "score": 0, "total_points": 10,
            "questions": [{"question": "Q", "answer": "wrong",
                            "points_earned": 0, "points_possible": 5}],
        }
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['points_earned'] == 0
        assert body['questions'][0]['points_earned'] == 0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_questions_returns_empty_array_with_200(self, mock_sb_fn, client, teacher_headers):
        results = {"score": 8, "total_points": 10}  # no `questions` key
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['questions'] == []
```

- [ ] **Step 6.2: Run to confirm failures**

```bash
pytest tests/test_submission_detail.py::TestSubmissionDetailHappyPath -v
```
Expected: 3 FAIL (placeholder still empty).

- [ ] **Step 6.3: Replace the `questions = []` placeholder with normalization logic**

In `get_student_submission_detail`, replace the line:
```python
    questions = []  # placeholder for Task 6
```

With:
```python
    # 7) Per-question normalization (spec fallback rules)
    raw_questions = results.get('questions')
    questions = []
    if isinstance(raw_questions, list):
        for q in raw_questions:
            if not isinstance(q, dict):
                _logger.warning("malformed question entry (type=%s) in submission %s — skipping",
                                type(q).__name__, submission_id)
                continue
            questions.append({
                "question_text": _coalesce(q.get('question'), q.get('question_text'), default=''),
                "question_type": _coalesce(q.get('type'), q.get('question_type'), default='unknown'),
                "student_answer": _coalesce(q.get('student_answer'), q.get('answer'), default=''),
                "correct_answer": q.get('correct_answer'),
                "is_correct": q.get('is_correct'),
                "ai_feedback": _coalesce(q.get('feedback'), q.get('reasoning'), q.get('quality'), default=''),
                "points_earned": _coalesce(q.get('points_earned'), q.get('score'), default=0),
                "points_possible": _coalesce(q.get('points_possible'), q.get('points'), default=0),
            })
    elif raw_questions is not None:
        _logger.warning("malformed results.questions (type=%s) in submission %s — returning empty",
                        type(raw_questions).__name__, submission_id)
```

- [ ] **Step 6.4: Run tests to verify they pass**

```bash
pytest tests/test_submission_detail.py -v
```
Expected: 7 PASS (4 authz + 3 happy path).

- [ ] **Step 6.5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_submission_detail.py
git commit -m "feat(submission-detail): per-question normalization with fallback rules"
```

---

## Task 7: Frontend API client (~10 LOC)

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 7.1: Add the two client functions**

Edit `frontend/src/services/api.js`. Find `getStudentReportCard` (added in Phase 2b). After it, add:

```javascript
export async function getClassGradebook(classId, attemptMode) {
  var mode = attemptMode || 'latest';
  var params = new URLSearchParams({ attempt_mode: mode });
  return fetchApi(
    '/api/teacher/class/' + encodeURIComponent(classId) +
    '/gradebook?' + params.toString()
  );
}

export async function getSubmissionDetail(submissionId) {
  return fetchApi('/api/teacher/submission/' + encodeURIComponent(submissionId) + '/detail');
}
```

- [ ] **Step 7.2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 7.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/services/api.js
git commit -m "feat(gradebook): frontend API clients"
```

---

## Task 8: Gradebook component (~220 LOC)

**Files:**
- Create: `frontend/src/tabs/Gradebook.jsx`

- [ ] **Step 8.1: Create the component**

Create `frontend/src/tabs/Gradebook.jsx`:

```javascript
import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import SubmissionDetail from "./SubmissionDetail";

function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

export default function Gradebook({ classId }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [missingOnly, setMissingOnly] = useState(false);
  var [selectedSubmissionId, setSelectedSubmissionId] = useState(null);

  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassGradebook(classId, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load gradebook');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load gradebook');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [classId, attemptMode]);

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading gradebook...</p>
      </div>
    );
  }
  if (error) {
    return <div className="glass-card" style={{ padding: "40px", color: "var(--danger)", textAlign: "center" }}>{error}</div>;
  }
  if (!data) return null;

  var students = data.students || [];
  var assessments = data.assessments || [];
  var grades = data.grades || {};

  var displayStudents = !missingOnly ? students : students.filter(function(s) {
    var row = grades[s.student_id] || {};
    return assessments.some(function(a) { return !row[a.content_id]; });
  });

  var btnStyle = function(active) {
    return {
      padding: "6px 14px", borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
    };
  };

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Gradebook {String.fromCharCode(8212)} {data.class_name}
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {students.length} students {String.fromCharCode(8226)} {assessments.length} assessments
      </p>

      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setMissingOnly(false); }} style={btnStyle(!missingOnly)}>All Students</button>
          <button onClick={function() { setMissingOnly(true); }} style={btnStyle(missingOnly)}>Missing Only</button>
        </div>
      </div>

      {students.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          No students enrolled in this class yet.
        </p>
      ) : assessments.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          No assessments published to this class yet.
        </p>
      ) : displayStudents.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          All students have submitted everything.
        </p>
      ) : (
        <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "600px" }}>
            <thead>
              <tr>
                <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 2, padding: "10px 14px", textAlign: "left", fontSize: "0.8rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>Student</th>
                {assessments.map(function(a) {
                  return (
                    <th key={a.content_id} style={{ padding: "10px 8px", fontSize: "0.7rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", minWidth: "100px", textAlign: "center" }}>
                      {a.title}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {displayStudents.map(function(student) {
                var row = grades[student.student_id] || {};
                return (
                  <tr key={student.student_id}>
                    <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)" }}>
                      {student.student_name}
                    </td>
                    {assessments.map(function(a) {
                      var cell = row[a.content_id];
                      var color = masteryColor(cell ? cell.percentage : null);
                      var clickable = !!cell;
                      return (
                        <td key={a.content_id}
                            onClick={function() { if (clickable) setSelectedSubmissionId(cell.submission_id); }}
                            style={{ padding: "10px 8px", textAlign: "center", borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", background: color.bg, color: color.text, fontSize: "0.8rem", fontWeight: 600, cursor: clickable ? "pointer" : "default" }}
                            title={clickable ? "Click to see this submission's detail" : "No submission"}>
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

      {selectedSubmissionId && (
        <SubmissionDetail
          submissionId={selectedSubmissionId}
          onClose={function() { setSelectedSubmissionId(null); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 8.2: Verify build (will FAIL because SubmissionDetail doesn't exist yet)**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build FAILS — `Could not resolve "./SubmissionDetail"`. That's expected; Task 9 creates it.

- [ ] **Step 8.3: DON'T commit yet** — wait until Task 9 also lands so the tree builds. (Ship Tasks 8 + 9 in two commits but the second commit makes the build green.)

---

## Task 9: SubmissionDetail component (~250 LOC)

**Files:**
- Create: `frontend/src/tabs/SubmissionDetail.jsx`

- [ ] **Step 9.1: Create the component**

Create `frontend/src/tabs/SubmissionDetail.jsx`:

```javascript
import React, { useState, useEffect } from "react";
import * as api from "../services/api";

function gradeColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

function formatDate(iso) {
  if (!iso) return String.fromCharCode(8212);
  try {
    var d = new Date(iso);
    return (d.getMonth() + 1) + "/" + d.getDate();
  } catch (e) {
    return String.fromCharCode(8212);
  }
}

export default function SubmissionDetail({ submissionId, onClose }) {
  // Local state — attempt selector mutates this, NOT the prop
  var [activeSubmissionId, setActiveSubmissionId] = useState(submissionId);
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [expandedQuestionIndex, setExpandedQuestionIndex] = useState(null);

  // Re-sync local state if prop changes (e.g., parent opens drawer with different submission)
  useEffect(function() { setActiveSubmissionId(submissionId); }, [submissionId]);

  useEffect(function() {
    if (!activeSubmissionId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    setExpandedQuestionIndex(null);
    api.getSubmissionDetail(activeSubmissionId)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load submission');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load submission');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [activeSubmissionId]);

  useEffect(function() {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return function() { window.removeEventListener('keydown', onKey); };
  }, [onClose]);

  return (
    <div
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 9500, display: "flex", justifyContent: "flex-end" }}
      onClick={onClose}
    >
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)" }} />
      <div className="glass-card"
           style={{ position: "relative", width: "min(600px, 100vw)", height: "100%", background: "var(--card-bg)", borderLeft: "1px solid var(--glass-border)", boxShadow: "-4px 0 20px rgba(0,0,0,0.2)", padding: "24px", overflowY: "auto" }}
           onClick={function(e) { e.stopPropagation(); }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{data ? data.student_name : 'Submission'}</h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              {data ? data.content_title : ''}
            </p>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.4rem" }}>
            {String.fromCharCode(10005)}
          </button>
        </div>

        {loading && <p style={{ color: "var(--text-secondary)" }}>Loading...</p>}
        {error && <div style={{ color: "var(--danger)" }}>{error}</div>}

        {data && !loading && !error && (
          <div>
            <div style={{ marginBottom: "16px", padding: "12px", background: "var(--glass-bg)", borderRadius: "8px" }}>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{data.percentage}%</div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                {data.points_earned}/{data.points_possible} pts {String.fromCharCode(8226)} attempt {data.attempt_number} of {data.total_attempts} {String.fromCharCode(8226)} submitted {formatDate(data.submitted_at)}
              </div>
            </div>

            {data.sibling_attempts && data.sibling_attempts.length > 1 && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "6px" }}>Switch attempt</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {data.sibling_attempts.map(function(a) {
                    var isActive = a.submission_id === activeSubmissionId;
                    return (
                      <button key={a.submission_id}
                              onClick={function() { setActiveSubmissionId(a.submission_id); }}
                              disabled={isActive}
                              style={{ padding: "4px 10px", fontSize: "0.75rem", borderRadius: "6px", border: "1px solid var(--glass-border)", background: isActive ? "rgba(99,102,241,0.15)" : "var(--glass-bg)", color: isActive ? "var(--accent-primary)" : "var(--text-secondary)", cursor: isActive ? "default" : "pointer" }}>
                        Attempt {a.attempt_number} ({a.percentage}%)
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Per-question breakdown</h4>
            {(!data.questions || data.questions.length === 0) ? (
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Per-question detail not available for this submission.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {data.questions.map(function(q, i) {
                  var qPct = q.points_possible > 0 ? Math.round((q.points_earned / q.points_possible) * 100) : null;
                  var color = gradeColor(qPct);
                  var isExpanded = expandedQuestionIndex === i;
                  return (
                    <div key={i} style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "10px 12px", background: color.bg }}>
                      <div onClick={function() { setExpandedQuestionIndex(isExpanded ? null : i); }}
                           style={{ display: "flex", justifyContent: "space-between", cursor: "pointer", alignItems: "center" }}>
                        <div style={{ flex: 1, fontSize: "0.85rem", color: color.text, fontWeight: 600 }}>
                          {(i + 1) + ". " + (q.question_text || '(no question text)')}
                        </div>
                        <div style={{ fontWeight: 700, color: color.text, fontSize: "0.9rem", marginLeft: "10px" }}>
                          {q.points_earned}/{q.points_possible}
                        </div>
                      </div>
                      {isExpanded && (
                        <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: "1px solid var(--glass-border)", display: "flex", flexDirection: "column", gap: "8px" }}>
                          <div style={{ fontSize: "0.8rem" }}>
                            <strong style={{ color: "var(--text-secondary)" }}>Student answer:</strong>{" "}
                            <span>{q.student_answer || '(blank)'}</span>
                          </div>
                          {q.correct_answer != null && (
                            <div style={{ fontSize: "0.8rem" }}>
                              <strong style={{ color: "var(--text-secondary)" }}>Correct answer:</strong>{" "}
                              <span>{q.correct_answer}</span>
                            </div>
                          )}
                          {q.ai_feedback && (
                            <div style={{ fontSize: "0.8rem" }}>
                              <strong style={{ color: "var(--text-secondary)" }}>AI feedback:</strong>{" "}
                              <span>{q.ai_feedback}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            <p style={{ marginTop: "20px", fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center" }}>
              Read-only view. Manual grade overrides will arrive in a future phase.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 9.2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green (Tasks 8 + 9 components both compile now).

- [ ] **Step 9.3: Commit Tasks 8 + 9 together**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/Gradebook.jsx frontend/src/tabs/SubmissionDetail.jsx
git commit -m "feat(gradebook): Gradebook table + SubmissionDetail drawer"
```

---

## Task 10: AnalyticsTab sub-tab switcher (wire-up)

**Files:**
- Modify: `frontend/src/tabs/AnalyticsTab.jsx`

- [ ] **Step 10.1: Add the import**

Edit `frontend/src/tabs/AnalyticsTab.jsx`. Find the existing `import ProgressRankGrid from "./ProgressRankGrid";` (around line 27). After it, add:
```javascript
import Gradebook from "./Gradebook";
```

- [ ] **Step 10.2: Add sub-tab state**

Find the existing `selectedClassForGrid` state (around line 2385). After it, add:
```javascript
  // Phase 3a: sub-tab switcher inside class-scoped view
  var [classView, setClassView] = useState('progressRank'); // 'progressRank' | 'gradebook'
```

- [ ] **Step 10.3: Replace the ProgressRankGrid render with the switcher + conditional render**

Find the existing render that says:
```javascript
{selectedClassForGrid !== 'all' ? (
  <ProgressRankGrid classId={selectedClassForGrid} />
) : analyticsLoading ? (
```

Replace the `<ProgressRankGrid classId={selectedClassForGrid} />` line and surrounding ternary with:
```javascript
{selectedClassForGrid !== 'all' ? (
  <div>
    {/* Sub-tab switcher (Phase 3a) */}
    <div style={{ display: "flex", gap: "4px", marginBottom: "12px" }}>
      <button
        onClick={function() { setClassView('progressRank'); }}
        style={{
          padding: "8px 16px",
          borderRadius: "8px",
          border: "1px solid " + (classView === 'progressRank' ? "var(--accent-primary)" : "var(--glass-border)"),
          background: classView === 'progressRank' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
          color: classView === 'progressRank' ? "var(--accent-primary)" : "var(--text-secondary)",
          fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
        }}>
        Progress Rank
      </button>
      <button
        onClick={function() { setClassView('gradebook'); }}
        style={{
          padding: "8px 16px",
          borderRadius: "8px",
          border: "1px solid " + (classView === 'gradebook' ? "var(--accent-primary)" : "var(--glass-border)"),
          background: classView === 'gradebook' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
          color: classView === 'gradebook' ? "var(--accent-primary)" : "var(--text-secondary)",
          fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
        }}>
        Gradebook
      </button>
    </div>
    {/* Conditional render — inactive sub-tab is unmounted so drawers can't collide */}
    {classView === 'progressRank' ? (
      <ProgressRankGrid classId={selectedClassForGrid} />
    ) : (
      <Gradebook classId={selectedClassForGrid} />
    )}
  </div>
) : analyticsLoading ? (
```

(Only the inner content of the `selectedClassForGrid !== 'all'` branch changes — wrap in a `<div>`, add the switcher buttons + conditional component.)

- [ ] **Step 10.4: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 10.5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/AnalyticsTab.jsx
git commit -m "feat(analytics): sub-tab switcher (Progress Rank / Gradebook)"
```

---

## Task 11: Manual smoke test

**Files:** none modified.

- [ ] **Step 11.1: Start backend**

```bash
source venv/bin/activate
python -m backend.app
```
Backend serves at `http://localhost:3000`. Leave running.

- [ ] **Step 11.2: Build frontend (in another terminal)**

```bash
cd frontend && npm run build
```

- [ ] **Step 11.3: Open the dashboard**

Open `http://localhost:3000` in a browser. Sign in. Use a teacher account that has at least one class with submitted assessments.

- [ ] **Step 11.4: Verify the gradebook**

1. Navigate to Analytics.
2. Pick a specific class from the "All Classes" dropdown (Phase 2's class selector).
3. Verify the new sub-tab switcher (Progress Rank / Gradebook) appears.
4. Click "Gradebook" — the gradebook table renders.
5. Verify:
   - [ ] Header shows class name + "X students × Y assessments".
   - [ ] Sticky student-name column on left + sticky assessment-header row on top.
   - [ ] Cells show percentages with 3-tier color (green/yellow/red).
   - [ ] Missing pairs show `—` in muted gray and are NOT clickable.
   - [ ] Click a populated cell → SubmissionDetail drawer slides in.
   - [ ] Drawer shows score badge + attempt-of-N + per-question breakdown.
   - [ ] Click a question → expands inline with student answer + correct answer (if present) + AI feedback.
   - [ ] Drawer's attempt selector switches between sibling attempts (drawer re-fetches).
   - [ ] Click backdrop / × / press Esc → drawer closes.
6. Toggle attempt mode (Latest / Best / Average) — cells update.
7. Toggle "Missing only" — rows filter to students with missing assessments.
8. Switch back to "Progress Rank" sub-tab — class context preserved.
9. Verify both drawers (StudentReportCard from Progress Rank, SubmissionDetail from Gradebook) cannot be open simultaneously: open one drawer, switch sub-tabs, the inactive sub-tab's component (and its drawer) should be unmounted.

- [ ] **Step 11.5: If any failure, fix + commit**

Each fix gets its own commit (`fix(gradebook): <what>`).

---

## Task 12: Push branch

**Files:** none modified.

- [ ] **Step 12.1: Push**

```bash
git push -u origin phase3a/gradebook
```

The controller (subagent-driven-development controller) opens the PR after Codex cross-check.

---

## Sequencing + dependencies

**Single PR, sequential tasks:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12.

Tasks 1-4 are pure backend (gradebook endpoint). Tasks 5-6 are pure backend (submission-detail endpoint). Task 7 is frontend API client. Tasks 8-9 are pure frontend (components). Task 10 is the frontend wire-up. Task 11 is manual smoke. Task 12 ships the branch.

**Tasks 8 + 9 are co-dependent** (Gradebook imports SubmissionDetail). They commit as one unit — Task 8's build verification will FAIL by design until Task 9 lands.

---

## Testing strategy

- 17 backend tests on the gradebook endpoint (4 coalesce + 2 authz + 4 happy path + 4 attempt modes + 3 edge cases).
- 7 backend tests on the submission-detail endpoint (4 authz + 3 happy path/normalization).
- Total new backend tests: 24.
- Frontend: build verification only (consistent with Phase 2 / 2b).
- Existing 1671+ unit tests + 24 from Phase 2b must still pass on each commit.
- All 8 CI jobs must pass.
- Routes are NOT in mypy strict scope (Phase 5d only typed `backend/grading/*` + 5 small modules). The new route handlers do not need annotations to satisfy CI.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| Gradebook endpoint authz (401/403) | Task 2 |
| Gradebook attempt mode + happy path | Task 3 |
| Average mode mean + latest anchor | Task 3 |
| Orphan enrollment / missing pair / malformed mastery | Task 3 (impl) + Task 4 (tests) |
| Sort by name (students) + publish_date (assessments) | Task 3 |
| Submission detail authz (401/403/404) | Task 5 |
| Submission detail per-question normalization with `_coalesce` | Task 6 |
| Frontend API client with URLSearchParams + encodeURIComponent | Task 7 |
| Gradebook.jsx (sticky cols, 3-tier color, "Missing only" filter) | Task 8 |
| SubmissionDetail.jsx (drawer at z-index 9500, Esc close, attempt selector mutates LOCAL activeSubmissionId) | Task 9 |
| AnalyticsTab sub-tab switcher (conditional unmount) | Task 10 |
| Manual smoke test | Task 11 |

Every spec § Backend / § Frontend / § Error handling bullet maps to a plan task.

**2. Placeholder scan:** No TBD/TODO/FIXME markers. Every code step has complete code blocks.

**3. Type consistency:**
- `_coalesce(*vals, default=None)` — same signature in Task 1 + every later use (Tasks 3, 5, 6).
- `get_class_gradebook(class_id)` and `get_student_submission_detail(submission_id)` — handler names consistent across Tasks 2/3/4 and 5/6.
- Endpoint URLs `/api/teacher/class/<class_id>/gradebook` and `/api/teacher/submission/<submission_id>/detail` — same in spec, handlers, tests, API client, frontend.
- Response field names: `students[].student_id`, `assessments[].content_id`, `grades[student_id][content_id].submission_id/percentage/attempt_number/total_attempts/submitted_at` — consistent across spec, handler, frontend reads.
- Submission-detail response field names: `submission_id, student_id, student_name, content_id, content_title, attempt_number, total_attempts, submitted_at, percentage, points_earned, points_possible, questions[], sibling_attempts[]` — consistent.

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-25-phase3a-gradebook.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task bundle, two-stage review between tasks (spec compliance + code quality), Codex full-PR cross-check before merge, fast iteration in this session.

**2. Inline Execution** — Execute tasks here in this session via executing-plans, batched with checkpoints.

**Which approach?**
