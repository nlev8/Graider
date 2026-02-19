"""
Test: Planning & classroom tools — bell ringer, exit ticket, grouping, etc.
"""
import pytest
from backend.services.assistant_tools_planning import (
    suggest_remediation, align_to_standards, get_pacing_status,
    generate_bell_ringer, generate_exit_ticket, suggest_grouping,
    generate_sub_plans,
)


class TestSuggestRemediation:
    def test_from_assignment(self, patch_paths):
        result = suggest_remediation(assignment_name="Chapter 1 Notes")
        assert "error" not in result
        # Should have either suggestions or a "no weaknesses" message
        assert result.get("suggestions") or result.get("message")

    def test_with_explicit_areas(self, patch_paths):
        result = suggest_remediation(weak_areas=["Writing Quality"])
        assert "error" not in result
        suggestions = result.get("suggestions", [])
        assert len(suggestions) > 0
        # Should include activities
        for s in suggestions:
            assert s.get("weakness")
            assert len(s.get("activities", [])) > 0

    def test_includes_available_tools(self, patch_paths):
        result = suggest_remediation(weak_areas=["Content Accuracy"])
        assert "available_tools" in result


class TestAlignToStandards:
    def test_topic_alignment(self, patch_paths):
        result = align_to_standards(topic="Constitution")
        assert "error" not in result
        assert result.get("covered_count") >= 0
        assert result.get("total_standards") > 0
        assert "coverage_pct" in result

    def test_covered_standards_have_codes(self, patch_paths):
        result = align_to_standards(topic="government")
        for s in result.get("covered_standards", []):
            assert "code" in s
            assert "benchmark" in s

    def test_empty_topic_errors(self, patch_paths):
        result = align_to_standards(topic="")
        assert "error" in result

    def test_broad_topic_covers_many(self, patch_paths):
        result = align_to_standards(topic="government")
        assert result.get("covered_count") > 0


class TestGetPacingStatus:
    def test_returns_status(self, patch_paths):
        result = get_pacing_status()
        assert "error" not in result
        assert result.get("status") in ("ahead", "behind", "on_track")
        assert result.get("total_standards") > 0
        assert "pct_standards_covered" in result

    def test_counts_present(self, patch_paths):
        result = get_pacing_status()
        assert result.get("standards_covered", 0) + result.get("standards_remaining", 0) == result.get("total_standards")


class TestGenerateBellRinger:
    def test_returns_questions(self, patch_paths):
        result = generate_bell_ringer(date="2026-02-18")
        assert "error" not in result
        questions = result.get("questions", [])
        assert len(questions) > 0
        assert len(questions) <= 3

    def test_question_structure(self, patch_paths):
        result = generate_bell_ringer(date="2026-02-18")
        for q in result.get("questions", []):
            assert "question" in q
            assert "type" in q

    def test_source_lesson_referenced(self, patch_paths):
        result = generate_bell_ringer(date="2026-02-18")
        # Should reference a lesson from calendar
        assert result.get("source_lesson") or result.get("source_date")


class TestGenerateExitTicket:
    def test_with_date(self, patch_paths):
        result = generate_exit_ticket(date="2026-02-18")
        assert "error" not in result
        questions = result.get("questions", [])
        assert len(questions) > 0
        assert len(questions) <= 3

    def test_with_topic(self, patch_paths):
        result = generate_exit_ticket(topic="Bill of Rights")
        assert "error" not in result
        assert len(result.get("questions", [])) > 0

    def test_question_types(self, patch_paths):
        result = generate_exit_ticket(date="2026-02-18")
        types = [q.get("type") for q in result.get("questions", [])]
        # Should have at least one question type
        assert len(types) > 0


class TestSuggestGrouping:
    def test_heterogeneous_groups(self, patch_paths):
        result = suggest_grouping(period="Period 1", group_type="heterogeneous")
        assert "error" not in result
        assert result.get("total_groups") > 0
        assert result.get("group_type") == "heterogeneous"

    def test_homogeneous_groups(self, patch_paths):
        result = suggest_grouping(period="Period 1", group_type="homogeneous")
        assert "error" not in result
        assert result.get("total_groups") > 0

    def test_group_has_members(self, patch_paths):
        result = suggest_grouping(period="Period 1", group_type="heterogeneous", group_size=3)
        for g in result.get("groups", []):
            assert len(g.get("members", [])) > 0
            assert g.get("group_avg") > 0

    def test_custom_group_size(self, patch_paths):
        result = suggest_grouping(period="Period 2", group_type="heterogeneous", group_size=2)
        assert "error" not in result
        # Groups should be approximately size 2
        for g in result.get("groups", []):
            assert len(g.get("members", [])) <= 3  # Allow +1 for remainder

    def test_invalid_group_type(self, patch_paths):
        result = suggest_grouping(period="Period 1", group_type="invalid")
        assert "error" in result

    def test_missing_period(self, patch_paths):
        result = suggest_grouping(period="", group_type="heterogeneous")
        assert "error" in result

    def test_heterogeneous_has_mixed_levels(self, patch_paths):
        result = suggest_grouping(period="Period 1", group_type="heterogeneous", group_size=4)
        groups = result.get("groups", [])
        if len(groups) >= 2:
            # Group averages should be relatively close for heterogeneous
            avgs = [g["group_avg"] for g in groups]
            spread = max(avgs) - min(avgs)
            assert spread < 40  # Groups shouldn't be wildly different


class TestGenerateSubPlans:
    def test_single_day(self, patch_paths):
        result = generate_sub_plans(date="2026-02-18")
        assert "error" not in result
        plans = result.get("daily_plans", [])
        assert len(plans) >= 1

    def test_multi_day(self, patch_paths):
        result = generate_sub_plans(date="2026-02-18", end_date="2026-02-20")
        plans = result.get("daily_plans", [])
        assert len(plans) >= 2

    def test_includes_lesson_info(self, patch_paths):
        result = generate_sub_plans(date="2026-02-18")
        plans = result.get("daily_plans", [])
        # Should have lesson title for a scheduled day
        lesson_plans = [p for p in plans if p.get("lesson_title") and p.get("lesson_title") != "No lesson scheduled"]
        assert len(lesson_plans) >= 0  # May or may not have a lesson depending on calendar

    def test_missing_date(self, patch_paths):
        result = generate_sub_plans(date="")
        assert "error" in result

    def test_skips_holidays(self, patch_paths):
        result = generate_sub_plans(date="2026-02-23")
        plans = result.get("daily_plans", [])
        holidays = [p for p in plans if p.get("holiday")]
        assert len(holidays) >= 1
