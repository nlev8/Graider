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

from backend.extensions import limiter
from backend.storage import load as storage_load, save as storage_save, list_keys
from backend.supabase_client import get_supabase as _get_supabase
from backend.utils.auth_decorators import require_teacher, require_admin
from backend.utils.errors import handle_route_errors
from backend.utils.audit import audit_log
import sentry_sdk

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

def _admin_claim_rate_limit_key():
    """Rate-limit key combining IP + authenticated user_id when present.

    A pure per-IP key lets one authenticated teacher distribute attempts
    across multiple IPs (mobile + WiFi + VPN) and multiply the budget.
    A pure per-user key lets one IP host many fake users at full budget.
    Combining both caps each (IP, user) pair independently.

    Falls back to bare IP when the auth context isn't yet attached
    (require_teacher hasn't run or the request is anonymous).
    """
    from flask_limiter.util import get_remote_address
    ip = get_remote_address()
    try:
        uid = getattr(g, "teacher_id", None) or getattr(g, "user_id", None)
    except Exception:
        uid = None
    return f"{ip}|{uid or 'anon'}"


@admin_bp.route("/api/admin/claim", methods=["POST"])
# Rate limit closes audit MAJOR #8 (Codex 2026-05-06): without a limit
# the route was brute-forceable by any authenticated teacher (invite
# codes are 6 hex chars = 16.7M keyspace; storage_load reveals validity
# via 404 vs 200). Two layers:
#   - Per-IP+user combo: caps a single attacker tuple. 10/hour + 5/min
#   - Per-user only:     caps a teacher who roams across IPs at 20/hour
# A teacher claiming a single invite never hits either. Brute-force at
# 10/hour vs 16.7M keyspace = ~190 years to enumerate.
@limiter.limit("10 per hour;5 per minute", key_func=_admin_claim_rate_limit_key)
@limiter.limit(
    "20 per hour",
    key_func=lambda: getattr(g, "teacher_id", None) or getattr(g, "user_id", None) or "anon",
)
@require_teacher
@handle_route_errors
def admin_claim():
    """Claim an admin invite code to become a school admin."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    # Closes audit MAJOR #8: previously distinguished missing/invalid/expired
    # via different status codes (400/404/410), letting an attacker
    # enumerate valid-but-expired codes from valid-now codes from
    # invalid-format codes. Now ALL failure modes return a single
    # generic 400 + same error string so the response shape carries
    # zero validity signal. Internal log captures the precise reason
    # for ops debugging.
    _GENERIC_FAILURE = (jsonify({"error": "Unable to claim invite. Verify the code and try again."}), 400)

    # Codex round-2 MINOR fold: the empty-code path used to early-return
    # before any storage call, leaving a measurable timing differential
    # (~10ms) vs the valid-shape paths. Probe storage even on empty
    # codes (with a sentinel that can never collide with a real key) so
    # all 5 failure modes share a similar wall-clock profile.
    _ = storage_load(f"admin_invite:__timing_anchor_{code or '_empty_'}__", "system")

    if not code:
        logger.info("admin_claim: rejected — empty code")
        return _GENERIC_FAILURE

    invite = storage_load(f"admin_invite:{code}", "system")
    if not invite or not isinstance(invite, dict):
        logger.info("admin_claim: rejected — code not found or malformed shape")
        return _GENERIC_FAILURE

    # Closes Codex round-1 MAJOR (2026-05-07): producer/consumer schema
    # mismatch. district_routes.py:444 writes `expires_at`; this route
    # previously only checked `created_at`, so production invites
    # NEVER expired — a leaked invite stayed claimable indefinitely.
    # Now reads BOTH fields (expires_at preferred — it's the production
    # path; created_at preserved for any legacy invites that exist).
    expires_at = invite.get("expires_at", "")
    created_at = invite.get("created_at", "")
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if datetime.now(tz=timezone.utc) > expires_dt:
                logger.info("admin_claim: rejected — code expired (expires_at)")
                return _GENERIC_FAILURE
        except (ValueError, TypeError):
            logger.info("admin_claim: rejected — expires_at parse failure")
            return _GENERIC_FAILURE
    elif created_at:
        # Legacy fallback: older invites that predate the expires_at
        # producer used a created_at + 7-day TTL pattern. Preserve so
        # those don't spuriously fail.
        try:
            created_dt = datetime.fromisoformat(created_at)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if datetime.now(tz=timezone.utc) - created_dt > timedelta(days=7):
                logger.info("admin_claim: rejected — code expired (created_at + 7d)")
                return _GENERIC_FAILURE
        except (ValueError, TypeError):
            logger.info("admin_claim: rejected — created_at parse failure")
            return _GENERIC_FAILURE

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
        sentry_sdk.capture_exception(e)

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
            sentry_sdk.capture_exception(e)

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


# Round-2 Codex HIGH fold: PostgREST `.in_()` lists are URL-encoded into
# the query string. With UUID values (~36 chars each + comma) and a
# typical PostgREST URL limit around 8 KB, 200 ids per chunk stays
# safely under the limit (~7.4 KB). Lists below this are sent as one
# query; longer lists chunk and aggregate.
_IN_CHUNK_SIZE = 200

# Round-3 Codex HIGH fold: Supabase imposes a default 1,000-row return
# cap on `select()` queries. `_chunked_in_rows` MUST paginate within
# each filter-value chunk via `.range(offset, offset+page_size-1)` or
# total_students / total_assessments / score aggregates would silently
# undercount on districts with > 1,000 matching rows in a single chunk.
_PAGE_SIZE = 1000

# Absolute ceiling per chunk-batch to prevent runaway memory in the
# pathological case (e.g., a single misconfigured admin scope with
# millions of audit rows). 100K rows × ~200B/row = ~20 MB peak.
_HARD_CAP = 100_000


def _chunked_in_rows(sb, table, column, values, select_cols,
                      order=None, limit=None):
    """Run `select_cols` from `table` filtered by `column .in_ values`,
    chunking `values` into `_IN_CHUNK_SIZE` slices AND paginating result
    rows within each chunk to defeat Supabase's default 1,000-row return
    cap. Returns a list of row dicts (possibly empty).

    `order` is an optional `(col, desc=True/False)` tuple. `limit` is
    a per-chunk ceiling (NOT global): each chunk fetches up to `limit`
    rows. If `limit` is None, defaults to `_HARD_CAP=100,000` per chunk.
    Callers needing a global cap MUST truncate the merged result
    themselves (see audit_log usage in `_enrich_teachers`).
    """
    if not values:
        return []
    out: list = []
    target = limit if limit is not None else _HARD_CAP
    for i in range(0, len(values), _IN_CHUNK_SIZE):
        chunk = values[i:i + _IN_CHUNK_SIZE]
        offset = 0
        while offset < target:
            page_size = min(_PAGE_SIZE, target - offset)
            q = sb.table(table).select(select_cols).in_(column, chunk)
            if order is not None:
                col, desc = order
                q = q.order(col, desc=desc)
            q = q.range(offset, offset + page_size - 1)
            rows = q.execute().data or []
            out.extend(rows)
            if len(rows) < page_size:
                break  # end of result set for this chunk
            offset += page_size
    return out


def _enrich_teachers(teachers):
    """Add classes_count, students_count, assessments_count, last_activity.

    Closes audit MAJOR #11 (Codex full-codebase audit 2026-05-06): the
    pre-fix implementation made 4 Supabase queries PER teacher (N+1
    pattern). For a 50-teacher district that meant 200 round trips on
    every dashboard load; for 500 teachers it was 2,000. Now uses 4
    batched queries via `_chunked_in_rows` (chunked at
    _IN_CHUNK_SIZE=200 to stay under PostgREST URL limits) and
    aggregates counts in Python.

    Pagination cap on the audit_log query (`AUDIT_TOP_N`) bounds memory
    if a hot teacher dominates recent activity. Quiet teachers whose
    last activity falls outside that window will report
    `last_activity=None` rather than triggering an unbounded fetch.

    Round-2 Codex MEDIUM fold: any exception inside the batched
    pipeline now resets ALL accumulated dicts so the apply loop
    delivers a uniform "all zeros" fallback rather than partial
    earlier counts + zero later counts. Matches the PR description.
    """
    sb = _get_supabase()
    if not sb:
        return

    teacher_ids = [t.get("user_id") for t in teachers if t.get("user_id")]
    if not teacher_ids:
        for t in teachers:
            t.update({"classes_count": 0, "students_count": 0,
                       "assessments_count": 0, "last_activity": None})
        return

    classes_count: dict = {}
    students_count: dict = {}
    assessments_count: dict = {}
    last_activity: dict = {}
    class_ids_by_teacher: dict = {}

    try:
        # 1. Classes per teacher — chunked .in_() over teacher_ids
        classes_rows = _chunked_in_rows(
            sb, "classes", "teacher_id", teacher_ids, "id, teacher_id",
        )
        for row in classes_rows:
            tid = row.get("teacher_id")
            cid = row.get("id")
            if not tid or not cid:
                continue
            classes_count[tid] = classes_count.get(tid, 0) + 1
            class_ids_by_teacher.setdefault(tid, []).append(cid)

        # 2. Students per teacher — chunked .in_() over all_class_ids
        all_class_ids = [cid for cids in class_ids_by_teacher.values() for cid in cids]
        if all_class_ids:
            class_to_teacher = {
                cid: tid
                for tid, cids in class_ids_by_teacher.items()
                for cid in cids
            }
            cs_rows = _chunked_in_rows(
                sb, "class_students", "class_id", all_class_ids,
                "class_id, student_id",
            )
            for row in cs_rows:
                tid = class_to_teacher.get(row.get("class_id"))
                if tid:
                    students_count[tid] = students_count.get(tid, 0) + 1

        # 3. Assessments per teacher — chunked .in_() over teacher_ids
        ass_rows = _chunked_in_rows(
            sb, "published_assessments", "teacher_id", teacher_ids,
            "id, teacher_id",
        )
        for row in ass_rows:
            tid = row.get("teacher_id")
            if tid:
                assessments_count[tid] = assessments_count.get(tid, 0) + 1

        # 4. Last activity per teacher — chunked .in_(), sorted desc PER
        # CHUNK then merged. Bounded by a global cap. For each teacher
        # we take the FIRST occurrence in descending timestamp order
        # AFTER sorting the merged result. A teacher with no activity
        # in the window reports None.
        AUDIT_TOP_N = max(500, len(teacher_ids) * 5)
        # Per-chunk limit ensures we don't pull a hot teacher's
        # entire history when a chunk happens to align with their ids.
        per_chunk_limit = AUDIT_TOP_N
        audit_rows = _chunked_in_rows(
            sb, "audit_log", "teacher_id", teacher_ids,
            "teacher_id, timestamp",
            order=("timestamp", True),
            limit=per_chunk_limit,
        )
        # Merge sort by timestamp desc, then take first per teacher.
        audit_rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
        for row in audit_rows[:AUDIT_TOP_N]:
            tid = row.get("teacher_id")
            ts = row.get("timestamp")
            if tid and ts and tid not in last_activity:
                last_activity[tid] = ts
    except Exception as e:
        logger.warning("Failed to enrich teachers (batched): %s", e)
        sentry_sdk.capture_exception(e)
        # Round-2 Codex MEDIUM fold: partial-failure path used to leave
        # earlier successful counts in place. The PR description says
        # "all zeros" on failure — match that contract exactly so the
        # dashboard never shows a misleading mix of stale + zero data.
        classes_count.clear()
        students_count.clear()
        assessments_count.clear()
        last_activity.clear()

    # Apply (defaults for teachers without any matching rows)
    for t in teachers:
        uid = t.get("user_id", "")
        t["classes_count"] = classes_count.get(uid, 0)
        t["students_count"] = students_count.get(uid, 0)
        t["assessments_count"] = assessments_count.get(uid, 0)
        t["last_activity"] = last_activity.get(uid, None)


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

    all_scores: list = []

    # Round-2 Codex HIGH fold: this route was N+1+M across teachers/
    # assessments/classes/contents. For 50 teachers with ~5 assessments
    # + 3 classes × 5 published content each, that was ~1,300 queries
    # per dashboard load. Now batched into ≤6 chunked queries total
    # (`_chunked_in_rows` chunks at _IN_CHUNK_SIZE to stay under
    # PostgREST URL limits) regardless of teacher count.
    try:
        # 1. published_assessments (join-code path) for these teachers
        pa_rows = _chunked_in_rows(
            sb, "published_assessments", "teacher_id", teacher_ids,
            "join_code, teacher_id",
        )
        join_codes = [r["join_code"] for r in pa_rows if r.get("join_code")]
        overview["total_assessments"] += len(join_codes)

        # 2. submissions for those join_codes (chunked)
        if join_codes:
            sub_rows = _chunked_in_rows(
                sb, "submissions", "join_code", join_codes, "score",
            )
            for s in sub_rows:
                score = s.get("score")
                if score is not None:
                    try:
                        all_scores.append(float(score))
                    except (ValueError, TypeError):
                        pass

        # 3. classes (class-based path) for these teachers
        classes_rows = _chunked_in_rows(
            sb, "classes", "teacher_id", teacher_ids, "id, teacher_id",
        )
        class_ids = [c["id"] for c in classes_rows if c.get("id")]

        # 4. class_students count for total_students. Pre-fix used
        # Supabase count='exact' header per teacher; here we count rows
        # client-side to preserve the row-count semantic and avoid the
        # extra HEAD requests. Bounded by total enrollments in scope.
        if class_ids:
            cs_rows = _chunked_in_rows(
                sb, "class_students", "class_id", class_ids,
                "class_id, student_id",
            )
            overview["total_students"] = len(cs_rows)

            # 5. published_content for those class_ids (chunked)
            pc_rows = _chunked_in_rows(
                sb, "published_content", "class_id", class_ids,
                "id, class_id",
            )
            overview["total_assessments"] += len(pc_rows)

            content_ids = [c["id"] for c in pc_rows if c.get("id")]

            # 6. student_submissions for those content_ids (chunked)
            if content_ids:
                ss_rows = _chunked_in_rows(
                    sb, "student_submissions", "content_id", content_ids,
                    "score",
                )
                for s in ss_rows:
                    score = s.get("score")
                    if score is not None:
                        try:
                            all_scores.append(float(score))
                        except (ValueError, TypeError):
                            pass

    except Exception as e:
        logger.warning("Overview aggregation error (batched): %s", e)
        sentry_sdk.capture_exception(e)

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
        sentry_sdk.capture_exception(e)

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
            sentry_sdk.capture_exception(e)

    # Sort by timestamp descending and limit to 50
    all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    activity = all_entries[:50]

    audit_log("ADMIN_VIEW_ACTIVITY", f"Viewed activity feed ({len(activity)} entries)",
              user="admin", teacher_id=g.teacher_id)
    return jsonify({"activity": activity})
