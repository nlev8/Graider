"""Tests for backend/services/assistant_tools_assessments.py — portal assessment tools."""

import pytest
from unittest.mock import patch, MagicMock


def _mock_supabase_with_assessments(assessments_data):
    """Create a mock Supabase client that returns the given assessments."""
    mock_sb = MagicMock()
    mock_result = MagicMock()
    mock_result.data = assessments_data
    # Fluent chain: every method returns mock_sb's table mock
    mock_table = MagicMock()
    for method in ('select', 'eq', 'neq', 'ilike', 'like', 'order', 'limit', 'offset'):
        getattr(mock_table, method).return_value = mock_table
    mock_table.execute.return_value = mock_result
    mock_sb.table.return_value = mock_table
    return mock_sb


def _mock_supabase_with_submissions(assessments_data, submissions_data):
    """Create a mock Supabase that returns assessments then submissions.
    Uses a fluent-chain mock: every chained method returns the same mock_table."""
    mock_sb = MagicMock()

    def table_router(name):
        mock_table = MagicMock()
        result = MagicMock()
        if name == 'published_assessments':
            result.data = assessments_data
        elif name == 'submissions':
            result.data = submissions_data
        else:
            result.data = []
        for method in ('select', 'eq', 'neq', 'ilike', 'like', 'order',
                       'limit', 'offset', 'gt', 'gte', 'lt', 'lte', 'in_',
                       'range'):
            getattr(mock_table, method).return_value = mock_table
        mock_table.execute.return_value = result
        return mock_table

    mock_sb.table = table_router
    return mock_sb


class TestListPublishedAssessments:
    def test_returns_assessments_list(self):
        from backend.services.assistant_tools_assessments import list_published_assessments_tool
        mock_data = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Unit 3 Quiz",
             "created_at": "2026-03-20T10:00:00", "submission_count": 25,
             "is_active": True, "settings": {"content_type": "assessment", "period": "Period 2"}},
            {"id": "uuid-2", "join_code": "DEF456", "title": "Chapter 5 Test",
             "created_at": "2026-03-15T10:00:00", "submission_count": 0,
             "is_active": False, "settings": {"content_type": "assessment"}},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments(mock_data)
            result = list_published_assessments_tool(teacher_id="teacher-1")
        assert "assessments" in result
        assert len(result["assessments"]) == 2
        assert result["assessments"][0]["title"] == "Unit 3 Quiz"
        assert result["assessments"][0]["submission_count"] == 25
        assert result["assessments"][1]["submission_count"] == 0

    def test_returns_empty_when_no_assessments(self):
        from backend.services.assistant_tools_assessments import list_published_assessments_tool
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments([])
            result = list_published_assessments_tool(teacher_id="teacher-1")
        assert result["assessments"] == []
        assert result["total"] == 0

    def test_returns_error_when_supabase_unavailable(self):
        from backend.services.assistant_tools_assessments import list_published_assessments_tool
        with patch('backend.services.assistant_tools_assessments._get_supabase', return_value=None):
            result = list_published_assessments_tool(teacher_id="teacher-1")
        assert "error" in result

    def test_filters_by_content_type(self):
        from backend.services.assistant_tools_assessments import list_published_assessments_tool
        mock_data = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Quiz 1",
             "created_at": "2026-03-20T10:00:00", "submission_count": 10,
             "is_active": True, "settings": {"content_type": "assessment"}},
            {"id": "uuid-2", "join_code": "DEF456", "title": "Homework 1",
             "created_at": "2026-03-15T10:00:00", "submission_count": 5,
             "is_active": True, "settings": {"content_type": "assignment"}},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments(mock_data)
            result = list_published_assessments_tool(content_type="assignment", teacher_id="teacher-1")
        assert len(result["assessments"]) == 1
        assert result["assessments"][0]["title"] == "Homework 1"


class TestQueryAssessmentResults:
    def test_returns_summary_for_assessment(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "uuid-1", "join_code": "ABC123", "title": "Unit 3 Quiz", "settings": {"content_type": "assessment"}}]
        submissions = [
            {"id": "s1", "student_name": "Alice Smith", "score": 85, "total_points": 100, "percentage": 85.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s2", "student_name": "Bob Jones", "score": 72, "total_points": 100, "percentage": 72.0, "submitted_at": "2026-03-20T10:05:00", "results": None},
            {"id": "s3", "student_name": "Carol Davis", "score": 95, "total_points": 100, "percentage": 95.0, "submitted_at": "2026-03-20T10:10:00", "results": None},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(assessment_name="Unit 3", teacher_id="teacher-1")
        assert result["assessment"]["title"] == "Unit 3 Quiz"
        assert result["summary"]["total_submissions"] == 3
        assert result["summary"]["average_score"] == 84.0
        assert result["summary"]["highest_score"] == 95.0
        assert result["summary"]["lowest_score"] == 72.0

    def test_returns_error_when_not_found(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions([], [])
            result = query_assessment_results(assessment_name="Nonexistent", teacher_id="teacher-1")
        assert "error" in result

    def test_returns_by_join_code(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "uuid-1", "join_code": "XYZ789", "title": "Pop Quiz", "settings": {}}]
        submissions = [{"id": "s1", "student_name": "Alice", "score": 90, "total_points": 100, "percentage": 90.0, "submitted_at": "2026-03-20T10:00:00", "results": None}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(join_code="XYZ789", teacher_id="teacher-1")
        assert result["assessment"]["join_code"] == "XYZ789"
        assert result["summary"]["total_submissions"] == 1

    def test_filters_by_min_score(self):
        # PR #229: filtering now happens on Supabase via .gte('percentage', N).
        # Test fixture provides only the matching rows (what Postgres would
        # return). The unit-tests for the Supabase chain construction itself
        # are below in TestQueryFilterPushdown.
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "uuid-1", "join_code": "ABC123", "title": "Test", "settings": {}}]
        submissions = [
            {"id": "s1", "student_name": "Alice", "score": 90, "total_points": 100, "percentage": 90.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(assessment_name="Test", min_score=70, teacher_id="teacher-1")
        assert len(result["submissions"]) == 1
        assert result["submissions"][0]["student_name"] == "Alice"

    def test_handles_no_submissions(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "uuid-1", "join_code": "ABC123", "title": "Empty Test", "settings": {}}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, [])
            result = query_assessment_results(assessment_name="Empty", teacher_id="teacher-1")
        assert result["summary"]["total_submissions"] == 0
        assert result["summary"]["average_score"] is None

    def test_grade_distribution(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "uuid-1", "join_code": "ABC123", "title": "Test", "settings": {}}]
        submissions = [
            {"id": "s1", "student_name": "A-student", "score": 95, "total_points": 100, "percentage": 95.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s2", "student_name": "B-student", "score": 85, "total_points": 100, "percentage": 85.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s3", "student_name": "C-student", "score": 75, "total_points": 100, "percentage": 75.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s4", "student_name": "F-student", "score": 50, "total_points": 100, "percentage": 50.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(assessment_name="Test", teacher_id="teacher-1")
        dist = result["summary"]["grade_distribution"]
        assert dist["A"] == 1
        assert dist["B"] == 1
        assert dist["C"] == 1
        assert dist["F"] == 1


class TestQueryFilterPushdown:
    """Closes audit MAJOR #12 (Codex 2026-05-06): filters that used to run in
    Python after an unbounded fetch are now pushed to Supabase.

    These tests pin the contract by recording every method call on the
    submissions chain and asserting the expected `.gte`/`.lte`/`.ilike`/
    `.range` calls were made before `.execute()`.
    """

    def _spy_supabase(self, assessments_data, submissions_page, stats_count=None):
        """Create a Supabase mock that records calls per submissions chain.

        Returns (mock_sb, recorded_calls) where `recorded_calls` is a
        dict { 'select_args': [...], 'eq_args': [...], 'gte_args': [...],
        'lte_args': [...], 'ilike_args': [...], 'range_args': [...],
        'order_args': [...] } accumulated across all submissions chains.
        """
        recorded = {
            'select_args': [], 'eq_args': [], 'gte_args': [],
            'lte_args': [], 'ilike_args': [], 'range_args': [],
            'order_args': [], 'execute_count': 0,
            'submissions_execute_n': 0,
        }
        # Stats response should reflect all matching (count); page returns the page slice.
        stats_result = MagicMock()
        stats_result.data = (
            [{'percentage': r.get('percentage')} for r in (submissions_page or [])]
            if stats_count is None else
            [{'percentage': r.get('percentage')} for r in (submissions_page or [])]
            + [{'percentage': 50.0}] * max(0, stats_count - len(submissions_page or []))
        )
        page_result = MagicMock()
        page_result.data = submissions_page

        def table_factory(name):
            chain = MagicMock()
            if name == 'published_assessments':
                # Simple chain: returns assessments
                pa_result = MagicMock()
                pa_result.data = assessments_data
                for m in ('select', 'eq', 'ilike'):
                    getattr(chain, m).return_value = chain
                chain.execute.return_value = pa_result
                return chain
            elif name == 'submissions':
                # Record everything across ALL submissions chains. Use
                # the closure-scoped `submissions_execute_n` counter so
                # the 1st submissions.execute() returns stats and the
                # 2nd returns the paginated page — even though each
                # chain is a fresh MagicMock instance.
                def mk(method_name):
                    def _called(*args, **kwargs):
                        recorded[f'{method_name}_args'].append(args)
                        return chain
                    return _called

                for m in ('select', 'eq', 'gte', 'lte', 'ilike',
                          'range', 'order'):
                    getattr(chain, m).side_effect = mk(m)

                def execute(*_args, **_kwargs):
                    recorded['execute_count'] += 1
                    recorded['submissions_execute_n'] += 1
                    # 1st execute = stats, 2nd execute = paginated list
                    return stats_result if recorded['submissions_execute_n'] == 1 else page_result

                chain.execute.side_effect = execute
                return chain
            else:
                # Default empty chain
                empty = MagicMock()
                empty.data = []
                for m in ('select', 'eq', 'ilike', 'order'):
                    getattr(chain, m).return_value = chain
                chain.execute.return_value = empty
                return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_factory
        return mock_sb, recorded

    def test_min_score_pushed_to_supabase_gte(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = [{"id": "s1", "student_name": "Alice", "score": 90, "total_points": 100,
                 "percentage": 90.0, "submitted_at": "2026-03-20T10:00:00", "results": None}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(assessment_name="T", min_score=70, teacher_id="t-1")
        assert ('percentage', 70) in recorded['gte_args'], (
            f"Expected gte('percentage', 70) call; got {recorded['gte_args']}"
        )

    def test_max_score_pushed_to_supabase_lte(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = [{"id": "s1", "student_name": "Bob", "score": 60, "total_points": 100,
                 "percentage": 60.0, "submitted_at": "2026-03-20T10:00:00", "results": None}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(assessment_name="T", max_score=70, teacher_id="t-1")
        assert ('percentage', 70) in recorded['lte_args']

    def test_student_name_pushed_to_supabase_ilike(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = [{"id": "s1", "student_name": "Alice", "score": 90, "total_points": 100,
                 "percentage": 90.0, "submitted_at": "2026-03-20T10:00:00", "results": None}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(assessment_name="T", student_name="Alice", teacher_id="t-1")
        # ilike calls happen on both published_assessments AND submissions chains.
        # We're looking for the submissions one with student_name pattern.
        assert any(
            args == ('student_name', '%Alice%') for args in recorded['ilike_args']
        ), f"Expected ilike('student_name', '%Alice%'); got {recorded['ilike_args']}"

    def test_default_pagination_uses_range_0_99(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = []
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(assessment_name="T", teacher_id="t-1")
        # Default page size 100 → range(0, 99)
        assert (0, 99) in recorded['range_args'], (
            f"Expected default range(0, 99); got {recorded['range_args']}"
        )

    def test_explicit_pagination_uses_provided_offset_and_limit(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = []
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(
                assessment_name="T", limit=50, offset=100, teacher_id="t-1",
            )
        # offset=100, limit=50 → range(100, 149)
        assert (100, 149) in recorded['range_args']

    def test_limit_clamped_to_max_500(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = []
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(
                assessment_name="T", limit=99999, teacher_id="t-1",
            )
        # Caller-supplied limit=99999 should be clamped to 500 → range(0, 499)
        assert (0, 499) in recorded['range_args']

    def test_negative_offset_clamped_to_zero(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = []
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            query_assessment_results(
                assessment_name="T", offset=-5, teacher_id="t-1",
            )
        assert (0, 99) in recorded['range_args']

    def test_response_includes_pagination_block(self):
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        page = [{"id": "s1", "student_name": "A", "score": 90, "total_points": 100,
                 "percentage": 90.0, "submitted_at": "x", "results": None}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page)
            mock_get.return_value = mock_sb
            result = query_assessment_results(
                assessment_name="T", limit=50, offset=10, teacher_id="t-1",
            )
        assert "pagination" in result
        assert result["pagination"]["limit"] == 50
        assert result["pagination"]["offset"] == 10
        assert result["pagination"]["returned"] == 1
        assert "has_more" in result["pagination"]

    def test_summary_uses_stats_query_not_paginated_page(self):
        # If stats are computed over the page only, paginating loses
        # accurate aggregates. Pin: total_submissions reflects the stats
        # query count, NOT len(submissions).
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "u1", "join_code": "ABC123", "title": "T", "settings": {}}]
        # Page returns 2 rows; stats simulated to indicate 5 total matching.
        page = [
            {"id": "s1", "student_name": "A", "score": 90, "total_points": 100, "percentage": 90.0, "submitted_at": "x", "results": None},
            {"id": "s2", "student_name": "B", "score": 80, "total_points": 100, "percentage": 80.0, "submitted_at": "x", "results": None},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_sb, recorded = self._spy_supabase(assessments, page, stats_count=5)
            mock_get.return_value = mock_sb
            result = query_assessment_results(
                assessment_name="T", limit=2, teacher_id="t-1",
            )
        # Stats query returns 5 percentages (page rows + 3 padding rows from
        # _spy_supabase fixture). total_submissions reflects ALL matching,
        # not just the page.
        assert result["summary"]["total_submissions"] == 5
        # But submissions list is bounded by page size.
        assert len(result["submissions"]) == 2


class TestAssessmentToolIntegration:
    """Integration tests: verify tools are registered and callable through execute_tool."""

    def test_execute_tool_dispatches_list_published_assessments(self):
        from backend.services.assistant_tools import execute_tool
        mock_data = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Quiz",
             "created_at": "2026-03-20T10:00:00", "submission_count": 5,
             "is_active": True, "settings": {}},
        ]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments(mock_data)
            result = execute_tool('list_published_assessments', {"teacher_id": "teacher-1"})
        assert "error" not in result
        assert "assessments" in result
        assert result["assessments"][0]["title"] == "Quiz"

    def test_execute_tool_dispatches_query_assessment_results(self):
        from backend.services.assistant_tools import execute_tool
        assessments = [{"id": "uuid-1", "join_code": "XYZ789", "title": "Final Exam", "settings": {}}]
        submissions = [{"id": "s1", "student_name": "Alice", "score": 88, "total_points": 100, "percentage": 88.0, "submitted_at": "2026-03-20T10:00:00", "results": None}]
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = execute_tool('query_assessment_results', {"assessment_name": "Final", "teacher_id": "teacher-1"})
        assert "error" not in result
        assert result["assessment"]["title"] == "Final Exam"
        assert result["summary"]["total_submissions"] == 1

    def test_execute_tool_returns_error_for_missing_name(self):
        from backend.services.assistant_tools import execute_tool
        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = MagicMock()
            result = execute_tool('query_assessment_results', {"teacher_id": "teacher-1"})
        assert "error" in result

    def test_tool_definitions_serialize_for_openai_function_calling(self):
        from backend.services.assistant_tools import TOOL_DEFINITIONS
        import json
        assessment_tools = [t for t in TOOL_DEFINITIONS if t["name"] in ("list_published_assessments", "query_assessment_results")]
        assert len(assessment_tools) == 2, "Both assessment tools must be registered"
        for tool_def in assessment_tools:
            assert isinstance(tool_def["name"], str) and len(tool_def["name"]) > 0
            assert isinstance(tool_def["description"], str) and len(tool_def["description"]) > 0
            assert isinstance(tool_def["input_schema"], dict)
            assert tool_def["input_schema"]["type"] == "object"
            assert "properties" in tool_def["input_schema"]
            openai_format = {"type": "function", "function": {"name": tool_def["name"], "description": tool_def["description"], "parameters": tool_def["input_schema"]}}
            assert json.dumps(openai_format)
