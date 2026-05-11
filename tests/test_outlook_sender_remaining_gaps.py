"""Additional gap-fill tests for backend/services/outlook_sender.py.

Audit MAJOR #4 sprint follow-up to PR #328. Companion to existing
`tests/test_outlook_sender.py` and `tests/test_outlook_sender_gaps.py`.

Targets the remaining 15 missing LOC (93.5% baseline). Most of these
are exception-swallow branches in `send_email` (CC visibility check)
and `main()` (per-email screenshot + Discard). The post-2FA Office365
redirect (lines 130-141) and the `__main__` block (line 379) are
deferred — covered by integration paths in test_outlook_sender_gaps.py.

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# send_email CC expand_btn exception swallow (lines 198-199)
# ──────────────────────────────────────────────────────────────────


class TestSendEmailCCExceptionSwallow:
    def test_cc_expand_btn_is_visible_raises_swallowed(self):
        """When CC expand_btn.is_visible() raises, the exception is
        caught and execution continues to the CC field click+type."""
        from backend.services.outlook_sender import send_email

        page = MagicMock()

        # Set up locators
        expand_btn_mock = MagicMock()
        expand_btn_mock.is_visible.side_effect = RuntimeError(
            "is_visible threw"
        )

        cc_field_mock = MagicMock()
        cc_field_mock.last = MagicMock()
        cc_field_mock.last.click = MagicMock()

        to_field_mock = MagicMock()
        to_field_mock.last = MagicMock()
        to_field_mock.last.click = MagicMock()

        def locator_side(selector):
            if 'Show Cc' in selector or 'Show Cc & Bcc' in selector:
                return expand_btn_mock
            if '"Cc"' in selector:
                return cc_field_mock
            if '"To"' in selector:
                return to_field_mock
            # Body field locator
            mock = MagicMock()
            mock.last = MagicMock()
            mock.last.click = MagicMock()
            mock.last.fill = MagicMock()
            mock.count.return_value = 0  # No fallback selectors hit
            return mock

        page.locator = MagicMock(side_effect=locator_side)
        page.get_by_role.return_value.click = MagicMock()
        page.get_by_placeholder.return_value.fill = MagicMock()
        page.keyboard = MagicMock()
        page.wait_for_timeout = MagicMock()
        page.frames = []

        eml = {
            "to": "alice@example.com",
            "cc": "bob@example.com",
            "student_name": "Alice Smith",
            "subject": "Test subject",
            "body": "Test body",
        }

        send_email(page, eml, 0, 1)

        # Proves the production try/except actually swallowed the
        # is_visible exception: if it had propagated, execution would
        # never reach the CC field click on the next line.
        expand_btn_mock.is_visible.assert_called_once()
        cc_field_mock.last.click.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# navigate_to_outlook post-2FA Office365 → Outlook redirect (lines 130-141)
# ──────────────────────────────────────────────────────────────────


class TestNavigateToOutlookPost2FA:
    def test_post_2fa_office365_jumps_to_outlook(self):
        """Lines 137-141: when 2FA completes and the URL is on Office
        365 (not Outlook), the function navigates directly to outlook.
        Tests the post-2FA office365.com → outlook.office365.com jump."""
        from backend.services.outlook_sender import navigate_to_outlook

        district = {
            "name": "Test District",
            "portal_url": "https://vportal.example/",
            "selectors": {
                "portal_login_button": "#login-btn",
                "username_field": "#user",
                "password_field": "#pass",
                "login_button": "#submit",
            },
        }

        # Stateful page.url: starts on office.com (which makes the
        # ADFS, ClassLink, and microsoftonline branches all skip), so
        # the only matching branch is the post-2FA Office365 → Outlook
        # jump at lines 137-141. After production calls page.goto on
        # the outlook URL, we advance state so the subsequent
        # wait_for_url and "outlook in url" assertion both succeed.
        state = {"url": "https://www.office.com/"}

        def goto_side(url, **_kwargs):
            if "outlook.office365.com" in url:
                state["url"] = url
            return None

        page = MagicMock()
        type(page).url = property(lambda self: state["url"])
        page.goto = MagicMock(side_effect=goto_side)
        page.wait_for_url = MagicMock()
        page.wait_for_load_state = MagicMock()
        page.wait_for_timeout = MagicMock()
        page.fill = MagicMock()
        page.click = MagicMock()
        page.get_by_role.return_value.wait_for = MagicMock()
        page.get_by_role.return_value.is_visible.return_value = False
        page.locator.return_value.is_visible.return_value = False
        page.locator.return_value.click = MagicMock()

        context = MagicMock()

        navigate_to_outlook(page, context, district, "u@x", "pw")

        # The post-2FA branch MUST have fired — production code calls
        # page.goto("https://outlook.office365.com/mail/", ...) when
        # current_url contains "office.com" and not "outlook".
        page.goto.assert_any_call(
            "https://outlook.office365.com/mail/",
            wait_until="domcontentloaded",
            timeout=30000,
        )


# ──────────────────────────────────────────────────────────────────
# Documentation pin: __main__ block is intentionally untested
# ──────────────────────────────────────────────────────────────────


class TestMainBlockIntentional:
    def test_main_function_is_callable(self):
        """Pin that main() exists as a callable. The `if __name__
        == '__main__': main()` line at module bottom (line 379) is
        intentionally not exercised in the unit test suite — it would
        require subprocess invocation. Existing
        `test_outlook_sender_gaps.py` covers the main() body via direct
        function calls."""
        from backend.services.outlook_sender import main
        assert callable(main)
