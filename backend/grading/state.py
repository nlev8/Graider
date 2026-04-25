"""Per-teacher grading state + persistence.

Extracted from backend/app.py in Phase 3a PR2. Keeps module-level dicts
and the thread-safe accessors exactly as they were at app.py head.
"""

import json
import logging
import os
import re
import threading
from typing import Any, Callable, Optional, cast

import sentry_sdk

_logger = logging.getLogger(__name__)

# Import storage abstraction (mirrors the fallback pattern in backend/app.py).
# The bare `from storage import` fallback is an unresolvable module name for
# mypy (it only exists on certain PYTHONPATH configs); suppress with ignore.
_StorageLoad = Optional[Callable[..., Any]]
_StorageSave = Optional[Callable[..., Any]]

storage_load: _StorageLoad
storage_save: _StorageSave

try:
    from backend.storage import load as storage_load, save as storage_save
except ImportError:
    try:
        from storage import load as storage_load, save as storage_save  # type: ignore[import-not-found,no-redef]
    except ImportError:
        storage_load = None
        storage_save = None

# Fallback results file path (same constant as app.py and assistant_tools.py)
RESULTS_FILE = os.path.expanduser("~/.graider_results.json")


def _sanitize_student_name(name: str) -> str:
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


def load_saved_results(teacher_id: str = 'local-dev') -> list[dict[str, Any]]:
    """Load results from storage (Supabase in prod, file locally)."""
    if storage_load is not None:
        data: Any = storage_load('results', teacher_id)
        if data and isinstance(data, list):
            for r in data:
                if 'graded_at' not in r:
                    r['graded_at'] = None
                # Sanitize corrupted student names (filename leaking into name)
                sn = r.get('student_name', '')
                cleaned = _sanitize_student_name(sn)
                if cleaned != sn:
                    r['student_name'] = cleaned
            return cast(list[dict[str, Any]], data)
    # Fallback to direct file read
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                results: list[dict[str, Any]] = json.load(f)
                for r in results:
                    if 'graded_at' not in r:
                        r['graded_at'] = None
                    sn = r.get('student_name', '')
                    cleaned = _sanitize_student_name(sn)
                    if cleaned != sn:
                        r['student_name'] = cleaned
                return results
        except Exception as e:
            sentry_sdk.capture_exception(e)
    return []

def save_results(results: list[dict[str, Any]], teacher_id: str = 'local-dev') -> None:
    """Save results to storage (dual-write: file + Supabase)."""
    if storage_save is not None:
        storage_save('results', results, teacher_id)
    else:
        try:
            with open(RESULTS_FILE, 'w') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            _logger.error("Error saving results: %s", e)
            sentry_sdk.capture_exception(e)

# ── Per-teacher grading state (dict-of-dicts) ────────────────
_grading_states: dict[str, dict[str, Any]] = {}   # teacher_id -> state dict
_grading_locks: dict[str, threading.Lock] = {}    # teacher_id -> Lock
_states_meta_lock = threading.Lock()


def _create_default_state(teacher_id: str = 'local-dev') -> dict[str, Any]:
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


def _get_state(teacher_id: str = 'local-dev') -> dict[str, Any]:
    """Get (or lazily create) the grading state dict for a teacher."""
    if teacher_id not in _grading_states:
        with _states_meta_lock:
            if teacher_id not in _grading_states:
                _grading_states[teacher_id] = _create_default_state(teacher_id)
                _grading_locks[teacher_id] = threading.Lock()
    return _grading_states[teacher_id]


def _get_lock(teacher_id: str = 'local-dev') -> threading.Lock:
    """Get (or lazily create) the grading lock for a teacher."""
    _get_state(teacher_id)  # ensure state+lock exist
    return _grading_locks[teacher_id]


def _update_state(teacher_id: str = 'local-dev', **kwargs: Any) -> None:
    """Thread-safe grading_state update for a specific teacher."""
    with _get_lock(teacher_id):
        _get_state(teacher_id).update(kwargs)


def reset_state(teacher_id: str = 'local-dev', clear_results: bool = False) -> None:
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
