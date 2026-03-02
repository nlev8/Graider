# Graider Companion iOS App — Phase 1 Implementation Plan

## Goal
Build a native SwiftUI iPhone app for teachers to track student behavior (corrections/praise) using on-device Whisper speech recognition, with real-time sync to the Graider web app via Supabase.

---

## Architecture Overview

```
┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│  iPhone App      │◄─────►│  Supabase        │◄─────►│  Graider Web    │
│  (SwiftUI)       │  RT   │  (Postgres + RT)  │  RT   │  (React + Flask)│
│                  │       │                  │       │                  │
│  - WhisperKit    │       │  behavior_sessions│      │  BehaviorPanel   │
│  - CoreML        │       │  behavior_events  │      │  useBehaviorStore│
│  - SwiftData     │       │  students (exist) │      │                  │
│  - ActivityKit   │       │  classes (exist)   │      │                  │
└─────────────────┘       └──────────────────┘       └─────────────────┘
```

**Key decision:** Both web and iOS write to the same Supabase tables. The web app's current local JSON storage (`~/.graider_data/behavior_tracking.json`) gets migrated to Supabase. Both platforms see the same data in real-time.

---

## Phase 1 Scope (Core Loop)

### What's IN Phase 1:
1. Teacher login (Supabase Auth — same account as web)
2. Class/period selection from existing roster
3. Session management (start/end tracking session)
4. On-device Whisper speech recognition (WhisperKit for iOS)
5. Student name detection from roster
6. Correction/praise classification from speech
7. Manual tally (tap to add correction/praise)
8. Pending event review (approve/dismiss/switch STT detections)
9. Live session dashboard (per-student tallies)
10. Supabase sync (real-time, both directions)
11. Offline support with SwiftData (sync when reconnected)
12. Live Activity / Dynamic Island (session status)

### What's in Phase 2+ (NOT this plan):
- Apple Watch companion
- Siri Shortcuts
- NFC desk tags
- Seating chart / heat map
- AirPods spatial audio cues
- Auto-start via geofence
- Co-tracking (multi-teacher sessions)
- Weekly digest push notifications
- Parent email generation from app

---

## Step 1: Supabase Schema — New Behavior Tables

Add two new tables that both the web and iOS app will use.

### Table: `behavior_sessions`
```sql
CREATE TABLE behavior_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    class_id UUID REFERENCES classes(id),
    period TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    device TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(teacher_id, date, period, started_at)
);

-- Indexes for common queries
CREATE INDEX idx_sessions_teacher_active ON behavior_sessions(teacher_id, is_active);
CREATE INDEX idx_sessions_teacher_date ON behavior_sessions(teacher_id, date);

ALTER TABLE behavior_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Teachers manage own sessions"
    ON behavior_sessions FOR ALL
    USING (auth.uid() = teacher_id)
    WITH CHECK (auth.uid() = teacher_id);
```

### Table: `behavior_events`
```sql
CREATE TABLE behavior_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES behavior_sessions(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL,
    student_id UUID REFERENCES students(id),
    student_name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('correction', 'praise')),
    note TEXT,
    transcript TEXT,
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'stt', 'watch')),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ,
    client_id UUID,  -- client-generated UUID for dedup (see Sync Model)

    -- Enforce session ownership: events can only reference sessions owned by the same teacher.
    -- Composite FK ensures a compromised client can't insert events into another teacher's session.
    FOREIGN KEY (session_id, teacher_id)
        REFERENCES behavior_sessions(id, teacher_id) ON DELETE CASCADE,

    -- Prevent duplicate uploads from offline retry
    UNIQUE(client_id)
);

-- Composite unique on sessions for the FK target
ALTER TABLE behavior_sessions ADD UNIQUE (id, teacher_id);

-- Indexes for common queries
CREATE INDEX idx_events_session ON behavior_events(session_id);
CREATE INDEX idx_events_student ON behavior_events(student_id);
CREATE INDEX idx_events_teacher_session_time ON behavior_events(teacher_id, session_id, event_time);
CREATE INDEX idx_events_teacher_date ON behavior_events(teacher_id, event_time);

ALTER TABLE behavior_events ENABLE ROW LEVEL SECURITY;

-- RLS checks both direct ownership AND session ownership via the composite FK
CREATE POLICY "Teachers manage own events"
    ON behavior_events FOR ALL
    USING (auth.uid() = teacher_id)
    WITH CHECK (auth.uid() = teacher_id);

-- Enable real-time
ALTER PUBLICATION supabase_realtime ADD TABLE behavior_sessions;
ALTER PUBLICATION supabase_realtime ADD TABLE behavior_events;
```

### Security Notes
- The composite FK `(session_id, teacher_id) → behavior_sessions(id, teacher_id)` prevents cross-account data leakage. Even if a compromised client fabricates `teacher_id`, the FK check ensures the session must also belong to that teacher.
- RLS on both tables restricts reads and writes to `auth.uid() = teacher_id`.
- The `client_id` unique constraint prevents duplicate event uploads during offline retry (see Sync Model below).

---

## Step 2: Xcode Project Setup

### 2a. Project structure
```
GraiderCompanion/
├── GraiderCompanion.xcodeproj
├── GraiderCompanion/
│   ├── App/
│   │   ├── GraiderCompanionApp.swift
│   │   └── AppState.swift
│   ├── Models/
│   │   ├── BehaviorSession.swift
│   │   ├── BehaviorEvent.swift
│   │   ├── Student.swift
│   │   └── ClassPeriod.swift
│   ├── Services/
│   │   ├── SupabaseManager.swift
│   │   ├── AuthService.swift
│   │   ├── SyncService.swift
│   │   └── WhisperService.swift
│   ├── Views/
│   │   ├── LoginView.swift
│   │   ├── HomeView.swift
│   │   ├── SessionView.swift
│   │   ├── PendingEventsView.swift
│   │   ├── StudentTallyRow.swift
│   │   └── SessionSummaryView.swift
│   ├── LiveActivity/
│   │   ├── BehaviorActivityAttributes.swift
│   │   └── BehaviorLiveActivity.swift
│   └── Resources/
│       └── Assets.xcassets
├── GraiderCompanionWidget/
│   └── GraiderCompanionWidgetBundle.swift
└── Packages/
```

### 2b. Dependencies (Swift Package Manager)
- **supabase-swift** (2.0+) — Auth, Database, Realtime
- **WhisperKit** (0.9+) — On-device Whisper via CoreML (Apple Neural Engine optimized)

### 2c. Capabilities
- Background Modes → Audio (Whisper listening with screen off)
- Push Notifications (future)
- App Groups (Live Activity widget data sharing)

---

## Step 3: Authentication

Same Supabase project as web. Teacher logs in with existing email/password.

```swift
class AuthService: ObservableObject {
    @Published var isAuthenticated = false
    @Published var userId: UUID?

    func signIn(email: String, password: String) async throws
    func signOut() async
    func restoreSession() async  // On app launch — check Keychain
}
```

**Flow:** Launch → check Keychain → valid session → HomeView, else → LoginView

---

## Step 4: Data Layer (SwiftData + Supabase Sync)

### 4a. Local models (SwiftData for offline)

```swift
@Model class LocalSession {
    var id: UUID              // client-generated, becomes client_id in Supabase
    var remoteId: UUID?       // Supabase-assigned UUID (nil until synced)
    var classId: UUID?
    var period: String
    var date: Date
    var startedAt: Date
    var endedAt: Date?
    var isActive: Bool
    var syncStatus: SyncStatus  // .pending | .syncing | .synced | .failed
    var lastSyncAttempt: Date?
    var syncError: String?
    @Relationship(deleteRule: .cascade) var events: [LocalEvent]
}

@Model class LocalEvent {
    var id: UUID              // client-generated, sent as client_id to Supabase
    var remoteId: UUID?       // Supabase-assigned UUID (nil until synced)
    var studentId: UUID?
    var studentName: String
    var type: String          // "correction" | "praise"
    var note: String?
    var transcript: String?
    var source: String        // "manual" | "stt"
    var eventTime: Date
    var syncStatus: SyncStatus
    var session: LocalSession?
}

enum SyncStatus: String, Codable {
    case pending   // not yet attempted
    case syncing   // upload in progress
    case synced    // confirmed in Supabase
    case failed    // last attempt failed (will retry)
}
```

### 4b. Sync model

**Local → Remote mapping:**
- Every local object gets a client-generated `id` (UUID) at creation time
- This `id` is sent as `client_id` in the Supabase INSERT
- Supabase returns a server-generated `id` — stored as `remoteId` locally
- The `UNIQUE(client_id)` constraint on the server prevents duplicate uploads
- Both `id` (local) and `remoteId` (remote) are persisted in SwiftData

**Write flow:**
1. Create LocalEvent in SwiftData with `syncStatus = .pending` (instant, UI updates)
2. SyncService picks up pending items, sets `syncStatus = .syncing`
3. INSERT to Supabase with `client_id = localEvent.id`
4. On success: store returned `remoteId`, set `syncStatus = .synced`
5. On conflict (duplicate `client_id`): already synced — fetch `remoteId`, set `.synced`
6. On failure: set `syncStatus = .failed`, log error, schedule retry

**Retry strategy:**
- On network restore (NWPathMonitor), flush all `.pending` and `.failed` items
- Exponential backoff: 1s → 2s → 4s → 8s → max 30s between retries
- Max 5 retries per item per app session; stale failures surface in UI

**Incoming sync (Realtime):**
- Subscribe to `behavior_events` INSERT where `teacher_id = currentUser`
- On incoming event: check if `client_id` matches any local `id` — if so, skip (own echo)
- If no match: create local object with `remoteId` set, `syncStatus = .synced` (came from web)

**Reinstall / new device:**
- On first login, pull all sessions+events from Supabase for the teacher
- Populate SwiftData with `remoteId` set, `syncStatus = .synced`
- No local `id` collision risk since these are fresh inserts

**Conflict resolution:**
- Events are append-only (no edits), so no merge conflicts
- Session `ended_at` updates use last-write-wins by timestamp
- Deletes propagate via Realtime subscription

---

## Step 5: WhisperKit (On-Device STT)

### 5a. Setup
WhisperKit downloads CoreML model on first launch (~40MB for `whisper-base`). Cached permanently after that. Runs on Neural Engine — faster and more battery-efficient than browser WASM.

### 5b. Audio pipeline
```
Microphone (16kHz mono)
    → 3-second chunks
    → RMS silence check (skip if < 0.01)
    → WhisperKit.transcribe()
    → Name detection (regex from roster)
    → Classification (correction/praise patterns)
    → PendingEvent → teacher reviews
```

### 5c. Classification patterns (ported from web)

```swift
let correctionPatterns = [
    "\\bstop\\b", "\\bsit down\\b", "\\bfocus\\b",
    "\\bplease\\s+(quiet|listen|stop)\\b", "\\bi need you to\\b",
    "\\bdon'?t\\b", "\\bpay attention\\b", "\\bhands to yourself\\b",
    "\\bthat'?s enough\\b", "\\bwarning\\b", "\\bin your seat\\b",
    "\\bturn around\\b", "\\bput.+away\\b", "\\bno (talking|phones)\\b"
]

let praisePatterns = [
    "\\bgood job\\b", "\\bgreat (work|job)\\b", "\\bexcellent\\b",
    "\\bthank you\\b", "\\bwell done\\b", "\\bawesome\\b",
    "\\bnice (work|job)\\b", "\\bperfect\\b", "\\bi'?m proud\\b",
    "\\bway to go\\b", "\\bkeep it up\\b",
    "\\bgood (thinking|listening|behavior)\\b"
]
```

### 5d. FERPA compliance
- All audio processed on-device via CoreML Neural Engine
- No audio leaves the phone
- No recordings saved
- Transcripts stored only for teacher-approved events

---

## Step 6: Views

### 6a. LoginView
Email/password form. "Sign in with your Graider account."

### 6b. HomeView (Period Picker)
```
┌─────────────────────────────┐
│  Graider Companion          │
│                             │
│  Good morning, Alex!        │
│                             │
│  Select a class:            │
│  ┌─────────────────────┐   │
│  │  Period 1 - ELA      │   │
│  │  28 students         │   │
│  └─────────────────────┘   │
│  ┌─────────────────────┐   │
│  │  Period 3 - ELA      │   │
│  │  31 students         │   │
│  └─────────────────────┘   │
│                             │
│  ┌─────────────────────┐   │
│  │   Start Session      │   │
│  └─────────────────────┘   │
└─────────────────────────────┘
```

### 6c. SessionView (Active Tracking)
```
┌─────────────────────────────┐
│ Period 3          LIVE      │
│ 14:23 elapsed    Listening  │
├─────────────────────────────┤
│ Pending (2)                 │
│ ┌───────────────────────┐   │
│ │ Marcus J. - correction│   │
│ │ "Marcus sit down"     │   │
│ │  Approve  Switch  X   │   │
│ └───────────────────────┘   │
├─────────────────────────────┤
│ Session Tally               │
│ Marcus J.      -3    +1    │
│ Sofia R.       -0    +4    │
│ Tyler W.       -1    +2    │
│                             │
│ [+ Manual Add]              │
│                             │
│  [End Session]              │
└─────────────────────────────┘
```

**Interactions:**
- Pending: swipe right approve, swipe left dismiss, tap to switch type
- Tally: tap -/+ to manually add
- Manual Add: search roster, pick type, optional note

### 6d. SessionSummaryView
Post-session: total tallies, per-student breakdown, sync status.

---

## Step 7: Live Activity / Dynamic Island

```swift
struct BehaviorActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var totalCorrections: Int
        var totalPraise: Int
        var lastStudentName: String?
        var elapsedMinutes: Int
    }
    var period: String
    var startTime: Date
}
```

- **Compact:** `"P3  -5  +12"`
- **Expanded:** Period, time, last event, tallies
- **Lock Screen:** Full session dashboard

---

## Step 8: Web App Migration (Backend → Supabase)

### 8a. Update `behavior_routes.py`
Same API contract, swap JSON file for Supabase queries:
- `POST /api/behavior/session` → INSERT into Supabase tables
- `GET /api/behavior/data` → SELECT with filters
- `DELETE /api/behavior/data` → DELETE from Supabase

### 8b. Update `assistant_tools_behavior.py`
Same migration — read from Supabase instead of JSON file.

### 8c. Add Realtime to web frontend
```javascript
supabase
  .channel('behavior-events')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'behavior_events',
    filter: `teacher_id=eq.${userId}`
  }, (payload) => {
    addEventFromSync(payload.new);
  })
  .subscribe();
```

---

## Step 9: Data Migration Script

One-time: migrate `behavior_tracking.json` → Supabase tables.

---

## Implementation Order

| # | Task | Dependencies |
|---|------|-------------|
| 1 | Run Supabase migration SQL (create tables) | None |
| 2 | Create Xcode project + SPM deps | None |
| 3 | AuthService (login) | 2 |
| 4 | HomeView (class picker) | 3 |
| 5 | SwiftData models + SyncService | 2 |
| 6 | SessionView (manual tally, no STT) | 4, 5 |
| 7 | Data migration script (JSON → Supabase) | 1 |
| 8 | Backend dual-write phase (write to both JSON + Supabase) | 7 |
| 9 | Validate migration (compare JSON vs Supabase counts) | 8 |
| 10 | Backend cutover (Supabase-only, drop JSON writes) | 9 |
| 11 | Web frontend Realtime subscription | 10 |
| 12 | WhisperKit integration | 6 |
| 13 | Pending events review UI | 12 |
| 14 | Live Activity / Dynamic Island | 6 |
| 15 | Offline queue + reconnect sync | 5 |

**Critical path (iOS):** 1 → 2 → 3 → 4 → 6 → 12 → 13
**Critical path (web migration):** 1 → 7 → 8 → 9 → 10 → 11

**Migration safety:** Data migration (step 7) runs BEFORE the backend cutover (step 10). Step 8 adds a dual-write phase where the backend writes to both JSON and Supabase simultaneously, so no data is lost during the transition. Step 9 validates that Supabase data matches the JSON source before cutting over. Only after validation passes does step 10 remove JSON writes.

---

## Testing Plan

### Functional (Happy Path)
1. Login with existing Graider teacher account on phone
2. Verify classes and students match web app
3. Manual tally: add events, end session → verify in web dashboard
4. Sync: add on phone → appears in web within 1-2 seconds (and vice versa)
5. STT: say student names + correction/praise → verify detection
6. Offline: airplane mode, add events, reconnect → verify sync + no duplicates
7. Live Activity: verify Dynamic Island during active session

### Security (RLS Penetration)
8. **Cross-account session injection:** Using Supabase client with Teacher A's JWT, attempt to INSERT an event with `session_id` belonging to Teacher B. Expected: FK violation (composite FK blocks it even if `teacher_id` is faked).
9. **Cross-account read:** With Teacher A's JWT, SELECT from `behavior_events` WHERE `teacher_id = Teacher B's UUID`. Expected: empty result (RLS blocks it).
10. **Direct table access:** Attempt INSERT/SELECT with anon key (no JWT). Expected: denied by RLS.
11. **Duplicate client_id:** INSERT two events with the same `client_id`. Expected: second INSERT returns unique constraint violation, SyncService treats as already-synced.

### Data Migration Validation
12. **Dry run:** Run migration script against a copy of `behavior_tracking.json`. Compare total event counts, per-student tallies, and date ranges between source JSON and Supabase output.
13. **Dual-write verification:** During step 8 (dual-write phase), run 10 grading sessions via web. Compare JSON file and Supabase table — counts must match exactly.
14. **Rollback test:** After cutover, verify the JSON file still exists as a backup and can be re-imported if Supabase data is lost.

### Background Audio & Battery
15. **Battery drain:** Run 45-minute session with Whisper active, screen off. Measure battery % before/after. Target: <10% drain.
16. **Background audio continuity:** Start session, lock screen, wait 5 minutes. Speak a student name + correction phrase. Verify pending event appears when screen is unlocked.
17. **WhisperKit model download failure:** Simulate network loss during first-launch model download. Verify graceful error, retry button, and that manual tally still works without STT.
18. **Memory pressure:** Run session for 30+ minutes with STT. Monitor memory usage via Instruments — verify no unbounded growth from audio buffers or transcript accumulation.

---

## What Success Looks Like

Teacher walks into Period 3, taps "Start Session," puts phone in pocket. Whisper listens. "Marcus, sit down" → phone detects "Marcus" + "correction," vibrates, pending event appears. Teacher glances at lock screen (Live Activity), swipes to approve. At desk later, opens Graider web — full session visible. Same data, two interfaces, zero manual entry.
