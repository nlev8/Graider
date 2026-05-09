"""Unit tests for backend/routes/seo_routes.py.

Audit MAJOR #4 sprint follow-up to PR #281. Targets the 32 uncovered
LOC in seo_routes.py — all 4 route handler bodies were entirely
untested.

Strategy
--------
Flask `test_client` + mocks of the underlying `seo_service` functions
(which themselves are 100% covered by `tests/test_seo_service_unit.py`
from PR #264). Each route gets:
  * Input validation (missing required field → 400)
  * Service-error pass-through (service returns {"error": ...} → 500)
  * Happy path (service returns dict → 200 JSON)

`require_teacher` is bypassed via the standard `app.test_client()` +
session-set pattern used elsewhere in the test suite.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    """Authenticated Flask test client (bypasses @require_teacher)."""
    from backend.app import app

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-teacher-1'
        yield c


# ──────────────────────────────────────────────────────────────────
# /api/seo/optimize-meta
# ──────────────────────────────────────────────────────────────────


class TestOptimizeMeta:
    def test_missing_content_returns_400(self, client):
        resp = client.post(
            "/api/seo/optimize-meta",
            json={},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body
        assert "content is required" in body["error"]

    def test_empty_content_returns_400(self, client):
        resp = client.post(
            "/api/seo/optimize-meta",
            json={"content": ""},
        )
        assert resp.status_code == 400

    def test_service_error_returns_500(self, client):
        with patch("backend.routes.seo_routes.optimize_meta",
                   return_value={"error": "AI down"}):
            resp = client.post(
                "/api/seo/optimize-meta",
                json={"content": "Article content"},
            )
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "AI down"

    def test_happy_path_returns_200(self, client):
        canned = {
            "title": "Optimized Title",
            "description": "Meta description",
            "keywords": ["education", "AI"],
        }
        with patch("backend.routes.seo_routes.optimize_meta",
                   return_value=canned) as mock:
            resp = client.post(
                "/api/seo/optimize-meta",
                json={"content": "Some article content here.",
                      "page_url": "https://x.com/page"},
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body == canned
        # Service called with content + page_url positional args
        assert mock.call_args.args == ("Some article content here.",
                                       "https://x.com/page")

    def test_page_url_optional(self, client):
        with patch("backend.routes.seo_routes.optimize_meta",
                   return_value={}) as mock:
            client.post(
                "/api/seo/optimize-meta",
                json={"content": "x"},
            )
        # When page_url omitted, defaults to ''
        assert mock.call_args.args[1] == ""


# ──────────────────────────────────────────────────────────────────
# /api/seo/generate-schema
# ──────────────────────────────────────────────────────────────────


class TestGenerateSchema:
    def test_missing_title_returns_400(self, client):
        resp = client.post(
            "/api/seo/generate-schema",
            json={"type": "article"},  # no title
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body
        assert "title is required" in body["error"]

    def test_empty_title_returns_400(self, client):
        resp = client.post(
            "/api/seo/generate-schema",
            json={"title": ""},
        )
        assert resp.status_code == 400

    def test_service_error_returns_500(self, client):
        with patch("backend.routes.seo_routes.generate_schema",
                   return_value={"error": "schema gen failed"}):
            resp = client.post(
                "/api/seo/generate-schema",
                json={"title": "Valid Title"},
            )
        assert resp.status_code == 500

    def test_happy_path_returns_200_with_full_data(self, client):
        canned = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Valid Title",
        }
        with patch("backend.routes.seo_routes.generate_schema",
                   return_value=canned) as mock:
            resp = client.post(
                "/api/seo/generate-schema",
                json={"title": "Valid Title", "type": "article"},
            )
        assert resp.status_code == 200
        assert resp.get_json() == canned
        # Service called with the entire request dict
        passed = mock.call_args.args[0]
        assert passed["title"] == "Valid Title"
        assert passed["type"] == "article"


# ──────────────────────────────────────────────────────────────────
# /api/seo/analyze-content
# ──────────────────────────────────────────────────────────────────


class TestAnalyzeContent:
    def test_missing_content_returns_400(self, client):
        resp = client.post(
            "/api/seo/analyze-content",
            json={"target_keyword": "x"},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "content is required" in body["error"]

    def test_service_error_returns_500(self, client):
        with patch("backend.routes.seo_routes.analyze_content",
                   return_value={"error": "AI down"}):
            resp = client.post(
                "/api/seo/analyze-content",
                json={"content": "article"},
            )
        assert resp.status_code == 500

    def test_happy_path_returns_200(self, client):
        canned = {"score": 85, "factors": [{"name": "Keyword density", "score": 90}]}
        with patch("backend.routes.seo_routes.analyze_content",
                   return_value=canned) as mock:
            resp = client.post(
                "/api/seo/analyze-content",
                json={"content": "Article body", "target_keyword": "AI grading"},
            )
        assert resp.status_code == 200
        assert resp.get_json() == canned
        # Service called with content + target_keyword
        assert mock.call_args.args == ("Article body", "AI grading")

    def test_target_keyword_optional(self, client):
        with patch("backend.routes.seo_routes.analyze_content",
                   return_value={}) as mock:
            client.post(
                "/api/seo/analyze-content",
                json={"content": "x"},
            )
        # Defaults to empty string
        assert mock.call_args.args[1] == ""


# ──────────────────────────────────────────────────────────────────
# /api/seo/suggest-blog-topics
# ──────────────────────────────────────────────────────────────────


class TestSuggestBlogTopics:
    def test_no_required_validation(self, client):
        # All inputs optional — no 400 path. Empty body still calls
        # the service.
        with patch("backend.routes.seo_routes.suggest_blog_topics",
                   return_value={"topics": []}):
            resp = client.post("/api/seo/suggest-blog-topics", json={})
        assert resp.status_code == 200

    def test_service_error_returns_500(self, client):
        with patch("backend.routes.seo_routes.suggest_blog_topics",
                   return_value={"error": "AI down"}):
            resp = client.post(
                "/api/seo/suggest-blog-topics",
                json={"existing_titles": ["Existing Post"]},
            )
        assert resp.status_code == 500

    def test_happy_path_returns_200(self, client):
        canned = {
            "topics": [
                {"title": "AI in Education", "keywords": ["AI", "edtech"]},
                {"title": "Adaptive Learning", "keywords": ["learning"]},
            ],
        }
        with patch("backend.routes.seo_routes.suggest_blog_topics",
                   return_value=canned) as mock:
            resp = client.post(
                "/api/seo/suggest-blog-topics",
                json={
                    "existing_titles": ["Old Post 1", "Old Post 2"],
                    "domain_keywords": ["AI", "education"],
                },
            )
        assert resp.status_code == 200
        assert resp.get_json() == canned
        # Service called with both args
        existing, domain = mock.call_args.args
        assert existing == ["Old Post 1", "Old Post 2"]
        assert domain == ["AI", "education"]

    def test_domain_keywords_defaults_to_none(self, client):
        with patch("backend.routes.seo_routes.suggest_blog_topics",
                   return_value={"topics": []}) as mock:
            client.post(
                "/api/seo/suggest-blog-topics",
                json={"existing_titles": []},
            )
        # Production: `domain_keywords = data.get('domain_keywords', None)`
        assert mock.call_args.args[1] is None

    def test_existing_titles_defaults_to_empty_list(self, client):
        with patch("backend.routes.seo_routes.suggest_blog_topics",
                   return_value={"topics": []}) as mock:
            client.post("/api/seo/suggest-blog-topics", json={})
        assert mock.call_args.args[0] == []
