#!/usr/bin/env python3
"""
Graider - AI-Powered Assignment Grading
=======================================
Run: python3 backend/app.py
Then open: http://localhost:3000
"""

import os
import sys
import json
import csv
import math
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from dotenv import load_dotenv

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
        from storage import load as storage_load, save as storage_save
    except ImportError:
        storage_load = None
        storage_save = None

# Load environment variables
_app_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_app_dir)
load_dotenv(os.path.join(_root_dir, '.env'), override=True)

# Add parent directory to path for importing assignment_grader
sys.path.insert(0, _root_dir)

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit
CORS(app, resources={r"/api/*": {"origins": [
    "https://app.graider.live",
    "https://graider.live",
    "https://*.up.railway.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]}})

# Fix request.host behind reverse proxy (Railway/gunicorn)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ══════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════
try:
    from auth import init_auth
    init_auth(app)
except Exception as e:
    print(f"Warning: Auth middleware not loaded: {e}")

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

def audit_log(action: str, details: str = "", user: str = "teacher"):
    """
    FERPA Compliance: Log all data access and modifications.
    Logs are kept locally and do not contain actual student data.
    """
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {user} | {action} | {details}\n"

        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Audit log error: {e}")


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


def load_saved_results(teacher_id='local-dev'):
    """Load results from storage (Supabase in prod, file locally)."""
    if storage_load:
        data = storage_load('results', teacher_id)
        if data and isinstance(data, list):
            for r in data:
                if 'graded_at' not in r:
                    r['graded_at'] = None
            return data
    # Fallback to direct file read
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
                for r in results:
                    if 'graded_at' not in r:
                        r['graded_at'] = None
                return results
        except Exception:
            pass
    return []

def save_results(results, teacher_id='local-dev'):
    """Save results to storage (dual-write: file + Supabase)."""
    if storage_save:
        storage_save('results', results, teacher_id)
    else:
        try:
            with open(RESULTS_FILE, 'w') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            print(f"Error saving results: {e}")

# ── Per-teacher grading state (dict-of-dicts) ────────────────
_grading_states = {}   # teacher_id -> state dict
_grading_locks = {}    # teacher_id -> Lock
_states_meta_lock = threading.Lock()


def _create_default_state(teacher_id='local-dev'):
    """Create a fresh grading state dict for a teacher."""
    return {
        "is_running": False,
        "stop_requested": False,
        "progress": 0,
        "total": 0,
        "current_file": "",
        "log": [],
        "results": load_saved_results(teacher_id),
        "complete": False,
        "error": None,
        "session_cost": {"total_cost": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_api_calls": 0},
        "cost_limit": 0,
        "cost_warning_pct": 80,
        "cost_limit_hit": False,
        "cost_warning_sent": False,
    }


def _get_state(teacher_id='local-dev'):
    """Get (or lazily create) the grading state dict for a teacher."""
    if teacher_id not in _grading_states:
        with _states_meta_lock:
            if teacher_id not in _grading_states:
                _grading_states[teacher_id] = _create_default_state(teacher_id)
                _grading_locks[teacher_id] = threading.Lock()
    return _grading_states[teacher_id]


def _get_lock(teacher_id='local-dev'):
    """Get (or lazily create) the grading lock for a teacher."""
    _get_state(teacher_id)  # ensure state+lock exist
    return _grading_locks[teacher_id]


def _update_state(teacher_id='local-dev', **kwargs):
    """Thread-safe grading_state update for a specific teacher."""
    with _get_lock(teacher_id):
        _get_state(teacher_id).update(kwargs)


def reset_state(teacher_id='local-dev', clear_results=False):
    """Reset grading state for a specific teacher."""
    state = _get_state(teacher_id)
    with _get_lock(teacher_id):
        state.update({
            "is_running": False,
            "stop_requested": False,
            "progress": 0,
            "total": 0,
            "current_file": "",
            "log": [],
            "results": [] if clear_results else state.get("results", []),
            "complete": False,
            "error": None,
            "session_cost": {"total_cost": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_api_calls": 0},
            "cost_limit": 0,
            "cost_warning_pct": 80,
            "cost_limit_hit": False,
            "cost_warning_sent": False,
        })


# ══════════════════════════════════════════════════════════════
# POST-BATCH CALIBRATION
# ══════════════════════════════════════════════════════════════

def _check_batch_calibration(results: list) -> dict:
    """Check if grading results have anomalous distribution.

    Runs after a full class is graded to catch systematic issues.
    Returns dict with calibrated flag and any concerns.
    """
    raw_scores = [r.get("score", 0) for r in results
                  if r.get("letter_grade") not in ("ERROR", "MANUAL REVIEW", "INCOMPLETE")]
    # Safely coerce scores to float (AI may return strings like "85")
    scores = []
    for s in raw_scores:
        try:
            scores.append(float(s))
        except (ValueError, TypeError):
            pass
    if len(scores) < 5:
        return {"calibrated": True, "concerns": []}

    import statistics
    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0
    ai_flagged = sum(1 for r in results
                     if r.get("ai_detection", {}).get("flag") in ("possible", "likely")
                     or r.get("plagiarism_detection", {}).get("flag") in ("possible", "likely"))

    concerns = []
    if mean > 95:
        concerns.append(f"Mean score is {mean:.0f} — unusually high, grading may be too lenient")
    elif mean < 55:
        concerns.append(f"Mean score is {mean:.0f} — unusually low, check rubric or extraction")

    if stdev < 5 and len(scores) > 10:
        concerns.append(f"Standard deviation is only {stdev:.1f} — scores are suspiciously uniform")

    if ai_flagged > len(results) * 0.3:
        concerns.append(f"{ai_flagged}/{len(results)} flagged for AI/plagiarism — detection may be oversensitive")

    return {
        "calibrated": len(concerns) == 0,
        "mean": round(mean, 1),
        "stdev": round(stdev, 1),
        "concerns": concerns,
        "ai_flagged_count": ai_flagged
    }


# ══════════════════════════════════════════════════════════════
# GRADING THREAD
# ══════════════════════════════════════════════════════════════

def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False, class_period='', rubric=None, ensemble_models=None, extraction_mode='structured', trusted_students=None, grading_style='standard', teacher_id='local-dev', user_api_keys=None):
    """Run the grading process in a background thread.

    Args:
        selected_files: List of filenames to grade, or None to grade all files
        ai_model: AI model to use (or primary model if not using ensemble)
        skip_verified: If True, skip files that were previously graded with verified status
        rubric: Custom rubric dict from Settings with categories, weights, descriptions
        ensemble_models: List of models for ensemble grading (e.g., ['gpt-4o-mini', 'claude-haiku', 'gemini-flash'])
        extraction_mode: "structured" (parse with rules) or "ai" (let AI identify responses)
        trusted_students: List of student IDs to skip AI/plagiarism detection for
        user_api_keys: Pre-resolved BYOK keys dict for contextvars propagation
    """
    # Resolve per-teacher state for try/finally
    state = _get_state(teacher_id)

    # BYOK: Set per-user API keys in contextvars for this thread + child workers
    from backend.api_keys import set_thread_keys, clear_thread_keys
    if user_api_keys:
        set_thread_keys(user_api_keys)

    try:
        _run_grading_thread_inner(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified, class_period, rubric, ensemble_models, extraction_mode, trusted_students, grading_style, teacher_id)
    finally:
        clear_thread_keys()


def _run_grading_thread_inner(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False, class_period='', rubric=None, ensemble_models=None, extraction_mode='structured', trusted_students=None, grading_style='standard', teacher_id='local-dev'):
    """Inner grading logic (extracted so run_grading_thread can wrap with BYOK context)."""
    # Shadow globals with per-teacher locals — all 100+ references below just work unchanged
    grading_state = _get_state(teacher_id)
    grading_lock = _get_lock(teacher_id)
    def _update_state(**kwargs):
        with grading_lock:
            grading_state.update(kwargs)

    # Log global AI notes status
    if global_ai_notes:
        preview = global_ai_notes[:100].replace('\n', ' ')
        print(f"[GRADING] Global AI Instructions received: {len(global_ai_notes)} chars - \"{preview}...\"")
    else:
        print("[GRADING] No Global AI Instructions provided")

    # Convert rubric to prompt string
    def format_rubric_for_prompt(rubric_data):
        """Convert rubric dict to a formatted prompt string."""
        if not rubric_data or not rubric_data.get('categories'):
            return None

        categories = rubric_data.get('categories', [])
        generous = rubric_data.get('generous', True)

        lines = []
        lines.append("GRADING RUBRIC (from teacher's custom settings):")
        lines.append("")

        total_weight = sum(c.get('weight', 0) for c in categories)
        lines.append(f"Total Points: {total_weight}")
        lines.append("")

        for i, cat in enumerate(categories, 1):
            name = cat.get('name', f'Category {i}')
            weight = cat.get('weight', 0)
            desc = cat.get('description', '')
            lines.append(f"{i}. {name.upper()} ({weight} points)")
            if desc:
                lines.append(f"   - {desc}")
            lines.append("")

        lines.append("GRADE RANGES:")
        lines.append("- A: 90-100 (Excellent)")
        lines.append("- B: 80-89 (Good)")
        lines.append("- C: 70-79 (Satisfactory)")
        lines.append("- D: 60-69 (Needs Improvement)")
        lines.append("- F: Below 60 (Unsatisfactory)")
        lines.append("")

        if generous:
            lines.append("GRADING STYLE: Be ENCOURAGING and GENEROUS. When in doubt, give the student the benefit of the doubt.")
        else:
            lines.append("GRADING STYLE: Grade strictly according to the rubric criteria.")

        return "\n".join(lines)

    # Format rubric and log status
    rubric_prompt = format_rubric_for_prompt(rubric)
    if rubric_prompt:
        print(f"[GRADING] Custom rubric loaded: {len(rubric.get('categories', []))} categories")
        grading_state["log"].append(f"📋 Using custom rubric ({len(rubric.get('categories', []))} categories)")
    else:
        print("[GRADING] No custom rubric - using default")

    # Build rubric_weights list for score aggregation
    # The breakdown always has 4 categories in order: content_accuracy, completeness, writing_quality, effort_engagement
    # Rubric categories map positionally to these (1st=content, 2nd=completeness, 3rd=writing, 4th=effort)
    rubric_weights = None
    if rubric and rubric.get('categories'):
        cats = rubric['categories']
        weights = [cat.get('weight', 0) for cat in cats]
        # Only use custom weights if they differ from the default 40/25/20/15
        default_weights = [40, 25, 20, 15]
        if len(weights) == 4 and weights != default_weights:
            rubric_weights = weights
            cat_names = [cat.get('name', '') for cat in cats]
            print(f"[GRADING] Custom rubric weights: {list(zip(cat_names, weights))}")

    # Load ALL saved assignment configs for auto-matching
    all_configs = {}
    assignments_dir = os.path.expanduser("~/.graider_assignments")
    if os.path.exists(assignments_dir):
        for f in os.listdir(assignments_dir):
            if f.endswith('.json'):
                config_name = f.replace('.json', '')
                try:
                    with open(os.path.join(assignments_dir, f), 'r') as cf:
                        all_configs[config_name.lower()] = json.load(cf)
                except Exception:
                    pass

    def extract_content_fingerprints(config_data):
        """Extract unique phrases from assignment's imported document for content matching."""
        fingerprints = set()
        imported_doc = config_data.get('importedDoc') or {}
        doc_text = imported_doc.get('text', '')

        if doc_text:
            # Extract significant phrases (questions, numbered items, unique sentences)
            import re
            # Get numbered questions/items (e.g., "1.", "1)", "Question 1")
            numbered = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|Question\s*\d+[:\.]?\s*)(.{20,100})', doc_text, re.IGNORECASE)
            for item in numbered[:10]:  # Limit to first 10
                clean = re.sub(r'\s+', ' ', item.strip().lower())
                if len(clean) > 20:
                    fingerprints.add(clean[:50])  # First 50 chars of each

            # Get marker texts as fingerprints
            for marker in config_data.get('customMarkers', []):
                if len(marker) > 10:
                    fingerprints.add(marker.lower()[:50])

            # Get unique sentences (not too short, not too long)
            sentences = re.split(r'[.!?]\s+', doc_text)
            for sent in sentences[:20]:
                clean = re.sub(r'\s+', ' ', sent.strip().lower())
                if 30 < len(clean) < 150:
                    fingerprints.add(clean[:50])

        return fingerprints

    def fuzzy_match_score(text1, text2):
        """Calculate fuzzy match score between two strings."""
        if not text1 or not text2:
            return 0

        t1 = text1.lower().strip()
        t2 = text2.lower().strip()

        # Exact match
        if t1 == t2:
            return 100

        # One contains the other
        if t1 in t2 or t2 in t1:
            return 80

        # Word overlap matching
        import re
        words1 = set(re.findall(r'\b\w{3,}\b', t1))  # Words 3+ chars
        words2 = set(re.findall(r'\b\w{3,}\b', t2))

        if not words1 or not words2:
            return 0

        overlap = len(words1 & words2)
        total = max(len(words1), len(words2))
        word_score = (overlap / total) * 60 if total > 0 else 0

        # Abbreviation detection (e.g., "Ch5" matches "Chapter 5")
        abbrev_patterns = [
            (r'ch(?:ap(?:ter)?)?[\s\-_]*(\d+)', r'chapter \1'),  # Ch5, Chap5, Chapter5
            (r'q(?:uiz)?[\s\-_]*(\d+)', r'quiz \1'),  # Q1, Quiz1
            (r'hw[\s\-_]*(\d+)', r'homework \1'),  # HW1
            (r'test[\s\-_]*(\d+)', r'test \1'),
            (r'unit[\s\-_]*(\d+)', r'unit \1'),
        ]

        for pattern, expansion in abbrev_patterns:
            t1_expanded = re.sub(pattern, expansion, t1, flags=re.IGNORECASE)
            t2_expanded = re.sub(pattern, expansion, t2, flags=re.IGNORECASE)
            if t1_expanded in t2_expanded or t2_expanded in t1_expanded:
                return 70

        return word_score

    def find_matching_config(filename, file_content=None):
        """Find matching config for a filename, with alias and fuzzy matching."""
        filename_lower = filename.lower()

        # Extract assignment part from filename.
        # Filenames follow pattern: FirstName_LastName_Assignment Title.ext
        # or FirstName_LastName_Assignment Title - Details (N).ext
        # Strip the student name prefix first, then use the full remaining
        # assignment title (which may itself contain ' - ').
        assignment_candidates = []

        # Strategy 1: Strip student name prefix (underscore-separated)
        if '_' in filename_lower:
            parts = filename_lower.split('_')
            if len(parts) > 2:
                full_assignment = '_'.join(parts[2:])
                full_assignment = os.path.splitext(full_assignment)[0]
                assignment_candidates.append(full_assignment)
                # Also strip trailing " (N)" version numbers
                import re
                stripped = re.sub(r'\s*\(\d+\)\s*$', '', full_assignment).strip()
                if stripped != full_assignment:
                    assignment_candidates.append(stripped)

        # Strategy 2: Split on ' - ' (legacy: assumes student_name - assignment)
        if ' - ' in filename_lower:
            after_dash = filename_lower.split(' - ', 1)[1]
            after_dash = os.path.splitext(after_dash)[0]
            if after_dash not in assignment_candidates:
                assignment_candidates.append(after_dash)

        # Strategy 3: Full filename as fallback
        fallback = os.path.splitext(filename_lower)[0]
        if fallback not in assignment_candidates:
            assignment_candidates.append(fallback)

        # Use the first candidate as primary (best quality extraction)
        assignment_part = assignment_candidates[0] if assignment_candidates else fallback

        best_match = None
        best_score = 0
        match_reason = ""

        for config_name, config_data in all_configs.items():
            config_title = config_data.get('title', '').lower()
            aliases = [a.lower() for a in config_data.get('aliases', [])]

            # Try all assignment candidates (full title, stripped version, dash-split, etc.)
            for candidate in assignment_candidates:
                # 1. Exact name/title match (highest priority)
                if config_name == candidate or config_title == candidate:
                    return config_data  # Perfect match, return immediately

                # 2. Substring match on name/title
                if config_name in candidate or candidate in config_name:
                    score = len(config_name) + 50
                    if score > best_score:
                        best_score = score
                        best_match = config_data
                        match_reason = f"name match: {config_name}"

                if config_title and (config_title in candidate or candidate in config_title):
                    score = len(config_title) + 50
                    if score > best_score:
                        best_score = score
                        best_match = config_data
                        match_reason = f"title match: {config_title}"

                # 3. Alias matching (check all aliases)
                for alias in aliases:
                    if alias in candidate or candidate in alias:
                        score = len(alias) + 40
                        if score > best_score:
                            best_score = score
                            best_match = config_data
                            match_reason = f"alias match: {alias}"

                    # Fuzzy match on alias
                    fuzzy = fuzzy_match_score(alias, candidate)
                    if fuzzy > 50 and fuzzy + 20 > best_score:
                        best_score = fuzzy + 20
                        best_match = config_data
                        match_reason = f"fuzzy alias: {alias}"

                # 4. Fuzzy matching on name/title
                fuzzy_name = fuzzy_match_score(config_name, candidate)
                if fuzzy_name > 50 and fuzzy_name > best_score:
                    best_score = fuzzy_name
                    best_match = config_data
                    match_reason = f"fuzzy name: {config_name}"

                fuzzy_title = fuzzy_match_score(config_title, candidate)
                if fuzzy_title > 50 and fuzzy_title > best_score:
                    best_score = fuzzy_title
                    best_match = config_data
                    match_reason = f"fuzzy title: {config_title}"

        # 5. Content fingerprinting (if no good match found and file content provided)
        if best_score < 50 and file_content:
            file_content_lower = file_content.lower()
            for config_name, config_data in all_configs.items():
                fingerprints = extract_content_fingerprints(config_data)
                if fingerprints:
                    matches = sum(1 for fp in fingerprints if fp in file_content_lower)
                    if matches >= 2:  # At least 2 fingerprint matches
                        content_score = min(matches * 15, 80)  # Cap at 80
                        if content_score > best_score:
                            best_score = content_score
                            best_match = config_data
                            match_reason = f"content fingerprint: {matches} matches"

        if best_match and match_reason:
            grading_state["log"].append(f"Auto-matched via {match_reason}")

        return best_match

    def calculate_late_penalty(filepath, matched_config):
        """Calculate late penalty based on file modification time and assignment config.

        Returns dict with penalty info or None if no penalty applies.
        """
        if not matched_config:
            return None

        due_date_str = matched_config.get('dueDate', '')
        late_penalty_cfg = matched_config.get('latePenalty', {})

        if not due_date_str or not late_penalty_cfg.get('enabled'):
            return None

        try:
            due_date = datetime.fromisoformat(due_date_str)
        except (ValueError, TypeError):
            return None

        # Get file modification time
        try:
            file_mtime = datetime.fromtimestamp(Path(filepath).stat().st_mtime)
        except (OSError, TypeError):
            return None

        # Apply grace period
        grace_hours = late_penalty_cfg.get('gracePeriodHours', 0) or 0
        from datetime import timedelta
        effective_due = due_date + timedelta(hours=grace_hours)

        if file_mtime <= effective_due:
            return {"is_late": False, "days_late": 0, "penalty_percent": 0, "penalty_points": 0}

        # Calculate days late (partial days round up)
        delta = file_mtime - effective_due
        days_late = math.ceil(delta.total_seconds() / 86400)

        penalty_type = late_penalty_cfg.get('type', 'points_per_day')
        amount = late_penalty_cfg.get('amount', 10) or 10
        max_penalty = late_penalty_cfg.get('maxPenalty', 50) or 50
        tiers = late_penalty_cfg.get('tiers', [])

        penalty_percent = 0
        penalty_points = 0

        if penalty_type == 'points_per_day':
            penalty_points = min(days_late * amount, max_penalty)
        elif penalty_type == 'percent_per_day':
            penalty_percent = min(days_late * amount, max_penalty)
        elif penalty_type == 'tiered':
            # Sort tiers by daysLate descending and find the matching bracket
            sorted_tiers = sorted(tiers, key=lambda t: t.get('daysLate', 0), reverse=True)
            for tier in sorted_tiers:
                if days_late >= tier.get('daysLate', 0):
                    penalty_percent = min(tier.get('penalty', 0), max_penalty)
                    break

        return {
            "is_late": True,
            "days_late": days_late,
            "penalty_type": penalty_type,
            "penalty_percent": penalty_percent,
            "penalty_points": penalty_points,
        }

    # Extract custom markers, notes, and response sections from selected config (fallback)
    fallback_markers = []
    fallback_notes = ''
    fallback_sections = []
    fallback_exclude_markers = []
    fallback_imported_doc = {}
    fallback_rubric_type = 'standard'
    fallback_custom_rubric = None
    fallback_completion_only = False
    fallback_use_section_points = False
    fallback_effort_points = 15
    if assignment_config:
        fallback_markers = assignment_config.get('customMarkers', [])
        fallback_notes = assignment_config.get('gradingNotes', '')
        fallback_sections = assignment_config.get('responseSections', [])
        fallback_exclude_markers = assignment_config.get('excludeMarkers', [])
        fallback_imported_doc = assignment_config.get('importedDoc') or {}
        fallback_rubric_type = assignment_config.get('rubricType') or 'standard'
        fallback_custom_rubric = assignment_config.get('customRubric', None)
        fallback_completion_only = assignment_config.get('completionOnly', False)
        fallback_use_section_points = assignment_config.get('useSectionPoints', False)
        fallback_effort_points = assignment_config.get('effortPoints', 15)

    try:
        from assignment_grader import (
            load_roster, parse_filename, read_assignment_file,
            extract_student_work, grade_assignment, grade_multipass, grade_with_parallel_detection,
            grade_with_ensemble, export_focus_csv, export_detailed_report,
            save_emails_to_folder, save_to_master_csv, ASSIGNMENT_NAME, STUDENT_WORK_MARKERS
        )

        if all_configs:
            grading_state["log"].append(f"Loaded {len(all_configs)} assignment configs for auto-matching")

        if global_ai_notes:
            grading_state["log"].append(f"Global AI notes loaded")

        # Load support documents (rubrics, curriculum guides, standards)
        support_docs_content = load_support_documents_for_grading(subject)
        if support_docs_content:
            grading_state["log"].append(f"Loaded reference documents for AI context")

        # Load student-to-period mapping from period CSVs for per-student grading levels
        student_period_map = {}  # Maps student name -> period name
        period_class_level_map = {}  # Maps period name -> class level (standard/advanced/support)
        periods_dir = os.path.expanduser("~/.graider_data/periods")
        if os.path.exists(periods_dir):
            import csv
            for period_file in os.listdir(periods_dir):
                if period_file.endswith('.csv'):
                    period_name = period_file.replace('.csv', '')
                    class_level = 'standard'  # Default

                    # Load class_level from metadata file if it exists
                    meta_path = os.path.join(periods_dir, f"{period_file}.meta.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, 'r') as mf:
                                meta = json.load(mf)
                                period_name = meta.get('period_name', period_name)
                                class_level = meta.get('class_level', 'standard')
                        except Exception:
                            pass

                    period_class_level_map[period_name] = class_level

                    try:
                        with open(os.path.join(periods_dir, period_file), 'r', encoding='utf-8') as pf:
                            reader = csv.DictReader(pf)
                            for row in reader:
                                # Try common column names for student name
                                first = row.get('FirstName', row.get('First Name', row.get('first_name', ''))).strip()
                                last = row.get('LastName', row.get('Last Name', row.get('last_name', ''))).strip()
                                full_name = row.get('Name', row.get('Student Name', row.get('Student', row.get('name', '')))).strip()

                                if first and last:
                                    student_key = f"{first} {last}".lower()
                                    student_period_map[student_key] = period_name
                                elif full_name:
                                    # Handle "Last; First" or "Last, First" formats
                                    if '; ' in full_name:
                                        parts = full_name.split('; ', 1)
                                        if len(parts) == 2:
                                            student_key = f"{parts[1]} {parts[0]}".lower()
                                            student_period_map[student_key] = period_name
                                    elif ', ' in full_name:
                                        parts = full_name.split(', ', 1)
                                        if len(parts) == 2:
                                            last_name = parts[0].strip()
                                            first_name = parts[1].strip()
                                            # Full key: "First Middle Last1 Last2"
                                            student_key = f"{first_name} {last_name}".lower()
                                            student_period_map[student_key] = period_name
                                            # Also add short key: "FirstWord LastWord" for filename matching
                                            first_simple = first_name.split()[0].lower() if first_name else ''
                                            last_simple = last_name.split()[0].lower() if last_name else ''
                                            if first_simple and last_simple:
                                                short_key = f"{first_simple} {last_simple}"
                                                if short_key != student_key:
                                                    student_period_map[short_key] = period_name
                                    else:
                                        student_period_map[full_name.lower()] = period_name
                    except Exception as e:
                        grading_state["log"].append(f"Warning: Could not load period file {period_file}: {e}")

            if student_period_map:
                grading_state["log"].append(f"Loaded period data for {len(student_period_map)} students")
                # Log class levels
                advanced_count = sum(1 for v in period_class_level_map.values() if v == 'advanced')
                support_count = sum(1 for v in period_class_level_map.values() if v == 'support')
                if advanced_count or support_count:
                    grading_state["log"].append(f"  Class levels: {advanced_count} advanced, {support_count} support, {len(period_class_level_map) - advanced_count - support_count} standard")

        os.makedirs(output_folder, exist_ok=True)

        # Load already graded files from master CSV AND in-memory results
        already_graded = set()

        # Check master CSV
        master_file = os.path.join(output_folder, "master_grades.csv")
        if os.path.exists(master_file):
            try:
                from backend.staging import canonicalize_filename as _canon_csv
                with open(master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        filename = row.get('Filename', '')
                        if filename:
                            already_graded.add(filename)
                            already_graded.add(_canon_csv(filename))  # also add canonical form
            except Exception:
                pass

        # Also check in-memory results (loaded from saved JSON)
        # Track which files are verified (have markers/config) for skip_verified option
        # Canonicalize all filenames so they match staged canonical names
        from backend.staging import canonicalize_filename as _canon
        verified_files = set()
        for r in grading_state.get("results", []):
            if r.get("filename"):
                already_graded.add(r["filename"])
                already_graded.add(_canon(r["filename"]))  # also add canonical form
                # Track verified status for skip_verified filtering
                if r.get("marker_status") == "verified":
                    verified_files.add(r["filename"])
                    verified_files.add(_canon(r["filename"]))

        if already_graded:
            grading_state["log"].append(f"Found {len(already_graded)} previously graded files")
            if verified_files:
                grading_state["log"].append(f"  ({len(verified_files)} verified, {len(already_graded) - len(verified_files)} unverified)")

        grading_state["log"].append("Loading student roster...")
        roster = load_roster(roster_file)
        grading_state["log"].append(f"Loaded {len(roster)//2} students")

        # Stage files: canonicalize names and deduplicate (keeps newest per student+assignment)
        from backend.staging import stage_files
        stage_result = stage_files(assignments_folder, log_fn=grading_state["log"].append)
        staging_folder = stage_result["staging_folder"]
        resubmissions = stage_result.get("resubmissions", set())

        staging_path = Path(staging_folder)
        all_files = []
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.pdf']:
            all_files.extend(staging_path.glob(ext))

        # Filter by selected files if provided (match canonical names)
        if selected_files is not None and len(selected_files) > 0:
            from backend.staging import canonicalize_filename as _canon
            selected_canonical = set(_canon(f) for f in selected_files)
            all_files = [f for f in all_files if f.name in selected_canonical]
            grading_state["log"].append(f"Matched {len(all_files)} of {len(selected_files)} selected files")
        else:
            grading_state["log"].append(f"Found {len(all_files)} total files (no filter applied)")

        # Filter out already graded files (only if not using selection)
        # Resubmissions bypass the already_graded filter — they have newer content
        if selected_files is None:
            new_files = [f for f in all_files
                         if f.name not in already_graded or f.name in resubmissions]
            resubmit_count = sum(1 for f in new_files if f.name in resubmissions and f.name in already_graded)
            if resubmit_count > 0:
                grading_state["log"].append(f"Re-grading {resubmit_count} resubmission(s) with newer versions")
            skipped = len(all_files) - len(new_files)
            if skipped > 0:
                grading_state["log"].append(f"Skipping {skipped} already-graded files")
        else:
            # When files are selected, grade them even if previously graded (re-grade)
            # BUT if skip_verified is True, skip files that were previously verified
            if skip_verified and verified_files:
                new_files = [f for f in all_files if f.name not in verified_files]
                skipped_verified = len(all_files) - len(new_files)
                if skipped_verified > 0:
                    grading_state["log"].append(f"Skipping {skipped_verified} verified grades (regrading only unverified)")
            else:
                new_files = all_files

        _update_state(total=len(new_files))
        grading_state["log"].append(f"Queued {len(new_files)} files for grading")

        if len(new_files) == 0:
            grading_state["log"].append("")
            grading_state["log"].append("All files have already been graded!")
            _update_state(complete=True, is_running=False)
            return

        all_grades = []

        # ═══════════════════════════════════════════════════════════
        # PARALLEL GRADING HELPER FUNCTION
        # ═══════════════════════════════════════════════════════════
        def grade_single_file(filepath, file_index, total_files):
            """Grade a single file - designed for parallel execution."""
            try:
                parsed = parse_filename(filepath.name)
                student_name = f"{parsed['first_name']} {parsed['last_name']}"
                lookup_key = parsed['lookup_key']

                # Lookup student in roster
                if lookup_key in roster:
                    student_info = roster[lookup_key].copy()
                else:
                    # Try fuzzy matching for partial/hyphenated last names
                    student_info = None
                    first_name_lower = parsed['first_name'].lower()
                    last_name_lower = parsed['last_name'].lower()
                    # Strip apostrophes/special chars for comparison (Da'Jaun → dajaun)
                    first_name_norm = first_name_lower.replace("'", "").replace("\u2019", "")
                    last_name_norm = last_name_lower.replace("'", "").replace("\u2019", "")
                    # Normalize spaces/hyphens (Salvador Guzman → salvadorguzman)
                    last_name_collapsed = last_name_norm.replace(" ", "").replace("-", "")

                    for roster_key, roster_data in roster.items():
                        if isinstance(roster_data, dict):
                            roster_first = roster_data.get('first_name', '').lower()
                            roster_last = roster_data.get('last_name', '').lower()
                            roster_first_norm = roster_first.replace("'", "").replace("\u2019", "")
                            roster_last_norm = roster_last.replace("'", "").replace("\u2019", "")
                            roster_last_collapsed = roster_last_norm.replace(" ", "").replace("-", "")

                            # Match first name (strip apostrophes for comparison)
                            if (roster_first_norm != first_name_norm
                                    and not roster_first_norm.startswith(first_name_norm)):
                                continue

                            # Check various last name matching patterns
                            roster_last_parts_hyphen = roster_last_norm.split('-')
                            roster_last_parts_space = roster_last_norm.split(' ')
                            if (
                                roster_last_norm.startswith(last_name_norm) or  # "k" matches "kolas"
                                roster_last_parts_hyphen[0] == last_name_norm or  # "kolas" matches "kolas-nowicki"
                                last_name_norm in roster_last_parts_hyphen or  # "nowicki" matches "kolas-nowicki"
                                roster_last_parts_space[0] == last_name_norm or  # "maloney" matches "maloney fox"
                                last_name_norm in roster_last_parts_space or  # "fox" matches "maloney fox"
                                roster_last_collapsed == last_name_collapsed  # "salvador guzman" matches "salvador-guzman"
                            ):
                                student_info = roster_data.copy()
                                student_name = f"{roster_data.get('first_name', parsed['first_name'])} {roster_data.get('last_name', parsed['last_name'])}"
                                grading_state["log"].append(f"  📎 Matched '{parsed['first_name']} {parsed['last_name']}' to '{student_name}'")
                                break

                    if not student_info:
                        student_info = {"student_id": "UNKNOWN", "student_name": student_name,
                                       "first_name": parsed['first_name'], "last_name": parsed['last_name'], "email": ""}

                # Match assignment config
                print(f"  🔍 Matching config for: {filepath.name}")
                print(f"  🔍 Available configs: {list(all_configs.keys())}")
                matched_config = find_matching_config(filepath.name)
                print(f"  🔍 Match result: {'FOUND - ' + matched_config.get('title', '?') if matched_config else 'NONE'}")
                if not matched_config:
                    try:
                        temp_file_data = read_assignment_file(filepath)
                        if temp_file_data and temp_file_data.get("type") == "text":
                            file_text = temp_file_data.get("content", "")
                            if file_text:
                                matched_config = find_matching_config(filepath.name, file_text)
                    except Exception:
                        pass

                # Track if config matches the submitted file
                config_mismatch = False
                config_mismatch_reason = ""

                if matched_config:
                    file_markers = matched_config.get('customMarkers', [])
                    file_exclude_markers = matched_config.get('excludeMarkers', [])
                    file_notes = matched_config.get('gradingNotes', '')
                    file_sections = matched_config.get('responseSections', [])
                    print(f"  ✅ Config matched: {matched_config.get('title', '?')}")
                    print(f"  ✅ Grading notes: {len(file_notes)} chars, LENIENT={'YES' if 'LENIENT' in file_notes.upper() else 'NO'}")
                    matched_title = matched_config.get('title', 'Unknown')
                    is_completion_only = matched_config.get('completionOnly', False)
                    imported_doc = matched_config.get('importedDoc') or {}
                    assignment_template_local = imported_doc.get('text', '')
                    rubric_type = matched_config.get('rubricType') or 'standard'
                    custom_rubric = matched_config.get('customRubric', None)
                    # Section-based point configuration - only use when toggle is enabled
                    use_section_points = matched_config.get('useSectionPoints', False)
                    marker_config = file_markers if use_section_points else None
                    effort_points = matched_config.get('effortPoints', 15) if use_section_points else 15
                else:
                    # NO MATCHING CONFIG FOUND
                    # Use parse_filename to properly strip student name prefix
                    import re
                    parsed = parse_filename(filepath.name)
                    submitted_assignment = parsed.get('assignment_part', '') or os.path.splitext(filepath.name)[0]
                    # Clean up: remove trailing (N) version numbers and extensions
                    submitted_assignment = re.sub(r'\s*\(\d+\)\s*$', '', submitted_assignment).strip()
                    submitted_assignment = re.sub(r'\.docx?\s*$', '', submitted_assignment, flags=re.IGNORECASE).strip()
                    submitted_assignment = re.sub(r'\.pdf\s*$', '', submitted_assignment, flags=re.IGNORECASE).strip()
                    # Replace underscores with spaces for display
                    submitted_assignment = submitted_assignment.replace('_', ' ').strip()

                    # Check if we're using a fallback config that doesn't match
                    fallback_title = assignment_config.get('title', '') if assignment_config else ''
                    if fallback_title and fallback_title.lower() != submitted_assignment.lower():
                        config_mismatch = True
                        config_mismatch_reason = f"Submitted '{submitted_assignment}' but no matching config found. Using fallback '{fallback_title}'"
                        grading_state["log"].append(f"  ⚠️  CONFIG MISMATCH: {config_mismatch_reason}")
                    elif not fallback_title:
                        config_mismatch = True
                        config_mismatch_reason = f"No saved config for '{submitted_assignment}'"
                        grading_state["log"].append(f"  ⚠️  NO CONFIG: {submitted_assignment}")

                    file_markers = fallback_markers
                    file_exclude_markers = fallback_exclude_markers
                    file_notes = fallback_notes
                    file_sections = fallback_sections
                    # Use the loaded assignment config name so all results group together.
                    # Only fall back to filename if there's truly no config at all.
                    matched_title = ASSIGNMENT_NAME if ASSIGNMENT_NAME else submitted_assignment
                    is_completion_only = fallback_completion_only
                    imported_doc = fallback_imported_doc
                    assignment_template_local = fallback_imported_doc.get('text', '')
                    rubric_type = fallback_rubric_type
                    custom_rubric = fallback_custom_rubric
                    use_section_points = fallback_use_section_points
                    marker_config = file_markers if use_section_points else None
                    effort_points = fallback_effort_points if use_section_points else 15

                # Handle completion-only rubric type
                if rubric_type == 'completion-only':
                    is_completion_only = True

                # Auto-detect rubric type from filename if not already set
                filename_lower = filepath.name.lower().replace('_', ' ').replace('-', ' ')
                if rubric_type == 'standard':
                    if 'fill in the blank' in filename_lower or 'fill in blank' in filename_lower or 'fillintheblank' in filename_lower.replace(' ', ''):
                        rubric_type = 'fill-in-blank'
                        print(f"  ✓ Auto-detected Fill-in-the-Blank from filename")
                    elif 'cornell notes' in filename_lower or 'cornellnotes' in filename_lower.replace(' ', ''):
                        rubric_type = 'cornell-notes'
                        print(f"  ✓ Auto-detected Cornell Notes from filename")

                # Get student's period - try exact match first, then fuzzy match
                student_name_lower = student_info['student_name'].lower()
                student_period = student_period_map.get(student_name_lower, None)

                # If no exact match, try fuzzy matching on period map
                if not student_period:
                    first_name_lower = student_info.get('first_name', '').lower() or student_name_lower.split()[0] if student_name_lower else ''
                    last_name_lower = student_info.get('last_name', '').lower() or (student_name_lower.split()[-1] if len(student_name_lower.split()) > 1 else '')

                    for period_key, period_val in student_period_map.items():
                        period_parts = period_key.split()
                        if len(period_parts) >= 2:
                            # period_key format: "firstname middlename lastname" or "firstname lastname"
                            period_first = period_parts[0]
                            period_last = period_parts[-1]

                            # Match first name
                            if period_first == first_name_lower or period_first.startswith(first_name_lower) or first_name_lower.startswith(period_first):
                                # Match last name (handle initials and compound names)
                                if (period_last == last_name_lower or
                                    period_last.startswith(last_name_lower) or
                                    last_name_lower.startswith(period_last) or
                                    (len(last_name_lower) == 1 and period_last.startswith(last_name_lower))):
                                    student_period = period_val
                                    break

                if not student_period:
                    student_period = class_period

                # Handle completion-only assignments
                if is_completion_only:
                    return {
                        "success": True,
                        "student_info": student_info,
                        "filepath": filepath,
                        "matched_title": matched_title,
                        "student_period": student_period,
                        "is_completion_only": True,
                        "grade_result": {
                            "score": 100,
                            "letter_grade": "SUBMITTED",
                            "feedback": "Completion-only assignment - submitted successfully.",
                            "breakdown": {},
                            "student_responses": [],
                            "unanswered_questions": [],
                            "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                            "plagiarism_detection": {"flag": "none", "reason": ""}
                        },
                        "file_data": {"type": "text", "content": ""},
                        "marker_status": "completion_only",
                        "baseline_deviation": {"flag": "normal", "reasons": [], "details": {}},
                        "log_messages": [f"  Completion only - recorded submission"]
                    }

                # Build AI notes
                file_ai_notes = global_ai_notes
                if global_ai_notes:
                    print(f"  ✓ Applying Global AI Instructions ({len(global_ai_notes)} chars)")
                if file_notes:
                    file_ai_notes += f"\n\nASSIGNMENT-SPECIFIC INSTRUCTIONS:\n{file_notes}"
                    print(f"  ✓ Applying Assignment-Specific Notes ({len(file_notes)} chars)")

                # Inject model answers from config (if generated)
                model_answers = matched_config.get('modelAnswers', {}) if matched_config else {}
                if model_answers:
                    ma_lines = ["\n\nMODEL ANSWERS (compare student responses against these):"]
                    for section_name, answer_text in model_answers.items():
                        ma_lines.append(f"- {section_name}: {answer_text}")
                    file_ai_notes += "\n".join(ma_lines)
                    print(f"  ✓ Applying Model Answers ({len(model_answers)} sections)")

                    # Detect fill-in-the-blank assignments and add special rubric override
                    # Use specific phrases to avoid false positives (e.g., "fill in the Cornell Notes")
                    _fn_lower = file_notes.lower()
                    if ('fill-in-the-blank' in _fn_lower or 'fill in the blank' in _fn_lower
                            or 'fill in blank' in _fn_lower or 'fillintheblank' in _fn_lower.replace(' ', '').replace('-', '')):
                        file_ai_notes += """

FILL-IN-THE-BLANK RUBRIC OVERRIDE:
This is a fill-in-the-blank assignment. IGNORE the standard rubric categories and use this instead:
- Content Accuracy (70%): Is each answer correct or essentially correct?
- Completeness (30%): Did the student attempt all blanks?

CRITICAL GRADING RULES FOR FILL-IN-THE-BLANK:
- DO NOT penalize for spelling errors if the word is recognizable
- DO NOT penalize for capitalization
- DO NOT assess "Writing Quality" or "Critical Thinking" - these don't apply
- Accept synonyms and reasonable variations
- If the answer is close enough to understand the intent, mark it CORRECT
- A student who fills in all blanks with mostly correct answers should get 90+
- Minor typos like "rebelion" for "rebellion" = FULL CREDIT
"""
                        print(f"  ✓ Fill-in-the-blank detected - applying lenient grading override")

                # Apply assignment-specific rubric type (overrides global rubric)
                if rubric_type and rubric_type != 'standard':
                    if rubric_type == 'fill-in-blank':
                        file_ai_notes += """

ASSIGNMENT RUBRIC TYPE: FILL-IN-THE-BLANK
IGNORE the standard rubric. Use these categories ONLY:
- Content Accuracy (70%): Is each answer correct or essentially correct?
- Completeness (30%): Did the student attempt all blanks?

CRITICAL RULES:
- DO NOT penalize spelling errors if the word is recognizable
- DO NOT penalize capitalization
- Accept synonyms and reasonable variations
- A student who fills in all blanks with mostly correct answers = 90+
"""
                        print(f"  ✓ Rubric Type: Fill-in-the-Blank")
                    elif rubric_type == 'essay':
                        file_ai_notes += """

ASSIGNMENT RUBRIC TYPE: ESSAY/WRITTEN RESPONSE
Use these categories:
- Content & Ideas (35%): Are the main points valid and well-supported?
- Writing Quality (30%): Grammar, spelling, sentence structure, clarity
- Critical Thinking & Analysis (20%): Depth of analysis, connections made
- Effort & Engagement (15%): Evidence of genuine effort and thought

Grade writing quality more strictly than fill-in-blank, but still be encouraging.
"""
                        print(f"  ✓ Rubric Type: Essay/Written Response")
                    elif rubric_type == 'cornell-notes':
                        file_ai_notes += """

ASSIGNMENT RUBRIC TYPE: CORNELL NOTES
Use these categories:
- Content Accuracy (40%): Are the notes factually correct and relevant?
- Note Structure (25%): Proper Cornell format - questions in cue column, notes in main area
- Summary Quality (20%): Does the summary synthesize main ideas?
- Effort & Completeness (15%): Are all sections filled in?

Look for: main ideas captured, good questions, clear summary at bottom.
"""
                        print(f"  ✓ Rubric Type: Cornell Notes")
                    elif rubric_type == 'custom' and custom_rubric:
                        rubric_text = "ASSIGNMENT RUBRIC TYPE: CUSTOM\nUse these categories ONLY:\n"
                        for cat in custom_rubric:
                            name = cat.get('name', 'Unknown')
                            weight = cat.get('weight', 0)
                            rubric_text += f"- {name} ({weight}%)\n"
                        file_ai_notes += f"\n{rubric_text}"
                        print(f"  ✓ Rubric Type: Custom ({len(custom_rubric)} categories)")

                # Add accommodation prompt if student has IEP/504
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    accommodation_prompt = build_accommodation_prompt(student_info['student_id'], teacher_id)
                    if accommodation_prompt:
                        file_ai_notes += f"\n{accommodation_prompt}"

                # Build student history context (passed separately to feedback, NOT mixed into grading instructions)
                history_context = ""
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    history_context = build_history_context(student_info['student_id'])

                # Add class period context for differentiated grading
                if student_period:
                    class_level = period_class_level_map.get(student_period, 'standard')
                    file_ai_notes += f"\n\nCLASS PERIOD: {student_period}"
                    file_ai_notes += f"\nCLASS LEVEL: {class_level.upper()}"

                    if class_level == 'advanced':
                        file_ai_notes += """
ADVANCED CLASS - RUBRIC ADJUSTMENT:
When applying the rubric above, make these automatic adjustments:
- INCREASE weight of Critical Thinking/Analysis categories by +15%
- INCREASE weight of Writing Quality/Communication by +10%
- DECREASE weight of Completion/Effort categories by -15%
- DECREASE weight of basic Content Accuracy by -10%
(Percentages are relative shifts - redistribute points accordingly)

ADVANCED CLASS GRADING EXPECTATIONS:
- Hold students to HIGHER standards than the base rubric suggests
- Expect detailed, thoughtful responses with deeper analysis
- Grade more strictly on grammar, vocabulary, and sophistication
- Look for evidence of critical thinking and connections between concepts
- Surface-level or simplistic answers should score in the B/C range, not A
- An "A" (90+) should represent truly exceptional, insightful work
- Be constructive but maintain high expectations
"""
                    elif class_level == 'support':
                        file_ai_notes += """
SUPPORT CLASS - RUBRIC ADJUSTMENT:
When applying the rubric above, make these automatic adjustments:
- INCREASE weight of Effort/Engagement categories by +20%
- INCREASE weight of Completion categories by +15%
- DECREASE weight of Writing Quality/Grammar by -20%
- DECREASE weight of Critical Thinking/Analysis by -15%
(Percentages are relative shifts - redistribute points accordingly)

SUPPORT CLASS GRADING EXPECTATIONS:
- Be MORE LENIENT and ENCOURAGING than the base rubric suggests
- Prioritize effort, completion, and basic understanding
- Be very generous with partial credit for attempts that show learning
- Do NOT penalize spelling, grammar, or incomplete sentences
- If student attempted the work and shows basic understanding, lean toward passing
- Recognize and praise progress and effort in feedback
- Focus feedback on encouragement and growth, not deficits
- A student who tries hard and completes work should score B or higher
"""
                    else:  # standard
                        file_ai_notes += """
STANDARD CLASS GRADING EXPECTATIONS:
- Apply the rubric as written without adjustment
- Balance rigor with encouragement
- Award credit for demonstrated understanding even if answers aren't perfect
- Grade fairly according to grade-level expectations
"""

                # Inject resubmission context so feedback references improvements
                if filepath.name in resubmissions:
                    sid = student_info.get('student_id', '')
                    prev_r = None

                    # Source 1: Current session results (has full breakdown + feedback)
                    for r in grading_state["results"]:
                        if r.get("student_id") == sid and r.get("assignment") == matched_title:
                            prev_r = r
                            break

                    # Source 2: Master CSV fallback (prior session)
                    if prev_r is None:
                        try:
                            master_csv = Path(output_folder) / "master_grades.csv"
                            if master_csv.exists():
                                import csv as csv_mod
                                with open(master_csv, 'r', encoding='utf-8') as csvf:
                                    reader = csv_mod.DictReader(csvf)
                                    for row in reader:
                                        if (row.get('Student ID', '') == sid and
                                            row.get('Assignment', '').strip().lower() == matched_title.strip().lower()):
                                            prev_r = {
                                                "score": row.get('Overall Score', '?'),
                                                "letter_grade": row.get('Letter Grade', '?'),
                                                "feedback": row.get('Feedback', ''),
                                                "breakdown": {}
                                            }
                                            break
                        except Exception:
                            pass

                    if prev_r:
                        prev_score = prev_r.get("score", "?")
                        prev_grade = prev_r.get("letter_grade", "?")
                        prev_breakdown = prev_r.get("breakdown", {})
                        prev_feedback = str(prev_r.get("feedback", ""))
                        if len(prev_feedback) > 500:
                            prev_feedback = prev_feedback[:500] + "..."

                        breakdown_lines = ""
                        if prev_breakdown:
                            breakdown_lines = (
                                f"- Content Accuracy: {prev_breakdown.get('content_accuracy', '?')}/40\n"
                                f"- Completeness: {prev_breakdown.get('completeness', '?')}/25\n"
                                f"- Writing Quality: {prev_breakdown.get('writing_quality', '?')}/20\n"
                                f"- Effort & Engagement: {prev_breakdown.get('effort_engagement', '?')}/15"
                            )

                        resub_context = (
                            "\n\nRESUBMISSION CONTEXT:\n"
                            "This student is resubmitting a previously graded assignment. "
                            "Compare their new work to the previous submission and highlight specific improvements.\n\n"
                            f"Previous submission:\n"
                            f"- Score: {prev_score} ({prev_grade})\n"
                            f"{breakdown_lines}\n"
                            f"- Previous feedback: {prev_feedback}\n\n"
                            "FEEDBACK INSTRUCTIONS FOR RESUBMISSION:\n"
                            "1. Start feedback by acknowledging this is a resubmission and that the student took the initiative to improve their work\n"
                            "2. Specifically call out what improved compared to the previous submission "
                            "(e.g., 'Your definition of X is now much more complete - last time you missed the key detail about Y')\n"
                            "3. If breakdown categories improved, mention which areas showed growth\n"
                            "4. If some areas still need work, note them as 'still developing' rather than as failures\n"
                            "5. End with encouragement about their growth mindset and willingness to revise\n"
                        )
                        file_ai_notes += resub_context
                        print(f"  🔄 Injected resubmission context (prev score: {prev_score})")

                # Read file
                file_data = read_assignment_file(filepath)
                if not file_data:
                    return {"success": False, "error": "Could not read file", "filepath": filepath}

                # Prepare grade data
                if file_data["type"] == "text":
                    grade_data = {"type": "text", "content": file_data["content"]}
                    # Pass through Graider table data for structured extraction
                    if file_data.get("graider_tables"):
                        grade_data["graider_tables"] = file_data["graider_tables"]
                else:
                    grade_data = file_data

                # Grade with parallel detection or ensemble
                # Pass file_markers (customMarkers) for extraction, not file_sections
                # Pass file_exclude_markers (excludeMarkers) to skip sections that shouldn't be graded
                # Pass marker_config and effort_points for section-based point rubric

                # GUARD: Skip grading if no assignment config exists
                # Prevents reading passages, handouts, and other non-assignment docs from being graded
                if not matched_config and not file_markers and not file_sections:
                    doc_label = matched_title or filepath.name
                    grading_state["log"].append(f"  ⏭️  SKIPPED: No assignment config — cannot grade without a configured assignment")
                    return {
                        "success": False,
                        "error": f"No assignment config found for '{doc_label}'. Set up an assignment in the Builder tab before grading.",
                        "filepath": filepath,
                        "is_config_missing": True
                    }

                # Check if student is trusted (skip AI/plagiarism detection)
                student_id = student_info.get('student_id', '')
                # Debug: Show what we're checking
                print(f"  🔍 Checking trust: student_id='{student_id}', trusted_list={trusted_students}")
                is_trusted = trusted_students and student_id in trusted_students
                if is_trusted:
                    print(f"  🛡️ Trusted student - skipping AI/copy detection")

                # FITB: Skip AI/plagiarism detection - answers are factual, not creative writing
                is_fitb = rubric_type == 'fill-in-blank'
                if is_fitb:
                    print(f"  📝 FITB assignment - skipping AI/copy detection")

                # Skip detection for trusted students or FITB assignments
                skip_detection = is_trusted or is_fitb

                # Per-assignment custom rubric overrides global rubric weights
                file_rubric_weights = rubric_weights
                if rubric_type == 'custom' and custom_rubric and len(custom_rubric) == 4:
                    file_rubric_weights = [cat.get('weight', 0) for cat in custom_rubric]
                    if file_rubric_weights != [40, 25, 20, 15]:
                        print(f"  📊 Using per-assignment custom rubric weights: {file_rubric_weights}")
                    else:
                        file_rubric_weights = None  # Default weights, no override needed

                if ensemble_models and len(ensemble_models) >= 2:
                    grade_result = grade_with_ensemble(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ensemble_models, student_info.get('student_id'),
                        assignment_template_local, rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style,
                        rubric_weights=file_rubric_weights
                    )
                elif is_trusted:
                    # Trusted student: Use full multi-pass pipeline, skip detection only
                    grade_result = grade_multipass(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ai_model, student_info.get('student_id'),
                        assignment_template_local, rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style,
                        student_history=history_context, rubric_weights=file_rubric_weights
                    )
                    grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "Trusted writer - detection skipped"}
                    grade_result['plagiarism_detection'] = {"flag": "none", "reason": "Trusted writer - detection skipped"}
                elif skip_detection:
                    # FITB only: Use single-pass (genuinely needs it)
                    grade_result = grade_assignment(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
                        rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style=grading_style,
                        rubric_weights=file_rubric_weights
                    )
                    grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "N/A - Fill-in-the-blank"}
                    grade_result['plagiarism_detection'] = {"flag": "none", "reason": "N/A - Fill-in-the-blank"}
                else:
                    grade_result = grade_with_parallel_detection(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
                        rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style,
                        student_history=history_context,
                        rubric_weights=file_rubric_weights
                    )

                # Check for errors
                if grade_result.get('letter_grade') == 'ERROR':
                    return {"success": False, "error": grade_result.get('feedback', 'API error'),
                            "filepath": filepath, "is_api_error": True}

                # Determine marker status
                has_config = matched_config is not None
                has_custom_markers = len(file_markers) > 0
                has_grading_notes = bool(file_notes.strip()) if file_notes else False
                has_response_sections = len(file_sections) > 0
                is_verified = has_config or has_custom_markers or has_grading_notes or has_response_sections
                marker_status = "verified" if is_verified else "unverified"

                # Check baseline deviation
                baseline_deviation = {"flag": "normal", "reasons": [], "details": {}}
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    try:
                        baseline_deviation = detect_baseline_deviation(student_info['student_id'], grade_result)
                    except Exception:
                        pass

                # Save to student history
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    try:
                        grade_record_hist = {**student_info, **grade_result, "filename": filepath.name,
                                       "assignment": matched_title, "period": student_period}
                        add_assignment_to_history(student_info['student_id'], grade_record_hist)
                    except Exception:
                        pass

                # Get class level for logging
                class_level = period_class_level_map.get(student_period, 'standard') if student_period else 'standard'
                level_indicator = "🎯" if class_level == "advanced" else "💚" if class_level == "support" else ""

                log_messages = [f"  Score: {grade_result['score']} ({grade_result['letter_grade']}) {level_indicator}{class_level.upper() if class_level != 'standard' else ''}".strip()]
                if config_mismatch:
                    log_messages.append(f"  ⚠️  CONFIG MISMATCH - may have wrong rubric!")
                if marker_status == "unverified":
                    log_messages.append(f"  ⚠️  UNVERIFIED: No assignment config")
                if baseline_deviation.get('flag') != 'normal':
                    log_messages.append(f"  ⚠️  Baseline deviation: {baseline_deviation.get('flag')}")
                if grade_result.get('ai_detection', {}).get('flag') in ['possible', 'likely']:
                    log_messages.append(f"  🤖 AI detected: {grade_result['ai_detection']['flag']}")
                if grade_result.get('plagiarism_detection', {}).get('flag') in ['possible', 'likely']:
                    log_messages.append(f"  📋 Plagiarism detected: {grade_result['plagiarism_detection']['flag']}")

                return {
                    "success": True,
                    "student_info": student_info,
                    "filepath": filepath,
                    "matched_title": matched_title,
                    "matched_config": matched_config,
                    "student_period": student_period,
                    "is_completion_only": False,
                    "grade_result": grade_result,
                    "file_data": file_data,
                    "marker_status": marker_status,
                    "baseline_deviation": baseline_deviation,
                    "config_mismatch": config_mismatch,
                    "config_mismatch_reason": config_mismatch_reason,
                    "log_messages": log_messages
                }

            except Exception as e:
                return {"success": False, "error": str(e), "filepath": filepath}

        # ═══════════════════════════════════════════════════════════
        # PARALLEL GRADING EXECUTION
        # ═══════════════════════════════════════════════════════════
        PARALLEL_WORKERS = 3  # Conservative: 3 students at once (6 API calls with detection)

        grading_state["log"].append(f"⚡ Parallel grading enabled ({PARALLEL_WORKERS} workers)")
        grading_state["log"].append("")

        completed = 0
        api_error_occurred = False

        with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit files in batches for responsive stop and ordered results
            file_index = 0
            stop_break = False
            while file_index < len(new_files) and not stop_break:
                if grading_state.get("stop_requested", False):
                    grading_state["log"].append("")
                    grading_state["log"].append(f"Stopped - {completed}/{len(new_files)} files completed")
                    break

                # Submit next batch
                batch_end = min(file_index + PARALLEL_WORKERS, len(new_files))
                future_to_file = {}
                for i in range(file_index, batch_end):
                    filepath = new_files[i]
                    future = executor.submit(grade_single_file, filepath, i + 1, len(new_files))
                    future_to_file[future] = (filepath, i + 1)

                # Wait for batch to complete, check stop between results
                for future in concurrent.futures.as_completed(future_to_file):
                    if grading_state.get("stop_requested", False):
                        for f in future_to_file:
                            f.cancel()
                        grading_state["log"].append("")
                        grading_state["log"].append(f"Stopped - {completed}/{len(new_files)} files completed")
                        stop_break = True
                        break

                    filepath, file_num = future_to_file[future]

                    try:
                        result = future.result()
                    except Exception as e:
                        grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                        grading_state["log"].append(f"  ❌ Error: {str(e)}")
                        continue

                    # Update progress
                    completed += 1
                    _update_state(progress=completed, current_file=filepath.name)

                    # Handle failed grading
                    if not result.get("success"):
                        grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                        if result.get("is_config_missing"):
                            grading_state["log"].append(f"  ⏭️  {result.get('error', 'No config')}")
                        else:
                            grading_state["log"].append(f"  ❌ {result.get('error', 'Unknown error')}")

                        # Stop on API errors
                        if result.get("is_api_error"):
                            api_error_occurred = True
                            grading_state["log"].append("")
                            grading_state["log"].append("=" * 50)
                            grading_state["log"].append("⚠️  GRADING STOPPED - API ERROR")
                            grading_state["log"].append("=" * 50)
                            _update_state(error=f"API Error: {result.get('error')}")
                            for f in future_to_file:
                                f.cancel()
                            stop_break = True
                            break
                        continue

                    # Log success
                    student_info = result["student_info"]
                    grade_result = result["grade_result"]

                    grading_state["log"].append(f"[{file_num}/{len(new_files)}] {student_info['student_name']}")
                    for msg in result.get("log_messages", []):
                        grading_state["log"].append(msg)

                    # Build grade record for export
                    file_data = result.get("file_data", {})
                    if file_data.get("type") == "text":
                        student_content = file_data.get("content", "")[:5000]
                        full_content = file_data.get("content", "")[:10000]
                    else:
                        student_content = "[Image file]"
                        full_content = "[Image file]"

                    grade_record = {
                        **student_info,
                        **grade_result,
                        "filename": filepath.name,
                        "assignment": result["matched_title"],
                        "period": result["student_period"],
                        "grading_period": grading_period,
                        "has_markers": False,
                        "config_mismatch": result.get("config_mismatch", False),
                        "config_mismatch_reason": result.get("config_mismatch_reason", ""),
                        "ai_model": ai_model,
                        "email_approval": "pending"
                    }

                    # Resubmission handling: only replace if new score >= old score
                    new_score = int(float(grade_result.get('score', 0) or 0))

                    # Late penalty calculation
                    matched_config = result.get("matched_config")
                    late_info = calculate_late_penalty(filepath, matched_config) if matched_config else None
                    original_score = new_score
                    if late_info and late_info.get('is_late'):
                        penalty_type = late_info.get('penalty_type', 'points_per_day')
                        if penalty_type == 'points_per_day':
                            new_score = max(0, new_score - late_info['penalty_points'])
                        else:
                            new_score = max(0, new_score - round(original_score * late_info['penalty_percent'] / 100))
                        penalty_applied = original_score - new_score
                        grading_state["log"].append(
                            f"  Late penalty: -{penalty_applied} pts ({late_info['days_late']} day{'s' if late_info['days_late'] != 1 else ''} late)"
                        )

                    # Only treat as resubmission if no explicit file selection
                    # (explicit selection = teacher re-grade, not student resubmission)
                    is_resub = filepath.name in resubmissions and selected_files is None
                    previous_result = None
                    previous_score = None

                    if is_resub:
                        sid = student_info.get('student_id', '')
                        assign = result["matched_title"]
                        for r in grading_state["results"]:
                            if r.get("student_id") == sid and r.get("assignment") == assign:
                                previous_result = r
                                previous_score = int(float(r.get("score", 0) or 0))
                                break

                        if previous_score is not None and new_score < previous_score:
                            grading_state["log"].append(f"  ↳ Kept original grade ({previous_score}) — resubmission scored lower ({new_score})")
                            if previous_result:
                                previous_result["is_resubmission"] = True
                                previous_result["resubmission_score"] = new_score
                                previous_result["kept_higher"] = True
                            continue

                    all_grades.append(grade_record)

                    # Add to results for UI (remove any existing result for same file first - for regrading)
                    new_result = {
                        "student_name": student_info['student_name'],
                        "student_id": student_info.get('student_id', ''),
                        "student_email": student_info.get('email', ''),
                        "filename": filepath.name,
                        "filepath": str(filepath),
                        "assignment": result["matched_title"],
                        "period": result["student_period"],
                        "score": new_score,
                        "letter_grade": grade_result.get('letter_grade', 'N/A'),
                        "feedback": grade_result.get('feedback', ''),
                        "student_content": student_content,
                        "full_content": full_content,
                        "breakdown": grade_result.get('breakdown', {}),
                        "student_responses": grade_result.get('student_responses', []),
                        "unanswered_questions": grade_result.get('unanswered_questions', []),
                        "ai_detection": grade_result.get('ai_detection', {}),
                        "plagiarism_detection": grade_result.get('plagiarism_detection', {}),
                        "baseline_deviation": result.get("baseline_deviation", {}),
                        "skills_demonstrated": grade_result.get('skills_demonstrated', {}),
                        "marker_status": result.get("marker_status", "unverified"),
                        "is_resubmission": is_resub,
                        "previous_score": previous_score,
                        "kept_higher": False,
                        "graded_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "ai_input": grade_result.get('_audit', {}).get('ai_input', ''),
                        "ai_response": grade_result.get('_audit', {}).get('ai_response', ''),
                        "token_usage": grade_result.get('token_usage', {}),
                        "email_approval": "pending",
                        "original_score": original_score if (late_info and late_info.get('is_late')) else None,
                        "late_penalty": {"days_late": late_info['days_late'], "penalty_applied": original_score - new_score, "penalty_type": late_info.get('penalty_type', '')} if (late_info and late_info.get('is_late')) else None,
                    }
                    with grading_lock:
                        from backend.staging import canonicalize_filename as _canon_dedup
                        canon_name = filepath.name
                        grading_state["results"] = [r for r in grading_state["results"]
                                                    if r.get("filename") != canon_name
                                                    and _canon_dedup(r.get("filename", "")) != canon_name]
                        if is_resub and previous_result:
                            sid = student_info.get('student_id', '')
                            assign = result["matched_title"]
                            grading_state["results"] = [r for r in grading_state["results"] if not (r.get("student_id") == sid and r.get("assignment") == assign)]
                        grading_state["results"].append(new_result)

                    # Accumulate session cost (lock for compound read-modify-write)
                    usage = grade_result.get('token_usage', {})
                    if usage:
                        with grading_lock:
                            grading_state["session_cost"]["total_cost"] += usage.get("total_cost", 0)
                            grading_state["session_cost"]["total_input_tokens"] += usage.get("total_input_tokens", 0)
                            grading_state["session_cost"]["total_output_tokens"] += usage.get("total_output_tokens", 0)
                            grading_state["session_cost"]["total_api_calls"] += usage.get("api_calls", 0)

                    # Warn when approaching cost limit
                    cost_limit = grading_state.get("cost_limit", 0)
                    if cost_limit > 0 and not grading_state.get("cost_warning_sent"):
                        warning_pct = grading_state.get("cost_warning_pct", 80) / 100
                        if grading_state["session_cost"]["total_cost"] >= cost_limit * warning_pct:
                            _update_state(cost_warning_sent=True)
                            grading_state["log"].append(f"  ⚠️ Approaching cost limit: ${grading_state['session_cost']['total_cost']:.4f} of ${cost_limit:.2f}")

                    # Auto-stop if cost limit exceeded
                    if cost_limit > 0 and grading_state["session_cost"]["total_cost"] >= cost_limit:
                        _update_state(stop_requested=True, cost_limit_hit=True)
                        grading_state["log"].append("")
                        grading_state["log"].append(f"Cost limit reached (${grading_state['session_cost']['total_cost']:.4f} >= ${cost_limit:.2f}). Auto-stopping...")

                # Advance to next batch
                file_index = batch_end

        # Handle API error - stop and save
        if api_error_occurred:
            _update_state(complete=True, is_running=False)
            with grading_lock:
                results_copy = list(grading_state["results"])
            if results_copy:
                save_results(results_copy, teacher_id)
            return

        # Export CSVs and emails
        if len(all_grades) > 0:
            grading_state["log"].append("")
            grading_state["log"].append("Exporting results...")

            # Focus CSVs (by assignment)
            export_focus_csv(all_grades, output_folder, ASSIGNMENT_NAME)
            grading_state["log"].append("  Focus CSVs created")

            # Detailed report
            export_detailed_report(all_grades, output_folder, ASSIGNMENT_NAME)
            grading_state["log"].append("  Detailed report created")

            # Email files
            save_emails_to_folder(all_grades, output_folder, teacher_name, subject, school_name)
            grading_state["log"].append("  Email files created")

            # Master tracking CSV
            save_to_master_csv(all_grades, output_folder)
            grading_state["log"].append("  Master grades updated")

            # Audit trail JSON
            audit_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audit_path = os.path.join(output_folder, f"Audit_{ASSIGNMENT_NAME}_{audit_timestamp}.json")
            audit_data = []
            for r in grading_state["results"]:
                audit_data.append({
                    "student_name": r["student_name"],
                    "student_id": r["student_id"],
                    "score": r["score"],
                    "letter_grade": r["letter_grade"],
                    "ai_input": r.get("ai_input", ""),
                    "ai_response": r.get("ai_response", "")
                })
            try:
                with open(audit_path, 'w') as f:
                    json.dump(audit_data, f, indent=2)
                grading_state["log"].append("  Audit trail saved")
            except Exception as e:
                grading_state["log"].append(f"  Audit trail error: {str(e)}")

        grading_state["log"].append("")
        grading_state["log"].append("=" * 50)

        if grading_state.get("stop_requested", False):
            grading_state["log"].append(f"GRADING STOPPED - {len(all_grades)} files saved")
            grading_state["log"].append("Restart to continue with remaining files")
        else:
            grading_state["log"].append("GRADING COMPLETE!")

        grading_state["log"].append(f"Results saved to: {output_folder}")
        _update_state(complete=True)

        # Post-batch calibration check
        with grading_lock:
            results_snapshot = list(grading_state["results"])
        calibration = _check_batch_calibration(results_snapshot)
        if not calibration["calibrated"]:
            for concern in calibration["concerns"]:
                grading_state["log"].append(f"⚠️ CALIBRATION: {concern}")
            _update_state(calibration=calibration)

        # Save results to storage for persistence across restarts
        save_results(results_snapshot, teacher_id)

    except Exception as e:
        _update_state(error=str(e))
        grading_state["log"].append(f"Error: {str(e)}")
    finally:
        _update_state(is_running=False, stop_requested=False)
        # Also save on stop/error to preserve partial results
        with grading_lock:
            results_copy = list(grading_state["results"])
        if results_copy:
            save_results(results_copy, teacher_id)


# ══════════════════════════════════════════════════════════════
# REGISTER MODULAR ROUTES
# ══════════════════════════════════════════════════════════════

from routes import register_routes
register_routes(app, _get_state, run_grading_thread, reset_state, _get_lock)


# ══════════════════════════════════════════════════════════════
# GRADING START ROUTE (kept here due to thread management)
# ══════════════════════════════════════════════════════════════

@app.route('/api/grade', methods=['POST'])
def start_grading():
    """Start the grading process."""
    print("🚀 BACKEND/APP.PY - /api/grade called")  # DEBUG: Confirm this file is being used

    # Capture teacher_id before thread start (g is request-scoped)
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    if grading_state["is_running"]:
        return jsonify({"error": "Grading already in progress"}), 400

    data = request.json
    assignments_folder = data.get('assignments_folder', os.path.expanduser('~/Downloads/Graider/Assignments'))
    output_folder = data.get('output_folder', os.path.expanduser('~/Downloads/Graider/Results'))
    roster_file = data.get('roster_file', os.path.expanduser('~/Downloads/Graider/all_students_updated.xlsx'))
    grading_period = data.get('grading_period', 'Q3')
    grade_level = data.get('grade_level', '7')
    subject = data.get('subject', 'US History')
    teacher_name = data.get('teacher_name', '')
    school_name = data.get('school_name', '')
    ai_model = data.get('ai_model', 'gpt-4o-mini')
    extraction_mode = data.get('extraction_mode', 'structured')  # "structured" or "ai"

    # Get custom assignment config and global AI notes
    assignment_config = data.get('assignmentConfig')
    global_ai_notes = data.get('globalAINotes', '')

    # Get selected files (if any) for selective grading
    selected_files = data.get('selectedFiles', None)  # None means grade all
    print(f"📋 selectedFiles received: {type(selected_files)} — {len(selected_files) if selected_files else 'None'}")
    if selected_files:
        print(f"📋 First 5 files: {selected_files[:5]}")

    # Skip verified grades on regrade (only regrade unverified assignments)
    skip_verified = data.get('skipVerified', False)

    # Get class period for differentiated grading (e.g., "Period 4" for different expectations)
    class_period = data.get('classPeriod', '')

    # Get custom rubric from Settings
    rubric = data.get('rubric', None)

    # Get ensemble models for multi-model grading
    ensemble_models = data.get('ensemble_models', None)

    # Get trusted students list (skip AI/plagiarism detection for these students)
    trusted_students = data.get('trustedStudents', [])
    print(f"🔐 Trusted students received: {trusted_students}")  # DEBUG

    # Get grading style (lenient / standard / strict)
    grading_style = data.get('gradingStyle', 'standard')

    if not os.path.exists(assignments_folder):
        return jsonify({"error": f"Assignments folder not found: {assignments_folder}"}), 400
    if not os.path.exists(roster_file):
        return jsonify({"error": f"Roster file not found: {roster_file}"}), 400

    reset_state(teacher_id)
    _update_state(teacher_id,
        is_running=True,
        cost_limit=float(data.get('cost_limit_per_session', 0)),
        cost_warning_pct=float(data.get('cost_warning_pct', 80)),
    )

    # BYOK: Pre-resolve API keys for this teacher before spawning thread
    from backend.api_keys import resolve_keys_for_teacher
    user_api_keys = resolve_keys_for_teacher(teacher_id)

    # FERPA: Audit log grading session start
    file_count = len(selected_files) if selected_files else "all"
    audit_log("START_GRADING", f"Started grading session for {subject} grade {grade_level} ({file_count} files)")

    thread = threading.Thread(
        target=run_grading_thread,
        args=(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified, class_period, rubric, ensemble_models, extraction_mode, trusted_students, grading_style, teacher_id, user_api_keys)
    )
    thread.start()

    return jsonify({"status": "started"})


# ══════════════════════════════════════════════════════════════
# INDIVIDUAL FILE GRADING (for paper/handwritten assignments)
# ══════════════════════════════════════════════════════════════

@app.route('/api/grade-individual', methods=['POST'])
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

        # FERPA audit log
        audit_log("GRADE_INDIVIDUAL", f"Graded individual upload for student (image-based, GPT-4o)")

        return jsonify(result)

    except Exception as e:
        print(f"Individual grading error: {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# LIST FILES IN FOLDER
# ══════════════════════════════════════════════════════════════

@app.route('/api/list-files', methods=['POST'])
def list_files():
    """List assignment files in a folder for selective grading."""
    data = request.json
    folder = data.get('folder', '')

    if not folder or not os.path.exists(folder):
        return jsonify({"files": [], "error": "Folder not found"})

    # Stage files first — canonicalize and deduplicate
    from backend.staging import stage_files, MANIFEST_NAME
    try:
        stage_result = stage_files(folder)
        staging_folder = stage_result["staging_folder"]
    except Exception as e:
        return jsonify({"files": [], "error": f"Staging failed: {e}"})

    # Get already graded files (canonicalize so they match staged names)
    from backend.staging import canonicalize_filename as _canon
    teacher_id = getattr(g, 'user_id', 'local-dev')
    already_graded = set()
    for result in _get_state(teacher_id).get("results", []):
        if result.get("filename"):
            already_graded.add(result["filename"])
            already_graded.add(_canon(result["filename"]))

    # List staged files (canonical names, deduplicated)
    supported_extensions = ['.docx', '.txt', '.jpg', '.jpeg', '.png', '.pdf']
    files = []

    try:
        for f in os.listdir(staging_folder):
            if f == MANIFEST_NAME:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_extensions:
                filepath = os.path.join(staging_folder, f)
                stat = os.stat(filepath)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "graded": f in already_graded
                })

        # Sort by name
        files.sort(key=lambda x: x["name"].lower())
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"files": [], "error": str(e)})


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


# ══════════════════════════════════════════════════════════════
# DELETE SINGLE RESULT
# ══════════════════════════════════════════════════════════════

@app.route('/api/delete-result', methods=['POST'])
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
        audit_log("DELETE_ALL_DATA_ERROR", str(e))
        return jsonify({"error": f"Failed to delete data: {str(e)}"}), 500


@app.route('/api/ferpa/audit-log', methods=['GET'])
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
        except Exception:
            pass
    export["accommodations"] = student_accommodations

    # 4. ELL data
    ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
    ell_data = None
    if os.path.exists(ell_file):
        try:
            with open(ell_file, 'r') as f:
                all_ell = json.load(f)
            ell_data = all_ell.get(safe_id) or all_ell.get(matched_id or '')
        except Exception:
            pass
    export["ell_data"] = ell_data

    # 5. Parent contacts
    contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
    parent_contacts = None
    if os.path.exists(contacts_file):
        try:
            with open(contacts_file, 'r') as f:
                all_contacts = json.load(f)
            parent_contacts = all_contacts.get(safe_id) or all_contacts.get(matched_id or '')
        except Exception:
            pass
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
        return jsonify({"error": f"Invalid JSON file: {e}"}), 400

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
            except Exception:
                pass
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
            except Exception:
                pass
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
def get_student_history_api(student_id):
    """Get a student's grading history and progress patterns."""
    history = load_student_history(student_id)
    if not history:
        return jsonify({"error": "No history found"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_HISTORY", f"Viewed history for student ID: {student_id[:6]}...")

    return jsonify(history)


@app.route('/api/student-baseline/<student_id>', methods=['GET'])
def get_student_baseline_api(student_id):
    """Get a student's baseline performance metrics for deviation detection."""
    baseline = get_baseline_summary(student_id)
    if not baseline:
        return jsonify({"error": "Insufficient history for baseline (need 3+ assignments)"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_BASELINE", f"Viewed baseline for student ID: {student_id[:6]}...")

    return jsonify(baseline)


@app.route('/api/retranslate-feedback', methods=['POST'])
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
        return jsonify({"error": str(e)})


# ══════════════════════════════════════════════════════════════
# ROSTER MANAGEMENT - Add student from screenshot
# ══════════════════════════════════════════════════════════════

@app.route('/api/extract-student-from-image', methods=['POST'])
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
        return jsonify({"error": f"Failed to parse AI response: {e}", "raw_response": response_text})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/add-student-to-roster', methods=['POST'])
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
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/api/list-periods', methods=['GET'])
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
        return jsonify({"error": str(e)})


# ══════════════════════════════════════════════════════════════
# USER MANUAL
# ══════════════════════════════════════════════════════════════

_user_manual_cache = {}

@app.route('/api/user-manual', methods=['GET'])
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
        return jsonify({"error": str(e)}), 500


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
