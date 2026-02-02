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
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Import student history for progress tracking
try:
    from backend.student_history import add_assignment_to_history, load_student_history, detect_baseline_deviation, get_baseline_summary, build_history_context
except ImportError:
    try:
        from student_history import add_assignment_to_history, load_student_history, detect_baseline_deviation, get_baseline_summary, build_history_context
    except ImportError:
        # Fallback if module not available
        def add_assignment_to_history(student_id, result):
            return None
        def load_student_history(student_id):
            return None
        def detect_baseline_deviation(student_id, result):
            return {"flag": "normal", "reasons": [], "details": {}}
        def get_baseline_summary(student_id):
            return None
        def build_history_context(student_id):
            return ""

# Import accommodation support for IEP/504 students
try:
    from backend.accommodations import build_accommodation_prompt
except ImportError:
    try:
        from accommodations import build_accommodation_prompt
    except ImportError:
        # Fallback if module not available
        def build_accommodation_prompt(student_id):
            return ""

# Load environment variables
_app_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_app_dir)
load_dotenv(os.path.join(_root_dir, '.env'), override=True)

# Add parent directory to path for importing assignment_grader
sys.path.insert(0, _root_dir)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

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
                    except:
                        continue
                elif filepath.endswith('.pdf'):
                    try:
                        import fitz  # PyMuPDF
                        pdf = fitz.open(filepath)
                        content = '\n'.join([page.get_text() for page in pdf])
                        pdf.close()
                    except:
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


def load_saved_results():
    """Load results from file on startup."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
                # Add placeholder timestamp to results that don't have one
                for r in results:
                    if 'graded_at' not in r:
                        r['graded_at'] = None  # Will show as '-' in frontend
                return results
        except:
            pass
    return []

def save_results(results):
    """Save results to file for persistence."""
    try:
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        print(f"Error saving results: {e}")

grading_state = {
    "is_running": False,
    "stop_requested": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "log": [],
    "results": load_saved_results(),  # Load saved results on startup
    "complete": False,
    "error": None
}


def reset_state(clear_results=False):
    global grading_state
    grading_state.update({
        "is_running": False,
        "stop_requested": False,
        "progress": 0,
        "total": 0,
        "current_file": "",
        "log": [],
        "results": [] if clear_results else grading_state.get("results", []),
        "complete": False,
        "error": None
    })


# ══════════════════════════════════════════════════════════════
# GRADING THREAD
# ══════════════════════════════════════════════════════════════

def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False, class_period='', rubric=None):
    """Run the grading process in a background thread.

    Args:
        selected_files: List of filenames to grade, or None to grade all files
        ai_model: OpenAI model to use ('gpt-4o' or 'gpt-4o-mini')
        skip_verified: If True, skip files that were previously graded with verified status
        rubric: Custom rubric dict from Settings with categories, weights, descriptions
    """
    global grading_state

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
                except:
                    pass

    def extract_content_fingerprints(config_data):
        """Extract unique phrases from assignment's imported document for content matching."""
        fingerprints = set()
        imported_doc = config_data.get('importedDoc', {})
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

        # Extract assignment part from filename
        if ' - ' in filename_lower:
            assignment_part = filename_lower.split(' - ', 1)[1]
        elif '_' in filename_lower:
            parts = filename_lower.split('_')
            assignment_part = '_'.join(parts[2:]) if len(parts) > 2 else filename_lower
        else:
            assignment_part = filename_lower

        assignment_part = os.path.splitext(assignment_part)[0]

        best_match = None
        best_score = 0
        match_reason = ""

        for config_name, config_data in all_configs.items():
            config_title = config_data.get('title', '').lower()
            aliases = [a.lower() for a in config_data.get('aliases', [])]

            # 1. Exact name/title match (highest priority)
            if config_name == assignment_part or config_title == assignment_part:
                return config_data  # Perfect match, return immediately

            # 2. Substring match on name/title
            if config_name in assignment_part or assignment_part in config_name:
                score = len(config_name) + 50
                if score > best_score:
                    best_score = score
                    best_match = config_data
                    match_reason = f"name match: {config_name}"

            if config_title and (config_title in assignment_part or assignment_part in config_title):
                score = len(config_title) + 50
                if score > best_score:
                    best_score = score
                    best_match = config_data
                    match_reason = f"title match: {config_title}"

            # 3. Alias matching (check all aliases)
            for alias in aliases:
                if alias in assignment_part or assignment_part in alias:
                    score = len(alias) + 40
                    if score > best_score:
                        best_score = score
                        best_match = config_data
                        match_reason = f"alias match: {alias}"

                # Fuzzy match on alias
                fuzzy = fuzzy_match_score(alias, assignment_part)
                if fuzzy > 50 and fuzzy + 20 > best_score:
                    best_score = fuzzy + 20
                    best_match = config_data
                    match_reason = f"fuzzy alias: {alias}"

            # 4. Fuzzy matching on name/title
            fuzzy_name = fuzzy_match_score(config_name, assignment_part)
            if fuzzy_name > 50 and fuzzy_name > best_score:
                best_score = fuzzy_name
                best_match = config_data
                match_reason = f"fuzzy name: {config_name}"

            fuzzy_title = fuzzy_match_score(config_title, assignment_part)
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

    # Extract custom markers, notes, and response sections from selected config (fallback)
    fallback_markers = []
    fallback_notes = ''
    fallback_sections = []
    if assignment_config:
        fallback_markers = assignment_config.get('customMarkers', [])
        fallback_notes = assignment_config.get('gradingNotes', '')
        fallback_sections = assignment_config.get('responseSections', [])

    try:
        from assignment_grader import (
            load_roster, parse_filename, read_assignment_file,
            extract_student_work, grade_assignment, grade_with_parallel_detection,
            export_focus_csv, export_detailed_report, save_emails_to_folder,
            save_to_master_csv, ASSIGNMENT_NAME, STUDENT_WORK_MARKERS
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
                        except:
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
                                    # Handle "LastName; FirstName" format
                                    if '; ' in full_name:
                                        parts = full_name.split('; ', 1)
                                        if len(parts) == 2:
                                            # Convert "LastName; FirstName" to "FirstName LastName"
                                            student_key = f"{parts[1]} {parts[0]}".lower()
                                            student_period_map[student_key] = period_name
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
                with open(master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        filename = row.get('Filename', '')
                        if filename:
                            already_graded.add(filename)
            except:
                pass

        # Also check in-memory results (loaded from saved JSON)
        # Track which files are verified (have markers/config) for skip_verified option
        verified_files = set()
        for r in grading_state.get("results", []):
            if r.get("filename"):
                already_graded.add(r["filename"])
                # Track verified status for skip_verified filtering
                if r.get("marker_status") == "verified":
                    verified_files.add(r["filename"])

        if already_graded:
            grading_state["log"].append(f"Found {len(already_graded)} previously graded files")
            if verified_files:
                grading_state["log"].append(f"  ({len(verified_files)} verified, {len(already_graded) - len(verified_files)} unverified)")

        grading_state["log"].append("Loading student roster...")
        roster = load_roster(roster_file)
        grading_state["log"].append(f"Loaded {len(roster)//2} students")

        assignment_path = Path(assignments_folder)
        all_files = []
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.pdf']:
            all_files.extend(assignment_path.glob(ext))

        # DEDUPLICATE: Keep only the most recent file per student + assignment combo
        # If a student uploads the same assignment twice, ignore all but the newest
        # But different assignments from the same student should all be graded
        def extract_student_and_assignment(filename):
            """Extract student name AND assignment from filename for deduplication.

            Returns tuple: (student_key, assignment_key)
            Example: 'jackson_gaytan_Chapter_10_Notes.docx' -> ('jackson_gaytan', 'chapter_10_notes')
            """
            import re
            name = filename.lower()
            name = os.path.splitext(name)[0]  # Remove extension

            # Try to split into student name (first 2 words) and assignment (rest)
            # Pattern: "firstname_lastname_assignment_name" or "firstname lastname - assignment"

            # Remove emojis for cleaner parsing
            name_clean = re.sub(r'[^\w\s_-]', '', name)

            # Split by underscores or spaces
            parts = re.split(r'[_\s]+', name_clean)
            parts = [p for p in parts if p]  # Remove empty parts

            if len(parts) >= 3:
                # First 2 parts are student name, rest is assignment
                student_key = f"{parts[0]}_{parts[1]}".lower()
                assignment_key = '_'.join(parts[2:]).lower()
            elif len(parts) == 2:
                student_key = f"{parts[0]}_{parts[1]}".lower()
                assignment_key = "unknown"
            else:
                student_key = name_clean
                assignment_key = "unknown"

            return (student_key, assignment_key)

        # Group files by student + assignment
        file_groups = {}
        for f in all_files:
            key = extract_student_and_assignment(f.name)
            if key not in file_groups:
                file_groups[key] = []
            file_groups[key].append(f)

        # Keep only the most recent file per student + assignment
        deduplicated_files = []
        duplicates_found = 0
        for (student_key, assignment_key), files in file_groups.items():
            if len(files) > 1:
                # Sort by modification time (newest first)
                files_sorted = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
                deduplicated_files.append(files_sorted[0])
                duplicates_found += len(files) - 1
                # Log which files were skipped
                for skipped in files_sorted[1:]:
                    grading_state["log"].append(f"⏭️ Skipping older version: {skipped.name}")
            else:
                deduplicated_files.append(files[0])

        if duplicates_found > 0:
            grading_state["log"].append(f"📋 Found {duplicates_found} duplicate submissions, using most recent only")

        all_files = deduplicated_files

        # Filter by selected files if provided
        if selected_files is not None and len(selected_files) > 0:
            selected_set = set(selected_files)
            all_files = [f for f in all_files if f.name in selected_set]
            grading_state["log"].append(f"🎯 Matched {len(all_files)} of {len(selected_files)} selected files")
        else:
            grading_state["log"].append(f"Found {len(all_files)} total files (no filter applied)")

        # Filter out already graded files (only if not using selection)
        if selected_files is None:
            new_files = [f for f in all_files if f.name not in already_graded]
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

        grading_state["total"] = len(new_files)
        grading_state["log"].append(f"Queued {len(new_files)} files for grading")

        if len(new_files) == 0:
            grading_state["log"].append("")
            grading_state["log"].append("All files have already been graded!")
            grading_state["complete"] = True
            grading_state["is_running"] = False
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
                    # Try fuzzy matching for last name initials
                    student_info = None
                    first_name_lower = parsed['first_name'].lower()
                    last_name_lower = parsed['last_name'].lower()

                    if len(last_name_lower) <= 2:
                        for roster_key, roster_data in roster.items():
                            if isinstance(roster_data, dict):
                                roster_first = roster_data.get('first_name', '').lower()
                                roster_last = roster_data.get('last_name', '').lower()
                                if roster_first == first_name_lower and roster_last.startswith(last_name_lower):
                                    student_info = roster_data.copy()
                                    student_name = f"{roster_data.get('first_name', parsed['first_name'])} {roster_data.get('last_name', parsed['last_name'])}"
                                    break

                    if not student_info:
                        student_info = {"student_id": "UNKNOWN", "student_name": student_name,
                                       "first_name": parsed['first_name'], "last_name": parsed['last_name'], "email": ""}

                # Match assignment config
                matched_config = find_matching_config(filepath.name)
                if not matched_config:
                    try:
                        temp_file_data = read_assignment_file(filepath)
                        if temp_file_data and temp_file_data.get("type") == "text":
                            file_text = temp_file_data.get("content", "")
                            if file_text:
                                matched_config = find_matching_config(filepath.name, file_text)
                    except:
                        pass

                if matched_config:
                    file_markers = matched_config.get('customMarkers', [])
                    file_exclude_markers = matched_config.get('excludeMarkers', [])
                    file_notes = matched_config.get('gradingNotes', '')
                    file_sections = matched_config.get('responseSections', [])
                    matched_title = matched_config.get('title', 'Unknown')
                    is_completion_only = matched_config.get('completionOnly', False)
                    imported_doc = matched_config.get('importedDoc', {})
                    assignment_template_local = imported_doc.get('text', '')
                    rubric_type = matched_config.get('rubricType', 'standard')
                    custom_rubric = matched_config.get('customRubric', None)
                else:
                    file_markers = fallback_markers
                    file_exclude_markers = []
                    file_notes = fallback_notes
                    file_sections = fallback_sections
                    matched_title = ASSIGNMENT_NAME
                    is_completion_only = False
                    assignment_template_local = ''
                    rubric_type = 'standard'
                    custom_rubric = None

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

                # Get student's period
                student_period = student_period_map.get(student_info['student_name'].lower(), class_period)

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

                    # Detect fill-in-the-blank assignments and add special rubric override
                    if 'fill-in' in file_notes.lower() or 'fill in' in file_notes.lower():
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
                    accommodation_prompt = build_accommodation_prompt(student_info['student_id'])
                    if accommodation_prompt:
                        file_ai_notes += f"\n{accommodation_prompt}"

                # Add student history context
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    history_context = build_history_context(student_info['student_id'])
                    if history_context:
                        file_ai_notes += f"\n{history_context}"

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

                # Read file
                file_data = read_assignment_file(filepath)
                if not file_data:
                    return {"success": False, "error": "Could not read file", "filepath": filepath}

                # Prepare grade data
                if file_data["type"] == "text":
                    grade_data = {"type": "text", "content": file_data["content"]}
                else:
                    grade_data = file_data

                # Grade with parallel detection
                # Pass file_markers (customMarkers) for extraction, not file_sections
                # Pass file_exclude_markers (excludeMarkers) to skip sections that shouldn't be graded
                grade_result = grade_with_parallel_detection(
                    student_info['student_name'], grade_data, file_ai_notes,
                    grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
                    rubric_prompt, file_markers, file_exclude_markers
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
                    except:
                        pass

                # Save to student history
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    try:
                        grade_record_hist = {**student_info, **grade_result, "filename": filepath.name,
                                       "assignment": matched_title, "period": student_period}
                        add_assignment_to_history(student_info['student_id'], grade_record_hist)
                    except:
                        pass

                # Get class level for logging
                class_level = period_class_level_map.get(student_period, 'standard') if student_period else 'standard'
                level_indicator = "🎯" if class_level == "advanced" else "💚" if class_level == "support" else ""

                log_messages = [f"  Score: {grade_result['score']} ({grade_result['letter_grade']}) {level_indicator}{class_level.upper() if class_level != 'standard' else ''}".strip()]
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
                    "student_period": student_period,
                    "is_completion_only": False,
                    "grade_result": grade_result,
                    "file_data": file_data,
                    "marker_status": marker_status,
                    "baseline_deviation": baseline_deviation,
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
            # Submit all files as futures
            future_to_file = {}
            for i, filepath in enumerate(new_files):
                if grading_state.get("stop_requested", False):
                    break
                future = executor.submit(grade_single_file, filepath, i + 1, len(new_files))
                future_to_file[future] = (filepath, i + 1)

            # Process completed futures as they finish
            for future in concurrent.futures.as_completed(future_to_file):
                if grading_state.get("stop_requested", False):
                    # Cancel remaining futures
                    for f in future_to_file:
                        f.cancel()
                    grading_state["log"].append("")
                    grading_state["log"].append(f"Stopped - {completed}/{len(new_files)} files completed")
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
                grading_state["progress"] = completed
                grading_state["current_file"] = filepath.name

                # Handle failed grading
                if not result.get("success"):
                    grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                    grading_state["log"].append(f"  ❌ {result.get('error', 'Unknown error')}")

                    # Stop on API errors
                    if result.get("is_api_error"):
                        api_error_occurred = True
                        grading_state["log"].append("")
                        grading_state["log"].append("=" * 50)
                        grading_state["log"].append("⚠️  GRADING STOPPED - API ERROR")
                        grading_state["log"].append("=" * 50)
                        grading_state["error"] = f"API Error: {result.get('error')}"
                        # Cancel remaining futures
                        for f in future_to_file:
                            f.cancel()
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
                    "has_markers": False
                }
                all_grades.append(grade_record)

                # Add to results for UI
                grading_state["results"].append({
                    "student_name": student_info['student_name'],
                    "student_id": student_info.get('student_id', ''),
                    "student_email": student_info.get('email', ''),
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "assignment": result["matched_title"],
                    "period": result["student_period"],
                    "score": grade_result.get('score', 0),
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
                    "graded_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

        # Handle API error - stop and save
        if api_error_occurred:
            grading_state["complete"] = True
            grading_state["is_running"] = False
            if grading_state["results"]:
                save_results(grading_state["results"])
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

        grading_state["log"].append("")
        grading_state["log"].append("=" * 50)

        if grading_state.get("stop_requested", False):
            grading_state["log"].append(f"GRADING STOPPED - {len(all_grades)} files saved")
            grading_state["log"].append("Restart to continue with remaining files")
        else:
            grading_state["log"].append("GRADING COMPLETE!")

        grading_state["log"].append(f"Results saved to: {output_folder}")
        grading_state["complete"] = True

        # Save results to file for persistence across restarts
        save_results(grading_state["results"])

    except Exception as e:
        grading_state["error"] = str(e)
        grading_state["log"].append(f"Error: {str(e)}")
    finally:
        grading_state["is_running"] = False
        grading_state["stop_requested"] = False
        # Also save on stop/error to preserve partial results
        if grading_state["results"]:
            save_results(grading_state["results"])


# ══════════════════════════════════════════════════════════════
# REGISTER MODULAR ROUTES
# ══════════════════════════════════════════════════════════════

from routes import register_routes
register_routes(app, grading_state, run_grading_thread, reset_state)


# ══════════════════════════════════════════════════════════════
# GRADING START ROUTE (kept here due to thread management)
# ══════════════════════════════════════════════════════════════

@app.route('/api/grade', methods=['POST'])
def start_grading():
    """Start the grading process."""
    global grading_state

    if grading_state["is_running"]:
        return jsonify({"error": "Grading already in progress"}), 400

    data = request.json
    assignments_folder = data.get('assignments_folder', '/Users/alexc/Library/CloudStorage/OneDrive-VolusiaCountySchools/Assignments')
    output_folder = data.get('output_folder', '/Users/alexc/Downloads/Graider/Results')
    roster_file = data.get('roster_file', '/Users/alexc/Downloads/Graider/all_students_updated.xlsx')
    grading_period = data.get('grading_period', 'Q3')
    grade_level = data.get('grade_level', '7')
    subject = data.get('subject', 'US History')
    teacher_name = data.get('teacher_name', '')
    school_name = data.get('school_name', '')
    ai_model = data.get('ai_model', 'gpt-4o-mini')

    # Get custom assignment config and global AI notes
    assignment_config = data.get('assignmentConfig')
    global_ai_notes = data.get('globalAINotes', '')

    # Get selected files (if any) for selective grading
    selected_files = data.get('selectedFiles', None)  # None means grade all

    # Skip verified grades on regrade (only regrade unverified assignments)
    skip_verified = data.get('skipVerified', False)

    # Get class period for differentiated grading (e.g., "Period 4" for different expectations)
    class_period = data.get('classPeriod', '')

    # Get custom rubric from Settings
    rubric = data.get('rubric', None)

    if not os.path.exists(assignments_folder):
        return jsonify({"error": f"Assignments folder not found: {assignments_folder}"}), 400
    if not os.path.exists(roster_file):
        return jsonify({"error": f"Roster file not found: {roster_file}"}), 400

    reset_state()
    grading_state["is_running"] = True

    # FERPA: Audit log grading session start
    file_count = len(selected_files) if selected_files else "all"
    audit_log("START_GRADING", f"Started grading session for {subject} grade {grade_level} ({file_count} files)")

    thread = threading.Thread(
        target=run_grading_thread,
        args=(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified, class_period, rubric)
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
        except:
            pass

    # Parse assignment config if provided
    assignment_config = None
    if assignment_config_str:
        try:
            assignment_config = json.loads(assignment_config_str)
        except:
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
        imported_doc = assignment_config.get('importedDoc', {})
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

        # Grade the assignment (no custom rubric for individual grading yet)
        grade_result = grade_with_parallel_detection(student_name, grade_data, file_ai_notes, grade_level, subject, ai_model, individual_student_id, assignment_template, None, None, file_exclude_markers)

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
            "score": grade_result.get('score', 0),
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

    # Get already graded files
    already_graded = set()
    for result in grading_state.get("results", []):
        if result.get("filename"):
            already_graded.add(result["filename"])

    # Scan folder for supported files
    supported_extensions = ['.docx', '.txt', '.jpg', '.jpeg', '.png', '.pdf']
    files = []

    try:
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_extensions:
                filepath = os.path.join(folder, f)
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


# ══════════════════════════════════════════════════════════════
# DELETE SINGLE RESULT
# ══════════════════════════════════════════════════════════════

@app.route('/api/delete-result', methods=['POST'])
def delete_single_result():
    """Delete a single grading result by filename."""
    global grading_state

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot delete results while grading is in progress"}), 400

    data = request.json
    filename = data.get('filename', '')

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Find and remove the result from state
    original_count = len(grading_state["results"])
    grading_state["results"] = [
        r for r in grading_state["results"]
        if r.get('filename', '') != filename
    ]

    if len(grading_state["results"]) == original_count:
        return jsonify({"error": "Result not found"}), 404

    # Save updated results to file
    save_results(grading_state["results"])

    # FERPA: Audit log the deletion
    audit_log("DELETE_RESULT", f"Deleted result for file: {filename[:30]}...")

    return jsonify({
        "status": "deleted",
        "filename": filename,
        "remaining_count": len(grading_state["results"])
    })


# ══════════════════════════════════════════════════════════════
# FERPA COMPLIANCE - DATA MANAGEMENT
# ══════════════════════════════════════════════════════════════

@app.route('/api/ferpa/delete-all-data', methods=['POST'])
def delete_all_student_data():
    """
    FERPA Compliance: Securely delete all student data.
    This includes grading results, settings, and cached data.
    """
    global grading_state

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
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
