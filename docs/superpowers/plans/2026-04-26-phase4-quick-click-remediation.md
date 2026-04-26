# Phase 4 — Quick-Click Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teachers click a red mastery cell or column header in the Progress Rank grid → AI generates 8 grade-level practice questions for that standard → preview-then-publish drawer → the assessment lands in `published_content` targeted to the student(s) who need it.

**Architecture:** New `POST /api/teacher/class/<class_id>/remediate` route (in `student_portal_routes.py`) calls the LLM adapter to generate, then runs `_post_process_assignment` with remediation defaults (5 MC + 3 SA, grade-level inferred). URL convention matches Phase 2/2b/3a/3b. One new column `published_content.target_student_ids JSONB NULL` enables per-student visibility. New shared helper `_content_visible_to_student` applied across 7 student-facing endpoints. `publish_to_class` is hardened with class-ownership + targeting validation (closes a pre-existing gap). Frontend: new `RemediationDrawer.jsx` + 2 trigger surfaces in `ProgressRankGrid.jsx` (cell click + column-header hover-reveal).

**Tech Stack:** Flask + flask-limiter + Supabase (PostgREST) + React + Vite. Reuses Phase 1+ standards mastery rollup, Phase 2 `_select_submissions_by_mode` / `_aggregate_mastery_for_student`, Phase 2b `_sanitize_standards_mastery`, Phase 3a `_coalesce`, Phase 3b filter-aware `_make_chain` test mock, Phase 5d `error_response` (RFC 7807), Phase 5a structured logging. Accommodation helper `build_accommodation_prompt(student_id, teacher_id)` from `backend/accommodations.py:475` (returns "" on missing — already FERPA-safe; portal grading wraps in try/except, we mirror).

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `tests/test_remediation.py` | **Create** | 29 backend tests (10 validation + 5 generation + 3 accommodations + 3 red-tier + 3 visibility helper + 5 publish hardening) |
| `backend/routes/student_portal_routes.py` | **Modify** (append) | New `get_class_remediate` route handler (~280 LOC) at end of file |
| `backend/database/migration_2026_04_26_phase4_target_student_ids.sql` | **Create** | One ALTER TABLE for `target_student_ids JSONB NULL` |
| `backend/database/rollback_2026_04_26_phase4_target_student_ids.sql` | **Create** | Companion rollback (DROP COLUMN) |
| `tests/test_migration_target_student_ids.py` | **Create** | 1 migration shape test |
| `backend/routes/student_account_routes.py` | **Modify** | Add `_content_visible_to_student` helper, apply to 7 endpoints, harden `publish_to_class`, add enrollment recheck to `_validate_student_session` |
| `tests/test_student_account_coverage.py` | **Modify** (append) | +1 test: `student_dashboard` list-filter |
| `tests/test_student_resources.py` | **Modify** (append) | +1 test: `student_resources` list-filter |
| `tests/test_student_content_visibility.py` | **Create** | 5 deny tests for single-row paths (resource content / content / submit / draft GET / draft POST) |
| `frontend/src/services/api.js` | **Modify** | New `postRemediate(...)` + extend `publishToClass(...)` body with `target_student_ids` |
| `frontend/src/tabs/RemediationDrawer.jsx` | **Create** | ~280 LOC drawer with state machine, slim local editor, pre-publish validation |
| `frontend/src/tabs/ProgressRankGrid.jsx` | **Modify** | Cell-popover button + column-header hover-reveal trigger |

Don't touch: Clever / ClassLink / OneRoster / LTI surfaces; Phase 5d infrastructure (`error_response`, `mypy.ini`); existing helpers (use, don't modify); the accommodation helper itself.

---

## Bundle 1 — Backend route + tests (Tasks 1-7)

### Task 1: Test scaffolding

**Files:**
- Create: `tests/test_remediation.py`

- [ ] **Step 1.1: Create the test file with fixtures + filter-aware mock**

Create `tests/test_remediation.py`:

```python
"""Tests for the Phase 4 Quick-Click Remediation endpoint.

Spec: docs/superpowers/specs/2026-04-26-phase4-quick-click-remediation-design.md
"""
import os
import sys
import json
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
    """Filter-aware Supabase mock — applies .eq() / .in_() / .neq() filters
    AND .range() slicing at .execute() time. Mirrors Phase 3b precedent."""
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    filters = []
    range_bounds = []

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

    def _range(start, end):
        range_bounds.append((start, end))
        return chain
    chain.range.side_effect = _range

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
            elif op == 'in':
                result = [r for r in result if r.get(field) in value]
            elif op == 'neq':
                result = [r for r in result if r.get(field) != value]
        if range_bounds:
            start, end = range_bounds[-1]
            result = result[start:end + 1]
            range_bounds.clear()
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


CLS_OWNED = [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001',
              'grade_level': '6', 'subject': 'Math'}]

CID_Q1 = '11111111-1111-1111-1111-111111111111'
STU_1 = 'stu-1111-1111-1111-1111-111111111111'
STU_2 = 'stu-2222-2222-2222-2222-222222222222'


def _sub(sub_id, student_id, content_id, percentage, mastery_dict, status='graded',
         attempt=1, submitted_at='2026-04-10T10:00:00Z'):
    return {
        'id': sub_id, 'student_id': student_id, 'content_id': content_id,
        'attempt_number': attempt, 'submitted_at': submitted_at,
        'percentage': percentage,
        'results': {'standards_mastery': mastery_dict, 'score': percentage / 10, 'total_points': 10},
        'status': status,
    }
```

- [ ] **Step 1.2: Verify the file imports cleanly (pytest collect)**

```bash
source venv/bin/activate
pytest tests/test_remediation.py --collect-only 2>&1 | tail -5
```
Expected: `collected 0 items` (no tests yet, but no import errors).

- [ ] **Step 1.3: Commit**

```bash
git add tests/test_remediation.py
git commit -m "test(remediate): test scaffolding (fixtures + filter-aware mock)"
```

---

### Task 2: Validation tests + route scaffold

**Files:**
- Modify: `tests/test_remediation.py`
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 2.1: Append 10 validation tests**

Append to `tests/test_remediation.py`:

```python
# ============ Validation tests ============

class TestRemediateValidation:
    """Auth + 6-step validation order."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        })
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'teacher_id': 'OTHER', 'name': 'X',
                         'grade_level': '6', 'subject': 'Math'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_bogus_target_mode_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'bogus',
        }, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'target_mode' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_target_student_id_for_single_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_target_student_uuid_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': 'not-a-uuid',
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_target_student_not_in_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],  # student NOT enrolled
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_standard_code_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': '',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_single_student_no_historical_evidence_returns_400(self, mock_sb_fn, client, teacher_headers):
        # Student exists in class but has no submissions covering this standard.
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'historical' in body.get('detail', '').lower() or 'prior' in body.get('detail', '').lower()

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_red_tier_no_red_students_returns_400(self, mock_sb_fn, client, teacher_headers):
        # Student exists, has a submission, but mastery is >=70 (not red).
        green_mastery = {'MA.6.AR.1.2': {'points_earned': 9, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 90, green_mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'red-tier' in body.get('detail', '').lower() or 'no' in body.get('detail', '').lower()

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_cross_class_injection_returns_403(self, mock_sb_fn, client, teacher_headers):
        # Student is in a DIFFERENT class.
        other_stu = 'stu-other-other-other-other-otherotherother'
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-other', 'student_id': other_stu}],
            'students': [{'id': other_stu}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'class_id': 'cls-1', 'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': other_stu,
        }, headers=teacher_headers)
        assert resp.status_code == 403
```

- [ ] **Step 2.2: Run tests to verify they fail (route doesn't exist)**

```bash
pytest tests/test_remediation.py::TestRemediateValidation -v
```
Expected: 10 FAIL — endpoint doesn't exist (404 from Flask routing).

- [ ] **Step 2.3: Add the route handler scaffold + validation**

Edit `backend/routes/student_portal_routes.py`. Find the file end (after the last route handler — likely after `get_class_assessment_comparison`). Append:

```python
@student_portal_bp.route('/api/teacher/class/<class_id>/remediate', methods=['POST'])
@require_teacher
@handle_route_errors
@limiter.limit("10 per minute")
def post_remediate(class_id):
    """Phase 4 Quick-Click Remediation: generate 8 grade-level practice
    questions targeted to a single student or class red-tier on one standard.

    Spec: docs/superpowers/specs/2026-04-26-phase4-quick-click-remediation-design.md
    """
    import uuid as _uuid
    from flask_limiter.util import get_remote_address  # noqa: F401  (limiter import side-effect)

    db = _get_teacher_supabase()
    body = request.get_json(silent=True) or {}
    standard_code = (body.get('standard_code') or '').strip()
    target_mode = body.get('target_mode')
    target_student_id = body.get('target_student_id')

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id, grade_level, subject').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    cls_row = cls.data[0]

    # 2) target_mode validation
    if target_mode not in ('single_student', 'red_tier_in_class'):
        return error_response("target_mode must be 'single_student' or 'red_tier_in_class'", 400)

    # 3) Single-student: target_student_id required + UUID + enrollment
    if target_mode == 'single_student':
        if not target_student_id:
            return error_response("target_student_id is required for single_student mode", 400)
        try:
            _uuid.UUID(str(target_student_id))
        except (ValueError, TypeError):
            return error_response("target_student_id must be a valid UUID", 400)
        # Enrollment check: must be in class_students AND must exist in students.
        enr = db.table('class_students').select('student_id').eq(
            'class_id', class_id
        ).eq('student_id', target_student_id).execute()
        if not enr.data:
            return error_response("Student is not enrolled in this class", 403)
        stu = db.table('students').select('id').eq('id', target_student_id).execute()
        if not stu.data:
            return error_response("Student record not found", 403)

    # 4) standard_code non-empty
    if not standard_code:
        return error_response("standard_code is required", 400)

    # Steps 5 + 6 land in Tasks 3 and 4 respectively. For now, return placeholder 200
    # so the validation tests pass. Generation lands later.
    return jsonify({
        "questions": [],
        "target_mode": target_mode,
        "target_student_ids": [target_student_id] if target_mode == 'single_student' else [],
        "standard_code": standard_code,
        "generated_at": "1970-01-01T00:00:00Z",
    }), 200
```

NOTE: at the top of `student_portal_routes.py` near the other imports, ensure `from backend.extensions import limiter` is present. If not, add it.

- [ ] **Step 2.4: Run validation tests — 8 of 10 should now pass**

```bash
pytest tests/test_remediation.py::TestRemediateValidation -v
```
Expected: 8 PASS, 2 FAIL — `test_single_student_no_historical_evidence_returns_400` and `test_red_tier_no_red_students_returns_400` still fail because steps 5/6 land in Tasks 3/4. Note: this is intentional — those two tests are duplicated as Task 3/4 entry assertions.

- [ ] **Step 2.5: Commit**

```bash
git add tests/test_remediation.py backend/routes/student_portal_routes.py
git commit -m "feat(remediate): route scaffold + auth/UUID/enrollment/standard validation"
```

---

### Task 3: Generation suite + happy-path generation

**Files:**
- Modify: `tests/test_remediation.py`
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 3.1: Append 5 generation tests**

Append to `tests/test_remediation.py`:

```python
# ============ Generation tests ============

class TestRemediateGeneration:
    """Single-student happy path; class-wide happy path; AI fallback paths."""

    def _ms(self, std='MA.6.AR.1.2', earned=4, possible=10):
        return {std: {'points_earned': earned, 'points_possible': possible, 'question_count': 2}}

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_single_student_happy_path(self, mock_sb_fn, mock_pp, client, teacher_headers):
        # 8 questions returned by the (mocked) post-processor.
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
                          'standard': 'MA.6.AR.1.2'} for i in range(1, 9)],
            'title': 'Remediation: MA.6.AR.1.2',
        }, {'total_tokens': 1500, 'prompt_tokens': 800, 'completion_tokens': 700})
        # Student has historical evidence on this standard at 40%.
        mastery = self._ms(earned=4, possible=10)
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1, 'student_name': 'Test Student'}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['questions']) == 8
        assert body['target_mode'] == 'single_student'
        assert body['target_student_ids'] == [STU_1]
        assert body['standard_code'] == 'MA.6.AR.1.2'
        # Post-processor was called once with prompt content.
        assert mock_pp.called

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_red_tier_happy_path(self, mock_sb_fn, mock_pp, client, teacher_headers):
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
                          'standard': 'MA.6.AR.1.2'} for i in range(1, 9)],
            'title': 'Remediation: MA.6.AR.1.2',
        }, {'total_tokens': 1500})
        # Two students: stu-1 red (40%), stu-2 green (90%).
        mastery_red = self._ms(earned=4, possible=10)
        mastery_green = self._ms(earned=9, possible=10)
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1},
                               {'class_id': 'cls-1', 'student_id': STU_2}],
            'students': [{'id': STU_1}, {'id': STU_2}],
            'student_submissions': [
                _sub('s-1', STU_1, CID_Q1, 40, mastery_red),
                _sub('s-2', STU_2, CID_Q1, 90, mastery_green),
            ],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['target_mode'] == 'red_tier_in_class'
        assert STU_1 in body['target_student_ids']
        assert STU_2 not in body['target_student_ids']

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_too_few_valid_questions_returns_422(self, mock_sb_fn, mock_pp, client, teacher_headers):
        # Post-processor returns only 2 valid questions — below the floor of 3.
        mock_pp.return_value = ({
            'questions': [{'id': 1, 'text': 'Q1', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'},
                          {'id': 2, 'text': 'Q2', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}],
        }, {'total_tokens': 800})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 422

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_grade_metadata_falls_back(self, mock_sb_fn, mock_pp, client, teacher_headers):
        # Class has no grade_level / subject — route should still generate.
        cls_no_meta = [{'id': 'cls-1', 'teacher_id': 'test-teacher-001', 'name': 'C',
                        'grade_level': None, 'subject': None}]
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                          for i in range(1, 9)],
        }, {'total_tokens': 1000})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': cls_no_meta,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_response_contains_generated_at_timestamp(self, mock_sb_fn, mock_pp, client, teacher_headers):
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                          for i in range(1, 9)],
        }, {'total_tokens': 1000})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        body = resp.get_json()
        assert 'generated_at' in body
        # ISO 8601 UTC.
        assert 'T' in body['generated_at'] and body['generated_at'].endswith('Z')
```

- [ ] **Step 3.2: Run tests — expect FAILs**

```bash
pytest tests/test_remediation.py::TestRemediateGeneration -v
```
Expected: 5 FAIL — placeholder route returns empty `questions` array.

- [ ] **Step 3.3: Replace placeholder with real generation logic**

In `backend/routes/student_portal_routes.py`, replace the `# Steps 5 + 6 land in...` placeholder block with:

```python
    # 5) Single-student historical evidence check.
    if target_mode == 'single_student':
        # Fetch student's submissions whose results contain this standard.
        subs = db.table('student_submissions').select(
            'id, percentage, results, status, submitted_at'
        ).eq('student_id', target_student_id).neq('status', 'draft').execute()
        has_evidence = False
        for s in (subs.data or []):
            mastery = (s.get('results') or {}).get('standards_mastery') or {}
            if isinstance(mastery, dict) and standard_code in mastery:
                has_evidence = True
                break
        if not has_evidence:
            _logger.warning(
                "remediation.no_historical_evidence teacher=%s class=%s student=%s standard=%s",
                g.teacher_id, class_id, target_student_id, standard_code,
            )
            return error_response(
                f"No prior assessment data on this standard for student",
                400,
            )
        target_student_ids = [target_student_id]

    # 6) Red-tier resolution (class-wide). Uses the same aggregation path that
    # Phase 2 Progress Rank uses, so the red-tier set matches the grid exactly.
    if target_mode == 'red_tier_in_class':
        # Resolve roster (skip orphans).
        enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
        enrolled_ids = [r['student_id'] for r in (enrollments.data or []) if r.get('student_id')]
        valid_ids = []
        if enrolled_ids:
            stu_rows = db.table('students').select('id').in_('id', enrolled_ids).execute()
            existing = {s['id'] for s in (stu_rows.data or []) if s.get('id')}
            valid_ids = [sid for sid in enrolled_ids if sid in existing]
        # Pull all class submissions covering this standard (any content row).
        red_tier = []
        if valid_ids:
            class_subs = db.table('student_submissions').select(
                'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
            ).in_('student_id', valid_ids).neq('status', 'draft').execute()
            # Build content title map for _aggregate_mastery_for_student.
            content_id_set = list({s.get('content_id') for s in (class_subs.data or [])
                                    if s.get('content_id')})
            content_titles = {}
            if content_id_set:
                rows = db.table('published_content').select('id, title').in_(
                    'id', content_id_set
                ).execute()
                content_titles = {r['id']: r.get('title', '') for r in (rows.data or [])}
            # Group submissions by student → content_id → [submissions].
            from collections import defaultdict
            per_student = defaultdict(lambda: defaultdict(list))
            for s in (class_subs.data or []):
                sid = s.get('student_id')
                cid = s.get('content_id')
                if sid and cid:
                    per_student[sid][cid].append(s)
            # For each student: select latest per content, aggregate mastery, read standard's percentage.
            for sid, by_cid in per_student.items():
                selected = _select_submissions_by_mode(by_cid, 'latest')
                mastery = _aggregate_mastery_for_student(selected, content_titles, 'latest')
                std_entry = mastery.get(standard_code) if isinstance(mastery, dict) else None
                if not std_entry:
                    continue
                pct = std_entry.get('percentage')
                if pct is None:
                    continue
                if pct < 70:
                    red_tier.append(sid)
        if not red_tier:
            _logger.warning(
                "remediation.no_red_tier_students teacher=%s class=%s standard=%s",
                g.teacher_id, class_id, standard_code,
            )
            return error_response("No red-tier students on this standard", 400)
        target_student_ids = red_tier

    # 7) Build remediation prompt.
    grade = cls_row.get('grade_level') or '7'
    subject = cls_row.get('subject') or 'General'
    base_prompt = (
        f"Generate exactly 8 grade-{grade} {subject} practice questions aligned to "
        f"standard {standard_code}. Mix: 5 multiple-choice questions (4 choices each, "
        f"exactly 1 correct, marked with an 'answer' field whose value is the choice "
        f"letter or text) and 3 short-answer questions (each with an 'answer' field "
        f"containing the model answer). Difficulty: grade-level review. Each question "
        f"MUST include a 'standard' field equal to '{standard_code}'. Return valid JSON "
        f"of shape: {{\"questions\": [...]}}"
    )

    accommodation_segment = ""
    if target_mode == 'single_student':
        try:
            from backend.accommodations import build_accommodation_prompt
            accommodation_segment = build_accommodation_prompt(target_student_id, g.teacher_id) or ""
        except Exception:
            _logger.warning(
                "remediation.accommodations_helper_failed teacher=%s student=%s",
                g.teacher_id, target_student_id,
            )
            accommodation_segment = ""
    final_prompt = base_prompt + ("\n\n" + accommodation_segment if accommodation_segment else "")

    # 8) Generate via the LLM adapter (matches planner_routes pattern at line 1878).
    try:
        from backend.services.llm_adapter import get_llm_adapter
        from backend.services.llm_types import LLMRequest, Message, TextPart, ResponseFormat
        from backend.routes.planner_routes import _get_openai_context, _extract_usage, _merge_usage
        from backend.services.assignment_post_processing import _post_process_assignment

        adapter = get_llm_adapter()
        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert teacher. Return valid JSON only.",
            messages=[Message(role="user", content=[TextPart(text=final_prompt)])],
            response_format=ResponseFormat(type="json_object"),
            metadata={"feature_label": "remediation"},
        ))
        raw_text = completion.content_parts[0].text if completion.content_parts else "{}"
        import json as _json
        assignment = _json.loads(raw_text)
        _ctx_uid, _ctx_client = _get_openai_context()
        assignment, extra_usage = _post_process_assignment(
            assignment, 8, target_total_points=80,
            subject=subject, grade=grade,
            valid_standard_codes=[standard_code],
            user_id=_ctx_uid, client=_ctx_client,
        )
        usage = _merge_usage(_extract_usage(completion, "gpt-4o"), extra_usage)
    except Exception:
        _logger.exception("remediation.generation_failed teacher=%s class=%s standard=%s",
                          g.teacher_id, class_id, standard_code)
        return error_response("Generation failed", 500)

    questions = (assignment or {}).get('questions') or []
    # 422 floor: fewer than 3 valid questions after post-processing.
    if len(questions) < 3:
        return error_response("Generation produced too few valid questions", 422)

    # 9) Audit log.
    if accommodation_segment:
        _logger.info(
            "remediation.accommodations_applied teacher=%s class=%s student=%s",
            g.teacher_id, class_id, target_student_id,
        )
    _logger.info(
        "remediation.generated teacher=%s class=%s mode=%s standard=%s targets=%d cost_tokens=%s",
        g.teacher_id, class_id, target_mode, standard_code, len(target_student_ids),
        (usage or {}).get('total_tokens', 0),
    )

    from datetime import datetime, timezone
    return jsonify({
        "questions": questions,
        "target_mode": target_mode,
        "target_student_ids": target_student_ids,
        "standard_code": standard_code,
        "generated_at": datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }), 200
```

**Imports note:** the inline imports inside the route are intentional (avoids a heavy module-level pull when the route is rarely hit). The signatures the route relies on:
- `get_llm_adapter()` returns the LLM adapter (Phase 5b infra).
- `LLMRequest(model, system_prompt, messages=[Message(role, content=[TextPart(text=...)])], response_format=ResponseFormat(type="json_object"), metadata={...})` per `backend/services/llm_types.py`.
- `_post_process_assignment(assignment_dict, target_question_count, target_total_points=N, subject=..., grade=..., valid_standard_codes=[...], user_id=..., client=...)` returns `(assignment, extra_usage)`.
- `_get_openai_context()`, `_extract_usage(completion, model)`, `_merge_usage(a, b)` — all exist in `backend/routes/planner_routes.py` (re-import locally rather than re-export).

If any of these signatures have shifted, the implementer reads the source file once at task start and adapts the call site accordingly. No silent guessing.

- [ ] **Step 3.4: Run all generation tests + validation**

```bash
pytest tests/test_remediation.py -v
```
Expected: 15 PASS (10 validation + 5 generation).

- [ ] **Step 3.5: Commit**

```bash
git add tests/test_remediation.py backend/routes/student_portal_routes.py
git commit -m "feat(remediate): historical evidence + red-tier resolution + generation"
```

---

### Task 4: Red-tier resolution edge cases

**Files:**
- Modify: `tests/test_remediation.py`

- [ ] **Step 4.1: Append 3 red-tier resolution tests**

Append to `tests/test_remediation.py`:

```python
# ============ Red-tier resolution tests ============

class TestRemediateRedTierResolution:
    """Edge cases for the red_tier_in_class resolver."""

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_excludes_students_with_no_submissions(self, mock_sb_fn, mock_pp, client, teacher_headers):
        # 3 enrolled students; only stu-1 has a submission (red).
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                          for i in range(1, 9)],
        }, {'total_tokens': 1000})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        STU_3 = 'stu-3333-3333-3333-3333-333333333333'
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [
                {'class_id': 'cls-1', 'student_id': STU_1},
                {'class_id': 'cls-1', 'student_id': STU_2},
                {'class_id': 'cls-1', 'student_id': STU_3},
            ],
            'students': [{'id': STU_1}, {'id': STU_2}, {'id': STU_3}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        body = resp.get_json()
        assert body['target_student_ids'] == [STU_1]

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_uses_latest_submission_per_student(self, mock_sb_fn, mock_pp, client, teacher_headers):
        # stu-1 has 2 submissions: older one was red (40%), latest is green (90%).
        # The latest must win — student NOT counted as red.
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                          for i in range(1, 9)],
        }, {'total_tokens': 1000})
        old_red = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        new_green = {'MA.6.AR.1.2': {'points_earned': 9, 'points_possible': 10, 'question_count': 2}}
        red_other = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1},
                               {'class_id': 'cls-1', 'student_id': STU_2}],
            'students': [{'id': STU_1}, {'id': STU_2}],
            'student_submissions': [
                _sub('s-1-old', STU_1, CID_Q1, 40, old_red, attempt=1, submitted_at='2026-04-01T10:00:00Z'),
                _sub('s-1-new', STU_1, CID_Q1, 90, new_green, attempt=2, submitted_at='2026-04-15T10:00:00Z'),
                _sub('s-2', STU_2, CID_Q1, 40, red_other),
            ],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        body = resp.get_json()
        assert STU_1 not in body['target_student_ids']  # latest is green
        assert STU_2 in body['target_student_ids']

    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_excludes_students_at_exactly_70_percent(self, mock_sb_fn, mock_pp, client, teacher_headers):
        # 70% is the lower bound of yellow — NOT red. Student excluded.
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                          for i in range(1, 9)],
        }, {'total_tokens': 1000})
        yellow = {'MA.6.AR.1.2': {'points_earned': 7, 'points_possible': 10, 'question_count': 2}}
        red = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1},
                               {'class_id': 'cls-1', 'student_id': STU_2}],
            'students': [{'id': STU_1}, {'id': STU_2}],
            'student_submissions': [
                _sub('s-1', STU_1, CID_Q1, 70, yellow),
                _sub('s-2', STU_2, CID_Q1, 40, red),
            ],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        body = resp.get_json()
        assert STU_1 not in body['target_student_ids']
        assert STU_2 in body['target_student_ids']
```

- [ ] **Step 4.2: Run tests**

```bash
pytest tests/test_remediation.py::TestRemediateRedTierResolution -v
```
Expected: 3 PASS (the resolution logic from Task 3 already handles these cases — these tests pin the behavior).

- [ ] **Step 4.3: Commit**

```bash
git add tests/test_remediation.py
git commit -m "test(remediate): red-tier resolution edge cases (latest wins, 70% excluded)"
```

---

### Task 5: Accommodations integration tests

**Files:**
- Modify: `tests/test_remediation.py`

- [ ] **Step 5.1: Append 3 accommodations tests**

Append to `tests/test_remediation.py`:

```python
# ============ Accommodations integration tests ============

class TestRemediateAccommodations:
    """Single-student path injects accommodation segment with try/except fall-through."""

    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_helper_success_appends_segment(self, mock_sb_fn, mock_pp, mock_helper,
                                             client, teacher_headers):
        mock_helper.return_value = "ACCOMMODATION INSTRUCTIONS: simplify vocabulary"
        captured_prompt = {}
        def _capture(prompt, config, **kwargs):
            captured_prompt['p'] = prompt
            return ({
                'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                              for i in range(1, 9)],
            }, {'total_tokens': 1000})
        mock_pp.side_effect = _capture
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        # Helper was called with the student's id and teacher id.
        mock_helper.assert_called_with(STU_1, 'test-teacher-001')
        # The segment was appended.
        assert 'ACCOMMODATION INSTRUCTIONS: simplify vocabulary' in captured_prompt['p']

    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_helper_raises_falls_back_to_grade_level(self, mock_sb_fn, mock_pp, mock_helper,
                                                       client, teacher_headers, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger='backend.routes.student_portal_routes')
        mock_helper.side_effect = RuntimeError("corrupt profile")
        captured_prompt = {}
        def _capture(prompt, config, **kwargs):
            captured_prompt['p'] = prompt
            return ({
                'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                              for i in range(1, 9)],
            }, {'total_tokens': 1000})
        mock_pp.side_effect = _capture
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        # Route still returns 200 — helper failure falls back to grade level.
        assert resp.status_code == 200
        # No accommodation segment appended.
        assert 'ACCOMMODATION' not in captured_prompt['p']
        # Warning logged.
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('accommodations_helper_failed' in r.getMessage() for r in warnings)

    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_segment_skips_audit_log(self, mock_sb_fn, mock_pp, mock_helper,
                                            client, teacher_headers, caplog):
        import logging
        caplog.set_level(logging.INFO, logger='backend.routes.student_portal_routes')
        mock_helper.return_value = ""  # No accommodations on file → empty string.
        mock_pp.return_value = ({
            'questions': [{'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                          for i in range(1, 9)],
        }, {'total_tokens': 1000})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        # No accommodations_applied audit event when segment is empty.
        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        assert not any('accommodations_applied' in r.getMessage() for r in infos)
```

- [ ] **Step 5.2: Run tests**

```bash
pytest tests/test_remediation.py::TestRemediateAccommodations -v
```
Expected: 3 PASS (logic landed in Task 3.3; these tests pin the behavior).

- [ ] **Step 5.3: Commit**

```bash
git add tests/test_remediation.py
git commit -m "test(remediate): accommodations helper success / failure / empty paths"
```

---

### Task 6: Visibility helper unit tests + helper definition

**Files:**
- Modify: `tests/test_remediation.py`
- Modify: `backend/routes/student_account_routes.py`

- [ ] **Step 6.1: Append 3 visibility helper tests**

Append to `tests/test_remediation.py`:

```python
# ============ Visibility helper unit tests ============

class TestContentVisibilityHelper:
    """Unit tests for _content_visible_to_student."""

    def test_class_wide_row_visible_to_enrolled_student(self):
        from backend.routes.student_account_routes import _content_visible_to_student
        db = _multi_table_sb({
            'published_content': [{'id': 'ct-1', 'class_id': 'cls-1', 'is_active': True,
                                   'target_student_ids': None}],
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
        })
        assert _content_visible_to_student(db, 'ct-1', STU_1, 'cls-1') is True

    def test_targeted_row_visible_to_listed_student(self):
        from backend.routes.student_account_routes import _content_visible_to_student
        db = _multi_table_sb({
            'published_content': [{'id': 'ct-1', 'class_id': 'cls-1', 'is_active': True,
                                   'target_student_ids': [STU_1]}],
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
        })
        assert _content_visible_to_student(db, 'ct-1', STU_1, 'cls-1') is True

    def test_targeted_row_invisible_to_non_listed_student(self):
        from backend.routes.student_account_routes import _content_visible_to_student
        db = _multi_table_sb({
            'published_content': [{'id': 'ct-1', 'class_id': 'cls-1', 'is_active': True,
                                   'target_student_ids': [STU_2]}],  # only STU_2 targeted
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1},
                               {'class_id': 'cls-1', 'student_id': STU_2}],
        })
        assert _content_visible_to_student(db, 'ct-1', STU_1, 'cls-1') is False
```

- [ ] **Step 6.2: Run tests — expect ImportError**

```bash
pytest tests/test_remediation.py::TestContentVisibilityHelper -v
```
Expected: 3 FAIL — `_content_visible_to_student` not defined.

- [ ] **Step 6.3: Define the helper in `student_account_routes.py`**

Edit `backend/routes/student_account_routes.py`. Find a good spot near the top of the module (after the imports, after `_validate_student_session`). Add:

```python
def _content_visible_to_student(db, content_id, student_id, class_id):
    """Phase 4: shared visibility check for student-facing endpoints.

    A student sees a published_content row iff:
    1. They're currently enrolled in published_content.class_id (re-checked, not session-cached).
    2. The row is is_active = true.
    3. target_student_ids IS NULL OR target_student_ids contains the student_id.

    Returns True iff all three hold; False otherwise.
    """
    # Enrollment fact (re-check, NOT session-cached).
    enr = db.table('class_students').select('student_id').eq(
        'class_id', class_id
    ).eq('student_id', student_id).execute()
    if not enr.data:
        _logger.debug("student.access.denied reason=not_enrolled student=%s class=%s",
                      student_id, class_id)
        return False
    # Content row.
    row = db.table('published_content').select(
        'id, class_id, is_active, target_student_ids'
    ).eq('id', content_id).eq('class_id', class_id).execute()
    if not row.data:
        return False
    item = row.data[0]
    if not item.get('is_active'):
        return False
    targets = item.get('target_student_ids')
    if targets is None:
        return True
    if isinstance(targets, list) and student_id in targets:
        return True
    _logger.debug("student.access.denied reason=not_targeted student=%s content=%s",
                  student_id, content_id)
    return False
```

- [ ] **Step 6.4: Run tests**

```bash
pytest tests/test_remediation.py::TestContentVisibilityHelper -v
```
Expected: 3 PASS.

- [ ] **Step 6.5: Commit**

```bash
git add tests/test_remediation.py backend/routes/student_account_routes.py
git commit -m "feat(remediate): _content_visible_to_student shared visibility helper"
```

---

### Task 7: Publish hardening tests + ownership/targeting checks

**Files:**
- Modify: `tests/test_remediation.py`
- Modify: `backend/routes/student_account_routes.py`

- [ ] **Step 7.1: Append 5 publish-hardening tests**

Append to `tests/test_remediation.py`:

```python
# ============ Publish-to-class hardening tests ============

class TestPublishToClassHardening:
    """Phase 4 closes a pre-existing gap: publish_to_class did not verify
    class ownership before insert. Targeting validation lands at the same time."""

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_without_ownership_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'teacher_id': 'OTHER'}],
        })
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Test',
        }, headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_non_enrolled_target_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Test',
            'target_student_ids': [STU_1, STU_2],  # STU_2 not enrolled
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_empty_target_array_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
        })
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Test',
            'target_student_ids': [],  # invalid
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_null_target_creates_class_wide_row(self, mock_sb_fn, client, teacher_headers):
        # NULL target_student_ids → existing class-wide behavior preserved.
        captured_insert = {}
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.side_effect = [
            MagicMock(data=[{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}]),
            MagicMock(data=[{'id': 'new-content-id'}]),
        ]
        def _insert(payload):
            captured_insert['payload'] = payload
            chain.execute.side_effect = [MagicMock(data=[{'id': 'new-content-id'}])]
            return chain
        chain.insert.side_effect = _insert
        sb = MagicMock()
        sb.table.return_value = chain
        mock_sb_fn.return_value = sb
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Test',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        # Insert payload should NOT contain target_student_ids OR have it as None.
        payload = captured_insert.get('payload', {})
        assert payload.get('target_student_ids') in (None, [])

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_valid_targets_inserts_with_targeting(self, mock_sb_fn, client, teacher_headers):
        captured_insert = {}
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.execute.side_effect = [
            MagicMock(data=[{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}]),  # class lookup
            MagicMock(data=[{'student_id': STU_1}]),  # class_students lookup for targets
            MagicMock(data=[{'id': STU_1}]),  # students existence lookup
            MagicMock(data=[{'id': 'new-content-id'}]),  # insert
        ]
        def _insert(payload):
            captured_insert['payload'] = payload
            return chain
        chain.insert.side_effect = _insert
        sb = MagicMock()
        sb.table.return_value = chain
        mock_sb_fn.return_value = sb
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Remediation',
            'target_student_ids': [STU_1],
        }, headers=teacher_headers)
        assert resp.status_code == 200
        assert captured_insert.get('payload', {}).get('target_student_ids') == [STU_1]
```

- [ ] **Step 7.2: Run tests — expect FAILs**

```bash
pytest tests/test_remediation.py::TestPublishToClassHardening -v
```
Expected: 5 FAIL — current `publish_to_class` doesn't verify ownership and accepts no `target_student_ids`.

- [ ] **Step 7.3: Harden `publish_to_class`**

In `backend/routes/student_account_routes.py`, find `def publish_to_class():` (around line 342). Replace its body with:

```python
def publish_to_class():
    """Publish an assessment or assignment to a class.

    Phase 4 hardening: verifies class ownership; supports target_student_ids
    for per-student visibility (None / omitted = class-wide). All explicit 4xx
    errors use error_response() per Phase 5d (RFC 7807).
    """
    teacher_id = g.teacher_id

    db = _get_teacher_supabase()
    data = request.json or {}
    class_id = data.get('class_id')
    content = data.get('content')
    content_type = data.get('content_type', 'assessment')
    title = data.get('title', 'Untitled')
    settings = data.get('settings', {})
    due_date = data.get('due_date')
    target_student_ids = data.get('target_student_ids')

    if not content:
        return error_response("No content provided", 400)
    ALLOWED_CONTENT_TYPES = ('assessment', 'assignment', 'study_guide', 'flashcards', 'slide_deck')
    if content_type not in ALLOWED_CONTENT_TYPES:
        return error_response(
            "content_type must be one of: " + ", ".join(ALLOWED_CONTENT_TYPES), 400
        )

    # Phase 4: class ownership check (closes pre-existing gap).
    cls = db.table('classes').select('id, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != teacher_id:
        return error_response("Not authorized for this class", 403)

    # Phase 4: target_student_ids validation.
    if target_student_ids is not None:
        if not isinstance(target_student_ids, list):
            return error_response("target_student_ids must be a list or null", 400)
        if len(target_student_ids) == 0:
            return error_response(
                "target_student_ids must be non-empty (use null for class-wide)", 400
            )
        import uuid as _uuid
        for sid in target_student_ids:
            try:
                _uuid.UUID(str(sid))
            except (ValueError, TypeError):
                return error_response("Invalid target_student_id UUID", 400)
        # Enrollment check.
        enr = db.table('class_students').select('student_id').eq(
            'class_id', class_id
        ).in_('student_id', target_student_ids).execute()
        enrolled = {r['student_id'] for r in (enr.data or [])}
        if any(sid not in enrolled for sid in target_student_ids):
            return error_response(
                "One or more target_student_ids are not enrolled in this class", 400
            )
        # Students existence check (orphan-resilience).
        stu_rows = db.table('students').select('id').in_(
            'id', target_student_ids
        ).execute()
        existing_students = {r['id'] for r in (stu_rows.data or [])}
        if any(sid not in existing_students for sid in target_student_ids):
            return error_response(
                "One or more target_student_ids do not match a student record", 400
            )

    join_code = _generate_class_code()

    if content_type == 'assessment':
        cat = settings.get('assessment_category', 'formative')
        if cat not in ('formative', 'summative'):
            settings['assessment_category'] = 'formative'
        else:
            settings['assessment_category'] = cat

    insert_payload = {
        'teacher_id': teacher_id,
        'class_id': class_id,
        'content_type': content_type,
        'title': title,
        'join_code': join_code,
        'content': content,
        'settings': settings,
        'is_active': True,
        'due_date': due_date,
        'target_student_ids': target_student_ids,  # None = class-wide
    }
    result = db.table('published_content').insert(insert_payload).execute()

    if not result.data:
        return error_response("Failed to publish", 500)

    host = request.host_url.rstrip('/')
    return jsonify({
        "success": True,
        "content_id": result.data[0]['id'],
        "join_code": join_code,
        "join_link": f"{host}/student?code={join_code}",
    })
```

- [ ] **Step 7.4: Run tests**

```bash
pytest tests/test_remediation.py::TestPublishToClassHardening -v
```
Expected: 5 PASS.

- [ ] **Step 7.5: Sibling regression check**

Verified before this step: zero existing backend tests post to `/api/publish-to-class`, so the hardening's backend-test impact is nil. The frontend has 1 production caller (`App.jsx:4667`) which uses positional args and won't be affected. Run the broader suite as a smoke:

```bash
pytest tests/test_student_account_coverage.py tests/test_student_resources.py -v 2>&1 | tail -20
```
Expected: all pass. (No tests directly hit publish_to_class, so this is just confirming nothing else regressed.)

- [ ] **Step 7.6: Run the full file**

```bash
pytest tests/test_remediation.py -v 2>&1 | tail -10
```
Expected: 29 PASS.

- [ ] **Step 7.7: Commit**

```bash
git add tests/test_remediation.py backend/routes/student_account_routes.py
git commit -m "feat(remediate): harden publish_to_class with ownership + target validation"
```

---

## Bundle 2 — Migration + visibility wiring (Tasks 8-11)

### Task 8: Migration + migration test

**Files:**
- Create: `backend/database/migration_2026_04_26_phase4_target_student_ids.sql`
- Create: `backend/database/rollback_2026_04_26_phase4_target_student_ids.sql`
- Create: `tests/test_migration_target_student_ids.py`

- [ ] **Step 8.1: Write the migration SQL**

Create `backend/database/migration_2026_04_26_phase4_target_student_ids.sql`:

```sql
-- Phase 4 — Quick-Click Remediation: target_student_ids column
-- Spec: docs/superpowers/specs/2026-04-26-phase4-quick-click-remediation-design.md
--
-- Adds JSONB column for per-student visibility on published_content rows.
-- NULL = class-wide (existing behavior preserved); non-empty array = visible
-- only to those students. Empty array [] is invalid and rejected by the route.
--
-- Safety: ADD COLUMN with no default is metadata-only on Postgres 11+
-- (no table rewrite). Pre-existing rows get NULL → existing class-wide
-- visibility unchanged. No GIN index in MVP (deferred until EXPLAIN justifies).

ALTER TABLE published_content
  ADD COLUMN IF NOT EXISTS target_student_ids JSONB NULL;
```

- [ ] **Step 8.2: Write the rollback SQL**

Create `backend/database/rollback_2026_04_26_phase4_target_student_ids.sql`:

```sql
-- Rollback for Phase 4 target_student_ids column.
-- Drops the column entirely. Any targeting metadata is lost; rows revert
-- to class-wide visibility (since the column no longer exists).

ALTER TABLE published_content
  DROP COLUMN IF EXISTS target_student_ids;
```

- [ ] **Step 8.3: Write the migration shape test**

Create `tests/test_migration_target_student_ids.py`:

```python
"""Verify the Phase 4 migration SQL has the expected shape."""
import os
import re


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(REPO_ROOT, 'backend', 'database',
                         'migration_2026_04_26_phase4_target_student_ids.sql')
ROLLBACK = os.path.join(REPO_ROOT, 'backend', 'database',
                        'rollback_2026_04_26_phase4_target_student_ids.sql')


def test_migration_adds_target_student_ids_jsonb_nullable():
    with open(MIGRATION) as f:
        sql = f.read()
    # Must add the column.
    assert re.search(r'ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+target_student_ids\s+JSONB',
                     sql, re.IGNORECASE)
    # Must NOT include NOT NULL (column is nullable for backwards compat).
    assert not re.search(r'target_student_ids\s+JSONB\s+NOT\s+NULL', sql, re.IGNORECASE)
    # No GIN index in MVP.
    assert 'CREATE INDEX' not in sql.upper() or 'GIN' not in sql.upper()


def test_rollback_drops_column():
    with open(ROLLBACK) as f:
        sql = f.read()
    assert re.search(r'DROP\s+COLUMN\s+IF\s+EXISTS\s+target_student_ids',
                     sql, re.IGNORECASE)
```

- [ ] **Step 8.4: Run the migration test**

```bash
pytest tests/test_migration_target_student_ids.py -v
```
Expected: 2 PASS.

- [ ] **Step 8.5: Commit**

```bash
git add backend/database/migration_2026_04_26_phase4_target_student_ids.sql \
        backend/database/rollback_2026_04_26_phase4_target_student_ids.sql \
        tests/test_migration_target_student_ids.py
git commit -m "feat(remediate): migration for target_student_ids JSONB column"
```

---

### Task 9: Apply visibility helper to 5 single-row endpoints

**Files:**
- Modify: `backend/routes/student_account_routes.py`
- Create: `tests/test_student_content_visibility.py`

- [ ] **Step 9.1: Write 5 deny-tests for the single-row endpoints**

Create `tests/test_student_content_visibility.py`:

```python
"""Phase 4: deny-tests for single-row student-facing endpoints when the
viewer is not in target_student_ids.

Each of: get_student_content, student_resource_content, submit_student_work,
save_submission_draft, get_submission_draft must return 404 (not the row's
content) when target_student_ids is set and the viewer is NOT in it.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app():
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def student_headers():
    return {'X-Student-Token': 'test-token-stu-1'}


def _session_chain(student_id, class_id):
    """Mock for the student_sessions lookup in _validate_student_session."""
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
    return [{'student_id': student_id, 'class_id': class_id, 'expires_at': expires}]


def _content_chain_targeted_to(other_student_id, content_id='ct-1', class_id='cls-1'):
    """A published_content row visible only to other_student_id."""
    return [{'id': content_id, 'class_id': class_id, 'is_active': True,
             'target_student_ids': [other_student_id], 'content': {'questions': []},
             'title': 'T', 'content_type': 'assessment', 'settings': {}}]


STU_VIEWER = '11111111-1111-1111-1111-111111111111'
STU_OTHER = '22222222-2222-2222-2222-222222222222'


@patch('backend.routes.student_account_routes._get_supabase')
def test_get_student_content_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    # Sequence: session lookup → enrollment recheck → content fetch.
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # enrolled
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/content/ct-1', headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_student_resource_content_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/resource/ct-1', headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_submit_student_work_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.insert.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.post('/api/student/submit/ct-1', json={'answers': {}}, headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_save_submission_draft_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.post('/api/student/submission/ct-1/draft', json={'answers': {}}, headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_get_submission_draft_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/submission/ct-1/draft', headers=student_headers)
    assert resp.status_code == 404
```

- [ ] **Step 9.2: Run tests — expect FAILs**

```bash
pytest tests/test_student_content_visibility.py -v
```
Expected: 5 FAIL — endpoints don't yet apply the visibility helper.

- [ ] **Step 9.3: Apply the visibility helper to all 5 single-row endpoints**

In `backend/routes/student_account_routes.py`, add the helper call at the top of each handler body (after `_validate_student_session` returns the session). Pattern:

```python
session = _validate_student_session()
if session is None:
    return jsonify({"error": "Not logged in"}), 401
student_id, class_id = session

# Phase 4: targeting visibility check.
db = _get_supabase()
if not _content_visible_to_student(db, content_id, student_id, class_id):
    return jsonify({"error": "Content not found"}), 404
```

Apply to (search by handler `def`):
- `get_student_content` (line ~703)
- `submit_student_work` (line ~761)
- `student_resource_content` (line ~1197)
- `save_submission_draft` (line ~1243)
- `get_submission_draft` (line ~1333)

NOTE: each of these already calls `_validate_student_session()` and creates a `db` reference. Add the visibility check BEFORE any other content read — so non-targeted students never see even the metadata. Replace the existing `published_content.select.eq('id', content_id)` lookup with one that trusts the visibility helper if convenient, but at minimum, run the helper first.

- [ ] **Step 9.4: Run tests**

```bash
pytest tests/test_student_content_visibility.py -v
```
Expected: 5 PASS.

- [ ] **Step 9.5: Sibling regression check**

```bash
pytest tests/test_student_account_coverage.py tests/test_student_resources.py -v 2>&1 | tail -20
```
Expected: all existing tests pass. If any fail because they didn't supply `target_student_ids = None` in their `published_content` fixture, add it (it's a no-op when None).

- [ ] **Step 9.6: Commit**

```bash
git add tests/test_student_content_visibility.py backend/routes/student_account_routes.py
git commit -m "feat(remediate): apply visibility helper to 5 single-row student endpoints"
```

---

### Task 10: List-filter for dashboard + resources

**Files:**
- Modify: `backend/routes/student_account_routes.py`
- Modify: `tests/test_student_account_coverage.py`
- Modify: `tests/test_student_resources.py`

- [ ] **Step 10.1: Add a list-filter test for `student_dashboard`**

Append to `tests/test_student_account_coverage.py` a new test:

```python
@patch('backend.routes.student_account_routes._get_supabase')
def test_student_dashboard_filters_target_student_ids(mock_sb, client, student_headers):
    """Phase 4: dashboard list excludes published_content rows targeting other students."""
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
    STU_ME = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    STU_OTHER = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
    rows_returned = []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    or_filter = {}
    def _or_clause(clause):
        or_filter['clause'] = clause
        return chain
    chain.or_ = MagicMock(side_effect=_or_clause)
    # 3 calls: session lookup, published_content list, student_submissions list.
    chain.execute.side_effect = [
        MagicMock(data=[{'student_id': STU_ME, 'class_id': 'cls-1', 'expires_at': expires}]),
        MagicMock(data=[
            {'id': 'ct-classwide', 'title': 'Class Quiz', 'content_type': 'assessment',
             'target_student_ids': None, 'settings': {}},
            {'id': 'ct-mine', 'title': 'For Me', 'content_type': 'assessment',
             'target_student_ids': [STU_ME], 'settings': {}},
        ]),  # NOTE: mock filter applies; we trust the .or_() syntax was used
        MagicMock(data=[]),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/dashboard', headers={'X-Student-Token': 'tok'})
    assert resp.status_code == 200
    # The route must have applied an .or_() filter for target_student_ids.
    assert 'target_student_ids' in or_filter.get('clause', '')
    assert 'is.null' in or_filter['clause']
```

- [ ] **Step 10.2: Add a list-filter test for `student_resources`**

Append to `tests/test_student_resources.py` a similar new test:

```python
@patch('backend.routes.student_account_routes._get_supabase')
def test_student_resources_filters_target_student_ids(mock_sb, client):
    """Phase 4: resource list excludes published_content targeting other students."""
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
    STU_ME = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    or_filter = {}
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    def _or_clause(clause):
        or_filter['clause'] = clause
        return chain
    chain.or_ = MagicMock(side_effect=_or_clause)
    chain.execute.side_effect = [
        MagicMock(data=[{'student_id': STU_ME, 'class_id': 'cls-1', 'expires_at': expires}]),
        MagicMock(data=[]),  # resources query result
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/resources', headers={'X-Student-Token': 'tok'})
    assert resp.status_code == 200
    assert 'target_student_ids' in or_filter.get('clause', '')
    assert 'is.null' in or_filter['clause']
```

- [ ] **Step 10.3: Run tests — expect FAILs**

```bash
pytest tests/test_student_account_coverage.py::test_student_dashboard_filters_target_student_ids tests/test_student_resources.py::test_student_resources_filters_target_student_ids -v
```
Expected: 2 FAIL — list endpoints don't apply `.or_()` yet.

- [ ] **Step 10.4: Apply `.or_()` filter to dashboard + resources queries**

In `backend/routes/student_account_routes.py`, find `student_dashboard` (line ~656). The existing `published_content.select.eq('class_id', class_id).eq('is_active', True).order(...)` chain. Insert a `.or_()` clause:

```python
        import json as _json
        targeting_filter = f'target_student_ids.is.null,target_student_ids.cs.{_json.dumps([student_id])}'
        content = db.table('published_content').select('*').eq(
            'class_id', class_id
        ).eq('is_active', True).or_(targeting_filter).order('created_at', desc=True).execute()
```

Then find `student_resources` (line ~1156) and apply the same `.or_()` insertion to its `published_content` list query.

- [ ] **Step 10.5: Run tests**

```bash
pytest tests/test_student_account_coverage.py::test_student_dashboard_filters_target_student_ids tests/test_student_resources.py::test_student_resources_filters_target_student_ids -v
```
Expected: 2 PASS.

- [ ] **Step 10.6: Sibling regression check**

```bash
pytest tests/test_student_account_coverage.py tests/test_student_resources.py -v 2>&1 | tail -20
```
Expected: all pre-existing tests still pass. If any fail with errors about `or_` being a MagicMock or returning unexpected data, the existing fixture's MagicMock chain needs `chain.or_.return_value = chain` added.

- [ ] **Step 10.7: Commit**

```bash
git add tests/test_student_account_coverage.py tests/test_student_resources.py backend/routes/student_account_routes.py
git commit -m "feat(remediate): list-filter target_student_ids on dashboard + resources"
```

---

### Task 11: `_validate_student_session` enrollment recheck

**Files:**
- Modify: `backend/routes/student_account_routes.py`
- Modify: `tests/test_student_content_visibility.py` (extend mock sequences from 3 → 4)

- [ ] **Step 11.1: Update Task 9's test mock sequences first (TDD: prove the test will exercise the new behavior)**

The existing 5 tests in `tests/test_student_content_visibility.py` mock 3 `.execute()` calls (session lookup, helper enrollment check, content fetch). After Task 11 lands, `_validate_student_session` itself does an enrollment recheck — adding a 4th call between the session lookup and the helper enrollment check.

In each of the 5 tests, change:
```python
chain.execute.side_effect = [
    MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
    MagicMock(data=[{'student_id': STU_VIEWER}]),  # enrolled
    MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
]
```
to:
```python
chain.execute.side_effect = [
    MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
    MagicMock(data=[{'student_id': STU_VIEWER}]),  # session enrollment recheck (Task 11)
    MagicMock(data=[{'student_id': STU_VIEWER}]),  # helper enrollment check
    MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
]
```

Apply this change to all 5 tests in the file.

- [ ] **Step 11.2: Run tests — expect FAILs (route does only 3 .execute() calls today; 4th mock is unused)**

```bash
pytest tests/test_student_content_visibility.py -v
```
Expected: 5 FAIL. The route currently does 3 calls; the test's 4th mock is unused, but the test's assertion still holds (404 returned). Wait — actually the test expected 404 still passes here since the helper still denies. Confirm: if all 5 still PASS even with 4-mock sequences, that's fine (the unused mock is a no-op). Whichever outcome — the test must continue to pass after Task 11.3.

- [ ] **Step 11.3: Add the enrollment recheck to `_validate_student_session`**

In `backend/routes/student_account_routes.py`, find `_validate_student_session()` (line ~102). After fetching the session and confirming it's not expired, ALSO confirm the student is still enrolled. Replace the function body's tail with:

```python
def _validate_student_session():
    """Validate student session token from X-Student-Token header.
    Returns (student_id, class_id) tuple or None if invalid.

    Phase 4: re-checks class_students enrollment so a student who has been
    removed from the class loses access immediately rather than at session
    expiry.
    """
    token = request.headers.get('X-Student-Token', '')
    if not token:
        return None

    db = _get_supabase()
    token_hash = _hash_token(token)
    result = db.table('student_sessions').select(
        'student_id, class_id, expires_at'
    ).eq('session_token', token_hash).execute()

    if not result.data:
        return None

    session = result.data[0]
    expires = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
    if expires < datetime.now(tz=timezone.utc):
        db.table('student_sessions').delete().eq('session_token', token_hash).execute()
        return None

    student_id = session['student_id']
    class_id = session['class_id']

    # Phase 4: re-check enrollment. A removed student loses access immediately.
    enr = db.table('class_students').select('student_id').eq(
        'class_id', class_id
    ).eq('student_id', student_id).execute()
    if not enr.data:
        _logger.debug("session.access.denied reason=not_enrolled student=%s class=%s",
                      student_id, class_id)
        return None

    return (student_id, class_id)
```

- [ ] **Step 11.4: Run all visibility + sibling tests**

```bash
pytest tests/test_student_account_coverage.py tests/test_student_resources.py tests/test_student_content_visibility.py tests/test_remediation.py -v 2>&1 | tail -10
```
Expected: all pass. The 5 visibility tests now consume their 4th mock (session enrollment recheck) before reaching the helper enrollment check.

If any existing tests outside the 5 fail because they don't mock the new `class_students` lookup that `_validate_student_session` now performs, add a `class_students` mock entry to their fixtures matching the test's `student_id` + `class_id`.

- [ ] **Step 11.5: Commit**

```bash
git add backend/routes/student_account_routes.py tests/test_student_content_visibility.py
git commit -m "feat(remediate): _validate_student_session re-checks enrollment"
```

---

## Bundle 3 — Frontend (Tasks 12-15)

### Task 12: API client extensions

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 12.1: Add `postRemediate` and extend `publishToClass` with a 7th positional param**

Verified before this step: `publishToClass` at `frontend/src/services/api.js:779` is positional — `publishToClass(classId, content, contentType, title, settings, dueDate)`. Single production caller at `frontend/src/App.jsx:4667` passes 6 positional args. One test mock at `frontend/src/__tests__/smoke.test.jsx:75` (`publishToClass: noopAsync`).

Adding a 7th optional positional `targetStudentIds` keeps existing callers working (they pass 6 args → 7th is `undefined` → JSON.stringify drops the field → backend treats as null = class-wide).

Edit `frontend/src/services/api.js`. Find the existing `publishToClass` and replace it with:

```javascript
export async function publishToClass(classId, content, contentType, title, settings, dueDate, targetStudentIds) {
  var body = {
    class_id: classId,
    content,
    content_type: contentType,
    title,
    settings,
    due_date: dueDate,
  };
  if (targetStudentIds != null) {
    body.target_student_ids = targetStudentIds;
  }
  return fetchApi('/api/publish-to-class', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
```

Then add `postRemediate` immediately after `publishToClass`:

```javascript
export async function postRemediate(classId, payload) {
  // payload: {standard_code, target_mode, target_student_id?}
  return fetchApi(
    '/api/teacher/class/' + encodeURIComponent(classId) + '/remediate',
    { method: 'POST', body: JSON.stringify(payload) }
  );
}
```

- [ ] **Step 12.2: Build verification**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 12.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/services/api.js
git commit -m "feat(remediate): API client postRemediate + publish target_student_ids"
```

---

### Task 13: RemediationDrawer.jsx component

**Files:**
- Create: `frontend/src/tabs/RemediationDrawer.jsx`

- [ ] **Step 13.1: Create the drawer component**

Create `frontend/src/tabs/RemediationDrawer.jsx`:

```javascript
import React, { useState, useEffect, useRef } from "react";
import * as api from "../services/api";

/**
 * Phase 4 — Remediation Drawer.
 *
 * State machine: idle → generating → preview → (regenerating | publishing) → success | error
 */
export default function RemediationDrawer({
  open, onClose, classId, standardCode, targetMode, targetStudentId, targetStudentName,
  onPublished,
}) {
  var [state, setState] = useState("idle");
  var [error, setError] = useState(null);
  var [data, setData] = useState(null);  // {questions, target_student_ids, ...}
  var [questions, setQuestions] = useState([]);
  var [confirmRegenOpen, setConfirmRegenOpen] = useState(false);
  var cancelRef = useRef({ cancelled: false });
  var successTimerRef = useRef(null);

  // Reset on open / close.
  useEffect(function() {
    if (!open) {
      cancelRef.current.cancelled = true;
      if (successTimerRef.current) { clearTimeout(successTimerRef.current); successTimerRef.current = null; }
      return;
    }
    cancelRef.current = { cancelled: false };
    setState("generating");
    setError(null);
    setData(null);
    setQuestions([]);
    var payload = { standard_code: standardCode, target_mode: targetMode };
    if (targetMode === "single_student") payload.target_student_id = targetStudentId;
    api.postRemediate(classId, payload)
      .then(function(res) {
        if (cancelRef.current.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Generation failed");
          setState("error");
          return;
        }
        setData(res);
        setQuestions(res.questions || []);
        setState("preview");
      })
      .catch(function(e) {
        if (cancelRef.current.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
    return function() { cancelRef.current.cancelled = true; };
  }, [open, classId, standardCode, targetMode, targetStudentId]);

  // Esc to close.
  useEffect(function() {
    if (!open) return;
    function handler(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", handler);
    return function() { document.removeEventListener("keydown", handler); };
  }, [open, onClose]);

  function regenerateAll() {
    setConfirmRegenOpen(false);
    setState("regenerating");
    var payload = { standard_code: standardCode, target_mode: targetMode };
    if (targetMode === "single_student") payload.target_student_id = targetStudentId;
    api.postRemediate(classId, payload)
      .then(function(res) {
        if (cancelRef.current.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Regeneration failed");
          setState("error");
          return;
        }
        setData(res);
        setQuestions(res.questions || []);
        setState("preview");
      })
      .catch(function(e) {
        if (cancelRef.current.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  // Pre-publish validation. Returns null on success, error string on failure.
  // Verifies: ≥1 question, every question has non-empty text, MC has ≥2
  // non-empty choices AND correct_answer references one of those choices.
  function validateBeforePublish() {
    if (questions.length < 1) return "At least one question required";
    for (var i = 0; i < questions.length; i++) {
      var q = questions[i];
      if (!q.text || !q.text.trim()) return "Question " + (i + 1) + " has no text";
      var t = (q.type || q.question_type || "").toLowerCase();
      if (t === "mcq" || t === "multiple_choice" || t === "mc") {
        var choices = q.choices || q.options || [];
        var nonEmptyChoices = [];
        for (var ci = 0; ci < choices.length; ci++) {
          var label = typeof choices[ci] === "string" ? choices[ci] : (choices[ci] && choices[ci].text);
          if (label && String(label).trim()) {
            nonEmptyChoices.push({ index: ci, label: String(label).trim() });
          }
        }
        if (nonEmptyChoices.length < 2) return "Question " + (i + 1) + " needs at least 2 choices";
        var correct = q.correct_answer != null ? q.correct_answer : q.answer;
        if (correct == null || correct === "") return "Question " + (i + 1) + " has no correct answer";
        // correct_answer may be a numeric index OR the choice text. Verify it
        // matches a non-empty choice either way.
        var matchesIndex = nonEmptyChoices.some(function(c) { return c.index === correct; });
        var matchesText = nonEmptyChoices.some(function(c) { return c.label === String(correct).trim(); });
        if (!matchesIndex && !matchesText) {
          return "Question " + (i + 1) + " correct answer doesn't match any choice";
        }
      }
    }
    return null;
  }

  // Validation error is shown inline in the preview state (not the error state).
  // Separate state slot so the drawer doesn't drop into the full-screen "error"
  // path (which is reserved for network/server errors).
  var [validationError, setValidationError] = useState(null);

  function publish() {
    var ve = validateBeforePublish();
    if (ve) { setValidationError(ve); return; }
    setValidationError(null);
    setState("publishing");
    api.publishToClass(
      classId,
      { questions: questions },
      "assessment",
      "Remediation: " + standardCode,
      {},  // settings — leave default
      null,  // dueDate — none
      data.target_student_ids,
    )
      .then(function(res) {
        if (cancelRef.current.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Publish failed");
          setState("error");
          return;
        }
        setState("success");
        if (onPublished) onPublished();
        successTimerRef.current = setTimeout(function() {
          if (!cancelRef.current.cancelled) onClose();
        }, 2000);
      })
      .catch(function(e) {
        if (cancelRef.current.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  if (!open) return null;

  var disabled = state === "generating" || state === "regenerating" || state === "publishing";
  var nTargets = data && data.target_student_ids ? data.target_student_ids.length : 0;
  var subtitle = "";
  if (targetMode === "single_student") {
    subtitle = "for " + (targetStudentName || "student");
  } else if (data && data.target_student_ids) {
    subtitle = "for " + nTargets + " red-tier student" + (nTargets === 1 ? "" : "s");
  }

  return (
    <>
      <div onClick={onClose}
           style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                    background: "rgba(0,0,0,0.4)", zIndex: 9499 }} />
      <div style={{
        position: "fixed", top: 0, right: 0, height: "100vh",
        width: "min(720px, 96vw)", background: "var(--card-bg)",
        zIndex: 9500, display: "flex", flexDirection: "column",
        boxShadow: "-4px 0 24px rgba(0,0,0,0.3)",
      }}>
        {/* Header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--glass-border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>Remediation: {standardCode}</h3>
              <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>{subtitle}</p>
            </div>
            <button onClick={onClose} disabled={disabled}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}>
              {String.fromCharCode(10005)}
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {state === "generating" || state === "regenerating" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
              {state === "regenerating" ? "Regenerating..." : "Generating 8 practice questions..."}
            </div>
          ) : state === "error" ? (
            <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>
              {error}
              <div style={{ marginTop: "16px" }}>
                <button onClick={regenerateAll} className="btn btn-primary">Retry</button>
              </div>
            </div>
          ) : state === "success" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--success)" }}>
              Published to {nTargets} student{nTargets === 1 ? "" : "s"}.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {validationError && (
                <div style={{
                  padding: "10px 14px", borderRadius: "6px",
                  background: "rgba(239,68,68,0.15)", color: "var(--danger)",
                  fontSize: "0.85rem", border: "1px solid var(--danger)",
                }}>
                  {validationError}
                </div>
              )}
              {questions.map(function(q, idx) {
                return (
                  <QuestionCard key={idx} index={idx} question={q} disabled={disabled}
                                onChange={function(updated) {
                                  var copy = questions.slice();
                                  copy[idx] = updated;
                                  setQuestions(copy);
                                }} />
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        {(state === "preview" || state === "publishing") && (
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--glass-border)",
                        display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            <button onClick={onClose} disabled={disabled} className="btn btn-secondary">Cancel</button>
            <button onClick={function() { setConfirmRegenOpen(true); }} disabled={disabled} className="btn btn-secondary">
              Regenerate all
            </button>
            <button onClick={publish} disabled={disabled} className="btn btn-primary">
              {state === "publishing" ? "Publishing..." : "Publish to " + nTargets}
            </button>
          </div>
        )}

        {/* Confirm regenerate dialog */}
        {confirmRegenOpen && (
          <div onClick={function() { setConfirmRegenOpen(false); }}
               style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                        zIndex: 9501, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div onClick={function(e) { e.stopPropagation(); }} className="glass-card"
                 style={{ padding: "20px", maxWidth: "400px" }}>
              <h4 style={{ marginTop: 0 }}>Regenerate all questions?</h4>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Any edits you've made will be lost.</p>
              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                <button onClick={function() { setConfirmRegenOpen(false); }} className="btn btn-secondary">Keep editing</button>
                <button onClick={regenerateAll} className="btn btn-primary">Regenerate</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function QuestionCard({ index, question, disabled, onChange }) {
  var t = (question.type || question.question_type || "").toLowerCase();
  var isMC = t === "mcq" || t === "multiple_choice" || t === "mc";
  function setText(v) { onChange(Object.assign({}, question, { text: v })); }
  function setChoice(i, v) {
    var choices = (question.choices || question.options || []).slice();
    if (typeof choices[i] === "string") choices[i] = v;
    else choices[i] = Object.assign({}, choices[i], { text: v });
    onChange(Object.assign({}, question, { choices: choices }));
  }
  function setCorrect(v) { onChange(Object.assign({}, question, { correct_answer: v })); }
  return (
    <div style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
        <strong style={{ fontSize: "0.85rem" }}>Q{index + 1}</strong>
        <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>{isMC ? "MC" : "SA"}</span>
      </div>
      <textarea value={question.text || ""} disabled={disabled}
                onChange={function(e) { setText(e.target.value); }}
                style={{ width: "100%", minHeight: "60px", padding: "6px",
                         border: "1px solid var(--glass-border)", borderRadius: "4px", fontSize: "0.85rem" }} />
      {isMC && (question.choices || question.options || []).map(function(c, ci) {
        var label = typeof c === "string" ? c : (c.text || "");
        return (
          <div key={ci} style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
            <input type="radio" name={"correct-" + index} disabled={disabled}
                   checked={question.correct_answer === ci || question.correct_answer === label}
                   onChange={function() { setCorrect(ci); }} />
            <input type="text" value={label} disabled={disabled}
                   onChange={function(e) { setChoice(ci, e.target.value); }}
                   style={{ flex: 1, padding: "4px", border: "1px solid var(--glass-border)",
                            borderRadius: "4px", fontSize: "0.8rem" }} />
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 13.2: Build verification**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 13.3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/RemediationDrawer.jsx
git commit -m "feat(remediate): RemediationDrawer with state machine + slim editor + pre-publish validation"
```

---

### Task 14: ProgressRankGrid triggers

**Files:**
- Modify: `frontend/src/tabs/ProgressRankGrid.jsx`

- [ ] **Step 14.1: Add the import + state hook**

Edit `frontend/src/tabs/ProgressRankGrid.jsx`. After the existing imports near the top, add:

```javascript
import RemediationDrawer from "./RemediationDrawer";
```

Inside the component near the existing `var [selectedCell, setSelectedCell] = useState(null);` line, add:

```javascript
  var [remediationTrigger, setRemediationTrigger] = useState(null);
  // shape: {standardCode, targetMode, targetStudentId?, targetStudentName?}
```

- [ ] **Step 14.2: Add the cell-click button in the popover**

Find the existing popover JSX (the `{selectedCell && (...)}` block, around line 192). Inside the inner glass-card, AFTER the contributing-submissions list `</div>` (line ~234), add:

```jsx
            {selectedCell.mastery && selectedCell.mastery.percentage < 85 && (
              <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid var(--glass-border)" }}>
                <button
                  onClick={function() {
                    setRemediationTrigger({
                      standardCode: selectedCell.standard,
                      targetMode: "single_student",
                      targetStudentId: selectedCell.student.student_id,
                      targetStudentName: selectedCell.student.student_name,
                    });
                    setSelectedCell(null);
                  }}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "8px", fontSize: "0.85rem" }}
                >
                  Generate remediation
                </button>
              </div>
            )}
```

- [ ] **Step 14.3: Add column-header hover-reveal trigger**

Find the column header rendering (the `{standards.map(function(code) { return (<th key={code} ...`)} block, around line 140). Compute red counts per column once and store in a constant before the table. Replace the `<th>` with one that has hover-reveal:

```javascript
              {/* Compute red counts per column once. */}
              {(function() {
                var redCounts = {};
                standards.forEach(function(code) {
                  redCounts[code] = displayStudents.filter(function(stu) {
                    var m = stu.mastery[code];
                    return m && typeof m.percentage === "number" && m.percentage < 70;
                  }).length;
                });
                return standards.map(function(code) {
                  var redCount = redCounts[code];
                  return (
                    <th key={code}
                        style={{ padding: "10px 8px", fontSize: "0.7rem", fontFamily: "monospace",
                                 fontWeight: 700, borderBottom: "1px solid var(--glass-border)",
                                 borderLeft: "1px solid var(--glass-border)", minWidth: "90px",
                                 textAlign: "center", position: "relative" }}
                        className="phase4-header-cell">
                      {code}
                      {redCount > 0 && (
                        <button
                          onClick={function() {
                            setRemediationTrigger({
                              standardCode: code,
                              targetMode: "red_tier_in_class",
                            });
                          }}
                          className="phase4-header-remediate"
                          tabIndex={0}
                          aria-label={"Remediate " + redCount + " red-tier students on " + code}
                          style={{
                            position: "absolute", top: "2px", right: "2px",
                            background: "rgba(239,68,68,0.15)", color: "var(--danger)",
                            border: "none", borderRadius: "4px", fontSize: "0.65rem",
                            padding: "2px 6px", cursor: "pointer", opacity: 0,
                            transition: "opacity 0.15s",
                          }}
                        >
                          Remediate ({redCount})
                        </button>
                      )}
                    </th>
                  );
                });
              })()}
```

Add the hover-reveal CSS at the bottom of the file's existing CSS or in a `<style>` block in the component:

```jsx
      <style>{`
        .phase4-header-cell:hover .phase4-header-remediate,
        .phase4-header-cell:focus-within .phase4-header-remediate {
          opacity: 1 !important;
        }
        .phase4-header-remediate:focus { opacity: 1 !important; outline: 2px solid var(--accent-primary); }
      `}</style>
```

- [ ] **Step 14.4: Render the drawer**

Near the bottom of the component's JSX (just before the closing fragment / outer div), add:

```jsx
      {remediationTrigger && (
        <RemediationDrawer
          open={!!remediationTrigger}
          onClose={function() { setRemediationTrigger(null); }}
          classId={classId}
          standardCode={remediationTrigger.standardCode}
          targetMode={remediationTrigger.targetMode}
          targetStudentId={remediationTrigger.targetStudentId}
          targetStudentName={remediationTrigger.targetStudentName}
          onPublished={function() { if (typeof refresh === "function") refresh(); }}
        />
      )}
```

If the existing `ProgressRankGrid` doesn't expose a `refresh` callback to its parent, just omit `onPublished` (the parent re-fetches when the user navigates away and back).

- [ ] **Step 14.5: Build verification**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: green.

- [ ] **Step 14.6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/tabs/ProgressRankGrid.jsx
git commit -m "feat(remediate): cell-click + column-header hover-reveal triggers in ProgressRankGrid"
```

---

### Task 15: Manual smoke checklist

**Files:** none modified.

- [ ] **Step 15.1: Start backend**

```bash
source venv/bin/activate
python -m backend.app
```

- [ ] **Step 15.2: Build frontend**

```bash
cd frontend && npm run build
```

- [ ] **Step 15.3: Open dashboard at `http://localhost:3000` and walk the click paths**

Sign in as a teacher with at least one class containing 3+ students who have submissions covering ≥2 standards with mastery split across red/yellow/green.

1. Analytics → pick the class → Progress Rank sub-tab.
2. Click a **red cell** → popover opens → "Generate remediation" button visible.
3. Click "Generate remediation" → popover closes, drawer opens, generating spinner.
4. After ~10-20 sec, drawer transitions to preview state with 8 question cards.
5. Edit Q1's text → text updates in local state.
6. Edit a Q2 MC choice → text updates.
7. Click "Regenerate all" → confirm dialog → click "Regenerate" → drawer enters regenerating state → returns with new questions, edits gone.
8. Click "Publish to 1" → drawer enters publishing → success state → toast "Published to 1 student" → drawer closes after 2s.
9. Click a **yellow cell** → popover opens → "Generate remediation" button still visible (mastery <85).
10. Click a **green cell** → popover opens → "Generate remediation" button hidden (mastery ≥85).
11. Hover over a column header that has red students → "Remediate (N)" button reveals.
12. Click the column "Remediate (N)" button → drawer opens for class-wide red-tier path.
13. Drawer shows "for N red-tier students" subtitle.
14. Edit a question, click Publish → drawer publishes, closes after 2s.
15. Hover over a column header with NO red students → "Remediate" button NOT shown.
16. Press Esc while drawer is open → drawer closes.
17. Switch to Gradebook sub-tab while drawer is open → drawer unmounts cleanly (no z-index ghost).

- [ ] **Step 15.4: If any failure, fix + commit**

Each fix gets its own commit (`fix(remediate): <what>`).

---

### Task 16: Push branch

**Files:** none modified.

- [ ] **Step 16.1: Push**

```bash
git push -u origin phase4/quick-click-remediation
```

The controller (subagent-driven-development) opens the PR after the Codex full-PR cross-check.

---

## Sequencing + dependencies

**Single PR, sequential bundles:**
- Bundle 1 (Tasks 1-7): backend route + tests. 29 backend tests by end.
- Bundle 2 (Tasks 8-11): migration + visibility helper + publish hardening. +8 sibling tests + 1 migration test.
- Bundle 3 (Tasks 12-15): frontend triggers + drawer + smoke.
- Bundle 4 (Task 16): push.

Tasks within a bundle are sequential. Bundles 1+2 can technically interleave (route doesn't strictly need the migration to exist for the validation tests to pass since the tests mock the DB layer), but ship them as written for review clarity.

---

## Testing strategy

**Backend** (37 tests total):
- 29 in new `tests/test_remediation.py` (10 validation + 5 generation + 3 accommodations + 3 red-tier + 3 visibility helper + 5 publish hardening).
- 5 in new `tests/test_student_content_visibility.py` (deny tests for 5 single-row endpoints).
- 1 in `tests/test_student_account_coverage.py` (dashboard list-filter).
- 1 in `tests/test_student_resources.py` (resources list-filter).
- 1 in new `tests/test_migration_target_student_ids.py` (migration shape).

**Frontend:** build verification only. Manual smoke checklist (Task 15) covers ~17 click paths.

**Sibling regression** (must continue passing): `tests/test_gradebook.py`, `tests/test_submission_detail.py`, `tests/test_student_report_card.py`, `tests/test_assessment_comparison.py`, all Clever / ClassLink / OneRoster / LTI suites.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| Validation order (6 steps) | Task 2 + 3 |
| Class ownership 403 | Task 2.3 |
| `target_mode` literal validation | Task 2.3 |
| Single-student UUID + enrollment | Task 2.3 |
| Standard non-empty | Task 2.3 |
| Historical evidence (single) | Task 3.3 |
| Red-tier resolution (class-wide) | Task 3.3 + Task 4 |
| Generation with `_post_process_assignment` | Task 3.3 |
| Accommodations try/except fall-through | Task 3.3 + Task 5 |
| 422 floor: <3 valid questions | Task 3.3 |
| Rate limit `@limiter.limit("10 per minute")` | Task 2.3 |
| 4 structured log events | Task 3.3 (generated, no_red_tier, no_historical, accommodations_applied) + Task 5 (helper_failed) |
| Schema migration (one column, no GIN) | Task 8 |
| Shared visibility helper | Task 6 |
| Helper applied to 5 single-row endpoints | Task 9 |
| List-filter on dashboard + resources | Task 10 |
| `_validate_student_session` enrollment recheck | Task 11 |
| `publish_to_class` ownership + targeting | Task 7 |
| Frontend: cell-click trigger (disabled at ≥85) | Task 14.2 |
| Frontend: column-header hover-reveal (hidden if no red) | Task 14.3 |
| Frontend: RemediationDrawer state machine | Task 13 |
| Frontend: pre-publish validation | Task 13 (`validateBeforePublish`) |
| Frontend: async cleanup (cancellation, timer) | Task 13 (cancelRef + successTimerRef) |
| Frontend: slim local editor (no QuestionEditor reuse) | Task 13 (QuestionCard) |
| Frontend: drawer chrome (z-index 9500, Esc, slide-in) | Task 13 |
| Frontend: wire contract (target_student_ids round-trips) | Task 13 (`publish` uses `data.target_student_ids`) |
| Manual smoke (~15 click paths) | Task 15 |

**2. Placeholder scan:** No TBD/TODO/FIXME markers. Each step has either complete code blocks or precise modify-this-existing-block instructions with the actual code shown.

**3. Type consistency:**
- Route URL `/api/teacher/class/<class_id>/remediate` consistent across handler, tests, and frontend client.
- Response fields `questions, target_mode, target_student_ids, standard_code, generated_at` consistent across spec, route, drawer, and tests.
- `_content_visible_to_student(db, content_id, student_id, class_id) -> bool` — signature matches spec, used identically in helper definition (Task 6.3) and call sites (Task 9.3).
- `target_student_ids` semantics: `None` (class-wide), non-empty list (subset), `[]` rejected — consistent across migration, route, publish_to_class, and helper.

**4. Edge cases tested:**
- Auth: 401 unauth, 403 wrong teacher, 403 cross-class injection, 403 student not in class.
- Validation: bogus target_mode, missing student id, malformed UUID, empty standard.
- Historical evidence: zero submissions for that standard.
- Red-tier: zero red students, students with no submissions excluded, latest submission wins (not aggregated), exactly-70% excluded.
- Accommodations: helper success, helper raises, empty segment.
- Publish hardening: ownership, non-enrolled target, empty array, NULL = class-wide, valid targets.
- Visibility helper: class-wide visible, targeted visible to listed, targeted invisible to non-listed.

**5. Known limitations (deferred to Phase 4.2 backlog):**
- Lesson-text remediation (mini-lesson + practice).
- Per-student class-wide generation (N AI calls).
- Pre-generation config dialog.
- Recall / "undelete" UX.
- Remediation audit trail / "did it work" dashboard.
- Per-question regenerate (full-batch only).
- Remediation badge in Gradebook.

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-26-phase4-quick-click-remediation.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task bundle, two-stage review (spec compliance + code quality) between bundles, Codex full-PR cross-check before merge. Same workflow as Phase 2b / 3a / 3b.

**2. Inline Execution** — execute tasks here in this session via executing-plans, batched with checkpoints.

**Which approach?**
