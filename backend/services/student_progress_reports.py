"""Class progress-rank + student report-card assembly for the student portal.

Wave 5 Slice 3 - extracted from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access; the route keeps
auth, request-arg parsing, the progress-rank TTLCache, and jsonify, and passes
the resolved `db` handle + already-fetched class_name/student_name in. These
functions only assemble data over `db`.

Mastery helpers are imported from backend.services.student_mastery (a sibling
service) — never from the route module (no service->route imports).
"""
from backend.services.student_mastery import (
    _sanitize_standards_mastery,
    _select_submissions_by_mode,
    _aggregate_mastery_for_student,
    _build_trajectory_for_student,
    _build_standards_breakdown_for_student,
)


def build_class_progress_rank(db, class_id, class_name, attempt_mode):
    """Assemble the class progress-rank grid payload.

    Returns ``(payload, cacheable)``. Only the FULL payload is cacheable; the
    empty-roster and empty-content short-circuits return ``cacheable=False`` so
    the caller does NOT cache them. This preserves the pre-extraction cache
    asymmetry: a teacher who just added their first student or assessment must
    not see a stale-empty grid for the cache TTL. Auth, the attempt_mode parse,
    and the TTLCache live in the route.
    """
    # Fetch class roster — query students directly by joining via class_students
    # Two-step query avoids Supabase foreign-table alias ambiguity
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    student_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    student_records = []
    if student_ids:
        students_rows = db.table('students').select(
            'id, first_name, last_name'
        ).in_('id', student_ids).execute()
        for sdata in students_rows.data or []:
            student_records.append({
                'student_id': sdata.get('id'),
                'student_name': ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip(),
            })
        # Sort alphabetically by name for stable grid order
        student_records.sort(key=lambda s: s['student_name'].lower())

    if not student_records:
        return ({
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "standards": [],
            "students": [],
        }, False)

    # Fetch all published_content for this class (assessments/assignments only)
    content = db.table('published_content').select(
        'id, title, content_type'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

    content_ids = [c['id'] for c in content.data or []]
    content_titles = {c['id']: c.get('title', '') for c in content.data or []}

    if not content_ids:
        return ({
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "standards": [],
            "students": [{'student_id': s['student_id'], 'student_name': s['student_name'], 'mastery': {}} for s in student_records],
        }, False)

    # Fetch all non-draft submissions for those contents, ordered for deterministic selection
    # Select only columns we need to keep payload bounded
    subs = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
    ).in_('content_id', content_ids).neq('status', 'draft').order(
        'submitted_at', desc=True
    ).execute()

    # Sanitize malformed standards_mastery in place so column-union and
    # aggregation don't 500 on a single corrupt row. Phase 2b extracted
    # this from get_student_report_card to share between endpoints.
    for s in subs.data or []:
        _sanitize_standards_mastery(s)

    # Group submissions by (student_id, content_id)
    from collections import defaultdict
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    all_standards_in_class = set()  # Union across the whole class — used for columns
    for s in subs.data or []:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)
            # Track every standard seen anywhere in the class for column union
            results = s.get('results') or {}
            mastery = results.get('standards_mastery') or {}
            for code in mastery.keys():
                if code:
                    all_standards_in_class.add(code)

    # Build per-student mastery
    students_output = []
    for student in student_records:
        sid = student['student_id']
        by_content = subs_by_student_content.get(sid, {})
        selected = _select_submissions_by_mode(by_content, attempt_mode)
        mastery = _aggregate_mastery_for_student(selected, content_titles, attempt_mode)
        students_output.append({
            'student_id': sid,
            'student_name': student['student_name'],
            'mastery': mastery,
        })

    payload = {
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "standards": sorted(all_standards_in_class),
        "students": students_output,
    }
    return (payload, True)


def build_student_report_card(db, class_id, class_name, student_id, student_name, attempt_mode):
    """Assemble the per-student report-card payload (trajectory + standards
    breakdown) for a student already verified to be in the class.

    The route keeps the class-ownership (403) / enrollment + student-exists
    (404) checks and resolves class_name/student_name; this function does the
    content + submissions fetch, trajectory, in-place mastery sanitize, and
    breakdown assembly, returning the response payload dict. No cache.
    """
    # 4) Fetch all class assessments/assignments
    content_rows = db.table('published_content').select(
        'id, title, content_type'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()
    content_ids = [c['id'] for c in (content_rows.data or [])]
    content_titles = {c['id']: c.get('title', '') for c in (content_rows.data or [])}

    if not content_ids:
        return {
            "student_id": student_id,
            "student_name": student_name,
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "trajectory": [],
            "standards_breakdown": [],
        }

    # 5) Fetch all non-draft submissions for this student in those contents
    subs_rows = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
    ).eq('student_id', student_id).in_('content_id', content_ids).neq(
        'status', 'draft'
    ).execute()
    submissions = subs_rows.data or []

    # 6) Build trajectory from ALL submissions chronologically
    # (trajectory tolerates missing standards_mastery — only uses
    # submitted_at + percentage from the row.)
    trajectory = _build_trajectory_for_student(submissions, content_titles)

    # 7) Sanitize standards_mastery IN PLACE so attempt-mode selection
    # still sees every submission. A malformed-mastery submission stays
    # selectable (so 'latest' picks the truly latest attempt), but its
    # mastery contribution is empty.
    for s in submissions:
        _sanitize_standards_mastery(s)

    # 8) Build standards_breakdown via existing helpers + bridge code
    from collections import defaultdict
    subs_by_content = defaultdict(list)
    for s in submissions:
        cid = s.get('content_id')
        if cid:
            subs_by_content[cid].append(s)
    selected = _select_submissions_by_mode(subs_by_content, attempt_mode)
    mastery_by_code = _aggregate_mastery_for_student(
        selected, content_titles, attempt_mode, include_dok=True,
    )
    submission_lookup = {s.get('id'): s for s in submissions if s.get('id')}
    standards_breakdown = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)

    return {
        "student_id": student_id,
        "student_name": student_name,
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "trajectory": trajectory,
        "standards_breakdown": standards_breakdown,
    }
