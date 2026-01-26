"""
Email API routes for Graider.
Handles sending grade feedback emails to students.
"""
from collections import defaultdict
from flask import Blueprint, request, jsonify

email_bp = Blueprint('email', __name__)


@email_bp.route('/api/send-emails', methods=['POST'])
def send_emails():
    """Send grade emails to students."""
    try:
        from backend.services.email_service import GraiderEmailer

        emailer = GraiderEmailer()
        if not emailer.config.get('gmail_address'):
            return jsonify({"error": "Email not configured. Go to Settings to configure email."})

        data = request.json
        results = data.get('results', [])

        if not results:
            return jsonify({"error": "No results to email"})

        # Group by student email for combined emails
        students = defaultdict(list)

        for r in results:
            email = r.get('email', '')
            if email and '@' in email and r.get('student_id') != 'UNKNOWN':
                students[email].append(r)

        sent = 0
        failed = 0

        for email, grades in students.items():
            first_name = grades[0].get('student_name', 'Student').split()[0]
            teacher = emailer.config.get('teacher_name', 'Your Teacher')

            # Check for custom email content (edited by teacher)
            if len(grades) == 1 and grades[0].get('custom_email_subject') and grades[0].get('custom_email_body'):
                subject = grades[0].get('custom_email_subject')
                body = grades[0].get('custom_email_body')
            else:
                # Build default subject
                if len(grades) == 1:
                    assignment = grades[0].get('assignment', 'Assignment')
                    subject = f"Grade for {assignment}: {grades[0].get('letter_grade', '')}"
                else:
                    subject = f"Grades for {len(grades)} Assignments"

                # Build default body
                body = f"Hi {first_name},\n\n"

                if len(grades) == 1:
                    g = grades[0]
                    body += f"Here is your grade and feedback for {g.get('assignment', 'your assignment')}:\n\n"
                    body += f"{'=' * 40}\n"
                    body += f"GRADE: {g.get('score', 0)}/100 ({g.get('letter_grade', '')})\n"
                    body += f"{'=' * 40}\n\n"
                    body += f"FEEDBACK:\n{g.get('feedback', 'No feedback available.')}\n"
                else:
                    body += "Here are your grades and feedback:\n\n"
                    for g in grades:
                        body += f"{'=' * 40}\n"
                        body += f"{g.get('assignment', 'Assignment')}\n"
                        body += f"GRADE: {g.get('score', 0)}/100 ({g.get('letter_grade', '')})\n\n"
                        body += f"FEEDBACK:\n{g.get('feedback', 'No feedback available.')}\n\n"

                body += f"\n{'=' * 40}\n"
                body += f"\nIf you have any questions, please see me during class.\n\n{teacher}"

            if emailer.send_email(email, first_name, subject, body):
                sent += 1
            else:
                failed += 1

        return jsonify({"sent": sent, "failed": failed, "total": len(students)})

    except ImportError:
        return jsonify({"error": "email_service not found."})
    except Exception as e:
        return jsonify({"error": str(e)})
