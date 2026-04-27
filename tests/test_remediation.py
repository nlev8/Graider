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
