"""
Provider-agnostic roster sync logic for Graider.

Shared by Clever and OneRoster integrations. Both normalise their data
into the same shape and call sync_roster_to_db() / delete_roster_data().
"""
import logging
import os

import sentry_sdk

from backend.utils.audit import audit_log

logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client, or None if not configured."""
    try:
        from backend.supabase_client import get_supabase
        return get_supabase()
    except Exception:
        return None


_PROVIDER_PREFIXES = {
    "clever": "",
    "oneroster": "oneroster:",
    "manual": "manual-",
    "classlink": "classlink:",
}


def sync_roster_to_db(classes, students, enrollments, teacher_id, provider="manual"):
    """Upsert normalised roster data into Supabase.

    Args:
        classes: list of dicts with keys: external_id, name, subject, grade_level
        students: list of dicts with keys: external_id, first_name, last_name, email
        enrollments: list of tuples (class_external_id, student_external_id)
        teacher_id: Graider teacher ID
        provider: "clever", "oneroster", or "manual" (for logging)

    Returns:
        dict with counts: {"classes": int, "students": int, "enrollments": int}
    """
    audit_log(
        "ROSTER_SYNC_START",
        f"provider={provider} classes={len(classes)} students={len(students)} enrollments={len(enrollments)}",
        teacher_id=teacher_id,
    )

    try:
        result = _sync_roster_to_db_impl(classes, students, enrollments, teacher_id, provider)
        audit_log(
            "ROSTER_SYNC_COMPLETE",
            f"provider={provider}",
            teacher_id=teacher_id,
        )
        return result
    except Exception:
        audit_log(
            "ROSTER_SYNC_FAILED",
            f"provider={provider}",
            teacher_id=teacher_id,
        )
        raise


def _sync_roster_to_db_impl(classes, students, enrollments, teacher_id, provider):
    """Internal implementation of sync_roster_to_db (no audit boundaries)."""
    from backend.supabase_client import get_supabase as _get_supabase

    zero = {"classes": 0, "students": 0, "enrollments": 0}

    sb = _get_supabase()
    if sb is None:
        logger.debug("Supabase not configured — skipping %s roster DB sync", provider)
        return zero

    # --- Phase 1: Batch upsert classes ---
    class_payloads = []
    for cls in classes:
        ext_id = cls.get("external_id")
        if not ext_id:
            continue
        class_payloads.append({
            "teacher_id": teacher_id,
            "name": cls.get("name", ""),
            "subject": cls.get("subject", ""),
            "grade_level": cls.get("grade_level", ""),
            "clever_section_id": ext_id,
            "is_active": True,
        })

    if not class_payloads:
        logger.info("%s DB sync complete: 0 classes, 0 students, 0 enrollments", provider)
        return zero

    try:
        class_result = (
            sb.table("classes")
            .upsert(class_payloads, on_conflict="teacher_id,clever_section_id")
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to batch-upsert classes (%s): %s", provider, str(e))
        sentry_sdk.capture_exception(e)
        return zero

    class_rows = class_result.data if class_result and class_result.data else []
    if not class_rows:
        logger.warning("No class rows returned from batch upsert (%s)", provider)
        return zero

    # Build external_id -> DB UUID map
    class_id_map = {}
    for row in class_rows:
        csid = row.get("clever_section_id", "")
        if csid and row.get("id"):
            class_id_map[csid] = row["id"]

    synced_classes = len(class_id_map)

    # --- Phase 2: Batch upsert students ---
    # Build student lookup by external_id
    student_ext_map = {}
    for stu in students:
        ext_id = stu.get("external_id")
        if ext_id:
            student_ext_map[ext_id] = stu

    # Collect unique students that appear in enrollments
    unique_students = {}
    valid_enrollments = []
    for class_ext_id, student_ext_id in enrollments:
        if class_ext_id not in class_id_map:
            continue
        stu = student_ext_map.get(student_ext_id)
        if not stu:
            continue
        valid_enrollments.append((class_ext_id, student_ext_id))
        if student_ext_id not in unique_students:
            unique_students[student_ext_id] = {
                "teacher_id": teacher_id,
                "student_id_number": student_ext_id,
                "first_name": stu.get("first_name", ""),
                "last_name": stu.get("last_name", ""),
                "email": stu.get("email", ""),
                "is_active": True,
            }

    if not unique_students:
        logger.info(
            "%s DB sync complete: %d classes, 0 students, 0 enrollments",
            provider, synced_classes,
        )
        return {"classes": synced_classes, "students": 0, "enrollments": 0}

    try:
        stu_result = (
            sb.table("students")
            .upsert(list(unique_students.values()), on_conflict="teacher_id,student_id_number")
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to batch-upsert students (%s): %s", provider, str(e))
        sentry_sdk.capture_exception(e)
        return {"classes": synced_classes, "students": 0, "enrollments": 0}

    stu_rows = stu_result.data if stu_result and stu_result.data else []
    if not stu_rows:
        logger.warning("No student rows returned from batch upsert (%s)", provider)
        return {"classes": synced_classes, "students": 0, "enrollments": 0}

    # Build external_id -> DB UUID map
    student_id_map = {}
    for row in stu_rows:
        sid_num = row.get("student_id_number", "")
        if sid_num and row.get("id"):
            student_id_map[sid_num] = row["id"]

    synced_students = len(student_id_map)

    # --- Phase 3: Batch upsert enrollments ---
    enrollment_payloads = []
    for class_ext_id, student_ext_id in valid_enrollments:
        class_db_id = class_id_map.get(class_ext_id)
        student_db_id = student_id_map.get(student_ext_id)
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
            logger.warning("Failed to batch-upsert enrollments (%s): %s", provider, str(e))
            sentry_sdk.capture_exception(e)

    logger.info(
        "%s DB sync complete: %d classes, %d students, %d enrollments",
        provider, synced_classes, synced_students, synced_enrollments,
    )
    return {"classes": synced_classes, "students": synced_students, "enrollments": synced_enrollments}


def deactivate_missing_students(teacher_id, current_student_external_ids, provider):
    """Soft-deactivate students no longer in the SIS roster.

    Only deactivates students matching the given provider's prefix.
    Manual students and students from other providers are never touched.
    """
    sb = _get_supabase()
    if sb is None:
        return 0

    try:
        result = sb.table('students').select('id, student_id_number').eq(
            'teacher_id', teacher_id
        ).eq('is_active', True).execute()

        if not result.data:
            return 0

        other_prefixes = [p for k, p in _PROVIDER_PREFIXES.items() if k != provider and p]

        deactivated = 0
        for student in result.data:
            sid = student.get('student_id_number', '')

            if any(sid.startswith(op) for op in other_prefixes):
                continue

            if sid not in current_student_external_ids:
                sb.table('students').update({'is_active': False}).eq('id', student['id']).execute()
                deactivated += 1

        if deactivated:
            logger.info("Deactivated %d %s students for teacher %s", deactivated, provider, teacher_id)

        return deactivated

    except Exception as e:
        logger.error("Failed to deactivate missing students for %s: %s", teacher_id, e)
        return 0


def delete_roster_data(teacher_id):
    """Delete all roster data for a teacher (provider-agnostic).

    Removes:
    - Supabase records: enrollments, students, classes, sessions, content, submissions
    - Local roster CSV files from ~/.graider_data/

    Returns dict with counts of deleted items.
    """
    from backend.supabase_client import get_supabase as _get_supabase

    deleted = {"classes": 0, "students": 0, "enrollments": 0, "roster_files": 0}

    # --- Step 1: Delete Supabase records ---
    sb = _get_supabase()
    if sb:
        try:
            # Get classes for this teacher
            classes_res = sb.table("classes").select("id").eq("teacher_id", teacher_id).execute()
            class_ids = [c["id"] for c in (classes_res.data or [])]

            if class_ids:
                # Class-scoped deletes (content, submissions, enrollments, classes)
                content_res = sb.table("published_content").select("id").in_("class_id", class_ids).execute()
                content_ids = [c["id"] for c in (content_res.data or [])]
                if content_ids:
                    sb.table("student_submissions").delete().in_("content_id", content_ids).execute()
                    sb.table("published_content").delete().in_("id", content_ids).execute()
                for cid in class_ids:
                    sb.table("class_students").delete().eq("class_id", cid).execute()

            # Always delete this teacher's students + their sessions — including
            # orphan students with no class rows (FERPA right-to-delete must be
            # complete). Still teacher_id-scoped: never another teacher's rows.
            students_res = sb.table("students").select("id").eq("teacher_id", teacher_id).execute()
            student_ids = [s["id"] for s in (students_res.data or [])]
            if student_ids:
                for sid in student_ids:
                    sb.table("student_sessions").delete().eq("student_id", sid).execute()
                sb.table("students").delete().eq("teacher_id", teacher_id).execute()

            if class_ids:
                sb.table("classes").delete().eq("teacher_id", teacher_id).execute()

            deleted["classes"] = len(class_ids)
            deleted["students"] = len(student_ids)
            deleted["enrollments"] = len(class_ids)  # approximation
        except Exception as e:
            logger.error("Supabase roster deletion failed for %s: %s", teacher_id, str(e))
            sentry_sdk.capture_exception(e)

    # --- Step 2: Delete local roster files ---
    import glob as globmod
    safe_id = teacher_id.replace(":", "_")
    data_dir = os.path.expanduser("~/.graider_data")
    rosters_dir = os.path.join(data_dir, "rosters")

    # Delete roster CSVs and related files
    for pattern in [
        os.path.join(rosters_dir, f"*roster_{safe_id}*"),
        os.path.join(rosters_dir, f"*roster_{safe_id}*"),
    ]:
        for filepath in globmod.glob(pattern):
            try:
                os.remove(filepath)
                deleted["roster_files"] += 1
            except OSError as e:
                logger.warning("Failed to delete %s: %s", filepath, e)
                sentry_sdk.capture_exception(e)

    logger.info("Roster data deletion complete for %s: %s", teacher_id, deleted)
    return deleted
