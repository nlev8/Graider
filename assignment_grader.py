"""
Assignment Grader for 6th Grade Social Studies
===============================================
Tailored for Southwestern Middle School

FILE NAMING EXPECTED: FirstName_LastName_AssignmentName.docx
ROSTER FORMAT: "LastName; FirstName" with Student ID and Email columns

FERPA COMPLIANCE:
- Student names are NOT sent to OpenAI's API
- Only assignment content is analyzed for grading
- All student identification stays local on your computer
- OpenAI API data is not used to train models (per their policy)
- Consult your district's policies for AI tool usage

SETUP:
1. pip install openai python-docx openpyxl python-dotenv
2. Create .env file with: OPENAI_API_KEY=your-key-here
3. Update the folder paths below
4. Update the ASSIGNMENT_INSTRUCTIONS for each assignment
"""

import os
from dotenv import load_dotenv

# NOTE (Wave 7 Phase B): csv, random, threading, datetime, typing.List/Optional and
# pydantic.BaseModel were dropped here — they became unused after the response schemas +
# TokenTracker moved to backend/services/grading_models.py and the export/roster helpers
# moved to their own services in earlier slices.

# ── Tier 2 Slice 2 PR1+PR2: pure parsing/extraction helpers extracted to ────
# backend/services/response_extraction.py (no Flask, no network, no I/O).
# Re-exported here so existing `from assignment_grader import ...` callers
# keep resolving unchanged.
from backend.services.response_extraction import (  # noqa: F401
    STUDENT_WORK_MARKERS as STUDENT_WORK_MARKERS,
    _strip_template_lines as _strip_template_lines,
    extract_fitb_by_template_comparison as extract_fitb_by_template_comparison,
    extract_student_responses as extract_student_responses,
    extract_student_work as extract_student_work,
    filter_questions_from_response as filter_questions_from_response,
    format_extracted_for_grading as format_extracted_for_grading,
    fuzzy_find_marker as fuzzy_find_marker,
    is_question_or_prompt as is_question_or_prompt,
    parse_numbered_questions as parse_numbered_questions,
    parse_vocab_terms as parse_vocab_terms,
    strip_emojis as strip_emojis,
)


# Structured-output response schemas moved to backend/services/grading_models.py
# (Wave 7 Phase B). Re-exported so existing `from assignment_grader import GradingResponse`
# (and the other schemas) callers keep resolving unchanged.
from backend.services.grading_models import (  # noqa: F401
    AiDetectionResult as AiDetectionResult,
    DetectionResponse as DetectionResponse,
    GradingBreakdown as GradingBreakdown,
    GradingResponse as GradingResponse,
    PlagiarismDetectionResult as PlagiarismDetectionResult,
    SkillsDemonstrated as SkillsDemonstrated,
)

# Import student history for personalized feedback
try:
    from backend.student_history import build_history_context
except ImportError:
    # Fallback if running standalone or module not available
    def build_history_context(student_id):
        return ""

# Import accommodations for IEP/504 support (FERPA compliant)
try:
    from backend.accommodations import build_accommodation_prompt
except ImportError:
    # Fallback if running standalone or module not available
    def build_accommodation_prompt(student_id):
        return ""

# Load environment variables from .env file (override system env vars)
import os
app_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(app_dir, '.env'), override=True)

# =============================================================================
# TOKEN / COST TRACKING
# =============================================================================

# MODEL_PRICING + TokenTracker moved to backend/services/grading_models.py (Wave 7 Phase B).
# MODEL_PRICING uses the explicit `as` form — external importers (planner_routes,
# assistant_routes, assignment_post_processing) do `from assignment_grader import MODEL_PRICING`.
from backend.services.grading_models import (  # noqa: F401
    MODEL_PRICING as MODEL_PRICING,
    TokenTracker as TokenTracker,
)


# Student-response extraction moved to backend/services/response_extraction.py (re-exported via the shim above).


# =============================================================================
# WRITING STYLE ANALYSIS - For AI Detection
# =============================================================================

from backend.services.writing_style import analyze_writing_style as analyze_writing_style  # noqa: F401 re-export (test_writing_style imports via assignment_grader)
from backend.services.writing_style import compare_writing_styles as compare_writing_styles  # noqa: F401 re-export (test_writing_style imports via assignment_grader)


# Writing-profile persistence moved to backend/services/writing_profile.py (Wave 7).
# Explicit `as` re-export so callers (grade_multipass/grade_assignment here, plus any
# external importer) keep resolving `assignment_grader.update_writing_profile/get_writing_profile`.
from backend.services.writing_profile import (  # noqa: F401
    get_writing_profile as get_writing_profile,
    update_writing_profile as update_writing_profile,
)

# =============================================================================
# CONFIGURATION - UPDATE THESE FOR EACH GRADING SESSION
# =============================================================================

# CLI config paths (ASSIGNMENT_FOLDER / OUTPUT_FOLDER / ROSTER_FILE) moved to
# backend/services/grader_cli.py alongside run_grading (CLI/email split, Wave 8).

# BYOK: API keys resolved per-request via contextvars → user keys → env vars

# Assignment name (used in output files and emails) — relocated to grading_models.py so the
# CLI/email service modules can reference it without importing this facade (no-cycle rule).
from backend.services.grading_models import ASSIGNMENT_NAME as ASSIGNMENT_NAME  # noqa: F401, E402

# Marker phrase(s) that indicate where student work begins
# Only content within the section (until next header) will be graded
# (Moved to backend/services/response_extraction.py — re-exported via shim below)

# Section headers that indicate a NEW section (stops extraction from previous marker)
SECTION_HEADERS = [
    "vocabulary",
    "vocabulary mini-lesson",
    "key vocabulary",
    "notes",
    "guided notes",
    "reading",
    "directions",
    "instructions",
    "primary source",
    "background",
    "overview",
    "introduction",
]


# =============================================================================
# GRADING RUBRIC - Customize point values and criteria as needed
# =============================================================================

# GRADING_RUBRIC (default rubric) moved to backend/services/grading_pipeline.py with its
# only user grade_assignment (Wave 7 Phase B). Re-exported for any dynamic reference.
from backend.services.grading_pipeline import GRADING_RUBRIC as GRADING_RUBRIC  # noqa: F401

# DEFAULT ASSIGNMENT INSTRUCTIONS - Only used if no assignment-specific config provided
# This should be empty or generic - assignment-specific instructions come from Builder configs
from backend.services.grading_pipeline import ASSIGNMENT_INSTRUCTIONS as ASSIGNMENT_INSTRUCTIONS  # noqa: F401 re-export


# =============================================================================
# ROSTER LOADING - Reads your Excel student list
# =============================================================================

from backend.services.grader_roster import load_roster as load_roster  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


# build_roster_from_periods moved to backend/services/grader_roster.py (Wave 7).
# Explicit `as` re-export so callers (email_routes.py imports it) keep resolving
# assignment_grader.build_roster_from_periods.
from backend.services.grader_roster import build_roster_from_periods as build_roster_from_periods  # noqa: F401


# =============================================================================
# FILE PARSING - Extract student name from filename
# =============================================================================

from backend.services.submission_parsing import parse_filename as parse_filename  # noqa: F401 explicit re-export (mypy no_implicit_reexport: grading/pipeline.py imports this)


from backend.services.submission_parsing import read_docx_file as read_docx_file  # noqa: F401 explicit re-export (grader-internal caller; consistency)


from backend.services.submission_parsing import read_docx_file_structured as read_docx_file_structured  # noqa: F401 explicit re-export (grader-internal caller; consistency)


from backend.services.submission_parsing import extract_from_tables as extract_from_tables  # noqa: F401 explicit re-export (grader-internal callers; consistency)


from backend.services.submission_parsing import extract_from_graider_text as extract_from_graider_text  # noqa: F401 explicit re-export (grader-internal callers; consistency)


from backend.services.submission_parsing import read_image_file as read_image_file  # noqa: F401 explicit re-export (grader-internal caller; consistency)


from backend.services.submission_parsing import read_assignment_file as read_assignment_file  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


# =============================================================================
# FERPA COMPLIANCE - PII SANITIZATION
# =============================================================================


from backend.services.grader_text_prep import preprocess_for_ai_detection as preprocess_for_ai_detection  # noqa: F401 re-export (test_grader_text_prep imports via assignment_grader)
from backend.services.grader_text_prep import sanitize_pii_for_ai as sanitize_pii_for_ai  # noqa: F401 re-export (test_grader_text_prep imports via assignment_grader)


from backend.services.grader_text_prep import log_pii_sanitization as log_pii_sanitization  # noqa: F401


# =============================================================================
# AI/PLAGIARISM DETECTION (Parallel Agent using GPT-4o-mini)
# =============================================================================



# detect_ai_plagiarism moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import detect_ai_plagiarism as detect_ai_plagiarism  # noqa: F401


# grade_with_ensemble moved to backend/services/grading_pipeline.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_pipeline import grade_with_ensemble as grade_with_ensemble  # noqa: F401 (pipeline.py imports via assignment_grader)


# grade_with_parallel_detection moved to backend/services/grading_pipeline.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_pipeline import grade_with_parallel_detection as grade_with_parallel_detection  # noqa: F401 (pipeline.py imports via assignment_grader)


# =============================================================================
# MULTI-PASS GRADING PIPELINE
# =============================================================================

# Per-question / feedback response schemas moved to backend/services/grading_models.py
# (Wave 7 Phase B). Re-exported for `from assignment_grader import ...` callers.
from backend.services.grading_models import (  # noqa: F401
    FeedbackResponse as FeedbackResponse,
    PerQuestionResponse as PerQuestionResponse,
    QuestionGrade as QuestionGrade,
)


from backend.services.grading_prep import _distribute_points as _distribute_points, _is_math_subject as _is_math_subject, _parse_expected_answers as _parse_expected_answers  # noqa: F401 re-export (test_grading_prep imports via assignment_grader)
from backend.services.grading_prep import build_section_rubric as build_section_rubric  # noqa: F401 re-export (test_build_section_rubric imports via assignment_grader)
from backend.services.grading_prep import MATH_SUBJECTS as MATH_SUBJECTS  # noqa: F401 re-export (tests + callers import via assignment_grader)


# grade_per_question moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import grade_per_question as grade_per_question  # noqa: F401


# generate_feedback moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import generate_feedback as generate_feedback  # noqa: F401


# grade_multipass moved to backend/services/grading_pipeline.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_pipeline import grade_multipass as grade_multipass  # noqa: F401


# =============================================================================
# SECTION-BASED RUBRIC BUILDER
# =============================================================================



# =============================================================================
# BILINGUAL FEEDBACK TRANSLATION (two-pass system for ELL students)
# =============================================================================

# _translate_feedback moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import _translate_feedback as _translate_feedback  # noqa: F401


# =============================================================================
# JSON PARSING HELPERS
# =============================================================================

from backend.services.grader_json import _try_parse_json_fallback as _try_parse_json_fallback  # noqa: F401 re-export (test_grader_json imports via assignment_grader)


# =============================================================================
# AI GRADING WITH CLAUDE
# =============================================================================

# grade_assignment moved to backend/services/grading_pipeline.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_pipeline import grade_assignment as grade_assignment  # noqa: F401


# =============================================================================
# EMAIL GENERATION
# =============================================================================

from backend.services.grader_export import generate_email_content as generate_email_content  # noqa: F401 explicit re-export (mypy no_implicit_reexport)


from backend.services.grader_export import save_emails_to_folder as save_emails_to_folder  # noqa: F401


from backend.services.grader_export import create_outlook_drafts as create_outlook_drafts  # noqa: F401


# =============================================================================
# CSV EXPORT FOR FOCUS
# =============================================================================

from backend.services.grader_export import export_focus_csv as export_focus_csv  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


from backend.services.grader_export import save_to_master_csv as save_to_master_csv  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


from backend.services.grader_export import export_detailed_report as export_detailed_report  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


# =============================================================================
# MAIN GRADING WORKFLOW
# =============================================================================

from backend.services.grader_cli import run_grading as run_grading  # noqa: F401  (CLI; facade __main__ + test callbacks import it here)


# =============================================================================
# RUN THE SCRIPT
# =============================================================================

if __name__ == "__main__":
    # Update the paths at the top of this file, then run!
    results = run_grading(
        create_outlook_emails=False  # Set True if you have Outlook desktop on Windows
    )
