#!/usr/bin/env python3
"""
Outlook Web email sender via Playwright.
Logs in through district SSO portal, opens Outlook, sends emails.

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
import re

# Add parent dir to path so we can import districts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from districts import find_district_by_email, get_district

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

    portal_url = district["portal_url"]
    sso_type = district.get("sso_type", "classlink")
    selectors = district.get("selectors", {})

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
            "body": "This is a test email from Graider.",
            "student_name": "Test",
        }]

    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

    with sync_playwright() as p:
        # Always visible — user may need to do 2FA
        context = p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            # Step 1: Navigate to district portal
            emit("status", message="Navigating to " + district["name"] + " portal...")
            page.goto(portal_url, wait_until="networkidle", timeout=30000)

            # Step 2: Handle SSO login if needed
            if sso_type == "classlink":
                if "login.classlink.com" in page.url or "launchpad.classlink.com" in page.url:
                    emit("status", message="Logging into ClassLink...")
                    page.fill(selectors["username_field"], email)
                    page.fill(selectors["password_field"], password)
                    page.click(selectors["login_button"])
                    page.wait_for_timeout(3000)

            # Step 3: If on SSO dashboard, click Outlook tile
            if "launchpad.classlink.com" in page.url:
                emit("status", message="Opening Outlook...")
                page.click(selectors["outlook_tile"])

                # Outlook may open in new tab
                page.wait_for_timeout(5000)
                if len(context.pages) > 1:
                    page = context.pages[-1]

            # Step 4: Wait for Outlook to load
            emit("status", message="Waiting for Outlook to load...")
            page.wait_for_url("**/outlook.office365.com/**", timeout=30000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            if login_only:
                emit("done", message="Login successful. Outlook is ready.")
                page.wait_for_timeout(5000)
                context.close()
                return

            # Step 5: Send emails
            total = len(emails)
            sent = 0
            failed = 0

            for i, eml in enumerate(emails):
                student = eml.get("student_name", "")
                try:
                    emit("progress", sent=sent, total=total, current=i + 1,
                         student=student, message="Composing email for " + student + "...")

                    # Click New Mail
                    page.click('[aria-label="New mail"]', timeout=10000)
                    page.wait_for_timeout(1500)

                    # Fill To
                    to_field = page.locator('[aria-label="To"]')
                    to_field.fill(eml["to"])
                    to_field.press("Enter")
                    page.wait_for_timeout(500)

                    # Fill CC if present
                    if eml.get("cc"):
                        try:
                            page.click('button:has-text("Cc")', timeout=3000)
                        except Exception:
                            pass
                        cc_field = page.locator('[aria-label="Cc"]')
                        cc_field.fill(eml["cc"])
                        cc_field.press("Enter")
                        page.wait_for_timeout(500)

                    # Fill Subject
                    page.fill('[aria-label="Add a subject"]', eml["subject"])

                    # Fill Body
                    body_field = page.locator('[aria-label="Message body"]')
                    body_field.click()
                    body_field.fill(eml["body"])
                    page.wait_for_timeout(500)

                    # Click Send
                    page.click('[aria-label="Send"]', timeout=10000)
                    page.wait_for_timeout(2000)

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

        except Exception as e:
            emit("error", message=str(e))
            try:
                page.screenshot(path=ERROR_SCREENSHOT)
            except Exception:
                pass
        finally:
            context.close()


if __name__ == "__main__":
    main()
