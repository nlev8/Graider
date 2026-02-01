# Assessment from Lessons/Assignments Feature

Generate assessment questions directly from your saved lessons and assignments, ensuring tests match what was actually taught.

---

## Overview

### Current Flow
```
Standards → AI → Assessment Questions
```

### New Flow
```
Saved Lessons + Assignments → AI → Assessment Questions (based on YOUR content)
```

---

## File Changes Required

### 1. Backend: New Lesson Storage Routes

**File:** `backend/routes/lesson_routes.py` (NEW FILE)

```python
"""
Lesson Plan storage routes for Graider.
Saves lesson plans for later use in assessment generation.
"""
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify

lesson_bp = Blueprint('lesson', __name__)

LESSONS_DIR = os.path.expanduser("~/.graider_lessons")


@lesson_bp.route('/api/save-lesson', methods=['POST'])
def save_lesson():
    """Save a lesson plan for later use in assessment generation."""
    data = request.json
    lesson = data.get('lesson', {})
    unit_name = data.get('unitName', 'General')

    os.makedirs(LESSONS_DIR, exist_ok=True)

    # Create unit subfolder
    unit_folder = os.path.join(LESSONS_DIR, _safe_filename(unit_name))
    os.makedirs(unit_folder, exist_ok=True)

    # Use lesson title for filename
    title = lesson.get('title', 'Untitled Lesson')
    safe_title = _safe_filename(title)
    filepath = os.path.join(unit_folder, f"{safe_title}.json")

    # Add metadata
    lesson['_saved_at'] = datetime.now().isoformat()
    lesson['_unit'] = unit_name

    try:
        with open(filepath, 'w') as f:
            json.dump(lesson, f, indent=2)
        return jsonify({"status": "saved", "path": filepath, "unit": unit_name})
    except Exception as e:
        return jsonify({"error": str(e)})


@lesson_bp.route('/api/list-lessons')
def list_lessons():
    """List all saved lessons organized by unit."""
    if not os.path.exists(LESSONS_DIR):
        return jsonify({"units": {}, "lessons": []})

    units = {}
    all_lessons = []

    for unit_name in os.listdir(LESSONS_DIR):
        unit_path = os.path.join(LESSONS_DIR, unit_name)
        if not os.path.isdir(unit_path):
            continue

        units[unit_name] = []

        for f in os.listdir(unit_path):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(unit_path, f), 'r') as lf:
                        lesson = json.load(lf)
                        lesson_info = {
                            "filename": f.replace('.json', ''),
                            "title": lesson.get('title', f.replace('.json', '')),
                            "unit": unit_name,
                            "standards": lesson.get('standards', []),
                            "objectives": lesson.get('learning_objectives', []),
                            "saved_at": lesson.get('_saved_at', '')
                        }
                        units[unit_name].append(lesson_info)
                        all_lessons.append(lesson_info)
                except Exception:
                    pass

    return jsonify({"units": units, "lessons": all_lessons})


@lesson_bp.route('/api/load-lesson')
def load_lesson():
    """Load a specific lesson by unit and filename."""
    unit = request.args.get('unit', '')
    filename = request.args.get('filename', '')

    filepath = os.path.join(LESSONS_DIR, _safe_filename(unit), f"{filename}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Lesson not found"})

    try:
        with open(filepath, 'r') as f:
            lesson = json.load(f)
        return jsonify({"lesson": lesson})
    except Exception as e:
        return jsonify({"error": str(e)})


@lesson_bp.route('/api/delete-lesson', methods=['DELETE'])
def delete_lesson():
    """Delete a saved lesson."""
    unit = request.args.get('unit', '')
    filename = request.args.get('filename', '')

    filepath = os.path.join(LESSONS_DIR, _safe_filename(unit), f"{filename}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Lesson not found"})

    try:
        os.remove(filepath)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)})


@lesson_bp.route('/api/list-units')
def list_units():
    """List all unit names."""
    if not os.path.exists(LESSONS_DIR):
        return jsonify({"units": []})

    units = [d for d in os.listdir(LESSONS_DIR)
             if os.path.isdir(os.path.join(LESSONS_DIR, d))]
    return jsonify({"units": sorted(units)})


def _safe_filename(name):
    """Convert name to safe filename."""
    return "".join(c for c in name if c.isalnum() or c in ' -_').strip()
```

---

### 2. Backend: Register New Blueprint

**File:** `backend/app.py`

**Add import (near other blueprint imports ~line 20):**
```python
from routes.lesson_routes import lesson_bp
```

**Register blueprint (near other registrations ~line 50):**
```python
app.register_blueprint(lesson_bp)
```

---

### 3. Backend: Update Assessment Generation

**File:** `backend/routes/planner_routes.py`

**Modify `generate_assessment` function to accept content sources:**

```python
@planner_bp.route('/api/generate-assessment', methods=['POST'])
def generate_assessment():
    """Generate an AI-powered assessment, optionally from saved lessons/assignments."""
    data = request.json

    # ... existing code for standards, config, etc ...

    # NEW: Content sources
    content_sources = data.get('contentSources', [])
    # content_sources = [
    #   {"type": "lesson", "unit": "Unit 1", "filename": "Intro to Fractions", "content": {...}},
    #   {"type": "assignment", "filename": "Fraction Practice", "content": {...}}
    # ]

    # Build source content for prompt
    source_content = ""
    if content_sources:
        source_content = "\n\n=== INSTRUCTIONAL CONTENT TO BASE QUESTIONS ON ===\n"
        source_content += "Generate questions that test the specific content, vocabulary, examples, and activities from these lessons/assignments:\n\n"

        for source in content_sources:
            if source['type'] == 'lesson':
                lesson = source.get('content', {})
                source_content += f"--- LESSON: {lesson.get('title', 'Untitled')} ---\n"
                source_content += f"Overview: {lesson.get('overview', '')}\n"
                source_content += f"Learning Objectives: {', '.join(lesson.get('learning_objectives', []))}\n"
                source_content += f"Essential Questions: {', '.join(lesson.get('essential_questions', []))}\n"

                # Include activities from each day
                for day in lesson.get('days', []):
                    source_content += f"\nDay {day.get('day', '?')}: {day.get('focus', '')}\n"
                    for activity in day.get('activities', []):
                        source_content += f"  - {activity.get('name', '')}: {activity.get('description', '')}\n"

                source_content += "\n"

            elif source['type'] == 'assignment':
                assignment = source.get('content', {})
                source_content += f"--- ASSIGNMENT: {assignment.get('title', 'Untitled')} ---\n"
                source_content += f"Instructions: {assignment.get('instructions', '')}\n"
                for q in assignment.get('questions', []):
                    source_content += f"  - {q.get('marker', '')}: {q.get('prompt', '')}\n"
                source_content += "\n"

        source_content += "=== END INSTRUCTIONAL CONTENT ===\n\n"
        source_content += "IMPORTANT: Questions must directly relate to the content above. Reference specific vocabulary, examples, and concepts from the lessons.\n\n"

    # Modify the prompt to include source content
    prompt = f"""You are an expert assessment creator...

{source_content}

{f'TARGET PERIOD: {target_period}' if target_period else ''}
{f'TEACHER INSTRUCTIONS: {global_ai_notes}' if global_ai_notes else ''}

... rest of existing prompt ...
"""
```

---

### 4. Frontend: API Service Updates

**File:** `frontend/src/services/api.js`

**Add new API methods:**

```javascript
// Lesson Plan Storage
export const saveLessonPlan = async (lesson, unitName) => {
  const response = await fetch(`${API_BASE}/api/save-lesson`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson, unitName })
  });
  return response.json();
};

export const listLessons = async () => {
  const response = await fetch(`${API_BASE}/api/list-lessons`);
  return response.json();
};

export const loadLesson = async (unit, filename) => {
  const response = await fetch(`${API_BASE}/api/load-lesson?unit=${encodeURIComponent(unit)}&filename=${encodeURIComponent(filename)}`);
  return response.json();
};

export const deleteLesson = async (unit, filename) => {
  const response = await fetch(`${API_BASE}/api/delete-lesson?unit=${encodeURIComponent(unit)}&filename=${encodeURIComponent(filename)}`, {
    method: 'DELETE'
  });
  return response.json();
};

export const listUnits = async () => {
  const response = await fetch(`${API_BASE}/api/list-units`);
  return response.json();
};
```

---

### 5. Frontend: State Additions

**File:** `frontend/src/App.jsx`

**Add new state variables (near other useState declarations ~line 900):**

```javascript
// Saved lessons for assessment generation
const [savedLessons, setSavedLessons] = useState({ units: {}, lessons: [] });
const [savedUnits, setSavedUnits] = useState([]);
const [selectedSources, setSelectedSources] = useState([]); // [{type, unit, filename, content}]
const [showSaveLesson, setShowSaveLesson] = useState(false);
const [saveLessonUnit, setSaveLessonUnit] = useState('');
const [newUnitName, setNewUnitName] = useState('');
```

**Add fetch function (near other data fetching functions):**

```javascript
const fetchSavedLessons = async () => {
  try {
    const data = await api.listLessons();
    setSavedLessons(data);
    setSavedUnits(Object.keys(data.units || {}));
  } catch (err) {
    console.error('Failed to fetch lessons:', err);
  }
};

// Call on mount and when lessons change
useEffect(() => {
  fetchSavedLessons();
}, []);
```

---

### 6. Frontend: Save Lesson Button in Lesson Planner

**File:** `frontend/src/App.jsx`

**Add Save button next to Export button in Lesson Planner (~line 13877):**

```javascript
{/* After the Export to Word button */}
<button
  onClick={() => setShowSaveLesson(true)}
  className="btn btn-secondary"
  style={{ padding: "10px 20px" }}
>
  <Icon name="FolderPlus" size={18} />
  Save to Unit
</button>

{/* Save Lesson Modal */}
{showSaveLesson && (
  <div
    style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: "rgba(0,0,0,0.7)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000
    }}
    onClick={() => setShowSaveLesson(false)}
  >
    <div
      className="glass-card"
      style={{ padding: "30px", width: "400px", maxWidth: "90vw" }}
      onClick={(e) => e.stopPropagation()}
    >
      <h3 style={{ marginBottom: "20px" }}>Save Lesson to Unit</h3>

      <label className="label">Select Unit</label>
      <select
        className="input"
        value={saveLessonUnit}
        onChange={(e) => setSaveLessonUnit(e.target.value)}
        style={{ width: "100%", marginBottom: "15px" }}
      >
        <option value="">-- Select or create new --</option>
        {savedUnits.map((unit) => (
          <option key={unit} value={unit}>{unit}</option>
        ))}
      </select>

      {saveLessonUnit === '' && (
        <>
          <label className="label">Or Create New Unit</label>
          <input
            type="text"
            className="input"
            placeholder="e.g., Unit 3 - Fractions"
            value={newUnitName}
            onChange={(e) => setNewUnitName(e.target.value)}
            style={{ width: "100%", marginBottom: "20px" }}
          />
        </>
      )}

      <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
        <button
          onClick={() => setShowSaveLesson(false)}
          className="btn btn-secondary"
        >
          Cancel
        </button>
        <button
          onClick={async () => {
            const unitName = saveLessonUnit || newUnitName;
            if (!unitName) {
              alert('Please select or enter a unit name');
              return;
            }
            try {
              await api.saveLessonPlan(lessonPlan, unitName);
              setShowSaveLesson(false);
              setSaveLessonUnit('');
              setNewUnitName('');
              fetchSavedLessons();
              alert('Lesson saved to ' + unitName);
            } catch (err) {
              alert('Failed to save: ' + err.message);
            }
          }}
          className="btn btn-primary"
          disabled={!saveLessonUnit && !newUnitName}
        >
          Save Lesson
        </button>
      </div>
    </div>
  </div>
)}
```

---

### 7. Frontend: Content Sources Panel in Assessment Generator

**File:** `frontend/src/App.jsx`

**Add new panel before the "Select Standards" panel in Assessment Generator (~line 15100):**

```javascript
{/* Content Sources Panel - NEW */}
<div className="glass-card" style={{ padding: "25px", marginBottom: "20px" }}>
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
    <div>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "5px" }}>
        <Icon name="BookOpen" size={18} style={{ marginRight: "8px" }} />
        Content Sources
      </h3>
      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
        Select lessons and assignments to generate questions from your actual instruction
      </p>
    </div>
    <button
      onClick={fetchSavedLessons}
      className="btn btn-secondary"
      style={{ padding: "6px 12px" }}
    >
      <Icon name="RefreshCw" size={14} />
      Refresh
    </button>
  </div>

  {Object.keys(savedLessons.units || {}).length === 0 ? (
    <div style={{
      padding: "20px",
      background: "rgba(255,255,255,0.03)",
      borderRadius: "10px",
      textAlign: "center"
    }}>
      <Icon name="FolderOpen" size={24} style={{ color: "var(--text-muted)", marginBottom: "10px" }} />
      <p style={{ color: "var(--text-secondary)", marginBottom: "10px" }}>
        No saved lessons yet
      </p>
      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
        Save lessons from the Lesson Planner to use them here
      </p>
    </div>
  ) : (
    <div style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
      {Object.entries(savedLessons.units).map(([unitName, lessons]) => (
        <div key={unitName}>
          <h4 style={{
            fontSize: "0.9rem",
            fontWeight: 600,
            marginBottom: "10px",
            color: "var(--primary)"
          }}>
            {unitName}
          </h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {lessons.map((lesson) => {
              const isSelected = selectedSources.some(
                s => s.type === 'lesson' && s.unit === unitName && s.filename === lesson.filename
              );
              return (
                <button
                  key={lesson.filename}
                  onClick={async () => {
                    if (isSelected) {
                      setSelectedSources(selectedSources.filter(
                        s => !(s.type === 'lesson' && s.unit === unitName && s.filename === lesson.filename)
                      ));
                    } else {
                      // Load full lesson content
                      const data = await api.loadLesson(unitName, lesson.filename);
                      if (data.lesson) {
                        setSelectedSources([...selectedSources, {
                          type: 'lesson',
                          unit: unitName,
                          filename: lesson.filename,
                          title: lesson.title,
                          content: data.lesson
                        }]);
                      }
                    }
                  }}
                  style={{
                    padding: "8px 14px",
                    borderRadius: "8px",
                    border: isSelected ? "2px solid var(--primary)" : "1px solid var(--glass-border)",
                    background: isSelected ? "rgba(99, 102, 241, 0.2)" : "rgba(255,255,255,0.05)",
                    color: isSelected ? "var(--primary)" : "var(--text-primary)",
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px"
                  }}
                >
                  <Icon name={isSelected ? "CheckCircle" : "FileText"} size={14} />
                  {lesson.title}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  )}

  {selectedSources.length > 0 && (
    <div style={{
      marginTop: "15px",
      padding: "10px 15px",
      background: "rgba(34, 197, 94, 0.1)",
      borderRadius: "8px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }}>
      <span style={{ color: "var(--success)", fontSize: "0.9rem" }}>
        <Icon name="Check" size={16} style={{ marginRight: "6px" }} />
        {selectedSources.length} source{selectedSources.length > 1 ? 's' : ''} selected
      </span>
      <button
        onClick={() => setSelectedSources([])}
        style={{
          background: "none",
          border: "none",
          color: "var(--text-muted)",
          cursor: "pointer",
          fontSize: "0.85rem"
        }}
      >
        Clear all
      </button>
    </div>
  )}
</div>
```

---

### 8. Frontend: Pass Sources to Assessment Generation

**File:** `frontend/src/App.jsx`

**Modify the generateAssessment call (~line 2500) to include sources:**

```javascript
const generateAssessment = async () => {
  setGeneratingAssessment(true);
  try {
    const data = await api.generateAssessment({
      standards: selectedStandards,
      config: assessmentConfig,
      globalNotes: globalAiNotes,
      contentSources: selectedSources  // NEW: Pass selected sources
    });

    if (data.assessment) {
      setGeneratedAssessment(data.assessment);
      setSelectedSources([]); // Clear after generation
    }
  } catch (err) {
    console.error('Failed to generate assessment:', err);
  } finally {
    setGeneratingAssessment(false);
  }
};
```

---

### 9. Frontend: Update assessmentConfig State

**File:** `frontend/src/App.jsx`

**Clear selectedSources when clearing assessment:**

```javascript
// In the Clear Assessment button onClick handler
onClick={() => {
  setGeneratedAssessment(null);
  setAssessmentAnswers({});
  setSelectedSources([]);  // Also clear selected sources
}}
```

---

## Database/Storage Structure

### Lesson Storage

```
~/.graider_lessons/
├── Unit 1 - Introduction/
│   ├── Lesson 1 - Overview.json
│   └── Lesson 2 - Key Concepts.json
├── Unit 2 - Core Topics/
│   ├── Lesson 1 - Foundations.json
│   └── Lesson 2 - Applications.json
└── Unit 3 - Advanced/
    └── Lesson 1 - Deep Dive.json
```

### Lesson JSON Structure

```json
{
  "title": "Introduction to Fractions",
  "overview": "Students will learn...",
  "standards": ["MA.4.FR.1.1", "MA.4.FR.1.2"],
  "learning_objectives": [
    "Identify parts of a fraction",
    "Compare fractions with same denominator"
  ],
  "essential_questions": [
    "What does a fraction represent?",
    "How do we compare fractions?"
  ],
  "days": [
    {
      "day": 1,
      "focus": "Introduction",
      "activities": [
        {
          "name": "Pizza Fractions",
          "description": "Students divide paper pizzas..."
        }
      ]
    }
  ],
  "_unit": "Unit 1 - Fractions",
  "_saved_at": "2025-01-31T10:30:00Z"
}
```

---

## User Workflow

### Saving Lessons

1. Go to **Lesson Planner**
2. Generate a lesson plan
3. Click **Save to Unit**
4. Select existing unit or create new one
5. Lesson is saved for future assessment generation

### Creating Assessments from Lessons

1. Go to **Assessment Generator**
2. In **Content Sources** panel, select lessons/assignments to test
3. Optionally select additional standards
4. Configure question types and counts
5. Click **Generate Assessment**
6. Questions are based on your selected instructional content

### Differentiation

1. Select the same lessons for both advanced and standard versions
2. Set **Target Period** to the specific period
3. Global AI Instructions differentiate the difficulty
4. Both versions test the same content at appropriate levels

---

## Benefits

1. **Alignment** - Assessments directly test what was taught
2. **Consistency** - Same source material for all versions
3. **Differentiation** - Same topics, different difficulty levels
4. **Time Savings** - No need to manually align assessments to instruction
5. **Documentation** - Clear record of what content was tested
