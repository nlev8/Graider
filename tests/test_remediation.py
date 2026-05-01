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
    from backend.extensions import limiter
    flask_app.config['TESTING'] = True
    flask_app.config['RATELIMIT_ENABLED'] = False
    # The global limiter is already initialized at module-import time, so
    # toggling config alone is too late. Mutate the runtime flag directly --
    # flask_limiter checks self.enabled at request time (see _extension.py:872).
    limiter.enabled = False
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
    isolated.config['RATELIMIT_ENABLED'] = False
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
# NOTE: The plan-source listed STU_1/STU_2 values like 'stu-1111-...' which
# are NOT valid UUIDs (uuid.UUID() rejects them). The route's step-3 UUID
# validation would short-circuit every test that passes STU_1 as a target,
# returning 400 instead of the intended 403 (or other downstream codes).
# Using all-digit UUIDs preserves the spirit (distinguishable, debug-readable)
# while satisfying uuid.UUID(). Verified before applying to fixtures.
STU_1 = '11111111-aaaa-aaaa-aaaa-111111111111'
STU_2 = '22222222-bbbb-bbbb-bbbb-222222222222'


def _sub(sub_id, student_id, content_id, percentage, mastery_dict, status='graded',
         attempt=1, submitted_at='2026-04-10T10:00:00Z'):
    return {
        'id': sub_id, 'student_id': student_id, 'content_id': content_id,
        'attempt_number': attempt, 'submitted_at': submitted_at,
        'percentage': percentage,
        'results': {'standards_mastery': mastery_dict, 'score': percentage / 10, 'total_points': 10},
        'status': status,
    }


# ============ LLM mock helpers ============
# Used by every test that exercises the route's generation block (which calls
# OpenAIAdapter.chat -> _post_process_assignment). The route imports
# OpenAIAdapter and get_api_key inline at request time; tests patch them at
# their source modules so the inline imports inside post_remediate pick up
# the mock. Setting `mock_completion.usage = None` is REQUIRED -- the route
# calls the REAL `_extract_usage(completion, "gpt-4o")` which formats
# `completion.usage.cost` with `f"${cost:.4f}"`. A bare MagicMock raises
# TypeError on the format string. None makes _extract_usage return defaults.
def _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key):
    """Returns the mock_adapter instance for inspection."""
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


def _llm_request_prompt_text(mock_adapter):
    """Extract the user prompt text from the LLMRequest passed to .chat()."""
    assert mock_adapter.chat.call_count == 1
    llm_req = mock_adapter.chat.call_args[0][0]
    return llm_req.messages[0].content[0].text


# ============ Validation tests ============

class TestRemediateValidation:
    """Auth + 6-step validation order."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
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
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_bogus_target_mode_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'bogus',
        }, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'target_mode' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_target_student_id_for_single_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_target_student_uuid_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
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
            'standard_code': 'MA.6.AR.1.2',
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
            'standard_code': '',
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
            'standard_code': 'MA.6.AR.1.2',
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
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'red-tier' in body.get('detail', '').lower() or 'no' in body.get('detail', '').lower()

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_cross_class_injection_returns_403(self, mock_sb_fn, client, teacher_headers):
        # Student is in a DIFFERENT class.
        other_stu = '99999999-cccc-cccc-cccc-999999999999'
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-other', 'student_id': other_stu}],
            'students': [{'id': other_stu}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': other_stu,
        }, headers=teacher_headers)
        assert resp.status_code == 403


# ============ Generation tests ============

class TestRemediateGeneration:
    """Single-student happy path; class-wide happy path; AI fallback paths."""

    def _ms(self, std='MA.6.AR.1.2', earned=4, possible=10):
        return {std: {'points_earned': earned, 'points_possible': possible, 'question_count': 2}}

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_single_student_happy_path(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # 8 questions returned by the (mocked) post-processor.
        mock_pp.return_value = ({
            'title': 'Remediation: MA.6.AR.1.2',
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
                 'standard': 'MA.6.AR.1.2'} for i in range(1, 9)
            ]}],
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_red_tier_happy_path(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'Remediation: MA.6.AR.1.2',
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
                 'standard': 'MA.6.AR.1.2'} for i in range(1, 9)
            ]}],
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_too_few_valid_questions_returns_422(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # Post-processor returns only 2 valid questions -- below the floor of 3.
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': 1, 'text': 'Q1', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'},
                {'id': 2, 'text': 'Q2', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'},
            ]}],
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_grade_metadata_falls_back(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # Class has no grade_level / subject -- route should still generate.
        cls_no_meta = [{'id': 'cls-1', 'teacher_id': 'test-teacher-001', 'name': 'C',
                        'grade_level': None, 'subject': None}]
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_response_contains_generated_at_timestamp(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_excludes_out_of_class_submissions_for_evidence(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        """Regression for cross-class submission leakage: a student with red mastery
        on this standard from ANOTHER class must NOT be considered red-tier in the
        current class. Spec promises parity with Progress Rank grid which scopes
        by class_id first."""
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1000})
        # Student has red mastery on MA.6.AR.1.2 in cls-OTHER (out of scope).
        # Has no submissions in cls-1 (current class).
        out_of_class_mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [
                # Submission is for cls-OTHER's content, not cls-1's.
                _sub('s-other', STU_1, 'content-OTHER-class', 40, out_of_class_mastery),
            ],
            'published_content': [
                # cls-1 has its own content but the student hasn't submitted to it.
                {'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1', 'content_type': 'assessment'},
                # NOTE: 'content-OTHER-class' is NOT in cls-1's published_content.
            ],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        # Should return 400 -- no in-class evidence means no red-tier students in this class.
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'red-tier' in body.get('detail', '').lower() or 'no' in body.get('detail', '').lower()

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_single_student_excludes_out_of_class_evidence(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        """Single-student historical-evidence check must scope to current class.
        Out-of-class evidence on the same standard must NOT count as historical
        evidence for THIS class's remediation."""
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1000})
        out_of_class_mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [
                _sub('s-other', STU_1, 'content-OTHER-class', 40, out_of_class_mastery),
            ],
            'published_content': [
                {'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1', 'content_type': 'assessment'},
            ],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student',
            'target_student_id': STU_1,
        }, headers=teacher_headers)
        # Should return 400 -- no in-class evidence on this standard.
        assert resp.status_code == 400


# ============ Red-tier resolution tests ============

class TestRemediateRedTierResolution:
    """Edge cases for the red_tier_in_class resolver."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_excludes_students_with_no_submissions(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # 3 enrolled students; only stu-1 has a submission (red).
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1000})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        STU_3 = '33333333-dddd-dddd-dddd-333333333333'
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_uses_latest_submission_per_student(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # stu-1 has 2 submissions: older one was red (40%), latest is green (90%).
        # The latest must win -- student NOT counted as red.
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_excludes_students_at_exactly_70_percent(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers):
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # 70% is the lower bound of yellow -- NOT red. Student excluded.
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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


# ============ Accommodations integration tests ============
# Uses _set_up_llm_mocks + _llm_request_prompt_text from Task 1 scaffolding.

class TestRemediateAccommodations:
    """Single-student path injects accommodation segment into the LLM prompt
    (NOT into _post_process_assignment, which receives the parsed assignment dict).
    Uses try/except fall-through on accommodation helper failure.
    """

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_helper_success_appends_segment(self, mock_sb_fn, mock_pp, mock_helper,
                                             mock_adapter_cls, mock_get_api_key,
                                             client, teacher_headers):
        mock_helper.return_value = "ACCOMMODATION INSTRUCTIONS: simplify vocabulary"
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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
        # Helper called with the student id + teacher id.
        mock_helper.assert_called_with(STU_1, 'test-teacher-001')
        # The accommodation segment shows up in the LLMRequest sent to the adapter.
        prompt_text = _llm_request_prompt_text(mock_adapter)
        assert 'ACCOMMODATION INSTRUCTIONS: simplify vocabulary' in prompt_text

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_helper_raises_falls_back_to_grade_level(self, mock_sb_fn, mock_pp, mock_helper,
                                                       mock_adapter_cls, mock_get_api_key,
                                                       client, teacher_headers, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger='backend.routes.student_portal_routes')
        mock_helper.side_effect = RuntimeError("corrupt profile")
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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
        # Route still returns 200 -- helper failure falls back to grade level.
        assert resp.status_code == 200
        # No accommodation segment in the LLM prompt.
        prompt_text = _llm_request_prompt_text(mock_adapter)
        assert 'ACCOMMODATION' not in prompt_text
        # Warning logged.
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('accommodations_helper_failed' in r.getMessage() for r in warnings)

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_segment_skips_audit_log(self, mock_sb_fn, mock_pp, mock_helper,
                                            mock_adapter_cls, mock_get_api_key,
                                            client, teacher_headers, caplog):
        import logging
        caplog.set_level(logging.INFO, logger='backend.routes.student_portal_routes')
        mock_helper.return_value = ""  # No accommodations on file -> empty string.
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'sections': [{'name': 'Practice', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
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

    @patch('backend.routes.student_account_routes._generate_class_code')
    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_null_target_creates_class_wide_row(self, mock_sb_fn, mock_gen_code, client, teacher_headers):
        # NULL target_student_ids -> existing class-wide behavior preserved.
        # Uses _multi_table_sb (filter-aware) + insert spy on published_content
        # so the test is decoupled from the route's exact .execute() ordering.
        # Patch _generate_class_code: it calls _get_supabase() (NOT _get_teacher_supabase)
        # which would hit a real Supabase client in CI without env credentials.
        mock_gen_code.return_value = 'TEST01'
        captured = {}
        table_data = {
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
            'published_content': [{'id': 'new-content-id'}],
        }
        def _table(name):
            chain = _make_chain(table_data.get(name, []))
            if name == 'published_content':
                def _spy_insert(payload):
                    captured['payload'] = payload
                    return chain
                chain.insert.side_effect = _spy_insert
            return chain
        sb = MagicMock()
        sb.table.side_effect = _table
        mock_sb_fn.return_value = sb
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Test',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        # Insert payload should NOT contain target_student_ids OR have it as None.
        payload = captured.get('payload', {})
        assert payload.get('target_student_ids') in (None, [])

    @patch('backend.routes.student_account_routes._generate_class_code')
    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_valid_targets_inserts_with_targeting(self, mock_sb_fn, mock_gen_code, client, teacher_headers):
        # Same decoupled pattern: filter-aware mock for table reads + insert spy.
        # Patch _generate_class_code (see prior test for rationale).
        mock_gen_code.return_value = 'TEST02'
        captured = {}
        table_data = {
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'published_content': [{'id': 'new-content-id'}],
        }
        def _table(name):
            chain = _make_chain(table_data.get(name, []))
            if name == 'published_content':
                def _spy_insert(payload):
                    captured['payload'] = payload
                    return chain
                chain.insert.side_effect = _spy_insert
            return chain
        sb = MagicMock()
        sb.table.side_effect = _table
        mock_sb_fn.return_value = sb
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1', 'content': {'questions': [{'text': 'Q1'}]},
            'content_type': 'assessment', 'title': 'Remediation',
            'target_student_ids': [STU_1],
        }, headers=teacher_headers)
        assert resp.status_code == 200
        assert captured.get('payload', {}).get('target_student_ids') == [STU_1]


# ============ Phase 4.2 #1 Lesson-text tests ============
# Spec: docs/superpowers/specs/2026-04-29-phase4.2-lesson-text-design.md

VALID_LESSON = {
    'intro': 'This standard asks students to combine like terms to simplify expressions. '
             'Like terms have the same variable raised to the same power.',
    'worked_example': 'Problem: Simplify 3x + 5 + 2x - 1.\n'
                      'Step 1: Identify like terms. 3x and 2x are like terms; 5 and -1 are like terms.\n'
                      'Step 2: Combine: (3x + 2x) + (5 - 1) = 5x + 4.\n'
                      'Answer: 5x + 4.',
    'key_takeaway': 'Combine variable terms with the same letter and exponent; combine constants separately.',
}


def _set_up_llm_mocks_with_ai_text(mock_adapter_cls, mock_get_api_key, ai_response_dict):
    """Variant of _set_up_llm_mocks that lets the test inject the AI's
    JSON response shape directly. Used for lesson tests where we need to
    control whether/what the AI returns in the `lesson` field."""
    mock_get_api_key.return_value = "sk-test-fake"
    mock_adapter = MagicMock()
    mock_completion = MagicMock()
    mock_completion.usage = None
    text_part = MagicMock()
    text_part.text = json.dumps(ai_response_dict)
    mock_completion.content_parts = [text_part]
    mock_adapter.chat.return_value = mock_completion
    mock_adapter_cls.return_value = mock_adapter
    return mock_adapter


def _lesson_test_supabase():
    """Returns a supabase mock with the boilerplate fixtures every lesson
    test needs: owned class, enrolled student with historical evidence."""
    mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
    return _multi_table_sb({
        'classes': CLS_OWNED,
        'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
        'students': [{'id': STU_1}],
        'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
        'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                               'content_type': 'assessment'}],
    })


def _post_processed_assignment():
    """The shape `_post_process_assignment` returns when mocked. 8 valid
    questions in sections shape — matches existing happy-path tests."""
    return ({
        'title': 'Practice - MA.6.AR.1.2',
        'sections': [{'name': 'Practice', 'questions': [
            {'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
             'standard': 'MA.6.AR.1.2'} for i in range(1, 9)
        ]}],
    }, {'total_tokens': 1500})


class TestLessonGenerationHappyPath:
    """Valid lesson dict round-trips through to the response."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_valid_lesson_round_trips_to_response(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        _set_up_llm_mocks_with_ai_text(
            mock_adapter_cls, mock_get_api_key,
            {'title': 'Practice - MA.6.AR.1.2', 'lesson': VALID_LESSON,
             'sections': [{'name': 'Practice', 'questions': []}]},
        )
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _lesson_test_supabase()
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['lesson'] is not None
        assert body['lesson']['intro'] == VALID_LESSON['intro']
        assert body['lesson']['worked_example'] == VALID_LESSON['worked_example']
        assert body['lesson']['key_takeaway'] == VALID_LESSON['key_takeaway']

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_response_always_includes_lesson_key_even_when_invalid(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """Spec contract: response.lesson is always present (None if dropped, dict if valid).
        Frontend null-check is consistent."""
        # AI returns NO lesson key.
        _set_up_llm_mocks_with_ai_text(
            mock_adapter_cls, mock_get_api_key,
            {'title': 'P', 'sections': [{'name': 'P', 'questions': []}]},
        )
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _lesson_test_supabase()
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'lesson' in body, "response must always include lesson key"
        assert body['lesson'] is None

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_capture_independent_of_post_process(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """`_post_process_assignment` doesn't touch top-level lesson — even if
        the post-processor (mocked here) returns sections without a lesson key,
        the lesson captured BEFORE the call still surfaces in the response."""
        _set_up_llm_mocks_with_ai_text(
            mock_adapter_cls, mock_get_api_key,
            {'title': 'P', 'lesson': VALID_LESSON,
             'sections': [{'name': 'P', 'questions': []}]},
        )
        # Mocked post-process returns no lesson key — captures the case where
        # the processor strips it. Route should still surface lesson via the
        # raw_lesson capture before the call.
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _lesson_test_supabase()
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        body = resp.get_json()
        assert body['lesson'] is not None


class TestLessonValidationDrop:
    """Each drop reason yields response.lesson is None."""

    def _drive(self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
               client, teacher_headers, lesson_value):
        _set_up_llm_mocks_with_ai_text(
            mock_adapter_cls, mock_get_api_key,
            {'title': 'P', 'lesson': lesson_value,
             'sections': [{'name': 'P', 'questions': []}]},
        )
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _lesson_test_supabase()
        return client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_as_string_dropped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        resp = self._drive(mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
                            client, teacher_headers, "this is not a dict")
        assert resp.get_json()['lesson'] is None

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_as_list_dropped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        resp = self._drive(mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
                            client, teacher_headers, ["intro", "worked", "takeaway"])
        assert resp.get_json()['lesson'] is None

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_missing_intro_dropped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        partial = {'worked_example': 'WE', 'key_takeaway': 'KT'}
        resp = self._drive(mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
                            client, teacher_headers, partial)
        assert resp.get_json()['lesson'] is None

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_empty_per_field_dropped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        empty_we = {'intro': 'I', 'worked_example': '   ', 'key_takeaway': 'KT'}
        resp = self._drive(mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
                            client, teacher_headers, empty_we)
        assert resp.get_json()['lesson'] is None

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_non_string_per_field_dropped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        non_string = {'intro': 'I', 'worked_example': 'WE', 'key_takeaway': 42}
        resp = self._drive(mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
                            client, teacher_headers, non_string)
        assert resp.get_json()['lesson'] is None

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_lesson_per_field_oversize_dropped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        oversize = {'intro': 'I' * 1501, 'worked_example': 'WE', 'key_takeaway': 'KT'}
        resp = self._drive(mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key,
                            client, teacher_headers, oversize)
        assert resp.get_json()['lesson'] is None


class TestLessonExtraFieldsStripped:
    """Validator must construct a clean dict with exactly the three known fields.
    Extra keys (`summary`, `tags`) must NOT be passed through (no unbounded
    JSONB leak)."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_extra_fields_stripped(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        bloated = dict(VALID_LESSON)
        bloated['summary'] = 'should not pass through'
        bloated['tags'] = ['math', 'algebra']
        bloated['arbitrary_dict'] = {'key': 'unbounded data attack vector'}
        _set_up_llm_mocks_with_ai_text(
            mock_adapter_cls, mock_get_api_key,
            {'title': 'P', 'lesson': bloated,
             'sections': [{'name': 'P', 'questions': []}]},
        )
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _lesson_test_supabase()
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        body = resp.get_json()
        assert body['lesson'] is not None
        # CRITICAL: response.lesson must contain ONLY the three canonical fields.
        assert set(body['lesson'].keys()) == {'intro', 'worked_example', 'key_takeaway'}, (
            f"Extra fields leaked through validator: {set(body['lesson'].keys())}"
        )


class TestFallbackWrapperPreservesLesson:
    """If AI returns {questions, lesson} (NOT sections-shape), the route's
    fallback wrapper at line ~2400 must preserve `lesson` through to validation.
    Without the fix, the wrapper would silently drop lesson before the
    raw_lesson capture."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_fallback_wrapper_preserves_lesson(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        # AI returns non-sections shape: {questions, lesson} at top level.
        _set_up_llm_mocks_with_ai_text(
            mock_adapter_cls, mock_get_api_key,
            {'title': 'P', 'lesson': VALID_LESSON,
             'questions': [{'id': i, 'standard': 'MA.6.AR.1.2'} for i in range(1, 9)]},
        )
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _lesson_test_supabase()
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Without the fallback-wrapper preserving lesson, this would be None.
        assert body['lesson'] is not None, (
            "Fallback wrapper at line ~2400 dropped lesson — it must copy lesson into "
            "the wrapped assignment dict so raw_lesson capture sees it"
        )
        assert body['lesson']['intro'] == VALID_LESSON['intro']


class TestPublishToClassRoundTripsLesson:
    """`/api/publish-to-class` must write `content` JSONB verbatim from the
    request body. Tests that posting `{content: {questions, lesson}}` results
    in both keys reaching `published_content.content`."""

    @patch('backend.routes.student_account_routes._generate_class_code')
    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_to_class_round_trips_lesson_in_content(
        self, mock_sb_fn, mock_gen_code, client, teacher_headers,
    ):
        # _generate_class_code calls _get_supabase (NOT _get_teacher_supabase)
        # which would hit a real Supabase client in CI without env credentials.
        # Pattern matches existing TestPublishToClassHardening tests.
        mock_gen_code.return_value = 'TEST02'
        captured = {}
        table_data = {
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'published_content': [{'id': 'new-content-id'}],
        }
        def _table(name):
            chain = _make_chain(table_data.get(name, []))
            if name == 'published_content':
                def _spy_insert(payload):
                    captured['payload'] = payload
                    return chain
                chain.insert.side_effect = _spy_insert
            return chain
        sb = MagicMock()
        sb.table.side_effect = _table
        mock_sb_fn.return_value = sb
        resp = client.post('/api/publish-to-class', json={
            'class_id': 'cls-1',
            'content': {
                'questions': [{'text': 'Q1', 'standard': 'MA.6.AR.1.2'}],
                'lesson': VALID_LESSON,
            },
            'content_type': 'assessment', 'title': 'Remediation',
            'target_student_ids': [STU_1],
        }, headers=teacher_headers)
        assert resp.status_code == 200
        # Verify lesson reached the JSONB column verbatim.
        stored_content = captured.get('payload', {}).get('content', {})
        assert 'lesson' in stored_content, (
            "publish_to_class must write content verbatim — lesson missing from JSONB row"
        )
        assert stored_content['lesson'] == VALID_LESSON
        assert stored_content.get('questions') == [{'text': 'Q1', 'standard': 'MA.6.AR.1.2'}]


# ============ Phase 4.2 #3: pre-generation config (count + difficulty) ============
# Spec: docs/superpowers/specs/2026-04-30-phase4.2-pregen-config-design.md

class TestRemediationConfigValidation:
    """Strict 400 on invalid count/difficulty values; defaults only when missing."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_count_too_low_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'count': 2,  # below REMEDIATION_COUNT_MIN=3
        }, headers=teacher_headers)
        assert resp.status_code == 400
        assert 'between 3 and 15' in (resp.get_json().get('detail') or '')

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_count_too_high_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'count': 16,  # above REMEDIATION_COUNT_MAX=15
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_count_boolean_returns_400(self, mock_sb_fn, client, teacher_headers):
        """Codex MAJOR: Python bool is int subclass. count=True must be rejected
        explicitly, otherwise it would slip past `isinstance(int)` and become count=1."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'count': True,
        }, headers=teacher_headers)
        assert resp.status_code == 400, "count=True must be rejected (bool is int subclass)"

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_difficulty_invalid_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'difficulty': 'hard',  # typo — must be one of: easier, same, harder
        }, headers=teacher_headers)
        assert resp.status_code == 400
        assert 'easier' in (resp.get_json().get('detail') or '')

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_count_and_difficulty_default_when_missing(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """Body missing count + difficulty → defaults (8, same). Backwards-compat."""
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'Practice', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
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
            'target_mode': 'single_student', 'target_student_id': STU_1,
            # No count or difficulty — should default
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('count') == 8
        assert body.get('difficulty') == 'same'


class TestRemediationConfigPromptIntegration:
    """Verify count + difficulty actually thread into the AI prompt."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_count_5_lands_in_prompt(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        # Match the requested count (5) so the 422 floor doesn't trip
        mock_pp.return_value = ({
            'title': 'Practice', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 6)
            ]}],
        }, {'total_tokens': 1500})
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
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'count': 5,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        # Prompt: "Generate exactly 5..." with mix 3 MC + 2 SA (60/40)
        prompt = _llm_request_prompt_text(mock_adapter)
        assert 'Generate exactly 5 grade-' in prompt
        assert '3 multiple-choice questions' in prompt
        assert '2 short-answer questions' in prompt
        body = resp.get_json()
        assert body.get('count') == 5

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_difficulty_harder_lands_in_prompt(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'Practice', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001',
                         'grade_level': '7', 'subject': 'Math'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'difficulty': 'harder',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        prompt = _llm_request_prompt_text(mock_adapter)
        assert 'more challenging vocabulary' in prompt
        assert 'grade-8' in prompt, "grade=7 + harder → grade-8 (clamped to K-12)"
        body = resp.get_json()
        assert body.get('difficulty') == 'harder'


class TestRemediationConfigGradeClamping:
    """Codex MINOR: grade arithmetic clamps to K-12 (no grade-13 references)."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_grade_12_with_harder_clamps_to_12(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
        mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001',
                         'grade_level': '12', 'subject': 'Math'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
            'student_submissions': [_sub('s-1', STU_1, CID_Q1, 40, mastery)],
            'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                                   'content_type': 'assessment'}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'difficulty': 'harder',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        prompt = _llm_request_prompt_text(mock_adapter)
        assert 'grade-13' not in prompt, "grade-13 must never appear (K-12 clamp)"
        assert 'grade-12' in prompt


# ============ Phase 4.2 #12: DOK control ============
# Spec: docs/superpowers/specs/2026-04-30-phase4.2-dok-control-design.md

class TestRemediationDokValidation:
    """Strict 400 on invalid dok values; defaults to None (Auto) when missing."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_dok_missing_defaults_to_null(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """Body missing dok → defaults to Auto (response.dok is null)."""
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
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
            'target_mode': 'single_student', 'target_student_id': STU_1,
            # No dok → defaults
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('dok') is None

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_dok_out_of_range_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'dok': 5,  # out of [1, 4]
        }, headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_dok_boolean_returns_400(self, mock_sb_fn, client, teacher_headers):
        """Codex MAJOR pattern: Python bool is int subclass — must be rejected
        explicitly so dok=True doesn't slip past isinstance(int) and become 1."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': STU_1}],
            'students': [{'id': STU_1}],
        })
        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'dok': True,
        }, headers=teacher_headers)
        assert resp.status_code == 400, "dok=True must be rejected (bool is int subclass)"


class TestRemediationDokPromptIntegration:
    """Verify dok lands in the AI prompt + clarifier for orthogonal coexistence."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_dok_2_lands_in_prompt(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """dok=2 → prompt contains 'DOK level 2: Skills & Concepts' and the
        cognitive-rigor-vs-vocab clarifier."""
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
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
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'dok': 2,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        prompt = _llm_request_prompt_text(mock_adapter)
        assert 'DOK level 2' in prompt
        assert 'Skills & Concepts' in prompt
        # Codex MAJOR: orthogonal-coexistence clarifier must appear.
        assert 'Cognitive rigor is set by DOK' in prompt
        body = resp.get_json()
        assert body.get('dok') == 2

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_dok_auto_no_directive_in_prompt(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """dok missing/null → no DOK directive in the prompt (preserves
        backwards-compat for legacy callers)."""
        mock_adapter = _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
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
            'target_mode': 'single_student', 'target_student_id': STU_1,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        prompt = _llm_request_prompt_text(mock_adapter)
        assert 'DOK level' not in prompt, "Auto mode must NOT inject a DOK directive"


class TestDokFieldPassThrough:
    """Codex round 2 MINOR: AI's per-question `dok: N` field must survive
    _post_process_assignment + response flattening to reach the response body."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_ai_dok_field_passes_through_to_response(
        self, mock_sb_fn, mock_pp, mock_adapter_cls, mock_get_api_key, client, teacher_headers,
    ):
        """Mock _post_process_assignment to return questions WITH dok fields;
        verify the response flattens them through and `dok: 2` survives."""
        _set_up_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq',
                 'standard': 'MA.6.AR.1.2', 'dok': 2}  # dok field on each question
                for i in range(1, 9)
            ]}],
        }, {'total_tokens': 1500})
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
            'target_mode': 'single_student', 'target_student_id': STU_1,
            'dok': 2,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Each question must keep its dok field through flattening.
        for q in body.get('questions') or []:
            assert q.get('dok') == 2, (
                "Per-question dok field must survive _post_process_assignment "
                "+ response flattening (Codex round 2 MINOR — pass-through "
                "contract is the most-likely-to-regress behavior)"
            )


# ============ Phase 4.3 Sprint 1: DOK display helpers ============
# Spec: docs/superpowers/specs/2026-05-01-phase4.3-sprint1-dok-display-design.md

class TestValidateDok:
    """_validate_dok normalizes int / numeric-string DOKs to int 1..4 or None.

    Codex round 1 MINOR: legacy storage and AI output drift can produce
    string DOKs ("3") instead of ints (3). Normalize on read so the
    frontend predicate stays simple. bool must be rejected explicitly.
    """

    def test_valid_int_returns_self(self):
        from backend.routes.student_portal_routes import _validate_dok
        for n in (1, 2, 3, 4):
            assert _validate_dok(n) == n

    def test_numeric_string_normalizes_to_int(self):
        from backend.routes.student_portal_routes import _validate_dok
        assert _validate_dok("1") == 1
        assert _validate_dok("3") == 3
        assert _validate_dok("  4  ") == 4

    def test_bool_rejected_even_though_int_subclass(self):
        from backend.routes.student_portal_routes import _validate_dok
        # bool is a subclass of int — without an explicit isinstance(value, bool)
        # check, True would slip through and become 1.
        assert _validate_dok(True) is None
        assert _validate_dok(False) is None

    def test_int_out_of_range_returns_none(self):
        from backend.routes.student_portal_routes import _validate_dok
        assert _validate_dok(0) is None
        assert _validate_dok(5) is None
        assert _validate_dok(-1) is None

    def test_non_numeric_string_returns_none(self):
        from backend.routes.student_portal_routes import _validate_dok
        assert _validate_dok("foo") is None
        assert _validate_dok("") is None
        assert _validate_dok("3.0") is None  # not a clean int

    def test_none_returns_none(self):
        from backend.routes.student_portal_routes import _validate_dok
        assert _validate_dok(None) is None

    def test_unsupported_types_return_none(self):
        from backend.routes.student_portal_routes import _validate_dok
        assert _validate_dok(3.0) is None  # float
        assert _validate_dok([3]) is None  # list
        assert _validate_dok({"dok": 3}) is None  # dict


class TestDeriveUniformDok:
    """_derive_uniform_dok returns the shared DOK from content.questions
    when ALL questions agree on a valid level (1..4), else None."""

    def test_uniform_dok_returns_value(self):
        from backend.routes.student_portal_routes import _derive_uniform_dok
        content = {'questions': [{'dok': 3}, {'dok': 3}, {'dok': 3}]}
        assert _derive_uniform_dok(content) == 3

    def test_mixed_dok_returns_none(self):
        from backend.routes.student_portal_routes import _derive_uniform_dok
        content = {'questions': [{'dok': 2}, {'dok': 3}, {'dok': 2}]}
        assert _derive_uniform_dok(content) is None

    def test_any_question_missing_dok_returns_none(self):
        from backend.routes.student_portal_routes import _derive_uniform_dok
        content = {'questions': [{'dok': 3}, {'dok': 3}, {}]}
        assert _derive_uniform_dok(content) is None

    def test_empty_questions_returns_none(self):
        from backend.routes.student_portal_routes import _derive_uniform_dok
        assert _derive_uniform_dok({'questions': []}) is None

    def test_no_questions_key_returns_none(self):
        from backend.routes.student_portal_routes import _derive_uniform_dok
        assert _derive_uniform_dok({}) is None

    def test_non_dict_content_returns_none(self):
        from backend.routes.student_portal_routes import _derive_uniform_dok
        assert _derive_uniform_dok(None) is None
        assert _derive_uniform_dok("invalid") is None
        assert _derive_uniform_dok([{'dok': 3}]) is None  # list at top-level

    def test_string_dok_normalized_uniformly(self):
        """Codex MINOR follow-up — if the AI ever wrote dok as string,
        the helper still derives uniform DOK because _validate_dok
        normalizes "3" → 3 first."""
        from backend.routes.student_portal_routes import _derive_uniform_dok
        content = {'questions': [{'dok': "3"}, {'dok': 3}, {'dok': "3"}]}
        assert _derive_uniform_dok(content) == 3
