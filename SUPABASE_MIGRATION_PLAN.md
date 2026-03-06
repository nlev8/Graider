# Migrate Graider Persistence to Supabase

## Context

All teacher data (grades, settings, rubric, assignments, student history, accommodations, rosters, calendar, etc.) is stored as JSON files under `~/.graider_*`. Railway's filesystem is ephemeral — data vanishes on every deploy/restart. Supabase is already integrated for auth and student portal tables. This migration adds a storage abstraction so production reads/writes Supabase while local dev keeps using files.

---

## Schema: Two Supabase Tables

Run this SQL in the Supabase dashboard (SQL Editor).

**File: `backend/database/supabase_teacher_schema.sql`** (NEW)

```sql
-- KV store for all per-teacher JSON blobs
CREATE TABLE IF NOT EXISTS teacher_data (
    teacher_id  TEXT NOT NULL,
    data_key    TEXT NOT NULL,
    data        JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (teacher_id, data_key)
);

-- Per-student history (N rows per teacher)
CREATE TABLE IF NOT EXISTS student_history_cloud (
    teacher_id  TEXT NOT NULL,
    student_id  TEXT NOT NULL,
    history     JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (teacher_id, student_id)
);

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER teacher_data_updated_at
    BEFORE UPDATE ON teacher_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER student_history_cloud_updated_at
    BEFORE UPDATE ON student_history_cloud
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS (service role gets full access)
ALTER TABLE teacher_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_history_cloud ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_teacher_data" ON teacher_data
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_student_history" ON student_history_cloud
    FOR ALL USING (true) WITH CHECK (true);

-- Index for prefix queries (list_keys)
CREATE INDEX idx_teacher_data_prefix ON teacher_data (teacher_id, data_key text_pattern_ops);
```

**data_key values:**

| Key | Local file |
|---|---|
| `settings` | `~/.graider_settings.json` |
| `global_settings` | `~/.graider_global_settings.json` |
| `rubric` | `~/.graider_rubric.json` |
| `results` | `~/.graider_results.json` |
| `accommodations` | `~/.graider_data/accommodations/student_accommodations.json` |
| `accommodation_presets` | `~/.graider_data/accommodations/presets.json` |
| `ell_students` | `~/.graider_data/ell_students.json` |
| `parent_contacts` | `~/.graider_data/parent_contacts.json` |
| `assistant_memory` | `~/.graider_data/assistant_memory.json` |
| `teaching_calendar` | `~/.graider_data/teaching_calendar.json` |
| `email_config` | `~/.graider_email_config.json` |
| `master_grades` | `~/Downloads/Graider/Results/master_grades.csv` (stored as JSON array) |
| `assignment:{safe_title}` | `~/.graider_assignments/{safe_title}.json` |
| `period:{filename}` | `~/.graider_data/periods/{filename}` (CSV parsed to JSON) |
| `period_meta:{filename}` | `~/.graider_data/periods/{filename}.meta.json` |
| `lesson:{unit}:{title}` | `~/.graider_lessons/{unit}/{title}.json` |

---

## Step 1: Create `backend/storage.py` (NEW FILE)

```python
"""
Storage abstraction for Graider.
Local dev: reads/writes JSON files under ~/.graider_*
Production: reads/writes Supabase teacher_data and student_history_cloud tables.
"""
import csv
import io
import os
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Use Supabase when both URL and key are configured
USE_SUPABASE = bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_KEY'))

_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_KEY')
        )
    return _supabase_client


def _use_cloud(teacher_id):
    """True if we should use Supabase for this request."""
    return USE_SUPABASE and teacher_id and teacher_id != 'local-dev'


# ═══════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════

def load(data_key: str, teacher_id: str = 'local-dev') -> Optional[Any]:
    """Load data for a teacher. Returns parsed Python object or None."""
    if _use_cloud(teacher_id):
        result = _load_supabase(data_key, teacher_id)
        if result is not None:
            return result
    return _load_file(data_key)


def save(data_key: str, data: Any, teacher_id: str = 'local-dev') -> bool:
    """Save data for a teacher. Returns True on success."""
    # Always write to file (keeps local files in sync for dev)
    file_ok = _save_file(data_key, data)
    if _use_cloud(teacher_id):
        return _save_supabase(data_key, data, teacher_id)
    return file_ok


def delete(data_key: str, teacher_id: str = 'local-dev') -> bool:
    """Delete data for a teacher."""
    # Delete local file
    path = _key_to_filepath(data_key)
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
    if _use_cloud(teacher_id):
        try:
            sb = _get_supabase()
            sb.table('teacher_data').delete() \
                .eq('teacher_id', teacher_id) \
                .eq('data_key', data_key) \
                .execute()
            return True
        except Exception as e:
            logger.error("Supabase delete error [%s]: %s", data_key, e)
            return False
    return True


def list_keys(prefix: str, teacher_id: str = 'local-dev') -> list:
    """List all data_keys matching a prefix. Returns list of (key, data) tuples."""
    if _use_cloud(teacher_id):
        result = _list_supabase(prefix, teacher_id)
        if result:
            return result
    return _list_file(prefix)


def load_student_hist(teacher_id: str, student_id: str) -> Optional[dict]:
    """Load a single student's history."""
    if _use_cloud(teacher_id):
        try:
            sb = _get_supabase()
            result = sb.table('student_history_cloud') \
                .select('history') \
                .eq('teacher_id', teacher_id) \
                .eq('student_id', student_id) \
                .execute()
            if result.data:
                return result.data[0]['history']
        except Exception as e:
            logger.error("load_student_hist error: %s", e)
    return None  # Caller falls back to file


def save_student_hist(teacher_id: str, student_id: str, history: dict) -> bool:
    """Save a single student's history."""
    if _use_cloud(teacher_id):
        try:
            sb = _get_supabase()
            sb.table('student_history_cloud').upsert({
                'teacher_id': teacher_id,
                'student_id': student_id,
                'history': history,
            }).execute()
            return True
        except Exception as e:
            logger.error("save_student_hist error: %s", e)
            return False
    return False  # Caller falls back to file


# ═══════════════════════════════════════════════════════
# FILE BACKEND (local dev)
# ═══════════════════════════════════════════════════════

_HOME = os.path.expanduser('~')
_DATA = os.path.join(_HOME, '.graider_data')

_STATIC_KEYS = {
    'settings':              os.path.join(_HOME, '.graider_settings.json'),
    'global_settings':       os.path.join(_HOME, '.graider_global_settings.json'),
    'rubric':                os.path.join(_HOME, '.graider_rubric.json'),
    'results':               os.path.join(_HOME, '.graider_results.json'),
    'email_config':          os.path.join(_HOME, '.graider_email_config.json'),
    'accommodations':        os.path.join(_DATA, 'accommodations', 'student_accommodations.json'),
    'accommodation_presets': os.path.join(_DATA, 'accommodations', 'presets.json'),
    'ell_students':          os.path.join(_DATA, 'ell_students.json'),
    'parent_contacts':       os.path.join(_DATA, 'parent_contacts.json'),
    'assistant_memory':      os.path.join(_DATA, 'assistant_memory.json'),
    'teaching_calendar':     os.path.join(_DATA, 'teaching_calendar.json'),
}


def _key_to_filepath(data_key: str) -> Optional[str]:
    """Resolve a data_key to its local file path."""
    if data_key in _STATIC_KEYS:
        return _STATIC_KEYS[data_key]
    if data_key == 'master_grades':
        # master_grades is stored as CSV on disk but JSON in Supabase
        # For file backend, return None — _load_master_csv handles its own CSV parsing
        return None
    if data_key.startswith('assignment:'):
        safe = data_key[len('assignment:'):]
        return os.path.join(_HOME, '.graider_assignments', f'{safe}.json')
    if data_key.startswith('period_meta:'):
        filename = data_key[len('period_meta:'):]
        return os.path.join(_DATA, 'periods', f'{filename}.meta.json')
    if data_key.startswith('period:'):
        filename = data_key[len('period:'):]
        return os.path.join(_DATA, 'periods', filename)
    if data_key.startswith('lesson:'):
        parts = data_key.split(':', 2)
        if len(parts) == 3:
            _, unit, title = parts
            return os.path.join(_HOME, '.graider_lessons', unit, f'{title}.json')
    return None


def _load_file(data_key: str) -> Optional[Any]:
    path = _key_to_filepath(data_key)
    if not path or not os.path.exists(path):
        return None
    try:
        # CSV period files → parse to list of dicts
        if path.endswith('.csv'):
            with open(path, 'r', encoding='utf-8') as f:
                return list(csv.DictReader(f))
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning("File load error for %s: %s", data_key, e)
        return None


def _save_file(data_key: str, data: Any) -> bool:
    path = _key_to_filepath(data_key)
    if not path:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # If it's a CSV period file, write as CSV
        if path.endswith('.csv') and isinstance(data, list) and data:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return True
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error("File save error for %s: %s", data_key, e)
        return False


def _list_file(prefix: str) -> list:
    """List (key, data) tuples for keys matching prefix from local files."""
    results = []
    if prefix == 'assignment:':
        adir = os.path.join(_HOME, '.graider_assignments')
        if os.path.exists(adir):
            for f in sorted(os.listdir(adir)):
                if f.endswith('.json'):
                    key = f'assignment:{f[:-5]}'
                    data = _load_file(key)
                    if data:
                        results.append((key, data))
    elif prefix == 'lesson:':
        ldir = os.path.join(_HOME, '.graider_lessons')
        if os.path.exists(ldir):
            for unit in sorted(os.listdir(ldir)):
                unit_path = os.path.join(ldir, unit)
                if os.path.isdir(unit_path):
                    for f in sorted(os.listdir(unit_path)):
                        if f.endswith('.json'):
                            key = f'lesson:{unit}:{f[:-5]}'
                            data = _load_file(key)
                            if data:
                                results.append((key, data))
    elif prefix == 'period:':
        pdir = os.path.join(_DATA, 'periods')
        if os.path.exists(pdir):
            for f in sorted(os.listdir(pdir)):
                if f.endswith('.csv'):
                    key = f'period:{f}'
                    data = _load_file(key)
                    if data:
                        results.append((key, data))
    elif prefix == 'period_meta:':
        pdir = os.path.join(_DATA, 'periods')
        if os.path.exists(pdir):
            for f in sorted(os.listdir(pdir)):
                if f.endswith('.meta.json'):
                    csv_name = f.replace('.meta.json', '')
                    key = f'period_meta:{csv_name}'
                    data = _load_file(key)
                    if data:
                        results.append((key, data))
    return results


# ═══════════════════════════════════════════════════════
# SUPABASE BACKEND
# ═══════════════════════════════════════════════════════

def _load_supabase(data_key: str, teacher_id: str) -> Optional[Any]:
    try:
        sb = _get_supabase()
        result = sb.table('teacher_data') \
            .select('data') \
            .eq('teacher_id', teacher_id) \
            .eq('data_key', data_key) \
            .execute()
        if result.data:
            return result.data[0]['data']
        return None
    except Exception as e:
        logger.error("Supabase load error [%s]: %s", data_key, e)
        return None


def _save_supabase(data_key: str, data: Any, teacher_id: str) -> bool:
    try:
        sb = _get_supabase()
        sb.table('teacher_data').upsert({
            'teacher_id': teacher_id,
            'data_key': data_key,
            'data': data,
        }).execute()
        return True
    except Exception as e:
        logger.error("Supabase save error [%s]: %s", data_key, e)
        return False


def _list_supabase(prefix: str, teacher_id: str) -> list:
    """List (key, data) tuples for keys matching prefix from Supabase."""
    try:
        sb = _get_supabase()
        result = sb.table('teacher_data') \
            .select('data_key, data') \
            .eq('teacher_id', teacher_id) \
            .like('data_key', prefix + '%') \
            .execute()
        return [(row['data_key'], row['data']) for row in (result.data or [])]
    except Exception as e:
        logger.error("Supabase list error [%s]: %s", prefix, e)
        return []
```

---

## Step 2: Migrate `backend/routes/settings_routes.py`

### 2a. `save_rubric()` (line 143)

**Find:**
```python
@settings_bp.route('/api/save-rubric', methods=['POST'])
def save_rubric():
    """Save rubric configuration to JSON file."""
    data = request.json
    rubric_path = os.path.expanduser("~/.graider_rubric.json")
    try:
        with open(rubric_path, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@settings_bp.route('/api/save-rubric', methods=['POST'])
def save_rubric():
    """Save rubric configuration."""
    data = request.json
    teacher_id = getattr(g, 'user_id', 'local-dev')
    try:
        from backend import storage
        storage.save('rubric', data, teacher_id)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

### 2b. `load_rubric()` (line 156)

**Find:**
```python
@settings_bp.route('/api/load-rubric')
def load_rubric():
    """Load rubric configuration from JSON file."""
    rubric_path = os.path.expanduser("~/.graider_rubric.json")
    if not os.path.exists(rubric_path):
        return jsonify({"rubric": None})
    try:
        with open(rubric_path, 'r') as f:
            data = json.load(f)
        return jsonify({"rubric": data})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@settings_bp.route('/api/load-rubric')
def load_rubric():
    """Load rubric configuration."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend import storage
    data = storage.load('rubric', teacher_id)
    return jsonify({"rubric": data})
```

### 2c. `save_global_settings()` (line 173)

**Find:**
```python
@settings_bp.route('/api/save-global-settings', methods=['POST'])
def save_global_settings():
    """Save global AI notes and settings."""
    data = request.json
    settings_path = os.path.expanduser("~/.graider_settings.json")
    try:
        with open(settings_path, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@settings_bp.route('/api/save-global-settings', methods=['POST'])
def save_global_settings():
    """Save global AI notes and settings."""
    data = request.json
    teacher_id = getattr(g, 'user_id', 'local-dev')
    try:
        from backend import storage
        storage.save('settings', data, teacher_id)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

### 2d. `load_global_settings()` (line 186)

**Find:**
```python
@settings_bp.route('/api/load-global-settings')
def load_global_settings():
    """Load global AI notes and settings."""
    settings_path = os.path.expanduser("~/.graider_settings.json")
    if not os.path.exists(settings_path):
        return jsonify({"settings": None})
    try:
        with open(settings_path, 'r') as f:
            data = json.load(f)
        return jsonify({"settings": data})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@settings_bp.route('/api/load-global-settings')
def load_global_settings():
    """Load global AI notes and settings."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend import storage
    data = storage.load('settings', teacher_id)
    return jsonify({"settings": data})
```

### 2e. Add import at top of settings_routes.py

Add `from flask import g` to the existing imports if not already present.

---

## Step 3: Migrate `backend/routes/assignment_routes.py`

### 3a. `save_assignment_config()` (line 14)

**Find:**
```python
@assignment_bp.route('/api/save-assignment-config', methods=['POST'])
def save_assignment_config():
    data = request.json
    os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)
    title = data.get('title', 'Untitled')
    safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
    filepath = os.path.join(ASSIGNMENTS_DIR, f"{safe_title}.json")
    try:
        existing = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, Exception):
                existing = {}
        merged = {**existing, **data}
        with open(filepath, 'w') as f:
            json.dump(merged, f, indent=2)
        return jsonify({"status": "saved", "path": filepath})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@assignment_bp.route('/api/save-assignment-config', methods=['POST'])
def save_assignment_config():
    data = request.json
    teacher_id = getattr(g, 'user_id', 'local-dev')
    title = data.get('title', 'Untitled')
    safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
    key = f'assignment:{safe_title}'
    try:
        from backend import storage
        existing = storage.load(key, teacher_id) or {}
        merged = {**existing, **data}
        storage.save(key, merged, teacher_id)
        return jsonify({"status": "saved", "path": key})
    except Exception as e:
        return jsonify({"error": str(e)})
```

### 3b. `list_assignments()` (line 126)

**Find:**
```python
@assignment_bp.route('/api/list-assignments')
def list_assignments():
    if not os.path.exists(ASSIGNMENTS_DIR):
        return jsonify({"assignments": [], "assignmentData": {}})
    files_with_mtime = []
    assignment_data = {}
    for f in os.listdir(ASSIGNMENTS_DIR):
        if f.endswith('.json'):
            name = f.replace('.json', '')
            filepath = os.path.join(ASSIGNMENTS_DIR, f)
            mtime = os.path.getmtime(filepath)
            files_with_mtime.append((name, mtime))
            try:
                with open(filepath, 'r') as af:
                    data = json.load(af)
```

**Replace with:**
```python
@assignment_bp.route('/api/list-assignments')
def list_assignments():
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend import storage
    entries = storage.list_keys('assignment:', teacher_id)
    if not entries:
        return jsonify({"assignments": [], "assignmentData": {}})
    files_with_mtime = []
    assignment_data = {}
    for key, data in entries:
        name = key[len('assignment:'):]
        files_with_mtime.append((name, 0))  # No mtime from Supabase
        try:
```

And update the inner block that reads `data` — since `data` is already loaded from `entries`, replace the `with open(filepath, 'r') as af: data = json.load(af)` block. The rest of the function body that uses `data` stays the same.

### 3c. `load_assignment()` (line 166)

**Find:**
```python
@assignment_bp.route('/api/load-assignment')
def load_assignment():
    name = request.args.get('name', '')
    filepath = os.path.join(ASSIGNMENTS_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        return jsonify({"error": "Assignment not found"})
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return jsonify({"assignment": data})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@assignment_bp.route('/api/load-assignment')
def load_assignment():
    name = request.args.get('name', '')
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend import storage
    data = storage.load(f'assignment:{name}', teacher_id)
    if data is None:
        return jsonify({"error": "Assignment not found"})
    return jsonify({"assignment": data})
```

### 3d. `delete_assignment()` (line 183)

**Find:**
```python
@assignment_bp.route('/api/delete-assignment', methods=['DELETE'])
def delete_assignment():
    name = request.args.get('name', '')
    filepath = os.path.join(ASSIGNMENTS_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        return jsonify({"error": "Assignment not found"})
    try:
        os.remove(filepath)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**Replace with:**
```python
@assignment_bp.route('/api/delete-assignment', methods=['DELETE'])
def delete_assignment():
    name = request.args.get('name', '')
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend import storage
    storage.delete(f'assignment:{name}', teacher_id)
    return jsonify({"status": "deleted"})
```

### 3e. Add import at top

Add `from flask import g` to existing imports.

---

## Step 4: Migrate `backend/services/assistant_tools.py`

### 4a. `_load_results()` (line 160)

**Find:**
```python
def _load_results():
    """Load grading results from the results JSON file."""
    if not os.path.exists(RESULTS_FILE):
        return []
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []
```

**Replace with:**
```python
def _load_results(teacher_id='local-dev'):
    """Load grading results."""
    from backend import storage
    data = storage.load('results', teacher_id)
    if data is not None:
        return data
    # File fallback
    if not os.path.exists(RESULTS_FILE):
        return []
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []
```

### 4b. `_load_settings()` (line 1829)

**Find:**
```python
def _load_settings():
    """Load teacher settings (subject, state, grade level, AI notes)."""
    settings_path = SETTINGS_FILE
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}
```

**Replace with:**
```python
def _load_settings(teacher_id='local-dev'):
    """Load teacher settings (subject, state, grade level, AI notes)."""
    from backend import storage
    data = storage.load('global_settings', teacher_id)
    if data is not None:
        return data
    # File fallback
    settings_path = SETTINGS_FILE
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}
```

### 4c. `_load_calendar()` and `_save_calendar()` (line 3148)

**Find:**
```python
def _load_calendar():
    """Load calendar data from disk."""
    if not os.path.exists(CALENDAR_FILE):
        return {"scheduled_lessons": [], "holidays": [], "school_days": {}}
    try:
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"scheduled_lessons": [], "holidays": [], "school_days": {}}


def _save_calendar(data):
    """Persist calendar data to disk."""
    os.makedirs(os.path.dirname(CALENDAR_FILE), exist_ok=True)
    with open(CALENDAR_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
```

**Replace with:**
```python
def _load_calendar(teacher_id='local-dev'):
    """Load calendar data."""
    from backend import storage
    data = storage.load('teaching_calendar', teacher_id)
    if data is not None:
        return data
    # File fallback
    if not os.path.exists(CALENDAR_FILE):
        return {"scheduled_lessons": [], "holidays": [], "school_days": {}}
    try:
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"scheduled_lessons": [], "holidays": [], "school_days": {}}


def _save_calendar(data, teacher_id='local-dev'):
    """Persist calendar data."""
    from backend import storage
    storage.save('teaching_calendar', data, teacher_id)
```

### 4d. `_load_parent_contacts()` (line 2285)

**Find:**
```python
def _load_parent_contacts():
    """Load parent contacts keyed by student ID."""
    if not os.path.exists(PARENT_CONTACTS_FILE):
        return {}
    try:
        with open(PARENT_CONTACTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
```

**Replace with:**
```python
def _load_parent_contacts(teacher_id='local-dev'):
    """Load parent contacts keyed by student ID."""
    from backend import storage
    data = storage.load('parent_contacts', teacher_id)
    if data is not None:
        return data
    if not os.path.exists(PARENT_CONTACTS_FILE):
        return {}
    try:
        with open(PARENT_CONTACTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
```

### 4e. `_load_memories()` and `_save_memories()` (line 3536)

**Find:**
```python
def _load_memories():
    """Load saved memories from disk. Returns list of fact strings."""
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_memories(memories):
    """Persist memories list to disk."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memories, f, indent=2)
```

**Replace with:**
```python
def _load_memories(teacher_id='local-dev'):
    """Load saved memories. Returns list of fact strings."""
    from backend import storage
    data = storage.load('assistant_memory', teacher_id)
    if data is not None:
        return data if isinstance(data, list) else []
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_memories(memories, teacher_id='local-dev'):
    """Persist memories list."""
    from backend import storage
    storage.save('assistant_memory', memories, teacher_id)
```

### 4f. `_load_accommodations()` (line 1808)

**Find:**
```python
def _load_accommodations():
    """Load student accommodation data (IEP/504 presets)."""
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
```

**Replace with:**
```python
def _load_accommodations(teacher_id='local-dev'):
    """Load student accommodation data (IEP/504 presets)."""
    from backend import storage
    data = storage.load('accommodations', teacher_id)
    if data is not None:
        return data
    # File fallback — reads per-student JSON files from ACCOMMODATIONS_DIR
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
```

### 4g. `_load_saved_assignments()` (line 2546)

**Find:**
```python
def _load_saved_assignments():
    """Load saved assignment configs from ~/.graider_assignments/.
    Returns list of dicts with normalized name and display title."""
    saved = []
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
            })
        except Exception:
            pass
    return saved
```

**Replace with:**
```python
def _load_saved_assignments(teacher_id='local-dev'):
    """Load saved assignment configs.
    Returns list of dicts with normalized name and display title."""
    from backend import storage
    entries = storage.list_keys('assignment:', teacher_id)
    if entries:
        saved = []
        for key, data in entries:
            title = data.get('title', key.replace('assignment:', ''))
            saved.append({
                "title": title,
                "norm": _normalize_assignment_name(title),
            })
        return saved
    # File fallback
    saved = []
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
            })
        except Exception:
            pass
    return saved
```

### 4h. `_load_email_config()` (line 3871)

**Find:**
```python
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
```

**Replace with:**
```python
def _load_email_config(teacher_id='local-dev'):
    """Load teacher email config (teacher_name, teacher_email, signature)."""
    from backend import storage
    data = storage.load('email_config', teacher_id)
    if data is not None:
        return data
    config_path = os.path.expanduser("~/.graider_email_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}
```

### 4i. `_load_master_csv()` (line 184)

This function is complex — it reads a CSV file AND merges with `_load_results()`. Add `teacher_id` param and pass it through.

**Find (line 184):**
```python
def _load_master_csv(period_filter='all'):
```

**Replace with:**
```python
def _load_master_csv(period_filter='all', teacher_id='local-dev'):
```

**Find (line 240, inside the function):**
```python
    results_json = _load_results()
```

**Replace with:**
```python
    results_json = _load_results(teacher_id)
```

### 4j. `execute_tool()` — thread teacher_id (line 4302)

**Find:**
```python
def execute_tool(tool_name, tool_input):
    """Execute a tool by name with the given input."""
    _merge_submodules()  # Ensure submodule tools are registered
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return handler(**tool_input)
    except Exception as e:
        return {"error": f"Tool execution error: {str(e)}"}
```

**Replace with:**
```python
def execute_tool(tool_name, tool_input, teacher_id='local-dev'):
    """Execute a tool by name with the given input."""
    _merge_submodules()  # Ensure submodule tools are registered
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        # Inject teacher_id for storage-aware tools
        import inspect
        sig = inspect.signature(handler)
        if 'teacher_id' in sig.parameters:
            tool_input = {**tool_input, 'teacher_id': teacher_id}
        return handler(**tool_input)
    except Exception as e:
        return {"error": f"Tool execution error: {str(e)}"}
```

---

## Step 5: Migrate `backend/routes/assistant_routes.py`

### 5a. Pass `teacher_id` to `execute_tool()` (line 1504)

**Find:**
```python
                    result = execute_tool(tb["name"], tool_input)
```

**Replace with:**
```python
                    result = execute_tool(tb["name"], tool_input, teacher_id=teacher_id)
```

### 5b. Capture `teacher_id` at the start of `generate()` SSE function

Inside the `assistant_chat()` endpoint, at the top of the `generate()` inner function, add:

```python
        teacher_id = getattr(g, 'user_id', 'local-dev')
```

This must be captured **before** the generator yields, because `g` is only valid during the request context.

### 5c. Migrate `_build_system_prompt()` (line 702)

**Find (lines 715–731):**
```python
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
```

**Replace with:**
```python
    from backend import storage
    teacher_id = getattr(g, 'user_id', 'local-dev')
    settings = storage.load('settings', teacher_id)
    if settings:
        try:
```

And remove the file open/json.load — `settings` is already a dict from `storage.load()`.

---

## Step 6: Migrate `backend/student_history.py`

### 6a. `load_student_history()` (line 44)

**Find:**
```python
def load_student_history(student_id: str) -> dict:
    """
    Load a student's complete grading history.
    Returns dict with: assignments, skill_scores, streaks, last_updated
    """
    if not student_id or student_id == "UNKNOWN":
        return None
    path = get_student_history_path(student_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "student_id": student_id,
        "assignments": [],
        "skill_scores": {},
        "streaks": {},
        "patterns": [],
        "last_updated": None
    }
```

**Replace with:**
```python
def load_student_history(student_id: str, teacher_id: str = 'local-dev') -> dict:
    """
    Load a student's complete grading history.
    Returns dict with: assignments, skill_scores, streaks, last_updated
    """
    if not student_id or student_id == "UNKNOWN":
        return None
    # Try Supabase first
    from backend import storage
    cloud = storage.load_student_hist(teacher_id, student_id)
    if cloud is not None:
        return cloud
    # File fallback
    path = get_student_history_path(student_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "student_id": student_id,
        "assignments": [],
        "skill_scores": {},
        "streaks": {},
        "patterns": [],
        "last_updated": None
    }
```

### 6b. `save_student_history()` (line 75)

**Find:**
```python
def save_student_history(student_id: str, history: dict):
    """Save student's history to file."""
    if not student_id or student_id == "UNKNOWN":
        return
    history["last_updated"] = datetime.now().isoformat()
    path = get_student_history_path(student_id)
    try:
        with open(path, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving student history: {e}")
```

**Replace with:**
```python
def save_student_history(student_id: str, history: dict, teacher_id: str = 'local-dev'):
    """Save student's history."""
    if not student_id or student_id == "UNKNOWN":
        return
    history["last_updated"] = datetime.now().isoformat()
    # Save to Supabase
    from backend import storage
    storage.save_student_hist(teacher_id, student_id, history)
    # Also save to file (local backup)
    path = get_student_history_path(student_id)
    try:
        with open(path, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving student history: {e}")
```

---

## Step 7: Migrate `backend/accommodations.py`

### 7a. `load_student_accommodations()` (line 253)

**Find:**
```python
def load_student_accommodations() -> dict:
    """
    Load student-to-accommodation mappings.
    Returns dict: {student_id: {"presets": [...], "custom_notes": "..."}}
    FERPA Note: Student IDs stored locally only, never sent to AI.
    """
    if os.path.exists(STUDENT_ACCOMMODATIONS_FILE):
        try:
            with open(STUDENT_ACCOMMODATIONS_FILE, 'r') as f:
                data = json.load(f)
            audit_log_accommodation("LOAD_STUDENT_MAPPINGS", f"Loaded {len(data)} student mappings")
            return data
        except Exception as e:
            print(f"Error loading student accommodations: {e}")
    return {}
```

**Replace with:**
```python
def load_student_accommodations(teacher_id='local-dev') -> dict:
    """
    Load student-to-accommodation mappings.
    Returns dict: {student_id: {"presets": [...], "custom_notes": "..."}}
    FERPA Note: Student IDs stored locally only, never sent to AI.
    """
    from backend import storage
    data = storage.load('accommodations', teacher_id)
    if data is not None:
        audit_log_accommodation("LOAD_STUDENT_MAPPINGS", f"Loaded {len(data)} student mappings")
        return data
    if os.path.exists(STUDENT_ACCOMMODATIONS_FILE):
        try:
            with open(STUDENT_ACCOMMODATIONS_FILE, 'r') as f:
                data = json.load(f)
            audit_log_accommodation("LOAD_STUDENT_MAPPINGS", f"Loaded {len(data)} student mappings")
            return data
        except Exception as e:
            print(f"Error loading student accommodations: {e}")
    return {}
```

### 7b. `save_student_accommodations()` (line 272)

**Find:**
```python
def save_student_accommodations(mappings: dict) -> bool:
    """Save student-to-accommodation mappings."""
    try:
        with open(STUDENT_ACCOMMODATIONS_FILE, 'w') as f:
            json.dump(mappings, f, indent=2)
        audit_log_accommodation("SAVE_STUDENT_MAPPINGS", f"Saved {len(mappings)} student mappings")
        return True
    except Exception as e:
        print(f"Error saving student accommodations: {e}")
        return False
```

**Replace with:**
```python
def save_student_accommodations(mappings: dict, teacher_id='local-dev') -> bool:
    """Save student-to-accommodation mappings."""
    from backend import storage
    storage.save('accommodations', mappings, teacher_id)
    try:
        with open(STUDENT_ACCOMMODATIONS_FILE, 'w') as f:
            json.dump(mappings, f, indent=2)
        audit_log_accommodation("SAVE_STUDENT_MAPPINGS", f"Saved {len(mappings)} student mappings")
        return True
    except Exception as e:
        print(f"Error saving student accommodations: {e}")
        return False
```

---

## Step 8: Migrate `backend/app.py` — grading thread

### 8a. `load_saved_results()` and `save_results()` (lines 221–242)

**Find:**
```python
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
```

**Replace with:**
```python
def load_saved_results(teacher_id='local-dev'):
    """Load results."""
    from backend import storage
    data = storage.load('results', teacher_id)
    if data is not None:
        for r in data:
            if 'graded_at' not in r:
                r['graded_at'] = None
        return data
    # File fallback
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
                for r in results:
                    if 'graded_at' not in r:
                        r['graded_at'] = None
                return results
        except:
            pass
    return []


def save_results(results, teacher_id='local-dev'):
    """Save results for persistence."""
    from backend import storage
    storage.save('results', results, teacher_id)
```

### 8b. `run_grading_thread()` signature (line 340)

**Find:**
```python
def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False, class_period='', rubric=None, ensemble_models=None, extraction_mode='structured', trusted_students=None, grading_style='standard'):
```

**Replace with:**
```python
def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False, class_period='', rubric=None, ensemble_models=None, extraction_mode='structured', trusted_students=None, grading_style='standard', teacher_id='local-dev'):
```

### 8c. Thread creation in `/api/grade` (line 1922)

**Find:**
```python
    thread = threading.Thread(
        target=run_grading_thread,
        args=(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified, class_period, rubric, ensemble_models, extraction_mode, trusted_students, grading_style)
    )
```

**Replace with:**
```python
    _teacher_id = getattr(g, 'user_id', 'local-dev')
    thread = threading.Thread(
        target=run_grading_thread,
        args=(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified, class_period, rubric, ensemble_models, extraction_mode, trusted_students, grading_style, _teacher_id)
    )
```

### 8d. Add `from flask import g` to imports if not present

---

## Step 9: Migrate `backend/routes/lesson_routes.py`

### 9a. `save_lesson()` (line 35)

**Find:**
```python
    try:
        with open(filepath, 'w') as f:
            json.dump(lesson, f, indent=2)
        return jsonify({"status": "saved", "path": filepath, "unit": unit_name})
```

**Replace with:**
```python
    try:
        from backend import storage
        teacher_id = getattr(g, 'user_id', 'local-dev')
        storage.save(f'lesson:{_safe_filename(unit_name)}:{safe_title}', lesson, teacher_id)
        return jsonify({"status": "saved", "path": filepath, "unit": unit_name})
```

Keep the existing `with open(filepath, 'w')` as a secondary write (dual-write), or let `storage.save()` handle it since the file backend writes to the same path.

### 9b. `list_lessons()` (line 65)

Add Supabase path at the top of the function:

```python
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend import storage
    entries = storage.list_keys('lesson:', teacher_id)
    # ... build units/all_lessons from entries if available
```

### 9c. `load_lesson()` (line 102)

**Find:**
```python
    try:
        with open(filepath, 'r') as f:
            lesson = json.load(f)
        return jsonify({"lesson": lesson})
```

**Replace with:**
```python
    from backend import storage
    teacher_id = getattr(g, 'user_id', 'local-dev')
    lesson = storage.load(f'lesson:{_safe_filename(unit)}:{filename}', teacher_id)
    if lesson is None:
        return jsonify({"error": "Lesson not found"})
    return jsonify({"lesson": lesson})
```

---

## Step 10: Sync Endpoint

### Add to `backend/routes/settings_routes.py`:

```python
@settings_bp.route('/api/sync-to-cloud', methods=['POST'])
def sync_to_cloud():
    """Upload all local data to Supabase for this teacher."""
    from backend import storage
    teacher_id = getattr(g, 'user_id', None)
    if not teacher_id or teacher_id == 'local-dev':
        return jsonify({"error": "Must be authenticated (not local-dev) to sync"}), 401
    if not storage.USE_SUPABASE:
        return jsonify({"error": "Supabase not configured"}), 400

    report = {}

    # 1. Sync static keys
    for key in storage._STATIC_KEYS:
        data = storage._load_file(key)
        if data is not None:
            storage._save_supabase(key, data, teacher_id)
            report[key] = 'synced'
        else:
            report[key] = 'not_found'

    # 2. Sync assignments
    count = 0
    assignments_dir = os.path.expanduser('~/.graider_assignments')
    if os.path.isdir(assignments_dir):
        for f in os.listdir(assignments_dir):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(assignments_dir, f), 'r') as fh:
                        data = json.load(fh)
                    storage._save_supabase(f'assignment:{f[:-5]}', data, teacher_id)
                    count += 1
                except Exception:
                    pass
    report['assignments'] = f'{count} synced'

    # 3. Sync student history
    count = 0
    history_dir = os.path.expanduser('~/.graider_data/student_history')
    if os.path.isdir(history_dir):
        for f in os.listdir(history_dir):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(history_dir, f), 'r') as fh:
                        data = json.load(fh)
                    storage.save_student_hist(teacher_id, f[:-5], data)
                    count += 1
                except Exception:
                    pass
    report['student_history'] = f'{count} synced'

    # 4. Sync periods
    count = 0
    periods_dir = os.path.expanduser('~/.graider_data/periods')
    if os.path.isdir(periods_dir):
        for f in os.listdir(periods_dir):
            if f.endswith('.csv'):
                try:
                    rows = []
                    with open(os.path.join(periods_dir, f), 'r') as fh:
                        rows = list(csv.DictReader(fh))
                    storage._save_supabase(f'period:{f}', rows, teacher_id)
                    count += 1
                except Exception:
                    pass
            elif f.endswith('.meta.json'):
                try:
                    with open(os.path.join(periods_dir, f), 'r') as fh:
                        data = json.load(fh)
                    csv_name = f.replace('.meta.json', '')
                    storage._save_supabase(f'period_meta:{csv_name}', data, teacher_id)
                except Exception:
                    pass
    report['periods'] = f'{count} synced'

    # 5. Sync lessons
    count = 0
    lessons_dir = os.path.expanduser('~/.graider_lessons')
    if os.path.isdir(lessons_dir):
        for unit in os.listdir(lessons_dir):
            unit_path = os.path.join(lessons_dir, unit)
            if os.path.isdir(unit_path):
                for f in os.listdir(unit_path):
                    if f.endswith('.json'):
                        try:
                            with open(os.path.join(unit_path, f), 'r') as fh:
                                data = json.load(fh)
                            storage._save_supabase(f'lesson:{unit}:{f[:-5]}', data, teacher_id)
                            count += 1
                        except Exception:
                            pass
    report['lessons'] = f'{count} synced'

    # 6. Sync master grades CSV as JSON
    output_folder = os.path.expanduser('~/Downloads/Graider/Results')
    master_csv = os.path.join(output_folder, 'master_grades.csv')
    if os.path.exists(master_csv):
        try:
            with open(master_csv, 'r') as fh:
                rows = list(csv.DictReader(fh))
            storage._save_supabase('master_grades', rows, teacher_id)
            report['master_grades'] = f'{len(rows)} rows synced'
        except Exception:
            report['master_grades'] = 'error'
    else:
        report['master_grades'] = 'not_found'

    return jsonify({"status": "complete", "results": report})
```

---

## Step 11: Frontend Sync Button

### Add to `frontend/src/App.jsx` in the Settings tab

Add state:
```javascript
const [syncStatus, setSyncStatus] = useState(null);
const [syncing, setSyncing] = useState(false);
```

Add handler:
```javascript
const handleSyncToCloud = async () => {
  setSyncing(true);
  setSyncStatus(null);
  try {
    const resp = await fetch('/api/sync-to-cloud', {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' }
    });
    const data = await resp.json();
    if (data.error) {
      addToast(data.error, 'error');
    } else {
      setSyncStatus(data.results);
      addToast('Data synced to cloud successfully!', 'success');
    }
  } catch (err) {
    addToast('Sync failed: ' + err.message, 'error');
  }
  setSyncing(false);
};
```

Add button (in Settings tab, near the bottom):
```jsx
<div style={{ marginTop: 24, padding: 16, background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' }}>
  <h4 style={{ margin: '0 0 8px' }}>Cloud Sync</h4>
  <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 12px' }}>
    Upload all local data (settings, assignments, grades, student history) to the cloud for use in production.
  </p>
  <button onClick={handleSyncToCloud} disabled={syncing}
    style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
    {syncing ? 'Syncing...' : 'Sync Data to Cloud'}
  </button>
  {syncStatus && (
    <pre style={{ marginTop: 12, fontSize: 12, background: '#fff', padding: 12, borderRadius: 6, overflow: 'auto' }}>
      {JSON.stringify(syncStatus, null, 2)}
    </pre>
  )}
</div>
```

Add `getAuthHeaders` import from `services/api.js` if not already available in the component.

---

## Known Challenges

| Challenge | Solution |
|---|---|
| Grading thread can't access Flask `g` | Pass `teacher_id` as explicit param (Step 8) |
| Period CSVs referenced by file path | On Railway, reconstruct temp CSV from Supabase data in `/tmp/` |
| `grading_state` singleton | Pre-existing limitation; not in scope |
| Two settings files (`settings.json` vs `global_settings.json`) | Map as separate keys: `settings` and `global_settings` |
| `_load_accommodations()` reads per-file vs single-file format | Cloud stores unified dict; file fallback preserves per-file format |
| Large results JSONB | Supabase handles up to ~1GB; fine for now |
| Binary documents (PDFs/DOCXs) | Deferred — use Supabase Storage later |

## Out of Scope

- Full multi-tenant grading state isolation
- Binary file storage (uploaded documents, Chrome profile)
- Conversation history, cost tracking, audit log
- Automation workflows, doc styles, assessment templates

## Verification

1. Run locally — confirm all data still reads/writes to `~/.graider_*` files
2. Deploy to Railway — confirm app starts without errors
3. Log in locally, click "Sync to Cloud" — confirm data uploads to Supabase
4. Log in on Railway — confirm settings, rubric, assignments, grades load from Supabase
5. Grade an assignment on Railway — confirm results persist across redeploy
6. Check AI assistant on Railway — confirm it can read grades, calendar, student history
