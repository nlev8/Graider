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
                       'limit', 'offset', 'gt', 'gte', 'lt', 'lte', 'in_'):
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
        from backend.services.assistant_tools_assessments import query_assessment_results
        assessments = [{"id": "uuid-1", "join_code": "ABC123", "title": "Test", "settings": {}}]
        submissions = [
            {"id": "s1", "student_name": "Alice", "score": 90, "total_points": 100, "percentage": 90.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s2", "student_name": "Bob", "score": 60, "total_points": 100, "percentage": 60.0, "submitted_at": "2026-03-20T10:00:00", "results": None},
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
