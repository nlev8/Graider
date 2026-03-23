"""Tests for backend/utils/compliance.py"""
import pytest
from unittest.mock import patch


class TestRequireTeacherId:
    def test_blocks_none(self):
        from backend.utils.compliance import require_teacher_id
        with pytest.raises(ValueError, match="teacher_id"):
            require_teacher_id(None)

    def test_blocks_empty(self):
        from backend.utils.compliance import require_teacher_id
        with pytest.raises(ValueError, match="teacher_id"):
            require_teacher_id("")

    @patch('backend.utils.compliance._is_supabase_configured', return_value=True)
    def test_blocks_local_dev_in_prod(self, mock_sb):
        from backend.utils.compliance import require_teacher_id
        with pytest.raises(ValueError, match="local-dev"):
            require_teacher_id("local-dev")

    @patch('backend.utils.compliance._is_supabase_configured', return_value=False)
    def test_allows_local_dev_in_dev(self, mock_sb):
        from backend.utils.compliance import require_teacher_id
        require_teacher_id("local-dev")  # Should not raise

    def test_allows_real_teacher_id(self):
        from backend.utils.compliance import require_teacher_id
        require_teacher_id("teacher-abc-123")  # Should not raise


class TestAnonymizeForAi:
    def test_roundtrip(self):
        from backend.utils.compliance import anonymize_for_ai, deanonymize
        roster = [{"student_name": "Maria Garcia"}, {"student_name": "John Smith"}]
        text = "Maria Garcia scored 85%. John Smith needs improvement."
        anon, mapping = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon
        assert "John Smith" not in anon
        assert "[STUDENT_" in anon
        restored = deanonymize(anon, mapping)
        assert "Maria Garcia" in restored
        assert "John Smith" in restored

    def test_preserves_accommodation_types(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Maria Garcia"}]
        text = "Maria Garcia has IEP accommodations: extended time, large text."
        anon, _ = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon
        assert "extended time" in anon
        assert "large text" in anon

    def test_handles_last_first_format(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Garcia, Maria"}]
        text = "Garcia, Maria scored well."
        anon, mapping = anonymize_for_ai(text, roster)
        assert "Garcia, Maria" not in anon
        assert len(mapping) > 0

    def test_handles_reversed_name_in_text(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Garcia, Maria"}]
        text = "Maria Garcia improved this quarter."
        anon, mapping = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon
        assert len(mapping) > 0

    def test_anonymizes_free_text_notes(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Maria Garcia"}]
        text = "Accommodation notes: Maria Garcia's mother requested extra time."
        anon, _ = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon

    @patch('backend.utils.compliance._is_supabase_configured', return_value=True)
    def test_requires_roster_in_prod(self, mock_sb):
        from backend.utils.compliance import anonymize_for_ai
        with pytest.raises(ValueError, match="roster"):
            anonymize_for_ai("Some text", roster=None)

    @patch('backend.utils.compliance._is_supabase_configured', return_value=False)
    def test_allows_no_roster_in_dev(self, mock_sb):
        from backend.utils.compliance import anonymize_for_ai
        anon, mapping = anonymize_for_ai("Some text with no names", roster=None)
        assert isinstance(anon, str)
        assert isinstance(mapping, dict)

    def test_no_names_returns_unchanged(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Maria Garcia"}]
        text = "This text has no student names in it."
        anon, mapping = anonymize_for_ai(text, roster)
        assert anon == text
        assert len(mapping) == 0


class TestAuditToolAction:
    @patch('backend.utils.audit.audit_log')
    def test_formats_action_correctly(self, mock_audit):
        from backend.utils.compliance import audit_tool_action
        audit_tool_action("teacher-123", "query_grades", "INVOKE", "period=1st")
        mock_audit.assert_called_once()
        args, kwargs = mock_audit.call_args
        assert "TOOL_query_grades_INVOKE" in args[0]
        assert kwargs.get('teacher_id') == "teacher-123"

    @patch('backend.utils.audit.audit_log')
    def test_strips_pii_from_details(self, mock_audit):
        from backend.utils.compliance import audit_tool_action
        audit_tool_action("teacher-123", "export", "EXPORT", "Exported data for Maria Garcia")
        args, kwargs = mock_audit.call_args
        # Details is the second positional arg
        assert "Maria Garcia" not in args[1]

    @patch('backend.utils.audit.audit_log')
    def test_handles_none_details(self, mock_audit):
        from backend.utils.compliance import audit_tool_action
        audit_tool_action("teacher-123", "test_tool", "INVOKE")
        mock_audit.assert_called_once()
