"""Characterization tests for /api/grade-assessment-answers (Wave 6 Slice 5).

Written BEFORE extracting the grading logic into planner_assessments, since the
endpoint had no CI-scoped test. The deterministic paths (MC, true/false, matching,
no-answer, missing->400) need no AI mock; the open-ended AI path is covered by a
direct service test (see test_planner_assessments_service.py) with a mocked adapter.
"""
import os
import sys

import pytest

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
def headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


MC_ASSESSMENT = {
    "sections": [{
        "name": "A",
        "questions": [
            {"number": 1, "question": "2+2?", "type": "multiple_choice",
             "options": ["3", "4", "5", "6"], "answer": "B", "points": 5},
            {"number": 2, "question": "Sky is blue?", "type": "true_false",
             "answer": "true", "points": 5},
        ],
    }],
}


def test_mc_and_tf_grading_scores_correctly(client, headers):
    # q0: pick "B" (correct, 5pts); q1: "true" (correct, 5pts) => 10/10, 100%
    resp = client.post('/api/grade-assessment-answers',
                      json={"assessment": MC_ASSESSMENT, "answers": {"0-0": "B", "0-1": "true"}},
                      headers=headers)
    assert resp.status_code == 200
    r = resp.get_json()["results"]
    assert r["total_points"] == 10
    assert r["score"] == 10
    assert r["percentage"] == 100
    assert r["questions"][0]["is_correct"] is True
    assert r["questions"][1]["is_correct"] is True


def test_mc_incorrect_scores_zero_for_that_question(client, headers):
    # q0: "A" (incorrect); q1: "false" (incorrect) => 0/10
    resp = client.post('/api/grade-assessment-answers',
                      json={"assessment": MC_ASSESSMENT, "answers": {"0-0": "A", "0-1": "false"}},
                      headers=headers)
    r = resp.get_json()["results"]
    assert r["score"] == 0 and r["percentage"] == 0
    assert r["questions"][0]["is_correct"] is False
    assert "correct answer is B" in r["questions"][0]["feedback"]


def test_no_answer_recorded_as_not_provided(client, headers):
    resp = client.post('/api/grade-assessment-answers',
                      json={"assessment": MC_ASSESSMENT, "answers": {"0-0": "B"}},
                      headers=headers)
    r = resp.get_json()["results"]
    assert r["questions"][1]["feedback"] == "No answer provided"
    assert r["score"] == 5  # only q0 credited


def test_mc_index_answer_format(client, headers):
    # student_answer as int index 1 -> letter "B" (correct)
    resp = client.post('/api/grade-assessment-answers',
                      json={"assessment": MC_ASSESSMENT, "answers": {"0-0": 1, "0-1": "true"}},
                      headers=headers)
    assert resp.get_json()["results"]["questions"][0]["is_correct"] is True


def test_missing_assessment_or_answers_returns_400(client, headers):
    assert client.post('/api/grade-assessment-answers', json={"answers": {"0-0": "B"}}, headers=headers).status_code == 400
    assert client.post('/api/grade-assessment-answers', json={"assessment": MC_ASSESSMENT}, headers=headers).status_code == 400
