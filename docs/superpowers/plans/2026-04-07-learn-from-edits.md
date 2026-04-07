# Learn from Edits — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture the delta when teachers correct AI-assigned grades, store per-teacher and global correction patterns, and inject those patterns into the grading prompt so the AI calibrates over time.

**Architecture:** On each grade edit, preserve the original AI score/feedback and log the correction. A new `correction_patterns.py` service computes per-teacher and global patterns (avg delta per question type). At grading time, `build_correction_context()` generates a prompt injection string with specific examples, appended to `file_ai_notes` (file-based) and `ai_notes` (portal).

**Tech Stack:** Python/Flask (backend only), `backend.storage` for persistence

**Spec:** `docs/superpowers/specs/2026-04-07-learn-from-edits-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/correction_patterns.py` | **Create** | Record corrections, compute patterns, build prompt context |
| `backend/routes/grading_routes.py` | **Modify** | Capture AI score/feedback delta on edit (lines 322-338) |
| `backend/app.py` | **Modify** | Inject correction context into `file_ai_notes` (line ~1320) |
| `backend/services/portal_grading.py` | **Modify** | Inject correction context into `build_portal_ai_notes` (line ~62) |
| `tests/test_correction_patterns.py` | **Create** | Tests for recording, pattern computation, prompt building |

---

### Task 1: Create correction_patterns.py with recording and pattern computation

**Files:**
- Create: `backend/services/correction_patterns.py`
- Create: `tests/test_correction_patterns.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_correction_patterns.py`:

```python
"""Tests for correction patterns — recording, computing, and prompt building."""

import pytest
from unittest.mock import patch, MagicMock


class TestRecordCorrection:
    """Tests for record_correction — storing teacher edits."""

    def test_records_score_correction(self):
        from backend.services.correction_patterns import record_correction

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._save_corrections") as mock_save:
            mock_load.return_value = {"corrections": [], "patterns": {}, "updated_at": ""}

            record_correction(
                teacher_id="teacher-abc",
                ai_score=2,
                teacher_score=4,
                max_points=5,
                question_type="short_answer",
                subject="US History",
                grade_level="8",
                assignment="Unit 3 Assessment",
                student_answer_snippet="Student explained cause but incomplete sentences",
            )

            saved = mock_save.call_args[0][1]
            assert len(saved["corrections"]) == 1
            c = saved["corrections"][0]
            assert c["ai_score"] == 2
            assert c["teacher_score"] == 4
            assert c["delta"] == 2
            assert c["question_type"] == "short_answer"

    def test_caps_corrections_at_100(self):
        from backend.services.correction_patterns import record_correction

        existing = {
            "corrections": [{"question_type": "mc", "delta": 0, "ai_score": 3, "teacher_score": 3, "timestamp": "t"}] * 100,
            "patterns": {},
            "updated_at": "",
        }

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._save_corrections") as mock_save:
            mock_load.return_value = existing

            record_correction(
                teacher_id="teacher-abc",
                ai_score=1, teacher_score=3, max_points=5,
                question_type="short_answer", subject="Math", grade_level="7",
                assignment="Quiz", student_answer_snippet="answer",
            )

            saved = mock_save.call_args[0][1]
            assert len(saved["corrections"]) == 100
            assert saved["corrections"][-1]["question_type"] == "short_answer"

    def test_updates_patterns_on_record(self):
        from backend.services.correction_patterns import record_correction

        existing = {
            "corrections": [
                {"question_type": "short_answer", "delta": 2, "ai_score": 2, "teacher_score": 4, "timestamp": "t"},
                {"question_type": "short_answer", "delta": 1, "ai_score": 3, "teacher_score": 4, "timestamp": "t"},
            ],
            "patterns": {},
            "updated_at": "",
        }

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._save_corrections") as mock_save:
            mock_load.return_value = existing

            record_correction(
                teacher_id="teacher-abc",
                ai_score=2, teacher_score=5, max_points=5,
                question_type="short_answer", subject="History", grade_level="8",
                assignment="Test", student_answer_snippet="good answer",
            )

            saved = mock_save.call_args[0][1]
            pattern = saved["patterns"]["short_answer"]
            assert pattern["count"] == 3
            assert pattern["direction"] == "up"
            assert round(pattern["avg_delta"], 1) == 2.0


class TestRecordGlobalCorrection:
    """Tests for global correction recording."""

    def test_records_anonymized_global_correction(self):
        from backend.services.correction_patterns import record_correction

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._save_corrections") as mock_save, \
             patch("backend.services.correction_patterns._load_global") as mock_gload, \
             patch("backend.services.correction_patterns._save_global") as mock_gsave:
            mock_load.return_value = {"corrections": [], "patterns": {}, "updated_at": ""}
            mock_gload.return_value = {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}

            record_correction(
                teacher_id="teacher-abc",
                ai_score=2, teacher_score=4, max_points=5,
                question_type="short_answer", subject="History", grade_level="8",
                assignment="Test", student_answer_snippet="answer",
            )

            gsaved = mock_gsave.call_args[0][0]
            gc = gsaved["corrections"][0]
            assert "teacher_id" not in gc
            assert "student_answer_snippet" not in gc
            assert gc["question_type"] == "short_answer"
            assert gc["delta"] == 2


class TestBuildCorrectionContext:
    """Tests for build_correction_context — prompt injection."""

    def test_returns_empty_when_no_patterns(self):
        from backend.services.correction_patterns import build_correction_context

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._load_global") as mock_gload:
            mock_load.return_value = {"corrections": [], "patterns": {}, "updated_at": ""}
            mock_gload.return_value = {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}

            result = build_correction_context("teacher-abc", "US History", ["short_answer", "multiple_choice"])
            assert result == ""

    def test_includes_per_teacher_pattern_with_3_plus_corrections(self):
        from backend.services.correction_patterns import build_correction_context

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._load_global") as mock_gload:
            mock_load.return_value = {
                "corrections": [
                    {"question_type": "short_answer", "delta": 2, "ai_score": 2, "teacher_score": 4,
                     "student_answer_snippet": "good but incomplete", "subject": "US History", "timestamp": "t"},
                ] * 5,
                "patterns": {"short_answer": {"avg_delta": 2.0, "count": 5, "direction": "up"}},
                "updated_at": "",
            }
            mock_gload.return_value = {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}

            result = build_correction_context("teacher-abc", "US History", ["short_answer"])
            assert "GRADING CALIBRATION" in result
            assert "short answer" in result.lower() or "Short Answer" in result
            assert "2.0" in result or "2 point" in result

    def test_skips_pattern_with_fewer_than_3_corrections(self):
        from backend.services.correction_patterns import build_correction_context

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._load_global") as mock_gload:
            mock_load.return_value = {
                "corrections": [
                    {"question_type": "short_answer", "delta": 2, "ai_score": 2, "teacher_score": 4,
                     "student_answer_snippet": "answer", "subject": "US History", "timestamp": "t"},
                ] * 2,
                "patterns": {"short_answer": {"avg_delta": 2.0, "count": 2, "direction": "up"}},
                "updated_at": "",
            }
            mock_gload.return_value = {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}

            result = build_correction_context("teacher-abc", "US History", ["short_answer"])
            assert result == ""

    def test_includes_global_pattern_when_3_plus_teachers(self):
        from backend.services.correction_patterns import build_correction_context

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._load_global") as mock_gload:
            mock_load.return_value = {"corrections": [], "patterns": {}, "updated_at": ""}
            mock_gload.return_value = {
                "corrections": [],
                "patterns": {"short_answer": {"avg_delta": 1.2, "count": 15, "direction": "up"}},
                "teacher_hashes": {"short_answer": ["hash1", "hash2", "hash3"]},
                "updated_at": "",
            }

            result = build_correction_context("teacher-abc", "US History", ["short_answer"])
            assert "ACCURACY NOTE" in result

    def test_caps_at_3_question_types(self):
        from backend.services.correction_patterns import build_correction_context

        patterns = {}
        corrections = []
        for qt in ["short_answer", "extended_writing", "vocabulary", "data_analysis", "math_computation"]:
            patterns[qt] = {"avg_delta": 1.5, "count": 10, "direction": "up"}
            corrections.extend([
                {"question_type": qt, "delta": 1.5, "ai_score": 3, "teacher_score": 4,
                 "student_answer_snippet": "answer", "subject": "Math", "timestamp": "t"},
            ] * 10)

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._load_global") as mock_gload:
            mock_load.return_value = {"corrections": corrections, "patterns": patterns, "updated_at": ""}
            mock_gload.return_value = {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}

            result = build_correction_context("teacher-abc", "Math", ["short_answer", "extended_writing", "vocabulary", "data_analysis", "math_computation"])
            # Should only include top 3 by count
            type_mentions = sum(1 for qt in ["short_answer", "extended_writing", "vocabulary", "data_analysis", "math_computation"]
                               if qt.replace("_", " ") in result.lower())
            assert type_mentions <= 3

    def test_total_injection_under_800_chars(self):
        from backend.services.correction_patterns import build_correction_context

        patterns = {}
        corrections = []
        for qt in ["short_answer", "extended_writing", "vocabulary"]:
            patterns[qt] = {"avg_delta": 1.5, "count": 10, "direction": "up"}
            corrections.extend([
                {"question_type": qt, "delta": 1.5, "ai_score": 3, "teacher_score": 4,
                 "student_answer_snippet": "A very long student answer that goes on and on " * 5, "subject": "History", "timestamp": "t"},
            ] * 10)

        with patch("backend.services.correction_patterns._load_corrections") as mock_load, \
             patch("backend.services.correction_patterns._load_global") as mock_gload:
            mock_load.return_value = {"corrections": corrections, "patterns": patterns, "updated_at": ""}
            mock_gload.return_value = {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}

            result = build_correction_context("teacher-abc", "History", ["short_answer", "extended_writing", "vocabulary"])
            assert len(result) <= 800
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_correction_patterns.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Create the correction_patterns service**

Create `backend/services/correction_patterns.py`:

```python
"""Correction patterns — learn from teacher grade edits.

Records the delta between AI-assigned and teacher-corrected scores,
computes per-teacher and global patterns, and builds prompt injection
context for future grading.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_CORRECTIONS = 100
MIN_PATTERN_COUNT = 3
MAX_PROMPT_TYPES = 3
MAX_PROMPT_CHARS = 800

QUESTION_TYPE_LABELS = {
    "short_answer": "Short Answer",
    "multiple_choice": "Multiple Choice",
    "extended_writing": "Extended Writing",
    "vocabulary": "Vocabulary",
    "true_false": "True/False",
    "math_computation": "Math Computation",
    "geometry_visual": "Geometry",
    "graphing": "Graphing",
    "data_analysis": "Data Analysis",
    "florida_fast": "FL FAST",
}


def _load_corrections(teacher_id):
    try:
        from backend.storage import load
        data = load("grading_corrections", teacher_id)
        if data:
            return data
    except Exception:
        pass
    return {"corrections": [], "patterns": {}, "updated_at": ""}


def _save_corrections(teacher_id, data):
    try:
        from backend.storage import save
        save("grading_corrections", data, teacher_id)
    except Exception as e:
        logger.warning("Failed to save corrections for %s: %s", teacher_id, e)


def _load_global():
    try:
        from backend.storage import load
        data = load("grading_corrections:global", "system")
        if data:
            return data
    except Exception:
        pass
    return {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}


def _save_global(data):
    try:
        from backend.storage import save
        save("grading_corrections:global", data, "system")
    except Exception as e:
        logger.warning("Failed to save global corrections: %s", e)


def _hash_teacher(teacher_id):
    salt = os.environ.get("FLASK_SECRET_KEY", "graider-default-salt")
    return hashlib.sha256((teacher_id + salt).encode()).hexdigest()[:12]


def _compute_patterns(corrections):
    """Compute avg delta per question type from corrections list."""
    by_type = {}
    for c in corrections:
        qt = c.get("question_type", "")
        if not qt:
            continue
        if qt not in by_type:
            by_type[qt] = []
        by_type[qt].append(c.get("delta", 0))

    patterns = {}
    for qt, deltas in by_type.items():
        if not deltas:
            continue
        avg = sum(deltas) / len(deltas)
        direction = "up" if avg > 0 else "down" if avg < 0 else "none"
        patterns[qt] = {
            "avg_delta": round(avg, 1),
            "count": len(deltas),
            "direction": direction,
        }
    return patterns


def record_correction(teacher_id, ai_score, teacher_score, max_points,
                      question_type, subject, grade_level, assignment,
                      student_answer_snippet=""):
    """Record a teacher correction and update patterns."""
    delta = teacher_score - ai_score
    now = datetime.now(timezone.utc).isoformat()

    entry = {
        "assignment": assignment,
        "question_type": question_type,
        "subject": subject,
        "grade_level": grade_level,
        "ai_score": ai_score,
        "teacher_score": teacher_score,
        "max_points": max_points,
        "delta": delta,
        "student_answer_snippet": (student_answer_snippet or "")[:200],
        "timestamp": now,
    }

    # Per-teacher
    data = _load_corrections(teacher_id)
    data["corrections"].append(entry)
    if len(data["corrections"]) > MAX_CORRECTIONS:
        data["corrections"] = data["corrections"][-MAX_CORRECTIONS:]
    data["patterns"] = _compute_patterns(data["corrections"])
    data["updated_at"] = now
    _save_corrections(teacher_id, data)

    # Global (anonymized)
    global_data = _load_global()
    global_entry = {
        "question_type": question_type,
        "subject": subject,
        "grade_level": grade_level,
        "ai_score": ai_score,
        "teacher_score": teacher_score,
        "delta": delta,
        "timestamp": now,
    }
    global_data["corrections"].append(global_entry)
    if len(global_data["corrections"]) > MAX_CORRECTIONS * 10:
        global_data["corrections"] = global_data["corrections"][-(MAX_CORRECTIONS * 10):]
    global_data["patterns"] = _compute_patterns(global_data["corrections"])

    # Track unique teachers per question type
    teacher_hash = _hash_teacher(teacher_id)
    if "teacher_hashes" not in global_data:
        global_data["teacher_hashes"] = {}
    if question_type not in global_data["teacher_hashes"]:
        global_data["teacher_hashes"][question_type] = []
    if teacher_hash not in global_data["teacher_hashes"][question_type]:
        global_data["teacher_hashes"][question_type].append(teacher_hash)

    global_data["updated_at"] = now
    _save_global(global_data)


def build_correction_context(teacher_id, subject, question_types):
    """Build prompt injection string from correction patterns.

    Args:
        teacher_id: teacher identifier
        subject: current assignment subject
        question_types: list of question type keys in current assignment

    Returns prompt string (may be empty if no patterns qualify).
    """
    data = _load_corrections(teacher_id)
    global_data = _load_global()

    parts = []

    # Per-teacher patterns (top 3 by count, min 3 corrections each)
    teacher_patterns = data.get("patterns", {})
    relevant = []
    for qt in question_types:
        p = teacher_patterns.get(qt)
        if p and p.get("count", 0) >= MIN_PATTERN_COUNT:
            relevant.append((qt, p))
    relevant.sort(key=lambda x: x[1]["count"], reverse=True)
    relevant = relevant[:MAX_PROMPT_TYPES]

    if relevant:
        lines = ["GRADING CALIBRATION (based on this teacher's previous corrections):"]
        for qt, p in relevant:
            label = QUESTION_TYPE_LABELS.get(qt, qt.replace("_", " ").title())
            direction_word = "upward" if p["direction"] == "up" else "downward"
            line = "- " + label + ": This teacher has adjusted scores " + direction_word
            line += " by ~" + str(abs(p["avg_delta"])) + " points on average"
            line += " across " + str(p["count"]) + " corrections."

            # Add one example
            examples = [c for c in data.get("corrections", []) if c.get("question_type") == qt]
            if examples:
                ex = examples[-1]
                snippet = (ex.get("student_answer_snippet") or "")[:80]
                if snippet:
                    line += " Example: student wrote '" + snippet + "'"
                    line += ", AI scored " + str(ex["ai_score"]) + "/" + str(ex["max_points"])
                    line += ", teacher corrected to " + str(ex["teacher_score"]) + "/" + str(ex["max_points"]) + "."

            lines.append(line)
        lines.append("Adjust your grading to match this teacher's expectations.")
        teacher_block = "\n".join(lines)
        parts.append(teacher_block)

    # Global patterns (3+ unique teachers, same direction)
    global_patterns = global_data.get("patterns", {})
    global_hashes = global_data.get("teacher_hashes", {})
    for qt in question_types:
        gp = global_patterns.get(qt)
        if not gp or gp.get("count", 0) < MIN_PATTERN_COUNT:
            continue
        unique_teachers = len(global_hashes.get(qt, []))
        if unique_teachers < 3:
            continue
        label = QUESTION_TYPE_LABELS.get(qt, qt.replace("_", " ").title())
        direction_word = "underscored" if gp["direction"] == "up" else "overscored"
        global_line = "ACCURACY NOTE: Multiple teachers have independently found that "
        global_line += label + " questions are " + direction_word
        global_line += " by ~" + str(abs(gp["avg_delta"])) + " points on average. "
        global_line += "Consider this systematic tendency when grading."
        parts.append(global_line)

    result = "\n\n".join(parts)
    if len(result) > MAX_PROMPT_CHARS:
        result = result[:MAX_PROMPT_CHARS]
    return result
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_correction_patterns.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/correction_patterns.py tests/test_correction_patterns.py
git commit -m "feat: correction patterns service (record, compute, build prompt)"
```

---

### Task 2: Capture AI score delta on grade edit

**Files:**
- Modify: `backend/routes/grading_routes.py:291-368`

- [ ] **Step 1: Preserve original AI values before overwriting**

In `backend/routes/grading_routes.py`, find the `_do_update()` function inside `update_result()` (line 312). After line 323 (`allowed_fields = ['score', 'letter_grade', 'feedback', 'verified']`) and before the field update loop (line 324), add:

```python
        # Preserve original AI values on first edit
        result = grading_state["results"][result_index]
        if ('score' in data or 'feedback' in data) and not result.get('teacher_edited'):
            if 'ai_score' not in result:
                result['ai_score'] = result.get('score')
            if 'ai_feedback' not in result:
                result['ai_feedback'] = result.get('feedback', '')
            result['teacher_edited'] = True
        if 'score' in data or 'feedback' in data:
            from datetime import datetime, timezone
            result['edit_timestamp'] = datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 2: Record correction after successful edit**

After line 363 (`_sync_result_to_master_csv(updated_result)`) and before the return, add:

```python
    # Record correction pattern if score was edited
    if 'score' in data and updated_result.get('ai_score') is not None:
        ai_score = updated_result['ai_score']
        teacher_score = int(data['score'])
        if ai_score != teacher_score:
            try:
                from backend.services.correction_patterns import record_correction
                record_correction(
                    teacher_id=teacher_id,
                    ai_score=ai_score,
                    teacher_score=teacher_score,
                    max_points=100,
                    question_type=updated_result.get('question_type', 'unknown'),
                    subject=updated_result.get('subject', ''),
                    grade_level=updated_result.get('grade_level', ''),
                    assignment=updated_result.get('assignment', ''),
                    student_answer_snippet='',
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to record correction: %s", e)
```

- [ ] **Step 3: Run existing grading tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "grading" -x -q 2>&1 | tail -10`
Expected: All pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add backend/routes/grading_routes.py
git commit -m "feat: capture AI score delta and record correction on grade edit"
```

---

### Task 3: Inject correction context into file-based grading

**Files:**
- Modify: `backend/app.py:1319-1325`

- [ ] **Step 1: Add correction context after global AI notes**

In `backend/app.py`, find line 1320 (`file_ai_notes = global_ai_notes`). After line 1325 (the `print` for assignment-specific notes), and before line 1327 (model answers injection), add:

```python
                # Inject correction patterns (learn from teacher edits)
                try:
                    from backend.services.correction_patterns import build_correction_context
                    _question_types = []
                    if matched_config:
                        _section_cats = matched_config.get('sectionCategories', {})
                        _question_types = [k for k, v in _section_cats.items() if v]
                    if not _question_types:
                        _question_types = ['short_answer', 'multiple_choice', 'extended_writing']
                    _correction_ctx = build_correction_context(
                        teacher_id, config.get('subject', ''), _question_types
                    )
                    if _correction_ctx:
                        file_ai_notes += "\n\n" + _correction_ctx
                        print(f"  ✓ Applying Correction Patterns ({len(_correction_ctx)} chars)")
                except Exception as e:
                    print(f"  ! Correction patterns skipped: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app.py
git commit -m "feat: inject correction patterns into file-based grading prompt"
```

---

### Task 4: Inject correction context into portal grading

**Files:**
- Modify: `backend/services/portal_grading.py:62-100`

- [ ] **Step 1: Add correction_context parameter to build_portal_ai_notes**

In `backend/services/portal_grading.py`, find `def build_portal_ai_notes` (line 62). Add `correction_context=""` parameter:

Change:
```python
def build_portal_ai_notes(global_ai_notes="", assignment_title="",
                          grade_level="", subject="", grading_style="standard",
                          rubric=None, accommodation_prompt="",
                          student_history="", class_period=""):
```

To:
```python
def build_portal_ai_notes(global_ai_notes="", assignment_title="",
                          grade_level="", subject="", grading_style="standard",
                          rubric=None, accommodation_prompt="",
                          student_history="", class_period="",
                          correction_context=""):
```

Then at the end of the function, before the return, add:

```python
    if correction_context:
        notes += "\n\n" + correction_context
```

- [ ] **Step 2: Pass correction context at the call sites**

Find where `build_portal_ai_notes` is called in `portal_grading.py`. There are two call sites (around lines 130 and 430). At each call site, add the correction context:

Before the call, add:
```python
            # Build correction context from teacher edit history
            _correction_ctx = ""
            try:
                from backend.services.correction_patterns import build_correction_context
                _q_types = list(set(q.get("question_type", "short_answer") for q in questions if q.get("question_type")))
                if not _q_types:
                    _q_types = ["short_answer", "multiple_choice"]
                _correction_ctx = build_correction_context(teacher_id, subject, _q_types)
            except Exception:
                pass
```

Then add `correction_context=_correction_ctx` to the `build_portal_ai_notes()` call.

- [ ] **Step 3: Run portal grading tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "portal" -x -q 2>&1 | tail -10`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/services/portal_grading.py
git commit -m "feat: inject correction patterns into portal grading prompt"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Correction patterns service + 10 tests | New `correction_patterns.py` | Low — new file |
| 2 | Capture AI score delta on edit | `grading_routes.py` | Low — additive fields |
| 3 | Inject into file-based grading | `app.py` | Low — appending to existing string |
| 4 | Inject into portal grading | `portal_grading.py` | Low — new parameter with default |

**Total: 1 new file, 3 modified files, 10 tests.**

**Before:** Teacher edits a score, original AI score is lost, AI makes the same mistake next time.
**After:** Original AI score is preserved, correction patterns accumulate, AI calibrates to each teacher's expectations and improves globally when multiple teachers agree.
