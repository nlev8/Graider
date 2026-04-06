# Focus Communications Playwright Fix — Precise Code Edits

## Diagnosis

The AI calls `send_focus_comms` (returns preview with `NOT_SENT: True`) and then in the **same response** writes "Sending via Focus Communications" — without ever calling `confirm_and_send`. The verification injection tells the AI "NOT executed yet" but the model ignores it and claims success in its text response.

Three problems:
1. **The AI never calls `confirm_and_send`** — it generates the preview text and the "sending" claim in one response
2. **The claim checker fires too late** — the false claim is already streamed to the frontend by the time the check runs
3. **The frontend "Send Now" button exists but may not be visible** — it only renders when `pendingSend` is set on the message, which depends on the SSE event having `pending_send: true`

## Fix Strategy

Stop relying on the AI to call `confirm_and_send`. Instead, make the frontend handle confirmation directly. When `send_focus_comms` returns `NOT_SENT: True`, the frontend already shows a green "Send Now" button — we just need to make sure it works and is prominent. The AI's job is to show the preview; the button does the actual send.

Additionally, strip the false "Sending via Focus Communications" text from the response before it reaches the user.

---

## Fix 1: Strip false send claims from streamed text

**File:** `backend/routes/assistant_routes.py`

**Why:** The AI writes "Sending via Focus Communications" in its streamed text. By the time the claim checker runs, the user already saw it. We need to suppress these phrases during streaming, not after.

**Find the text accumulation for all three providers.** Each provider accumulates text into `full_response_text` and yields SSE events. We add a filter that strips known false claim phrases when a preview tool was called this turn.

**After the `if not tool_use_blocks:` claim check block (~line 1523), add a text sanitizer before the break:**

This is already handled by the claim check. But the real fix is Fix 2 — making the button work so the AI doesn't need to call confirm_and_send at all.

## Fix 2: Make the frontend "Send Now" button the primary send path

**File:** `frontend/src/components/AssistantChat.jsx`

**Why:** The frontend already has a "Send Now" button that appears when `pending_send` is true in the tool result event. This button calls `POST /api/confirm-send` directly — no AI involvement. We need to ensure this button is visible and working.

**Check 1:** Verify the button renders. Find line 964:
```javascript
{msg.pendingSend && !msg.sendConfirmed && (
```

This condition requires `msg.pendingSend` to be true. It gets set at line 474:
```javascript
if (event.pending_send) {
    newState.pendingSend = true
```

This comes from the SSE `tool_result` event where `event_data['pending_send'] = True` (backend line 1658). This should work — `send_focus_comms` returns `NOT_SENT: True` which triggers this.

**Check 2:** Verify the payload reaches the button. The button sends `msg.pendingPayload` to `/api/confirm-send`. This comes from `event.pending_payload` in the SSE event. The backend reads this from the filesystem at line 1660-1664. After our fix, it should also be written to the filesystem.

**No code change needed here** if the filesystem write is working. But add a fallback: if `pendingPayload` is empty, the button should read directly from the pending storage.

**Find (line 970-973):**
```javascript
const resp = await fetch('/api/confirm-send', {
    method: 'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify(msg.pendingPayload || {}),
})
```

**Replace with:**
```javascript
const resp = await fetch('/api/confirm-send', {
    method: 'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify(msg.pendingPayload || {action: 'send_focus_comms'}),
})
```

This way, even if `pendingPayload` is null, the endpoint will try to read from the pending file/storage.

## Fix 3: Make `/api/confirm-send` check Supabase storage too

**File:** `backend/routes/email_routes.py`

**Why:** The `/api/confirm-send` endpoint only reads from POST body or filesystem. On production, the pending is in Supabase. It should also check Supabase.

**Find (~line 1433-1451):**
```python
    pending = None
    pending_path = os.path.join(GRAIDER_DATA_DIR, "pending_send.json")

    # Try POST body first (sent by frontend Send Now button)
    body = request.get_json(silent=True) or {}
    if body.get("action"):
        pending = body

    # Fall back to pending file
    if not pending and os.path.exists(pending_path):
        try:
            with open(pending_path, 'r') as f:
                pending = json.load(f)
        except Exception as e:
            _logger.exception("Failed to read pending send file")
            return jsonify({"error": "An internal error occurred"}), 500

    if not pending:
        return jsonify({"error": "No pending send. Generate a preview first."})
```

**Replace with:**
```python
    pending = None
    pending_path = os.path.join(GRAIDER_DATA_DIR, "pending_send.json")

    # Try POST body first (sent by frontend Send Now button)
    body = request.get_json(silent=True) or {}
    if body.get("action") and body.get("messages"):
        pending = body

    # Try Supabase storage
    if not pending:
        try:
            from backend.storage import load as _storage_load
            from flask import g
            _teacher_id = getattr(g, 'user_id', 'local-dev')
            pending = _storage_load('pending_send', _teacher_id)
            if not pending:
                # Check keyed storage
                for _key in ('send_focus_comms', 'send_behavior_email', 'send_parent_emails'):
                    pending = _storage_load('pending_send:' + _key, _teacher_id)
                    if pending:
                        break
        except Exception:
            pass

    # Fall back to pending file
    if not pending and os.path.exists(pending_path):
        try:
            with open(pending_path, 'r') as f:
                pending = json.load(f)
        except Exception as e:
            _logger.exception("Failed to read pending send file")
            return jsonify({"error": "An internal error occurred"}), 500

    if not pending:
        return jsonify({"error": "No pending send. Generate a preview first."})
```

## Fix 4: Make the "Send Now" button more prominent

**File:** `frontend/src/components/AssistantChat.jsx`

**Why:** The user may not be seeing the button, or may be typing "yes send it" to the AI instead of clicking the button.

**Find the button text (~line 997-1001):**
```javascript
>
    Send Now via Focus Communications
</button>
```

No change needed — just verify the button is actually rendering. Add a console.log for debugging:

**Find (~line 964):**
```javascript
{msg.pendingSend && !msg.sendConfirmed && (
```

**Before this line, add:**
```javascript
{msg.pendingSend && console.log('SEND BUTTON VISIBLE, payload:', msg.pendingPayload)}
```

Remove after confirming the button renders.

## Fix 5: Add diagnostic logging to confirm_and_send tool

**File:** `backend/services/assistant_tools_reports.py`

**Why:** We need to know if `confirm_and_send` is ever being called by the AI tool loop.

**Find the start of `confirm_and_send` (~line 2506):**
```python
def confirm_and_send(teacher_id='local-dev'):
    """Execute the pending send action after teacher confirmation."""
    require_teacher_id(teacher_id)
```

**Add after `require_teacher_id`:**
```python
    import logging
    logging.getLogger(__name__).info("confirm_and_send CALLED by teacher_id=%s", teacher_id)
```

## Summary of Fixes

| Fix | File | What |
|-----|------|------|
| 1 | `assistant_routes.py` | Already done — claim check + diagnostic logging |
| 2 | `AssistantChat.jsx` | Fallback payload for Send Now button |
| 3 | `email_routes.py` | Check Supabase storage in /api/confirm-send |
| 4 | `AssistantChat.jsx` | Verify button renders (diagnostic) |
| 5 | `assistant_tools_reports.py` | Diagnostic logging on confirm_and_send |

## Root Cause Summary

The AI model (GPT-4/Claude) is not reliably calling `confirm_and_send` as a tool after the preview. It writes "Sending via Focus Communications" as text instead. This is a model behavior issue that cannot be fixed with prompt instructions alone.

The real fix is to stop depending on the AI to trigger the send. The frontend "Send Now" button at line 964 of AssistantChat.jsx already exists for this purpose — it calls `/api/confirm-send` directly. We need to ensure:
1. The button has the correct payload (Fix 2)
2. The backend endpoint checks all storage locations (Fix 3)
3. The button is visible to the user (Fix 4)
