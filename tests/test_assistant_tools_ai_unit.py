"""Unit tests for backend/services/assistant_tools_ai.py.

Audit MAJOR #4 sprint follow-up. Targets 108 uncovered LOC (10% baseline).

Strategy
--------
Same proven pattern as PR #251 (assistant_tools_grading), PR #261
(assistant_tools_data), PR #263 (email_service), and PR #264 (seo_service):

* Mock `_call_haiku` at the module level for public-function tests so we
  exercise prompt assembly and return-shape forwarding without a real API call.
* Mock `backend.api_keys.get_api_key` + `backend.services.llm_adapter.AnthropicAdapter`
  for `_call_haiku` itself, covering all four branches: missing key, happy
  path, markdown-fence stripping, JSON decode error, generic adapter exception.
* For `generate_iep_progress_notes`, mock the local-data loaders so we can
  exercise the "no data → error", master-CSV path, results path, accommodations
  path, and trend computation. Also pin the anonymize → deanonymize round-trip.

Per `feedback_codex_always_high_effort.md` standing directive, the merge
review uses Codex high-effort.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# _call_haiku — internal helper
# ──────────────────────────────────────────────────────────────────


class TestCallHaiku:
    def test_no_api_key_returns_error(self):
        from backend.services.assistant_tools_ai import _call_haiku

        with patch("backend.api_keys.get_api_key", return_value=None):
            result = _call_haiku("test prompt")
        assert "error" in result
        assert "ANTHROPIC_API_KEY not configured" in result["error"]

    def test_happy_path_returns_parsed_json(self):
        from backend.services.assistant_tools_ai import _call_haiku

        mock_response = MagicMock()
        mock_response.content_parts = [
            MagicMock(text='{"versions": [{"level": "on", "text": "x"}]}')
        ]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("differentiate this")
        assert result == {"versions": [{"level": "on", "text": "x"}]}

    def test_strips_markdown_code_fences(self):
        from backend.services.assistant_tools_ai import _call_haiku

        wrapped = "```json\n{\"foo\": \"bar\"}\n```"
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text=wrapped)]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert result == {"foo": "bar"}

    def test_strips_unlabeled_code_fences(self):
        # The fence-strip handles plain ``` (no language tag) too.
        from backend.services.assistant_tools_ai import _call_haiku

        wrapped = "```\n{\"k\": 1}\n```"
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text=wrapped)]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert result == {"k": 1}

    def test_strips_single_line_fenced_response(self):
        # PR #267 Codex round-1 MINOR fold + Rule #11 production fix:
        # Previously a single-line fenced response (no newline) caused
        # `text.index("\n")` to raise ValueError, swallowed by the generic
        # exception handler with the unhelpful message "substring not found".
        # Hardened: malformed fences strip leading/trailing backticks and
        # fall through to json.loads.
        from backend.services.assistant_tools_ai import _call_haiku

        wrapped = "```{\"single_line\": true}```"
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text=wrapped)]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert result == {"single_line": True}

    def test_malformed_fence_falls_through_to_json_error(self):
        # Confirms the malformed-fence branch produces a clean JSONDecodeError
        # path with `raw` set, instead of a cryptic "substring not found".
        from backend.services.assistant_tools_ai import _call_haiku

        wrapped = "```not valid json at all```"
        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text=wrapped)]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert "error" in result
        assert "non-JSON" in result["error"]
        # `raw` reflects post-fence-strip text, so the leading/trailing
        # backticks are gone but the inner garbage remains
        assert "not valid json at all" in result.get("raw", "")
        assert "substring not found" not in result["error"]

    def test_invalid_json_returns_error_with_raw(self):
        from backend.services.assistant_tools_ai import _call_haiku

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
        from backend.services.assistant_tools_ai import _call_haiku

        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.side_effect = RuntimeError("API down")
            result = _call_haiku("x")
        assert "error" in result
        assert "AI call failed" in result["error"]
        assert "API down" in result["error"]

    def test_empty_content_parts_treated_as_blank_text(self):
        # When `response.content_parts` is empty, text == "" → JSONDecodeError
        # path with raw == "".
        from backend.services.assistant_tools_ai import _call_haiku

        mock_response = MagicMock()
        mock_response.content_parts = []
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            result = _call_haiku("x")
        assert "error" in result
        assert "non-JSON" in result["error"]
        assert result.get("raw", "") == ""

    def test_max_tokens_threaded_through(self):
        # Confirm the max_tokens kwarg actually reaches the adapter.
        from backend.services.assistant_tools_ai import _call_haiku

        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text="{}")]
        with patch("backend.api_keys.get_api_key", return_value="sk-test"), \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            _call_haiku("x", max_tokens=4242)
            req = MockAdapter.return_value.chat.call_args.args[0]
        assert req.max_tokens == 4242

    def test_teacher_id_threaded_to_get_api_key(self):
        # Confirm tenant id is forwarded to api_keys.get_api_key().
        from backend.services.assistant_tools_ai import _call_haiku

        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text="{}")]
        with patch("backend.api_keys.get_api_key", return_value="sk-test") as mock_get_key, \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            _call_haiku("x", teacher_id="teach-42")
        mock_get_key.assert_called_once_with("anthropic", "teach-42")

    def test_default_teacher_id_is_local_dev(self):
        from backend.services.assistant_tools_ai import _call_haiku

        mock_response = MagicMock()
        mock_response.content_parts = [MagicMock(text="{}")]
        with patch("backend.api_keys.get_api_key", return_value="sk-test") as mock_get_key, \
             patch("backend.services.llm_adapter.AnthropicAdapter") as MockAdapter:
            MockAdapter.return_value.chat.return_value = mock_response
            _call_haiku("x")
        # When teacher_id is None, the helper falls back to 'local-dev'.
        mock_get_key.assert_called_once_with("anthropic", "local-dev")


# ──────────────────────────────────────────────────────────────────
# differentiate_content
# ──────────────────────────────────────────────────────────────────


class TestDifferentiateContent:
    def test_empty_text_returns_error(self):
        from backend.services.assistant_tools_ai import differentiate_content

        result = differentiate_content(text="", teacher_id="teach-1")
        assert "error" in result
        assert "text is required" in result["error"]

    def test_whitespace_only_text_returns_error_without_calling_haiku(self):
        # PR #267 Codex round-1 MINOR fold: assert _call_haiku is NOT invoked.
        # Previously, with no API key set, a missing `.strip()` validation in
        # production would still satisfy `"error" in result` because _call_haiku
        # itself returns an error dict. That made this test smoke-only.
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku") as mock_haiku:
            result = differentiate_content(text="   \n\t  ", teacher_id="teach-1")
        assert result == {"error": "text is required"}
        mock_haiku.assert_not_called()

    def test_default_levels_in_prompt(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={"versions": []}) as mock:
            differentiate_content(
                text="The water cycle is the continuous movement of water.",
                teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        # Default levels = ['below', 'on', 'above'] — joined by ', '
        assert "below, on, above" in prompt
        assert "The water cycle" in prompt

    def test_custom_levels_in_prompt(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={"versions": []}) as mock:
            differentiate_content(
                text="content",
                levels=["easy", "medium", "hard"],
                teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "easy, medium, hard" in prompt

    def test_grade_level_in_prompt(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            differentiate_content(
                text="x", grade_level="11th", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "11th-grade classroom" in prompt

    def test_default_grade_level_is_6th(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            differentiate_content(text="x", teacher_id="teach-1")
        prompt = mock.call_args.args[0]
        assert "6th-grade classroom" in prompt

    def test_uses_2000_max_tokens(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            differentiate_content(text="x", teacher_id="teach-1")
        max_tokens = mock.call_args.kwargs.get("max_tokens")
        assert max_tokens == 2000

    def test_threads_teacher_id_to_haiku(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            differentiate_content(text="x", teacher_id="teach-tenant-9")
        assert mock.call_args.kwargs.get("teacher_id") == "teach-tenant-9"

    def test_passes_through_haiku_result(self):
        from backend.services.assistant_tools_ai import differentiate_content

        canned = {"versions": [{"level": "on", "text": "rewritten"}]}
        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value=canned):
            result = differentiate_content(text="x", teacher_id="teach-1")
        assert result == canned

    def test_passes_through_haiku_error(self):
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={"error": "AI down"}):
            result = differentiate_content(text="x", teacher_id="teach-1")
        assert result == {"error": "AI down"}


# ──────────────────────────────────────────────────────────────────
# generate_questions_from_text
# ──────────────────────────────────────────────────────────────────


class TestGenerateQuestionsFromText:
    def test_empty_text_returns_error(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        result = generate_questions_from_text(text="", teacher_id="teach-1")
        assert "error" in result
        assert "text is required" in result["error"]

    def test_default_count_5_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(
                text="A passage about photosynthesis.",
                teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Generate 5 questions" in prompt
        assert "photosynthesis" in prompt

    def test_custom_count_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(
                text="x", count=12, teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Generate 12 questions" in prompt

    def test_default_question_types_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(text="x", teacher_id="teach-1")
        prompt = mock.call_args.args[0]
        # All four default types listed
        for t in ("recall", "inference", "analysis", "evaluation"):
            assert t in prompt

    def test_custom_question_types_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(
                text="x", types=["recall", "analysis"], teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "recall, analysis" in prompt

    def test_grade_level_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(
                text="x", grade_level="9th", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "9th-grade students" in prompt

    def test_uses_2000_max_tokens(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(text="x", teacher_id="teach-1")
        assert mock.call_args.kwargs.get("max_tokens") == 2000

    def test_threads_teacher_id(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_questions_from_text(text="x", teacher_id="teach-77")
        assert mock.call_args.kwargs.get("teacher_id") == "teach-77"

    def test_passes_through_haiku_result(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        canned = {"questions": [{"question": "Q?", "type": "recall", "answer_key": "A"}]}
        with patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value=canned):
            result = generate_questions_from_text(text="x", teacher_id="teach-1")
        assert result == canned


# ──────────────────────────────────────────────────────────────────
# generate_iep_progress_notes
# ──────────────────────────────────────────────────────────────────


def _patch_loaders(*, master=None, results=None, accommodations=None, roster=None):
    """Helper to patch all four local-data loaders at once."""
    return [
        patch("backend.services.assistant_tools_ai._load_master_csv",
              return_value=master or []),
        patch("backend.services.assistant_tools_ai._load_results",
              return_value=results or []),
        patch("backend.services.assistant_tools_ai._load_accommodations",
              return_value=accommodations or {}),
        patch("backend.services.assistant_tools_ai._load_roster",
              return_value=roster or []),
    ]


class TestGenerateIepProgressNotes:
    def test_empty_student_name_returns_error(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        result = generate_iep_progress_notes(student_name="", teacher_id="teach-1")
        assert "error" in result
        assert "student_name is required" in result["error"]

    def test_no_grade_data_returns_error(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]):
            result = generate_iep_progress_notes(
                student_name="Jane Doe", teacher_id="teach-1",
            )
        assert "error" in result
        assert "No grade data found" in result["error"]
        assert "Jane Doe" in result["error"]

    def test_master_csv_data_builds_prompt(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [
            {"Student Name": "Jane Doe", "Score": "85", "Assignment": "Quiz 1"},
            {"Student Name": "Jane Doe", "Score": "90", "Assignment": "Quiz 2"},
            {"Student Name": "Other Student", "Score": "70", "Assignment": "Quiz 1"},
        ]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={"progress_notes": []}) as mock:
            generate_iep_progress_notes(
                student_name="Jane Doe", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Jane Doe" in prompt
        # Both Jane's assignments should appear; "Other Student" should not
        assert "Quiz 1: 85%" in prompt or "Quiz 1: 85" in prompt
        assert "Quiz 2: 90" in prompt
        assert "Other Student" not in prompt

    def test_trend_improving_when_recent_higher(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        # earlier=[60,65,70], recent=[85,90,95] → improving
        master = [
            {"Student Name": "Stu", "Score": str(s), "Assignment": f"A{i}"}
            for i, s in enumerate([60, 65, 70, 75, 80, 85, 90, 95])
        ]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Trend: improving" in prompt

    def test_trend_declining_when_recent_lower(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        # earlier=[95,90,85], recent=[60,55,50] → declining
        master = [
            {"Student Name": "Stu", "Score": str(s), "Assignment": f"A{i}"}
            for i, s in enumerate([95, 90, 85, 80, 75, 60, 55, 50])
        ]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Trend: declining" in prompt

    def test_trend_omitted_when_fewer_than_three_scores(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        # 2 scores → branch `len(scores_only) >= 3` is False, no Trend line
        master = [
            {"Student Name": "Stu", "Score": "70", "Assignment": "A1"},
            {"Student Name": "Stu", "Score": "80", "Assignment": "A2"},
        ]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Trend:" not in prompt

    def test_results_data_renders_rubric_breakdown(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        results = [{
            "student_name": "Stu",
            "assignment": "Essay 1",
            "score": 85,
            "content_score": 90,
            "completeness_score": 80,
            "writing_score": 85,
        }]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=results), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "Essay 1" in prompt
        assert "content=90" in prompt
        assert "completeness=80" in prompt
        assert "writing=85" in prompt

    def test_accommodations_data_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "85", "Assignment": "Q1"}]
        accommodations = {
            "Stu": {
                "presets": ["extended_time", "small_group"],
                "notes": "Prefers visuals",
            },
        }
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations",
                   return_value=accommodations), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "extended_time" in prompt
        assert "Prefers visuals" in prompt

    def test_goal_area_filter_in_prompt(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock:
            generate_iep_progress_notes(
                student_name="Stu",
                goal_area="reading comprehension",
                teacher_id="teach-1",
            )
        prompt = mock.call_args.args[0]
        assert "reading comprehension" in prompt
        assert "Focus specifically" in prompt

    def test_audit_tool_action_called_with_send_ai(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action") as mock_audit, \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _roster: (text, {})), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}):
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-tenant-9",
            )
        # Confirms compliance audit fired with correct event tag.
        mock_audit.assert_called_once_with(
            "teach-tenant-9", "generate_iep_progress_notes", "SEND_AI"
        )

    def test_anonymize_called_with_roster(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        roster = [{"name": "Stu", "id": "s1"}]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=roster), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   side_effect=lambda text, _r: (text, {})) as mock_anon, \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}):
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        # Roster is reshaped to [{"student_name": "Stu"}] before passing
        roster_arg = mock_anon.call_args.args[1]
        assert roster_arg == [{"student_name": "Stu"}]

    def test_anonymized_prompt_sent_to_haiku_not_raw_pii(self):
        # PR #267 Codex round-1 MAJOR fold: pin that the *anonymized* prompt
        # is what reaches _call_haiku. A regression that called
        # `_call_haiku(prompt_text, ...)` instead of
        # `_call_haiku(anon_prompt, ...)` would leak PII to the external AI.
        # Without this assertion the prior round-trip test would still pass.
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster",
                   return_value=[{"name": "Stu"}]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   return_value=("ANONYMIZED_SAFE_PROMPT", {"S1": "Stu"})), \
             patch("backend.services.assistant_tools_ai.deanonymize",
                   side_effect=lambda s, m: s), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock_haiku:
            generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        # First positional arg to _call_haiku must be the anonymized prompt
        sent_prompt = mock_haiku.call_args.args[0]
        assert sent_prompt == "ANONYMIZED_SAFE_PROMPT", (
            f"Expected anonymized prompt sent to AI; got {sent_prompt!r}"
        )
        # Hard PII-leak guard: the raw student name must not appear in the
        # prompt that left the process boundary.
        assert "Stu" not in sent_prompt, (
            f"PII leak: student name 'Stu' in prompt: {sent_prompt!r}"
        )

    def test_deanonymize_round_trip_restores_names(self):
        # anonymize replaces "Stu" → "S1" in the prompt, then the AI response
        # comes back with "S1". deanonymize turns that back into "Stu".
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        ai_response = {
            "student_name": "S1",
            "progress_notes": [{"narrative": "S1 is making progress"}],
        }
        # anonymize_for_ai returns (anon_text, mapping) — we set mapping
        # so that deanonymize will substitute S1 → Stu.
        mapping = {"S1": "Stu"}
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster",
                   return_value=[{"name": "Stu"}]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   return_value=("anon prompt", mapping)), \
             patch("backend.services.assistant_tools_ai.deanonymize",
                   side_effect=lambda s, m: s.replace("S1", "Stu")), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value=ai_response):
            result = generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        # The deanonymized response should reference "Stu" again, not "S1"
        assert result["student_name"] == "Stu"
        assert "Stu" in result["progress_notes"][0]["narrative"]

    def test_deanonymize_skip_when_response_is_error(self):
        # If _call_haiku returns an error dict, the deanonymize-then-reload
        # branch still runs but should not blow up.
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   return_value=("p", {"X": "Stu"})), \
             patch("backend.services.assistant_tools_ai.deanonymize",
                   side_effect=lambda s, m: s), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={"error": "AI down"}):
            result = generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        # Error dict survives the deanonymize round-trip
        assert result == {"error": "AI down"}

    def test_deanonymize_handles_invalid_json_round_trip(self):
        # If `deanonymize` produces a string that no longer parses as JSON,
        # the function falls back to the original `result`.
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        master = [{"Student Name": "Stu", "Score": "80", "Assignment": "Q1"}]
        original_result = {"student_name": "S1", "progress_notes": []}
        with patch("backend.services.assistant_tools_ai._load_master_csv", return_value=master), \
             patch("backend.services.assistant_tools_ai._load_results", return_value=[]), \
             patch("backend.services.assistant_tools_ai._load_accommodations", return_value={}), \
             patch("backend.services.assistant_tools_ai._load_roster", return_value=[]), \
             patch("backend.services.assistant_tools_ai.audit_tool_action"), \
             patch("backend.services.assistant_tools_ai.anonymize_for_ai",
                   return_value=("p", {"S1": "Stu"})), \
             patch("backend.services.assistant_tools_ai.deanonymize",
                   side_effect=lambda s, m: "{not valid json}"), \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value=original_result):
            result = generate_iep_progress_notes(
                student_name="Stu", teacher_id="teach-1",
            )
        # Falls back to original (pre-deanonymize) result
        assert result == original_result


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract pin (see PR #251 / #261 / #264 pattern)
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    """Pin that every public tool actually invokes require_teacher_id().

    require_teacher_id is the cross-tenant safety contract — these tests
    ensure that adding a new tool to the module without wiring it through
    the contract would fail.
    """

    def test_differentiate_content_calls_require_teacher_id(self):
        # PR #267 Codex round-1 MAJOR fold: also patch _call_haiku so this
        # contract test cannot leak into a real Anthropic API call when run
        # in an environment with ANTHROPIC_API_KEY set.
        from backend.services.assistant_tools_ai import differentiate_content

        with patch("backend.services.assistant_tools_ai.require_teacher_id") as mock_req, \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock_haiku:
            differentiate_content(text="x", teacher_id="t")
        mock_req.assert_called_once_with("t")
        # Also verify _call_haiku was reached (i.e. require_teacher_id didn't
        # short-circuit) — this is the order the contract guarantees.
        mock_haiku.assert_called_once()

    def test_generate_questions_calls_require_teacher_id(self):
        from backend.services.assistant_tools_ai import generate_questions_from_text

        with patch("backend.services.assistant_tools_ai.require_teacher_id") as mock_req, \
             patch("backend.services.assistant_tools_ai._call_haiku",
                   return_value={}) as mock_haiku:
            generate_questions_from_text(text="x", teacher_id="t")
        mock_req.assert_called_once_with("t")
        mock_haiku.assert_called_once()

    def test_generate_iep_progress_notes_calls_require_teacher_id(self):
        from backend.services.assistant_tools_ai import generate_iep_progress_notes

        # Empty student name short-circuits before _call_haiku is reached, so
        # we don't need to patch _call_haiku here — the early return
        # `{"error": "student_name is required"}` prevents any AI call.
        with patch("backend.services.assistant_tools_ai.require_teacher_id") as mock_req:
            generate_iep_progress_notes(student_name="", teacher_id="t")
        mock_req.assert_called_once_with("t")


# ──────────────────────────────────────────────────────────────────
# Module-level exports
# ──────────────────────────────────────────────────────────────────


class TestExports:
    def test_tool_definitions_lists_all_three_tools(self):
        from backend.services.assistant_tools_ai import AI_TOOL_DEFINITIONS

        names = {td["name"] for td in AI_TOOL_DEFINITIONS}
        assert names == {
            "differentiate_content",
            "generate_questions_from_text",
            "generate_iep_progress_notes",
        }

    def test_tool_handlers_map_matches_definitions(self):
        from backend.services.assistant_tools_ai import (
            AI_TOOL_DEFINITIONS, AI_TOOL_HANDLERS,
        )

        defined = {td["name"] for td in AI_TOOL_DEFINITIONS}
        handled = set(AI_TOOL_HANDLERS.keys())
        assert defined == handled, (
            f"Tool registry drift: definitions={defined}, handlers={handled}"
        )

    def test_tool_handlers_are_callable(self):
        from backend.services.assistant_tools_ai import AI_TOOL_HANDLERS

        for name, handler in AI_TOOL_HANDLERS.items():
            assert callable(handler), f"Handler for {name} is not callable"
