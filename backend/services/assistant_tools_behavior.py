"""
Behavior Tracking Tools
========================
Assistant tools for querying behavior data, generating behavior emails,
and sending them via Resend or Focus portal automation.
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

from backend.services.assistant_tools import (
    _load_roster, _fuzzy_name_match, _normalize_period,
    _extract_first_name, PARENT_CONTACTS_FILE,
)

# ═══════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
BEHAVIOR_FILE = os.path.join(GRAIDER_DATA_DIR, "behavior_tracking.json")
SETTINGS_FILE = os.path.expanduser("~/.graider_global_settings.json")


def _load_behavior_data():
    if not os.path.exists(BEHAVIOR_FILE):
        return {"version": 1, "students": {}}
    try:
        with open(BEHAVIOR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"version": 1, "students": {}}


def _load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _load_parent_contacts():
    if not os.path.exists(PARENT_CONTACTS_FILE):
        return []
    try:
        with open(PARENT_CONTACTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

BEHAVIOR_TOOL_DEFINITIONS = [
    {
        "name": "get_behavior_summary",
        "description": "Get a behavior summary for a student or class period. Shows correction and praise counts, dates, notes, and trends. Use when the teacher asks 'how has [student] behaved?' or 'show behavior data for Period 3'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (fuzzy match). Omit for full period/class view."
                },
                "period": {
                    "type": "string",
                    "description": "Period filter (e.g. 'Period 3'). Optional."
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 7, max 90)"
                }
            }
        }
    },
    {
        "name": "generate_behavior_email",
        "description": "Generate a professional behavior email to a student's parents. Includes correction counts, specific dates, teacher notes, and a constructive tone. Returns the draft for review before sending.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (required, fuzzy match)"
                },
                "tone": {
                    "type": "string",
                    "enum": ["concern", "positive", "followup"],
                    "description": "Email tone: 'concern' for behavior issues, 'positive' for praise, 'followup' for checking in after prior contact. Default: auto-detect from data."
                },
                "custom_note": {
                    "type": "string",
                    "description": "Optional additional note to include in the email"
                }
            },
            "required": ["student_name"]
        }
    },
    {
        "name": "send_behavior_email",
        "description": "Send a behavior email to a student's parents. Requires a draft from generate_behavior_email. Supports two methods: 'email' (Resend API) or 'focus' (generates Playwright workflow for Focus portal messaging).",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (required)"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Email body text (from generate_behavior_email draft)"
                },
                "method": {
                    "type": "string",
                    "enum": ["email", "focus"],
                    "description": "Send method: 'email' via Resend API, 'focus' via Focus portal automation. Default: email."
                }
            },
            "required": ["student_name", "subject", "body"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# IMPLEMENTATION
# ═══════════════════════════════════════════════════════

def get_behavior_summary(student_name=None, period=None, days=7):
    """Get behavior summary for a student or period."""
    behavior = _load_behavior_data()
    students_data = behavior.get("students", {})

    if not students_data:
        return {"status": "success", "data": "No behavior data recorded yet. Start a behavior tracking session in the Assistant tab to begin logging."}

    days = min(max(days or 7, 1), 90)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    period_filter = _normalize_period(period) if period else None

    # If student name provided, find matching student(s)
    if student_name:
        matches = []
        for sid, sdata in students_data.items():
            if _fuzzy_name_match(student_name, sdata.get("name", "")):
                matches.append((sid, sdata))

        if not matches:
            return {"error": f"No behavior data found for '{student_name}'. Check the name or start tracking."}

        results = []
        for sid, sdata in matches:
            entries = sdata.get("entries", [])
            filtered = [e for e in entries if e.get("date", "") >= cutoff]
            if period_filter:
                filtered = [e for e in filtered if _normalize_period(e.get("period", "")) == period_filter]

            corrections = sum(e.get("count", 0) for e in filtered if e.get("type") == "correction")
            praise = sum(e.get("count", 0) for e in filtered if e.get("type") == "praise")

            # Collect all notes
            all_notes = []
            for e in filtered:
                for note in e.get("notes", []):
                    if note:
                        all_notes.append({"date": e.get("date", ""), "note": note, "type": e.get("type", "")})

            # Day-by-day breakdown
            daily = defaultdict(lambda: {"corrections": 0, "praise": 0})
            for e in filtered:
                d = e.get("date", "unknown")
                if e.get("type") == "correction":
                    daily[d]["corrections"] += e.get("count", 0)
                else:
                    daily[d]["praise"] += e.get("count", 0)

            results.append({
                "name": sdata.get("name", ""),
                "period_range": f"Last {days} days",
                "total_corrections": corrections,
                "total_praise": praise,
                "notes": all_notes[-10:],  # Last 10 notes
                "daily_breakdown": dict(sorted(daily.items())),
            })

        return {"status": "success", "data": results}

    # No student name — show class/period overview
    overview = []
    for sid, sdata in students_data.items():
        entries = sdata.get("entries", [])
        filtered = [e for e in entries if e.get("date", "") >= cutoff]
        if period_filter:
            filtered = [e for e in filtered if _normalize_period(e.get("period", "")) == period_filter]

        if not filtered:
            continue

        corrections = sum(e.get("count", 0) for e in filtered if e.get("type") == "correction")
        praise = sum(e.get("count", 0) for e in filtered if e.get("type") == "praise")

        overview.append({
            "name": sdata.get("name", ""),
            "corrections": corrections,
            "praise": praise,
            "last_date": max(e.get("date", "") for e in filtered),
        })

    # Sort by most corrections first
    overview.sort(key=lambda x: -x["corrections"])

    return {
        "status": "success",
        "data": {
            "period_range": f"Last {days} days",
            "period_filter": period or "All",
            "students": overview,
            "total_students_tracked": len(overview),
        }
    }


def generate_behavior_email(student_name, tone=None, custom_note=None):
    """Generate a professional behavior email draft."""
    behavior = _load_behavior_data()
    students_data = behavior.get("students", {})

    # Find student
    match = None
    for sid, sdata in students_data.items():
        if _fuzzy_name_match(student_name, sdata.get("name", "")):
            match = sdata
            break

    if not match:
        return {"error": f"No behavior data found for '{student_name}'."}

    # Load teacher settings for signature
    settings = _load_settings()
    config = settings.get('config', {})
    teacher_name = config.get('teacher_name', 'Your Teacher')
    subject_area = config.get('subject', '')
    school_name = config.get('school_name', '')
    email_signature = config.get('email_signature', '')

    name = match.get("name", student_name)
    first_name = _extract_first_name(name)
    entries = match.get("entries", [])

    # Recent entries (last 14 days)
    cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    recent = [e for e in entries if e.get("date", "") >= cutoff]

    corrections = sum(e.get("count", 0) for e in recent if e.get("type") == "correction")
    praise = sum(e.get("count", 0) for e in recent if e.get("type") == "praise")

    # Collect notes
    correction_notes = []
    praise_notes = []
    for e in recent:
        for note in e.get("notes", []):
            if note:
                if e.get("type") == "correction":
                    correction_notes.append(note)
                else:
                    praise_notes.append(note)

    # Get dates of corrections
    correction_dates = sorted(set(e.get("date", "") for e in recent if e.get("type") == "correction"))

    # Auto-detect tone
    if not tone:
        if corrections > praise and corrections >= 3:
            tone = "concern"
        elif praise > corrections:
            tone = "positive"
        else:
            tone = "concern"

    # Look up parent contact
    contacts = _load_parent_contacts()
    parent_email = ""
    parent_name = ""
    for contact in contacts:
        if _fuzzy_name_match(name, contact.get("student_name", "")):
            parent_email = contact.get("parent_email", "") or contact.get("email", "")
            parent_name = contact.get("parent_name", "") or contact.get("contact_name", "")
            break

    # Also check roster for parent info
    if not parent_email:
        roster = _load_roster()
        for s in roster:
            if _fuzzy_name_match(name, s.get("name", "")):
                parent_email = s.get("parent_email", "") or s.get("guardian_email", "")
                parent_name = s.get("parent_name", "") or s.get("guardian_name", "")
                break

    parent_greeting = f"Dear {parent_name}" if parent_name else f"Dear Parent/Guardian of {first_name}"

    # Build email based on tone
    if tone == "positive":
        email_subject = f"Positive Behavior Update - {first_name}"
        lines = [
            f"{parent_greeting},",
            "",
            f"I wanted to reach out with a positive update about {first_name}'s behavior in {subject_area + ' ' if subject_area else ''}class.",
            "",
        ]
        if praise > 0:
            lines.append(f"Over the past two weeks, {first_name} has received {praise} positive recognition(s) for good behavior.")
        if praise_notes:
            lines.append("Specifically noted: " + "; ".join(praise_notes[:5]) + ".")
        lines.extend([
            "",
            f"It's great to see {first_name} making positive contributions to our classroom. Please let {first_name} know how proud we are!",
        ])
    elif tone == "followup":
        email_subject = f"Behavior Follow-Up - {first_name}"
        lines = [
            f"{parent_greeting},",
            "",
            f"I'm following up on {first_name}'s behavior in {subject_area + ' ' if subject_area else ''}class.",
            "",
        ]
        if corrections > 0:
            lines.append(f"Since our last communication, {first_name} has had {corrections} correction(s).")
        if praise > 0:
            lines.append(f"{first_name} has also received {praise} positive recognition(s), which is encouraging.")
        lines.extend([
            "",
            "I'd like to continue working together to support improvement. Please don't hesitate to reach out if you have questions.",
        ])
    else:  # concern
        email_subject = f"Behavior Update - {first_name}"
        lines = [
            f"{parent_greeting},",
            "",
            f"I'm reaching out regarding {first_name}'s behavior in {subject_area + ' ' if subject_area else ''}class. I want to partner with you to help {first_name} succeed.",
            "",
        ]
        if corrections > 0:
            lines.append(f"Over the past two weeks, {first_name} has needed {corrections} correction(s) during class.")
        if correction_dates:
            lines.append(f"Dates: {', '.join(correction_dates)}.")
        if correction_notes:
            lines.append(f"Areas of concern: {'; '.join(correction_notes[:5])}.")
        if praise > 0:
            lines.extend([
                "",
                f"I also want to note that {first_name} has received {praise} positive recognition(s) during this period, which shows potential for improvement.",
            ])
        lines.extend([
            "",
            "I believe that with consistent support at home and school, we can help turn this around. I'd appreciate it if you could discuss this with " + first_name + ".",
            "",
            "Please feel free to contact me if you'd like to schedule a conference or discuss strategies.",
        ])

    if custom_note:
        lines.extend(["", custom_note])

    # Add signature
    lines.extend([
        "",
        "Thank you for your support,",
    ])
    if email_signature:
        lines.append(email_signature)
    else:
        lines.append(teacher_name)
        if school_name:
            lines.append(school_name)

    body = "\n".join(lines)

    return {
        "status": "success",
        "data": {
            "subject": email_subject,
            "body": body,
            "to_email": parent_email,
            "parent_name": parent_name,
            "student_name": name,
            "tone": tone,
            "corrections": corrections,
            "praise": praise,
            "note": "Review the draft above. Ask me to send it when ready, or request changes.",
        }
    }


def send_behavior_email(student_name, subject, body, method="email"):
    """Send a behavior email via Resend or Focus automation."""
    if method == "focus":
        # Generate a Playwright automation workflow for Focus messaging
        return {
            "status": "success",
            "data": {
                "method": "focus",
                "message": "To send via Focus, use the 'create an automation' command with these details. Say: 'Create an automation to send a message in Focus to " + student_name + "'s parents with this subject and body.'",
                "subject": subject,
                "body": body,
                "student_name": student_name,
            }
        }

    # Email method via Resend
    try:
        from backend.services.email_service import EmailService
        email_svc = EmailService()

        if not email_svc.resend_available:
            return {"error": "Email not configured. Add RESEND_API_KEY to .env file."}

        # Find parent email
        contacts = _load_parent_contacts()
        parent_email = ""
        for contact in contacts:
            if _fuzzy_name_match(student_name, contact.get("student_name", "")):
                parent_email = contact.get("parent_email", "") or contact.get("email", "")
                break

        if not parent_email:
            roster = _load_roster()
            for s in roster:
                if _fuzzy_name_match(student_name, s.get("name", "")):
                    parent_email = s.get("parent_email", "") or s.get("guardian_email", "")
                    break

        if not parent_email:
            return {"error": f"No parent email found for '{student_name}'. Add parent contacts in the student roster or parent contacts file."}

        success = email_svc.send_email(
            to_email=parent_email,
            student_name=student_name,
            subject=subject,
            body=body,
        )

        if success:
            return {
                "status": "success",
                "data": {
                    "message": f"Email sent to {parent_email}",
                    "to": parent_email,
                    "subject": subject,
                }
            }
        else:
            return {"error": "Failed to send email. Check Resend configuration."}

    except Exception as e:
        return {"error": f"Email send error: {str(e)}"}


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

BEHAVIOR_TOOL_HANDLERS = {
    "get_behavior_summary": get_behavior_summary,
    "generate_behavior_email": generate_behavior_email,
    "send_behavior_email": send_behavior_email,
}
