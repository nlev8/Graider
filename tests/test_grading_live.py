"""
Live API tests for the grading pipeline.

These tests make REAL API calls and require OPENAI_API_KEY.
Run with: pytest tests/test_grading_live.py -m live -v

Skipped automatically if OPENAI_API_KEY is not set.
"""
import os
import json
import pytest

pytestmark = pytest.mark.live

# Auto-skip if no API key
if not os.environ.get("OPENAI_API_KEY"):
    # Also check .env file
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
    except ImportError:
        pass

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping live tests", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name):
    """Load a fixture file from tests/fixtures/grading/."""
    fpath = os.path.join(os.path.dirname(__file__), "fixtures", "grading", name)
    if name.endswith(".json"):
        with open(fpath) as f:
            return json.load(f)
    with open(fpath) as f:
        return f.read()


def _grade_per_question_live(question, answer, expected="", points=10,
                              grade_level="7", subject="Social Studies",
                              teacher_instructions="", grading_style="standard"):
    """Call the real grade_per_question with OpenAI."""
    from assignment_grader import grade_per_question
    return grade_per_question(
        question=question,
        student_answer=answer,
        expected_answer=expected,
        points=points,
        grade_level=grade_level,
        subject=subject,
        teacher_instructions=teacher_instructions,
        grading_style=grading_style,
        ai_model="gpt-4o-mini",
        ai_provider="openai",
        response_type="numbered_question",
        section_name="",
        section_type="written",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLiveGradePerQuestion:
    """Live tests for grade_per_question."""

    def test_live_grade_per_question_valid_score(self):
        """Real API call returns a score in valid range."""
        result = _grade_per_question_live(
            question="Why did Napoleon sell the Louisiana Territory?",
            answer="Napoleon needed money for his wars in Europe and he lost control of Haiti.",
            expected="Napoleon sold because of wars in Europe and the loss of Haiti.",
            points=10,
        )
        assert "grade" in result
        score = result["grade"]["score"]
        assert 0 <= score <= 10

    def test_live_lenient_higher_than_strict(self):
        """Same mediocre answer: lenient should score >= strict."""
        question = "Explain the significance of the Louisiana Purchase."
        answer = "It was important because it made the US bigger."

        lenient = _grade_per_question_live(
            question=question, answer=answer, points=10, grading_style="lenient"
        )
        strict = _grade_per_question_live(
            question=question, answer=answer, points=10, grading_style="strict"
        )

        lenient_score = lenient["grade"]["score"]
        strict_score = strict["grade"]["score"]
        # Lenient should be >= strict (with some tolerance for AI variance)
        assert lenient_score >= strict_score - 2, (
            f"Lenient ({lenient_score}) should be >= strict ({strict_score})"
        )


class TestLiveCustomRubric:
    """Live tests for custom rubric influence."""

    def test_live_global_notes_floor(self):
        """Teacher note 'minimum 85 if all answered' should push score up."""
        result = _grade_per_question_live(
            question="What is a treaty?",
            answer="A treaty is when two countries agree on something official.",
            expected="An official agreement between countries.",
            points=10,
            teacher_instructions="Be very generous. If the student attempted an answer, give at least 85% credit.",
        )
        score = result["grade"]["score"]
        # With strong floor instruction, should get high score
        assert score >= 7, f"Expected >= 7 with floor instruction, got {score}"


class TestLiveBlankSubmission:
    """Live tests for blank/empty submissions."""

    def test_live_blank_submission_low_score(self):
        """Blank answer should score 0."""
        result = _grade_per_question_live(
            question="Describe the process of photosynthesis.",
            answer="",
            points=10,
        )
        assert result["grade"]["score"] == 0


class TestLiveBatchConsistency:
    """Live tests for grading consistency."""

    def test_live_batch_regrade_consistency(self):
        """Same question graded twice should be within 3 points of each other."""
        kwargs = dict(
            question="How did the Louisiana Purchase affect the size of the United States?",
            answer="The Louisiana Purchase doubled the size of the US by adding territory west of the Mississippi.",
            expected="Doubled the size, added 828,000 square miles west of Mississippi.",
            points=10,
            grading_style="standard",
        )

        score1 = _grade_per_question_live(**kwargs)["grade"]["score"]
        score2 = _grade_per_question_live(**kwargs)["grade"]["score"]

        assert abs(score1 - score2) <= 3, (
            f"Scores should be within 3 points: {score1} vs {score2}"
        )


@pytest.mark.parametrize("subject_key,subject_name,question,answer", [
    ("social_studies", "Social Studies",
     "Why did Napoleon sell the Louisiana Territory?",
     "He needed money for wars and lost Haiti."),
    ("ela", "English/ELA",
     "What is the main theme of To Kill a Mockingbird?",
     "The theme is moral courage, shown through Atticus defending Tom Robinson."),
    ("math", "Math",
     "Solve: 3x + 7 = 22",
     "3x = 15, x = 5"),
    ("science", "Science",
     "What is photosynthesis?",
     "Photosynthesis is when plants use sunlight, water and CO2 to make glucose and oxygen."),
])
class TestLivePerSubjectScores:
    """Verify reasonable scores across different subjects."""

    def test_live_per_subject_reasonable_score(self, subject_key, subject_name, question, answer):
        """Each subject should produce a reasonable score (4-10 out of 10)."""
        result = _grade_per_question_live(
            question=question,
            answer=answer,
            points=10,
            subject=subject_name,
            grade_level="7",
        )
        score = result["grade"]["score"]
        assert 4 <= score <= 10, f"{subject_name}: expected 4-10, got {score}"
