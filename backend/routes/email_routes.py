"""
Email API routes for Graider.
Handles sending grade feedback emails to students via Resend.
"""
import os
import sys
import json
import subprocess
import threading
from collections import defaultdict
from datetime import datetime
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

        # Load parent contacts for email fallback
        parent_contacts = {}
        contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
        if os.path.exists(contacts_file):
            try:
                with open(contacts_file, 'r', encoding='utf-8') as cf:
                    parent_contacts = json.load(cf)
            except Exception:
                pass

        # Group by student email for combined emails
        students = defaultdict(list)

        for r in results:
            # Support both 'email' and 'student_email' field names
            email = r.get('student_email') or r.get('email', '')
            # Fallback: look up parent email from parent_contacts.json
            if (not email or '@' not in email) and r.get('student_id'):
                contact = parent_contacts.get(str(r['student_id']), {})
                parent_emails = contact.get('parent_emails', [])
                if parent_emails:
                    email = parent_emails[0]
                    r['_cc_emails'] = parent_emails[1:] if len(parent_emails) > 1 else []
            if email and '@' in email:
                students[email].append(r)

        sent = 0
        failed = 0

        for email, grades in students.items():
            # Extract first name correctly from "Last, First" or "First Last" formats
            raw_name = grades[0].get('student_name', 'Student')
            if ',' in raw_name or ';' in raw_name:
                sep = ',' if ',' in raw_name else ';'
                after = raw_name.split(sep, 1)[1].strip()
                first_name = after.split()[0] if after else raw_name.split()[0]
            else:
                first_name = raw_name.split()[0]
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
                    # Use grading period from first result for combined emails
                    grading_period = grades[0].get('grading_period', 'Q3')
                    subject = f"Your Assignment Grades - {grading_period} Progress Report"

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
                    grading_period = grades[0].get('grading_period', 'this quarter')
                    body += f"Here are your grades and feedback for {grading_period} so far:\n\n"
                    for g in grades:
                        body += f"{'=' * 40}\n"
                        body += f"📚 {g.get('assignment', 'Assignment')}\n"
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


# ══════════════════════════════════════════════════════════════
# OUTLOOK EMAIL EXPORT
# ══════════════════════════════════════════════════════════════

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
PARENT_CONTACTS_FILE = os.path.join(GRAIDER_DATA_DIR, "parent_contacts.json")
OUTLOOK_EXPORTS_DIR = os.path.expanduser("~/.graider_exports/outlook")
os.makedirs(OUTLOOK_EXPORTS_DIR, exist_ok=True)


@email_bp.route('/api/export-outlook-emails', methods=['POST'])
def export_outlook_emails():
    """
    Build email payloads for parent notification via Outlook.
    Matches students to parent emails via parent_contacts.json.

    Writes JSON to ~/.graider_exports/outlook/

    Input JSON: {
        results?,           # defaults to saved results
        teacher_name?,      # defaults to saved config
        email_signature?,   # custom signature
        include_secondary?  # include CC for secondary contacts (default true)
    }
    """
    try:
        data = request.json or {}

        # Load parent contacts
        if not os.path.exists(PARENT_CONTACTS_FILE):
            return jsonify({
                "error": "No parent contacts imported. Upload class list in Settings first."
            }), 400

        with open(PARENT_CONTACTS_FILE, 'r') as f:
            contacts = json.load(f)

        # Get results - try request body first, then saved results file
        results = data.get('results', [])
        if not results:
            try:
                results_file = os.path.expanduser("~/.graider_results.json")
                if os.path.exists(results_file):
                    with open(results_file, 'r') as f:
                        results = json.load(f)
            except Exception:
                pass

        if not results:
            return jsonify({"error": "No results to export"}), 400

        teacher_name = data.get('teacher_name', 'Your Teacher')
        email_signature = data.get('email_signature', '')
        include_secondary = data.get('include_secondary', True)
        assignment = data.get('assignment') or results[0].get('assignment', 'Assignment')

        # Try to load teacher config
        try:
            from backend.services.email_service import GraiderEmailer
            emailer = GraiderEmailer()
            if not teacher_name or teacher_name == 'Your Teacher':
                teacher_name = emailer.config.get('teacher_name', teacher_name)
        except Exception:
            pass

        emails = []
        no_contact = []

        for r in results:
            student_id = r.get('student_id', '')
            student_name = r.get('student_name', 'Student')
            score = r.get('score', 0)
            letter_grade = r.get('letter_grade', '')
            feedback = r.get('feedback', '')
            period = r.get('period', '')
            first_name = student_name.split()[0] if student_name else 'Student'
            last_name = student_name.split()[-1] if student_name and len(student_name.split()) > 1 else ''

            # Look up parent contact by student_id
            contact = contacts.get(student_id, {})
            parent_emails = contact.get('parent_emails', [])

            if not parent_emails:
                no_contact.append(student_name)
                continue

            # Build email
            to_email = parent_emails[0]
            cc_emails = parent_emails[1:] if include_secondary and len(parent_emails) > 1 else []

            subject = f"Grade for {assignment}: {letter_grade}"

            family_name = last_name or first_name
            body = f"Dear {family_name} family,\n\n"
            body += f"Here is {first_name}'s grade and feedback for {assignment}:\n\n"
            body += f"{'=' * 40}\n"
            body += f"GRADE: {score}/100 ({letter_grade})\n"
            body += f"{'=' * 40}\n\n"
            body += f"FEEDBACK:\n{feedback}\n"
            body += f"\n{'=' * 40}\n"
            body += f"\nIf you have any questions, please don't hesitate to reach out.\n\n"

            if email_signature:
                body += email_signature
            else:
                body += teacher_name

            emails.append({
                "to": to_email,
                "cc": ', '.join(cc_emails) if cc_emails else '',
                "subject": subject,
                "body": body,
                "student_name": student_name,
                "student_id": student_id,
                "period": period,
            })

        # Write to file
        safe_assignment = ''.join(
            c if c.isalnum() or c in ' -_' else '' for c in assignment
        ).strip().replace(' ', '_')

        output = {
            "assignment": assignment,
            "exported_at": datetime.now().isoformat(),
            "emails": emails,
            "count": len(emails),
            "no_contact": no_contact,
            "export_dir": OUTLOOK_EXPORTS_DIR,
        }

        output_path = os.path.join(OUTLOOK_EXPORTS_DIR, f"emails_{safe_assignment}.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        return jsonify(output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# OUTLOOK PLAYWRIGHT SENDING
# ══════════════════════════════════════════════════════════════

_outlook_send_state = {
    "process": None,
    "status": "idle",      # idle | running | done | error
    "sent": 0,
    "failed": 0,
    "total": 0,
    "message": "",
    "log": [],
}


def _read_outlook_output(proc):
    """Background thread: read subprocess stdout and update state."""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            etype = event.get("type", "")
            if etype == "progress":
                _outlook_send_state["sent"] = event.get("sent", 0)
                _outlook_send_state["total"] = event.get("total", 0)
                _outlook_send_state["message"] = event.get("message", "")
            elif etype == "status":
                _outlook_send_state["message"] = event.get("message", "")
            elif etype == "done":
                _outlook_send_state["status"] = "done"
                _outlook_send_state["sent"] = event.get("sent", 0)
                _outlook_send_state["failed"] = event.get("failed", 0)
                _outlook_send_state["message"] = "Complete"
            elif etype == "error":
                _outlook_send_state["failed"] += 1
                _outlook_send_state["message"] = event.get("message", "")
            _outlook_send_state["log"].append(event)
            if len(_outlook_send_state["log"]) > 100:
                _outlook_send_state["log"] = _outlook_send_state["log"][-50:]
        except json.JSONDecodeError:
            pass

    if _outlook_send_state["status"] == "running":
        _outlook_send_state["status"] = "done"


@email_bp.route('/api/send-outlook-emails', methods=['POST'])
def send_outlook_emails():
    """Start sending emails via Playwright Outlook automation."""
    if _outlook_send_state.get("status") == "running":
        return jsonify({"error": "Already sending. Check status or wait."}), 409

    try:
        data = request.json or {}
        email_type = data.get("type", "parent")

        if email_type == "parent":
            if not os.path.exists(PARENT_CONTACTS_FILE):
                return jsonify({"error": "No parent contacts imported."}), 400

            with open(PARENT_CONTACTS_FILE, 'r') as f:
                contacts = json.load(f)

            results = data.get('results', [])
            if not results:
                return jsonify({"error": "No results provided"}), 400

            teacher_name = data.get('teacher_name', 'Your Teacher')
            email_signature = data.get('email_signature', '')
            include_secondary = data.get('include_secondary', True)
            assignment = data.get('assignment') or results[0].get('assignment', 'Assignment')

            emails = []
            for r in results:
                student_id = r.get('student_id', '')
                student_name = r.get('student_name', 'Student')
                score = r.get('score', 0)
                letter_grade = r.get('letter_grade', '')
                feedback = r.get('feedback', '')
                first_name = student_name.split()[0] if student_name else 'Student'
                last_name = student_name.split()[-1] if student_name and len(student_name.split()) > 1 else ''

                contact = contacts.get(student_id, {})
                parent_emails = contact.get('parent_emails', [])
                if not parent_emails:
                    continue

                to_email = parent_emails[0]
                cc_emails = parent_emails[1:] if include_secondary and len(parent_emails) > 1 else []

                subject = "Grade for " + assignment + ": " + letter_grade
                family_name = last_name or first_name
                body = "Dear " + family_name + " family,\n\n"
                body += "Here is " + first_name + "'s grade and feedback for " + assignment + ":\n\n"
                body += "=" * 40 + "\n"
                body += "GRADE: " + str(score) + "/100 (" + letter_grade + ")\n"
                body += "=" * 40 + "\n\n"
                body += "FEEDBACK:\n" + feedback + "\n"
                body += "\n" + "=" * 40 + "\n"
                body += "\nIf you have any questions, please don't hesitate to reach out.\n\n"
                body += email_signature if email_signature else teacher_name

                emails.append({
                    "to": to_email,
                    "cc": ', '.join(cc_emails) if cc_emails else '',
                    "subject": subject,
                    "body": body,
                    "student_name": student_name,
                })

        else:
            # Student emails
            results = data.get('results', [])
            if not results:
                return jsonify({"error": "No results provided"}), 400

            teacher_name = data.get('teacher_name', 'Your Teacher')
            email_signature = data.get('email_signature', '')

            emails = []
            for r in results:
                student_email = r.get('student_email') or r.get('email', '')
                if not student_email or '@' not in student_email:
                    continue

                student_name = r.get('student_name', 'Student')
                first_name = student_name.split()[0]
                assignment = r.get('assignment', 'Assignment')
                score = r.get('score', 0)
                letter_grade = r.get('letter_grade', '')
                feedback = r.get('feedback', '')

                subject = "Grade for " + assignment + ": " + letter_grade
                body = "Hi " + first_name + ",\n\n"
                body += "Here is your grade and feedback for " + assignment + ":\n\n"
                body += "=" * 40 + "\n"
                body += "GRADE: " + str(score) + "/100 (" + letter_grade + ")\n"
                body += "=" * 40 + "\n\n"
                body += "FEEDBACK:\n" + feedback + "\n"
                body += "\n" + "=" * 40 + "\n"
                body += "\nIf you have any questions, please see me during class.\n\n"
                body += email_signature if email_signature else teacher_name

                emails.append({
                    "to": student_email,
                    "cc": "",
                    "subject": subject,
                    "body": body,
                    "student_name": student_name,
                })

        if not emails:
            return jsonify({"error": "No emails to send (no matching contacts)"}), 400

        # Write temp JSON for the Playwright script
        tmp_file = os.path.join(GRAIDER_DATA_DIR, "tmp_outlook_emails.json")
        os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
        with open(tmp_file, 'w') as f:
            json.dump({"emails": emails}, f)

        # Reset state
        _outlook_send_state.update({
            "status": "running",
            "sent": 0,
            "failed": 0,
            "total": len(emails),
            "message": "Starting Outlook...",
            "log": [],
        })

        # Spawn Playwright script
        script_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'outlook_sender.py')
        proc = subprocess.Popen(
            [sys.executable, script_path, tmp_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        _outlook_send_state["process"] = proc

        thread = threading.Thread(target=_read_outlook_output, args=(proc,), daemon=True)
        thread.start()

        return jsonify({"status": "started", "total": len(emails)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@email_bp.route('/api/outlook-send/status')
def outlook_send_status():
    """Get current Outlook sending progress."""
    return jsonify({
        "status": _outlook_send_state.get("status", "idle"),
        "sent": _outlook_send_state.get("sent", 0),
        "failed": _outlook_send_state.get("failed", 0),
        "total": _outlook_send_state.get("total", 0),
        "message": _outlook_send_state.get("message", ""),
    })


@email_bp.route('/api/outlook-login', methods=['POST'])
def outlook_login():
    """Open Outlook in browser for login verification."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'outlook_sender.py')
        subprocess.Popen(
            [sys.executable, script_path, "--login-only"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return jsonify({"status": "started", "message": "Browser opening..."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
