"""
Clever SSO and Secure Sync routes.
"""
import os
import asyncio
import logging
import secrets
import threading
import time as _time

from flask import Blueprint, request, jsonify, redirect, session, g

from backend.clever import (
    get_clever_config,
    get_authorize_url,
    exchange_code_for_token,
    get_clever_user,
    sync_roster,
    extract_student_accommodations,
    extract_parent_contacts,
    persist_roster_as_csv,
    persist_sections_as_periods,
    persist_parent_contacts,
    map_sections_to_periods,
    delete_clever_data,
)
from backend.accommodations import set_student_accommodation
from backend.auth import load_clever_links, save_clever_link, resolve_clever_user_id
from backend.supabase_client import get_supabase as _get_supabase_safe

logger = logging.getLogger(__name__)

clever_bp = Blueprint("clever", __name__)


def _clever_audit(action, details="", teacher_id=""):
    """FERPA audit log for Clever operations."""
    logger.info("AUDIT: %s | teacher=%s | %s", action, teacher_id, details)
    try:
        from backend.supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            from datetime import datetime
            sb.table('audit_log').insert({
                'timestamp': datetime.now().isoformat(),
                'teacher_id': teacher_id,
                'action': action,
                'details': details[:500],
                'user_type': 'teacher',
            }).execute()
    except Exception:
        pass

# Short-lived auth codes for student Clever SSO (code → {token, expires})
_pending_student_auth_codes = {}
_AUTH_CODE_TTL = 60  # seconds


def _create_student_auth_code(raw_token):
    """Create a short-lived auth code that can be exchanged for a session token."""
    code = secrets.token_urlsafe(32)
    _pending_student_auth_codes[code] = {
        "token": raw_token,
        "expires": _time.time() + _AUTH_CODE_TTL,
    }
    # Cleanup expired codes
    now = _time.time()
    expired = [k for k, v in _pending_student_auth_codes.items() if v["expires"] < now]
    for k in expired:
        del _pending_student_auth_codes[k]
    return code


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _sync_classes_to_db(sections, students, teacher_id):
    """Upsert Clever sections and students into Supabase classes/students/class_students tables.

    Called after file-based persist so the class-based student portal can see Clever-rostered data.
    Silently skips if Supabase is not configured.

    Uses batched upserts to minimise Supabase HTTP round-trips:
      - ONE call to upsert all classes
      - ONE call to upsert all unique students
      - ONE call to upsert all (class, student) enrollment pairs

    Args:
        sections: List of Clever section dicts (with 'data' wrapper).
        students: List of Clever student dicts (with 'data' wrapper).
        teacher_id: Graider teacher ID (may be 'clever:xxx' format).
    """
    sb = _get_supabase_safe()
    if sb is None:
        logger.debug("Supabase not configured — skipping class DB sync")
        return

    # Build a lookup from clever student id -> student record for fast access
    student_map = {}
    for s in students:
        sd = s.get("data", s)
        sid = sd.get("id")
        if sid:
            student_map[sid] = sd

    # --- Phase 1: Collect and batch-upsert all class records ---
    # Preserve insertion order so callers can predict class_id_map contents
    section_data_map = {}  # clever_section_id -> section dict
    class_payloads = []
    for section in sections:
        sec = section.get("data", section)
        clever_section_id = sec.get("id")
        if not clever_section_id:
            continue
        section_data_map[clever_section_id] = sec
        class_payloads.append({
            "teacher_id": teacher_id,
            "name": sec.get("name", ""),
            "subject": sec.get("subject", ""),
            "grade_level": sec.get("grade", ""),
            "clever_section_id": clever_section_id,
            "is_active": True,
        })

    if not class_payloads:
        logger.info("DB class sync complete: 0 classes, 0 students, 0 enrollments")
        return

    try:
        class_result = (
            sb.table("classes")
            .upsert(class_payloads, on_conflict="teacher_id,clever_section_id")
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to batch-upsert classes: %s", str(e))
        return

    class_rows = class_result.data if class_result and class_result.data else []
    if not class_rows:
        logger.warning("No class rows returned from batch upsert")
        return

    # Build clever_section_id -> DB class UUID map from returned rows
    class_id_map = {}
    for row in class_rows:
        csid = row.get("clever_section_id", "")
        if csid and row.get("id"):
            class_id_map[csid] = row["id"]

    synced_classes = len(class_id_map)

    # --- Phase 2: Collect and batch-upsert all unique students ---
    # Also build the list of (section_id, student_clever_id) pairs for enrollment
    enrollment_pairs = []   # list of (clever_section_id, clever_student_id)
    unique_students = {}    # clever_student_id -> student upsert payload

    for clever_section_id, sec in section_data_map.items():
        if clever_section_id not in class_id_map:
            # No DB class was returned for this section — skip its students
            continue
        for clever_student_id in sec.get("students", []):
            sd = student_map.get(clever_student_id)
            if not sd:
                continue
            enrollment_pairs.append((clever_section_id, clever_student_id))
            if clever_student_id not in unique_students:
                name = sd.get("name", {})
                unique_students[clever_student_id] = {
                    "teacher_id": teacher_id,
                    "student_id_number": clever_student_id,
                    "first_name": name.get("first", ""),
                    "last_name": name.get("last", ""),
                    "email": sd.get("email", ""),
                    "is_active": True,
                }

    if not unique_students:
        logger.info(
            "DB class sync complete: %d classes, 0 students, 0 enrollments",
            synced_classes,
        )
        return

    try:
        stu_result = (
            sb.table("students")
            .upsert(list(unique_students.values()), on_conflict="teacher_id,student_id_number")
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to batch-upsert students: %s", str(e))
        logger.info(
            "DB class sync complete: %d classes, 0 students, 0 enrollments",
            synced_classes,
        )
        return

    stu_rows = stu_result.data if stu_result and stu_result.data else []
    if not stu_rows:
        logger.warning("No student rows returned from batch upsert")
        logger.info(
            "DB class sync complete: %d classes, 0 students, 0 enrollments",
            synced_classes,
        )
        return

    # Build clever_student_id -> DB student UUID map from returned rows
    student_id_map = {}
    for row in stu_rows:
        sid_num = row.get("student_id_number", "")
        if sid_num and row.get("id"):
            student_id_map[sid_num] = row["id"]

    synced_students = len(student_id_map)

    # --- Phase 3: Batch-upsert all (class, student) enrollment pairs ---
    enrollment_payloads = []
    for clever_section_id, clever_student_id in enrollment_pairs:
        class_db_id = class_id_map.get(clever_section_id)
        student_db_id = student_id_map.get(clever_student_id)
        if class_db_id and student_db_id:
            enrollment_payloads.append({"class_id": class_db_id, "student_id": student_db_id})

    synced_enrollments = 0
    if enrollment_payloads:
        try:
            sb.table("class_students").upsert(
                enrollment_payloads, on_conflict="class_id,student_id"
            ).execute()
            synced_enrollments = len(enrollment_payloads)
        except Exception as e:
            logger.warning("Failed to batch-upsert enrollments: %s", str(e))

    logger.info(
        "DB class sync complete: %d classes, %d students, %d enrollments",
        synced_classes, synced_students, synced_enrollments,
    )


def _create_clever_student_session(clever_id, email):
    """Look up a student by their Clever ID, find their class enrollment,
    create a hashed session token, and return session info.

    Args:
        clever_id: Clever student ID (stored as student_id_number).
        email: Student email from Clever (used as fallback lookup).

    Returns:
        dict with keys 'token', 'student', 'class', or None if not found.
    """
    import secrets as _secrets
    import hashlib
    from datetime import datetime, timezone, timedelta

    sb = _get_supabase_safe()
    if sb is None:
        logger.debug("Supabase not configured — cannot create student session")
        return None

    try:
        # Look up student by Clever ID (stored as student_id_number)
        # NOTE: Not scoped by teacher_id because this runs during student SSO
        # (OAuth callback) where we only have the student's Clever identity —
        # teacher_id is unknown.  If the same Clever student exists under
        # multiple teachers, the first DB row wins.  The subsequent enrollment
        # lookup (class_students join) naturally narrows to a valid class, so
        # the session is still usable.  A fully correct fix would query
        # class_students joined with students to find all enrollments, then
        # let the student pick a class — but that requires a UI flow change.
        res = sb.table("students").select("*").eq("student_id_number", clever_id).execute()
        student_row = res.data[0] if res and res.data else None

        # Fallback: look up by email
        if student_row is None and email:
            res2 = sb.table("students").select("*").eq("email", email).execute()
            student_row = res2.data[0] if res2 and res2.data else None

        if student_row is None:
            logger.info("Clever student not found: clever_id=%s email=%s", clever_id, email)
            return None

        student_db_id = student_row["id"]

        # Find class enrollment
        enroll_res = (
            sb.table("class_students")
            .select("class_id, classes(id, name, subject)")
            .eq("student_id", student_db_id)
            .limit(1)
            .execute()
        )
        enroll_rows = enroll_res.data if enroll_res and enroll_res.data else []
        if not enroll_rows:
            logger.info("Clever student %s has no class enrollment", student_db_id)
            return None

        enrollment = enroll_rows[0]
        class_info = enrollment.get("classes") or {}
        class_id = class_info.get("id") or enrollment.get("class_id")

        # Create session: store hash, return raw token
        raw_token = _secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires = datetime.now(tz=timezone.utc) + timedelta(hours=8)

        sb.table("student_sessions").insert({
            "student_id": student_db_id,
            "class_id": class_id,
            "session_token": token_hash,
            "expires_at": expires.isoformat(),
        }).execute()

        return {
            "token": raw_token,
            "student": {
                "first_name": student_row.get("first_name", ""),
                "last_name": student_row.get("last_name", ""),
                "email": student_row.get("email", ""),
                "student_id": student_row.get("student_id_number", ""),
                "period": student_row.get("period", ""),
            },
            "class": {
                "name": class_info.get("name", ""),
                "subject": class_info.get("subject", ""),
            },
        }
    except Exception as e:
        logger.warning("Failed to create clever student session: %s", str(e))
        return None


def _background_roster_sync(district_token, teacher_id):
    """Run roster sync in a background thread so OAuth callback returns immediately."""
    try:
        roster = _run_async(sync_roster(district_token))
        students = roster.get("students", [])
        if students:
            persist_roster_as_csv(students, teacher_id)
        sections = roster.get("sections", [])
        if sections:
            persist_sections_as_periods(sections, teacher_id)
            _sync_classes_to_db(sections, students, teacher_id)
        contacts = roster.get("contacts", [])
        if contacts and students:
            contact_map = extract_parent_contacts(contacts, students)
            if contact_map:
                persist_parent_contacts(contact_map, teacher_id)
        logger.info("Background roster sync complete: %d students, %d sections, %d contacts",
                    len(students), len(sections), len(contacts))
    except Exception as e:
        logger.warning("Background roster sync failed: %s", str(e))


@clever_bp.route("/api/clever/login-url", methods=["GET"])
def clever_login_url():
    """Return the Clever OAuth authorization URL."""
    config = get_clever_config()
    if not config:
        return jsonify({"error": "Clever not configured"}), 503

    state = secrets.token_urlsafe(32)
    session["clever_oauth_state"] = state
    url = get_authorize_url(state=state)
    return jsonify({"url": url})


@clever_bp.route("/api/clever/callback", methods=["GET"])
def clever_callback():
    """Handle the OAuth redirect from Clever.

    Exchanges the authorization code for a token, fetches the user
    profile, and creates a Graider session.
    """
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        logger.warning("Clever OAuth error: %s", error)
        return redirect(f"/?clever_error={error}")

    if not code:
        return redirect("/?clever_error=missing_code")

    # Validate state parameter (CSRF protection)
    # Clever Portal/Instant Login may not include state, but if we set one
    # in the session, it MUST match. Missing expected_state = session lost = reject.
    expected_state = session.pop("clever_oauth_state", None)
    if not expected_state or state != expected_state:
        logger.warning("Clever OAuth state mismatch (expected=%s, got=%s)",
                       bool(expected_state), bool(state))
        return redirect("/?clever_error=state_mismatch")

    # Exchange code for token
    token_data = _run_async(exchange_code_for_token(code))
    if not token_data or "access_token" not in token_data:
        return redirect("/?clever_error=token_exchange_failed")

    access_token = token_data["access_token"]

    # Fetch user identity
    clever_user = _run_async(get_clever_user(access_token))
    if not clever_user:
        return redirect("/?clever_error=user_fetch_failed")

    # Handle student login — create student session and redirect to portal
    if clever_user["type"] == "student":
        student_session = _create_clever_student_session(
            clever_user["clever_id"],
            clever_user.get("email", ""),
        )
        if student_session:
            from urllib.parse import urlencode
            auth_code = _create_student_auth_code(student_session["token"])
            params = urlencode({
                "clever": "1",
                "code": auth_code,
            })
            logger.info("AUDIT: Clever student login: clever_id=%s email=%s",
                        clever_user["clever_id"], clever_user.get("email", ""))
            return redirect("/student?" + params)
        else:
            logger.info("AUDIT: Clever student login failed (not enrolled): clever_id=%s email=%s",
                        clever_user["clever_id"], clever_user.get("email", ""))
            return redirect("/?clever_error=student_not_enrolled")

    # Reject unknown roles
    if clever_user["type"] not in ("teacher", "district_admin", "school_admin", "staff"):
        return redirect("/?clever_error=unsupported_role")

    # Clear any existing session (shared device support — Clever requirement)
    session.clear()

    # Store Clever session info
    session.permanent = True  # Apply PERMANENT_SESSION_LIFETIME (8h inactivity timeout)
    session["clever_user"] = {
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user["type"],
        "district": clever_user.get("district", ""),
        # Do NOT store access_token in session — it's short-lived
        # and only needed for the initial user fetch
    }

    # Account merging: link Clever account to existing Supabase user if emails match.
    # This lets teachers who already have a Graider account keep all their data
    # when they switch to Clever SSO login.
    clever_id = clever_user["clever_id"]
    clever_email = clever_user.get("email", "")
    existing_links = load_clever_links()
    if clever_id not in existing_links and clever_email:
        try:
            sb = _get_supabase_safe()
            if sb:
                # Look up Supabase user by email — collect all matches to avoid
                # silently merging when multiple accounts share an email.
                res = sb.auth.admin.list_users()
                matches = [
                    u for u in (res or [])
                    if getattr(u, 'email', None) and u.email.lower() == clever_email.lower()
                ]
                if len(matches) == 1:
                    save_clever_link(clever_id, matches[0].id)
                    logger.info("Merged Clever user %s with existing account %s (%s)",
                                clever_id, matches[0].id, clever_email)
                elif len(matches) > 1:
                    logger.warning(
                        "Multiple Supabase users match email %s — skipping merge to avoid data conflict",
                        clever_email,
                    )
        except Exception as e:
            logger.warning("Clever account merge check failed (non-fatal): %s", str(e))

    # Trigger BACKGROUND roster sync on login (Clever requires daily data updates;
    # login-triggered sync satisfies this requirement). Runs in a separate thread
    # so the OAuth redirect returns immediately.
    district_token = os.getenv("CLEVER_DISTRICT_TOKEN")
    teacher_id = resolve_clever_user_id(clever_id)
    if district_token:
        thread = threading.Thread(
            target=_background_roster_sync,
            args=(district_token, teacher_id),
            daemon=True,
        )
        thread.start()

    logger.info("AUDIT: Clever teacher login: email=%s type=%s district=%s clever_id=%s",
                clever_user.get("email"), clever_user["type"],
                clever_user.get("district", ""), clever_user["clever_id"])
    return redirect("/?clever_login=success")


@clever_bp.route("/api/clever/session", methods=["GET"])
def clever_session_check():
    """Return current Clever session info (if logged in via Clever)."""
    clever_user = session.get("clever_user")
    if not clever_user:
        return jsonify({"authenticated": False})
    resolved_id = resolve_clever_user_id(clever_user["clever_id"])

    import time
    import glob as _glob
    last_sync_time = None
    try:
        safe_id = clever_user["clever_id"].replace(":", "_")
        roster_pattern = os.path.join(os.path.expanduser("~/.graider_data/rosters"), f"clever_roster_*{safe_id}*")
        roster_files = _glob.glob(roster_pattern)
        if roster_files:
            last_sync_time = os.path.getmtime(roster_files[0])
    except Exception:
        pass

    return jsonify({
        "authenticated": True,
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user.get("type", ""),
        "district": clever_user.get("district", ""),
        "account_linked": not resolved_id.startswith("clever:"),
        "last_sync": last_sync_time,
    })


@clever_bp.route("/api/clever/sync-roster", methods=["POST"])
def clever_sync_roster():
    """Trigger a roster sync from Clever.

    Pulls students and sections, persists them to ROSTERS_DIR and PERIODS_DIR
    (same format as manual CSV upload), and returns accommodation suggestions.

    Optional body: { "section_ids": ["id1", "id2"] } to sync only specific sections.
    If omitted, syncs all sections.
    """
    if not session.get("clever_user"):
        return jsonify({"error": "Clever session required"}), 401

    district_token = os.getenv("CLEVER_DISTRICT_TOKEN")
    if not district_token:
        return jsonify({"error": "District token not configured"}), 503

    teacher_id = getattr(g, "user_id", "local-dev")
    data = request.get_json(silent=True) or {}
    selected_section_ids = data.get("section_ids")  # None = all sections

    try:
        roster = _run_async(sync_roster(district_token))
    except Exception as e:
        logger.error("Clever roster sync failed: %s", str(e))
        return jsonify({"error": "Failed to sync roster from Clever"}), 502

    # SECURITY: Server-side section filtering — teachers only see their own sections
    clever_user = session.get("clever_user", {})
    teacher_clever_id = clever_user.get("clever_id", "")
    if teacher_clever_id:
        all_sections = roster.get("sections", [])
        own_sections = []
        for sec in all_sections:
            sd = sec.get("data", sec)
            section_teachers = sd.get("teachers", [])
            # teachers can be a list of IDs or a list of dicts with 'id'
            teacher_ids = []
            for t in section_teachers:
                if isinstance(t, str):
                    teacher_ids.append(t)
                elif isinstance(t, dict):
                    teacher_ids.append(t.get("id", ""))
            if teacher_clever_id in teacher_ids:
                own_sections.append(sec)
        roster["sections"] = own_sections
        logger.info("Filtered sections for teacher %s: %d of %d",
                     teacher_clever_id, len(own_sections), len(all_sections))

    # Filter sections if teacher selected specific ones
    sections = roster.get("sections", [])
    if selected_section_ids is not None:
        selected_set = set(selected_section_ids)
        sections = [s for s in sections if s.get("data", s).get("id", "") in selected_set]

    # Collect student IDs from selected sections to filter students
    students = roster.get("students", [])
    if selected_section_ids is not None and sections:
        # Only include students enrolled in selected sections
        section_student_ids = set()
        for s in sections:
            sd = s.get("data", s)
            section_student_ids.update(sd.get("students", []))
        students = [st for st in students
                    if st.get("data", st).get("id", "") in section_student_ids]

    # Persist roster to CSV (same location as manual upload)
    if students:
        persist_roster_as_csv(students, teacher_id)

    # Persist sections as periods (same location as manual period creation)
    if sections:
        persist_sections_as_periods(sections, teacher_id)

    # Persist parent contacts from Clever guardians
    contacts = roster.get("contacts", [])
    contacts_count = 0
    if contacts and students:
        contact_map = extract_parent_contacts(contacts, students)
        if contact_map:
            persist_parent_contacts(contact_map, teacher_id)
            contacts_count = len(contact_map)

    # Extract accommodation suggestions (teacher reviews before applying)
    accomm_data = extract_student_accommodations(students)

    # Sync to Supabase (class-based student portal)
    if sections:
        _sync_classes_to_db(sections, students, teacher_id)

    _clever_audit("clever_roster_sync",
                  f"Synced {len(students)} students, {len(sections)} sections",
                  teacher_id)

    # Return all available sections so the frontend can show a selection UI
    all_sections_mapped = map_sections_to_periods(roster.get("sections", []))

    return jsonify({
        "status": "synced",
        "counts": {
            "teachers": len(roster.get("teachers", [])),
            "students": len(students),
            "sections": len(sections),
            "students_with_accommodations": len(accomm_data),
            "parent_contacts": contacts_count,
        },
        "accommodation_suggestions": accomm_data,
        "available_sections": all_sections_mapped,
    })


@clever_bp.route("/api/clever/apply-accommodations", methods=["POST"])
def clever_apply_accommodations():
    """Apply Clever-sourced IEP/ELL flags as Graider accommodation presets.

    The teacher has reviewed and optionally modified the suggestions.
    Body: {
        "accommodations": {
            "student_clever_id": {
                "name": "Jane Doe",
                "suggested_presets": ["simplified_language", "ell_support"],
                "custom_notes": "",
                "home_language": "Spanish",
            },
            ...
        }
    }
    """
    if not session.get("clever_user"):
        return jsonify({"error": "Clever session required"}), 401

    data = request.json or {}
    accommodations = data.get("accommodations", {})
    teacher_id = getattr(g, "user_id", "local-dev")

    applied = 0
    errors = []

    for student_id, info in accommodations.items():
        preset_ids = info.get("suggested_presets", [])
        name = info.get("name", "")
        custom_notes = info.get("custom_notes", "")

        if info.get("ell_status") and info.get("home_language"):
            custom_notes += f"\nHome language: {info['home_language']}"

        try:
            success = set_student_accommodation(
                student_id=student_id,
                preset_ids=preset_ids,
                custom_notes=custom_notes.strip(),
                student_name=name,
                teacher_id=teacher_id,
            )
            if success:
                applied += 1
            else:
                errors.append(f"Failed to save for {student_id}")
        except Exception as e:
            logger.error("Error applying accommodation for %s: %s", student_id, str(e))
            errors.append(f"Error for {student_id}")

    _clever_audit("clever_apply_accommodations",
                  f"Applied {applied} accommodations",
                  teacher_id)

    return jsonify({
        "applied": applied,
        "total": len(accommodations),
        "errors": errors if errors else None,
    })


@clever_bp.route("/api/clever/delete-data", methods=["POST"])
def clever_delete_data():
    """Delete all Clever-sourced student data for the current teacher.

    Clever requires apps to support data deletion when a district disconnects.
    This endpoint removes roster CSVs, period files, parent contacts,
    and accommodation data sourced from Clever.
    """
    # Require active Clever session for data deletion
    if not session.get("clever_user"):
        return jsonify({"error": "Not authenticated via Clever"}), 403

    teacher_id = getattr(g, "user_id", "")
    if not teacher_id.startswith("clever:"):
        return jsonify({"error": "Not a Clever user"}), 403

    try:
        result = delete_clever_data(teacher_id)

        # Also delete Supabase records created by Clever sync
        try:
            sb = _get_supabase_safe()
            if sb:
                # Get classes for this teacher
                classes = sb.table('classes').select('id').eq('teacher_id', teacher_id).execute()
                class_ids = [c['id'] for c in (classes.data or [])]

                student_ids = []
                if class_ids:
                    # Delete student_submissions for these classes' content
                    content = sb.table('published_content').select('id').in_('class_id', class_ids).execute()
                    content_ids = [c['id'] for c in (content.data or [])]
                    if content_ids:
                        sb.table('student_submissions').delete().in_('content_id', content_ids).execute()
                        sb.table('published_content').delete().in_('id', content_ids).execute()

                    # Delete enrollments
                    for cid in class_ids:
                        sb.table('class_students').delete().eq('class_id', cid).execute()

                    # Get student IDs for this teacher
                    students_res = sb.table('students').select('id').eq('teacher_id', teacher_id).execute()
                    student_ids = [s['id'] for s in (students_res.data or [])]
                    if student_ids:
                        for sid in student_ids:
                            sb.table('student_sessions').delete().eq('student_id', sid).execute()
                        sb.table('students').delete().eq('teacher_id', teacher_id).execute()

                    # Delete classes
                    sb.table('classes').delete().eq('teacher_id', teacher_id).execute()

                result["supabase_deleted"] = {
                    "classes": len(class_ids),
                    "students": len(student_ids),
                }
                logger.info("AUDIT: Clever Supabase data deleted for %s: %s", teacher_id, result.get("supabase_deleted"))
        except Exception as sb_err:
            logger.error("Supabase deletion failed for %s: %s", teacher_id, str(sb_err))
            result["supabase_error"] = "Partial deletion — local files removed, Supabase cleanup failed"

        _clever_audit("clever_data_deletion", f"Deleted: {result}", teacher_id)
        logger.info("Clever data deletion for %s: %s", teacher_id, result)
        return jsonify({"status": "deleted", "deleted": result})
    except Exception as e:
        logger.error("Clever data deletion failed for %s: %s", teacher_id, str(e))
        return jsonify({"error": "An internal error occurred"}), 500


@clever_bp.route("/api/clever/district-keys", methods=["GET"])
def clever_district_keys_status():
    """Check which API keys are configured at the district level."""
    clever_user = session.get("clever_user")
    if not clever_user:
        return jsonify({"error": "Not authenticated via Clever"}), 403

    district_id = clever_user.get("district", "")
    if not district_id:
        return jsonify({"error": "No district associated"}), 400

    from backend.api_keys import check_district_keys
    status = check_district_keys(district_id)
    return jsonify({"district_id": district_id, "keys": status})


@clever_bp.route("/api/clever/district-keys", methods=["POST"])
def clever_save_district_keys():
    """Save district-level API keys. Only district_admin users can do this.

    Body: { "openai": "sk-...", "anthropic": "sk-ant-...", "gemini": "AI..." }
    Empty strings are ignored (won't overwrite existing keys).
    """
    clever_user = session.get("clever_user")
    if not clever_user:
        return jsonify({"error": "Not authenticated via Clever"}), 403

    # Only district admins can set district-wide keys
    if clever_user.get("type") != "district_admin":
        return jsonify({"error": "Only district administrators can manage district API keys"}), 403

    district_id = clever_user.get("district", "")
    if not district_id:
        return jsonify({"error": "No district associated"}), 400

    data = request.get_json(silent=True) or {}
    keys = {}
    for provider in ("openai", "anthropic", "gemini"):
        val = data.get(provider, "").strip()
        if val:
            keys[provider] = val

    if not keys:
        return jsonify({"error": "No API keys provided"}), 400

    from backend.api_keys import save_district_keys
    ok = save_district_keys(district_id, keys)
    if ok:
        teacher_id = resolve_clever_user_id(clever_user.get("clever_id", ""))
        _clever_audit("clever_district_keys_saved",
                      "District API keys updated",
                      teacher_id)
        logger.info("District API keys updated by %s for district %s",
                     clever_user.get("email"), district_id)
        return jsonify({"status": "saved", "district_id": district_id})
    else:
        return jsonify({"error": "Failed to save district keys"}), 500


@clever_bp.route("/api/clever/student-token", methods=["POST"])
def exchange_student_auth_code():
    """Exchange a short-lived auth code for a student session token."""
    data = request.json or {}
    code = data.get("code", "")

    if not code or code not in _pending_student_auth_codes:
        return jsonify({"error": "Invalid or expired code"}), 401

    entry = _pending_student_auth_codes.pop(code)
    if _time.time() > entry["expires"]:
        return jsonify({"error": "Code expired"}), 401

    return jsonify({"token": entry["token"]})


@clever_bp.route("/api/clever/health", methods=["GET"])
def clever_health():
    """Health check for Clever integration — verifies config and connectivity."""
    config = get_clever_config()
    health = {
        "configured": config is not None,
        "client_id_set": bool(os.getenv("CLEVER_CLIENT_ID")),
        "client_secret_set": bool(os.getenv("CLEVER_CLIENT_SECRET")),
        "redirect_uri_set": bool(os.getenv("CLEVER_REDIRECT_URI")),
        "district_token_set": bool(os.getenv("CLEVER_DISTRICT_TOKEN")),
        "api_version": os.getenv("CLEVER_API_VERSION", "v3.0"),
    }

    # Check Supabase connectivity for class sync
    sb = _get_supabase_safe()
    health["supabase_available"] = sb is not None

    status_code = 200 if health["configured"] else 503
    return jsonify(health), status_code


@clever_bp.route("/api/clever/logout", methods=["POST"])
def clever_logout():
    """Clear the Clever session."""
    session.pop("clever_user", None)
    return jsonify({"status": "logged_out"})
