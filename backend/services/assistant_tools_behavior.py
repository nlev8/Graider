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
        source = row.get('source', 'manual')
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
                "manual_notes": [],
                "stt_notes": [],
                "transcripts": [],
                "timestamps": [],
            }

        entry = student["entries_map"][entry_key]
        entry["count"] += 1
        if note and note not in entry["notes"]:
            entry["notes"].append(note)
            if source == 'stt':
                entry["stt_notes"].append(note)
            else:
                entry["manual_notes"].append(note)
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
        "description": "Generate a professional behavior email to a student's parents. Can use companion app behavior data from Supabase (corrections, praise, dates, notes) OR draft from chat context only. IMPORTANT: Before calling this, always ask the teacher: 'Would you like me to include behavior data from the Companion app, or draft using just the information you provided?' Set use_behavior_data accordingly.",
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
                    "description": "When use_behavior_data is false, this should contain ALL the context for the email (what the teacher described in chat). When true, this is an optional additional note."
                },
                "use_behavior_data": {
                    "type": "boolean",
                    "description": "If true, fetch behavior data from the Companion app (Supabase) and include it in the email. If false, draft the email using ONLY the custom_note (information from the chat conversation). Default: true."
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
                    "description": "Send method: 'focus' via Focus portal automation (default), 'email' via Resend API."
                }
            },
            "required": ["student_name", "subject", "body"]
        }
    },
    {
        "name": "debug_behavior",
        "description": "Diagnostic tool: shows teacher_id, total session/event counts, and all student names stored in behavior data. Use when behavior data retrieval fails to diagnose why.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
]


# ═══════════════════════════════════════════════════════
# IMPLEMENTATION
# ═══════════════════════════════════════════════════════

def debug_behavior(teacher_id='local-dev'):
    """Diagnostic: show what behavior data exists for the current teacher."""
    if not teacher_id or teacher_id == 'local-dev':
        teacher_id = _get_teacher_id() or teacher_id
    if not teacher_id or teacher_id == 'local-dev':
        return {"error": "Not authenticated. teacher_id resolved to '" + str(teacher_id) + "'. This means the auth middleware did not set a real user ID. Check that the JWT token is being sent with the request."}

    try:
        sb = _get_supabase()

        ses_res = sb.table('behavior_sessions').select('id, period, date, device').eq(
            'teacher_id', teacher_id
        ).execute()
        sessions = ses_res.data or []

        evt_res = sb.table('behavior_events').select('id, student_name, type, event_time').eq(
            'teacher_id', teacher_id
        ).order('event_time', desc=True).limit(100).execute()
        events = evt_res.data or []

        student_names = sorted(set(e.get('student_name', '') for e in events if e.get('student_name')))

        return {
            "status": "success",
            "teacher_id": teacher_id,
            "total_sessions": len(sessions),
            "total_events": len(events),
            "student_names_in_db": student_names,
            "recent_sessions": [{"period": s.get("period"), "date": s.get("date"), "device": s.get("device")} for s in sessions[:5]],
            "recent_events": [{"name": e.get("student_name"), "type": e.get("type"), "time": e.get("event_time")} for e in events[:10]],
        }
    except Exception as e:
        return {"error": f"Debug query failed: {str(e)}", "teacher_id": teacher_id}


def get_behavior_summary(student_name=None, period=None, days=7, teacher_id='local-dev'):
    """Get behavior summary for a student or period."""
    if not teacher_id or teacher_id == 'local-dev':
        teacher_id = _get_teacher_id() or teacher_id
    if not teacher_id or teacher_id == 'local-dev':
        return {"error": "Not authenticated — teacher_id is 'local-dev'. The auth middleware did not resolve your user ID."}

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

    # Collect notes — separate manual (reliable) from STT (approximate)
    correction_notes, praise_notes = [], []
    stt_context = []
    for e in entries:
        for note in e.get("manual_notes", []):
            if note:
                (correction_notes if e.get("type") == "correction" else praise_notes).append(note)
        # STT notes are rough speech transcripts — only use for general context
        for note in e.get("stt_notes", []):
            if note:
                stt_context.append(note)

    correction_dates = sorted(set(e.get("date", "") for e in entries if e.get("type") == "correction"))

    # Look up parent contact
    contacts_raw = _load_parent_contacts()
    # contacts_raw may be a dict (keyed by student ID) or a list
    contacts_list = contacts_raw.values() if isinstance(contacts_raw, dict) else contacts_raw
    parent_email, parent_name = "", ""
    for contact in contacts_list:
        if not isinstance(contact, dict):
            continue
        if _fuzzy_name_match(name, contact.get("student_name", "")):
            # parent_emails may be a list; grab first one
            emails = contact.get("parent_emails", [])
            parent_email = emails[0] if isinstance(emails, list) and emails else contact.get("parent_email", "") or contact.get("email", "")
            # Extract parent name from contacts array or top-level fields
            clist = contact.get("contacts", [])
            if clist and isinstance(clist[0], dict):
                parent_name = f"{clist[0].get('first_name', '')} {clist[0].get('last_name', '')}".strip()
            if not parent_name:
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
        "stt_context": stt_context[-10:],
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
        if ctx.get('stt_context'):
            behavior_lines.append("Approximate voice-detected context (rough speech-to-text, do NOT quote verbatim):")
            for s in ctx['stt_context'][:5]:
                # Strip common STT artifacts
                cleaned = s.replace('[BLANK_AUDIO]', '').replace('[LAUGHTER]', '').replace('[laughter]', '').strip()
                if cleaned:
                    behavior_lines.append(f"  \"{cleaned[:120]}\"")

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
- Reference specific behavioral incidents using the teacher notes — don't just cite counts
- Teacher notes are reliable and can be referenced directly
- Voice-detected context (if any) is approximate speech-to-text — use it only to understand general patterns, NEVER quote it verbatim in the email
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


def generate_behavior_email(student_name, tone=None, custom_note=None, use_behavior_data=True, teacher_id='local-dev'):
    """Generate a professional behavior email draft using AI (with template fallback).

    If use_behavior_data=True, fetches companion app data from Supabase.
    If use_behavior_data=False, drafts using only the custom_note (chat context).
    """
    if not teacher_id or teacher_id == 'local-dev':
        teacher_id = _get_teacher_id() or teacher_id
    if not teacher_id or teacher_id == 'local-dev':
        return {"error": "Not authenticated — teacher_id is 'local-dev'. The auth middleware did not resolve your user ID."}

    if use_behavior_data:
        # Fetch companion app behavior data from Supabase
        ctx = _gather_email_context(teacher_id, student_name)
        if not ctx:
            return {"error": f"No behavior data found for '{student_name}' in the last 14 days. Call get_behavior_summary with days=30 or days=90 first to check if older data exists. The student name must match exactly what was recorded in the Companion app."}
    else:
        # Chat-context-only mode: build minimal context without Supabase
        if not custom_note:
            return {"error": "When not using companion app data, you must provide context about the student in the custom_note parameter (the information the teacher shared in chat)."}
        settings = _load_settings()
        config = settings.get('config', {})
        first_name = _extract_first_name(student_name)
        # Look up parent contact info (still useful even without behavior data)
        parent_email, parent_name = "", ""
        contacts_raw = _load_parent_contacts()
        contacts_list = contacts_raw.values() if isinstance(contacts_raw, dict) else contacts_raw
        for contact in contacts_list:
            if not isinstance(contact, dict):
                continue
            if _fuzzy_name_match(student_name, contact.get("student_name", "")):
                emails = contact.get("parent_emails", [])
                parent_email = emails[0] if isinstance(emails, list) and emails else contact.get("parent_email", "") or contact.get("email", "")
                clist = contact.get("contacts", [])
                if clist and isinstance(clist[0], dict):
                    parent_name = f"{clist[0].get('first_name', '')} {clist[0].get('last_name', '')}".strip()
                if not parent_name:
                    parent_name = contact.get("parent_name", "") or contact.get("contact_name", "")
                break
        if not parent_email:
            roster = _load_roster()
            for s in roster:
                if _fuzzy_name_match(student_name, s.get("name", "")):
                    parent_email = s.get("parent_email", "") or s.get("guardian_email", "")
                    parent_name = s.get("parent_name", "") or s.get("guardian_name", "")
                    break
        ctx = {
            "name": student_name,
            "first_name": first_name,
            "corrections": 0,
            "praise": 0,
            "correction_notes": [],
            "praise_notes": [],
            "correction_dates": [],
            "stt_context": [],
            "parent_email": parent_email,
            "parent_name": parent_name,
            "teacher_name": config.get('teacher_name', 'Your Teacher'),
            "subject_area": config.get('subject', ''),
            "school_name": config.get('school_name', ''),
            "email_signature": config.get('email_signature', ''),
        }

    # Auto-detect tone
    if not tone:
        if use_behavior_data:
            if ctx['corrections'] > ctx['praise'] and ctx['corrections'] >= 3:
                tone = "concern"
            elif ctx['praise'] > ctx['corrections']:
                tone = "positive"
            else:
                tone = "concern"
        else:
            tone = "concern"  # Default for chat-only; AI will adapt based on custom_note

    # Try AI generation first, fall back to template
    ai_generated = False
    ai_result = _generate_email_ai(ctx, tone, custom_note, teacher_id)
    if ai_result:
        email_subject, body = ai_result
        ai_generated = True
    else:
        email_subject, body = _generate_email_template(ctx, tone, custom_note)

    result_data = {
        "subject": email_subject,
        "body": body,
        "to_email": ctx['parent_email'],
        "parent_name": ctx['parent_name'],
        "student_name": ctx['name'],
        "tone": tone,
        "ai_generated": ai_generated,
        "used_behavior_data": use_behavior_data,
        "note": "Review the draft above. Ask me to send it when ready, or request changes.",
    }
    if use_behavior_data:
        result_data["corrections"] = ctx['corrections']
        result_data["praise"] = ctx['praise']

    return {"status": "success", "data": result_data}


def send_behavior_email(student_name, subject, body, method="focus"):
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
        contacts_raw = _load_parent_contacts()
        contacts_list = contacts_raw.values() if isinstance(contacts_raw, dict) else contacts_raw
        parent_email = ""
        for contact in contacts_list:
            if not isinstance(contact, dict):
                continue
            if _fuzzy_name_match(student_name, contact.get("student_name", "")):
                emails = contact.get("parent_emails", [])
                parent_email = emails[0] if isinstance(emails, list) and emails else contact.get("parent_email", "") or contact.get("email", "")
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
    "debug_behavior": debug_behavior,
    "get_behavior_summary": get_behavior_summary,
    "generate_behavior_email": generate_behavior_email,
    "send_behavior_email": send_behavior_email,
}
