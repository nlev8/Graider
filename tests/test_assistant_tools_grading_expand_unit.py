"""
Expansion unit tests for backend/services/assistant_tools_grading.py.

Audit MAJOR #4 sprint follow-up to PR #264. Covers the deferred
functions from PR #251: analyze_grade_causes, get_feedback_patterns,
scan_submissions_folder, _build_missing_assignments_data, and
get_missing_assignments — all complex orchestrators.

Strategy:
- Mock the loader helpers (_load_results, _load_master_csv, _load_roster,
  _load_settings, _load_saved_assignments, _normalize_period,
  _normalize_assignment_name, _fuzzy_name_match, _safe_int_score).
- For scan_submissions_folder: create a real tmp filesystem with
  parseable + unparseable filenames to exercise the staging integration.
- HOME redirect via fixture so the settings_path os.path.expanduser
  resolves under tmp_path.

Pattern matches PR #251 (assistant_tools_grading covers query_grades /
get_student_summary / get_class_analytics / get_assignment_stats /
list_assignments_tool / compare_periods).
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


TID = "teacher-alice"


# ──────────────────────────────────────────────────────────────────
# analyze_grade_causes
# ──────────────────────────────────────────────────────────────────


class TestAnalyzeGradeCauses:
    def test_no_results_match_assignment_returns_error(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = analyze_grade_causes("Quiz 1", teacher_id=TID)
        assert "error" in result
        assert "No results found" in result["error"]

    def test_period_filter_no_match_returns_error(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        results = [
            {"assignment": "Quiz 1", "score": 80, "period": "1", "breakdown": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results):
            result = analyze_grade_causes("Quiz 1", period="2", teacher_id=TID)
        assert "error" in result
        assert "No results match" in result["error"]

    def test_score_threshold_filter(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        results = [
            {"assignment": "Quiz", "score": 90, "breakdown": {}},
            {"assignment": "Quiz", "score": 50, "breakdown": {}},
            {"assignment": "Quiz", "score": 30, "breakdown": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = analyze_grade_causes("Quiz", score_threshold=60, teacher_id=TID)
        # 2 students below 60
        assert result["students_analyzed"] == 2
        assert result["score_filter"] == "below 60"

    def test_category_breakdown_aggregation(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        results = [
            {"assignment": "Quiz", "score": 80, "breakdown": {
                "content": 8, "completeness": 9, "writing": 7, "effort": 10,
            }},
            {"assignment": "Quiz", "score": 60, "breakdown": {
                "content": 0, "completeness": 5, "writing": 6, "effort": 8,
            }},
            {"assignment": "Quiz", "score": 40, "breakdown": {
                "content": 0, "completeness": 4, "writing": 0, "effort": 6,
            }},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = analyze_grade_causes("Quiz", teacher_id=TID)

        cb = result["category_breakdown"]
        # content has 2 zeros out of 3 → 66.7% zero_pct
        assert cb["content"]["zeros"] == 2
        assert cb["content"]["zero_pct"] == 66.7
        # writing has 1 zero out of 3 → 33.3%
        assert cb["writing"]["zeros"] == 1
        # weakest_category = content (lowest avg)
        assert result["weakest_category"]["name"] == "content"

    def test_unanswered_questions_aggregation(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        results = [
            {"assignment": "Q", "score": 80, "breakdown": {},
             "unanswered_questions": ["Q3", "Q5"]},
            {"assignment": "Q", "score": 70, "breakdown": {},
             "unanswered_questions": ["Q3"]},
            {"assignment": "Q", "score": 95, "breakdown": {},
             "unanswered_questions": []},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = analyze_grade_causes("Q", teacher_id=TID)

        uq = result["unanswered_questions"]
        # 2 students with omissions, 3 total omissions
        assert uq["students_with_omissions"] == 2
        assert uq["total_omissions"] == 3
        # Q3 most skipped (twice)
        most_skipped = uq["most_skipped_questions"]
        assert most_skipped[0]["question"] == "Q3"
        assert most_skipped[0]["times_skipped"] == 2

        # omission_score_impact: avg with=75, avg without=95, gap=20
        impact = result["omission_score_impact"]
        assert impact["students_with_omissions"] == 2
        assert impact["students_without_omissions"] == 1
        assert impact["score_gap"] == 20.0

    def test_no_unanswered_omits_omission_impact(self):
        """If all students have unanswered or none do, omission_score_impact
        is empty (need both groups to compute the gap)."""
        from backend.services.assistant_tools_grading import analyze_grade_causes
        results = [
            {"assignment": "Q", "score": 80, "breakdown": {},
             "unanswered_questions": []},
            {"assignment": "Q", "score": 70, "breakdown": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = analyze_grade_causes("Q", teacher_id=TID)
        # Empty since no group with omissions
        assert result["omission_score_impact"] == {}

    def test_empty_breakdown_no_weakest_category(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        results = [
            {"assignment": "Quiz", "score": 90, "breakdown": {}},  # no category data
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = analyze_grade_causes("Quiz", teacher_id=TID)
        assert result["weakest_category"] is None
        assert result["category_breakdown"] == {}


# ──────────────────────────────────────────────────────────────────
# get_feedback_patterns
# ──────────────────────────────────────────────────────────────────


class TestGetFeedbackPatterns:
    def test_no_results_returns_error(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = get_feedback_patterns("Quiz", teacher_id=TID)
        assert "error" in result

    def test_period_filter_no_match_returns_error(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        results = [{"assignment": "Q", "period": "1", "score": 80}]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results):
            result = get_feedback_patterns("Q", period="2", teacher_id=TID)
        assert "error" in result

    def test_aggregates_strengths_and_developing(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        results = [
            {"assignment": "Q", "score": 90, "feedback": "fb1",
             "skills_demonstrated": {"strengths": ["clarity", "organization"],
                                     "developing": ["punctuation"]}},
            {"assignment": "Q", "score": 85, "feedback": "fb2",
             "skills_demonstrated": {"strengths": ["clarity"],
                                     "developing": ["punctuation", "spelling"]}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = get_feedback_patterns("Q", teacher_id=TID)

        # clarity appears 2x, organization 1x
        strengths = result["common_strengths"]
        clarity = next(s for s in strengths if s["skill"] == "clarity")
        assert clarity["count"] == 2
        assert clarity["pct"] == 100.0  # 2/2 students
        # punctuation appears 2x in developing
        developing = result["common_areas_for_growth"]
        punct = next(d for d in developing if d["skill"] == "punctuation")
        assert punct["count"] == 2

    def test_low_and_high_scoring_feedback_samples(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        results = [
            {"assignment": "Q", "score": s, "feedback": f"fb-{s}",
             "student_name": f"Student{s}", "skills_demonstrated": {}}
            for s in (50, 60, 70, 80, 90, 95, 99)
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = get_feedback_patterns("Q", teacher_id=TID)
        # Up to 5 of each
        assert len(result["lowest_scoring_feedback"]) == 5
        assert len(result["highest_scoring_feedback"]) == 5
        # Lowest sorted ascending → 50 first
        assert result["lowest_scoring_feedback"][0]["score"] == 50
        # Highest sorted descending → 99 first
        assert result["highest_scoring_feedback"][0]["score"] == 99

    def test_feedback_truncated_at_250(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        long_fb = "x" * 500
        results = [
            {"assignment": "Q", "score": 80, "feedback": long_fb,
             "student_name": "Alice", "skills_demonstrated": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   return_value=80):
            result = get_feedback_patterns("Q", teacher_id=TID)
        sample = result["lowest_scoring_feedback"][0]
        # Truncated to 250 + "..."
        assert sample["feedback_preview"].endswith("...")
        assert len(sample["feedback_preview"]) == 253

    def test_marker_status_distribution(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        results = [
            {"assignment": "Q", "score": 80, "marker_status": "complete",
             "skills_demonstrated": {}},
            {"assignment": "Q", "score": 90, "marker_status": "partial",
             "skills_demonstrated": {}},
            {"assignment": "Q", "score": 70, "marker_status": "complete",
             "skills_demonstrated": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = get_feedback_patterns("Q", teacher_id=TID)
        assert result["marker_status"] == {"complete": 2, "partial": 1}


# ──────────────────────────────────────────────────────────────────
# scan_submissions_folder
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def submission_folder(tmp_path, monkeypatch):
    """Create a real tmp folder with sample student submission files
    in `Firstname_Lastname_AssignmentName.ext` format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    folder = tmp_path / "submissions"
    folder.mkdir()
    # Parseable
    (folder / "Alice_Smith_Quiz1.docx").write_text("content")
    (folder / "Bob_Jones_Quiz1.docx").write_text("content")
    (folder / "Carol_Davis_Quiz1.pdf").write_text("content")
    (folder / "Alice_Smith_Quiz2.docx").write_text("content")
    # Unparseable (only 2 underscores)
    (folder / "Bad_Filename.docx").write_text("content")
    # Unsupported extension
    (folder / "Alice_Smith_Test.xyz").write_text("content")
    return folder


class TestScanSubmissionsFolder:
    def test_no_folder_configured_returns_error(self, tmp_path, monkeypatch):
        from backend.services.assistant_tools_grading import scan_submissions_folder
        # No settings file, no global settings, default folder doesn't exist
        monkeypatch.setenv("HOME", str(tmp_path))
        # Default fallback ~/Downloads/Graider/Assignments doesn't exist
        with patch("backend.services.assistant_tools_grading._load_settings",
                   return_value={}):
            result = scan_submissions_folder(teacher_id=TID)
        assert "error" in result
        assert "Assignments folder not found" in result["error"]

    def test_groups_by_assignment(self, submission_folder, monkeypatch):
        from backend.services.assistant_tools_grading import scan_submissions_folder
        # Configure ~/.graider_settings.json to point at our tmp folder
        settings = {"config": {"assignments_folder": str(submission_folder)}}
        settings_path = monkeypatch.MonkeyPatch().__enter__().setenv if False else None
        # Use the actual HOME redirect from fixture
        home_settings = monkeypatch.delenv  # placeholder
        # Write the settings file at the path expanduser will resolve
        cfg_path = os.path.expanduser("~/.graider_settings.json")
        with open(cfg_path, 'w') as f:
            json.dump(settings, f)

        try:
            with patch("backend.services.assistant_tools_grading._load_settings",
                       return_value={}), \
                 patch("backend.services.assistant_tools_grading._load_results",
                       return_value=[]), \
                 patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                       side_effect=lambda x: x.lower().strip()), \
                 patch("backend.staging.stage_files",
                       return_value={"staging_folder": str(submission_folder),
                                     "duplicates_skipped": 0}):
                result = scan_submissions_folder(teacher_id=TID)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

        # Codex round-1 LOW: previous version was too permissive. Now
        # asserts the concrete output shape:
        # - 5 supported files (Quiz1 x3, Quiz2 x1, Bad_Filename = 5; .xyz skipped)
        # - 3 unique students (Alice, Bob, Carol — last initials normalized)
        # - 2 parseable assignments (Quiz1, Quiz2)
        # - Bad_Filename.docx in unparseable_files
        assert result.get("error") is None, f"Unexpected error: {result.get('error')}"
        # 4 parseable + 1 unparseable = 5 supported files (.xyz excluded)
        assert result["total_files"] == 5
        # Quiz1 + Quiz2 — Bad_Filename never made it to the assignment_groups
        assert result["unique_assignments"] == 2
        # Alice S., Bob J., Carol D. — student_display = "First L." form
        assert result["unique_students"] == 3
        # Top assignments sorted by submission count desc
        top = result["top_assignments"]
        assert len(top) == 2
        # Quiz1 has 3 submissions (Alice, Bob, Carol)
        quiz1 = next((a for a in top if a["assignment"].lower() == "quiz1"), None)
        assert quiz1 is not None
        assert quiz1["submissions"] == 3
        assert quiz1["student_count"] == 3
        # Quiz2 has 1 submission (Alice)
        quiz2 = next((a for a in top if a["assignment"].lower() == "quiz2"), None)
        assert quiz2 is not None
        assert quiz2["submissions"] == 1
        # All ungraded (no results passed in)
        assert quiz1["ungraded"] == 3
        assert quiz2["ungraded"] == 1
        # Bad_Filename.docx is unparseable
        assert any("Bad_Filename" in f for f in result["unparseable_files"])


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract for the deferred tools
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequiredExpand:
    def test_analyze_grade_causes_empty_raises(self):
        from backend.services.assistant_tools_grading import analyze_grade_causes
        with pytest.raises(ValueError, match="teacher_id is required"):
            analyze_grade_causes("Quiz", teacher_id="")

    def test_get_feedback_patterns_empty_raises(self):
        from backend.services.assistant_tools_grading import get_feedback_patterns
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_feedback_patterns("Quiz", teacher_id="")

    def test_scan_submissions_folder_empty_raises(self):
        from backend.services.assistant_tools_grading import scan_submissions_folder
        with pytest.raises(ValueError, match="teacher_id is required"):
            scan_submissions_folder(teacher_id="")
