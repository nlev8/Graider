"""TDD guard tests for contentless-export bug.

Bug: export_lesson_plan and export_generated_assignment wrote a
title-only docx to ~/Downloads/Graider/ and subprocess-opened it even
when the submitted payload had no renderable content (empty plan / no
sections).  A stale browser tab could spam junk files and pop Word open
repeatedly.

Fix contract:
  - POST with empty plan  → 400, JSON error "Nothing to export"
  - POST with empty sections → 400, JSON error "Nothing to export"
  - Valid payloads still pass through (no false rejection)
  - subprocess.run is NEVER called on the 400 paths

Auth pattern: reuses `client` fixture from conftest_routes.py, which
registers all blueprints against a minimal Flask app and injects
g.user_id = 'test-teacher' via before_request — the same pattern used
by test_assignment_routes_unit.py and test_planner_routes.py.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Reuse the exact same fixtures as test_assignment_routes_unit.py /
# test_planner_routes.py — no new auth bypass invented.
from tests.conftest_routes import client, flask_app, mock_grading_state, grading_lock  # noqa: F401,E501


# ---------------------------------------------------------------------------
# Module-scoped autouse fixture: hermetic isolation for ALL tests in this file
#
# Every test runs with these side-effects completely mocked out, whether or
# not the production guard is present (RED phase).  The mock targets cover
# every real-disk/real-window path reached by either route:
#
#   1. subprocess.run          — prevents 'open' launching Word/Preview
#   2. docx.Document           — prevents python-docx writing a real .docx
#   3. _export_assignment_docx_graider — prevents the Graider table writer
#   4. reportlab SimpleDocTemplate    — prevents PDF writes
#   5. os.makedirs             — prevents ~/Downloads/Graider dir creation
#
# The fixture yields the subprocess mock so individual tests can assert on it.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _hermetic_export(request):
    """Patch out every file-writing / OS-window side-effect for this module."""
    mock_doc = MagicMock()
    mock_doc.paragraphs = []
    mock_doc.add_heading.return_value = MagicMock()
    mock_doc.add_paragraph.return_value = MagicMock()
    mock_doc.add_table.return_value = MagicMock()
    mock_doc.add_run = MagicMock(return_value=MagicMock())

    mock_subprocess = MagicMock()

    with patch('backend.routes.planner_routes.subprocess.run', mock_subprocess), \
         patch('docx.Document', return_value=mock_doc), \
         patch(
             'backend.routes.planner_routes._export_assignment_docx_graider',
             return_value='/tmp/fake_assignment.docx',
         ), \
         patch('reportlab.platypus.SimpleDocTemplate') as mock_pdf_cls, \
         patch('backend.routes.planner_routes.os.makedirs'):
        mock_pdf_cls.return_value.build = MagicMock()
        # Expose the subprocess mock via the test's request node so individual
        # tests can retrieve it with the `mock_subprocess_run` fixture below.
        request.node._hermetic_subprocess = mock_subprocess
        yield mock_subprocess


@pytest.fixture()
def mock_subprocess_run(request):
    """Return the subprocess.run mock installed by _hermetic_export."""
    return request.node._hermetic_subprocess


# ---------------------------------------------------------------------------
# export_lesson_plan — empty plan → 400
# ---------------------------------------------------------------------------

def test_export_lesson_plan_empty_returns_400(client, mock_subprocess_run):  # noqa: F811
    """POST /api/export-lesson-plan with an empty plan dict must return 400
    and must NOT call subprocess.run (i.e. must not open Word or write a
    file to ~/Downloads/Graider/)."""
    resp = client.post(
        '/api/export-lesson-plan',
        json={'plan': {}},
        content_type='application/json',
    )
    assert resp.status_code == 400, (
        f"Expected 400 for empty plan, got {resp.status_code}; "
        f"body: {resp.get_data(as_text=True)}"
    )
    body = resp.get_json()
    assert body is not None, "Response must be JSON"
    assert 'error' in body, f"Expected 'error' key in JSON, got: {body}"
    assert 'Nothing to export' in body['error'], (
        f"Expected 'Nothing to export' in error, got: {body['error']}"
    )
    mock_subprocess_run.assert_not_called()


# ---------------------------------------------------------------------------
# export_lesson_plan — valid plan → still succeeds (no false rejection)
# ---------------------------------------------------------------------------

def test_export_lesson_plan_with_days_still_succeeds(client):  # noqa: F811
    """POST /api/export-lesson-plan with a plan that has 'days' must NOT
    be rejected — the guard must only fire on truly empty plans."""
    payload = {
        'plan': {
            'title': 'Test Plan',
            'days': [{'day': 1, 'topic': 'Introduction to Testing'}],
        }
    }
    resp = client.post(
        '/api/export-lesson-plan',
        json=payload,
        content_type='application/json',
    )
    # Must not be a 400 (guard must not fire for valid content)
    assert resp.status_code != 400, (
        f"Guard fired falsely on a plan with 'days'; status={resp.status_code}; "
        f"body: {resp.get_data(as_text=True)}"
    )


# ---------------------------------------------------------------------------
# export_generated_assignment — no sections → 400
# ---------------------------------------------------------------------------

def test_export_generated_assignment_no_sections_returns_400(client, mock_subprocess_run):  # noqa: F811
    """POST /api/export-generated-assignment with an assignment that has no
    sections must return 400 and must NOT call subprocess.run."""
    payload = {
        'assignment': {'title': 'Empty Assignment'},
        'format': 'docx',
    }
    resp = client.post(
        '/api/export-generated-assignment',
        json=payload,
        content_type='application/json',
    )
    assert resp.status_code == 400, (
        f"Expected 400 for assignment with no sections, got {resp.status_code}; "
        f"body: {resp.get_data(as_text=True)}"
    )
    body = resp.get_json()
    assert body is not None, "Response must be JSON"
    assert 'error' in body, f"Expected 'error' key in JSON, got: {body}"
    assert 'Nothing to export' in body['error'], (
        f"Expected 'Nothing to export' in error, got: {body['error']}"
    )
    mock_subprocess_run.assert_not_called()


# ---------------------------------------------------------------------------
# export_generated_assignment — valid sections → not 400
# ---------------------------------------------------------------------------

def test_export_generated_assignment_with_sections_still_exports(client):  # noqa: F811
    """POST /api/export-generated-assignment with a non-empty sections list
    must NOT be rejected by the guard — valid assignments still export."""
    payload = {
        'assignment': {
            'title': 'Real Assignment',
            'sections': [
                {
                    'name': 'Part 1',
                    'questions': [{'text': 'What is 2+2?', 'points': 5}],
                }
            ],
        },
        'format': 'pdf',
    }
    resp = client.post(
        '/api/export-generated-assignment',
        json=payload,
        content_type='application/json',
    )
    # Must not be a 400 (guard must not fire for valid content)
    assert resp.status_code != 400, (
        f"Guard fired falsely on assignment with sections; status={resp.status_code}; "
        f"body: {resp.get_data(as_text=True)}"
    )
