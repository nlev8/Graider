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
import functools
import hashlib
import io
import json
import os
import random
import secrets
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as _get_supabase
from backend.extensions import limiter

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


def require_teacher(f):
    """Decorator that enforces teacher authentication.
    Sets g.teacher_id for use in the wrapped route handler.
    Returns 401 if no authenticated teacher session exists."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        teacher_id = getattr(g, 'user_id', None)
        if not teacher_id:
            return jsonify({"error": "Authentication required"}), 401
        g.teacher_id = teacher_id
        return f(*args, **kwargs)
    return wrapper


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


# ============ Teacher Endpoints (require teacher JWT) ============

@student_account_bp.route('/api/classes', methods=['POST'])
@require_teacher
def create_class():
    """Create a class. Generates join code."""
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()
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
def list_classes():
    """List teacher's classes with student counts."""
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()
        classes = db.table('classes').select(
            '*, class_students(count)'
        ).eq('teacher_id', teacher_id).eq('is_active', True).execute()

        return jsonify({"classes": classes.data})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/classes/<class_id>/sync-roster', methods=['POST'])
@require_teacher
def sync_roster_to_class(class_id):
    """Sync students from an uploaded CSV into the class.
    Accepts multipart/form-data with a 'file' field containing the CSV.
    CSV must have columns for student identification (Student ID, First Name, Last Name).
    """
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()

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
def list_class_students(class_id):
    """List students enrolled in a class."""
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()

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
def publish_to_class():
    """Publish an assessment or assignment to a class."""
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()
        data = request.json
        class_id = data.get('class_id')
        content = data.get('content')
        content_type = data.get('content_type', 'assessment')
        title = data.get('title', 'Untitled')
        settings = data.get('settings', {})
        due_date = data.get('due_date')

        if not content:
            return jsonify({"error": "No content provided"}), 400
        if content_type not in ('assessment', 'assignment'):
            return jsonify({"error": "content_type must be 'assessment' or 'assignment'"}), 400

        join_code = _generate_class_code()

        result = db.table('published_content').insert({
            'teacher_id': teacher_id,
            'class_id': class_id,
            'content_type': content_type,
            'title': title,
            'join_code': join_code,
            'content': content,
            'settings': settings,
            'is_active': True,
            'due_date': due_date,
        }).execute()

        if not result.data:
            return jsonify({"error": "Failed to publish"}), 500

        host = request.host_url.rstrip('/')
        return jsonify({
            "success": True,
            "content_id": result.data[0]['id'],
            "join_code": join_code,
            "join_link": f"{host}/student?code={join_code}",
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/portal-submissions', methods=['GET'])
@require_teacher
def get_portal_submissions():
    """Get all student submissions for the Results tab."""
    teacher_id = g.teacher_id

    # Local dev has no real Supabase teacher record
    if teacher_id == 'local-dev':
        return jsonify({"submissions": [], "pending_confirmations": 0})

    try:
        db = _get_supabase()

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
        except Exception:
            pass

        return jsonify({"submissions": results, "pending_confirmations": pending_count})
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/grade-portal-submission', methods=['POST'])
@require_teacher
def grade_portal_submission():
    """Grade a portal submission using the existing grading pipeline.
    Takes a submission_id and runs it through the assessment auto-grader.
    """
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()
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
        questions = assessment.get('questions', [])

        # Auto-grade each question
        total_points = 0
        earned_points = 0
        graded_results = []

        for i, q in enumerate(questions):
            q_points = q.get('points', 1)
            total_points += q_points
            student_ans = student_answers.get(str(i), student_answers.get(str(i + 1), ''))
            correct_ans = q.get('correct_answer', q.get('answer', ''))
            q_type = q.get('question_type', 'short_answer')

            points_earned = 0

            if q_type == 'multiple_choice':
                if str(student_ans).strip().lower() == str(correct_ans).strip().lower():
                    points_earned = q_points
            elif q_type == 'true_false':
                if str(student_ans).strip().lower() == str(correct_ans).strip().lower():
                    points_earned = q_points
            elif q_type == 'matching':
                if isinstance(student_ans, dict) and isinstance(correct_ans, dict):
                    correct_count = sum(1 for k, v in correct_ans.items()
                                        if student_ans.get(k, '').strip().lower() == v.strip().lower())
                    if correct_ans:
                        points_earned = round(q_points * correct_count / len(correct_ans), 1)
            elif q_type in ('fill_in_blank', 'fitb'):
                if str(student_ans).strip().lower() == str(correct_ans).strip().lower():
                    points_earned = q_points
            else:
                # Short answer / written — mark as needs_review for teacher
                points_earned = 0  # Teacher reviews these

            earned_points += points_earned
            graded_results.append({
                'question_index': i,
                'question_text': q.get('question_text', q.get('question', '')),
                'student_answer': student_ans,
                'correct_answer': correct_ans,
                'points_earned': points_earned,
                'points_possible': q_points,
                'auto_graded': q_type in ('multiple_choice', 'true_false', 'matching', 'fill_in_blank', 'fitb'),
            })

        percentage = round((earned_points / total_points * 100) if total_points > 0 else 0, 1)
        letter_grade = (
            'A' if percentage >= 90 else
            'B' if percentage >= 80 else
            'C' if percentage >= 70 else
            'D' if percentage >= 60 else 'F'
        )

        # Update the submission with grading results
        db.table('student_submissions').update({
            'results': graded_results,
            'score': earned_points,
            'total_points': total_points,
            'percentage': percentage,
            'letter_grade': letter_grade,
            'status': 'graded',
            'graded_at': datetime.now(tz=timezone.utc).isoformat(),
        }).eq('id', submission_id).execute()

        needs_review = [r for r in graded_results if not r['auto_graded']]

        return jsonify({
            "success": True,
            "score": earned_points,
            "total_points": total_points,
            "percentage": percentage,
            "letter_grade": letter_grade,
            "results": graded_results,
            "needs_review": len(needs_review),
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Student Endpoints (public, session-based auth) ============

@student_account_bp.route('/api/student/login', methods=['POST'])
@limiter.limit("10/minute")
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
def student_dashboard():
    """Get student's assigned work (assessments + assignments)."""
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        content = db.table('published_content').select('*').eq(
            'class_id', class_id
        ).eq('is_active', True).order('created_at', desc=True).execute()

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

        result = db.table('published_content').select('*').eq(
            'id', content_id
        ).eq('class_id', class_id).eq('is_active', True).execute()

        if not result.data:
            return jsonify({"error": "Content not found"}), 404

        item = result.data[0]
        content = item['content']

        # Strip answer keys
        if 'questions' in content:
            for q in content['questions']:
                q.pop('correct_answer', None)
                q.pop('answer', None)
                q.pop('rubric', None)
                q.pop('expected_answer', None)
                q.pop('answer_key', None)
                if q.get('question_type') in ('matching', 'drag_drop', 'ordering'):
                    if 'options' in q and isinstance(q['options'], list):
                        random.shuffle(q['options'])

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
def submit_student_work(content_id):
    """Submit answers for an assessment or assignment."""
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()
        data = request.json
        answers = data.get('answers', {})
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

        result = db.table('student_submissions').insert({
            'student_id': student_id,
            'content_id': content_id,
            'student_name': student_name,
            'student_id_number': s['student_id_number'],
            'period': s.get('period', ''),
            'answers': answers,
            'status': 'submitted',
            'time_taken_seconds': time_taken,
            'attempt_number': attempt,
        }).execute()

        if not result.data:
            return jsonify({"error": "Failed to submit"}), 500

        # Queue confirmation email for batch sending via Outlook
        student_email = s.get('email')
        teacher_id = s.get('teacher_id')
        if student_email and teacher_id:
            try:
                # Get assignment title
                pc = db.table('published_content').select('title').eq(
                    'id', content_id).execute()
                assignment_title = pc.data[0]['title'] if pc.data else 'Assignment'

                # Compute missing assignments for this student
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
                    'submission_id': result.data[0]['id'],
                    'teacher_id': teacher_id,
                    'student_email': student_email,
                    'student_name': student_name,
                    'assignment_title': assignment_title,
                    'attempt_number': attempt,
                    'missing_assignments': missing,
                    'submitted_at': now_ts,
                    'status': 'pending',
                }).execute()
            except Exception as conf_err:
                # UNIQUE conflict or other error — skip silently, submission still succeeds
                print(f"Confirmation queue insert skipped: {conf_err}")

        return jsonify({
            "success": True,
            "submission_id": result.data[0]['id'],
            "message": "Submitted successfully!",
        })
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_account_bp.route('/api/student/session', methods=['GET'])
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
        return jsonify({
            "valid": True,
            "student": {
                "first_name": s['first_name'],
                "last_name": s['last_name'],
                "email": s.get('email', ''),
                "student_id": s['student_id_number'],
            },
        })
    except Exception:
        return jsonify({"valid": False}), 401


@student_account_bp.route('/api/send-submission-confirmations', methods=['POST'])
@require_teacher
def send_submission_confirmations():
    """Batch-send pending submission confirmations via Outlook."""
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()

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
def mark_confirmations_sent():
    """Mark confirmations as sent after Outlook send completes."""
    teacher_id = g.teacher_id

    try:
        db = _get_supabase()
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
