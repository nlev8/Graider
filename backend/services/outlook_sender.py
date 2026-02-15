#!/usr/bin/env python3
"""
Outlook Web email sender via Playwright.
Logs in through district SSO portal, opens Outlook, sends emails.

Flow (Volusia): VPortal -> "Click to Login" -> ADFS login -> ClassLink dashboard
                -> Microsoft 365 tile -> Office 365 Apps -> Outlook -> Send

Usage:
  python outlook_sender.py emails.json          # Send batch
  python outlook_sender.py --login-only         # Just log in and verify
  python outlook_sender.py --test recipient@x   # Send one test email

Input JSON format:
  { "emails": [{ "to": "...", "cc": "...", "subject": "...", "body": "...", "student_name": "..." }] }

Output: JSON lines to stdout for progress reporting.
"""
import os
import sys
import json
import base64
import time

# Add parent dir to path so we can import districts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from districts import find_district_by_email

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
BROWSER_DATA_DIR = os.path.join(GRAIDER_DATA_DIR, "outlook_browser")
CREDS_FILE = os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")
ERROR_SCREENSHOT = os.path.join(GRAIDER_DATA_DIR, "outlook_error.png")


def emit(event_type, **kwargs):
    """Print a JSON line to stdout for the backend to read."""
    print(json.dumps({"type": event_type, **kwargs}), flush=True)


def load_credentials():
    """Load VPortal credentials from existing config."""
    if not os.path.exists(CREDS_FILE):
        return None, None
    with open(CREDS_FILE, 'r') as f:
        data = json.load(f)
    email = data.get("email", "")
    password = base64.b64decode(data.get("password", "")).decode()
    return email, password


def wait_for_new_tab(context, old_count, timeout=15000):
    """Wait for a new tab to open and return it."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if len(context.pages) > old_count:
            new_page = context.pages[-1]
            new_page.wait_for_load_state("domcontentloaded")
            return new_page
        time.sleep(0.3)
    return None


def navigate_to_outlook(page, context, district, email, password):
    """Navigate through SSO portal to reach Outlook. Returns the Outlook page."""
    selectors = district.get("selectors", {})
    portal_url = district["portal_url"]

    # Step 1: Navigate to district portal
    emit("status", message="Opening " + district["name"] + " portal...")
    page.goto(portal_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Step 2: Click "Click to Login" on VPortal landing (if present)
    portal_btn = selectors.get("portal_login_button", "")
    if portal_btn:
        try:
            page.click(portal_btn, timeout=5000)
            emit("status", message="Clicked portal login, waiting for ADFS...")
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(2000)
        except Exception:
            pass  # May already be past this step (cached session)

    # Step 3: ADFS login (if we landed on the ADFS form)
    current_url = page.url.lower()
    if "adfs" in current_url or "login" in current_url:
        try:
            username_sel = selectors.get("username_field", "#userNameInput")
            password_sel = selectors.get("password_field", "#passwordInput")
            login_sel = selectors.get("login_button", "#submitButton")

            page.fill(username_sel, email, timeout=5000)
            page.fill(password_sel, password, timeout=5000)
            emit("status", message="Signing in to ADFS...")
            page.click(login_sel)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(3000)
        except Exception:
            pass  # May already be authenticated (persistent session)

    # Step 4: Skip M365 tile — go straight to Outlook
    # SSO cookies are set from ADFS login, so direct nav works
    if "classlink.com" in page.url or "myapps" in page.url:
        emit("status", message="SSO authenticated, going to Outlook...")
        page.goto(
            "https://outlook.office365.com/mail/",
            wait_until="domcontentloaded", timeout=30000
        )
        page.wait_for_timeout(3000)

    # Step 6: Handle Microsoft login/2FA if prompted
    if "login.microsoftonline.com" in page.url or "login.microsoft.com" in page.url:
        emit("status", message="Microsoft login detected — complete 2FA in the browser...")
        # Wait up to 2 minutes for user to complete 2FA
        try:
            page.wait_for_url(
                lambda url: "login.microsoftonline.com" not in url and "login.microsoft.com" not in url,
                timeout=120000
            )
            emit("status", message="2FA complete, continuing...")
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(3000)
        except Exception:
            raise Exception("2FA timeout — did not complete within 2 minutes. Current URL: " + page.url)

    # If we landed on Office 365 after 2FA (not directly on Outlook), go directly
    current_url = page.url.lower()
    if ("office.com" in current_url or "microsoft365.com" in current_url or "m365.cloud.microsoft" in current_url) and "outlook" not in current_url:
        emit("status", message="On Office 365 after 2FA, navigating directly to Outlook...")
        page.goto("https://outlook.office365.com/mail/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

    # Step 7: Wait for Outlook to fully load
    emit("status", message="Waiting for Outlook to load...")
    try:
        page.wait_for_url(
            lambda u: "outlook" in u.lower(),
            timeout=30000
        )
    except Exception:
        emit("status", message="URL check: " + page.url[:80])
        if "outlook" not in page.url.lower():
            raise Exception(
                "Failed to reach Outlook. URL: " + page.url
            )

    # Wait for Outlook UI to be interactive (New mail button)
    try:
        page.get_by_role("button", name="New mail").wait_for(
            state="visible", timeout=30000
        )
    except Exception:
        pass  # Continue anyway — UI might use different labels
    page.wait_for_timeout(2000)

    return page


def send_email(page, eml, index, total):
    """Compose and send a single email in Outlook Web."""
    student = eml.get("student_name", "")
    emit("progress", sent=index, total=total, current=index + 1,
         student=student, message="Composing email for " + student + "...")

    # Click New Mail
    page.get_by_role("button", name="New mail").click(timeout=10000)
    page.wait_for_timeout(2000)

    # Fill To — click the To input, type address, press Tab to resolve it
    page.locator('[aria-label="To"]').last.click()
    page.keyboard.type(eml["to"])
    page.wait_for_timeout(1000)
    page.keyboard.press("Tab")
    page.wait_for_timeout(1000)

    # Fill CC if present
    if eml.get("cc"):
        page.locator('[aria-label="Cc"]').last.click()
        page.keyboard.type(eml["cc"])
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

    # Fill Subject — try placeholder first, then text, then aria-label
    subject_filled = False
    for selector in [
        lambda: page.get_by_placeholder("Add a subject"),
        lambda: page.locator('input[placeholder="Add a subject"]'),
        lambda: page.locator('[aria-label="Add a subject"]'),
        lambda: page.get_by_text("Add a subject"),
    ]:
        try:
            el = selector()
            el.click(timeout=5000)
            page.keyboard.type(eml["subject"])
            subject_filled = True
            break
        except Exception:
            continue
    if not subject_filled:
        raise Exception("Could not find subject field")
    page.wait_for_timeout(300)

    # Fill Body — click body area, move cursor to top (above signature), then type
    body_filled = False
    for selector in [
        lambda: page.get_by_placeholder("Type / to insert files and more"),
        lambda: page.locator('[aria-label="Message body, press Alt+F10 to exit"]'),
        lambda: page.locator('div[role="textbox"][contenteditable="true"]').last,
        lambda: page.get_by_text("Type / to insert files and more"),
    ]:
        try:
            el = selector()
            el.click(timeout=5000)
            # Move cursor to the very top of body (above signature)
            page.keyboard.press("Meta+ArrowUp")
            page.wait_for_timeout(200)
            page.keyboard.type(eml["body"])
            body_filled = True
            break
        except Exception:
            continue
    if not body_filled:
        raise Exception("Could not find body field")
    page.wait_for_timeout(500)

    # Screenshot before send for debugging
    pre_send_screenshot = os.path.join(GRAIDER_DATA_DIR, "outlook_pre_send.png")
    page.screenshot(path=pre_send_screenshot)
    emit("status", message="Pre-send screenshot saved to " + pre_send_screenshot)

    # Send via keyboard shortcut (Command+Enter on macOS)
    page.keyboard.press("Meta+Enter")
    page.wait_for_timeout(3000)


def main():
    from playwright.sync_api import sync_playwright

    args = sys.argv[1:]
    login_only = "--login-only" in args
    test_mode = "--test" in args

    # Load credentials
    email, password = load_credentials()
    if not email or not password:
        emit("error", message="No portal credentials configured. Go to Settings > Tools.")
        sys.exit(1)

    # Auto-detect district from email domain
    district = find_district_by_email(email)
    if not district:
        emit("error", message="No district config found for " + email + ". Contact support.")
        sys.exit(1)

    # Load emails to send (unless login-only)
    emails = []
    if not login_only and not test_mode:
        json_file = None
        for a in args:
            if not a.startswith("--"):
                json_file = a
                break
        if not json_file or not os.path.exists(json_file):
            emit("error", message="No email JSON file provided")
            sys.exit(1)
        with open(json_file, 'r') as f:
            data = json.load(f)
        emails = data.get("emails", [])
        if not emails:
            emit("error", message="No emails in JSON file")
            sys.exit(1)

    if test_mode:
        test_idx = args.index("--test")
        test_recipient = args[test_idx + 1] if len(args) > test_idx + 1 else email
        emails = [{
            "to": test_recipient,
            "cc": "",
            "subject": "Graider Test Email",
            "body": "This is a test email from Graider.\n\nIf you received this, Outlook sending is working.",
            "student_name": "Test",
        }]

    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

    with sync_playwright() as p:
        # Persistent context preserves login sessions between runs
        context = p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            # Navigate through SSO to Outlook
            page = navigate_to_outlook(page, context, district, email, password)

            if login_only:
                emit("done", message="Login successful. Outlook is ready. Staying open 5 min.")
                page.wait_for_timeout(300000)
                context.close()
                return

            # Send emails
            total = len(emails)
            sent = 0
            failed = 0

            for i, eml in enumerate(emails):
                student = eml.get("student_name", "")
                try:
                    send_email(page, eml, sent, total)
                    sent += 1
                    emit("progress", sent=sent, total=total, current=i + 1,
                         student=student, message="Sent to " + student)
                except Exception as e:
                    failed += 1
                    emit("error", message="Failed for " + student + ": " + str(e))
                    try:
                        page.screenshot(path=ERROR_SCREENSHOT)
                    except Exception:
                        pass
                    # Try to dismiss any open compose window
                    try:
                        page.click('[aria-label="Discard"]', timeout=3000)
                    except Exception:
                        pass

                # Brief delay between emails
                if i < total - 1:
                    time.sleep(1.5)

            emit("done", sent=sent, failed=failed, total=total)

            # In test mode, keep browser open so user can verify
            if test_mode:
                emit("status", message="Browser staying open 60s to verify...")
                page.wait_for_timeout(60000)

        except Exception as e:
            emit("error", message=str(e))
            try:
                page.screenshot(path=ERROR_SCREENSHOT)
            except Exception:
                pass
            # Keep browser open on error so user can inspect
            if test_mode or login_only:
                page.wait_for_timeout(60000)
        finally:
            context.close()


if __name__ == "__main__":
    main()
