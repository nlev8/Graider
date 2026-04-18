#!/usr/bin/env python3
"""
Graider - AI-Powered Assignment Grading
=======================================
Run: python3 backend/app.py
Then open: http://localhost:3000
"""

import os
import re
import sys
import json
import csv
import math
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime

import logging
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables and set up path FIRST
# (storage.py reads SUPABASE_* at import time; backend modules need root on sys.path)
_app_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_app_dir)
sys.path.insert(0, _root_dir)
load_dotenv(os.path.join(_root_dir, '.env'), override=True)

from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
import sentry_sdk

# Import student history for progress tracking
try:
    from backend.student_history import add_assignment_to_history, load_student_history, save_student_history, detect_baseline_deviation, get_baseline_summary, build_history_context
except ImportError:
    try:
        from student_history import add_assignment_to_history, load_student_history, save_student_history, detect_baseline_deviation, get_baseline_summary, build_history_context
    except ImportError:
        # Fallback if module not available
        def add_assignment_to_history(student_id, result):
            return None
        def load_student_history(student_id):
            return None
        def save_student_history(student_id, history):
            pass
        def detect_baseline_deviation(student_id, result):
            return {"flag": "normal", "reasons": [], "details": {}}
        def get_baseline_summary(student_id):
            return None
        def build_history_context(student_id):
            return ""

# Import accommodation support for IEP/504 students
try:
    from backend.accommodations import build_accommodation_prompt, load_student_accommodations, save_student_accommodations
except ImportError:
    try:
        from accommodations import build_accommodation_prompt, load_student_accommodations, save_student_accommodations
    except ImportError:
        # Fallback if module not available
        def build_accommodation_prompt(student_id):
            return ""
        def load_student_accommodations():
            return {}
        def save_student_accommodations(mappings):
            return False

# Import storage abstraction
try:
    from backend.storage import load as storage_load, save as storage_save
except ImportError:
    try:
        from backend.storage import load as storage_load, save as storage_save
    except ImportError:
        storage_load = None
        storage_save = None

app = Flask(__name__, static_folder='static', static_url_path='')

# Initialize Sentry error tracking. No-op if SENTRY_DSN is unset (local dev, CI).
from backend.observability import init_sentry
init_sentry()

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit
CORS(app, resources={r"/api/*": {"origins": [
    "https://app.graider.live",
    "https://graider.live",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]}})

# Rate limiter (shared via backend.extensions to avoid circular imports)
from backend.extensions import limiter
limiter.init_app(app)

# CSRF protection strategy:
# 1. SameSite=Lax cookies prevent cross-site POST (configured above)
# 2. CORS restricts origins to app.graider.live (configured above)
# 3. JWT Bearer tokens required on all /api/ teacher endpoints (@require_teacher)
# 4. Clever endpoints use session-based auth (@require_clever_session)
# 5. Student endpoints validate X-Student-Token header
#
# This triple-layer protection (SameSite + CORS + token auth) provides
# equivalent or stronger CSRF protection than traditional CSRF tokens
# for a JSON API. CSRF tokens are not added because the React frontend
# sends JSON via fetch() with Bearer tokens, not HTML form submissions.

_logger = logging.getLogger(__name__)


@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
    # Add CSP only on non-API responses (HTML pages)
    if not request.path.startswith('/api/'):
        supabase_url = os.getenv('SUPABASE_URL', '')
        connect_src = f"'self' {supabase_url}" if supabase_url else "'self'"
        response.headers['Content-Security-Policy'] = (
            f"default-src 'self'; "
            f"script-src 'self'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"connect-src {connect_src}; "
            f"frame-ancestors 'none'"
        )
    return response

# Fix request.host / request.remote_addr behind reverse proxy (Railway/gunicorn)
#
# x_for=2 because Railway's ingress produces a 2-hop X-Forwarded-For chain:
#   [real_client_ip, railway_edge_ip]
# and Railway rotates the edge IP per request (empirically verified
# 2026-04-18: five back-to-back requests from one client saw the last
# XFF entry vary .22 → .37 → .39 → .20 → .24). With x_for=1, ProxyFix
# would set request.remote_addr to that rotating edge IP, breaking
# flask-limiter (every request in its own bucket) and making logs
# indistinguishable across clients.
#
# x_for=2 takes XFF[-2] which is the stable real-client IP. Spoofing is
# not a concern: Railway always APPENDS the real TCP source as the
# penultimate entry (verified — a client sending "X-Forwarded-For:
# 6.6.6.6" produced "6.6.6.6, 99.77.78.219, 157.52.98.26" server-side,
# so [-2] is still the real client). If Railway ever adds a second
# proxy layer this becomes brittle and x_for must be bumped to match.
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=1, x_host=1)

# Session configuration — Redis in production, filesystem locally
is_dev = os.getenv('FLASK_ENV', '').lower() in ('development', 'dev')
_secret = os.getenv('FLASK_SECRET_KEY')
if not _secret and not is_dev:
    raise RuntimeError("FLASK_SECRET_KEY must be set in production")
app.secret_key = _secret or 'dev-secret-change-in-production'
app.config['SESSION_COOKIE_SECURE'] = not is_dev  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Session inactivity timeout
if os.getenv('REDIS_URL'):
    # Production: server-side sessions via Redis (survives multi-worker)
    from flask_session import Session
    import redis
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = True  # Use PERMANENT_SESSION_LIFETIME for expiry
    app.config['SESSION_KEY_PREFIX'] = 'graider:'
    app.config['SESSION_REDIS'] = redis.from_url(os.getenv('REDIS_URL'))
    Session(app)

# ══════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════
try:
    from backend.utils.logging_utils import configure_logging, log_request_timing
    configure_logging(app)
    log_request_timing(app)
except Exception as e:
    print(f"Warning: Logging configuration failed: {e}")

try:
    from backend.auth import init_auth
    init_auth(app)
except Exception as e:
    print(f"Warning: Auth middleware not loaded: {e}")
    sentry_sdk.capture_exception(e)

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def handle_404(e):
    # Don't return JSON for HTML pages (SPA routing)
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# Recover stale partial submissions from prior deploys (daemon threads killed on restart)
try:
    from backend.supabase_client import get_supabase as _recovery_sb
    _sb = _recovery_sb()
    if _sb:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(minutes=30)).isoformat()
        for table in ['submissions', 'student_submissions']:
            try:
                stale = _sb.table(table).select('id').eq('status', 'partial').lt('graded_at', cutoff).execute()
                if stale.data:
                    ids = [r['id'] for r in stale.data]
                    for sid in ids:
                        _sb.table(table).update({'status': 'grading_failed'}).eq('id', sid).execute()
                    print(f"Recovered {len(ids)} stale partial submissions in {table}")
            except Exception:
                pass
except Exception:
    pass

# ══════════════════════════════════════════════════════════════
# GRADING STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════

RESULTS_FILE = os.path.expanduser("~/.graider_results.json")
AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")
SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")
DOCUMENTS_DIR = os.path.expanduser("~/.graider_data/documents")

# ══════════════════════════════════════════════════════════════
# FERPA COMPLIANCE - AUDIT LOGGING
# ══════════════════════════════════════════════════════════════

from backend.utils.audit import audit_log  # noqa: E402 — extracted to avoid circular imports


def get_audit_logs(limit: int = 100):
    """Retrieve recent audit log entries."""
    if not os.path.exists(AUDIT_LOG_FILE):
        return []

    try:
        with open(AUDIT_LOG_FILE, 'r') as f:
            lines = f.readlines()
            # Return last N entries
            recent = lines[-limit:] if len(lines) > limit else lines
            logs = []
            for line in recent:
                parts = line.strip().split(' | ')
                if len(parts) >= 4:
                    logs.append({
                        'timestamp': parts[0],
                        'user': parts[1],
                        'action': parts[2],
                        'details': parts[3] if len(parts) > 3 else ''
                    })
            return logs[::-1]  # Newest first
    except Exception as e:
        print(f"Error reading audit logs: {e}")
        sentry_sdk.capture_exception(e)
        return []


# ══════════════════════════════════════════════════════════════
# SUPPORT DOCUMENTS FOR AI CONTEXT
# ══════════════════════════════════════════════════════════════

def load_support_documents_for_grading(subject: str = None) -> str:
    """
    Load relevant support documents to include in AI grading context.

    Args:
        subject: Optional subject to filter documents

    Returns:
        String with document content to include in AI prompt
    """
    if not os.path.exists(DOCUMENTS_DIR):
        return ""

    docs_content = []
    total_chars = 0
    max_chars = 8000  # Limit to avoid overwhelming the AI

    # Load metadata for all documents
    for f in os.listdir(DOCUMENTS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(DOCUMENTS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)

                doc_type = metadata.get('doc_type', 'general')
                filepath = metadata.get('filepath', '')
                description = metadata.get('description', '')

                # Prioritize rubrics and curriculum docs
                if doc_type not in ['rubric', 'curriculum', 'standards']:
                    continue

                if not os.path.exists(filepath):
                    continue

                # Read document content
                content = ""
                if filepath.endswith('.txt') or filepath.endswith('.md'):
                    with open(filepath, 'r', encoding='utf-8') as df:
                        content = df.read()
                elif filepath.endswith('.docx'):
                    try:
                        from docx import Document
                        doc = Document(filepath)
                        content = '\n'.join([p.text for p in doc.paragraphs])
                    except Exception:
                        continue
                elif filepath.endswith('.pdf'):
                    try:
                        import fitz  # PyMuPDF
                        pdf = fitz.open(filepath)
                        content = '\n'.join([page.get_text() for page in pdf])
                        pdf.close()
                    except Exception:
                        continue

                if content and total_chars + len(content) < max_chars:
                    doc_label = doc_type.upper()
                    if description:
                        doc_label += f" - {description}"
                    docs_content.append(f"[{doc_label}]\n{content[:2000]}")
                    total_chars += len(content[:2000])

            except Exception as e:
                print(f"Error loading document: {e}")
                continue

    if not docs_content:
        return ""

    return "\n".join([
        "",
        "═══════════════════════════════════════════════════════════",
        "REFERENCE DOCUMENTS (Use these to inform your grading):",
        "═══════════════════════════════════════════════════════════",
        "",
        *docs_content,
        "",
        "═══════════════════════════════════════════════════════════",
        ""
    ])


def _sanitize_student_name(name):
    """Fix student names that contain assignment titles from bad filename parsing.

    Examples of corrupted names:
      'Berriozabal, Daniel 📓 CORNELL NOTES Chapter 10 – Section 2'
      'Deloach, Rylee M. 📓 CORNELL NOTES Chapter 10 – Section 2'

    Returns the cleaned student name.
    """
    if not name:
        return name
    # Strip at emoji boundary (📓 etc.) — emoji never appears in real student names
    emoji_pattern = re.compile(
        r'[\U0001F300-\U0001F9FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F'
        r'\U0000200D\U00002600-\U000026FF\U00002B50]'
    )
    match = emoji_pattern.search(name)
    if match:
        name = name[:match.start()].strip()
    # Strip common assignment title patterns that got appended to names
    assignment_markers = [
        ' CORNELL NOTES', ' Cornell Notes', ' cornell notes',
        ' Chapter ', ' chapter ',
        ' Section ', ' section ',
        ' Unit ', ' unit ',
    ]
    for marker in assignment_markers:
        idx = name.find(marker)
        if idx > 0:
            name = name[:idx].strip()
    # Remove trailing punctuation left over from stripping (preserve periods for initials like "M.")
    name = name.rstrip(' ,;:-–—')
    return name


# Grading state + thread live in backend/grading/ (Phase 3a).
# app.py imports only the names it uses directly:
#   - init_app() passes _get_state, run_grading_thread, reset_state, _get_lock
#     to register_routes(...)
#   - _handle_sigterm walks _grading_states to stop running grading threads
from backend.grading.state import _get_state, _get_lock, reset_state, _grading_states, _states_meta_lock
from backend.grading.thread import run_grading_thread


# ══════════════════════════════════════════════════════════════
# POST-BATCH CALIBRATION
# ══════════════════════════════════════════════════════════════
# _check_batch_calibration moved to backend/grading/pipeline.py in PR3.
# Only caller was _run_grading_thread_inner (also moved).


# ══════════════════════════════════════════════════════════════
# GRADING THREAD
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN — Stop grading threads on SIGTERM
# ══════════════════════════════════════════════════════════════

import signal
from backend.routes import register_routes

def _handle_sigterm(signum, frame):
    """Graceful shutdown: stop any running grading thread before exit.

    Snapshots _grading_states under _states_meta_lock before iterating —
    _get_state() mutates the dict under the same lock, so iterating the
    raw dict while a concurrent submission creates a new teacher entry
    would raise ``RuntimeError: dictionary changed size during iteration``
    and abort shutdown partway through.
    """
    _logger.info("SIGTERM received — requesting grading thread stop")
    with _states_meta_lock:
        snapshot = list(_grading_states.items())
    for teacher_id, state in snapshot:
        if state.get("is_running"):
            state["stop_requested"] = True
            _logger.info("  Requested stop for teacher %s", teacher_id)
    # Let gunicorn handle the actual process exit


def init_app(app):
    """Imperative initialization wiring for the Flask app.

    Idempotent: a second call is a no-op. Flask raises
    ``AssertionError: View function mapping is overwriting...`` if
    ``register_routes`` runs twice on the same app, so the guard prevents
    subtle breakage if any future caller invokes init_app again (e.g., a
    test fixture that re-wires an existing app instead of building fresh).
    """
    if getattr(app, '_graider_initialized', False):
        return
    register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    app._graider_initialized = True


# Call initializer at the original register_routes/SIGTERM location
# (mid-file, before remaining module-level @app.route decorators) so
# module-level side-effect ordering is preserved exactly as main.
init_app(app)


# ══════════════════════════════════════════════════════════════
# INDIVIDUAL FILE GRADING (for paper/handwritten assignments)
# ══════════════════════════════════════════════════════════════

@app.route('/api/grade-individual', methods=['POST'])
@limiter.limit("5 per minute")
@require_teacher
@handle_route_errors
def grade_individual():
    """Grade a single uploaded image file (for paper/handwritten assignments).

    Automatically uses GPT-4o for better handwriting recognition.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    student_name = request.form.get('student_name', 'Unknown Student')
    grade_level = request.form.get('grade_level', '7')
    subject = request.form.get('subject', 'Social Studies')
    output_folder = request.form.get('output_folder', '')
    global_ai_notes = request.form.get('globalAINotes', '')
    assignment_config_str = request.form.get('assignmentConfig', '')
    student_info_str = request.form.get('studentInfo', '')
    teacher_name = request.form.get('teacher_name', '')
    school_name = request.form.get('school_name', '')
    class_period = request.form.get('classPeriod', '')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Parse student info from CSV if provided
    student_info = None
    if student_info_str:
        try:
            student_info = json.loads(student_info_str)
        except Exception:
            pass

    # Parse assignment config if provided
    assignment_config = None
    if assignment_config_str:
        try:
            assignment_config = json.loads(assignment_config_str)
        except Exception:
            pass

    # Build AI notes from config
    file_ai_notes = global_ai_notes or ''
    assignment_template = ''
    file_exclude_markers = []
    if class_period:
        file_ai_notes += f"\nCLASS PERIOD BEING GRADED: {class_period}\n(Apply any period-specific grading expectations from the instructions above)\n"
    if assignment_config:
        if assignment_config.get('gradingNotes'):
            file_ai_notes = assignment_config['gradingNotes'] + '\n\n' + file_ai_notes
        # Get assignment template for question context
        imported_doc = assignment_config.get('importedDoc') or {}
        assignment_template = imported_doc.get('text', '')
        # Get exclude markers
        file_exclude_markers = assignment_config.get('excludeMarkers', [])

    try:
        import base64

        # Read file content
        file_content = file.read()
        file_ext = os.path.splitext(file.filename)[1].lower()

        # Determine media type
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.heif': 'image/heif',
        }
        media_type = media_type_map.get(file_ext, 'image/jpeg')

        # Encode as base64
        base64_content = base64.b64encode(file_content).decode('utf-8')

        # Create grade data for image
        grade_data = {
            "type": "image",
            "content": base64_content,
            "media_type": media_type
        }

        # ALWAYS use GPT-4o for images (better handwriting recognition)
        ai_model = 'gpt-4o'

        # Get student ID for history tracking
        individual_student_id = student_info.get('id', '') if student_info else None

        # Build student history context (passed separately to feedback)
        history_context = ""
        if individual_student_id:
            history_context = build_history_context(individual_student_id)

        # Grade the assignment (no custom rubric for individual grading yet)
        # Pass None for marker_config and 15 for effort_points (defaults)
        grade_result = grade_with_parallel_detection(student_name, grade_data, file_ai_notes, grade_level, subject, ai_model, individual_student_id, assignment_template, None, None, file_exclude_markers, None, 15, student_history=history_context)

        if grade_result.get('letter_grade') == 'ERROR':
            return jsonify({"error": grade_result.get('feedback', 'Grading failed')}), 500

        # Save original image to output folder
        original_image_path = None
        if output_folder and os.path.exists(output_folder):
            safe_name = student_name.replace(' ', '_').replace('/', '_')
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Save the original image
            image_filename = f"{safe_name}_handwritten_{timestamp_str}{file_ext}"
            original_image_path = os.path.join(output_folder, image_filename)
            with open(original_image_path, 'wb') as img_file:
                img_file.write(file_content)

        # Build result object (matching regular grading structure)
        result = {
            "student_name": student_name,
            "filename": file.filename,
            "assignment": assignment_config.get('title', 'Individual Upload') if assignment_config else 'Individual Upload',
            "score": int(float(grade_result.get('score', 0) or 0)),
            "letter_grade": grade_result.get('letter_grade', 'N/A'),
            "feedback": grade_result.get('feedback', ''),
            "breakdown": grade_result.get('breakdown', {}),
            "ai_detection": grade_result.get('ai_detection', {}),
            "plagiarism_detection": grade_result.get('plagiarism_detection', {}),
            "student_responses": grade_result.get('student_responses', []),
            "excellent_answers": grade_result.get('excellent_answers', []),
            "needs_improvement": grade_result.get('needs_improvement', []),
            "unanswered_questions": grade_result.get('unanswered_questions', []),
            "timestamp": datetime.now().isoformat(),
            "model_used": ai_model,
            # Handwritten/image-specific fields
            "is_handwritten": True,
            "original_image_path": original_image_path,
            # Student info from CSV (if matched)
            "student_id": student_info.get('id', '') if student_info else '',
            "student_email": student_info.get('email', '') if student_info else '',
            # Teacher/school info
            "teacher_name": teacher_name,
            "school_name": school_name,
        }

        # Save result JSON to output folder if specified
        if output_folder and os.path.exists(output_folder):
            result_filename = f"{safe_name}_individual_{timestamp_str}.json"
            result_path = os.path.join(output_folder, result_filename)
            with open(result_path, 'w') as f:
                json.dump(result, f, indent=2)

        # Save to student history for progress tracking
        if result.get('student_id'):
            try:
                add_assignment_to_history(result['student_id'], result)
            except Exception as e:
                print(f"  Note: Could not update student history: {e}")
                sentry_sdk.capture_exception(e)

        # FERPA audit log
        audit_log("GRADE_INDIVIDUAL", f"Graded individual upload for student (image-based, GPT-4o)")

        return jsonify(result)

    except Exception as e:
        _logger.exception("Individual grading error")
        return jsonify({"error": "An internal error occurred"}), 500


def _remove_from_master_csv(result):
    """Remove a deleted result from master_grades.csv so the Assistant sees fresh data."""
    import re
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    master_file = os.path.join(output_folder, "master_grades.csv")
    if not os.path.exists(master_file):
        return

    student_id = str(result.get('student_id', ''))
    assignment = result.get('assignment', '')
    if not student_id or not assignment:
        return

    def normalize(name):
        n = name.strip()
        n = re.sub(r'\s*\(\d+\)\s*$', '', n)
        n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
        return n.strip().lower()

    def matches(csv_assign, target):
        csv_norm = normalize(csv_assign)
        target_norm = normalize(target)
        if csv_norm == target_norm:
            return True
        if len(csv_norm) >= 20 and target_norm.startswith(csv_norm):
            return True
        if len(target_norm) >= 20 and csv_norm.startswith(target_norm):
            return True
        return False

    try:
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            rows = list(reader)

        filtered = [row for row in rows
                     if not (row.get('Student ID', '') == student_id
                             and matches(row.get('Assignment', ''), assignment))]

        if len(filtered) < len(rows):
            with open(master_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(filtered)
    except Exception as e:
        print(f"Could not remove from master_grades.csv: {e}")
        sentry_sdk.capture_exception(e)


def _sync_approval_to_master_csv(result, approval_status):
    """Update the Approved column in master_grades.csv for a specific result."""
    import re
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    master_file = os.path.join(output_folder, "master_grades.csv")
    if not os.path.exists(master_file):
        return

    student_id = str(result.get('student_id', ''))
    assignment = result.get('assignment', '')
    if not student_id or not assignment:
        return

    def normalize(name):
        n = name.strip()
        n = re.sub(r'\s*\(\d+\)\s*$', '', n)
        n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
        return n.strip().lower()

    try:
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            rows = list(reader)

        # Add Approved column if missing (legacy CSV)
        if 'Approved' not in header:
            feedback_idx = header.index('Feedback') if 'Feedback' in header else -1
            if feedback_idx >= 0:
                header.insert(feedback_idx + 1, 'Approved')
            else:
                header.append('Approved')
            for row in rows:
                row['Approved'] = ''

        updated = False
        target_norm = normalize(assignment)
        for row in rows:
            row_sid = row.get('Student ID', '')
            row_assign_norm = normalize(row.get('Assignment', ''))
            if row_sid == student_id and row_assign_norm == target_norm:
                row['Approved'] = approval_status
                updated = True

        if updated:
            with open(master_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
    except Exception as e:
        print(f"Could not sync approval to master_grades.csv: {e}")
        sentry_sdk.capture_exception(e)


# ══════════════════════════════════════════════════════════════
# DELETE SINGLE RESULT
# ══════════════════════════════════════════════════════════════

@app.route('/api/delete-result', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_single_result():
    """Delete a single grading result by filename."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot delete results while grading is in progress"}), 400

    data = request.json
    filename = data.get('filename', '')

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Find the result before removing (need student_id + assignment for master CSV sync)
    deleted_result = None
    for r in grading_state["results"]:
        if r.get('filename', '') == filename:
            deleted_result = r
            break

    original_count = len(grading_state["results"])
    grading_state["results"] = [
        r for r in grading_state["results"]
        if r.get('filename', '') != filename
    ]

    # If result wasn't found, that's OK - it's already deleted
    if len(grading_state["results"]) == original_count:
        return jsonify({"status": "already_deleted", "filename": filename})

    # Save updated results to storage
    save_results(grading_state["results"], teacher_id)

    # Also remove from master_grades.csv so the Assistant sees fresh data
    if deleted_result:
        _remove_from_master_csv(deleted_result)

    # FERPA: Audit log the deletion
    audit_log("DELETE_RESULT", f"Deleted result for file: {filename[:30]}...")

    return jsonify({
        "status": "deleted",
        "filename": filename,
        "remaining_count": len(grading_state["results"])
    })


@app.route('/api/update-approval', methods=['POST'])
@require_teacher
@handle_route_errors
def update_approval():
    """Update email approval status for a result."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    data = request.json
    filename = data.get('filename')
    approval = data.get('approval')  # 'approved', 'rejected', or 'pending'
    graded_at = data.get('graded_at')  # optional — disambiguate duplicates

    if not filename:
        return jsonify({"error": "Missing filename"}), 400

    # Find and update the result (prefer exact match on graded_at for duplicates)
    target = None
    for r in grading_state["results"]:
        if r.get('filename') == filename:
            if graded_at and r.get('graded_at') == graded_at:
                target = r
                break  # exact match
            if target is None:
                target = r  # fallback to first match

    if target:
        target['email_approval'] = approval
        save_results(grading_state["results"], teacher_id)
        _sync_approval_to_master_csv(target, approval)
        return jsonify({"status": "updated", "filename": filename, "approval": approval})

    return jsonify({"error": "Result not found"}), 404


@app.route('/api/update-approvals-bulk', methods=['POST'])
@require_teacher
@handle_route_errors
def update_approvals_bulk():
    """Update email approval status for multiple results at once."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    data = request.json
    approvals = data.get('approvals', {})  # { filename: approval_status }

    if not approvals:
        return jsonify({"error": "No approvals provided"}), 400

    updated = 0
    for r in grading_state["results"]:
        filename = r.get('filename')
        if filename in approvals:
            r['email_approval'] = approvals[filename]
            _sync_approval_to_master_csv(r, approvals[filename])
            updated += 1

    if updated > 0:
        save_results(grading_state["results"], teacher_id)

    return jsonify({"status": "updated", "count": updated})


# ══════════════════════════════════════════════════════════════
# FERPA COMPLIANCE - DATA MANAGEMENT
# ══════════════════════════════════════════════════════════════

@app.route('/api/ferpa/delete-all-data', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_all_student_data():
    """
    FERPA Compliance: Securely delete all student data.
    This includes grading results, settings, and cached data.
    """
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot delete data while grading is in progress"}), 400

    data = request.json or {}
    confirm = data.get('confirm', False)

    if not confirm:
        return jsonify({
            "error": "Confirmation required",
            "message": "Send {confirm: true} to proceed with deletion"
        }), 400

    deleted_items = []

    try:
        # Delete grading results
        if os.path.exists(RESULTS_FILE):
            result_count = len(grading_state.get("results", []))
            os.remove(RESULTS_FILE)
            deleted_items.append(f"Grading results ({result_count} records)")

        # Clear in-memory results
        grading_state["results"] = []
        grading_state["log"] = []
        grading_state["progress"] = 0
        grading_state["total"] = 0
        grading_state["complete"] = False

        # Delete settings (optional - based on request)
        if data.get('include_settings', False) and os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
            deleted_items.append("Settings")

        # Audit log the deletion (this is kept for compliance)
        audit_log("DELETE_ALL_DATA", f"Deleted: {', '.join(deleted_items)}")

        return jsonify({
            "status": "success",
            "message": "All student data has been securely deleted",
            "deleted": deleted_items,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        _logger.exception("Failed to delete all student data")
        audit_log("DELETE_ALL_DATA_ERROR", "internal error")
        return jsonify({"error": "An internal error occurred"}), 500


@app.route('/api/ferpa/audit-log', methods=['GET'])
@require_teacher
@handle_route_errors
def get_audit_log():
    """
    FERPA Compliance: Retrieve audit log entries.
    Shows who accessed what data and when.
    """
    limit = request.args.get('limit', 100, type=int)
    logs = get_audit_logs(limit)

    return jsonify({
        "logs": logs,
        "total": len(logs),
        "file": AUDIT_LOG_FILE
    })


@app.route('/api/ferpa/data-summary', methods=['GET'])
@require_teacher
@handle_route_errors
def get_data_summary():
    """
    FERPA Compliance: Get summary of stored student data.
    Helps teachers understand what data is stored locally.
    """
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)
    summary = {
        "results": {
            "count": len(grading_state.get("results", [])),
            "file": RESULTS_FILE,
            "exists": os.path.exists(RESULTS_FILE)
        },
        "settings": {
            "file": SETTINGS_FILE,
            "exists": os.path.exists(SETTINGS_FILE)
        },
        "audit_log": {
            "file": AUDIT_LOG_FILE,
            "exists": os.path.exists(AUDIT_LOG_FILE)
        },
        "data_locations": [
            "~/.graider_results.json - Grading results",
            "~/.graider_settings.json - App settings",
            "~/.graider_audit.log - Audit trail",
            "Output folder (configured in settings) - Exported grades"
        ],
        "ferpa_notes": {
            "pii_handling": "Student names are sanitized before AI processing",
            "data_storage": "All data stored locally on teacher's computer",
            "ai_training": "OpenAI API does not train on API-submitted data",
            "deletion": "Use DELETE /api/ferpa/delete-all-data to remove all data"
        }
    }

    # Audit log access to data summary
    audit_log("VIEW_DATA_SUMMARY", "Teacher viewed data storage summary")

    return jsonify(summary)


@app.route('/api/ferpa/export-data', methods=['GET'])
@require_teacher
@handle_route_errors
def export_student_data():
    """
    FERPA Compliance: Export all student data for portability.
    Supports parent/guardian data requests.
    """
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)
    student_name = request.args.get('student', '')

    if student_name:
        # Export specific student's data
        student_results = [
            r for r in grading_state.get("results", [])
            if r.get("student_name", "").lower() == student_name.lower()
        ]
        audit_log("EXPORT_STUDENT_DATA", f"Exported data for student (name redacted)")
    else:
        # Export all data
        student_results = grading_state.get("results", [])
        audit_log("EXPORT_ALL_DATA", f"Exported all {len(student_results)} records")

    return jsonify({
        "export_date": datetime.now().isoformat(),
        "record_count": len(student_results),
        "data": student_results
    })


@app.route('/api/ferpa/export-student', methods=['POST'])
@require_teacher
@handle_route_errors
def export_individual_student_data():
    """
    FERPA Compliance: Export all stored data for a specific student.
    Generates JSON (raw data) + PDF (formatted report) saved to ~/.graider_exports/student/.
    """
    import re
    import subprocess

    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    data = request.json or {}
    student_name = data.get('student_name', '').strip()
    if not student_name:
        return jsonify({"error": "student_name is required"}), 400

    # --- fuzzy match helper (inline, mirrors assistant_tools) ---
    def _fuzzy(search, full_name):
        clean = lambda s: re.sub(r'[,;.\'"]+', ' ', s.lower()).split()
        sw = clean(search)
        nw = clean(full_name)
        if not sw:
            return False
        return all(any(n.startswith(s) or s.startswith(n) for n in nw) for s in sw)

    # --- locate student across roster CSVs ---
    periods_dir = os.path.expanduser("~/.graider_data/periods")
    matched_name = None
    matched_id = None
    matched_period = None
    matched_email = None

    if os.path.isdir(periods_dir):
        for fname in sorted(os.listdir(periods_dir)):
            if not fname.endswith('.csv'):
                continue
            meta_path = os.path.join(periods_dir, fname + '.meta.json')
            period_label = fname.replace('.csv', '').replace('_', ' ')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as mf:
                        meta = json.load(mf)
                    period_label = meta.get('period_name', period_label)
                except Exception:
                    pass
            try:
                with open(os.path.join(periods_dir, fname), 'r', encoding='utf-8') as pf:
                    reader = csv.DictReader(pf)
                    for row in reader:
                        raw = row.get('Student', '').strip().strip('"')
                        # Parse "Last; First" or "Last, First"
                        display = raw
                        if '; ' in raw:
                            parts = raw.split('; ', 1)
                            display = (parts[1].strip() + ' ' + parts[0].strip()).strip()
                        elif ', ' in raw:
                            parts = raw.split(', ', 1)
                            display = (parts[1].strip() + ' ' + parts[0].strip()).strip()
                        if _fuzzy(student_name, display) or _fuzzy(student_name, raw):
                            matched_name = display
                            matched_id = row.get('Student ID', row.get('student_id', row.get('ID', '')))
                            matched_email = row.get('Email', row.get('email', ''))
                            matched_period = period_label
                            break
            except Exception:
                continue
            if matched_name:
                break

    # Also try matching from grading results if roster didn't match
    if not matched_name:
        for r in grading_state.get("results", []):
            rn = r.get("student_name", "")
            if _fuzzy(student_name, rn):
                matched_name = rn
                matched_id = r.get("student_id", "")
                matched_period = r.get("period", "")
                matched_email = r.get("student_email", "")
                break

    if not matched_name:
        return jsonify({
            "error": f"No student found matching '{student_name}'.",
            "hint": "Try the student's full name as it appears on the roster."
        }), 404

    safe_id = matched_id or re.sub(r'[^\w]', '_', matched_name.lower())

    # --- collect data from all sources ---
    export = {
        "export_date": datetime.now().isoformat(),
        "student_name": matched_name,
        "student_id": matched_id or "",
        "period": matched_period or "",
        "email": matched_email or "",
    }

    # 1. Grading results
    student_results = [
        r for r in grading_state.get("results", [])
        if _fuzzy(student_name, r.get("student_name", ""))
    ]
    export["grading_results"] = student_results

    # 2. Student history
    history = load_student_history(safe_id) if safe_id else None
    export["student_history"] = history

    # 3. Accommodations
    accomm_file = os.path.expanduser("~/.graider_data/accommodations/student_accommodations.json")
    student_accommodations = None
    if os.path.exists(accomm_file):
        try:
            with open(accomm_file, 'r') as f:
                all_acc = json.load(f)
            student_accommodations = all_acc.get(safe_id) or all_acc.get(matched_id or '')
        except Exception as e:
            sentry_sdk.capture_exception(e)
    export["accommodations"] = student_accommodations

    # 4. ELL data
    ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
    ell_data = None
    if os.path.exists(ell_file):
        try:
            with open(ell_file, 'r') as f:
                all_ell = json.load(f)
            ell_data = all_ell.get(safe_id) or all_ell.get(matched_id or '')
        except Exception as e:
            sentry_sdk.capture_exception(e)
    export["ell_data"] = ell_data

    # 5. Parent contacts
    contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
    parent_contacts = None
    if os.path.exists(contacts_file):
        try:
            with open(contacts_file, 'r') as f:
                all_contacts = json.load(f)
            parent_contacts = all_contacts.get(safe_id) or all_contacts.get(matched_id or '')
        except Exception as e:
            sentry_sdk.capture_exception(e)
    export["parent_contacts"] = parent_contacts

    record_count = len(student_results) + (1 if history else 0) + (1 if student_accommodations else 0) + (1 if ell_data else 0) + (1 if parent_contacts else 0)

    # --- save JSON ---
    export_dir = os.path.expanduser("~/.graider_exports/student")
    os.makedirs(export_dir, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    safe_fname = re.sub(r'[^\w\s-]', '', matched_name).strip().replace(' ', '_')
    json_path = os.path.join(export_dir, f"{safe_fname}_data_{date_str}.json")
    with open(json_path, 'w') as f:
        json.dump(export, f, indent=2, default=str)

    # --- generate PDF ---
    pdf_path = os.path.join(export_dir, f"{safe_fname}_report_{date_str}.pdf")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors as rl_colors

        doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('ExportTitle', parent=styles['Title'], fontSize=18, spaceAfter=6)
        subtitle_style = ParagraphStyle('ExportSub', parent=styles['Normal'], fontSize=10, textColor=rl_colors.grey, spaceAfter=12)
        section_style = ParagraphStyle('ExportSection', parent=styles['Heading2'], fontSize=13, spaceBefore=16, spaceAfter=6)
        body_style = ParagraphStyle('ExportBody', parent=styles['Normal'], fontSize=9, leading=12)

        elements = []

        # Header
        elements.append(Paragraph(f"Student Data Report: {matched_name}", title_style))
        header_parts = [f"Exported {date_str}"]
        if matched_id:
            header_parts.append(f"ID: {matched_id}")
        if matched_period:
            header_parts.append(f"Period: {matched_period}")
        elements.append(Paragraph(" | ".join(header_parts), subtitle_style))
        elements.append(Spacer(1, 12))

        # Scores table
        if student_results:
            elements.append(Paragraph("Assignment Scores", section_style))
            table_data = [["Date", "Assignment", "Score", "Grade"]]
            for r in sorted(student_results, key=lambda x: x.get('graded_at', '')):
                table_data.append([
                    (r.get('graded_at') or '')[:10],
                    (r.get('assignment') or r.get('filename', ''))[:40],
                    str(r.get('score', '')),
                    r.get('letter_grade', ''),
                ])
            t = Table(table_data, colWidths=[1*inch, 3.5*inch, 0.8*inch, 0.7*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#4f46e5')),
                ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.lightgrey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f5f5f5')]),
            ]))
            elements.append(t)

        # Skill patterns (from history)
        if history and history.get('skill_scores'):
            elements.append(Paragraph("Skill Patterns", section_style))
            skills = history['skill_scores']
            for skill, val in skills.items():
                avg = val if isinstance(val, (int, float)) else val.get('average', 'N/A') if isinstance(val, dict) else 'N/A'
                elements.append(Paragraph(f"<b>{skill.replace('_', ' ').title()}:</b> {avg}", body_style))

        # Accommodations
        if student_accommodations:
            elements.append(Paragraph("Accommodations (IEP/504)", section_style))
            presets = student_accommodations.get('presets', [])
            if presets:
                elements.append(Paragraph("Presets: " + ", ".join(p.replace('_', ' ').title() for p in presets), body_style))
            notes = student_accommodations.get('custom_notes') or student_accommodations.get('notes', '')
            if notes:
                elements.append(Paragraph(f"Notes: {notes}", body_style))

        # ELL
        if ell_data:
            elements.append(Paragraph("ELL Information", section_style))
            lang = ell_data.get('language', '') if isinstance(ell_data, dict) else str(ell_data)
            elements.append(Paragraph(f"Language: {lang}", body_style))

        # Recent feedback (last 3)
        feedback_results = [r for r in student_results if r.get('feedback')]
        if feedback_results:
            elements.append(Paragraph("Recent Feedback", section_style))
            for r in feedback_results[-3:]:
                assign = r.get('assignment') or r.get('filename', '')
                fb = r.get('feedback', '')[:500]
                elements.append(Paragraph(f"<b>{assign}:</b>", body_style))
                elements.append(Paragraph(fb, body_style))
                elements.append(Spacer(1, 6))

        doc.build(elements)
    except Exception as e:
        pdf_path = None
        sentry_sdk.capture_exception(e)
        print(f"PDF generation error: {e}")

    # Open folder (macOS local dev only)
    if sys.platform == 'darwin':
        try:
            subprocess.run(['open', export_dir], check=False)
        except Exception:
            pass

    audit_log("EXPORT_STUDENT_DATA", f"Exported full data for student (name redacted), {record_count} records")

    return jsonify({
        "status": "success",
        "student_name": matched_name,
        "student_id": matched_id or "",
        "record_count": record_count,
        "json_path": json_path,
        "pdf_path": pdf_path,
    })


@app.route('/api/ferpa/import-student', methods=['POST'])
@require_teacher
@handle_route_errors
def import_individual_student_data():
    """FERPA-compliant: Import a previously exported student data file."""
    import re as _re

    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    preview = request.form.get('preview', 'false').lower() == 'true'
    period_filename = request.form.get('period_filename', '')
    student_id_override = request.form.get('student_id', '')

    # Get uploaded file
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if not file.filename or not file.filename.endswith('.json'):
        return jsonify({"error": "File must be a .json file"}), 400

    try:
        data = json.loads(file.read().decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _logger.exception("Invalid JSON file uploaded")
        return jsonify({"error": "Invalid JSON file"}), 400

    # Validate required fields
    student_name = data.get('student_name')
    if not student_name:
        return jsonify({"error": "Missing 'student_name' in export file. This may not be a Graider export."}), 400

    has_data = any(data.get(k) for k in ('grading_results', 'student_history', 'accommodations', 'ell_data', 'parent_contacts'))
    if not has_data:
        return jsonify({"error": "Export file contains no importable data sections."}), 400

    original_id = data.get('student_id', '')
    original_period = data.get('period', '')
    student_id = student_id_override or original_id or _re.sub(r'[^\w]', '_', student_name.lower())

    grading_results = data.get('grading_results') or []
    student_history = data.get('student_history')
    accommodations = data.get('accommodations')
    ell_data = data.get('ell_data')
    parent_contacts = data.get('parent_contacts')

    # Build preview summary
    summary = {
        "student_name": student_name,
        "original_period": original_period,
        "original_id": original_id,
        "sections": {
            "results": len(grading_results),
            "history": bool(student_history),
            "accommodations": bool(accommodations),
            "ell": bool(ell_data),
            "contacts": bool(parent_contacts),
        },
    }

    # Add human-readable details for preview
    details = []
    if grading_results:
        details.append(f"{len(grading_results)} grades")
    if student_history:
        details.append("history")
    if accommodations:
        presets = accommodations.get('presets', [])
        if presets:
            details.append(f"IEP accommodations ({', '.join(p.replace('_', ' ') for p in presets[:3])})")
        else:
            details.append("accommodations")
    if ell_data:
        lang = ell_data.get('language', '') if isinstance(ell_data, dict) else str(ell_data)
        details.append(f"ELL ({lang})" if lang and lang != 'none' else "ELL")
    if parent_contacts:
        details.append("parent contacts")
    summary["detail_text"] = ", ".join(details) if details else "no data"

    if preview:
        return jsonify({"status": "preview", **summary})

    # ── Import mode ──────────────────────────────────────────
    imported = {"results": 0, "history": False, "accommodations": False, "ell": False, "contacts": False}

    # 1. Grading results — append, deduplicate by graded_at timestamp
    if grading_results:
        existing_timestamps = set()
        for r in grading_state.get("results", []):
            ts = r.get("graded_at", "")
            nm = r.get("student_name", "")
            if nm.lower() == student_name.lower() and ts:
                existing_timestamps.add(ts)

        new_results = []
        for r in grading_results:
            # Update period/ID if overrides provided
            if student_id_override:
                r["student_id"] = student_id_override
            if period_filename:
                r["period"] = period_filename.replace('.csv', '').replace('_', ' ')
            # Deduplicate by timestamp
            if r.get("graded_at") and r["graded_at"] in existing_timestamps:
                continue
            new_results.append(r)

        if new_results:
            grading_state["results"].extend(new_results)
            save_results(grading_state["results"], teacher_id)
            imported["results"] = len(new_results)

    # 2. Student history — merge assignments lists
    if student_history:
        existing_history = load_student_history(student_id)
        if existing_history and existing_history.get("assignments"):
            # Merge: add assignments not already present (by date + assignment name)
            existing_keys = set()
            for a in existing_history.get("assignments", []):
                existing_keys.add((a.get("date", ""), a.get("assignment", "")))
            for a in student_history.get("assignments", []):
                key = (a.get("date", ""), a.get("assignment", ""))
                if key not in existing_keys:
                    existing_history["assignments"].append(a)
            # Merge skill_scores — keep existing, add new
            for skill, val in student_history.get("skill_scores", {}).items():
                if skill not in existing_history.get("skill_scores", {}):
                    existing_history.setdefault("skill_scores", {})[skill] = val
            save_student_history(student_id, existing_history)
        else:
            # No existing history — save the imported one with updated ID
            student_history["student_id"] = student_id
            save_student_history(student_id, student_history)
        imported["history"] = True

    # 3. Accommodations
    if accommodations:
        tid = getattr(g, 'user_id', 'local-dev')
        all_acc = load_student_accommodations(tid)
        all_acc[student_id] = accommodations
        all_acc[student_id]["updated"] = datetime.now().isoformat()
        save_student_accommodations(all_acc, tid)
        imported["accommodations"] = True

    # 4. ELL data
    if ell_data:
        ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
        all_ell = {}
        if os.path.exists(ell_file):
            try:
                with open(ell_file, 'r') as f:
                    all_ell = json.load(f)
            except Exception as e:
                sentry_sdk.capture_exception(e)
        all_ell[student_id] = ell_data
        os.makedirs(os.path.dirname(ell_file), exist_ok=True)
        with open(ell_file, 'w') as f:
            json.dump(all_ell, f, indent=2)
        imported["ell"] = True

    # 5. Parent contacts
    if parent_contacts:
        contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
        all_contacts = {}
        if os.path.exists(contacts_file):
            try:
                with open(contacts_file, 'r') as f:
                    all_contacts = json.load(f)
            except Exception as e:
                sentry_sdk.capture_exception(e)
        all_contacts[student_id] = parent_contacts
        os.makedirs(os.path.dirname(contacts_file), exist_ok=True)
        with open(contacts_file, 'w') as f:
            json.dump(all_contacts, f, indent=2)
        imported["contacts"] = True

    # 6. Roster — add student to period CSV if specified
    if period_filename:
        try:
            periods_dir = os.path.expanduser("~/.graider_data/periods")
            csv_path = os.path.join(periods_dir, period_filename)
            if os.path.exists(csv_path):
                # Read existing rows to avoid duplicate
                existing_names = set()
                with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    rows = list(reader)
                    for row in rows:
                        existing_names.add(row.get("student_name", "").lower())

                if student_name.lower() not in existing_names:
                    new_row = {"student_name": student_name}
                    if "student_id" in fieldnames:
                        new_row["student_id"] = student_id
                    if "email" in fieldnames:
                        new_row["email"] = data.get("email", "")
                    rows.append(new_row)
                    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
        except Exception as e:
            print(f"Warning: Could not add student to roster: {e}")
            sentry_sdk.capture_exception(e)

    audit_log("IMPORT_STUDENT_DATA", f"Imported data for student (name redacted), sections: {imported}")

    return jsonify({
        "status": "success",
        "student_name": student_name,
        "student_id": student_id,
        "imported_sections": imported,
    })


# ══════════════════════════════════════════════════════════════
# STUDENT PROGRESS HISTORY
# ══════════════════════════════════════════════════════════════

@app.route('/api/student-history/<student_id>', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_history_api(student_id):
    """Get a student's grading history and progress patterns."""
    history = load_student_history(student_id)
    if not history:
        return jsonify({"error": "No history found"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_HISTORY", f"Viewed history for student ID: {student_id[:6]}...")

    return jsonify(history)


@app.route('/api/student-baseline/<student_id>', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_baseline_api(student_id):
    """Get a student's baseline performance metrics for deviation detection."""
    baseline = get_baseline_summary(student_id)
    if not baseline:
        return jsonify({"error": "Insufficient history for baseline (need 3+ assignments)"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_BASELINE", f"Viewed baseline for student ID: {student_id[:6]}...")

    return jsonify(baseline)


@app.route('/api/retranslate-feedback', methods=['POST'])
@require_teacher
@handle_route_errors
def retranslate_feedback():
    """Re-translate English feedback to the target language."""
    import openai

    data = request.json
    english_feedback = data.get('english_feedback', '')
    target_language = data.get('target_language', 'spanish')

    if not english_feedback:
        return jsonify({"error": "No feedback provided"})

    try:
        from backend.api_keys import get_api_key
        client = openai.OpenAI(api_key=get_api_key('openai', getattr(g, 'user_id', 'local-dev')))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Translate the following teacher feedback to {target_language}. Keep the same warm, encouraging tone. Only output the translation, nothing else.\n\nFeedback:\n{english_feedback}"
            }],
            temperature=0.3
        )

        translation = response.choices[0].message.content.strip()
        return jsonify({"translation": translation})

    except Exception as e:
        _logger.exception("Failed to translate feedback")
        return jsonify({"error": "An internal error occurred"}), 500


# ══════════════════════════════════════════════════════════════
# ROSTER MANAGEMENT - Add student from screenshot
# ══════════════════════════════════════════════════════════════

@app.route('/api/extract-student-from-image', methods=['POST'])
@require_teacher
@handle_route_errors
def extract_student_from_image():
    """Use Claude Opus 4.5 to extract student info from a screenshot."""
    try:
        data = request.json
        image_data = data.get('image')  # Base64 encoded image

        if not image_data:
            return jsonify({"error": "No image provided"})

        # Use Anthropic Claude Opus 4.5 for extraction
        try:
            import anthropic
        except ImportError:
            return jsonify({"error": "Anthropic library not installed. Run: pip install anthropic"})

        from backend.api_keys import get_api_key
        api_key = get_api_key('anthropic', getattr(g, 'user_id', 'local-dev'))
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured"})

        client = anthropic.Anthropic(api_key=api_key)

        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        prompt = """Extract student information from this screenshot. Return ONLY a JSON object with these fields:
{
    "first_name": "Student's first name",
    "middle_name": "Student's middle name (if visible, otherwise empty string)",
    "last_name": "Student's last name",
    "student_id": "Student ID number (if visible, otherwise empty string)",
    "email": "Student's email address (if visible, otherwise empty string)",
    "grade": "Grade level (if visible, otherwise empty string)",
    "period": "Class period number only, e.g., '2' not 'Period 2' (if visible, otherwise empty string)"
}

Important:
- Extract exactly what you see, don't guess
- For names with multiple parts, include all parts (e.g., middle names)
- Return ONLY the JSON, no other text"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        response_text = response.content[0].text.strip()

        # Parse JSON from response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])

        student_info = json.loads(response_text)
        return jsonify({"success": True, "student": student_info})

    except json.JSONDecodeError as e:
        _logger.exception("Failed to parse AI response for student extraction")
        return jsonify({"error": "Failed to parse AI response"})
    except Exception as e:
        _logger.exception("Failed to extract student from image")
        return jsonify({"error": "An internal error occurred"}), 500


@app.route('/api/add-student-to-roster', methods=['POST'])
@require_teacher
@handle_route_errors
def add_student_to_roster():
    """Add a student to the appropriate period CSV and optionally the main roster."""
    try:
        data = request.json
        student = data.get('student', {})
        period = data.get('period', '').strip()

        if not period:
            return jsonify({"error": "Period is required"})

        first_name = student.get('first_name', '').strip()
        middle_name = student.get('middle_name', '').strip()
        last_name = student.get('last_name', '').strip()
        student_id = student.get('student_id', '').strip()
        email = student.get('email', '').strip()
        grade = student.get('grade', '06').strip()

        if not first_name or not last_name:
            return jsonify({"error": "First name and last name are required"})

        # Build full first name with middle name
        full_first = f"{first_name} {middle_name}".strip() if middle_name else first_name

        # Format: "LastName; FirstName MiddleName"
        student_name = f"{last_name}; {full_first}"

        # Find the period CSV file
        periods_dir = os.path.expanduser("~/.graider_data/periods")
        period_file = None

        for f in os.listdir(periods_dir):
            if f.endswith('.csv'):
                # Match "Period 2.csv", "Period_2.csv", "Period2.csv", etc.
                f_lower = f.lower().replace('_', ' ').replace('.csv', '')
                if f"period {period}" in f_lower or f"period{period}" in f_lower:
                    period_file = os.path.join(periods_dir, f)
                    break

        if not period_file:
            # Create new period file
            period_file = os.path.join(periods_dir, f"Period {period}.csv")
            with open(period_file, 'w', newline='', encoding='utf-8') as pf:
                writer = csv.writer(pf)
                writer.writerow(["Student", "Student ID", "Local ID", "Grade", "Local Student ID", "Team"])

        # Check if student already exists
        existing_students = []
        with open(period_file, 'r', encoding='utf-8') as pf:
            reader = csv.reader(pf)
            existing_students = list(reader)

        for row in existing_students[1:]:  # Skip header
            if row and row[0].lower() == student_name.lower():
                return jsonify({"error": f"Student '{student_name}' already exists in Period {period}"})

        # Add student to period CSV
        with open(period_file, 'a', newline='', encoding='utf-8') as pf:
            writer = csv.writer(pf)
            writer.writerow([student_name, student_id, student_id, grade, student_id, ""])

        return jsonify({
            "success": True,
            "message": f"Added {full_first} {last_name} to Period {period}",
            "student_name": student_name,
            "period_file": period_file
        })

    except Exception as e:
        _logger.exception("Failed to add student")
        return jsonify({"error": "An error occurred while adding the student"}), 500


@app.route('/api/list-periods', methods=['GET'])
@require_teacher
@handle_route_errors
def list_periods():
    """List available period CSV files."""
    try:
        periods_dir = os.path.expanduser("~/.graider_data/periods")
        periods = []

        if os.path.exists(periods_dir):
            for f in os.listdir(periods_dir):
                if f.endswith('.csv'):
                    period_name = f.replace('.csv', '').replace('_', ' ')
                    # Count students
                    count = 0
                    try:
                        with open(os.path.join(periods_dir, f), 'r', encoding='utf-8') as pf:
                            count = sum(1 for _ in pf) - 1  # Subtract header
                    except Exception:
                        pass
                    periods.append({"name": period_name, "file": f, "student_count": count})

        periods.sort(key=lambda x: x['name'])
        return jsonify({"periods": periods})

    except Exception as e:
        _logger.exception("Failed to list periods")
        return jsonify({"error": "An internal error occurred"}), 500


# ══════════════════════════════════════════════════════════════
# USER MANUAL
# ══════════════════════════════════════════════════════════════

_user_manual_cache = {}

@app.route('/api/user-manual', methods=['GET'])
@handle_route_errors
def get_user_manual():
    """Return User_Manual.md content as JSON."""
    try:
        if 'content' not in _user_manual_cache:
            manual_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'User_Manual.md')
            if not os.path.exists(manual_path):
                return jsonify({"error": "User manual not found"}), 404
            with open(manual_path, 'r', encoding='utf-8') as f:
                _user_manual_cache['content'] = f.read()
        return jsonify({"content": _user_manual_cache['content']})
    except Exception as e:
        _logger.exception("Failed to load user manual")
        return jsonify({"error": "An internal error occurred"}), 500


# ══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════

@app.route('/healthz')
def healthz():
    """General health check for Railway load balancer."""
    # Alert-drill short-circuit — exercises the full BetterStack alert
    # pipeline without touching Supabase, so student/teacher API traffic
    # is unaffected during drills. See docs/observability.md § "Quarterly
    # drill procedure" for the full runbook.
    if os.getenv('FORCE_HEALTHZ_FAIL') == '1':
        return jsonify({"app": "ok", "supabase": "drill_forced_failure"}), 503

    status = {"app": "ok"}
    # Supabase — raw httpx GET with a short timeout.
    # Deliberately bypasses ResilientClient: a healthcheck must fail fast,
    # not retry for 30s while the pod reports healthy. If this check fails
    # the pod should be marked degraded immediately so the orchestrator can
    # route around it.
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        if not supabase_url or not supabase_key:
            status["supabase"] = "not configured"
        else:
            import httpx
            resp = httpx.get(
                f"{supabase_url.rstrip('/')}/rest/v1/published_assessments?select=id&limit=1",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                timeout=3.0,
            )
            if resp.status_code == 200:
                status["supabase"] = "ok"
            else:
                status["supabase"] = f"degraded (status {resp.status_code})"
    except Exception:
        status["supabase"] = "error"

    # Check Redis if configured
    try:
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            status["redis"] = "ok"
        else:
            status["redis"] = "not configured"
    except Exception:
        status["redis"] = "error"

    return jsonify(status)


# ══════════════════════════════════════════════════════════════
# STATIC FILE SERVING
# ══════════════════════════════════════════════════════════════

@app.route('/')
def serve_frontend():
    """Serve the React frontend."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/join')
@app.route('/join/')
@app.route('/join/<path:code>')
def serve_student_portal(code=None):
    """Serve React app for student portal routes."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/student')
@app.route('/student/')
@app.route('/student/<path:subpath>')
def serve_student_app(subpath=None):
    """Serve React app for authenticated student portal."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/district')
@app.route('/district/')
def serve_district_setup():
    """Serve React app for district admin setup."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files or fall back to index.html for SPA routing."""
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import webbrowser

    def open_browser():
        """Open browser after short delay to let server start."""
        import time
        time.sleep(1.5)
        webbrowser.open('http://localhost:3000')

    print()
    print("+" + "=" * 50 + "+")
    print("|  Graider - AI-Powered Assignment Grading         |")
    print("+" + "=" * 50 + "+")
    print("|                                                  |")
    print("|  Open in browser: http://localhost:3000          |")
    print("|                                                  |")
    print("|  Press Ctrl+C to stop                            |")
    print("+" + "=" * 50 + "+")
    print()

    # Auto-open browser
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host='0.0.0.0', port=3000, debug=False)
