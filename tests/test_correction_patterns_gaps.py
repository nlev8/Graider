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


class TestStorageKeysContractViaRecordCorrection:
    """PR #271 Codex round-1 MINOR fold: test the storage-key contract
    through the public `record_correction` entry point instead of patching
    private one-line wrappers. This still hits coverage lines 52 and 65
    (the wrappers' bodies) AND pins the contract that callers depend on:
    per-teacher data lands at `grading_corrections:<teacher_id>` while
    global data lands at `grading_corrections:global:system`.
    """

    def test_record_correction_routes_save_calls_to_correct_keys(self):
        from backend.services.correction_patterns import record_correction

        with patch(f"{MODULE}._load_corrections",
                   return_value={"corrections": [], "patterns": {},
                                 "updated_at": ""}), \
             patch(f"{MODULE}._load_global",
                   return_value={"corrections": [], "patterns": {},
                                 "teacher_hashes": {}, "updated_at": ""}), \
             patch(f"{MODULE}.save") as mock_save:
            record_correction(
                teacher_id="teacher-7",
                ai_score=5, teacher_score=8, max_points=10,
                question_type="essay",
                subject="English", grade_level="8",
                assignment="Quiz",
            )

        # Two save calls, in order: per-teacher then global
        assert mock_save.call_count == 2
        first, second = mock_save.call_args_list

        # Per-teacher save: namespaced key + teacher's own ID
        assert first.args[0] == "grading_corrections"
        assert first.args[2] == "teacher-7"

        # Global save: ':global' suffix + 'system' as owner
        assert second.args[0] == "grading_corrections:global"
        assert second.args[2] == "system"


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
        # When FLASK_SECRET_KEY is unset, falls back to "graider-default-salt".
        # PR #271 Codex round-1 MINOR fold: assert the EXACT hash, not just
        # length, to prove the default salt was actually used. Otherwise any
        # 12-char output (e.g. fallback to a different default) would pass.
        from backend.services.correction_patterns import _hash_teacher
        import hashlib
        import os

        # Compute what the hash should be when default-salt is applied
        expected = hashlib.sha256(
            ("teacher-x" + "graider-default-salt").encode()
        ).hexdigest()[:12]

        # Remove FLASK_SECRET_KEY if set so the `or` fallback fires
        env_no_salt = {k: v for k, v in os.environ.items()
                       if k != "FLASK_SECRET_KEY"}
        with patch.dict("os.environ", env_no_salt, clear=True):
            h = _hash_teacher("teacher-x")
        assert h == expected, (
            f"Expected default-salt hash {expected!r} but got {h!r}. "
            f"This means _hash_teacher's fallback salt isn't 'graider-default-salt'."
        )
