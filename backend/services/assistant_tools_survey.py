"""
Parent Survey Tools
====================
Assistant tools for creating parent surveys, retrieving results,
and compiling survey reports.
"""
import json
import logging
import os
import random

logger = logging.getLogger(__name__)


def _get_supabase():
    from backend.supabase_client import get_supabase_or_raise
    return get_supabase_or_raise()


DEFAULT_QUESTIONS = [
    {
        "id": "communication",
        "text": "How well does the teacher communicate about your student's progress?",
        "type": "rating",
    },
    {
        "id": "availability",
        "text": "How available is the teacher when you have questions or concerns?",
        "type": "rating",
    },
    {
        "id": "support",
        "text": "How well does the teacher support your student's academic needs?",
        "type": "rating",
    },
    {
        "id": "expectations",
        "text": "How clearly does the teacher communicate classroom expectations and assignments?",
        "type": "rating",
    },
    {
        "id": "feedback",
        "text": "Is there anything else you'd like to share about your experience?",
        "type": "text",
    },
]


def create_parent_survey(title=None, teacher_name=None, questions=None):
    """Create a parent survey and return the shareable link."""
    db = _get_supabase()

    title = title or "Parent Communication Survey"
    teacher_name = teacher_name or "Teacher"
    questions = questions or DEFAULT_QUESTIONS

    # Generate unique code
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choices(chars, k=6))
        result = db.table('published_assessments').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            break

    db.table('published_assessments').insert({
        'join_code': code,
        'title': title,
        'teacher_name': teacher_name,
        'assessment': {
            'content_type': 'survey',
            'questions': questions,
            'responses': [],
        },
        'settings': {
            'content_type': 'survey',
        },
        'is_active': True,
        'submission_count': 0,
    }).execute()

    return {
        "status": "success",
        "join_code": code,
        "survey_url": f"/survey/{code}",
        "message": f"Survey created! Share this link with parents: /survey/{code} (join code: {code}). "
                   f"The survey has {len(questions)} questions and responses are anonymous.",
    }


def get_survey_results(join_code=None):
    """Get survey results with aggregate statistics."""
    db = _get_supabase()

    if join_code:
        result = db.table('published_assessments') \
            .select('join_code, assessment, title, submission_count, created_at') \
            .eq('join_code', join_code) \
            .execute()
    else:
        # Get all surveys for this teacher
        result = db.table('published_assessments') \
            .select('join_code, assessment, title, submission_count, created_at') \
            .eq('settings->>content_type', 'survey') \
            .order('created_at', desc=True) \
            .execute()

    if not result.data:
        return {"error": "No surveys found"}

    surveys = []
    for record in result.data:
        assessment = record.get('assessment', {})
        if assessment.get('content_type') != 'survey':
            continue

        responses = assessment.get('responses', [])
        questions = assessment.get('questions', [])

        summary = {}
        for q in questions:
            qid = q['id']
            if q['type'] == 'rating':
                ratings = [r.get(qid) for r in responses if r.get(qid) is not None]
                summary[qid] = {
                    'question': q['text'],
                    'type': 'rating',
                    'count': len(ratings),
                    'average': round(sum(ratings) / len(ratings), 1) if ratings else 0,
                    'distribution': {str(i): ratings.count(i) for i in range(1, 6)},
                }
            elif q['type'] == 'text':
                texts = [r.get(qid) for r in responses if r.get(qid)]
                summary[qid] = {
                    'question': q['text'],
                    'type': 'text',
                    'count': len(texts),
                    'responses': texts,
                }

        surveys.append({
            'join_code': record.get('join_code'),
            'title': record.get('title', 'Survey'),
            'total_responses': len(responses),
            'created_at': record.get('created_at'),
            'questions': summary,
        })

    if join_code and surveys:
        return surveys[0]
    return {"surveys": surveys}


def compile_survey_report(join_code):
    """Compile a detailed survey report with analysis and recommendations."""
    results = get_survey_results(join_code=join_code)
    if results.get('error'):
        return results

    total = results.get('total_responses', 0)
    if total == 0:
        return {
            "report": f"Survey '{results.get('title')}' has no responses yet. "
                      f"Share the link /survey/{join_code} with parents to collect feedback.",
            "join_code": join_code,
        }

    # Build report text
    lines = [
        f"# Parent Survey Report: {results.get('title')}",
        f"**Total Responses:** {total}",
        f"**Survey Code:** {join_code}",
        "",
    ]

    rating_scores = []
    for qid, data in results.get('questions', {}).items():
        if data['type'] == 'rating':
            avg = data['average']
            rating_scores.append(avg)
            dist = data['distribution']
            bar = ""
            for star in range(1, 6):
                count = int(dist.get(str(star), 0))
                bar += f"  {star} star: {'*' * count} ({count})"
            lines.append(f"### {data['question']}")
            lines.append(f"**Average: {avg}/5.0** ({data['count']} ratings)")
            lines.append(bar)
            lines.append("")
        elif data['type'] == 'text' and data.get('responses'):
            lines.append(f"### {data['question']}")
            lines.append(f"**{data['count']} written responses:**")
            for resp in data['responses']:
                lines.append(f"- \"{resp}\"")
            lines.append("")

    overall_avg = round(sum(rating_scores) / len(rating_scores), 1) if rating_scores else 0
    lines.insert(3, f"**Overall Average Rating:** {overall_avg}/5.0")
    lines.insert(4, "")

    return {
        "report": "\n".join(lines),
        "overall_average": overall_avg,
        "total_responses": total,
        "join_code": join_code,
    }


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS & HANDLERS
# ═══════════════════════════════════════════════════════

SURVEY_TOOL_DEFINITIONS = [
    {
        "name": "create_parent_survey",
        "description": "Create a parent survey to assess your communication and support. "
                       "Returns a shareable link parents can click to rate you on 4-5 questions. "
                       "Responses are anonymous. Use when the teacher wants parent feedback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Survey title (default: 'Parent Communication Survey')"
                },
                "teacher_name": {
                    "type": "string",
                    "description": "Teacher's name shown on the survey"
                },
            }
        }
    },
    {
        "name": "get_survey_results",
        "description": "Get parent survey results with average ratings and written feedback. "
                       "Shows per-question breakdown with star distribution. "
                       "Omit join_code to list all surveys.",
        "input_schema": {
            "type": "object",
            "properties": {
                "join_code": {
                    "type": "string",
                    "description": "Survey join code (6 chars). Omit to list all surveys."
                },
            }
        }
    },
    {
        "name": "compile_survey_report",
        "description": "Compile a detailed parent survey report with aggregate stats, "
                       "rating distributions, written feedback, and overall score. "
                       "Use when the teacher wants a summary or report of survey results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "join_code": {
                    "type": "string",
                    "description": "Survey join code (required)"
                },
            },
            "required": ["join_code"]
        }
    },
]

SURVEY_TOOL_HANDLERS = {
    "create_parent_survey": create_parent_survey,
    "get_survey_results": get_survey_results,
    "compile_survey_report": compile_survey_report,
}
