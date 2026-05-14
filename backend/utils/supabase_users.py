"""Pagination helper for Supabase Auth list_users().

The supabase-py SDK defaults to page_size=50 (verified at
venv/.../supabase_auth/_sync/gotrue_admin_api.py:134). Call sites that
need to scan ALL users (account merge, approval lookup, Stripe linking)
must iterate.

Regression tests: tests/test_list_users_pagination_issue372.py
Source: 2026-05-14 dimensional review S4.
"""
from typing import List

_PAGE_SIZE = 50
_MAX_PAGES = 100  # Hard cap: 5,000 users. Well above any plausible
                  # deployment; protects against mock-induced infinite
                  # loops in tests that use .return_value (Gemini-proxy
                  # plan review caught this risk pattern).


def list_all_users(sb) -> List:
    """Return ALL users from sb.auth.admin.list_users(), iterating pages.

    Calls list_users(page=N, per_page=50) until a page returns fewer than
    50 records (or we hit the hard cap). The SDK is expected to accept
    these kwargs; if it doesn't, this raises rather than silently
    falling back to single-page (Gemini-proxy plan review S5 — silent
    fallback is a security regression vector).
    """
    all_users = []
    for page in range(1, _MAX_PAGES + 1):
        resp = sb.auth.admin.list_users(page=page, per_page=_PAGE_SIZE)
        page_users = list(resp or [])
        all_users.extend(page_users)
        if len(page_users) < _PAGE_SIZE:
            break
    return all_users
