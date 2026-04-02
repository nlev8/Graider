"""
Assistant Tools — Portal Assessment Results
============================================
Tools for querying published assessment/assignment results from the
student portal (Supabase: published_assessments + submissions tables).

These are SEPARATE from file-graded results in _load_results() which
only cover documents graded via the Grading tab. This module covers
content published via join codes or class-based publishing.
"""

import logging
from backend.utils.compliance import require_teacher_id

logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client, or None if not configured."""
    try:
        from backend.supabase_client import get_supabase
        return get_supabase()
    except Exception:
        return None


def list_published_assessments_tool(content_type=None, teacher_id='local-dev'):
    """List all published assessments/assignments for this teacher."""
    require_teacher_id(teacher_id)
    sb = _get_supabase()
    if not sb:
        return {"error": "Assessment results require Supabase. Not available in local-dev mode."}

    try:
        result = sb.table('published_assessments').select(
            'id, join_code, title, created_at, submission_count, is_active, settings'
        ).eq('teacher_id', teacher_id).order('created_at', desc=True).execute()

        assessments = []
        for a in (result.data or []):
            settings = a.get('settings') or {}
            a_type = settings.get('content_type', 'assessment')

            if content_type and a_type != content_type:
                continue

            assessments.append({
                "title": a.get('title', ''),
                "join_code": a.get('join_code', ''),
                "created_at": a.get('created_at', ''),
                "submission_count": a.get('submission_count', 0),
                "is_active": a.get('is_active', True),
                "content_type": a_type,
                "period": settings.get('period', ''),
            })

        return {"assessments": assessments, "total": len(assessments)}

    except Exception as e:
        logger.exception("list_published_assessments_tool failed")
        return {"error": f"Failed to load assessments: {e}"}


def _pct_to_letter(pct):
    """Convert a percentage to a letter grade."""
    if pct is None:
        return "N/A"
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 70:
        return "C"
    if pct >= 60:
        return "D"
    return "F"


def query_assessment_results(assessment_name=None, join_code=None,
                              min_score=None, max_score=None,
                              student_name=None,
                              teacher_id='local-dev'):
    """Query results for a published assessment/assignment."""
    require_teacher_id(teacher_id)
    sb = _get_supabase()
    if not sb:
        return {"error": "Assessment results require Supabase. Not available in local-dev mode."}

    if not assessment_name and not join_code:
        return {"error": "Provide either assessment_name or join_code to look up results."}

    try:
        if join_code:
            query = sb.table('published_assessments').select(
                'id, join_code, title, settings'
            ).eq('teacher_id', teacher_id).eq('join_code', join_code.upper())
        else:
            query = sb.table('published_assessments').select(
                'id, join_code, title, settings'
            ).eq('teacher_id', teacher_id).ilike('title', f'%{assessment_name}%')

        assessment_result = query.execute()

        if not assessment_result.data:
            search_term = join_code or assessment_name
            return {"error": f"No published assessment found matching '{search_term}'."}

        assessment = assessment_result.data[0]
        code = assessment['join_code']

        subs_result = sb.table('submissions').select(
            'id, student_name, score, total_points, percentage, submitted_at, results'
        ).eq('join_code', code).order('submitted_at', desc=True).execute()

        submissions = subs_result.data or []

        if student_name:
            student_lower = student_name.lower()
            submissions = [s for s in submissions if student_lower in (s.get('student_name') or '').lower()]

        if min_score is not None:
            submissions = [s for s in submissions if (s.get('percentage') or 0) >= min_score]

        if max_score is not None:
            submissions = [s for s in submissions if (s.get('percentage') or 0) <= max_score]

        percentages = [s['percentage'] for s in submissions if s.get('percentage') is not None]

        if percentages:
            avg = round(sum(percentages) / len(percentages), 1)
            highest = max(percentages)
            lowest = min(percentages)
        else:
            avg = None
            highest = None
            lowest = None

        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for pct in percentages:
            grade_dist[_pct_to_letter(pct)] += 1

        formatted = []
        for s in submissions:
            formatted.append({
                "student_name": s.get('student_name', ''),
                "score": s.get('score'),
                "total_points": s.get('total_points'),
                "percentage": s.get('percentage'),
                "letter_grade": _pct_to_letter(s.get('percentage')),
                "submitted_at": s.get('submitted_at', ''),
            })

        settings = assessment.get('settings') or {}

        return {
            "assessment": {
                "title": assessment.get('title', ''),
                "join_code": code,
                "content_type": settings.get('content_type', 'assessment'),
                "period": settings.get('period', ''),
            },
            "summary": {
                "total_submissions": len(submissions),
                "average_score": avg,
                "highest_score": highest,
                "lowest_score": lowest,
                "grade_distribution": grade_dist,
            },
            "submissions": formatted,
        }

    except Exception as e:
        logger.exception("query_assessment_results failed")
        return {"error": f"Failed to query assessment results: {e}"}
