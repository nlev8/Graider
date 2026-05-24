"""Class gradebook assembly for the student portal.

Wave 5 Slice 4 - extracted from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access; the route keeps
auth (the class-ownership 403), the request-arg parse, and jsonify, and passes
the resolved `db` handle + class_name in. This function does the roster /
content / submissions fetch and canonical-grade assembly, returning the
response payload dict (including the two empty short-circuits — there is no
cache here, so they are plain dict returns).

Helpers are imported from sibling services (student_mastery, dok) — never from
the route module (no service->route imports).
"""
import logging

from backend.services.dok import _derive_uniform_dok
from backend.services.student_mastery import (
    _select_submissions_by_mode,
    _coalesce,
    _parse_ts,
)

_logger = logging.getLogger(__name__)


def build_class_gradebook(db, class_id, class_name, attempt_mode):
    """Assemble the per-(student, assessment) canonical-grade gradebook payload.

    The route keeps the class-ownership 403 check and resolves class_name; this
    function does steps 2-5 (roster, content metadata + remediation DOK,
    paginated submissions fetch, canonical-grade map) and returns the payload
    dict. The two empty short-circuits (no roster / no assessments) return their
    payload dicts directly.
    """
    # 2) Fetch class roster: enrollments + students. Skip orphans silently.
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    student_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    student_records = []
    if student_ids:
        students_rows = db.table('students').select(
            'id, first_name, last_name'
        ).in_('id', student_ids).execute()
        seen = {s['id']: s for s in (students_rows.data or []) if s.get('id')}
        for sid in student_ids:
            sdata = seen.get(sid)
            if sdata is None:
                _logger.debug("Orphan enrollment in class %s: student_id=%s missing from students table", class_id, sid)
                continue
            student_records.append({
                'student_id': sid,
                'student_name': ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip(),
            })
        student_records.sort(key=lambda s: s['student_name'].lower())

    if not student_records:
        return {
            "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
            "students": [], "assessments": [], "grades": {},
        }

    # 3) Fetch all class assessments/assignments. Sort ASC by created_at.
    # Note: 2026-05-01 — fixed long-standing column name bug (was `publish_date`,
    # which doesn't exist on published_content; the actual write-time column is
    # `created_at`). Tests passed with mocks; this route never hit real Supabase
    # until Phase 4.3 work surfaced it.
    content_rows = db.table('published_content').select(
        'id, title, content_type, created_at, due_date, is_active, target_student_ids'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

    assessments = sorted(
        (content_rows.data or []),
        key=lambda c: (c.get('created_at') or '', c.get('id') or ''),
    )
    # Phase 4.2 #7: capture is_active and target_student_ids for the
    # remediation-badge UI. The grouping logic below keys off c['id'] only,
    # so adding these passthrough fields doesn't affect any join/aggregation.
    content_titles = {c['id']: c.get('title', '') for c in assessments}

    if not assessments:
        return {
            "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
            "students": [{'student_id': s['student_id'], 'student_name': s['student_name']} for s in student_records],
            "assessments": [], "grades": {},
        }

    # Phase 4.3 Sprint 1: derive uniform DOK for remediation rows only.
    # The metadata SELECT above intentionally omits `content` (JSONB blob —
    # could be 50-200KB per row × dozens of rows). Remediation rows are
    # typically 1-3 per class, so a focused second fetch keeps the payload
    # tight while letting the gradebook column header render a "DOK N" pill.
    remediation_ids = [
        c['id'] for c in assessments
        if c.get('target_student_ids') and c.get('id')
    ]
    assessment_dok_by_id = {}
    if remediation_ids:
        # Paginate via .range() — same pattern as the submissions fetch
        # below. PostgREST's default row cap is 1000; a class can in
        # principle accumulate more remediations over time (Phase 4.2 #8
        # caps publishes per-(teacher × student × rolling 7-day) but the
        # historical total can grow). Without pagination, later rows would
        # silently miss assessment_dok (Codex full-PR MINOR).
        page_size = 1000
        rem_start = 0
        while True:
            rem_page = db.table('published_content').select(
                'id, content'
            ).in_('id', remediation_ids).range(rem_start, rem_start + page_size - 1).execute()
            rem_rows = rem_page.data or []
            for row in rem_rows:
                cid = row.get('id')
                if cid:
                    assessment_dok_by_id[cid] = _derive_uniform_dok(row.get('content'))
            if len(rem_rows) < page_size:
                break
            rem_start += page_size

    # 4) Fetch non-draft submissions for these students × these contents.
    # Paginate via .range() because PostgREST's default row cap is 1000 —
    # a real class (30 students x 40 assessments x several attempts each) can
    # silently truncate without paging. Drop `results` from the SELECT —
    # gradebook only needs row-level columns (id/percentage/attempt_number
    # /submitted_at), not the rich per-question results JSON; this also
    # means we don't need the defensive _sanitize_standards_mastery call here.
    student_id_set = [s['student_id'] for s in student_records]
    content_id_set = [c['id'] for c in assessments]
    page_size = 1000
    submissions = []
    start = 0
    while True:
        page = db.table('student_submissions').select(
            'id, student_id, content_id, attempt_number, submitted_at, percentage, status'
        ).in_('student_id', student_id_set).in_('content_id', content_id_set).neq(
            'status', 'draft'
        ).range(start, start + page_size - 1).execute()
        rows = page.data or []
        submissions.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size

    # 5) Group by (student_id, content_id) and build the canonical-grade map
    from collections import defaultdict
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)

    grades = {}
    for sid, by_content in subs_by_student_content.items():
        per_student = {}
        for cid, subs in by_content.items():
            if not subs:
                continue
            total_attempts = len(subs)
            selected = _select_submissions_by_mode({cid: subs}, attempt_mode).get(cid, [])
            if attempt_mode == 'average':
                # mean percentage across attempts; drilldown anchor = latest.
                # Use _coalesce (NOT `or`) so a legitimate 0 doesn't fall through.
                pcts = [_coalesce(s.get('percentage'), default=0) for s in subs]
                mean_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0
                latest = max(subs, key=lambda s: (s.get('attempt_number') or 0, _parse_ts(s.get('submitted_at'))))
                per_student[cid] = {
                    'submission_id': latest.get('id'),
                    'percentage': mean_pct,
                    'attempt_number': latest.get('attempt_number'),
                    'submitted_at': latest.get('submitted_at'),
                    'total_attempts': total_attempts,
                }
            else:
                if not selected:
                    continue
                chosen = selected[0]
                per_student[cid] = {
                    'submission_id': chosen.get('id'),
                    'percentage': chosen.get('percentage'),
                    'attempt_number': chosen.get('attempt_number'),
                    'submitted_at': chosen.get('submitted_at'),
                    'total_attempts': total_attempts,
                }
        if per_student:
            grades[sid] = per_student

    return {
        "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
        "students": [{'student_id': s['student_id'], 'student_name': s['student_name']} for s in student_records],
        "assessments": [
            {'content_id': c['id'], 'title': c.get('title', ''), 'content_type': c.get('content_type'),
             # Response field kept as `publish_date` for backward compat with
             # frontend consumers that may look for it; sourced from the actual
             # `created_at` column.
             'publish_date': c.get('created_at'), 'due_date': c.get('due_date'),
             # Phase 4.2 #7: surface remediation flags for the badge UI.
             'is_active': c.get('is_active'),
             'target_student_ids': c.get('target_student_ids'),
             # Phase 4.3 Sprint 1: uniform DOK for remediation rows only.
             # Non-remediation rows always get None (no badge).
             'assessment_dok': assessment_dok_by_id.get(c['id'])}
            for c in assessments
        ],
        "grades": grades,
    }
