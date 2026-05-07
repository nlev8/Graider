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


_DEFAULT_PAGE_SIZE = 100
_MAX_PAGE_SIZE = 500


def query_assessment_results(assessment_name=None, join_code=None,
                              min_score=None, max_score=None,
                              student_name=None,
                              limit=None, offset=0,
                              teacher_id='local-dev'):
    """Query results for a published assessment/assignment.

    Closes audit MAJOR #12 (Codex full-codebase audit 2026-05-06): the
    previous implementation fetched ALL submissions for the join_code
    then filtered in Python — unbounded memory growth on assessments
    with many submissions. Filters now push to Supabase; the submission
    list is paginated; summary stats are computed in a separate light
    `percentage`-only query (bounded by the assessment's total
    submission count regardless of page size).

    Args:
        limit: Page size for the `submissions` list (default 100, cap 500).
            Summary stats always reflect ALL matching submissions.
        offset: Page offset for `submissions`.
    """
    require_teacher_id(teacher_id)
    sb = _get_supabase()
    if not sb:
        return {"error": "Assessment results require Supabase. Not available in local-dev mode."}

    if not assessment_name and not join_code:
        return {"error": "Provide either assessment_name or join_code to look up results."}

    # Validate pagination args defensively — assistant LLM tool calls can
    # pass arbitrary values.
    try:
        page_size = int(limit) if limit is not None else _DEFAULT_PAGE_SIZE
    except (TypeError, ValueError):
        page_size = _DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, _MAX_PAGE_SIZE))
    try:
        page_offset = max(0, int(offset))
    except (TypeError, ValueError):
        page_offset = 0

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

        # Helper: build a Supabase submissions query filtered by all the
        # caller's predicates EXCEPT pagination. Reused for both the
        # stats query (selects only `percentage`) and the paginated
        # listing (selects the full row shape).
        def _filtered_subs(select_cols):
            q = sb.table('submissions').select(select_cols).eq('join_code', code)
            if student_name:
                # Case-insensitive partial match — pushed to Postgres.
                q = q.ilike('student_name', f'%{student_name}%')
            if min_score is not None:
                q = q.gte('percentage', min_score)
            if max_score is not None:
                q = q.lte('percentage', max_score)
            return q

        # 1) Stats query: percentage-only over ALL matching rows. Even
        # 100K rows × 8 bytes = 800KB — fine over the wire. Bounded by
        # the assessment's total submission count rather than by an
        # unbounded full-row fetch.
        stats_result = _filtered_subs('percentage').execute()
        stats_rows = stats_result.data or []
        percentages = [r['percentage'] for r in stats_rows if r.get('percentage') is not None]

        # 2) Paginated listing query: full row shape, ordered + limited.
        page_query = _filtered_subs(
            'id, student_name, score, total_points, percentage, submitted_at, results'
        ).order('submitted_at', desc=True).range(page_offset, page_offset + page_size - 1)
        page_result = page_query.execute()
        submissions = page_result.data or []

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
        total_matching = len(stats_rows)

        return {
            "assessment": {
                "title": assessment.get('title', ''),
                "join_code": code,
                "content_type": settings.get('content_type', 'assessment'),
                "period": settings.get('period', ''),
            },
            "summary": {
                "total_submissions": total_matching,
                "average_score": avg,
                "highest_score": highest,
                "lowest_score": lowest,
                "grade_distribution": grade_dist,
            },
            "pagination": {
                "limit": page_size,
                "offset": page_offset,
                "returned": len(submissions),
                "has_more": (page_offset + len(submissions)) < total_matching,
            },
            "submissions": formatted,
        }

    except Exception as e:
        logger.exception("query_assessment_results failed")
        return {"error": f"Failed to query assessment results: {e}"}


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

ASSESSMENT_TOOL_DEFINITIONS = [
    {
        "name": "list_published_assessments",
        "description": "List all published assessments and assignments from the student portal. Shows title, join code, submission count, active status, and content type. Use when the teacher asks 'what assessments have I published?' or 'show my portal assignments'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content_type": {
                    "type": "string",
                    "description": "Filter by type: 'assessment' or 'assignment' (omit for both)"
                }
            }
        }
    },
    {
        "name": "query_assessment_results",
        "description": "Get results and statistics for a published assessment or assignment from the student portal. Shows per-student scores, class average, grade distribution, highest/lowest scores. Search by title (partial match) or join code. Optionally filter by student name or score range. Use when the teacher asks 'how did my class do on X?', 'who failed the quiz?', 'what was the average on the test?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assessment_name": {
                    "type": "string",
                    "description": "Assessment/assignment title to search for (partial match, case-insensitive)"
                },
                "join_code": {
                    "type": "string",
                    "description": "Exact 6-character join code (alternative to assessment_name)"
                },
                "min_score": {
                    "type": "number",
                    "description": "Only include submissions with percentage >= this value"
                },
                "max_score": {
                    "type": "number",
                    "description": "Only include submissions with percentage <= this value"
                },
                "student_name": {
                    "type": "string",
                    "description": "Filter to a specific student (partial match)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Page size for the submission list (default 100, max 500). Summary stats always reflect ALL matching submissions, not just this page."
                },
                "offset": {
                    "type": "integer",
                    "description": "Page offset for the submission list (default 0). Use with `limit` to page through large assessments."
                }
            }
        }
    },
]

ASSESSMENT_TOOL_HANDLERS = {
    "list_published_assessments": list_published_assessments_tool,
    "query_assessment_results": query_assessment_results,
}
