"""
Assessment Results Routes for Graider.
Returns aggregated assessment results with per-question analysis.
Queries both join-code (published_assessments + submissions) and
class-based (published_content + student_submissions) paths.
"""
import logging
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as get_supabase
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

assessment_results_bp = Blueprint('assessment_results', __name__)
_logger = logging.getLogger(__name__)


def _compute_letter_grade(percentage):
    """Convert percentage to letter grade."""
    if percentage is None:
        return None
    if percentage >= 90:
        return 'A'
    if percentage >= 80:
        return 'B'
    if percentage >= 70:
        return 'C'
    if percentage >= 60:
        return 'D'
    return 'F'


def _compute_question_analysis(assessment_data, all_submissions):
    """Compute per-question stats from submissions.

    Returns list of question analysis objects with percent_correct
    and response_distribution for MC/TF questions.
    """
    sections = assessment_data.get('sections', [])
    questions = []
    for sIdx, section in enumerate(sections):
        for qIdx, q in enumerate(section.get('questions', [])):
            key = str(sIdx) + '-' + str(qIdx)
            q_type = q.get('type', 'multiple_choice')
            analysis = {
                'number': q.get('number', qIdx + 1),
                'question': q.get('question', ''),
                'type': q_type,
                'correct_answer': q.get('answer'),
                'points': q.get('points', 1),
            }

            if q_type in ('multiple_choice', 'true_false'):
                # Count responses
                correct_count = 0
                total_count = 0
                distribution = {}

                if q_type == 'multiple_choice':
                    options = q.get('options', [])
                    for i in range(len(options)):
                        letter = chr(65 + i)
                        distribution[letter] = {'count': 0, 'percent': 0, 'is_correct': False}
                    # Mark correct
                    correct_letter = str(q.get('answer', '')).upper().strip()
                    if len(correct_letter) > 1 and correct_letter[1:2] == ')':
                        correct_letter = correct_letter[0]
                    if correct_letter in distribution:
                        distribution[correct_letter]['is_correct'] = True
                else:
                    distribution = {
                        'True': {'count': 0, 'percent': 0, 'is_correct': False},
                        'False': {'count': 0, 'percent': 0, 'is_correct': False},
                    }
                    correct_val = str(q.get('answer', '')).strip()
                    if correct_val in distribution:
                        distribution[correct_val]['is_correct'] = True

                for sub in all_submissions:
                    answers = sub.get('answers', {}) or {}
                    student_ans = answers.get(key)
                    if student_ans is None:
                        continue
                    total_count += 1

                    if q_type == 'multiple_choice':
                        if isinstance(student_ans, int):
                            letter = chr(65 + student_ans)
                        else:
                            letter = str(student_ans).upper().strip()
                            if len(letter) > 1 and letter[1:2] == ')':
                                letter = letter[0]
                        if letter in distribution:
                            distribution[letter]['count'] += 1
                        if letter == correct_letter:
                            correct_count += 1
                    else:
                        val = str(student_ans).strip()
                        if val in distribution:
                            distribution[val]['count'] += 1
                        if val.lower() == correct_val.lower():
                            correct_count += 1

                # Compute percentages
                for k in distribution:
                    if total_count > 0:
                        distribution[k]['percent'] = round(distribution[k]['count'] / total_count * 100)

                analysis['percent_correct'] = round(correct_count / total_count * 100) if total_count > 0 else 0
                analysis['total_responses'] = total_count
                analysis['response_distribution'] = distribution

            elif q_type in ('short_answer', 'extended_response'):
                graded = 0
                pending = 0
                total_score = 0
                max_pts = q.get('points', 1)
                for sub in all_submissions:
                    results = sub.get('results', {}) or {}
                    q_results = results.get('questions', [])
                    # Find matching question result
                    for qr in q_results:
                        if qr.get('number') == q.get('number'):
                            if qr.get('points_earned') is not None:
                                graded += 1
                                total_score += qr.get('points_earned', 0)
                            else:
                                pending += 1
                            break
                    else:
                        pending += 1

                analysis['percent_correct'] = None
                analysis['graded_count'] = graded
                analysis['pending_count'] = pending
                analysis['average_score'] = round(total_score / graded, 1) if graded > 0 else None
                analysis['max_points'] = max_pts

            else:
                # Matching or other types
                correct_count = 0
                total_count = 0
                for sub in all_submissions:
                    results = sub.get('results', {}) or {}
                    for qr in results.get('questions', []):
                        if qr.get('number') == q.get('number'):
                            total_count += 1
                            if qr.get('is_correct'):
                                correct_count += 1
                            break
                analysis['percent_correct'] = round(correct_count / total_count * 100) if total_count > 0 else 0
                analysis['total_responses'] = total_count

            questions.append(analysis)

    return questions


@assessment_results_bp.route('/api/assessment-results', methods=['GET'])
@require_teacher
@handle_route_errors
def get_assessment_results():
    """Return all assessments with aggregated results for the current teacher."""
    db = get_supabase()
    teacher_id = g.teacher_id

    # Audit log
    try:
        from backend.utils.audit import audit_log
        audit_log("VIEW_ASSESSMENT_RESULTS", "Teacher viewed assessment results", user="teacher", teacher_id=teacher_id)
    except Exception:
        pass

    assessments = []

    # 1. Join-code assessments (published_assessments + submissions)
    try:
        pa_result = db.table('published_assessments').select('*').eq('teacher_id', teacher_id).order('created_at', desc=True).execute()
        for pa in (pa_result.data or []):
            settings = pa.get('settings', {}) or {}
            content_type = settings.get('content_type', 'assessment')
            if content_type != 'assessment':
                continue

            join_code = pa.get('join_code', '')
            assessment_data = pa.get('assessment', {}) or {}

            # Fetch submissions for this assessment
            subs_result = db.table('submissions').select('*').eq('join_code', join_code).order('submitted_at', desc=True).execute()
            subs = subs_result.data or []

            # Compute stats
            scores = [s.get('percentage') for s in subs if s.get('percentage') is not None]
            times = [s.get('time_taken_seconds') for s in subs if s.get('time_taken_seconds')]
            pending = sum(1 for s in subs if s.get('score') is None)

            entry = {
                'id': pa.get('id'),
                'title': pa.get('title', assessment_data.get('title', 'Untitled')),
                'assessment_category': settings.get('assessment_category', 'formative'),
                'content_type': 'assessment',
                'source': 'join_code',
                'join_code': join_code,
                'period': settings.get('period', ''),
                'published_at': pa.get('created_at'),
                'is_active': pa.get('is_active', True),
                'stats': {
                    'total_submissions': len(subs),
                    'expected_submissions': None,
                    'average_score': round(sum(scores) / len(scores)) if scores else None,
                    'highest_score': max(scores) if scores else None,
                    'lowest_score': min(scores) if scores else None,
                    'average_time_seconds': round(sum(times) / len(times)) if times else None,
                    'pending_count': pending,
                    'graded_count': len(subs) - pending,
                },
                'submissions': [
                    {
                        'student_name': s.get('student_name', 'Anonymous'),
                        'score': s.get('score'),
                        'percentage': s.get('percentage'),
                        'letter_grade': _compute_letter_grade(s.get('percentage')),
                        'time_taken_seconds': s.get('time_taken_seconds'),
                        'submitted_at': s.get('submitted_at'),
                        'status': 'pending' if s.get('score') is None else 'graded',
                    }
                    for s in subs
                ],
                'question_analysis': _compute_question_analysis(assessment_data, subs),
            }
            assessments.append(entry)
    except Exception as e:
        _logger.warning("Error fetching join-code assessments: %s", str(e))

    # 2. Class-based assessments (published_content + student_submissions)
    try:
        pc_result = db.table('published_content').select('*').eq('teacher_id', teacher_id).eq('content_type', 'assessment').order('created_at', desc=True).execute()
        for pc in (pc_result.data or []):
            content_id = pc.get('id')
            settings = pc.get('settings', {}) or {}
            assessment_data = pc.get('content', {}) or {}

            # Fetch submissions
            subs_result = db.table('student_submissions').select('*').eq('content_id', content_id).order('submitted_at', desc=True).execute()
            subs = subs_result.data or []

            # Expected count from class enrollment
            expected = None
            class_id = pc.get('class_id')
            if class_id:
                try:
                    enrolled = db.table('class_students').select('id', count='exact').eq('class_id', class_id).execute()
                    expected = enrolled.count
                except Exception:
                    pass

            scores = [s.get('percentage') for s in subs if s.get('percentage') is not None]
            times = [s.get('time_taken_seconds') for s in subs if s.get('time_taken_seconds')]
            pending = sum(1 for s in subs if s.get('status') in ('submitted', 'partial'))

            entry = {
                'id': content_id,
                'title': pc.get('title', 'Untitled'),
                'assessment_category': settings.get('assessment_category', 'formative'),
                'content_type': 'assessment',
                'source': 'class_based',
                'join_code': pc.get('join_code', ''),
                'period': settings.get('period', '') or pc.get('period', ''),
                'published_at': pc.get('created_at'),
                'is_active': pc.get('is_active', True),
                'stats': {
                    'total_submissions': len(subs),
                    'expected_submissions': expected,
                    'average_score': round(sum(scores) / len(scores)) if scores else None,
                    'highest_score': max(scores) if scores else None,
                    'lowest_score': min(scores) if scores else None,
                    'average_time_seconds': round(sum(times) / len(times)) if times else None,
                    'pending_count': pending,
                    'graded_count': len(subs) - pending,
                },
                'submissions': [
                    {
                        'student_name': s.get('student_name', 'Anonymous'),
                        'score': s.get('score'),
                        'percentage': s.get('percentage'),
                        'letter_grade': _compute_letter_grade(s.get('percentage')),
                        'time_taken_seconds': s.get('time_taken_seconds'),
                        'submitted_at': s.get('submitted_at'),
                        'status': s.get('status', 'submitted'),
                    }
                    for s in subs
                ],
                'question_analysis': _compute_question_analysis(assessment_data, subs),
            }
            assessments.append(entry)
    except Exception as e:
        _logger.warning("Error fetching class-based assessments: %s", str(e))

    # Sort by published_at descending
    assessments.sort(key=lambda a: a.get('published_at') or '', reverse=True)

    # Filter by category if requested
    category = request.args.get('category')
    if category in ('formative', 'summative'):
        assessments = [a for a in assessments if a.get('assessment_category') == category]

    return jsonify({'assessments': assessments})
