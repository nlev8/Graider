"""
OneRoster API routes for Graider.

Provides config management, connectivity testing, roster sync,
accommodation application, and data deletion endpoints.
"""
import asyncio
import logging

import sentry_sdk
from flask import Blueprint, request, jsonify, g

from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config
from backend.roster_sync import sync_roster_to_db
from backend.services.oneroster_gradebook import ensure_line_item, post_results
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

logger = logging.getLogger(__name__)

oneroster_bp = Blueprint("oneroster", __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── GET /api/oneroster/config ──────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/config", methods=["GET"])
@require_teacher
@handle_route_errors
def get_config():
    """Return OneRoster config status (never exposes secrets)."""
    cfg = get_oneroster_config(g.teacher_id)
    if not cfg:
        return jsonify({
            "configured": False,
            "base_url": "",
            "school_id": "",
            "teacher_sourced_id": "",
            "token_url": "",
            "has_credentials": False,
        })

    return jsonify({
        "configured": True,
        "base_url": cfg.get("base_url", ""),
        "school_id": cfg.get("school_id", ""),
        "teacher_sourced_id": cfg.get("teacher_sourced_id", ""),
        "token_url": cfg.get("token_url", ""),
        "has_credentials": bool(cfg.get("client_id") and cfg.get("client_secret")),
    })


# ── POST /api/oneroster/config ─────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/config", methods=["POST"])
@require_teacher
@handle_route_errors
def save_config():
    """Save OneRoster configuration."""
    from backend.storage import save as _storage_save
    from backend.utils.audit import audit_log

    data = request.get_json(silent=True) or {}

    base_url = data.get("base_url", "").strip()
    client_id = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()
    teacher_sourced_id = data.get("teacher_sourced_id", "").strip()

    if not base_url or not client_id or not client_secret or not teacher_sourced_id:
        return jsonify({"error": "base_url, client_id, client_secret, and teacher_sourced_id are required"}), 400

    config = {
        "base_url": base_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": data.get("token_url", "").strip() or None,
        "school_id": data.get("school_id", "").strip() or None,
        "teacher_sourced_id": teacher_sourced_id,
    }

    _storage_save("oneroster_config", config, g.teacher_id)
    audit_log("ONEROSTER_CONFIG_SAVED", "OneRoster config saved", teacher_id=g.teacher_id)

    return jsonify({"status": "saved"})


# ── POST /api/oneroster/test ───────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/test", methods=["POST"])
@require_teacher
@handle_route_errors
def test_connection():
    """Test OneRoster API connectivity."""
    cfg = get_oneroster_config(g.teacher_id)
    if not cfg:
        return jsonify({"error": "OneRoster not configured"}), 400

    client = OneRosterClient(
        base_url=cfg["base_url"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        token_url=cfg.get("token_url"),
    )

    try:
        # Try to fetch one class to verify connectivity
        async def _test():
            async with __import__("httpx").AsyncClient(timeout=15.0) as http:
                await client._ensure_token(http)
                url = f"{client.base_url}/classes?limit=1"
                return await client._get_with_retry(http, url, label="test-connection")

        _run_async(_test())
        return jsonify({"status": "connected"})
    except Exception as e:
        logger.warning("OneRoster connection test failed: %s", str(e))
        return jsonify({"error": "Connection failed"}), 502


# ── POST /api/oneroster/sync-roster ───────────────────────────────────────

@oneroster_bp.route("/api/oneroster/sync-roster", methods=["POST"])
@require_teacher
@handle_route_errors
def sync_roster():
    """Sync roster from OneRoster API."""
    from backend.supabase_client import get_supabase as _get_supabase
    from backend.clever import persist_roster_as_csv, persist_sections_as_periods
    from backend.utils.audit import audit_log

    teacher_id = g.teacher_id

    # Provider exclusivity is enforced at the district level.
    # Guard: if a provider switch cleanup is in progress, block sync.
    # Lock has a 5-minute TTL — if the process died, the lock auto-expires.
    try:
        from backend.storage import load as _sl, save as _ss
        import time as _time
        cleanup_flag = _sl("district:provider_switch_in_progress", "system")
        if cleanup_flag:
            # Check TTL — expire after 5 minutes to prevent permanent lockout
            lock_time = cleanup_flag.get("timestamp", 0) if isinstance(cleanup_flag, dict) else 0
            if _time.time() - lock_time < 300:  # 5 minutes
                return jsonify({"error": "A provider switch is in progress. Please wait and try again."}), 503
            else:
                # Stale lock — clear it and proceed
                logger.warning("Stale provider switch lock detected (>5min old). Clearing.")
                _ss("district:provider_switch_in_progress", None, "system")
    except Exception as e:
        sentry_sdk.capture_exception(e)

    # Load config
    cfg = get_oneroster_config(teacher_id)
    if not cfg:
        return jsonify({"error": "OneRoster not configured"}), 400

    # Create client and fetch roster
    client = OneRosterClient(
        base_url=cfg["base_url"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        token_url=cfg.get("token_url"),
    )

    try:
        raw = _run_async(client.fetch_roster(
            school_id=cfg.get("school_id"),
            teacher_sourced_id=cfg.get("teacher_sourced_id"),
        ))
    except Exception as e:
        logger.error("OneRoster roster fetch failed: %s", str(e))
        return jsonify({"error": "Failed to fetch roster from OneRoster API"}), 502

    # Normalize and sync
    classes, students, enrollments, accommodations = normalize_roster(raw)

    # Convert enrollment dicts to tuples for sync_roster_to_db
    enrollment_tuples = [
        (e["class_external_id"], e["student_external_id"])
        for e in enrollments
    ]

    counts = sync_roster_to_db(classes, students, enrollment_tuples, teacher_id, provider="oneroster")

    # Persist as CSV for file compatibility (convert to Clever-like format)
    try:
        csv_students = [
            {"data": {
                "id": s.get("external_id", "").replace("oneroster:", ""),
                "name": {"first": s.get("first_name", ""), "last": s.get("last_name", "")},
                "email": s.get("email", ""),
            }}
            for s in students
        ]
        persist_roster_as_csv(csv_students, teacher_id)
    except Exception as e:
        logger.warning("Failed to persist OneRoster roster as CSV: %s", str(e))
        sentry_sdk.capture_exception(e)

    try:
        csv_sections = [
            {"data": {
                "id": c.get("external_id", "").replace("oneroster:", ""),
                "name": c.get("name", ""),
                "subject": c.get("subject", ""),
                "grade": c.get("grade_level", ""),
            }}
            for c in classes
        ]
        persist_sections_as_periods(csv_sections, teacher_id)
    except Exception as e:
        logger.warning("Failed to persist OneRoster sections as periods: %s", str(e))
        sentry_sdk.capture_exception(e)

    # Build accommodation suggestions
    accommodation_suggestions = {}
    for acc in accommodations:
        ext_id = acc.get("student_external_id", "")
        suggestions = []
        if acc.get("iep_status"):
            suggestions.append("modified_expectations")
            suggestions.append("chunked_feedback")
        if acc.get("ell_status"):
            suggestions.append("ell_support")
            suggestions.append("simplified_language")
        if suggestions:
            accommodation_suggestions[ext_id] = {
                "suggested_presets": suggestions,
                "iep_status": acc.get("iep_status"),
                "ell_status": acc.get("ell_status"),
                "home_language": acc.get("home_language"),
            }

    audit_log(
        "ONEROSTER_ROSTER_SYNCED",
        f"Synced {counts.get('classes', 0)} classes, {counts.get('students', 0)} students, "
        f"{counts.get('enrollments', 0)} enrollments",
        teacher_id=teacher_id,
    )

    return jsonify({
        "status": "synced",
        "counts": counts,
        "accommodation_suggestions": accommodation_suggestions,
    })


# ── POST /api/oneroster/apply-accommodations ──────────────────────────────

@oneroster_bp.route("/api/oneroster/apply-accommodations", methods=["POST"])
@require_teacher
@handle_route_errors
def apply_accommodations():
    """Apply IEP/ELL accommodation presets to students."""
    from backend.accommodations import set_student_accommodation

    data = request.get_json(silent=True) or {}
    accommodations = data.get("accommodations", {})

    if not accommodations:
        return jsonify({"error": "No accommodations provided"}), 400

    applied = 0
    for student_id, acc_data in accommodations.items():
        presets = acc_data.get("presets", [])
        notes = acc_data.get("notes", "")
        name = acc_data.get("name", "")
        set_student_accommodation(student_id, presets, notes, name, teacher_id=g.teacher_id)
        applied += 1

    return jsonify({"status": "applied", "count": applied})


# ── POST /api/oneroster/teacher-id ────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/teacher-id", methods=["POST"])
@require_teacher
@handle_route_errors
def save_teacher_id():
    """Save just the teacher's OneRoster sourcedId (used with district-level config)."""
    data = request.json or {}
    teacher_sourced_id = data.get("teacher_sourced_id", "").strip()
    if not teacher_sourced_id:
        return jsonify({"error": "teacher_sourced_id is required"}), 400

    from backend.storage import save
    save("oneroster_teacher_id", {"teacher_sourced_id": teacher_sourced_id}, g.teacher_id)
    return jsonify({"status": "saved"})


# ── POST /api/oneroster/delete-data ───────────────────────────────────────

@oneroster_bp.route("/api/oneroster/delete-data", methods=["POST"])
@require_teacher
@handle_route_errors
def delete_data():
    """Delete all OneRoster roster data and clear config."""
    from backend.roster_sync import delete_roster_data
    from backend.storage import save as _storage_save
    from backend.utils.audit import audit_log

    teacher_id = g.teacher_id

    deleted = delete_roster_data(teacher_id)
    _storage_save("oneroster_config", None, teacher_id)

    audit_log(
        "ONEROSTER_DATA_DELETED",
        f"Deleted {deleted.get('classes', 0)} classes, {deleted.get('students', 0)} students",
        teacher_id=teacher_id,
    )

    return jsonify({"status": "deleted", "counts": deleted})


# ── POST /api/oneroster/sync-grades ───────────────────────────────────────

@oneroster_bp.route("/api/oneroster/sync-grades", methods=["POST"])
@require_teacher
@handle_route_errors
def sync_grades():
    """Push graded scores + comments to SIS via OneRoster Gradebook API."""
    teacher_id = g.teacher_id
    cfg = get_oneroster_config(teacher_id)
    if not cfg or not cfg.get("base_url"):
        return jsonify({"error": "OneRoster not configured. Set up SIS connection in District Portal first."}), 400

    data = request.json or {}
    assessment_id = data.get("assessment_id")
    title = data.get("title")
    total_points = data.get("total_points")
    class_sourced_id = data.get("class_sourced_id")
    scores = data.get("scores", [])

    if not assessment_id or not title or not total_points or not class_sourced_id:
        return jsonify({"error": "Missing required fields: assessment_id, title, total_points, class_sourced_id"}), 400

    if not scores:
        return jsonify({"error": "No scores to sync"}), 400

    client = OneRosterClient(
        base_url=cfg["base_url"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        token_url=cfg.get("token_url"),
    )

    try:
        line_item_id = _run_async(ensure_line_item(
            client=client,
            teacher_id=teacher_id,
            assessment_id=assessment_id,
            title=title,
            total_points=float(total_points),
            class_sourced_id=class_sourced_id,
        ))
    except Exception as e:
        logger.error("Failed to create/find lineItem: %s", e)
        return jsonify({"error": "Failed to create assignment in SIS"}), 500

    try:
        result = _run_async(post_results(client, line_item_id, scores))
    except Exception as e:
        logger.error("Failed to post results: %s", e)
        return jsonify({"error": "Failed to post scores"}), 500

    return jsonify({
        "status": "success",
        "line_item_id": line_item_id,
        "synced": result["synced"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "errors": result["errors"],
    })
