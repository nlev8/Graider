"""Unit tests for backend/routes/survey_routes.py.

Audit MAJOR #4 sprint follow-up to PR #291. Targets the ~82 uncovered
LOC (25% baseline). Covers all 5 endpoints + the _generate_survey_code
helper:

* POST /api/survey/create (teacher-auth)
* GET  /api/survey/results (teacher-auth)
* GET  /api/survey/list (teacher-auth)
* GET  /survey/<code> (public HTML page)
* POST /api/survey/<code>/submit (public)

Strategy: minimal Flask app fixture + chain-mocked Supabase via the
same FakeChain helper used in test_behavior_routes_unit.py. Auth via
FLASK_ENV=development + X-Test-Teacher-Id for teacher endpoints;
public endpoints bypass auth so no header needed.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"X-Test-Teacher-Id": "teach-1", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")


# ──────────────────────────────────────────────────────────────────
# Chain-mock helper for Supabase fluent queries
# ──────────────────────────────────────────────────────────────────


class FakeChain:
    def __init__(self, execute_data=None, execute_side_effect=None):
        self._execute_data = execute_data
        self._execute_side_effect = execute_side_effect
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        return self

    def table(self, *a, **kw): return self._record("table", *a, **kw)
    def select(self, *a, **kw): return self._record("select", *a, **kw)
    def insert(self, *a, **kw): return self._record("insert", *a, **kw)
    def update(self, *a, **kw): return self._record("update", *a, **kw)
    def delete(self, *a, **kw): return self._record("delete", *a, **kw)
    def eq(self, *a, **kw): return self._record("eq", *a, **kw)
    def order(self, *a, **kw): return self._record("order", *a, **kw)

    def execute(self):
        self.calls.append(("execute", (), {}))
        if self._execute_side_effect is not None:
            raise self._execute_side_effect
        m = MagicMock()
        m.data = self._execute_data
        return m


def patch_supabase(execute_data=None, execute_side_effect=None,
                   execute_sequence=None):
    """Patch get_request_supabase. If execute_sequence is provided, each
    .execute() call returns the next item; otherwise execute_data is
    used for every call."""
    chain = FakeChain(execute_data, execute_side_effect)
    sb = MagicMock()
    sb.table.side_effect = chain.table

    if execute_sequence is not None:
        seq_iter = iter(execute_sequence)

        def seq_execute():
            chain.calls.append(("execute", (), {}))
            try:
                return next(seq_iter)
            except StopIteration:
                m = MagicMock(); m.data = []
                return m

        chain.execute = seq_execute  # type: ignore[assignment]

    p = patch(
        "backend.routes.survey_routes.get_supabase",
        return_value=sb,
    )
    return p, chain


# ──────────────────────────────────────────────────────────────────
# /api/survey/create (POST) — create_survey
# ──────────────────────────────────────────────────────────────────


class TestCreateSurvey:
    def test_happy_path_inserts_with_default_questions(
        self, client, auth_headers,
    ):
        # _generate_survey_code does a select to check uniqueness — first
        # iteration returns empty data → code is unique → returns it.
        # Then create_survey calls insert(...).
        # execute_sequence:
        #   1. unique-code probe → MagicMock(data=[])
        #   2. final insert → MagicMock(data=[{"id": "row-1"}])
        seq = [
            MagicMock(data=[]),  # unique-code check
            MagicMock(data=[{"id": "row-1"}]),  # insert
        ]
        p, chain = patch_supabase(execute_sequence=seq)
        with p:
            resp = client.post(
                "/api/survey/create",
                data=json.dumps({}),  # no body → defaults
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert len(body["join_code"]) == 6
        assert body["survey_url"].startswith("/survey/")
        assert body["survey_url"].endswith(body["join_code"])
        # Confirm an insert was issued (production sends an insert kwarg-
        # less call after the unique-code probe)
        insert_calls = [c for c in chain.calls if c[0] == "insert"]
        assert len(insert_calls) == 1
        payload = insert_calls[0][1][0]
        assert payload["join_code"] == body["join_code"]
        assert payload["title"] == "Parent Communication Survey"
        assert payload["teacher_name"] == "Teacher"
        assert payload["assessment"]["content_type"] == "survey"
        assert payload["is_active"] is True
        assert payload["submission_count"] == 0

    def test_custom_title_and_questions_used(
        self, client, auth_headers,
    ):
        custom_qs = [
            {"id": "q1", "text": "Custom Q", "type": "rating"},
        ]
        seq = [MagicMock(data=[]), MagicMock(data=[{"id": "x"}])]
        p, chain = patch_supabase(execute_sequence=seq)
        with p:
            resp = client.post(
                "/api/survey/create",
                data=json.dumps({
                    "teacher_name": "Ms Doe",
                    "title": "End-of-Year Feedback",
                    "questions": custom_qs,
                }),
                headers=auth_headers,
            )
        assert resp.status_code == 200
        insert_call = next(c for c in chain.calls if c[0] == "insert")
        payload = insert_call[1][0]
        assert payload["teacher_name"] == "Ms Doe"
        assert payload["title"] == "End-of-Year Feedback"
        assert payload["assessment"]["questions"] == custom_qs

    def test_code_collision_retries_until_unique(
        self, client, auth_headers,
    ):
        # First two probes return existing rows (collision), third is
        # empty → loop terminates with that code; then the insert.
        seq = [
            MagicMock(data=[{"id": "collide-1"}]),
            MagicMock(data=[{"id": "collide-2"}]),
            MagicMock(data=[]),  # unique
            MagicMock(data=[{"id": "row"}]),  # insert
        ]
        p, chain = patch_supabase(execute_sequence=seq)
        with p:
            resp = client.post(
                "/api/survey/create",
                data=json.dumps({}),
                headers=auth_headers,
            )
        assert resp.status_code == 200
        # Probed select 3 times before insert
        select_calls = [c for c in chain.calls if c[0] == "select"]
        assert len(select_calls) == 3


# ──────────────────────────────────────────────────────────────────
# /api/survey/results (GET) — survey_results
# ──────────────────────────────────────────────────────────────────


class TestSurveyResults:
    def test_missing_code_returns_400(self, client, auth_headers):
        resp = client.get("/api/survey/results", headers=auth_headers)
        assert resp.status_code == 400
        assert "Missing code" in resp.get_json()["error"]

    def test_survey_not_found_returns_404(self, client, auth_headers):
        p, _ = patch_supabase(execute_data=[])
        with p:
            resp = client.get(
                "/api/survey/results?code=ABC123",
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_aggregates_rating_distribution_and_text_responses(
        self, client, auth_headers,
    ):
        record = {
            "title": "Year-End",
            "submission_count": 3,
            "assessment": {
                "questions": [
                    {"id": "communication", "text": "Comms?", "type": "rating"},
                    {"id": "feedback", "text": "Anything else?",
                     "type": "text"},
                    # Unknown type — production silently skips
                    {"id": "ignored", "text": "?", "type": "weird"},
                ],
                "responses": [
                    {"communication": 5, "feedback": "Great class"},
                    {"communication": 4, "feedback": "Good"},
                    # Missing rating → counted only when present
                    {"feedback": ""},  # empty text → filtered out
                ],
            },
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.get(
                "/api/survey/results?code=ABC123",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["title"] == "Year-End"
        assert body["total_responses"] == 3
        comm = body["questions"]["communication"]
        assert comm["count"] == 2
        assert comm["average"] == 4.5
        assert comm["distribution"]["5"] == 1
        assert comm["distribution"]["4"] == 1
        assert comm["distribution"]["1"] == 0
        # Empty text response was filtered out (truthy check)
        feedback = body["questions"]["feedback"]
        assert feedback["count"] == 2
        assert "Great class" in feedback["responses"]
        assert "Good" in feedback["responses"]
        # Unknown type doesn't appear in summary
        assert "ignored" not in body["questions"]

    def test_no_ratings_returns_zero_average(self, client, auth_headers):
        record = {
            "title": "Empty",
            "submission_count": 0,
            "assessment": {
                "questions": [
                    {"id": "q1", "text": "Q", "type": "rating"},
                ],
                "responses": [],
            },
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.get(
                "/api/survey/results?code=ABC",
                headers=auth_headers,
            )
        body = resp.get_json()
        # Rating with no responses → average=0 (no ZeroDivisionError)
        assert body["questions"]["q1"]["average"] == 0
        assert body["questions"]["q1"]["count"] == 0


# ──────────────────────────────────────────────────────────────────
# /api/survey/list (GET) — list_surveys
# ──────────────────────────────────────────────────────────────────


class TestListSurveys:
    def test_returns_data_array(self, client, auth_headers):
        rows = [
            {"join_code": "AAA123", "title": "S1", "submission_count": 5,
             "is_active": True, "created_at": "2026-05-01T00:00:00"},
            {"join_code": "BBB456", "title": "S2", "submission_count": 0,
             "is_active": False, "created_at": "2026-05-02T00:00:00"},
        ]
        p, chain = patch_supabase(execute_data=rows)
        with p:
            resp = client.get("/api/survey/list", headers=auth_headers)
        body = resp.get_json()
        assert body["surveys"] == rows
        # Pin filter + ordering args
        assert ("eq",
                ("settings->>content_type", "survey"),
                {}) in chain.calls
        assert ("order",
                ("created_at",),
                {"desc": True}) in chain.calls

    def test_no_surveys_returns_empty(self, client, auth_headers):
        p, _ = patch_supabase(execute_data=None)
        with p:
            resp = client.get("/api/survey/list", headers=auth_headers)
        assert resp.get_json()["surveys"] == []


# ──────────────────────────────────────────────────────────────────
# GET /survey/<code> — survey_page (public HTML)
# ──────────────────────────────────────────────────────────────────


class TestSurveyPage:
    def test_not_found_returns_404_html(self, client):
        p, _ = patch_supabase(execute_data=[])
        with p:
            resp = client.get("/survey/MISSING")
        assert resp.status_code == 404
        assert b"Survey not found" in resp.data

    def test_not_a_survey_returns_400(self, client):
        record = {
            "title": "T", "teacher_name": "X", "is_active": True,
            "assessment": {"content_type": "quiz"},  # not 'survey'
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.get("/survey/CODE")
        assert resp.status_code == 400
        assert b"Not a survey" in resp.data

    def test_inactive_survey_returns_410(self, client):
        record = {
            "title": "T", "teacher_name": "X", "is_active": False,
            "assessment": {"content_type": "survey"},
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.get("/survey/CODE")
        assert resp.status_code == 410
        assert b"no longer accepting" in resp.data

    def test_active_survey_renders_html_with_questions(self, client):
        record = {
            "title": "Year End",
            "teacher_name": "Ms Doe",
            "is_active": True,
            "assessment": {
                "content_type": "survey",
                "questions": [
                    {"id": "rating1", "text": "Star Question",
                     "type": "rating"},
                    {"id": "text1", "text": "Thoughts?", "type": "text"},
                ],
            },
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.get("/survey/HAPPY1")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/html")
        body = resp.data.decode()
        # Title + teacher + both questions appear
        assert "Year End" in body
        assert "Ms Doe" in body
        assert "Star Question" in body
        assert "Thoughts?" in body
        # Star inputs rendered
        assert 'name="rating1"' in body
        # Textarea rendered
        assert 'name="text1"' in body
        # Submit URL embedded (uses code from path)
        assert "/api/survey/HAPPY1/submit" in body


# ──────────────────────────────────────────────────────────────────
# POST /api/survey/<code>/submit — submit_survey
# ──────────────────────────────────────────────────────────────────


class TestSubmitSurvey:
    def test_not_found_returns_404(self, client):
        p, _ = patch_supabase(execute_data=[])
        with p:
            resp = client.post(
                "/api/survey/MISSING/submit",
                data=json.dumps({}),
                content_type="application/json",
            )
        assert resp.status_code == 404

    def test_inactive_returns_410(self, client):
        record = {
            "id": "row-1", "is_active": False,
            "assessment": {"content_type": "survey", "responses": []},
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.post(
                "/api/survey/CODE/submit",
                data=json.dumps({"q1": 5}),
                content_type="application/json",
            )
        assert resp.status_code == 410
        assert "closed" in resp.get_json()["error"]

    def test_not_a_survey_returns_400(self, client):
        record = {
            "id": "row-1", "is_active": True,
            "assessment": {"content_type": "assessment"},
        }
        p, _ = patch_supabase(execute_data=[record])
        with p:
            resp = client.post(
                "/api/survey/CODE/submit",
                data=json.dumps({}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_happy_path_appends_response_and_updates_count(self, client):
        record = {
            "id": "row-42", "is_active": True,
            "assessment": {
                "content_type": "survey",
                "responses": [{"existing": "response"}],
            },
        }
        # Two execute calls: first the SELECT, then the UPDATE
        seq = [MagicMock(data=[record]), MagicMock(data=None)]
        p, chain = patch_supabase(execute_sequence=seq)
        with p:
            resp = client.post(
                "/api/survey/CODE/submit",
                data=json.dumps({"communication": 5,
                                 "feedback": "Great"}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        # Pin update payload: responses appended; submission_count = 2
        update_call = next(c for c in chain.calls if c[0] == "update")
        payload = update_call[1][0]
        assert payload["submission_count"] == 2
        new_responses = payload["assessment"]["responses"]
        assert len(new_responses) == 2
        # New response carries the submitted_at timestamp + form data
        latest = new_responses[-1]
        assert latest["communication"] == 5
        assert latest["feedback"] == "Great"
        assert "submitted_at" in latest
