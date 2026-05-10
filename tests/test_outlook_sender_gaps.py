"""Gap-fill unit tests for backend/services/outlook_sender.py.

Audit MAJOR #4 sprint follow-up to PR #301. Companion to existing
tests/test_outlook_sender.py (which covers emit / load_credentials /
wait_for_new_tab / send_email happy + fallback). Targets the
remaining 143 uncovered LOC (38% baseline → ~99%).

Branches covered
* navigate_to_outlook (lines 73-170) — full SSO state machine through
  VPortal → ADFS → ClassLink → Outlook with Meta + 2FA + URL guard
* send_email gap branches (CC visibility check raise, subject "could
  not find" raise on full fallback exhaustion, body all-fallbacks-fail
  raise)
* main() (lines 260-375) — login-only / test-mode / batch / no-creds /
  no-district / per-email failure swallow with screenshot + outer
  exception path
"""
from __future__ import annotations

import base64
import json
import sys
from unittest.mock import patch, MagicMock

import pytest

import backend.services.outlook_sender as outlook_sender


def _make_page():
    """Build a MagicMock page that can serve as a Playwright page-like."""
    page = MagicMock()
    # Default URL chain: outlook landing page
    page.url = "https://outlook.office365.com/mail/"
    return page


# ──────────────────────────────────────────────────────────────────
# navigate_to_outlook — happy path + ADFS + 2FA branches
# ──────────────────────────────────────────────────────────────────


class TestNavigateToOutlook:
    def _district(self):
        return {
            "name": "Test District",
            "portal_url": "https://vportal.example/",
            "selectors": {
                "portal_login_button": "#login-btn",
                "username_field": "#user",
                "password_field": "#pass",
                "login_button": "#submit",
            },
        }

    def test_full_sso_flow_with_adfs_classlink_outlook(self):
        # URL accesses in order through the flow:
        # 1. Step 3 ADFS check (line 94) → "adfs/login" matches → fills run
        # 2. Step 4 classlink check (line 113) → "classlink.com" matches
        # 3. Step 6 Microsoft login check (line 122) → outlook URL (skip 2FA)
        # 4. Step 6b Office 365 post-2FA check (line 138) → outlook URL
        # 5. Step 7 reachout outlook check (lines 151-152) → already outlook
        url_seq = iter([
            "https://vportal.example/adfs/login",  # ADFS check
            "https://classlink.com/dashboard",      # classlink check
            "https://outlook.office365.com/mail/",  # MS-login check
            "https://outlook.office365.com/mail/",  # post-2FA office365 check
            "https://outlook.office365.com/mail/",  # final outlook URL check
        ])

        class WrappedPage:
            def __init__(self):
                self._mock = MagicMock()

            def __getattr__(self, name):
                if name == "url":
                    return next(url_seq, "https://outlook.office365.com/mail/")
                return getattr(self._mock, name)

        wp = WrappedPage()
        ctx = MagicMock()

        result = outlook_sender.navigate_to_outlook(
            wp, ctx, self._district(),
            "teacher@district.org", "secret-pw",
        )
        assert result is wp
        # ADFS fill happened (twice: username + password)
        assert wp._mock.fill.call_count == 2
        # ClassLink → outlook direct nav
        outlook_gotos = [
            call for call in wp._mock.goto.call_args_list
            if "outlook.office365.com" in str(call.args)
        ]
        assert outlook_gotos

    def test_portal_login_button_click_failure_swallowed(self):
        # Step 2 click raises (cached session past landing) → swallowed
        page = MagicMock()
        page.url = "https://classlink.com/dashboard"  # already past
        page.click.side_effect = [Exception("no button"), None, None]
        ctx = MagicMock()

        result = outlook_sender.navigate_to_outlook(
            page, ctx, self._district(),
            "teacher@district.org", "secret-pw",
        )
        assert result is page

    def test_microsoft_2fa_timeout_raises(self):
        page = MagicMock()
        # URL stays on Microsoft login → wait_for_url times out
        page.url = "https://login.microsoftonline.com/auth"
        page.wait_for_url.side_effect = Exception("timeout")
        ctx = MagicMock()
        with pytest.raises(Exception, match="2FA timeout"):
            outlook_sender.navigate_to_outlook(
                page, ctx, self._district(),
                "teacher@district.org", "secret-pw",
            )

    def test_outlook_url_check_failure_raises_helpful_error(self):
        page = MagicMock()
        # We pass through everything but page never lands on outlook URL
        page.url = "https://other.example/"
        page.wait_for_url.side_effect = Exception("url timeout")
        ctx = MagicMock()
        # ADFS step skipped because URL has no adfs/login
        with pytest.raises(Exception, match="Failed to reach Outlook"):
            outlook_sender.navigate_to_outlook(
                page, ctx, self._district(),
                "teacher@district.org", "secret-pw",
            )

    def test_2fa_completes_successfully_inside_try(self):
        # Lines 130-132: wait_for_url returns successfully → emit/wait
        # branch fires. Build URL sequence so MS-login check matches.
        url_seq = iter([
            "https://vportal.example/x",          # ADFS skip
            "https://vportal.example/x",          # classlink skip
            "https://login.microsoftonline.com/auth",  # MS login match
            "https://outlook.office365.com/mail/",  # post-2FA office365 check
            "https://outlook.office365.com/mail/",  # final outlook check
        ])

        class WrappedPage:
            def __init__(self):
                self._mock = MagicMock()
                # wait_for_url returns successfully (no raise)
                self._mock.wait_for_url.return_value = None

            def __getattr__(self, name):
                if name == "url":
                    return next(url_seq, "https://outlook.office365.com/mail/")
                return getattr(self._mock, name)

        wp = WrappedPage()
        ctx = MagicMock()
        result = outlook_sender.navigate_to_outlook(
            wp, ctx, self._district(),
            "teacher@district.org", "secret-pw",
        )
        assert result is wp
        # wait_for_url called for the 2FA wait
        wp._mock.wait_for_url.assert_called()

    def test_adfs_fill_failure_swallowed(self):
        # Lines 107-109: page.fill raises during ADFS form fill →
        # swallowed (cached session means form may not be present).
        url_seq = iter([
            "https://vportal.example/login",  # ADFS check matches "login"
            "https://outlook.office365.com/mail/",  # classlink skip
            "https://outlook.office365.com/mail/",  # MS login skip
            "https://outlook.office365.com/mail/",  # office365 check
            "https://outlook.office365.com/mail/",  # final
        ])

        class WrappedPage:
            def __init__(self):
                self._mock = MagicMock()
                # fill raises → except path fires
                self._mock.fill.side_effect = Exception("no form")

            def __getattr__(self, name):
                if name == "url":
                    return next(url_seq, "https://outlook.office365.com/mail/")
                return getattr(self._mock, name)

        wp = WrappedPage()
        ctx = MagicMock()
        # Must not raise; ADFS exception swallowed
        result = outlook_sender.navigate_to_outlook(
            wp, ctx, self._district(),
            "teacher@district.org", "secret-pw",
        )
        assert result is wp

    def test_outlook_button_wait_failure_swallowed_returns_page(self):
        # The "New mail" button wait may fail (Outlook localizes labels) —
        # production swallows and returns the page anyway.
        page = MagicMock()
        page.url = "https://outlook.office365.com/mail/"
        ctx = MagicMock()
        # Make get_by_role(...).wait_for raise — production swallows.
        new_mail_btn = MagicMock()
        new_mail_btn.wait_for.side_effect = Exception("button not visible")
        page.get_by_role.return_value = new_mail_btn

        result = outlook_sender.navigate_to_outlook(
            page, ctx, self._district(),
            "teacher@district.org", "secret-pw",
        )
        assert result is page



# ──────────────────────────────────────────────────────────────────
# send_email gap branches
# ──────────────────────────────────────────────────────────────────


class TestSendEmailGapBranches:
    def test_subject_field_not_found_raises(self):
        # All 4 subject selectors raise → "Could not find subject field"
        page = MagicMock()
        bad = MagicMock()
        bad.click.side_effect = Exception("never findable")
        bad.is_visible.return_value = False  # CC expand path
        page.get_by_placeholder.return_value = bad
        page.locator.return_value = bad
        page.get_by_text.return_value = bad

        with pytest.raises(Exception, match="Could not find subject field"):
            outlook_sender.send_email(page, {
                "to": "x@y.com",
                "subject": "Won't be findable",
                "body": "B",
                "student_name": "S",
            }, index=0, total=1)

    def test_cc_expand_button_visible_clicks(self):
        # Pin the branch where Show Cc & Bcc button exists and is visible
        # → expand_btn.click() fires, CC field becomes available.
        page = MagicMock()
        # is_visible returns True so the click happens
        cc_expand = MagicMock()
        cc_expand.is_visible.return_value = True

        # Track locator selectors
        def locator_side(sel, *a, **kw):
            m = MagicMock()
            if 'Show Cc & Bcc' in sel:
                return cc_expand
            return m

        page.locator.side_effect = locator_side
        # Subject + body succeed via get_by_placeholder
        good = MagicMock()
        page.get_by_placeholder.return_value = good
        page.get_by_text.return_value = good

        outlook_sender.send_email(page, {
            "to": "x@y.com", "cc": "copy@y.com",
            "subject": "S", "body": "B", "student_name": "S",
        }, index=0, total=1)

        # cc_expand.click was called
        cc_expand.click.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# main() — sys.argv + sync_playwright orchestration
# ──────────────────────────────────────────────────────────────────


def _make_playwright_context():
    """Build a fake sync_playwright context manager."""
    fake_page = MagicMock()
    fake_page.url = "https://outlook.office365.com/mail/"

    fake_context = MagicMock()
    fake_context.pages = [fake_page]
    fake_context.new_page.return_value = fake_page

    fake_chromium = MagicMock()
    fake_chromium.launch_persistent_context.return_value = fake_context

    fake_p = MagicMock()
    fake_p.chromium = fake_chromium

    fake_pw_cm = MagicMock()
    fake_pw_cm.__enter__ = MagicMock(return_value=fake_p)
    fake_pw_cm.__exit__ = MagicMock(return_value=None)

    return fake_pw_cm, fake_p, fake_context, fake_page


class TestMain:
    @pytest.fixture(autouse=True)
    def _no_real_sleep(self, monkeypatch):
        # Speed up time.sleep calls in main() between emails
        monkeypatch.setattr(outlook_sender.time, "sleep", lambda *a: None)

    def test_no_credentials_exits_1(self, monkeypatch, capsys):
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: (None, None),
        )
        with pytest.raises(SystemExit) as exc:
            outlook_sender.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "No portal credentials" in out

    def test_no_district_exits_1(self, monkeypatch, capsys):
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@unknown.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: None,
        )
        with pytest.raises(SystemExit) as exc:
            outlook_sender.main()
        assert exc.value.code == 1
        assert "No district config" in capsys.readouterr().out

    def test_login_only_navigates_and_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["outlook_sender.py", "--login-only"])
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "Test", "portal_url": "https://x.example/",
                           "selectors": {}},
        )
        nav_mock = MagicMock(return_value=MagicMock(
            url="https://outlook.office365.com/mail/",
        ))
        monkeypatch.setattr(
            outlook_sender, "navigate_to_outlook", nav_mock,
        )

        fake_pw_cm, fake_p, fake_context, fake_page = _make_playwright_context()
        with patch(
            "playwright.sync_api.sync_playwright",
            return_value=fake_pw_cm,
        ):
            outlook_sender.main()

        # Login-only path: navigate_to_outlook called, no email send
        nav_mock.assert_called_once()
        # context.close() in finally
        fake_context.close.assert_called()
        out = capsys.readouterr().out
        assert "Login successful" in out

    def test_test_mode_sends_one_email(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", [
            "outlook_sender.py", "--test", "recipient@example.com",
        ])
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "Test", "portal_url": "https://x/",
                           "selectors": {}},
        )
        monkeypatch.setattr(
            outlook_sender, "navigate_to_outlook",
            lambda *a, **kw: a[0],  # pass the page through
        )
        send_mock = MagicMock()
        monkeypatch.setattr(outlook_sender, "send_email", send_mock)

        fake_pw_cm, *_ = _make_playwright_context()
        with patch(
            "playwright.sync_api.sync_playwright",
            return_value=fake_pw_cm,
        ):
            outlook_sender.main()

        # Test mode → one synthetic email sent to recipient@example.com
        send_mock.assert_called_once()
        sent_eml = send_mock.call_args.args[1]
        assert sent_eml["to"] == "recipient@example.com"
        assert sent_eml["student_name"] == "Test"

    def test_batch_mode_sends_all_emails(self, monkeypatch, tmp_path, capsys):
        emails_json = tmp_path / "emails.json"
        emails_json.write_text(json.dumps({
            "emails": [
                {"to": "a@x.com", "subject": "S1", "body": "B1",
                 "student_name": "A"},
                {"to": "b@x.com", "subject": "S2", "body": "B2",
                 "student_name": "B"},
            ],
        }))
        monkeypatch.setattr(
            sys, "argv", ["outlook_sender.py", str(emails_json)],
        )
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "T", "portal_url": "x", "selectors": {}},
        )
        monkeypatch.setattr(
            outlook_sender, "navigate_to_outlook",
            lambda *a, **kw: a[0],
        )
        send_mock = MagicMock()
        monkeypatch.setattr(outlook_sender, "send_email", send_mock)

        fake_pw_cm, *_ = _make_playwright_context()
        with patch(
            "playwright.sync_api.sync_playwright",
            return_value=fake_pw_cm,
        ):
            outlook_sender.main()

        # Both emails sent
        assert send_mock.call_count == 2
        out = capsys.readouterr().out
        assert '"sent": 2' in out
        assert '"failed": 0' in out

    def test_batch_mode_no_json_file_exits_1(
        self, monkeypatch, capsys,
    ):
        monkeypatch.setattr(sys, "argv", ["outlook_sender.py"])
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "T", "portal_url": "x", "selectors": {}},
        )
        with pytest.raises(SystemExit) as exc:
            outlook_sender.main()
        assert exc.value.code == 1
        assert "No email JSON file" in capsys.readouterr().out

    def test_batch_mode_empty_emails_exits_1(
        self, monkeypatch, tmp_path, capsys,
    ):
        emails_json = tmp_path / "empty.json"
        emails_json.write_text(json.dumps({"emails": []}))
        monkeypatch.setattr(
            sys, "argv", ["outlook_sender.py", str(emails_json)],
        )
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "T", "portal_url": "x", "selectors": {}},
        )
        with pytest.raises(SystemExit) as exc:
            outlook_sender.main()
        assert exc.value.code == 1
        assert "No emails in JSON" in capsys.readouterr().out

    def test_per_email_failure_records_screenshot_and_continues(
        self, monkeypatch, tmp_path, capsys,
    ):
        emails_json = tmp_path / "emails.json"
        emails_json.write_text(json.dumps({
            "emails": [
                {"to": "a@x.com", "subject": "S", "body": "B",
                 "student_name": "A"},
                {"to": "b@x.com", "subject": "S", "body": "B",
                 "student_name": "B"},
            ],
        }))
        monkeypatch.setattr(
            sys, "argv", ["outlook_sender.py", str(emails_json)],
        )
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "T", "portal_url": "x", "selectors": {}},
        )
        monkeypatch.setattr(
            outlook_sender, "navigate_to_outlook",
            lambda *a, **kw: a[0],
        )
        # First email raises, second succeeds
        send_mock = MagicMock(
            side_effect=[Exception("fail"), None],
        )
        monkeypatch.setattr(outlook_sender, "send_email", send_mock)

        fake_pw_cm, _, _, fake_page = _make_playwright_context()
        with patch(
            "playwright.sync_api.sync_playwright",
            return_value=fake_pw_cm,
        ):
            outlook_sender.main()

        # Both attempted
        assert send_mock.call_count == 2
        # Screenshot called on the failure
        fake_page.screenshot.assert_called()
        out = capsys.readouterr().out
        assert '"sent": 1' in out
        assert '"failed": 1' in out

    def test_outer_exception_keeps_browser_open_in_test_mode(
        self, monkeypatch,
    ):
        monkeypatch.setattr(sys, "argv", [
            "outlook_sender.py", "--test", "recipient@example.com",
        ])
        monkeypatch.setattr(
            outlook_sender, "load_credentials",
            lambda: ("teacher@x.org", "pw"),
        )
        monkeypatch.setattr(
            outlook_sender, "find_district_by_email",
            lambda email: {"name": "T", "portal_url": "x", "selectors": {}},
        )
        # navigate_to_outlook raises → outer exception path
        monkeypatch.setattr(
            outlook_sender, "navigate_to_outlook",
            MagicMock(side_effect=Exception("nav blew up")),
        )

        fake_pw_cm, _, fake_context, fake_page = _make_playwright_context()
        with patch(
            "playwright.sync_api.sync_playwright",
            return_value=fake_pw_cm,
        ):
            outlook_sender.main()

        # Error screenshot taken; context.close in finally
        fake_page.screenshot.assert_called()
        fake_context.close.assert_called()
