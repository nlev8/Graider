"""
Data Loading/Saving Assistant Tools
====================================
Persistence helpers for assistant memory, calendar, and email config.
These are extracted from assistant_tools.py to reduce file size.
"""
import os
import json
from datetime import datetime

# Import storage abstraction
try:
    from backend.storage import load as storage_load, save as storage_save
except ImportError:
    try:
        from storage import load as storage_load, save as storage_save
    except ImportError:
        storage_load = None
        storage_save = None

# Constants
MEMORY_FILE = os.path.expanduser("~/.graider_data/assistant_memory.json")
CALENDAR_FILE = os.path.expanduser("~/.graider_data/teaching_calendar.json")
MAX_MEMORIES = 50


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

DATA_TOOL_DEFINITIONS = [
    {
        "name": "save_memory",
        "description": "Save an important fact about the teacher or their classes for future conversations. Use this when the teacher shares preferences, class structure, workflow habits, or any information that would be useful to remember across sessions. Only save genuinely useful facts, not temporary or conversation-specific details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact to remember (e.g., 'Period 3 is honors with higher expectations')"
                }
            },
            "required": ["fact"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# MEMORY HELPERS
# ═══════════════════════════════════════════════════════

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


def save_memory(fact):
    """Save a fact to persistent memory for future conversations."""
    if not fact or not fact.strip():
        return {"error": "No fact provided"}

    fact = fact.strip()
    memories = _load_memories()

    # Duplicate check — skip if a very similar fact already exists
    fact_lower = fact.lower()
    for existing in memories:
        existing_text = existing.get("fact", existing) if isinstance(existing, dict) else str(existing)
        if existing_text.lower() == fact_lower:
            return {"status": "already_saved", "fact": fact, "message": "This fact is already saved."}

    # Build entry with timestamp
    entry = {"fact": fact, "saved_at": datetime.now().isoformat()}
    memories.append(entry)

    # Cap at MAX_MEMORIES (remove oldest if exceeded)
    if len(memories) > MAX_MEMORIES:
        memories = memories[-MAX_MEMORIES:]

    _save_memories(memories)
    return {"status": "saved", "fact": fact, "total_memories": len(memories)}


# ═══════════════════════════════════════════════════════
# CALENDAR HELPERS
# ═══════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════
# EMAIL CONFIG HELPER
# ═══════════════════════════════════════════════════════

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
# EXPORT MAP
# ═══════════════════════════════════════════════════════

DATA_TOOL_DEFINITIONS = DATA_TOOL_DEFINITIONS  # re-export for clarity

DATA_TOOL_HANDLERS = {
    "save_memory": save_memory,
}
