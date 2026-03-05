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


def launch_outlook_sender(emails, teacher_id='local-dev'):
    """Write email payloads to temp file and spawn the Playwright Outlook sender.

    Args:
        emails: list of dicts with keys: to, cc, subject, body, student_name
        teacher_id: teacher identifier for credential lookup

    Returns:
        dict with status and total count, or error
    """
    if _outlook_send_state.get("status") == "running":
        return {"error": "Already sending. Check status or wait."}

    if not emails:
        return {"error": "No emails to send"}

    # Write per-teacher creds to temp file for subprocess access
    from backend.routes.assistant_routes import write_temp_creds_file
    if not write_temp_creds_file(teacher_id):
        return {"error": "VPortal credentials not configured. Go to Settings > Tools to set them up."}

    tmp_file = os.path.join(GRAIDER_DATA_DIR, "tmp_outlook_emails.json")
    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
    with open(tmp_file, 'w') as f:
        json.dump({"emails": emails}, f)

    _outlook_send_state.update({
        "status": "running",
        "sent": 0,
        "failed": 0,
        "total": len(emails),
        "message": "Starting Outlook...",
        "log": [],
    })

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

    return {"status": "started", "total": len(emails)}


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

        from flask import g
        teacher_id = getattr(g, 'user_id', 'local-dev')
        result = launch_outlook_sender(emails, teacher_id=teacher_id)
        if "error" in result:
            return jsonify(result), 409
        return jsonify(result)

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
        # Write per-teacher creds to temp file for subprocess access
        from flask import g
        teacher_id = getattr(g, 'user_id', 'local-dev')
        from backend.routes.assistant_routes import write_temp_creds_file
        if not write_temp_creds_file(teacher_id):
            return jsonify({"error": "VPortal credentials not configured. Go to Settings > Tools to set them up."}), 400
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


# ══════════════════════════════════════════════════════════════
# FILE-BASED CONFIRMATION EMAILS
# ══════════════════════════════════════════════════════════════

ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_assignments")
RESULTS_FILE = os.path.expanduser("~/.graider_results.json")


def _unique_roster_students(roster, period_filter=''):
    """Yield deduplicated (student_name, info) from roster, filtered by period and valid email."""
    seen_ids = set()
    for key, val in roster.items():
        vid = id(val)
        if vid in seen_ids:
            continue
        seen_ids.add(vid)
        email = val.get('email', '')
        if not email or '@' not in email:
            continue
        if period_filter and val.get('period', '') != period_filter:
            continue
        student_name = val.get('student_name', '')
        if student_name:
            yield student_name, val


def _normalize_submission_name(raw_name):
    """Normalize a filename-derived assignment name for dedup and matching.

    Strips version suffixes like (1), (2), trailing numbers,
    replaces underscores with spaces, and cleans up punctuation.
    """
    import re
    name = raw_name.strip()
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    # Strip trailing version suffixes: " (1)", " (2)", " 1", " 2" at end
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\s+\d+\s*$', '', name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _match_to_config_title(normalized_name, config_titles):
    """Find the best matching config title for a normalized assignment name.

    Returns the config title if matched, otherwise the normalized name itself.
    """
    import re
    if not config_titles:
        return normalized_name

    n_lower = normalized_name.lower()

    # Try exact match first
    for title in config_titles:
        if title.lower() == n_lower:
            return title

    # Try substring: config title contains the name or vice versa
    for title in config_titles:
        t_lower = title.lower()
        if n_lower in t_lower or t_lower in n_lower:
            return title

    # Word overlap: normalize both sides and compare
    def _words(s):
        return set(re.sub(r'[^\w\s]', ' ', s.lower()).split())

    n_words = _words(normalized_name)
    if len(n_words) < 2:
        return normalized_name

    best_title = None
    best_overlap = 0
    for title in config_titles:
        t_words = _words(title)
        overlap = len(n_words & t_words)
        # Require at least 60% of the shorter set's words to match
        min_len = min(len(n_words), len(t_words))
        if overlap >= max(2, min_len * 0.6) and overlap > best_overlap:
            best_overlap = overlap
            best_title = title

    return best_title or normalized_name



def _find_in_roster(roster, parsed):
    """Find a student in the roster using multiple matching strategies.

    parse_filename() returns a single lookup_key like 'firstname lastname',
    but the roster may store names differently.  Try several fallbacks before
    giving up.
    """
    import re

    lookup_key = parsed.get('lookup_key', '')

    # Strategy 1: direct lookup
    info = roster.get(lookup_key)
    if info:
        return info

    first = parsed.get('first_name', '').strip()
    last = parsed.get('last_name', '').strip()

    # Strategy 2: reverse name order
    if first and last:
        reverse_key = f"{last} {first}".lower()
        info = roster.get(reverse_key)
        if info:
            return info

    # Strategy 3: strip punctuation / middle initials and retry
    clean_first = re.sub(r'[^\w\s]', '', first).strip().split()[0] if first else ''
    clean_last = re.sub(r'[^\w\s]', '', last).strip()
    if clean_first or clean_last:
        clean_key = f"{clean_first} {clean_last}".lower().strip()
        if clean_key != lookup_key:
            info = roster.get(clean_key)
            if info:
                return info
            # also reversed
            clean_rev = f"{clean_last} {clean_first}".lower().strip()
            info = roster.get(clean_rev)
            if info:
                return info

    # Strategy 4: prefix match — handles last-initial-only filenames
    # e.g., "Serenity P" should match "Serenity Petite"
    if first and last and len(last) <= 2:
        first_lower = clean_first.lower() if clean_first else first.lower()
        last_lower = last.lower()
        seen_ids = set()
        for key, val in roster.items():
            vid = id(val)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            r_first = val.get('first_name', '').split()[0].lower() if val.get('first_name') else ''
            r_last = val.get('last_name', '').lower()
            if r_first == first_lower and r_last.startswith(last_lower):
                return val

    # Strategy 5: fuzzy match — handles typos and nicknames
    # Match when one name is exact and the other is within edit distance 2
    if first and last:
        first_lower = (clean_first or first).lower()
        last_lower = (clean_last or last).lower()
        best = None
        best_dist = 3  # max acceptable distance
        seen_ids = set()
        for key, val in roster.items():
            vid = id(val)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            r_first = val.get('first_name', '').split()[0].lower() if val.get('first_name') else ''
            r_last = val.get('last_name', '').lower()
            if not r_first or not r_last:
                continue
            # Exact last + fuzzy first, or exact first + fuzzy last
            if r_last == last_lower:
                d = _edit_distance(first_lower, r_first)
                if d < best_dist:
                    best, best_dist = val, d
            elif r_first == first_lower:
                d = _edit_distance(last_lower, r_last)
                if d < best_dist:
                    best, best_dist = val, d
        if best:
            return best

    return None


def _edit_distance(a, b):
    """Levenshtein distance between two strings."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


@email_bp.route('/api/send-confirmation-emails', methods=['POST'])
def send_confirmation_emails():
    """Send submission-received confirmations for ALL files in the assignments folder.

    Scans the assignments folder (SharePoint sync), matches each file to a
    student via the roster, and sends confirmation emails for every file
    that hasn't already been confirmed — graded or not.
    """
    try:
        from pathlib import Path

        data = request.json or {}
        assignments_folder = data.get('assignments_folder', '')
        teacher_name = data.get('teacher_name', 'Your Teacher')
        period_filter = data.get('period_filter', '')
        student_filter = data.get('student_filter', '')
        cc_parents = data.get('cc_parents', False)

        if not assignments_folder or not os.path.exists(assignments_folder):
            return jsonify({"error": "Assignments folder not found: " + assignments_folder}), 400

        # Load roster from period CSVs (no Excel roster needed)
        try:
            from assignment_grader import build_roster_from_periods, parse_filename
        except ImportError:
            from backend.assignment_grader import build_roster_from_periods, parse_filename

        roster = build_roster_from_periods()
        if not roster:
            return jsonify({"error": "No students found in period CSVs (~/.graider_data/periods/)"}), 400

        # Load already-confirmed filenames from confirmations file + grading_state
        confirmed_filenames = _load_confirmed_filenames()
        from backend.routes.grading_routes import grading_state, grading_lock
        if grading_state and grading_state.get("results"):
            lock = grading_lock
            results = grading_state["results"] if not lock else None
            if lock:
                with lock:
                    results = list(grading_state["results"])
            for r in (results or []):
                if r.get('confirmation_sent'):
                    confirmed_filenames.add(r.get('filename', ''))

        # Scan assignments folder for all submitted files
        assignment_path = Path(assignments_folder)
        all_files = []
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.pdf']:
            all_files.extend(assignment_path.glob(ext))

        # Load all saved assignment config titles (and aliases) for matching.
        # alias_to_title maps every name (title + aliases) back to the canonical title.
        all_assignment_titles = set()
        alias_to_title = {}
        if os.path.exists(ASSIGNMENTS_DIR):
            for f in os.listdir(ASSIGNMENTS_DIR):
                if f.endswith('.json'):
                    try:
                        filepath = os.path.join(ASSIGNMENTS_DIR, f)
                        with open(filepath, 'r') as fh:
                            cfg = json.load(fh)
                        title = cfg.get('title') or f.replace('.json', '')
                        all_assignment_titles.add(title)
                        alias_to_title[title] = title
                        for alias in cfg.get('aliases', []):
                            if alias:
                                alias_to_title[alias] = title
                    except Exception:
                        pass
        all_config_names = set(alias_to_title.keys())

        # Track which assignments each student has submitted (by file presence)
        student_submitted = defaultdict(set)
        # Build list of eligible files
        eligible_files = []

        for filepath in all_files:
            filename = filepath.name
            if filename in confirmed_filenames:
                continue

            parsed = parse_filename(filename)
            student_info = _find_in_roster(roster, parsed)
            if not student_info:
                continue

            email = student_info.get('email', '')
            if not email or '@' not in email:
                continue

            student_period = student_info.get('period', '')
            if period_filter and student_period != period_filter:
                continue

            student_name_check = student_info.get('student_name', '')
            if student_filter and student_name_check != student_filter:
                continue

            raw_part = parsed.get('assignment_part', '') or 'Assignment'
            normalized = _normalize_submission_name(raw_part)
            matched = _match_to_config_title(normalized, all_config_names)
            canonical = alias_to_title.get(matched, matched)

            # Skip files that don't match any saved assignment config
            if canonical not in all_assignment_titles:
                continue

            eligible_files.append({
                'filename': filename,
                'student_name': student_info.get('student_name', 'Student'),
                'first_name': student_info.get('first_name', 'Student'),
                'email': email,
                'student_id': student_info.get('student_id', ''),
                'assignment': canonical,
            })

            student_submitted[student_info.get('student_name', '')].add(canonical)

        # Group eligible files by student for one email per student
        students_map = {}
        sent_filenames = []
        for f in eligible_files:
            name = f['student_name']
            if name not in students_map:
                students_map[name] = {
                    'first_name': f['first_name'],
                    'email': f['email'],
                    'student_id': f.get('student_id', ''),
                    'assignments': [],
                    'filenames': [],
                }
            students_map[name]['assignments'].append(f['assignment'])
            students_map[name]['filenames'].append(f['filename'])

        # Scan ALL files (including already confirmed) to build
        # all_student_submitted for the "outstanding" calculation
        all_student_submitted = defaultdict(set)
        for filepath in all_files:
            parsed = parse_filename(filepath.name)
            student_info = _find_in_roster(roster, parsed)
            if student_info:
                sname = student_info.get('student_name', '')
                raw_part = parsed.get('assignment_part', '') or 'Assignment'
                if sname:
                    normalized = _normalize_submission_name(raw_part)
                    matched = _match_to_config_title(normalized, all_config_names)
                    canonical = alias_to_title.get(matched, matched)
                    # Only count files that match a saved assignment config
                    if canonical in all_assignment_titles:
                        all_student_submitted[sname].add(canonical)

        # Add ALL roster students not already in students_map — includes
        # students with zero files AND those whose files are all confirmed
        for name, val in _unique_roster_students(roster, period_filter):
            if student_filter and name != student_filter:
                continue
            if name not in students_map:
                students_map[name] = {
                    'first_name': val.get('first_name', 'Student'),
                    'email': val.get('email', ''),
                    'student_id': val.get('student_id', ''),
                    'assignments': [],
                    'filenames': [],
                }

        if not students_map:
            return jsonify({"error": "No pending confirmations"}), 400

        # Load parent contacts if CC parents requested
        parent_contacts = {}
        if cc_parents:
            contacts_path = os.path.expanduser("~/.graider_data/parent_contacts.json")
            if os.path.exists(contacts_path):
                try:
                    with open(contacts_path, 'r') as fh:
                        parent_contacts = json.load(fh)
                except Exception:
                    pass

        # Build one confirmation email per student
        emails = []
        for name, info in students_map.items():
            submitted = sorted(set(info['assignments']))
            # Outstanding = all assignment configs minus everything this student submitted
            all_submitted = all_student_submitted.get(name, set())
            outstanding = sorted(all_assignment_titles - all_submitted)

            subject = "Submission Confirmation \u2014 " + name

            first_name_only = info['first_name'].split()[0] if info.get('first_name') else 'Student'
            # Always show the full submitted list (new + previously confirmed)
            all_confirmed_list = sorted(all_submitted)

            body = "Hi " + first_name_only + ",\n\n"
            if all_confirmed_list:
                body += "Here are the assignments you've submitted so far:\n\n"
                for a in all_confirmed_list:
                    body += "\u2713 " + a + "\n"
            else:
                body += "No submissions have been received yet.\n"

            if outstanding:
                body += "\nHere are your outstanding assignments that are still due:\n\n"
                for title in outstanding:
                    body += "\u2022 " + title + "\n"
            elif all_confirmed_list:
                body += "\nAll assignments have been received. Great job!\n"

            body += ""

            cc_email = ""
            if cc_parents and info.get('student_id'):
                contact = parent_contacts.get(str(info['student_id']), {})
                parent_emails = contact.get('parent_emails', [])
                if parent_emails:
                    cc_email = parent_emails[0]

            emails.append({
                "to": info['email'],
                "cc": cc_email,
                "subject": subject,
                "body": body,
                "student_name": name,
            })
            sent_filenames.extend(info['filenames'])

        if not emails:
            return jsonify({"error": "No emails to send"}), 400

        from flask import g
        teacher_id = getattr(g, 'user_id', 'local-dev')
        result = launch_outlook_sender(emails, teacher_id=teacher_id)
        if "error" in result:
            return jsonify(result), 409

        result["sent_filenames"] = sent_filenames
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


CONFIRMATIONS_FILE = os.path.expanduser("~/.graider_data/confirmations_sent.json")


@email_bp.route('/api/pending-confirmations', methods=['POST'])
def pending_confirmations():
    """Count how many files in the assignments folder need confirmation emails.

    Scans the folder, matches to roster, excludes already-confirmed files.
    Called on-demand (not polled) since it requires folder scan + roster load.
    """
    try:
        from pathlib import Path

        data = request.json or {}
        assignments_folder = data.get('assignments_folder', '')
        period_filter = data.get('period_filter', '')
        student_filter = data.get('student_filter', '')

        if not assignments_folder or not os.path.exists(assignments_folder):
            return jsonify({"count": 0, "students": []})

        try:
            from assignment_grader import build_roster_from_periods, parse_filename
        except ImportError:
            from backend.assignment_grader import build_roster_from_periods, parse_filename

        roster = build_roster_from_periods()
        if not roster:
            return jsonify({"count": 0, "students": []})

        # Load confirmed filenames
        confirmed_filenames = _load_confirmed_filenames()
        from backend.routes.grading_routes import grading_state, grading_lock
        if grading_state and grading_state.get("results"):
            lock = grading_lock
            results = grading_state["results"] if not lock else None
            if lock:
                with lock:
                    results = list(grading_state["results"])
            for r in (results or []):
                if r.get('confirmation_sent'):
                    confirmed_filenames.add(r.get('filename', ''))

        # Scan folder — count unique students with pending (unconfirmed) files
        assignment_path = Path(assignments_folder)
        pending_students = set()
        students_with_files = set()
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.pdf']:
            for filepath in assignment_path.glob(ext):
                filename = filepath.name
                parsed = parse_filename(filename)
                student_info = _find_in_roster(roster, parsed)
                if not student_info:
                    continue
                email = student_info.get('email', '')
                if not email or '@' not in email:
                    continue
                if period_filter and student_info.get('period', '') != period_filter:
                    continue
                student_name = student_info.get('student_name', '')
                students_with_files.add(student_name)
                if filename not in confirmed_filenames:
                    pending_students.add(student_name)

        # Include ALL roster students — those with no files, and those
        # whose files are all confirmed, so the full class list appears
        for name, val in _unique_roster_students(roster, period_filter):
            pending_students.add(name)

        # Apply student filter for count only (student list always shows all)
        if student_filter:
            count = 1 if student_filter in pending_students else 0
        else:
            count = len(pending_students)

        return jsonify({"count": count, "students": sorted(pending_students)})

    except Exception as e:
        return jsonify({"count": 0, "students": [], "error": str(e)})


def _load_confirmed_filenames():
    """Load set of filenames that have had confirmations sent."""
    if os.path.exists(CONFIRMATIONS_FILE):
        try:
            with open(CONFIRMATIONS_FILE, 'r') as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_confirmed_filenames(filenames_set):
    """Persist confirmed filenames to disk."""
    os.makedirs(os.path.dirname(CONFIRMATIONS_FILE), exist_ok=True)
    try:
        with open(CONFIRMATIONS_FILE, 'w') as f:
            json.dump(sorted(filenames_set), f, indent=2)
    except Exception as e:
        print(f"Error saving confirmations file: {e}")


@email_bp.route('/api/mark-confirmations-sent-file', methods=['POST'])
def mark_confirmations_sent_file():
    """Mark files as confirmation_sent after Outlook send completes.

    Takes filenames array, marks them in:
    1. grading_state results (for graded files) + persists to results.json
    2. confirmations_sent.json (for all files, graded or not)
    """
    try:
        data = request.json or {}
        filenames = set(data.get('filenames', []))

        if not filenames:
            return jsonify({"error": "No filenames provided"}), 400

        # Update grading_state for graded results
        from backend.routes.grading_routes import grading_state, grading_lock

        updated = 0
        if grading_state and grading_state.get("results"):
            lock = grading_lock
            results = grading_state["results"]
            if lock:
                with lock:
                    for r in results:
                        if r.get('filename') in filenames:
                            r['confirmation_sent'] = True
                            updated += 1
            else:
                for r in results:
                    if r.get('filename') in filenames:
                        r['confirmation_sent'] = True
                        updated += 1

            # Persist grading results
            try:
                with open(RESULTS_FILE, 'w') as f:
                    json.dump(results, f, indent=2)
            except Exception as e:
                print(f"Error saving results after marking confirmations: {e}")

        # Also persist to dedicated confirmations file (covers ungraded files)
        confirmed = _load_confirmed_filenames()
        confirmed.update(filenames)
        _save_confirmed_filenames(confirmed)

        return jsonify({"status": "ok", "updated": updated, "total_confirmed": len(confirmed)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ══════════════════════════════════════════════════════════════
# FOCUS SIS COMMUNICATIONS (Email + SMS via browser automation)
# ══════════════════════════════════════════════════════════════

FOCUS_COMMS_SCRIPT = os.path.join(
    os.path.expanduser("~/Downloads/Graider-Focus-Comms"),
    "focus-comms.js",
)

_focus_comms_state = {
    "process": None,
    "status": "idle",      # idle | running | done | error
    "sent": 0,
    "failed": 0,
    "skipped": 0,
    "total": 0,
    "message": "",
    "log": [],
}


def launch_focus_comms(messages, teacher_id='local-dev'):
    """Write messages to temp file and spawn the Focus Communications script.

    Args:
        messages: list of dicts with keys: student_name, subject, email_body, sms_body, cc_emails
        teacher_id: teacher identifier for credential lookup

    Returns:
        dict with status and total count, or error
    """
    if _focus_comms_state.get("status") == "running":
        return {"error": "Focus Comms already running. Check status or wait."}

    if not messages:
        return {"error": "No messages to send"}

    # Write per-teacher creds to temp file for subprocess access
    from backend.routes.assistant_routes import write_temp_creds_file
    if not write_temp_creds_file(teacher_id):
        return {"error": "VPortal credentials not configured. Go to Settings > Tools to set them up."}

    if not os.path.exists(FOCUS_COMMS_SCRIPT):
        return {"error": "focus-comms.js not found at " + FOCUS_COMMS_SCRIPT}

    tmp_file = os.path.join(GRAIDER_DATA_DIR, "tmp_focus_comms.json")
    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
    with open(tmp_file, 'w') as f:
        json.dump({"messages": messages}, f)

    _focus_comms_state.update({
        "status": "running",
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "total": len(messages),
        "message": "Starting Focus Communications...",
        "log": [],
    })

    proc = subprocess.Popen(
        ["node", FOCUS_COMMS_SCRIPT, "--screenshot", tmp_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    _focus_comms_state["process"] = proc

    thread = threading.Thread(target=_read_focus_comms_output, args=(proc,), daemon=True)
    thread.start()

    return {"status": "started", "total": len(messages)}


def _read_focus_comms_output(proc):
    """Background thread: read focus-comms.js NDJSON stdout and update state."""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            etype = event.get("type", "")
            if etype == "progress":
                _focus_comms_state["sent"] = event.get("current", 0)
                _focus_comms_state["total"] = event.get("total", _focus_comms_state["total"])
                _focus_comms_state["message"] = event.get("message", "")
            elif etype == "status":
                _focus_comms_state["message"] = event.get("message", "")
            elif etype == "done":
                _focus_comms_state["status"] = "done"
                _focus_comms_state["sent"] = event.get("sent", 0)
                _focus_comms_state["failed"] = event.get("failed", 0)
                _focus_comms_state["skipped"] = event.get("skipped", 0)
                _focus_comms_state["message"] = "Complete"
            elif etype == "error":
                _focus_comms_state["failed"] += 1
                _focus_comms_state["message"] = event.get("message", "")
            _focus_comms_state["log"].append(event)
            if len(_focus_comms_state["log"]) > 100:
                _focus_comms_state["log"] = _focus_comms_state["log"][-50:]
        except json.JSONDecodeError:
            pass

    # Read stderr for crash diagnostics
    stderr_output = ""
    try:
        stderr_output = proc.stderr.read().strip()
    except Exception:
        pass

    proc.wait()

    if _focus_comms_state["status"] == "running":
        _focus_comms_state["status"] = "error" if stderr_output else "done"
        if stderr_output:
            # Extract the key error line (e.g. "browserType.launchPersistentContext: ...")
            err_lines = [l for l in stderr_output.split('\n') if l.strip() and not l.strip().startswith('at ')]
            err_msg = err_lines[0] if err_lines else stderr_output[:200]
            _focus_comms_state["message"] = "Script error: " + err_msg
            _focus_comms_state["log"].append({"type": "error", "message": err_msg})


@email_bp.route('/api/send-focus-comms', methods=['POST'])
def send_focus_comms():
    """Start sending messages via Focus SIS Communications."""
    try:
        data = request.json or {}
        messages = data.get("messages", [])

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        from flask import g
        teacher_id = getattr(g, 'user_id', 'local-dev')
        result = launch_focus_comms(messages, teacher_id=teacher_id)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@email_bp.route('/api/focus-comms/status')
def focus_comms_status():
    """Get current Focus Communications sending progress."""
    return jsonify({
        "status": _focus_comms_state.get("status", "idle"),
        "sent": _focus_comms_state.get("sent", 0),
        "failed": _focus_comms_state.get("failed", 0),
        "skipped": _focus_comms_state.get("skipped", 0),
        "total": _focus_comms_state.get("total", 0),
        "message": _focus_comms_state.get("message", ""),
    })


@email_bp.route('/api/focus-comms/stop', methods=['POST'])
def focus_comms_stop():
    """Kill the Focus Communications subprocess if running."""
    proc = _focus_comms_state.get("process")
    if proc and proc.poll() is None:
        proc.kill()
        _focus_comms_state["status"] = "done"
        _focus_comms_state["message"] = "Stopped by user"
        return jsonify({"status": "stopped"})
    return jsonify({"status": "not_running"})


@email_bp.route('/api/confirm-send', methods=['POST'])
def confirm_send():
    """Execute a confirmed send action from the assistant preview.

    Accepts payload from POST body (preferred) or reads from pending_send.json file.
    Called by the frontend 'Send Now' button or by the confirm_and_send tool.
    """
    pending = None
    pending_path = os.path.join(GRAIDER_DATA_DIR, "pending_send.json")

    # Try POST body first (sent by frontend Send Now button)
    body = request.get_json(silent=True) or {}
    if body.get("action"):
        pending = body

    # Fall back to pending file
    if not pending and os.path.exists(pending_path):
        try:
            with open(pending_path, 'r') as f:
                pending = json.load(f)
        except Exception as e:
            return jsonify({"error": "Failed to read pending send: " + str(e)})

    if not pending:
        return jsonify({"error": "No pending send. Generate a preview first."})

    # Clean up file if it exists (prevent double-send)
    try:
        if os.path.exists(pending_path):
            os.remove(pending_path)
    except Exception:
        pass

    action = pending.get("action")
    from flask import g
    teacher_id = getattr(g, 'user_id', 'local-dev')

    if action == "send_focus_comms":
        messages = pending.get("messages", [])
        if not messages:
            return jsonify({"error": "No messages in pending payload"})
        result = launch_focus_comms(messages, teacher_id=teacher_id)
        return jsonify(result)

    elif action == "send_parent_emails":
        emails = pending.get("emails", [])
        if not emails:
            return jsonify({"error": "No emails in pending payload"})
        result = launch_outlook_sender(emails, teacher_id=teacher_id)
        return jsonify(result)

    else:
        return jsonify({"error": f"Unknown pending action: {action}"})
