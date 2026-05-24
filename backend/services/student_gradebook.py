"""Class gradebook assembly for the student portal.

Wave 5 Slice 4 - extracted from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access; routes keep auth
(the class-ownership 403 / interleaved 404s), request-arg parsing, and jsonify,
and pass the resolved `db` handle + teacher_id/class_name in.
- build_class_gradebook: roster/content/submissions fetch + canonical-grade
  assembly -> payload dict (two empty short-circuits return plain dicts; no cache).
- build_submission_detail: per-submission detail assembly -> (payload, err); the
  interleaved not-found/not-authorized cases return (None, (message, status)) for
  the route to translate via error_response.

Helpers are imported from sibling services (student_mastery, dok) — never from
the route module (no service->route imports).
"""
import logging

from backend.services.dok import _derive_uniform_dok, _validate_dok
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


def build_submission_detail(db, submission_id, teacher_id):
    """Assemble per-submission detail (metadata + per-question breakdown +
    sibling attempts), or return an error to translate at the route.

    Returns ``(payload, None)`` on success, or ``(None, (message, status))``
    for the interleaved not-found / not-authorized cases. The route keeps the
    Flask ``error_response`` translation and supplies ``teacher_id`` (the
    service never reads Flask ``g``).
    """
    # 1) Look up the submission
    sub_row = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status, score, total_points'
    ).eq('id', submission_id).execute()
    if not sub_row.data:
        return (None, ("Submission not found", 404))
    sub = sub_row.data[0]

    # 2) Look up the content. Phase 4.2 #7: also fetch is_active and
    # target_student_ids so the drawer header can render the remediation
    # badges that match the gradebook column header.
    content_id = sub.get('content_id')
    content_row = db.table('published_content').select(
        'id, title, class_id, is_active, target_student_ids, content'
    ).eq('id', content_id).execute()
    if not content_row.data:
        return (None, ("Submission's content no longer exists", 404))
    content = content_row.data[0]

    # 3) Verify class ownership
    class_row = db.table('classes').select('id, teacher_id').eq('id', content.get('class_id')).execute()
    if not class_row.data or class_row.data[0].get('teacher_id') != teacher_id:
        return (None, ("Not authorized", 403))

    # 4) Look up the student
    student_id = sub.get('student_id')
    student_row = db.table('students').select(
        'id, first_name, last_name'
    ).eq('id', student_id).execute()
    if not student_row.data:
        return (None, ("Student not found", 404))
    sdata = student_row.data[0]
    student_name = ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip()

    # 5) Sibling attempts (same student × same content)
    siblings_row = db.table('student_submissions').select(
        'id, attempt_number, submitted_at, percentage'
    ).eq('student_id', student_id).eq('content_id', content_id).execute()
    siblings = sorted(
        siblings_row.data or [],
        key=lambda s: (s.get('attempt_number') or 0, _parse_ts(s.get('submitted_at'))),
    )

    # 6) Top-level score with row + results fallback. Use _coalesce so legitimate 0 isn't lost.
    results = sub.get('results') or {}
    points_earned = _coalesce(results.get('score'), sub.get('score'), default=0)
    points_possible = _coalesce(results.get('total_points'), sub.get('total_points'), default=0)

    # 7) Per-question normalization (spec fallback rules)
    raw_questions = results.get('questions')
    questions = []
    if isinstance(raw_questions, list):
        for q in raw_questions:
            if not isinstance(q, dict):
                _logger.warning("malformed question entry (type=%s) in submission %s — skipping",
                                type(q).__name__, submission_id)
                continue
            questions.append({
                "question_text": _coalesce(q.get('question'), q.get('question_text'), default=''),
                "question_type": _coalesce(q.get('type'), q.get('question_type'), default='unknown'),
                "student_answer": _coalesce(q.get('student_answer'), q.get('answer'), default=''),
                "correct_answer": q.get('correct_answer'),
                "is_correct": q.get('is_correct'),
                "ai_feedback": _coalesce(q.get('feedback'), q.get('reasoning'), q.get('quality'), default=''),
                "points_earned": _coalesce(q.get('points_earned'), q.get('score'), default=0),
                "points_possible": _coalesce(q.get('points_possible'), q.get('points'), default=0),
                "dok": _validate_dok(q.get('dok')),
            })
    elif raw_questions is not None:
        _logger.warning("malformed results.questions (type=%s) in submission %s — returning empty",
                        type(raw_questions).__name__, submission_id)

    return ({
        "submission_id": sub.get('id'),
        "student_id": student_id,
        "student_name": student_name,
        "content_id": content_id,
        "content_title": content.get('title', ''),
        # Phase 4.2 #7: surface remediation flags so SubmissionDetail drawer
        # header can render the badges (matches Gradebook column header).
        "is_active": content.get('is_active'),
        "target_student_ids": content.get('target_student_ids'),
        # Phase 4.3 Sprint 1: uniform DOK across all questions, else null.
        # Drives the optional "DOK N" pill in RemediationBadges.
        "assessment_dok": _derive_uniform_dok(content.get('content')),
        "attempt_number": sub.get('attempt_number'),
        "total_attempts": len(siblings),
        "submitted_at": sub.get('submitted_at'),
        "percentage": sub.get('percentage'),
        "points_earned": points_earned,
        "points_possible": points_possible,
        "questions": questions,
        "sibling_attempts": [
            {"submission_id": s.get('id'), "attempt_number": s.get('attempt_number'),
             "submitted_at": s.get('submitted_at'), "percentage": s.get('percentage')}
            for s in siblings
        ],
    }, None)
