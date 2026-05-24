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
import re
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


from backend.services.grader_text_prep import preprocess_for_ai_detection as preprocess_for_ai_detection  # noqa: F401 re-export (test_grader_text_prep imports via assignment_grader)
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
