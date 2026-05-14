"""Regression tests for unpaginated list_users(). Source: 2026-05-14 dimensional review S4.

supabase-py admin.list_users() defaults to 50 results per page. Three production
call sites assumed the unpaginated default returns the full list; past 50
teachers, users on page 2+ would silently fail to merge.
"""
from unittest.mock import MagicMock


def _users(prefix, n):
    return [MagicMock(id=f"{prefix}{i}", email=f"{prefix}{i}@s.edu") for i in range(n)]


class TestListAllUsersPagination:
    def test_single_short_page_returns_all_users(self):
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = _users("u", 10)
        assert len(list_all_users(sb)) == 10

    def test_multiple_full_pages_concatenated(self):
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.side_effect = [
            _users("a", 50), _users("b", 25),
        ]
        assert len(list_all_users(sb)) == 75

    def test_two_full_pages_then_empty(self):
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.side_effect = [
            _users("a", 50), _users("b", 50), [],
        ]
        assert len(list_all_users(sb)) == 100

    def test_hard_cap_prevents_infinite_loop(self):
        """If a misconfigured mock returns a full page forever (like
        existing tests' .return_value pattern), the helper must hard-cap
        rather than loop indefinitely."""
        from backend.utils.supabase_users import list_all_users, _MAX_PAGES
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = _users("u", 50)
        result = list_all_users(sb)
        assert len(result) == 50 * _MAX_PAGES, (
            f"Expected hard cap at {_MAX_PAGES} pages x 50 = {50 * _MAX_PAGES}, "
            f"got {len(result)}"
        )

    def test_called_with_page_kwargs(self):
        """Helper must request specific pages — not the no-arg form."""
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = []
        list_all_users(sb)
        sb.auth.admin.list_users.assert_called_with(page=1, per_page=50)
