# CLAUDE.md - Graider Development Guide

## Virtual Environment
The Python venv is at: `/Users/alexc/Downloads/Graider/venv/`
Activate with: `source venv/bin/activate`
Always use this venv for running Python commands, installing packages, and starting the backend.

## CRITICAL: Active Frontend

**The active frontend is `frontend/src/App.jsx`** (React + Vite, served via `backend/app.py`).

**`graider_app.py` is the LEGACY frontend** — it contains an old embedded React UI that is NOT in use.
**NEVER edit `graider_app.py` for UI changes.** All frontend work goes in `frontend/src/`.

- Backend entry point: `backend/app.py` (serves the Vite-built frontend from `backend/static/`)
- Frontend source: `frontend/src/App.jsx` and `frontend/src/` directory

## Project Overview

Graider is an AI-powered grading assistant for educators. It's a Flask application with a React frontend that uses OpenAI's GPT-4 API to grade student assignments.

## Architecture

### File Structure
```
graider/
├── graider_app.py          # LEGACY - old embedded React UI, DO NOT EDIT for UI changes
├── assignment_grader.py    # Core grading logic, file parsing, OpenAI calls
├── email_sender.py         # Email functionality for sending feedback
├── sharepoint_watcher.py   # OneDrive/SharePoint file watching
├── .env                    # API keys (never commit)
└── ~/.graider_*/           # User config files (rubric, assignments, settings)
```

### Key Components

1. **Flask Backend** (`graider_app.py`)
   - Serves embedded React UI via HTML template string
   - REST API endpoints under `/api/*`
   - Grading runs in background thread

2. **Embedded React Frontend** (inside `graider_app.py`)
   - Uses CDN-loaded React, ReactDOM, Babel
   - NO separate npm/node process needed
   - Single `python graider_app.py` serves everything

3. **Grading Engine** (`assignment_grader.py`)
   - Parses Word docs, PDFs, images
   - Extracts student work using markers
   - Calls OpenAI API for grading

4. **Persistence**
   - `~/.graider_rubric.json` - Rubric settings
   - `~/.graider_settings.json` - Global AI notes
   - `~/.graider_assignments/` - Saved assignment configs
   - `~/.graider_email.json` - Email credentials

---

## AI Grading Factors (CRITICAL — Never Drop Any Factor)

The multipass grading pipeline (`grade_multipass` → `grade_per_question` → `generate_feedback`) must account for ALL of these factors. Dropping any factor produces incorrect scores or generic feedback.

### How factors flow through the pipeline:
- **`file_ai_notes`** (built in `app.py`): Accumulates global AI instructions, assignment grading notes, rubric type overrides, IEP/504 accommodations, student history, class period differentiation into ONE string. Passed as `custom_ai_instructions` → `teacher_instructions`.
- **`rubric_prompt`** (from Settings): Teacher's custom rubric categories/weights. Appended to `effective_instructions` in `grade_multipass()` so per-question graders see it.
- **`grading_style`** (lenient/standard/strict): Included in `grade_per_question()` prompt AND used for score caps in `grade_multipass()`.

### Complete factor list:
1. **Global AI Instructions** — Teacher's global notes from Settings
2. **Assignment Grading Notes** — Per-assignment expected answers, vocab definitions, summary key points
3. **Custom Rubric** — Categories, weights, descriptions from Settings
4. **Rubric Type Override** — cornell-notes, fill-in-blank, standard (per assignment)
5. **Grading Style** — lenient/standard/strict (affects AI prompt + score caps)
6. **IEP/504 Accommodations** — Per-student modified expectations
7. **Student History** — Past scores, streaks, improvement trends
8. **Class Period Differentiation** — Honors vs regular expectations
9. **Expected Answers** — Matched by question number, text, term, or index
10. **Grade Level & Subject** — Age-appropriate expectations
11. **Section Type** — vocab_term, numbered_question, fitb, summary, written
12. **Section Name & Points** — Marker section + per-question point allocation
13. **Student Actual Answers** — Literal text for specific feedback
14. **ELL Language** — Feedback translation for ELL students
15. **Effort Points & Completeness Caps** — Missing sections cap max score
16. **Assignment Template** — Strips prompt text from extracted responses
17. **FITB Exemption** — Fill-in-blank exempt from AI/plagiarism detection
18. **Writing Style Profile** — Historical patterns for detection

### Key code locations:
- Factor accumulation: `backend/app.py` lines 982-1126 (`file_ai_notes`)
- Rubric formatting: `backend/app.py` `format_rubric_for_prompt()`
- Per-question grading: `assignment_grader.py` `grade_per_question()`
- Feedback generation: `assignment_grader.py` `generate_feedback()`
- Multipass orchestration: `assignment_grader.py` `grade_multipass()`
- Single-pass (Claude/Gemini): `assignment_grader.py` `grade_assignment()`

---

## Code Style

### JavaScript (Embedded React)

```javascript
// GOOD: Single-line style for inline JSX
<button onClick={() => doSomething()} style={{ padding: '10px' }}>Click</button>

// GOOD: Use String.fromCharCode(10) for newlines in strings
const nl = String.fromCharCode(10);
const text = 'Line 1' + nl + 'Line 2';

// BAD: Multi-line strings with \n (causes Babel parse errors)
const text = 'Line 1\nLine 2';  // NEVER DO THIS

// GOOD: String concatenation for complex strings
const html = '<h1>' + title + '</h1><p>' + content + '</p>';

// BAD: Template literals with backticks (can break in embedded context)
const html = `<h1>${title}</h1>`;  // AVOID
```

### Python (Flask Backend)

```python
# GOOD: Use explicit imports
from dotenv import load_dotenv
import json
import os

# GOOD: Load .env with override
load_dotenv(os.path.join(app_dir, '.env'), override=True)

# GOOD: Thread-safe state management
grading_state = {
    "is_running": False,
    "log": [],
    "results": []
}

# BAD: Global mutable state without locks for critical sections
```

---

## Prohibited Patterns

### JavaScript/React

1. **NO multi-line string literals**
   ```javascript
   // NEVER DO THIS - causes Babel syntax errors
   const str = 'line 1
   line 2';

   // DO THIS INSTEAD
   const nl = String.fromCharCode(10);
   const str = 'line 1' + nl + 'line 2';
   ```

2. **NO template literals with newlines**
   ```javascript
   // AVOID - can break in embedded context
   const html = `
     <div>
       ${content}
     </div>
   `;

   // DO THIS
   const html = '<div>' + content + '</div>';
   ```

3. **NO unclosed JSX tags**
   - Always verify matching opening/closing tags
   - Use React Fragments `<>...</>` for adjacent elements

4. **NO Icon components inside button onClick handlers**
   - Icons in buttons can block click events
   - Put Icon as child, not in onClick

### Python

1. **NO hardcoded API keys**
   ```python
   # NEVER
   api_key = "sk-..."

   # ALWAYS
   api_key = os.getenv("OPENAI_API_KEY")
   ```

2. **NO database operations in `__init__` methods**

3. **NO blocking operations in Flask routes**
   - Use threading for long-running tasks like grading

---

## Best Practices

### State Management

```javascript
// Track loaded assignment by filename, not title
const [loadedAssignmentName, setLoadedAssignmentName] = useState('');

// Clear state when importing new document
setLoadedAssignmentName('');

// Compare using filename for highlighting
background: loadedAssignmentName === name ? 'selected' : 'default'
```

### API Endpoints

```python
@app.route('/api/endpoint', methods=['POST'])
def endpoint():
    try:
        data = request.json
        # Validate input
        if not data.get('required_field'):
            return jsonify({"error": "Missing required field"})

        # Process
        result = process(data)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"error": str(e)})
```

### File Operations

```python
# Always use expanduser for user config paths
config_path = os.path.expanduser("~/.graider_settings.json")

# Create directories if needed
os.makedirs(output_folder, exist_ok=True)

# Use Path for cross-platform compatibility
from pathlib import Path
filepath = Path(folder) / filename
```

### Grading Thread

```python
def run_grading_thread(folder, config):
    global grading_state
    grading_state["is_running"] = True

    try:
        # Do work
        for file in files:
            if grading_state.get("stop_requested"):
                break
            # Process file
            grading_state["log"].append(f"Processing {file}")
    finally:
        grading_state["is_running"] = False
```

---

## Common Issues & Fixes

### "Unterminated string constant" Error
**Cause**: Multi-line strings or escape characters in embedded JavaScript
**Fix**: Use `String.fromCharCode(10)` for newlines, string concatenation for multi-line

### "Adjacent JSX elements must be wrapped" Error
**Cause**: Two sibling elements without a parent wrapper
**Fix**: Wrap in `<div>` or `<>...</>` fragment

### Button onClick not working
**Cause**: Often Icon component or styling blocking clicks
**Fix**: Simplify button, test with just `onClick={() => alert('test')}`

### State not updating in UI
**Cause**: State reference not changing or stale closure
**Fix**: Spread operator for new object `{...oldState, newField: value}`

### Assignment config not matching files
**Cause**: Filename sanitization differs from title
**Fix**: Use `loadedAssignmentName` to track by filename, not title

---

## Testing Checklist

Before committing changes:

1. [ ] App starts without Babel errors: `python graider_app.py`
2. [ ] All tabs render (Home, Results, Builder, Planner, Settings)
3. [ ] Can import document in Builder
4. [ ] Can save/load assignment configs
5. [ ] Grading starts and produces results
6. [ ] No console errors in browser DevTools

---

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Run app
python graider_app.py
# Opens at http://localhost:3000
```

---

## API Reference

### Grading
- `POST /api/grade` - Start grading job
- `GET /api/status` - Get grading status/progress
- `POST /api/stop-grading` - Stop current grading

### Assignments
- `GET /api/list-assignments` - List saved configs
- `GET /api/load-assignment?name=X` - Load specific config
- `POST /api/save-assignment-config` - Save config
- `DELETE /api/delete-assignment?name=X` - Delete config

### Settings
- `GET /api/load-rubric` - Load rubric
- `POST /api/save-rubric` - Save rubric
- `GET /api/load-global-settings` - Load global AI notes
- `POST /api/save-global-settings` - Save global AI notes

### Documents
- `POST /api/parse-document` - Parse uploaded Word/PDF
- `POST /api/export-assignment` - Export to Word/PDF

### Lesson Planner
- `POST /api/get-standards` - Get curriculum standards
- `POST /api/generate-lesson-plan` - Generate AI lesson plan
- `POST /api/export-lesson-plan` - Export to Word

---

## Performance Notes

- Grading runs in background thread to keep UI responsive
- Auto-save rubric uses 500ms debounce
- Status polling every 500ms during grading
- Large files (>10MB) may timeout on parse

---

*Last updated: January 2025*
