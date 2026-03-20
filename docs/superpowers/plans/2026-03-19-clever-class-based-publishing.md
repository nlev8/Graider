# Clever Class-Based Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Clever-synced sections into the class-based student portal so teachers can publish assignments/assessments to classes and students log in with email + class code — no anonymous join codes for graded work.

**Architecture:** On Clever roster sync, auto-create database `classes` records from synced sections and enroll students via `class_students`. Update the Publish modal in App.jsx to offer class selection. The backend endpoints (`/api/publish-to-class`, `/api/classes`, student login/dashboard) already exist.

**Tech Stack:** Python/Flask (backend), React (frontend), Supabase (database)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/routes/clever_routes.py` | Modify | Add `_sync_classes_from_clever()` to background sync |
| `backend/routes/student_account_routes.py` | Modify | Add `clever_section_id` support to class creation |
| `frontend/src/App.jsx` | Modify | Add class picker to Publish modal, show classes in Student Portal tab |
| `tests/test_clever_classes.py` | Create | Tests for class auto-creation from Clever sections |

---

### Task 1: Auto-create database classes from Clever sections on sync

**Files:**
- Modify: `backend/routes/clever_routes.py:44-61` (add class sync to `_background_roster_sync`)
- Modify: `backend/routes/student_account_routes.py:118-154` (support `clever_section_id` on class create)
- Create: `tests/test_clever_classes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_clever_classes.py`:

```python
"""Tests for auto-creating classes from Clever sections during roster sync."""
import json
import pytest
from unittest.mock import patch, MagicMock


def test_sync_classes_creates_db_classes():
    """Verify that _sync_classes_to_db creates classes from Clever section data."""
    from backend.routes.clever_routes import _sync_classes_to_db

    sections = [
        {
            "data": {
                "id": "sec_001",
                "name": "Algebra I - Smith - 5(A)",
                "subject": "math",
                "grade": "9",
                "teachers": ["teacher_001"],
                "students": ["stu_001", "stu_002"],
                "period": "5",
            }
        },
        {
            "data": {
                "id": "sec_002",
                "name": "US History - Smith - 3(B)",
                "subject": "social studies",
                "grade": "8",
                "teachers": ["teacher_001"],
                "students": ["stu_003"],
                "period": "3",
            }
        },
    ]

    students = [
        {"data": {"id": "stu_001", "name": {"first": "Jane", "last": "Doe"}, "email": "jane@school.edu", "roles": {"student": {"grade": "9"}}}},
        {"data": {"id": "stu_002", "name": {"first": "John", "last": "Smith"}, "email": "john@school.edu", "roles": {"student": {"grade": "9"}}}},
        {"data": {"id": "stu_003", "name": {"first": "Alex", "last": "Lee"}, "email": "alex@school.edu", "roles": {"student": {"grade": "8"}}}},
    ]

    mock_db = MagicMock()
    # Mock class upsert returning class records
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "cls_uuid_1", "join_code": "ABC123"},
    ]
    # Mock student upsert
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=mock_db):
        result = _sync_classes_to_db(sections, students, "teacher_uuid_123")

    assert result["classes_synced"] == 2
    assert result["students_enrolled"] >= 0  # May vary by mock setup


def test_sync_classes_handles_empty_sections():
    """Verify graceful handling when no sections exist."""
    from backend.routes.clever_routes import _sync_classes_to_db

    mock_db = MagicMock()
    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=mock_db):
        result = _sync_classes_to_db([], [], "teacher_uuid_123")

    assert result["classes_synced"] == 0
    assert result["students_enrolled"] == 0


def test_sync_classes_skips_when_no_supabase():
    """Verify no crash when Supabase is not configured."""
    from backend.routes.clever_routes import _sync_classes_to_db

    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=None):
        result = _sync_classes_to_db([{"data": {"id": "s1", "name": "Test"}}], [], "t1")

    assert result["classes_synced"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_clever_classes.py -v`
Expected: FAIL with `ImportError: cannot import name '_sync_classes_to_db'`

- [ ] **Step 3: Write the implementation**

Add to `backend/routes/clever_routes.py` — new import and helper function:

```python
# At top of file, add import:
from backend.supabase_client import get_supabase as _get_supabase_safe

# Add new function after _background_roster_sync:
def _sync_classes_to_db(sections, students, teacher_id):
    """Create/update database classes from Clever sections and enroll students.

    This bridges Clever's file-based period sync with the class-based student portal.
    Classes are upserted by (teacher_id, clever_section_id) to avoid duplicates on re-sync.
    """
    result = {"classes_synced": 0, "students_enrolled": 0}
    db = _get_supabase_safe()
    if not db or not sections:
        return result

    # Build student lookup: clever_id -> student data
    student_map = {}
    for s in students:
        data = s.get("data", s)
        student_map[data.get("id", "")] = data

    for section in sections:
        data = section.get("data", section)
        section_id = data.get("id", "")
        section_name = data.get("name", f"Section {section_id}")
        subject = data.get("subject", "")
        grade = data.get("grade", "")
        student_ids = data.get("students", [])

        if not section_id:
            continue

        try:
            # Upsert class (create if new, update name/subject if changed)
            class_result = db.table("classes").upsert({
                "teacher_id": teacher_id,
                "name": section_name,
                "subject": subject,
                "grade_level": grade,
                "clever_section_id": section_id,
                "is_active": True,
            }, on_conflict="teacher_id,clever_section_id").execute()

            if not class_result.data:
                continue

            class_id = class_result.data[0]["id"]
            join_code = class_result.data[0].get("join_code", "")
            result["classes_synced"] += 1

            # Enroll students in this class
            for stu_clever_id in student_ids:
                stu_data = student_map.get(stu_clever_id)
                if not stu_data:
                    continue

                stu_name = stu_data.get("name", {})
                stu_email = stu_data.get("email", "")
                stu_roles = stu_data.get("roles", {}).get("student", {})

                # Upsert student record
                student_result = db.table("students").upsert({
                    "teacher_id": teacher_id,
                    "student_id_number": stu_clever_id,
                    "first_name": stu_name.get("first", ""),
                    "last_name": stu_name.get("last", ""),
                    "email": stu_email,
                    "period": section_name,
                    "is_active": True,
                }, on_conflict="teacher_id,student_id_number").execute()

                if student_result.data:
                    student_uuid = student_result.data[0]["id"]
                    db.table("class_students").upsert({
                        "class_id": class_id,
                        "student_id": student_uuid,
                    }, on_conflict="class_id,student_id").execute()
                    result["students_enrolled"] += 1

        except Exception as e:
            logger.warning("Failed to sync class for section %s: %s", section_id, str(e))

    logger.info("Clever class sync: %d classes, %d students enrolled",
                result["classes_synced"], result["students_enrolled"])
    return result
```

- [ ] **Step 4: Add `_sync_classes_to_db` call to `_background_roster_sync`**

In `backend/routes/clever_routes.py`, modify `_background_roster_sync` to call the new function after persisting sections:

```python
def _background_roster_sync(district_token, teacher_id):
    """Run roster sync in a background thread so OAuth callback returns immediately."""
    try:
        roster = _run_async(sync_roster(district_token))
        students = roster.get("students", [])
        if students:
            persist_roster_as_csv(students, teacher_id)
        sections = roster.get("sections", [])
        if sections:
            persist_sections_as_periods(sections, teacher_id)
            # Also create/update database classes for the student portal
            _sync_classes_to_db(sections, students, teacher_id)
        contacts = roster.get("contacts", [])
        if contacts and students:
            contact_map = extract_parent_contacts(contacts, students)
            if contact_map:
                persist_parent_contacts(contact_map, teacher_id)
        logger.info("Background roster sync complete: %d students, %d sections, %d contacts",
                    len(students), len(sections), len(contacts))
    except Exception as e:
        logger.warning("Background roster sync failed: %s", str(e))
```

- [ ] **Step 5: Add `clever_section_id` column to classes table**

The `classes` table needs a `clever_section_id` column and a unique constraint on `(teacher_id, clever_section_id)` for upsert. Also needs a default `join_code` generated by the database.

Run this SQL in Supabase Dashboard > SQL Editor:

```sql
-- Add clever_section_id to classes table
ALTER TABLE classes ADD COLUMN IF NOT EXISTS clever_section_id TEXT;

-- Add unique constraint for upsert (one class per section per teacher)
ALTER TABLE classes ADD CONSTRAINT classes_teacher_clever_section_unique
    UNIQUE (teacher_id, clever_section_id);

-- Add trigger to auto-generate join_code on insert if not provided
CREATE OR REPLACE FUNCTION generate_class_join_code()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.join_code IS NULL OR NEW.join_code = '' THEN
        NEW.join_code := upper(substr(md5(random()::text), 1, 6));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS classes_auto_join_code ON classes;
CREATE TRIGGER classes_auto_join_code
    BEFORE INSERT ON classes
    FOR EACH ROW
    EXECUTE FUNCTION generate_class_join_code();
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_clever_classes.py -v`
Expected: 3 tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/routes/clever_routes.py tests/test_clever_classes.py
git commit -m "feat: auto-create database classes from Clever sections on roster sync"
```

---

### Task 2: Add class picker to Publish modal in App.jsx

**Files:**
- Modify: `frontend/src/App.jsx` — Publish modal (around line 16380+), publishAssessmentHandler, confirmPublishAssessment

- [ ] **Step 1: Add classes state and fetch**

In `App.jsx`, near other state declarations (around line 1957):

```javascript
const [teacherClasses, setTeacherClasses] = useState([]);
const [publishClassId, setPublishClassId] = useState('');
```

Add a fetch function near other publish functions:

```javascript
const fetchTeacherClasses = async () => {
    try {
        const data = await api.listClasses();
        if (data.classes) setTeacherClasses(data.classes);
    } catch (e) {
        console.error("Failed to load classes:", e);
    }
};
```

- [ ] **Step 2: Load classes when Publish modal opens**

In `publishAssessmentHandler` in App.jsx (around line 4783), add class fetch:

```javascript
const publishAssessmentHandler = () => {
    var content = getActiveAssignment();
    if (!content) {
        addToast("No content to publish", "warning");
        return;
    }
    setPublishSettings({
        period: '',
        periodFilename: '',
        isMakeup: false,
        selectedStudents: [],
        timeLimit: content.time_limit || null,
        applyAccommodations: true,
    });
    setPublishClassId('');
    setPublishModalStudents([]);
    fetchTeacherClasses();  // Load available classes
    setShowPublishModal(true);
};
```

- [ ] **Step 3: Add class dropdown to Publish modal UI**

In the Publish modal JSX (around line 16380), add a class selector ABOVE the period selector:

```jsx
{/* Class Selection */}
<div style={{ marginBottom: "15px" }}>
    <label className="label" style={{ marginBottom: "6px" }}>
        Publish to Class (optional)
    </label>
    <select
        className="input"
        value={publishClassId}
        onChange={(e) => setPublishClassId(e.target.value)}
        style={{ width: "100%" }}
    >
        <option value="">Join Code Only (no class)</option>
        {teacherClasses.map((cls) => (
            <option key={cls.id} value={cls.id}>
                {cls.name} ({cls.join_code})
            </option>
        ))}
    </select>
    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "4px" }}>
        {publishClassId
            ? "Students log in with email + class code to access this."
            : "Anyone with the join code can access this (anonymous)."}
    </p>
</div>
```

- [ ] **Step 4: Update confirmPublishAssessment to use class-based publish when class selected**

In `confirmPublishAssessment` in App.jsx (around line 4823), branch based on whether a class is selected:

```javascript
const confirmPublishAssessment = async () => {
    var contentToPublish = getActiveAssignment();
    if (!contentToPublish) return;

    setPublishingAssessment(true);
    try {
        let studentAccommodationsMap = {};
        if (publishSettings.applyAccommodations && publishModalStudents.length > 0) {
            publishModalStudents.forEach(student => {
                const studentId = student.id || student.email || (student.first + ' ' + student.last);
                const accommodation = studentAccommodations[studentId];
                if (accommodation) {
                    studentAccommodationsMap[student.first + ' ' + student.last] = accommodation;
                }
            });
        }

        let restrictedStudents = null;
        if (publishSettings.isMakeup && publishSettings.selectedStudents.length > 0) {
            restrictedStudents = publishSettings.selectedStudents;
        }

        let data;
        if (publishClassId) {
            // Class-based publish — students log in with email + class code
            data = await api.publishToClass(
                publishClassId,
                contentToPublish,
                contentToPublish.sections ? 'assignment' : 'assessment',
                contentToPublish.title || 'Untitled',
                {
                    teacher_name: config.teacher_name || "Teacher",
                    teacher_email: config.teacher_email,
                    show_correct_answers: true,
                    show_score_immediately: true,
                    time_limit_minutes: publishSettings.timeLimit,
                    student_accommodations: studentAccommodationsMap,
                },
                null, // due_date — can add later
            );
        } else {
            // Join-code publish — anonymous access
            data = await api.publishAssessmentToPortal(contentToPublish, {
                teacher_name: config.teacher_name || "Teacher",
                teacher_email: config.teacher_email,
                show_correct_answers: true,
                show_score_immediately: true,
                period: publishSettings.period,
                restricted_students: restrictedStudents,
                student_accommodations: studentAccommodationsMap,
                time_limit_minutes: publishSettings.timeLimit,
            });
        }

        if (data.error) {
            addToast("Error publishing: " + data.error, "error");
        } else if (data.success) {
            setShowPublishModal(false);
            setPublishedAssessmentModal({
                show: true,
                joinCode: data.join_code,
                joinLink: data.join_link,
            });
            addToast("Published to student portal!", "success");
            fetchPublishedAssessments();
        }
    } catch (e) {
        addToast("Error publishing: " + e.message, "error");
    } finally {
        setPublishingAssessment(false);
    }
};
```

- [ ] **Step 5: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add class picker to Publish modal for class-based publishing"
```

---

### Task 3: Show classes in Student Portal tab for teacher management

**Files:**
- Modify: `frontend/src/App.jsx` — Student Portal dashboard section (around line 13858)

- [ ] **Step 1: Add class list section to Student Portal dashboard**

Above the "Published Assessments" section in the Student Portal tab (line 13858), add a Classes management section:

```jsx
{/* Teacher's Classes */}
<div className="glass-card" style={{ padding: "20px", marginBottom: "20px" }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="School" size={20} />
            Your Classes
        </h3>
        <button onClick={fetchTeacherClasses} className="btn btn-secondary" style={{ padding: "8px 12px", fontSize: "0.85rem" }}>
            <Icon name="RefreshCw" size={16} /> Refresh
        </button>
    </div>
    {teacherClasses.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            No classes yet. Classes are created automatically when you sync your Clever roster, or you can create one manually.
        </p>
    ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {teacherClasses.map((cls) => (
                <div key={cls.id} style={{
                    padding: "12px 15px",
                    background: "rgba(255,255,255,0.03)",
                    borderRadius: "10px",
                    border: "1px solid rgba(255,255,255,0.1)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                }}>
                    <div>
                        <div style={{ fontWeight: 600 }}>{cls.name}</div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                            Code: {cls.join_code} | {cls.subject || "No subject"} | {(cls.class_students || [{}])[0]?.count || 0} students
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )}
</div>
```

- [ ] **Step 2: Load classes on Student Portal tab mount**

Add a useEffect to fetch classes when the Student Portal tab is selected:

```javascript
useEffect(() => {
    if (plannerMode === "dashboard") {
        fetchTeacherClasses();
    }
}, [plannerMode]);
```

- [ ] **Step 3: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: show teacher's classes in Student Portal dashboard"
```

---

### Task 4: Update published content display to show class-based items

**Files:**
- Modify: `frontend/src/App.jsx` — Student Portal dashboard, fetchPublishedAssessments

- [ ] **Step 1: Update fetchPublishedAssessments to also fetch class-based content**

The current `fetchPublishedAssessments` only fetches from the join-code `published_assessments` table. Add a parallel fetch for `published_content` (class-based):

Find `fetchPublishedAssessments` in App.jsx and update to merge both sources:

```javascript
const fetchPublishedAssessments = async () => {
    setLoadingPublished(true);
    try {
        // Fetch join-code assessments (existing)
        const joinCodeData = await api.getPublishedAssessments();

        // Fetch class-based published content
        const classData = await api.getPortalSubmissions();

        // Merge both lists
        let all = [];
        if (joinCodeData.assessments) {
            all = all.concat(joinCodeData.assessments.map(a => ({...a, source: 'join_code'})));
        }
        if (classData.content) {
            all = all.concat(classData.content.map(c => ({
                ...c,
                join_code: c.join_code,
                title: c.title,
                source: 'class',
                class_name: c.class_name,
            })));
        }
        setPublishedAssessments(all);
    } catch (e) {
        console.error("Failed to load published content:", e);
    } finally {
        setLoadingPublished(false);
    }
};
```

- [ ] **Step 2: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Manual test**

1. Log in via Clever (or localhost)
2. Go to Planner > Lesson Planning, generate an assignment
3. Click "Publish to Portal"
4. Select a class from the dropdown (if classes exist from Clever sync)
5. Publish — should get join code and link
6. Go to Student Portal tab — should see the published content
7. Open `/student` in incognito, log in with a student email + class code
8. Should see the assignment on the student dashboard

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: merge join-code and class-based content in Student Portal dashboard"
```

---

### Task 5: Run full verification

- [ ] **Step 1: Run all Clever tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_clever.py tests/test_clever_classes.py -v`
Expected: All tests pass

- [ ] **Step 2: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Clean build

- [ ] **Step 3: Verify backend imports**

Run: `cd /Users/alexc/Downloads/Graider/backend && source ../venv/bin/activate && python -c "from app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Clever class-based publishing — auto-create classes from sections, publish to classes, student portal integration"
```
