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
import json
import re
import concurrent.futures
from pathlib import Path
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

from backend.services.writing_style import analyze_writing_style
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

# Folder containing student assignment files (.docx)
ASSIGNMENT_FOLDER = "/Users/alexc/Downloads/Assignments"

# Output folder for CSV and email files
OUTPUT_FOLDER = "/Users/alexc/Downloads/Assignment Grader/Results"

# Path to your student roster Excel file
ROSTER_FILE = "/Users/alexc/Downloads/Assignment Grader/all_students_updated.xlsx"

# BYOK: API keys resolved per-request via contextvars → user keys → env vars

# Assignment name (used in output files and emails)
ASSIGNMENT_NAME = ""  # Set dynamically from assignment config; empty = use filename

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


from backend.services.grader_text_prep import preprocess_for_ai_detection
from backend.services.grader_text_prep import sanitize_pii_for_ai as sanitize_pii_for_ai  # noqa: F401 re-export (test_grader_text_prep imports via assignment_grader)


def log_pii_sanitization(student_name: str, original_len: int, sanitized_len: int, removals: dict):
    """
    Log PII sanitization actions for audit purposes.
    Does not log actual PII - only counts and types of removals.
    """
    # This could be extended to write to an audit log file
    if any(removals.values()):
        print(f"  🔒 PII sanitized for student submission (removed: {', '.join(k for k, v in removals.items() if v > 0)})")


# =============================================================================
# AI/PLAGIARISM DETECTION (Parallel Agent using GPT-4o-mini)
# =============================================================================



# detect_ai_plagiarism moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import detect_ai_plagiarism as detect_ai_plagiarism  # noqa: F401


def grade_with_ensemble(student_name: str, assignment_data: dict, custom_ai_instructions: str = '',
                        grade_level: str = '6', subject: str = 'Social Studies',
                        ensemble_models: list = None, student_id: str = None,
                        assignment_template: str = None, rubric_prompt: str = None,
                        custom_markers: list = None, exclude_markers: list = None,
                        marker_config: list = None, effort_points: int = 15,
                        extraction_mode: str = 'structured', grading_style: str = 'standard',
                        rubric_weights: list = None) -> dict:
    """
    Grade assignment using multiple AI models and combine results.

    Args:
        ensemble_models: List of model names to use (e.g., ['gpt-4o-mini', 'claude-haiku', 'gemini-flash'])
        marker_config: List of marker configs with points for section-based grading
        effort_points: Points for effort/engagement category (default 15)

    Returns:
        Combined result with:
        - score: Average of all model scores
        - ensemble_scores: Individual scores from each model
        - ensemble_feedback: Feedback from each model
        - letter_grade: Based on averaged score
    """
    if not ensemble_models or len(ensemble_models) < 2:
        # Fall back to single model grading
        model = ensemble_models[0] if ensemble_models else 'gpt-4o-mini'
        return grade_with_parallel_detection(student_name, assignment_data, custom_ai_instructions,
                                             grade_level, subject, model, student_id,
                                             assignment_template, rubric_prompt, custom_markers, exclude_markers,
                                             marker_config, effort_points, extraction_mode, grading_style,
                                             rubric_weights=rubric_weights)

    print(f"  🎯 Ensemble grading with {len(ensemble_models)} models: {', '.join(ensemble_models)}")

    # Run all models in parallel
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ensemble_models)) as executor:
        futures = {}
        for model in ensemble_models:
            future = executor.submit(
                grade_assignment, student_name, assignment_data, custom_ai_instructions,
                grade_level, subject, model, student_id, assignment_template, rubric_prompt,
                custom_markers, exclude_markers, marker_config, effort_points, extraction_mode,
                grading_style, rubric_weights=rubric_weights
            )
            futures[future] = model

        # Collect results
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
                results[model] = result
                print(f"    ✓ {model}: {result.get('score', 0)} ({result.get('letter_grade', 'N/A')})")
            except Exception as e:
                print(f"    ✗ {model}: Error - {str(e)[:50]}")
                results[model] = {"score": 0, "letter_grade": "ERROR", "feedback": f"Error: {e}"}

    # Calculate ensemble score
    valid_scores = [r.get('score', 0) for r in results.values() if r.get('letter_grade') != 'ERROR']
    if not valid_scores:
        return {"score": 0, "letter_grade": "ERROR", "feedback": "All models failed", "breakdown": {}}

    # Use median for robustness against outliers
    valid_scores.sort()
    if len(valid_scores) % 2 == 0:
        median_score = (valid_scores[len(valid_scores)//2 - 1] + valid_scores[len(valid_scores)//2]) / 2
    else:
        median_score = valid_scores[len(valid_scores)//2]

    avg_score = sum(valid_scores) / len(valid_scores)
    final_score = round(median_score)  # Use median as final

    # Determine letter grade
    if final_score >= 90:
        letter_grade = "A"
    elif final_score >= 80:
        letter_grade = "B"
    elif final_score >= 70:
        letter_grade = "C"
    elif final_score >= 60:
        letter_grade = "D"
    else:
        letter_grade = "F"

    # Pick the best feedback (from the model closest to median score)
    best_model = min(results.keys(), key=lambda m: abs(results[m].get('score', 0) - median_score) if results[m].get('letter_grade') != 'ERROR' else 999)
    best_result = results[best_model]

    # Build ensemble result
    ensemble_result = {
        "score": final_score,
        "letter_grade": letter_grade,
        "feedback": best_result.get("feedback", ""),
        "breakdown": best_result.get("breakdown", {}),
        "ai_detection": best_result.get("ai_detection", {}),
        "plagiarism_detection": best_result.get("plagiarism_detection", {}),
        "student_responses": best_result.get("student_responses", []),
        "unanswered_questions": best_result.get("unanswered_questions", []),
        # Ensemble-specific fields
        "ensemble_grading": True,
        "ensemble_models": ensemble_models,
        "ensemble_scores": {model: results[model].get("score", 0) for model in results},
        "ensemble_grades": {model: results[model].get("letter_grade", "N/A") for model in results},
        "ensemble_avg": round(avg_score, 1),
        "ensemble_median": round(median_score, 1),
        "ensemble_feedback_source": best_model,
    }

    print(f"  📊 Ensemble result: {final_score} ({letter_grade}) - avg: {avg_score:.1f}, median: {median_score:.1f}")

    return ensemble_result


def grade_with_parallel_detection(student_name: str, assignment_data: dict, custom_ai_instructions: str = '',
                                   grade_level: str = '6', subject: str = 'Social Studies',
                                   ai_model: str = 'gpt-4o-mini', student_id: str = None,
                                   assignment_template: str = None, rubric_prompt: str = None,
                                   custom_markers: list = None, exclude_markers: list = None,
                                   marker_config: list = None, effort_points: int = 15,
                                   extraction_mode: str = 'structured', grading_style: str = 'standard',
                                   student_history: str = '', rubric_weights: list = None) -> dict:
    """
    Grade assignment with parallel AI/plagiarism detection.
    Runs detection (GPT-4o-mini) and grading simultaneously for speed.

    Args:
        rubric_prompt: Custom rubric prompt string from Settings (overrides default)
        marker_config: List of marker configs with points for section-based grading
        effort_points: Points for effort/engagement category (default 15)
    """
    # Extract responses first (needed for both detection and grading context)
    content = assignment_data.get("content", "")
    extracted_text = ""

    # Strip embedded answer key before extraction (handles -- and --- variants)
    if content and "GRAIDER_ANSWER_KEY_START" in content:
        content = content.split("GRAIDER_ANSWER_KEY_START")[0].rstrip().rstrip('-')
        assignment_data = {**assignment_data, "content": content}
        print(f"  🧹 Stripped embedded answer key from document")

    # Priority: Graider structured tables > Graider text fallback > regex extraction
    extraction_result = None
    graider_tables = assignment_data.get("graider_tables")
    if graider_tables:
        print(f"  📊 Parallel detection: Using Graider table extraction ({len(graider_tables)} tables)")
        extraction_result = extract_from_tables(graider_tables, exclude_markers)
    elif assignment_data.get("type") == "text" and content:
        # Try GRAIDER tag plain-text fallback before generic extraction
        if '[GRAIDER:' in content:
            extraction_result = extract_from_graider_text(content, exclude_markers)
        if not extraction_result or not extraction_result.get("extracted_responses"):
            extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)

    if extraction_result and extraction_result.get("extracted_responses"):
        # Filter out FITB and vocab items — only send written responses to detection
        # FITB answers (names, dates, facts) and vocab definitions naturally match sources
        skip_types = {'fitb_full', 'vocab_term'}
        written_responses = [
            r for r in extraction_result["extracted_responses"]
            if 'fill_in_blank' not in r.get('type', '') and r.get('type') not in skip_types
        ]
        # If no written responses (pure FITB), extracted_text stays empty → detection skipped
        extracted_text = "\n".join([
            f"Q: {r.get('question', 'Unknown')}\nA: {r.get('answer', '')}"
            for r in written_responses
        ])

    # If no extracted text, can't do parallel detection
    if not extracted_text:
        return grade_assignment(student_name, assignment_data, custom_ai_instructions,
                               grade_level, subject, ai_model, student_id, assignment_template, rubric_prompt,
                               custom_markers, exclude_markers, marker_config, effort_points, extraction_mode,
                               grading_style=grading_style)

    # Multi-pass grading for all providers
    use_multipass = True
    print(f"  🔄 Running parallel detection + multi-pass grading ({ai_model})...")

    # Preprocess text for AI detection (removes template text, focuses on student writing)
    detection_text = preprocess_for_ai_detection(extracted_text)

    # Shared token tracker for both detection and grading
    tracker = TokenTracker()

    # Run detection and grading in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        detection_future = executor.submit(detect_ai_plagiarism, detection_text, grade_level, token_tracker=tracker)

        if use_multipass:
            grading_future = executor.submit(grade_multipass, student_name, assignment_data,
                                             custom_ai_instructions, grade_level, subject,
                                             ai_model, student_id, assignment_template, rubric_prompt,
                                             custom_markers, exclude_markers, marker_config, effort_points,
                                             extraction_mode, grading_style, token_tracker=tracker,
                                             student_history=student_history, rubric_weights=rubric_weights)
        else:
            grading_future = executor.submit(grade_assignment, student_name, assignment_data,
                                             custom_ai_instructions, grade_level, subject,
                                             ai_model, student_id, assignment_template, rubric_prompt,
                                             custom_markers, exclude_markers, marker_config, effort_points,
                                             extraction_mode, grading_style, token_tracker=tracker,
                                             rubric_weights=rubric_weights)

        # Wait for both to complete
        detection_result = detection_future.result()
        grading_result = grading_future.result()

    # Skip detection merging for blank/incomplete submissions — nothing to detect
    if grading_result.get("letter_grade") == "INCOMPLETE" and grading_result.get("score", 0) == 0:
        print(f"  📝 Blank/incomplete submission — skipping AI/plagiarism detection merge")
        grading_result["token_usage"] = tracker.summary()
        return grading_result

    # Merge detection results into grading results
    # Detection agent's flags override grading agent's (more specialized)
    detection_ai = detection_result.get("ai_detection", {})
    detection_plag = detection_result.get("plagiarism_detection", {})

    grading_ai = grading_result.get("ai_detection", {})
    grading_plag = grading_result.get("plagiarism_detection", {})

    # Use the more severe flag from either source
    flag_severity = {"none": 0, "unlikely": 1, "possible": 2, "likely": 3}

    # AI detection - take the higher severity
    if flag_severity.get(detection_ai.get("flag", "none"), 0) >= flag_severity.get(grading_ai.get("flag", "none"), 0):
        grading_result["ai_detection"] = detection_ai
        if detection_ai.get("flag") in ["possible", "likely"]:
            print(f"  🤖 Detection agent flagged AI: {detection_ai.get('flag')} - {detection_ai.get('reason', '')[:100]}")

    # Plagiarism detection - take the higher severity
    if flag_severity.get(detection_plag.get("flag", "none"), 0) >= flag_severity.get(grading_plag.get("flag", "none"), 0):
        grading_result["plagiarism_detection"] = detection_plag
        if detection_plag.get("flag") in ["possible", "likely"]:
            print(f"  📋 Detection agent flagged plagiarism: {detection_plag.get('flag')} - {detection_plag.get('reason', '')[:100]}")

    # Apply score caps based on detection flags
    ai_flag = grading_result.get("ai_detection", {}).get("flag", "none")
    plag_flag = grading_result.get("plagiarism_detection", {}).get("flag", "none")
    original_score = grading_result.get("score", 0)

    # Determine cap based on flags
    cap = 100
    cap_reason = ""

    if ai_flag == "likely" and plag_flag == "likely":
        cap = 40
        cap_reason = "AI + Plagiarism detected"
    elif ai_flag == "likely":
        cap = 50
        cap_reason = "Likely AI-generated"
    elif plag_flag == "likely":
        cap = 50
        cap_reason = "Likely plagiarized"
    elif ai_flag == "possible":
        cap = 65
        cap_reason = "Possible AI use"
    elif plag_flag == "possible":
        cap = 65
        cap_reason = "Possible plagiarism"

    # Apply cap if needed
    if original_score > cap:
        grading_result["score"] = cap
        grading_result["score_capped"] = True
        grading_result["original_score"] = original_score
        grading_result["cap_reason"] = cap_reason
        # Update letter grade
        if cap <= 59:
            grading_result["letter_grade"] = "F"
        elif cap <= 69:
            grading_result["letter_grade"] = "D"
        elif cap <= 79:
            grading_result["letter_grade"] = "C"
        print(f"  ⚠️  Score capped: {original_score} → {cap} ({cap_reason})")

    # Replace feedback with academic integrity message for high AI/plagiarism likelihood
    # But NOT for blank submissions (they get their own feedback)
    ai_confidence = grading_result.get("ai_detection", {}).get("confidence", 0)
    student_responses = grading_result.get("student_responses", [])
    ai_score = grading_result.get("score", 0)
    # Only treat as blank if: no student_responses AND AI gave score 0 AND no JSON recovery.
    # Previously this fired whenever student_responses was empty, which could override
    # legitimate grades if the AI simply didn't populate that field.
    is_blank = (not student_responses and not grading_result.get("json_recovery")
                and (ai_score == 0 or ai_score is None))

    if is_blank:
        # Blank submission — zero score, clear feedback, no AI/plagiarism flags
        grading_result["feedback"] = "You submitted a blank assignment with no responses. Please complete all sections and resubmit."
        grading_result["score"] = 0
        grading_result["letter_grade"] = "INCOMPLETE"
        grading_result["ai_detection"] = {"flag": "none", "confidence": 0, "reason": "Blank submission — no content to evaluate."}
        grading_result["plagiarism_detection"] = {"flag": "none", "reason": "Blank submission — no content to evaluate."}
        grading_result.pop("academic_integrity_flag", None)
        print(f"  📝 Blank submission detected — scored as 0/INCOMPLETE")
    elif ai_confidence >= 50 or plag_flag in ["possible", "likely"]:
        grading_result["original_feedback"] = grading_result.get("feedback", "")
        grading_result["feedback"] = "Please resubmit using your own words. Copying and pasting from Google (plagiarism) or use of AI is considered a violation of academic integrity."
        grading_result["academic_integrity_flag"] = True
        print(f"  🚨 Academic integrity concern - feedback replaced")

    # Update token_usage with final tracker summary (includes both detection + grading)
    grading_result["token_usage"] = tracker.summary()

    return grading_result


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


from backend.services.grading_prep import _distribute_points, _is_math_subject, _parse_expected_answers
from backend.services.grading_prep import build_section_rubric as build_section_rubric  # noqa: F401 re-export (test_build_section_rubric imports via assignment_grader)
from backend.services.grading_prep import MATH_SUBJECTS as MATH_SUBJECTS  # noqa: F401 re-export (tests + callers import via assignment_grader)


# grade_per_question moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import grade_per_question as grade_per_question  # noqa: F401


# generate_feedback moved to backend/services/grading_leaves.py (Wave 7 Phase B). Re-export shim.
from backend.services.grading_leaves import generate_feedback as generate_feedback  # noqa: F401


def grade_multipass(student_name: str, assignment_data: dict, custom_ai_instructions: str = '',
                    grade_level: str = '6', subject: str = 'Social Studies',
                    ai_model: str = 'gpt-4o-mini', student_id: str = None,
                    assignment_template: str = None, rubric_prompt: str = None,
                    custom_markers: list = None, exclude_markers: list = None,
                    marker_config: list = None, effort_points: int = 15,
                    extraction_mode: str = 'structured', grading_style: str = 'standard',
                    token_tracker: 'TokenTracker' = None,
                    student_history: str = '', rubric_weights: list = None) -> dict:
    """Multi-pass grading pipeline for consistent, robust scoring.

    Pass 1: Extract responses (reuses existing extraction logic)
    Pass 2: Grade each question individually (parallel, structured output)
    Pass 3: Generate feedback (cheaper model)
    Final: Aggregate scores, apply caps, build result
    """
    # Determine provider from model name
    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "openai"

    tracker = token_tracker or TokenTracker()
    content = assignment_data.get("content", "")

    # === EXTRACTION ===
    # Priority: Graider structured tables > Graider text fallback > regex extraction
    extraction_result = None

    # Check for Graider table data (structured worksheets)
    graider_tables = assignment_data.get("graider_tables")
    if graider_tables:
        print(f"  📊 Multi-pass: Using Graider table extraction ({len(graider_tables)} tables)")
        extraction_result = extract_from_tables(graider_tables, exclude_markers)
    elif assignment_data.get("type") == "text" and content:
        # Try GRAIDER tag plain-text fallback before generic extraction
        if '[GRAIDER:' in content:
            extraction_result = extract_from_graider_text(content, exclude_markers)
        if not extraction_result or not extraction_result.get("extracted_responses"):
            extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)

    if extraction_result:
        answered = extraction_result.get("answered_questions", 0)
        total = extraction_result.get("total_questions", 0)
        print(f"  📋 Multi-pass: Extracted {answered}/{total} responses")

        if answered == 0:
            return {
                "score": 0, "letter_grade": "INCOMPLETE",
                "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                "feedback": "You submitted a blank assignment with no responses. Please complete all sections and resubmit.",
                "student_responses": [], "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
                "ai_detection": {"flag": "none", "confidence": 0, "reason": "Blank submission — no content to evaluate."},
                "plagiarism_detection": {"flag": "none", "reason": "Blank submission — no content to evaluate."},
                "skills_demonstrated": {"strengths": [], "developing": []},
                "excellent_answers": [], "needs_improvement": []
            }

        # Force zero if 80%+ of questions are blank — prevents template text inflation
        total_questions = extraction_result.get("total_questions", 0)
        blank_questions_count = len(extraction_result.get("blank_questions", [])) + len(extraction_result.get("missing_sections", []))
        if total_questions > 0 and blank_questions_count / total_questions >= 0.8:
            print(f"  ⚠️  NEARLY BLANK: {blank_questions_count}/{total_questions} questions blank (≥80%)")
            return {
                "score": 0, "letter_grade": "INCOMPLETE",
                "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                "feedback": f"Your assignment is nearly blank — {blank_questions_count} out of {total_questions} questions have no response. Please complete all sections and resubmit.",
                "student_responses": [], "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
                "ai_detection": {"flag": "none", "confidence": 0, "reason": "Nearly blank submission."},
                "plagiarism_detection": {"flag": "none", "reason": "Nearly blank submission."},
                "skills_demonstrated": {"strengths": [], "developing": []},
                "excellent_answers": [], "needs_improvement": []
            }

    if not extraction_result or not extraction_result.get("extracted_responses"):
        # Fall back to single-pass for edge cases
        print(f"  ⚠️ Multi-pass: No extracted responses, falling back to single-pass")
        return grade_assignment(student_name, assignment_data, custom_ai_instructions,
                               grade_level, subject, ai_model, student_id, assignment_template,
                               rubric_prompt, custom_markers, exclude_markers, marker_config,
                               effort_points, extraction_mode, grading_style)

    responses = extraction_result["extracted_responses"]

    # DEBUG: Log extracted responses before filtering
    print(f"  🔍 Multi-pass: {len(responses)} extracted responses before filtering:")
    for i, resp in enumerate(responses):
        q = resp.get("question", "?")[:80]
        a = resp.get("answer", "")[:120].replace('\n', ' ')
        t = resp.get("type", "?")
        print(f"      [{i+1}] Q: {q}")
        print(f"           A: {a}")
        print(f"           Type: {t}")

    # Filter question/prompt text from extracted answers before grading.
    # If filtering empties a response, move it to blank_questions so completeness caps apply.
    filtered_out = []
    for resp in responses:
        answer = resp.get("answer", "")
        if answer and resp.get("type") != "fitb":
            cleaned = filter_questions_from_response(answer)
            if cleaned and len(cleaned.strip()) >= 3:
                resp["answer"] = cleaned
            else:
                q_label = resp.get("question", "Unknown")
                print(f"      ⚠️ Response for '{q_label[:50]}' was only template text — marking blank")
                extraction_result.setdefault("blank_questions", []).append(q_label)
                filtered_out.append(resp)
    if filtered_out:
        responses = [r for r in responses if r not in filtered_out]
        extraction_result["extracted_responses"] = responses

    # Build expected answers lookup from gradingNotes within custom_ai_instructions
    expected_answers = _parse_expected_answers(custom_ai_instructions)

    # NOTE: accommodation context, student history, period differentiation, and rubric
    # type overrides are ALREADY embedded in custom_ai_instructions by app.py (lines 975-1119).
    # We pass the full string untruncated to each per-question call.

    # Append the custom rubric prompt (from Settings) so per-question graders see it.
    # In single-pass, rubric_prompt overrides GRADING_RUBRIC. In multipass, we append it
    # to the teacher instructions so each per-question call gets the rubric categories/weights.
    effective_instructions = custom_ai_instructions
    if rubric_prompt:
        effective_instructions += "\n\n" + rubric_prompt

    # === PASS 2: PER-QUESTION GRADING (parallel) ===
    total_content_points = 100 - effort_points
    question_meta = _distribute_points(responses, marker_config, total_content_points)

    # Use the selected model for per-question grading (no auto-upgrade)
    grading_model = ai_model

    print(f"  🔄 Multi-pass: Grading {len(responses)} questions with {grading_model}...")

    # Submit all questions in parallel, track by index
    question_results = [None] * len(responses)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_idx = {}
        for i, resp in enumerate(responses):
            question = resp.get("question", f"Question {i+1}")
            answer = resp.get("answer", "")
            resp_type = resp.get("type", "marker_response")
            meta = question_meta[i] if i < len(question_meta) else {'points': 10, 'section_name': '', 'section_type': 'written'}

            # Match expected answer by multiple strategies:
            # 1. Question number from text (e.g., "1) What was..." → Q1 → index 0)
            # 2. Term/question text match (for vocab: "Seminole Wars" → key match)
            # 3. Section name match
            # 4. Response list index (only works if no vocab terms shift indices)
            expected = ""

            # Strategy 1: Extract question number and match to Q-index
            q_num_match = re.match(r'^(\d+)', question.strip())
            if q_num_match:
                q_idx = int(q_num_match.group(1)) - 1  # "1)" → index 0
                expected = expected_answers.get(q_idx, "") or expected_answers.get(f"Q{q_num_match.group(1)}", "")

            # Strategy 2: Match by term/question text or section name
            if not expected:
                expected = (expected_answers.get(question, "") or
                            expected_answers.get(question.split(':')[0].strip(), "") or
                            expected_answers.get(meta['section_name'], ""))

            # Strategy 3: Fall back to list index
            if not expected:
                expected = expected_answers.get(i, "")

            # SymPy pre-check: if math subject with expected answer, try exact match first
            if _is_math_subject(subject) and expected and answer:
                try:
                    from backend.services.stem_grading import check_math_equivalence
                    equiv = check_math_equivalence(answer, expected)
                    if equiv.get('equivalent'):
                        pts = meta['points']
                        question_results[i] = {
                            "grade": {"score": pts, "possible": pts,
                                      "reasoning": f"Mathematically equivalent ({equiv['method']})",
                                      "is_correct": True, "quality": "excellent"},
                            "excellent": True, "improvement_note": ""
                        }
                        continue  # Skip LLM call — instant correct, zero cost
                except Exception:
                    pass  # SymPy failed — fall through to normal AI grading

            f = executor.submit(
                grade_per_question,
                question=question,
                student_answer=answer,
                expected_answer=expected,
                points=meta['points'],
                grade_level=grade_level,
                subject=subject,
                teacher_instructions=effective_instructions,  # FULL — includes rubric
                grading_style=grading_style,
                ai_model=grading_model,
                ai_provider=provider,
                response_type=resp_type,
                section_name=meta['section_name'],
                section_type=meta['section_type'],
                token_tracker=tracker
            )
            future_to_idx[f] = i

        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                question_results[idx] = future.result()
            except Exception as e:
                print(f"    ⚠️ Question {idx+1} grading failed: {e}")
                meta = question_meta[idx] if idx < len(question_meta) else {'points': 10}
                question_results[idx] = {
                    "grade": {"score": int(meta['points'] * 0.7), "possible": meta['points'],
                              "reasoning": "Error during grading", "is_correct": True, "quality": "adequate"},
                    "excellent": False, "improvement_note": ""
                }

    # === TEACHER LENIENCY POST-PROCESSING ===
    # If the teacher requested leniency for specific section types, apply score floors in code.
    # This is more reliable than prompt engineering — the AI scores normally, then we adjust.
    _ei_lower = (effective_instructions or '').lower()
    _has_vocab_leniency = any(phrase in _ei_lower for phrase in [
        'lenient', 'accept general', 'accept basic', 'go easy', 'be generous',
        'not strict', 'relaxed', 'don\'t be harsh', 'accept simple'
    ]) and any(w in _ei_lower for w in ['vocab', 'definition', 'terms'])

    if _has_vocab_leniency:
        adjusted_count = 0
        for i, resp in enumerate(responses):
            if resp.get("type") == "vocab_term" and resp.get("answer", "").strip():
                qr = question_results[i]
                if qr:
                    grade = qr.get("grade", {})
                    pts = grade.get("possible", 9)
                    current_score = grade.get("score", 0)
                    min_score = int(pts * 0.65)  # At least 65% for any non-blank vocab answer
                    if current_score < min_score:
                        grade["score"] = min_score
                        grade["quality"] = "adequate"
                        # REPLACE reasoning entirely — the old reasoning says "too basic"
                        # and the feedback generator echoes it. Clean reasoning = clean feedback.
                        term = resp.get("question", "this term")
                        grade["reasoning"] = f"Student provided a basic definition for {term} that shows general understanding. Teacher accepts general/dictionary-level definitions for vocabulary on this assignment."
                        adjusted_count += 1
        if adjusted_count > 0:
            print(f"  📌 Vocab leniency: adjusted {adjusted_count} vocab scores to minimum 65%")

    # === AGGREGATE SCORES ===
    total_earned = sum(qr.get("grade", {}).get("score", 0) for qr in question_results if qr)
    total_possible = sum(qr.get("grade", {}).get("possible", 10) for qr in question_results if qr)

    blank_count = len(extraction_result.get("blank_questions", [])) + len(extraction_result.get("missing_sections", []))
    if blank_count == 0:
        effort_earned = effort_points
    elif blank_count == 1:
        effort_earned = int(effort_points * 0.7)
    elif blank_count == 2:
        effort_earned = int(effort_points * 0.4)
    else:
        effort_earned = 0  # 3+ blanks = no effort credit

    raw_score = int(round((total_earned / max(total_possible, 1)) * (100 - effort_points) + effort_earned))
    raw_score = max(0, min(100, raw_score))

    # Completeness caps by grading style — each missing section drops max possible grade
    if grading_style == 'strict':
        caps = {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35, 7: 25, 8: 15}
    elif grading_style == 'lenient':
        caps = {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49, 7: 39, 8: 29}
    else:
        caps = {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39, 7: 29, 8: 19}
    if blank_count >= len(caps):
        cap = 0  # More blanks than cap table entries → zero
    else:
        cap = caps.get(blank_count, 0)
    final_score = min(raw_score, cap)
    if blank_count > 0:
        print(f"  📉 Completeness: {blank_count} blank/missing → cap at {cap}")

    if final_score >= 90: letter_grade = "A"
    elif final_score >= 80: letter_grade = "B"
    elif final_score >= 70: letter_grade = "C"
    elif final_score >= 60: letter_grade = "D"
    else: letter_grade = "F"

    per_q_scores = [qr.get("grade", {}).get("score", 0) for qr in question_results if qr]
    print(f"  📊 Per-question: {per_q_scores}")
    print(f"  📊 Raw: {raw_score}, Cap: {cap}, Final: {final_score} ({letter_grade})")

    # === PASS 3: FEEDBACK GENERATION ===
    ell_language = None
    if student_id and student_id != "UNKNOWN":
        ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
        if os.path.exists(ell_file):
            try:
                with open(ell_file, 'r', encoding='utf-8') as f:
                    ell_data = json.load(f)
                ell_entry = ell_data.get(student_id, {})
                lang = ell_entry.get("language")
                if lang and lang != "none":
                    ell_language = lang
            except Exception:
                pass

    # === BUILD BREAKDOWN (before feedback so we can pass rubric scores) ===
    content_pts = int(round((total_earned / max(total_possible, 1)) * 40))
    completeness_pts = max(0, 25 - (blank_count * 6))
    qualities = [qr.get("grade", {}).get("quality", "adequate") for qr in question_results if qr]
    if qualities.count("excellent") + qualities.count("good") > len(qualities) * 0.7:
        writing_pts = 18
    elif qualities.count("developing") + qualities.count("insufficient") > len(qualities) * 0.5:
        writing_pts = 10
    else:
        writing_pts = 15

    rubric_breakdown = {
        "content_accuracy": {"score": content_pts, "possible": 40},
        "completeness": {"score": completeness_pts, "possible": 25},
        "writing_quality": {"score": writing_pts, "possible": 20},
        "effort_engagement": {"score": effort_earned, "possible": effort_points},
    }

    # === APPLY CUSTOM RUBRIC WEIGHTS ===
    # rubric_weights is a list of 4 weights [content, completeness, writing, effort]
    if rubric_weights and len(rubric_weights) == 4:
        cat_pcts = [
            content_pts / 40,                          # content_accuracy normalized
            completeness_pts / 25,                     # completeness normalized
            writing_pts / 20,                          # writing_quality normalized
            effort_earned / max(effort_points, 1),     # effort_engagement normalized
        ]
        total_weight = sum(rubric_weights) or 100
        weighted_score = sum(
            pct * (w / total_weight)
            for pct, w in zip(cat_pcts, rubric_weights)
        )
        final_score = int(round(weighted_score * 100))
        final_score = max(0, min(100, final_score))
        # Still apply completeness cap if there are blanks
        if blank_count > 0:
            final_score = min(final_score, cap)
        # Recalculate letter grade
        if final_score >= 90: letter_grade = "A"
        elif final_score >= 80: letter_grade = "B"
        elif final_score >= 70: letter_grade = "C"
        elif final_score >= 60: letter_grade = "D"
        else: letter_grade = "F"
        print(f"  📊 Rubric-weighted score: {final_score} ({letter_grade}) [weights: {rubric_weights}]")

    # Collect blank/missing info for feedback
    blank_questions = extraction_result.get("blank_questions", [])
    missing_sections = extraction_result.get("missing_sections", [])

    # Use gpt-4o for feedback — it's 1 call per student and the most important output
    feedback_model = ai_model
    if provider == "openai":
        feedback_model = "gpt-4o"  # Feedback is what teachers/parents read — needs quality
    # Claude/Gemini: use the teacher's selected model

    print(f"  🔄 Multi-pass: Generating feedback ({feedback_model})...")
    feedback_result = generate_feedback(
        question_results=question_results,
        total_score=final_score, total_possible=100,
        letter_grade=letter_grade,
        grade_level=grade_level, subject=subject,
        teacher_instructions=effective_instructions,
        ell_language=ell_language,
        ai_model=feedback_model,
        ai_provider=provider,
        student_responses=responses,
        rubric_breakdown=rubric_breakdown,
        blank_questions=blank_questions,
        missing_sections=missing_sections,
        token_tracker=tracker,
        student_history=student_history,
        grading_style=grading_style
    )

    # === BUILD RESULT ===
    student_response_texts = [resp.get("answer", "")[:500] for resp in responses if resp.get("answer")]

    result = {
        "score": final_score,
        "letter_grade": letter_grade,
        "breakdown": {
            "content_accuracy": min(content_pts, 40),
            "completeness": min(completeness_pts, 25),
            "writing_quality": min(writing_pts, 20),
            "effort_engagement": effort_earned
        },
        "student_responses": student_response_texts,
        "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
        "excellent_answers": feedback_result.get("excellent_answers", []),
        "needs_improvement": feedback_result.get("needs_improvement", []),
        "skills_demonstrated": feedback_result.get("skills_demonstrated", {"strengths": [], "developing": []}),
        "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
        "plagiarism_detection": {"flag": "none", "reason": ""},
        "feedback": feedback_result.get("feedback", ""),
        "multipass_grading": True,
        "per_question_scores": [
            {"question": responses[i].get("question", "")[:60],
             "score": qr.get("grade", {}).get("score", 0),
             "possible": qr.get("grade", {}).get("possible", 10),
             "quality": qr.get("grade", {}).get("quality", "")}
            for i, qr in enumerate(question_results) if qr
        ],
        "token_usage": tracker.summary()
    }

    # Add audit trail for AI Reasoning / Raw API Output
    audit_input_parts = []
    for i, resp in enumerate(responses):
        q = resp.get("question", f"Q{i+1}")
        a = resp.get("answer", "")
        audit_input_parts.append(f"[{q}]\n{a}")
    audit_response_parts = []
    for i, qr in enumerate(question_results):
        if qr:
            g = qr.get("grade", {})
            audit_response_parts.append(
                f"Q{i+1}: {g.get('score', 0)}/{g.get('possible', 10)} "
                f"({g.get('quality', 'N/A')}) - {g.get('reasoning', '')}"
            )
    result["_audit"] = {
        "ai_input": "\n\n".join(audit_input_parts),
        "ai_response": "\n".join(audit_response_parts) + "\n\n--- FEEDBACK ---\n" + feedback_result.get("feedback", "")
    }

    # Update writing profile
    if student_id and student_id != "UNKNOWN" and content:
        current_writing_style = analyze_writing_style(content)
        if current_writing_style:
            ai_flag = result.get("ai_detection", {}).get("flag", "none")
            if ai_flag not in ["likely", "possible"]:
                try:
                    update_writing_profile(student_id, current_writing_style, student_name)
                except Exception:
                    pass

    print(f"  ✅ Multi-pass grading complete: {final_score} ({letter_grade})")
    return result


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


def save_emails_to_folder(grades: list, output_folder: str, teacher_name: str = '', subject: str = '', school_name: str = ''):
    """
    Save emails as individual text files - ONE EMAIL PER STUDENT
    with feedback for ALL their assignments combined.
    """
    email_folder = Path(output_folder) / "emails"
    email_folder.mkdir(parents=True, exist_ok=True)
    
    # Group grades by student
    students = {}
    for grade in grades:
        student_name = grade.get('student_name', 'Unknown')
        if student_name not in students:
            # Get only first name (no middle initial)
            full_first = grade.get('first_name', student_name.split()[0])
            first_only = full_first.split()[0] if full_first else student_name.split()[0]
            students[student_name] = {
                'email': grade.get('email', ''),
                'first_name': first_only,
                'assignments': []
            }
        students[student_name]['assignments'].append(grade)
    
    email_count = 0
    for student_name, data in students.items():
        if not data['email']:
            continue
        
        # Build combined email
        assignments = data['assignments']
        first_name = data['first_name']
        
        # Email subject line
        if len(assignments) == 1:
            email_subject = f"Grade for {assignments[0].get('assignment', 'Assignment')}: {assignments[0]['letter_grade']}"
        else:
            email_subject = f"Grades for {len(assignments)} Assignments"
        
        # Body
        body = f"Hi {first_name},\n\n"
        
        if len(assignments) == 1:
            a = assignments[0]
            body += f"Here is your grade and feedback for {a.get('assignment', 'your assignment')}:\n\n"
            body += f"GRADE: {a['score']}/100 ({a['letter_grade']})\n\n"
            body += f"FEEDBACK:\n{a.get('feedback', 'No feedback available.')}\n"
        else:
            body += "Here are your grades and feedback:\n\n"
            for a in assignments:
                assignment_name = a.get('assignment', 'Assignment')
                body += f"{'='*50}\n"
                body += f"📝 {assignment_name}\n"
                body += f"{'='*50}\n"
                body += f"GRADE: {a['score']}/100 ({a['letter_grade']})\n\n"
                body += f"FEEDBACK:\n{a.get('feedback', 'No feedback available.')}\n\n"
        
        body += "\nIf you have any questions about your grades, please see me during class.\n\n"
        signature = teacher_name if teacher_name else "Your Teacher"
        if subject:
            signature += f" {subject}"
        body += f"- {signature}\n"
        
        # Save file
        safe_name = re.sub(r'[^\w\s-]', '', student_name).replace(' ', '_')
        filepath = email_folder / f"{safe_name}_email.txt"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"TO: {data['email']}\n")
            f.write(f"SUBJECT: {email_subject}\n")
            f.write(f"{'='*50}\n\n")
            f.write(body)
        
        email_count += 1
    
    print(f"📧 Saved {email_count} email files to: {email_folder}")


def create_outlook_drafts(grades: list):
    """
    Create draft emails in Outlook desktop app (Windows only).
    This lets you review each email before sending.
    """
    try:
        import win32com.client
    except ImportError:
        print("⚠️  pywin32 not installed. Run: pip install pywin32")
        print("   Falling back to saving emails as files.")
        return False
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        count = 0
        
        for grade in grades:
            if not grade.get('email'):
                continue
                
            subject, body = generate_email_content(grade, grade, ASSIGNMENT_NAME)
            
            mail = outlook.CreateItem(0)  # 0 = mail item
            mail.To = grade['email']
            mail.Subject = subject
            mail.Body = body
            mail.Save()  # Save as draft
            count += 1
        
        print(f"📧 Created {count} draft emails in Outlook")
        return True
        
    except Exception as e:
        print(f"⚠️  Outlook error: {e}")
        return False


# =============================================================================
# CSV EXPORT FOR FOCUS
# =============================================================================

from backend.services.grader_export import export_focus_csv as export_focus_csv  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


from backend.services.grader_export import save_to_master_csv as save_to_master_csv  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


from backend.services.grader_export import export_detailed_report as export_detailed_report  # noqa: F401 explicit re-export (grading/pipeline.py imports this — mypy no_implicit_reexport)


# =============================================================================
# MAIN GRADING WORKFLOW
# =============================================================================

def run_grading(
    assignment_folder: str = ASSIGNMENT_FOLDER,
    output_folder: str = OUTPUT_FOLDER,
    roster_file: str = ROSTER_FILE,
    assignment_name: str = ASSIGNMENT_NAME,
    create_outlook_emails: bool = False  # Set True if you have Outlook on Windows
):
    """
    Main function - runs the complete grading workflow.
    
    1. Loads student roster
    2. Reads each .docx file from assignment folder
    3. Grades each assignment with AI
    4. Generates emails (saves to files or creates Outlook drafts)
    5. Creates Focus CSV for grade import
    6. Creates detailed report for your records
    """
    print("=" * 60)
    print("📚 ASSIGNMENT GRADER - 6th Grade Social Studies")
    print("=" * 60)
    print(f"📁 Assignment folder: {assignment_folder}")
    print(f"💾 Output folder: {output_folder}")
    print(f"📝 Assignment: {assignment_name}")
    print()
    
    # Load roster
    roster = load_roster(roster_file)
    
    # Get all .docx files
    assignment_path = Path(assignment_folder)
    if not assignment_path.exists():
        print(f"❌ Assignment folder not found: {assignment_folder}")
        return []
    
    # Find all supported files (docx, txt, and images)
    supported_extensions = ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
    all_files = []
    for ext in supported_extensions:
        all_files.extend(assignment_path.glob(ext))
    
    print(f"📄 Found {len(all_files)} files ({', '.join(supported_extensions)})")
    print()
    
    # Process each file
    all_grades = []
    
    for i, filepath in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] {filepath.name}")
        
        # Parse filename to get student name
        parsed = parse_filename(filepath.name)
        student_name = f"{parsed['first_name']} {parsed['last_name']}"
        lookup_key = parsed['lookup_key']
        
        # Look up student in roster
        if lookup_key in roster:
            student_info = roster[lookup_key].copy()
            print(f"  👤 {student_info['student_name']} (ID: {student_info['student_id']})")
        else:
            # Not found in roster - use parsed name
            student_info = {
                "student_id": "UNKNOWN",
                "student_name": student_name,
                "first_name": parsed['first_name'],
                "last_name": parsed['last_name'],
                "email": ""
            }
            print(f"  👤 {student_name} (⚠️ NOT IN ROSTER)")
        
        # Read file content
        file_data = read_assignment_file(filepath)
        if not file_data:
            print(f"  ❌ Could not read file")
            continue
        
        # Handle based on file type
        markers_found = []
        
        if file_data["type"] == "text":
            # Text-based file - check for markers
            content = file_data["content"]
            
            if len(content.strip()) < 20:
                print(f"  ⚠️  File appears empty ({len(content)} chars)")
                continue
            
            # Extract only the student work portion
            student_work, markers_found = extract_student_work(content)
            
            if markers_found:
                print(f"  📝 Found marker(s): {', '.join(markers_found[:2])}{'...' if len(markers_found) > 2 else ''}")
            else:
                print(f"  ⚠️  NO MARKERS FOUND - Check if student uploaded wrong document!")
                print(f"      → Review manually: {filepath.name}")
            
            if len(student_work.strip()) < 10:
                print(f"  ⚠️  No student work found after marker")
                continue
            
            # Prepare data for grading
            grade_data = {"type": "text", "content": student_work}
        
        elif file_data["type"] == "image":
            # Image file - send entire image to AI for grading
            print(f"  🖼️  Image file - sending to AI for visual grading")
            grade_data = file_data
            markers_found = ["image"]  # Mark as having content
        
        else:
            print(f"  ❌ Unknown file type")
            continue
        
        # Grade with AI
        grade_result = grade_assignment(student_info['student_name'], grade_data)
        
        # Combine all info
        # Extract assignment name from filename
        parts = Path(filepath.name).stem.split('_')
        if len(parts) >= 3:
            assignment_from_file = ' '.join(parts[2:])
        else:
            assignment_from_file = ASSIGNMENT_NAME
        
        grade_record = {
            **student_info,
            **grade_result,
            "filename": filepath.name,
            "assignment": assignment_from_file,
            "has_markers": len(markers_found) > 0
        }
        all_grades.append(grade_record)
        
        print(f"  ✅ Score: {grade_result['score']} ({grade_result['letter_grade']})")
        print()
    
    # Export results
    print("=" * 60)
    print("📊 EXPORTING RESULTS")
    print("=" * 60)
    
    # Focus CSVs (separated by assignment)
    focus_files = export_focus_csv(all_grades, output_folder, assignment_name)
    
    # Detailed report (one file with all grades)
    export_detailed_report(all_grades, output_folder, assignment_name)
    
    # Emails
    if create_outlook_emails:
        if not create_outlook_drafts(all_grades):
            save_emails_to_folder(all_grades, output_folder)
    else:
        save_emails_to_folder(all_grades, output_folder)
    
    # Summary
    print()
    print("=" * 60)
    print("📈 GRADING SUMMARY")
    print("=" * 60)
    
    if all_grades:
        scores = [g['score'] for g in all_grades if g['score'] > 0]
        if scores:
            print(f"Total graded: {len(all_grades)}")
            print(f"Average score: {sum(scores)/len(scores):.1f}")
            print(f"Highest: {max(scores)}")
            print(f"Lowest: {min(scores)}")
            
            # Grade distribution
            grade_dist = {}
            for g in all_grades:
                letter = g['letter_grade']
                grade_dist[letter] = grade_dist.get(letter, 0) + 1
            print(f"Distribution: {dict(sorted(grade_dist.items()))}")
            
            # Per-assignment breakdown
            print(f"\n📚 By Assignment:")
            assignments = {}
            for g in all_grades:
                a = g.get('assignment', 'Unknown')
                if a not in assignments:
                    assignments[a] = []
                assignments[a].append(g['score'])
            
            for assignment, scores_list in sorted(assignments.items()):
                valid_scores = [s for s in scores_list if s > 0]
                if valid_scores:
                    avg = sum(valid_scores) / len(valid_scores)
                    print(f"   • {assignment[:40]}: {len(scores_list)} students, avg {avg:.1f}")
        
        # List students not in roster
        unknown = [g for g in all_grades if g['student_id'] == 'UNKNOWN']
        if unknown:
            print(f"\n⚠️  {len(unknown)} students NOT FOUND in roster:")
            for g in unknown:
                print(f"   - {g['student_name']} ({g['filename']})")
        
        # List documents with no markers (possible wrong uploads)
        no_markers = [g for g in all_grades if not g.get('has_markers', True)]
        if no_markers:
            print(f"\n🚨 {len(no_markers)} documents had NO MARKERS - review for possible wrong uploads:")
            for g in no_markers:
                print(f"   - {g['student_name']}: {g['filename']}")
    
    print()
    print("✅ GRADING COMPLETE!")
    return all_grades


# =============================================================================
# RUN THE SCRIPT
# =============================================================================

if __name__ == "__main__":
    # Update the paths at the top of this file, then run!
    results = run_grading(
        create_outlook_emails=False  # Set True if you have Outlook desktop on Windows
    )
