# Table-Based Structured Templates — Implementation Guide

## Problem

The current extraction pipeline (`extract_student_responses()` in `assignment_grader.py`) uses ~800 lines of fragile regex to figure out where student responses are in a Word document. Every new assignment format introduces new bugs — missed answers, wrong section boundaries, template text mixed with student responses.

## Solution

When the Builder generates a Word template (worksheet), use **tables** to create structured response areas. Each question gets a 2-row, 1-column table:
- **Row 0 (header)**: Blue shading, question text + points + hidden `[GRAIDER:TYPE:ID]` tag
- **Row 1 (response)**: Empty white cell where the student types their answer

When parsing, detect Graider table structure and extract responses directly from cells — no regex needed.

---

## File 1: `backend/services/worksheet_generator.py`

### 1A. Add imports (line 15, after existing imports)

```python
# EXISTING:
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ADD:
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
```

### 1B. Add `_add_graider_table()` helper (after line 24, before `create_worksheet_docx`)

```python
def _add_graider_table(doc, header_text, graider_tag, points, style,
                       response_height_twips=1440, body_font="Calibri",
                       body_size=11):
    """Add a 2-row Graider structured table for one question/term.

    Row 0: Shaded header with hidden [GRAIDER:TYPE:ID] tag + visible question + points
    Row 1: Empty response cell with minimum height for student to type in

    Args:
        doc: python-docx Document object
        header_text: Visible question/term text
        graider_tag: Hidden metadata tag (e.g., "GRAIDER:VOCAB:Osmosis")
        points: Point value to display
        style: Style dict for fonts/colors
        response_height_twips: Height of response row in twips (1440 = ~1 inch)
        body_font: Font name for body text
        body_size: Font size for body text
    """
    table = doc.add_table(rows=2, cols=1)
    table.style = 'Table Grid'

    # --- Row 0: Header cell ---
    header_cell = table.rows[0].cells[0]
    header_cell.text = ""  # Clear default
    p = header_cell.paragraphs[0]

    # Hidden tag run (font color matches background — invisible but parseable)
    bg_hex = style.get("table_header_bg", "#4472C4")
    bg_clean = bg_hex.lstrip('#') if bg_hex else "4472C4"
    tag_run = p.add_run("[" + graider_tag + "] ")
    tag_run.font.size = Pt(1)
    tag_run.font.color.rgb = RGBColor(
        int(bg_clean[0:2], 16), int(bg_clean[2:4], 16), int(bg_clean[4:6], 16)
    )

    # Visible question text
    q_run = p.add_run(header_text)
    q_run.bold = True
    q_run.font.name = style.get("heading_font_name", "Georgia")
    q_run.font.size = Pt(body_size)
    text_color_hex = style.get("table_header_text_color", "#FFFFFF")
    tc = text_color_hex.lstrip('#')
    q_run.font.color.rgb = RGBColor(int(tc[0:2], 16), int(tc[2:4], 16), int(tc[4:6], 16))

    # Points badge
    pts_run = p.add_run("  (" + str(points) + " pts)")
    pts_run.font.size = Pt(9)
    pts_run.font.name = body_font
    pts_run.font.color.rgb = RGBColor(200, 200, 220)

    # Apply shading to header cell
    shading = parse_xml(
        '<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), bg_clean)
    )
    header_cell._tc.get_or_add_tcPr().append(shading)

    # --- Row 1: Response cell ---
    response_cell = table.rows[1].cells[0]
    response_cell.text = ""  # Empty — student types here

    # Set minimum row height
    tr = table.rows[1]._tr
    trPr = tr.get_or_add_trPr()
    trHeight = parse_xml(
        '<w:trHeight {} w:val="{}" w:hRule="atLeast"/>'.format(
            nsdecls('w'), str(response_height_twips)
        )
    )
    trPr.append(trHeight)

    # Set font for response cell so student typing inherits it
    resp_p = response_cell.paragraphs[0]
    resp_run = resp_p.add_run("")
    resp_run.font.name = body_font
    resp_run.font.size = Pt(body_size)

    # Spacing after table
    doc.add_paragraph()

    return table
```

### 1C. Replace `create_worksheet_docx()` body (lines 73-131)

**OLD (lines 73-87) — Vocabulary section:**
```python
    # Vocabulary Section
    if vocab_terms:
        vh = doc.add_heading('VOCABULARY', level=2)
        _apply_style_to_heading(vh, 2, style)
        for item in vocab_terms:
            p = doc.add_paragraph()
            term_text = item.get('term', '') + ': '
            run = p.add_run(term_text)
            run.bold = True
            run.font.size = Pt(body_size)
            run.font.name = body_font
            fill_run = p.add_run('_' * 60)
            fill_run.font.name = body_font

        doc.add_paragraph()  # spacing
```

**NEW:**
```python
    # Vocabulary Section — table-based structured response areas
    if vocab_terms:
        vh = doc.add_heading('VOCABULARY', level=2)
        _apply_style_to_heading(vh, 2, style)
        vocab_pts = max(1, total_points // (len(vocab_terms) + len(questions or []) + (1 if summary_prompt else 0)) if (len(vocab_terms) + len(questions or []) + (1 if summary_prompt else 0)) > 0 else 5)
        for item in vocab_terms:
            term = item.get('term', '')
            _add_graider_table(
                doc, term, "GRAIDER:VOCAB:" + term, vocab_pts, style,
                response_height_twips=1080, body_font=body_font, body_size=body_size
            )
```

**OLD (lines 89-120) — Questions section:**
```python
    # Questions Section
    if questions:
        qh = doc.add_heading('QUESTIONS', level=2)
        _apply_style_to_heading(qh, 2, style)
        for i, q in enumerate(questions, 1):
            pts = q.get('points', 10)
            question_text = q.get('question', '')

            # Question line with point value
            p = doc.add_paragraph()
            num_run = p.add_run(str(i) + ') ')
            num_run.bold = True
            num_run.font.size = Pt(body_size)
            num_run.font.name = body_font
            _parse_markdown_runs(p, question_text, body_font, body_size)
            pts_run = p.add_run('  (' + str(pts) + ' pts)')
            pts_run.font.size = Pt(9)
            pts_run.font.name = body_font
            pts_run.font.color.rgb = RGBColor(128, 128, 128)

            # Response lines
            p = doc.add_paragraph()
            run = p.add_run('Response: ')
            run.bold = True
            run.font.size = Pt(body_size)
            run.font.name = body_font
            fill_run = p.add_run('_' * 55)
            fill_run.font.name = body_font
            line_p = doc.add_paragraph()
            line_run = line_p.add_run('_' * 65)
            line_run.font.name = body_font
            doc.add_paragraph()  # spacing between questions
```

**NEW:**
```python
    # Questions Section — table-based structured response areas
    if questions:
        qh = doc.add_heading('QUESTIONS', level=2)
        _apply_style_to_heading(qh, 2, style)
        for i, q in enumerate(questions, 1):
            pts = q.get('points', 10)
            question_text = q.get('question', '')
            _add_graider_table(
                doc, str(i) + ") " + question_text,
                "GRAIDER:QUESTION:" + str(i), pts, style,
                response_height_twips=2160, body_font=body_font, body_size=body_size
            )
```

**OLD (lines 122-131) — Summary section:**
```python
    # Summary Section
    if summary_prompt:
        sh = doc.add_heading('SUMMARY', level=2)
        _apply_style_to_heading(sh, 2, style)
        sp = doc.add_paragraph()
        _parse_markdown_runs(sp, summary_prompt, body_font, body_size)
        for _ in range(5):
            line_p = doc.add_paragraph()
            line_run = line_p.add_run('_' * 70)
            line_run.font.name = body_font
```

**NEW:**
```python
    # Summary Section — table-based structured response area
    if summary_prompt:
        sh = doc.add_heading('SUMMARY', level=2)
        _apply_style_to_heading(sh, 2, style)
        summary_pts = max(5, total_points // 5)  # ~20% for summary
        _add_graider_table(
            doc, summary_prompt, "GRAIDER:SUMMARY:main", summary_pts, style,
            response_height_twips=4320, body_font=body_font, body_size=body_size
        )
```

### 1D. Add hidden marker paragraph (line 133, before `doc.save()`)

**OLD:**
```python
    doc.save(filepath)
```

**NEW:**
```python
    # Hidden marker paragraph — identifies this as a Graider structured template
    marker_p = doc.add_paragraph()
    marker_run = marker_p.add_run("GRAIDER_TABLE_V1")
    marker_run.font.size = Pt(1)
    marker_run.font.color.rgb = RGBColor(255, 255, 255)

    doc.save(filepath)
```

### 1E. Add `tableStructured` flag to config (in `generate_worksheet()`, after line 218)

**OLD (lines 212-218):**
```python
    config["worksheetDownloadUrl"] = download_url
    config["importedDoc"] = {
        "text": doc_text,
        "html": "",
        "filename": filename,
        "loading": False
    }
```

**NEW:**
```python
    config["worksheetDownloadUrl"] = download_url
    config["tableStructured"] = True
    config["tableVersion"] = "v1"
    config["importedDoc"] = {
        "text": doc_text,
        "html": "",
        "filename": filename,
        "loading": False
    }
```

---

## File 2: `assignment_grader.py`

### 2A. Add `read_docx_file_structured()` (after `read_docx_file()`, after line 2552)

```python
def read_docx_file_structured(filepath: str) -> dict:
    """Read a Word document, preserving Graider table structure if present.

    Checks for [GRAIDER:TYPE:ID] tags in 2-row tables to detect structured templates.

    Returns:
        {
            "is_graider_table": bool,
            "plain_text": str,        # Same as read_docx_file() output
            "tables": [               # Structured table data (empty if not Graider tables)
                {
                    "tag": "GRAIDER:VOCAB:Osmosis",
                    "header_text": "Osmosis",
                    "response_text": "Movement of water through a membrane",
                    "type": "VOCAB",
                    "id": "Osmosis",
                    "points": 5
                },
                ...
            ]
        }
    """
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        return None

    try:
        doc = Document(filepath)
        full_text = []
        graider_tables = []

        for element in doc.element.body:
            if element.tag.endswith('p'):
                para = Paragraph(element, doc)
                if para.text.strip():
                    full_text.append(para.text)
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                rows = list(table.rows)

                # Check if this is a Graider structured table (2 rows, tag in row 0)
                if len(rows) >= 2:
                    header_text = rows[0].cells[0].text.strip()
                    tag_match = re.match(r'\[GRAIDER:(\w+):([^\]]+)\]\s*(.*)', header_text, re.DOTALL)

                    if tag_match:
                        tag_type = tag_match.group(1)   # VOCAB, QUESTION, SUMMARY
                        tag_id = tag_match.group(2)     # term name, question #, "main"
                        visible_text = tag_match.group(3).strip()

                        # Extract points from visible text if present
                        pts_match = re.search(r'\((\d+)\s*pts?\)', visible_text)
                        pts = int(pts_match.group(1)) if pts_match else 0

                        # Clean visible text (remove points badge)
                        clean_header = re.sub(r'\s*\(\d+\s*pts?\)\s*$', '', visible_text).strip()

                        # Response is in row 1 (or last row if student added rows)
                        response_text = rows[-1].cells[0].text.strip()

                        graider_tables.append({
                            "tag": "GRAIDER:" + tag_type + ":" + tag_id,
                            "header_text": clean_header,
                            "response_text": response_text,
                            "type": tag_type,
                            "id": tag_id,
                            "points": pts
                        })

                        # Also add to plain text for backward compatibility
                        full_text.append(clean_header)
                        if response_text:
                            full_text.append(response_text)
                        continue

                # Non-Graider table — flatten as before
                for row in rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        full_text.append(' | '.join(row_text))

        is_graider = len(graider_tables) > 0
        if is_graider:
            print(f"  📋 Detected Graider structured template: {len(graider_tables)} table sections")

        return {
            "is_graider_table": is_graider,
            "plain_text": '\n'.join(full_text),
            "tables": graider_tables
        }

    except Exception as e:
        print(f"  ⚠️  Error in structured read: {e}")
        return None
```

### 2B. Add `extract_from_tables()` (before `extract_student_responses()`, before line 780)

```python
def extract_from_tables(table_data: list, exclude_markers: list = None) -> dict:
    """Extract student responses from Graider structured tables.

    This replaces the 800-line regex extraction for documents generated by the
    Builder with table-based response areas. Each table entry has a clear
    question (header) and response (cell) with no ambiguity.

    Args:
        table_data: List of table dicts from read_docx_file_structured()
        exclude_markers: Section names to exclude from grading

    Returns:
        Same format as extract_student_responses():
        {
            "extracted_responses": [{"question": ..., "answer": ..., "type": ...}, ...],
            "blank_questions": [...],
            "missing_sections": [],
            "total_questions": int,
            "answered_questions": int,
            "extraction_summary": str,
            "excluded_sections": [...]
        }
    """
    exclude_markers = exclude_markers or []
    exclude_lower = [m.lower().strip() if isinstance(m, str) else str(m).lower().strip() for m in exclude_markers]

    extracted = []
    blanks = []
    excluded = []

    # Map Graider table types to extraction response types
    type_map = {
        "VOCAB": "vocab_term",
        "QUESTION": "numbered_question",
        "SUMMARY": "marker_response",
    }

    for entry in table_data:
        header = entry.get("header_text", "")
        response = entry.get("response_text", "")
        tag_type = entry.get("type", "QUESTION")
        tag_id = entry.get("id", "")

        # Check if this section is excluded
        header_lower = header.lower().strip()
        is_excluded = False
        for ex in exclude_lower:
            if ex in header_lower or header_lower in ex:
                is_excluded = True
                break
        if is_excluded:
            excluded.append(header)
            continue

        # Determine response type
        resp_type = type_map.get(tag_type, "marker_response")

        # Check if blank (empty, only whitespace, or only underscores)
        cleaned = re.sub(r'[_\s]+', '', response).strip()
        is_blank = len(cleaned) < 3

        if is_blank:
            blanks.append(header if header else "Section " + tag_id)
        else:
            extracted.append({
                "question": header,
                "answer": response,
                "type": resp_type
            })

    total = len(extracted) + len(blanks)
    answered = len(extracted)
    summary = "Table extraction: " + str(answered) + "/" + str(total) + " responses from " + str(len(table_data)) + " structured sections"
    if excluded:
        summary += " (" + str(len(excluded)) + " excluded)"

    print(f"  📋 {summary}")

    return {
        "extracted_responses": extracted,
        "blank_questions": blanks,
        "missing_sections": [],  # Tables are always present — no "missing" sections
        "total_questions": total,
        "answered_questions": answered,
        "extraction_summary": summary,
        "excluded_sections": excluded
    }
```

### 2C. Modify `read_assignment_file()` (lines 2609-2617)

**OLD:**
```python
    if extension == '.docx':
        content = read_docx_file(filepath)
        if content:
            # Strip embedded answer key from generated worksheets (handles -- and --- variants)
            if "GRAIDER_ANSWER_KEY_START" in content:
                content = content.split("GRAIDER_ANSWER_KEY_START")[0].rstrip().rstrip('-')
                print(f"  🧹 Stripped embedded answer key at file read")
            return {"type": "text", "content": content}
        return None
```

**NEW:**
```python
    if extension == '.docx':
        # Try structured reading first (detects Graider table templates)
        structured = read_docx_file_structured(str(filepath))
        if structured and structured.get("is_graider_table"):
            content = structured["plain_text"]
            if "GRAIDER_ANSWER_KEY_START" in content:
                content = content.split("GRAIDER_ANSWER_KEY_START")[0].rstrip().rstrip('-')
                print(f"  🧹 Stripped embedded answer key at file read")
            return {
                "type": "text",
                "content": content,
                "graider_tables": structured["tables"]
            }
        # Fall back to plain text reading
        content = read_docx_file(filepath)
        if content:
            if "GRAIDER_ANSWER_KEY_START" in content:
                content = content.split("GRAIDER_ANSWER_KEY_START")[0].rstrip().rstrip('-')
                print(f"  🧹 Stripped embedded answer key at file read")
            return {"type": "text", "content": content}
        return None
```

### 2D. Modify `grade_multipass()` extraction routing (lines 3754-3757)

**OLD:**
```python
    # === EXTRACTION (reuse existing logic) ===
    extraction_result = None
    if assignment_data.get("type") == "text" and content:
        extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
```

**NEW:**
```python
    # === EXTRACTION ===
    extraction_result = None
    if assignment_data.get("type") == "text" and content:
        # Priority: Use table-based extraction if document has Graider structured tables
        graider_tables = assignment_data.get("graider_tables")
        if graider_tables:
            extraction_result = extract_from_tables(graider_tables, exclude_markers)
            if extraction_result:
                answered = extraction_result.get("answered_questions", 0)
                total = extraction_result.get("total_questions", 0)
                print(f"  📋 Multi-pass: Table extraction - {answered}/{total} responses")
        # Fall back to regex extraction for non-table documents
        if not extraction_result or not extraction_result.get("extracted_responses"):
            extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
```

### 2E. Modify `grade_with_parallel_detection()` extraction routing (lines 3158-3159)

**OLD:**
```python
    if assignment_data.get("type") == "text" and content:
        extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
```

**NEW:**
```python
    if assignment_data.get("type") == "text" and content:
        # Priority: Use table-based extraction if document has Graider structured tables
        graider_tables = assignment_data.get("graider_tables")
        if graider_tables:
            extraction_result = extract_from_tables(graider_tables, exclude_markers)
        else:
            extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
```

---

## File 3: `backend/app.py`

### 3A. Pass `graider_tables` through grade_data (line 1165-1166)

**OLD:**
```python
                if file_data["type"] == "text":
                    grade_data = {"type": "text", "content": file_data["content"]}
```

**NEW:**
```python
                if file_data["type"] == "text":
                    grade_data = {"type": "text", "content": file_data["content"]}
                    # Preserve Graider table structure for table-based extraction
                    if file_data.get("graider_tables"):
                        grade_data["graider_tables"] = file_data["graider_tables"]
```

---

## File 4: `backend/routes/assignment_routes.py` (optional, for Builder export)

### 4A. Modify `_export_docx()` to optionally use tables (lines 139-199)

**OLD:**
```python
def _export_docx(title, instructions, questions, output_folder, safe_title):
    """Export assignment to Word format."""
    try:
        from docx import Document
        from docx.shared import Inches, Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Title
        title_para = doc.add_heading(title, 0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Name/Date line
        name_para = doc.add_paragraph("Name: _________________________ Date: _____________")
        name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        # Instructions
        if instructions:
            inst_para = doc.add_paragraph(instructions)
            inst_para.italic = True
            doc.add_paragraph()

        # Questions
        for i, q in enumerate(questions, 1):
            marker = q.get('marker', 'Answer:')
            prompt = q.get('prompt', '')
            points = q.get('points', 10)
            q_type = q.get('type', 'short_answer')

            # Question header with marker
            q_para = doc.add_paragraph()
            run = q_para.add_run(f"{marker} ")
            run.bold = True
            q_para.add_run(f"({points} pts)")

            # Question prompt
            if prompt:
                doc.add_paragraph(prompt)

            # Answer space
            lines = 3 if q_type == 'short_answer' else 6 if q_type == 'essay' else 2
            for _ in range(lines):
                doc.add_paragraph("_" * 70)

            doc.add_paragraph()

        filepath = os.path.join(output_folder, f"{safe_title}.docx")
        doc.save(filepath)

        # Open the folder
        os.system(f'open "{output_folder}"')

        return jsonify({"status": "exported", "path": filepath})

    except ImportError:
        return jsonify({"error": "python-docx not installed. Run: pip3 install python-docx"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

**NEW:**
```python
def _export_docx(title, instructions, questions, output_folder, safe_title):
    """Export assignment to Word format with Graider structured tables."""
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import nsdecls
        from docx.oxml import parse_xml
        from backend.services.document_generator import DEFAULT_STYLE
        from backend.services.worksheet_generator import _add_graider_table

        style = dict(DEFAULT_STYLE)
        body_font = style.get("body_font_name", "Calibri")
        body_size = style.get("body_font_size", 11)

        doc = Document()

        # Title
        title_para = doc.add_heading(title, 0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Name/Date line
        name_para = doc.add_paragraph("Name: _________________________ Date: _____________")
        name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        # Instructions
        if instructions:
            inst_para = doc.add_paragraph(instructions)
            inst_para.italic = True
            doc.add_paragraph()

        # Questions — each gets a Graider structured table
        for i, q in enumerate(questions, 1):
            marker = q.get('marker', 'Answer:')
            prompt = q.get('prompt', '')
            points = q.get('points', 10)
            q_type = q.get('type', 'short_answer')

            header_text = marker
            if prompt:
                header_text = marker + " " + prompt

            height = 2160 if q_type == 'short_answer' else 4320 if q_type == 'essay' else 1440
            _add_graider_table(
                doc, header_text, "GRAIDER:QUESTION:" + str(i), points, style,
                response_height_twips=height, body_font=body_font, body_size=body_size
            )

        # Hidden marker paragraph
        marker_p = doc.add_paragraph()
        marker_run = marker_p.add_run("GRAIDER_TABLE_V1")
        marker_run.font.size = Pt(1)
        marker_run.font.color.rgb = RGBColor(255, 255, 255)

        filepath = os.path.join(output_folder, f"{safe_title}.docx")
        doc.save(filepath)

        # Open the folder
        os.system(f'open "{output_folder}"')

        return jsonify({"status": "exported", "path": filepath})

    except ImportError:
        return jsonify({"error": "python-docx not installed. Run: pip3 install python-docx"})
    except Exception as e:
        return jsonify({"error": str(e)})
```

---

## Auto-Detection Flow

```
Student submits .docx
        |
        v
read_assignment_file()
        |
        v
read_docx_file_structured()
        |
    Has [GRAIDER:...] tags in tables?
       /              \
     YES               NO
      |                  |
      v                  v
Return with           read_docx_file() (plain text)
graider_tables        Return without graider_tables
      |                  |
      v                  v
grade_multipass()     grade_multipass()
      |                  |
      v                  v
extract_from_tables() extract_student_responses()
  (~80 lines)           (~800 lines regex)
      |                  |
      v                  v
  Same return format → grade_per_question() → generate_feedback()
```

---

## What Does NOT Change

- `extract_student_responses()` — kept intact as fallback for non-table documents
- `grade_per_question()` — receives same question/answer pairs
- `generate_feedback()` — receives same aggregate scores
- `_strip_template_lines()` — not called for table extraction
- Frontend `App.jsx` — no changes needed
- All existing assignment configs — no `tableStructured` flag = regex extraction

---

## Verification Steps

1. Generate a worksheet via the API/Builder — open in Word, verify:
   - Tables render with blue header rows
   - Response cells are tall and empty
   - Hidden `[GRAIDER:...]` tags are invisible
2. Type answers in response cells, save the document
3. Run grading on the filled document — verify:
   - `read_docx_file_structured()` detects Graider tables
   - `extract_from_tables()` extracts correct question/answer pairs
   - `grade_multipass()` produces scores and feedback
4. Grade an old-format (non-table) document — verify regex fallback still works
5. Leave some response cells empty — verify blank detection and completeness caps
