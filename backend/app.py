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
    _logger.warning("Logging configuration failed: %s", e)

try:
    from backend.auth import init_auth
    init_auth(app)
except Exception as e:
    _logger.warning("Auth middleware not loaded: %s", e)
    sentry_sdk.capture_exception(e)

# Phase 4.5: structured logging for DB mode + auth source per request.
# Used to measure direct-JWT traffic share before flipping
# USE_PER_USER_JWT to "1". See backend/observability/db_mode.py.
try:
    from backend.observability.db_mode import register as _register_db_mode
    _register_db_mode(app)
except Exception as e:
    _logger.warning("db_mode observability hook not loaded: %s", e)
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
                    _logger.info("Recovered %d stale partial submissions in %s", len(ids), table)
            except Exception:
                pass
except Exception:
    pass

# ══════════════════════════════════════════════════════════════
# GRADING STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════

DOCUMENTS_DIR = os.path.expanduser("~/.graider_data/documents")

# ══════════════════════════════════════════════════════════════
# FERPA COMPLIANCE - AUDIT LOGGING
# ══════════════════════════════════════════════════════════════

from backend.utils.audit import audit_log  # noqa: E402 — extracted to avoid circular imports


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
                _logger.error("Error loading document: %s", e)
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
    data = request.json
    english_feedback = data.get('english_feedback', '')
    target_language = data.get('target_language', 'spanish')

    if not english_feedback:
        return jsonify({"error": "No feedback provided"})

    try:
        from backend.api_keys import get_api_key
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, TextPart
        adapter = OpenAIAdapter(api_key=get_api_key('openai', getattr(g, 'user_id', 'local-dev')))
        response = adapter.chat(LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(
                text=f"Translate the following teacher feedback to {target_language}. Keep the same warm, encouraging tone. Only output the translation, nothing else.\n\nFeedback:\n{english_feedback}"
            )])],
            temperature=0.3,
            metadata={"feature_label": "retranslate_feedback"},
        ))
        translation = (response.content_parts[0].text if response.content_parts else "").strip()
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

        from backend.api_keys import get_api_key
        from backend.services.llm_adapter import (
            AnthropicAdapter, ImagePart, LLMRequest, Message, TextPart,
        )
        api_key = get_api_key('anthropic', getattr(g, 'user_id', 'local-dev'))
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured"})

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

        adapter = AnthropicAdapter(api_key=api_key)
        response = adapter.chat(LLMRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[Message(
                role="user",
                content=[
                    ImagePart(url=None, base64=image_data, mime_type="image/png"),
                    TextPart(text=prompt),
                ],
            )],
            metadata={"feature_label": "extract_student_from_image"},
        ))

        response_text = (response.content_parts[0].text if response.content_parts else "").strip()

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
@limiter.exempt
def healthz():
    """General health check for Railway load balancer.

    Exempt from Flask-Limiter so a Redis outage that breaks the limiter's
    before_request storage call cannot turn a dependency check into a
    500. The route owns its own Redis check below and surfaces 503
    fail-closed semantics — that contract must not be pre-empted.

    Known defensive gap (Codex PR #220 round-2 MINOR): Flask-Session
    (Redis-backed) can still pre-empt this route if the request carries
    a session cookie, since the session interface loads BEFORE this
    handler runs. Healthcheck probes (Railway, BetterStack) don't carry
    cookies, so this is not the deploy-gate failure mode. But a
    cookie-bearing client hitting /healthz during a Redis outage will
    still see Flask 500. Filed as future hardening; not in scope for #220.
    """
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

    # Fail-closed contract: HTTP 503 when any required dependency is not
    # healthy, so Railway / load balancers can route around a degraded
    # pod. "not configured" is treated as healthy (dev/test where the
    # dep isn't wired). "ok" is healthy; everything else (including
    # "error" and "degraded (status N)") is unhealthy.
    healthy_states = {"ok", "not configured"}
    is_healthy = all(
        status.get(dep, "missing") in healthy_states
        for dep in ("supabase", "redis")
    )
    return jsonify(status), 200 if is_healthy else 503


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

    _logger.info("")
    _logger.info("+" + "=" * 50 + "+")
    _logger.info("|  Graider - AI-Powered Assignment Grading         |")
    _logger.info("+" + "=" * 50 + "+")
    _logger.info("|                                                  |")
    _logger.info("|  Open in browser: http://localhost:3000          |")
    _logger.info("|                                                  |")
    _logger.info("|  Press Ctrl+C to stop                            |")
    _logger.info("+" + "=" * 50 + "+")
    _logger.info("")

    # Auto-open browser
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host='0.0.0.0', port=3000, debug=False)
