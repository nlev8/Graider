"""Regression tests for issue #355 — survey/publish-assessment endpoints
return 500 instead of 503 when Supabase is unconfigured.

The Phase-2 load harness (`tests/load/`) runs the backend WITHOUT Supabase
in CI to exercise local-file fallbacks for rubric/settings/etc. Three
endpoints lack any fallback and were unhandled-erroring when their
unconditional `db.table(...)` call hit a `None` client:

  - POST `/api/survey/create`
  - GET  `/api/survey/list`
  - POST `/api/publish-assessment`

Pre-fix the routes raised `AttributeError: 'NoneType' object has no
attribute 'table'`, caught by `handle_route_errors`, returned 500.
Post-fix they detect the null client at the top and return 503
("Supabase not configured") — matching the canonical pattern at
`backend/routes/district_routes.py:527`.

503 is the production-correct response for "endpoint is structurally
fine but persistence backend is unavailable" — it would also be the
right behavior if Supabase ever went down in production. The
behavioral fix here closes a real prod-reliability gap, not just a
test-only failure mode.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {
        "X-Test-Teacher-Id": "teach-1",
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    """Allow X-Test-Teacher-Id auth-shim path for these tests."""
    monkeypatch.setenv("FLASK_ENV", "development")


class TestSurveyCreateNoSupabase:
    def test_returns_503_not_500_when_db_unconfigured(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.survey_routes.get_supabase",
            return_value=None,
        ):
            resp = client.post(
                "/api/survey/create",
                data=json.dumps({"title": "Feedback"}),
                headers=auth_headers,
            )

        assert resp.status_code == 503, (
            f"Pre-#355 returned 500 (unhandled AttributeError on None.table); "
            f"post-fix should return 503 Service Unavailable. Got "
            f"{resp.status_code}: {resp.get_data(as_text=True)[:200]}"
        )
        body = resp.get_json() or {}
        assert "supabase" in (body.get("error", "") + body.get("detail", "")).lower()


class TestSurveyListNoSupabase:
    def test_returns_503_not_500_when_db_unconfigured(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.survey_routes.get_supabase",
            return_value=None,
        ):
            resp = client.get("/api/survey/list", headers=auth_headers)

        assert resp.status_code == 503, (
            f"Pre-#355 returned 500; post-fix should return 503. Got "
            f"{resp.status_code}: {resp.get_data(as_text=True)[:200]}"
        )


class TestPublishAssessmentNoSupabase:
    def test_returns_503_not_500_when_db_unconfigured(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.student_portal_routes._get_teacher_supabase",
            return_value=None,
        ):
            resp = client.post(
                "/api/publish-assessment",
                data=json.dumps({
                    "assessment": {"title": "Quiz 1"},
                    "settings": {},
                }),
                headers=auth_headers,
            )

        assert resp.status_code == 503, (
            f"Pre-#355 returned 500 (unhandled AttributeError on None.table); "
            f"post-fix should return 503 Service Unavailable. Got "
            f"{resp.status_code}: {resp.get_data(as_text=True)[:200]}"
        )


# ── Sibling routes in survey_routes.py have the same latent bug ────


class TestSurveyResultsNoSupabase:
    """`/api/survey/results` is a sibling of the 3 above with the same
    `db.table()` first-call pattern. Not in #355's literal scope (the
    load test skips it when create_survey doesn't return a join_code),
    but the bug is identical — fix it in the same PR per CLAUDE.md
    Rule #11 (small fix, no unrelated code touched)."""

    def test_returns_503_not_500_when_db_unconfigured(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.survey_routes.get_supabase",
            return_value=None,
        ):
            resp = client.get(
                "/api/survey/results?code=ABC123", headers=auth_headers,
            )

        assert resp.status_code == 503, (
            f"Expected 503; got {resp.status_code}: "
            f"{resp.get_data(as_text=True)[:200]}"
        )


class TestPublicSurveyPageNoSupabase:
    """`/survey/<code>` is parent-facing (no teacher auth). Same bug:
    raw `db.table()` hits None. Should return a 503 HTML page so parents
    see a graceful error, not an opaque 500."""

    def test_returns_503_not_500_when_db_unconfigured(self, client):
        with patch(
            "backend.routes.survey_routes.get_supabase",
            return_value=None,
        ):
            resp = client.get("/survey/ABC123")

        assert resp.status_code == 503, (
            f"Expected 503 (graceful parent-facing error); got "
            f"{resp.status_code}"
        )
