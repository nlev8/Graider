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

from backend.services.writing_style import analyze_writing_style, compare_writing_styles


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
from backend.api_keys import get_api_key as _get_api_key
from backend.retry import with_retry

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

GRADING_RUBRIC = """
You are grading 6th grade Social Studies assignments. Be ENCOURAGING and GENEROUS.
These are 11-12 year old students - grade with appropriate expectations for their age.

IMPORTANT GRADING GUIDELINES:
- For FILL-IN-THE-BLANK exercises: Accept any answer that is factually correct or very close. Spelling mistakes should NOT reduce the grade if the intent is clear.
- Accept reasonable synonyms, alternate phrasings, and partial answers that demonstrate understanding.
- If a student gets the main idea right but uses slightly different wording, give FULL CREDIT.
- Minor spelling errors (like "piler" instead of "pillar") should NOT be penalized.
- Be GENEROUS - when in doubt, give the student the benefit of the doubt.

GRADING SCALE (out of 100 points):

1. CONTENT ACCURACY (40 points)
   - Are the answers factually correct or demonstrate understanding?
   - For fill-in-the-blank: Is the completed statement essentially true?
   - 40 pts: Most answers correct (90%+)
   - 35 pts: Good understanding (80-89% correct)
   - 30 pts: Solid effort (70-79% correct)
   - 25 pts: Some understanding (60-69% correct)
   - 20 pts: Partial understanding (50-59% correct)
   - Below 20: Less than half correct

2. COMPLETENESS (25 points)
   - Did the student attempt ALL questions/blanks?
   - 25 pts: All questions attempted
   - 20 pts: Nearly all attempted (90%+)
   - 15 pts: Most attempted (75%+)
   - 10 pts: About half attempted
   - 5 pts: Less than half attempted

3. WRITING QUALITY (20 points)
   - Is the writing legible and understandable?
   - For fill-in-blank, this is less important - be generous
   - 20 pts: Clear and readable
   - 15 pts: Minor issues but understandable
   - 10 pts: Some difficulty but can figure out meaning
   - 5 pts: Hard to understand

4. EFFORT & ENGAGEMENT (15 points)
   - Did the student put in genuine effort?
   - Are answers thoughtful (not random guesses)?
   - 15 pts: Clear effort shown
   - 10 pts: Good effort
   - 5 pts: Minimal effort
   - 0 pts: No real effort

GRADE RANGES:
- A: 90-100 (Great job!)
- B: 80-89 (Good work!)
- C: 70-79 (Solid effort)
- D: 60-69 (Needs improvement)
- F: Below 60 (Significant concerns)

REMEMBER: These are 6th graders. Be kind, encouraging, and generous with grading.
A student who attempts all questions and gets most right should get an A or B.
"""

# DEFAULT ASSIGNMENT INSTRUCTIONS - Only used if no assignment-specific config provided
# This should be empty or generic - assignment-specific instructions come from Builder configs
ASSIGNMENT_INSTRUCTIONS = """
Grade the student's work based on what they were asked to do.
Focus on the content they provided, not on sections that may not apply to this assignment type.
"""


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


from backend.services.grader_text_prep import preprocess_for_ai_detection, sanitize_pii_for_ai


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


from backend.services.grading_prep import build_section_rubric, _distribute_points, _is_math_subject, _parse_expected_answers
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

from backend.services.grader_json import _try_parse_json_fallback


# =============================================================================
# AI GRADING WITH CLAUDE
# =============================================================================

def grade_assignment(student_name: str, assignment_data: dict, custom_ai_instructions: str = '', grade_level: str = '6', subject: str = 'Social Studies', ai_model: str = 'gpt-4o-mini', student_id: str = None, assignment_template: str = None, rubric_prompt: str = None, custom_markers: list = None, exclude_markers: list = None, marker_config: list = None, effort_points: int = 15, extraction_mode: str = 'structured', grading_style: str = 'standard', token_tracker: 'TokenTracker' = None, rubric_weights: list = None) -> dict:
    """
    Use OpenAI GPT to grade a student assignment.

    FERPA COMPLIANCE: Student name is NOT sent to OpenAI.
    We use "Student" as a placeholder to protect privacy.

    Supports both text and image inputs.

    Parameters:
    - student_name: Name of the student (kept local, not sent to API)
    - assignment_data: dict with "type" ("text" or "image") and "content"
    - custom_ai_instructions: Additional grading instructions from the teacher
    - grade_level: The student's grade level (e.g., '6', '7', '8')
    - subject: The subject being graded (e.g., 'Social Studies', 'English/ELA')
    - ai_model: OpenAI model to use ('gpt-4o' or 'gpt-4o-mini')
    - assignment_template: The original assignment template with all questions (for context)

    Returns dict with:
    - score: numeric grade (0-100)
    - letter_grade: A, B, C, D, or F
    - feedback: detailed feedback for the student
    - breakdown: points for each rubric category
    - authenticity_flag: 'clean', 'review', or 'flagged'
    - authenticity_reason: Explanation for flagged or review status
    """
    # Determine which API to use based on model name
    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "openai"

    # Initialize the appropriate client
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            print("❌ anthropic not installed. Run: pip install anthropic")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Anthropic API not available - pip install anthropic"}

        if not _get_api_key('anthropic'):
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Anthropic API key not configured"}

        claude_client = anthropic.Anthropic(api_key=_get_api_key('anthropic'))
        claude_model_map = {
            "claude-haiku": "claude-3-5-haiku-latest",
            "claude-sonnet": "claude-sonnet-4-20250514",
            "claude-opus": "claude-opus-4-20250514",
        }
        actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")
        print(f"  🤖 Using Claude model: {actual_model}")

    elif provider == "gemini":
        try:
            import google.generativeai as genai
        except ImportError:
            print("❌ google-generativeai not installed. Run: pip install google-generativeai")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Google AI not available - pip install google-generativeai"}

        if not _get_api_key('gemini'):
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Gemini API key not configured"}

        genai.configure(api_key=_get_api_key('gemini'))
        gemini_model_map = {
            "gemini-flash": "gemini-2.0-flash",
            "gemini-pro": "gemini-2.0-pro-exp",
        }
        actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
        gemini_client = genai.GenerativeModel(actual_model)
        print(f"  🤖 Using Gemini model: {actual_model}")

    else:  # OpenAI
        try:
            from openai import OpenAI
        except ImportError:
            print("❌ openai not installed. Run: pip install openai")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "OpenAI API not available"}

        openai_client = OpenAI(api_key=_get_api_key('openai'))

    content = assignment_data.get("content", "")

    # Strip embedded answer key from generated worksheets (handles -- and --- variants)
    if content and "GRAIDER_ANSWER_KEY_START" in content:
        content = content.split("GRAIDER_ANSWER_KEY_START")[0].rstrip().rstrip('-')
        assignment_data = {**assignment_data, "content": content}
        print(f"  🧹 Stripped embedded answer key from document")

    # Check for empty/blank student submissions before sending to API
    if assignment_data.get("type") == "text" and content:
        import re

        # Method 1: Check for filled-in blanks (text between underscores like ___answer___)
        filled_blanks = re.findall(r'_{2,}([^_\n]+)_{2,}', content)
        filled_blanks = [b.strip() for b in filled_blanks if b.strip() and len(b.strip()) > 1]

        # Method 2: Check for content after colons that isn't just blanks
        # e.g., "Nationalism: the belief that..." vs "Nationalism: ___"
        after_colons = re.findall(r':\s*([^_\n:]{10,})', content)
        # Filter out template instruction text that isn't student writing
        _instruction_patterns = re.compile(
            r'^(define|summarize|explain|describe|write|use|answer|identify|list|compare|analyze|discuss|'
            r'read|complete|fill|circle|match|select|choose|highlight|underline|review|include)\b',
            re.IGNORECASE
        )
        after_colons = [
            a.strip() for a in after_colons
            if a.strip()
            and not a.strip().startswith('_')
            and not _instruction_patterns.match(a.strip())
            and not a.strip().endswith('?')
            and 'complete sentences' not in a.lower()
            and 'using evidence' not in a.lower()
            and 'in your own words' not in a.lower()
            and 'from the reading' not in a.lower()
            and 'pp ' not in a.strip()[:5]  # page references like "pp 348-349"
        ]

        # Method 3: Look for paragraph-length responses (likely written answers)
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        # Filter out paragraphs that are mostly underscores
        real_paragraphs = [p for p in paragraphs if p.count('_') < len(p) * 0.3]

        # Method 4: Count lines that are JUST underscores (blank response lines)
        blank_lines = len(re.findall(r'^[\s_]+$', content, re.MULTILINE))
        total_lines = len([l for l in content.split('\n') if l.strip()])
        blank_ratio = blank_lines / max(total_lines, 1)

        # Method 5: Check for questions followed by no response
        # Look for question patterns and check if there's content after them
        lines = content.split('\n')
        unanswered_questions = []
        question_indices = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Check if line is a question (ends with ? or starts with number/bullet or is a vocab term with colon)
            is_question = (
                line_stripped.endswith('?') or
                re.match(r'^[•\*\-\u2022\u2023\u25E6\u2043\u2219\s]*\d+[\.\)]\s*\w', line_stripped) or  # "• 1. Question" or "1) Question"
                re.match(r'^[•\*\-\u2022\u2023\u25E6\u2043\u2219\s]*[a-zA-Z][\.\)]\s*\w', line_stripped) or  # "• a. Question" or "a) Question"
                (line_stripped.endswith(':') and len(line_stripped) > 5 and '_' not in line_stripped)  # "Nationalism:"
            )
            if is_question and len(line_stripped) > 5:
                question_indices.append(i)

        # Check content between consecutive questions
        for idx, q_idx in enumerate(question_indices):
            line_stripped = lines[q_idx].strip()
            # Determine where the next question starts (or end of document)
            next_q_idx = question_indices[idx + 1] if idx + 1 < len(question_indices) else len(lines)

            # Get content between this question and the next
            content_between = []
            for j in range(q_idx + 1, min(next_q_idx, q_idx + 6)):  # Check up to 5 lines after
                if j < len(lines):
                    between_line = lines[j].strip()
                    # Skip empty lines and lines that are just underscores
                    if between_line and not re.match(r'^[_\s\-\.]+$', between_line):
                        # Check if this line has actual content (not just template markers)
                        if len(between_line) > 3 and between_line.count('_') < len(between_line) * 0.5:
                            content_between.append(between_line)

            # If no substantive content found after this question, mark as unanswered
            if not content_between:
                unanswered_questions.append(line_stripped[:60] + "..." if len(line_stripped) > 60 else line_stripped)

        # Determine if submission is blank
        has_filled_blanks = len(filled_blanks) >= 2
        has_written_responses = len(after_colons) >= 2 or len(real_paragraphs) >= 1
        mostly_blank_lines = blank_ratio > 0.4
        many_unanswered = len(unanswered_questions) >= 3

        is_blank = (not has_filled_blanks and not has_written_responses and mostly_blank_lines) or \
                   (many_unanswered and not has_filled_blanks and not has_written_responses)

        if is_blank:
            print(f"  ⚠️  BLANK/EMPTY SUBMISSION DETECTED")
            print(f"      Filled blanks: {len(filled_blanks)}, Written responses: {len(after_colons)}")
            print(f"      Blank line ratio: {blank_ratio:.1%}, Unanswered questions: {len(unanswered_questions)}")
            return {
                "score": 0,
                "letter_grade": "INCOMPLETE",
                "breakdown": {
                    "content_accuracy": 0,
                    "completeness": 0,
                    "critical_thinking": 0,
                    "communication": 0
                },
                "feedback": "You submitted a blank assignment with no responses. Please complete all sections and resubmit.",
                "student_responses": [],
                "unanswered_questions": unanswered_questions[:10],
                "ai_detection": {"flag": "none", "confidence": 0, "reason": "Blank submission — no content to evaluate."},
                "plagiarism_detection": {"flag": "none", "reason": "Blank submission — no content to evaluate."},
                "authenticity_flag": "clean",
                "authenticity_reason": "",
                "skills_demonstrated": {}
            }

    # FERPA: Use anonymous placeholder instead of real student name
    anonymous_name = "Student"
    
    # Build custom instructions section if provided
    custom_section = ''
    if custom_ai_instructions:
        custom_section = f"""
---
TEACHER'S GRADING INSTRUCTIONS (FOLLOW THESE CAREFULLY):
{custom_ai_instructions}
---
"""

    # Build student history context for personalized feedback
    history_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            history_context = build_history_context(student_id)
        except Exception as e:
            print(f"  Note: Could not load student history: {e}")

    # Build accommodation context for IEP/504 students (FERPA compliant)
    # NOTE: Only accommodation TYPE is sent to AI - no student identifying info
    accommodation_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            accommodation_context = build_accommodation_prompt(student_id)
            if accommodation_context:
                print(f"  Applying accommodations for student")
        except Exception as e:
            print(f"  Note: Could not load accommodations: {e}")

    # Check if this is a fill-in-the-blank assignment
    is_fitb = False
    content_lower = content.lower() if content else ''
    if 'fill-in' in content_lower or 'fill in the blank' in content_lower or 'fillintheblank' in content_lower.replace(' ', '').replace('-', ''):
        is_fitb = True
    # Also check custom AI instructions for FITB rubric type
    if 'FILL-IN-THE-BLANK' in (custom_ai_instructions or '').upper():
        is_fitb = True
    # Also detect FITB by timestamp pattern (e.g., "1. (0:00)" format common in video worksheets)
    if not is_fitb and content:
        import re as _re
        has_timestamps = bool(_re.search(r'\d+\.\s*\(\d+:\d+', content))
        has_filled_underscores = len(_re.findall(r'_{2,}([^_\n]+)_{2,}', content)) >= 2
        if has_timestamps and has_filled_underscores:
            is_fitb = True
            print(f"  📝 FITB detected via timestamps + filled underscores")

    # PRE-EXTRACT student responses to prevent AI hallucination
    extraction_result = None
    extracted_responses_text = ''
    # If teacher set up custom markers, use marker-based extraction even if FITB was detected.
    # Markers mean the teacher explicitly defined which sections to grade — that takes priority.
    has_real_markers = custom_markers and len(custom_markers) > 0
    if is_fitb and has_real_markers:
        print(f"  📝 FITB detected but custom markers present — using marker extraction instead")
        is_fitb = False
    if assignment_data.get("type") == "text" and content:
        if is_fitb:
            # FITB assignment — send full content for grading (works with or without markers)
            print(f"  📝 FITB assignment - sending full content for grading")
            extracted_responses_text = f"""
==================================================
FILL-IN-THE-BLANK SUBMISSION
==================================================

STUDENT'S COMPLETED DOCUMENT:
{content}

==================================================
Grade based on:
1. ACCURACY: Did the student fill in the blanks correctly?
2. COMPLETENESS: Did the student attempt all blanks?
Do NOT penalize for AI/plagiarism - these are factual answers.
==================================================
"""
            extraction_result = {
                "extracted_responses": [{"question": "Fill-in-the-blank", "answer": content, "type": "fitb_full"}],
                "blank_questions": [],
                "total_questions": 1,
                "answered_questions": 1,
                "extraction_summary": "FITB - full content submitted for grading"
            }
        else:
            # Normal extraction for non-FITB assignments
            # Priority: GRAIDER tag plain-text fallback > custom marker extraction
            if '[GRAIDER:' in content:
                extraction_result = extract_from_graider_text(content, exclude_markers)

            if not extraction_result or not extraction_result.get("extracted_responses"):
                # Debug: Log markers being used
                marker_count = len(custom_markers) if custom_markers else 0
                print(f"  🔍 Extraction using {marker_count} markers")
                if custom_markers and marker_count > 0:
                    for i, m in enumerate(custom_markers[:3]):  # Show first 3
                        marker_text = m.get('start', m) if isinstance(m, dict) else m
                        print(f"      Marker {i+1}: {marker_text[:50]}...")

                extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
            if extraction_result:
                # Filter question/prompt text from extracted answers before grading.
                # If filtering empties a response, move it to blank_questions so
                # completeness caps apply (e.g., primary source quotes that survive extraction).
                filtered_out = []
                for resp in extraction_result.get("extracted_responses", []):
                    answer = resp.get("answer", "")
                    if answer and resp.get("type") != "fitb":
                        cleaned = filter_questions_from_response(answer)
                        if cleaned and len(cleaned.strip()) >= 3:
                            resp["answer"] = cleaned
                        else:
                            # Response was entirely template/prompt text — mark as blank
                            q_label = resp.get("question", "Unknown")
                            print(f"      ⚠️ Response for '{q_label[:50]}' was only template text — marking blank")
                            extraction_result.setdefault("blank_questions", []).append(q_label)
                            filtered_out.append(resp)
                # Remove blanked-out responses from extracted list
                if filtered_out:
                    extraction_result["extracted_responses"] = [
                        r for r in extraction_result["extracted_responses"] if r not in filtered_out
                    ]
                    extraction_result["answered_questions"] = len(extraction_result["extracted_responses"])

                extracted_responses_text = format_extracted_for_grading(extraction_result, marker_config, extraction_mode)
                answered = extraction_result.get("answered_questions", 0)
                total = extraction_result.get("total_questions", 0)
                blank_qs = extraction_result.get("blank_questions", [])
                missing_secs = extraction_result.get("missing_sections", [])
                print(f"  📋 Pre-extracted {answered}/{total} responses, {len(blank_qs)} blank, {len(missing_secs)} missing")
                if blank_qs:
                    print(f"      Blank questions: {blank_qs}")
                if missing_secs:
                    print(f"      Missing sections: {missing_secs}")

                # DEBUG: Show what was extracted
                for i, resp in enumerate(extraction_result.get("extracted_responses", [])):
                    q_label = resp.get("question", "?")[:60]
                    ans_preview = resp.get("answer", "")[:100].replace('\n', ' ')
                    print(f"      [{i+1}] {q_label}...")
                    print(f"          Answer: {ans_preview}...")

                # If no responses found, return early with 0 score
                if answered == 0:
                    print(f"  ⚠️  NO RESPONSES EXTRACTED - Document is blank or markers don't match")
                    return {
                        "score": 0,
                        "letter_grade": "INCOMPLETE",
                        "breakdown": {
                            "content_accuracy": 0,
                            "completeness": 0,
                            "critical_thinking": 0,
                            "communication": 0
                        },
                        "feedback": "You submitted a blank assignment with no responses. Please complete all sections and resubmit.",
                        "student_responses": [],
                        "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
                        "ai_detection": {"flag": "none", "confidence": 0, "reason": "Blank submission — no content to evaluate."},
                        "plagiarism_detection": {"flag": "none", "reason": "Blank submission — no content to evaluate."},
                        "authenticity_flag": "clean",
                        "authenticity_reason": "",
                        "skills_demonstrated": {},
                        "extraction_result": extraction_result
                    }

    # Analyze current submission's writing style for AI detection
    writing_style_context = ''
    current_writing_style = None
    style_comparison = None
    if assignment_data.get("type") == "text" and content:
        current_writing_style = analyze_writing_style(content)
        if current_writing_style:
            # Get student's historical writing profile
            historical_profile = get_writing_profile(student_id) if student_id and student_id != "UNKNOWN" else None

            if historical_profile and historical_profile.get("sample_count", 0) >= 2:
                # Compare current vs historical style
                style_comparison = compare_writing_styles(current_writing_style, historical_profile)

                if style_comparison.get("ai_likelihood") in ["likely", "possible"]:
                    print(f"  ⚠️  Writing style deviation detected: {style_comparison.get('deviation')}")
                    writing_style_context = f"""
---
WRITING STYLE ANALYSIS (COMPARE TO STUDENT'S HISTORY):
This student's historical writing profile (based on {historical_profile.get('sample_count', 0)} previous assignments):
- Average complexity score: {historical_profile.get('avg_complexity_score', 'N/A')}/10
- Average sentence length: {historical_profile.get('avg_sentence_length', 'N/A')} words
- Average word length: {historical_profile.get('avg_word_length', 'N/A')} characters
- Typical academic vocabulary: {historical_profile.get('avg_academic_words', 0):.1f} words per submission

Current submission analysis:
- Complexity score: {current_writing_style.get('complexity_score', 'N/A')}/10
- Sentence length: {current_writing_style.get('avg_sentence_length', 'N/A')} words
- Word length: {current_writing_style.get('avg_word_length', 'N/A')} characters
- Academic vocabulary count: {current_writing_style.get('academic_word_count', 0)}

DEVIATION ALERT: {'; '.join(style_comparison.get('deviations', []))}
This suggests possible AI use - be extra vigilant in your authenticity check!
---
"""

    # Map grade level to age range for context
    grade_age_map = {
        'K': '5-6', '1': '6-7', '2': '7-8', '3': '8-9', '4': '9-10', '5': '10-11',
        '6': '11-12', '7': '12-13', '8': '13-14', '9': '14-15', '10': '15-16',
        '11': '16-17', '12': '17-18'
    }
    age_range = grade_age_map.get(str(grade_level), '11-12')

    # Build extracted responses section for the prompt
    extracted_responses_section = ""
    if extracted_responses_text:
        extracted_responses_section = f"""
---
{extracted_responses_text}
---
"""

    # Build assignment template section (provides question context)
    assignment_template_section = ""
    if assignment_template:
        # Truncate if very long to save tokens
        template_text = assignment_template[:8000] if len(assignment_template) > 8000 else assignment_template
        assignment_template_section = f"""
---
ASSIGNMENT TEMPLATE (The questions/prompts the student was asked to answer):
{template_text}
---
"""

    # Use custom rubric if provided, otherwise use default
    # If marker_config is provided, build a section-based rubric
    section_rubric = ""
    if marker_config:
        section_rubric = build_section_rubric(marker_config, effort_points)

    effective_rubric = rubric_prompt if rubric_prompt else GRADING_RUBRIC

    # Build extraction mode-specific instructions
    if extraction_mode == 'ai':
        extraction_instructions = """
CRITICAL - AI EXTRACTION MODE:
The content above contains RAW section content that includes BOTH prompts/questions AND student responses.
YOUR JOB is to identify what is a prompt/question vs what the student actually wrote.

IDENTIFYING STUDENT RESPONSES:
- Questions end with "?" - anything AFTER the "?" on the same line is the student's answer
- Vocabulary format "Term:" - anything after the ":" is the student's definition
- Prompts like "Write your answer:", "Explain...", etc. are instructions, not student content
- Look for the actual student-written text, which is usually less formal and may have spelling errors
- If a section has only a prompt with no student response, mark it as BLANK/UNANSWERED

For example:
- "1. What year was the Louisiana Purchase? 1803" → Student answer is "1803"
- "Antebellum: the period before the war" → Student answer is "the period before the war"
- "Antebellum:" with nothing after → BLANK, student didn't answer
- "Write your answer:" with nothing after → BLANK

Be thorough in separating prompts from responses. Students often write answers on the same line as questions.
"""
    else:
        extraction_instructions = """
CRITICAL - PRE-EXTRACTED RESPONSES:
The student responses have been PRE-EXTRACTED from the document and listed above.
DO NOT invent or hallucinate any responses that are not in the VERIFIED STUDENT RESPONSES section.
ONLY grade the responses that were explicitly extracted and shown to you.
If a question is listed as "UNANSWERED", it means the student left it blank - do not imagine an answer.
"""

    # Build grading style instructions
    if grading_style == 'lenient':
        grading_style_instructions = """
GRADING APPROACH: LENIENT
- Prioritize EFFORT over perfection. If a student attempted a section, they deserve significant credit.
- Brief answers that show understanding should receive 70-80% credit even if not fully developed.
- Do NOT penalize short answers if they demonstrate the student understood the material.
- A student who attempts ALL sections with genuine effort should receive at minimum a B (80+).
- Writing quality expectations should be relaxed - focus on content understanding, not eloquence.
- One-sentence answers to open-ended questions are acceptable if they show comprehension.
- Reserve grades below C only for students who clearly did not try or left sections truly blank/missing.
"""
    elif grading_style == 'strict':
        grading_style_instructions = """
GRADING APPROACH: STRICT
- Hold students to high standards for their grade level.
- Brief, underdeveloped answers to open-ended questions should be penalized.
- Writing quality matters - expect complete sentences and proper grammar.
- Full credit requires thorough, well-developed responses that demonstrate deep understanding.
- Partial answers receive proportionally reduced credit.
"""
    else:
        grading_style_instructions = """
GRADING APPROACH: STANDARD
- Balance accuracy, completeness, writing quality, and effort evenly per the rubric.
- Brief answers should receive partial credit proportional to their quality.
- Students should be encouraged but held to grade-level expectations.
"""

    # Build authenticity/detection section — per-section FITB awareness
    if is_fitb and not custom_markers:
        # Pure FITB (no markers) — skip all detection
        fitb_authenticity_section = f"""AUTHENTICITY CHECKS - FILL-IN-THE-BLANK EXEMPTION:
This is a fill-in-the-blank assignment. Students are expected to write short factual answers (names, dates, places, vocabulary terms).
These answers will naturally match textbook/source material — that is the CORRECT behavior, NOT plagiarism or AI use.
DO NOT flag any answers for AI use or plagiarism. Set ai_detection to "none" and plagiarism_detection to "none".
Focus ONLY on whether the answers are factually correct and complete.

HARD CAPS FOR INCOMPLETE WORK (MANDATORY - each skipped section = one letter grade drop):
Count the number of skipped/unanswered blanks or sections:
- 0 skipped = eligible for A (up to 100)
- 1 skipped = MAXIMUM 89 (B) - NO EXCEPTIONS
- 2 skipped = MAXIMUM 79 (C) - NO EXCEPTIONS
- 3 skipped = MAXIMUM 69 (D) - NO EXCEPTIONS
- 4+ skipped = MAXIMUM 59 (F)
- 5+ skipped = MAXIMUM 49 (F)
- 6+ skipped = MAXIMUM 39 (F)

NEARLY BLANK SUBMISSIONS - Score based on effort shown:
- If student answered only 1-2 blanks out of 5+ = score 10-25 (F)
- If student answered only 3-4 blanks out of 10+ = score 25-40 (F)
- Empty or nearly empty = score in the 0-30 range"""
    else:
        # Full detection — with FITB exemption note for hybrid assignments
        fitb_exemption_note = ""
        if is_fitb:
            fitb_exemption_note = """IMPORTANT - FILL-IN-THE-BLANK EXEMPTION:
This assignment contains fill-in-the-blank sections mixed with written response sections.
Fill-in-the-blank answers (short factual responses like names, dates, places, vocabulary terms) are EXEMPT from AI/plagiarism detection.
These answers are EXPECTED to match textbook/source material — that is correct behavior, NOT cheating.
ONLY apply AI/plagiarism checks to WRITTEN responses (paragraphs, reflections, summaries, explanations).
Do NOT use fill-in-the-blank answers as evidence of AI use or plagiarism.

"""
        fitb_authenticity_section = f"""{fitb_exemption_note}CRITICAL - AUTHENTICITY CHECKS (YOU MUST CHECK THIS CAREFULLY!):

1. AI DETECTION - Compare the student's simple answers to their written paragraphs:
STEP 1: Look at their short answers (fill-in-blanks, one-word responses). Note the vocabulary level.
STEP 2: Look at their paragraph responses. Compare the vocabulary and complexity.
STEP 3: If there's a MISMATCH (simple short answers but sophisticated paragraphs), flag as "likely" AI.

AUTOMATIC "likely" AI FLAGS - if you see ANY of these phrases, it's 100% AI:
- "transformed the nation into a continental power"
- "transforming a limited mission"
- "historic deal that doubled"
- "fueling westward expansion"
- "triggered intense political debates"
- "spurred exploration"
- "fundamentally altered the trajectory"
- "establishing the precedent for"
- "constitutional questions regarding federal authority"
- "resonate through subsequent decades"
- "vital for trade and growth"
- "securing vital trade routes"
- "manifest destiny"
- "territorial expansion"
- "abundant natural resources"
- Any phrase starting with "Transforming...", "Establishing...", "Securing..."
- Any phrase a {age_range} year old would NEVER write

CRITICAL CONTRAST CHECK - THIS IS THE MOST IMPORTANT CHECK:
Look at the student's spelling and grammar in simple answers. If they write:
- Misspellings like "Tomas Jefferson", "the u's", "france" (lowercase)
- Simple phrases like "It doubled in size", "idk"
- Basic vocabulary and short sentences

BUT THEN write sophisticated phrases like:
- "Transforming a limited mission to buy New Orleans into a historic deal"
- Any sentence with words like "vital", "securing", "expanding", "historic deal"

That is 100% AI or copied - flag as "likely" IMMEDIATELY. A student who misspells "Thomas" does NOT write "transforming a limited mission into a historic deal."

Real grade {grade_level} students write: "it made the US bigger", "they needed the river for boats", "so ships could go there"
AI writes: "it transformed the nation into a continental power", "securing vital trade routes"

OBVIOUS COPY-PASTE DEFINITIONS (flag as PLAGIARISM "likely" IMMEDIATELY):
- "exclusive possession or control of the supply of or trade in a commodity or service" = Google definition of monopoly
- "an ideology emphasizing intense loyalty to one's nation" = textbook definition
- "government-provided financial incentives" = too sophisticated
- "implementing three interconnected policies" = not student language
- "authority not explicitly stated in the U.S. Constitution but deemed necessary" = textbook definition of implied powers
- ANY definition that sounds like it was copied from a dictionary or Wikipedia = PLAGIARISM

A real {age_range} year old defines monopoly as: "when one company controls everything" or "only one person sells something"
NOT: "exclusive possession or control of the supply of or trade in a commodity or service"

2. PLAGIARISM DETECTION - Look for:
- SUDDEN SHIFTS in writing quality (simple answers + sophisticated paragraphs = copied/AI)
- Textbook-perfect definitions that don't match the student's other answers
- Phrases that sound memorized or copied verbatim
- Statistics or specific numbers not in the reading (like "828,000 square miles")
- DICTIONARY DEFINITIONS - If a vocabulary definition sounds like it was copied from Google/dictionary (e.g., "exclusive possession or control of the supply of or trade in a commodity or service" for monopoly), flag as PLAGIARISM "likely"
- SOPHISTICATED VOCABULARY MISMATCH - Words like "ideology", "emphasizing", "fostering", "interconnected", "implementing" are NOT how grade {grade_level} students write definitions
- FRAGMENT ANSWERS that are clearly pasted (no complete sentence, just a definition dump)
- If student writes simple answers for some questions but sophisticated definitions for vocabulary = COPY/PASTE from Google

HARD CAPS FOR AI USE / PLAGIARISM (apply FIRST, before other caps):
- AI flag "likely" = MAX score is 50 (F) - this is cheating
- AI flag "possible" = MAX score is 65 (D) - suspicious, needs verification
- Plagiarism flag "likely" = MAX score is 50 (F) - this is cheating
- Plagiarism flag "possible" = MAX score is 65 (D) - suspicious
- If BOTH AI and plagiarism are flagged = MAX score is 40 (F)

In feedback for AI/plagiarism flags:
- Clearly state the work appears to be AI-generated or copied
- Explain that academic integrity is important
- Recommend the student redo the assignment in their own words
- Note this will be reviewed by the teacher

THEN apply HARD CAPS FOR INCOMPLETE WORK (MANDATORY - each skipped section = one letter grade drop):
Count the number of skipped/unanswered written sections (Student Task, Reflection, Explain, etc.):
- 0 skipped = eligible for A (up to 100)
- 1 skipped = MAXIMUM 89 (B) - NO EXCEPTIONS
- 2 skipped = MAXIMUM 79 (C) - NO EXCEPTIONS
- 3 skipped = MAXIMUM 69 (D) - NO EXCEPTIONS
- 4+ skipped = MAXIMUM 59 (F)
- 5+ skipped = MAXIMUM 49 (F)
- 6+ skipped = MAXIMUM 39 (F)

NEARLY BLANK SUBMISSIONS - Score based on effort shown:
- If student answered only 1-2 questions out of 5+ = score 10-25 (F)
- If student answered only 3-4 questions out of 10+ = score 25-40 (F)
- A single poor answer like "idk" or "going again" does NOT earn 50 points
- The score should reflect ACTUAL WORK DONE, not a default minimum
- Empty or nearly empty = score in the 0-30 range

YOU MUST APPLY THESE CAPS. If a student skipped 2 written sections, their score CANNOT be above 79 even if their fill-in-the-blanks were perfect.

The LOWEST cap wins. Example: AI "likely" (cap 50) + 6 sections skipped (cap 39) = final cap is 39."""

    # Load ELL designation for this student (teacher-controlled bilingual feedback)
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

    # Always grade in English only — bilingual translation is handled as a separate post-grading step
    ell_instruction = "Write feedback in English only."

    # Repeat teacher instructions at end of prompt — placed here so the AI sees them LAST
    # before generating its response. Earlier placement gets buried under 80+ lines of default rules.
    teacher_override_section = ""
    if custom_ai_instructions and custom_ai_instructions.strip():
        teacher_override_section = f"""

FINAL AUTHORITY — TEACHER'S GRADING INSTRUCTIONS (repeated here because they override ALL defaults above):
{custom_ai_instructions}

^^^ THESE INSTRUCTIONS OVERRIDE the default scoring rules. If the teacher says to be lenient, be lenient.
If the teacher says to accept general definitions, accept them. Do NOT contradict the teacher's instructions
in your scoring or feedback. The teacher knows their students better than any rubric."""

    prompt_text = f"""
{effective_rubric}

{section_rubric}

{ASSIGNMENT_INSTRUCTIONS}
{custom_section}
{grading_style_instructions}
{accommodation_context}
{history_context}
{writing_style_context}
{assignment_template_section}
---

STUDENT CONTEXT:
- Grade Level: {grade_level}
- Subject: {subject}
- Expected Age Range: {age_range} years old

{extracted_responses_section}

{extraction_instructions}

IMPORTANT: Assess ALL sections that appear in the EXTRACTED RESPONSES, UNANSWERED QUESTIONS, and MISSING SECTIONS above.
If a section appears in MISSING SECTIONS, the student entirely omitted a required part of the assignment — penalize accordingly.
If a section appears in UNANSWERED QUESTIONS, the student left a required section blank — penalize accordingly.
Only the extracted/marked sections, unanswered questions, and missing sections count toward the grade.

Your "student_responses" field MUST contain ONLY the raw answer text from each "STUDENT ANSWER:" line above.
Do NOT include question numbers, section names, or labels like "[1] Summary:" - just the student's actual written text.
Example: If the verified response shows 'STUDENT ANSWER: "The treaty was signed in 1803"', your student_responses should contain "The treaty was signed in 1803" - not "Summary: The treaty was signed in 1803".
If no responses were extracted, the student gets a 0.

For MATCHING exercises specifically:
- Look for numbers placed next to vocabulary terms in the extracted responses
- The number indicates which definition the student chose
- Grade whether they matched correctly

GRADING GUIDELINES:
- Assess EVERY answer the student provided.
- For fill-in-the-blank: check if the answer is factually correct or close enough.
- Accept multiple valid answers and synonyms.
- DO NOT penalize spelling mistakes if the meaning is clear.
- Be age-appropriate - these are grade {grade_level} students ({age_range} years old).
- IMPORTANT: If the teacher provided custom grading instructions above, follow them carefully.

CRITICAL - COMPLETENESS REQUIREMENTS:
- Check the EXTRACTED RESPONSES, UNANSWERED QUESTIONS, and MISSING SECTIONS lists above.
- MISSING SECTIONS are sections the teacher REQUIRED but the student ENTIRELY OMITTED from their submission.
  Each missing section must be treated the SAME as a skipped section — it lowers the grade by one full letter.
- UNANSWERED QUESTIONS are sections the student included but left blank — also penalize.
- IMPORTANT: Individual vocabulary terms or bullet points WITHIN a section that HAS a student answer are NOT unanswered questions. Only count items explicitly listed in the UNANSWERED QUESTIONS section above.
- For the sections that WERE extracted, check if the student answered them adequately, especially:
  * "Explain in your own words" sections - these require written responses, not blank
  * "Reflection" or "Final Reflection" questions - these MUST be answered
  * "Student Task" sections - these are major components requiring written responses
  * Any prompt asking students to "Write a few sentences" or "Describe" or "Explain"
  * Summary sections
  * Primary source analysis tasks
- Skipping or omitting written sections shows AVOIDANCE OF EFFORT and must be penalized!
- Count total skipped = UNANSWERED QUESTIONS + MISSING SECTIONS.
{f"""- LENIENT PENALTY SCALE (teacher selected lenient grading):
  * 0 sections skipped/missing = eligible for A (90-100)
  * 1 section skipped/missing = eligible for A/B (85-95) - minor deduction only
  * 2 sections skipped/missing = maximum B (80-89)
  * 3 sections skipped/missing = maximum C (70-79)
  * 4+ sections skipped/missing = maximum D (60-69)
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
- Students who attempt most sections with genuine effort should receive at minimum a C (70+).
- An "A" grade (90+) is possible if ALL answered sections show genuine effort and understanding.""" if grading_style == 'lenient' else f"""- STRICT PENALTY SCALE (teacher selected strict grading):
  * 0 sections skipped/missing = eligible for A (90-100)
  * 1 section skipped/missing = maximum B- (80-85) - dropped one letter
  * 2 sections skipped/missing = maximum C (70-75) - dropped two letters
  * 3 sections skipped/missing = maximum D (60-65) - dropped three letters
  * 4+ sections skipped/missing = F (below 60) - shows no effort
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
- Students who ONLY do fill-in-the-blanks and skip ALL written responses = maximum D (65)
- An "A" grade (90+) is ONLY possible if ALL sections are completed with thorough, well-developed responses.""" if grading_style == 'strict' else """- STANDARD PENALTY SCALE:
  * 0 sections skipped/missing = eligible for A (90-100)
  * 1 section skipped/missing = maximum B (80-89) - dropped one letter
  * 2 sections skipped/missing = maximum C (70-79) - dropped two letters
  * 3 sections skipped/missing = maximum D (60-69) - dropped three letters
  * 4+ sections skipped/missing = F (below 60) - shows no effort on written work
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
- Students who ONLY do fill-in-the-blanks and skip ALL written responses = maximum C (75)
- An "A" grade (90+) is ONLY possible if ALL sections are completed with quality responses."""}
- This applies to ALL assignments - skipping reflections, explanations, or analysis tasks is unacceptable
- In the "unanswered_questions" field, ONLY list items from the UNANSWERED QUESTIONS and MISSING SECTIONS lists above — do NOT invent new unanswered items from individual vocab terms or bullet points within answered sections

{fitb_authenticity_section}
{teacher_override_section}
Provide your response in the following JSON format ONLY (no other text):
{{
    "score": <FIRST calculate raw score, THEN apply the caps above. If 2 sections skipped, max is 79>,
    "letter_grade": "<A, B, C, D, or F - must match the capped score>",
    "breakdown": {{
        "content_accuracy": <points out of 40 - correctness of answers>,
        "completeness": <points out of 25 - ALL sections must be attempted. MISSING SECTIONS and UNANSWERED QUESTIONS both count as skipped. Written responses (reflections, explanations, Student Tasks) count heavily! 0-5 if 2+ major sections skipped/missing, 6-12 if 1 major section skipped/missing, 13-20 if minor gaps only, 21-25 only if ALL parts fully completed>,
        "writing_quality": <points out of 20>,
        "effort_engagement": <points out of 15>
    }},
    "student_responses": ["<EXTRACT ONLY the actual answer text that appears after 'STUDENT ANSWER:' in the verified responses above. Do NOT include the question/section name, number, or label. WRONG: 'Summary: The treaty was...' or '[1] Summary: The treaty...' - RIGHT: 'The treaty was signed in 1803 and...' - just the raw answer text the student wrote>"],
    "unanswered_questions": ["<ONLY list sections/questions from the UNANSWERED QUESTIONS and MISSING SECTIONS lists above. Do NOT list individual vocab terms or bullet points that appear WITHIN a section the student completed — those are part of the student's response, not separate unanswered questions. If a section has a STUDENT ANSWER with content, it is NOT unanswered even if individual terms within it seem brief.>"],
    "excellent_answers": ["<Quote 2-4 specific answers that were particularly strong, accurate, or showed great understanding. Include the exact text the student wrote.>"],
    "needs_improvement": ["<Quote 1-3 specific answers that were incorrect or incomplete, along with what the correct/better answer would be. Format: 'You wrote [X] but [correct info]' or 'For the question about [topic], [guidance]'>"],
    "skills_demonstrated": {{
        "strengths": ["<List 2-4 specific skills the student showed strength in. Go BEYOND the rubric categories - identify skills like: reading comprehension, critical thinking, source analysis, making connections, vocabulary usage, following directions, organization, creativity, historical thinking, cause-and-effect reasoning, comparing/contrasting, using evidence, drawing conclusions, summarizing, note-taking, attention to detail, etc. Only include skills clearly demonstrated in THIS assignment.>"],
        "developing": ["<List 1-2 skills the student is still developing or struggled with. Same skill types as above. Be specific about what skill needs work based on their answers.>"]
    }},
    "ai_detection": {{
        "flag": "<none, unlikely, possible, or likely>",
        "confidence": <number 0-100 representing confidence in the assessment>,
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "plagiarism_detection": {{
        "flag": "<none, possible, or likely>",
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "feedback": "<Write 3-4 paragraphs of thorough, personalized feedback that sounds like a real teacher wrote it - warm, encouraging, and specific. IMPORTANT GUIDELINES: 1) VARY your sentence structure and openings - don't start every sentence the same way. Mix short punchy sentences with longer ones. 2) QUOTE specific answers from the student's work when praising them (e.g., 'I loved how you explained that [quote their answer]' or 'Your answer about [topic] - '[their exact words]' - shows real understanding'). 3) When mentioning areas to improve, be gentle and constructive - reference specific questions they struggled with and give them a hint or the right direction. 4) Sound HUMAN - use contractions (you're, that's, I'm), occasional casual phrases ('Nice!', 'Great thinking here'), and vary your enthusiasm. 5) End with genuine encouragement that connects to something specific they did well. 6) Do NOT use the student's name - say 'you' or 'your'. 7) Avoid repetitive phrases like 'Great job!' at the start of every paragraph - mix it up! 8) IF STUDENT HISTORY IS PROVIDED ABOVE: Reference their progress! Mention streaks, acknowledge CONSISTENT SKILLS (e.g., 'Your reading comprehension continues to be a real strength!'), celebrate IMPROVING SKILLS (e.g., 'I notice your critical thinking is getting sharper - great progress!'), and gently encourage SKILLS TO DEVELOP (e.g., 'Keep working on making connections between ideas'). Connect current work to past achievements when relevant. 9) BILINGUAL FEEDBACK: {ell_instruction}>"
}}
"""

    print(f"  🤖 Grading with AI...")

    try:
        # FERPA COMPLIANCE: Sanitize PII from text content before sending to AI
        if assignment_data["type"] == "text":
            original_content = assignment_data['content']
            anon_id, sanitized_content = sanitize_pii_for_ai(student_name, original_content)

            # Log if any PII was removed (for audit trail)
            if sanitized_content != original_content:
                print(f"  🔒 PII sanitized from submission before AI processing")

            # HARD BLOCK: Only send extracted responses to prevent hallucination
            # If extraction succeeded, use ONLY extracted responses (not raw content)
            if extracted_responses_text:
                # Send only the pre-extracted verified responses
                print(f"  ✅ Using ONLY pre-extracted responses (hallucination prevention)")
                full_prompt = prompt_text + f"\n\nSTUDENT'S VERIFIED RESPONSES (extracted from document):\n{extracted_responses_text}"
            else:
                # Extraction failed or found nothing - REQUIRES MANUAL REVIEW
                print(f"  ⚠️  HARD BLOCK: No responses extracted - flagging for manual review")
                return {
                    "score": 0,
                    "letter_grade": "MANUAL REVIEW",
                    "breakdown": {
                        "content_accuracy": 0,
                        "completeness": 0,
                        "critical_thinking": 0,
                        "communication": 0
                    },
                    "feedback": "⚠️ MANUAL REVIEW REQUIRED: The automated extraction could not find student responses in this document. This could mean:\n\n1. The document is blank or nearly blank\n2. The formatting is unusual\n3. The student wrote in unexpected locations\n\nPlease open the original document and grade manually to prevent AI hallucination.",
                    "student_responses": [],
                    "unanswered_questions": [],
                    "authenticity_flag": "manual_review",
                    "authenticity_reason": "Extraction failed - cannot verify responses",
                    "skills_demonstrated": {},
                    "requires_manual_review": True
                }
            messages = [{"role": "user", "content": full_prompt}]

        elif assignment_data["type"] == "image":
            # Image-based assignment - use vision
            # WARNING: Cannot extract/verify responses from images - higher hallucination risk
            print(f"  ⚠️  IMAGE SUBMISSION: Cannot pre-extract responses - recommend spot-checking")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{assignment_data['media_type']};base64,{assignment_data['content']}"
                        }
                    }
                ]
            }]
            # Flag that this is an unverified image submission
            extraction_result = {"type": "image", "verified": False}
        else:
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Unknown content type"}

        # Make API call based on provider
        if provider == "anthropic":
            # Claude API call
            if assignment_data.get("type") == "image":
                claude_content = [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": assignment_data['media_type'],
                            "data": assignment_data['content']
                        }
                    }
                ]
            else:
                claude_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]

            response = with_retry(lambda: claude_client.messages.create(
                model=actual_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": claude_content}]
            ), label="grade_assignment_anthropic")
            if token_tracker:
                token_tracker.record_anthropic(response, actual_model)
            response_text = response.content[0].text.strip()

        elif provider == "gemini":
            if assignment_data.get("type") == "image":
                import base64
                image_data = base64.b64decode(assignment_data['content'])
                image_part = {
                    "mime_type": assignment_data['media_type'],
                    "data": image_data
                }
                full_prompt = prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."
                response = with_retry(
                    lambda: gemini_client.generate_content([full_prompt, image_part]),
                    label="grade_assignment_gemini_image",
                )
            else:
                text_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]
                response = with_retry(
                    lambda: gemini_client.generate_content(text_content),
                    label="grade_assignment_gemini_text",
                )
            if token_tracker:
                token_tracker.record_gemini(response, actual_model)
            response_text = response.text.strip()

        else:
            # OpenAI API call with structured output for guaranteed schema
            try:
                response = with_retry(lambda: openai_client.beta.chat.completions.parse(
                    model=ai_model,
                    messages=messages,
                    response_format=GradingResponse,
                    max_tokens=2000,
                    temperature=0,
                    seed=42
                ), label="grade_assignment_structured")
                if token_tracker:
                    token_tracker.record_openai(response, ai_model)
                parsed = response.choices[0].message.parsed
                if parsed:
                    result = parsed.model_dump()
                    original_text = json.dumps(result)
                    print(f"  ✅ Structured output parsed successfully")
                    # Skip all JSON cleanup — jump straight to post-processing below
                else:
                    # Model refused or structured parse failed — fall back to text
                    response_text = response.choices[0].message.content or ""
                    print(f"  ⚠️  Structured output empty, falling back to text parse")
                    result = None
            except Exception as structured_err:
                # Structured output not supported for this model — fall back to standard call
                print(f"  ⚠️  Structured output failed ({structured_err}), falling back to standard API")
                response = with_retry(lambda: openai_client.chat.completions.create(
                    model=ai_model,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0,
                    seed=42
                ), label="grade_assignment_fallback")
                if token_tracker:
                    token_tracker.record_openai(response, ai_model)
                response_text = response.choices[0].message.content.strip()
                result = None

            # If structured output succeeded, skip text parsing
            if result is not None:
                pass  # result already set from parsed.model_dump()
            else:
                # Text fallback: clean up and parse JSON manually
                if response_text.startswith("```"):
                    lines = response_text.split('\n')
                    start = 1 if lines[0].startswith("```") else 0
                    end = len(lines)
                    for i in range(len(lines)-1, -1, -1):
                        if lines[i].strip() == "```":
                            end = i
                            break
                    response_text = '\n'.join(lines[start:end])
                response_text = response_text.strip()
                original_text = response_text

                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    # Try basic JSON repair for text fallback
                    result = _try_parse_json_fallback(response_text)
                    if result is None:
                        raise

        # For Claude/Gemini providers, parse their text response
        if provider in ("anthropic", "gemini"):
            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```"):
                lines = response_text.split('\n')
                start = 1 if lines[0].startswith("```") else 0
                end = len(lines)
                for i in range(len(lines)-1, -1, -1):
                    if lines[i].strip() == "```":
                        end = i
                        break
                response_text = '\n'.join(lines[start:end])
            response_text = response_text.strip()
            original_text = response_text

            result = _try_parse_json_fallback(response_text)
            if result is None:
                raise json.JSONDecodeError("Failed to parse response", response_text, 0)

        # Post-processing: fix double-escaped newlines from some AI providers
        feedback = result.get("feedback", "")
        if "\\n" in feedback:
            feedback = feedback.replace("\\n", "\n")
            result["feedback"] = feedback

        # Strip any accidental bilingual sections from grading response
        if "\n---\n" in feedback:
            feedback = feedback.split("\n---\n")[0].strip()
            result["feedback"] = feedback

        # Two-pass bilingual feedback: translate via separate dedicated API call
        if ell_language and result.get("feedback"):
            print(f"  🌐 Translating feedback to {ell_language}...")
            translated = _translate_feedback(result["feedback"], ell_language, ai_model, token_tracker=token_tracker)
            if translated:
                result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                print(f"  ✅ Bilingual feedback added ({ell_language})")
            else:
                print(f"  ⚠️  Translation failed, feedback remains English only")

        # === APPLY CUSTOM RUBRIC WEIGHTS (single-pass) ===
        # rubric_weights is a list of 4 weights [content, completeness, writing, effort]
        if rubric_weights and len(rubric_weights) == 4:
            breakdown = result.get("breakdown", {})
            cat_pcts = [
                breakdown.get("content_accuracy", 0) / 40,
                breakdown.get("completeness", 0) / 25,
                breakdown.get("writing_quality", 0) / 20,
                breakdown.get("effort_engagement", 0) / 15,
            ]
            total_weight = sum(rubric_weights) or 100
            weighted_score = sum(
                pct * (w / total_weight)
                for pct, w in zip(cat_pcts, rubric_weights)
            )
            result["score"] = int(round(weighted_score * 100))
            result["score"] = max(0, min(100, result["score"]))
            s = result["score"]
            result["letter_grade"] = "A" if s >= 90 else "B" if s >= 80 else "C" if s >= 70 else "D" if s >= 60 else "F"
            print(f"  📊 Rubric-weighted score: {result['score']} ({result['letter_grade']}) [weights: {rubric_weights}]")

        # === DETERMINISTIC COMPLETENESS CAPS (single-pass) ===
        # The AI prompt asks it to penalize blank sections, but it doesn't reliably do so.
        # Apply the same deterministic caps as grade_multipass() based on actual extraction data.
        if extraction_result:
            extraction_blanks = extraction_result.get("blank_questions", [])
            extraction_missing = extraction_result.get("missing_sections", [])
            blank_count = len(extraction_blanks) + len(extraction_missing)

            # Override AI's unanswered_questions with deterministic extraction data.
            # The AI often misses blank/missing sections even when told about them.
            if blank_count > 0:
                deterministic_unanswered = extraction_blanks + extraction_missing
                ai_unanswered = result.get("unanswered_questions", [])
                # Merge: keep AI's list but ensure extraction-detected items are included
                merged = list(ai_unanswered)
                for item in deterministic_unanswered:
                    if not any(item.lower() in existing.lower() or existing.lower() in item.lower() for existing in merged):
                        merged.append(item)
                if merged != ai_unanswered:
                    print(f"  🔧 Overriding unanswered_questions: AI had {len(ai_unanswered)}, extraction found {len(deterministic_unanswered)}, merged to {len(merged)}")
                result["unanswered_questions"] = merged

            if blank_count > 0:
                if grading_style == 'strict':
                    caps = {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35, 7: 25, 8: 15}
                elif grading_style == 'lenient':
                    caps = {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49, 7: 39, 8: 29}
                else:
                    caps = {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39, 7: 29, 8: 19}
                cap = caps.get(blank_count, 0) if blank_count < len(caps) else 0
                old_score = result["score"]
                if old_score > cap:
                    result["score"] = cap
                    s = result["score"]
                    result["letter_grade"] = "A" if s >= 90 else "B" if s >= 80 else "C" if s >= 70 else "D" if s >= 60 else "F"
                    blank_names = extraction_blanks + extraction_missing
                    print(f"  📉 Completeness cap: {blank_count} blank/missing → capped {old_score} to {cap} ({result['letter_grade']})")
                    print(f"      Blank sections: {blank_names}")

        # Update student's writing profile (only if not flagged as AI)
        # This builds their baseline for future AI detection
        if student_id and student_id != "UNKNOWN" and current_writing_style:
            ai_flag = result.get("ai_detection", {}).get("flag", "none")
            if ai_flag not in ["likely", "possible"]:
                try:
                    update_writing_profile(student_id, current_writing_style, student_name)
                    print(f"  📊 Updated writing profile for {student_name}")
                except Exception as e:
                    print(f"  Note: Could not update writing profile: {e}")

        # Add style comparison info to result for transparency
        if style_comparison and style_comparison.get("ai_likelihood") in ["likely", "possible"]:
            result["writing_style_deviation"] = style_comparison

        # Add audit trail data
        result["_audit"] = {
            "ai_input": extracted_responses_section,
            "ai_response": original_text
        }

        # Add token usage tracking
        if token_tracker:
            result["token_usage"] = token_tracker.summary()

        return result

    except json.JSONDecodeError as e:
        print(f"  ⚠️  Error parsing AI response: {e}")
        # Try to show response content for debugging
        try:
            raw_preview = response_text[:800] if len(response_text) > 800 else response_text
            print(f"  ⚠️  Raw response preview:\n{raw_preview}")
            # Write full response to temp file for debugging
            import tempfile
            debug_file = tempfile.NamedTemporaryFile(mode='w', suffix='_graider_debug.json', delete=False)
            debug_file.write(response_text)
            debug_file.close()
            print(f"  ⚠️  Full response saved to: {debug_file.name}")
        except Exception:
            print(f"  ⚠️  Could not display response")

        # Try to extract key fields with regex as fallback
        try:
            score_match = re.search(r'"score":\s*(\d+)', response_text)
            grade_match = re.search(r'"letter_grade":\s*"([A-F])"', response_text)
            feedback_match = re.search(r'"feedback":\s*"([^"]{20,500})', response_text)

            if score_match and grade_match:
                print(f"  ✅ Recovered score/grade from malformed JSON")
                return {
                    "score": int(score_match.group(1)),
                    "letter_grade": grade_match.group(1),
                    "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                    "feedback": feedback_match.group(1) + "..." if feedback_match else "Grading completed but response was malformed.",
                    "student_responses": [],
                    "unanswered_questions": [],
                    "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                    "plagiarism_detection": {"flag": "none", "reason": ""},
                    "skills_demonstrated": {"strengths": [], "developing": []},
                    "json_recovery": True
                }
        except Exception:
            pass

        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": f"Error grading - AI returned invalid JSON. Please review manually."
        }
    except Exception as e:
        print(f"  ⚠️  API error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": f"API error: {e}"
        }


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
