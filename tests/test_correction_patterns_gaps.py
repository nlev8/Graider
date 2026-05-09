"""Targeted coverage extension for backend/services/correction_patterns.py.

Audit MAJOR #4 sprint follow-up to PR #270. The module is at 93% coverage
already (`tests/test_correction_patterns.py` has good baseline coverage),
but 8 lines remain unhit:

  * 15-16 — ImportError fallback for `from backend.storage import ...`
  * 46    — `_load_corrections` returns default dict when storage empty
  * 59    — `_load_global` returns default dict when storage empty
  * 99-102 — `_compute_patterns` direction branches: up / down / none
  * 180   — `record_correction` global-corrections trim at MAX_CORRECTIONS

This file adds focused tests for the reachable lines (46, 59, 99-102, 180).
Lines 15-16 are an import-time fallback that requires reload-with-stub
(out of scope for a small extension; documented as intentionally
unexercised here).

Per `feedback_codex_medium_effort_2026-05-09.md` (session-temp), the merge
review uses Codex medium effort once the daily limit resets.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


MODULE = "backend.services.correction_patterns"


# ──────────────────────────────────────────────────────────────────
# _load_corrections / _load_global — empty-storage fallback
# ──────────────────────────────────────────────────────────────────


class TestSaveWrappers:
    def test_save_corrections_calls_storage_with_namespaced_key(self):
        # Hit line 52: `save("grading_corrections", data, teacher_id)`
        from backend.services.correction_patterns import _save_corrections

        with patch(f"{MODULE}.save") as mock_save:
            _save_corrections("teacher-9", {"corrections": [{"x": 1}]})
        mock_save.assert_called_once_with(
            "grading_corrections",
            {"corrections": [{"x": 1}]},
            "teacher-9",
        )

    def test_save_global_uses_global_key_and_system_owner(self):
        # Hit line 65: `save("grading_corrections:global", data, "system")`
        from backend.services.correction_patterns import _save_global

        with patch(f"{MODULE}.save") as mock_save:
            _save_global({"corrections": []})
        mock_save.assert_called_once_with(
            "grading_corrections:global",
            {"corrections": []},
            "system",
        )


class TestLoadFallbacks:
    def test_load_corrections_returns_default_when_storage_empty(self):
        # Hit line 46: `if not data: return {"corrections": [], ...}`
        from backend.services.correction_patterns import _load_corrections

        with patch(f"{MODULE}.load", return_value=None):
            result = _load_corrections("teacher-1")
        assert result == {"corrections": [], "patterns": {}, "updated_at": ""}

    def test_load_corrections_returns_data_when_present(self):
        # Symmetric pin: confirms the early-return only fires for empty data
        from backend.services.correction_patterns import _load_corrections

        canned = {
            "corrections": [{"delta": 1}],
            "patterns": {"essay": {"count": 1}},
            "updated_at": "2026-05-09T00:00:00Z",
        }
        with patch(f"{MODULE}.load", return_value=canned):
            assert _load_corrections("teacher-1") == canned

    def test_load_global_returns_default_when_storage_empty(self):
        # Hit line 59: `if not data: return {... "teacher_hashes": {} ...}`
        from backend.services.correction_patterns import _load_global

        with patch(f"{MODULE}.load", return_value=None):
            result = _load_global()
        assert result == {
            "corrections": [],
            "patterns": {},
            "teacher_hashes": {},
            "updated_at": "",
        }

    def test_load_global_returns_data_when_present(self):
        from backend.services.correction_patterns import _load_global

        canned = {
            "corrections": [{"delta": 0}],
            "patterns": {},
            "teacher_hashes": {"essay": ["abc123"]},
            "updated_at": "2026-05-09T00:00:00Z",
        }
        with patch(f"{MODULE}.load", return_value=canned):
            assert _load_global() == canned


# ──────────────────────────────────────────────────────────────────
# _compute_patterns — direction branches
# ──────────────────────────────────────────────────────────────────


class TestComputePatternsDirection:
    """Pin all three direction branches at lines 97-102.

    Production:
        if avg > 0.1:    direction = "up"
        elif avg < -0.1: direction = "down"
        else:            direction = "none"
    """

    def test_direction_up_when_avg_above_threshold(self):
        from backend.services.correction_patterns import _compute_patterns

        corrections = [
            {"question_type": "essay", "delta": 2},
            {"question_type": "essay", "delta": 3},
        ]
        # avg = 2.5 → direction "up"
        result = _compute_patterns(corrections)
        assert result["essay"]["direction"] == "up"
        assert result["essay"]["avg_delta"] == 2.5
        assert result["essay"]["count"] == 2

    def test_direction_down_when_avg_below_negative_threshold(self):
        from backend.services.correction_patterns import _compute_patterns

        corrections = [
            {"question_type": "short_answer", "delta": -1},
            {"question_type": "short_answer", "delta": -2},
        ]
        # avg = -1.5 → direction "down"
        result = _compute_patterns(corrections)
        assert result["short_answer"]["direction"] == "down"
        assert result["short_answer"]["avg_delta"] == -1.5

    def test_direction_none_when_avg_within_threshold(self):
        from backend.services.correction_patterns import _compute_patterns

        # avg = 0.0 (one +1, one -1) → direction "none"
        corrections = [
            {"question_type": "matching", "delta": 1},
            {"question_type": "matching", "delta": -1},
        ]
        result = _compute_patterns(corrections)
        assert result["matching"]["direction"] == "none"
        assert result["matching"]["avg_delta"] == 0.0

    def test_direction_none_at_positive_boundary(self):
        # avg = 0.1 exactly is NOT > 0.1 → "none" branch (else)
        from backend.services.correction_patterns import _compute_patterns

        corrections = [
            {"question_type": "vocab", "delta": 0.1},
        ]
        result = _compute_patterns(corrections)
        assert result["vocab"]["direction"] == "none"

    def test_direction_none_at_negative_boundary(self):
        # avg = -0.1 exactly is NOT < -0.1 → "none" branch
        from backend.services.correction_patterns import _compute_patterns

        corrections = [
            {"question_type": "vocab", "delta": -0.1},
        ]
        result = _compute_patterns(corrections)
        assert result["vocab"]["direction"] == "none"

    def test_direction_up_just_above_boundary(self):
        from backend.services.correction_patterns import _compute_patterns

        # avg = 0.11 → just above 0.1 → "up"
        corrections = [
            {"question_type": "essay", "delta": 0.11},
        ]
        result = _compute_patterns(corrections)
        assert result["essay"]["direction"] == "up"

    def test_direction_down_just_below_negative_boundary(self):
        from backend.services.correction_patterns import _compute_patterns

        # avg = -0.11 → just below -0.1 → "down"
        corrections = [
            {"question_type": "essay", "delta": -0.11},
        ]
        result = _compute_patterns(corrections)
        assert result["essay"]["direction"] == "down"

    def test_missing_question_type_uses_unknown_bucket(self):
        # `c.get("question_type", "unknown")` — pin the fallback bucket name
        from backend.services.correction_patterns import _compute_patterns

        corrections = [
            {"delta": 0.5},  # no question_type key
        ]
        result = _compute_patterns(corrections)
        assert "unknown" in result
        assert result["unknown"]["count"] == 1

    def test_missing_delta_treated_as_zero(self):
        # `c.get("delta", 0)` fallback
        from backend.services.correction_patterns import _compute_patterns

        corrections = [
            {"question_type": "essay"},  # no delta
            {"question_type": "essay", "delta": 1},
        ]
        result = _compute_patterns(corrections)
        # avg = (0 + 1) / 2 = 0.5 → up
        assert result["essay"]["avg_delta"] == 0.5
        assert result["essay"]["direction"] == "up"

    def test_empty_corrections_returns_empty_patterns(self):
        from backend.services.correction_patterns import _compute_patterns

        assert _compute_patterns([]) == {}

    def test_avg_delta_rounded_to_two_decimals(self):
        from backend.services.correction_patterns import _compute_patterns

        # Three deltas that average to 0.333... → should round to 0.33
        corrections = [
            {"question_type": "essay", "delta": 1},
            {"question_type": "essay", "delta": 0},
            {"question_type": "essay", "delta": 0},
        ]
        result = _compute_patterns(corrections)
        assert result["essay"]["avg_delta"] == 0.33


# ──────────────────────────────────────────────────────────────────
# record_correction — global trim at MAX_CORRECTIONS
# ──────────────────────────────────────────────────────────────────


class TestRecordCorrectionGlobalTrim:
    def test_global_corrections_trimmed_to_max(self):
        # Hit line 180: `if len(global_data["corrections"]) > MAX_CORRECTIONS:
        # global_data["corrections"] = global_data["corrections"][-MAX_CORRECTIONS:]`
        from backend.services.correction_patterns import (
            record_correction, MAX_CORRECTIONS,
        )

        # Pre-fill global with MAX_CORRECTIONS entries — the new one pushes
        # over the cap
        existing = [
            {
                "ai_score": 5, "teacher_score": 6, "max_points": 10,
                "delta": 1, "question_type": "essay", "subject": "Old",
                "grade_level": "8", "assignment": "Old",
                "timestamp": f"2026-01-{i % 28 + 1:02d}T00:00:00+00:00",
            }
            for i in range(MAX_CORRECTIONS)
        ]
        pre_global = {
            "corrections": existing,
            "patterns": {},
            "teacher_hashes": {"essay": ["existing-hash"]},
            "updated_at": "",
        }

        global_saved = {}

        with patch(f"{MODULE}._load_corrections",
                   return_value={"corrections": [], "patterns": {}, "updated_at": ""}), \
             patch(f"{MODULE}._save_corrections"), \
             patch(f"{MODULE}._load_global", return_value=pre_global), \
             patch(f"{MODULE}._save_global",
                   side_effect=lambda d: global_saved.update({"data": d})):

            record_correction(
                teacher_id="teacher-1",
                ai_score=5, teacher_score=8, max_points=10,
                question_type="short_answer",
                subject="English", grade_level="8",
                assignment="New Quiz",
            )

        # Global cap enforced — trimmed back to MAX_CORRECTIONS
        assert len(global_saved["data"]["corrections"]) == MAX_CORRECTIONS, (
            f"Expected global trim to {MAX_CORRECTIONS}; got "
            f"{len(global_saved['data']['corrections'])}"
        )
        # The newest correction (the one we just added) is preserved at the end
        last = global_saved["data"]["corrections"][-1]
        assert last["assignment"] == "New Quiz"
        assert last["question_type"] == "short_answer"

    def test_global_no_trim_when_under_cap(self):
        # Symmetric pin: stays under cap, no trimming
        from backend.services.correction_patterns import (
            record_correction, MAX_CORRECTIONS,
        )

        # Pre-fill with MAX_CORRECTIONS - 1 entries — adding one stays at cap
        existing = [
            {
                "ai_score": 5, "teacher_score": 6, "max_points": 10,
                "delta": 1, "question_type": "essay", "subject": "Old",
                "grade_level": "8", "assignment": f"Old-{i}",
                "timestamp": f"2026-01-{i % 28 + 1:02d}T00:00:00+00:00",
            }
            for i in range(MAX_CORRECTIONS - 1)
        ]
        pre_global = {
            "corrections": existing,
            "patterns": {},
            "teacher_hashes": {},
            "updated_at": "",
        }
        global_saved = {}

        with patch(f"{MODULE}._load_corrections",
                   return_value={"corrections": [], "patterns": {}, "updated_at": ""}), \
             patch(f"{MODULE}._save_corrections"), \
             patch(f"{MODULE}._load_global", return_value=pre_global), \
             patch(f"{MODULE}._save_global",
                   side_effect=lambda d: global_saved.update({"data": d})):

            record_correction(
                teacher_id="teacher-1",
                ai_score=5, teacher_score=8, max_points=10,
                question_type="short_answer",
                subject="English", grade_level="8",
                assignment="One More",
            )

        # Exactly at cap — no trim should fire (path through `if` is False)
        assert len(global_saved["data"]["corrections"]) == MAX_CORRECTIONS


# ──────────────────────────────────────────────────────────────────
# _hash_teacher — anonymization helper
# ──────────────────────────────────────────────────────────────────


class TestHashTeacher:
    def test_hash_is_deterministic(self):
        # Same teacher_id with same salt → same hash
        from backend.services.correction_patterns import _hash_teacher

        with patch.dict("os.environ", {"FLASK_SECRET_KEY": "test-salt"}):
            h1 = _hash_teacher("teacher-abc")
            h2 = _hash_teacher("teacher-abc")
        assert h1 == h2

    def test_hash_is_12_chars(self):
        from backend.services.correction_patterns import _hash_teacher

        h = _hash_teacher("any-id")
        assert len(h) == 12

    def test_different_teachers_get_different_hashes(self):
        from backend.services.correction_patterns import _hash_teacher

        with patch.dict("os.environ", {"FLASK_SECRET_KEY": "test-salt"}):
            h_a = _hash_teacher("teacher-a")
            h_b = _hash_teacher("teacher-b")
        assert h_a != h_b

    def test_hash_uses_salt_from_env(self):
        # Different salt should produce different hash for the same teacher
        from backend.services.correction_patterns import _hash_teacher

        with patch.dict("os.environ", {"FLASK_SECRET_KEY": "salt-1"}):
            h1 = _hash_teacher("teacher-x")
        with patch.dict("os.environ", {"FLASK_SECRET_KEY": "salt-2"}):
            h2 = _hash_teacher("teacher-x")
        assert h1 != h2

    def test_hash_falls_back_to_default_salt(self):
        # When FLASK_SECRET_KEY is unset, falls back to "graider-default-salt"
        from backend.services.correction_patterns import _hash_teacher
        import os

        # Remove the env var if set
        env_no_salt = {k: v for k, v in os.environ.items()
                       if k != "FLASK_SECRET_KEY"}
        with patch.dict("os.environ", env_no_salt, clear=True):
            h = _hash_teacher("teacher-x")
        # Hash is still 12 chars (fallback worked, didn't crash)
        assert len(h) == 12
