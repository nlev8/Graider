"""
School Admin Routes
====================
Endpoints for school-level admin dashboard: status, invite claim,
teacher discovery, overview metrics, drill-down, and activity feed.

All admin data stored with teacher_id="system" via backend.storage.
"""
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, g

from backend.storage import load as storage_load, save as storage_save, list_keys
from backend.supabase_client import get_supabase as _get_supabase
from backend.utils.auth_decorators import require_teacher, require_admin
from backend.utils.errors import handle_route_errors
from backend.utils.audit import audit_log

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


# ── GET /api/admin/status ─────────────────────────────────────────────────

@admin_bp.route("/api/admin/status", methods=["GET"])
@require_teacher
@handle_route_errors
def admin_status():
    """Check whether the current teacher is a school admin."""
    admin_role = storage_load(f"admin_role:{g.teacher_id}", "system")
    if admin_role and isinstance(admin_role, dict):
        audit_log("ADMIN_VIEW_STATUS", "Admin status check: is_admin=true",
                  user="admin", teacher_id=g.teacher_id)
        return jsonify({
            "is_admin": True,
            "school": admin_role.get("school", ""),
        })
    return jsonify({"is_admin": False})


# ── POST /api/admin/claim ─────────────────────────────────────────────────

@admin_bp.route("/api/admin/claim", methods=["POST"])
@require_teacher
@handle_route_errors
def admin_claim():
    """Claim an admin invite code to become a school admin."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Invite code is required"}), 400

    invite = storage_load(f"admin_invite:{code}", "system")
    if not invite or not isinstance(invite, dict):
        return jsonify({"error": "Invalid invite code"}), 404

    # Check 7-day TTL
    created_at = invite.get("created_at", "")
    if created_at:
        try:
            created_dt = datetime.fromisoformat(created_at)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if datetime.now(tz=timezone.utc) - created_dt > timedelta(days=7):
                return jsonify({"error": "Invite code has expired"}), 410
        except (ValueError, TypeError):
            pass

    school = invite.get("school", "")
    admin_role = {
        "school": school,
        "claimed_at": datetime.now(tz=timezone.utc).isoformat(),
        "invite_code": code,
        "manual_teachers": invite.get("manual_teachers", []),
    }
    storage_save(f"admin_role:{g.teacher_id}", admin_role, "system")

    # Delete used invite
    from backend.storage import delete as storage_delete
    storage_delete(f"admin_invite:{code}", "system")

    audit_log("ADMIN_CLAIM", f"Admin role claimed for school={school}",
              user="admin", teacher_id=g.teacher_id)
    return jsonify({"status": "claimed", "school": school})


# ── GET /api/admin/teachers ───────────────────────────────────────────────

@admin_bp.route("/api/admin/teachers", methods=["GET"])
@require_admin
@handle_route_errors
def admin_teachers():
    """List teachers in the admin's school (multi-layer discovery)."""
    teachers = _discover_teachers(g.admin_role)
    audit_log("ADMIN_VIEW_TEACHERS", f"Viewed {len(teachers)} teachers",
              user="admin", teacher_id=g.teacher_id)
    return jsonify({"teachers": teachers})


def _discover_teachers(admin_role):
    """Three-layer teacher discovery: SIS, manual, fallback."""
    teacher_map = {}  # email -> {user_id, name, email, source}

    # Layer 1: SIS auto-discovery
    try:
        _discover_via_sis(admin_role, teacher_map)
    except Exception as e:
        logger.warning("SIS teacher discovery failed: %s", e)

    # Layer 2: Manual assignments
    for entry in admin_role.get("manual_teachers", []):
        email = entry.get("email", "").lower()
        if email and email not in teacher_map:
            teacher_map[email] = {
                "user_id": entry.get("user_id", ""),
                "name": entry.get("name", email),
                "email": email,
                "source": "manual",
            }

    # Layer 3: Fallback — all teachers in teacher_data
    if not teacher_map:
        try:
            _discover_fallback(teacher_map)
        except Exception as e:
            logger.warning("Fallback teacher discovery failed: %s", e)

    # Enrich with counts
    teachers = list(teacher_map.values())
    _enrich_teachers(teachers)
    return teachers


def _discover_via_sis(admin_role, teacher_map):
    """Layer 1: Use OneRoster to find teachers at the admin's school."""
    sis_config = storage_load("district:sis_config", "system")
    if not sis_config or not isinstance(sis_config, dict):
        return
    if sis_config.get("sis_type") != "oneroster":
        return

    base_url = sis_config.get("base_url")
    client_id = sis_config.get("client_id")
    client_secret = sis_config.get("client_secret")
    if not all([base_url, client_id, client_secret]):
        return

    import asyncio
    from backend.oneroster import OneRosterClient

    oneroster = OneRosterClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        token_url=sis_config.get("token_url"),
    )

    school_name = admin_role.get("school", "")

    async def _fetch():
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as http:
            await oneroster._ensure_token(http)

            # Find school by name
            schools_url = f"{oneroster.base_url}/schools?limit=100"
            schools_data = await oneroster._get_with_retry(http, schools_url, label="admin-schools")
            schools = schools_data if isinstance(schools_data, list) else schools_data.get("orgs", [])

            school_id = None
            for s in schools:
                if s.get("name", "").lower() == school_name.lower():
                    school_id = s.get("sourcedId")
                    break

            if not school_id:
                return []

            # Fetch teachers for school
            teachers_url = f"{oneroster.base_url}/schools/{school_id}/teachers?limit=500"
            teachers_data = await oneroster._get_with_retry(http, teachers_url, label="admin-teachers")
            return teachers_data if isinstance(teachers_data, list) else teachers_data.get("users", [])

    loop = asyncio.new_event_loop()
    try:
        sis_teachers = loop.run_until_complete(_fetch())
    finally:
        loop.close()

    if not sis_teachers:
        return

    # Build email -> user_id map from teacher_data settings
    email_map = _build_email_map()

    for t in sis_teachers:
        email = t.get("email", "").lower()
        if not email:
            continue
        given = t.get("givenName", "")
        family = t.get("familyName", "")
        name = f"{given} {family}".strip() or email
        teacher_map[email] = {
            "user_id": email_map.get(email, ""),
            "name": name,
            "email": email,
            "source": "sis",
        }


def _discover_fallback(teacher_map):
    """Layer 3: Query all distinct teacher_ids from teacher_data."""
    sb = _get_supabase()
    if not sb:
        return

    result = sb.table("teacher_data") \
        .select("teacher_id, data") \
        .eq("data_key", "settings") \
        .execute()

    if not result.data:
        return

    for row in result.data:
        tid = row.get("teacher_id", "")
        if not tid or tid == "system":
            continue
        data = row.get("data") or {}
        email = ""
        name = ""
        if isinstance(data, dict):
            email = data.get("email", "").lower()
            name = data.get("name", "") or data.get("teacher_name", "")
        key = email or tid
        if key not in teacher_map:
            teacher_map[key] = {
                "user_id": tid,
                "name": name or tid,
                "email": email,
                "source": "fallback",
            }


def _build_email_map():
    """Build email -> user_id map from teacher_data settings rows."""
    sb = _get_supabase()
    if not sb:
        return {}

    result = sb.table("teacher_data") \
        .select("teacher_id, data") \
        .eq("data_key", "settings") \
        .execute()

    email_map = {}
    if result.data:
        for row in result.data:
            tid = row.get("teacher_id", "")
            data = row.get("data") or {}
            if isinstance(data, dict):
                email = data.get("email", "").lower()
                if email:
                    email_map[email] = tid
    return email_map


def _enrich_teachers(teachers):
    """Add classes_count, students_count, assessments_count, last_activity."""
    sb = _get_supabase()
    if not sb:
        return

    for t in teachers:
        uid = t.get("user_id", "")
        if not uid:
            t.update({"classes_count": 0, "students_count": 0,
                       "assessments_count": 0, "last_activity": None})
            continue

        try:
            # Classes count
            classes_res = sb.table("classes").select("id", count="exact") \
                .eq("teacher_id", uid).execute()
            t["classes_count"] = classes_res.count if classes_res.count is not None else len(classes_res.data or [])

            # Students count (via class_students for teacher's classes)
            class_ids = [c["id"] for c in (classes_res.data or [])]
            if class_ids:
                students_res = sb.table("class_students").select("student_id", count="exact") \
                    .in_("class_id", class_ids).execute()
                t["students_count"] = students_res.count if students_res.count is not None else len(students_res.data or [])
            else:
                t["students_count"] = 0

            # Assessments count
            assessments_res = sb.table("published_assessments").select("id", count="exact") \
                .eq("teacher_id", uid).execute()
            t["assessments_count"] = assessments_res.count if assessments_res.count is not None else len(assessments_res.data or [])

            # Last activity from audit_log
            audit_res = sb.table("audit_log").select("timestamp") \
                .eq("teacher_id", uid) \
                .order("timestamp", desc=True) \
                .limit(1).execute()
            t["last_activity"] = audit_res.data[0]["timestamp"] if audit_res.data else None

        except Exception as e:
            logger.warning("Failed to enrich teacher %s: %s", uid, e)
            t.setdefault("classes_count", 0)
            t.setdefault("students_count", 0)
            t.setdefault("assessments_count", 0)
            t.setdefault("last_activity", None)


# ── GET /api/admin/overview ───────────────────────────────────────────────

@admin_bp.route("/api/admin/overview", methods=["GET"])
@require_admin
@handle_route_errors
def admin_overview():
    """Aggregate metrics across admin's teachers."""
    teachers = _discover_teachers(g.admin_role)
    teacher_ids = [t["user_id"] for t in teachers if t.get("user_id")]

    overview = {
        "total_teachers": len(teachers),
        "total_students": 0,
        "total_assessments": 0,
        "average_score": None,
        "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
    }

    sb = _get_supabase()
    if not sb or not teacher_ids:
        audit_log("ADMIN_VIEW_OVERVIEW", "Viewed overview (no data)",
                  user="admin", teacher_id=g.teacher_id)
        return jsonify(overview)

    all_scores = []

    for tid in teacher_ids:
        try:
            # Join-code path: published_assessments + submissions
            pa_res = sb.table("published_assessments").select("join_code") \
                .eq("teacher_id", tid).execute()
            join_codes = [r["join_code"] for r in (pa_res.data or []) if r.get("join_code")]
            overview["total_assessments"] += len(join_codes)

            for code in join_codes:
                sub_res = sb.table("submissions").select("score") \
                    .eq("join_code", code).execute()
                for s in (sub_res.data or []):
                    score = s.get("score")
                    if score is not None:
                        try:
                            all_scores.append(float(score))
                        except (ValueError, TypeError):
                            pass

            # Class-based path: published_content + student_submissions
            classes_res = sb.table("classes").select("id") \
                .eq("teacher_id", tid).execute()
            class_ids = [c["id"] for c in (classes_res.data or [])]

            # Count students
            if class_ids:
                cs_res = sb.table("class_students").select("student_id", count="exact") \
                    .in_("class_id", class_ids).execute()
                overview["total_students"] += cs_res.count if cs_res.count is not None else len(cs_res.data or [])

            for cid in class_ids:
                pc_res = sb.table("published_content").select("id") \
                    .eq("class_id", cid).execute()
                overview["total_assessments"] += len(pc_res.data or [])

                for pc in (pc_res.data or []):
                    ss_res = sb.table("student_submissions").select("score") \
                        .eq("content_id", pc["id"]).execute()
                    for s in (ss_res.data or []):
                        score = s.get("score")
                        if score is not None:
                            try:
                                all_scores.append(float(score))
                            except (ValueError, TypeError):
                                pass

        except Exception as e:
            logger.warning("Overview aggregation error for teacher %s: %s", tid, e)

    # Compute average and distribution
    if all_scores:
        overview["average_score"] = round(sum(all_scores) / len(all_scores), 1)
        for score in all_scores:
            if score >= 90:
                overview["grade_distribution"]["A"] += 1
            elif score >= 80:
                overview["grade_distribution"]["B"] += 1
            elif score >= 70:
                overview["grade_distribution"]["C"] += 1
            elif score >= 60:
                overview["grade_distribution"]["D"] += 1
            else:
                overview["grade_distribution"]["F"] += 1

    audit_log("ADMIN_VIEW_OVERVIEW", f"Viewed overview: {len(teachers)} teachers, {len(all_scores)} scores",
              user="admin", teacher_id=g.teacher_id)
    return jsonify(overview)


# ── GET /api/admin/teacher/<teacher_id>/summary ───────────────────────────

@admin_bp.route("/api/admin/teacher/<teacher_id>/summary", methods=["GET"])
@require_admin
@handle_route_errors
def admin_teacher_summary(teacher_id):
    """Drill-down summary for a specific teacher in the admin's school."""
    # Verify teacher_id is in admin's school
    teachers = _discover_teachers(g.admin_role)
    valid_ids = {t["user_id"] for t in teachers if t.get("user_id")}
    if teacher_id not in valid_ids:
        return jsonify({"error": "Teacher not found in your school"}), 404

    sb = _get_supabase()
    if not sb:
        return jsonify({"error": "Database unavailable"}), 503

    summary = {"classes": [], "recent_assessments": [], "recent_activity": []}

    try:
        # Classes
        classes_res = sb.table("classes").select("id, name, subject") \
            .eq("teacher_id", teacher_id).execute()
        for cls in (classes_res.data or []):
            cs_res = sb.table("class_students").select("id", count="exact") \
                .eq("class_id", cls["id"]).execute()
            student_count = cs_res.count if cs_res.count is not None else len(cs_res.data or [])
            summary["classes"].append({
                "name": cls.get("name", ""),
                "subject": cls.get("subject", ""),
                "student_count": student_count,
            })

        # Recent assessments (join-code)
        pa_res = sb.table("published_assessments") \
            .select("title, join_code, created_at") \
            .eq("teacher_id", teacher_id) \
            .order("created_at", desc=True) \
            .limit(10).execute()
        for pa in (pa_res.data or []):
            sub_res = sb.table("submissions").select("score") \
                .eq("join_code", pa.get("join_code", "")).execute()
            scores = []
            for s in (sub_res.data or []):
                sc = s.get("score")
                if sc is not None:
                    try:
                        scores.append(float(sc))
                    except (ValueError, TypeError):
                        pass
            summary["recent_assessments"].append({
                "title": pa.get("title", ""),
                "submissions": len(sub_res.data or []),
                "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            })

        # Recent audit activity (last 10)
        audit_res = sb.table("audit_log").select("action, details, timestamp") \
            .eq("teacher_id", teacher_id) \
            .order("timestamp", desc=True) \
            .limit(10).execute()
        summary["recent_activity"] = audit_res.data or []

    except Exception as e:
        logger.warning("Teacher summary error for %s: %s", teacher_id, e)

    audit_log("ADMIN_VIEW_TEACHER_SUMMARY", f"Viewed summary for teacher={teacher_id}",
              user="admin", teacher_id=g.teacher_id)
    return jsonify(summary)


# ── GET /api/admin/activity ───────────────────────────────────────────────

@admin_bp.route("/api/admin/activity", methods=["GET"])
@require_admin
@handle_route_errors
def admin_activity():
    """Recent activity feed across all admin's teachers."""
    teachers = _discover_teachers(g.admin_role)
    teacher_ids = [t["user_id"] for t in teachers if t.get("user_id")]
    name_map = {t["user_id"]: t.get("name", "") for t in teachers if t.get("user_id")}

    sb = _get_supabase()
    if not sb or not teacher_ids:
        return jsonify({"activity": []})

    all_entries = []
    for tid in teacher_ids:
        try:
            res = sb.table("audit_log") \
                .select("action, details, timestamp, teacher_id") \
                .eq("teacher_id", tid) \
                .order("timestamp", desc=True) \
                .limit(50).execute()
            for entry in (res.data or []):
                entry["teacher_name"] = name_map.get(tid, "")
                all_entries.append(entry)
        except Exception as e:
            logger.warning("Activity fetch error for teacher %s: %s", tid, e)

    # Sort by timestamp descending and limit to 50
    all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    activity = all_entries[:50]

    audit_log("ADMIN_VIEW_ACTIVITY", f"Viewed activity feed ({len(activity)} entries)",
              user="admin", teacher_id=g.teacher_id)
    return jsonify({"activity": activity})
