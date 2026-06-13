"""Parent / focus communication tools and the confirm-and-send executor.

Pure-move of whole functions out of the former single-file module; bodies
are byte-identical. The pending-send helpers (``_parse_student_name``,
``_fill_email_template``) live here because only the comms writers use them.

NOTE: ``test_gh280_cross_module_pending_send_unit.py`` patches
``storage_load`` / ``storage_save`` / ``_load_roster`` /
``_load_parent_contacts`` / ``_load_email_config`` / ``audit_tool_action``
on THIS module (the implementation home of the comms writers), not on the
package ``__init__``. The names are still re-exported from ``__init__`` for
normal imports.
"""
import os
import json
import logging

from backend.services.assistant_tools import (
    _load_settings, _load_roster, _load_parent_contacts, _load_email_config,
    _fuzzy_name_match, _normalize_period,
)
from backend.services.assistant_tools_grading import get_missing_assignments
from backend.utils.compliance import audit_tool_action, require_teacher_id
from backend.utils.pending_send import (
    pending_send_path as _pending_send_path,
    assert_pending_belongs_to as _assert_pending_belongs_to,
)
import sentry_sdk

_logger = logging.getLogger(__name__)

try:
    from backend.storage import load as storage_load, save as storage_save
except ImportError:
    try:
        from storage import load as storage_load, save as storage_save
    except ImportError:
        storage_load = None
        storage_save = None


def _parse_student_name(name):
    """Parse 'Last, First Middle' or 'First Last' into components.

    Returns dict with first_name, last_name, full_name (as 'First Last').
    """
    if not name:
        return {"first_name": "Student", "last_name": "", "full_name": "Student"}

    name = name.strip()
    for sep in [',', ';']:
        if sep in name:
            parts = name.split(sep, 1)
            last = parts[0].strip()
            after = parts[1].strip()
            first = after.split()[0] if after else last
            return {
                "first_name": first,
                "last_name": last,
                "full_name": first + " " + last,
            }
    words = name.split()
    return {
        "first_name": words[0],
        "last_name": words[-1] if len(words) > 1 else "",
        "full_name": name,
    }


def _fill_email_template(template, replacements):
    """Replace {placeholders} in a template string."""
    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def send_parent_emails(email_subject, email_body, student_names=None, period=None,
                       zero_submissions=False, dry_run=True, teacher_id='local-dev'):
    """Generate email preview for parents/guardians via Outlook automation.

    When called from the AI assistant, this ALWAYS returns a preview.
    Actual sending is triggered by the frontend confirm action via /api/confirm-send.
    """
    require_teacher_id(teacher_id)
    # Programmatic guard: AI assistant must never send directly
    dry_run = True
    # Load parent contacts
    contacts = _load_parent_contacts(teacher_id)
    if not contacts:
        return {"error": "No parent contacts imported. Upload class list in Settings first."}

    # Load teacher settings
    settings = _load_settings(teacher_id)
    config = settings.get('config', {})
    email_config = _load_email_config()
    teacher_name = email_config.get('teacher_name', '') or config.get('teacher_name', 'Your Teacher')
    subject_area = config.get('subject', '')
    email_signature = email_config.get('email_signature', '')

    # Build reverse map: normalized student name -> (student_id, contact data)
    name_to_contact = {}
    for student_id, contact in contacts.items():
        sname = contact.get('student_name', '')
        if sname:
            name_to_contact[sname] = (student_id, contact)

    # Resolve target students
    target_students = []  # list of (student_id, contact_data, period)

    if zero_submissions:
        missing_data = get_missing_assignments(period="all")
        if "error" in missing_data:
            return {"error": "Could not check missing assignments: " + missing_data["error"]}

        zero_list = missing_data.get("zero_submission_students", [])
        if not zero_list:
            return {"message": "No students with zero submissions found.", "total_emails": 0}

        for entry in zero_list:
            sname = entry.get("student_name", "")
            speriod = entry.get("period", "")

            # Try exact match first, then fuzzy
            matched = False
            for cname, (sid, cdata) in name_to_contact.items():
                if _fuzzy_name_match(sname, cname):
                    target_students.append((sid, cdata, speriod))
                    matched = True
                    break
            if not matched:
                target_students.append((None, {"student_name": sname}, speriod))

    elif student_names:
        for search_name in student_names:
            matched = False
            for cname, (sid, cdata) in name_to_contact.items():
                if _fuzzy_name_match(search_name, cname):
                    speriod = cdata.get('period', '')
                    target_students.append((sid, cdata, speriod))
                    matched = True
                    break
            if not matched:
                target_students.append((None, {"student_name": search_name}, ""))

    elif period:
        target_period = _normalize_period(period)
        for sid, cdata in contacts.items():
            cperiod = cdata.get('period', '')
            if _normalize_period(cperiod) == target_period:
                target_students.append((sid, cdata, cperiod))

    else:
        return {"error": "Provide student_names, period, or set zero_submissions=true to target students."}

    # Build email payloads
    emails = []
    skipped = []

    for sid, cdata, speriod in target_students:
        parent_emails = cdata.get('parent_emails', [])
        sname = cdata.get('student_name', 'Student')

        if not parent_emails:
            skipped.append(sname)
            continue

        parsed = _parse_student_name(sname)
        parent_name = cdata.get('primary_contact_name', '')
        if not parent_name:
            parent_name = "Parent/Guardian"

        replacements = {
            "student_first_name": parsed["first_name"],
            "student_last_name": parsed["last_name"],
            "student_name": parsed["full_name"],
            "parent_name": parent_name,
            "period": speriod or cdata.get('period', ''),
            "teacher_name": teacher_name,
            "subject_area": subject_area,
        }

        filled_subject = _fill_email_template(email_subject, replacements)
        filled_body = _fill_email_template(email_body, replacements)

        # Append teacher signature
        if email_signature:
            filled_body += "\n\n" + email_signature
        elif teacher_name and teacher_name != 'Your Teacher':
            filled_body += "\n\n" + teacher_name

        to_email = parent_emails[0]
        cc_emails = parent_emails[1:] if len(parent_emails) > 1 else []

        emails.append({
            "to": to_email,
            "cc": ', '.join(cc_emails) if cc_emails else '',
            "subject": filled_subject,
            "body": filled_body,
            "student_name": sname,
        })

    if not emails and skipped:
        return {
            "error": "No parent emails found for any targeted students.",
            "skipped_students": skipped,
        }
    if not emails:
        return {"error": "No matching students found."}

    # Dry run: return preview
    if dry_run:
        previews = []
        for e in emails[:3]:
            previews.append({
                "to": e["to"],
                "cc": e.get("cc", ""),
                "subject": e["subject"],
                "body": e["body"][:500] + ("..." if len(e["body"]) > 500 else ""),
                "student_name": e["student_name"],
            })
        # Store pending payload for confirm_and_send tool.
        # GH #280 fix: inject teacher_id so confirm_and_send can do
        # cross-tenant IDOR validation; use per-tenant filesystem path
        # via _pending_send_path() helper.
        pending_data = {
            "action": "send_parent_emails",
            "emails": emails,
            "teacher_id": teacher_id,
        }
        if storage_save:
            storage_save('pending_send', pending_data, teacher_id)
        # Filesystem fallback (SSE event builder reads from here) —
        # now per-tenant, never the legacy global path.
        pending_path = _pending_send_path(teacher_id)
        os.makedirs(os.path.dirname(pending_path), exist_ok=True)
        try:
            with open(pending_path, 'w') as pf:
                json.dump(pending_data, pf)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            sentry_sdk.capture_exception(e)

        audit_tool_action(teacher_id, 'send_parent_emails', 'SEND_EMAIL')

        return {
            "dry_run": True,
            "NOT_SENT": True,
            "preview_count": len(previews),
            "total_emails": len(emails),
            "previews": previews,
            "skipped_students": skipped,
            "message": "PREVIEW ONLY — emails have NOT been sent yet. Show this preview to the teacher and ask if they want to send it. If they confirm, call confirm_and_send.",
        }

    # Actually send via Outlook/Playwright
    try:
        from backend.routes.email_routes import launch_outlook_sender
        result = launch_outlook_sender(emails, teacher_id=teacher_id)
        result["skipped_students"] = skipped
        result["total_emails"] = len(emails)
        return result
    except ImportError:
        return {"error": "Outlook sender not available. Check backend installation."}
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return {"error": "Failed to launch Outlook sender: " + str(e)}


def send_focus_comms(email_subject, email_body=None, sms_body=None, student_names=None,
                     period=None, dry_run=True, recipient_type=None, teacher_id='local-dev'):
    """Generate email/SMS preview for parents via Focus SIS Communications.

    When called from the AI assistant, this ALWAYS returns a preview.
    Actual sending is triggered by the frontend confirm action via /api/confirm-send.
    Supports email-only, SMS-only, or both.
    """
    require_teacher_id(teacher_id)
    # Programmatic guard: AI assistant must never send directly
    dry_run = True

    if not email_body and not sms_body:
        return {"error": "Provide email_body, sms_body, or both."}

    # Auto-generate SMS notification if email is provided but SMS is not.
    # Default behavior: always send both email + SMS unless SMS-only was requested.
    if email_body and not sms_body:
        settings = _load_settings(teacher_id)
        config = settings.get('config', {})
        email_config = _load_email_config()
        teacher_name = email_config.get('teacher_name', '') or config.get('teacher_name', 'Your Teacher')
        sms_body = "Please check your email for a message regarding " + email_subject + ". -" + teacher_name
    FOCUS_ROSTER_FILE = os.path.expanduser("~/.graider_data/focus_roster_import.json")

    if not os.path.exists(FOCUS_ROSTER_FILE):
        return {"error": "No Focus roster imported. Import roster from Focus in Settings first."}

    try:
        with open(FOCUS_ROSTER_FILE, 'r', encoding='utf-8') as f:
            roster = json.load(f)
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return {"error": "Failed to load Focus roster: " + str(e)}

    # Build flat list of all students from roster periods
    all_students = []  # list of (student_name, period_name)
    periods = roster.get("periods", {})
    for period_name, period_data in periods.items():
        for student in period_data.get("students", []):
            all_students.append((student.get("name", ""), period_name))

    if not all_students:
        return {"error": "Focus roster is empty."}

    # Resolve target students
    target_students = []  # list of (student_name, period_name)

    if student_names:
        for search_name in student_names:
            matched = False
            for sname, pname in all_students:
                if _fuzzy_name_match(search_name, sname):
                    target_students.append((sname, pname))
                    matched = True
                    break
            if not matched:
                target_students.append((search_name, ""))
    elif period:
        target_period = _normalize_period(period)
        for sname, pname in all_students:
            if _normalize_period(pname) == target_period:
                target_students.append((sname, pname))
    else:
        return {"error": "Provide student_names or period to target students."}

    if not target_students:
        return {"error": "No matching students found in Focus roster."}

    # Build messages in focus-comms.js format
    messages = []
    skipped = []

    for sname, pname in target_students:
        parsed = _parse_student_name(sname)

        replacements = {
            "student_first_name": parsed["first_name"],
            "student_last_name": parsed["last_name"],
            "student_name": parsed["full_name"],
        }

        filled_subject = _fill_email_template(email_subject, replacements)
        filled_body = _fill_email_template(email_body, replacements) if email_body else ""
        filled_sms = _fill_email_template(sms_body, replacements) if sms_body else ""

        msg_entry = {
            "student_name": sname,
            "subject": filled_subject,
            "email_body": filled_body,
            "sms_body": filled_sms,
            "cc_emails": [],
        }
        if recipient_type and recipient_type != "Primary Contacts":
            msg_entry["recipient_type"] = recipient_type
        messages.append(msg_entry)

    if not messages:
        return {"error": "No messages to send."}

    # Dry run: return preview
    if dry_run:
        previews = []
        for m in messages:
            previews.append({
                "student_name": m["student_name"],
                "subject": m["subject"],
                "email_body": m["email_body"][:500] + ("..." if len(m["email_body"]) > 500 else ""),
                "sms_body": m["sms_body"][:200] if m["sms_body"] else "(no SMS)",
            })
        # Store pending payload for confirm_and_send tool.
        # GH #280 fix: inject teacher_id + per-tenant filesystem path.
        pending_data = {
            "action": "send_focus_comms",
            "messages": messages,
            "teacher_id": teacher_id,
        }
        if storage_save:
            storage_save('pending_send', pending_data, teacher_id)
        # Filesystem fallback (SSE event builder reads from here) —
        # now per-tenant, never the legacy global path.
        pending_path = _pending_send_path(teacher_id)
        os.makedirs(os.path.dirname(pending_path), exist_ok=True)
        try:
            with open(pending_path, 'w') as pf:
                json.dump(pending_data, pf)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            sentry_sdk.capture_exception(e)

        audit_tool_action(teacher_id, 'send_focus_comms', 'SEND_EMAIL')

        return {
            "dry_run": True,
            "NOT_SENT": True,
            "preview_count": len(previews),
            "total_messages": len(messages),
            "recipient_names": [m["student_name"] for m in messages],
            "previews": previews,
            "message": "PREVIEW ONLY — messages have NOT been sent yet. VERIFY the recipient names are correct before asking the teacher to confirm. If they confirm, call confirm_and_send.",
        }

    # Actually send via focus-comms.js
    try:
        from backend.routes.email_routes import launch_focus_comms
        result = launch_focus_comms(messages, teacher_id=teacher_id)
        result["total_messages"] = len(messages)
        return result
    except ImportError:
        return {"error": "Focus Comms route not available. Check backend installation."}
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return {"error": "Failed to launch Focus Comms: " + str(e)}


def confirm_and_send(teacher_id='local-dev'):
    """Execute the pending send action after teacher confirmation.

    Reads the pending payload saved by send_focus_comms or send_parent_emails,
    then triggers the actual Playwright automation.

    NOTE: This tool is called by the AI assistant. The frontend "Send Now" button
    calls /api/confirm-send directly (email_routes.py) instead.
    """
    require_teacher_id(teacher_id)
    # Load pending payload from storage (preferred) or filesystem fallback
    pending = None
    if storage_load:
        pending = storage_load('pending_send', teacher_id)

    if not pending:
        # Check keyed storage entries (send_behavior_email etc. save under action-specific keys)
        for action_key in ('send_behavior_email', 'send_focus_comms', 'send_parent_emails'):
            keyed = storage_load('pending_send:' + action_key, teacher_id) if storage_load else None
            if keyed:
                pending = keyed
                break

    if not pending:
        # GH #280 fix: per-tenant filesystem path (was global)
        pending_path = _pending_send_path(teacher_id)
        if not os.path.exists(pending_path):
            return {"error": "No pending send action. Generate a preview first using send_focus_comms or send_parent_emails."}
        try:
            with open(pending_path, 'r') as f:
                pending = json.load(f)
        except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
            return {"error": "Failed to read pending send: " + str(e)}

    # GH #280 fix: cross-tenant IDOR validation. Defense-in-depth even
    # though the storage layer is already tenant-namespaced — guards
    # against legacy payloads + filesystem-fallback misroutes.
    idor_err = _assert_pending_belongs_to(pending, teacher_id)
    if idor_err is not None:
        return idor_err

    action = pending.get("action")

    try:
        if action == "send_focus_comms":
            from backend.routes.email_routes import launch_focus_comms
            messages = pending.get("messages", [])
            if not messages:
                return {"error": "No messages in pending payload."}
            result = launch_focus_comms(messages, teacher_id=teacher_id)
            if "error" in result:
                # Keep pending data so teacher can retry
                return result
            # Success — clear pending to prevent double-send. GH #280
            # round-2 fold: previously this used `if storage_save: ... else:`
            # which left the local file orphaned in production (where
            # storage_save is non-None). Subsequent confirmations would
            # then read the orphaned file and replay the send. Now both
            # storage clears AND the file remove run unconditionally.
            if storage_save:
                storage_save('pending_send', None, teacher_id)
                storage_save('pending_send:send_focus_comms', None, teacher_id)
            try:
                os.remove(_pending_send_path(teacher_id))
            except OSError as e:
                _logger.debug("Pending-send file cleanup skipped (likely already absent): %s", e)
            audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')
            result["total_messages"] = len(messages)
            return result
        elif action == "send_parent_emails":
            from backend.routes.email_routes import launch_outlook_sender
            emails = pending.get("emails", [])
            if not emails:
                return {"error": "No emails in pending payload."}
            result = launch_outlook_sender(emails, teacher_id=teacher_id)
            if "error" in result:
                return result
            # Success — clear both Supabase keys + local file (GH #280 R2)
            if storage_save:
                storage_save('pending_send', None, teacher_id)
                storage_save('pending_send:send_parent_emails', None, teacher_id)
            try:
                os.remove(_pending_send_path(teacher_id))
            except OSError as e:
                _logger.debug("Pending-send file cleanup skipped (likely already absent): %s", e)
            audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')
            result["total_emails"] = len(emails)
            return result
        elif action == "send_behavior_email":
            student_name = pending.get("student_name", "")
            subject = pending.get("subject", "")
            body = pending.get("body", "")
            method = pending.get("method", "focus")

            def _clear_behavior_pending():
                if storage_save:
                    storage_save('pending_send', None, teacher_id)
                    storage_save('pending_send:send_behavior_email', None, teacher_id)
                try:
                    os.remove(_pending_send_path(teacher_id))
                except OSError as e:
                    _logger.debug("Pending-send file cleanup skipped (likely already absent): %s", e)

            if method == "focus":
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
                    return result
                _clear_behavior_pending()
                audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')
                return {
                    "status": "started",
                    "method": "focus",
                    "message": "Focus Communications sending to " + student_name + "'s parents. Check the automation progress — a browser window will open for 2FA if needed.",
                }
            else:
                from backend.services.email_service import EmailService
                email_svc = EmailService()
                parent_email = pending.get("parent_email", "")
                if not parent_email:
                    return {"error": "No parent email in pending payload."}
                success = email_svc.send_email(
                    to_email=parent_email,
                    student_name=student_name,
                    subject=subject,
                    body=body,
                )
                if not success:
                    return {"error": "Failed to send email. Check Resend configuration."}
                _clear_behavior_pending()
                audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')
                return {
                    "status": "started",
                    "method": "email",
                    "message": "Email sent to " + parent_email,
                }
        else:
            return {"error": f"Unknown pending action: {action}"}
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return {"error": f"Failed to launch send: {str(e)}"}
