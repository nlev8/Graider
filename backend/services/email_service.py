#!/usr/bin/env python3
"""
Graider - Email Sender
======================
Send grade feedback emails to students via Gmail SMTP.

Setup:
1. Create Gmail App Password at https://myaccount.google.com/apppasswords
2. Run: python3 email_sender.py --setup
3. Use: python3 email_sender.py --send-all (after grading)
"""

import os
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


class GraiderEmailer:
    """Send grade feedback emails via Gmail."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser("~/.graider_email_config.json")
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_config(self, gmail_address: str, app_password: str, teacher_name: str = "Mr. Crionas"):
        """Save email configuration."""
        # Clean app password - remove ALL whitespace and special characters
        clean_password = ''.join(c for c in app_password if c.isalnum())
        
        self.config = {
            "gmail_address": gmail_address.strip(),
            "app_password": clean_password,
            "teacher_name": teacher_name,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587
        }
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        os.chmod(self.config_path, 0o600)
        print("✅ Email configuration saved!")
    
    def send_email(self, to_email: str, student_name: str, subject: str, body: str) -> bool:
        """
        Send a single email.
        
        Returns True if successful.
        """
        if not self.config.get('gmail_address') or not self.config.get('app_password'):
            print("❌ Email not configured. Run --setup first.")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = f"Graider <{self.config['gmail_address']}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = self.config['gmail_address']
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            context = ssl.create_default_context()
            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls(context=context)
                server.login(self.config['gmail_address'], self.config['app_password'])
                server.send_message(msg)
            
            print(f"  ✅ Sent to {student_name} ({to_email})")
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to send to {to_email}: {e}")
            return False
    
    def send_grade_email(self, student_info: dict, grade_result: dict, assignment_name: str) -> bool:
        """
        Send a grade feedback email to a student.
        
        Args:
            student_info: Dict with student_name, first_name, email
            grade_result: Dict with score, letter_grade, feedback
            assignment_name: Name of the assignment
        """
        email = student_info.get('email', '')
        if not email:
            print(f"  ⚠️  No email for {student_info.get('student_name', 'Unknown')}")
            return False
        
        first_name = student_info.get('first_name', 'Student').split()[0]
        teacher = self.config.get('teacher_name', 'Your Teacher')
        
        subject = f"Grade for {assignment_name}: {grade_result['letter_grade']}"
        
        body = f"""Hi {first_name},

Here is your grade and feedback for {assignment_name}:

GRADE: {grade_result['score']}/100 ({grade_result['letter_grade']})

FEEDBACK:
{grade_result.get('feedback', 'No feedback available.')}

If you have any questions about your grade, please see me during class.

{teacher}

---
This email was sent by Graider.
"""
        
        return self.send_email(email, first_name, subject, body)
    
    def send_bulk_grades(self, grades: list, assignment_name: str = None) -> dict:
        """
        Send grade emails to all students in the grades list.
        
        Args:
            grades: List of grade dicts (from grading run)
            assignment_name: Override assignment name
            
        Returns:
            Dict with sent/failed counts
        """
        print(f"\n📧 Sending {len(grades)} grade emails...")
        
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
            
            if self.send_grade_email(student_info, grade_result, assignment):
                sent += 1
            else:
                failed += 1
        
        print(f"\n📊 Email Summary:")
        print(f"   ✅ Sent: {sent}")
        print(f"   ❌ Failed: {failed}")
        print(f"   ⏭️  Skipped (no email): {skipped}")
        
        return {'sent': sent, 'failed': failed, 'skipped': skipped}
    
    def send_combined_emails(self, grades: list) -> dict:
        """
        Send one email per student with all their assignments combined.
        
        Args:
            grades: List of all grade dicts
            
        Returns:
            Dict with sent/failed counts
        """
        # Group by student
        from collections import defaultdict
        students = defaultdict(list)
        
        for grade in grades:
            email = grade.get('email', '')
            if email and grade.get('student_id') != 'UNKNOWN':
                students[email].append(grade)
        
        print(f"\n📧 Sending combined emails to {len(students)} students...")
        
        sent = 0
        failed = 0
        teacher = self.config.get('teacher_name', 'Your Teacher')
        
        for email, student_grades in students.items():
            first_name = student_grades[0].get('first_name', 'Student').split()[0]
            student_name = student_grades[0].get('student_name', 'Student')
            
            # Build subject
            if len(student_grades) == 1:
                assignment = student_grades[0].get('assignment', 'Assignment')
                subject = f"Grade for {assignment}: {student_grades[0]['letter_grade']}"
            else:
                subject = f"Grades for {len(student_grades)} Assignments"
            
            # Build body
            body = f"Hi {first_name},\n\n"
            
            if len(student_grades) == 1:
                g = student_grades[0]
                body += f"Here is your grade and feedback for {g.get('assignment', 'your assignment')}:\n\n"
                body += f"GRADE: {g['score']}/100 ({g['letter_grade']})\n\n"
                body += f"FEEDBACK:\n{g.get('feedback', 'No feedback available.')}\n"
            else:
                body += "Here are your grades and feedback:\n\n"
                for g in student_grades:
                    body += f"{'='*50}\n"
                    body += f"📝 {g.get('assignment', 'Assignment')}\n"
                    body += f"GRADE: {g['score']}/100 ({g['letter_grade']})\n\n"
                    body += f"FEEDBACK:\n{g.get('feedback', 'No feedback available.')}\n\n"
            
            body += f"\nIf you have any questions, please see me during class.\n\n{teacher}\n\n---\nThis email was sent by Graider."
            
            if self.send_email(email, student_name, subject, body):
                sent += 1
            else:
                failed += 1
        
        print(f"\n📊 Email Summary:")
        print(f"   ✅ Sent: {sent}")
        print(f"   ❌ Failed: {failed}")
        
        return {'sent': sent, 'failed': failed}
    
    def test_connection(self) -> bool:
        """Test the email configuration by sending a test email to yourself."""
        if not self.config.get('gmail_address'):
            print("❌ Not configured. Run --setup first.")
            return False
        
        print("📧 Sending test email...")
        
        return self.send_email(
            self.config['gmail_address'],
            "Test",
            "Graider Test Email",
            "If you received this, Graider email is working!\n\n✅ Configuration successful."
        )


# =============================================================================
# STANDALONE USAGE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Graider Email Sender")
    parser.add_argument("--setup", action="store_true", help="Configure email settings")
    parser.add_argument("--test", action="store_true", help="Send test email to yourself")
    
    args = parser.parse_args()
    
    emailer = GraiderEmailer()
    
    if args.setup:
        print("\n📧 Graider Email Setup\n")
        print("You need a Gmail App Password (not your regular password).")
        print("Get one at: https://myaccount.google.com/apppasswords\n")
        
        gmail = input("Gmail address [graider.app@gmail.com]: ").strip()
        if not gmail:
            gmail = "graider.app@gmail.com"
        
        app_password = input("App Password (16 characters, no spaces): ").strip()
        
        teacher = input("Teacher name [Mr. Crionas]: ").strip()
        if not teacher:
            teacher = "Mr. Crionas"
        
        emailer.save_config(gmail, app_password, teacher)
        
        print("\n🧪 Testing connection...")
        if emailer.test_connection():
            print("\n✅ Setup complete! Check your inbox for test email.")
        else:
            print("\n❌ Test failed. Check your app password.")
    
    elif args.test:
        emailer.test_connection()
    
    else:
        parser.print_help()
