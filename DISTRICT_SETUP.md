# Outlook Email Integration — Implementation Changes

## Overview
Send grade/parent emails from the teacher's school Outlook account by automating Outlook Web with Playwright. Login goes through the district's SSO portal (ClassLink, Clever, etc.). District-agnostic — each district is a JSON config file.

## Files Created

### `backend/districts/__init__.py`
District loader module. Functions: `list_districts()`, `get_district(id)`, `find_district_by_email(email)`. Auto-detects district from teacher's email domain.

### `backend/districts/volusia.json`
Volusia County Schools config. Selectors are TODO until captured via `playwright codegen`.

### `backend/districts/README.md`
Guide for adding new district configs.

### `backend/services/outlook_sender.py`
Standalone Playwright script (~200 lines). Spawned as subprocess by the backend. Reads district config, logs into SSO portal, opens Outlook Web, sends emails one by one. Outputs JSON lines to stdout for progress tracking. Supports `--login-only` and `--test` modes.

## Files Modified

### `requirements.txt`
Added `playwright>=1.40.0`.

### `backend/routes/email_routes.py`
Added 3 endpoints:
- `POST /api/send-outlook-emails` — spawns outlook_sender.py subprocess, reads progress via background thread
- `GET /api/outlook-send/status` — returns current send progress (sent/failed/total/message)
- `POST /api/outlook-login` — opens browser for login verification only

Added imports: `subprocess`, `threading`, `sys`.
Added module-level `_outlook_send_state` dict and `_read_outlook_output()` thread function.

### `frontend/src/services/api.js`
Added 3 API functions: `sendOutlookEmails()`, `getOutlookSendStatus()`, `outlookLogin()`.
Added to default export object.

### `frontend/src/App.jsx`
- Added state: `outlookSendStatus`, `outlookSendPolling`
- Added useEffect for polling `/api/outlook-send/status` every 2s while sending
- Added "Send via Outlook" button in Results tab toolbar (next to existing Parent Emails button)
- Added inline progress bar below toolbar when sending is active
- Updated VPortal credentials description to mention Outlook sending

## Verification Steps
1. `pip install playwright && playwright install chromium`
2. `python -m playwright codegen https://vportal.volusia.k12.fl.us/` — record flow, fill selectors in volusia.json
3. `python backend/services/outlook_sender.py --login-only` — verify login
4. `python backend/services/outlook_sender.py --test teacher@school.edu` — send test email
5. Start Graider → Results tab → "Send via Outlook" → progress bar shows sending
