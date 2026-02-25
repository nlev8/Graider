# Student Account System & Unified Portal

## Context

Currently, students submit assignments via SharePoint (OneDrive-synced folder). The teacher has to manually search inside the SharePoint folder to find ungraded submissions, then load them into Graider for grading. The assessment portal uses anonymous name entry — students type their name each time, leading to typos and no verified identity.

**Goals:**
1. Student accounts created from the existing roster/period CSVs
2. Unified student portal for assessments AND assignments
3. Pending submissions visible in the Results tab (no more SharePoint searching)
4. Eventually replace SharePoint for digital assignment submission

**Constraint:** The school district currently blocks Graider on their WiFi. This is a build-now, test-when-IT-whitelists situation.

---

## Phase 1: Supabase Schema

Create these tables in the Supabase dashboard (SQL Editor):

```sql
-- Students table (created from teacher's roster imports)
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    student_id_number TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    period TEXT,
    class_code TEXT,
    accommodations JSONB DEFAULT '{}',
    ell_language TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(teacher_id, student_id_number)
);

CREATE INDEX idx_students_lookup ON students(student_id_number, teacher_id);
CREATE INDEX idx_students_teacher ON students(teacher_id);

-- Classes table (one per period, holds join code)
CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    name TEXT NOT NULL,
    join_code TEXT NOT NULL UNIQUE,
    subject TEXT,
    grade_level TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(teacher_id, name)
);

CREATE INDEX idx_classes_join_code ON classes(join_code);

-- Junction: students ↔ classes
CREATE TABLE class_students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(class_id, student_id)
);

-- Student sessions (lightweight auth, no Supabase auth.users for students)
CREATE TABLE student_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sessions_token ON student_sessions(session_token);

-- Published content (unified: assessments + assignments)
-- Extends the existing published_assessments pattern
CREATE TABLE published_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    class_id UUID REFERENCES classes(id),
    content_type TEXT NOT NULL CHECK (content_type IN ('assessment', 'assignment')),
    title TEXT NOT NULL,
    join_code TEXT UNIQUE,
    content JSONB NOT NULL,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_published_class ON published_content(class_id, is_active);

-- Student submissions (unified: replaces current submissions table for new flow)
CREATE TABLE student_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id),
    content_id UUID REFERENCES published_content(id),
    student_name TEXT NOT NULL,
    student_id_number TEXT,
    period TEXT,
    answers JSONB,
    results JSONB,
    score NUMERIC,
    total_points NUMERIC,
    percentage NUMERIC,
    letter_grade TEXT,
    status TEXT DEFAULT 'submitted' CHECK (status IN (
        'in_progress', 'submitted', 'grading', 'graded', 'returned'
    )),
    time_taken_seconds INTEGER,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    graded_at TIMESTAMPTZ,
    attempt_number INTEGER DEFAULT 1
);

CREATE INDEX idx_submissions_student ON student_submissions(student_id);
CREATE INDEX idx_submissions_content ON student_submissions(content_id);
CREATE INDEX idx_submissions_status ON student_submissions(status);
```

**Note:** The existing `published_assessments` and `submissions` tables are kept for backward compatibility. New content goes through `published_content` / `student_submissions`.

---

## Phase 2: Backend — Student Account Routes

### New file: `backend/routes/student_account_routes.py`

```python
"""
Student Account Routes for Graider.
Handles student auth, class management, and unified content delivery.
Students log in with Student ID + Class Join Code (no passwords).
"""
import json
import os
import random
import string
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from supabase import create_client, Client

student_account_bp = Blueprint('student_account', __name__)

# Supabase client (reuse pattern from student_portal_routes.py)
_supabase: Client = None

def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Supabase credentials not configured")
        _supabase = create_client(url, key)
    return _supabase


def _generate_class_code():
    """Generate a unique 6-char class join code."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    db = _get_supabase()
    while True:
        code = ''.join(random.choices(chars, k=6))
        result = db.table('classes').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code


def _validate_student_session(require=True):
    """Validate student session token from X-Student-Token header.
    Returns (student_id, class_id) tuple or (None, None) if invalid.
    """
    token = request.headers.get('X-Student-Token', '')
    if not token:
        return (None, None) if not require else None

    db = _get_supabase()
    result = db.table('student_sessions').select(
        'student_id, class_id, expires_at'
    ).eq('session_token', token).execute()

    if not result.data:
        return (None, None) if not require else None

    session = result.data[0]
    if datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00')) < datetime.now(
        tz=__import__('datetime').timezone.utc
    ):
        # Expired — clean up
        db.table('student_sessions').delete().eq('session_token', token).execute()
        return (None, None) if not require else None

    return (session['student_id'], session['class_id'])


# ============ Teacher Endpoints (require teacher JWT) ============

@student_account_bp.route('/api/classes', methods=['POST'])
def create_class():
    """Create a class from a period. Generates join code."""
    try:
        db = _get_supabase()
        data = request.json
        name = data.get('name', '').strip()
        subject = data.get('subject', '')
        grade_level = data.get('grade_level', '')

        if not name:
            return jsonify({"error": "Class name is required"}), 400

        join_code = _generate_class_code()
        teacher_id = getattr(g, 'user_id', 'local-dev')

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
        return jsonify({"error": str(e)}), 500


@student_account_bp.route('/api/classes', methods=['GET'])
def list_classes():
    """List teacher's classes with student counts."""
    try:
        db = _get_supabase()
        teacher_id = getattr(g, 'user_id', 'local-dev')

        classes = db.table('classes').select(
            '*, class_students(count)'
        ).eq('teacher_id', teacher_id).eq('is_active', True).execute()

        return jsonify({"classes": classes.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@student_account_bp.route('/api/classes/<class_id>/sync-roster', methods=['POST'])
def sync_roster_to_class(class_id):
    """Sync students from a period CSV file into Supabase students table.
    Reads from the existing ~/.graider_data/periods/ files.
    """
    try:
        db = _get_supabase()
        data = request.json
        period_filename = data.get('period_filename', '')
        teacher_id = getattr(g, 'user_id', 'local-dev')

        # Verify class belongs to teacher
        cls = db.table('classes').select('*').eq('id', class_id).eq(
            'teacher_id', teacher_id
        ).execute()
        if not cls.data:
            return jsonify({"error": "Class not found"}), 404

        # Read students from local period file
        from backend.routes.settings_routes import get_students_from_period_file, PERIODS_DIR
        from werkzeug.utils import secure_filename
        filepath = os.path.join(PERIODS_DIR, secure_filename(period_filename))
        if not os.path.exists(filepath):
            return jsonify({"error": "Period file not found"}), 404

        students = get_students_from_period_file(filepath)
        synced = 0
        errors = []

        for s in students:
            first = s.get('first', '').strip()
            last = s.get('last', '').strip()
            sid = s.get('id', '').strip()
            if not first and not last:
                continue
            if not sid:
                sid = f"{first}_{last}".lower().replace(' ', '_')

            try:
                # Upsert student
                student_result = db.table('students').upsert({
                    'teacher_id': teacher_id,
                    'student_id_number': sid,
                    'first_name': first,
                    'last_name': last,
                    'period': cls.data[0].get('name', ''),
                    'is_active': True,
                    'updated_at': datetime.utcnow().isoformat(),
                }, on_conflict='teacher_id,student_id_number').execute()

                if student_result.data:
                    student_uuid = student_result.data[0]['id']
                    # Link to class
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
            "total": len(students),
            "errors": errors,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@student_account_bp.route('/api/classes/<class_id>/students', methods=['GET'])
def list_class_students(class_id):
    """List students enrolled in a class."""
    try:
        db = _get_supabase()
        teacher_id = getattr(g, 'user_id', 'local-dev')

        # Verify class ownership
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
        return jsonify({"error": str(e)}), 500


@student_account_bp.route('/api/publish-to-class', methods=['POST'])
def publish_to_class():
    """Publish an assessment or assignment to a class."""
    try:
        db = _get_supabase()
        data = request.json
        class_id = data.get('class_id')
        content = data.get('content')
        content_type = data.get('content_type', 'assessment')
        title = data.get('title', 'Untitled')
        settings = data.get('settings', {})
        due_date = data.get('due_date')
        teacher_id = getattr(g, 'user_id', 'local-dev')

        if not content:
            return jsonify({"error": "No content provided"}), 400
        if content_type not in ('assessment', 'assignment'):
            return jsonify({"error": "content_type must be 'assessment' or 'assignment'"}), 400

        # Generate join code for backward compat / direct links
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
        return jsonify({"error": str(e)}), 500


@student_account_bp.route('/api/portal-submissions', methods=['GET'])
def get_portal_submissions():
    """Get all student submissions for the Results tab.
    Returns both graded and pending submissions.
    """
    try:
        db = _get_supabase()
        teacher_id = getattr(g, 'user_id', 'local-dev')

        # Get all published content IDs for this teacher
        content = db.table('published_content').select('id, title, content_type').eq(
            'teacher_id', teacher_id
        ).execute()
        content_ids = [c['id'] for c in content.data]
        content_map = {c['id']: c for c in content.data}

        if not content_ids:
            return jsonify({"submissions": []})

        # Get all submissions for this teacher's content
        subs = db.table('student_submissions').select('*').in_(
            'content_id', content_ids
        ).order('submitted_at', desc=True).execute()

        # Format for Results tab compatibility
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

        return jsonify({"submissions": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ Student Endpoints (public, session-based auth) ============

@student_account_bp.route('/api/student/login', methods=['POST'])
def student_login():
    """Student login with Student ID + class join code.
    Returns a session token valid for 8 hours.
    """
    try:
        db = _get_supabase()
        data = request.json
        student_id_number = data.get('student_id', '').strip()
        class_code = data.get('class_code', '').strip().upper()

        if not student_id_number or not class_code:
            return jsonify({"error": "Student ID and class code are required"}), 400

        # Find the class by join code
        cls = db.table('classes').select('id, teacher_id, name, subject').eq(
            'join_code', class_code
        ).eq('is_active', True).execute()

        if not cls.data:
            return jsonify({"error": "Invalid class code"}), 404

        class_data = cls.data[0]

        # Find the student by ID + teacher
        student = db.table('students').select('*').eq(
            'student_id_number', student_id_number
        ).eq('teacher_id', class_data['teacher_id']).eq(
            'is_active', True
        ).execute()

        if not student.data:
            return jsonify({"error": "Student ID not found. Ask your teacher for help."}), 404

        student_data = student.data[0]

        # Verify student is enrolled in this class
        enrollment = db.table('class_students').select('id').eq(
            'class_id', class_data['id']
        ).eq('student_id', student_data['id']).execute()

        if not enrollment.data:
            return jsonify({"error": "You are not enrolled in this class"}), 403

        # Create session token (64 random chars, 8-hour expiry)
        token = secrets.token_urlsafe(48)
        expires = datetime.utcnow() + timedelta(hours=8)

        db.table('student_sessions').insert({
            'student_id': student_data['id'],
            'class_id': class_data['id'],
            'session_token': token,
            'expires_at': expires.isoformat(),
        }).execute()

        return jsonify({
            "success": True,
            "token": token,
            "student": {
                "first_name": student_data['first_name'],
                "last_name": student_data['last_name'],
                "student_id": student_data['student_id_number'],
                "period": student_data.get('period', ''),
            },
            "class": {
                "name": class_data['name'],
                "subject": class_data.get('subject', ''),
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@student_account_bp.route('/api/student/dashboard', methods=['GET'])
def student_dashboard():
    """Get student's assigned work (assessments + assignments)."""
    session = _validate_student_session()
    if session is None:
        return jsonify({"error": "Not logged in"}), 401

    student_id, class_id = session

    try:
        db = _get_supabase()

        # Get published content for this class
        content = db.table('published_content').select('*').eq(
            'class_id', class_id
        ).eq('is_active', True).order('created_at', desc=True).execute()

        # Get student's existing submissions
        submissions = db.table('student_submissions').select(
            'content_id, status, score, percentage, letter_grade, submitted_at'
        ).eq('student_id', student_id).execute()

        sub_map = {}
        for s in submissions.data:
            sub_map[s['content_id']] = s

        # Build dashboard items
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
        return jsonify({"error": str(e)}), 500


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

        # Get the content
        result = db.table('published_content').select('*').eq(
            'id', content_id
        ).eq('class_id', class_id).eq('is_active', True).execute()

        if not result.data:
            return jsonify({"error": "Content not found"}), 404

        item = result.data[0]
        content = item['content']

        # Strip answer keys (same logic as existing student_portal_routes.py)
        if 'questions' in content:
            for q in content['questions']:
                q.pop('correct_answer', None)
                q.pop('answer', None)
                q.pop('rubric', None)
                q.pop('expected_answer', None)
                q.pop('answer_key', None)
                if q.get('question_type') in ('matching', 'drag_drop', 'ordering'):
                    # Shuffle options for matching/ordering
                    import random as rnd
                    if 'options' in q and isinstance(q['options'], list):
                        rnd.shuffle(q['options'])

        return jsonify({
            "content_id": item['id'],
            "title": item['title'],
            "content_type": item['content_type'],
            "content": content,
            "settings": item.get('settings', {}),
            "due_date": item.get('due_date'),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

        # Get student info for denormalized fields
        student = db.table('students').select(
            'first_name, last_name, student_id_number, period'
        ).eq('id', student_id).execute()

        if not student.data:
            return jsonify({"error": "Student not found"}), 404

        s = student.data[0]
        student_name = f"{s['first_name']} {s['last_name']}"

        # Check for existing submission (prevent duplicates)
        existing = db.table('student_submissions').select('id').eq(
            'student_id', student_id
        ).eq('content_id', content_id).execute()

        attempt = len(existing.data) + 1

        # Insert submission
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

        return jsonify({
            "success": True,
            "submission_id": result.data[0]['id'],
            "message": "Submitted successfully!",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
            'first_name, last_name, student_id_number'
        ).eq('id', student_id).execute()

        if not student.data:
            return jsonify({"valid": False}), 401

        s = student.data[0]
        return jsonify({
            "valid": True,
            "student": {
                "first_name": s['first_name'],
                "last_name": s['last_name'],
                "student_id": s['student_id_number'],
            },
        })
    except Exception:
        return jsonify({"valid": False}), 401
```

---

## Phase 3: Register the New Blueprint

### File: `backend/routes/__init__.py`

**Edit 1 — Add import** (after line 24):
```python
# OLD (line 24):
from .automation_routes import automation_bp

# NEW:
from .automation_routes import automation_bp
from .student_account_routes import student_account_bp
```

**Edit 2 — Register blueprint** (after line 48):
```python
# OLD (line 48):
    app.register_blueprint(automation_bp)

# NEW:
    app.register_blueprint(automation_bp)
    app.register_blueprint(student_account_bp)
```

**Edit 3 — Add to __all__** (after `'automation_bp'` in __all__ list):
```python
    'automation_bp',
    'student_account_bp',
```

---

## Phase 4: Update Auth to Handle Student Routes

### File: `backend/auth.py`

No changes needed — `/api/student/` is already in `PUBLIC_PREFIXES` (line 12). All student endpoints (`/api/student/login`, `/api/student/dashboard`, `/api/student/submit/*`, `/api/student/session`, `/api/student/content/*`) are already covered.

Teacher endpoints (`/api/classes`, `/api/publish-to-class`, `/api/portal-submissions`) go through normal JWT auth — no changes needed.

---

## Phase 5: Frontend — Student Login & Dashboard

### New file: `frontend/src/components/StudentLogin.jsx`

```jsx
/**
 * Student Login Component
 * Students enter their Student ID + Class Join Code to access the portal.
 */
import React, { useState } from "react";

export default function StudentLogin({ onLogin }) {
  const [studentId, setStudentId] = useState("");
  const [classCode, setClassCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!studentId.trim() || !classCode.trim()) {
      setError("Please enter both your Student ID and class code");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/student/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_id: studentId.trim(),
          class_code: classCode.trim().toUpperCase(),
        }),
      });

      const data = await response.json();
      if (data.success) {
        localStorage.setItem("student_token", data.token);
        localStorage.setItem("student_info", JSON.stringify(data.student));
        localStorage.setItem("student_class", JSON.stringify(data.class));
        onLogin(data);
      } else {
        setError(data.error || "Login failed");
      }
    } catch (e) {
      setError("Could not connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", background: "linear-gradient(135deg, #0f172a, #1e293b)",
      fontFamily: "Inter, sans-serif",
    }}>
      <div style={{
        background: "rgba(30,41,59,0.95)", borderRadius: "16px",
        padding: "40px", maxWidth: "400px", width: "90%",
        border: "1px solid rgba(99,102,241,0.3)",
      }}>
        <h1 style={{ color: "white", fontSize: "1.5rem", fontWeight: 700, marginBottom: "8px", textAlign: "center" }}>
          Graider Student Portal
        </h1>
        <p style={{ color: "#94a3b8", textAlign: "center", marginBottom: "24px", fontSize: "0.9rem" }}>
          Enter your Student ID and class code to get started
        </p>

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ color: "#cbd5e1", fontSize: "0.85rem", display: "block", marginBottom: "6px" }}>
              Student ID
            </label>
            <input
              type="text"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="Enter your student ID number"
              style={{
                width: "100%", padding: "12px", borderRadius: "8px",
                background: "rgba(15,23,42,0.8)", border: "1px solid rgba(99,102,241,0.3)",
                color: "white", fontSize: "1rem", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label style={{ color: "#cbd5e1", fontSize: "0.85rem", display: "block", marginBottom: "6px" }}>
              Class Code
            </label>
            <input
              type="text"
              value={classCode}
              onChange={(e) => setClassCode(e.target.value.toUpperCase())}
              placeholder="e.g. ABC123"
              maxLength={6}
              style={{
                width: "100%", padding: "12px", borderRadius: "8px",
                background: "rgba(15,23,42,0.8)", border: "1px solid rgba(99,102,241,0.3)",
                color: "white", fontSize: "1.2rem", fontWeight: 600, letterSpacing: "3px",
                textAlign: "center", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div style={{
              background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: "8px", padding: "10px 14px", marginBottom: "16px",
              color: "#fca5a5", fontSize: "0.85rem",
            }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            width: "100%", padding: "14px", borderRadius: "10px",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "white", fontSize: "1rem", fontWeight: 600, border: "none",
            cursor: loading ? "wait" : "pointer", opacity: loading ? 0.7 : 1,
          }}>
            {loading ? "Logging in..." : "Enter Portal"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

### New file: `frontend/src/components/StudentDashboard.jsx`

```jsx
/**
 * Student Dashboard Component
 * Shows assigned assessments and assignments after login.
 */
import React, { useState, useEffect } from "react";
import StudentPortal from "./StudentPortal";

export default function StudentDashboard({ studentInfo, classInfo, onLogout }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeContent, setActiveContent] = useState(null); // When taking an assessment/assignment
  const token = localStorage.getItem("student_token");

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/student/dashboard", {
        headers: { "X-Student-Token": token },
      });
      const data = await response.json();
      if (data.items) setItems(data.items);
    } catch (e) {
      console.error("Failed to load dashboard:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("student_token");
    localStorage.removeItem("student_info");
    localStorage.removeItem("student_class");
    onLogout();
  };

  const openContent = async (item) => {
    try {
      const response = await fetch(`/api/student/content/${item.content_id}`, {
        headers: { "X-Student-Token": token },
      });
      const data = await response.json();
      if (data.content) {
        setActiveContent({ ...data, studentName: `${studentInfo.first_name} ${studentInfo.last_name}` });
      }
    } catch (e) {
      console.error("Failed to load content:", e);
    }
  };

  // If student is taking an assessment, render the assessment UI
  if (activeContent) {
    return (
      <StudentPortal
        preloadedAssessment={activeContent.content}
        preloadedStudentName={activeContent.studentName}
        contentId={activeContent.content_id}
        studentToken={token}
        onBack={() => { setActiveContent(null); loadDashboard(); }}
      />
    );
  }

  const statusColors = {
    not_started: { bg: "rgba(100,116,139,0.2)", text: "#94a3b8", label: "Not Started" },
    in_progress: { bg: "rgba(234,179,8,0.2)", text: "#fbbf24", label: "In Progress" },
    submitted: { bg: "rgba(59,130,246,0.2)", text: "#60a5fa", label: "Submitted" },
    graded: { bg: "rgba(34,197,94,0.2)", text: "#4ade80", label: "Graded" },
    returned: { bg: "rgba(168,85,247,0.2)", text: "#c084fc", label: "Returned" },
  };

  return (
    <div style={{
      minHeight: "100vh", background: "linear-gradient(135deg, #0f172a, #1e293b)",
      fontFamily: "Inter, sans-serif", color: "white",
    }}>
      {/* Header */}
      <div style={{
        background: "rgba(30,41,59,0.95)", borderBottom: "1px solid rgba(99,102,241,0.2)",
        padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <h1 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0 }}>
            {studentInfo.first_name} {studentInfo.last_name}
          </h1>
          <p style={{ color: "#94a3b8", fontSize: "0.8rem", margin: "2px 0 0" }}>
            {classInfo.name} {classInfo.subject ? " \u2022 " + classInfo.subject : ""}
          </p>
        </div>
        <button onClick={handleLogout} style={{
          padding: "8px 16px", borderRadius: "8px", background: "rgba(239,68,68,0.2)",
          border: "1px solid rgba(239,68,68,0.3)", color: "#fca5a5", cursor: "pointer",
          fontSize: "0.85rem",
        }}>
          Log Out
        </button>
      </div>

      {/* Content */}
      <div style={{ maxWidth: "800px", margin: "0 auto", padding: "24px" }}>
        <h2 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "16px", color: "#e2e8f0" }}>
          Your Assignments
        </h2>

        {loading ? (
          <p style={{ color: "#64748b" }}>Loading...</p>
        ) : items.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "60px 20px",
            background: "rgba(30,41,59,0.5)", borderRadius: "12px",
            border: "1px solid rgba(99,102,241,0.1)",
          }}>
            <p style={{ color: "#64748b", fontSize: "1.1rem" }}>No assignments yet</p>
            <p style={{ color: "#475569", fontSize: "0.85rem" }}>
              Your teacher will publish assignments here
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {items.map((item) => {
              const st = statusColors[item.status] || statusColors.not_started;
              return (
                <div key={item.content_id} onClick={() => item.status !== "graded" && openContent(item)} style={{
                  background: "rgba(30,41,59,0.8)", borderRadius: "12px",
                  border: "1px solid rgba(99,102,241,0.15)", padding: "16px 20px",
                  cursor: item.status === "graded" ? "default" : "pointer",
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  transition: "border-color 0.2s",
                }}>
                  <div>
                    <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 4px" }}>
                      {item.title}
                    </h3>
                    <p style={{ color: "#64748b", fontSize: "0.8rem", margin: 0 }}>
                      {item.content_type === "assessment" ? "Assessment" : "Assignment"}
                      {item.due_date ? " \u2022 Due " + new Date(item.due_date).toLocaleDateString() : ""}
                    </p>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{
                      padding: "4px 12px", borderRadius: "20px", fontSize: "0.75rem",
                      fontWeight: 600, background: st.bg, color: st.text,
                    }}>
                      {st.label}
                    </span>
                    {item.score != null && (
                      <p style={{ color: "#e2e8f0", fontSize: "0.9rem", fontWeight: 600, margin: "6px 0 0" }}>
                        {item.percentage != null ? Math.round(item.percentage) + "%" : item.score}
                        {item.letter_grade ? ` (${item.letter_grade})` : ""}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
```

### New file: `frontend/src/components/StudentApp.jsx`

```jsx
/**
 * StudentApp — Top-level router for the student portal.
 * Handles login state and renders either login or dashboard.
 */
import React, { useState, useEffect } from "react";
import StudentLogin from "./StudentLogin";
import StudentDashboard from "./StudentDashboard";

export default function StudentApp() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [studentInfo, setStudentInfo] = useState(null);
  const [classInfo, setClassInfo] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem("student_token");
    const savedStudent = localStorage.getItem("student_info");
    const savedClass = localStorage.getItem("student_class");

    if (token && savedStudent) {
      // Validate token with backend
      fetch("/api/student/session", {
        headers: { "X-Student-Token": token },
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.valid) {
            setStudentInfo(JSON.parse(savedStudent));
            setClassInfo(JSON.parse(savedClass || "{}"));
            setLoggedIn(true);
          } else {
            // Session expired — clear
            localStorage.removeItem("student_token");
            localStorage.removeItem("student_info");
            localStorage.removeItem("student_class");
          }
        })
        .catch(() => {})
        .finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  if (checking) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "#0f172a", color: "#64748b",
        fontFamily: "Inter, sans-serif",
      }}>
        Loading...
      </div>
    );
  }

  if (!loggedIn) {
    return (
      <StudentLogin
        onLogin={(data) => {
          setStudentInfo(data.student);
          setClassInfo(data.class);
          setLoggedIn(true);
        }}
      />
    );
  }

  return (
    <StudentDashboard
      studentInfo={studentInfo}
      classInfo={classInfo}
      onLogout={() => {
        setLoggedIn(false);
        setStudentInfo(null);
        setClassInfo(null);
      }}
    />
  );
}
```

---

## Phase 6: Frontend — Route Gating in App.jsx

### File: `frontend/src/App.jsx`

**Edit 1 — Add import** (after line 30):
```javascript
// OLD (line 30):
import StudentPortal from "./components/StudentPortal";

// NEW:
import StudentPortal from "./components/StudentPortal";
import StudentApp from "./components/StudentApp";
```

**Edit 2 — Add /student route** (at line 655-658):
```javascript
// OLD:
function App() {
  // Check if this is the student portal route
  if (window.location.pathname.startsWith("/join")) {
    return <StudentPortal />;
  }

// NEW:
function App() {
  // Check if this is the student portal route
  if (window.location.pathname.startsWith("/student")) {
    return <StudentApp />;
  }
  if (window.location.pathname.startsWith("/join")) {
    return <StudentPortal />;
  }
```

---

## Phase 7: Frontend — Results Tab Portal Submissions

### File: `frontend/src/App.jsx`

**Edit 1 — Add state for portal submissions** (near other state declarations, around line 700-area):
```javascript
const [portalSubmissions, setPortalSubmissions] = useState([]);
```

**Edit 2 — Add fetch for portal submissions** (inside the main useEffect or as a new effect):
```javascript
// Fetch portal submissions for Results tab
useEffect(() => {
  const loadPortalSubmissions = async () => {
    try {
      const data = await fetchApi('/api/portal-submissions');
      if (data.submissions) setPortalSubmissions(data.submissions);
    } catch (e) {
      // Silently fail — portal submissions are supplementary
    }
  };
  loadPortalSubmissions();
  // Refresh every 30 seconds
  const interval = setInterval(loadPortalSubmissions, 30000);
  return () => clearInterval(interval);
}, []);
```

**Edit 3 — Add "Portal" filter option** to the Results tab filter bar (where `resultsFilter` options are rendered, near line 8830-area). Add after the existing filter buttons:

```jsx
<button
  onClick={() => setResultsFilter("portal_pending")}
  style={{
    padding: "6px 14px", borderRadius: "8px", fontSize: "0.8rem", fontWeight: 500,
    border: "1px solid " + (resultsFilter === "portal_pending" ? "rgba(234,179,8,0.5)" : "rgba(99,102,241,0.2)"),
    background: resultsFilter === "portal_pending" ? "rgba(234,179,8,0.15)" : "rgba(30,41,59,0.5)",
    color: resultsFilter === "portal_pending" ? "#fbbf24" : "#94a3b8",
    cursor: "pointer",
  }}
>
  Portal Pending ({portalSubmissions.filter(s => s.status === "submitted").length})
</button>
```

**Edit 4 — Render portal submissions section** in the Results tab (before or after the main results table). Add a "Portal Submissions" section that shows pending submissions with student name, assignment title, submitted time, and status badge:

```jsx
{/* Portal Submissions Section */}
{portalSubmissions.length > 0 && (resultsFilter === "all" || resultsFilter === "portal_pending") && (
  <div style={{
    background: "rgba(30,41,59,0.5)", borderRadius: "12px",
    border: "1px solid rgba(234,179,8,0.15)", padding: "16px", marginBottom: "20px",
  }}>
    <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "12px", color: "#fbbf24", display: "flex", alignItems: "center", gap: "8px" }}>
      <Icon name="Inbox" size={18} /> Portal Submissions
      <span style={{ fontSize: "0.8rem", fontWeight: 400, color: "#94a3b8" }}>
        ({portalSubmissions.filter(s => s.status === "submitted").length} pending)
      </span>
    </h3>
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {portalSubmissions
        .filter(s => resultsFilter === "all" || s.status === "submitted")
        .map((sub) => (
          <div key={sub.submission_id} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "10px 14px", borderRadius: "8px",
            background: sub.status === "graded" ? "rgba(34,197,94,0.08)" : "rgba(234,179,8,0.08)",
            border: "1px solid " + (sub.status === "graded" ? "rgba(34,197,94,0.2)" : "rgba(234,179,8,0.2)"),
          }}>
            <div>
              <span style={{ fontWeight: 600, color: "#e2e8f0" }}>{sub.student_name}</span>
              <span style={{ color: "#64748b", marginLeft: "8px", fontSize: "0.85rem" }}>
                {sub.assignment} {sub.period ? "\u2022 " + sub.period : ""}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              {sub.status === "graded" ? (
                <span style={{ color: "#4ade80", fontWeight: 600 }}>
                  {sub.percentage != null ? Math.round(sub.percentage) + "%" : sub.score}
                  {sub.letter_grade ? ` (${sub.letter_grade})` : ""}
                </span>
              ) : (
                <span style={{
                  padding: "3px 10px", borderRadius: "12px", fontSize: "0.75rem",
                  fontWeight: 600, background: "rgba(234,179,8,0.2)", color: "#fbbf24",
                }}>
                  Pending
                </span>
              )}
              <span style={{ color: "#475569", fontSize: "0.75rem" }}>
                {new Date(sub.submitted_at).toLocaleString()}
              </span>
            </div>
          </div>
        ))}
    </div>
  </div>
)}
```

---

## Phase 8: API Service Functions

### File: `frontend/src/services/api.js`

Add these exports (after existing student portal functions, around line 644):

```javascript
// ============ Student Account Portal ============

export async function createClass(name, subject, gradeLevel) {
  return fetchApi('/api/classes', {
    method: 'POST',
    body: JSON.stringify({ name, subject, grade_level: gradeLevel }),
  })
}

export async function listClasses() {
  return fetchApi('/api/classes')
}

export async function syncRosterToClass(classId, periodFilename) {
  return fetchApi(`/api/classes/${classId}/sync-roster`, {
    method: 'POST',
    body: JSON.stringify({ period_filename: periodFilename }),
  })
}

export async function listClassStudents(classId) {
  return fetchApi(`/api/classes/${classId}/students`)
}

export async function publishToClass(classId, content, contentType, title, settings, dueDate) {
  return fetchApi('/api/publish-to-class', {
    method: 'POST',
    body: JSON.stringify({
      class_id: classId,
      content, content_type: contentType,
      title, settings, due_date: dueDate,
    }),
  })
}

export async function getPortalSubmissions() {
  return fetchApi('/api/portal-submissions')
}
```

Add to the exports list at the bottom of the file:
```javascript
  createClass,
  listClasses,
  syncRosterToClass,
  listClassStudents,
  publishToClass,
  getPortalSubmissions,
```

---

## Implementation Order

1. **Supabase tables** — Run SQL in Supabase dashboard
2. **`backend/routes/student_account_routes.py`** — New file, all backend logic
3. **`backend/routes/__init__.py`** — Register the new blueprint (3 small edits)
4. **`frontend/src/components/StudentLogin.jsx`** — New file
5. **`frontend/src/components/StudentDashboard.jsx`** — New file
6. **`frontend/src/components/StudentApp.jsx`** — New file (router)
7. **`frontend/src/App.jsx`** — Add import + `/student` route + portal submissions in Results tab
8. **`frontend/src/services/api.js`** — Add API functions
9. **`npm run build`** — Verify no errors

---

## Verification

1. **Build passes**: `cd frontend && npm run build`
2. **Student login flow**: Visit `/student` → enter Student ID + class code → see dashboard
3. **Backward compat**: `/join/ABC123` still works for anonymous assessments
4. **Teacher sees submissions**: Results tab shows "Portal Submissions" section with pending count
5. **Session expiry**: Student token expires after 8 hours, redirect to login
6. **Roster sync**: Teacher creates class → syncs roster → students appear in Supabase
7. **Content delivery**: Teacher publishes assessment to class → student sees it on dashboard
