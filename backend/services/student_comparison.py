"""Cross-assessment comparison assembly for the student portal.

Wave 5 Slice 4c - extracted from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access. The route keeps
steps 1-5 (auth 403, content_ids CSV parse + UUID validation + count-bounds
400s, the published_content fetch + cross-class/type guard 403) and passes the
filtered `found` rows + content_ids in; this function does steps 6-10 (roster
resolve, paginated submissions, sanitize + percentage normalization, per-content
distribution stats, standards-matrix bridge) and returns the payload dict.

Helpers are imported from sibling services (student_mastery) — never from the
route module (no service->route imports).
"""
import logging

from backend.services.student_mastery import (
    _sanitize_standards_mastery,
    _select_submissions_by_mode,
    _aggregate_mastery_for_student,
    _coalesce,
)

_logger = logging.getLogger(__name__)


def build_assessment_comparison(db, class_id, class_name, content_ids, found, attempt_mode):
    """Assemble the 2-6 assessment comparison payload (distribution stats +
    standards matrix) for content rows already validated + ownership-checked by
    the route (steps 1-5). Does steps 6-10 and returns the payload dict.
    """
    # 6) Resolve valid roster (skip orphans matching Phase 3a pattern)
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    enrolled_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    valid_student_ids = []
    if enrolled_ids:
        students_rows = db.table('students').select('id').in_('id', enrolled_ids).execute()
        existing = {s['id'] for s in (students_rows.data or []) if s.get('id')}
        for sid in enrolled_ids:
            if sid in existing:
                valid_student_ids.append(sid)
            else:
                _logger.debug("Orphan enrollment in class %s: student_id=%s missing from students table", class_id, sid)

    class_roster_size = len(valid_student_ids)

    # Local numeric sanitizer — coerce percentage to float or None.
    # Use this instead of `or` because legitimate 0 must not fall through.
    def _safe_percentage(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            _logger.warning(
                "non-numeric percentage value (type=%s, value=%r) — skipping",
                type(val).__name__, val,
            )
            return None

    # 7) Fetch non-draft submissions for these students × these contents (paginated)
    submissions = []
    if valid_student_ids:
        page_size = 1000
        start = 0
        while True:
            page = db.table('student_submissions').select(
                'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
            ).in_('student_id', valid_student_ids).in_('content_id', content_ids).neq(
                'status', 'draft'
            ).range(start, start + page_size - 1).execute()
            rows = page.data or []
            submissions.extend(rows)
            if len(rows) < page_size:
                break
            start += page_size

    # 8) Sanitize-in-place
    for s in submissions:
        _sanitize_standards_mastery(s)

    # Normalize percentage to float (or 0.0 sentinel) so best-mode's max(...) doesn't
    # TypeError on mixed numeric/string values. Distribution stats still call
    # _safe_percentage downstream on `_raw_percentage`, which converts non-numeric
    # back to None and skips them — preserving the existing skip contract.
    for s in submissions:
        s['_raw_percentage'] = s.get('percentage')
        coerced = _safe_percentage(s.get('percentage'))
        s['percentage'] = coerced if coerced is not None else 0.0

    # 9) Group submissions by (student_id, content_id)
    from collections import defaultdict
    import statistics as _stats
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)

    assessments_out = []
    # Keep selected_per_content for the standards-matrix bridge in Task 4.
    selected_per_content_per_student = {}
    for cid in content_ids:
        match = next((c for c in found if c.get('id') == cid), None)
        # Same _coalesce fallback ladder as Task 2 — row column → content JSON → settings JSON.
        if match:
            content_json = match.get('content') if isinstance(match.get('content'), dict) else None
            settings_json = match.get('settings') if isinstance(match.get('settings'), dict) else None
            max_points = _coalesce(
                match.get('max_points'),
                content_json.get('max_points') if content_json else None,
                settings_json.get('max_points') if settings_json else None,
                default=0,
            )
        else:
            max_points = 0
        title = match.get('title', '') if match else ''

        percentages = []
        selected_for_this_content = {}
        for sid in valid_student_ids:
            student_subs = subs_by_student_content.get(sid, {}).get(cid, [])
            if not student_subs:
                continue
            selected = _select_submissions_by_mode({cid: student_subs}, attempt_mode).get(cid, [])
            if attempt_mode == 'average':
                # Mean across attempts for this student. Read `_raw_percentage` (set above)
                # so non-numeric values are still skipped by _safe_percentage instead of
                # being counted as the 0.0 ranking sentinel.
                attempt_pcts = [_safe_percentage(s.get('_raw_percentage')) for s in student_subs]
                attempt_pcts = [p for p in attempt_pcts if p is not None]
                if not attempt_pcts:
                    continue
                student_pct = sum(attempt_pcts) / len(attempt_pcts)
            else:
                # latest/best modes — _select_submissions_by_mode picks one submission per
                # (student, content). The pre-pass normalization above coerced `percentage`
                # to a float (or 0.0 sentinel for non-numeric), so best-mode's max(...) is
                # safe. We still read `_raw_percentage` here so submissions with originally
                # non-numeric percentages get skipped from the distribution rather than
                # contributing the 0.0 sentinel.
                if not selected:
                    continue
                student_pct = _safe_percentage(selected[0].get('_raw_percentage'))
                if student_pct is None:
                    continue
            percentages.append(student_pct)
            selected_for_this_content[sid] = selected

        selected_per_content_per_student[cid] = selected_for_this_content

        n = len(percentages)
        if n >= 2:
            sorted_pcts = sorted(percentages)
            mean_v = round(sum(sorted_pcts) / n, 2)
            median_v = round(_stats.median(sorted_pcts), 2)
            quartiles = _stats.quantiles(sorted_pcts, n=4, method='inclusive')
            q1_v, q3_v = round(quartiles[0], 2), round(quartiles[2], 2)
            min_v, max_v = sorted_pcts[0], sorted_pcts[-1]
        elif n == 1:
            mean_v = median_v = q1_v = q3_v = min_v = max_v = round(percentages[0], 2)
        else:
            mean_v = median_v = q1_v = q3_v = min_v = max_v = 0

        submission_rate = round(n / class_roster_size, 2) if class_roster_size > 0 else 0.0

        assessments_out.append({
            "content_id": cid,
            "title": title,
            "max_points": max_points,
            "n": n,
            "submission_rate": submission_rate,
            "mean": mean_v,
            "median": median_v,
            "min": min_v,
            "max": max_v,
            "q1": q1_v,
            "q3": q3_v,
            "percentages": [round(p, 2) for p in percentages],
        })

    # 10) Standards-matrix bridge: invert per-student mastery rollups into
    # per-(content_id, standard_code) class-mean cells.
    cells_accumulator: dict = {}  # cid -> standard_code -> list[float]
    content_titles = {c['id']: c.get('title', '') for c in found}
    for cid in content_ids:
        cells_accumulator[cid] = {}
        for sid, selected in selected_per_content_per_student.get(cid, {}).items():
            if not selected:
                continue
            mastery_by_code = _aggregate_mastery_for_student(
                {cid: selected}, content_titles, attempt_mode,
            )
            for code, m in mastery_by_code.items():
                pct = _safe_percentage(m.get('percentage'))
                if pct is None:
                    continue
                cells_accumulator[cid].setdefault(code, []).append(pct)

    cells_out: dict = {}
    all_standards: set = set()
    for cid, by_code in cells_accumulator.items():
        cells_out[cid] = {}
        for code, pct_list in by_code.items():
            students_assessed = len(pct_list)
            cells_out[cid][code] = {
                "percentage": round(sum(pct_list) / students_assessed, 2) if students_assessed > 0 else 0,
                "students_assessed": students_assessed,
            }
            all_standards.add(code)

    standards_matrix = {
        "standards": sorted(all_standards),
        "cells": cells_out,
    }

    return {
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "class_roster_size": class_roster_size,
        "assessments": assessments_out,
        "standards_matrix": standards_matrix,
    }
