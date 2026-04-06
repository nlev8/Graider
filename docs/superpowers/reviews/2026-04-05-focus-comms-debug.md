# Focus Communications Not Triggering — Debug Report

## Symptom

When teacher confirms "yes send it" after seeing a Focus Communications preview, the Playwright browser automation never opens. The AI says "Sending via Focus Communications" but nothing happens.

## Root Cause

Two issues found:

### Issue 1: Frontend "Send Now" button has no payload on production

The SSE event builder in `assistant_routes.py` (lines 1660-1664) reads the pending payload from the **filesystem** (`~/.graider_data/pending_send.json`) to attach to the SSE event:

```python
if result.get('NOT_SENT'):
    event_data['pending_send'] = True
    pending_path = os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json")
    try:
        if os.path.exists(pending_path):
            with open(pending_path, 'r') as _pf:
                event_data['pending_payload'] = json.load(_pf)
    except Exception:
        pass
```

But on production (Railway), `send_focus_comms` saves the pending payload to **Supabase** via `storage_save('pending_send', ...)` at line 2472. The filesystem fallback at line 2474-2477 only runs when `storage_save` is falsy. On production, `storage_save` is available, so the file is never written.

Result: `pending_payload` is never set in the SSE event → frontend's "Send Now" button renders but has an empty/null payload → clicking it sends `{}` to `/api/confirm-send` → "No pending send" error.

### Issue 2: AI writes "Sending via Focus Communications" as text instead of calling confirm_and_send

Even with the same-turn blocking fix, the AI still writes the text "Sending via Focus Communications" in its response without making a tool call. The post-response claim check catches "has been sent" but "Sending via Focus Communications" doesn't match any claim phrase in the registry.

## Proposed Fixes

### Fix 1: Read pending payload from storage, not filesystem (assistant_routes.py:1657-1666)

**File:** `backend/routes/assistant_routes.py`

**Find (lines 1657-1666):**
```python
                        if result.get('NOT_SENT'):
                            event_data['pending_send'] = True
                            # Include payload so frontend can send directly
                            pending_path = os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json")
                            try:
                                if os.path.exists(pending_path):
                                    with open(pending_path, 'r') as _pf:
                                        event_data['pending_payload'] = json.load(_pf)
                            except Exception:
                                pass
```

**Replace with:**
```python
                        if result.get('NOT_SENT'):
                            event_data['pending_send'] = True
                            # Include the tool result directly as the pending payload
                            # (it already contains the action + messages/data)
                            # Previously read from filesystem which doesn't exist on Railway
                            if isinstance(result, dict) and result.get('action'):
                                event_data['pending_payload'] = result
                            else:
                                # For tools that don't include action in result,
                                # try storage first, then filesystem fallback
                                try:
                                    from backend.storage import load as _storage_load
                                    _pending = _storage_load('pending_send', teacher_id)
                                    if _pending:
                                        event_data['pending_payload'] = _pending
                                except Exception:
                                    pass
                                if 'pending_payload' not in event_data:
                                    pending_path = os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json")
                                    try:
                                        if os.path.exists(pending_path):
                                            with open(pending_path, 'r') as _pf:
                                                event_data['pending_payload'] = json.load(_pf)
                                    except Exception:
                                        pass
```

### Fix 2: Also write pending to filesystem on production (assistant_tools_reports.py:2471-2477)

Simpler alternative to Fix 1: always write to both Supabase AND filesystem.

**File:** `backend/services/assistant_tools_reports.py`

**Find (lines 2471-2477):**
```python
        if storage_save:
            storage_save('pending_send', {"action": "send_focus_comms", "messages": messages}, teacher_id)
        else:
            pending_path = os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json")
            os.makedirs(os.path.dirname(pending_path), exist_ok=True)
            with open(pending_path, 'w') as pf:
                json.dump({"action": "send_focus_comms", "messages": messages}, pf)
```

**Replace with:**
```python
        pending_data = {"action": "send_focus_comms", "messages": messages}
        if storage_save:
            storage_save('pending_send', pending_data, teacher_id)
        # Always write filesystem fallback (needed by SSE event builder)
        pending_path = os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json")
        os.makedirs(os.path.dirname(pending_path), exist_ok=True)
        try:
            with open(pending_path, 'w') as pf:
                json.dump(pending_data, pf)
        except Exception:
            pass
```

**Recommendation:** Apply Fix 2 — it's simpler and fixes the problem at the source. The `send_focus_comms` tool should always write the filesystem file since the SSE builder reads from it. Apply the same pattern to `send_parent_emails` (lines 2329-2334) and `send_behavior_email` in `assistant_tools_behavior.py`.

### Fix 3: Add "Sending" to claim phrases (assistant_tool_guards.py)

**File:** `backend/services/assistant_tool_guards.py`

In the `confirm_and_send` entry's `claim_phrases` list, add:
```python
"sending via", "sending to",
```

This catches the AI writing "Sending via Focus Communications" without calling the tool.
