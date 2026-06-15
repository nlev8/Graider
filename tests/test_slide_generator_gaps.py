"""Gap-fill tests for backend/services/slide_generator.py.

Audit MAJOR #4 sprint follow-up to PR #323. Companion to existing
`tests/test_slide_generator.py`. Targets the 40 missing LOC
(89.0% baseline → 95%+ goal):

* `generate_slide_content` global_ai_notes prompt block, lesson_plan
  prompt block, instructions block, fence-strip variants (no-newline,
  trailing fence, json prefix), theme fallback when AI omits colors
* `generate_slide_images` CircuitBreakerError suppression branch
* PPTX layout helpers — image rendering paths + speaker_notes on
  image_focus + section_divider layouts (lines 308-309, 509-510,
  524-525, 558-559)

Per dual-rate-limit precedent (PRs #269/#270/#290+): test-only PR
merging on green CI when both Codex (until 2026-05-12) and Gemini
(quota exhausted) unavailable.
"""
from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


MODULE = "backend.services.slide_generator"


# ──────────────────────────────────────────────────────────────────
# generate_slide_content branches
# ──────────────────────────────────────────────────────────────────


_VALID_RESPONSE = {
    "title": "Test",
    "theme": {
        "primary_color": "#1a56db",
        "secondary_color": "#60a5fa",
        "accent": "#dbeafe",
    },
    "slides": [
        {"layout": "title", "title": "Hi", "subtitle": "world"},
    ],
}


def _make_mock_adapter(response_text):
    """Build a mock GeminiAdapter that returns the given response text."""
    from backend.services.llm_adapter.types import (
        LLMResponse, TextPart, Usage,
    )
    mock_resp = LLMResponse(
        content_parts=[TextPart(text=response_text)],
        tool_calls=[],
        usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.0),
        finish_reason="stop",
        provider="gemini",
        model="gemini-2.0-flash",
    )
    mock_adapter = MagicMock()
    mock_adapter.chat.return_value = mock_resp
    return mock_adapter


class TestGenerateSlideContentBranches:
    def test_global_ai_notes_included_in_prompt(self):
        from backend.services.slide_generator import generate_slide_content
        mock_adapter = _make_mock_adapter(json.dumps(_VALID_RESPONSE))

        with patch("backend.services.llm_adapter.GeminiAdapter",
                   return_value=mock_adapter):
            generate_slide_content(
                content="some content", subject="Civics", grade="7",
                title="T", api_key="fake",
                global_ai_notes="be lenient with younger students",
            )

        # Verify the prompt sent to the adapter included the notes
        prompt = mock_adapter.chat.call_args.args[0].messages[0].content[0].text
        assert "TEACHER INSTRUCTIONS (MUST FOLLOW)" in prompt
        assert "lenient with younger students" in prompt

    def test_lesson_plan_block_included(self):
        from backend.services.slide_generator import generate_slide_content
        mock_adapter = _make_mock_adapter(json.dumps(_VALID_RESPONSE))

        lesson_plan = {
            "title": "Bill of Rights",
            "overview": "First 10 amendments",
            "objectives": ["Identify amendments"],
            "vocabulary": ["amendment", "ratify"],
            "essential_questions": ["Why amendments?"],
            "days": [{"day": 1, "topic": "Intro"}],
        }
        with patch("backend.services.llm_adapter.GeminiAdapter",
                   return_value=mock_adapter):
            generate_slide_content(
                content="", subject="Civics", grade="7",
                title="T", api_key="fake", lesson_plan=lesson_plan,
            )

        prompt = mock_adapter.chat.call_args.args[0].messages[0].content[0].text
        assert "=== LESSON PLAN ===" in prompt
        assert "Bill of Rights" in prompt
        assert "Identify amendments" in prompt
        assert "amendment, ratify" in prompt
        assert "Why amendments?" in prompt
        assert "Day 1: Intro" in prompt

    def test_instructions_appended_to_prompt(self):
        from backend.services.slide_generator import generate_slide_content
        mock_adapter = _make_mock_adapter(json.dumps(_VALID_RESPONSE))

        with patch("backend.services.llm_adapter.GeminiAdapter",
                   return_value=mock_adapter):
            generate_slide_content(
                content="content", subject="X", grade="7",
                title="T", api_key="fake",
                instructions="emphasize visuals over text",
            )

        prompt = mock_adapter.chat.call_args.args[0].messages[0].content[0].text
        assert "Additional instructions: emphasize visuals over text" in prompt

    def test_fence_strip_no_newline(self):
        # Response is just ```{...}``` with no newline after opening
        from backend.services.slide_generator import generate_slide_content
        # `text.startswith("```")` then `text[3:]` if no newline
        wrapped = "```" + json.dumps(_VALID_RESPONSE) + "```"
        mock_adapter = _make_mock_adapter(wrapped)

        with patch("backend.services.llm_adapter.GeminiAdapter",
                   return_value=mock_adapter):
            result = generate_slide_content(
                content="x", subject="X", grade="7",
                title="T", api_key="fake",
            )
        assert result["title"] == "Test"

    def test_json_prefix_stripped(self):
        # Gemini quality-review MAJOR fold: pre-fix wrapped in
        # ```json\n...\n``` would be intercepted by the
        # `startswith("```")` branch FIRST (which splits on \n,
        # dropping the "json" line entirely). The
        # `startswith("json")` branch never ran.
        #
        # Bare `json\n{...}` (no markdown fences) exercises the
        # targeted prefix-strip branch directly.
        from backend.services.slide_generator import generate_slide_content
        wrapped = "json\n" + json.dumps(_VALID_RESPONSE)
        mock_adapter = _make_mock_adapter(wrapped)

        with patch("backend.services.llm_adapter.GeminiAdapter",
                   return_value=mock_adapter):
            result = generate_slide_content(
                content="x", subject="X", grade="7",
                title="T", api_key="fake",
            )
        assert result["title"] == "Test"

    def test_theme_fallback_when_ai_omits_colors(self):
        # AI returned slides but no primary_color → fallback to defaults
        from backend.services.slide_generator import generate_slide_content
        no_theme_response = {
            "title": "No Theme",
            "theme": {},  # empty, no primary_color
            "slides": [{"layout": "title", "title": "Hi"}],
        }
        mock_adapter = _make_mock_adapter(json.dumps(no_theme_response))

        with patch("backend.services.llm_adapter.GeminiAdapter",
                   return_value=mock_adapter):
            result = generate_slide_content(
                content="x", subject="X", grade="7",
                title="T", api_key="fake",
            )
        # Fallback colors injected
        assert result["theme"]["primary_color"] == "#1a56db"
        assert result["theme"]["secondary_color"] == "#60a5fa"
        assert result["theme"]["accent"] == "#dbeafe"
        # style_prompt is now composed from the selected template's structured
        # ImageStyle (spec §5), decoupled from the AI's per-deck colors; the
        # default template resolves to Minimal. Verify the composition ran.
        assert "No text in the image" in result["theme"]["style_prompt"]


# ──────────────────────────────────────────────────────────────────
# generate_slide_images CircuitBreakerError suppression
# ──────────────────────────────────────────────────────────────────


class TestGenerateSlideImagesBreaker:
    def test_circuit_breaker_error_does_not_capture_to_sentry(
        self, monkeypatch,
    ):
        # When the breaker is OPEN, every image call raises
        # CircuitBreakerError. The slide generator should still log a
        # warning but NOT capture to Sentry (alert fatigue prevention).
        from backend.services.slide_generator import generate_slide_images
        import pybreaker

        slides = [{"layout": "content", "image_prompt": "draw"}]
        theme = {"style_prompt": "x", "primary_color": "#000"}

        def raise_breaker(self, request):
            raise pybreaker.CircuitBreakerError("breaker OPEN")

        monkeypatch.setattr(
            "backend.services.llm_adapter.gemini_adapter.GeminiAdapter."
            "generate_image", raise_breaker,
        )
        monkeypatch.setattr(
            "backend.services.llm_adapter.gemini_adapter.genai.Client",
            lambda api_key=None: object(),
        )

        with patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            images = generate_slide_images(
                slides, theme, api_key="fake", max_images=5,
            )

        # No images generated (all raised)
        assert images == {}
        # Sentry NOT called for CircuitBreakerError
        mock_sentry.assert_not_called()

    def test_non_breaker_exception_captures_to_sentry(self, monkeypatch):
        from backend.services.slide_generator import generate_slide_images

        slides = [{"layout": "content", "image_prompt": "draw"}]
        theme = {"style_prompt": "x", "primary_color": "#000"}

        def raise_other(self, request):
            raise RuntimeError("API error")

        monkeypatch.setattr(
            "backend.services.llm_adapter.gemini_adapter.GeminiAdapter."
            "generate_image", raise_other,
        )
        monkeypatch.setattr(
            "backend.services.llm_adapter.gemini_adapter.genai.Client",
            lambda api_key=None: object(),
        )

        with patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            images = generate_slide_images(
                slides, theme, api_key="fake", max_images=5,
            )

        assert images == {}
        # Sentry IS called for non-breaker exceptions
        mock_sentry.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# PPTX layout edges - image + speaker_notes paths
# ──────────────────────────────────────────────────────────────────


def _make_image_bytes():
    """Build a tiny valid PNG image."""
    from PIL import Image
    img = Image.new("RGB", (100, 56), "white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPptxLayoutEdges:
    def test_title_slide_with_image_and_speaker_notes(self, tmp_path):
        from backend.services.slide_generator import assemble_pptx

        slides = [{
            "layout": "title", "title": "Hello",
            "subtitle": "World",
            "speaker_notes": "Welcome the class",
        }]
        theme = {
            "primary_color": "#1a56db", "secondary_color": "#60a5fa",
            "accent": "#dbeafe",
        }
        images = {0: _make_image_bytes()}

        filepath = tmp_path / "out.pptx"
        assemble_pptx(slides, theme, "T", images, str(filepath))
        assert filepath.exists()

    def test_image_focus_slide_with_image_and_caption(self, tmp_path):
        from backend.services.slide_generator import assemble_pptx

        slides = [{
            "layout": "image_focus",
            "title": "Visualize",
            "caption": "A diagram",
            "speaker_notes": "Explain the diagram",
        }]
        theme = {"primary_color": "#1a56db",
                 "secondary_color": "#60a5fa", "accent": "#dbeafe"}
        images = {0: _make_image_bytes()}

        filepath = tmp_path / "img_focus.pptx"
        assemble_pptx(slides, theme, "T", images, str(filepath))
        assert filepath.exists()

    def test_section_divider_with_speaker_notes(self, tmp_path):
        from backend.services.slide_generator import assemble_pptx

        slides = [{
            "layout": "section_divider",
            "title": "Part 2",
            "speaker_notes": "Transition to part 2",
        }]
        theme = {"primary_color": "#1a56db",
                 "secondary_color": "#60a5fa", "accent": "#dbeafe"}

        filepath = tmp_path / "section.pptx"
        assemble_pptx(slides, theme, "T", {}, str(filepath))
        assert filepath.exists()

    def test_image_focus_no_image_no_caption(self, tmp_path):
        # Image_focus without an image or caption — both branches skipped
        from backend.services.slide_generator import assemble_pptx

        slides = [{
            "layout": "image_focus",
            "title": "Just text",
        }]
        theme = {"primary_color": "#1a56db",
                 "secondary_color": "#60a5fa", "accent": "#dbeafe"}
        filepath = tmp_path / "nfo.pptx"
        assemble_pptx(slides, theme, "T", {}, str(filepath))
        assert filepath.exists()
