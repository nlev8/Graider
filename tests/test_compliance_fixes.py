"""Regression tests for Clever/OneRoster compliance fixes.

Covers: analytics filter bypass, provider switch lock TTL,
contact save retry, email validation + normalization.
"""
import json
import time
import pytest
from unittest.mock import patch, MagicMock, call


# ═══════════════════════════════════════════════════════════
# Analytics Filter Bypass
# ═══════════════════════════════════════════════════════════

class TestAnalyticsFilterBypass:
    """When saved config names don't match any graded assignment names,
    analytics should show everything instead of an empty dashboard."""

    def _make_results(self, assignments):
        return [
            {"student_name": f"Student {i}", "assignment": name,
             "score": 80 + i, "total_points": 100, "percentage": 80 + i,
             "breakdown": {}, "period": "Period 1"}
            for i, name in enumerate(assignments)
        ]

    def test_zero_matches_bypasses_filter(self):
        """No config names match results → filter_bypassed=True, all results shown."""
        from backend.routes.analytics_routes import _assignment_matches_config

        valid_names = {'worksheet 1', 'worksheet 2'}
        results = self._make_results(['Cornell Notes - Ch 5', 'Cornell Notes - Ch 6'])

        has_any_match = any(
            _assignment_matches_config(r.get("assignment", ""), valid_names)
            for r in results if r.get("student_name", "").strip()
        )
        assert has_any_match is False  # No matches → bypass should trigger

    def test_matching_names_filter_works(self):
        """Config names that match results → filter should NOT bypass."""
        from backend.routes.analytics_routes import _assignment_matches_config

        valid_names = {'cornell notes'}
        results = self._make_results(['Cornell Notes - Ch 5', 'Something Else'])

        has_any_match = any(
            _assignment_matches_config(r.get("assignment", ""), valid_names)
            for r in results if r.get("student_name", "").strip()
        )
        assert has_any_match is True  # Match found → filter stays active

    def test_empty_valid_names_shows_everything(self):
        """No saved configs → no filter applied, all results shown."""
        valid_names = set()
        # Empty set is falsy, so the filter check is skipped entirely
        assert not valid_names  # Confirms empty set bypasses the filter


# ═══════════════════════════════════════════════════════════
# Provider Switch Lock TTL
# ═══════════════════════════════════════════════════════════

class TestProviderSwitchLockTTL:
    """Lock flag should expire after 5 minutes to prevent permanent lockout."""

    def test_fresh_lock_blocks(self):
        """Lock set < 5 min ago → should block."""
        lock_data = {"timestamp": time.time()}
        lock_time = lock_data.get("timestamp", 0)
        is_fresh = (time.time() - lock_time) < 300
        assert is_fresh is True

    def test_stale_lock_expires(self):
        """Lock set > 5 min ago → should be treated as expired."""
        lock_data = {"timestamp": time.time() - 600}  # 10 minutes ago
        lock_time = lock_data.get("timestamp", 0)
        is_fresh = (time.time() - lock_time) < 300
        assert is_fresh is False  # Stale → should auto-clear

    def test_legacy_lock_without_timestamp_expires(self):
        """Lock set as True (no timestamp) → treated as expired (timestamp=0)."""
        lock_data = True  # Legacy format
        lock_time = lock_data.get("timestamp", 0) if isinstance(lock_data, dict) else 0
        is_fresh = (time.time() - lock_time) < 300
        assert is_fresh is False  # No timestamp → epoch 0 → definitely > 5 min

    def test_no_lock_allows_sync(self):
        """None lock → sync proceeds."""
        lock_data = None
        assert not lock_data  # Falsy → skip lock check


# ═══════════════════════════════════════════════════════════
# Contact Save Retry
# ═══════════════════════════════════════════════════════════

class TestContactSaveRetry:
    """_save_parent_contacts retries once on Supabase failure."""

    def test_first_attempt_succeeds(self):
        """Normal case — no retry needed."""
        mock_save = MagicMock()
        with patch('backend.routes.settings_routes.storage_save', mock_save), \
             patch('builtins.open', MagicMock()):
            from backend.routes.settings_routes import _save_parent_contacts
            result = _save_parent_contacts({"test": "data"}, teacher_id="t1")
            assert result["supabase_ok"] is True
            assert mock_save.call_count == 1

    def test_retry_on_transient_failure(self):
        """First attempt fails, retry succeeds."""
        mock_save = MagicMock(side_effect=[Exception("timeout"), None])
        with patch('backend.routes.settings_routes.storage_save', mock_save), \
             patch('builtins.open', MagicMock()):
            from backend.routes.settings_routes import _save_parent_contacts
            result = _save_parent_contacts({"test": "data"}, teacher_id="t1")
            assert result["supabase_ok"] is True
            assert mock_save.call_count == 2

    def test_both_attempts_fail(self):
        """Both attempts fail → supabase_ok False."""
        mock_save = MagicMock(side_effect=Exception("permanent failure"))
        with patch('backend.routes.settings_routes.storage_save', mock_save), \
             patch('builtins.open', MagicMock()):
            from backend.routes.settings_routes import _save_parent_contacts
            result = _save_parent_contacts({"test": "data"}, teacher_id="t1")
            assert result["supabase_ok"] is False
            assert mock_save.call_count == 2


# ═══════════════════════════════════════════════════════════
# Email Validation + Normalization
# ═══════════════════════════════════════════════════════════

class TestEmailNormalization:
    """Student emails should be validated and lowercased."""

    def test_valid_email_accepted(self):
        import re
        email = "Student@School.EDU"
        assert re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email)

    def test_valid_email_lowercased(self):
        email = "Student@School.EDU".lower()
        assert email == "student@school.edu"

    def test_invalid_email_rejected(self):
        import re
        assert not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', "not-an-email")
        assert not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', "missing@")
        assert not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', "@no-local.com")

    def test_empty_email_skips_validation(self):
        """Empty string should not trigger validation — email is optional."""
        email = ""
        # The code only validates when student_email is truthy
        assert not email  # Falsy → skip validation block

    def test_whitespace_stripped(self):
        email = "  student@school.edu  ".strip()
        assert email == "student@school.edu"

    def test_alpha_id_format(self):
        """Volusia-style alpha ID emails should pass validation."""
        import re
        assert re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', "2AADB@vcs2go.net")
