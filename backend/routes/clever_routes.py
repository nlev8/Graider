"""
Clever SSO and Secure Sync routes.
"""
import hashlib
import hmac
import os
import asyncio
import logging
import secrets
import threading
import time as _time

import sentry_sdk
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
from backend.auth import (
    load_clever_links,
    resolve_clever_user_id,
    resolve_clever_user_id_or_create,
)
from backend.roster_sync import sync_roster_to_db as _shared_sync_roster_to_db
from backend.supabase_client import get_supabase as _get_supabase_safe
from backend.utils.errors import handle_route_errors
from backend.utils.auth_decorators import require_clever_session
from backend.utils.redaction import redact_email
from backend.services.clever_roster_scope import filter_roster_to_teacher

logger = logging.getLogger(__name__)

clever_bp = Blueprint("clever", __name__)


def _clever_audit(action, details="", teacher_id=""):
    """FERPA audit log for Clever operations.

    Round-2 Codex HIGH fold (PR #227): delegates to the central
    `backend.utils.audit.audit_log` so the redaction helper is applied
    uniformly. Previously this function wrote a Supabase row directly,
    bypassing `_redact_for_audit()`.

    Round-3 Codex HIGH fold (PR #227): the operations debug logger.info
    line previously emitted RAW `details` BEFORE central redaction ran.
    With Sentry's default logging breadcrumbs, raw audit details could
    reach Sentry exception capture even though `audit_log()` itself is
    redaction-safe. Now we redact via `_redact_for_audit` BEFORE the
    logger.info so the logger / breadcrumb path can never see raw PII.
    """
    from backend.utils.audit import audit_log as _central_audit_log
    from backend.utils.audit import _redact_for_audit
    safe_details = _redact_for_audit(details)
    logger.info("AUDIT: %s | teacher=%s | %s", action, teacher_id, safe_details)
    _central_audit_log(action, details, user="teacher", teacher_id=teacher_id)

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


# Short-lived class-selection tokens for the multi-enrollment Clever SSO
# disambiguation flow (Task A). Mirrors the _pending_student_auth_codes
# pattern above: in-process, TTL-bounded, inline cleanup. Same
# not-shared-across-workers property as the auth-code store (acceptable —
# the pick round-trip is immediate; a shared store is a separate baseline
# item, not Task A's scope).
_pending_class_selections = {}
_CLASS_SELECTION_TTL = 120  # seconds


def _public_candidates(candidates):
    """Browser-safe projection of selection candidates — strips the
    server-only `_student_row` (PII) so the picker never sees it
    (Task C/C1)."""
    return [
        {"class_id": c["class_id"], "name": c.get("name", ""),
         "subject": c.get("subject", "")}
        for c in candidates
    ]


def _create_class_selection(candidates):
    """Mint a short-lived token the student exchanges (with a chosen
    class_id) for a real scoped session. Returns the raw token.

    Task C/C1: each candidate carries its own `_student_row` (a Clever
    student may exist under multiple teachers' rosters), so the finalize
    endpoint mints against the row that owns the chosen class."""
    code = secrets.token_urlsafe(32)
    _pending_class_selections[code] = {
        "candidates": candidates,
        "expires": _time.time() + _CLASS_SELECTION_TTL,
    }
    now = _time.time()
    expired = [k for k, v in _pending_class_selections.items() if v["expires"] < now]
    for k in expired:
        del _pending_class_selections[k]
    return code


def _mint_clever_student_session(sb, student_row, chosen):
    """Insert a hashed `student_sessions` row for `student_row` scoped to
    `chosen` ({class_id,name,subject}) and return {token,student,class}.

    Shared by the single-enrollment path and the multi-enrollment finalize
    endpoint so the session-mint stays identical and secure in both.
    """
    import secrets as _secrets
    from datetime import datetime, timezone, timedelta

    raw_token = _secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=8)

    sb.table("student_sessions").insert({
        "student_id": student_row["id"],
        "class_id": chosen["class_id"],
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
            "name": chosen.get("name", ""),
            "subject": chosen.get("subject", ""),
        },
    }


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _sync_classes_to_db(sections, students, teacher_id):
    """Normalise Clever data and delegate to shared roster sync.

    Converts Clever's ``{data: {...}}`` wrapper format into the provider-agnostic
    shape expected by ``sync_roster_to_db`` and calls it.

    Args:
        sections: List of Clever section dicts (with 'data' wrapper).
        students: List of Clever student dicts (with 'data' wrapper).
        teacher_id: Graider teacher ID (may be 'clever:xxx' format).

    Returns:
        Counts dict from sync_roster_to_db: {"classes": int, "students": int, "enrollments": int}.
    """
    # Build a lookup from clever student id -> unwrapped student record
    student_map = {}
    for s in students:
        sd = s.get("data", s)
        sid = sd.get("id")
        if sid:
            student_map[sid] = sd

    # Normalise classes
    norm_classes = []
    section_data_map = {}
    for section in sections:
        sec = section.get("data", section)
        clever_section_id = sec.get("id")
        if not clever_section_id:
            continue
        section_data_map[clever_section_id] = sec
        norm_classes.append({
            "external_id": clever_section_id,
            "name": sec.get("name", ""),
            "subject": sec.get("subject", ""),
            "grade_level": sec.get("grade", ""),
        })

    # Normalise students and build enrollment pairs
    norm_students = []
    seen_students = set()
    enrollment_pairs = []
    for clever_section_id, sec in section_data_map.items():
        for clever_student_id in sec.get("students", []):
            sd = student_map.get(clever_student_id)
            if not sd:
                continue
            enrollment_pairs.append((clever_section_id, clever_student_id))
            if clever_student_id not in seen_students:
                seen_students.add(clever_student_id)
                name = sd.get("name", {})
                norm_students.append({
                    "external_id": clever_student_id,
                    "first_name": name.get("first", ""),
                    "last_name": name.get("last", ""),
                    "email": sd.get("email", ""),
                })

    return _shared_sync_roster_to_db(norm_classes, norm_students, enrollment_pairs, teacher_id, provider="clever")


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
    from datetime import datetime, timezone, timedelta

    sb = _get_supabase_safe()
    if sb is None:
        logger.debug("Supabase not configured — cannot create student session")
        return None

    try:
        # Look up the student by Clever ID. A Clever student can exist as
        # MULTIPLE `students` rows — the same kid imported by several
        # teachers' rosters. Task C/C1: enumerate ALL matching rows (NOT
        # res.data[0] first-row-wins, the residual the closing re-score
        # found Task A left open) and disambiguate when the resulting
        # (student_row × class) set is ambiguous. teacher_id is unknown
        # during student SSO, so a student-facing picker is the correct fix.
        res = sb.table("students").select("*").eq("student_id_number", clever_id).execute()
        student_rows = list(res.data) if res and res.data else []

        # Fallback: look up by email
        if not student_rows and email:
            res2 = sb.table("students").select("*").eq("email", email).execute()
            student_rows = list(res2.data) if res2 and res2.data else []

        if not student_rows:
            logger.info("Clever student not found: email=%s clever_id_hash=%s",
                        redact_email(email),
                        hashlib.sha256(str(clever_id).encode()).hexdigest()[:8])
            return None

        _cid_hash = hashlib.sha256(str(clever_id).encode()).hexdigest()[:8]

        # Build candidates across ALL student rows; each carries its own
        # student_row so the finalize endpoint mints against the row that
        # owns the chosen class. Dedupe by class_id (globally unique).
        candidates = []
        _seen_cids = set()
        for srow in student_rows:
            srow_id = srow.get("id")
            if not srow_id:
                continue
            enroll_res = (
                sb.table("class_students")
                .select("class_id, classes(id, name, subject)")
                .eq("student_id", srow_id)
                .execute()
            )
            for er in (enroll_res.data if enroll_res and enroll_res.data else []):
                ci = er.get("classes") or {}
                cid = ci.get("id") or er.get("class_id")
                if not cid or cid in _seen_cids:
                    continue
                _seen_cids.add(cid)
                candidates.append({
                    "class_id": cid,
                    "name": ci.get("name", ""),
                    "subject": ci.get("subject", ""),
                    "_student_row": srow,
                })

        if not candidates:
            logger.info("Clever student (clever_id_hash=%s) has no class enrollment", _cid_hash)
            return None

        if len(candidates) > 1:
            # Ambiguous — do NOT mint a session. Return a short-lived
            # selection token; the student picks via the finalize endpoint.
            selection_token = _create_class_selection(candidates)
            logger.info(
                "Clever student (clever_id_hash=%s) has %d class options — needs selection",
                _cid_hash, len(candidates),
            )
            return {
                "status": "needs_class_selection",
                "classes": _public_candidates(candidates),
                "selection_token": selection_token,
            }

        # Exactly one (student_row, class) — mint against the owning row.
        chosen = candidates[0]
        return _mint_clever_student_session(sb, chosen["_student_row"], chosen)
    except Exception as e:
        logger.warning("Failed to create clever student session: %s", str(e))
        sentry_sdk.capture_exception(e)
        return None


def _background_roster_sync(district_token, teacher_id):
    """Run roster sync in a background thread so OAuth callback returns immediately."""
    try:
        roster = _run_async(sync_roster(district_token))

        # Scope to this teacher's sections (2026-05-14 dimensional review
        # S2, background-sync variant per Codex revised-plan review). Same
        # helper as the manual route + periodic cron.
        if teacher_id.startswith("clever:"):
            teacher_clever_id = teacher_id[len("clever:"):]
        else:
            links = load_clever_links()
            teacher_clever_id = next(
                (cid for cid, tid in links.items() if tid == teacher_id),
                None,
            )
        if not teacher_clever_id:
            logger.warning(
                "Background roster sync skipped: could not resolve "
                "Clever ID for teacher_hash=%s",
                hashlib.sha256(str(teacher_id).encode()).hexdigest()[:8],
            )
            return
        sections, students = filter_roster_to_teacher(roster, teacher_clever_id)

        if students:
            persist_roster_as_csv(students, teacher_id)
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
        sentry_sdk.capture_exception(e)


@clever_bp.route("/api/clever/login-url", methods=["GET"])
@handle_route_errors
def clever_login_url():
    """Return the Clever OAuth authorization URL."""
    config = get_clever_config()
    if not config:
        # In redirect mode (top-level nav from the landing page) a JSON body
        # would render as a raw page; bounce to a friendly error instead.
        if request.args.get("redirect"):
            return redirect("/?clever_error=not_configured")
        return jsonify({"error": "Clever not configured"}), 503

    state = secrets.token_urlsafe(32)
    session["clever_oauth_state"] = state
    url = get_authorize_url(state=state)
    # ?redirect=1 → 302 straight to the provider instead of returning JSON.
    # Used by the cross-origin landing page (graider.live): a top-level
    # navigation to this endpoint sets the session cookie first-party for
    # app.graider.live (a cross-origin fetch would discard it), so the OAuth
    # state survives to the callback.
    if request.args.get("redirect"):
        return redirect(url)
    return jsonify({"url": url})


@clever_bp.route("/api/clever/callback", methods=["GET"])
@handle_route_errors
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
    # Clever Portal/Instant Login sends users directly to callback without state.
    # Three cases:
    #   1. We set state AND Clever returned it → must match (normal OAuth flow)
    #   2. Neither side has state → Instant Login, allow (no CSRF risk, code is single-use)
    #   3. One side has state but not the other → session lost or spoofed, reject
    expected_state = session.pop("clever_oauth_state", None)
    if expected_state and state:
        # Normal flow — both sides have state, must match.
        # Use hmac.compare_digest for constant-time compare (issue #373,
        # closes 2026-05-14 dimensional-review state/nonce variant).
        if not hmac.compare_digest(state.encode("utf-8"),
                                   expected_state.encode("utf-8")):
            logger.warning("Clever OAuth state mismatch")
            return redirect("/?clever_error=state_mismatch")
    elif expected_state or state:
        # One side has state, other doesn't — session lost or spoofed
        logger.warning("Clever OAuth state mismatch (expected=%s, got=%s)",
                       bool(expected_state), bool(state))
        return redirect("/?clever_error=state_mismatch")
    # else: neither has state — Instant Login flow, proceed

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
        if student_session and student_session.get("status") == "needs_class_selection":
            # Multi-enrolled — hand the student to the class picker instead
            # of silently choosing for them (Task A). No session minted yet.
            from urllib.parse import urlencode
            params = urlencode({
                "clever_select": "1",
                "sel": student_session["selection_token"],
            })
            logger.info(
                "AUDIT: Clever student multi-enrollment, selection required: "
                "email=%s clever_id_hash=%s",
                redact_email(clever_user.get("email", "")),
                hashlib.sha256(str(clever_user["clever_id"]).encode()).hexdigest()[:8],
            )
            return redirect("/student?" + params)
        if student_session:
            from urllib.parse import urlencode
            auth_code = _create_student_auth_code(student_session["token"])
            params = urlencode({
                "clever": "1",
                "code": auth_code,
            })
            logger.info("AUDIT: Clever student login: email=%s clever_id_hash=%s",
                        redact_email(clever_user.get("email", "")),
                        hashlib.sha256(str(clever_user["clever_id"]).encode()).hexdigest()[:8])
            return redirect("/student?" + params)
        else:
            logger.info("AUDIT: Clever student login failed (not enrolled): email=%s clever_id_hash=%s",
                        redact_email(clever_user.get("email", "")),
                        hashlib.sha256(str(clever_user["clever_id"]).encode()).hexdigest()[:8])
            return redirect("/?clever_error=student_not_enrolled")

    # Any non-student Clever user can access the teacher dashboard
    # (teacher, district_admin, school_admin, staff, contact, etc.)
    if clever_user["type"] == "student":
        # Already handled above — this is a safety net
        return redirect("/?clever_error=students_use_portal")
    logger.info("AUDIT: Clever login accepted: type=%s email=%s clever_id_hash=%s",
                clever_user["type"],
                redact_email(clever_user.get("email", "")),
                hashlib.sha256(str(clever_user.get("clever_id", "")).encode()).hexdigest()[:8])

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

    # Resolve to a real Supabase UUID (link-or-create), failing OPEN to clever:{id}
    # so a >1-match / outage never blocks a currently-working teacher.
    clever_id = clever_user["clever_id"]
    clever_email = clever_user.get("email", "")
    resolved_id, outcome = resolve_clever_user_id_or_create(
        clever_id, clever_email, clever_user.get("name"))
    is_uuid = not str(resolved_id).startswith("clever:")
    if is_uuid:
        session["clever_user"]["user_id"] = resolved_id
    logger.info("Clever teacher resolve: outcome=%s linked=%s", outcome, is_uuid)

    # Trigger BACKGROUND roster sync on login (Clever requires daily data updates;
    # login-triggered sync satisfies this requirement). Runs in a separate thread
    # so the OAuth redirect returns immediately. UUID-only: a legacy clever:{id}
    # outcome must never start the DB roster sync.
    from backend.api_keys import resolve_clever_district_token
    district_token = resolve_clever_district_token(clever_user.get("district", "") or None)
    if district_token and is_uuid:
        thread = threading.Thread(
            target=_background_roster_sync,
            args=(district_token, resolved_id),
            daemon=True,
        )
        thread.start()

    logger.info("AUDIT: Clever teacher login: email=%s type=%s district=%s clever_id_hash=%s",
                redact_email(clever_user.get("email")),
                clever_user["type"],
                clever_user.get("district", ""),
                hashlib.sha256(str(clever_user["clever_id"]).encode()).hexdigest()[:8])
    return redirect("/?clever_login=success")


@clever_bp.route("/api/clever/session", methods=["GET"])
@handle_route_errors
def clever_session_check():
    """Return current Clever session info (if logged in via Clever)."""
    clever_user = session.get("clever_user")
    if not clever_user:
        return jsonify({"authenticated": False})
    resolved_id = clever_user.get("user_id") or resolve_clever_user_id(clever_user["clever_id"])

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
        logger.warning("clever roster last-sync time lookup failed", exc_info=True)

    return jsonify({
        "authenticated": True,
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user.get("type", ""),
        "district": clever_user.get("district", ""),
        "user_id": resolved_id,
        "account_linked": not resolved_id.startswith("clever:"),
        "last_sync": last_sync_time,
    })


@clever_bp.route("/api/clever/sync-roster", methods=["POST"])
@require_clever_session
@handle_route_errors
def clever_sync_roster():
    """Trigger a roster sync from Clever.

    Pulls students and sections, persists them to ROSTERS_DIR and PERIODS_DIR
    (same format as manual CSV upload), and returns accommodation suggestions.

    Optional body: { "section_ids": ["id1", "id2"] } to sync only specific sections.
    If omitted, syncs all sections.
    """
    from backend.api_keys import resolve_clever_district_token
    district_token = resolve_clever_district_token(g.clever_user.get("district", "") or None)
    if not district_token:
        return jsonify({"error": "District token not configured"}), 503

    teacher_id = g.teacher_id
    data = request.get_json(silent=True) or {}
    selected_section_ids = data.get("section_ids")  # None = all sections

    try:
        roster = _run_async(sync_roster(district_token))
    except Exception as e:
        logger.error("Clever roster sync failed: %s", str(e))
        return jsonify({"error": "Failed to sync roster from Clever"}), 502

    # SECURITY: scope roster to this teacher's own sections + students.
    # Previously, students was only filtered when selected_section_ids was
    # provided — a teacher syncing without a section filter received the
    # full district roster (2026-05-14 dimensional review S2).
    clever_user = session.get("clever_user", {})
    teacher_clever_id = clever_user.get("clever_id", "")
    own_sections, own_students = filter_roster_to_teacher(roster, teacher_clever_id)
    # Mutate roster["sections"] so the downstream map_sections_to_periods
    # call (~line 568) returns only own sections in the response payload,
    # not the full district (Codex revised-plan review Q4).
    roster["sections"] = own_sections
    if teacher_clever_id:
        logger.info(
            "Filtered roster for teacher_hash=%s: %d sections, %d students "
            "(district had %d sections total)",
            hashlib.sha256(str(teacher_clever_id).encode()).hexdigest()[:8],
            len(own_sections),
            len(own_students),
            len(roster.get("sections", [])) if not own_sections else len(own_sections),
        )

    # Optional secondary filter: teacher selected a subset of their own sections
    sections = own_sections
    students = own_students
    if selected_section_ids is not None:
        selected_set = set(selected_section_ids)
        sections = [s for s in sections if s.get("data", s).get("id", "") in selected_set]
        section_student_ids = set()
        for s in sections:
            sd = s.get("data", s)
            section_student_ids.update(sd.get("students", []))
        students = [st for st in own_students
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
@require_clever_session
@handle_route_errors
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
    data = request.json or {}
    accommodations = data.get("accommodations", {})
    teacher_id = g.teacher_id

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
            logger.error("Error applying accommodation for %s: %s",
                         hashlib.sha256(str(student_id).encode()).hexdigest()[:8], e)
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
@require_clever_session
@handle_route_errors
def clever_delete_data():
    """Delete all Clever-sourced student data for the current teacher.

    Clever requires apps to support data deletion when a district disconnects.
    This endpoint removes roster CSVs, period files, parent contacts,
    and accommodation data sourced from Clever.
    """
    # @require_clever_session already guarantees a Clever session; gate on its
    # presence (NOT the id prefix — UUID-linked Clever teachers have a non-
    # 'clever:' teacher_id but are still Clever users entitled to delete).
    if not g.get("clever_user"):
        return jsonify({"error": "Not a Clever user"}), 403
    teacher_id = g.teacher_id
    clever_id = g.clever_user.get("clever_id", "")

    try:
        result = delete_clever_data(teacher_id)
        # FERPA: also purge any legacy clever:{id}-keyed data written BEFORE this
        # teacher was linked to a UUID. delete_clever_data -> delete_roster_data
        # deletes roster CSVs AND the Supabase roster rows it keys by teacher_id
        # (classes/students/student_sessions/published_content/student_submissions
        # /class_students), so this second call closes the gap where pre-link
        # rows keyed clever:{id} would otherwise survive a UUID-only delete
        # (_claim_clever_text_data only re-keys teacher_data/published_assessments
        # /student_history, and only on the create path). NOT covered here:
        # legacy-keyed period or parent-contact files — pre-existing scope gap.
        # No-op when no legacy data exists.
        if clever_id and not str(teacher_id).startswith("clever:"):
            try:
                result["legacy_cleanup"] = delete_clever_data(f"clever:{clever_id}")
            except Exception as e:
                logger.warning("Legacy Clever cleanup failed (non-fatal): %s", type(e).__name__)
                sentry_sdk.capture_exception(e)
                result["legacy_cleanup_error"] = type(e).__name__

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
            sentry_sdk.capture_exception(sb_err)
            result["supabase_error"] = "Partial deletion — local files removed, Supabase cleanup failed"

        _clever_audit("clever_data_deletion", f"Deleted: {result}", teacher_id)
        logger.info("Clever data deletion for %s: %s", teacher_id, result)
        return jsonify({"status": "deleted", "deleted": result})
    except Exception as e:
        logger.error("Clever data deletion failed for %s: %s", teacher_id, str(e))
        return jsonify({"error": "An internal error occurred"}), 500


@clever_bp.route("/api/clever/district-keys", methods=["GET"])
@require_clever_session
@handle_route_errors
def clever_district_keys_status():
    """Check which API keys are configured at the district level."""
    clever_user = g.clever_user

    district_id = clever_user.get("district", "")
    if not district_id:
        return jsonify({"error": "No district associated"}), 400

    from backend.api_keys import check_district_keys
    status = check_district_keys(district_id)
    return jsonify({"district_id": district_id, "keys": status})


@clever_bp.route("/api/clever/district-keys", methods=["POST"])
@require_clever_session
@handle_route_errors
def clever_save_district_keys():
    """Save district-level API keys. Only district_admin users can do this.

    Body: { "openai": "sk-...", "anthropic": "sk-ant-...", "gemini": "AI..." }
    Empty strings are ignored (won't overwrite existing keys).
    """
    clever_user = g.clever_user

    # Only district admins can set district-wide keys
    if clever_user.get("type") != "district_admin":
        return jsonify({"error": "Only district administrators can manage district API keys"}), 403

    district_id = clever_user.get("district", "")
    if not district_id:
        return jsonify({"error": "No district associated"}), 400

    data = request.get_json(silent=True) or {}
    keys = {}
    # clever_district_token (Task C / C3): lets a district admin set the
    # Clever Secure-Sync roster token so multi-district sync works
    # end-to-end (resolve_clever_district_token now has a write path).
    for provider in ("openai", "anthropic", "gemini", "clever_district_token"):
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
                     redact_email(clever_user.get("email", "")), district_id)
        return jsonify({"status": "saved", "district_id": district_id})
    else:
        return jsonify({"error": "Failed to save district keys"}), 500


@clever_bp.route("/api/clever/select-class", methods=["GET", "POST"])
@handle_route_errors
def select_clever_class():
    """Multi-enrollment Clever SSO finalize (Task A).

    GET  ?selection_token=…  → list the candidate classes for the picker
                               (does NOT consume the token).
    POST {selection_token, class_id} → mint the scoped session.

    Mirrors /api/clever/student-token. Single-use on success only — a bad
    class_id (400) does NOT consume the token so the student can retry.
    """
    if request.method == "GET":
        token = request.args.get("selection_token", "")
    else:
        data = request.json or {}
        token = data.get("selection_token", "")
        class_id = data.get("class_id", "")

    entry = _pending_class_selections.get(token)
    if not entry:
        return jsonify({"error": "Invalid or expired selection"}), 401
    if _time.time() > entry["expires"]:
        _pending_class_selections.pop(token, None)
        return jsonify({"error": "Selection expired"}), 401

    if request.method == "GET":
        return jsonify({"classes": _public_candidates(entry["candidates"])})

    chosen = next((c for c in entry["candidates"] if c["class_id"] == class_id), None)
    if chosen is None:
        return jsonify({"error": "Class not among offered choices"}), 400

    sb = _get_supabase_safe()
    if sb is None:
        return jsonify({"error": "Supabase not configured"}), 503

    # Task C/C1: mint against the student_row that owns the chosen class
    # (candidates carry _student_row). Fall back to a legacy top-level
    # student_row for any pre-C1 stored entry shape (defensive).
    mint_row = chosen.get("_student_row") or entry.get("student_row")
    session_info = _mint_clever_student_session(sb, mint_row, chosen)
    _pending_class_selections.pop(token, None)  # single-use, success only
    return jsonify({"token": session_info["token"]})


@clever_bp.route("/api/clever/student-token", methods=["POST"])
@handle_route_errors
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
@handle_route_errors
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
@handle_route_errors
def clever_logout():
    """Clear the Clever session."""
    session.pop("clever_user", None)
    return jsonify({"status": "logged_out"})
