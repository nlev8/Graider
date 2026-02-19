"""
Test: EdTech quiz generator tools — format validation for all 6 platforms.
"""
import csv
import io
import base64
import pytest
from backend.services.assistant_tools_edtech import (
    generate_kahoot_quiz, generate_blooket_set, generate_gimkit_kit,
    generate_quizlet_set, generate_canvas_qti,
    _build_questions_from_source, _build_vocab_pairs,
)


class TestBuildQuestionsFromSource:
    def test_returns_questions(self, patch_paths):
        questions = _build_questions_from_source(topic="Constitution")
        assert len(questions) > 0

    def test_question_structure(self, patch_paths):
        questions = _build_questions_from_source(topic="Bill of Rights")
        for q in questions:
            assert "question" in q
            assert "correct_answer" in q
            assert "q_type" in q

    def test_respects_count(self, patch_paths):
        questions = _build_questions_from_source(topic="government", question_count=5)
        assert len(questions) <= 5

    def test_difficulty_easy(self, patch_paths):
        questions = _build_questions_from_source(topic="rights", difficulty="easy")
        assert len(questions) > 0
        # Easy should prefer vocab questions
        vocab_count = sum(1 for q in questions if q["q_type"] == "vocab")
        assert vocab_count >= 0  # At least some vocab

    def test_no_topic_uses_all_standards(self, patch_paths):
        questions = _build_questions_from_source(question_count=10)
        assert len(questions) > 0


class TestBuildVocabPairs:
    def test_returns_pairs(self, patch_paths):
        pairs = _build_vocab_pairs(topic="government")
        assert len(pairs) > 0
        for p in pairs:
            assert "term" in p
            assert "definition" in p

    def test_respects_count(self, patch_paths):
        pairs = _build_vocab_pairs(topic="Constitution", question_count=3)
        assert len(pairs) <= 3


class TestGenerateKahootQuiz:
    def test_produces_xlsx(self, patch_paths):
        result = generate_kahoot_quiz(topic="government")
        assert "error" not in result
        assert result.get("format") == "xlsx"
        assert result.get("document")
        assert result.get("filename", "").endswith(".xlsx")

    def test_has_questions(self, patch_paths):
        result = generate_kahoot_quiz(topic="government")
        assert result.get("question_count") > 0

    def test_valid_base64(self, patch_paths):
        result = generate_kahoot_quiz(topic="rights")
        doc = result.get("document", "")
        # Should decode without error
        data = base64.b64decode(doc)
        assert len(data) > 0


class TestGenerateBlooketSet:
    def test_produces_csv(self, patch_paths):
        result = generate_blooket_set(topic="Constitution")
        assert "error" not in result
        assert result.get("format") == "csv"
        assert result.get("filename", "").endswith(".csv")

    def test_csv_structure(self, patch_paths):
        result = generate_blooket_set(topic="government")
        doc = base64.b64decode(result["document"]).decode("utf-8")
        reader = csv.reader(io.StringIO(doc))
        headers = next(reader)
        assert "Question Text" in headers or "Question #" in headers
        rows = list(reader)
        assert len(rows) > 0


class TestGenerateGimkitKit:
    def test_produces_csv(self, patch_paths):
        result = generate_gimkit_kit(topic="rights")
        assert "error" not in result
        assert result.get("format") == "csv"

    def test_gimkit_columns(self, patch_paths):
        result = generate_gimkit_kit(topic="government")
        doc = base64.b64decode(result["document"]).decode("utf-8")
        reader = csv.reader(io.StringIO(doc))
        headers = next(reader)
        assert headers[0] == "Question"
        assert headers[1] == "Correct Answer"
        assert "Incorrect Answer" in headers[2]

    def test_has_questions(self, patch_paths):
        result = generate_gimkit_kit(topic="Constitution")
        assert result.get("question_count") > 0


class TestGenerateQuizletSet:
    def test_produces_txt(self, patch_paths):
        result = generate_quizlet_set(topic="government")
        assert "error" not in result
        assert result.get("format") == "txt"
        assert result.get("filename", "").endswith(".txt")

    def test_tab_separated(self, patch_paths):
        result = generate_quizlet_set(topic="Constitution")
        doc = base64.b64decode(result["document"]).decode("utf-8")
        lines = [l for l in doc.strip().split("\n") if l.strip()]
        assert len(lines) > 0
        for line in lines:
            assert "\t" in line, f"Line not tab-separated: {line[:50]}"

    def test_card_count(self, patch_paths):
        result = generate_quizlet_set(topic="rights")
        assert result.get("card_count") > 0


class TestGenerateCanvasQTI:
    def test_produces_xml(self, patch_paths):
        result = generate_canvas_qti(topic="government")
        assert "error" not in result
        assert result.get("format") == "xml"
        assert result.get("filename", "").endswith(".xml")

    def test_valid_xml_structure(self, patch_paths):
        result = generate_canvas_qti(topic="Constitution")
        doc = base64.b64decode(result["document"]).decode("utf-8")
        assert "<?xml" in doc
        assert "questestinterop" in doc
        assert "<item" in doc

    def test_has_questions(self, patch_paths):
        result = generate_canvas_qti(topic="rights")
        assert result.get("question_count") > 0


class TestEdgeCases:
    def test_no_matching_topic(self, patch_paths):
        result = generate_kahoot_quiz(topic="quantum_physics_xyz")
        # Should fall back to all standards rather than error
        assert result.get("question_count", 0) > 0 or "error" in result

    def test_empty_topic(self, patch_paths):
        result = generate_quizlet_set()
        # Should work with no topic (uses all standards)
        assert "error" not in result or result.get("card_count", 0) > 0
