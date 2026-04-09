"""
Tests for backend/services/correction_patterns.py

Covers:
  - TestRecordCorrection        (3 tests)
  - TestRecordGlobalCorrection  (1 test)
  - TestBuildCorrectionContext  (5 tests)
  - TestPromptLength            (1 test)
"""
import pytest
from unittest.mock import patch, MagicMock


MODULE = "backend.services.correction_patterns"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_correction(question_type="short_answer", ai_score=7, teacher_score=8):
    """Return kwargs for record_correction."""
    return dict(
        teacher_id="teacher-abc",
        ai_score=ai_score,
        teacher_score=teacher_score,
        max_points=10,
        question_type=question_type,
        subject="English",
        grade_level="8",
        assignment="Unit 3 Quiz",
        student_answer_snippet="The theme is about perseverance",
    )


def _empty_teacher():
    return {"corrections": [], "patterns": {}, "updated_at": ""}


def _empty_global():
    return {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}


# ══════════════════════════════════════════════════════════════════════════════
# TestRecordCorrection
# ══════════════════════════════════════════════════════════════════════════════

class TestRecordCorrection:

    def test_records_score_correction(self):
        """record_correction saves an entry with the correct delta."""
        from backend.services.correction_patterns import record_correction

        saved = {}

        def fake_load_teacher(tid):
            return _empty_teacher()

        def fake_save_teacher(tid, data):
            saved["data"] = data

        with patch(f"{MODULE}._load_corrections", side_effect=fake_load_teacher), \
             patch(f"{MODULE}._save_corrections", side_effect=fake_save_teacher), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()), \
             patch(f"{MODULE}._save_global"):

            record_correction(**_make_correction(ai_score=6, teacher_score=9))

        corrections = saved["data"]["corrections"]
        assert len(corrections) == 1
        entry = corrections[0]
        assert entry["ai_score"] == 6
        assert entry["teacher_score"] == 9
        assert entry["delta"] == 3
        assert entry["question_type"] == "short_answer"

    def test_caps_corrections_at_100(self):
        """Correction log never exceeds MAX_CORRECTIONS (100)."""
        from backend.services.correction_patterns import record_correction, MAX_CORRECTIONS

        # Pre-fill with 100 entries
        existing = [
            {
                "ai_score": 5, "teacher_score": 6, "max_points": 10,
                "delta": 1, "question_type": "essay", "subject": "English",
                "grade_level": "8", "assignment": "Old Quiz",
                "student_answer_snippet": "", "timestamp": "2026-01-01T00:00:00+00:00",
            }
            for _ in range(MAX_CORRECTIONS)
        ]
        pre_loaded = {"corrections": existing, "patterns": {}, "updated_at": ""}

        saved = {}

        with patch(f"{MODULE}._load_corrections", return_value=pre_loaded), \
             patch(f"{MODULE}._save_corrections", side_effect=lambda tid, d: saved.update({"data": d})), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()), \
             patch(f"{MODULE}._save_global"):

            record_correction(**_make_correction())

        assert len(saved["data"]["corrections"]) == MAX_CORRECTIONS

    def test_updates_patterns_on_record(self):
        """Patterns are recomputed after each record_correction call."""
        from backend.services.correction_patterns import record_correction

        saved = {}

        def fake_load_teacher(tid):
            return _empty_teacher()

        with patch(f"{MODULE}._load_corrections", side_effect=fake_load_teacher), \
             patch(f"{MODULE}._save_corrections", side_effect=lambda tid, d: saved.update({"data": d})), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()), \
             patch(f"{MODULE}._save_global"):

            record_correction(**_make_correction(ai_score=5, teacher_score=8))

        patterns = saved["data"]["patterns"]
        assert "short_answer" in patterns
        assert patterns["short_answer"]["count"] == 1
        assert patterns["short_answer"]["avg_delta"] == 3.0
        assert patterns["short_answer"]["direction"] == "up"


# ══════════════════════════════════════════════════════════════════════════════
# TestRecordGlobalCorrection
# ══════════════════════════════════════════════════════════════════════════════

class TestRecordGlobalCorrection:

    def test_records_anonymized_global_correction(self):
        """Global entry must NOT contain teacher_id or student_answer_snippet."""
        from backend.services.correction_patterns import record_correction

        global_saved = {}

        with patch(f"{MODULE}._load_corrections", return_value=_empty_teacher()), \
             patch(f"{MODULE}._save_corrections"), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()), \
             patch(f"{MODULE}._save_global", side_effect=lambda d: global_saved.update({"data": d})):

            record_correction(**_make_correction())

        corrections = global_saved["data"]["corrections"]
        assert len(corrections) == 1
        entry = corrections[0]
        assert "teacher_id" not in entry
        assert "student_answer_snippet" not in entry
        # But it should have the question_type and scores
        assert "question_type" in entry
        assert "delta" in entry


# ══════════════════════════════════════════════════════════════════════════════
# TestBuildCorrectionContext
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildCorrectionContext:

    def test_returns_empty_when_no_patterns(self):
        """No corrections → empty string returned."""
        from backend.services.correction_patterns import build_correction_context

        with patch(f"{MODULE}._load_corrections", return_value=_empty_teacher()), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()):

            result = build_correction_context(
                teacher_id="teacher-abc",
                subject="Math",
                question_types=["short_answer"],
            )

        assert result == ""

    def test_includes_per_teacher_pattern_with_3_plus_corrections(self):
        """5 corrections for short_answer → GRADING CALIBRATION block included."""
        from backend.services.correction_patterns import build_correction_context, _compute_patterns

        corrections = [
            {
                "ai_score": 6, "teacher_score": 8, "max_points": 10,
                "delta": 2, "question_type": "short_answer", "subject": "English",
                "grade_level": "8", "assignment": "Quiz", "timestamp": "2026-01-01T00:00:00+00:00",
                "student_answer_snippet": "The theme is perseverance",
            }
            for _ in range(5)
        ]
        teacher_data = {
            "corrections": corrections,
            "patterns": _compute_patterns(corrections),
            "updated_at": "",
        }

        with patch(f"{MODULE}._load_corrections", return_value=teacher_data), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()):

            result = build_correction_context(
                teacher_id="teacher-abc",
                subject="English",
                question_types=["short_answer"],
            )

        assert "GRADING CALIBRATION" in result
        assert "Short Answer" in result
        assert "higher" in result  # avg delta is +2

    def test_skips_pattern_with_fewer_than_3_corrections(self):
        """Only 2 corrections → pattern does not surface (below MIN_PATTERN_COUNT)."""
        from backend.services.correction_patterns import build_correction_context, _compute_patterns

        corrections = [
            {
                "ai_score": 5, "teacher_score": 8, "max_points": 10,
                "delta": 3, "question_type": "essay", "subject": "English",
                "grade_level": "8", "assignment": "Quiz", "timestamp": "2026-01-01T00:00:00+00:00",
                "student_answer_snippet": "",
            }
            for _ in range(2)
        ]
        teacher_data = {
            "corrections": corrections,
            "patterns": _compute_patterns(corrections),
            "updated_at": "",
        }

        with patch(f"{MODULE}._load_corrections", return_value=teacher_data), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()):

            result = build_correction_context(
                teacher_id="teacher-abc",
                subject="English",
                question_types=["essay"],
            )

        assert result == ""

    def test_includes_global_pattern_when_3_plus_teachers(self):
        """3+ unique teacher hashes for a type → ACCURACY NOTE block included."""
        from backend.services.correction_patterns import build_correction_context, _compute_patterns

        global_corrections = [
            {
                "ai_score": 7, "teacher_score": 9, "max_points": 10,
                "delta": 2, "question_type": "essay", "subject": "English",
                "grade_level": "8", "assignment": "Quiz", "timestamp": "2026-01-01T00:00:00+00:00",
            }
            for _ in range(5)
        ]
        global_data = {
            "corrections": global_corrections,
            "patterns": _compute_patterns(global_corrections),
            # 3 unique teacher hashes → qualifies
            "teacher_hashes": {"essay": ["hash000000aa", "hash000000bb", "hash000000cc"]},
            "updated_at": "",
        }

        with patch(f"{MODULE}._load_corrections", return_value=_empty_teacher()), \
             patch(f"{MODULE}._load_global", return_value=global_data):

            result = build_correction_context(
                teacher_id="teacher-xyz",
                subject="English",
                question_types=["essay"],
            )

        assert "ACCURACY NOTE" in result
        assert "Essay" in result

    def test_caps_at_3_question_types(self):
        """5 question types with 3+ corrections each → only 3 appear in output."""
        from backend.services.correction_patterns import build_correction_context, _compute_patterns, MAX_PROMPT_TYPES

        all_types = ["short_answer", "essay", "vocabulary", "summary", "open_ended"]
        corrections = []
        for qt in all_types:
            for _ in range(4):
                corrections.append({
                    "ai_score": 5, "teacher_score": 7, "max_points": 10,
                    "delta": 2, "question_type": qt, "subject": "English",
                    "grade_level": "8", "assignment": "Quiz", "timestamp": "2026-01-01T00:00:00+00:00",
                    "student_answer_snippet": "",
                })

        teacher_data = {
            "corrections": corrections,
            "patterns": _compute_patterns(corrections),
            "updated_at": "",
        }

        with patch(f"{MODULE}._load_corrections", return_value=teacher_data), \
             patch(f"{MODULE}._load_global", return_value=_empty_global()):

            result = build_correction_context(
                teacher_id="teacher-abc",
                subject="English",
                question_types=all_types,
            )

        assert result != ""
        # Count how many of the known type labels appear
        labels_present = sum(
            1 for qt in all_types
            if qt.replace("_", " ").title() in result
            or (qt == "short_answer" and "Short Answer" in result)
            or (qt == "open_ended" and "Open Ended" in result)
        )
        assert labels_present <= MAX_PROMPT_TYPES


# ══════════════════════════════════════════════════════════════════════════════
# TestPromptLength
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptLength:

    def test_total_injection_under_800_chars(self):
        """Output of build_correction_context is always <= MAX_PROMPT_CHARS."""
        from backend.services.correction_patterns import (
            build_correction_context, _compute_patterns, MAX_PROMPT_CHARS
        )

        # Build a large dataset that could produce a long output
        all_types = ["short_answer", "essay", "vocabulary", "summary", "open_ended",
                     "multiple_choice", "true_false", "matching"]
        corrections = []
        for qt in all_types:
            for _ in range(10):
                corrections.append({
                    "ai_score": 3, "teacher_score": 8, "max_points": 10,
                    "delta": 5, "question_type": qt, "subject": "Language Arts",
                    "grade_level": "10", "assignment": "Semester Final",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "student_answer_snippet": "A" * 120,  # Long snippet
                })

        teacher_data = {
            "corrections": corrections,
            "patterns": _compute_patterns(corrections),
            "updated_at": "",
        }
        global_data = {
            "corrections": [
                {
                    "ai_score": 3, "teacher_score": 8, "max_points": 10,
                    "delta": 5, "question_type": qt, "subject": "English",
                    "grade_level": "10", "assignment": "Final", "timestamp": "2026-01-01T00:00:00+00:00",
                }
                for qt in all_types for _ in range(5)
            ],
            "patterns": _compute_patterns([
                {"delta": 5, "question_type": qt}
                for qt in all_types for _ in range(5)
            ]),
            "teacher_hashes": {qt: [f"h{i:012x}" for i in range(5)] for qt in all_types},
            "updated_at": "",
        }

        with patch(f"{MODULE}._load_corrections", return_value=teacher_data), \
             patch(f"{MODULE}._load_global", return_value=global_data):

            result = build_correction_context(
                teacher_id="teacher-abc",
                subject="Language Arts",
                question_types=all_types,
            )

        assert len(result) <= MAX_PROMPT_CHARS
