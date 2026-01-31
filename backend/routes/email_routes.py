"""
Email API routes for Graider.
Handles sending grade feedback emails to students via Resend.
"""
from collections import defaultdict
from flask import Blueprint, request, jsonify

email_bp = Blueprint('email', __name__)


@email_bp.route('/api/send-emails', methods=['POST'])
def send_emails():
    """Send grade emails to students via Resend."""
    try:
        from backend.services.email_service import GraiderEmailer

        emailer = GraiderEmailer()
        if not emailer.resend_available:
            return jsonify({
                "error": "Email not configured. Make sure RESEND_API_KEY is in .env file."
            })

        data = request.json
        results = data.get('results', [])
        teacher_email = data.get('teacher_email', '')  # For Reply-To
        teacher_name = data.get('teacher_name', '') or emailer.config.get('teacher_name', 'Your Teacher')
        email_signature = data.get('email_signature', '')

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
            teacher = teacher_name

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
                body += f"\nIf you have any questions, please see me during class.\n\n"
                # Add custom signature or default
                if email_signature:
                    body += email_signature
                else:
                    body += teacher
                body += "\n\n---\nThis email was sent by Graider (https://graider.live)"

            # Use teacher_email from request as Reply-To
            reply_to = teacher_email or emailer.config.get('teacher_email')

            if emailer.send_email(email, first_name, subject, body, reply_to):
                sent += 1
            else:
                failed += 1

        return jsonify({"sent": sent, "failed": failed, "total": len(students)})

    except ImportError:
        return jsonify({"error": "email_service not found."})
    except Exception as e:
        return jsonify({"error": str(e)})


@email_bp.route('/api/test-email', methods=['POST'])
def test_email():
    """Send a test email to verify configuration."""
    try:
        from backend.services.email_service import GraiderEmailer

        emailer = GraiderEmailer()

        data = request.json or {}
        test_address = data.get('email', 'delivered@resend.dev')

        if emailer.test_connection(test_address):
            return jsonify({"success": True, "message": f"Test email sent to {test_address}"})
        else:
            return jsonify({
                "success": False,
                "message": "Failed to send test email. Check RESEND_API_KEY in .env"
            })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@email_bp.route('/api/email-status', methods=['GET'])
def email_status():
    """Check if email is configured."""
    try:
        from backend.services.email_service import GraiderEmailer, RESEND_AVAILABLE

        if not RESEND_AVAILABLE:
            return jsonify({
                "configured": False,
                "message": "Resend package not installed. Run: pip install resend"
            })

        emailer = GraiderEmailer()

        return jsonify({
            "configured": emailer.resend_available,
            "from_email": emailer.from_email if emailer.resend_available else None,
            "teacher_name": emailer.config.get('teacher_name', ''),
            "teacher_email": emailer.config.get('teacher_email', ''),
            "message": "Ready to send emails" if emailer.resend_available else "RESEND_API_KEY not configured"
        })

    except Exception as e:
        return jsonify({"configured": False, "message": str(e)})


@email_bp.route('/api/save-email-config', methods=['POST'])
def save_email_config():
    """Save teacher email configuration."""
    try:
        from backend.services.email_service import GraiderEmailer

        data = request.json
        teacher_name = data.get('teacher_name', 'Your Teacher')
        teacher_email = data.get('teacher_email', '')

        emailer = GraiderEmailer()
        emailer.save_config(teacher_name, teacher_email)

        return jsonify({"success": True, "message": "Email configuration saved"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
