"""
Tests for the grading pipeline mechanics (grade_multipass, grade_per_question, grade_assignment).

All tests use mocked AI responses — no real API calls.
Verifies that parameters flow correctly and pipeline logic is sound.
"""
import json
import re
import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_per_question_result(score, points, quality="good"):
    """Build a valid grade_per_question return dict."""
    return {
        "grade": {
            "score": score,
            "possible": points,
            "reasoning": "Mock reasoning.",
            "is_correct": score >= points * 0.6,
            "quality": quality,
        },
        "excellent": score >= points * 0.9,
        "improvement_note": "" if score >= points * 0.9 else "Could improve.",
    }


def _mock_feedback_result():
    """Build a valid generate_feedback return dict."""
    return {
        "feedback": "Good work overall. Keep it up.",
        "excellent_answers": ["Q1 was great"],
        "needs_improvement": ["Q3 needs more detail"],
        "skills_demonstrated": {
            "strengths": ["content knowledge"],
            "developing": ["writing clarity"],
        },
    }


def _make_extraction_result(num_responses=4, blank_count=0):
    """Build an extraction result with N responses and M blanks."""
    responses = []
    for i in range(num_responses):
        responses.append({
            "question": f"Question {i+1}",
            "answer": f"This is a test response for question {i+1} with enough content.",
            "type": "numbered_question",
        })
    blanks = [f"Question {num_responses + j + 1}" for j in range(blank_count)]
    return {
        "extracted_responses": responses,
        "answered_questions": num_responses,
        "total_questions": num_responses + blank_count,
        "blank_questions": blanks,
        "missing_sections": [],
    }


# ---------------------------------------------------------------------------
# A. grade_per_question prompt verification
# ---------------------------------------------------------------------------

class TestGradePerQuestionPrompts:
    """Verify that grade_per_question builds prompts with correct content."""

    def _capture_prompt(self, **override_kwargs):
        """Call grade_per_question with mocked OpenAI and return the prompt sent."""
        captured_prompt = {}

        mock_parsed = MagicMock()
        mock_parsed.model_dump.return_value = _mock_per_question_result(8, 10)

        mock_choice = MagicMock()
        mock_choice.message.parsed = mock_parsed

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        def fake_parse(**kwargs):
            captured_prompt["messages"] = kwargs.get("messages", [])
            return mock_response

        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse = fake_parse

        defaults = {
            "question": "What caused the Louisiana Purchase?",
            "student_answer": "Napoleon needed money for wars.",
            "expected_answer": "Napoleon sold because of wars and Haiti revolt.",
            "points": 10,
            "grade_level": "7",
            "subject": "Social Studies",
            "teacher_instructions": "Be encouraging. Accept partial answers.",
            "grading_style": "standard",
            "ai_model": "gpt-4o-mini",
            "ai_provider": "openai",
            "response_type": "numbered_question",
            "section_name": "QUESTIONS",
            "section_type": "written",
        }
        defaults.update(override_kwargs)

        with patch("openai.OpenAI", return_value=mock_client), \
             patch("assignment_grader._get_api_key", return_value="test-key"):
            from assignment_grader import grade_per_question
            grade_per_question(**defaults)

        # Combine system + user messages for full prompt
        full_prompt = ""
        for msg in captured_prompt.get("messages", []):
            full_prompt += msg.get("content", "") + "\n"
        return full_prompt

    def test_per_question_includes_teacher_instructions(self):
        prompt = self._capture_prompt(teacher_instructions="Accept short answers. Be generous.")
        assert "Accept short answers" in prompt
        assert "Be generous" in prompt

    def test_per_question_lenient_style_instructions(self):
        prompt = self._capture_prompt(grading_style="lenient")
        assert "LENIENT" in prompt
        assert "EFFORT" in prompt

    def test_per_question_strict_style_instructions(self):
        prompt = self._capture_prompt(grading_style="strict")
        assert "STRICT" in prompt
        assert "high standards" in prompt

    def test_per_question_standard_style_instructions(self):
        prompt = self._capture_prompt(grading_style="standard")
        assert "STANDARD" in prompt
        assert "Balance" in prompt

    def test_per_question_section_type_vocab(self):
        prompt = self._capture_prompt(response_type="vocab_term")
        assert "VOCABULARY DEFINITION" in prompt
        assert "paraphrasing" in prompt.lower()

    def test_per_question_section_type_fitb(self):
        prompt = self._capture_prompt(response_type="fill_in_blank")
        assert "FILL-IN-THE-BLANK" in prompt
        assert "synonyms" in prompt.lower()

    def test_per_question_expected_answer_included(self):
        prompt = self._capture_prompt(expected_answer="Napoleon needed money for European wars")
        assert "EXPECTED ANSWER" in prompt
        assert "Napoleon needed money" in prompt

    def test_per_question_expected_answer_omitted_when_empty(self):
        prompt = self._capture_prompt(expected_answer="")
        assert "EXPECTED ANSWER" not in prompt


# ---------------------------------------------------------------------------
# B. grade_multipass logic
# ---------------------------------------------------------------------------

class TestGradeMultipassLogic:
    """Test grade_multipass pipeline with mocked extraction and grading."""

    def _run_multipass(self, content="Test content", custom_ai_instructions="",
                       rubric_prompt=None, grading_style="standard",
                       extraction_result=None, per_question_scores=None,
                       effort_points=15):
        """Run grade_multipass with comprehensive mocking."""

        if extraction_result is None:
            extraction_result = _make_extraction_result(4, 0)

        if per_question_scores is None:
            per_question_scores = [8, 7, 9, 6]  # out of variable points

        call_idx = {"i": 0}

        def fake_grade_per_question(**kwargs):
            i = call_idx["i"]
            call_idx["i"] += 1
            pts = kwargs.get("points", 10)
            score = per_question_scores[i] if i < len(per_question_scores) else int(pts * 0.7)
            return _mock_per_question_result(score, pts)

        def fake_generate_feedback(**kwargs):
            return _mock_feedback_result()

        assignment_data = {"type": "text", "content": content}

        with patch("assignment_grader.extract_student_responses", return_value=extraction_result), \
             patch("assignment_grader.extract_from_tables", return_value=None), \
             patch("assignment_grader.extract_from_graider_text", return_value=None), \
             patch("assignment_grader.grade_per_question", side_effect=fake_grade_per_question) as mock_gpq, \
             patch("assignment_grader.generate_feedback", side_effect=fake_generate_feedback), \
             patch("assignment_grader._get_api_key", return_value="test-key"):
            from assignment_grader import grade_multipass
            result = grade_multipass(
                student_name="Test Student",
                assignment_data=assignment_data,
                custom_ai_instructions=custom_ai_instructions,
                grade_level="7",
                subject="Social Studies",
                ai_model="gpt-4o-mini",
                rubric_prompt=rubric_prompt,
                grading_style=grading_style,
                effort_points=effort_points,
            )
            return result, mock_gpq

    def test_multipass_appends_rubric_to_effective_instructions(self):
        """Rubric prompt should be appended to teacher_instructions in per-question calls."""
        rubric_prompt = "GRADING RUBRIC: Content Accuracy (40 points)"
        custom = "Be encouraging."

        result, mock_gpq = self._run_multipass(
            custom_ai_instructions=custom,
            rubric_prompt=rubric_prompt,
        )

        # Check that grade_per_question was called with combined instructions
        for call in mock_gpq.call_args_list:
            teacher_inst = call.kwargs.get("teacher_instructions", "")
            assert "Be encouraging" in teacher_inst
            assert "GRADING RUBRIC" in teacher_inst

    def test_multipass_blank_submission_scores_zero(self):
        """80%+ blank responses → score 0, INCOMPLETE."""
        extraction = _make_extraction_result(num_responses=1, blank_count=4)
        result, _ = self._run_multipass(
            extraction_result=extraction,
            per_question_scores=[5],
        )
        assert result["score"] == 0
        assert result["letter_grade"] == "INCOMPLETE"

    def test_multipass_fully_blank_scores_zero(self):
        """0 answered questions → score 0, INCOMPLETE."""
        extraction = {
            "extracted_responses": [],
            "answered_questions": 0,
            "total_questions": 4,
            "blank_questions": ["Q1", "Q2", "Q3", "Q4"],
            "missing_sections": [],
        }
        result, _ = self._run_multipass(extraction_result=extraction)
        assert result["score"] == 0
        assert result["letter_grade"] == "INCOMPLETE"

    def test_multipass_grading_style_passed_through(self):
        """Each per-question call receives the grading_style."""
        result, mock_gpq = self._run_multipass(grading_style="lenient")
        for call in mock_gpq.call_args_list:
            assert call.kwargs.get("grading_style") == "lenient"

    def test_multipass_returns_valid_structure(self):
        """Result has all required keys."""
        result, _ = self._run_multipass()
        required_keys = ["score", "letter_grade", "breakdown", "feedback",
                         "student_responses", "unanswered_questions",
                         "ai_detection", "plagiarism_detection"]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_multipass_score_in_range(self):
        """Score should be 0-100."""
        result, _ = self._run_multipass()
        assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# C. grade_assignment single-pass
# ---------------------------------------------------------------------------

class TestGradeAssignmentSinglePass:
    """Test grade_assignment with mocked AI responses."""

    def _run_single_pass(self, content="QUESTIONS:\n1) The answer is that Napoleon sold it.\n2) It doubled the size.",
                          custom_ai_instructions="", rubric_prompt=None,
                          grading_style="standard"):
        """Run grade_assignment with mocked OpenAI."""

        mock_response_json = json.dumps({
            "score": 78,
            "letter_grade": "C",
            "breakdown": {
                "content_accuracy": 32,
                "completeness": 20,
                "writing_quality": 14,
                "effort_engagement": 12,
            },
            "feedback": "Good effort overall.",
            "student_responses": ["response 1"],
            "unanswered_questions": [],
            "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
            "plagiarism_detection": {"flag": "none", "reason": ""},
            "skills_demonstrated": {"strengths": ["content"], "developing": ["writing"]},
            "excellent_answers": [],
            "needs_improvement": ["Q3"],
        })

        captured = {"messages": None}

        mock_choice = MagicMock()
        mock_choice.message.content = mock_response_json

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=500, completion_tokens=200, total_tokens=700)

        def fake_create(**kwargs):
            captured["messages"] = kwargs.get("messages", [])
            return mock_response

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create

        # Provide extraction result so grade_assignment doesn't abort as blank
        extraction = _make_extraction_result(2, 0)

        assignment_data = {"type": "text", "content": content}

        with patch("openai.OpenAI", return_value=mock_client), \
             patch("assignment_grader._get_api_key", return_value="test-key"), \
             patch("assignment_grader.extract_student_responses", return_value=extraction):
            from assignment_grader import grade_assignment
            result = grade_assignment(
                student_name="Test Student",
                assignment_data=assignment_data,
                custom_ai_instructions=custom_ai_instructions,
                grade_level="7",
                subject="Social Studies",
                ai_model="gpt-4o-mini",
                rubric_prompt=rubric_prompt,
                grading_style=grading_style,
            )
        return result, captured

    def test_single_pass_includes_custom_instructions(self):
        """custom_ai_instructions should appear in the prompt."""
        result, captured = self._run_single_pass(
            custom_ai_instructions="Accept short answers. Be lenient on vocab."
        )
        full_prompt = " ".join(
            msg.get("content", "") for msg in (captured["messages"] or [])
            if isinstance(msg.get("content"), str)
        )
        assert "Accept short answers" in full_prompt

    def test_single_pass_blank_submission_low_score(self):
        """Empty/blank content should return low score."""
        # grade_assignment checks for blank submissions early
        assignment_data = {"type": "text", "content": "   \n\n   "}

        with patch("assignment_grader._get_api_key", return_value="test-key"):
            from assignment_grader import grade_assignment
            result = grade_assignment(
                student_name="Test",
                assignment_data=assignment_data,
                grade_level="7",
                subject="Social Studies",
            )
        # Blank submissions should get 0 or INCOMPLETE
        assert result["score"] <= 20 or result["letter_grade"] == "INCOMPLETE"


# ---------------------------------------------------------------------------
# D. Cross-subject parametrized tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("subject_key,rubric_type,expected_type_text", [
    ("social_studies", "cornell-notes", "CORNELL NOTES"),
    ("ela", "essay", "ESSAY/WRITTEN RESPONSE"),
    ("math", "fill-in-blank", "FILL-IN-THE-BLANK"),
    ("science", "standard", None),  # standard has no special type text
])
class TestCrossSubjectConfig:
    """Verify configs produce correct rubric type text across subjects."""

    def test_config_rubric_type_matches(self, grading_fixtures, subject_key, rubric_type, expected_type_text):
        config = grading_fixtures["configs"][subject_key]
        assert config["rubricType"] == rubric_type

    def test_config_has_markers_with_points(self, grading_fixtures, subject_key, rubric_type, expected_type_text):
        config = grading_fixtures["configs"][subject_key]
        markers = config.get("customMarkers", [])
        assert len(markers) >= 1
        total_points = sum(m.get("points", 0) for m in markers)
        assert total_points > 0

    def test_config_grading_notes_nonempty(self, grading_fixtures, subject_key, rubric_type, expected_type_text):
        config = grading_fixtures["configs"][subject_key]
        assert len(config.get("gradingNotes", "")) > 20
