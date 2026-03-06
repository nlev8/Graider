"""
Assistant Tools Service
=======================
Shared helpers, data loading functions, and submodule merge mechanism
for the AI assistant tool system.

Tool handler functions and definitions are in submodules:
  - assistant_tools_grading.py   (grade queries, analytics, comparisons)
  - assistant_tools_reports.py   (exports, documents, calendar, resources, comms)
  - assistant_tools_data.py      (memory, calendar, email config persistence)
  - assistant_tools_edtech.py    (EdTech integrations)
  - assistant_tools_analytics.py (advanced analytics)
  - assistant_tools_planning.py  (lesson planning)
  - assistant_tools_communication.py (communication)
  - assistant_tools_student.py   (student-facing)
  - assistant_tools_ai.py        (AI-powered content generation)
  - assistant_tools_stem.py      (STEM tools)
  - assistant_tools_automation.py (browser automation)
"""

import os
import csv
import json
import subprocess
import statistics
from collections import defaultdict
from datetime import datetime

# Import storage abstraction
try:
    from backend.storage import load as storage_load, save as storage_save, list_keys as storage_list_keys
except ImportError:
    try:
        from storage import load as storage_load, save as storage_save, list_keys as storage_list_keys
    except ImportError:
        storage_load = None
        storage_save = None
        storage_list_keys = None


# Paths
RESULTS_FILE = os.path.expanduser("~/.graider_results.json")
SETTINGS_FILE = os.path.expanduser("~/.graider_global_settings.json")
ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_assignments")
STUDENT_HISTORY_DIR = os.path.expanduser("~/.graider_data/student_history")
EXPORTS_DIR = os.path.expanduser("~/.graider_exports/focus")
CREDS_FILE = os.path.expanduser("~/.graider_data/portal_credentials.json")
LESSONS_DIR = os.path.expanduser("~/.graider_lessons")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STANDARDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PERIODS_DIR = os.path.expanduser("~/.graider_data/periods")
ACCOMMODATIONS_DIR = os.path.expanduser("~/.graider_data/accommodations")
PARENT_CONTACTS_FILE = os.path.expanduser("~/.graider_data/parent_contacts.json")
PERIOD_CSVS_DIR = os.path.join(PROJECT_ROOT, "Period CSVs")
MEMORY_FILE = os.path.expanduser("~/.graider_data/assistant_memory.json")
DOCUMENTS_DIR = os.path.expanduser("~/.graider_data/documents")
MAX_MEMORIES = 50
CALENDAR_FILE = os.path.expanduser("~/.graider_data/teaching_calendar.json")


# ═══════════════════════════════════════════════════════
# SHARED UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════

def _fuzzy_name_match(search, full_name):
    """Word-based name matching. Returns True if every word in search appears
    as a word (or word-prefix) in full_name. Order-independent, case-insensitive.

    Also handles middle name mismatch: if search has 3+ words and full_name
    has fewer, tries matching first + last words only (middle names are often
    dropped or abbreviated in different systems).

    Examples:
        _fuzzy_name_match("Dicen Wilkins", "Dicen Macheil Wilkins Reels") → True
        _fuzzy_name_match("Dicen Wilkins", "Wilkins Reels, Dicen Macheil") → True
        _fuzzy_name_match("Luke Lundell", "Luke J Lundell") → True
        _fuzzy_name_match("John Smith", "Jane Smith") → False
        _fuzzy_name_match("Troy Jaxson Mikell", "Troy Mikell") → True
    """
    import re
    # Strip punctuation (commas, semicolons, periods) and normalize
    clean = lambda s: re.sub(r'[,;.\'"]+', ' ', s.lower()).split()
    search_words = clean(search)
    name_words = clean(full_name)
    if not search_words:
        return False

    def _words_match(sw_list, nw_list):
        return all(
            any(nw.startswith(sw) or (len(nw) >= 2 and sw.startswith(nw)) for nw in nw_list)
            for sw in sw_list
        )

    # Strict: all search words match
    if _words_match(search_words, name_words):
        return True

    # Middle name tolerance: if search has 3+ words and more words than
    # full_name, try first + last only (covers "Troy Jaxson Mikell" → "Troy Mikell")
    if len(search_words) >= 3 and len(search_words) > len(name_words):
        key_words = [search_words[0], search_words[-1]]
        if _words_match(key_words, name_words):
            return True

    # Reverse: full_name has more words, try matching with first + last of full_name
    if len(name_words) >= 3 and len(name_words) > len(search_words):
        key_name = [name_words[0], name_words[-1]]
        if _words_match(search_words, key_name):
            return True

    return False


def _extract_first_name(name):
    """Extract the actual first name from various name formats.

    Handles:
        "First Last"                → "First"
        "Last, First Middle"        → "First"
        "Last; First Middle"        → "First"
        "First Middle Last Last2"   → "First"
    """
    if not name or name == 'Student':
        return 'Student'
    name = name.strip()
    # If comma or semicolon present, part after separator is first name
    for sep in [',', ';']:
        if sep in name:
            parts = name.split(sep, 1)
            after = parts[1].strip()
            return after.split()[0] if after else parts[0].strip().split()[0]
    return name.split()[0]


def _safe_int_score(val):
    """Safely convert a score value to int (handles str, float, None)."""
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError):
        return 0


def _normalize_assignment_name(name):
    """Normalize assignment name for comparison (strips suffixes like (1), .docx)."""
    import re
    n = name.strip()
    n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)  # Remove .docx
    n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)    # Remove .pdf
    n = re.sub(r'\s*\(\d+\)\s*$', '', n)       # Remove trailing (1), (2) — after extensions
    n = re.sub(r'[^\w\s&\']', ' ', n)          # Strip punctuation/symbols/emoji (keep & and ')
    n = n.replace('_', ' ')                    # Underscores to spaces
    n = re.sub(r'\s+', ' ', n)                 # Collapse whitespace
    return n.strip().lower()


def _get_period_assignments(rows):
    """Build a map of normalized_period -> set of normalized assignment names.
    Also returns the display name for each normalized assignment.
    Merges truncated assignment names with their full versions."""
    from collections import defaultdict
    period_assigns = defaultdict(set)
    assign_display = {}  # normalized -> best display name
    for row in rows:
        period = _normalize_period(row.get("period", "") or row.get("quarter", ""))
        assign = row.get("assignment", "")
        if period and assign:
            norm = _normalize_assignment_name(assign)
            period_assigns[period].add(norm)
            # Keep the longest display name (most descriptive)
            if norm not in assign_display or len(assign) > len(assign_display[norm]):
                assign_display[norm] = assign

    # Merge truncated names: if one norm is a prefix of another (>=20 chars), unify them
    all_norms = sorted(assign_display.keys(), key=len, reverse=True)
    merge_map = {}  # short_norm -> long_norm
    for i, short in enumerate(all_norms):
        if short in merge_map:
            continue
        short_lower = short.lower()
        for long in all_norms[:i]:
            if long in merge_map:
                continue
            if len(short_lower) >= 20 and long.lower().startswith(short_lower) and short_lower != long.lower():
                merge_map[short] = long
                break

    if merge_map:
        for period in period_assigns:
            merged = set()
            for n in period_assigns[period]:
                merged.add(merge_map.get(n, n))
            period_assigns[period] = merged
        for short, long in merge_map.items():
            if short in assign_display:
                # Keep the longer display name
                if long not in assign_display or len(assign_display[short]) > len(assign_display[long]):
                    assign_display[long] = assign_display[short]
                del assign_display[short]

    return period_assigns, assign_display, merge_map


def _get_output_folder(teacher_id='local-dev'):
    """Get the configured output folder for grading results."""
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    settings = _load_settings(teacher_id)
    if settings:
        output_folder = settings.get('output_folder', output_folder)
    return output_folder


def _normalize_period(p):
    """Normalize period strings so '6', 'period 6', 'Period 6', 'Period_6' all match."""
    if not p or p == 'all':
        return p
    import re
    s = p.strip().lower().replace('_', ' ')
    # Extract just the number if present
    m = re.search(r'\d+', s)
    if m:
        return f"Period {m.group()}"
    return p


# ═══════════════════════════════════════════════════════
# DATA LOADING FUNCTIONS
# ═══════════════════════════════════════════════════════

def _load_results(teacher_id='local-dev'):
    """Load grading results from storage."""
    if storage_load:
        data = storage_load('results', teacher_id)
        if data is not None:
            return data
    # Fallback to file
    if not os.path.exists(RESULTS_FILE):
        return []
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _load_master_csv(period_filter='all'):
    """Load and parse the master grades CSV, then merge in any results from
    the results JSON that aren't already present. This ensures the Assistant
    always sees the most complete, up-to-date data."""
    import re

    def _norm_assign(name):
        n = name.strip()
        n = re.sub(r'\s*\(\d+\)\s*$', '', n)
        n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
        return n.strip().lower()

    output_folder = _get_output_folder()
    master_file = os.path.join(output_folder, "master_grades.csv")
    period_filter = _normalize_period(period_filter)

    rows = []
    seen_keys = set()  # (student_id, normalized_assignment)

    # 1. Load master CSV
    if os.path.exists(master_file):
        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row.get("Student Name"):
                        continue
                    if period_filter != 'all' and _normalize_period(row.get("Quarter", "")) != period_filter:
                        continue
                    sid = row.get("Student ID", "")
                    assign = row.get("Assignment", "")
                    parsed = {
                        "student_name": row.get("Student Name", ""),
                        "student_id": sid,
                        "first_name": row.get("First Name", ""),
                        "date": row.get("Date", ""),
                        "assignment": assign,
                        "period": row.get("Period", ""),
                        "quarter": row.get("Quarter", ""),
                        "score": int(float(row.get("Overall Score", 0) or 0)),
                        "letter_grade": row.get("Letter Grade", ""),
                        "content": int(float(row.get("Content Accuracy", 0) or 0)),
                        "completeness": int(float(row.get("Completeness", 0) or 0)),
                        "writing": int(float(row.get("Writing Quality", 0) or 0)),
                        "effort": int(float(row.get("Effort Engagement", 0) or 0)),
                    }
                    rows.append(parsed)
                    if sid and sid != "UNKNOWN":
                        seen_keys.add((sid, _norm_assign(assign)))
        except Exception:
            pass

    # 2. Merge in results JSON entries not already in master CSV.
    #    Master CSV is authoritative for scores (it's synced on edits).
    #    Results JSON fills in grades that haven't been written to CSV yet.
    results_json = _load_results()

    # Build a name→student_id lookup from known data for resolving UNKNOWN IDs
    name_to_id = {}
    name_to_period = {}
    for row in rows:
        sid = row["student_id"]
        name = row["student_name"].lower().strip()
        if sid and sid != "UNKNOWN" and name:
            name_to_id[name] = sid
            if row["period"]:
                name_to_period[name] = row["period"]

    for r in results_json:
        sid = str(r.get("student_id", ""))
        rname = r.get("student_name", "")
        assign = r.get("assignment", "")
        if not assign or not rname:
            continue

        # Resolve UNKNOWN student_id by matching name against known students
        if not sid or sid == "UNKNOWN":
            rname_lower = rname.lower().strip()
            rname_words = rname_lower.split()
            resolved_sid = None
            for known_name, known_id in name_to_id.items():
                # Exact substring match
                if len(rname_lower) >= 5 and (rname_lower in known_name or known_name.startswith(rname_lower)):
                    resolved_sid = known_id
                    break
                # Word-prefix match: every word in the short name starts a word in the known name
                # Handles "vincent scar" → "vincent ray scarola"
                if len(rname_words) >= 2:
                    known_words = known_name.split()
                    if all(any(kw.startswith(rw) for kw in known_words) for rw in rname_words):
                        resolved_sid = known_id
                        break
            if resolved_sid:
                sid = resolved_sid
            else:
                continue  # Can't resolve — skip

        key = (sid, _norm_assign(assign))
        if key in seen_keys:
            # Already in master CSV — master CSV is authoritative, don't overwrite
            continue

        # Not in master CSV — add it from results JSON
        breakdown = r.get("breakdown", {})
        period = r.get("period", "") or name_to_period.get(rname.lower().strip(), "")
        if period_filter != 'all' and _normalize_period(period) != period_filter and period != "":
            continue
        rows.append({
            "student_name": rname if len(rname) > 5 else next((row["student_name"] for row in rows if row["student_id"] == sid), rname),
            "student_id": sid,
            "first_name": _extract_first_name(rname),
            "date": r.get("graded_at", "")[:10] if r.get("graded_at") else "",
            "assignment": assign,
            "period": period,
            "quarter": "",
            "score": int(float(r.get("score", 0) or 0)),
            "letter_grade": r.get("letter_grade", ""),
            "content": int(float(breakdown.get("content_accuracy", 0) or 0)),
            "completeness": int(float(breakdown.get("completeness", 0) or 0)),
            "writing": int(float(breakdown.get("writing_quality", 0) or 0)),
            "effort": int(float(breakdown.get("effort_engagement", 0) or 0)),
        })
        seen_keys.add(key)

    return rows


def _load_period_class_levels(teacher_id='local-dev'):
    """Load class level (advanced/standard/support) for each period from metadata."""
    levels = {}
    if not os.path.exists(PERIODS_DIR):
        return levels
    for f in os.listdir(PERIODS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(PERIODS_DIR, f), 'r') as fh:
                    meta = json.load(fh)
                period_name = meta.get('period_name', f.replace('.csv.meta.json', ''))
                class_level = meta.get('class_level', 'standard')
                levels[period_name] = class_level
            except Exception:
                pass
    return levels


def _load_accommodations(teacher_id='local-dev'):
    """Load student accommodation data (IEP/504 presets)."""
    if storage_load:
        data = storage_load('accommodations', teacher_id)
        if data is not None:
            return data
    # Fallback to file
    accommodations = {}
    if not os.path.exists(ACCOMMODATIONS_DIR):
        return accommodations
    for f in os.listdir(ACCOMMODATIONS_DIR):
        if f.endswith('.json'):
            try:
                with open(os.path.join(ACCOMMODATIONS_DIR, f), 'r') as fh:
                    data = json.load(fh)
                student_id = f.replace('.json', '')
                accommodations[student_id] = {
                    "presets": data.get('presets', []),
                    "notes": data.get('notes', ''),
                    "student_id": student_id,
                }
            except Exception:
                pass
    return accommodations


def _load_settings(teacher_id='local-dev'):
    """Load teacher settings (subject, state, grade level, AI notes)."""
    if storage_load:
        data = storage_load('settings', teacher_id)
        if data is not None:
            return data
    # Fallback to file
    settings_path = SETTINGS_FILE
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _load_standards():
    """Load curriculum standards based on teacher's configured subject/state."""
    settings = _load_settings()
    config = settings.get('config', {})
    state = config.get('state', 'FL').lower()
    subject = config.get('subject', '').lower().replace(' ', '_')

    # Map subject names to filenames
    subject_map = {
        'us_history': 'us_history',
        'u.s._history': 'us_history',
        'world_history': 'world_history',
        'civics': 'civics',
        'geography': 'geography',
        'english/ela': 'english-ela',
        'english': 'english-ela',
        'ela': 'english-ela',
        'math': 'math',
        'science': 'science',
        'social_studies': 'social_studies',
    }
    subject_key = subject_map.get(subject, subject)
    filename = f"standards_fl_{subject_key}.json"
    filepath = os.path.join(STANDARDS_DIR, filename)

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Handle both formats: wrapped dict {"standards": [...]} or flat array [...]
            if isinstance(data, list):
                return data
            return data.get('standards', [])
        except Exception:
            pass
    return []


def _load_saved_lessons(teacher_id='local-dev'):
    """Load saved lesson plan titles and topics."""
    lessons = []
    if storage_list_keys and storage_load:
        keys = storage_list_keys('lesson:', teacher_id)
        for key in keys:
            data = storage_load(key, teacher_id) or {}
            parts = key.split(':', 2)
            unit = parts[1] if len(parts) > 1 else ''
            lessons.append({
                "title": data.get('title', parts[2] if len(parts) > 2 else ''),
                "unit": unit,
                "standards": data.get('standards', []),
            })
        if lessons:
            return lessons
    # Fallback to file
    if not os.path.exists(LESSONS_DIR):
        return lessons
    for unit_dir in os.listdir(LESSONS_DIR):
        unit_path = os.path.join(LESSONS_DIR, unit_dir)
        if os.path.isdir(unit_path):
            for f in os.listdir(unit_path):
                if f.endswith('.json'):
                    try:
                        with open(os.path.join(unit_path, f), 'r') as fh:
                            data = json.load(fh)
                        lessons.append({
                            "title": data.get('title', f.replace('.json', '')),
                            "unit": unit_dir,
                            "standards": data.get('standards', []),
                        })
                    except Exception:
                        pass
    return lessons


def _load_roster(teacher_id='local-dev'):
    """Load student roster from periods. Returns list of dicts with name, id, local_id, grade, period, course_codes."""
    roster = []
    if not os.path.exists(PERIODS_DIR):
        return roster
    # Load period metadata for course codes
    period_meta = {}
    for f in os.listdir(PERIODS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(PERIODS_DIR, f), 'r') as fh:
                    meta = json.load(fh)
                csv_name = f.replace('.meta.json', '')
                period_meta[csv_name] = meta
            except Exception:
                pass

    for f in sorted(os.listdir(PERIODS_DIR)):
        if not f.endswith('.csv'):
            continue
        meta = period_meta.get(f, {})
        period_name = meta.get('period_name', f.replace('.csv', '').replace('_', ' '))
        course_codes = meta.get('course_codes', [])
        filepath = os.path.join(PERIODS_DIR, f)
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    raw_name = row.get('Student', '').strip().strip('"')
                    student_id = row.get('Student ID', '').strip().strip('"')
                    local_id = row.get('Local ID', '').strip().strip('"')
                    grade = row.get('Grade', '').strip().strip('"')
                    # Convert "Last, First Middle" or "Last; First Middle" to "First Middle Last"
                    if ';' in raw_name:
                        parts = raw_name.split(';', 1)
                        last = parts[0].strip()
                        first = parts[1].strip() if len(parts) > 1 else ''
                        display_name = f"{first} {last}".strip()
                    elif ',' in raw_name:
                        parts = raw_name.split(',', 1)
                        last = parts[0].strip()
                        first = parts[1].strip() if len(parts) > 1 else ''
                        display_name = f"{first} {last}".strip()
                    else:
                        display_name = raw_name
                    if display_name:
                        roster.append({
                            "name": display_name,
                            "student_id": student_id,
                            "local_id": local_id,
                            "grade": grade,
                            "period": period_name,
                            "course_codes": course_codes,
                        })
        except Exception:
            pass
    return roster


def _load_parent_contacts(teacher_id='local-dev'):
    """Load parent contacts keyed by student ID."""
    if storage_load:
        data = storage_load('parent_contacts', teacher_id)
        if data is not None:
            return data
    # Fallback to file
    if not os.path.exists(PARENT_CONTACTS_FILE):
        return {}
    try:
        with open(PARENT_CONTACTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _load_saved_assignments(teacher_id='local-dev'):
    """Load saved assignment configs.
    Returns list of dicts with normalized name and display title."""
    saved = []
    def _collect_aliases(data, aliases):
        """Build normalized alias list from explicit aliases + importedDoc filename."""
        norms = [_normalize_assignment_name(a) for a in aliases if a]
        imported_fn = data.get('importedDoc', {}).get('filename', '')
        if imported_fn:
            norms.append(_normalize_assignment_name(imported_fn))
        return [n for n in norms if n]

    if storage_list_keys and storage_load:
        keys = storage_list_keys('assignment:', teacher_id)
        for key in keys:
            data = storage_load(key, teacher_id) or {}
            title = data.get('title', key[len('assignment:'):])
            saved.append({
                "title": title,
                "norm": _normalize_assignment_name(title),
                "aliases": _collect_aliases(data, data.get('aliases', [])),
            })
        if saved:
            return saved
    # Fallback to file
    if not os.path.exists(ASSIGNMENTS_DIR):
        return saved
    for f in sorted(os.listdir(ASSIGNMENTS_DIR)):
        if not f.endswith('.json'):
            continue
        try:
            with open(os.path.join(ASSIGNMENTS_DIR, f), 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            title = data.get('title', f.replace('.json', ''))
            saved.append({
                "title": title,
                "norm": _normalize_assignment_name(title),
                "aliases": _collect_aliases(data, data.get('aliases', [])),
            })
        except Exception:
            pass
    return saved


def _load_calendar(teacher_id='local-dev'):
    """Load calendar data from storage."""
    default = {"scheduled_lessons": [], "holidays": [], "school_days": {}}
    if storage_load:
        data = storage_load('teaching_calendar', teacher_id)
        if data is not None:
            return data
    # Fallback to file
    if not os.path.exists(CALENDAR_FILE):
        return default
    try:
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save_calendar(data, teacher_id='local-dev'):
    """Persist calendar data to storage."""
    if storage_save:
        storage_save('teaching_calendar', data, teacher_id)
    else:
        os.makedirs(os.path.dirname(CALENDAR_FILE), exist_ok=True)
        with open(CALENDAR_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


def _load_memories(teacher_id='local-dev'):
    """Load saved memories from storage. Returns list of fact strings."""
    if storage_load:
        data = storage_load('assistant_memory', teacher_id)
        if data is not None:
            return data if isinstance(data, list) else []
    # Fallback to file
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_memories(memories, teacher_id='local-dev'):
    """Persist memories list to storage."""
    if storage_save:
        storage_save('assistant_memory', memories, teacher_id)
    else:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memories, f, indent=2)


def _load_email_config():
    """Load teacher email config (teacher_name, teacher_email, signature)."""
    config_path = os.path.expanduser("~/.graider_email_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS & HANDLERS (populated by submodules via _merge_submodules)
# ═══════════════════════════════════════════════════════

TOOL_DEFINITIONS = []

TOOL_HANDLERS = {}


# ═══════════════════════════════════════════════════════
# MERGE SUBMODULE TOOLS (deferred to avoid circular imports)
# ═══════════════════════════════════════════════════════

_submodules_merged = False
_merge_in_progress = False


def _merge_submodules():
    """Lazily merge tool definitions from submodules on first access.
    Uses a reentrancy guard to handle circular imports gracefully:
    if a submodule triggers this module to load, the nested call is a no-op.
    Only marks as complete when ALL submodules loaded successfully."""
    global _submodules_merged, _merge_in_progress
    if _submodules_merged or _merge_in_progress:
        return
    _merge_in_progress = True

    submodules = [
        ("backend.services.assistant_tools_grading", "GRADING_TOOL_DEFINITIONS", "GRADING_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_reports", "REPORT_TOOL_DEFINITIONS", "REPORT_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_data", "DATA_TOOL_DEFINITIONS", "DATA_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_edtech", "EDTECH_TOOL_DEFINITIONS", "EDTECH_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_analytics", "ANALYTICS_TOOL_DEFINITIONS", "ANALYTICS_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_planning", "PLANNING_TOOL_DEFINITIONS", "PLANNING_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_communication", "COMMUNICATION_TOOL_DEFINITIONS", "COMMUNICATION_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_student", "STUDENT_TOOL_DEFINITIONS", "STUDENT_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_ai", "AI_TOOL_DEFINITIONS", "AI_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_stem", "STEM_TOOL_DEFINITIONS", "STEM_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_automation", "AUTOMATION_TOOL_DEFINITIONS", "AUTOMATION_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_behavior", "BEHAVIOR_TOOL_DEFINITIONS", "BEHAVIOR_TOOL_HANDLERS"),
    ]

    existing_names = {td["name"] for td in TOOL_DEFINITIONS}
    all_loaded = True
    import importlib
    for mod_name, defs_attr, handlers_attr in submodules:
        try:
            mod = importlib.import_module(mod_name)
            defs = getattr(mod, defs_attr, None)
            handlers = getattr(mod, handlers_attr, None)
            if defs is None or handlers is None:
                all_loaded = False
                continue
            for td in defs:
                if td["name"] not in existing_names:
                    TOOL_DEFINITIONS.append(td)
                    existing_names.add(td["name"])
            for name, handler in handlers.items():
                if name not in TOOL_HANDLERS:
                    TOOL_HANDLERS[name] = handler
        except (ImportError, AttributeError):
            all_loaded = False

    _merge_in_progress = False
    if all_loaded:
        _submodules_merged = True


# Attempt merge immediately — works when this module is loaded first (normal app startup).
# If circular import prevents full merge, execute_tool() retries via _merge_submodules().
_merge_submodules()


def execute_tool(tool_name, tool_input):
    """Execute a tool by name with the given input.

    All handlers MUST be bare functions (not lambda wrappers).
    They are called with **kwargs from tool_input.
    teacher_id is injected by the assistant route for per-teacher context;
    it's stripped before calling handlers that don't accept it.
    """
    import inspect
    _merge_submodules()  # Ensure submodule tools are registered
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        if tool_input:
            # Strip teacher_id if the handler doesn't accept it
            kwargs = dict(tool_input)
            if 'teacher_id' in kwargs:
                try:
                    sig = inspect.signature(handler)
                    if 'teacher_id' not in sig.parameters and not any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                    ):
                        kwargs.pop('teacher_id')
                except (ValueError, TypeError):
                    kwargs.pop('teacher_id', None)
            return handler(**kwargs)
        else:
            return handler()
    except Exception as e:
        return {"error": f"Tool execution error: {str(e)}"}
