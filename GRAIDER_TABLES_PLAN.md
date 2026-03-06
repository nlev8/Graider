# Extend Graider Tables to Assessment & Assignment Exports

## Context

Graider already has a reliable, near-deterministic extraction system for worksheets: hidden `[GRAIDER:TYPE:ID]` tags in 2-row Word tables. When students fill in these docs and submit them, extraction is structural (read table cell by tag ID) — no text matching, no fuzzy search, no marker leakage bugs.

**The problem:** Two export paths skip this system entirely:
- **Assessment export** (`/api/export-assessment`) — creates .docx with plain paragraphs + underscore lines
- **Assignment export** (`/api/export-generated-assignment`) — creates PDF via ReportLab (no structured extraction possible)

This plan extends the existing Graider table format to both paths. **No extraction code changes needed** — the existing pipeline already handles `GRAIDER:QUESTION:N` tags.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/routes/planner_routes.py` | Modify `export_assessment()`, add `_export_assignment_docx_graider()`, `_question_to_visual_dict()`, `_save_grading_config_for_export()` |
| `frontend/src/App.jsx` | Add "Export DOCX" buttons at 3 locations |
| No changes to: `worksheet_generator.py`, `assignment_grader.py`, `api.js` |

---

## Edit 1: Modify `export_assessment()` — add Graider tables

**File:** `backend/routes/planner_routes.py`

### Replace lines 4905-4983 with:

```python
    try:
        from docx import Document
        from docx.shared import Inches, Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import tempfile
        import base64
        from backend.services.worksheet_generator import _add_graider_table, _add_graider_marker
        from backend.services.document_generator import DEFAULT_STYLE

        doc = Document()
        style = dict(DEFAULT_STYLE)

        # Title
        title = doc.add_heading(assessment.get('title', 'Assessment'), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Header info
        header_info = doc.add_paragraph()
        header_info.add_run(f"Subject: {assessment.get('subject', '')}").bold = True
        header_info.add_run(f"    Grade: {assessment.get('grade', '')}")
        header_info.add_run(f"    Time: {assessment.get('time_estimate', '')}")
        header_info.add_run(f"    Total Points: {assessment.get('total_points', '')}")

        # Student info line
        doc.add_paragraph("Name: _________________________    Date: _____________    Period: _____")

        # Instructions
        if assessment.get('instructions'):
            inst = doc.add_paragraph()
            inst.add_run("Instructions: ").bold = True
            inst.add_run(assessment.get('instructions'))

        doc.add_paragraph()  # Space

        # Sections — use Graider tables for structured extraction
        global_q_num = 1
        for section in assessment.get('sections', []):
            # Section header
            sec_head = doc.add_heading(section.get('name', 'Section'), level=1)

            if section.get('instructions'):
                sec_inst = doc.add_paragraph()
                sec_inst.add_run(section.get('instructions')).italic = True

            # Questions
            for q in section.get('questions', []):
                q_num = q.get('number', global_q_num)
                q_text = q.get('question', '')
                q_points = q.get('points', 1)
                q_type = q.get('type', section.get('type', ''))

                # --- MC/TF: options as paragraphs above, small answer table ---
                if q.get('options'):
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_num}. ").bold = True
                    q_para.add_run(f"{q_text}")
                    for opt in q.get('options', []):
                        opt_para = doc.add_paragraph(f"    {opt}")
                        opt_para.paragraph_format.space_before = Pt(2)
                        opt_para.paragraph_format.space_after = Pt(2)
                    _add_graider_table(doc, f"Answer for Question {q_num}",
                                       f"GRAIDER:QUESTION:{q_num}", q_points, style, 720)

                # --- Matching: terms/defs above, answer table ---
                elif q.get('terms') and q.get('definitions'):
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_num}. ").bold = True
                    q_para.add_run(f"{q_text}")
                    doc.add_paragraph("Terms:")
                    for i, term in enumerate(q.get('terms', []), 1):
                        doc.add_paragraph(f"    {i}. {term}")
                    doc.add_paragraph("Definitions:")
                    for letter_idx, defn in enumerate(q.get('definitions', [])):
                        letter = chr(65 + letter_idx)
                        doc.add_paragraph(f"    {letter}. {defn}")
                    _add_graider_table(doc, f"Your Matches for Question {q_num}",
                                       f"GRAIDER:QUESTION:{q_num}", q_points, style, 1440)

                # --- Written: question in Graider table header ---
                else:
                    if q_type == 'extended_response':
                        height = 4320  # 3 inches
                    elif q_type == 'short_answer':
                        height = 2160  # 1.5 inches
                    else:
                        height = 2160  # default
                    _add_graider_table(doc, f"{q_num}. {q_text}",
                                       f"GRAIDER:QUESTION:{q_num}", q_points, style, height)

                global_q_num += 1

        # Add Graider marker BEFORE answer key
        _add_graider_marker(doc)
```

### Keep lines 4984-5023 unchanged (answer key page + save/encode logic)

The answer key page stays as-is — no Graider tables for teacher reference.

---

## Edit 2: Add `_question_to_visual_dict()` helper

**File:** `backend/routes/planner_routes.py`

### Insert before `export_generated_assignment()` (before line 3544):

```python
def _question_to_visual_dict(q):
    """Convert a planner question dict to a visual dict compatible with _embed_visual().

    Returns None if the question type has no visual component.
    """
    q_type = q.get('question_type', q.get('visual_type', ''))
    if not q_type:
        return None

    if q_type == 'number_line':
        return {
            'type': 'number_line',
            'min': q.get('min_val', q.get('number_line_min', -10)),
            'max': q.get('max_val', q.get('number_line_max', 10)),
            'points': [],
            'title': '', 'blank': True,
        }
    elif q_type == 'coordinate_plane':
        return {
            'type': 'coordinate_plane',
            'x_range': q.get('x_range', [-6, 6]),
            'y_range': q.get('y_range', [-6, 6]),
            'points': [],
            'title': '', 'blank': True,
        }
    elif q_type in ('geometry', 'triangle', 'pythagorean', 'trig', 'angles', 'similarity'):
        return {
            'type': 'shape', 'shape_type': 'triangle',
            'base': q.get('base', 6), 'height': q.get('height', 4),
            'title': '', 'blank': True,
        }
    elif q_type == 'rectangle':
        return {
            'type': 'shape', 'shape_type': 'rectangle',
            'width': q.get('base', q.get('width', 6)), 'height': q.get('height', 4),
            'title': '', 'blank': True,
        }
    elif q_type == 'circle':
        return {
            'type': 'circle',
            'radius': q.get('radius', 5),
            'show_radius': True, 'blank': True,
        }
    elif q_type == 'box_plot':
        return {
            'type': 'box_plot',
            'data': q.get('data', [[50, 60, 70, 80, 90]]),
            'labels': q.get('data_labels', []),
            'blank': False,
        }
    elif q_type == 'function_graph':
        return {
            'type': 'function_graph',
            'expressions': q.get('expressions', [q.get('expression', 'x')]),
            'x_range': q.get('x_range', (-10, 10)),
            'y_range': q.get('y_range'),
            'title': '', 'blank': True,
        }
    elif q_type in ('polygon', 'regular_polygon'):
        return {
            'type': 'polygon',
            'sides': q.get('sides', 5),
            'side_length': q.get('side_length', 4),
            'title': '', 'blank': True,
        }
    elif q_type == 'histogram':
        return {
            'type': 'histogram',
            'data': q.get('data', []),
            'bins': q.get('bins', 10),
            'title': '', 'x_label': q.get('x_label', ''),
            'y_label': 'Frequency', 'blank': False,
        }
    elif q_type == 'pie_chart':
        return {
            'type': 'pie_chart',
            'categories': q.get('categories', []),
            'values': q.get('values', []),
            'title': '', 'blank': False,
        }
    elif q_type == 'dot_plot':
        return {
            'type': 'dot_plot',
            'categories': q.get('categories'),
            'dots': q.get('dots'),
            'min_val': q.get('min_val', 0), 'max_val': q.get('max_val', 10),
            'title': '', 'blank': False,
        }
    elif q_type == 'stem_and_leaf':
        return {
            'type': 'stem_and_leaf',
            'data': q.get('data', []),
            'title': '', 'blank': False,
        }
    elif q_type == 'venn_diagram':
        return {
            'type': 'venn_diagram',
            'sets': q.get('sets', 2),
            'labels': q.get('labels'),
            'regions': q.get('regions'),
            'title': '', 'blank': True,
        }
    elif q_type in ('protractor', 'angle_protractor'):
        return {
            'type': 'protractor',
            'given_angle': q.get('given_angle', 45),
            'blank': True,
        }
    return None
```

---

## Edit 3: Add `_export_assignment_docx_graider()` helper

**File:** `backend/routes/planner_routes.py`

### Insert after `_question_to_visual_dict()` (before `export_generated_assignment()`):

```python
def _export_assignment_docx_graider(assignment, output_folder, safe_title):
    """Export a generated assignment as .docx with Graider structured tables.

    Student version only — answer keys should use PDF.
    Returns filepath of the saved .docx.
    """
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from backend.services.worksheet_generator import (
        _add_graider_table, _add_graider_marker, _embed_visual
    )
    from backend.services.document_generator import DEFAULT_STYLE

    doc = Document()
    style = dict(DEFAULT_STYLE)

    title = assignment.get('title', 'Assignment')
    instructions = assignment.get('instructions', '')
    sections = assignment.get('sections', [])
    total_points = assignment.get('total_points', 100)
    time_estimate = assignment.get('time_estimate', '')

    # Title
    heading = doc.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Student info
    doc.add_paragraph("Name: _______________________  Date: _______________  Period: _____")

    # Meta info
    meta_parts = []
    if time_estimate:
        meta_parts.append(f"Time: {time_estimate}")
    if total_points:
        meta_parts.append(f"Total Points: {total_points}")
    if meta_parts:
        doc.add_paragraph("    ".join(meta_parts))

    # Instructions
    if instructions:
        inst = doc.add_paragraph()
        inst.add_run("Instructions: ").bold = True
        inst.add_run(instructions)

    doc.add_paragraph()  # spacer

    question_num = 1

    for section in sections:
        section_name = section.get('name', 'Section')
        section_points = section.get('points', 0)
        section_type = section.get('type', 'short_answer')
        questions = section.get('questions', [])

        # Section header
        pts_text = f" ({section_points} points)" if section_points else ""
        doc.add_heading(f"{section_name}{pts_text}", level=1)

        for q in questions:
            q_number = q.get('number', question_num)
            q_text = q.get('question', '')
            q_points = q.get('points', 0)
            q_options = q.get('options', [])
            q_type = q.get('question_type', section_type)

            # --- MC/TF: options above, small answer table ---
            if q_options:
                q_para = doc.add_paragraph()
                q_para.add_run(f"{q_number}. ").bold = True
                q_para.add_run(q_text)
                for opt in q_options:
                    opt_para = doc.add_paragraph(f"    {opt}")
                    opt_para.paragraph_format.space_before = Pt(2)
                    opt_para.paragraph_format.space_after = Pt(2)
                _add_graider_table(doc, f"Answer for Question {q_number}",
                                   f"GRAIDER:QUESTION:{q_number}", q_points, style, 720)

            # --- Matching: terms/defs above, answer table ---
            elif q.get('terms') and q.get('definitions'):
                q_para = doc.add_paragraph()
                q_para.add_run(f"{q_number}. ").bold = True
                q_para.add_run(q_text)
                doc.add_paragraph("Terms:")
                for i, term in enumerate(q.get('terms', []), 1):
                    doc.add_paragraph(f"    {i}. {term}")
                doc.add_paragraph("Definitions:")
                for idx, defn in enumerate(q.get('definitions', [])):
                    letter = chr(65 + idx)
                    doc.add_paragraph(f"    {letter}. {defn}")
                _add_graider_table(doc, f"Your Matches for Question {q_number}",
                                   f"GRAIDER:QUESTION:{q_number}", q_points, style, 1440)

            # --- Data table: visible table above, answer table below ---
            elif q_type == 'data_table':
                q_para = doc.add_paragraph()
                q_para.add_run(f"{q_number}. ").bold = True
                q_para.add_run(q_text)

                headers = q.get('headers', q.get('column_headers', ['Column 1', 'Column 2']))
                row_labels = q.get('row_labels', [])
                num_rows = q.get('num_rows', 5)
                cols = len(headers) + (1 if row_labels else 0)
                tbl = doc.add_table(rows=num_rows + 1, cols=cols)
                tbl.style = 'Table Grid'
                offset = 1 if row_labels else 0
                for hi, h in enumerate(headers):
                    tbl.rows[0].cells[hi + offset].text = h
                if row_labels:
                    for ri in range(min(num_rows, len(row_labels))):
                        tbl.rows[ri + 1].cells[0].text = row_labels[ri]
                doc.add_paragraph()
                _add_graider_table(doc, f"Data entries for Question {q_number}",
                                   f"GRAIDER:QUESTION:{q_number}", q_points, style, 1440)

            # --- All other types: optional visual above, Graider table below ---
            else:
                # Embed visual element if applicable
                visual_dict = _question_to_visual_dict(q)
                if visual_dict:
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_number}. ").bold = True
                    q_para.add_run(q_text)
                    try:
                        _embed_visual(doc, visual_dict)
                    except Exception as ve:
                        print(f"  Warning: Could not render visual for Q{q_number}: {ve}")

                # Determine height by question type
                if q_type in ('extended_response', 'essay'):
                    height = 4320  # 3 inches
                elif q_type == 'math_equation':
                    height = 2880  # 2 inches
                elif q_type in ('multiple_choice', 'true_false'):
                    height = 720   # 0.5 inch
                elif q_type == 'coordinates':
                    height = 1440  # 1 inch
                else:
                    height = 2160  # 1.5 inches (short_answer default)

                # If visual was shown, use "Your Answer" as header; otherwise include question text
                if visual_dict:
                    header_text = f"Your Answer for Question {q_number}"
                else:
                    header_text = f"{q_number}. {q_text}"
                _add_graider_table(doc, header_text,
                                   f"GRAIDER:QUESTION:{q_number}", q_points, style, height)

            question_num += 1

    # Add Graider marker
    _add_graider_marker(doc)

    # Save
    filename = f"{safe_title}_Student.docx"
    filepath = os.path.join(output_folder, filename)
    doc.save(filepath)
    return filepath
```

---

## Edit 4: Modify `export_generated_assignment()` to support .docx format

**File:** `backend/routes/planner_routes.py`

### Replace lines 3558-3603 with:

```python
    try:
        title = assignment.get('title', 'Assignment')
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
        output_folder = os.path.expanduser("~/Downloads/Graider/Assignments")
        os.makedirs(output_folder, exist_ok=True)

        # Student .docx with Graider tables (for digital submission + structured grading)
        if format_type == 'docx' and not include_answers:
            filepath = _export_assignment_docx_graider(assignment, output_folder, safe_title)
            subprocess.run(['open', filepath])
            return jsonify({"status": "success", "path": filepath})

        # PDF path (for printing and answer keys) — existing ReportLab code below
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.colors import black, gray, lightgrey, red, green
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image,
            Table, TableStyle, PageBreak, KeepTogether
        )
        import io

        # Set up styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            alignment=TA_CENTER, fontSize=18, spaceAfter=6
        )
        heading_style = ParagraphStyle(
            'CustomHeading', parent=styles['Heading2'],
            fontSize=14, spaceAfter=6, spaceBefore=12
        )
        normal_style = styles['Normal']
        bold_style = ParagraphStyle(
            'Bold', parent=styles['Normal'],
            fontName='Helvetica-Bold'
        )
        center_style = ParagraphStyle(
            'Center', parent=styles['Normal'],
            alignment=TA_CENTER
        )
        answer_style = ParagraphStyle(
            'Answer', parent=styles['Normal'],
            fontName='Helvetica-Bold', textColor=green
        )

        # Build the PDF
        suffix = "_ANSWER_KEY" if include_answers else "_Student"
        filename = f"{safe_title}{suffix}.pdf"
        filepath = os.path.join(output_folder, filename)

        doc = SimpleDocTemplate(
            filepath, pagesize=letter,
```

(Existing PDF code continues from the original line 3603 onwards — the `doc = SimpleDocTemplate(` line. The `title`, `instructions`, `sections`, `total_points`, `time_estimate` local variables are now set before the format branch, so they're available to both paths.)

### Also move the variable declarations from lines 3552-3556 BEFORE the try block:

The original code has:
```python
    title = assignment.get('title', 'Assignment')
    instructions = assignment.get('instructions', '')
    sections = assignment.get('sections', [])
    total_points = assignment.get('total_points', 100)
    time_estimate = assignment.get('time_estimate', '')
```

These are already on lines 3552-3556, before the `try:` on line 3558. They remain as-is since the new code uses them.

---

## Edit 5: Add `_save_grading_config_for_export()` helper

**File:** `backend/routes/planner_routes.py`

### Insert near the other helper functions (before `export_generated_assignment()`):

```python
def _save_grading_config_for_export(assessment_or_assignment):
    """Save a grading config to ~/.graider_assignments/ for a Graider-table .docx export.

    Builds the config format expected by the grading pipeline so the teacher
    doesn't have to manually set up the assignment in the Builder.
    """
    import time

    title = assessment_or_assignment.get('title', 'Untitled')
    safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in title).strip()

    # Build grading notes from answer key
    grading_notes_parts = []
    answer_key = assessment_or_assignment.get('answer_key', {})
    for q_num_str, answer_data in sorted(answer_key.items(),
                                          key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        if isinstance(answer_data, dict):
            ans = answer_data.get('answer', '')
            explanation = answer_data.get('explanation', '')
            grading_notes_parts.append(f"Q{q_num_str}: {ans}")
            if explanation:
                grading_notes_parts.append(f"  Explanation: {explanation}")
        else:
            grading_notes_parts.append(f"Q{q_num_str}: {answer_data}")

    # Also pull expected answers from sections/questions
    sections = assessment_or_assignment.get('sections', [])
    q_idx = 0
    for section in sections:
        for q in section.get('questions', []):
            q_idx += 1
            q_answer = q.get('answer', '')
            if q_answer and str(q_idx) not in answer_key:
                grading_notes_parts.append(f"Q{q_idx}: {q_answer}")

    config = {
        "title": title,
        "subject": assessment_or_assignment.get('subject', ''),
        "totalPoints": assessment_or_assignment.get('total_points', 100),
        "instructions": assessment_or_assignment.get('instructions', ''),
        "aliases": [],
        "customMarkers": [],
        "excludeMarkers": [],
        "gradingNotes": "\n".join(grading_notes_parts),
        "rubricType": "standard",
        "useSectionPoints": True,
        "tableStructured": True,
        "tableVersion": "v1",
        "effortPoints": 15,
    }

    config_dir = os.path.expanduser("~/.graider_assignments")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, f"{safe_title}.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    return safe_title
```

### Call it from both export paths:

In `export_assessment()`, after the `_add_graider_marker(doc)` call:
```python
        _save_grading_config_for_export(assessment)
```

In `_export_assignment_docx_graider()`, after `_add_graider_marker(doc)`:
```python
    _save_grading_config_for_export(assignment)
```

---

## Edit 6: Frontend — Add "Export DOCX" buttons

**File:** `frontend/src/App.jsx`

### Location 1 (line ~21822): After the "Export PDF" button for lesson plan assignments

Insert after the closing `</button>` tag on line 21822:

```jsx
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "docx", false);
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Gradeable DOCX exported!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export as Word doc with structured answer tables for reliable grading"
                                  >
                                    <Icon name="FileText" size={16} /> Gradeable DOCX
                                  </button>
```

### Location 2 (line ~21917): After the "Export PDF" button for generated assignments

Insert after the closing `</button>` tag on line 21917:

```jsx
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "docx", false);
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Gradeable DOCX exported!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export as Word doc with structured answer tables for reliable grading"
                                  >
                                    <Icon name="FileText" size={16} /> Gradeable DOCX
                                  </button>
```

### Location 3 (line ~22533): After the "Export PDF" button in the assignment builder

Insert after the closing `</button>` tag on line 22533:

```jsx
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "docx", false);
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Gradeable DOCX exported!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export as Word doc with structured answer tables for reliable grading"
                                  >
                                    <Icon name="FileText" size={16} /> Gradeable DOCX
                                  </button>
```

---

## Caveats Addressed

### Config overwrite prevention
`_save_grading_config_for_export()` writes to `{title}.json`. If a teacher re-exports "Quiz" after editing questions, the config SHOULD overwrite — it reflects the latest version. But if they have two different assessments both titled "Quiz", one clobbers the other. Fix: append a short hash of the assessment content to the filename:
```python
    import hashlib
    content_hash = hashlib.md5(json.dumps(assessment_or_assignment, sort_keys=True).encode()).hexdigest()[:6]
    config_path = os.path.join(config_dir, f"{safe_title}_{content_hash}.json")
```

### Missing visual types handled gracefully
`_question_to_visual_dict()` returns `None` for unsupported types. The calling code wraps `_embed_visual()` in a try/except and prints a warning — the question text and Graider answer table still render, just without the diagram. No crash.

### Frontend spinner / double-click protection
Add `disabled` state to the DOCX buttons while export is in progress. Use a local ref or state variable:
```jsx
const [exportingDocx, setExportingDocx] = useState(false);
// In onClick: setExportingDocx(true); try { ... } finally { setExportingDocx(false); }
// On button: disabled={exportingDocx}
```

### File size for visual-heavy exports
`_embed_visual()` renders matplotlib figures to PNG at screen DPI (~100). For a 25-question assignment with visuals, the .docx will be ~2-5MB — reasonable for Word. No special handling needed.

### ReportLab stays optional
ReportLab imports are inside the PDF branch (`if format_type != 'docx'`). The .docx branch only imports python-docx and worksheet_generator, which are already required dependencies.

---

## No Changes Required

- **`backend/services/worksheet_generator.py`** — `_add_graider_table()`, `_add_graider_marker()`, `_embed_visual()` are imported and used as-is
- **`assignment_grader.py`** — `read_docx_file_structured()` and `extract_from_tables()` already handle `GRAIDER:QUESTION:N` tags
- **`frontend/src/services/api.js`** — `exportGeneratedAssignment()` already accepts a `format` parameter
- **Assessment "Word Doc" button** — already exports .docx; the backend change (Edit 1) adds Graider tables automatically

---

## Verification

1. **Assessment export**: Create assessment with MC + short answer + extended response → export Word Doc → open in Word → fill in answers → save → grade in Graider → verify debug log shows "Using Graider table extraction (N tables)"
2. **Assignment export (DOCX)**: Generate assignment with visuals → click "Gradeable DOCX" → verify images render above Graider tables → fill in → grade → verify structured extraction
3. **Assignment export (PDF)**: "Export PDF" and "Answer Key" buttons still produce PDFs as before
4. **Answer key**: Export answer key → verify NO Graider tables or GRAIDER_TABLE_V1 marker in the doc
5. **Grading config**: After export, check `~/.graider_assignments/` for auto-saved config with `tableStructured: true`
6. **Edge case — wrong cell**: Open exported .docx, type in the blue header cell instead of the answer cell → grade → verify extraction recovers the response (existing recovery logic)
7. **Fallback**: Copy student answers to a plain .docx (no tables) → grade → verify text-matching fallback still works
8. `cd frontend && npm run build` passes
