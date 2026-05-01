"""Tests for Phase 4.2 #2 — per-student generation in class-wide remediations.

Spec: docs/superpowers/specs/2026-04-30-phase4.2-perstudent-gen-design.md

Auto-decide: if at least one targeted student has accommodations, /remediate
generates N personalized variants in parallel; else stays on shared path.
Hard cap REMEDIATION_PERSONALIZED_MAX=10 students. New batch publish
endpoint at /api/publish-to-class-batch with duplicate rejection +
atomic insert.
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Fixtures (shared with other test modules) ============

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
    """Filter-aware Supabase mock supporting eq/in/neq/gte."""
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


def _build_red_tier_supabase(student_ids):
    """Class with N red-tier students + class content + low-mastery submissions."""
    mastery = {'MA.6.AR.1.2': {'points_earned': 4, 'points_possible': 10, 'question_count': 2}}
    sub_template = lambda sid, sub_id: {
        'id': sub_id, 'student_id': sid, 'content_id': CID_Q1,
        'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
        'percentage': 40,
        'results': {'standards_mastery': mastery, 'score': 4, 'total_points': 10},
        'status': 'graded',
    }
    return _multi_table_sb({
        'classes': CLS_OWNED,
        'class_students': [
            {'class_id': 'cls-1', 'student_id': sid} for sid in student_ids
        ],
        'students': [
            {'id': sid, 'first_name': f'Student{i+1}', 'last_name': 'X'}
            for i, sid in enumerate(student_ids)
        ],
        'student_submissions': [sub_template(sid, f's-{i}') for i, sid in enumerate(student_ids)],
        'published_content': [{'id': CID_Q1, 'class_id': 'cls-1', 'title': 'Q1',
                               'content_type': 'assessment'}],
    })


def _make_ai_response(title='Practice'):
    """Stable AI mock response (sections shape with 8 questions)."""
    return {
        'title': title,
        'lesson': {
            'intro': 'Intro paragraph.',
            'worked_example': 'Worked example with steps.',
            'key_takeaway': 'Key takeaway.',
        },
        'sections': [{'name': 'Practice', 'questions': [
            {'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
             'standard': 'MA.6.AR.1.2'} for i in range(1, 9)
        ]}],
    }


def _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key, ai_response=None):
    """Set up adapter mock such that EVERY OpenAIAdapter() instantiation
    returns a MagicMock with a working .chat() call. Required for personalized
    mode where each worker thread instantiates its own adapter."""
    mock_get_api_key.return_value = "sk-test-fake"
    if ai_response is None:
        ai_response = _make_ai_response()

    def make_completion():
        completion = MagicMock()
        completion.usage = None
        text_part = MagicMock()
        text_part.text = json.dumps(ai_response)
        completion.content_parts = [text_part]
        return completion

    def make_adapter(*args, **kwargs):
        adapter = MagicMock()
        adapter.chat.return_value = make_completion()
        return adapter

    mock_adapter_cls.side_effect = make_adapter
    return mock_adapter_cls


def _post_processed_assignment(question_count=8):
    return ({
        'title': 'Practice',
        'sections': [{'name': 'Practice', 'questions': [
            {'id': i, 'text': f'Q{i}', 'type': 'mcq' if i < 6 else 'short_answer',
             'standard': 'MA.6.AR.1.2'} for i in range(1, question_count + 1)
        ]}],
    }, {'total_tokens': 1500, 'input_tokens': 800, 'output_tokens': 700, 'cost': 0.01})


# ============ Auto-decide trigger ============

class TestAutoDecideTrigger:
    """At least one student with accommodations triggers personalized mode."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_no_accommodations_stays_shared(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """All targeted students have NO accommodations → stays on shared path,
        response.mode = 'shared'."""
        mock_bap.return_value = ""  # No accommodations for anyone
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('mode') == 'shared'
        assert 'questions' in body
        assert 'variants' not in body

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_one_student_with_accommodations_triggers_personalized(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """If even ONE targeted student has accommodations → personalized
        mode for ALL N (uniform N)."""
        # Only STU_2 has accommodations.
        def bap_side(sid, tid):
            return "STUDENT ACCOMMODATIONS\n- Extra time" if sid == STU_2 else ""
        mock_bap.side_effect = bap_side
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('mode') == 'personalized'
        assert len(body.get('variants') or []) == 3, "uniform N: all 3 targeted students get a variant"
        # Verify deterministic sort by student_name (Student1, Student2, Student3).
        student_ids_in_order = [v['student_id'] for v in body['variants']]
        assert student_ids_in_order == [STU_1, STU_2, STU_3]

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_accommodation_load_failure_treated_as_empty(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """build_accommodation_prompt raises → that student is treated as
        no-accommodations. Doesn't crash the route."""
        def bap_side(sid, tid):
            if sid == STU_2:
                raise RuntimeError("simulated load failure")
            return ""
        mock_bap.side_effect = bap_side
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        # No crash. Since all students effectively have empty accommodations,
        # stays shared.
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('mode') == 'shared'


# ============ Personalized mode cap ============

class TestPersonalizedCap:
    """REMEDIATION_PERSONALIZED_MAX = 10 limits N students with accommodations."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_eleven_students_with_accommodations_returns_422(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """11 red-tier students all with accommodations → 422 (over personalized max)."""
        eleven_students = [
            f'{i:08d}-aaaa-aaaa-aaaa-{i:012d}' for i in range(1, 12)
        ]
        mock_bap.return_value = "STUDENT ACCOMMODATIONS\n- Extra time"
        mock_sb_fn.return_value = _build_red_tier_supabase(eleven_students)
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 422
        body = resp.get_json()
        assert 'too many students' in (body.get('error') or '').lower()
        assert body.get('max') == 10
        assert body.get('target_count') == 11

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_eleven_students_no_accommodations_stays_shared(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """11 red-tier students with NO accommodations → stays shared, NOT 422.
        Personalization cap only matters when personalized mode would trigger."""
        eleven_students = [
            f'{i:08d}-aaaa-aaaa-aaaa-{i:012d}' for i in range(1, 12)
        ]
        mock_bap.return_value = ""  # No accommodations
        mock_sb_fn.return_value = _build_red_tier_supabase(eleven_students)
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        # NOT 422 — auto-decide stays shared because no personalization would occur.
        assert resp.status_code == 200
        assert resp.get_json().get('mode') == 'shared'


# ============ Variant generation ============

class TestVariantGeneration:
    """Worker results aggregate correctly; failures fail the whole publish."""

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_all_variants_succeed_returns_sorted_array(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        mock_bap.side_effect = lambda sid, tid: (
            "STUDENT ACCOMMODATIONS\n- Extra time" if sid == STU_2 else ""
        )
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_2, STU_1, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        body = resp.get_json()
        assert body['mode'] == 'personalized'
        # Sorted by student name (Student1, Student2, Student3 from the
        # supabase fixture's first_name=f'Student{i+1}').
        names = [v['student_name'] for v in body['variants']]
        assert names == sorted(names, key=lambda n: n.lower())
        # Each variant has its expected shape.
        for v in body['variants']:
            assert 'student_id' in v
            assert 'student_name' in v
            assert 'questions' in v
            assert 'lesson' in v
            assert 'usage' not in v, "usage field stripped before response"

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_one_variant_failure_returns_500(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """If one worker raises, the entire publish fails (all-or-nothing)."""
        mock_bap.return_value = "STUDENT ACCOMMODATIONS\n- Extra time"

        # Configure adapter to raise on one specific call by using a counter.
        call_count = {'n': 0}
        def make_adapter(*args, **kwargs):
            adapter = MagicMock()
            def chat_side(*a, **k):
                call_count['n'] += 1
                if call_count['n'] == 2:  # Second call raises
                    raise RuntimeError("simulated AI failure")
                completion = MagicMock()
                completion.usage = None
                text_part = MagicMock()
                text_part.text = json.dumps(_make_ai_response())
                completion.content_parts = [text_part]
                return completion
            adapter.chat.side_effect = chat_side
            return adapter
        mock_adapter_cls.side_effect = make_adapter
        mock_get_api_key.return_value = "sk-test-fake"
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        assert resp.status_code == 500
        body = resp.get_json()
        assert 'failed' in (body.get('error') or '').lower() or 'fail' in (body.get('error') or '').lower()
        assert 'failed_student_ids' in body

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_personalized_mode_honors_count_and_difficulty(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """Phase 4.2 #3 (Codex full-PR MINOR): personalized mode threads
        count + difficulty into the AI prompt for each variant + echoes
        them in the response."""
        mock_bap.side_effect = lambda sid, tid: (
            "STUDENT ACCOMMODATIONS\n- Extra time" if sid == STU_2 else ""
        )

        # Capture prompts seen by each adapter instance so we can verify
        # count + difficulty landed.
        captured_prompts = []
        def make_adapter(*args, **kwargs):
            adapter = MagicMock()
            def chat_side(req):
                captured_prompts.append(req.messages[0].content[0].text)
                completion = MagicMock()
                completion.usage = None
                text_part = MagicMock()
                text_part.text = json.dumps(_make_ai_response())
                completion.content_parts = [text_part]
                return completion
            adapter.chat.side_effect = chat_side
            return adapter
        mock_adapter_cls.side_effect = make_adapter
        mock_get_api_key.return_value = "sk-test-fake"

        # post-process returns 5 questions to match count=5
        mock_pp.return_value = ({
            'title': 'P', 'sections': [{'name': 'P', 'questions': [
                {'id': i, 'text': f'Q{i}', 'type': 'mcq', 'standard': 'MA.6.AR.1.2'}
                for i in range(1, 6)
            ]}],
        }, {'total_tokens': 1500})
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
            'count': 5,
            'difficulty': 'harder',
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['mode'] == 'personalized'
        assert body['count'] == 5
        assert body['difficulty'] == 'harder'
        assert len(body['variants']) == 3
        # Every variant's prompt should contain count=5 and "more challenging" directive.
        assert len(captured_prompts) == 3
        for prompt in captured_prompts:
            assert 'Generate exactly 5 grade-' in prompt
            assert '3 multiple-choice' in prompt
            assert '2 short-answer' in prompt
            assert 'more challenging vocabulary' in prompt

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_personalized_mode_threads_dok_into_all_variants(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """Phase 4.2 #12 (Codex round 2 MINOR): personalized mode threads
        dok into each variant's prompt. All N variants get the same DOK
        directive."""
        mock_bap.side_effect = lambda sid, tid: (
            "STUDENT ACCOMMODATIONS\n- Extra time" if sid == STU_2 else ""
        )

        captured_prompts = []
        def make_adapter(*args, **kwargs):
            adapter = MagicMock()
            def chat_side(req):
                captured_prompts.append(req.messages[0].content[0].text)
                completion = MagicMock()
                completion.usage = None
                text_part = MagicMock()
                text_part.text = json.dumps(_make_ai_response())
                completion.content_parts = [text_part]
                return completion
            adapter.chat.side_effect = chat_side
            return adapter
        mock_adapter_cls.side_effect = make_adapter
        mock_get_api_key.return_value = "sk-test-fake"

        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
            'dok': 3,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['mode'] == 'personalized'
        assert body['dok'] == 3
        # Every variant prompt must contain the DOK 3 directive.
        assert len(captured_prompts) == 3
        for prompt in captured_prompts:
            assert 'DOK level 3' in prompt
            assert 'Strategic Thinking' in prompt

    @patch('backend.api_keys.get_api_key')
    @patch('backend.services.llm_adapter.OpenAIAdapter')
    @patch('backend.services.assignment_post_processing._post_process_assignment')
    @patch('backend.accommodations.build_accommodation_prompt')
    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_uniform_n_no_accommodation_student_still_gets_variant(
        self, mock_sb_fn, mock_bap, mock_pp, mock_adapter_cls, mock_get_api_key,
        client, teacher_headers,
    ):
        """In personalized mode (triggered by ANY accommodation), even
        students WITHOUT accommodations get their own variant (uniform N)."""
        # Only STU_1 has accommodations.
        mock_bap.side_effect = lambda sid, tid: (
            "STUDENT ACCOMMODATIONS\n- Extra time" if sid == STU_1 else ""
        )
        _set_up_threaded_llm_mocks(mock_adapter_cls, mock_get_api_key)
        mock_pp.return_value = _post_processed_assignment()
        mock_sb_fn.return_value = _build_red_tier_supabase([STU_1, STU_2, STU_3])

        resp = client.post('/api/teacher/class/cls-1/remediate', json={
            'standard_code': 'MA.6.AR.1.2',
            'target_mode': 'red_tier_in_class',
        }, headers=teacher_headers)
        body = resp.get_json()
        assert body['mode'] == 'personalized'
        sids = sorted(v['student_id'] for v in body['variants'])
        assert sids == sorted([STU_1, STU_2, STU_3]), (
            "Uniform N: all 3 targeted students get a variant, even ones "
            "without accommodations"
        )


# ============ Batch publish endpoint ============

class TestBatchPublishEndpoint:
    """POST /api/publish-to-class-batch atomic insert with cap + dup checks."""

    def _batch_supabase(self, prior_remediations=None):
        prior = prior_remediations or []
        return _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [
                {'class_id': 'cls-1', 'student_id': STU_1},
                {'class_id': 'cls-1', 'student_id': STU_2},
                {'class_id': 'cls-1', 'student_id': STU_3},
            ],
            'students': [{'id': STU_1}, {'id': STU_2}, {'id': STU_3}],
            'published_content': prior + [{'id': 'new-content-id'}],
        })

    @patch('backend.routes.student_account_routes._generate_class_code')
    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_happy_path_atomic_insert(
        self, mock_sb_fn, mock_gen_code, client, teacher_headers,
    ):
        """N items publish in a single .insert(list) call (atomic)."""
        mock_gen_code.return_value = 'TEST09'
        captured = {'insert_calls': []}
        sb_chains = {}

        def make_table_side(name):
            if name not in sb_chains:
                if name == 'classes':
                    sb_chains[name] = _make_chain(CLS_OWNED)
                elif name == 'class_students':
                    sb_chains[name] = _make_chain([
                        {'class_id': 'cls-1', 'student_id': STU_1},
                        {'class_id': 'cls-1', 'student_id': STU_2},
                    ])
                elif name == 'students':
                    sb_chains[name] = _make_chain([{'id': STU_1}, {'id': STU_2}])
                elif name == 'published_content':
                    chain = _make_chain([])
                    def _spy_insert(payload):
                        captured['insert_calls'].append(payload)
                        # Return chain whose .execute() returns success-shaped data.
                        result_chain = MagicMock()
                        result_chain.execute.return_value = MagicMock(data=[
                            {'id': f'new-{i}'} for i in range(len(payload))
                        ])
                        return result_chain
                    chain.insert.side_effect = _spy_insert
                    sb_chains[name] = chain
                else:
                    sb_chains[name] = _make_chain([])
            return sb_chains[name]

        sb = MagicMock()
        sb.table.side_effect = make_table_side
        mock_sb_fn.return_value = sb

        resp = client.post('/api/publish-to-class-batch', json={
            'class_id': 'cls-1',
            'content_type': 'assessment',
            'items': [
                {'content': {'questions': [{'text': 'Q1'}]},
                 'target_student_ids': [STU_1], 'title': 'Rem 1', 'settings': {}},
                {'content': {'questions': [{'text': 'Q2'}]},
                 'target_student_ids': [STU_2], 'title': 'Rem 2', 'settings': {}},
            ],
        }, headers=teacher_headers)
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.get_json()}"
        body = resp.get_json()
        assert body.get('success') is True
        assert len(body.get('content_ids') or []) == 2
        # CRITICAL: atomic write — exactly ONE .insert() call with a list of 2.
        assert len(captured['insert_calls']) == 1, (
            f"expected single .insert(list) call, got {len(captured['insert_calls'])}"
        )
        assert isinstance(captured['insert_calls'][0], list)
        assert len(captured['insert_calls'][0]) == 2

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_wrong_owner_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'teacher_id': 'OTHER'}],
        })
        resp = client.post('/api/publish-to-class-batch', json={
            'class_id': 'cls-1',
            'content_type': 'assessment',
            'items': [{'content': {}, 'target_student_ids': [STU_1], 'title': 'X'}],
        }, headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_duplicate_student_across_items_returns_400(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Codex round 2 MAJOR: duplicate target_student_ids across batch
        items is a defense-in-depth rejection."""
        mock_sb_fn.return_value = self._batch_supabase()
        resp = client.post('/api/publish-to-class-batch', json={
            'class_id': 'cls-1',
            'content_type': 'assessment',
            'items': [
                {'content': {}, 'target_student_ids': [STU_1], 'title': 'A'},
                {'content': {}, 'target_student_ids': [STU_1], 'title': 'B'},  # DUPLICATE
            ],
        }, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'duplicate' in (body.get('detail') or body.get('error') or '').lower()

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_one_item_at_cap_returns_422(self, mock_sb_fn, client, teacher_headers):
        """If any student in any item is at weekly cap → 422 entire batch."""
        from datetime import datetime, timedelta, timezone
        recent = lambda d: (datetime.now(tz=timezone.utc) - timedelta(days=d)).isoformat()
        prior = [
            {'id': 'r1', 'teacher_id': TEACHER, 'target_student_ids': [STU_1],
             'created_at': recent(1)},
            {'id': 'r2', 'teacher_id': TEACHER, 'target_student_ids': [STU_1],
             'created_at': recent(2)},
            {'id': 'r3', 'teacher_id': TEACHER, 'target_student_ids': [STU_1],
             'created_at': recent(3)},
        ]
        mock_sb_fn.return_value = self._batch_supabase(prior_remediations=prior)
        resp = client.post('/api/publish-to-class-batch', json={
            'class_id': 'cls-1',
            'content_type': 'assessment',
            'items': [
                {'content': {}, 'target_student_ids': [STU_1], 'title': 'A'},
                {'content': {}, 'target_student_ids': [STU_2], 'title': 'B'},
            ],
        }, headers=teacher_headers)
        assert resp.status_code == 422
        body = resp.get_json()
        assert body.get('error') == 'Weekly remediation cap reached'
        assert STU_1 in (body.get('capped_student_ids') or [])

    @patch('backend.routes.student_account_routes._get_teacher_supabase')
    def test_empty_items_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = self._batch_supabase()
        resp = client.post('/api/publish-to-class-batch', json={
            'class_id': 'cls-1',
            'content_type': 'assessment',
            'items': [],
        }, headers=teacher_headers)
        assert resp.status_code == 400
