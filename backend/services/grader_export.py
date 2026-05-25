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


def save_to_master_csv(grades: list, output_folder: str):
    """
    Save grades to a master CSV file that tracks ALL grades over time.
    This enables progress tracking across the entire school year.

    DEDUPLICATION: If a student is re-graded on the same assignment,
    the old row is REPLACED (not duplicated). The unique key is
    (Student ID, Assignment).

    Columns:
    - Date, Student ID, Student Name, Period, Assignment, Unit, Quarter
    - Overall Score, Letter Grade
    - Content Accuracy, Completeness, Writing Quality, Effort & Engagement
    """
    master_file = Path(output_folder) / "master_grades.csv"

    HEADER = [
        'Date', 'Student ID', 'Student Name', 'First Name', 'Last Name',
        'Period', 'Assignment', 'Unit', 'Quarter',
        'Overall Score', 'Letter Grade',
        'Content Accuracy', 'Completeness', 'Writing Quality', 'Effort Engagement',
        'Feedback', 'Approved',
        'API Cost', 'Input Tokens', 'Output Tokens', 'API Calls', 'AI Model'
    ]

    # Determine current quarter based on date
    today = datetime.now()
    month = today.month
    if month >= 8 and month <= 10:
        quarter = "Q1"
    elif month >= 11 or month <= 1:
        quarter = "Q2"
    elif month >= 2 and month <= 4:
        quarter = "Q3"
    else:
        quarter = "Q4"

    # Normalize assignment name for dedup matching
    # Handles: trailing "(1)", ".docx", extra whitespace, etc.
    def _normalize_assignment(name):
        n = name.strip()
        n = re.sub(r'\s*\(\d+\)\s*$', '', n)      # Remove trailing (1), (2), etc.
        n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)  # Remove .docx/.doc
        n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)    # Remove .pdf
        n = n.strip().lower()
        return n

    # Build set of (student_id, normalized_assignment) keys being written now
    new_keys = set()
    for grade in grades:
        sid = grade.get('student_id', '')
        assignment = grade.get('assignment', '')
        if sid and sid != "UNKNOWN" and assignment:
            new_keys.add((sid, _normalize_assignment(assignment)))

    # Read existing rows, filtering out any that will be replaced (only if new score >= old)
    existing_rows = []
    kept_old_keys = set()
    if master_file.exists():
        try:
            with open(master_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header row (value unused)
                for row in reader:
                    if len(row) >= 7:
                        row_sid = row[1]       # Student ID column
                        row_assign = row[6]    # Assignment column
                        key = (row_sid, _normalize_assignment(row_assign))
                        if key in new_keys:
                            # Compare scores — only replace if new is higher or equal
                            old_score = float(row[9]) if len(row) > 9 and row[9] else 0
                            new_grade = next((g for g in grades if g.get('student_id') == row_sid and _normalize_assignment(g.get('assignment', '')) == key[1]), None)
                            new_score = float(new_grade.get('score', 0) or 0) if new_grade else 0
                            if new_score >= old_score:
                                continue  # Replace — new is higher or equal
                            else:
                                kept_old_keys.add(key)
                                # Keep old row, skip the new grade
                    existing_rows.append(row)
        except Exception as e:
            _logger.warning("Could not read existing master CSV: %s", e)

    # Filter out grades where old score was kept
    if kept_old_keys:
        grades = [g for g in grades if (g.get('student_id', ''), _normalize_assignment(g.get('assignment', ''))) not in kept_old_keys]

    # Write full file: header + existing (deduplicated) + new grades
    with open(master_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)

        # Write back existing rows (minus duplicates)
        for row in existing_rows:
            writer.writerow(row)

        # Write new grades
        for grade in grades:
            if grade.get('student_id') == "UNKNOWN":
                continue

            breakdown = grade.get('breakdown', {})

            token_usage = grade.get('token_usage', {})

            writer.writerow([
                today.strftime('%Y-%m-%d'),
                grade.get('student_id', ''),
                grade.get('student_name', ''),
                grade.get('first_name', ''),
                grade.get('last_name', ''),
                grade.get('period', ''),
                grade.get('assignment', ''),
                grade.get('unit', ''),
                grade.get('grading_period', quarter),
                grade.get('score', 0),
                grade.get('letter_grade', ''),
                breakdown.get('content_accuracy', 0),
                breakdown.get('completeness', 0),
                breakdown.get('writing_quality', 0),
                breakdown.get('effort_engagement', 0),
                grade.get('feedback', '').replace('\r', ' ').replace('\n', ' ')[:500],
                grade.get('email_approval', 'pending'),
                token_usage.get('total_cost', ''),
                token_usage.get('total_input_tokens', ''),
                token_usage.get('total_output_tokens', ''),
                token_usage.get('api_calls', ''),
                grade.get('ai_model', '')
            ])
    
    _logger.info("Updated master grades file: %s", master_file)


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
    
    _logger.info(f"📧 Saved {email_count} email files to: {email_folder}")
