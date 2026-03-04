# Behavior Management Feature — Classroom Tracking + Parent Communication

## Overview

Passive classroom behavior tracking integrated into the Assistant tab. The teacher can manually log corrections/praise per student, or enable local Whisper STT to passively detect student names and auto-classify events. All audio processing is local (FERPA-compliant). The assistant can query behavior data, generate parent emails, and send them via Resend or Focus.

---

## Architecture

```
Browser (local)                          Backend (Flask)
┌─────────────────────┐                  ┌──────────────────────────┐
│ BehaviorPanel.jsx   │                  │ behavior_routes.py       │
│  ├─ useBehaviorStore│──POST/GET/DEL──▶│  POST /api/behavior/session │
│  │  (useReducer)    │                  │  GET  /api/behavior/data    │
│  │  + localStorage  │                  │  DEL  /api/behavior/data    │
│  │                  │                  │  GET  /api/behavior/roster  │
│  └─ useBehaviorListener              │                              │
│     ├─ getUserMedia │                  │ assistant_tools_behavior.py │
│     ├─ Whisper Base │                  │  get_behavior_summary       │
│     │  (WASM, local)│                  │  generate_behavior_email    │
│     ├─ Name detect  │                  │  send_behavior_email        │
│     └─ Classify     │                  └──────────────────────────┘
│                     │                           │
│  Audio never leaves │                  ~/.graider_data/
│  the browser        │                  └─ behavior_tracking.json
└─────────────────────┘
```

---

## New Files

### `backend/routes/behavior_routes.py`
REST endpoints for behavior data persistence.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/behavior/session` | POST | Save a completed session (list of events) |
| `/api/behavior/data` | GET | Query cumulative data with filters (student, period, date range) |
| `/api/behavior/data` | DELETE | Clear data for a student or all students |
| `/api/behavior/roster` | GET | Lightweight roster for name matching (reads period CSVs) |

**Session POST body:**
```json
{
  "events": [
    {
      "student_id": "john_smith",
      "student_name": "John Smith",
      "type": "correction",
      "note": "Talking during instruction",
      "timestamp": "09:15",
      "period": "Period 3"
    }
  ],
  "period": "Period 3",
  "date": "2026-02-27"
}
```

Events are merged into cumulative per-student entries grouped by date + period + type.

---

### `backend/services/assistant_tools_behavior.py`
Three assistant tools following the existing submodule pattern (exports `BEHAVIOR_TOOL_DEFINITIONS` + `BEHAVIOR_TOOL_HANDLERS`).

**`get_behavior_summary`**
- Input: `student_name` (optional, fuzzy match), `period` (optional), `days` (1-90, default 7)
- Returns: per-student correction/praise counts, daily breakdown, recent notes
- If no student specified, returns class overview sorted by most corrections

**`generate_behavior_email`**
- Input: `student_name` (required), `tone` (concern/positive/followup, auto-detected), `custom_note`
- Loads behavior data + teacher settings (name, subject, school, signature) + parent contacts
- Returns draft with subject, body, parent email, tone, counts
- Three template tones:
  - **concern**: correction counts, dates, specific notes, partnership language
  - **positive**: praise counts, specific recognitions, encouragement
  - **followup**: mixed data, checking in after prior contact

**`send_behavior_email`**
- Input: `student_name`, `subject`, `body`, `method` (email/focus)
- **email**: Sends via existing `EmailService` (Resend API), looks up parent email from contacts/roster
- **focus**: Returns instructions to create a Playwright automation for Focus portal messaging

---

### `frontend/src/hooks/useBehaviorStore.js`
Session state management via `useReducer`.

**State shape:**
- `sessionActive`, `sessionStartTime`, `period`, `date`
- `pendingEvents` — detected by STT, awaiting teacher approval
- `sessionEvents` — approved events for this session
- `cumulativeData` — loaded from backend
- `viewMode` — "session" or "cumulative"

**Key behaviors:**
- `startSession(period)` — resets events, starts tracking
- `endSession()` — POSTs all approved events to backend, clears localStorage
- `addPending(event)` — STT detection enters pending queue
- `approvePending(id)` — moves from pending to session events
- `increment/decrement(name, id, type)` — quick +/- buttons on tally
- **localStorage backup**: session data auto-saved every 500ms, restored on page load if session was active

---

### `frontend/src/hooks/useBehaviorListener.js`
Local Whisper STT for passive classroom listening.

**Model loading:**
- Lazy-loads `onnx-community/whisper-base` via `@huggingface/transformers` on first Listen click
- Uses WASM backend with q8 quantization (~150MB, cached in browser IndexedDB after first download)
- Progress callback updates a loading bar in the UI

**Audio pipeline:**
1. `getUserMedia` with mono 16kHz, echo cancellation + noise suppression
2. `ScriptProcessor` buffers audio frames
3. Every 3 seconds, concatenates buffer into Float32Array
4. RMS silence check (skip if < 0.01)
5. Whisper transcription with `language: 'en'`, `chunk_length_s: 5`

**Name detection:**
- Builds regex word-boundary matchers from roster (first name, last name, full name)
- Skips names shorter than 3 characters to reduce false positives
- Deduplicates — each student matched at most once per chunk

**Classification:**
- Correction patterns: stop, sit down, focus, please quiet/listen, warning, in your seat, etc.
- Praise patterns: good job, great work, excellent, thank you, well done, etc.
- Defaults to "correction" when ambiguous
- Teacher always reviews in pending queue before counting

**Safety:**
- Pauses detection when `voiceModeActive` is true (avoids false positives from teacher-assistant voice conversation)
- All audio processed locally, no recordings stored, no data transmitted
- Resources cleaned up on unmount (mic stream, audio context, intervals)

---

### `frontend/src/components/BehaviorPanel.jsx`
Collapsible sidebar UI attached to the Assistant tab.

**Layout:**
- Collapsed: small icon tab on the right edge with green dot when session is active
- Expanded: 320px sidebar with header, controls, pending events, tally table

**Sections:**

1. **Header** — "Behavior" title, LIVE badge when session active, collapse button

2. **Session controls** — period input + Start button (when idle), or Listen/Add/End buttons (when active)
   - Listen: toggles Whisper STT with model loading progress bar
   - Add: opens manual add form
   - End: saves session to backend

3. **Model loading** — progress bar when Whisper is downloading

4. **FERPA disclaimer** — "Audio processed locally. No recordings stored or transmitted."

5. **Manual add form** — student name autocomplete from roster, correction/praise toggle, optional note, Add button

6. **Pending events** (from STT) — cards showing student name, auto-classified type, transcript snippet, Approve/Switch/Dismiss buttons

7. **View toggle** — session vs cumulative

8. **Tally table** — per-student rows with correction count (red +/-) and praise count (green +/-), sorted by most corrections

9. **Last transcript** — shows what Whisper last heard (when listening)

---

## Modified Files

### `backend/routes/__init__.py`
- Added `from .behavior_routes import behavior_bp`
- Added `app.register_blueprint(behavior_bp)` in `register_routes()`
- Added `'behavior_bp'` to `__all__`

### `backend/services/assistant_tools.py`
- Added to `_merge_submodules()`:
  ```python
  ("backend.services.assistant_tools_behavior", "BEHAVIOR_TOOL_DEFINITIONS", "BEHAVIOR_TOOL_HANDLERS"),
  ```

### `backend/routes/assistant_routes.py`
- Added behavior tool descriptions to `_build_system_prompt()` after the existing tool list:
  - `get_behavior_summary` — query behavior data
  - `generate_behavior_email` — draft parent emails
  - `send_behavior_email` — send via Resend or Focus

### `frontend/src/App.jsx`
- Imported `BehaviorPanel` component
- Wrapped Assistant tab content in a flex container:
  - Left: `AssistantChat` (flex: 1)
  - Right: `BehaviorPanel` (320px sidebar, collapsible)

### `frontend/package.json`
- Added `"@huggingface/transformers": "^3.4.0"` to dependencies

---

## Data Schema

```json
// ~/.graider_data/behavior_tracking.json
{
  "version": 1,
  "students": {
    "john_smith": {
      "name": "John Smith",
      "entries": [
        {
          "date": "2026-02-27",
          "period": "Period 3",
          "type": "correction",
          "count": 3,
          "notes": ["Talking during instruction", "Off task twice"],
          "timestamps": ["09:15", "09:23", "09:41"]
        },
        {
          "date": "2026-02-27",
          "period": "Period 3",
          "type": "praise",
          "count": 1,
          "notes": ["Good participation"],
          "timestamps": ["09:50"]
        }
      ]
    }
  }
}
```

---

## Classification Patterns

### Corrections
`stop`, `sit down`, `focus`, `please quiet/listen/stop`, `I need you to`, `don't`, `pay attention`, `hands to yourself`, `that's enough`, `warning`, `in your seat`, `turn around`, `put away`, `no talking/phones`

### Praise
`good job`, `great work`, `excellent`, `thank you`, `well done`, `awesome`, `nice work`, `perfect`, `I'm proud`, `way to go`, `keep it up`, `good thinking/listening/behavior`

Default: correction (when ambiguous). Teacher always reviews before counting.

---

## FERPA Compliance

- Whisper runs entirely in-browser via WASM (no server calls for audio)
- No audio recordings are stored anywhere
- No audio data is transmitted over the network
- Only student names + event counts are persisted (in local JSON file)
- UI displays a shield icon disclaimer when listening is active

---

## Verification Checklist

- [ ] Build passes: `cd frontend && npm run build`
- [ ] App starts without errors: `python backend/app.py`
- [ ] Assistant tab shows BehaviorPanel collapsed on right edge
- [ ] Click panel icon to expand, enter period, click Start Session
- [ ] Manual add: type student name, see autocomplete from roster, add correction/praise
- [ ] Tally table shows student with +/- buttons for corrections and praise
- [ ] End session saves to backend (check `~/.graider_data/behavior_tracking.json`)
- [ ] Switch to cumulative view shows saved data
- [ ] Listen button loads Whisper model (first time: ~150MB download with progress bar)
- [ ] Speaking a student name creates pending event with transcript
- [ ] Approve/Switch/Dismiss buttons work on pending events
- [ ] Ask assistant "How has [student] behaved this week?" returns data
- [ ] Ask assistant "Write a behavior email for [student]'s parents" generates draft
- [ ] FERPA disclaimer visible when listening
