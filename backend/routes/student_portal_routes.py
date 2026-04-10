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
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as get_supabase

student_portal_bp = Blueprint('student_portal', __name__)
_logger = logging.getLogger(__name__)

from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
from backend.services.grading_service import grade_deterministic_question, grade_student_submission, grade_instant_only


def generate_join_code():
    """Generate a unique 6-character join code (e.g., 'ABC123')."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choices(chars, k=6))
        # Check if code already exists
        db = get_supabase()
        result = db.table('published_assessments').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code


# ============ Teacher Endpoints ============

@student_portal_bp.route('/api/publish-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
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
        db = get_supabase()
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

        # Insert into Supabase
        result = db.table('published_assessments').insert({
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_id": g.teacher_id,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }).execute()

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
        db = get_supabase()

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
        db = get_supabase()
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
        db = get_supabase()
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
        db = get_supabase()
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
@handle_route_errors
def get_assessment_for_student(code):
    """
    Get assessment details for a student joining with a code.
    Returns assessment without answers for student to take.
    """
    try:
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

        # Shared material content (NotebookLM) — return directly
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
@handle_route_errors
def submit_assessment(code):
    """
    Submit student answers for grading.
    Returns immediate feedback and score.
    """
    try:
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
            from datetime import timezone
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

        try:
            submission_result = db.table('submissions').insert(submission_row).execute()
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
            from backend.services.portal_grading import run_portal_grading_thread
            from backend.services.grading_service import load_teacher_config
            teacher_id = assessment_data.get("teacher_id") or ""
            teacher_config = load_teacher_config(teacher_id)

            # Get student accommodations from published assessment settings
            published_accommodations = assessment_data.get("settings", {}).get("student_accommodations", {})

            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    answers,
                    {"student_name": student_name, "student_id": "", "email": ""},
                    teacher_config,
                    teacher_id,
                    "submissions",
                ),
                kwargs={"student_accommodations": published_accommodations},
                daemon=True,
            )
            thread.start()

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
        db = get_supabase()

        result = db.table('published_content').select(
            'id, title, content_type, class_id, created_at, is_active'
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
        db = get_supabase()

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
        db = get_supabase()
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


