"""Gap-fill tests for backend/services/assistant_tools_assessments.py.

Audit MAJOR #4 sprint follow-up to PR #324. Companion to existing
`tests/test_assessment_tools.py`. Targets the 16 missing LOC
(86.8% baseline → 100% goal):

* `_get_supabase` ImportError → None (lines 20-24)
* `list_published_assessments_tool` outer-except (lines 59-61)
* `query_assessment_results` pagination defensive errors (lines
  127, 136-137, 141-142)
* `query_assessment_results` outer-except (lines 289-291)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


MODULE = "backend.services.assistant_tools_assessments"


# ──────────────────────────────────────────────────────────────────
# _get_supabase
# ──────────────────────────────────────────────────────────────────


class TestGetSupabase:
    def test_import_error_returns_none(self):
        # Genuine ImportError from the `from backend.supabase_client
        # import get_supabase` statement — `sys.modules` is poisoned so
        # the import resolves to None and Python raises ImportError.
        from backend.services.assistant_tools_assessments import (
            _get_supabase,
        )
        with patch.dict("sys.modules", {"backend.supabase_client": None}):
            result = _get_supabase()
        assert result is None

    def test_runtime_error_during_call_returns_none(self):
        # The same except Exception: block also catches post-import
        # call-time errors from get_supabase() — covers the other branch
        # through the same try block.
        from backend.services.assistant_tools_assessments import (
            _get_supabase,
        )
        with patch("backend.supabase_client.get_supabase",
                   side_effect=RuntimeError("boom")):
            result = _get_supabase()
        assert result is None

    def test_happy_path_returns_client(self):
        from backend.services.assistant_tools_assessments import (
            _get_supabase,
        )
        fake_client = MagicMock()
        with patch("backend.supabase_client.get_supabase",
                   return_value=fake_client):
            result = _get_supabase()
        assert result is fake_client


# ──────────────────────────────────────────────────────────────────
# list_published_assessments_tool exception path
# ──────────────────────────────────────────────────────────────────


class TestListPublishedAssessmentsExceptions:
    def test_supabase_query_exception_returns_error(self):
        from backend.services.assistant_tools_assessments import (
            list_published_assessments_tool,
        )
        # Force the chained query to raise
        mock_sb = MagicMock()
        (mock_sb.table.return_value.select.return_value.eq.return_value
            .order.return_value.execute.side_effect) = RuntimeError("query failed")

        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = list_published_assessments_tool(teacher_id="t")
        assert "error" in result
        assert "Failed to load assessments" in result["error"]


# ──────────────────────────────────────────────────────────────────
# query_assessment_results pagination + outer exception
# ──────────────────────────────────────────────────────────────────


class TestQueryAssessmentResultsBranches:
    def test_no_assessment_name_no_join_code_returns_error(self):
        from backend.services.assistant_tools_assessments import (
            query_assessment_results,
        )
        with patch(f"{MODULE}._get_supabase", return_value=MagicMock()):
            result = query_assessment_results(teacher_id="t")
        assert "error" in result
        assert "assessment_name or join_code" in result["error"]

    def test_invalid_limit_falls_back_to_default(self):
        # `limit="not-a-number"` → defensive fallback to _DEFAULT_PAGE_SIZE
        from backend.services.assistant_tools_assessments import (
            query_assessment_results,
        )
        # Build minimal mock chain so the function actually runs
        mock_sb = MagicMock()
        # First execute returns an assessment record
        first_result = MagicMock(data=[{
            "id": "a1", "join_code": "ABC123",
            "title": "Q1", "settings": {},
        }])
        # All subsequent execute() calls return empty data → no submissions
        empty_result = MagicMock(data=[])

        # Production calls eq.eq.execute exactly once (the initial
        # published_assessments lookup); subsequent pagination uses the
        # eq.range and eq.order.range chains mocked below. The 100-element
        # side_effect array was vacuous (never consumed past element 0).
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = first_result
        mock_sb.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = empty_result
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = empty_result

        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = query_assessment_results(
                join_code="ABC123",
                limit="not-a-number",  # invalid
                teacher_id="t",
            )

        # Function should not raise — returns valid output (even if empty)
        # Defensive try/except converted invalid limit to _DEFAULT_PAGE_SIZE
        assert "pagination" in result
        assert result["pagination"]["limit"] == 100  # _DEFAULT_PAGE_SIZE

    def test_invalid_offset_falls_back_to_zero(self):
        from backend.services.assistant_tools_assessments import (
            query_assessment_results,
        )
        mock_sb = MagicMock()
        first_result = MagicMock(data=[{
            "id": "a1", "join_code": "ABC123",
            "title": "Q1", "settings": {},
        }])
        empty_result = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = first_result
        mock_sb.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = empty_result
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = empty_result

        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = query_assessment_results(
                join_code="ABC123",
                offset="invalid-offset",  # falls back to 0
                teacher_id="t",
            )
        assert result["pagination"]["offset"] == 0

    def test_page_size_clamped_to_max(self):
        # limit=10000 should be clamped to _MAX_PAGE_SIZE=500
        from backend.services.assistant_tools_assessments import (
            query_assessment_results,
        )
        mock_sb = MagicMock()
        first_result = MagicMock(data=[{
            "id": "a1", "join_code": "ABC123",
            "title": "Q1", "settings": {},
        }])
        empty_result = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = first_result
        mock_sb.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = empty_result
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = empty_result

        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = query_assessment_results(
                join_code="ABC123",
                limit=10000,
                teacher_id="t",
            )
        assert result["pagination"]["limit"] == 500

    def test_outer_exception_returns_error(self):
        # Force any inner query to raise → outer except returns error dict
        from backend.services.assistant_tools_assessments import (
            query_assessment_results,
        )
        mock_sb = MagicMock()
        # Make the very first select chain raise
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = RuntimeError("DB exploded")

        with patch(f"{MODULE}._get_supabase", return_value=mock_sb):
            result = query_assessment_results(
                join_code="ABC", teacher_id="t",
            )
        assert "error" in result
        assert "Failed to query assessment results" in result["error"]
