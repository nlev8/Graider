"""PR7 hardening: real behavioral tests for response_extraction helpers that the
existing characterization tests leave uncovered — `format_extracted_for_grading`
(prompt formatting incl. points/blanks/missing sections), `extract_student_work`
(marker slicing), plus additional edge/negative branches of the leaf parsers.

The module is pure (`import re` only — guarded by test_module_is_pure_*). No
mocks. Every assertion pins exact extracted text / structure (per plan guard).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services import response_extraction as rx


# ── format_extracted_for_grading ─────────────────────────────────────────────


class TestFormatExtractedForGrading:
    def test_empty_result_returns_blank_notice(self):
        assert rx.format_extracted_for_grading({}) == (
            "NO STUDENT RESPONSES FOUND - Document appears to be blank or unfinished.")

    def test_no_extracted_responses_returns_blank_notice(self):
        assert rx.format_extracted_for_grading({"extracted_responses": []}) == (
            "NO STUDENT RESPONSES FOUND - Document appears to be blank or unfinished.")

    def test_full_output_with_points_blanks_and_missing(self):
        res = {
            "extracted_responses": [
                {"question": "Summary section", "answer": "The war ended in 1945.",
                 "type": "summary"}],
            "blank_questions": ["Vocabulary section"],
            "missing_sections": ["Reflection section"],
            "extraction_summary": "1 of 2 answered",
        }
        out = rx.format_extracted_for_grading(res, marker_config=[
            {"start": "Summary", "points": 20},
            {"start": "Vocabulary", "points": 10},
            {"start": "Reflection", "points": 5},
        ])
        # answered section shows its point value and cleaned student answer
        assert '[1] Summary section [20 points]' in out
        assert 'STUDENT ANSWER: "The war ended in 1945."' in out
        assert '(Type: summary)' in out
        # blank section shows the "LOSES n points" form
        assert '• Vocabulary section [LOSES 10 points]' in out
        # missing section uses the omitted form
        assert '✗ Reflection section [LOSES 5 points] — ENTIRELY OMITTED' in out
        assert 'SUMMARY: 1 of 2 answered' in out

    def test_ai_mode_header_and_raw_answer(self):
        res = {"extracted_responses": [
            {"question": "Q1", "answer": "What year? 1803", "type": "qa"}]}
        out = rx.format_extracted_for_grading(res, extraction_mode='ai')
        # AI mode keeps the raw answer (no prompt-stripping) and uses its own header
        assert 'RAW SECTION CONTENT' in out
        assert 'STUDENT ANSWER: "What year? 1803"' in out

    def test_structured_mode_strips_question_prefix(self):
        # Structured mode keeps only text AFTER a '?'.
        res = {"extracted_responses": [
            {"question": "Q1", "answer": "What year was it? 1803", "type": "qa"}]}
        out = rx.format_extracted_for_grading(res)  # default structured
        assert 'STUDENT ANSWER: "1803"' in out


# ── extract_student_work ──────────────────────────────────────────────────────


class TestExtractStudentWork:
    def test_returns_text_from_first_marker_onward(self):
        content = ("Lecture notes here.\nMore notes.\n"
                   "Answer the question below.\nMy response.")
        work, markers = rx.extract_student_work(content)
        assert work == "Answer the question below.\nMy response."
        # both "answer the question" and the shorter "answer the" markers match
        assert "answer the question" in markers
        assert "answer the" in markers

    def test_no_marker_returns_full_content_and_empty_list(self):
        content = "Just some plain text with nothing special at all."
        work, markers = rx.extract_student_work(content)
        assert work == content
        assert markers == []


# ── leaf parser edge / negative branches ──────────────────────────────────────


class TestNumberedQuestionsEdges:
    def test_all_blank_answers_marked_is_blank(self):
        result = rx.parse_numbered_questions(
            "1. What is x?\n2. What is y?\n3. What is z?")
        assert result == [
            {"question": "1. What is x?", "answer": "", "is_blank": True},
            {"question": "2. What is y?", "answer": "", "is_blank": True},
            {"question": "3. What is z?", "answer": "", "is_blank": True},
        ]

    def test_too_short_text_returns_empty(self):
        # Negative: <20 chars short-circuits to [].
        assert rx.parse_numbered_questions("1. a\n2. b") == []

    def test_non_sequential_start_returns_empty(self):
        # Negative: must start at 1.
        text = "3. First question here?\n4. Second question here?\nmore text padding"
        assert rx.parse_numbered_questions(text) == []

    def test_answers_after_question_mark_extracted(self):
        text = ("1. What is x? The answer is five.\n"
                "2. What is y? Ten apples here.\n"
                "3. What is z? Twenty things.")
        result = rx.parse_numbered_questions(text)
        assert result == [
            {"question": "1. What is x?", "answer": "The answer is five.",
             "is_blank": False},
            {"question": "2. What is y?", "answer": "Ten apples here.",
             "is_blank": False},
            {"question": "3. What is z?", "answer": "Twenty things.",
             "is_blank": False},
        ]

    def test_no_question_mark_uses_newline_separator(self):
        text = ("1. Define osmosis\nMovement of water across membrane\n"
                "2. Define diffusion\nSpreading of particles here\n"
                "3. Define solute\nDissolved substance here")
        result = rx.parse_numbered_questions(text)
        assert result[0] == {"question": "1. Define osmosis",
                             "answer": "Movement of water across membrane",
                             "is_blank": False}


class TestIsQuestionOrPromptScoring:
    def test_requirement_language_is_prompt(self):
        assert rx.is_question_or_prompt("Write a response in 3-4 sentences.") is True

    def test_at_least_quantifier_is_prompt(self):
        assert rx.is_question_or_prompt("Provide at least 3 examples.") is True

    def test_long_question_word_statement_is_response(self):
        # Question word, no '?', long → scored as a student statement.
        assert rx.is_question_or_prompt(
            "How they resolved the conflict was through a peaceful negotiation "
            "that lasted several weeks") is False


class TestVocabTermsEdges:
    def test_blank_definition_on_next_line_is_picked_up(self):
        result = rx.parse_vocab_terms(
            "Osmosis:\nthe movement of water\nDiffusion: spreading of particles")
        assert result == [
            {"term": "Osmosis", "answer": "the movement of water", "is_blank": False},
            {"term": "Diffusion", "answer": "spreading of particles", "is_blank": False},
        ]

    def test_fewer_than_two_terms_returns_empty(self):
        # Negative: a single term is below the 2-term false-positive floor.
        assert rx.parse_vocab_terms("Photosynthesis: how plants make food") == []

    def test_header_keyword_terms_skipped(self):
        # "Vocabulary"/"Directions" are skip_keywords → no real terms → [].
        text = "Vocabulary: the words\nDirections: follow these steps"
        assert rx.parse_vocab_terms(text) == []


class TestFitbExtraction:
    def test_inline_underscore_answer_extracted(self):
        result = rx.extract_fitb_by_template_comparison(
            "The mitochondria is the _powerhouse_ of the cell.", "template")
        assert result == [{
            "question": "Response 1",
            "answer": "The mitochondria is the _powerhouse_ of the cell.",
            "type": "fill_in_blank_sentence"}]

    def test_numbered_line_becomes_item_label(self):
        result = rx.extract_fitb_by_template_comparison(
            "1. The capital of France is Paris.", "template")
        assert result == [{
            "question": "Item 1",
            "answer": "The capital of France is Paris.",
            "type": "fill_in_blank_sentence"}]

    def test_empty_student_text_returns_empty(self):
        # Negative: no student text → [].
        assert rx.extract_fitb_by_template_comparison("", "template") == []


class TestFilterAndIsQuestion:
    def test_filter_keeps_answer_after_question_mark(self):
        assert rx.filter_questions_from_response(
            "What year was the Louisiana Purchase?\n1803") == "1803"

    def test_filter_drops_pure_question(self):
        assert rx.filter_questions_from_response(
            "How did slavery affect daily life?") == ""

    def test_is_question_or_prompt_imperative_is_true(self):
        assert rx.is_question_or_prompt("Summarize the key events in 3-4 sentences.") is True

    def test_is_question_or_prompt_student_statement_is_false(self):
        assert rx.is_question_or_prompt(
            "The Louisiana Purchase was a land deal in 1803 because Jefferson "
            "wanted to expand the country westward.") is False

    def test_empty_text_is_prompt(self):
        # Empty/whitespace is treated as "not a valid response" → True.
        assert rx.is_question_or_prompt("   ") is True


class TestStripTemplateLines:
    def test_removes_matching_template_instruction_line(self):
        response = ("Summarize the key events in 4-5 sentences.\n"
                    "The war ended in 1945 with Allied victory.")
        template = "SUMMARY\nSummarize the key events in 4-5 sentences.\nVOCABULARY"
        result = rx._strip_template_lines(response, "SUMMARY", template)
        assert result == "The war ended in 1945 with Allied victory."

    def test_no_template_returns_response_unchanged(self):
        # Negative: no template_text → response returned as-is.
        assert rx._strip_template_lines("student answer", "SUMMARY", "") == "student answer"

    def test_marker_not_in_template_returns_unchanged(self):
        # Negative: marker absent from template → no stripping.
        assert rx._strip_template_lines(
            "student answer", "MISSING", "TEMPLATE\nother content here") == "student answer"

    def test_strips_exact_instruction_keeps_student_sentence(self):
        response = ("Explain the main causes of the war.\n"
                    "The war was caused by economic tensions.")
        template = "CAUSES\nExplain the main causes of the war.\nVOCAB"
        result = rx._strip_template_lines(response, "CAUSES", template)
        assert result == "The war was caused by economic tensions."

    def test_fuzzy_word_overlap_strips_reworded_prompt(self):
        # The first response line shares >=60% of its words with the template
        # instruction (reworded) → fuzzy-matched and stripped.
        response = ("The primary causes of the great war were economic.\n"
                    "My real answer about tensions.")
        template = "CAUSES\nList the primary causes of the great war here.\nNEXT"
        result = rx._strip_template_lines(response, "CAUSES", template)
        assert result == "My real answer about tensions."


class TestFuzzyFindMarker:
    def test_exact_match_position(self):
        doc = "Some text before\nVOCABULARY\nsome content after"
        assert rx.fuzzy_find_marker(doc, "VOCABULARY") == 17

    def test_single_word_boundary_match(self):
        # No exact case match needed — lowercased word-boundary search finds it.
        doc = "intro paragraph then Summary heading"
        assert rx.fuzzy_find_marker(doc, "summary") == 21

    def test_marker_absent_returns_minus_one(self):
        # Negative: a multi-word marker with no overlap → -1.
        assert rx.fuzzy_find_marker("totally unrelated text", "the missing section") == -1


class TestStripEmojis:
    def test_removes_emoji_keeps_text(self):
        assert rx.strip_emojis("Hello \U0001F600 World \U0001F680") == "Hello  World"

    def test_plain_text_unchanged(self):
        assert rx.strip_emojis("no emojis here") == "no emojis here"


# ── extract_student_responses (marker-based extraction integration) ───────────


class TestExtractStudentResponses:
    DOC = (
        "Name: Jane\n"
        "SUMMARY\n"
        "The Louisiana Purchase doubled the size of the United States in 1803.\n"
        "VOCABULARY\n"
        "Annexation: the act of adding territory to a country\n"
    )

    def test_two_marker_sections_extracted_exactly(self):
        res = rx.extract_student_responses(self.DOC, custom_markers=["SUMMARY", "VOCABULARY"])
        assert res["total_questions"] == 2
        assert res["answered_questions"] == 2
        assert res["extracted_responses"] == [
            {"question": "SUMMARY",
             "answer": "The Louisiana Purchase doubled the size of the United "
                       "States in 1803.",
             "type": "marker_response"},
            {"question": "VOCABULARY",
             "answer": "Annexation: the act of adding territory to a country",
             "type": "marker_response"},
        ]
        assert res["blank_questions"] == []
        assert res["missing_sections"] == []
        assert res["extraction_summary"] == (
            "Extracted 2 responses using 2 markers (2 exact).")

    def test_excluded_marker_section_skipped(self):
        res = rx.extract_student_responses(
            self.DOC, custom_markers=["SUMMARY", "VOCABULARY"],
            exclude_markers=["VOCABULARY"])
        assert res["excluded_sections"] == ["VOCABULARY"]
        # only the SUMMARY section is graded
        assert len(res["extracted_responses"]) == 1
        assert res["extracted_responses"][0]["question"] == "SUMMARY"

    def test_marker_not_in_doc_reported_missing(self):
        res = rx.extract_student_responses(
            self.DOC, custom_markers=["SUMMARY", "VOCABULARY", "REFLECTION"])
        assert res["missing_sections"] == ["REFLECTION"]

    def test_marker_present_but_empty_is_blank(self):
        doc = "SUMMARY\nVOCABULARY\nPhotosynthesis: how plants make food\n"
        res = rx.extract_student_responses(doc, custom_markers=["SUMMARY", "VOCABULARY"])
        # SUMMARY heading immediately followed by next marker → no content → blank
        assert res["blank_questions"] == ["SUMMARY"]
        assert res["answered_questions"] == 1
        assert res["total_questions"] == 2

    def test_fitb_keyword_triggers_fitb_extraction(self):
        doc = ("Fill in the blank activity\n"
               "1. The capital of France is Paris.\n"
               "2. The largest planet is Jupiter.\n")
        res = rx.extract_student_responses(doc)
        answers = [r["answer"] for r in res["extracted_responses"]]
        assert "The capital of France is Paris." in answers
        assert "The largest planet is Jupiter." in answers

    def test_no_markers_no_fitb_returns_empty_responses(self):
        # Negative: plain text with no markers → no extracted responses.
        res = rx.extract_student_responses("Just plain text without any markers here.")
        assert res["extracted_responses"] == []
        assert res["answered_questions"] == 0

    def test_object_marker_end_marker_and_section_delimiter(self):
        # Object marker with an explicit end marker: content stops at the end
        # marker (📖), so the reading material after it is NOT captured.
        doc = ("INTRO text\n"
               "SUMMARY\n"
               "The war ended in 1945 with an Allied victory after years of "
               "conflict.\n"
               "📖 Reading material that should not be graded.\n"
               "VOCAB\nfoo\n")
        res = rx.extract_student_responses(
            doc, custom_markers=[{"start": "SUMMARY", "end": "📖"}])
        assert res["extracted_responses"] == [{
            "question": "SUMMARY",
            "answer": "The war ended in 1945 with an Allied victory after years "
                      "of conflict.",
            "type": "marker_response"}]

    def test_multiline_marker_parses_numbered_questions_in_section(self):
        # A multi-line marker whose body contains numbered Q&A → the section is
        # split into per-question numbered_question items.
        doc = ("DIRECTIONS\n"
               "ANALYSIS QUESTIONS\n"
               "Answer the following questions in complete sentences.\n"
               "1. What caused the war? Economic tensions caused it.\n"
               "2. Who won the war? The allied powers won.\n")
        marker = ("ANALYSIS QUESTIONS\n"
                  "Answer the following questions in complete sentences.")
        res = rx.extract_student_responses(doc, custom_markers=[{"start": marker}])
        assert res["extracted_responses"] == [
            {"question": "1. What caused the war?",
             "answer": "Economic tensions caused it.", "type": "numbered_question"},
            {"question": "2. Who won the war?",
             "answer": "The allied powers won.", "type": "numbered_question"},
        ]

    def test_vocabulary_section_type_parses_terms(self):
        # A marker typed 'vocabulary' routes the section through the vocab parser.
        doc = ("VOCAB\n"
               "Osmosis: movement of water\n"
               "Diffusion: spreading of particles\n")
        res = rx.extract_student_responses(
            doc, custom_markers=[{"start": "VOCAB", "type": "vocabulary"}])
        assert res["extracted_responses"] == [
            {"question": "Osmosis", "answer": "movement of water",
             "type": "vocab_term"},
            {"question": "Diffusion", "answer": "spreading of particles",
             "type": "vocab_term"},
        ]

    def test_fitb_blank_underscore_line_skipped(self):
        # FITB path: an underscore-only blank line is dropped; only the real
        # filled answer survives.
        doc = ("Fill in the blank worksheet\n"
               "1. The mitochondria is the powerhouse of the cell here.\n"
               "2. _______________\n")
        res = rx.extract_student_responses(doc)
        answers = [r["answer"] for r in res["extracted_responses"]]
        assert "The mitochondria is the powerhouse of the cell here." in answers
        assert all("___" not in a for a in answers)
