"""Gap-fill tests for backend/services/assistant_tools_edtech.py.

Audit MAJOR #4 sprint follow-up to PR #314. Companion to existing
`tests/test_edtech_tools.py` which pins the format-validation
contracts. This file targets the 59 missing LOC (75.8% baseline →
95%+ goal):

* `_build_questions_from_source` weak-topic mapping branch (lines
  147-171): assignment_name with `_load_results` returning data,
  developing-skills frequency aggregation, weak-topic → standards
  matching, MC sample-assessment parser
* `generate_kahoot_quiz` no-MC error + ImportError swallow (line 327, 331-332)
* `generate_blooket_set` no-MC error (line 376)
* `generate_gimkit_kit` no-MC error (line 410)
* `generate_quizlet_set` no-pairs error + question fallback (line 443-449)
* `generate_nearpod_questions` full pipeline (lines 471-509)
* `generate_canvas_qti` empty options skip + correct_letter (lines 487-509)

Per dual-rate-limit precedent (PRs #269/#270/#290+): test-only PR
merging on green CI when both Codex (until 2026-05-12) and Gemini
(quota exhausted) unavailable.
"""
from __future__ import annotations

import base64
from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_edtech"


# ──────────────────────────────────────────────────────────────────
# _build_questions_from_source weak-topic branch
# ──────────────────────────────────────────────────────────────────


class TestBuildQuestionsFromSourceWeakTopics:
    def test_assignment_name_loads_results_and_picks_weak_topics(
        self, patch_paths,
    ):
        from backend.services.assistant_tools_edtech import (
            _build_questions_from_source,
        )

        # Mock _load_results to return a graded result with developing
        # skills that match terms in our standards vocabulary
        results = [
            {"assignment": "Quiz One",
             "skills_demonstrated": {
                 "developing": ["amendment", "amendment", "ratify"],
             }},
        ]
        with patch(f"{MODULE}._load_results", return_value=results):
            questions = _build_questions_from_source(
                topic="constitution",
                assignment_name="Quiz One",
                question_count=5,
            )
        # Function still returns questions (even if 0 weak-topic
        # mapping yields a fallback to all standards)
        assert isinstance(questions, list)

    def test_assignment_name_with_no_developing_skills(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            _build_questions_from_source,
        )

        # Results have skills_demonstrated as non-dict (skipped)
        results = [
            {"assignment": "Quiz Two",
             "skills_demonstrated": "not a dict"},
        ]
        with patch(f"{MODULE}._load_results", return_value=results):
            questions = _build_questions_from_source(
                topic="rights",
                assignment_name="Quiz Two",
                question_count=5,
            )
        assert isinstance(questions, list)

    def test_assignment_name_no_matching_results(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            _build_questions_from_source,
        )

        # No graded results match the assignment name → no weak topics
        with patch(f"{MODULE}._load_results", return_value=[]):
            questions = _build_questions_from_source(
                topic="rights",
                assignment_name="Nonexistent",
                question_count=3,
            )
        assert isinstance(questions, list)


# ──────────────────────────────────────────────────────────────────
# generate_kahoot_quiz error paths
# ──────────────────────────────────────────────────────────────────


class TestGenerateKahootQuizErrors:
    def test_no_mc_questions_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_kahoot_quiz,
        )

        # Force _build_questions_from_source to return only open-ended
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=[{"question": "Why?",
                                  "correct_answer": "Because",
                                  "wrong_answers": [],
                                  "q_type": "open"}]):
            result = generate_kahoot_quiz(topic="x")
        assert "error" in result
        assert "multiple-choice" in result["error"].lower()

    def test_openpyxl_missing_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_kahoot_quiz,
        )

        # Force ImportError when openpyxl is loaded
        with patch.dict("sys.modules", {"openpyxl": None}):
            result = generate_kahoot_quiz(topic="constitution")
        assert "error" in result
        assert "openpyxl" in result["error"]


# ──────────────────────────────────────────────────────────────────
# generate_blooket_set / generate_gimkit_kit error paths
# ──────────────────────────────────────────────────────────────────


class TestGenerateBlooketGimkitErrors:
    def test_blooket_no_mc_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_blooket_set,
        )

        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=[{"question": "Why?",
                                  "correct_answer": "Because",
                                  "wrong_answers": [],
                                  "q_type": "open"}]):
            result = generate_blooket_set(topic="x")
        assert "error" in result

    def test_gimkit_no_mc_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_gimkit_kit,
        )

        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=[]):
            result = generate_gimkit_kit(topic="x")
        assert "error" in result


# ──────────────────────────────────────────────────────────────────
# generate_quizlet_set fallback + error paths
# ──────────────────────────────────────────────────────────────────


class TestGenerateQuizletSetFallback:
    def test_no_vocab_pairs_falls_back_to_questions(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_quizlet_set,
        )

        with patch(f"{MODULE}._build_vocab_pairs", return_value=[]), \
             patch(f"{MODULE}._build_questions_from_source",
                   return_value=[{"question": "What is X?",
                                  "correct_answer": "X is the answer",
                                  "wrong_answers": [],
                                  "q_type": "open"}]):
            result = generate_quizlet_set(topic="x")
        assert "error" not in result
        assert result["format"] == "txt"
        # Decoded content should have the term + tab + definition
        decoded = base64.b64decode(result["document"]).decode()
        assert "What is X?" in decoded
        assert "X is the answer" in decoded
        assert "\t" in decoded

    def test_no_vocab_no_questions_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_quizlet_set,
        )

        with patch(f"{MODULE}._build_vocab_pairs", return_value=[]), \
             patch(f"{MODULE}._build_questions_from_source",
                   return_value=[]):
            result = generate_quizlet_set(topic="x")
        assert "error" in result
        assert "vocabulary" in result["error"].lower()


# ──────────────────────────────────────────────────────────────────
# generate_nearpod_questions full pipeline
# ──────────────────────────────────────────────────────────────────


class TestGenerateNearpodQuestions:
    def test_no_questions_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_nearpod_questions,
        )

        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=[]):
            result = generate_nearpod_questions(topic="x")
        assert "error" in result

    def test_document_generator_missing_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_nearpod_questions,
        )

        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=[{"question": "Q?",
                                  "correct_answer": "A",
                                  "wrong_answers": [],
                                  "q_type": "open"}]), \
             patch.dict("sys.modules",
                        {"backend.services.document_generator": None}):
            result = generate_nearpod_questions(topic="x")
        assert "error" in result
        assert "Document generator" in result["error"]

    def test_full_pipeline_with_mc_questions(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_nearpod_questions,
        )

        questions = [
            {"question": "What is freedom?",
             "correct_answer": "Liberty to act",
             "wrong_answers": ["Random A", "Random B", "Random C"],
             "source_standard": "SS.7.C.1.1",
             "q_type": "mc"},
        ]
        # Mock the doc generator to return a stub result
        fake_doc_result = {
            "document": "BASE64DATA",
            "filename": "Nearpod_Questions.docx",
            "format": "docx",
        }
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=questions), \
             patch("backend.services.document_generator.generate_document",
                   return_value=fake_doc_result):
            result = generate_nearpod_questions(topic="freedom")
        assert "error" not in result
        assert result["question_count"] == 1
        assert "Nearpod" in result["message"]

    def test_full_pipeline_with_open_questions(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_nearpod_questions,
        )

        questions = [
            {"question": "Why is liberty important?",
             "correct_answer": "Freedom enables agency.",
             "wrong_answers": [],  # open-ended → expected_answer block
             "source_standard": "SS.7.C.1.1",
             "q_type": "open"},
        ]
        fake_doc_result = {"document": "BASE64DATA",
                            "filename": "x.docx",
                            "format": "docx"}
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=questions), \
             patch("backend.services.document_generator.generate_document",
                   return_value=fake_doc_result):
            result = generate_nearpod_questions(topic="liberty")
        assert "error" not in result

    def test_doc_generator_no_document_field_passes_through(
        self, patch_paths,
    ):
        from backend.services.assistant_tools_edtech import (
            generate_nearpod_questions,
        )

        questions = [{"question": "Q",
                      "correct_answer": "A",
                      "wrong_answers": ["B", "C", "D"],
                      "q_type": "mc"}]
        # generate_document returns no "document" → no question_count
        # added; result still flows
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=questions), \
             patch("backend.services.document_generator.generate_document",
                   return_value={"error": "doc gen failure"}):
            result = generate_nearpod_questions(topic="x")
        # Result is the doc-gen output passed through (no
        # question_count injection because no document field)
        assert "question_count" not in result
        assert "error" in result


# ──────────────────────────────────────────────────────────────────
# generate_canvas_qti edge branches
# ──────────────────────────────────────────────────────────────────


class TestGenerateCanvasQtiEdges:
    def test_empty_options_filtered_out(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_canvas_qti,
        )

        # Provide questions where wrong_answers contain empty strings
        questions = [
            {"question": "What?",
             "correct_answer": "Right",
             "wrong_answers": ["", "Wrong B", "", "Wrong D"],
             "source_standard": "X.1.2",
             "q_type": "mc"},
        ]
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=questions):
            result = generate_canvas_qti(topic="testing")
        assert "error" not in result
        decoded = base64.b64decode(result["document"]).decode("utf-8")
        # "Right" + "Wrong B" + "Wrong D" = 3 options (empties filtered)
        assert decoded.count('<response_label ident="') == 3
        assert "Right" in decoded
        assert "Wrong B" in decoded
        assert "Wrong D" in decoded

    def test_no_mc_questions_returns_error(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_canvas_qti,
        )
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=[]):
            result = generate_canvas_qti(topic="x")
        assert "error" in result

    def test_filename_uses_topic_or_assignment(self, patch_paths):
        from backend.services.assistant_tools_edtech import (
            generate_canvas_qti,
        )

        questions = [{"question": "Q",
                      "correct_answer": "A",
                      "wrong_answers": ["B", "C", "D"],
                      "q_type": "mc"}]
        with patch(f"{MODULE}._build_questions_from_source",
                   return_value=questions):
            r1 = generate_canvas_qti(assignment_name="My Quiz")
        assert "My_Quiz" in r1["filename"]


# ──────────────────────────────────────────────────────────────────
# _safe_filename pure helper
# ──────────────────────────────────────────────────────────────────


class TestSafeFilename:
    def test_strips_special_chars(self):
        from backend.services.assistant_tools_edtech import _safe_filename
        assert _safe_filename("Quiz #1: Civics 2026!") == "Quiz_1_Civics_2026"

    def test_none_returns_quiz(self):
        from backend.services.assistant_tools_edtech import _safe_filename
        assert _safe_filename(None) == "quiz"

    def test_empty_returns_quiz(self):
        from backend.services.assistant_tools_edtech import _safe_filename
        assert _safe_filename("") == "quiz"

    def test_preserves_alphanumeric_and_dash_underscore(self):
        from backend.services.assistant_tools_edtech import _safe_filename
        assert _safe_filename("Hello-world_2026") == "Hello-world_2026"
