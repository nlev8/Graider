"""
Storage Abstraction Layer for Graider
======================================
Provides load/save/delete/list_keys for teacher data with two backends:
  - File backend (local dev): reads/writes to ~/.graider_* files
  - Supabase backend (production): upserts to teacher_data / student_history tables

Detection: USE_SUPABASE = True when SUPABASE_URL and SUPABASE_SERVICE_KEY are set.
Local-dev (teacher_id == 'local-dev') always uses files regardless.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Environment detection (lazy — checked at call time, not import time) ──
def _is_supabase_configured():
    """Check at call time so .env has been loaded by then."""
    return bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_KEY'))

# ── Supabase client (canonical import) ────────────────────────
from backend.supabase_client import get_supabase as _get_supabase


# ── File path mapping ─────────────────────────────────────────

HOME = str(Path.home())
ASSIGNMENTS_DIR = os.path.join(HOME, ".graider_assignments")
GRAIDER_DATA_DIR = os.path.join(HOME, ".graider_data")
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")
ACCOMMODATIONS_DIR = os.path.join(GRAIDER_DATA_DIR, "accommodations")
LESSONS_DIR = os.path.join(HOME, ".graider_lessons")
STUDENT_HISTORY_DIR = os.path.join(GRAIDER_DATA_DIR, "student_history")


def _key_to_filepath(data_key):
    """Map a data_key to its existing ~/.graider_* file path.

    Key patterns:
      'settings'                   -> ~/.graider_settings.json
      'rubric'                     -> ~/.graider_rubric.json
      'results'                    -> ~/.graider_results.json
      'accommodations'             -> ~/.graider_data/accommodations/student_accommodations.json
      'accommodation_presets'      -> ~/.graider_data/accommodations/presets.json
      'ell_students'               -> ~/.graider_data/ell_students.json
      'parent_contacts'            -> ~/.graider_data/parent_contacts.json
      'assistant_memory'           -> ~/.graider_data/assistant_memory.json
      'teaching_calendar'          -> ~/.graider_data/teaching_calendar.json
      'master_grades'              -> (output_folder)/master_grades.csv  [read-only, not mapped]
      'assignment:{title}'         -> ~/.graider_assignments/{title}.json
      'period:{filename}'          -> ~/.graider_data/periods/{filename}
      'period_meta:{filename}'     -> ~/.graider_data/periods/{filename}.meta.json
      'lesson:{unit}:{title}'      -> ~/.graider_lessons/{unit}/{title}.json
    """
    if data_key == 'settings':
        return os.path.join(HOME, ".graider_settings.json")
    elif data_key == 'rubric':
        return os.path.join(HOME, ".graider_rubric.json")
    elif data_key == 'results':
        return os.path.join(HOME, ".graider_results.json")
    elif data_key == 'accommodations':
        return os.path.join(ACCOMMODATIONS_DIR, "student_accommodations.json")
    elif data_key == 'accommodation_presets':
        return os.path.join(ACCOMMODATIONS_DIR, "presets.json")
    elif data_key == 'ell_students':
        return os.path.join(GRAIDER_DATA_DIR, "ell_students.json")
    elif data_key == 'parent_contacts':
        return os.path.join(GRAIDER_DATA_DIR, "parent_contacts.json")
    elif data_key == 'assistant_memory':
        return os.path.join(GRAIDER_DATA_DIR, "assistant_memory.json")
    elif data_key == 'teaching_calendar':
        return os.path.join(GRAIDER_DATA_DIR, "teaching_calendar.json")
    elif data_key == 'api_keys':
        return os.path.join(GRAIDER_DATA_DIR, ".api_keys.json")
    elif data_key == 'portal_credentials':
        return os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")
    elif data_key.startswith('assignment:'):
        title = data_key[len('assignment:'):]
        return os.path.join(ASSIGNMENTS_DIR, f"{title}.json")
    elif data_key.startswith('period_meta:'):
        filename = data_key[len('period_meta:'):]
        return os.path.join(PERIODS_DIR, f"{filename}.meta.json")
    elif data_key.startswith('period:'):
        filename = data_key[len('period:'):]
        return os.path.join(PERIODS_DIR, filename)
    elif data_key.startswith('lesson:'):
        # lesson:{unit}:{title}
        parts = data_key.split(':', 2)
        if len(parts) == 3:
            unit = parts[1]
            title = parts[2]
            return os.path.join(LESSONS_DIR, unit, f"{title}.json")
    return None


def _use_supabase(teacher_id):
    """Determine whether to use Supabase for this request."""
    if teacher_id == 'local-dev':
        return False
    return _is_supabase_configured()


# ══════════════════════════════════════════════════════════════
# FILE BACKEND
# ══════════════════════════════════════════════════════════════

def _file_load(data_key):
    """Load data from a local file. Returns parsed JSON, or raw text for CSVs."""
    filepath = _key_to_filepath(data_key)
    if not filepath:
        return None
    if not os.path.exists(filepath):
        return None
    try:
        # CSV period files are not JSON — return raw text
        if data_key.startswith('period:') and filepath.endswith('.csv'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load file %s: %s", filepath, e)
        return None


def _file_save(data_key, data):
    """Save data to a local file. Returns True on success."""
    filepath = _key_to_filepath(data_key)
    if not filepath:
        return False
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # CSV period files are raw text, not JSON
        if data_key.startswith('period:') and filepath.endswith('.csv'):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(data if isinstance(data, str) else str(data))
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error("Failed to save file %s: %s", filepath, e)
        return False


def _file_delete(data_key):
    """Delete a local file. Returns True on success."""
    filepath = _key_to_filepath(data_key)
    if not filepath:
        return False
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        return True
    except Exception as e:
        logger.error("Failed to delete file %s: %s", filepath, e)
        return False


def _file_list_keys(prefix):
    """List data keys matching a prefix from local files."""
    keys = []

    if prefix == 'assignment:' or prefix.startswith('assignment:'):
        if os.path.exists(ASSIGNMENTS_DIR):
            for f in os.listdir(ASSIGNMENTS_DIR):
                if f.endswith('.json'):
                    name = f[:-5]  # Strip .json
                    keys.append(f"assignment:{name}")

    elif prefix == 'lesson:' or prefix.startswith('lesson:'):
        if os.path.exists(LESSONS_DIR):
            for unit_name in os.listdir(LESSONS_DIR):
                unit_path = os.path.join(LESSONS_DIR, unit_name)
                if os.path.isdir(unit_path):
                    for f in os.listdir(unit_path):
                        if f.endswith('.json'):
                            title = f[:-5]
                            keys.append(f"lesson:{unit_name}:{title}")

    elif prefix == 'period:' or prefix.startswith('period:'):
        if os.path.exists(PERIODS_DIR):
            for f in os.listdir(PERIODS_DIR):
                if f.endswith('.csv'):
                    keys.append(f"period:{f}")

    elif prefix == 'period_meta:' or prefix.startswith('period_meta:'):
        if os.path.exists(PERIODS_DIR):
            for f in os.listdir(PERIODS_DIR):
                if f.endswith('.meta.json'):
                    # Strip .meta.json to get original filename
                    orig = f[:-10]
                    keys.append(f"period_meta:{orig}")

    return sorted(keys)


# ══════════════════════════════════════════════════════════════
# SUPABASE BACKEND
# ══════════════════════════════════════════════════════════════

def _sb_load(data_key, teacher_id):
    """Load data from Supabase teacher_data table. Retries once on transient errors."""
    import time as _time
    for attempt in range(3):
        try:
            sb = _get_supabase()
            if not sb:
                return None
            result = sb.table('teacher_data') \
                .select('data') \
                .eq('teacher_id', teacher_id) \
                .eq('data_key', data_key) \
                .execute()
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            if attempt < 2 and 'Resource temporarily unavailable' in str(e):
                _time.sleep(0.5 * (attempt + 1))
                continue
            logger.error("Supabase load failed for key=%s teacher=%s: %s", data_key, teacher_id, e)
            return None


def _sb_save(data_key, data, teacher_id):
    """Upsert data to Supabase teacher_data table. Retries once on transient errors."""
    import time as _time
    for attempt in range(3):
        try:
            sb = _get_supabase()
            if not sb:
                return False
            sb.table('teacher_data').upsert({
                'teacher_id': teacher_id,
                'data_key': data_key,
                'data': data,
                'updated_at': datetime.utcnow().isoformat(),
            }).execute()
            return True
        except Exception as e:
            if attempt < 2 and 'Resource temporarily unavailable' in str(e):
                _time.sleep(0.5 * (attempt + 1))
                continue
            logger.error("Supabase save failed for key=%s teacher=%s: %s", data_key, teacher_id, e)
            return False


def _sb_delete(data_key, teacher_id):
    """Delete a row from Supabase teacher_data table. Retries once on transient errors."""
    import time as _time
    for attempt in range(3):
        try:
            sb = _get_supabase()
            if not sb:
                return False
            sb.table('teacher_data') \
                .delete() \
                .eq('teacher_id', teacher_id) \
                .eq('data_key', data_key) \
                .execute()
            return True
        except Exception as e:
            if attempt < 2 and 'Resource temporarily unavailable' in str(e):
                _time.sleep(0.5 * (attempt + 1))
                continue
            logger.error("Supabase delete failed for key=%s teacher=%s: %s", data_key, teacher_id, e)
            return False


def _sb_list_keys(prefix, teacher_id):
    """List data keys matching a prefix from Supabase. Retries once on transient errors."""
    import time as _time
    for attempt in range(3):
        try:
            sb = _get_supabase()
            if not sb:
                return []
            result = sb.table('teacher_data') \
                .select('data_key') \
                .eq('teacher_id', teacher_id) \
                .like('data_key', f"{prefix}%") \
                .execute()
            return sorted([row['data_key'] for row in result.data]) if result.data else []
        except Exception as e:
            if attempt < 2 and 'Resource temporarily unavailable' in str(e):
                _time.sleep(0.5 * (attempt + 1))
                continue
            logger.error("Supabase list_keys failed for prefix=%s teacher=%s: %s", prefix, teacher_id, e)
            return []


# ══════════════════════════════════════════════════════════════
# STUDENT HISTORY (separate table)
# ══════════════════════════════════════════════════════════════

def _file_load_student_history(student_id):
    """Load student history from local file."""
    safe_id = str(student_id).replace('/', '_').replace('\\', '_')
    filepath = os.path.join(STUDENT_HISTORY_DIR, f"{safe_id}.json")
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _file_save_student_history(student_id, history):
    """Save student history to local file."""
    safe_id = str(student_id).replace('/', '_').replace('\\', '_')
    os.makedirs(STUDENT_HISTORY_DIR, exist_ok=True)
    filepath = os.path.join(STUDENT_HISTORY_DIR, f"{safe_id}.json")
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        return True
    except Exception as e:
        logger.error("Failed to save student history file %s: %s", filepath, e)
        return False


def _sb_load_student_history(teacher_id, student_id):
    """Load student history from Supabase. Retries once on transient errors."""
    import time as _time
    for attempt in range(3):
        try:
            sb = _get_supabase()
            if not sb:
                return None
            result = sb.table('student_history') \
                .select('history') \
                .eq('teacher_id', teacher_id) \
                .eq('student_id', student_id) \
                .execute()
            if result.data and len(result.data) > 0:
                return result.data[0]['history']
            return None
        except Exception as e:
            if attempt < 2 and 'Resource temporarily unavailable' in str(e):
                _time.sleep(0.5 * (attempt + 1))
                continue
            logger.error("Supabase load student_history failed: %s", e)
            return None


def _sb_save_student_history(teacher_id, student_id, history):
    """Upsert student history to Supabase. Retries once on transient errors."""
    import time as _time
    for attempt in range(3):
        try:
            sb = _get_supabase()
            if not sb:
                return False
            sb.table('student_history').upsert({
                'teacher_id': teacher_id,
                'student_id': student_id,
                'history': history,
                'updated_at': datetime.utcnow().isoformat(),
            }).execute()
            return True
        except Exception as e:
            if attempt < 2 and 'Resource temporarily unavailable' in str(e):
                _time.sleep(0.5 * (attempt + 1))
                continue
            logger.error("Supabase save student_history failed: %s", e)
            return False


# ══════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════

def load(data_key, teacher_id='local-dev'):
    """Load teacher data by key.

    Args:
        data_key: Key identifying the data (e.g. 'settings', 'assignment:Unit 3')
        teacher_id: Teacher's Supabase UUID, or 'local-dev' for file backend

    Returns:
        Parsed JSON data (dict or list), or None if not found.
    """
    if _use_supabase(teacher_id):
        result = _sb_load(data_key, teacher_id)
        if result is not None:
            return result
        # Don't fall back to shared file for sensitive keys (prevents cross-teacher leakage)
        if data_key in _SENSITIVE_KEYS:
            return None
        # Fallback: try local file (covers first-time migration)
        return _file_load(data_key)
    return _file_load(data_key)


_SENSITIVE_KEYS = {'api_keys', 'portal_credentials'}


def save(data_key, data, teacher_id='local-dev'):
    """Save teacher data by key. Dual-writes to both file and Supabase when applicable.

    Args:
        data_key: Key identifying the data
        data: JSON-serializable data (dict or list)
        teacher_id: Teacher's Supabase UUID, or 'local-dev' for file backend

    Returns:
        True on success.
    """
    if _use_supabase(teacher_id):
        sb_ok = _sb_save(data_key, data, teacher_id)
        # Skip file write for sensitive data when not local-dev
        # to prevent different teachers from overwriting each other's secrets
        if data_key not in _SENSITIVE_KEYS:
            _file_save(data_key, data)
        return sb_ok

    # Local-dev: file only
    return _file_save(data_key, data)


def delete(data_key, teacher_id='local-dev'):
    """Delete teacher data by key.

    Returns:
        True on success.
    """
    file_ok = _file_delete(data_key)

    if _use_supabase(teacher_id):
        sb_ok = _sb_delete(data_key, teacher_id)
        return sb_ok
    return file_ok


def list_keys(prefix, teacher_id='local-dev'):
    """List data keys matching a prefix.

    Args:
        prefix: Key prefix (e.g. 'assignment:', 'lesson:')
        teacher_id: Teacher's Supabase UUID

    Returns:
        Sorted list of matching data_key strings.
    """
    if _use_supabase(teacher_id):
        keys = _sb_list_keys(prefix, teacher_id)
        if keys:
            return keys
        # Fallback to files if Supabase returns empty (pre-migration)
        return _file_list_keys(prefix)
    return _file_list_keys(prefix)


def load_student_history(teacher_id='local-dev', student_id=None):
    """Load a student's grading history.

    Args:
        teacher_id: Teacher's Supabase UUID
        student_id: Student identifier

    Returns:
        History dict, or None.
    """
    if not student_id:
        return None
    if _use_supabase(teacher_id):
        result = _sb_load_student_history(teacher_id, student_id)
        if result is not None:
            return result
        # Fallback to local file
        return _file_load_student_history(student_id)
    return _file_load_student_history(student_id)


def save_student_history(teacher_id='local-dev', student_id=None, history=None):
    """Save a student's grading history. Dual-writes.

    Returns:
        True on success.
    """
    if not student_id or history is None:
        return False

    # Always write local file
    _file_save_student_history(student_id, history)

    if _use_supabase(teacher_id):
        return _sb_save_student_history(teacher_id, student_id, history)
    return True


# ══════════════════════════════════════════════════════════════
# SYNC: Upload all local files to Supabase for a teacher
# ══════════════════════════════════════════════════════════════

def sync_all_to_cloud(teacher_id):
    """Upload all local ~/.graider_* data to Supabase for the given teacher.

    Returns:
        Summary dict of what was synced.
    """
    if not teacher_id or teacher_id == 'local-dev':
        return {"error": "Cannot sync without a valid teacher ID (must be logged in)"}

    summary = {}

    # Single-key data files
    single_keys = [
        'settings', 'rubric', 'results', 'accommodations',
        'accommodation_presets', 'ell_students', 'parent_contacts',
        'assistant_memory', 'teaching_calendar',
    ]

    for key in single_keys:
        data = _file_load(key)
        if data is not None:
            ok = _sb_save(key, data, teacher_id)
            summary[key] = "synced" if ok else "failed"
        else:
            summary[key] = "no local data"

    # Assignments
    assignment_keys = _file_list_keys('assignment:')
    synced_assignments = 0
    for key in assignment_keys:
        data = _file_load(key)
        if data is not None:
            _sb_save(key, data, teacher_id)
            synced_assignments += 1
    summary['assignments'] = f"{synced_assignments} synced"

    # Lessons
    lesson_keys = _file_list_keys('lesson:')
    synced_lessons = 0
    for key in lesson_keys:
        data = _file_load(key)
        if data is not None:
            _sb_save(key, data, teacher_id)
            synced_lessons += 1
    summary['lessons'] = f"{synced_lessons} synced"

    # Period metadata
    period_meta_keys = _file_list_keys('period_meta:')
    synced_periods = 0
    for key in period_meta_keys:
        data = _file_load(key)
        if data is not None:
            _sb_save(key, data, teacher_id)
            synced_periods += 1
    summary['periods'] = f"{synced_periods} synced"

    # Period CSV data (store as JSON with rows)
    period_keys = _file_list_keys('period:')
    for key in period_keys:
        filename = key[len('period:'):]
        filepath = os.path.join(PERIODS_DIR, filename)
        if os.path.exists(filepath):
            try:
                import csv as csv_mod
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv_mod.DictReader(f)
                    rows = list(reader)
                    headers = reader.fieldnames or []
                _sb_save(key, {"headers": headers, "rows": rows}, teacher_id)
            except Exception as e:
                logger.warning("Failed to sync period CSV %s: %s", key, e)

    # Student history
    history_dir = STUDENT_HISTORY_DIR
    synced_history = 0
    if os.path.exists(history_dir):
        for f in os.listdir(history_dir):
            if f.endswith('.json'):
                student_id = f[:-5]
                try:
                    with open(os.path.join(history_dir, f), 'r', encoding='utf-8') as fh:
                        history = json.load(fh)
                    _sb_save_student_history(teacher_id, student_id, history)
                    synced_history += 1
                except Exception:
                    pass
    summary['student_history'] = f"{synced_history} synced"

    return summary
