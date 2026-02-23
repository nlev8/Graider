# Assistant Document Generation + Planner Calendar

## Context

The AI Assistant can already generate worksheets and documents via `generate_worksheet` and `generate_document` tools, but it's **context-starved** — it only receives 6 of 10+ config fields and has zero access to standards, lesson plans, differentiation, or accommodations. The teacher has to re-explain everything each time. Separately, the Planner tab has no date/calendar awareness — lessons are "Day 1, Day 2" with no real scheduling.

**Two features:**
1. Enrich assistant with full teacher context + new tools for standards and lesson history, so it can generate accurate documents from simple prompts like "create a quiz for this unit"
2. Add a full calendar view to the Planner for date-based lesson scheduling with holidays

---

## Feature 1: Assistant Context Enrichment

### Files to modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/routes/assistant_routes.py` | **MODIFY** | Inject all settings, differentiation, accommodations into system prompt |
| `backend/services/assistant_tools.py` | **MODIFY** | Add `get_standards`, `get_recent_lessons` tools |

### Step 1A: Expand system prompt — `assistant_routes.py` `_build_system_prompt()`

Currently loads 6 fields. Expand to load and inject:

- **`globalAINotes`** — teacher's custom grading/teaching instructions (the most critical missing piece — contains differentiation rules, grading philosophy, grade level expectations)
- **`state`** — for standards context (e.g., "FL")
- **`grading_period`** — current quarter (e.g., "Q3")
- **Period differentiation** — load from `~/.graider_data/periods/*.meta.json`, inject which periods are advanced/standard/support
- **Accommodation summary** — load from `~/.graider_data/accommodations/student_accommodations.json`, inject count of students with accommodations and types used (no student names — FERPA)

Add to system prompt after teacher context:
```
## TEACHING CONTEXT
- State: FL | Grade: 8 | Subject: US History | Quarter: Q3
- Global AI Instructions: [teacher's globalAINotes]

## CLASS DIFFERENTIATION
- Periods 1, 2, 5: Advanced (DOK 1-4)
- Periods 4, 6, 7: Support (DOK 1-2)

## ACCOMMODATIONS IN USE
- 8 students have IEP/504 accommodations
- Common presets: simplified_language (5), effort_focused (3), chunked_feedback (2)
```

Also update the tools documentation in the system prompt to mention `get_standards` and `get_recent_lessons`.

### Step 1B: Add `get_standards` tool — `assistant_tools.py`

**Purpose:** Let the assistant query curriculum standards when generating documents.

**Tool definition:**
```python
{
    "name": "get_standards",
    "description": "Look up curriculum standards for the teacher's state and subject. Use this when generating standards-aligned documents, worksheets, quizzes, or lesson content. Filter by topic keyword to find relevant standards.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Topic keyword to filter standards (e.g., 'fractions', 'civil war', 'photosynthesis')"
            },
            "dok_max": {
                "type": "integer",
                "description": "Maximum DOK level to include (1-4). Use lower for support classes, higher for advanced."
            }
        }
    }
}
```

**Handler:** Load standards from `backend/data/standards_{state}_{subject}.json`, filter by topic keyword (match against `benchmark`, `topics`, `vocabulary` fields), optionally filter by DOK level. Return matching standards with code, benchmark, vocabulary, learning_targets, essential_questions. Cap at 15 results.

Reuse existing `_load_standards()` pattern from `recommend_next_lesson` (loads `SETTINGS_FILE` for state/subject, builds filename, reads JSON).

### Step 1C: Add `get_recent_lessons` tool — `assistant_tools.py`

**Purpose:** Let the assistant know what's been taught recently, so "create a quiz for this unit" or "quiz on what we did this week" works.

**Tool definition:**
```python
{
    "name": "get_recent_lessons",
    "description": "List saved lesson plans, optionally filtered by unit name. Shows what has been taught recently — topics, standards covered, vocabulary, and objectives. Use this when the teacher asks to create a quiz or worksheet 'for this unit', 'for what we've been doing', or references past lessons.",
    "input_schema": {
        "type": "object",
        "properties": {
            "unit_name": {
                "type": "string",
                "description": "Filter by unit name (partial match). Omit to show all units and recent lessons."
            }
        }
    }
}
```

**Handler:** Scan `~/.graider_lessons/` directory structure. For each unit folder, read lesson JSON files. Return structured summary: unit names, lesson titles, topics per day, standards addressed, vocabulary, objectives. Sort by `_saved_at` timestamp (most recent first). Cap at 10 lessons.

---

## Feature 2: Planner Calendar View

### Files to modify

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/App.jsx` | **MODIFY** | Add calendar mode, state, and rendering |
| `backend/routes/lesson_routes.py` | **MODIFY** | Add calendar data endpoints (schedule CRUD, holidays) |

### Step 2A: Calendar data model — `lesson_routes.py`

**New file:** `~/.graider_data/teaching_calendar.json`

```json
{
  "scheduled_lessons": [
    {
      "id": "uuid",
      "date": "2026-02-16",
      "unit": "American Revolution",
      "lesson_title": "Causes of the Revolution",
      "day_number": 1,
      "lesson_file": "American Revolution/Causes of the Revolution.json",
      "color": "#6366f1"
    }
  ],
  "holidays": [
    { "date": "2026-02-16", "name": "Presidents' Day" },
    { "date": "2026-03-16", "name": "Spring Break", "end_date": "2026-03-20" }
  ],
  "school_days": {
    "monday": true, "tuesday": true, "wednesday": true,
    "thursday": true, "friday": true, "saturday": false, "sunday": false
  }
}
```

**New endpoints:**
- `GET /api/calendar` — returns full calendar data
- `PUT /api/calendar/schedule` — add/update a scheduled lesson `{ date, unit, lesson_title, day_number, lesson_file }`
- `DELETE /api/calendar/schedule/<id>` — remove a scheduled lesson
- `POST /api/calendar/holiday` — add holiday `{ date, name, end_date? }`
- `DELETE /api/calendar/holiday` — remove holiday by date
- `PUT /api/calendar/school-days` — update which days are school days

### Step 2B: Calendar UI — `App.jsx`

**New planner mode:** Add `"calendar"` to the mode toggle (alongside "lesson", "assessment", "dashboard").

**State additions** (~line 1295):
```javascript
const [calendarData, setCalendarData] = useState({ scheduled_lessons: [], holidays: [], school_days: {} })
const [calendarMonth, setCalendarMonth] = useState(new Date())
const [calendarView, setCalendarView] = useState('month') // 'month' or 'week'
const [selectedCalendarDate, setSelectedCalendarDate] = useState(null)
const [showHolidayModal, setShowHolidayModal] = useState(false)
```

**Calendar component** (renders when `plannerMode === "calendar"`):

1. **Header bar:** Month/Year with prev/next arrows, Today button, Month/Week toggle, "Add Holiday" button
2. **Month view:** 7-column grid (Mon-Fri, optionally Sat-Sun grayed). Each day cell shows:
   - Day number
   - Holiday badge (red, if holiday)
   - Lesson cards (colored by unit) showing lesson title
   - Click to schedule a lesson from saved lessons
3. **Week view:** 5 columns (Mon-Fri), taller cells with more detail per day — lesson title, unit, standards, day number
4. **Schedule modal:** When clicking an empty date, show a dropdown of saved units → lessons to assign. When clicking a scheduled lesson, option to remove or reassign.
5. **Holiday modal:** Date picker + name input to add holidays/breaks (with optional end date for multi-day breaks like Spring Break)

**No external library** — custom grid using CSS Grid, consistent with existing inline style patterns. Calendar math uses native `Date` API.

**Drag-and-drop:** Implement basic drag via HTML5 `draggable` attribute on lesson cards. On `onDrop` of a day cell, call `PUT /api/calendar/schedule` to reschedule.

### Step 2C: Load calendar data — `App.jsx`

Load calendar when planner tab + calendar mode activates:
```javascript
useEffect(() => {
  if (activeTab === 'planner' && plannerMode === 'calendar') {
    fetch('/api/calendar').then(r => r.json()).then(setCalendarData)
  }
}, [activeTab, plannerMode])
```

### Step 2D: Auto-schedule from lesson generation

When a lesson plan is generated with a duration (e.g., 5 days), and the teacher saves it, offer to auto-schedule it on the calendar starting from a selected date. Add a "Schedule on Calendar" button next to "Save to Unit" in the lesson plan header.

---

## Verification

### Feature 1 (Assistant Context)
1. Start the backend, open Assistant
2. Ask "What do you know about my classes?" — should mention subject, grade level, period differentiation, globalAINotes summary
3. Ask "Show me the standards for [topic]" — should call `get_standards` and return relevant standards
4. Ask "What have I taught recently?" — should call `get_recent_lessons` and list saved lessons
5. Ask "Create a vocabulary quiz for the current unit" — should query lessons, pull vocab, and generate a worksheet with relevant terms

### Feature 2 (Calendar)
1. Open Planner tab, click "Calendar" mode toggle
2. Month grid renders with current month, navigation works
3. Add a holiday — appears on calendar in red
4. Click empty date, assign a saved lesson — appears as colored card
5. Drag lesson card to new date — reschedules
6. Switch to week view — shows detailed daily view
7. `cd frontend && npm run build` — builds without errors
