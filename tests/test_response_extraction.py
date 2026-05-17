from backend.services import response_extraction as rx


def test_module_is_pure_no_network_no_io():
    src = open(rx.__file__, encoding="utf-8").read()
    assert "from assignment_grader" not in src and "import assignment_grader" not in src
    for forbidden in ("import requests", "import openai", "import anthropic",
                       "from flask import", "OpenAI(", "Anthropic("):
        assert forbidden not in src, f"service must be network-free: found {forbidden}"


def test_strip_emojis_is_pure():
    assert rx.strip_emojis("hi \U0001F600 there") == "hi  there"


def test_is_question_or_prompt_returns_bool():
    assert isinstance(rx.is_question_or_prompt("What is 2+2?"), bool)


# ── Leaf characterization tests ──────────────────────────────────────────────


def test_parse_numbered_questions_three_block():
    text = (
        "1. What was the Louisiana Purchase?\nIt was a land deal.\n"
        "2. Why did Jefferson buy it?\nTo expand the country.\n"
        "3. When did it happen?\n1803"
    )
    result = rx.parse_numbered_questions(text)
    assert len(result) == 3
    assert result[0] == {"question": "1. What was the Louisiana Purchase?", "answer": "It was a land deal.", "is_blank": False}
    assert result[1] == {"question": "2. Why did Jefferson buy it?", "answer": "To expand the country.", "is_blank": False}
    assert result[2] == {"question": "3. When did it happen?", "answer": "1803", "is_blank": False}


def test_parse_vocab_terms_three_terms():
    text = (
        "Manifest Destiny: the belief that expansion westward was inevitable\n"
        "Annexation: the act of adding new territory to a country\n"
        "Treaty: a formal agreement between nations"
    )
    result = rx.parse_vocab_terms(text)
    assert len(result) == 3
    assert result[0] == {"term": "Manifest Destiny", "answer": "the belief that expansion westward was inevitable", "is_blank": False}
    assert result[1] == {"term": "Annexation", "answer": "the act of adding new territory to a country", "is_blank": False}
    assert result[2] == {"term": "Treaty", "answer": "a formal agreement between nations", "is_blank": False}


def test_fuzzy_find_marker_exact():
    doc = "Some text before\nVOCABULARY\nsome content after"
    assert rx.fuzzy_find_marker(doc, "VOCABULARY") == 17


def test_fuzzy_find_marker_near_match_emoji():
    doc = "Some text\n\U0001F4DA VOCABULARY\nmore content"
    result = rx.fuzzy_find_marker(doc, "VOCABULARY")
    assert result == 12


def test_extract_fitb_by_template_comparison_one_blank():
    student = "1. The capital of France is Paris."
    template = "fill in the blanks below"
    result = rx.extract_fitb_by_template_comparison(student, template)
    assert result == [{"question": "Item 1", "answer": "The capital of France is Paris.", "type": "fill_in_blank_sentence"}]


def test_strip_template_lines_removes_template_line():
    response = "Summarize the key events in 4-5 sentences.\nThe war ended in 1945 with Allied victory."
    marker = "SUMMARY"
    template = "SUMMARY\nSummarize the key events in 4-5 sentences.\nVOCABULARY"
    result = rx._strip_template_lines(response, marker, template)
    assert result == "The war ended in 1945 with Allied victory."


def test_filter_questions_from_response_drops_question():
    # Question with answer on next line: answer is kept
    assert rx.filter_questions_from_response("What year was the Louisiana Purchase?\n1803") == "1803"
    # Just a question: empty result
    assert rx.filter_questions_from_response("How did slavery affect daily life?") == ""


def test_is_question_or_prompt_question_vs_answer():
    assert rx.is_question_or_prompt("What is 2+2?") is True
    assert rx.is_question_or_prompt("The answer is 4 because simple arithmetic") is False


def test_strip_emojis_mixed_text():
    assert rx.strip_emojis("Hello \U0001F600 World \U0001F680") == "Hello  World"
