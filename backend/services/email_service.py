#!/usr/bin/env python3
"""
Graider - Email Service
=======================
Send grade feedback emails to students via Resend API.

Setup:
1. Add RESEND_API_KEY to .env file
2. Verify your domain at https://resend.com/domains
3. Emails will be sent from noreply@graider.live
"""

import os
import json
from pathlib import Path

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    print("Warning: resend package not installed. Run: pip install resend")


class GraiderEmailer:
    """Send grade feedback emails via Resend API."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser("~/.graider_email_config.json")
        self.config = self._load_config()
        self._init_resend()

    def _init_resend(self):
        """Initialize Resend with API key from environment."""
        if not RESEND_AVAILABLE:
            return

        # Try to load from .env
        api_key = os.getenv('RESEND_API_KEY')

        if not api_key:
            # Try to load from .env file directly
            env_paths = [
                Path(__file__).parent.parent.parent / '.env',
                Path.cwd() / '.env',
            ]
            for env_path in env_paths:
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        if line.startswith('RESEND_API_KEY='):
                            api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                            break
                if api_key:
                    break

        if api_key:
            resend.api_key = api_key
            self.resend_available = True
            self.from_email = os.getenv('RESEND_FROM_EMAIL', 'Graider <noreply@graider.live>')
        else:
            self.resend_available = False

    def _load_config(self) -> dict:
        """Load email configuration."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}

    def save_config(self, teacher_name: str = "Your Teacher", teacher_email: str = ""):
        """Save email configuration (teacher name for signatures)."""
        self.config = {
            "teacher_name": teacher_name,
            "teacher_email": teacher_email,  # For Reply-To
        }

        os.makedirs(os.path.dirname(self.config_path) or '.', exist_ok=True)

        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        os.chmod(self.config_path, 0o600)
        print("Email configuration saved!")

    def send_email(self, to_email: str, student_name: str, subject: str, body: str,
                   reply_to: str = None) -> bool:
        """
        Send a single email via Resend.

        Args:
            to_email: Recipient email address
            student_name: Student's name (for logging)
            subject: Email subject
            body: Email body (plain text)
            reply_to: Optional reply-to address (teacher's email)

        Returns:
            True if successful
        """
        if not RESEND_AVAILABLE:
            print("Resend package not installed. Run: pip install resend")
            return False

        if not self.resend_available:
            print("Resend API key not configured. Add RESEND_API_KEY to .env")
            return False

        try:
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "text": body,
            }

            # Add reply-to if provided (teacher's email)
            if reply_to:
                params["reply_to"] = reply_to
            elif self.config.get('teacher_email'):
                params["reply_to"] = self.config.get('teacher_email')

            response = resend.Emails.send(params)

            if response and response.get('id'):
                print(f"  Sent to {student_name} ({to_email})")
                return True
            else:
                print(f"  Failed to send to {to_email}: No response ID")
                return False

        except Exception as e:
            print(f"  Failed to send to {to_email}: {e}")
            return False

    def send_grade_email(self, student_info: dict, grade_result: dict,
                         assignment_name: str, reply_to: str = None) -> bool:
        """
        Send a grade feedback email to a student.

        Args:
            student_info: Dict with student_name, first_name, email
            grade_result: Dict with score, letter_grade, feedback
            assignment_name: Name of the assignment
            reply_to: Teacher's email for replies
        """
        email = student_info.get('email', '')
        if not email:
            print(f"  No email for {student_info.get('student_name', 'Unknown')}")
            return False

        first_name = student_info.get('first_name', 'Student').split()[0]
        teacher = self.config.get('teacher_name', 'Your Teacher')

        subject = f"Grade for {assignment_name}: {grade_result['letter_grade']}"

        body = f"""Hi {first_name},

Here is your grade and feedback for {assignment_name}:

{'=' * 40}
GRADE: {grade_result['score']}/100 ({grade_result['letter_grade']})
{'=' * 40}

FEEDBACK:
{grade_result.get('feedback', 'No feedback available.')}

If you have any questions about your grade, please see me during class.

{teacher}

---
This email was sent by Graider (https://graider.live)
"""

        return self.send_email(email, first_name, subject, body, reply_to)

    def send_bulk_grades(self, grades: list, assignment_name: str = None,
                         reply_to: str = None) -> dict:
        """
        Send grade emails to all students in the grades list.

        Args:
            grades: List of grade dicts (from grading run)
            assignment_name: Override assignment name
            reply_to: Teacher's email for replies

        Returns:
            Dict with sent/failed/skipped counts
        """
        print(f"\nSending {len(grades)} grade emails...")

        sent = 0
        failed = 0
        skipped = 0

        for grade in grades:
            email = grade.get('email', '')

            if not email:
                skipped += 1
                continue

            if grade.get('student_id') == 'UNKNOWN':
                skipped += 1
                continue

            student_info = {
                'student_name': grade.get('student_name', 'Student'),
                'first_name': grade.get('first_name', grade.get('student_name', 'Student')),
                'email': email
            }

            grade_result = {
                'score': grade.get('score', 0),
                'letter_grade': grade.get('letter_grade', 'N/A'),
                'feedback': grade.get('feedback', '')
            }

            assignment = assignment_name or grade.get('assignment', 'Assignment')

            if self.send_grade_email(student_info, grade_result, assignment, reply_to):
                sent += 1
            else:
                failed += 1

        print(f"\nEmail Summary:")
        print(f"   Sent: {sent}")
        print(f"   Failed: {failed}")
        print(f"   Skipped (no email): {skipped}")

        return {'sent': sent, 'failed': failed, 'skipped': skipped}

    def test_connection(self, test_email: str = None) -> bool:
        """Test the email configuration by sending a test email."""
        if not RESEND_AVAILABLE:
            print("Resend package not installed.")
            return False

        if not self.resend_available:
            print("Resend API key not configured.")
            return False

        # Send to provided email or a test address
        to_email = test_email or "delivered@resend.dev"

        print(f"Sending test email to {to_email}...")

        return self.send_email(
            to_email,
            "Test",
            "Graider Test Email",
            "If you received this, Graider email is working!\n\nConfiguration successful.\n\n- Graider Team"
        )


# =============================================================================
# STANDALONE USAGE
# =============================================================================

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    # Load environment
    load_dotenv()

    parser = argparse.ArgumentParser(description="Graider Email Service")
    parser.add_argument("--test", type=str, nargs='?', const='delivered@resend.dev',
                        help="Send test email (optionally provide email address)")
    parser.add_argument("--setup", action="store_true", help="Configure teacher settings")

    args = parser.parse_args()

    emailer = GraiderEmailer()

    if args.setup:
        print("\nGraider Email Setup\n")
        print("Emails will be sent from: noreply@graider.live")
        print("Students can reply to your email address.\n")

        teacher = input("Your name (for email signature) [Your Teacher]: ").strip()
        if not teacher:
            teacher = "Your Teacher"

        teacher_email = input("Your email (for student replies): ").strip()

        emailer.save_config(teacher, teacher_email)
        print("\nConfiguration saved!")

    elif args.test:
        if emailer.test_connection(args.test):
            print("\nTest email sent successfully!")
        else:
            print("\nTest failed. Check your RESEND_API_KEY in .env")

    else:
        parser.print_help()
