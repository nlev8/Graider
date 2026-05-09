"""
Unit tests for backend/services/seo_service.py.

Audit MAJOR #4 sprint follow-up to PR #263. Targets 49 uncovered LOC
(14% baseline) — small + safe target with AI-mock pattern.

Strategy:
- Mock _call_haiku at the module level so no real Claude API calls.
- Test each public function's input validation + prompt assembly +
  mock-return passthrough.
- Test _call_haiku itself with mocked AnthropicAdapter to cover the
  markdown-fence stripping + JSON parsing + error paths.

Pattern: same AI-mock approach as PR #251 (assistant_tools_grading)
and PR #261 (assistant_tools_data).
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# _call_haiku — internal helper with adapter call
# ──────────────────────────────────────────────────────────────────


class TestCallHaiku:
    def test_no_api_key_returns_error(self):
        from backend.services.seo_service import _call_haiku
        with patch("backend.api_keys.get_api_key", return_value=None):
            result = _call_haiku("test prompt")
        assert "error" in result
        assert "ANTHROPIC_API_KEY not configured" in result["error"]

    def test_happy_path_returns_parsed_json(self):
        from backend.services.seo_service import _call_haiku
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text='{"title": "Test", "score": 85}')]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("Generate title")
        assert result == {"title": "Test", "score": 85}

    def test_strips_markdown_code_fences(self):
        """The helper strips ``` fences before json.loads()."""
        from backend.services.seo_service import _call_haiku
        wrapped = "```json\n{\"title\": \"From fenced response\"}\n```"
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text=wrapped)]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert result == {"title": "From fenced response"}

    def test_invalid_json_returns_error_with_raw(self):
        from backend.services.seo_service import _call_haiku
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text="not json at all")]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert "error" in result
        assert "non-JSON" in result["error"]
        assert result["raw"] == "not json at all"

    def test_adapter_exception_returns_error(self):
        from backend.services.seo_service import _call_haiku
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.side_effect = RuntimeError("API down")
            result = _call_haiku("x")
        assert "error" in result
        assert "AI call failed" in result["error"]
        assert "API down" in result["error"]

    def test_empty_response_returns_error(self):
        """Empty content_parts → empty text → JSONDecodeError → returns error."""
        from backend.services.seo_service import _call_haiku
        mock_response = MagicMock()
        mock_response.content_parts = []
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert "error" in result

    def test_passes_max_tokens_to_request(self):
        from backend.services.seo_service import _call_haiku
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text='{}')]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            _call_haiku("x", max_tokens=2500)
        # The LLMRequest passed to .chat had max_tokens=2500
        request = MockAdapter.return_value.chat.call_args.args[0]
        assert request.max_tokens == 2500


# ──────────────────────────────────────────────────────────────────
# optimize_meta
# ──────────────────────────────────────────────────────────────────


class TestOptimizeMeta:
    def test_empty_content_returns_error(self):
        from backend.services.seo_service import optimize_meta
        assert "error" in optimize_meta("")
        assert "error" in optimize_meta("   ")

    def test_calls_haiku_with_content(self):
        from backend.services.seo_service import optimize_meta
        with patch("backend.services.seo_service._call_haiku",
                   return_value={"title": "Optimized"}) as mock:
            result = optimize_meta("Some page content about AI grading.")
        assert result == {"title": "Optimized"}
        # Called once with prompt that contains the content
        prompt = mock.call_args.args[0]
        assert "Some page content about AI grading." in prompt

    def test_truncates_content_to_3000_chars(self):
        from backend.services.seo_service import optimize_meta
        long_content = "X" * 5000
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            optimize_meta(long_content)
        prompt = mock.call_args.args[0]
        # Truncated to first 3000 chars of content
        assert "X" * 3000 in prompt
        # The full 5000 isn't there
        assert "X" * 3001 not in prompt

    def test_includes_url_when_provided(self):
        from backend.services.seo_service import optimize_meta
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            optimize_meta("content", page_url="https://graider.live/blog")
        prompt = mock.call_args.args[0]
        assert "https://graider.live/blog" in prompt

    def test_omits_url_section_when_not_provided(self):
        from backend.services.seo_service import optimize_meta
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            optimize_meta("content")
        prompt = mock.call_args.args[0]
        assert "Page URL:" not in prompt

    def test_uses_800_max_tokens(self):
        from backend.services.seo_service import optimize_meta
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            optimize_meta("content")
        # Second positional or kwarg max_tokens=800
        kwargs = mock.call_args.kwargs
        args = mock.call_args.args
        max_tokens = kwargs.get("max_tokens", args[1] if len(args) > 1 else None)
        assert max_tokens == 800


# ──────────────────────────────────────────────────────────────────
# generate_schema
# ──────────────────────────────────────────────────────────────────


class TestGenerateSchema:
    def test_no_title_returns_error(self):
        from backend.services.seo_service import generate_schema
        result = generate_schema({"type": "article"})
        assert "error" in result

    def test_calls_haiku_with_page_info(self):
        from backend.services.seo_service import generate_schema
        with patch("backend.services.seo_service._call_haiku",
                   return_value={"json_ld": []}) as mock:
            result = generate_schema({
                "type": "article",
                "title": "Test Article",
                "description": "About AI grading",
                "url": "https://graider.live/blog/test",
                "published": "2026-05-01",
            })
        assert result == {"json_ld": []}
        prompt = mock.call_args.args[0]
        assert "Test Article" in prompt
        assert "About AI grading" in prompt
        assert "https://graider.live/blog/test" in prompt
        assert "2026-05-01" in prompt

    def test_includes_faqs_when_provided(self):
        from backend.services.seo_service import generate_schema
        faqs = [{"question": "Q1?", "answer": "A1"}, {"question": "Q2?", "answer": "A2"}]
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            generate_schema({
                "title": "Faq Page", "type": "faq", "faqs": faqs,
            })
        prompt = mock.call_args.args[0]
        assert "FAQ items to include" in prompt
        assert "Q1?" in prompt
        assert "A2" in prompt

    def test_omits_faq_section_when_none_provided(self):
        from backend.services.seo_service import generate_schema
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            generate_schema({"title": "Plain Article"})
        prompt = mock.call_args.args[0]
        assert "FAQ items to include" not in prompt

    def test_default_type_is_article(self):
        from backend.services.seo_service import generate_schema
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            generate_schema({"title": "Untyped"})
        prompt = mock.call_args.args[0]
        assert "Page type: article" in prompt

    def test_uses_2000_max_tokens(self):
        from backend.services.seo_service import generate_schema
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            generate_schema({"title": "x"})
        max_tokens = mock.call_args.kwargs.get("max_tokens")
        if max_tokens is None and len(mock.call_args.args) > 1:
            max_tokens = mock.call_args.args[1]
        assert max_tokens == 2000


# ──────────────────────────────────────────────────────────────────
# analyze_content
# ──────────────────────────────────────────────────────────────────


class TestAnalyzeContent:
    def test_empty_content_returns_error(self):
        from backend.services.seo_service import analyze_content
        assert "error" in analyze_content("")
        assert "error" in analyze_content("   \n\t   ")

    def test_calls_haiku_with_content(self):
        from backend.services.seo_service import analyze_content
        with patch("backend.services.seo_service._call_haiku",
                   return_value={"score": 85, "factors": []}) as mock:
            result = analyze_content("Some article content.")
        assert result["score"] == 85
        prompt = mock.call_args.args[0]
        assert "Some article content." in prompt

    def test_truncates_to_4000_chars(self):
        from backend.services.seo_service import analyze_content
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            analyze_content("X" * 5000)
        prompt = mock.call_args.args[0]
        assert "X" * 4000 in prompt
        assert "X" * 4001 not in prompt

    def test_includes_target_keyword_when_provided(self):
        from backend.services.seo_service import analyze_content
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            analyze_content("content", target_keyword="AI grading")
        prompt = mock.call_args.args[0]
        assert "Target keyword: AI grading" in prompt

    def test_omits_keyword_section_when_not_provided(self):
        from backend.services.seo_service import analyze_content
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            analyze_content("content")
        prompt = mock.call_args.args[0]
        assert "Target keyword:" not in prompt


# ──────────────────────────────────────────────────────────────────
# suggest_blog_topics
# ──────────────────────────────────────────────────────────────────


class TestSuggestBlogTopics:
    def test_empty_titles_uses_none_yet(self):
        from backend.services.seo_service import suggest_blog_topics
        with patch("backend.services.seo_service._call_haiku",
                   return_value={"topics": []}) as mock:
            suggest_blog_topics([])
        prompt = mock.call_args.args[0]
        assert "None yet" in prompt

    def test_includes_existing_titles_in_prompt(self):
        from backend.services.seo_service import suggest_blog_topics
        with patch("backend.services.seo_service._call_haiku",
                   return_value={"topics": []}) as mock:
            suggest_blog_topics([
                "How AI Grading Works",
                "Lesson Planning Tips",
            ])
        prompt = mock.call_args.args[0]
        assert "How AI Grading Works" in prompt
        assert "Lesson Planning Tips" in prompt

    def test_default_keywords_used_when_none_provided(self):
        from backend.services.seo_service import suggest_blog_topics
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            suggest_blog_topics(["x"])
        prompt = mock.call_args.args[0]
        # Default keywords list includes known terms
        assert "AI grading" in prompt
        assert "K-12" in prompt
        assert "FERPA" in prompt

    def test_custom_keywords_used_when_provided(self):
        from backend.services.seo_service import suggest_blog_topics
        with patch("backend.services.seo_service._call_haiku",
                   return_value={}) as mock:
            suggest_blog_topics([], domain_keywords=["custom-term-1", "another-term"])
        prompt = mock.call_args.args[0]
        assert "custom-term-1" in prompt
        assert "another-term" in prompt
        # Default keywords NOT used (override worked)
        assert "FERPA" not in prompt

    def test_returns_haiku_response(self):
        from backend.services.seo_service import suggest_blog_topics
        expected = {"topics": [{"title": "X", "target_keyword": "y"}]}
        with patch("backend.services.seo_service._call_haiku",
                   return_value=expected):
            result = suggest_blog_topics(["z"])
        assert result == expected
