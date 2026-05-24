"""Export for the grading pipeline: student email subject/body + CSV/report file
export. Flask-free (csv / file I/O — no LLM) extracted from assignment_grader.py.
Wave 7 (grading-engine decomposition). Diagnostic output uses the module logger
(the grader's debug prints became _logger calls on extraction — return values and
written files are unchanged).
"""
import csv
import logging
import random
import re
from datetime import datetime
from pathlib import Path

_logger = logging.getLogger(__name__)


def generate_email_content(student_info: dict, grade_result: dict, assignment_name: str) -> tuple:
    """
    Generate email subject and body for a student.
    
    Returns: (subject, body)
    """
    first_name = student_info.get('first_name', 'Student').split()[0]  # Just first name
    
    subject = f"Grade for {assignment_name}: {grade_result['letter_grade']}"
    
    body = f"""Hi {first_name},

Here is your grade and feedback for {assignment_name}:

GRADE: {grade_result['score']}/100 ({grade_result['letter_grade']})

FEEDBACK:
{grade_result['feedback']}

If you have any questions about your grade, please see me during class.

- Mr. Crionas US History
"""
    return subject, body


def export_detailed_report(grades: list, output_folder: str, assignment_name: str) -> str:
    """
    Create detailed CSV with all grading information for your records.
    """
    safe_name = re.sub(r'[^\w\s-]', '', assignment_name).replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = Path(output_folder) / f"Detailed_Report_{safe_name}_{timestamp}.csv"
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Student ID', 'Student Name', 'Email', 'Assignment', 'Score', 'Letter Grade',
            'Content (40)', 'Completeness (25)', 'Writing (20)', 'Effort (15)',
            'Feedback', 'Filename'
        ])
        
        for grade in grades:
            breakdown = grade.get('breakdown', {})
            writer.writerow([
                grade.get('student_id', ''),
                grade.get('student_name', ''),
                grade.get('email', ''),
                grade.get('assignment', ''),
                grade.get('score', ''),
                grade.get('letter_grade', ''),
                breakdown.get('content_accuracy', ''),
                breakdown.get('completeness', ''),
                breakdown.get('writing_quality', ''),
                breakdown.get('effort_engagement', breakdown.get('critical_thinking', '')),
                grade.get('feedback', ''),
                grade.get('filename', '')
            ])
    
    _logger.info("Detailed report saved: %s", filepath)
    return str(filepath)


def export_focus_csv(grades: list, output_folder: str, assignment_name: str) -> list:
    """
    Create CSV files formatted for Focus import, SEPARATED BY ASSIGNMENT.
    
    Groups students by the assignment extracted from their filename,
    creates one CSV per assignment type.
    
    Format:
    Student ID,Score,Comment
    1950304,85,"Great job, Jackson! You correctly identified..."
    1956701,92,"Excellent work, Maria!..."
    
    Returns list of created file paths.
    """
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Group grades by assignment
    assignments = {}
    for grade in grades:
        # Extract assignment name from filename (everything after FirstName_LastName_)
        filename = grade.get('filename', '')
        parts = Path(filename).stem.split('_')
        if len(parts) >= 3:
            # Assignment is everything after first two parts (first_last)
            assignment = '_'.join(parts[2:])
        else:
            assignment = "Unknown_Assignment"
        
        # Clean up assignment name for display (replace underscores with spaces)
        assignment = assignment.strip().replace('_', ' ')
        
        if assignment not in assignments:
            assignments[assignment] = []
        assignments[assignment].append(grade)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    created_files = []
    
    _logger.info("Creating %d separate Focus CSVs by assignment", len(assignments))
    
    for assignment, assignment_grades in assignments.items():
        # Clean assignment name for filename
        safe_name = re.sub(r'[^\w\s-]', '', assignment).replace(' ', '_')[:50]
        filepath = Path(output_folder) / f"{safe_name}_{timestamp}.csv"
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Column headers: Student ID, Score, Comment
            writer.writerow(['Student ID', 'Score', 'Comment'])
            
            for grade in assignment_grades:
                if grade['student_id'] != "UNKNOWN":
                    # Get student's first name only (no middle initial)
                    full_first = grade.get('first_name', '')
                    first_name = full_first.split()[0] if full_first else ''
                    
                    # Clean up feedback
                    feedback = grade.get('feedback', '')
                    feedback_clean = ' '.join(feedback.split())
                    
                    # Varied natural phrases based on grade
                    score = grade.get('score', 0)
                    
                    if first_name:
                        if score >= 90:
                            openers = [
                                f"Great job, {first_name}!",
                                f"Excellent work, {first_name}!",
                                f"{first_name}, this was fantastic!",
                                f"Well done, {first_name}!",
                                f"{first_name}, you nailed this!"
                            ]
                        elif score >= 80:
                            openers = [
                                f"Nice work, {first_name}!",
                                f"Good job, {first_name}!",
                                f"{first_name}, solid effort here!",
                                f"Well done, {first_name}!",
                                f"{first_name}, this was good work!"
                            ]
                        elif score >= 70:
                            openers = [
                                f"{first_name}, decent effort!",
                                f"Good start, {first_name}!",
                                f"{first_name}, you're on the right track!",
                                f"Keep it up, {first_name}!",
                                f"{first_name}, nice try!"
                            ]
                        else:
                            openers = [
                                f"{first_name}, let's work on this together.",
                                f"{first_name}, I know you can do better!",
                                f"Keep trying, {first_name}!",
                                f"{first_name}, don't give up!",
                                f"{first_name}, let's review this."
                            ]
                        
                        opener = random.choice(openers)  # nosec B311 — comment-opener variety, not security
                        comment = f"{opener} {feedback_clean}"
                    else:
                        comment = feedback_clean
                    
                    writer.writerow([
                        grade['student_id'], 
                        grade['score'],
                        comment
                    ])
        
        _logger.info("%s: %d students -> %s", assignment, len(assignment_grades), filepath.name)
        created_files.append(str(filepath))
    
    return created_files
