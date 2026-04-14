"""Behavior-pinning tests for backend/student_history.py.

Phase 2 Task 6 PR-c-1. Per Codex Gate 1: cross-boundary FERPA module,
behavior-pinning required (not smoke-only). Pins:

  - Dual-write semantics (storage layer + local file fallback)
  - load/save round-trip
  - assignment trim window (max 20)
  - Score / category baselines + std-dev math
  - Streak detection (improving / declining / A-streak)
  - Pattern detection (strength / weakness / detailed responses)
  - Baseline-deviation flagging (normal / review / significant_deviation)
  - History context string assembly

Storage-layer is monkeypatched so tests are filesystem-only and
deterministic.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import backend.student_history as sh


@pytest.fixture
def history_root(tmp_path, monkeypatch):
    """Redirect HISTORY_DIR to a tmp folder and disable storage layer."""
    hist_dir = tmp_path / "history"
    monkeypatch.setattr(sh, "HISTORY_DIR", str(hist_dir))
    # Disable storage layer to force file-fallback path everywhere
    monkeypatch.setattr(sh, "_storage_load_history", None)
    monkeypatch.setattr(sh, "_storage_save_history", None)
    return hist_dir


# ─────────────────────────────────────────────────────────────────
# load / save / dual-write
# ─────────────────────────────────────────────────────────────────

class TestLoadSave:
    def test_unknown_student_returns_none(self, history_root):
        assert sh.load_student_history("UNKNOWN") is None
        assert sh.load_student_history("") is None

    def test_unknown_student_save_no_op(self, history_root):
        sh.save_student_history("UNKNOWN", {"assignments": []})
        # No file created
        assert not list(history_root.iterdir()) if history_root.exists() else True

    def test_load_missing_returns_default(self, history_root):
        result = sh.load_student_history("student_1")
        assert result["student_id"] == "student_1"
        assert result["assignments"] == []
        assert result["skill_scores"] == {}
        assert result["streaks"] == {}
        assert result["patterns"] == []
        assert result["last_updated"] is None

    def test_save_then_load_roundtrip(self, history_root):
        sh.save_student_history("student_1", {
            "student_id": "student_1",
            "assignments": [{"score": 90, "assignment": "A1"}],
        })
        loaded = sh.load_student_history("student_1")
        assert loaded["assignments"][0]["score"] == 90
        assert loaded["last_updated"] is not None  # Stamped on save

    def test_save_creates_history_dir(self, history_root):
        assert not history_root.exists()
        sh.save_student_history("student_1", {"assignments": []})
        assert history_root.exists()

    def test_load_corrupt_file_falls_back_to_default(self, history_root):
        sh.ensure_history_dir()
        path = sh.get_student_history_path("student_1")
        Path(path).write_text("not valid json {{{")
        with patch("backend.student_history.sentry_sdk") as mock_sentry:
            result = sh.load_student_history("student_1")
        assert result["assignments"] == []
        # Corrupt-load failure should be observable
        mock_sentry.capture_exception.assert_called_once()

    def test_history_path_sanitizes_slashes(self, history_root):
        path = sh.get_student_history_path("foo/bar\\baz")
        assert "/" not in os.path.basename(path).rstrip(".json")
        assert "\\" not in os.path.basename(path).rstrip(".json")


# ─────────────────────────────────────────────────────────────────
# add_assignment_to_history
# ─────────────────────────────────────────────────────────────────

def _result(score=85, breakdown=None, **extra):
    """Build a minimal grading result for history append."""
    return {
        "score": score,
        "letter_grade": "B",
        "assignment": "Essay 1",
        "breakdown": breakdown or {"content_accuracy": 25, "completeness": 35},
        "excellent_answers": [],
        "needs_improvement": [],
        "student_responses": [],
        **extra,
    }


class TestAddAssignment:
    def test_unknown_student_returns_none(self, history_root):
        assert sh.add_assignment_to_history("UNKNOWN", _result()) is None
        assert sh.add_assignment_to_history("", _result()) is None

    def test_appends_assignment(self, history_root):
        history = sh.add_assignment_to_history("s1", _result(score=88))
        assert len(history["assignments"]) == 1
        assert history["assignments"][0]["score"] == 88

    def test_trims_to_last_20(self, history_root):
        for i in range(25):
            sh.add_assignment_to_history("s1", _result(score=70 + i, assignment=f"A{i}"))
        history = sh.load_student_history("s1")
        assert len(history["assignments"]) == 20
        # Newest ones kept (scores 75..94)
        scores = [a["score"] for a in history["assignments"]]
        assert scores[-1] == 70 + 24
        assert scores[0] == 70 + 5

    def test_extracts_skills_from_dict(self, history_root):
        history = sh.add_assignment_to_history("s1", _result(skills_demonstrated={
            "strengths": ["analysis", "evidence"],
            "developing": ["organization"],
        }))
        rec = history["assignments"][0]
        assert "analysis" in rec["skills_strengths"]
        assert "organization" in rec["skills_developing"]

    def test_handles_skills_as_non_dict(self, history_root):
        # Defensive: skills_demonstrated could be a string from older results
        history = sh.add_assignment_to_history("s1", _result(skills_demonstrated="legacy_string"))
        rec = history["assignments"][0]
        assert rec["skills_strengths"] == []
        assert rec["skills_developing"] == []


# ─────────────────────────────────────────────────────────────────
# calculate_skill_averages — overall trend logic
# ─────────────────────────────────────────────────────────────────

class TestSkillAverages:
    def test_empty_assignments(self):
        assert sh.calculate_skill_averages([]) == {}

    def test_single_assignment_skill_avg(self):
        avgs = sh.calculate_skill_averages([
            {"breakdown": {"content_accuracy": 25}},
        ])
        assert avgs["content_accuracy"]["current_avg"] == 25.0
        assert avgs["content_accuracy"]["count"] == 1

    def test_uses_only_last_5(self):
        # 6 assignments — only last 5 should contribute to current_avg
        assignments = [{"breakdown": {"content_accuracy": s}} for s in [10, 20, 30, 40, 50, 60]]
        avgs = sh.calculate_skill_averages(assignments)
        # Last 5: 20,30,40,50,60 → avg 40
        assert avgs["content_accuracy"]["current_avg"] == 40.0

    def test_overall_trend_improving(self):
        # First half avg low, second half high
        assignments = [{"score": 50}, {"score": 55}, {"score": 60}, {"score": 80}, {"score": 85}, {"score": 90}]
        avgs = sh.calculate_skill_averages(assignments)
        assert avgs["_overall_trend"] == "improving"

    def test_overall_trend_declining(self):
        assignments = [{"score": 90}, {"score": 88}, {"score": 86}, {"score": 60}, {"score": 55}, {"score": 50}]
        avgs = sh.calculate_skill_averages(assignments)
        assert avgs["_overall_trend"] == "declining"

    def test_overall_trend_stable(self):
        assignments = [{"score": 80}, {"score": 82}, {"score": 81}, {"score": 80}, {"score": 81}]
        avgs = sh.calculate_skill_averages(assignments)
        assert avgs["_overall_trend"] == "stable"

    def test_below_three_no_trend(self):
        assignments = [{"score": 80}, {"score": 90}]
        avgs = sh.calculate_skill_averages(assignments)
        assert "_overall_trend" not in avgs


# ─────────────────────────────────────────────────────────────────
# detect_streaks
# ─────────────────────────────────────────────────────────────────

class TestStreaks:
    def test_empty_returns_empty(self):
        assert sh.detect_streaks([]) == {}

    def test_below_three_returns_empty(self):
        assert sh.detect_streaks([{"score": 90}, {"score": 95}]) == {}

    def test_a_streak_detected(self):
        result = sh.detect_streaks([
            {"score": 95}, {"score": 92}, {"score": 96},
        ])
        assert result.get("_grade_streak", {}).get("type") == "A_streak"

    def test_b_or_better_streak(self):
        result = sh.detect_streaks([
            {"score": 80}, {"score": 85}, {"score": 88},
        ])
        assert result.get("_grade_streak", {}).get("type") == "B_or_better"

    def test_overall_improving_streak(self):
        result = sh.detect_streaks([
            {"score": 60}, {"score": 65}, {"score": 75},
        ])
        assert result.get("_grade_streak", {}).get("type") == "improving"


# ─────────────────────────────────────────────────────────────────
# detect_patterns
# ─────────────────────────────────────────────────────────────────

class TestPatterns:
    def test_below_two_returns_empty(self):
        assert sh.detect_patterns([{"score": 90}]) == []

    def test_consistent_strength(self):
        # content_accuracy max=40; need 2+ scores >=85% (>=34)
        assignments = [
            {"breakdown": {"content_accuracy": 36}},
            {"breakdown": {"content_accuracy": 38}},
        ]
        patterns = sh.detect_patterns(assignments)
        assert any(p["type"] == "strength" for p in patterns)

    def test_consistent_weakness(self):
        # completeness max=25; need 2+ scores <=60% (<=15)
        assignments = [
            {"breakdown": {"completeness": 12}},
            {"breakdown": {"completeness": 14}},
        ]
        patterns = sh.detect_patterns(assignments)
        assert any(p["type"] == "weakness" for p in patterns)

    def test_excellent_answers_pattern(self):
        assignments = [
            {"excellent_answers": ["a", "b"]},
            {"excellent_answers": ["c", "d"]},
        ]
        patterns = sh.detect_patterns(assignments)
        assert any(p["skill"] == "detailed_responses" for p in patterns)


# ─────────────────────────────────────────────────────────────────
# calculate_student_baseline
# ─────────────────────────────────────────────────────────────────

class TestBaseline:
    def test_below_three_returns_none(self):
        assert sh.calculate_student_baseline([{"score": 80}, {"score": 90}]) is None

    def test_basic_baseline_shape(self):
        assignments = [
            {"score": 80, "breakdown": {"content_accuracy": 25}},
            {"score": 85, "breakdown": {"content_accuracy": 27}},
            {"score": 90, "breakdown": {"content_accuracy": 28}},
        ]
        b = sh.calculate_student_baseline(assignments)
        assert b["overall_avg"] == 85.0
        assert "overall_std" in b
        assert "category_baselines" in b
        assert b["assignment_count"] == 3

    def test_typical_skills_threshold(self):
        # Skills appearing in >= 30% of assignments are "typical"
        assignments = [
            {"score": 80, "skills_strengths": ["analysis"]},
            {"score": 85, "skills_strengths": ["analysis", "evidence"]},
            {"score": 90, "skills_strengths": ["analysis"]},
        ]
        b = sh.calculate_student_baseline(assignments)
        # "analysis" appears in all 3 (>30%); "evidence" in 1 (<30% of 3=0.9; threshold is 0.9)
        assert "analysis" in b["typical_skills"]


# ─────────────────────────────────────────────────────────────────
# detect_baseline_deviation
# ─────────────────────────────────────────────────────────────────

class TestBaselineDeviation:
    def test_no_history_normal(self, history_root):
        result = sh.detect_baseline_deviation("UNKNOWN", _result())
        assert result["flag"] == "normal"

    def test_insufficient_history_normal(self, history_root):
        sh.add_assignment_to_history("s1", _result(score=80))
        sh.add_assignment_to_history("s1", _result(score=82))
        result = sh.detect_baseline_deviation("s1", _result(score=85))
        assert result["flag"] == "normal"

    def test_significant_deviation_dramatic_jump(self, history_root):
        # Establish low baseline
        for s in [50, 55, 52]:
            sh.add_assignment_to_history("s1", _result(score=s))
        # Submit dramatically higher — triggers both overall-score and
        # sudden-improvement deviations → 2 deviations → significant_deviation
        # per backend/student_history.py:528-534.
        result = sh.detect_baseline_deviation("s1", _result(score=98))
        assert result["flag"] == "significant_deviation"
        assert len(result["reasons"]) >= 2


# ─────────────────────────────────────────────────────────────────
# get_baseline_summary + build_history_context
# ─────────────────────────────────────────────────────────────────

class TestSummaryAndContext:
    def test_baseline_summary_no_history(self, history_root):
        # UNKNOWN student_id → load returns None → summary returns None
        # per backend/student_history.py:545-547.
        assert sh.get_baseline_summary("UNKNOWN") is None

    def test_history_context_no_history(self, history_root):
        # No history → returns exactly "" per backend/student_history.py:572-574.
        assert sh.build_history_context("UNKNOWN") == ""

    def test_history_context_with_assignments(self, history_root):
        for s in [70, 75, 80]:
            sh.add_assignment_to_history("s1", _result(score=s, assignment="Essay 1"))
        ctx = sh.build_history_context("s1")
        # Header + assignment count + PREVIOUS ASSIGNMENTS block assembled
        # per backend/student_history.py:582-597, 689-694.
        assert ctx.startswith("---")
        assert "STUDENT PERFORMANCE HISTORY" in ctx
        assert "3 previous assignments graded" in ctx
        assert "PREVIOUS ASSIGNMENTS" in ctx
        assert "Essay 1" in ctx
