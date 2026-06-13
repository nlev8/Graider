"""
Report / Export / Calendar / Resource Assistant Tools
=====================================================
Tools for exporting grades, generating documents & worksheets,
curriculum standards lookup, calendar management, resource browsing,
parent communication, and assignment config saving.

This package was split out of the former single-file module of the same name
(it had grown to 2,723 LOC). Every public symbol the rest of the codebase and
the test suite imported from ``backend.services.assistant_tools_reports`` is
re-exported below, so existing imports keep working unchanged. Behaviour is
byte-identical (pure move of whole functions).
"""
# Module-level path constants (public surface; preserved from the old module).
from ._paths import (
    CREDS_FILE,
    PROJECT_ROOT,
    PARENT_CONTACTS_FILE,
    CALENDAR_FILE,
)

# Tool definition schemas.
from .tool_defs import REPORT_TOOL_DEFINITIONS

# Lesson tools.
from .lessons import (
    _analyze_group_weaknesses,
    _match_standards,
    recommend_next_lesson,
    get_recent_lessons,
)

# Document / worksheet / resource tools.
from .documents import (
    MAX_RESOURCE_TEXT,
    _extract_pdf_text,
    _extract_docx_text,
    generate_worksheet_tool,
    generate_document_tool,
    generate_csv_tool,
    save_document_style_tool,
    list_document_styles_tool,
    list_resources_tool,
    read_resource_tool,
)

# Grade export + Focus assignment + student lookup tools.
from .grades import (
    create_focus_assignment,
    export_grades_csv,
    lookup_student_info,
)

# Standards tools.
from .standards import (
    get_standards_tool,
    list_all_standards_tool,
)

# Calendar tools (+ the curriculum-map date parser they use).
from .calendar_tools import (
    _parse_curriculum_map_for_dates,
    get_calendar,
    schedule_lesson_tool,
    unschedule_lesson_tool,
    add_calendar_holiday,
)

# Assignment-config saving.
from .config import save_assignment_config

# Communication tools + pending-send executor.
from .comms import (
    _parse_student_name,
    _fill_email_template,
    send_parent_emails,
    send_focus_comms,
    confirm_and_send,
)


# ═══════════════════════════════════════════════════════
# EXPORT MAP
# ═══════════════════════════════════════════════════════

REPORT_TOOL_HANDLERS = {
    "create_focus_assignment": create_focus_assignment,
    "export_grades_csv": export_grades_csv,
    "lookup_student_info": lookup_student_info,
    "generate_worksheet": generate_worksheet_tool,
    "generate_document": generate_document_tool,
    "generate_csv": generate_csv_tool,
    "save_document_style": save_document_style_tool,
    "list_document_styles": list_document_styles_tool,
    "recommend_next_lesson": recommend_next_lesson,
    "get_standards": get_standards_tool,
    "list_all_standards": list_all_standards_tool,
    "get_recent_lessons": get_recent_lessons,
    "get_calendar": get_calendar,
    "schedule_lesson": schedule_lesson_tool,
    "unschedule_lesson": unschedule_lesson_tool,
    "add_calendar_holiday": add_calendar_holiday,
    "list_resources": list_resources_tool,
    "read_resource": read_resource_tool,
    "save_assignment_config": save_assignment_config,
    "send_parent_emails": send_parent_emails,
    "send_focus_comms": send_focus_comms,
    "confirm_and_send": confirm_and_send,
}

__all__ = [
    "CREDS_FILE",
    "PROJECT_ROOT",
    "PARENT_CONTACTS_FILE",
    "CALENDAR_FILE",
    "REPORT_TOOL_DEFINITIONS",
    "REPORT_TOOL_HANDLERS",
    "MAX_RESOURCE_TEXT",
    "_analyze_group_weaknesses",
    "_match_standards",
    "recommend_next_lesson",
    "get_recent_lessons",
    "_extract_pdf_text",
    "_extract_docx_text",
    "generate_worksheet_tool",
    "generate_document_tool",
    "generate_csv_tool",
    "save_document_style_tool",
    "list_document_styles_tool",
    "list_resources_tool",
    "read_resource_tool",
    "create_focus_assignment",
    "export_grades_csv",
    "lookup_student_info",
    "get_standards_tool",
    "list_all_standards_tool",
    "_parse_curriculum_map_for_dates",
    "get_calendar",
    "schedule_lesson_tool",
    "unschedule_lesson_tool",
    "add_calendar_holiday",
    "save_assignment_config",
    "_parse_student_name",
    "_fill_email_template",
    "send_parent_emails",
    "send_focus_comms",
    "confirm_and_send",
]
