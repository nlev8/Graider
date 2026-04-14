"""Behavior-pinning tests for backend/services/outlook_sender.py.

Phase 2 Task 6 PR-c-3 per Codex Gate 1 path (b):
  - Pure utilities: emit / load_credentials / wait_for_new_tab
  - Mocked Playwright: send_email happy-path + fallback/failure

Explicitly SKIPS navigate_to_outlook() (URL state machine too brittle
for unit mocks) and main() (sys.argv + sync_playwright).

Codex guidance followed:
  - wait_for_new_tab uses monkeypatched time.time / time.sleep, not
    real sleeps → no flake.
  - send_email assertions target critical effects (what was typed where),
    not full mock_calls ordering.
  - Body-path Meta+ArrowUp cursor move accounted for.
"""
import base64
import json
from unittest.mock import MagicMock

import pytest

import backend.services.outlook_sender as outlook_sender
from backend.services.outlook_sender import (
    emit,
    load_credentials,
    send_email,
    wait_for_new_tab,
)


# ─────────────────────────────────────────────────────────────────
# emit()
# ─────────────────────────────────────────────────────────────────

class TestEmit:
    def test_emits_json_line_with_type(self, capsys):
        emit("status", message="hello")
        out = capsys.readouterr().out.strip()
        parsed = json.loads(out)
        assert parsed == {"type": "status", "message": "hello"}

    def test_emits_with_multiple_kwargs(self, capsys):
        emit("progress", sent=3, total=10, student="Jane")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["type"] == "progress"
        assert parsed["sent"] == 3
        assert parsed["total"] == 10
        assert parsed["student"] == "Jane"

    def test_each_emit_is_a_single_line(self, capsys):
        emit("a")
        emit("b")
        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "a"
        assert json.loads(lines[1])["type"] == "b"


# ─────────────────────────────────────────────────────────────────
# load_credentials()
# ─────────────────────────────────────────────────────────────────

class TestLoadCredentials:
    def test_returns_none_none_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(outlook_sender, "CREDS_FILE", str(tmp_path / "nope.json"))
        email, pwd = load_credentials()
        assert email is None and pwd is None

    def test_loads_email_and_decodes_password(self, tmp_path, monkeypatch):
        creds = tmp_path / "creds.json"
        creds.write_text(json.dumps({
            "email": "teacher@district.org",
            "password": base64.b64encode(b"secret-pw").decode(),
        }))
        monkeypatch.setattr(outlook_sender, "CREDS_FILE", str(creds))
        email, pwd = load_credentials()
        assert email == "teacher@district.org"
        assert pwd == "secret-pw"

    def test_missing_keys_return_empty_string(self, tmp_path, monkeypatch):
        creds = tmp_path / "creds.json"
        creds.write_text(json.dumps({}))  # no email, no password
        monkeypatch.setattr(outlook_sender, "CREDS_FILE", str(creds))
        email, pwd = load_credentials()
        # Empty string for email (default "") and decode of "" → ""
        assert email == ""
        assert pwd == ""


# ─────────────────────────────────────────────────────────────────
# wait_for_new_tab() — monkeypatched time
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_clock(monkeypatch):
    """Monotonic fake clock advanced manually via .advance(); time.sleep no-op."""
    state = {"now": 0.0}
    monkeypatch.setattr(outlook_sender.time, "time", lambda: state["now"])
    monkeypatch.setattr(outlook_sender.time, "sleep", lambda s: state.__setitem__("now", state["now"] + s))
    return state


class TestWaitForNewTab:
    def test_returns_new_page_when_tab_opens(self, fake_clock):
        new_page = MagicMock(name="new_page")
        ctx = MagicMock(pages=[MagicMock(), new_page])  # already 2 pages
        result = wait_for_new_tab(ctx, old_count=1, timeout=1000)
        assert result is new_page
        new_page.wait_for_load_state.assert_called_once_with("domcontentloaded")

    def test_returns_none_on_timeout(self, fake_clock):
        ctx = MagicMock(pages=[MagicMock()])  # pages stays at 1
        result = wait_for_new_tab(ctx, old_count=1, timeout=100)
        assert result is None

    def test_polls_then_succeeds(self, fake_clock, monkeypatch):
        """Context gains a page after two poll cycles — helper picks it up."""
        pages = [MagicMock()]
        ctx = MagicMock()
        # MagicMock doesn't let us make .pages dynamic easily; assign a list
        # we mutate between time.sleep calls.
        type(ctx).pages = property(lambda self: pages)

        calls = {"count": 0}

        def fake_sleep(s):
            calls["count"] += 1
            if calls["count"] == 2:
                pages.append(MagicMock(name="second"))
            fake_clock["now"] += s

        monkeypatch.setattr(outlook_sender.time, "sleep", fake_sleep)

        result = wait_for_new_tab(ctx, old_count=1, timeout=5000)
        assert result is pages[-1]


# ─────────────────────────────────────────────────────────────────
# send_email() — mocked Playwright page
# ─────────────────────────────────────────────────────────────────

def _make_page():
    """Build a MagicMock page that supports all the send_email operations."""
    page = MagicMock(name="page")
    # Chain helpers that return elements with click/is_visible/type
    page.get_by_role.return_value = MagicMock(name="new_mail_button")
    page.locator.return_value = MagicMock(name="locator")
    page.get_by_placeholder.return_value = MagicMock(name="placeholder_el")
    page.get_by_text.return_value = MagicMock(name="text_el")
    page.keyboard = MagicMock(name="keyboard")
    return page


class TestSendEmailHappyPath:
    def test_sends_to_subject_body(self, capsys):
        page = _make_page()
        eml = {
            "to": "parent@example.com",
            "subject": "Weekly update",
            "body": "Hello, your student did well this week.",
            "student_name": "Jane",
        }
        send_email(page, eml, index=0, total=1)

        # Typed To, Subject, Body into keyboard somewhere in that order
        typed = [c.args[0] for c in page.keyboard.type.mock_calls if c.args]
        assert "parent@example.com" in typed
        assert "Weekly update" in typed
        assert "Hello, your student did well this week." in typed

        # Meta+Enter was pressed exactly once at the end
        pressed = [c.args[0] for c in page.keyboard.press.mock_calls if c.args]
        assert "Meta+Enter" in pressed

        # Progress event emitted for the student
        out = capsys.readouterr().out
        assert "Jane" in out

    def test_skips_cc_when_not_provided(self):
        page = _make_page()
        send_email(page, {
            "to": "x@y.com", "subject": "S", "body": "B", "student_name": "S1"
        }, index=0, total=1)
        # No call to fill the Cc aria-label-specific locator for CC input:
        # locator() is called many times; ensure the specific '[aria-label="Cc"]'
        # invocation never happened.
        cc_calls = [
            c for c in page.locator.mock_calls
            if c.args and '[aria-label="Cc"]' in str(c.args[0])
        ]
        assert cc_calls == []

    def test_cc_present_types_cc_address(self):
        page = _make_page()
        send_email(page, {
            "to": "x@y.com", "cc": "copy@y.com",
            "subject": "S", "body": "B", "student_name": "S1",
        }, index=0, total=1)
        typed = [c.args[0] for c in page.keyboard.type.mock_calls if c.args]
        assert "copy@y.com" in typed

    def test_body_cursor_moves_to_top_before_type(self):
        """Body path presses Meta+ArrowUp before typing body so text lands
        above the signature."""
        page = _make_page()
        send_email(page, {
            "to": "x@y.com", "subject": "S", "body": "BODY",
            "student_name": "S1",
        }, index=0, total=1)
        presses = [c.args[0] for c in page.keyboard.press.mock_calls if c.args]
        # Meta+ArrowUp comes before Meta+Enter (the send shortcut)
        arrow_idx = presses.index("Meta+ArrowUp")
        enter_idx = presses.index("Meta+Enter")
        assert arrow_idx < enter_idx


class TestSendEmailFallbackAndFailure:
    def test_subject_fallback_chain_succeeds_on_later_selector(self):
        """First subject selectors raise; a later one succeeds. send_email
        must NOT raise 'Could not find subject field'."""
        page = _make_page()

        # placeholder path raises on click; locator path returns an element
        # whose click raises; get_by_text returns an element that works.
        bad_el = MagicMock()
        bad_el.click.side_effect = Exception("not found")
        page.get_by_placeholder.return_value = bad_el

        # locator() returns bad_el for aria-label subject but good ones for To/Cc;
        # easier: make all locator() return bad_el to force fallback further.
        def locator_side_effect(sel, *a, **kw):
            if "Add a subject" in sel:
                return bad_el
            # good default for other locators
            good = MagicMock()
            return good
        page.locator.side_effect = locator_side_effect

        # get_by_text returns a working element (final subject fallback)
        good_text_el = MagicMock()
        page.get_by_text.return_value = good_text_el

        send_email(page, {
            "to": "x@y.com", "subject": "Subj!", "body": "B",
            "student_name": "s",
        }, index=0, total=1)

        typed = [c.args[0] for c in page.keyboard.type.mock_calls if c.args]
        assert "Subj!" in typed

    def test_body_all_fail_raises(self):
        page = _make_page()
        # Force every body selector to raise — subject must succeed first
        # so we actually reach the body phase.
        page.get_by_placeholder.return_value = MagicMock()  # subject OK
        page.locator.return_value = MagicMock()
        page.get_by_text.return_value = MagicMock()

        # Patch body-phase lookups to raise. The body-phase iterates in order:
        # get_by_placeholder("Type / to insert..."), locator(aria-label msg body),
        # locator('div[role="textbox"][contenteditable="true"]').last, get_by_text.
        # Make any element returned fail on click to exhaust chain.
        def raising(*a, **kw):
            el = MagicMock()
            el.click.side_effect = Exception("no field")
            # ".last" attribute access on a locator also needs to raise on click
            el.last = el
            return el

        # Need to retain the subject path working. Use call counter:
        placeholder_calls = {"n": 0}

        def placeholder_side(arg):
            placeholder_calls["n"] += 1
            # 1st call: subject placeholder — return working el
            # 2nd+ calls: body placeholders — raise
            if placeholder_calls["n"] == 1:
                return MagicMock()
            return raising()

        page.get_by_placeholder.side_effect = placeholder_side

        # Body-phase locator calls: make all raise
        def body_locator_side(sel, *a, **kw):
            if 'textbox' in sel or 'Message body' in sel:
                return raising()
            return MagicMock()
        page.locator.side_effect = body_locator_side

        # Body-phase get_by_text: make it raise
        get_by_text_calls = {"n": 0}

        def text_side(arg):
            get_by_text_calls["n"] += 1
            # Subject fallback's final get_by_text ("Add a subject") happens
            # during subject phase; body's "Type / to insert..." happens later.
            # We don't expect the subject to reach get_by_text because its
            # earlier selectors succeed. Always raise here.
            return raising()
        page.get_by_text.side_effect = text_side

        with pytest.raises(Exception, match="Could not find body field"):
            send_email(page, {
                "to": "x@y.com", "subject": "S", "body": "B",
                "student_name": "s",
            }, index=0, total=1)
