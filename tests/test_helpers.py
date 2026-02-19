"""
Test: Helper functions — fuzzy matching, normalization, data loading.
"""
import pytest
from backend.services.assistant_tools import (
    _fuzzy_name_match, _extract_first_name, _safe_int_score,
    _normalize_assignment_name, _normalize_period,
)


class TestFuzzyNameMatch:
    def test_exact_match(self):
        assert _fuzzy_name_match("Alice Johnson", "Alice Johnson")

    def test_partial_first_name(self):
        assert _fuzzy_name_match("Alice", "Alice Johnson")

    def test_last_first_format(self):
        assert _fuzzy_name_match("Dicen Wilkins", "Wilkins Reels, Dicen Macheil")

    def test_middle_name_skipped(self):
        assert _fuzzy_name_match("Luke Lundell", "Luke J Lundell")

    def test_no_match(self):
        assert not _fuzzy_name_match("John Smith", "Jane Smith")

    def test_empty_search(self):
        assert not _fuzzy_name_match("", "Alice Johnson")

    def test_case_insensitive(self):
        assert _fuzzy_name_match("alice", "ALICE JOHNSON")


class TestExtractFirstName:
    def test_first_last(self):
        assert _extract_first_name("Alice Johnson") == "Alice"

    def test_last_comma_first(self):
        assert _extract_first_name("Johnson, Alice Marie") == "Alice"

    def test_empty(self):
        assert _extract_first_name("") == "Student"

    def test_none(self):
        assert _extract_first_name(None) == "Student"


class TestSafeIntScore:
    def test_int(self):
        assert _safe_int_score(85) == 85

    def test_float(self):
        assert _safe_int_score(85.7) == 85

    def test_string(self):
        assert _safe_int_score("92") == 92

    def test_none(self):
        assert _safe_int_score(None) == 0

    def test_empty_string(self):
        assert _safe_int_score("") == 0

    def test_invalid(self):
        assert _safe_int_score("abc") == 0


class TestNormalizeAssignmentName:
    def test_strips_docx(self):
        assert _normalize_assignment_name("Chapter 1 Notes.docx") == "Chapter 1 Notes"

    def test_strips_number_suffix(self):
        assert _normalize_assignment_name("Quiz 1 (2)") == "Quiz 1"

    def test_strips_pdf(self):
        assert _normalize_assignment_name("Essay.pdf") == "Essay"

    def test_plain_name(self):
        assert _normalize_assignment_name("Bill of Rights Quiz") == "Bill of Rights Quiz"


class TestNormalizePeriod:
    def test_number_only(self):
        assert _normalize_period("6") == "Period 6"

    def test_period_prefix(self):
        assert _normalize_period("Period 6") == "Period 6"

    def test_lowercase(self):
        assert _normalize_period("period 2") == "Period 2"

    def test_underscore(self):
        assert _normalize_period("Period_3") == "Period 3"

    def test_all_passthrough(self):
        assert _normalize_period("all") == "all"

    def test_none_passthrough(self):
        assert _normalize_period(None) is None


class TestDataLoading:
    """Test that fixture data loads correctly through monkeypatched paths."""

    def test_load_master_csv(self, patch_paths, sample_grades):
        assert len(sample_grades) > 0
        assert sample_grades[0].get("student_name")

    def test_load_results(self, patch_paths, sample_results):
        assert len(sample_results) > 0
        assert sample_results[0].get("student_name")

    def test_load_standards(self, patch_paths, sample_standards):
        assert len(sample_standards) > 0
        assert sample_standards[0].get("code")
        assert sample_standards[0].get("vocabulary")

    def test_grades_have_expected_students(self, sample_grades):
        names = set(r.get("student_name") for r in sample_grades)
        assert "Alice Johnson" in names
        assert "Emma Davis" in names

    def test_grades_have_expected_fields(self, sample_grades):
        row = sample_grades[0]
        for field in ("student_name", "score", "assignment", "period", "content", "completeness"):
            assert field in row, f"Missing field: {field}"
