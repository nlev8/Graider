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

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_null_target_creates_class_wide_row(self, mock_sb_fn, client, teacher_headers):
        # NULL target_student_ids -> existing class-wide behavior preserved.
        # Uses _multi_table_sb (filter-aware) + insert spy on published_content
        # so the test is decoupled from the route's exact .execute() ordering.
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

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_publish_with_valid_targets_inserts_with_targeting(self, mock_sb_fn, client, teacher_headers):
        # Same decoupled pattern: filter-aware mock for table reads + insert spy.
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
