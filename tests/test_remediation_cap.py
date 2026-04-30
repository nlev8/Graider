"""Tests for Phase 4.2 #8 — per-student weekly remediation cap.

Spec: docs/superpowers/specs/2026-04-30-phase4.2-weekly-cap-design.md

Cap: 3 publish events per (teacher × student) per rolling 7-day window.
Counting basis includes recalled rows. Enforced at /remediate AND
/publish-to-class.
"""
import os
import sys
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Fixtures ============

@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    from backend.extensions import limiter
    flask_app.config['TESTING'] = True
    flask_app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher_headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def _make_chain(execute_data=None):
    """Filter-aware Supabase mock: applies .eq() / .in_() / .neq() / .gte()."""
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
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

    def _gte(field, value):
        filters.append(('gte', field, value))
        return chain
    chain.gte.side_effect = _gte

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
            elif op == 'in':
                result = [r for r in result if r.get(field) in value]
            elif op == 'neq':
                result = [r for r in result if r.get(field) != value]
            elif op == 'gte':
                result = [r for r in result if (r.get(field) or '') >= value]
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


# ============ Test data ============

TEACHER = 'test-teacher-001'
STU_1 = '11111111-aaaa-aaaa-aaaa-111111111111'
STU_2 = '22222222-bbbb-bbbb-bbbb-222222222222'
STU_3 = '33333333-cccc-cccc-cccc-333333333333'
CLS_OWNED = [{'id': 'cls-1', 'name': 'P3', 'teacher_id': TEACHER,
              'grade_level': '6', 'subject': 'Math'}]
CID_Q1 = '99999999-1111-1111-1111-111111111111'


def _rem_row(rid, target_ids, teacher_id=TEACHER, age_days=1, is_active=True):
    """Build a published_content remediation row inside the 7-day window
    (age_days < 7) by default."""
    created_at = (datetime.now(tz=timezone.utc) - timedelta(days=age_days)).isoformat()
    return {
        'id': rid,
        'teacher_id': teacher_id,
        'target_student_ids': target_ids,
        'is_active': is_active,
        'created_at': created_at,
    }


# ============ Helper unit tests ============

class TestCapCountingHelper:
    """_check_remediation_cap helper: pure function over fetched rows."""

    def test_empty_target_list_returns_empty(self):
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': []})
        assert _check_remediation_cap(sb, TEACHER, []) == []

    def test_below_cap_returns_empty(self):
        """Two prior remediations for STU_1 in the window → 3rd publish is fine."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            _rem_row('r1', [STU_1], age_days=1),
            _rem_row('r2', [STU_1], age_days=2),
        ]})
        assert _check_remediation_cap(sb, TEACHER, [STU_1]) == []

    def test_at_cap_returns_capped_id(self):
        """Three prior remediations for STU_1 in the window → 4th would exceed."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            _rem_row('r1', [STU_1], age_days=1),
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ]})
        assert _check_remediation_cap(sb, TEACHER, [STU_1]) == [STU_1]

    def test_recalled_rows_count(self):
        """Per spec: recall (is_active=False) does NOT refund the slot.
        3 publishes including 1 recalled = STILL at cap."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            _rem_row('r1', [STU_1], age_days=1, is_active=False),  # recalled
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ]})
        assert _check_remediation_cap(sb, TEACHER, [STU_1]) == [STU_1]

    def test_class_wide_remediation_counts_against_each_student(self):
        """A single class-wide remediation with target_student_ids=[s1, s2, s3]
        counts +1 against EACH targeted student. Three such publishes = each
        student is at cap."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            _rem_row('rw1', [STU_1, STU_2, STU_3], age_days=1),
            _rem_row('rw2', [STU_1, STU_2, STU_3], age_days=2),
            _rem_row('rw3', [STU_1, STU_2, STU_3], age_days=3),
        ]})
        result = _check_remediation_cap(sb, TEACHER, [STU_1, STU_2, STU_3])
        assert sorted(result) == sorted([STU_1, STU_2, STU_3])

    def test_other_teachers_remediations_dont_count(self):
        """Cross-teacher: another teacher's remediations on STU_1 don't
        count against THIS teacher's cap. .eq('teacher_id', ...) filter."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            _rem_row('r1', [STU_1], teacher_id='OTHER-TEACHER', age_days=1),
            _rem_row('r2', [STU_1], teacher_id='OTHER-TEACHER', age_days=2),
            _rem_row('r3', [STU_1], teacher_id='OTHER-TEACHER', age_days=3),
        ]})
        assert _check_remediation_cap(sb, TEACHER, [STU_1]) == []

    def test_old_rows_outside_window_dont_count(self):
        """A remediation 8 days old is outside the rolling 7-day window."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            _rem_row('r1', [STU_1], age_days=8),  # outside window
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ]})
        # The .gte('created_at', cutoff) filter excludes the 8-day-old row.
        # Only 2 within window → not at cap.
        assert _check_remediation_cap(sb, TEACHER, [STU_1]) == []

    def test_malformed_target_student_ids_skipped(self):
        """A row with target_student_ids as a string (not a list) is
        skipped (with a warning log) rather than crashing."""
        from backend.routes.student_portal_routes import _check_remediation_cap
        sb = _multi_table_sb({'published_content': [
            {'id': 'rmal', 'teacher_id': TEACHER, 'target_student_ids': 'not-a-list',
             'created_at': (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()},
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ]})
        # Malformed row skipped → only 2 valid rows for STU_1 → not at cap.
        assert _check_remediation_cap(sb, TEACHER, [STU_1]) == []


# ============ /remediate route enforcement ============

def _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key):
    mock_get_api_key.return_value = "sk-test-fake"
    mock_adapter = MagicMock()
    mock_completion = MagicMock()
    mock_completion.usage = None
    text_part = MagicMock()
    text_part.text = '{"title":"P","sections":[{"name":"P","questions":[]}]}'
    mock_completion.content_parts = [text_part]
    mock_adapter.chat.return_value = mock_completion
    mock_adapter_cls.return_value = mock_adapter
    return mock_adapter


def _student_with_evidence_supabase(prior_rems=None):
    """Build supabase mock with: owned class, enrolled student with historical
    evidence on the standard, plus optional prior remediation rows for the
    cap check to find.
    """
    prior_rems = prior_rems or []
    mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
    sub = {
        'id': 's-1', 'student_id': STU_1, 'content_id': CID_Q1,
        'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
        'percentage': 40,
        'results': {'standards_mastery': mastery, 'score': 4, 'total_points': 10},
        'status': 'graded',
    }
    base_content = [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                     'content_type': 'assessment'}]
    return _multi_table_sb({
        'classes': CLS_OWNED,
        'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
        'students': [{'id': STU_1}],
        'student_submissions': [sub],
        'published_content': base_content + prior_rems,
    })


class TestRemediateRouteCap:
    """Cap enforcement on POST /api/teacher/class/<id>/remediate."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_below_cap_publishes_normally(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """2 prior remediations for STU_1 → /remediate succeeds (200)."""
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
        mock_sb_fn.return_value = _student_with_evidence_supabase(prior_rems=[
            _rem_row('r1', [STU_1], age_days=1),
            _rem_row('r2', [STU_1], age_days=2),
        ])
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_at_cap_returns_422(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """3 prior remediations for STU_1 → /remediate returns 422 BEFORE
        the LLM call (no AI mocks needed; cap check happens first)."""
        mock_sb_fn.return_value = _student_with_evidence_supabase(prior_rems=[
            _rem_row('r1', [STU_1], age_days=1),
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ])
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 422
        body = resp.get_json()
        assert body.get('error') == 'Weekly remediation cap reached'
        assert body.get('capped_student_ids') == [STU_1]
        assert body.get('cap') == 3
        assert body.get('window_days') == 7

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_recalled_rows_count_toward_cap_at_remediate(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Spec: recall (is_active=False) does NOT free a slot."""
        mock_sb_fn.return_value = _student_with_evidence_supabase(prior_rems=[
            _rem_row('r1', [STU_1], age_days=1, is_active=False),  # recalled
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ])
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 422, (
            "Recalled remediation row must count toward cap (recall is "
            "audit/visibility, not slot refund)"
        )


# ============ /publish-to-class route enforcement ============

class TestPublishToClassRouteCap:
    """Defense-in-depth cap at /publish-to-class write path. Catches the
    direct-API-bypass case (Codex CRITICAL finding)."""

    @patch('backend.routes.student_account_routes._generate_class_code')
    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_targeted_publish_at_cap_returns_422(
        self, mock_sb_fn, mock_gen_code, client, teacher_headers,
    ):
        """Direct call to /publish-to-class with target_student_ids triggers
        the cap check. _generate_class_code is patched (calls _get_supabase
        which would hit a real client without env credentials)."""
        mock_gen_code.return_value = 'TEST07'
        prior = [
            _rem_row('r1', [STU_1], age_days=1),
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'published_content': prior,
        })
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1',
            'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment',
            'title': 'Bypass attempt',
            'target_student_ids': [STU_1],
        }, headers=teacher_headers)
        assert resp.status_code == 422
        body = resp.get_json()
        assert body.get('error') == 'Weekly remediation cap reached'
        assert body.get('capped_student_ids') == [STU_1]

    @patch('backend.routes.student_account_routes._generate_class_code')
    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_class_wide_publish_not_affected_by_cap(
        self, mock_sb_fn, mock_gen_code, client, teacher_headers,
    ):
        """target_student_ids=None (class-wide non-remediation publish) is
        NOT subject to the per-student cap. Even if STU_1 is at cap from
        prior single-student remediations, a class-wide assessment still
        publishes."""
        mock_gen_code.return_value = 'TEST08'
        prior = [
            _rem_row('r1', [STU_1], age_days=1),
            _rem_row('r2', [STU_1], age_days=2),
            _rem_row('r3', [STU_1], age_days=3),
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': prior + [{'id': 'new-content-id'}],
        })
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1',
            'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment',
            'title': 'Class-wide quiz',
            # No target_student_ids → class-wide
        }, headers=teacher_headers)
        assert resp.status_code == 200, (
            "Class-wide publish (target_student_ids=None) must NOT be "
            "subject to the per-student cap"
        )
