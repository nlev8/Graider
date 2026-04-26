"""Tests for the gradebook endpoint and the _coalesce helper.

Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ _coalesce helper unit tests ============

class TestCoalesce:
    """_coalesce: first-non-None semantics (NOT `or`-truthiness)."""

    def test_returns_first_non_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, "fallback", "later") == "fallback"

    def test_returns_default_when_all_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, None, default=42) == 42

    def test_zero_is_kept_not_treated_as_falsy(self):
        """The whole reason this helper exists: legitimate 0 must not fall through."""
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(0, 999, default=-1) == 0

    def test_empty_string_is_kept_not_treated_as_falsy(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce("", "fallback", default="default") == ""
