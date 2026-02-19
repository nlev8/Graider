"""
Test: Tool schema validation and handler coverage.
Every TOOL_DEFINITIONS entry must have name/description/input_schema,
and every handler must exist.

NOTE: These tests import at call time to avoid ordering issues with monkeypatch.
"""
import backend.services.assistant_tools as at


def test_tool_definitions_have_required_fields():
    """Every tool definition must have name, description, input_schema."""
    for td in at.TOOL_DEFINITIONS:
        assert "name" in td, f"Missing 'name' in tool definition: {td}"
        assert "description" in td, f"Missing 'description' for tool: {td.get('name')}"
        assert "input_schema" in td, f"Missing 'input_schema' for tool: {td.get('name')}"
        assert isinstance(td["input_schema"], dict), f"input_schema not a dict for: {td['name']}"
        assert td["input_schema"].get("type") == "object", f"input_schema type not 'object' for: {td['name']}"


def test_every_definition_has_handler():
    """Every tool in TOOL_DEFINITIONS must have a matching handler."""
    handler_names = set(at.TOOL_HANDLERS.keys())
    for td in at.TOOL_DEFINITIONS:
        name = td["name"]
        assert name in handler_names, f"Tool '{name}' has definition but no handler"


def test_every_handler_has_definition():
    """Every handler must have a matching definition."""
    definition_names = set(td["name"] for td in at.TOOL_DEFINITIONS)
    for name in at.TOOL_HANDLERS:
        assert name in definition_names, f"Handler '{name}' has no matching definition"


def test_no_duplicate_tool_names():
    """No duplicate names in TOOL_DEFINITIONS."""
    names = [td["name"] for td in at.TOOL_DEFINITIONS]
    assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"


def test_handlers_are_callable():
    """All handlers must be callable functions."""
    for name, handler in at.TOOL_HANDLERS.items():
        assert callable(handler), f"Handler '{name}' is not callable"


def test_tool_count():
    """Verify we have the expected 52 tools (29 original + 23 new)."""
    assert len(at.TOOL_DEFINITIONS) >= 52, f"Expected >= 52 tools, got {len(at.TOOL_DEFINITIONS)}"
    assert len(at.TOOL_HANDLERS) >= 52, f"Expected >= 52 handlers, got {len(at.TOOL_HANDLERS)}"


def test_new_tools_present():
    """Verify all 23 new tools are registered."""
    names = set(td["name"] for td in at.TOOL_DEFINITIONS)
    new_tools = [
        # EdTech (6)
        "generate_kahoot_quiz", "generate_blooket_set", "generate_gimkit_kit",
        "generate_quizlet_set", "generate_nearpod_questions", "generate_canvas_qti",
        # Analytics (4)
        "get_grade_trends", "get_rubric_weakness", "flag_at_risk_students", "compare_assignments",
        # Planning (7)
        "suggest_remediation", "align_to_standards", "get_pacing_status",
        "generate_bell_ringer", "generate_exit_ticket", "suggest_grouping", "generate_sub_plans",
        # Communication (4)
        "generate_progress_report", "generate_report_card_comments",
        "draft_student_feedback", "generate_parent_conference_notes",
        # Student (2)
        "get_student_accommodations", "get_student_streak",
    ]
    for tool in new_tools:
        assert tool in names, f"New tool '{tool}' not found in TOOL_DEFINITIONS"


def test_descriptions_non_empty():
    """All descriptions should be meaningful (at least 20 chars)."""
    for td in at.TOOL_DEFINITIONS:
        desc = td.get("description", "")
        assert len(desc) >= 20, f"Description too short for '{td['name']}': '{desc}'"
