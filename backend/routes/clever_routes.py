"""
Clever SSO and Secure Sync routes.
"""
import os
import asyncio
import logging
import secrets

from flask import Blueprint, request, jsonify, redirect, session, g

from backend.clever import (
    get_clever_config,
    get_authorize_url,
    exchange_code_for_token,
    get_clever_user,
    sync_roster,
    extract_student_accommodations,
    persist_roster_as_csv,
    persist_sections_as_periods,
)
from backend.accommodations import set_student_accommodation

logger = logging.getLogger(__name__)

clever_bp = Blueprint("clever", __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
    expected_state = session.pop("clever_oauth_state", None)
    if expected_state and state != expected_state:
        logger.warning("Clever OAuth state mismatch")
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

    # Only allow teachers and district admins
    if clever_user["type"] not in ("teacher", "district_admin", "staff"):
        return redirect("/?clever_error=students_use_portal")

    # Store Clever session info
    session["clever_user"] = {
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user["type"],
        "district": clever_user.get("district", ""),
        # Do NOT store access_token in session — it's short-lived
        # and only needed for the initial user fetch
    }

    logger.info("Clever SSO login: %s (%s)", clever_user.get("email"), clever_user["type"])
    return redirect("/?clever_login=success")


@clever_bp.route("/api/clever/session", methods=["GET"])
def clever_session_check():
    """Return current Clever session info (if logged in via Clever)."""
    clever_user = session.get("clever_user")
    if not clever_user:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "clever_id": clever_user["clever_id"],
        "email": clever_user.get("email", ""),
        "name": clever_user.get("name", {}),
        "type": clever_user.get("type", ""),
        "district": clever_user.get("district", ""),
    })


@clever_bp.route("/api/clever/sync-roster", methods=["POST"])
def clever_sync_roster():
    """Trigger a roster sync from Clever.

    Pulls students and sections, persists them to ROSTERS_DIR and PERIODS_DIR
    (same format as manual CSV upload), and returns accommodation suggestions.
    """
    district_token = os.getenv("CLEVER_DISTRICT_TOKEN")
    if not district_token:
        return jsonify({"error": "District token not configured"}), 503

    teacher_id = getattr(g, "user_id", "local-dev")

    roster = _run_async(sync_roster(district_token))

    # Persist roster to CSV (same location as manual upload)
    students = roster.get("students", [])
    if students:
        persist_roster_as_csv(students, teacher_id)

    # Persist sections as periods (same location as manual period creation)
    sections = roster.get("sections", [])
    if sections:
        persist_sections_as_periods(sections, teacher_id)

    # Extract accommodation suggestions (teacher reviews before applying)
    accomm_data = extract_student_accommodations(students)

    return jsonify({
        "status": "synced",
        "counts": {
            "teachers": len(roster.get("teachers", [])),
            "students": len(students),
            "sections": len(sections),
            "students_with_accommodations": len(accomm_data),
        },
        "accommodation_suggestions": accomm_data,
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
            errors.append(f"Error for {student_id}: {str(e)}")

    return jsonify({
        "applied": applied,
        "total": len(accommodations),
        "errors": errors if errors else None,
    })


@clever_bp.route("/api/clever/logout", methods=["POST"])
def clever_logout():
    """Clear the Clever session."""
    session.pop("clever_user", None)
    return jsonify({"status": "logged_out"})
