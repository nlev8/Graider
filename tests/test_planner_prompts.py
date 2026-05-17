from backend.services import planner_prompts as pp


def test_period_block_is_string_and_pure():
    out = pp._build_period_differentiation_block("Honors")
    assert isinstance(out, str)
    src = open(pp.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src


def test_assignment_prompt_includes_config_signal():
    prompt = pp._build_assignment_prompt(
        {"title": "L1", "objectives": ["o1"]},
        {"num_questions": 5},
        assignment_type="essay",
    )
    assert isinstance(prompt, str) and len(prompt) > 0
