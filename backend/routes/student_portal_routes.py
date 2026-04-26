"""
Student Assessment Portal Routes for Graider.
Handles publishing assessments, student access via join codes, and submission grading.
Uses Supabase for cloud storage - students can submit anytime.
"""
import json
import logging
import os
import random
import string
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as get_supabase
# Phase 4.5: this module has MIXED auth paths. Teacher-authenticated
# handlers use _get_teacher_supabase() so their requests land under RLS
# when USE_PER_USER_JWT=1. Anonymous join-code paths
# (/api/student/join/<code>, /api/student/submit/<code>) and the
# generate_join_code() uniqueness-check helper stay on service-role
# via get_supabase() — they have no teacher JWT.
from backend.supabase_client_scoped import get_request_supabase as _get_teacher_supabase

student_portal_bp = Blueprint('student_portal', __name__)
_logger = logging.getLogger(__name__)

from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import error_response, handle_route_errors
from backend.extensions import limiter
from backend.services.grading_service import grade_deterministic_question, grade_student_submission, grade_instant_only
from backend.observability import critical_path


def _spawn_thread_grading(submission_id, assessment, answers, student_info,
                         teacher_config, teacher_id, supabase_table,
                         student_accommodations):
    """Thread-based portal grading spawn.

    Used for (a) the Celery enqueue-failure fallback on the join-code path
    (Redis outage → thread so the student doesn't lose their submission)
    and (b) the class-based submission path in student_account_routes.py,
    which remains thread-backed until Phase 4.1b migrates it to Celery.

    Preserves run_portal_grading_thread's full 8-arg contract including
    accommodations.
    """
    import threading
    from backend.services.portal_grading import run_portal_grading_thread
    thread = threading.Thread(
        target=run_portal_grading_thread,
        args=(submission_id, assessment, answers, student_info,
              teacher_config, teacher_id, supabase_table, student_accommodations),
        daemon=True,
    )
    thread.start()


def generate_join_code():
    """Generate a unique 6-character join code (e.g., 'ABC123')."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choices(chars, k=6))
        # Uniqueness check must see ALL existing codes across all teachers,
        # so we stay on service-role here even when USE_PER_USER_JWT=1.
        # Per-user RLS would limit visibility to current teacher's codes
        # and increase collision probability.
        db = get_supabase()
        result = db.table('published_assessments').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code


def _parse_ts(ts):
    """Parse an ISO timestamp string to a datetime for safe comparison.
    Returns datetime.min if parsing fails so unparseable timestamps sort last.
    """
    if not ts:
        return datetime.min
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return datetime.min


def _coalesce(*vals, default=None):
    """Return the first non-None value among `vals`, or `default` if all are None.

    Use this instead of Python's `or` for fallback chains where 0 / "" / False
    are legitimate values. `or` short-circuits on falsy, corrupting numeric/text
    fallbacks (e.g., a legitimate `points_earned = 0` would silently become the
    fallback's value).
    """
    for v in vals:
        if v is not None:
            return v
    return default


def _find_content_row(db, content_id, teacher_id):
    """Locate a published content row by ID in either published_assessments
    or published_content, verifying teacher ownership.

    Returns (table_name, row_dict) or (None, None) if not found.
    """
    pa = db.table('published_assessments').select('id, settings, teacher_id').eq(
        'id', content_id
    ).execute()
    if pa.data:
        row = pa.data[0]
        if row.get('teacher_id') != teacher_id:
            return (None, None)
        return ('published_assessments', row)

    pc = db.table('published_content').select('id, settings, teacher_id').eq(
        'id', content_id
    ).execute()
    if pc.data:
        row = pc.data[0]
        if row.get('teacher_id') != teacher_id:
            return (None, None)
        return ('published_content', row)

    return (None, None)


def _select_submissions_by_mode(submissions_by_content, attempt_mode):
    """Given a dict of content_id -> list of submissions, return one selected
    submission per content based on attempt_mode.

    attempt_mode: 'latest' | 'best' | 'average'
    For 'average', returns all submissions; caller handles averaging.

    Tie-breaking:
    - 'latest': prefers higher attempt_number, then newer submitted_at (parsed)
    - 'best': prefers higher percentage, then newer submitted_at (parsed) on ties
    - 'average': no selection; all submissions used
    """
    selected = {}
    for content_id, subs in submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'best':
            best = max(subs, key=lambda s: (
                s.get('percentage') or 0,
                _parse_ts(s.get('submitted_at')),
                s.get('attempt_number') or 0,
            ))
            selected[content_id] = [best]
        elif attempt_mode == 'average':
            selected[content_id] = subs
        else:  # 'latest' (default)
            latest = max(subs, key=lambda s: (
                s.get('attempt_number') or 0,
                _parse_ts(s.get('submitted_at')),
            ))
            selected[content_id] = [latest]
    return selected


def _aggregate_mastery_for_student(selected_submissions_by_content, content_titles, attempt_mode):
    """Aggregate standards_mastery across submissions into a per-standard dict.

    Input: { content_id: [submission, ...] } (one per content unless attempt_mode=='average')
    Output: { standard_code: { percentage, points_earned, points_possible, question_count, contributing_submissions } }
    """
    from collections import defaultdict
    totals = defaultdict(lambda: {
        'points_earned': 0.0,
        'points_possible': 0.0,
        'question_count': 0,
        'contributing_submissions': [],
    })

    for content_id, subs in selected_submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'average' and len(subs) > 1:
            # Average each standard's percentage across attempts, then scale
            per_standard_avg = defaultdict(lambda: {'pct_sum': 0.0, 'count': 0, 'pts_poss': 0, 'q_count': 0, 'attempts': []})
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, m in mastery.items():
                    if not m or not m.get('points_possible'):
                        continue
                    pct = (m.get('points_earned', 0) / m['points_possible']) * 100
                    per_standard_avg[code]['pct_sum'] += pct
                    per_standard_avg[code]['count'] += 1
                    per_standard_avg[code]['pts_poss'] = m.get('points_possible', 0)
                    per_standard_avg[code]['q_count'] = m.get('question_count', 0)
                    per_standard_avg[code]['attempts'].append({
                        'submission_id': sub.get('id'),
                        'attempt_number': sub.get('attempt_number', 1),
                        'points_earned': m.get('points_earned', 0),
                        'points_possible': m['points_possible'],
                    })
            for code, agg in per_standard_avg.items():
                avg_pct = agg['pct_sum'] / agg['count']
                totals[code]['points_earned'] += (avg_pct / 100.0) * agg['pts_poss']
                totals[code]['points_possible'] += agg['pts_poss']
                totals[code]['question_count'] += agg['q_count']
                # In average mode, record each contributing attempt individually
                for a in agg['attempts']:
                    totals[code]['contributing_submissions'].append({
                        'submission_id': a['submission_id'],
                        'title': content_titles.get(content_id, ''),
                        'points_earned': a['points_earned'],
                        'points_possible': a['points_possible'],
                        'attempt_number': a['attempt_number'],
                    })
        else:
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, m in mastery.items():
                    if not m or not m.get('points_possible'):
                        continue
                    totals[code]['points_earned'] += m.get('points_earned', 0)
                    totals[code]['points_possible'] += m['points_possible']
                    totals[code]['question_count'] += m.get('question_count', 0)
                    totals[code]['contributing_submissions'].append({
                        'submission_id': sub.get('id'),
                        'title': content_titles.get(content_id, ''),
                        'points_earned': m.get('points_earned', 0),
                        'points_possible': m['points_possible'],
                        'attempt_number': sub.get('attempt_number', 1),
                    })

    # Compute final percentages and cap contributing_submissions at 10 (most recent first)
    result = {}
    for code, t in totals.items():
        pct = round((t['points_earned'] / t['points_possible']) * 100, 1) if t['points_possible'] > 0 else 0
        # Sort contributing submissions by attempt_number desc before capping
        contributing = sorted(
            t['contributing_submissions'],
            key=lambda c: c.get('attempt_number') or 0,
            reverse=True,
        )[:10]
        result[code] = {
            'percentage': pct,
            'points_earned': round(t['points_earned'], 2),
            'points_possible': t['points_possible'],
            'question_count': t['question_count'],
            'contributing_submissions': contributing,
        }
    return result


def _build_standards_breakdown_for_student(mastery_by_code, submission_lookup):
    """Convert _aggregate_mastery_for_student's dict output to the
    standards_breakdown array shape required by the report-card endpoint.

    - Sorts ASC by percentage (worst-first) per Phase 2b spec.
    - Enriches each contributing_submission with `submitted_at` and
      `percentage` (computed from points_earned / points_possible).
      Pulls `submitted_at` from `submission_lookup` (a dict keyed by
      submission_id). Keeps the existing 10-cap from the upstream helper.

    Args:
        mastery_by_code: dict from _aggregate_mastery_for_student
        submission_lookup: dict[submission_id -> submission row] for enrichment
    Returns:
        list[dict] sorted by percentage ASC; each dict has
        {code, percentage, points_earned, points_possible, question_count,
         contributing_submissions: [...]} with each contributing_submission
        having submission_id, title, attempt_number, points_earned,
        points_possible, percentage, submitted_at.
    """
    rows = []
    for code, m in mastery_by_code.items():
        enriched_contribs = []
        for c in m.get("contributing_submissions", []):
            pts_poss = c.get("points_possible") or 0
            pts_earned = c.get("points_earned") or 0
            pct = round((pts_earned / pts_poss) * 100, 1) if pts_poss > 0 else 0.0
            sub_row = submission_lookup.get(c.get("submission_id")) or {}
            enriched_contribs.append({
                "submission_id": c.get("submission_id"),
                "title": c.get("title", ""),
                "attempt_number": c.get("attempt_number"),
                "points_earned": pts_earned,
                "points_possible": pts_poss,
                "percentage": pct,
                "submitted_at": sub_row.get("submitted_at"),
            })
        rows.append({
            "code": code,
            "percentage": m.get("percentage", 0),
            "points_earned": m.get("points_earned", 0),
            "points_possible": m.get("points_possible", 0),
            "question_count": m.get("question_count", 0),
            "contributing_submissions": enriched_contribs,
        })
    rows.sort(key=lambda r: r["percentage"])  # ASC = worst-first
    return rows


def _build_trajectory_for_student(submissions, content_titles):
    """Build the chronological trajectory array for the report card.

    Sorted ASC by submitted_at; submissions with null submitted_at are
    appended at the END (we treat them as the "most recent" since their
    real position is unknown, and we'd rather not pollute the early-trend
    reading).

    Args:
        submissions: list of submission rows (id, content_id, submitted_at,
                     percentage, attempt_number, results.points_earned/possible).
        content_titles: dict[content_id -> title] for the title field.
    Returns:
        list[dict] of {submission_id, content_id, title, submitted_at,
                       percentage, attempt_number, points_earned,
                       points_possible}.
    """
    def sort_key(s):
        ts = s.get("submitted_at")
        # Use _parse_ts so mixed ISO formats ("Z" vs "+00:00" suffix) sort
        # by actual instant rather than by raw string. Null/empty timestamps
        # sort to bucket 1 (END), non-null to bucket 0 (chronological).
        return (0, _parse_ts(ts)) if ts else (1, datetime.min)

    sorted_subs = sorted(submissions, key=sort_key)
    out = []
    for s in sorted_subs:
        results = s.get("results") or {}
        out.append({
            "submission_id": s.get("id"),
            "content_id": s.get("content_id"),
            "title": content_titles.get(s.get("content_id"), ""),
            "submitted_at": s.get("submitted_at"),
            "percentage": s.get("percentage"),
            "attempt_number": s.get("attempt_number"),
            "points_earned": results.get("points_earned"),
            "points_possible": results.get("points_possible"),
        })
    return out


def _sanitize_standards_mastery(sub):
    """Sanitize standards_mastery in a submission dict IN PLACE.

    Replaces missing/non-dict outer values with {} and drops individual
    non-dict entries. Logs a WARNING per malformed case.
    Shared between get_student_report_card and get_class_progress_rank.
    Phase 2b extracted this from get_student_report_card to share between endpoints.
    """
    results = sub.get('results') or {}
    raw = results.get('standards_mastery')
    if raw is None:
        results['standards_mastery'] = {}
        sub['results'] = results
        return
    if not isinstance(raw, dict):
        _logger.warning(
            "malformed standards_mastery (type=%s) in submission %s — treating as empty",
            type(raw).__name__, sub.get('id'),
        )
        results['standards_mastery'] = {}
        sub['results'] = results
        return
    # Valid dict at the outer level; drop individual non-dict values.
    cleaned = {}
    for code, m in raw.items():
        if isinstance(m, dict):
            cleaned[code] = m
        else:
            _logger.warning(
                "malformed standards_mastery entry (code=%s, type=%s) in submission %s — skipping entry",
                code, type(m).__name__, sub.get('id'),
            )
    results['standards_mastery'] = cleaned
    sub['results'] = results


# ============ Teacher Endpoints ============

@student_portal_bp.route('/api/publish-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
@critical_path
def publish_assessment():
    """
    Publish an assessment for students to take.
    Returns a unique join code and shareable link.

    New features:
    - period: Class period for organization
    - restricted_students: List of student names (for makeup exams)
    - accommodations: Applied accommodations per student
    """
    try:
        db = _get_teacher_supabase()
        data = request.json
        assessment = data.get('assessment')
        settings = data.get('settings', {})

        if not assessment:
            return jsonify({"error": "No assessment provided"}), 400

        # Generate unique join code
        join_code = generate_join_code()

        # Get period and student restrictions
        period = settings.get('period', '')
        restricted_students = settings.get('restricted_students') or []  # Empty = open to all
        student_accommodations = settings.get('student_accommodations', {})  # {student_name: accommodation_settings}

        # Validate content_type
        content_type = settings.get('content_type', 'assessment')
        if content_type not in ('assessment', 'assignment'):
            content_type = 'assessment'

        # Validate assessment_category
        assessment_category = settings.get('assessment_category', 'formative')
        if assessment_category not in ('formative', 'summative'):
            assessment_category = 'formative'

        # Prepare settings
        db_settings = {
            "time_limit_minutes": settings.get('time_limit_minutes'),
            "allow_multiple_attempts": settings.get('allow_multiple_attempts', False),
            "show_correct_answers": settings.get('show_correct_answers', True),
            "show_score_immediately": settings.get('show_score_immediately', True),
            "require_name": settings.get('require_name', True),
            "content_type": content_type,
            "assessment_category": assessment_category,
            "period": period,
            "restricted_students": restricted_students,
            "student_accommodations": student_accommodations,
            "is_makeup": len(restricted_students) > 0,
            "available_from": settings.get('available_from'),
            "available_until": settings.get('available_until'),
            "due_date": settings.get('due_date'),
        }

        # Caller-generated UUID makes this retry-safe under full retry policy.
        result = db.table('published_assessments').upsert({
            "id": str(uuid.uuid4()),
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_id": g.teacher_id,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }, on_conflict='id').execute()

        if not result.data:
            return jsonify({"error": "Failed to publish assessment"}), 500

        # Generate shareable link (use request host for development)
        host = request.host_url.rstrip('/')
        join_link = f"{host}/join/{join_code}"

        return jsonify({
            "success": True,
            "join_code": join_code,
            "join_link": join_link,
            "period": period,
            "restricted_students": restricted_students,
            "message": f"Assessment published! Students can join with code: {join_code}"
        })

    except Exception as e:
        _logger.exception("Publish assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Saved Assessments (Local Storage) ============

SAVED_ASSESSMENTS_DIR = os.path.expanduser("~/.graider_saved_assessments")

@student_portal_bp.route('/api/save-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def save_assessment():
    """Save a generated assessment locally for later use."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        data = request.json
        assessment = data.get('assessment')
        name = data.get('name', assessment.get('title', 'Untitled'))

        if not assessment:
            return jsonify({"error": "No assessment provided"}), 400

        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_name}.json"
        filepath = os.path.join(teacher_dir, filename)

        # Save with metadata
        save_data = {
            "name": name,
            "assessment": assessment,
            "saved_at": datetime.now().isoformat(),
        }

        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)

        return jsonify({"success": True, "filename": filename, "message": f"Assessment '{name}' saved"})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/list-saved-assessments', methods=['GET'])
@require_teacher
@handle_route_errors
def list_saved_assessments():
    """List all saved assessments."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        assessments = []
        for filename in os.listdir(teacher_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(teacher_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        assessment = data.get('assessment', {})
                        # Count questions
                        question_count = 0
                        for section in assessment.get('sections', []):
                            question_count += len(section.get('questions', []))
                        assessments.append({
                            "filename": filename,
                            "name": data.get('name', filename.replace('.json', '')),
                            "title": assessment.get('title', 'Untitled'),
                            "saved_at": data.get('saved_at'),
                            "total_points": assessment.get('total_points'),
                            "question_count": question_count,
                        })
                except Exception:
                    pass

        assessments.sort(key=lambda x: x.get('saved_at', ''), reverse=True)
        return jsonify({"assessments": assessments})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/load-saved-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def load_saved_assessment():
    """Load a saved assessment by filename."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        data = request.json
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "No filename provided"}), 400

        # Prevent path traversal
        filepath = os.path.join(teacher_dir, filename)
        if not os.path.realpath(filepath).startswith(os.path.realpath(teacher_dir)):
            return jsonify({"error": "Invalid filename"}), 400

        if not os.path.exists(filepath):
            return jsonify({"error": "Assessment not found"}), 404

        with open(filepath, 'r') as f:
            save_data = json.load(f)

        return jsonify({
            "success": True,
            "assessment": save_data.get('assessment'),
            "name": save_data.get('name'),
        })

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/delete-saved-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_saved_assessment():
    """Delete a saved assessment."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        data = request.json
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "No filename provided"}), 400

        # Prevent path traversal
        filepath = os.path.join(teacher_dir, filename)
        if not os.path.realpath(filepath).startswith(os.path.realpath(teacher_dir)):
            return jsonify({"error": "Invalid filename"}), 400

        if os.path.exists(filepath):
            os.remove(filepath)

        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessments', methods=['GET'])
@require_teacher
@handle_route_errors
def list_published_assessments():
    """List all published assessments for the teacher."""
    try:
        db = _get_teacher_supabase()

        result = db.table('published_assessments').select(
            'id, join_code, title, created_at, submission_count, is_active, teacher_name, settings'
        ).eq('teacher_id', g.teacher_id).order('created_at', desc=True).execute()

        assessments = [{
            "id": a.get('id'),
            "join_code": a.get('join_code'),
            "title": a.get('title'),
            "created_at": a.get('created_at'),
            "submission_count": a.get('submission_count', 0),
            "is_active": a.get('is_active', True),
            "content_type": a.get('settings', {}).get('content_type', 'assessment'),
            "period": a.get('settings', {}).get('period', ''),
            "is_makeup": a.get('settings', {}).get('is_makeup', False),
            "restricted_students": a.get('settings', {}).get('restricted_students', []),
            "unit_name": a.get('settings', {}).get('unit_name', ''),
            "tags": a.get('settings', {}).get('tags', []),
        } for a in result.data]

        return jsonify({"assessments": assessments})

    except Exception as e:
        _logger.exception("List assessments error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/results', methods=['GET'])
@require_teacher
@handle_route_errors
def get_assessment_results(code):
    """Get all submissions for a published assessment."""
    try:
        db = _get_teacher_supabase()
        code = code.upper()

        # Get assessment — scoped to this teacher
        assessment_result = db.table('published_assessments').select('*').eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        if not assessment_result.data:
            return jsonify({"error": "Assessment not found"}), 404

        assessment_data = assessment_result.data[0]

        # Get submissions
        submissions_result = db.table('submissions').select('*').eq('join_code', code).order('submitted_at', desc=True).execute()

        submissions = [{
            "submission_id": s.get('id'),
            "student_name": s.get('student_name'),
            "score": s.get('score'),
            "total_points": s.get('total_points'),
            "percentage": s.get('percentage'),
            "time_taken_seconds": s.get('time_taken_seconds'),
            "submitted_at": s.get('submitted_at'),
            "results": s.get('results'),
        } for s in submissions_result.data]

        return jsonify({
            "assessment": {
                "title": assessment_data.get('title'),
                "join_code": code,
                "created_at": assessment_data.get('created_at'),
                "is_active": assessment_data.get('is_active'),
            },
            "submissions": submissions,
            "total_submissions": len(submissions),
        })

    except Exception as e:
        _logger.exception("Get results error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/toggle', methods=['POST'])
@require_teacher
@handle_route_errors
def toggle_assessment(code):
    """Activate or deactivate a published assessment."""
    try:
        db = _get_teacher_supabase()
        code = code.upper()

        # Get current status — scoped to this teacher
        result = db.table('published_assessments').select('is_active').eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        if not result.data:
            return jsonify({"error": "Assessment not found"}), 404

        current_active = result.data[0].get('is_active', True)
        new_active = not current_active

        # Update
        db.table('published_assessments').update({'is_active': new_active}).eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        status = "activated" if new_active else "deactivated"
        return jsonify({
            "success": True,
            "active": new_active,
            "message": f"Assessment {status}"
        })

    except Exception as e:
        _logger.exception("Toggle assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_published_assessment(code):
    """Delete a published assessment and all its submissions."""
    try:
        db = _get_teacher_supabase()
        code = code.upper()

        # Verify ownership before deleting
        ownership = db.table('published_assessments').select('id').eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()
        if not ownership.data:
            return jsonify({"error": "Assessment not found"}), 404

        # Delete submissions first (cascade should handle this, but be explicit)
        db.table('submissions').delete().eq('join_code', code).execute()

        # Delete assessment — scoped to this teacher
        result = db.table('published_assessments').delete().eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        return jsonify({"success": True, "message": "Assessment deleted"})

    except Exception as e:
        _logger.exception("Delete assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Student Endpoints ============

@student_portal_bp.route('/api/student/join/<code>', methods=['GET'])
@limiter.limit("30 per minute")
@handle_route_errors
def get_assessment_for_student(code):
    """
    Get assessment details for a student joining with a code.
    Returns assessment without answers for student to take.

    Rate-limited at 30/min per IP (Phase 4.6) to prevent join-code
    enumeration attacks. Typical student traffic is <5/min per IP.
    """
    try:
        # Anonymous join-code path — no teacher JWT, so service-role.
        db = get_supabase()
        code = code.upper()

        result = db.table('published_assessments').select('*').eq('join_code', code).execute()

        if not result.data:
            return jsonify({"error": "Assessment not found. Check your join code."}), 404

        data = result.data[0]

        # Check if assessment is active
        if not data.get('is_active', True):
            return jsonify({"error": "This assessment is no longer accepting submissions."}), 403

        assessment = data.get('assessment', {})
        settings = data.get('settings', {})

        # Shared study-material content (study guide, flashcards, etc.) — return directly
        content_type = settings.get('content_type') or assessment.get('content_type')
        # Only study materials get the material response format.
        # Assignments and assessments both get the sections/questions format.
        material_types = ('study_guide', 'flashcards', 'slide_deck', 'mind_map',
                          'audio_overview', 'video_overview', 'infographic', 'data_table')
        if content_type and content_type in material_types:
            resp = {
                "content_type": content_type,
                "title": assessment.get('title', data.get('title', content_type)),
                "teacher": data.get('teacher_name', 'Teacher'),
            }
            # JSON types: quiz, flashcards, mind_map
            if assessment.get('data'):
                resp["data"] = assessment['data']
            # Legacy flashcards format
            if assessment.get('cards'):
                resp["data"] = assessment['cards']
            # Text types: study_guide
            if assessment.get('content'):
                resp["content"] = assessment['content']
            # Media types: provide URL
            if assessment.get('shared_file'):
                resp["media_url"] = "/api/student/shared-media/" + code
            return jsonify(resp)

        # Remove answers from questions before sending to student
        sanitized_sections = []
        for section in assessment.get('sections', []):
            sanitized_questions = []
            for q in section.get('questions', []):
                student_question = {
                    "number": q.get('number'),
                    "question": q.get('question'),
                    "type": q.get('type') or q.get('question_type', 'short_answer'),
                    "points": q.get('points'),
                    "options": q.get('options'),
                    "terms": q.get('terms'),
                    "definitions": q.get('definitions'),
                }
                sanitized_questions.append(student_question)

            sanitized_sections.append({
                "name": section.get('name'),
                "instructions": section.get('instructions'),
                "questions": sanitized_questions,
            })

        # Check for student restrictions (makeup exams)
        restricted_students = settings.get('restricted_students', [])
        student_accommodations = settings.get('student_accommodations', {})
        is_makeup = settings.get('is_makeup', False)

        return jsonify({
            "title": assessment.get('title'),
            "instructions": assessment.get('instructions'),
            "total_points": assessment.get('total_points'),
            "time_estimate": assessment.get('time_estimate'),
            "sections": sanitized_sections,
            "settings": {
                "content_type": content_type or 'assessment',
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
                "is_makeup": is_makeup,
                "restricted_students": restricted_students,  # Frontend checks if student allowed
                "period": settings.get('period', ''),
            },
            "student_accommodations": student_accommodations,  # Accommodations per student
            "teacher": data.get('teacher_name', 'Teacher'),
        })

    except Exception as e:
        _logger.exception("Get assessment for student error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/student/submit/<code>', methods=['POST'])
@limiter.limit("10 per minute")
@handle_route_errors
@critical_path
def submit_assessment(code):
    """
    Submit student answers for grading.
    Returns immediate feedback and score.
    """
    try:
        # Anonymous join-code path — no teacher JWT, so service-role.
        db = get_supabase()
        code = code.upper()

        # Get assessment
        assessment_result = db.table('published_assessments').select('*').eq('join_code', code).execute()

        if not assessment_result.data:
            return jsonify({"error": "Assessment not found"}), 404

        assessment_data = assessment_result.data[0]

        # Check if active
        if not assessment_data.get('is_active', True):
            return jsonify({"error": "This assessment is no longer accepting submissions."}), 403

        data = request.json
        student_name = data.get('student_name', 'Anonymous')
        answers = data.get('answers', {})
        time_taken_seconds = data.get('time_taken_seconds')

        settings = assessment_data.get('settings', {})

        # Enforce availability window (assessments)
        available_from = settings.get('available_from')
        available_until = settings.get('available_until')
        if available_from or available_until:
            now = datetime.now(timezone.utc).isoformat()
            if available_from and now < available_from:
                return jsonify({"error": "This assessment is not yet available."}), 403
            if available_until and now > available_until:
                return jsonify({"error": "This assessment is no longer accepting submissions."}), 403

        # Check for duplicate submission
        if not settings.get('allow_multiple_attempts', False):
            existing = db.table('submissions').select('id, results').eq('join_code', code).ilike('student_name', student_name).execute()
            if existing.data:
                return jsonify({
                    "error": "You have already submitted this assessment.",
                    "previous_results": existing.data[0].get('results')
                }), 400

        # Determine grading strategy
        assessment = assessment_data.get('assessment', {})
        from backend.services.portal_grading import has_written_questions
        needs_multipass = has_written_questions(assessment)

        if needs_multipass:
            # Mixed assignment: grade MC/TF instantly, queue written for multipass
            results = grade_instant_only(assessment, answers)
        else:
            # MC-only: use existing instant grader (no AI calls needed)
            results = grade_student_submission(assessment, answers)
        _logger.info("Grading complete: score=%s/%s", results.get('score'), results.get('total_points'))

        # Insert submission
        submission_row = {
            "assessment_id": assessment_data.get('id'),
            "join_code": code,
            "student_name": student_name,
            "answers": answers,
            "results": results,
            "time_taken_seconds": time_taken_seconds,
            "graded_at": datetime.now().isoformat(),
        }
        if needs_multipass:
            submission_row["score"] = None
            submission_row["total_points"] = results.get('total_points')
            submission_row["percentage"] = None
            # Note: submissions table has no grading_status column
            # Status is tracked in the results JSON instead
        else:
            submission_row["score"] = results.get('score')
            submission_row["total_points"] = results.get('total_points')
            submission_row["percentage"] = results.get('percentage')

        # Caller-generated UUID + upsert on id makes this retry-safe.
        submission_row['id'] = str(uuid.uuid4())
        try:
            submission_result = db.table('submissions').upsert(
                submission_row, on_conflict='id'
            ).execute()
        except Exception as insert_err:
            if '23505' in str(insert_err) or 'duplicate' in str(insert_err).lower():
                return jsonify({
                    "error": "You have already submitted this assessment.",
                }), 400
            raise

        if not submission_result.data:
            return jsonify({"error": "Failed to save submission"}), 500

        submission_id = submission_result.data[0].get('id')

        # Spawn multipass grading thread for written questions
        if needs_multipass:
            from backend.services.grading_service import load_teacher_config

            # Hoist context values that both the Celery path and the thread
            # fallback need. Before Phase 4.1 these were constructed inline
            # inside the threading.Thread(...) spawn.
            teacher_id = assessment_data.get("teacher_id") or ""
            teacher_config = load_teacher_config(teacher_id)
            student_info = {"student_name": student_name, "student_id": "", "email": ""}
            student_accommodations = assessment_data.get("settings", {}).get("student_accommodations", {})

            # Phase 4.1 PR3: Celery is the always-on primary path for join-code
            # grading. The CELERY_PORTAL_GRADING flag gate + else-branch thread
            # spawn were removed after the 48h post-flip monitor window closed
            # green. Thread-based grading still runs for the class-based
            # submission path (backend/routes/student_account_routes.py); that
            # migration is Phase 4.1b scope.
            from backend.tasks.grading_tasks import grade_portal_submission
            # Enqueue-failure fallback — broker outage degrades to the
            # legacy thread path so the student doesn't lose their
            # submission. Catch ONLY known broker-communication failures:
            #   - kombu.exceptions.OperationalError: Kombu's wrapped
            #     connection failure (redis down, auth, network)
            #   - kombu.exceptions.ConnectionError: transport-layer
            #     errors (NOT Python's builtin ConnectionError)
            # Do NOT catch bare Exception — programming bugs
            # (serialization, missing decorator) must surface loudly.
            import kombu.exceptions
            try:
                district_id = getattr(g, 'district_id', None)
                user_id = getattr(g, 'user_id', None)
            except RuntimeError:
                district_id = None
                user_id = None
            try:
                grade_portal_submission.delay(
                    submission_id,
                    teacher_id,
                    'submissions',
                    district_id=district_id,
                    user_id=user_id,
                )
            except (kombu.exceptions.OperationalError,
                    kombu.exceptions.ConnectionError) as e:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag('celery_enqueue_failure', True)
                    scope.level = 'warning'
                    sentry_sdk.capture_exception(e)
                _spawn_thread_grading(submission_id, assessment, answers,
                                      student_info, teacher_config, teacher_id,
                                      'submissions', student_accommodations)

            # Mark results as partially graded for frontend
            results["grading_status"] = "partial"
            results["message"] = "Multiple choice and true/false graded. Written responses pending teacher review."

        # Prepare response based on settings
        # Use assessment_data settings (not shadowed variable) for display decisions
        publish_settings = assessment_data.get('settings', {})
        response = {
            "success": True,
            "submission_id": submission_id,
            "student_name": student_name,
        }

        # Assessment mode: if both score and answers are hidden, return pending_review
        if not publish_settings.get('show_score_immediately', True) and not publish_settings.get('show_correct_answers', True):
            response["grading_status"] = "pending_review"
            response["message"] = "Submitted! Your teacher will review and share your results."
        elif results.get("grading_status") == "partial":
            # Mixed assignment: show MC scores but not percentage
            mc_correct = sum(1 for q in (results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("short_answer", "extended_response", "essay", "written"))
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = results["message"]
            if publish_settings.get('show_correct_answers', True):
                response["detailed_results"] = [q for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching")]
        else:
            # MC-only: show full results
            if publish_settings.get('show_score_immediately', True):
                response["score"] = results.get('score')
                response["total_points"] = results.get('total_points')
                response["percentage"] = results.get('percentage')
                response["feedback_summary"] = results.get('feedback_summary')
            if publish_settings.get('show_correct_answers', True):
                response["detailed_results"] = results.get('questions')

        return jsonify(response)

    except Exception as e:
        _logger.exception("Submit assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


RESOURCE_CONTENT_TYPES = ('study_guide', 'flashcards', 'slide_deck')


@student_portal_bp.route('/api/teacher/shared-resources', methods=['GET'])
@require_teacher
@handle_route_errors
def list_shared_resources():
    """List all shared resources (flashcards, study guides, slide decks) for the teacher."""
    try:
        db = _get_teacher_supabase()

        result = db.table('published_content').select(
            'id, title, content_type, class_id, created_at, is_active, settings'
        ).eq('teacher_id', g.teacher_id).in_(
            'content_type', list(RESOURCE_CONTENT_TYPES)
        ).order('created_at', desc=True).execute()

        # Fetch class names for display
        class_ids = list(set(r.get('class_id') for r in result.data if r.get('class_id')))
        class_names = {}
        if class_ids:
            classes_result = db.table('classes').select('id, name').in_('id', class_ids).execute()
            class_names = {c['id']: c['name'] for c in classes_result.data}

        resources = [{
            "id": r.get('id'),
            "title": r.get('title'),
            "content_type": r.get('content_type'),
            "class_id": r.get('class_id'),
            "class_name": class_names.get(r.get('class_id'), 'Unknown'),
            "created_at": r.get('created_at'),
            "is_active": r.get('is_active', True),
            "unit_name": r.get('settings', {}).get('unit_name', ''),
            "tags": r.get('settings', {}).get('tags', []),
        } for r in result.data]

        return jsonify({"resources": resources})

    except Exception as e:
        _logger.exception("List shared resources error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_shared_resource(resource_id):
    """Delete a single shared resource."""
    try:
        db = _get_teacher_supabase()

        # Verify ownership
        check = db.table('published_content').select('id').eq(
            'id', resource_id
        ).eq('teacher_id', g.teacher_id).execute()
        if not check.data:
            return jsonify({"error": "Resource not found"}), 404

        db.table('published_content').delete().eq('id', resource_id).execute()
        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Delete shared resource error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/delete-shared-resources-bulk', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_shared_resources_bulk():
    """Delete all shared resources matching a title for this teacher."""
    try:
        db = _get_teacher_supabase()
        data = request.json
        title = data.get('title', '').strip()

        if not title:
            return jsonify({"error": "Title is required"}), 400

        result = db.table('published_content').delete().eq(
            'teacher_id', g.teacher_id
        ).eq('title', title).in_(
            'content_type', list(RESOURCE_CONTENT_TYPES)
        ).execute()

        deleted = len(result.data) if result.data else 0
        return jsonify({"success": True, "deleted": deleted})

    except Exception as e:
        _logger.exception("Bulk delete shared resources error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>/unit', methods=['POST'])
@require_teacher
@handle_route_errors
def update_shared_resource_unit(resource_id):
    """Update the unit_name in a published content row's settings.
    Works for both published_assessments and published_content tables.
    """
    try:
        db = _get_teacher_supabase()
        data = request.json
        unit_name = data.get('unit_name', '').strip()

        table_name, row = _find_content_row(db, resource_id, g.teacher_id)
        if not row:
            return jsonify({"error": "Resource not found"}), 404

        existing_settings = row.get('settings') or {}
        existing_settings['unit_name'] = unit_name

        db.table(table_name).update({
            'settings': existing_settings
        }).eq('id', resource_id).execute()

        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Update unit error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/end-attempt/<submission_id>', methods=['POST'])
@require_teacher
@handle_route_errors
def end_student_attempt(submission_id):
    """Force-end a student's in-progress draft, converting it to a submitted row."""
    try:
        db = _get_teacher_supabase()

        # Fetch the draft
        sub = db.table('student_submissions').select('*').eq('id', submission_id).execute()
        if not sub.data:
            return jsonify({"error": "Submission not found"}), 404
        row = sub.data[0]

        if row.get('status') != 'draft':
            return jsonify({"error": "Not an in-progress draft"}), 400

        # Verify teacher owns the class this content belongs to
        content_id = row.get('content_id')
        content = db.table('published_content').select('teacher_id').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        # Convert draft to submission
        db.table('student_submissions').update({
            'status': 'submitted',
            'answers': row.get('draft_answers') or {},
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'results': {'force_ended_by_teacher': True},
        }).eq('id', submission_id).execute()

        return jsonify({"success": True})
    except Exception as e:
        _logger.exception("End attempt error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/content/<content_id>/in-progress', methods=['GET'])
@require_teacher
@handle_route_errors
def list_in_progress_drafts(content_id):
    """List students currently drafting a specific piece of class-based content."""
    try:
        db = _get_teacher_supabase()

        # Verify teacher owns this content
        content = db.table('published_content').select('teacher_id, settings').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        drafts = db.table('student_submissions').select(
            'id, student_name, draft_answers, marked_for_review, time_started_at'
        ).eq('content_id', content_id).eq('status', 'draft').execute()

        now = datetime.now(timezone.utc)
        rows = []
        for d in drafts.data:
            answers = d.get('draft_answers') or {}
            answered_count = sum(1 for v in answers.values() if v not in (None, '', []))
            elapsed_seconds = 0
            remaining_seconds = None
            if d.get('time_started_at'):
                started = datetime.fromisoformat(d['time_started_at'].replace('Z', '+00:00'))
                elapsed_seconds = int((now - started).total_seconds())
                if time_limit_seconds:
                    remaining_seconds = max(0, time_limit_seconds - elapsed_seconds)
            rows.append({
                "submission_id": d['id'],
                "student_name": d.get('student_name'),
                "answered_count": answered_count,
                "elapsed_seconds": elapsed_seconds,
                "remaining_seconds": remaining_seconds,
            })

        return jsonify({"drafts": rows})
    except Exception as e:
        _logger.exception("List in-progress error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/content/<content_id>/submissions', methods=['GET'])
@require_teacher
@handle_route_errors
def list_content_submissions(content_id):
    """List all submissions (all attempts per student) for a class-based assessment."""
    try:
        db = _get_teacher_supabase()

        # Verify teacher owns this content
        content = db.table('published_content').select('teacher_id, title, content, settings').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        # Fetch all submissions for this content (excluding drafts)
        submissions = db.table('student_submissions').select('*').eq(
            'content_id', content_id
        ).neq('status', 'draft').order('student_id', desc=False).order('attempt_number', desc=False).execute()

        # Group by student
        groups = {}
        for s in submissions.data:
            sid = s.get('student_id') or s.get('student_name')
            if sid not in groups:
                groups[sid] = {
                    'student_id': s.get('student_id'),
                    'student_name': s.get('student_name'),
                    'student_id_number': s.get('student_id_number'),
                    'period': s.get('period'),
                    'attempts': [],
                }
            groups[sid]['attempts'].append({
                'submission_id': s.get('id'),
                'attempt_number': s.get('attempt_number', 1),
                'score': s.get('score'),
                'total_points': s.get('total_points'),
                'percentage': s.get('percentage'),
                'letter_grade': s.get('letter_grade'),
                'status': s.get('status'),
                'time_taken_seconds': s.get('time_taken_seconds'),
                'question_times': s.get('question_times'),
                'submitted_at': s.get('submitted_at'),
                'results': s.get('results'),
            })

        return jsonify({
            "content_id": content_id,
            "title": content.data[0].get('title'),
            "content": content.data[0].get('content'),
            "students": list(groups.values()),
        })
    except Exception as e:
        _logger.exception("List content submissions error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/class/<class_id>/progress-rank', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_progress_rank(class_id):
    """Return a class-scoped progress rank grid aggregating standards_mastery
    across all graded submissions for students in the class.

    Query params:
      attempt_mode: 'latest' (default) | 'best' | 'average'
    """
    try:
        db = _get_teacher_supabase()

        attempt_mode = request.args.get('attempt_mode', 'latest')
        if attempt_mode not in ('latest', 'best', 'average'):
            attempt_mode = 'latest'

        # Verify class ownership
        cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
        if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403
        class_name = cls.data[0].get('name')

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
            return jsonify({
                "class_id": class_id,
                "class_name": class_name,
                "attempt_mode": attempt_mode,
                "standards": [],
                "students": [],
            })

        # Fetch all published_content for this class (assessments/assignments only)
        content = db.table('published_content').select(
            'id, title, content_type'
        ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

        content_ids = [c['id'] for c in content.data or []]
        content_titles = {c['id']: c.get('title', '') for c in content.data or []}

        if not content_ids:
            return jsonify({
                "class_id": class_id,
                "class_name": class_name,
                "attempt_mode": attempt_mode,
                "standards": [],
                "students": [{'student_id': s['student_id'], 'student_name': s['student_name'], 'mastery': {}} for s in student_records],
            })

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

        return jsonify({
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "standards": sorted(all_standards_in_class),
            "students": students_output,
        })
    except Exception as e:
        _logger.exception("Progress rank error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/class/<class_id>/student/<student_id>/report-card', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_report_card(class_id, student_id):
    """Return per-student report card: trajectory + standards breakdown.

    Class-scoped view of a single student's mastery within ONE class.
    Reuses _select_submissions_by_mode + _aggregate_mastery_for_student
    + bridge helpers to assemble the response.

    Spec: docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md
    """
    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Student-in-class check
    enrollment = db.table('class_students').select('student_id').eq(
        'class_id', class_id
    ).eq('student_id', student_id).execute()
    if not enrollment.data:
        return error_response("Student not in class", 404)

    # 3) Fetch student name (orphan-enrollment guard)
    student_row = db.table('students').select(
        'id, first_name, last_name'
    ).eq('id', student_id).execute()
    if not student_row.data:
        return error_response("Student not in class", 404)
    student_name = (
        (student_row.data[0].get('first_name') or '') + ' ' +
        (student_row.data[0].get('last_name') or '')
    ).strip()

    # 4) Fetch all class assessments/assignments
    content_rows = db.table('published_content').select(
        'id, title, content_type'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()
    content_ids = [c['id'] for c in (content_rows.data or [])]
    content_titles = {c['id']: c.get('title', '') for c in (content_rows.data or [])}

    if not content_ids:
        return jsonify({
            "student_id": student_id,
            "student_name": student_name,
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "trajectory": [],
            "standards_breakdown": [],
        })

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
    mastery_by_code = _aggregate_mastery_for_student(selected, content_titles, attempt_mode)
    submission_lookup = {s.get('id'): s for s in submissions if s.get('id')}
    standards_breakdown = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)

    return jsonify({
        "student_id": student_id,
        "student_name": student_name,
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "trajectory": trajectory,
        "standards_breakdown": standards_breakdown,
    })


@student_portal_bp.route('/api/teacher/class/<class_id>/gradebook', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_gradebook(class_id):
    """Return per-(student, assessment) canonical grades for a class.

    Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
    """
    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # Skeleton: empty arrays. Happy-path data fetch lands in Task 3.
    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "students": [],
        "assessments": [],
        "grades": {},
    })


@student_portal_bp.route('/api/teacher/tags', methods=['GET'])
@require_teacher
@handle_route_errors
def list_teacher_tags():
    """Return all unique tags across the teacher's published content (both tables),
    including unit_name values and tags array values.
    """
    try:
        db = _get_teacher_supabase()
        teacher_id = g.teacher_id

        tag_set = set()

        pa = db.table('published_assessments').select('settings').eq(
            'teacher_id', teacher_id
        ).execute()
        for row in pa.data or []:
            s = row.get('settings') or {}
            unit = s.get('unit_name')
            if unit and isinstance(unit, str) and unit.strip():
                tag_set.add(unit.strip())
            for t in (s.get('tags') or []):
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())

        pc = db.table('published_content').select('settings').eq(
            'teacher_id', teacher_id
        ).execute()
        for row in pc.data or []:
            s = row.get('settings') or {}
            unit = s.get('unit_name')
            if unit and isinstance(unit, str) and unit.strip():
                tag_set.add(unit.strip())
            for t in (s.get('tags') or []):
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())

        return jsonify({"tags": sorted(tag_set)})
    except Exception as e:
        _logger.exception("List teacher tags error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/published-content/<content_id>/tags', methods=['POST'])
@require_teacher
@handle_route_errors
def set_content_tags(content_id):
    """Replace the tags array on a published content row (either table).

    Request: { "tags": [str, ...] }
    Preserves all other settings fields.
    """
    try:
        db = _get_teacher_supabase()
        data = request.json or {}
        raw_tags = data.get('tags')
        if not isinstance(raw_tags, list):
            return jsonify({"error": "tags must be an array"}), 400

        seen = set()
        clean_tags = []
        for t in raw_tags:
            if not isinstance(t, str):
                continue
            s = t.strip()
            if not s or s in seen:
                continue
            if len(s) > 100:
                s = s[:100]
            seen.add(s)
            clean_tags.append(s)

        table_name, row = _find_content_row(db, content_id, g.teacher_id)
        if not row:
            return jsonify({"error": "Content not found"}), 404

        existing_settings = row.get('settings') or {}
        existing_settings['tags'] = clean_tags

        db.table(table_name).update({'settings': existing_settings}).eq('id', content_id).execute()
        return jsonify({"success": True, "tags": clean_tags})
    except Exception as e:
        _logger.exception("Set content tags error")
        return jsonify({"error": "An internal error occurred"}), 500

