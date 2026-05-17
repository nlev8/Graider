from backend.services import planner_prompts as pp


def test_period_block_is_string_and_pure():
    out = pp._build_period_differentiation_block("Honors")
    assert isinstance(out, str)
    src = open(pp.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src


def test_assignment_prompt_essay_reflects_config():
    # Pins real interpolation: subject and grade appear verbatim in the essay prompt header.
    # Verified by running the function and inspecting p[:600] (2026-05-17).
    prompt = pp._build_assignment_prompt(
        {"title": "L1"},
        {"subject": "Biology", "grade": "9"},
        assignment_type="essay",
    )
    assert isinstance(prompt, str) and len(prompt) > 0
    low = prompt.lower()
    assert "biology" in low and "grade 9" in low
