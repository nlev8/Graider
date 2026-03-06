"""
Behavior Tracking Tools
========================
Assistant tools for querying behavior data, generating behavior emails,
and sending them via Resend or Focus portal automation.

Data source: Supabase (behavior_sessions + behavior_events tables).
"""
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

from flask import g

logger = logging.getLogger(__name__)

from backend.services.assistant_tools import (
    _load_roster, _fuzzy_name_match, _normalize_period,
    _extract_first_name, PARENT_CONTACTS_FILE,
)

# ═══════════════════════════════════════════════════════
# SUPABASE CLIENT (lazy, same pattern as routes)
# ═══════════════════════════════════════════════════════

_supabase = None
SETTINGS_FILE = os.path.expanduser("~/.graider_global_settings.json")


def _get_supabase():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Supabase credentials not configured")
        _supabase = create_client(url, key)
    return _supabase


def _get_teacher_id():
    """Get current teacher's UUID from Flask request context."""
    return getattr(g, 'user_id', None)


def _load_behavior_events(teacher_id, cutoff_date=None, period=None, student_name=None):
    """Query behavior events from Supabase and return them grouped by student.

    Returns dict shaped like the old JSON format for compatibility:
    {
        "student_key": {
            "name": "...",
            "entries": [ { date, period, type, count, notes, transcripts, timestamps } ]
        }
    }
    """
    sb = _get_supabase()

    logger.info("_load_behavior_events: teacher_id=%s cutoff=%s period=%s student=%s",
                teacher_id, cutoff_date, period, student_name)

    rows = []
    try:
        query = sb.table('behavior_events').select(
            'student_name, type, note, transcript, event_time, source, '
            'behavior_sessions!inner(period, date)'
        ).eq('teacher_id', teacher_id)

        if cutoff_date:
            query = query.gte('behavior_sessions.date', cutoff_date)
        if period:
            query = query.eq('behavior_sessions.period', period)

        res = query.execute()
        rows = res.data or []
        logger.info("_load_behavior_events: joined query returned %d rows", len(rows))
    except Exception as e:
        # Fallback: query without the session join if it fails
        logger.warning("_load_behavior_events: joined query failed (%s), trying fallback", e)
        try:
            query = sb.table('behavior_events').select(
                'student_name, type, note, transcript, event_time, source, session_id'
            ).eq('teacher_id', teacher_id)
            res = query.execute()
            fallback_rows = res.data or []
            logger.info("_load_behavior_events: fallback query returned %d rows", len(fallback_rows))

            # Fetch session data separately
            session_ids = list(set(r.get('session_id', '') for r in fallback_rows if r.get('session_id')))
            sessions_map = {}
            if session_ids:
                ses_res = sb.table('behavior_sessions').select('id, period, date').in_('id', session_ids).execute()
                for s in (ses_res.data or []):
                    sessions_map[s['id']] = {'period': s.get('period', ''), 'date': s.get('date', '')}

            for r in fallback_rows:
                sid = r.get('session_id', '')
                session_info = sessions_map.get(sid, {'period': '', 'date': ''})
                # Apply date/period filters
                if cutoff_date and session_info.get('date', '') < cutoff_date:
                    continue
                if period and session_info.get('period', '') != period:
                    continue
                r['behavior_sessions'] = session_info
                rows.append(r)
            logger.info("_load_behavior_events: after fallback filtering, %d rows", len(rows))
        except Exception as e2:
            logger.error("_load_behavior_events: fallback query also failed: %s", e2)

    # Filter by student name in Python (fuzzy match)
    if student_name:
        before_count = len(rows)
        rows = [r for r in rows if _fuzzy_name_match(student_name, r.get('student_name', ''))]
        logger.info("_load_behavior_events: fuzzy filter '%s' reduced %d -> %d rows",
                    student_name, before_count, len(rows))

    # Aggregate into legacy shape
    students = defaultdict(lambda: {"name": "", "entries_map": {}})

    for row in rows:
        name = row.get('student_name', '')
        sid = name.lower().replace(' ', '_')
        evt_type = row.get('type', 'correction')
        note = row.get('note', '')
        transcript = row.get('transcript', '')
        session = row.get('behavior_sessions', {})
        date_val = session.get('date', '')
        period_val = session.get('period', '')

        # Parse event_time for HH:MM
        event_time_str = row.get('event_time', '')
        timestamp = ''
        if event_time_str:
            try:
                dt = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                timestamp = dt.strftime('%H:%M')
            except Exception:
                pass

        student = students[sid]
        student["name"] = name

        entry_key = (date_val, period_val, evt_type)
        if entry_key not in student["entries_map"]:
            student["entries_map"][entry_key] = {
                "date": date_val,
                "period": period_val,
                "type": evt_type,
                "count": 0,
                "notes": [],
                "transcripts": [],
                "timestamps": [],
            }

        entry = student["entries_map"][entry_key]
        entry["count"] += 1
        if note and note not in entry["notes"]:
            entry["notes"].append(note)
        if transcript and transcript not in entry["transcripts"]:
            entry["transcripts"].append(transcript)
        if timestamp:
            entry["timestamps"].append(timestamp)

    # Convert entries_map to entries list
    result = {}
    for sid, sdata in students.items():
        result[sid] = {
            "name": sdata["name"],
            "entries": list(sdata["entries_map"].values()),
        }
    return result


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
        "description": "Send a behavior email to a student's parents. Requires a draft from generate_behavior_email. Supports two methods: 'email' (Resend API) or 'focus' (sends via Focus Communications portal using Playwright browser automation — opens browser, logs in, and sends through Focus SIS).",
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

def get_behavior_summary(student_name=None, period=None, days=7, teacher_id='local-dev'):
    """Get behavior summary for a student or period."""
    if not teacher_id or teacher_id == 'local-dev':
        teacher_id = _get_teacher_id() or teacher_id
    if not teacher_id:
        return {"error": "Not authenticated"}

    days = min(max(days or 7, 1), 90)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    period_filter = _normalize_period(period) if period else None

    # Query from Supabase
    students_data = _load_behavior_events(
        teacher_id=teacher_id,
        cutoff_date=cutoff,
        period=period_filter,
        student_name=student_name if student_name else None,
    )

    if not students_data:
        if student_name:
            hint = f" Try again with days=30 or days=90 for a wider window." if days <= 14 else ""
            return {"error": f"No behavior data found for '{student_name}' in the last {days} days.{hint} The student name must match what was recorded in the Companion app."}
        return {"status": "success", "data": "No behavior data recorded yet. Start a behavior tracking session in the Companion app to begin logging."}

    # If student name provided, return detailed view
    if student_name:
        results = []
        for sid, sdata in students_data.items():
            entries = sdata.get("entries", [])

            corrections = sum(e.get("count", 0) for e in entries if e.get("type") == "correction")
            praise = sum(e.get("count", 0) for e in entries if e.get("type") == "praise")

            # Collect all notes and transcripts
            all_notes = []
            all_transcripts = []
            for e in entries:
                for note in e.get("notes", []):
                    if note:
                        all_notes.append({"date": e.get("date", ""), "note": note, "type": e.get("type", "")})
                for t in e.get("transcripts", []):
                    if t:
                        all_transcripts.append({"date": e.get("date", ""), "transcript": t, "type": e.get("type", "")})

            # Day-by-day breakdown
            daily = defaultdict(lambda: {"corrections": 0, "praise": 0})
            for e in entries:
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
                "notes": all_notes[-10:],
                "recent_transcripts": all_transcripts[-10:],
                "daily_breakdown": dict(sorted(daily.items())),
            })

        return {"status": "success", "data": results}

    # No student name — show class/period overview
    overview = []
    for sid, sdata in students_data.items():
        entries = sdata.get("entries", [])
        if not entries:
            continue

        corrections = sum(e.get("count", 0) for e in entries if e.get("type") == "correction")
        praise = sum(e.get("count", 0) for e in entries if e.get("type") == "praise")

        overview.append({
            "name": sdata.get("name", ""),
            "corrections": corrections,
            "praise": praise,
            "last_date": max(e.get("date", "") for e in entries),
        })

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


def _gather_email_context(teacher_id, student_name):
    """Gather all behavior data and teacher settings needed for email generation."""
    cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')

    students_data = _load_behavior_events(
        teacher_id=teacher_id,
        cutoff_date=cutoff,
        student_name=student_name,
    )
    if not students_data:
        # Try wider window (30 days) before giving up
        logger.info("_gather_email_context: no data in 14 days, trying 30 days")
        cutoff_30 = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        students_data = _load_behavior_events(
            teacher_id=teacher_id,
            cutoff_date=cutoff_30,
            student_name=student_name,
        )
    if not students_data:
        logger.warning("_gather_email_context: no behavior data for '%s' teacher=%s", student_name, teacher_id)
        return None

    match = next(iter(students_data.values()))
    settings = _load_settings()
    config = settings.get('config', {})

    name = match.get("name", student_name)
    first_name = _extract_first_name(name)
    entries = match.get("entries", [])

    corrections = sum(e.get("count", 0) for e in entries if e.get("type") == "correction")
    praise = sum(e.get("count", 0) for e in entries if e.get("type") == "praise")

    # Collect notes and transcripts
    correction_notes, praise_notes = [], []
    all_transcripts = []
    for e in entries:
        for note in e.get("notes", []):
            if note:
                (correction_notes if e.get("type") == "correction" else praise_notes).append(note)
        for t in e.get("transcripts", []):
            if t:
                all_transcripts.append({"date": e.get("date", ""), "type": e.get("type", ""), "transcript": t})

    correction_dates = sorted(set(e.get("date", "") for e in entries if e.get("type") == "correction"))

    # Look up parent contact
    contacts = _load_parent_contacts()
    parent_email, parent_name = "", ""
    for contact in contacts:
        if _fuzzy_name_match(name, contact.get("student_name", "")):
            parent_email = contact.get("parent_email", "") or contact.get("email", "")
            parent_name = contact.get("parent_name", "") or contact.get("contact_name", "")
            break
    if not parent_email:
        roster = _load_roster()
        for s in roster:
            if _fuzzy_name_match(name, s.get("name", "")):
                parent_email = s.get("parent_email", "") or s.get("guardian_email", "")
                parent_name = s.get("parent_name", "") or s.get("guardian_name", "")
                break

    return {
        "name": name,
        "first_name": first_name,
        "corrections": corrections,
        "praise": praise,
        "correction_notes": correction_notes,
        "praise_notes": praise_notes,
        "correction_dates": correction_dates,
        "transcripts": all_transcripts[-15:],
        "parent_email": parent_email,
        "parent_name": parent_name,
        "teacher_name": config.get('teacher_name', 'Your Teacher'),
        "subject_area": config.get('subject', ''),
        "school_name": config.get('school_name', ''),
        "email_signature": config.get('email_signature', ''),
    }


def _generate_email_ai(ctx, tone, custom_note, teacher_id):
    """Generate email using Claude AI. Returns (subject, body) or None on failure."""
    try:
        from backend.api_keys import get_api_key
        import anthropic

        api_key = get_api_key('anthropic', teacher_id)
        if not api_key:
            return None

        # Build behavior data summary for the prompt
        behavior_lines = []
        behavior_lines.append(f"Student: {ctx['name']}")
        behavior_lines.append(f"Total corrections (last 14 days): {ctx['corrections']}")
        behavior_lines.append(f"Total praise (last 14 days): {ctx['praise']}")
        if ctx['correction_dates']:
            behavior_lines.append(f"Correction dates: {', '.join(ctx['correction_dates'])}")
        if ctx['correction_notes']:
            behavior_lines.append(f"Teacher notes (corrections): {'; '.join(ctx['correction_notes'][:8])}")
        if ctx['praise_notes']:
            behavior_lines.append(f"Teacher notes (praise): {'; '.join(ctx['praise_notes'][:5])}")
        if ctx['transcripts']:
            behavior_lines.append("Voice transcripts from class:")
            for t in ctx['transcripts']:
                behavior_lines.append(f"  [{t['date']}] ({t['type']}) \"{t['transcript'][:120]}\"")

        behavior_data = "\n".join(behavior_lines)

        parent_label = ctx['parent_name'] if ctx['parent_name'] else f"Parent/Guardian of {ctx['first_name']}"

        tone_instructions = {
            "concern": "Express concern about behavioral issues. Be direct but constructive. Emphasize partnership with parents. Reference specific incidents from the data.",
            "positive": "Celebrate positive behavior. Be warm and encouraging. Reference specific instances of good behavior from the data.",
            "followup": "Follow up on previous behavior communication. Note progress or continued concerns. Reference specific recent data.",
        }

        prompt = f"""Write a professional parent behavior email from a teacher.

BEHAVIOR DATA:
{behavior_data}

DETAILS:
- Teacher: {ctx['teacher_name']}
- Subject: {ctx['subject_area'] or 'class'}
- School: {ctx['school_name'] or ''}
- Parent/Guardian: {parent_label}
- Student first name: {ctx['first_name']}
- Tone: {tone}
- {tone_instructions.get(tone, tone_instructions['concern'])}
{f'- Additional note from teacher: {custom_note}' if custom_note else ''}

INSTRUCTIONS:
- Write a complete email body (no subject line — just the body)
- Start with "Dear {parent_label},"
- Reference specific behavioral incidents using the transcript and note data — don't just cite counts
- Keep it professional, constructive, and concise (150-250 words)
- End with a signature using the teacher name{' and school' if ctx['school_name'] else ''}
{f'- Use this exact signature block: {ctx["email_signature"]}' if ctx['email_signature'] else ''}
- Do not use markdown formatting — plain text only
- Do not include a subject line"""

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )

        body = response.content[0].text.strip()

        # Generate subject line
        subject_map = {
            "concern": f"Behavior Update - {ctx['first_name']}",
            "positive": f"Positive Behavior Update - {ctx['first_name']}",
            "followup": f"Behavior Follow-Up - {ctx['first_name']}",
        }
        subject = subject_map.get(tone, f"Behavior Update - {ctx['first_name']}")

        return subject, body

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"AI email generation failed: {e}")
        return None


def _generate_email_template(ctx, tone, custom_note):
    """Generate email using hardcoded template (fallback)."""
    first_name = ctx['first_name']
    subject_area = ctx['subject_area']
    parent_greeting = f"Dear {ctx['parent_name']}" if ctx['parent_name'] else f"Dear Parent/Guardian of {first_name}"

    if tone == "positive":
        email_subject = f"Positive Behavior Update - {first_name}"
        lines = [
            f"{parent_greeting},",
            "",
            f"I wanted to reach out with a positive update about {first_name}'s behavior in {subject_area + ' ' if subject_area else ''}class.",
            "",
        ]
        if ctx['praise'] > 0:
            lines.append(f"Over the past two weeks, {first_name} has received {ctx['praise']} positive recognition(s) for good behavior.")
        if ctx['praise_notes']:
            lines.append("Specifically noted: " + "; ".join(ctx['praise_notes'][:5]) + ".")
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
        if ctx['corrections'] > 0:
            lines.append(f"Since our last communication, {first_name} has had {ctx['corrections']} correction(s).")
        if ctx['praise'] > 0:
            lines.append(f"{first_name} has also received {ctx['praise']} positive recognition(s), which is encouraging.")
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
        if ctx['corrections'] > 0:
            lines.append(f"Over the past two weeks, {first_name} has needed {ctx['corrections']} correction(s) during class.")
        if ctx['correction_dates']:
            lines.append(f"Dates: {', '.join(ctx['correction_dates'])}.")
        if ctx['correction_notes']:
            lines.append(f"Areas of concern: {'; '.join(ctx['correction_notes'][:5])}.")
        if ctx['praise'] > 0:
            lines.extend([
                "",
                f"I also want to note that {first_name} has received {ctx['praise']} positive recognition(s) during this period, which shows potential for improvement.",
            ])
        lines.extend([
            "",
            f"I believe that with consistent support at home and school, we can help turn this around. I'd appreciate it if you could discuss this with {first_name}.",
            "",
            "Please feel free to contact me if you'd like to schedule a conference or discuss strategies.",
        ])

    if custom_note:
        lines.extend(["", custom_note])

    lines.extend(["", "Thank you for your support,"])
    if ctx['email_signature']:
        lines.append(ctx['email_signature'])
    else:
        lines.append(ctx['teacher_name'])
        if ctx['school_name']:
            lines.append(ctx['school_name'])

    return email_subject, "\n".join(lines)


def generate_behavior_email(student_name, tone=None, custom_note=None, teacher_id='local-dev'):
    """Generate a professional behavior email draft using AI (with template fallback)."""
    if not teacher_id or teacher_id == 'local-dev':
        teacher_id = _get_teacher_id() or teacher_id
    if not teacher_id:
        return {"error": "Not authenticated"}

    ctx = _gather_email_context(teacher_id, student_name)
    if not ctx:
        return {"error": f"No behavior data found for '{student_name}' in the last 14 days. Call get_behavior_summary with days=30 or days=90 first to check if older data exists. The student name must match exactly what was recorded in the Companion app."}

    # Auto-detect tone
    if not tone:
        if ctx['corrections'] > ctx['praise'] and ctx['corrections'] >= 3:
            tone = "concern"
        elif ctx['praise'] > ctx['corrections']:
            tone = "positive"
        else:
            tone = "concern"

    # Try AI generation first, fall back to template
    ai_generated = False
    ai_result = _generate_email_ai(ctx, tone, custom_note, teacher_id)
    if ai_result:
        email_subject, body = ai_result
        ai_generated = True
    else:
        email_subject, body = _generate_email_template(ctx, tone, custom_note)

    return {
        "status": "success",
        "data": {
            "subject": email_subject,
            "body": body,
            "to_email": ctx['parent_email'],
            "parent_name": ctx['parent_name'],
            "student_name": ctx['name'],
            "tone": tone,
            "corrections": ctx['corrections'],
            "praise": ctx['praise'],
            "ai_generated": ai_generated,
            "note": "Review the draft above. Ask me to send it when ready, or request changes.",
        }
    }


def send_behavior_email(student_name, subject, body, method="email"):
    """Send a behavior email via Resend or Focus Communications automation."""
    teacher_id = _get_teacher_id() or 'local-dev'

    if method == "focus":
        # Send via Focus Communications Playwright automation
        try:
            from backend.routes.email_routes import launch_focus_comms

            message = {
                "student_name": student_name,
                "subject": subject,
                "email_body": body,
                "sms_body": "",
                "cc_emails": [],
            }

            result = launch_focus_comms([message], teacher_id=teacher_id)
            if result.get("error"):
                return {"error": result["error"]}

            return {
                "status": "success",
                "data": {
                    "method": "focus",
                    "message": f"Focus Communications sending to {student_name}'s parents. Check the automation progress — a browser window will open for 2FA if needed.",
                    "subject": subject,
                    "student_name": student_name,
                }
            }
        except Exception as e:
            return {"error": f"Focus Communications error: {str(e)}"}

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
