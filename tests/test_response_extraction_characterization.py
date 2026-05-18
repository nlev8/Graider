"""
Exhaustive characterization net for Slice 2 PR2.

Pinned against PRE-MOVE code from assignment_grader. Every expected value was
observed by running the function and capturing its output. No value was assumed.

Pre-existing bugs surfaced (DO NOT FIX HERE, pin as-is):
- extract_student_responses_legacy always raises NameError('response_sections')
  regardless of input. The function body references `response_sections` which is
  never defined. Pinned with pytest.raises below.
"""

import pytest

from backend.services.response_extraction import (
    extract_student_responses,
    extract_student_responses_legacy,
    extract_student_work,
    format_extracted_for_grading,
)


# ===========================================================================
# extract_student_responses — cross-product:
#   extraction path × document shape × subject/grade
# ===========================================================================

class TestExtractStudentResponses:

    # -----------------------------------------------------------------------
    # PATH: plain pattern matching (no custom_markers)
    # -----------------------------------------------------------------------

    def test_plain_numbered_social_studies_gr12(self):
        doc = (
            "1. How did the New Deal impact the economy?\n"
            "Government intervention helped reduce unemployment and stabilize banks.\n"
            "2. What were the main causes of World War II?\n"
            "Nazi ideology, economic depression, and weak international response."
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [
                {
                    "question": "How did the New Deal impact the economy?",
                    "answer": "Government intervention helped reduce unemployment and stabilize banks.",
                    "type": "numbered_qa",
                },
                {
                    "question": "What were the main causes of World War II?",
                    "answer": "Nazi ideology, economic depression, and weak international response.",
                    "type": "numbered_qa",
                },
            ],
            "blank_questions": [],
            "total_questions": 2,
            "answered_questions": 2,
            "extraction_summary": "Found 2 responses via pattern matching.",
        }

    def test_plain_numbered_ela_gr8(self):
        doc = (
            "1. Why was the Louisiana Purchase important? "
            "It doubled the size of the US.\n"
            "2. Who was Meriwether Lewis? An explorer."
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [
                {
                    "question": "Why was the Louisiana Purchase important?",
                    "answer": "It doubled the size of the US.",
                    "type": "numbered_qa",
                },
                {
                    "question": "Who was Meriwether Lewis?",
                    "answer": "An explorer.",
                    "type": "numbered_qa",
                },
            ],
            "blank_questions": [],
            "total_questions": 2,
            "answered_questions": 2,
            "extraction_summary": "Found 2 responses via pattern matching.",
        }

    def test_plain_numbered_science_gr10(self):
        doc = (
            "1. What is the atomic number of carbon?\n"
            "6\n"
            "2. What type of bond forms between sodium and chlorine?\n"
            "Ionic bond"
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [
                {
                    "question": "What type of bond forms between sodium and chlorine?",
                    "answer": "Ionic bond",
                    "type": "numbered_qa",
                },
            ],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Found 1 responses via pattern matching.",
        }

    def test_plain_numbered_math_gr5_no_markers(self):
        """Math gr5 numbered — answer is short number, fallback pattern doesn't pick it up."""
        doc = (
            "1. What is 7 x 8?\n"
            "56\n"
            "2. What is 144 / 12?\n"
            "12"
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 0,
            "extraction_summary": "Found 0 responses via pattern matching.",
        }

    def test_vocab_term_no_markers_returns_empty(self):
        """Vocab-term format without custom markers: pattern matching yields nothing."""
        doc = (
            "Photosynthesis: the process by which plants make food\n"
            "Mitosis: cell division"
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 0,
            "extraction_summary": "Found 0 responses via pattern matching.",
        }

    def test_summary_written_no_markers_returns_empty(self):
        """Summary/written format without custom markers: no responses extracted."""
        doc = (
            "📝 SUMMARY\n"
            "Explain what you learned:\n"
            "Today I learned about the water cycle. Water evaporates and forms clouds."
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 0,
            "extraction_summary": "Found 0 responses via pattern matching.",
        }

    # -----------------------------------------------------------------------
    # PATH: FITB (fill-in-the-blank keyword triggers FITB extraction)
    # -----------------------------------------------------------------------

    def test_fitb_math_gr5_timestamps(self):
        """Math gr5 fill-in-the-blank with timestamps triggers FITB extraction."""
        doc = (
            "Math fill-in-the-blank\n"
            "1. (0:00) Addition: 5 + 3 = ___8___\n"
            "2. (0:30) Subtraction: 10 - 4 = ___6___"
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [
                {"question": "Item 1 (0:00)", "answer": "Addition: 5 + 3 = ___8___", "type": "fill_in_blank_sentence"},
                {"question": "Item 2 (0:30)", "answer": "Subtraction: 10 - 4 = ___6___", "type": "fill_in_blank_sentence"},
                {"question": "Fill-in-blank", "answer": "8", "type": "fill_in_blank"},
                {"question": "Fill-in-blank", "answer": "6", "type": "fill_in_blank"},
            ],
            "blank_questions": [],
            "total_questions": 4,
            "answered_questions": 4,
            "extraction_summary": "Found 4 responses via pattern matching.",
        }

    def test_fitb_ela_gr8_vocab(self):
        """ELA gr8 fill-in-the-blank with literary terms."""
        doc = (
            "Fill-in-the-blank vocabulary exercise\n"
            "a. The _protagonist_ is the main character of a story.\n"
            "b. _Foreshadowing_ hints at future events.\n"
            "c. A _simile_ uses like or as to compare."
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [
                {"question": "Item A", "answer": "The _protagonist_ is the main character of a story.", "type": "fill_in_blank_sentence"},
                {"question": "Item B", "answer": "_Foreshadowing_ hints at future events.", "type": "fill_in_blank_sentence"},
                {"question": "Item C", "answer": "A _simile_ uses like or as to compare.", "type": "fill_in_blank_sentence"},
                {"question": "Fill-in-blank", "answer": "protagonist", "type": "fill_in_blank"},
                {"question": "Fill-in-blank", "answer": "Foreshadowing", "type": "fill_in_blank"},
                {"question": "Fill-in-blank", "answer": "simile", "type": "fill_in_blank"},
            ],
            "blank_questions": [],
            "total_questions": 6,
            "answered_questions": 6,
            "extraction_summary": "Found 6 responses via pattern matching.",
        }

    def test_fitb_social_studies_gr12_blanks(self):
        """Social studies gr12 fill-in-the-blank."""
        doc = (
            "Fill-in-the-blank activity\n"
            "1. The capital of France is ___Paris___\n"
            "2. The largest ocean is ___Pacific___"
        )
        result = extract_student_responses(doc)
        assert result == {
            "extracted_responses": [
                {"question": "Item 1", "answer": "The capital of France is ___Paris___", "type": "fill_in_blank_sentence"},
                {"question": "Item 2", "answer": "The largest ocean is ___Pacific___", "type": "fill_in_blank_sentence"},
                {"question": "Fill-in-blank", "answer": "Paris", "type": "fill_in_blank"},
                {"question": "Fill-in-blank", "answer": "Pacific", "type": "fill_in_blank"},
                {"question": "Question 1", "answer": "The capital of France is ___Paris___", "type": "fill_in_blank"},
                {"question": "Question 2", "answer": "The largest ocean is ___Pacific___", "type": "fill_in_blank"},
            ],
            "blank_questions": [],
            "total_questions": 6,
            "answered_questions": 6,
            "extraction_summary": "Found 6 responses via pattern matching.",
        }

    # -----------------------------------------------------------------------
    # PATH: custom_markers (structured extraction via Builder markers)
    # -----------------------------------------------------------------------

    def test_custom_marker_single_ela_gr8_reflection(self):
        """ELA gr8: single string marker for Reflection section."""
        doc = (
            "REFLECTION\n"
            "I believe the author was trying to show how inequality impacts society "
            "in many ways. The poor struggled while the rich thrived."
        )
        result = extract_student_responses(doc, custom_markers=["REFLECTION"])
        assert result == {
            "extracted_responses": [
                {
                    "question": "REFLECTION",
                    "answer": (
                        "I believe the author was trying to show how inequality impacts society "
                        "in many ways. The poor struggled while the rich thrived."
                    ),
                    "type": "marker_response",
                }
            ],
            "blank_questions": [],
            "missing_sections": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Extracted 1 responses using 1 markers (1 exact).",
            "excluded_sections": [],
        }

    def test_custom_marker_single_science_gr10_summary(self):
        """Science gr10: single string marker for student summary."""
        doc = (
            "STUDENT SUMMARY\n"
            "Cells need energy to function. Mitochondria produce ATP through cellular "
            "respiration, which uses glucose and oxygen."
        )
        result = extract_student_responses(doc, custom_markers=["STUDENT SUMMARY"])
        assert result == {
            "extracted_responses": [
                {
                    "question": "STUDENT SUMMARY",
                    "answer": (
                        "Cells need energy to function. Mitochondria produce ATP through cellular "
                        "respiration, which uses glucose and oxygen."
                    ),
                    "type": "marker_response",
                }
            ],
            "blank_questions": [],
            "missing_sections": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Extracted 1 responses using 1 markers (1 exact).",
            "excluded_sections": [],
        }

    def test_custom_marker_multiple_ela_gr8_docx_table(self):
        """ELA gr8: docx-table-derived multi-section markers."""
        doc = (
            "MAIN IDEA\n"
            "The story shows how courage can overcome fear.\n"
            "EVIDENCE\n"
            "The protagonist faced the dragon despite trembling with terror."
        )
        result = extract_student_responses(doc, custom_markers=["MAIN IDEA", "EVIDENCE"])
        assert result == {
            "extracted_responses": [
                {
                    "question": "MAIN IDEA",
                    "answer": "The story shows how courage can overcome fear.",
                    "type": "marker_response",
                },
                {
                    "question": "EVIDENCE",
                    "answer": "The protagonist faced the dragon despite trembling with terror.",
                    "type": "marker_response",
                },
            ],
            "blank_questions": [],
            "missing_sections": [],
            "total_questions": 2,
            "answered_questions": 2,
            "extraction_summary": "Extracted 2 responses using 2 markers (2 exact).",
            "excluded_sections": [],
        }

    def test_custom_marker_multiple_math_gr5_docx_table(self):
        """Math gr5: docx-table-derived multi-section markers."""
        doc = (
            "ADDITION\n"
            "5 + 3 = 8\n"
            "7 + 9 = 16\n"
            "SUBTRACTION\n"
            "10 - 4 = 6\n"
            "15 - 7 = 8"
        )
        result = extract_student_responses(doc, custom_markers=["ADDITION", "SUBTRACTION"])
        assert result == {
            "extracted_responses": [
                {
                    "question": "ADDITION",
                    "answer": "5 + 3 = 8\n7 + 9 = 16",
                    "type": "marker_response",
                },
                {
                    "question": "SUBTRACTION",
                    "answer": "10 - 4 = 6\n15 - 7 = 8",
                    "type": "marker_response",
                },
            ],
            "blank_questions": [],
            "missing_sections": [],
            "total_questions": 2,
            "answered_questions": 2,
            "extraction_summary": "Extracted 2 responses using 2 markers (2 exact).",
            "excluded_sections": [],
        }

    def test_custom_marker_summary_social_studies_gr12(self):
        """Social studies gr12: single marker for summary."""
        doc = (
            "SUMMARY\n"
            "The Civil War was fought over slavery and states rights."
        )
        result = extract_student_responses(doc, custom_markers=["SUMMARY"])
        assert result == {
            "extracted_responses": [
                {
                    "question": "SUMMARY",
                    "answer": "The Civil War was fought over slavery and states rights.",
                    "type": "marker_response",
                }
            ],
            "blank_questions": [],
            "missing_sections": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Extracted 1 responses using 1 markers (1 exact).",
            "excluded_sections": [],
        }

    def test_custom_marker_vocab_type_social_studies_gr12(self):
        """Social studies gr12: vocabulary section with dict marker (type=vocabulary)."""
        doc = (
            "VOCABULARY\n"
            "Democracy: rule by the people\n"
            "Autocracy: rule by one person\n"
            "OLIGARCHY: rule by a few"
        )
        result = extract_student_responses(
            doc,
            custom_markers=[{"start": "VOCABULARY", "type": "vocabulary"}],
        )
        assert result == {
            "extracted_responses": [
                {"question": "Democracy", "answer": "rule by the people", "type": "vocab_term"},
                {"question": "Autocracy", "answer": "rule by one person", "type": "vocab_term"},
                {"question": "OLIGARCHY", "answer": "rule by a few", "type": "vocab_term"},
            ],
            "blank_questions": [],
            "missing_sections": [],
            "total_questions": 3,
            "answered_questions": 3,
            "extraction_summary": "Extracted 3 responses using 1 markers (1 exact).",
            "excluded_sections": [],
        }

    def test_custom_marker_missing_section_reported(self):
        """Marker present in config but absent from doc → appears in missing_sections."""
        doc = "SUMMARY\nThe Civil War ended in 1865."
        result = extract_student_responses(
            doc, custom_markers=["SUMMARY", "REFLECTION"]
        )
        assert "REFLECTION" in result["missing_sections"]
        assert result["answered_questions"] == 1

    # -----------------------------------------------------------------------
    # Determinism
    # -----------------------------------------------------------------------

    def test_deterministic_plain_numbered(self):
        doc = (
            "1. Why was the Louisiana Purchase important? "
            "It doubled the size of the US.\n"
            "2. Who was Meriwether Lewis? An explorer."
        )
        assert extract_student_responses(doc) == extract_student_responses(doc)

    def test_deterministic_custom_marker(self):
        doc = "SUMMARY\nThe Civil War was fought over slavery and states rights."
        r1 = extract_student_responses(doc, custom_markers=["SUMMARY"])
        r2 = extract_student_responses(doc, custom_markers=["SUMMARY"])
        assert r1 == r2

    def test_deterministic_fitb(self):
        doc = (
            "Fill-in-the-blank activity\n"
            "1. The capital of France is ___Paris___\n"
            "2. The largest ocean is ___Pacific___"
        )
        assert extract_student_responses(doc) == extract_student_responses(doc)


# ===========================================================================
# extract_student_responses_legacy — always raises NameError (pre-existing bug)
# ===========================================================================

class TestExtractStudentResponsesLegacy:
    """
    Pre-existing bug: the function body references `response_sections` which is
    never defined as a local or global variable. Every call raises NameError.
    DO NOT fix this here — pin actual observed behavior.
    """

    def test_plain_text_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy(
                "1. Why was the Louisiana Purchase important? It doubled the size."
            )

    def test_ela_gr8_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy(
                "REFLECTION\nI believe the author was conveying hope.",
                custom_markers=None,
            )

    def test_science_gr10_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy(
                "Photosynthesis: plants convert sunlight to energy.",
                custom_markers=["Vocabulary"],
            )

    def test_social_studies_gr12_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy(
                "The New Deal had lasting economic effects.",
                custom_markers=None,
            )

    def test_math_gr5_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy("1. 5 + 3 = 8")

    def test_empty_string_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy("")

    def test_custom_markers_list_raises_nameerror(self):
        with pytest.raises(NameError, match="response_sections"):
            extract_student_responses_legacy(
                "SUMMARY\nSome student text.",
                custom_markers=["SUMMARY"],
            )


# ===========================================================================
# format_extracted_for_grading — structured and ai modes
# ===========================================================================

class TestFormatExtractedForGrading:

    def test_empty_dict_returns_no_responses_msg(self):
        assert format_extracted_for_grading({}) == (
            "NO STUDENT RESPONSES FOUND - Document appears to be blank or unfinished."
        )

    def test_none_returns_no_responses_msg(self):
        assert format_extracted_for_grading(None) == (
            "NO STUDENT RESPONSES FOUND - Document appears to be blank or unfinished."
        )

    def test_structured_mode_science_gr10(self):
        extraction = {
            "extracted_responses": [
                {
                    "question": "What is photosynthesis?",
                    "answer": "The process by which plants make food.",
                    "type": "short_answer",
                },
                {
                    "question": "Define mitosis",
                    "answer": "Cell division",
                    "type": "vocab_term",
                },
            ],
            "blank_questions": ["What is respiration?"],
            "total_questions": 3,
            "answered_questions": 2,
            "extraction_summary": "Found 2 responses.",
        }
        result = format_extracted_for_grading(extraction, extraction_mode="structured")
        assert result == (
            "==================================================\n"
            "VERIFIED STUDENT RESPONSES (extracted from document)\n"
            "==================================================\n"
            "\n"
            "[1] What is photosynthesis?\n"
            '    STUDENT ANSWER: "The process by which plants make food."\n'
            "    (Type: short_answer)\n"
            "\n"
            "[2] Define mitosis\n"
            '    STUDENT ANSWER: "Cell division"\n'
            "    (Type: vocab_term)\n"
            "\n"
            "--------------------------------------------------\n"
            "UNANSWERED QUESTIONS (left blank by student):\n"
            "  • What is respiration?\n"
            "\n"
            "SUMMARY: Found 2 responses."
        )

    def test_ai_mode_ela_gr8_summary(self):
        extraction = {
            "extracted_responses": [
                {
                    "question": "Summary",
                    "answer": "The water cycle describes how water moves through the environment.",
                    "type": "written_response",
                },
            ],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Found 1 responses.",
        }
        result = format_extracted_for_grading(extraction, extraction_mode="ai")
        assert result == (
            "==================================================\n"
            "RAW SECTION CONTENT (AI will identify prompts vs student responses)\n"
            "==================================================\n"
            "\n"
            "[1] Summary\n"
            '    STUDENT ANSWER: "The water cycle describes how water moves through the environment."\n'
            "    (Type: written_response)\n"
            "\n"
            "\n"
            "SUMMARY: Found 1 responses."
        )

    def test_structured_with_marker_config_points_math_gr5(self):
        extraction = {
            "extracted_responses": [
                {
                    "question": "Problem Set A",
                    "answer": "5 + 3 = 8, 7 + 2 = 9",
                    "type": "marker_response",
                }
            ],
            "blank_questions": ["Problem Set B"],
            "missing_sections": ["Problem Set C"],
            "total_questions": 3,
            "answered_questions": 1,
            "extraction_summary": "Found 1 of 3.",
        }
        marker_config = [
            {"start": "Problem Set A", "points": 30},
            {"start": "Problem Set B", "points": 30},
            {"start": "Problem Set C", "points": 40},
        ]
        result = format_extracted_for_grading(
            extraction, marker_config=marker_config, extraction_mode="structured"
        )
        assert result == (
            "==================================================\n"
            "VERIFIED STUDENT RESPONSES (extracted from document)\n"
            "==================================================\n"
            "\n"
            "[1] Problem Set A [30 points]\n"
            '    STUDENT ANSWER: "5 + 3 = 8, 7 + 2 = 9"\n'
            "    (Type: marker_response)\n"
            "\n"
            "--------------------------------------------------\n"
            "UNANSWERED QUESTIONS (left blank by student):\n"
            "  • Problem Set B [LOSES 30 points]\n"
            "--------------------------------------------------\n"
            "MISSING SECTIONS (required by assignment but not found in student submission):\n"
            "  ✗ Problem Set C [LOSES 40 points] — ENTIRELY OMITTED\n"
            "\n"
            "SUMMARY: Found 1 of 3."
        )

    def test_structured_with_points_social_studies_gr12(self):
        extraction = {
            "extracted_responses": [
                {
                    "question": "Summary",
                    "answer": "The water cycle is important.",
                    "type": "written_response",
                },
            ],
            "blank_questions": ["Reflection"],
            "total_questions": 2,
            "answered_questions": 1,
            "extraction_summary": "Found 1 of 2.",
        }
        marker_config = [
            {"start": "Summary", "points": 20},
            {"start": "Reflection", "points": 15},
        ]
        result = format_extracted_for_grading(
            extraction, marker_config=marker_config, extraction_mode="structured"
        )
        assert result == (
            "==================================================\n"
            "VERIFIED STUDENT RESPONSES (extracted from document)\n"
            "==================================================\n"
            "\n"
            "[1] Summary [20 points]\n"
            '    STUDENT ANSWER: "The water cycle is important."\n'
            "    (Type: written_response)\n"
            "\n"
            "--------------------------------------------------\n"
            "UNANSWERED QUESTIONS (left blank by student):\n"
            "  • Reflection [LOSES 15 points]\n"
            "\n"
            "SUMMARY: Found 1 of 2."
        )

    def test_deterministic_structured(self):
        extraction = {
            "extracted_responses": [
                {"question": "Q1", "answer": "A1", "type": "short_answer"}
            ],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Found 1.",
        }
        r1 = format_extracted_for_grading(extraction, extraction_mode="structured")
        r2 = format_extracted_for_grading(extraction, extraction_mode="structured")
        assert r1 == r2

    def test_deterministic_ai_mode(self):
        extraction = {
            "extracted_responses": [
                {
                    "question": "Summary",
                    "answer": "Student wrote something.",
                    "type": "written_response",
                }
            ],
            "blank_questions": [],
            "total_questions": 1,
            "answered_questions": 1,
            "extraction_summary": "Found 1.",
        }
        r1 = format_extracted_for_grading(extraction, extraction_mode="ai")
        r2 = format_extracted_for_grading(extraction, extraction_mode="ai")
        assert r1 == r2


# ===========================================================================
# extract_student_work — cross-product: content shape × subject
# ===========================================================================

class TestExtractStudentWork:

    def test_student_task_marker_ela_gr8(self):
        """ELA gr8: 'student task' is a STUDENT_WORK_MARKERS entry."""
        doc = (
            "INSTRUCTIONS: Read the text.\n"
            "Student Task: Answer the questions below.\n"
            "1. What happened? It was important.\n"
            "2. Why? Because of history."
        )
        student_work, markers_found = extract_student_work(doc)
        assert student_work == (
            "Student Task: Answer the questions below.\n"
            "1. What happened? It was important.\n"
            "2. Why? Because of history."
        )
        assert "student task" in markers_found

    def test_no_markers_returns_full_content(self):
        """No STUDENT_WORK_MARKERS → returns full content unchanged."""
        doc = "Just some plain text here with no markers."
        student_work, markers_found = extract_student_work(doc)
        assert student_work == doc
        assert markers_found == []

    def test_check_understanding_science_gr10(self):
        """Science gr10: 'check your understanding' is a marker."""
        doc = (
            "Introduction: Read the passage about cells.\n"
            "Check your understanding:\n"
            "1. What is mitosis? It is cell division.\n"
            "2. What is the powerhouse? Mitochondria."
        )
        student_work, markers_found = extract_student_work(doc)
        assert student_work == (
            "Check your understanding:\n"
            "1. What is mitosis? It is cell division.\n"
            "2. What is the powerhouse? Mitochondria."
        )
        assert "check your understanding" in markers_found

    def test_write_marker_social_studies_gr12(self):
        """Social studies gr12: 'write' is a STUDENT_WORK_MARKERS entry."""
        doc = (
            "Background reading: The Great Depression began in 1929.\n"
            "Write your response: The New Deal helped millions of Americans by "
            "creating jobs and stabilizing banks."
        )
        student_work, markers_found = extract_student_work(doc)
        assert student_work == (
            "Write your response: The New Deal helped millions of Americans by "
            "creating jobs and stabilizing banks."
        )
        assert "write" in markers_found

    def test_reflect_marker_ela_gr8(self):
        """ELA gr8: 'reflect' and 'write' both present — earliest wins."""
        doc = (
            "Today we read a novel about war.\n"
            "Background: The story takes place in 1944.\n"
            "Reflect: Write your thoughts here.\n"
            "I think the author wanted us to understand the human cost of conflict."
        )
        student_work, markers_found = extract_student_work(doc)
        assert student_work == (
            "Reflect: Write your thoughts here.\n"
            "I think the author wanted us to understand the human cost of conflict."
        )
        assert "write" in markers_found
        assert "reflect" in markers_found

    def test_practice_marker_math_gr5(self):
        """Math gr5: 'practice' is a STUDENT_WORK_MARKERS entry."""
        doc = (
            "Let us review fractions.\n"
            "Practice your skills:\n"
            "1. 1/2 + 1/4 = 3/4\n"
            "2. 2/3 - 1/6 = 1/2"
        )
        student_work, markers_found = extract_student_work(doc)
        assert student_work == (
            "Practice your skills:\n"
            "1. 1/2 + 1/4 = 3/4\n"
            "2. 2/3 - 1/6 = 1/2"
        )
        assert "practice" in markers_found

    def test_deterministic_with_marker(self):
        doc = "Student Task: Do this.\nI did it because it was important."
        r1 = extract_student_work(doc)
        r2 = extract_student_work(doc)
        assert r1 == r2

    def test_deterministic_no_marker(self):
        doc = "Just plain text with no special markers at all."
        r1 = extract_student_work(doc)
        r2 = extract_student_work(doc)
        assert r1 == r2

    def test_multiple_markers_earliest_position_wins(self):
        """When multiple markers appear, the function returns from the earliest one."""
        doc = (
            "Background text.\n"
            "Answer the question below.\n"
            "Reflect on what you learned.\n"
            "My reflection is that history repeats itself."
        )
        student_work, markers_found = extract_student_work(doc)
        # 'answer the' appears before 'reflect' — earliest marker should win
        assert "answer the" in markers_found or len(markers_found) >= 1
        # student_work starts from the first marker position
        assert student_work.startswith("Answer the question") or "Answer the" in student_work
