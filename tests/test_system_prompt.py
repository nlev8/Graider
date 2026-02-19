"""
Test: System prompt references all tools.
"""
from backend.services.assistant_tools import TOOL_DEFINITIONS


def test_all_new_tools_documented():
    """Verify the system prompt text in assistant_routes.py mentions every new tool."""
    import os
    routes_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               "backend", "routes", "assistant_routes.py")
    with open(routes_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_tools = [
        "generate_kahoot_quiz", "generate_blooket_set", "generate_gimkit_kit",
        "generate_quizlet_set", "generate_nearpod_questions", "generate_canvas_qti",
        "get_grade_trends", "get_rubric_weakness", "flag_at_risk_students", "compare_assignments",
        "get_grade_distribution", "detect_score_outliers",
        "suggest_remediation", "align_to_standards", "get_pacing_status",
        "generate_bell_ringer", "generate_exit_ticket", "suggest_grouping", "generate_sub_plans",
        "generate_progress_report", "generate_report_card_comments",
        "draft_student_feedback", "generate_parent_conference_notes",
        "get_student_accommodations", "get_student_streak",
    ]
    for tool in new_tools:
        assert tool in content, f"Tool '{tool}' not found in assistant_routes.py system prompt"


def test_original_tools_still_documented():
    """Verify original tools are still in the system prompt."""
    import os
    routes_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               "backend", "routes", "assistant_routes.py")
    with open(routes_path, "r", encoding="utf-8") as f:
        content = f.read()

    original_tools = [
        "query_grades", "get_student_summary", "get_class_analytics",
        "get_assignment_stats", "list_assignments", "generate_worksheet",
        "generate_document", "save_memory", "get_standards",
    ]
    for tool in original_tools:
        assert tool in content, f"Original tool '{tool}' missing from system prompt"
