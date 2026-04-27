"""
Student Account Routes for Graider.
Handles student auth, class management, and unified content delivery.
Students log in with Student ID + Class Join Code (no passwords).

Review fixes applied:
1. Hashed session tokens (SHA-256) — only hash stored in DB
2. Hard-fail on missing teacher user_id — no 'local-dev' fallback
3. Roster sync via CSV upload — not local filesystem reads
4. Submissions connect to grading pipeline via /api/grade-portal-submission
5. Rate-limited login — 5 attempts per student per 10 minutes
"""
import csv
import hashlib
import io
import json
import os
import random
import secrets
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import sentry_sdk
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as _get_supabase
# Phase 4.5: this module has MIXED auth paths. Teacher endpoints use
# get_request_supabase() so their requests land under RLS when the
# USE_PER_USER_JWT flag is on. Student-session endpoints (authenticated
# via X-Student-Token, not a Supabase JWT) and shared helpers continue
# to use _get_supabase() / service-role.
from backend.supabase_client_scoped import get_request_supabase as _get_teacher_supabase
from backend.extensions import limiter
from backend.observability import critical_path

import logging
_logger = logging.getLogger(__name__)

student_account_bp = Blueprint('student_account', __name__)

# In-memory rate limiter: {student_id_number: [(timestamp, ...)] }
_login_attempts = defaultdict(list)
LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW = 600  # 10 minutes


def _get_teacher_id():
    """Get authenticated teacher ID. Hard-fails if missing."""
    teacher_id = getattr(g, 'user_id', None)
    if not teacher_id:
        return None
    return teacher_id


from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import error_response, handle_route_errors


def _generate_class_code():
    """Generate a unique 6-char class join code."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    db = _get_supabase()
    for _ in range(20):
        code = ''.join(random.choices(chars, k=6))
        result = db.table('classes').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code
    raise Exception("Could not generate unique class code after 20 attempts")


def _hash_token(token):
    """Hash a session token with SHA-256 for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _spawn_grading_thread_safe(*, target, args, kwargs=None):
    """Start a daemon thread for grading work; capture to Sentry on failure.
    Returns the started Thread, or None if spawn failed."""
    try:
        t = threading.Thread(target=target, args=args, kwargs=kwargs or {}, daemon=True)
        t.start()
        return t
    except Exception as e:
        _logger.warning("Failed to spawn portal grading: %s", e)
        sentry_sdk.capture_exception(e)
        return None


def _check_rate_limit(student_id_number):
    """Check if login attempts are within rate limit. Returns True if allowed."""
    now = datetime.now(tz=timezone.utc).timestamp()
    key = student_id_number.lower()
    # Prune old attempts
    _login_attempts[key] = [t for t in _login_attempts[key] if now - t < LOGIN_RATE_WINDOW]
    if len(_login_attempts[key]) >= LOGIN_RATE_LIMIT:
        return False
    _login_attempts[key].append(now)
    return True


def _validate_student_session():
    """Validate student session token from X-Student-Token header.
    Returns (student_id, class_id) tuple or None if invalid.
    """
    token = request.headers.get('X-Student-Token', '')
    if not token:
        return None

    db = _get_supabase()
    token_hash = _hash_token(token)
    result = db.table('student_sessions').select(
        'student_id, class_id, expires_at'
    ).eq('session_token', token_hash).execute()

    if not result.data:
        return None

    session = result.data[0]
    expires = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
    if expires < datetime.now(tz=timezone.utc):
        db.table('student_sessions').delete().eq('session_token', token_hash).execute()
        return None

    return (session['student_id'], session['class_id'])


def _content_visible_to_student(db, content_id, student_id, class_id):
    """Phase 4: shared visibility check for student-facing endpoints.

    A student sees a published_content row iff:
    1. They're currently enrolled in published_content.class_id (re-checked, not session-cached).
    2. The row is is_active = true.
    3. target_student_ids IS NULL OR target_student_ids contains the student_id.

    Returns True iff all three hold; False otherwise.
    """
    # Enrollment fact (re-check, NOT session-cached).
    enr = db.table('class_students').select('student_id').eq(
        'class_id', class_id
    ).eq('student_id', student_id).execute()
    if not enr.data:
        _logger.debug("student.access.denied reason=not_enrolled student=%s class=%s",
                      student_id, class_id)
        return False
    # Content row.
    row = db.table('published_content').select(
        'id, class_id, is_active, target_student_ids'
    ).eq('id', content_id).eq('class_id', class_id).execute()
    if not row.data:
        return False
    item = row.data[0]
    if not item.get('is_active'):
        return False
    targets = item.get('target_student_ids')
    if targets is None:
        return True
    if isinstance(targets, list) and student_id in targets:
        return True
    _logger.debug("student.access.denied reason=not_targeted student=%s content=%s",
                  student_id, content_id)
    return False


# ============ Teacher Endpoints (require teacher JWT) ============

@student_account_bp.route('/api/classes', methods=['POST'])
@require_teacher
@handle_route_errors
def create_class():
    """Create a class. Generates join code."""
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()
        data = request.json
        name = data.get('name', '').strip()
        subject = data.get('subject', '')
        grade_level = data.get('grade_level', '')

        if not name:
            return jsonify({"error": "Class name is required"}), 400

        join_code = _generate_class_code()

        result = db.table('classes').insert({
            'teacher_id': teacher_id,
            'name': name,
            'join_code': join_code,
            'subject': subject,
            'grade_level': grade_level,
            'is_active': True,
        }).execute()

        if not result.data:
            return jsonify({"error": "Failed to create class"}), 500

        return jsonify({
            "success": True,
            "class": result.data[0],
            "join_code": join_code,
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/classes', methods=['GET'])
@require_teacher
@handle_route_errors
def list_classes():
    """List teacher's classes with student counts."""
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()
        classes = db.table('classes').select(
            '*, class_students(count)'
        ).eq('teacher_id', teacher_id).eq('is_active', True).execute()

        return jsonify({"classes": classes.data})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/classes/<class_id>/sync-roster', methods=['POST'])
@require_teacher
@handle_route_errors
def sync_roster_to_class(class_id):
    """Sync students from an uploaded CSV into the class.
    Accepts multipart/form-data with a 'file' field containing the CSV.
    CSV must have columns for student identification (Student ID, First Name, Last Name).
    """
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()

        # Verify class belongs to teacher
        cls = db.table('classes').select('*').eq('id', class_id).eq(
            'teacher_id', teacher_id
        ).execute()
        if not cls.data:
            return jsonify({"error": "Class not found"}), 404

        # Read CSV from upload
        if 'file' not in request.files:
            return jsonify({"error": "No CSV file uploaded. Send as multipart/form-data with 'file' field."}), 400

        file = request.files['file']
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
        if ext != '.csv':
            return jsonify({"error": "File must be a CSV"}), 400

        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        if not reader.fieldnames:
            return jsonify({"error": "CSV has no headers"}), 400

        # Map column names flexibly
        def _find_col(fieldnames, candidates):
            for col in fieldnames:
                if col.strip().lower().replace('_', ' ') in candidates:
                    return col
            return None

        id_col = _find_col(reader.fieldnames, ['student id', 'student_id', 'id', 'studentid'])
        first_col = _find_col(reader.fieldnames, ['first name', 'first_name', 'firstname', 'first'])
        last_col = _find_col(reader.fieldnames, ['last name', 'last_name', 'lastname', 'last'])
        name_col = _find_col(reader.fieldnames, ['student', 'student name', 'student_name', 'name'])
        email_col = _find_col(reader.fieldnames, ['email', 'email address', 'student email', 'student_email'])

        synced = 0
        errors = []

        for row in reader:
            # Parse name
            first = row.get(first_col, '').strip() if first_col else ''
            last = row.get(last_col, '').strip() if last_col else ''

            # Handle combined name column (e.g., "Last; First Middle")
            if not first and not last and name_col:
                raw_name = row.get(name_col, '').strip()
                if ';' in raw_name:
                    parts = raw_name.split(';', 1)
                    last = parts[0].strip()
                    first = parts[1].strip().split()[0] if parts[1].strip() else ''
                elif ',' in raw_name:
                    parts = raw_name.split(',', 1)
                    last = parts[0].strip()
                    first = parts[1].strip().split()[0] if parts[1].strip() else ''
                else:
                    parts = raw_name.split()
                    if len(parts) >= 2:
                        first = parts[0]
                        last = ' '.join(parts[1:])
                    elif parts:
                        first = parts[0]

            if not first and not last:
                continue

            sid = row.get(id_col, '').strip() if id_col else ''
            if not sid:
                sid = f"{first}_{last}".lower().replace(' ', '_')

            email = row.get(email_col, '').strip().lower() if email_col else ''

            try:
                upsert_data = {
                    'teacher_id': teacher_id,
                    'student_id_number': sid,
                    'first_name': first,
                    'last_name': last,
                    'period': cls.data[0].get('name', ''),
                    'is_active': True,
                    'updated_at': datetime.now(tz=timezone.utc).isoformat(),
                }
                if email:
                    upsert_data['email'] = email

                student_result = db.table('students').upsert(
                    upsert_data, on_conflict='teacher_id,student_id_number'
                ).execute()

                if student_result.data:
                    student_uuid = student_result.data[0]['id']
                    db.table('class_students').upsert({
                        'class_id': class_id,
                        'student_id': student_uuid,
                    }, on_conflict='class_id,student_id').execute()
                    synced += 1
            except Exception as e:
                errors.append(f"{first} {last}: {str(e)}")

        return jsonify({
            "success": True,
            "synced": synced,
            "total": synced + len(errors),
            "errors": errors,
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/classes/<class_id>/students', methods=['GET'])
@require_teacher
@handle_route_errors
def list_class_students(class_id):
    """List students enrolled in a class."""
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()

        cls = db.table('classes').select('id').eq('id', class_id).eq(
            'teacher_id', teacher_id
        ).execute()
        if not cls.data:
            return jsonify({"error": "Class not found"}), 404

        result = db.table('class_students').select(
            'student_id, students(id, student_id_number, first_name, last_name, period, accommodations, is_active)'
        ).eq('class_id', class_id).execute()

        students = [row['students'] for row in result.data if row.get('students')]
        return jsonify({"students": students})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/publish-to-class', methods=['POST'])
@require_teacher
@handle_route_errors
def publish_to_class():
    """Publish an assessment or assignment to a class.

    Phase 4 hardening: verifies class ownership; supports target_student_ids
    for per-student visibility (None / omitted = class-wide). All explicit 4xx
    errors use error_response() per Phase 5d (RFC 7807).
    """
    teacher_id = g.teacher_id

    db = _get_teacher_supabase()
    data = request.json or {}
    class_id = data.get('class_id')
    content = data.get('content')
    content_type = data.get('content_type', 'assessment')
    title = data.get('title', 'Untitled')
    settings = data.get('settings', {})
    due_date = data.get('due_date')
    target_student_ids = data.get('target_student_ids')

    if not content:
        return error_response("No content provided", 400)
    ALLOWED_CONTENT_TYPES = ('assessment', 'assignment', 'study_guide', 'flashcards', 'slide_deck')
    if content_type not in ALLOWED_CONTENT_TYPES:
        return error_response(
            "content_type must be one of: " + ", ".join(ALLOWED_CONTENT_TYPES), 400
        )

    # Phase 4: class ownership check (closes pre-existing gap).
    cls = db.table('classes').select('id, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != teacher_id:
        return error_response("Not authorized for this class", 403)

    # Phase 4: target_student_ids validation.
    if target_student_ids is not None:
        if not isinstance(target_student_ids, list):
            return error_response("target_student_ids must be a list or null", 400)
        if len(target_student_ids) == 0:
            return error_response(
                "target_student_ids must be non-empty (use null for class-wide)", 400
            )
        import uuid as _uuid
        for sid in target_student_ids:
            try:
                _uuid.UUID(str(sid))
            except (ValueError, TypeError):
                return error_response("Invalid target_student_id UUID", 400)
        # Enrollment check.
        enr = db.table('class_students').select('student_id').eq(
            'class_id', class_id
        ).in_('student_id', target_student_ids).execute()
        enrolled = {r['student_id'] for r in (enr.data or [])}
        if any(sid not in enrolled for sid in target_student_ids):
            return error_response(
                "One or more target_student_ids are not enrolled in this class", 400
            )
        # Students existence check (orphan-resilience).
        stu_rows = db.table('students').select('id').in_(
            'id', target_student_ids
        ).execute()
        existing_students = {r['id'] for r in (stu_rows.data or [])}
        if any(sid not in existing_students for sid in target_student_ids):
            return error_response(
                "One or more target_student_ids do not match a student record", 400
            )

    join_code = _generate_class_code()

    # Validate assessment_category for assessments
    if content_type == 'assessment':
        cat = settings.get('assessment_category', 'formative')
        if cat not in ('formative', 'summative'):
            settings['assessment_category'] = 'formative'
        else:
            settings['assessment_category'] = cat

    insert_payload = {
        'teacher_id': teacher_id,
        'class_id': class_id,
        'content_type': content_type,
        'title': title,
        'join_code': join_code,
        'content': content,
        'settings': settings,
        'is_active': True,
        'due_date': due_date,
        'target_student_ids': target_student_ids,  # None = class-wide
    }
    result = db.table('published_content').insert(insert_payload).execute()

    if not result.data:
        return error_response("Failed to publish", 500)

    host = request.host_url.rstrip('/')
    return jsonify({
        "success": True,
        "content_id": result.data[0]['id'],
        "join_code": join_code,
        "join_link": f"{host}/student?code={join_code}",
    })


@student_account_bp.route('/api/portal-submissions', methods=['GET'])
@require_teacher
@handle_route_errors
def get_portal_submissions():
    """Get all student submissions for the Results tab."""
    teacher_id = g.teacher_id

    # Local dev has no real Supabase teacher record
    if teacher_id == 'local-dev':
        return jsonify({"submissions": [], "pending_confirmations": 0})

    try:
        db = _get_teacher_supabase()

        content = db.table('published_content').select('id, title, content_type').eq(
            'teacher_id', teacher_id
        ).execute()
        content_ids = [c['id'] for c in content.data]
        content_map = {c['id']: c for c in content.data}

        if not content_ids:
            return jsonify({"submissions": [], "pending_confirmations": 0})

        subs = db.table('student_submissions').select('*').in_(
            'content_id', content_ids
        ).order('submitted_at', desc=True).execute()

        results = []
        for s in subs.data:
            content_info = content_map.get(s['content_id'], {})
            results.append({
                'student_name': s['student_name'],
                'student_id': s.get('student_id_number', ''),
                'assignment': content_info.get('title', 'Unknown'),
                'period': s.get('period', ''),
                'score': s.get('score'),
                'letter_grade': s.get('letter_grade', ''),
                'percentage': s.get('percentage'),
                'status': s['status'],
                'source': 'portal_' + content_info.get('content_type', 'assessment'),
                'submitted_at': s['submitted_at'],
                'graded_at': s.get('graded_at'),
                'submission_id': s['id'],
                'content_id': s['content_id'],
                'content_type': content_info.get('content_type', ''),
                'answers': s.get('answers'),
                'results': s.get('results'),
                'time_taken_seconds': s.get('time_taken_seconds'),
            })

        # Piggyback pending confirmations count
        pending_count = 0
        try:
            pending_conf = db.table('submission_confirmations').select(
                'id', count='exact'
            ).eq('teacher_id', teacher_id).eq('status', 'pending').execute()
            pending_count = pending_conf.count or 0
        except Exception as e:
            sentry_sdk.capture_exception(e)

        return jsonify({"submissions": results, "pending_confirmations": pending_count})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/grade-portal-submission', methods=['POST'])
@require_teacher
@handle_route_errors
def grade_portal_submission():
    """Grade a portal submission using the existing grading pipeline.
    Takes a submission_id and runs it through the assessment auto-grader.
    """
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()
        data = request.json
        submission_id = data.get('submission_id')

        if not submission_id:
            return jsonify({"error": "submission_id required"}), 400

        # Get the submission
        sub = db.table('student_submissions').select('*').eq('id', submission_id).execute()
        if not sub.data:
            return jsonify({"error": "Submission not found"}), 404

        submission = sub.data[0]

        # Get the published content (has the answer key)
        content = db.table('published_content').select('*').eq(
            'id', submission['content_id']
        ).eq('teacher_id', teacher_id).execute()

        if not content.data:
            return jsonify({"error": "Content not found or not yours"}), 404

        assessment = content.data[0]['content']
        student_answers = submission.get('answers', {})

        # Use the portal grading service for consistent grading
        from backend.services.portal_grading import has_written_questions, run_portal_grading_thread
        from backend.services.grading_service import grade_instant_only, grade_student_submission

        needs_multipass = has_written_questions(assessment)

        if needs_multipass:
            instant_results = grade_instant_only(assessment, student_answers)
        else:
            instant_results = grade_student_submission(assessment, student_answers)

        # Update submission with instant results
        update_data = {
            'results': instant_results,
            'status': 'partial' if needs_multipass else 'graded',
            'graded_at': datetime.now(tz=timezone.utc).isoformat(),
        }
        if not needs_multipass:
            update_data['score'] = instant_results.get('score')
            update_data['total_points'] = instant_results.get('total_points')
            update_data['percentage'] = instant_results.get('percentage')

        db.table('student_submissions').update(update_data).eq('id', submission_id).execute()

        # Spawn multipass for written questions
        if needs_multipass:
            student_name = submission.get('student_name', '')
            student_id_number = submission.get('student_id_number', '')

            from backend.services.grading_service import load_teacher_config
            teacher_config = load_teacher_config(teacher_id)
            teacher_config["period"] = submission.get('period', '')

            # Get accommodations from published content (content var holds select('*') result)
            published_accommodations = content.data[0].get('settings', {}).get('student_accommodations', {}) if content.data else {}

            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    student_answers,
                    {"student_name": student_name, "student_id": student_id_number, "email": ""},
                    teacher_config,
                    teacher_id,
                    "student_submissions",
                ),
                kwargs={"student_accommodations": published_accommodations},
                daemon=True,
            )
            thread.start()

        needs_review = sum(1 for q in instant_results.get('questions', []) if q.get('status') == 'pending_review')

        return jsonify({
            "success": True,
            "score": instant_results.get('score', 0),
            "total_points": instant_results.get('total_points', 0),
            "percentage": instant_results.get('percentage', 0),
            "results": instant_results.get('questions', []),
            "needs_review": needs_review,
            "grading_status": "partial" if needs_multipass else "complete",
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Student Endpoints (public, session-based auth) ============

@student_account_bp.route('/api/student/login', methods=['POST'])
@limiter.limit("10/minute")
@handle_route_errors
def student_login():
    """Student login with email + class join code.
    Returns a session token valid for 8 hours.
    Rate-limited: 5 attempts per email per 10 minutes.
    """
    try:
        db = _get_supabase()
        data = request.json
        email = data.get('email', '').strip().lower()
        class_code = data.get('class_code', '').strip().upper()

        if not email or not class_code:
            return jsonify({"error": "Email and class code are required"}), 400

        # Rate limit check
        if not _check_rate_limit(email):
            return jsonify({"error": "Too many login attempts. Try again in 10 minutes."}), 429

        # Find the class by join code
        cls = db.table('classes').select('id, teacher_id, name, subject').eq(
            'join_code', class_code
        ).eq('is_active', True).execute()

        if not cls.data:
            return jsonify({"error": "Invalid class code"}), 404

        class_data = cls.data[0]

        # Find the student by email
        student = db.table('students').select('*').eq(
            'email', email
        ).eq('teacher_id', class_data['teacher_id']).eq(
            'is_active', True
        ).execute()

        if not student.data:
            return jsonify({"error": "Email not found. Ask your teacher for help."}), 404

        student_data = student.data[0]

        # Verify enrollment
        enrollment = db.table('class_students').select('id').eq(
            'class_id', class_data['id']
        ).eq('student_id', student_data['id']).execute()

        if not enrollment.data:
            return jsonify({"error": "You are not enrolled in this class"}), 403

        # Create session: store hash, return raw token
        raw_token = secrets.token_urlsafe(48)
        token_hash = _hash_token(raw_token)
        expires = datetime.now(tz=timezone.utc) + timedelta(hours=8)

        db.table('student_sessions').insert({
            'student_id': student_data['id'],
            'class_id': class_data['id'],
            'session_token': token_hash,
            'expires_at': expires.isoformat(),
        }).execute()

        return jsonify({
            "success": True,
            "token": raw_token,
            "student": {
                "first_name": student_data['first_name'],
                "last_name": student_data['last_name'],
                "email": student_data.get('email', ''),
                "student_id": student_data['student_id_number'],
                "period": student_data.get('period', ''),
            },
            "class": {
                "name": class_data['name'],
                "subject": class_data.get('subject', ''),
            },
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/student/dashboard', methods=['GET'])
@handle_route_errors
def student_dashboard():
    """Get student's assigned work (assessments + assignments)."""
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        # Phase 4: list-filter — only show class-wide rows OR rows targeting this student.
        # student_id is a UUID from session lookup (validated by Supabase), so safe to interpolate.
        targeting_filter = f'target_student_ids.is.null,target_student_ids.cs.{json.dumps([student_id])}'
        content = db.table('published_content').select('*').eq(
            'class_id', class_id
        ).eq('is_active', True).or_(targeting_filter).order('created_at', desc=True).execute()

        submissions = db.table('student_submissions').select(
            'content_id, status, score, percentage, letter_grade, submitted_at'
        ).eq('student_id', student_id).execute()

        sub_map = {}
        for s in submissions.data:
            sub_map[s['content_id']] = s

        items = []
        for c in content.data:
            sub = sub_map.get(c['id'])
            items.append({
                'content_id': c['id'],
                'title': c['title'],
                'content_type': c['content_type'],
                'unit_name': c.get('settings', {}).get('unit_name', ''),
                'due_date': c.get('due_date'),
                'status': sub['status'] if sub else 'not_started',
                'score': sub.get('score') if sub else None,
                'percentage': sub.get('percentage') if sub else None,
                'letter_grade': sub.get('letter_grade') if sub else None,
                'submitted_at': sub.get('submitted_at') if sub else None,
            })

        return jsonify({"items": items})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/student/content/<content_id>', methods=['GET'])
@handle_route_errors
def get_student_content(content_id):
    """Get assessment/assignment content for a student to complete.
    Strips answer keys before sending.
    """
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        # Phase 4: targeting visibility check (must run before any content read).
        if not _content_visible_to_student(db, content_id, student_id, class_id):
            return jsonify({"error": "Content not found"}), 404

        result = db.table('published_content').select('*').eq(
            'id', content_id
        ).eq('class_id', class_id).eq('is_active', True).execute()

        if not result.data:
            return jsonify({"error": "Content not found"}), 404

        item = result.data[0]
        content = item['content']

        # Strip answer keys and normalize question types
        def _sanitize_question(q):
            q.pop('correct_answer', None)
            q.pop('answer', None)
            q.pop('rubric', None)
            q.pop('expected_answer', None)
            q.pop('answer_key', None)
            # Normalize question_type → type for frontend consistency
            if not q.get('type') and q.get('question_type'):
                q['type'] = q['question_type']

        if 'questions' in content:
            for q in content['questions']:
                _sanitize_question(q)
        if 'sections' in content:
            for section in content.get('sections', []):
                for q in section.get('questions', []):
                    _sanitize_question(q)

        return jsonify({
            "content_id": item['id'],
            "title": item['title'],
            "content_type": item['content_type'],
            "content": content,
            "settings": item.get('settings', {}),
            "due_date": item.get('due_date'),
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/student/submit/<content_id>', methods=['POST'])
@handle_route_errors
@critical_path
def submit_student_work(content_id):
    """Submit answers for an assessment or assignment."""
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        # Phase 4: targeting visibility check (must run before any content read).
        if not _content_visible_to_student(db, content_id, student_id, class_id):
            return jsonify({"error": "Content not found"}), 404

        data = request.json
        answers = data.get('answers', {})
        question_times = data.get('question_times') or {}
        time_taken = data.get('time_taken_seconds', 0)

        student = db.table('students').select(
            'first_name, last_name, student_id_number, period, email, teacher_id'
        ).eq('id', student_id).execute()

        if not student.data:
            return jsonify({"error": "Student not found"}), 404

        s = student.data[0]
        student_name = f"{s['first_name']} {s['last_name']}"

        existing = db.table('student_submissions').select('id').eq(
            'student_id', student_id
        ).eq('content_id', content_id).execute()

        attempt = len(existing.data) + 1

        # Load published content to get assessment data for grading
        pc = db.table('published_content').select('content, title, teacher_id, settings').eq(
            'id', content_id).execute()
        if not pc.data:
            return jsonify({"error": "Published content not found"}), 404

        assessment_content = pc.data[0].get('content', {})
        content_title = pc.data[0].get('title', 'Assignment')
        teacher_id = pc.data[0].get('teacher_id', s.get('teacher_id', ''))

        # Check for late submission (assignments with due dates)
        due_date = pc.data[0].get('due_date')
        is_late = False
        if due_date:
            now_ts = datetime.now(tz=timezone.utc).isoformat()
            if now_ts > due_date:
                is_late = True

        # Grade instant questions (MC/TF/matching) immediately
        from backend.services.portal_grading import has_written_questions, run_portal_grading_thread
        from backend.services.grading_service import grade_instant_only, grade_student_submission
        needs_multipass = has_written_questions(assessment_content)

        if needs_multipass:
            instant_results = grade_instant_only(assessment_content, answers)
        else:
            instant_results = grade_student_submission(assessment_content, answers)

        # Build submission row with instant grading results
        submission_row = {
            'student_id': student_id,
            'content_id': content_id,
            'student_name': student_name,
            'student_id_number': s['student_id_number'],
            'period': s.get('period', ''),
            'answers': answers,
            'question_times': question_times,
            'results': instant_results,
            'time_taken_seconds': time_taken,
            'attempt_number': attempt,
            'is_late': is_late,
        }

        if needs_multipass:
            submission_row['status'] = 'partial'
            submission_row['score'] = None
            submission_row['percentage'] = None
            submission_row['grading_status'] = 'partial'
        else:
            submission_row['status'] = 'graded'
            submission_row['score'] = instant_results.get('score')
            submission_row['percentage'] = instant_results.get('percentage')
            submission_row['total_points'] = instant_results.get('total_points')

        # Caller-generated UUID + upsert on id makes this retry-safe: if a
        # transient error drops the response after the server committed,
        # the retry merges-duplicates on the same id (no double-write).
        submission_row['id'] = str(uuid.uuid4())
        try:
            result = db.table('student_submissions').upsert(
                submission_row, on_conflict='id'
            ).execute()
        except Exception as insert_err:
            if '23505' in str(insert_err) or 'duplicate' in str(insert_err).lower():
                return jsonify({"error": "You have already submitted this assignment."}), 400
            raise

        if not result.data:
            return jsonify({"error": "Failed to submit"}), 500

        submission_id = result.data[0]['id']

        # Spawn multipass grading thread for written questions
        if needs_multipass:
            from backend.services.grading_service import load_teacher_config
            teacher_config = load_teacher_config(teacher_id)
            teacher_config["period"] = s.get("period", "")

            # Get accommodations from published content settings (already fetched with settings column)
            published_accommodations = pc.data[0].get('settings', {}).get('student_accommodations', {}) if pc.data else {}

            _spawn_grading_thread_safe(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment_content,
                    answers,
                    {
                        "student_name": student_name,
                        "student_id": s.get("student_id_number", ""),
                        "email": s.get("email", ""),
                    },
                    teacher_config,
                    teacher_id,
                    "student_submissions",
                ),
                kwargs={"student_accommodations": published_accommodations},
            )

        # Queue confirmation email (keep existing logic)
        student_email = s.get('email')
        if student_email and teacher_id:
            try:
                missing = []
                all_content = db.table('published_content').select('id, title').eq(
                    'class_id', class_id).eq('is_active', True).execute()
                if all_content.data:
                    all_content_ids = [c['id'] for c in all_content.data]
                    student_subs = db.table('student_submissions').select(
                        'content_id'
                    ).eq('student_id', student_id).in_(
                        'content_id', all_content_ids
                    ).execute()
                    submitted_ids = {sub['content_id'] for sub in student_subs.data}
                    missing = [
                        c['title'] for c in all_content.data
                        if c['id'] not in submitted_ids and c['id'] != content_id
                    ]

                now_ts = datetime.now(tz=timezone.utc).isoformat()
                db.table('submission_confirmations').insert({
                    'submission_id': submission_id,
                    'teacher_id': teacher_id,
                    'student_email': student_email,
                    'student_name': student_name,
                    'assignment_title': content_title,
                    'attempt_number': attempt,
                    'missing_assignments': missing,
                    'submitted_at': now_ts,
                    'status': 'pending',
                }).execute()
            except Exception as conf_err:
                _logger.debug("Confirmation queue insert skipped: %s", conf_err)

        # Return instant results to student (MC scores immediately)
        publish_settings = pc.data[0].get('settings', {}) if pc.data else {}
        response = {
            "success": True,
            "submission_id": submission_id,
            "is_late": is_late,
        }

        # Assessment mode: if both score and answers are hidden, return pending_review
        if not publish_settings.get('show_score_immediately', True) and not publish_settings.get('show_correct_answers', True):
            response["grading_status"] = "pending_review"
            response["message"] = "Submitted! Your teacher will review and share your results."
        elif needs_multipass:
            mc_correct = sum(1 for q in (instant_results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (instant_results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (instant_results.get("questions") or []) if q.get("status") == "pending_review")
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = "Multiple choice graded. Written responses pending teacher review."
        else:
            response["message"] = "Submitted and graded successfully!"
            if publish_settings.get('show_score_immediately', True):
                response["score"] = instant_results.get("score")
                response["percentage"] = instant_results.get("percentage")
            else:
                response["grading_status"] = "pending_review"
                response["message"] = "Submitted! Your teacher will review and share your results."

        return jsonify(response)
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/student/session', methods=['GET'])
@handle_route_errors
def check_student_session():
    """Check if current student session is valid."""
    session = _validate_student_session()
    if session is None:
        return jsonify({"valid": False}), 401

    student_id, class_id = session
    try:
        db = _get_supabase()
        student = db.table('students').select(
            'first_name, last_name, student_id_number, email'
        ).eq('id', student_id).execute()

        if not student.data:
            return jsonify({"valid": False}), 401

        s = student.data[0]

        # Include class info for Clever SSO students (dashboard header)
        class_info = {}
        try:
            cls = db.table('classes').select('name, subject').eq('id', class_id).execute()
            if cls.data:
                class_info = {
                    "name": cls.data[0].get('name', ''),
                    "subject": cls.data[0].get('subject', ''),
                }
        except Exception as e:
            sentry_sdk.capture_exception(e)

        return jsonify({
            "valid": True,
            "student": {
                "first_name": s['first_name'],
                "last_name": s['last_name'],
                "email": s.get('email', ''),
                "student_id": s['student_id_number'],
            },
            "class_info": class_info,
        })
    except Exception:
        return jsonify({"valid": False}), 401


@student_account_bp.route('/api/send-submission-confirmations', methods=['POST'])
@require_teacher
@handle_route_errors
def send_submission_confirmations():
    """Batch-send pending submission confirmations via Outlook."""
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()

        # Recover stale 'processing' rows (stuck > 10 min) back to pending
        stale_cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=10)).isoformat()
        db.table('submission_confirmations').update({
            'status': 'pending'
        }).eq('teacher_id', teacher_id).eq('status', 'processing').lt(
            'created_at', stale_cutoff
        ).execute()

        # Fetch all pending for this teacher
        pending = db.table('submission_confirmations').select('*').eq(
            'teacher_id', teacher_id
        ).eq('status', 'pending').execute()

        if not pending.data:
            return jsonify({"error": "No pending confirmations"}), 400

        # Mark as processing immediately
        conf_ids = [row['id'] for row in pending.data]
        db.table('submission_confirmations').update({
            'status': 'processing'
        }).eq('teacher_id', teacher_id).eq('status', 'pending').execute()

        # Load teacher name from email config
        email_config_path = os.path.join(
            os.path.expanduser('~'), '.graider_data', 'email_config.json'
        )
        teacher_name = 'Your Teacher'
        if os.path.exists(email_config_path):
            with open(email_config_path, 'r') as f:
                email_cfg = json.load(f)
                teacher_name = email_cfg.get('teacher_name', teacher_name)

        # Build Outlook email array
        emails = []
        for row in pending.data:
            first_name = row['student_name'].split()[0] if row['student_name'] else 'Student'

            body = f"Hi {first_name},\n\n"
            body += f"Your submission for \"{row['assignment_title']}\" was received successfully.\n\n"
            body += f"Attempt: #{row['attempt_number']}\n"

            sub_time = row.get('submitted_at', '')
            if sub_time:
                try:
                    dt = datetime.fromisoformat(sub_time.replace('Z', '+00:00'))
                    sub_time = dt.strftime('%B %d, %Y at %I:%M %p')
                except Exception:
                    pass
            body += f"Submitted: {sub_time}\n"

            if row['attempt_number'] > 1:
                body += f"\nThis is attempt #{row['attempt_number']}. Your previous submission(s) are also on file.\n"

            missing = row.get('missing_assignments') or []
            if isinstance(missing, str):
                missing = json.loads(missing)
            if missing:
                body += "\nAssignments still due:\n"
                for title in missing:
                    body += f"  - {title}\n"

            body += f"\n{teacher_name}"

            emails.append({
                'to': row['student_email'],
                'cc': '',
                'subject': f"Submission Confirmed \u2014 {row['assignment_title']}",
                'body': body,
                'student_name': row['student_name'],
            })

        # Launch Outlook sender
        from flask import g
        from backend.routes.email_routes import launch_outlook_sender
        teacher_id = getattr(g, 'user_id', 'local-dev')
        result = launch_outlook_sender(emails, teacher_id=teacher_id)

        if 'error' in result:
            # Revert to pending on launch failure
            db.table('submission_confirmations').update({
                'status': 'pending'
            }).in_('id', conf_ids).execute()
            return jsonify(result), 500

        return jsonify({
            "status": "started",
            "total": len(emails),
            "confirmation_ids": conf_ids,
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/mark-confirmations-sent', methods=['POST'])
@require_teacher
@handle_route_errors
def mark_confirmations_sent():
    """Mark confirmations as sent after Outlook send completes."""
    teacher_id = g.teacher_id

    try:
        db = _get_teacher_supabase()
        data = request.json or {}
        conf_ids = data.get('confirmation_ids', [])
        status = data.get('status', 'sent')

        if not conf_ids:
            # Mark all processing as sent for this teacher
            db.table('submission_confirmations').update({
                'status': 'sent',
                'sent_at': datetime.now(tz=timezone.utc).isoformat(),
            }).eq('teacher_id', teacher_id).eq('status', 'processing').execute()
        else:
            if status == 'sent':
                db.table('submission_confirmations').update({
                    'status': 'sent',
                    'sent_at': datetime.now(tz=timezone.utc).isoformat(),
                }).in_('id', conf_ids).execute()
            else:
                # Revert failed ones to pending for retry
                db.table('submission_confirmations').update({
                    'status': 'pending',
                }).in_('id', conf_ids).execute()

        return jsonify({"success": True})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Student Resource Endpoints ============

RESOURCE_CONTENT_TYPES = ['study_guide', 'flashcards', 'slide_deck']


@student_account_bp.route('/api/student/resources', methods=['GET'])
@handle_route_errors
def student_resources():
    """List resources (study guides, flashcards, slide decks) published to student's class.

    Uses X-Student-Token header for auth (same as student dashboard).
    Returns only resource-type content, not assessments/assignments.
    """
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        # Phase 4: list-filter — only show class-wide rows OR rows targeting this student.
        # student_id is a UUID from session lookup (validated by Supabase), so safe to interpolate.
        targeting_filter = f'target_student_ids.is.null,target_student_ids.cs.{json.dumps([student_id])}'
        # Get published content for this class
        content_result = db.table('published_content').select(
            'id, title, content_type, created_at, settings'
        ).eq('class_id', class_id).eq('is_active', True).or_(
            targeting_filter
        ).order('created_at', desc=True).execute()

        resources = []
        for item in (content_result.data or []):
            if item.get('content_type') in RESOURCE_CONTENT_TYPES:
                resources.append({
                    "id": item['id'],
                    "title": item.get('title', 'Untitled'),
                    "content_type": item['content_type'],
                    "created_at": item.get('created_at', ''),
                })

        return jsonify({"resources": resources})

    except Exception as e:
        _logger.exception("Student resources error")
        return jsonify({"error": "Failed to load resources"}), 500


@student_account_bp.route('/api/student/resource/<content_id>', methods=['GET'])
@handle_route_errors
def student_resource_content(content_id):
    """Get full resource content for viewing/downloading.

    Returns the content JSON for study guides/flashcards, or the
    slide deck data for download.
    """
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        # Phase 4: targeting visibility check (must run before any content read).
        if not _content_visible_to_student(db, content_id, student_id, class_id):
            return jsonify({"error": "Resource not found"}), 404

        # Get the resource — must belong to student's class
        content_result = db.table('published_content').select(
            'id, title, content_type, content, settings'
        ).eq('id', content_id).eq('class_id', class_id).eq(
            'is_active', True
        ).execute()

        if not content_result.data:
            return jsonify({"error": "Resource not found"}), 404

        item = content_result.data[0]
        if item.get('content_type') not in RESOURCE_CONTENT_TYPES:
            return jsonify({"error": "Not a resource"}), 400

        return jsonify({
            "resource": {
                "id": item['id'],
                "title": item.get('title', 'Untitled'),
                "content_type": item['content_type'],
                "content": item.get('content', {}),
            }
        })

    except Exception as e:
        _logger.exception("Student resource content error")
        return jsonify({"error": "Failed to load resource"}), 500


@student_account_bp.route('/api/student/submission/<content_id>/draft', methods=['POST'])
@handle_route_errors
@critical_path
def save_submission_draft(content_id):
    """Save or update a draft submission for the authenticated student."""
    session_info = _validate_student_session()
    if not session_info:
        return jsonify({"error": "Invalid session"}), 401
    student_id, class_id = session_info

    try:
        db = _get_supabase()

        # Phase 4: targeting visibility check (must run before any content read).
        if not _content_visible_to_student(db, content_id, student_id, class_id):
            return jsonify({"error": "Content not found"}), 404

        data = request.json or {}
        draft_answers = data.get('answers') or {}
        question_times = data.get('question_times') or {}
        marked_for_review = data.get('marked_for_review') or []

        # Verify content belongs to this class
        content = db.table('published_content').select('id, settings').eq(
            'id', content_id
        ).eq('class_id', class_id).execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        # Check for existing submission
        existing = db.table('student_submissions').select('*').eq(
            'student_id', student_id
        ).eq('content_id', content_id).execute()

        if existing.data:
            row = existing.data[0]
            if row.get('status') in ('submitted', 'graded', 'grading', 'partial'):
                return jsonify({"error": "Already submitted"}), 409
            # Update existing draft
            db.table('student_submissions').update({
                'draft_answers': draft_answers,
                'question_times': question_times,
                'marked_for_review': marked_for_review,
                'status': 'draft',
            }).eq('id', row['id']).execute()
            time_started_at = row.get('time_started_at')
            if not time_started_at:
                # Backfill if missing
                time_started_at = datetime.now(timezone.utc).isoformat()
                db.table('student_submissions').update({
                    'time_started_at': time_started_at
                }).eq('id', row['id']).execute()
        else:
            # Create new draft row
            now_iso = datetime.now(timezone.utc).isoformat()
            student_row = db.table('students').select(
                'first_name, last_name, student_id_number, period'
            ).eq('id', student_id).execute()
            sdata = student_row.data[0] if student_row.data else {}
            db.table('student_submissions').upsert({
                'id': str(uuid.uuid4()),
                'student_id': student_id,
                'content_id': content_id,
                'student_name': (sdata.get('first_name', '') + ' ' + sdata.get('last_name', '')).strip(),
                'student_id_number': sdata.get('student_id_number'),
                'period': sdata.get('period'),
                'status': 'draft',
                'draft_answers': draft_answers,
                'question_times': question_times,
                'marked_for_review': marked_for_review,
                'time_started_at': now_iso,
            }, on_conflict='id').execute()
            time_started_at = now_iso

        # Calculate remaining time
        remaining_seconds = None
        if time_limit_seconds and time_started_at:
            started = datetime.fromisoformat(time_started_at.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            remaining_seconds = max(0, int(time_limit_seconds - elapsed))

        return jsonify({
            "success": True,
            "time_started_at": time_started_at,
            "remaining_seconds": remaining_seconds,
            "time_limit_seconds": time_limit_seconds,
        })
    except Exception as e:
        _logger.exception("Save draft error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/student/submission/<content_id>/draft', methods=['GET'])
@handle_route_errors
def get_submission_draft(content_id):
    """Fetch an existing draft for resume."""
    session_info = _validate_student_session()
    if not session_info:
        return jsonify({"error": "Invalid session"}), 401
    student_id, class_id = session_info

    try:
        db = _get_supabase()

        # Phase 4: targeting visibility check (must run before any content read).
        if not _content_visible_to_student(db, content_id, student_id, class_id):
            return jsonify({"error": "Content not found"}), 404

        # Verify content belongs to class
        content = db.table('published_content').select('id, settings').eq(
            'id', content_id
        ).eq('class_id', class_id).execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        # Find existing draft
        existing = db.table('student_submissions').select('*').eq(
            'student_id', student_id
        ).eq('content_id', content_id).eq('status', 'draft').execute()

        if not existing.data:
            return jsonify({"draft": None})

        row = existing.data[0]
        time_started_at = row.get('time_started_at')
        remaining_seconds = None
        if time_limit_seconds and time_started_at:
            started = datetime.fromisoformat(time_started_at.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            remaining_seconds = max(0, int(time_limit_seconds - elapsed))

        return jsonify({
            "draft": {
                "answers": row.get('draft_answers') or {},
                "question_times": row.get('question_times') or {},
                "marked_for_review": row.get('marked_for_review') or [],
                "time_started_at": time_started_at,
                "remaining_seconds": remaining_seconds,
                "time_limit_seconds": time_limit_seconds,
            }
        })
    except Exception as e:
        _logger.exception("Get draft error")
        return jsonify({"error": "An internal error occurred"}), 500
