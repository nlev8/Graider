# Combined Implementation Plan: Trusted Regrade Fix + Model Answers

---

# Part 1: Fix Trusted Regrade to Use Multi-Pass Pipeline

## Context

Trusted students currently bypass the multi-pass grading pipeline entirely. When a student is trusted (or regraded via the Trust+Regrade button), `app.py` routes them to `grade_assignment()` (single-pass) instead of `grade_multipass()`. This causes:

1. **Inferior scoring accuracy** — single-pass grading is less consistent than per-question grading
2. **Missing section detection failure** — `grade_assignment()` relies on AI to populate `unanswered_questions`, which is unreliable (the Madelyn Ann Parrish bug)
3. **No student history injection** — `grade_assignment()` call doesn't pass `student_history`
4. **Lower feedback quality** — single-pass produces generic feedback vs. per-question specifics

The fix: trusted students should use `grade_multipass()` directly (same as non-trusted), just skip detection. FITB assignments genuinely need single-pass and stay on `grade_assignment()`.

## Key Files

| File | Change |
|------|--------|
| `backend/app.py` ~line 1446 | Split `skip_detection` into `is_trusted` → `grade_multipass()` vs `is_fitb` → `grade_assignment()` |

## Step 1: Change the skip_detection branch

**File:** `backend/app.py` (lines 1446–1461)

**Replace this:**
```python
                elif skip_detection:
                    # Trusted student or FITB: Use direct grading without detection
                    grade_result = grade_assignment(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
                        rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style=grading_style,
                        rubric_weights=file_rubric_weights
                    )
                    # Set detection to "none"
                    if is_trusted:
                        grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "Trusted writer - detection skipped"}
                        grade_result['plagiarism_detection'] = {"flag": "none", "reason": "Trusted writer - detection skipped"}
                    else:
                        grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "N/A - Fill-in-the-blank"}
                        grade_result['plagiarism_detection'] = {"flag": "none", "reason": "N/A - Fill-in-the-blank"}
```

**With this:**
```python
                elif is_trusted:
                    # Trusted student: Use full multi-pass pipeline, skip detection only
                    grade_result = grade_multipass(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ai_model, student_info.get('student_id'),
                        assignment_template_local, rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style,
                        student_history=history_context, rubric_weights=file_rubric_weights
                    )
                    grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "Trusted writer - detection skipped"}
                    grade_result['plagiarism_detection'] = {"flag": "none", "reason": "Trusted writer - detection skipped"}
                elif skip_detection:
                    # FITB only: Use single-pass (genuinely needs it)
                    grade_result = grade_assignment(
                        student_info['student_name'], grade_data, file_ai_notes,
                        grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
                        rubric_prompt, file_markers, file_exclude_markers,
                        marker_config, effort_points, extraction_mode, grading_style=grading_style,
                        rubric_weights=file_rubric_weights
                    )
                    grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "N/A - Fill-in-the-blank"}
                    grade_result['plagiarism_detection'] = {"flag": "none", "reason": "N/A - Fill-in-the-blank"}
```

**Why this works:**
- `is_trusted` is checked first → routes to `grade_multipass()` with identical params as the normal `grade_with_parallel_detection()` path (lines 4233-4238), including `student_history=history_context`
- `skip_detection` (which is `is_trusted or is_fitb`) only triggers for FITB after `is_trusted` is handled
- Detection flags are set to "none"/"skipped" exactly as before
- `grade_multipass()` has deterministic extraction, per-question grading, and proper completeness caps — the Madelyn Parrish bug is impossible in this path

## Step 2: Add grade_multipass to imports

**File:** `backend/app.py` (line 705)

`grade_multipass` is NOT currently imported. Add it to the existing import block:

**Replace:**
```python
            extract_student_work, grade_assignment, grade_with_parallel_detection,
```

**With:**
```python
            extract_student_work, grade_assignment, grade_multipass, grade_with_parallel_detection,
```

## Verification

1. Trust a student → regrade via Trust button → console should show multi-pass output (extraction pass, per-question grading, feedback generation) instead of single "Grading with gpt-4o-mini..."
2. Regrade Madelyn Ann Parrish's Cornell Notes (missing Summary) → `unanswered_questions` should contain "SUMMARY"
3. FITB assignment → should still use `grade_assignment()` (single-pass)
4. Detection flags for trusted student → `"none"` / `"Trusted writer - detection skipped"`

---
---

# Part 2: Model Answers Feature

## Context

Teachers need AI-generated model answers per assignment section so the grading engine can compare student responses against them. Currently expected answers only exist as free text in `gradingNotes` (manually typed), parsed by `_parse_expected_answers()`. The worksheet generator already populates these for generated worksheets, but imported assignments get nothing — the teacher must manually type expected answers or the AI grades blind.

This feature: teacher clicks "Generate Model Answers" in Grading Setup → AI produces grade-appropriate model answers per section → shown as editable previews → stored on config → injected into the grading pipeline.

**This augments the existing pipeline.** Model answers are formatted into `file_ai_notes` alongside manual `gradingNotes`, flowing through the same `_parse_expected_answers()` → `grade_per_question(expected_answer=...)` path. Zero grading engine changes.

---

## Key Files

| File | Change |
|------|--------|
| `backend/routes/assignment_routes.py` | New `POST /api/generate-model-answers` endpoint |
| `backend/app.py` ~line 1172 | Inject `modelAnswers` into `file_ai_notes` at grading time |
| `frontend/src/App.jsx` | Generate button + editable previews in Grading Setup |

---

## Step 1: Backend endpoint

**File:** `backend/routes/assignment_routes.py` (after `save_assignment_config`, ~line 48)

```python
@assignment_bp.route('/api/generate-model-answers', methods=['POST'])
def generate_model_answers():
    """Generate AI model answers for each section/marker in an assignment config."""
    data = request.json
    markers = data.get('customMarkers', [])
    doc_text = data.get('documentText', '')
    title = data.get('title', 'Assignment')
    grade_level = data.get('grade_level', '7')
    subject = data.get('subject', 'Social Studies')
    global_notes = data.get('globalAINotes', '')

    if not markers:
        return jsonify({"error": "No sections/markers configured"}), 400
    if not doc_text:
        return jsonify({"error": "Import the assignment document first."}), 400

    sections_desc = []
    for i, m in enumerate(markers):
        if isinstance(m, dict):
            name = m.get('start', f'Section {i+1}')
            sec_type = m.get('type', 'written')
            points = m.get('points', 10)
            sections_desc.append(f"- {name} (type: {sec_type}, {points} pts)")
        else:
            sections_desc.append(f"- {m}")

    prompt = f"""You are a {subject} teacher creating a model answer key for a {grade_level}th grade assignment.

ASSIGNMENT: {title}

DOCUMENT TEXT (the actual assignment students receive):
{doc_text[:8000]}

SECTIONS TO ANSWER:
{chr(10).join(sections_desc)}

{f"TEACHER INSTRUCTIONS (follow these for tone/expectations):{chr(10)}{global_notes}" if global_notes else ""}

For EACH section listed above, generate the MODEL ANSWER a strong {grade_level}th grade student would write.
Use the section type (vocabulary, written, short_answer, math_equation, etc.) and the subject ({subject}) to determine the appropriate format.

RULES:
- Match the grade level — use age-appropriate vocabulary and complexity for a {grade_level}th grader
- Match the SUBJECT — a Math model answer needs worked steps/equations, a Science answer needs observations/data/conclusions, an ELA answer needs textual evidence/analysis, a History answer needs facts/context/significance
- Use the DOCUMENT TEXT to derive correct, specific answers — reference actual content from the assignment
- For vocabulary/definitions: student-friendly language, not textbook definitions
- For written/summary sections: demonstrate understanding, not copy the text
- For math/equations: show work and final answer
- For fill-in-the-blank: provide the correct word/phrase
- These model what a GOOD student would write, not a perfect adult answer

Return ONLY valid JSON:
{{
    "model_answers": [
        {{"section": "<exact section/marker name>", "answer": "<model answer text>"}}
    ]
}}"""

    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.3
        )
        response_text = response.choices[0].message.content.strip()
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            start = 1
            end = len(lines)
            for i in range(len(lines)-1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            response_text = '\n'.join(lines[start:end])
        result = json.loads(response_text)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response. Try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

---

## Step 2: Grading integration

**File:** `backend/app.py` (~line 1172, right after `file_notes` is appended to `file_ai_notes`)

Insert after the existing block at line 1171:
```python
if file_notes:
    file_ai_notes += f"\n\nASSIGNMENT-SPECIFIC INSTRUCTIONS:\n{file_notes}"
```

Add:
```python
# Inject model answers from config (if generated)
model_answers = matched_config.get('modelAnswers', {}) if matched_config else {}
if model_answers:
    ma_lines = ["\nMODEL ANSWERS (compare student responses against these):"]
    for section_name, answer_text in model_answers.items():
        ma_lines.append(f"- {section_name}: {answer_text}")
    file_ai_notes += "\n".join(ma_lines)
    print(f"  ✓ Applying Model Answers ({len(model_answers)} sections)")
```

This works because:
- `_parse_expected_answers()` already handles `"- Term: definition"` format
- `grade_per_question()` matches expected answers by section name (strategy 2, line 5126)
- Single-pass sees model answers in `custom_ai_instructions` as teacher instructions

---

## Step 3: Frontend

**File:** `frontend/src/App.jsx`

### 3a. Loading state (~line 1330, near assignment state)

```javascript
const [modelAnswersLoading, setModelAnswersLoading] = useState(false);
```

### 3b. Generate function (near other assignment handlers)

```javascript
const generateModelAnswers = async () => {
    if (!importedDoc || !importedDoc.text) {
        addToast("Import the assignment document first", "warning");
        return;
    }
    if (!assignment.customMarkers || assignment.customMarkers.length === 0) {
        addToast("Add section markers first", "warning");
        return;
    }
    setModelAnswersLoading(true);
    try {
        var settingsResp = {};
        try { settingsResp = await api.loadGlobalSettings(); } catch(e) {}
        var settings = (settingsResp && settingsResp.settings) || {};
        var resp = await fetch("/api/generate-model-answers", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                customMarkers: assignment.customMarkers,
                documentText: importedDoc.text,
                title: assignment.title,
                grade_level: config.grade_level || "7",
                subject: config.subject || "Social Studies",
                globalAINotes: settings.globalAINotes || ""
            })
        });
        var data = await resp.json();
        if (data.error) { addToast(data.error, "error"); return; }
        var answers = {};
        (data.model_answers || []).forEach(function(ma) {
            answers[ma.section] = ma.answer;
        });
        setAssignment(function(prev) { return Object.assign({}, prev, { modelAnswers: answers }); });
        addToast("Model answers generated! Review and edit below.", "success");
    } catch (err) {
        addToast("Failed: " + err.message, "error");
    } finally {
        setModelAnswersLoading(false);
    }
};
```

### 3c. Generate button (after markers list, before gradingNotes textarea ~line 18501)

```jsx
{assignment.customMarkers && assignment.customMarkers.length > 0
 && importedDoc && importedDoc.text && (
    <div style={{ marginTop: "12px", marginBottom: "12px" }}>
        <button className="btn btn-secondary" onClick={generateModelAnswers}
            disabled={modelAnswersLoading}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {modelAnswersLoading
                ? React.createElement(React.Fragment, null,
                    React.createElement(Loader2, {size:14, className:"spinning"}), " Generating...")
                : React.createElement(React.Fragment, null,
                    React.createElement(Sparkles, {size:14}), " Generate Model Answers")}
        </button>
        {assignment.modelAnswers && Object.keys(assignment.modelAnswers).length > 0 && (
            <span style={{ marginLeft: "8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                {Object.keys(assignment.modelAnswers).length + " sections answered"}
            </span>
        )}
    </div>
)}
```

### 3d. Editable preview below each marker

Below each marker row (in section-points mode ~line 18257, and basic mode ~line 7046), add the model answer preview. The marker name is `m.start || m` depending on format:

```jsx
{/* Model answer preview */}
{assignment.modelAnswers && assignment.modelAnswers[markerName] && (
    <div style={{ marginTop: "4px", marginLeft: "24px", marginBottom: "8px" }}>
        <label style={{ fontSize: "11px", color: "var(--text-secondary)",
            display: "block", marginBottom: "2px" }}>
            Model Answer:
        </label>
        <textarea className="input"
            value={assignment.modelAnswers[markerName]}
            onChange={function(e) {
                var updated = Object.assign({}, assignment.modelAnswers);
                updated[markerName] = e.target.value;
                setAssignment(function(prev) {
                    return Object.assign({}, prev, { modelAnswers: updated });
                });
            }}
            style={{ fontSize: "12px", minHeight: "60px",
                backgroundColor: "var(--bg-tertiary)", opacity: 0.9 }}
        />
    </div>
)}
```

Where `markerName` = `typeof m === 'string' ? m : m.start`

---

## Data Flow

```
Generate:  Button → POST /api/generate-model-answers → gpt-4o-mini → JSON
Store:     assignment.modelAnswers = { "VOCABULARY": "...", "SUMMARY": "..." }
Save:      Auto-saved to ~/.graider_assignments/Title.json (merge-save)
Display:   Editable textareas below each marker in Grading Setup
Grade:     app.py loads modelAnswers → appends to file_ai_notes →
           _parse_expected_answers() extracts them →
           grade_per_question(expected_answer=...) compares student vs model
```

---

## Verification

1. Import Cornell Notes doc → add VOCABULARY/QUESTIONS/SUMMARY markers → click Generate
2. Model answers appear below each marker, grade-appropriate per Global AI Instructions
3. Edit a model answer → auto-saves with config
4. Grade student → console shows `✓ Applying Model Answers (3 sections)`
5. Student who wrote "What I wrote" for Summary → gets low score with feedback referencing what the summary should contain
6. Reload page → model answers persist from saved config
