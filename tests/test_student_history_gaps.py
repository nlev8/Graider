"""Gap-fill tests for backend/student_history.py.

Audit MAJOR #4 sprint follow-up to PR #311. Targets the 81 uncovered
LOC (77.3% baseline → 95%+ goal). Companion to existing
`tests/test_student_history.py` which pins the dual-write contract +
score/baseline math; this file fills the prompt-formatting branches
in `build_history_context`, the streak edges in
`detect_skill_patterns`, and the per-category deviation flags in
`detect_baseline_deviation`.

Branches covered
* `load_student_history` storage-hit short-circuit + storage-miss
  file fallback + corrupt-file sentry capture
* `save_student_history` file-write OSError swallow + storage dual-
  write call
* `detect_streaks` improving/declining streak detection (lines 235,
  241)
* `detect_skill_patterns` improving + needs_focus branches (lines
  332-379)
* `detect_baseline_deviation` per-category flag, new-skills detection,
  significant_deviation/review flag levels
* `get_baseline_summary` no-history + no-baseline returns
* `build_history_context` previous needs_improvement, declining
  trend, declining streak, weakness pattern, improving skills,
  focus skills, excellent answer continuity

Per `feedback_codex_medium_effort_2026-05-09.md`: dual-rate-limit
precedent. Test-only PR merging on green CI.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest

import backend.student_history as sh


@pytest.fixture
def history_root(tmp_path, monkeypatch):
    hist_dir = tmp_path / "history"
    monkeypatch.setattr(sh, "HISTORY_DIR", str(hist_dir))
    monkeypatch.setattr(sh, "_storage_load_history", None)
    monkeypatch.setattr(sh, "_storage_save_history", None)
    return hist_dir


# ──────────────────────────────────────────────────────────────────
# load_student_history storage layer
# ──────────────────────────────────────────────────────────────────


class TestLoadStorageLayer:
    def test_storage_hit_short_circuits(self, tmp_path, monkeypatch):
        # Storage returns data → file fallback never runs
        hist_dir = tmp_path / "history"
        monkeypatch.setattr(sh, "HISTORY_DIR", str(hist_dir))

        mock_load = MagicMock(return_value={"from": "storage"})
        monkeypatch.setattr(sh, "_storage_load_history", mock_load)
        monkeypatch.setattr(sh, "_storage_save_history", None)

        result = sh.load_student_history(
            student_id="sid-1", teacher_id="teach-1",
        )
        assert result == {"from": "storage"}
        mock_load.assert_called_once_with(
            teacher_id="teach-1", student_id="sid-1",
        )

    def test_storage_miss_falls_back_to_file(self, tmp_path, monkeypatch):
        # VB2b (audit #3): the file fallback is now tenant-scoped. For a real
        # teacher_id it reads ~/.graider_tenants/<safe>/.graider_data/
        # student_history/ — NOT the shared global dir (which leaked across
        # tenants). Pre-write the tenant file and assert the miss falls back
        # to it.
        from backend import storage as st
        monkeypatch.setattr(st, "HOME", str(tmp_path))
        tenant_dir = (tmp_path / ".graider_tenants" / "teach-1"
                      / ".graider_data" / "student_history")
        tenant_dir.mkdir(parents=True)
        (tenant_dir / "sid-1.json").write_text(
            json.dumps({"from": "file", "assignments": []}),
        )

        monkeypatch.setattr(
            sh, "_storage_load_history", MagicMock(return_value=None),
        )
        monkeypatch.setattr(sh, "_storage_save_history", None)

        result = sh.load_student_history(
            student_id="sid-1", teacher_id="teach-1",
        )
        assert result == {"from": "file", "assignments": []}

    def test_corrupt_file_sentry_capture(self, tmp_path, monkeypatch):
        hist_dir = tmp_path / "history"
        hist_dir.mkdir()
        (hist_dir / "sid-1.json").write_text("not valid json")

        monkeypatch.setattr(sh, "HISTORY_DIR", str(hist_dir))
        monkeypatch.setattr(sh, "_storage_load_history", None)
        monkeypatch.setattr(sh, "_storage_save_history", None)

        with patch.object(sh.sentry_sdk, "capture_exception") as mock_sentry:
            result = sh.load_student_history(student_id="sid-1")

        # Sentry alerted
        mock_sentry.assert_called_once()
        # Default empty history shape returned
        assert result["student_id"] == "sid-1"
        assert result["assignments"] == []


# ──────────────────────────────────────────────────────────────────
# save_student_history exception + storage dual-write
# ──────────────────────────────────────────────────────────────────


class TestSaveExceptionAndStorage:
    def test_file_write_exception_swallowed(self, history_root):
        # Patch open to raise; sentry should capture but no raise
        with patch("builtins.open", side_effect=OSError("disk full")), \
             patch.object(sh.sentry_sdk, "capture_exception") as mock_sentry:
            sh.save_student_history("sid-1", {"assignments": []})
        mock_sentry.assert_called_once()

    def test_storage_dual_write_called_when_available(
        self, tmp_path, monkeypatch,
    ):
        hist_dir = tmp_path / "history"
        monkeypatch.setattr(sh, "HISTORY_DIR", str(hist_dir))

        mock_save = MagicMock()
        monkeypatch.setattr(sh, "_storage_load_history", None)
        monkeypatch.setattr(sh, "_storage_save_history", mock_save)

        history = {"assignments": [{"score": 80}]}
        sh.save_student_history(
            student_id="sid-1", history=history, teacher_id="teach-1",
        )

        mock_save.assert_called_once()
        # Verify last_updated injected
        kwargs = mock_save.call_args.kwargs
        assert kwargs["teacher_id"] == "teach-1"
        assert kwargs["student_id"] == "sid-1"
        assert kwargs["history"]["assignments"] == [{"score": 80}]
        assert "last_updated" in kwargs["history"]


# ──────────────────────────────────────────────────────────────────
# detect_streaks improving/declining branches
# ──────────────────────────────────────────────────────────────────


class TestDetectStreaks:
    def test_improving_streak_detected(self):
        # 3 increasing scores in last 3 → improving
        assignments = [
            {"breakdown": {"content_accuracy": 30}},
            {"breakdown": {"content_accuracy": 35}},
            {"breakdown": {"content_accuracy": 38}},
        ]
        streaks = sh.detect_streaks(assignments)
        assert streaks["content_accuracy"]["type"] == "improving"
        assert streaks["content_accuracy"]["latest_score"] == 38

    def test_declining_streak_detected(self):
        assignments = [
            {"breakdown": {"content_accuracy": 38}},
            {"breakdown": {"content_accuracy": 35}},
            {"breakdown": {"content_accuracy": 30}},
        ]
        streaks = sh.detect_streaks(assignments)
        assert streaks["content_accuracy"]["type"] == "declining"
        assert streaks["content_accuracy"]["latest_score"] == 30


# ──────────────────────────────────────────────────────────────────
# detect_skill_patterns - improving + needs_focus branches
# ──────────────────────────────────────────────────────────────────


class TestDetectSkillPatterns:
    def test_below_two_returns_empty_shape(self):
        result = sh.detect_skill_patterns([{}])
        assert result == {
            "consistent_strengths": [], "improving": [], "needs_focus": [],
        }

    def test_consistent_strength_detected(self):
        assignments = [
            {"skills_strengths": ["reading"]},
            {"skills_strengths": ["reading", "writing"]},
            {"skills_strengths": ["reading"]},
        ]
        result = sh.detect_skill_patterns(assignments)
        skills = [s["skill"] for s in result["consistent_strengths"]]
        assert "reading" in skills

    def test_improving_skill_detected(self):
        # Skill appears in BOTH strengths + developing across history,
        # but recent (last 3) shows it as strength more than developing
        assignments = [
            # Older: appears as developing
            {"skills_developing": ["math"], "skills_strengths": []},
            {"skills_developing": ["math"], "skills_strengths": []},
            # Recent (last 3): appears as strength more than developing
            {"skills_strengths": ["math"], "skills_developing": []},
            {"skills_strengths": ["math"], "skills_developing": []},
            {"skills_strengths": ["math"], "skills_developing": []},
        ]
        result = sh.detect_skill_patterns(assignments)
        skills = [s["skill"] for s in result["improving"]]
        assert "math" in skills

    def test_needs_focus_detected(self):
        # Skill appears as developing in 2+ assignments and NOT in improving
        assignments = [
            {"skills_developing": ["spelling"]},
            {"skills_developing": ["spelling"]},
            {"skills_strengths": []},
        ]
        result = sh.detect_skill_patterns(assignments)
        skills = [s["skill"] for s in result["needs_focus"]]
        assert "spelling" in skills

    def test_non_string_skills_ignored(self):
        # isinstance(skill, str) filter — non-strings shouldn't count
        assignments = [
            {"skills_strengths": [None, 123, "reading"]},
            {"skills_strengths": [{"obj": True}, "reading"]},
        ]
        result = sh.detect_skill_patterns(assignments)
        skills = [s["skill"] for s in result["consistent_strengths"]]
        assert "reading" in skills
        # Garbage didn't show up as a strength
        for s in skills:
            assert isinstance(s, str)


# ──────────────────────────────────────────────────────────────────
# detect_baseline_deviation - per-category flag + new skills + flag levels
# ──────────────────────────────────────────────────────────────────


class TestBaselineDeviationGaps:
    @pytest.fixture
    def seeded_history(self, history_root):
        # Seed a history with 5 baseline assignments at modest scores
        # so std is small + baseline is established
        history = {
            "student_id": "sid-1",
            "assignments": [
                {"score": 70, "breakdown": {"content_accuracy": 25,
                                            "completeness": 18},
                 "skills_strengths": ["reading"]},
                {"score": 72, "breakdown": {"content_accuracy": 26,
                                            "completeness": 18},
                 "skills_strengths": ["reading"]},
                {"score": 68, "breakdown": {"content_accuracy": 24,
                                            "completeness": 17},
                 "skills_strengths": ["reading"]},
                {"score": 71, "breakdown": {"content_accuracy": 25,
                                            "completeness": 18},
                 "skills_strengths": ["reading"]},
                {"score": 70, "breakdown": {"content_accuracy": 25,
                                            "completeness": 18},
                 "skills_strengths": ["reading"]},
            ],
            "skill_scores": {},
            "streaks": {},
            "patterns": [],
            "last_updated": None,
        }
        sh.save_student_history("sid-1", history)
        return history

    def test_category_flag_when_above_max_seen(self, seeded_history):
        # Isolate the category-deviation branch by keeping score=70
        # (matches baseline avg ~70.2 → std_devs ~0 → no overall trigger).
        # Then content_accuracy=40 alone exceeds max_seen(26)+5 → fires
        # ONLY the category branch. Prior score=95 also triggered the
        # overall-deviation branch, making the `or` assertion vacuous.
        current = {
            "score": 70,
            "breakdown": {
                "content_accuracy": 40,  # max_seen was 26 → 40 > 26+5
                "completeness": 18,      # within baseline — no fire
            },
        }
        result = sh.detect_baseline_deviation("sid-1", current)
        joined = " ".join(result["reasons"])
        # Strict assertion: ONLY the category branch should appear.
        assert "Category deviations" in joined
        assert "above baseline" not in joined
        # Exactly 1 deviation, std_deviations ~0 → review (not significant)
        assert result["flag"] == "review"

    def test_new_skills_detected(self, seeded_history):
        # Current submission has 3+ skills NOT in baseline typical_skills
        # (baseline only has "reading" as typical). Score 72 sits ~1.2
        # std devs above baseline avg ~70.2 (sample std ~1.5) → stays
        # below the 2.5 trigger so the overall-deviation branch does
        # NOT fire, isolating the new-skills branch. Prior score 75
        # was ~3.2 std devs above and DID accidentally trigger overall.
        current = {
            "score": 72,
            "breakdown": {
                "content_accuracy": 26, "completeness": 18,
            },
            "skills_demonstrated": {
                "strengths": [
                    "advanced critical thinking",
                    "sophisticated source synthesis",
                    "rhetorical analysis",
                ],
            },
        }
        result = sh.detect_baseline_deviation("sid-1", current)
        joined = " ".join(result["reasons"])
        assert "new skills" in joined.lower()

    def test_significant_deviation_flag_with_two_reasons(
        self, seeded_history,
    ):
        # Trigger 2+ deviations → significant_deviation
        current = {
            "score": 95,  # +25 from recent avg → triggers sudden improvement
            "breakdown": {
                "content_accuracy": 40,  # exceeds max_seen by >5
            },
            "skills_demonstrated": {
                "strengths": [
                    "advanced critical thinking",
                    "sophisticated source synthesis",
                    "rhetorical analysis",
                ],
            },
        }
        result = sh.detect_baseline_deviation("sid-1", current)
        assert result["flag"] == "significant_deviation"
        assert len(result["reasons"]) >= 2

    def test_review_flag_with_single_reason(self, seeded_history):
        # Hit the "review" branch: len(deviations) == 1 AND
        # std_deviations <= 3. Score 70 keeps std_deviations ~0 so the
        # overall-score deviation does NOT fire. content_accuracy=32
        # exceeds max_seen(26)+5 → triggers exactly ONE category
        # deviation. Result: 1 deviation, std_devs ~0 → "review".
        # Prior score=90 had std_devs ~13 which forced the
        # significant_deviation path via the std_deviations > 3 clause,
        # making the `in ("review", "significant_deviation")` assertion
        # vacuous (it could never test the review path).
        current = {
            "score": 70,
            "breakdown": {
                "content_accuracy": 32,  # > max_seen(26)+5 → category fires
                "completeness": 18,
            },
            "skills_demonstrated": {
                "strengths": ["reading"],
            },
        }
        result = sh.detect_baseline_deviation("sid-1", current)
        # Strict assertion: this MUST hit the review branch.
        assert result["flag"] == "review"
        assert len(result["reasons"]) == 1


# ──────────────────────────────────────────────────────────────────
# get_baseline_summary
# ──────────────────────────────────────────────────────────────────


class TestGetBaselineSummary:
    def test_no_history_returns_none(self, history_root):
        # Empty student_id (UNKNOWN) → load_student_history returns None
        assert sh.get_baseline_summary("UNKNOWN") is None

    def test_no_baseline_returns_none(self, history_root):
        # History exists but <3 assignments → calculate_student_baseline
        # returns None → summary returns None
        sh.save_student_history(
            "sid-1",
            {
                "assignments": [
                    {"score": 80, "breakdown": {}},
                    {"score": 85, "breakdown": {}},
                ],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "last_updated": None, "student_id": "sid-1",
            },
        )
        result = sh.get_baseline_summary("sid-1")
        assert result is None

    def test_returns_summary_shape(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "assignments": [
                    {"score": 70, "breakdown": {"content_accuracy": 28},
                     "skills_strengths": ["reading"]},
                    {"score": 72, "breakdown": {"content_accuracy": 30},
                     "skills_strengths": ["reading"]},
                    {"score": 75, "breakdown": {"content_accuracy": 32},
                     "skills_strengths": ["reading"]},
                    {"score": 73, "breakdown": {"content_accuracy": 30},
                     "skills_strengths": ["reading"]},
                ],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "last_updated": None, "student_id": "sid-1",
            },
        )
        result = sh.get_baseline_summary("sid-1")
        assert "overall_avg" in result
        assert "overall_std" in result
        assert "assignment_count" in result
        assert isinstance(result["typical_skills"], list)
        assert isinstance(result["category_averages"], dict)


# ──────────────────────────────────────────────────────────────────
# build_history_context - prompt-formatting branches
# ──────────────────────────────────────────────────────────────────


class TestBuildHistoryContextBranches:
    def test_includes_previous_needs_improvement(self, history_root):
        # The most recent assignment carries needs_improvement items
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [
                    {"assignment": "Q1", "score": 80, "letter_grade": "B",
                     "date": "2026-01-01",
                     "needs_improvement": [
                         "Add more textual evidence to support claims",
                         "Improve transitions between paragraphs",
                     ]},
                ],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "AREAS STUDENT WAS TOLD TO IMPROVE LAST TIME" in ctx
        assert "textual evidence" in ctx

    def test_includes_declining_trend(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 80}],
                "skill_scores": {"_overall_trend": "declining"},
                "streaks": {}, "patterns": [], "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "TREND" in ctx
        assert "declining" in ctx

    def test_includes_improving_trend(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 80}],
                "skill_scores": {"_overall_trend": "improving"},
                "streaks": {}, "patterns": [], "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "IMPROVING" in ctx

    def test_includes_a_streak(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 95}],
                "skill_scores": {},
                "streaks": {"_grade_streak": {"type": "A_streak"}},
                "patterns": [], "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "STREAK" in ctx
        assert "A grades" in ctx or "A_streak" in ctx or "consecutive" in ctx

    def test_includes_grade_improving_streak(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 80}],
                "skill_scores": {},
                "streaks": {"_grade_streak": {"type": "improving"}},
                "patterns": [], "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "STREAK" in ctx
        assert "improved" in ctx.lower()

    def test_includes_per_skill_streak_improving_and_declining(
        self, history_root,
    ):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 80}],
                "skill_scores": {},
                "streaks": {
                    "content_accuracy": {"type": "improving"},
                    "completeness": {"type": "declining"},
                },
                "patterns": [], "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "Content Accuracy" in ctx
        # improving line
        assert "improving for" in ctx
        # declining line
        assert "CONCERN" in ctx

    def test_includes_strength_and_weakness_patterns(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 80}],
                "skill_scores": {}, "streaks": {},
                "patterns": [
                    {"type": "strength",
                     "description": "Excellent textual analysis"},
                    {"type": "weakness",
                     "description": "Needs work on transitions"},
                ],
                "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "STRENGTHS" in ctx
        assert "Excellent textual analysis" in ctx
        assert "AREAS FOR GROWTH" in ctx
        assert "transitions" in ctx

    def test_includes_skill_patterns_consistent_improving_focus(
        self, history_root,
    ):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [{"score": 80}],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "skill_patterns": {
                    "consistent_strengths": [
                        {"skill": "reading"}, {"skill": "writing"},
                    ],
                    "improving": [{"skill": "math"}],
                    "needs_focus": [{"skill": "vocabulary"}],
                },
                "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "CONSISTENT SKILLS" in ctx
        assert "reading" in ctx
        assert "IMPROVING SKILLS" in ctx
        assert "math" in ctx
        assert "SKILLS TO ENCOURAGE" in ctx
        assert "vocabulary" in ctx

    def test_includes_excellent_answer_continuity(self, history_root):
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [
                    {"score": 80,
                     "excellent_answers": [
                         "A nuanced thesis with strong evidence",
                     ]},
                ],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "excellent work" in ctx.lower()

    def test_empty_history_returns_empty(self, history_root):
        # No assignments at all → returns ""
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert ctx == ""

    def test_appends_mandatory_referencing_block(self, history_root):
        # Verify the trailing "YOU MUST reference this history" block
        sh.save_student_history(
            "sid-1",
            {
                "student_id": "sid-1",
                "assignments": [
                    {"assignment": "Q1", "score": 80, "letter_grade": "B"},
                ],
                "skill_scores": {}, "streaks": {}, "patterns": [],
                "last_updated": None,
            },
        )
        ctx = sh.build_history_context("sid-1")
        assert "YOU MUST reference this history" in ctx
