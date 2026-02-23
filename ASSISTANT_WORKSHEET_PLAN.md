# Assistant File Upload + Worksheet Generator Plan

## Overview

Enable the Assistant to accept file uploads (images, PDFs, DOCX), generate structured worksheets from textbook readings, and output them as downloadable Word documents that auto-save to the Builder/Saved Assignments. Worksheets include an invisible text layer with answer keys and parsing markers for consistent AI grading.

---

## Workflow

```
Teacher uploads textbook page (image/PDF/DOCX) to Assistant
  → "Create a Cornell Notes worksheet from this reading"
  → Assistant reads the content via Claude vision / text extraction
  → Generates worksheet structure (vocab, questions, summary)
  → Creates .docx with invisible parsing layer
  → Saves assignment config to Builder
  → Returns download link in chat
```

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/routes/assistant_routes.py` | Accept file uploads in chat endpoint |
| `backend/services/assistant_tools.py` | New tools: `generate_worksheet`, `save_to_builder` |
| `backend/services/worksheet_generator.py` | **NEW** — DOCX generation with invisible text layer |
| `frontend/src/components/AssistantChat.jsx` | File upload UI (drag-drop + button) |
| `frontend/src/services/api.js` | Update chat API call for multipart/file data |

---

## 1. File Upload in Assistant Chat

### Backend: `assistant_routes.py`

**Current**: Accepts JSON `{ messages: [...], session_id }` only.

**Change**: Accept files alongside messages. Two approaches:

**Option A — Base64 in JSON** (simpler, recommended):
```python
# Frontend converts file to base64 before sending
{
  "messages": [{ "role": "user", "content": "Create a worksheet from this" }],
  "session_id": "...",
  "files": [
    {
      "filename": "textbook_page.png",
      "media_type": "image/png",
      "data": "base64_encoded_string..."
    }
  ]
}
```

**In the endpoint**, build Claude message content blocks:
```python
content_blocks = []

# Add file content blocks
for file_info in files:
    if file_info["media_type"].startswith("image/"):
        # Claude handles images natively
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": file_info["media_type"],
                "data": file_info["data"]
            }
        })
    elif file_info["media_type"] == "application/pdf":
        # Extract text using existing _parse_pdf / PyMuPDF
        text = extract_text_from_pdf(base64.b64decode(file_info["data"]))
        content_blocks.append({"type": "text", "text": f"[PDF Content]:\n{text}"})
    elif "word" in file_info["media_type"] or file_info["filename"].endswith(".docx"):
        # Extract text using existing read_docx_file
        text = extract_text_from_docx(base64.b64decode(file_info["data"]))
        content_blocks.append({"type": "text", "text": f"[Document Content]:\n{text}"})

# Add user text message
content_blocks.append({"type": "text", "text": user_message_text})

# Send to Claude with multimodal content
messages.append({"role": "user", "content": content_blocks})
```

**Reuse existing extraction functions:**
- `assignment_grader.py` → `read_docx_file(filepath)` (line 2152)
- `assignment_grader.py` → `read_image_file(filepath)` (line 2192)
- `backend/routes/document_routes.py` → `_parse_pdf(file_data, filename)` (line 203)

For base64 input, write to a temp file, call the existing function, then clean up.

### Frontend: `AssistantChat.jsx`

Add to the input area:
- **Paperclip/attach button** next to the send button
- **Hidden file input** accepting `.png, .jpg, .jpeg, .gif, .webp, .pdf, .docx`
- **File preview chip** showing filename + remove button above the input when a file is attached
- **Drag-and-drop zone** on the chat area (optional, nice-to-have)

On send:
```javascript
// Convert file to base64
const reader = new FileReader()
reader.onload = () => {
  const base64 = reader.result.split(',')[1]
  const fileData = {
    filename: file.name,
    media_type: file.type || 'application/octet-stream',
    data: base64
  }
  // Send with message
  sendMessage(text, [fileData])
}
reader.readAsDataURL(file)
```

Update `api.js` `assistantChat()` to include files array in the JSON body.

---

## 2. `generate_worksheet` Tool

### Tool Definition (in `assistant_tools.py`)

```python
{
    "name": "generate_worksheet",
    "description": "Generate a structured worksheet document (Cornell Notes, Fill-in-the-Blank, etc.) from a reading or topic. Creates a downloadable Word document with an embedded invisible answer key for consistent AI grading. Use when the teacher asks to create a worksheet, assignment, or activity.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Worksheet title (e.g., 'Cornell Notes - Expanding into Native American Lands')"
            },
            "worksheet_type": {
                "type": "string",
                "enum": ["cornell-notes", "fill-in-blank", "short-answer", "vocabulary"],
                "description": "Type of worksheet to generate"
            },
            "vocab_terms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": { "type": "string" },
                        "definition": { "type": "string", "description": "Expected definition (for answer key)" }
                    }
                },
                "description": "Vocabulary terms with expected definitions"
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": { "type": "string" },
                        "expected_answer": { "type": "string", "description": "Expected answer (for answer key)" },
                        "points": { "type": "integer", "default": 10 }
                    }
                },
                "description": "Questions with expected answers"
            },
            "summary_prompt": {
                "type": "string",
                "description": "Instruction for the summary section (e.g., 'Summarize in 3-5 sentences...')"
            },
            "summary_key_points": {
                "type": "array",
                "items": { "type": "string" },
                "description": "Key points that should appear in a good summary"
            },
            "total_points": {
                "type": "integer",
                "default": 100
            }
        },
        "required": ["title", "worksheet_type"]
    }
}
```

### Tool Handler

```python
def generate_worksheet(title, worksheet_type, vocab_terms=None, questions=None,
                       summary_prompt=None, summary_key_points=None, total_points=100):
    """Generate a .docx worksheet with invisible answer key layer."""
    from backend.services.worksheet_generator import create_worksheet_docx

    output_dir = os.path.expanduser("~/Downloads/Graider/Worksheets")
    os.makedirs(output_dir, exist_ok=True)

    safe_title = re.sub(r'[^\w\s-]', '', title).replace(' ', '_')
    filename = f"{safe_title}.docx"
    filepath = os.path.join(output_dir, filename)

    create_worksheet_docx(
        filepath=filepath,
        title=title,
        worksheet_type=worksheet_type,
        vocab_terms=vocab_terms or [],
        questions=questions or [],
        summary_prompt=summary_prompt,
        summary_key_points=summary_key_points or [],
        total_points=total_points
    )

    # Also save assignment config to Builder
    config = _build_assignment_config(
        title, worksheet_type, vocab_terms, questions,
        summary_prompt, summary_key_points, total_points
    )
    config_dir = os.path.expanduser("~/.graider_assignments")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, f"{safe_title}.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    return {
        "status": "created",
        "filepath": filepath,
        "filename": filename,
        "download_url": f"/api/download-worksheet/{filename}",
        "saved_to_builder": True,
        "config_name": safe_title
    }
```

---

## 3. Worksheet Generator (NEW FILE)

### `backend/services/worksheet_generator.py`

Uses `python-docx` to create a structured .docx with two text layers:

**Visible layer** (what students see when printing):
- Header: Name / Date / Period blanks
- Vocabulary section with terms and underscore blanks
- Questions section with numbered questions and response areas
- Summary section with prompt and blank lines

**Invisible layer** (what AI grader reads):
- White text (font color = white, size 1pt) embedded at the end of the document
- Contains: answer key, expected definitions, rubric weights, section markers
- Invisible to students when printed on white paper
- Fully readable when Graider extracts text from the .docx

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_worksheet_docx(filepath, title, worksheet_type, vocab_terms,
                          questions, summary_prompt, summary_key_points, total_points):
    doc = Document()

    # ── VISIBLE LAYER ──

    # Title
    doc.add_heading(title, level=1)

    # Header fields
    for field in ['Name', 'Date', 'Period']:
        p = doc.add_paragraph()
        run = p.add_run(f'{field}: ')
        run.bold = True
        p.add_run('_' * 50)

    # Vocabulary Section
    if vocab_terms:
        doc.add_heading('VOCABULARY', level=2)
        for item in vocab_terms:
            p = doc.add_paragraph()
            run = p.add_run(f"{item['term']}: ")
            run.bold = True
            p.add_run('_' * 60)

    # Questions Section
    if questions:
        doc.add_heading('QUESTIONS', level=2)
        for i, q in enumerate(questions, 1):
            doc.add_paragraph(f"{i}) {q['question']}")
            p = doc.add_paragraph()
            run = p.add_run('Response: ')
            run.bold = True
            p.add_run('_' * 55)
            doc.add_paragraph('_' * 65)  # Extra line for longer answers

    # Summary Section
    if summary_prompt:
        doc.add_heading('SUMMARY', level=2)
        doc.add_paragraph(summary_prompt)
        for _ in range(5):
            doc.add_paragraph('_' * 70)

    # ── INVISIBLE LAYER (answer key for AI grading) ──

    doc.add_page_break()
    _add_invisible_text(doc, _build_answer_key(
        title, worksheet_type, vocab_terms, questions,
        summary_key_points, total_points
    ))

    doc.save(filepath)


def _add_invisible_text(doc, text):
    """Add white 1pt text that's invisible when printed but readable by text extraction."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(1)
    run.font.color.rgb = RGBColor(255, 255, 255)  # White text


def _build_answer_key(title, worksheet_type, vocab_terms, questions,
                      summary_key_points, total_points):
    """Build structured answer key text for the invisible layer."""
    lines = [
        "---GRAIDER_ANSWER_KEY_START---",
        f"TITLE: {title}",
        f"TYPE: {worksheet_type}",
        f"TOTAL_POINTS: {total_points}",
        ""
    ]

    if vocab_terms:
        lines.append("VOCABULARY_ANSWERS:")
        for v in vocab_terms:
            lines.append(f"  {v['term']}: {v.get('definition', '')}")
        lines.append("")

    if questions:
        lines.append("QUESTION_ANSWERS:")
        for i, q in enumerate(questions, 1):
            lines.append(f"  Q{i}: {q.get('expected_answer', '')}")
            lines.append(f"  Q{i}_POINTS: {q.get('points', 10)}")
        lines.append("")

    if summary_key_points:
        lines.append("SUMMARY_KEY_POINTS:")
        for kp in summary_key_points:
            lines.append(f"  - {kp}")
        lines.append("")

    lines.append("---GRAIDER_ANSWER_KEY_END---")
    return "\n".join(lines)
```

### Grading Engine Integration

In `assignment_grader.py`, during text extraction, detect the `---GRAIDER_ANSWER_KEY_START---` marker:

```python
# In extract_student_responses() or grade_assignment()
if "---GRAIDER_ANSWER_KEY_START---" in full_text:
    parts = full_text.split("---GRAIDER_ANSWER_KEY_START---")
    student_text = parts[0]  # Everything before the key
    answer_key_text = parts[1].split("---GRAIDER_ANSWER_KEY_END---")[0]
    # Parse answer key and inject into grading prompt as reference
```

This means the answer key **travels with the document** — no config file lookup needed. But we still save a config for the Builder UI.

---

## 4. Assignment Config Auto-Save

When `generate_worksheet` runs, it also saves a Builder-compatible config:

```python
def _build_assignment_config(title, worksheet_type, vocab_terms, questions,
                             summary_prompt, summary_key_points, total_points):
    rubric_map = {
        "cornell-notes": "cornell-notes",
        "fill-in-blank": "fill-in-blank",
        "short-answer": "standard",
        "vocabulary": "fill-in-blank"
    }

    # Build custom markers from the sections
    markers = []
    if vocab_terms:
        markers.append("VOCABULARY")
    if questions:
        markers.append("QUESTIONS")
    if summary_prompt:
        markers.append("SUMMARY")

    # Build grading notes with answer key
    grading_notes_parts = []
    if vocab_terms:
        grading_notes_parts.append("VOCABULARY EXPECTED DEFINITIONS:")
        for v in vocab_terms:
            grading_notes_parts.append(f"- {v['term']}: {v.get('definition', 'Accept reasonable definition')}")
    if questions:
        grading_notes_parts.append("\nEXPECTED ANSWERS:")
        for i, q in enumerate(questions, 1):
            grading_notes_parts.append(f"- Q{i}: {q.get('expected_answer', '')}")
    if summary_key_points:
        grading_notes_parts.append("\nSUMMARY SHOULD INCLUDE:")
        for kp in summary_key_points:
            grading_notes_parts.append(f"- {kp}")

    return {
        "title": title,
        "subject": "",  # Filled from settings
        "totalPoints": total_points,
        "instructions": "",
        "aliases": [],
        "customMarkers": markers,
        "excludeMarkers": [],
        "gradingNotes": "\n".join(grading_notes_parts),
        "responseSections": [],
        "rubricType": rubric_map.get(worksheet_type, "standard"),
        "customRubric": None,
        "useSectionPoints": False,
        "sectionTemplate": "Custom",
        "effortPoints": 15,
        "completionOnly": False,
        "countsTowardsGrade": True,
        "importedDoc": None
    }
```

---

## 5. Download Endpoint

### `backend/routes/assignment_routes.py`

```python
@assignment_bp.route('/api/download-worksheet/<filename>')
def download_worksheet(filename):
    """Serve a generated worksheet for download."""
    worksheets_dir = os.path.expanduser("~/Downloads/Graider/Worksheets")
    return send_from_directory(worksheets_dir, filename, as_attachment=True)
```

### Frontend: Download Link in Chat

When the Assistant returns a `generate_worksheet` tool result containing `download_url`, the chat UI renders it as a clickable download button. Add to `AssistantChat.jsx` markdown rendering:

```javascript
// Detect download links in assistant responses
if (text.includes('/api/download-worksheet/')) {
  // Render as styled download button
}
```

Or the Assistant can just include a markdown link in its response text that the user clicks.

---

## 6. System Prompt Update

Add to `_build_system_prompt()` in `assistant_routes.py`:

```
- generate_worksheet: Create downloadable worksheet documents (Cornell Notes, fill-in-blank,
  short-answer, vocabulary) with built-in answer keys for AI grading. Automatically saved to
  Builder. When the teacher uploads a textbook page or reading and asks for a worksheet,
  ALWAYS use this tool to create it. Extract vocab terms, write questions with expected answers,
  and include summary key points. The worksheet will have an invisible answer key embedded for
  consistent grading.
```

---

## Implementation Order

1. **`backend/services/worksheet_generator.py`** — New file, DOCX generation with invisible layer
2. **`backend/services/assistant_tools.py`** — Add `generate_worksheet` tool definition + handler
3. **`backend/routes/assistant_routes.py`** — Add file upload support to chat endpoint, update system prompt
4. **`backend/routes/assignment_routes.py`** — Add download endpoint
5. **`frontend/src/components/AssistantChat.jsx`** — File upload UI + download button rendering
6. **`frontend/src/services/api.js`** — Update chat API for file data
7. **`assignment_grader.py`** — Detect and parse `GRAIDER_ANSWER_KEY` from documents

---

## Verification

1. Open Assistant, attach a textbook screenshot
2. Ask "Create a Cornell Notes worksheet from this reading"
3. Assistant reads the image, extracts key content
4. Calls `generate_worksheet` with vocab terms, questions, summary prompt
5. .docx appears in `~/Downloads/Graider/Worksheets/`
6. Assignment config appears in Builder's saved assignments list
7. Open the .docx — visible layer shows clean student worksheet
8. Extract text from .docx — invisible answer key is present
9. Print the .docx — answer key is invisible (white text on white paper)
10. Student fills out worksheet, submits for grading
11. Graider detects the embedded answer key and grades consistently
