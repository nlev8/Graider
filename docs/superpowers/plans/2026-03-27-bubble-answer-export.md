# Bubble Answer Sheet Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fill-in-the-bubble answer format to DOCX exports for MC/TF questions — student version (empty bubbles) and teacher answer key (correct bubble filled).

**Architecture:** New shared helper function `_add_bubble_row()` in `backend/services/worksheet_generator.py` that renders a row of circle bubbles using `python-docx` XML manipulation. Both export paths (`assignment_routes.py` and `planner_routes.py`) call this helper instead of (or in addition to) the current Graider answer table for MC/TF questions. Export produces two pages: student worksheet + answer key page at the end.

**Tech Stack:** `python-docx` (already installed) — uses `OxmlElement`, `parse_xml`, `RGBColor` for bubble rendering via Word XML drawing shapes.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/services/worksheet_generator.py` | MODIFY | Add `_add_bubble_row()` and `_add_answer_key_page()` helper functions |
| `backend/routes/planner_routes.py` | MODIFY | Use bubbles for MC/TF in `_export_assignment_docx_graider()` + append answer key page |
| `backend/routes/assignment_routes.py` | MODIFY | Use bubbles for MC/TF in `_export_docx()` + append answer key page |
| `tests/test_bubble_export.py` | CREATE | Unit tests for bubble rendering |

---

### Task 1: Bubble Rendering Helper Functions

**Files:**
- Modify: `backend/services/worksheet_generator.py`
- Create: `tests/test_bubble_export.py`

- [ ] **Step 1: Add `_add_bubble_row()` to `backend/services/worksheet_generator.py`**

Append after the existing `_add_graider_marker` function:

```python
def _add_bubble_row(doc, question_number, options, correct_answer=None, is_tf=False):
    """Add a row of fill-in-the-bubble circles for MC or TF questions.

    Args:
        doc: python-docx Document
        question_number: int — question number label
        options: list of option labels (e.g., ['A', 'B', 'C', 'D'] or ['True', 'False'])
        correct_answer: str or None — if provided, fills in the correct bubble (answer key mode)
        is_tf: bool — True/False question (uses T/F labels instead of A/B/C/D)
    """
    from docx.shared import Pt, RGBColor, Inches
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.space_before = Pt(2)

    # Question number
    num_run = para.add_run(f"{question_number}.  ")
    num_run.font.size = Pt(11)
    num_run.font.bold = True

    # Render each bubble
    for i, opt_label in enumerate(options):
        # Determine if this bubble should be filled
        is_correct = False
        if correct_answer is not None:
            if is_tf:
                is_correct = opt_label.lower().strip() == str(correct_answer).lower().strip()
            else:
                # Match by letter (A, B, C, D) or by index
                correct_upper = str(correct_answer).upper().strip()
                # Handle "A)", "B)", etc.
                if len(correct_upper) > 1 and correct_upper[1] == ')':
                    correct_upper = correct_upper[0]
                is_correct = opt_label.upper().strip() == correct_upper

        # Bubble character: filled circle ● or empty circle ○
        if is_correct:
            bubble_char = "\u25CF"  # ● Black circle (filled)
        else:
            bubble_char = "\u25CB"  # ○ White circle (empty)

        # Add bubble with border styling
        bubble_run = para.add_run(f" {bubble_char} ")
        bubble_run.font.size = Pt(16)
        if is_correct:
            bubble_run.font.color.rgb = RGBColor(0, 0, 0)  # Black filled
        else:
            bubble_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)  # Gray outline

        # Add option label
        label_run = para.add_run(f"{opt_label}  ")
        label_run.font.size = Pt(10)
        label_run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    return para


def _add_answer_key_page(doc, questions_with_answers):
    """Add an answer key page at the end of the document.

    Shows all MC/TF questions with the correct bubble filled in.

    Args:
        doc: python-docx Document
        questions_with_answers: list of dicts with keys:
            - number: int
            - options: list of str (e.g., ['A', 'B', 'C', 'D'])
            - correct_answer: str (e.g., 'B' or 'True')
            - is_tf: bool
            - question_text: str (optional, for reference)
    """
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    if not questions_with_answers:
        return

    # Page break before answer key
    page_break_para = doc.add_paragraph()
    run = page_break_para.add_run()
    br = OxmlElement('w:br')
    br.set(qn('w:type'), 'page')
    run._element.append(br)

    # Answer Key header
    heading = doc.add_heading("ANSWER KEY", level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Subtitle
    sub = doc.add_paragraph("For teacher use only — do not distribute to students")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size = Pt(9)
    sub.runs[0].font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    sub.runs[0].italic = True

    doc.add_paragraph()  # Spacer

    # Render each question with filled correct bubble
    for q in questions_with_answers:
        _add_bubble_row(
            doc,
            question_number=q["number"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            is_tf=q.get("is_tf", False),
        )

        # Add question text as reference (smaller, gray)
        if q.get("question_text"):
            ref_para = doc.add_paragraph()
            ref_run = ref_para.add_run(f"    {q['question_text'][:100]}")
            ref_run.font.size = Pt(8)
            ref_run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
            ref_run.italic = True
```

- [ ] **Step 2: Create `tests/test_bubble_export.py`**

```python
"""Unit tests for bubble answer sheet export."""
import pytest
from unittest.mock import MagicMock


class TestAddBubbleRow:
    def test_empty_bubbles_mc(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'])
        text = para.text
        # Should have question number and all option labels
        assert '1.' in text
        assert 'A' in text
        assert 'D' in text
        # Should have empty circles (no filled)
        assert '\u25CB' in text  # ○ empty
        assert '\u25CF' not in text  # ● filled should NOT appear

    def test_filled_bubble_mc(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'], correct_answer='B')
        text = para.text
        # Should have one filled bubble
        assert '\u25CF' in text  # ● filled
        assert text.count('\u25CF') == 1  # Only one filled

    def test_empty_bubbles_tf(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 5, ['True', 'False'], is_tf=True)
        text = para.text
        assert 'True' in text
        assert 'False' in text
        assert '\u25CF' not in text  # No filled bubbles

    def test_filled_bubble_tf(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 5, ['True', 'False'], correct_answer='True', is_tf=True)
        text = para.text
        assert text.count('\u25CF') == 1  # One filled

    def test_correct_answer_with_paren(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'], correct_answer='B)')
        text = para.text
        assert text.count('\u25CF') == 1  # Handles "B)" format


class TestAddAnswerKeyPage:
    def test_answer_key_has_header(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_answer_key_page
        doc = Document()
        questions = [
            {"number": 1, "options": ["A", "B", "C", "D"], "correct_answer": "B", "is_tf": False},
            {"number": 2, "options": ["True", "False"], "correct_answer": "True", "is_tf": True},
        ]
        _add_answer_key_page(doc, questions)
        # Check the document has content
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "ANSWER KEY" in full_text
        assert "teacher use only" in full_text.lower()

    def test_answer_key_empty_list(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_answer_key_page
        doc = Document()
        _add_answer_key_page(doc, [])
        # Should not add anything
        assert len(doc.paragraphs) == 0

    def test_answer_key_has_filled_bubbles(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_answer_key_page
        doc = Document()
        questions = [
            {"number": 1, "options": ["A", "B", "C", "D"], "correct_answer": "C", "is_tf": False},
        ]
        _add_answer_key_page(doc, questions)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert '\u25CF' in full_text  # Has filled bubble
```

- [ ] **Step 3: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_bubble_export.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/services/worksheet_generator.py tests/test_bubble_export.py
git commit -m "feat: add bubble answer sheet rendering helpers (_add_bubble_row, _add_answer_key_page)"
```

---

### Task 2: Integrate Bubbles into Planner Export

**Files:**
- Modify: `backend/routes/planner_routes.py`

- [ ] **Step 1: Modify `_export_assignment_docx_graider()` to use bubbles for MC/TF**

In `backend/routes/planner_routes.py`, find the `_export_assignment_docx_graider` function (line 4089). Locate the MC/TF rendering block (around line 4179-4194):

**Current code:**
```python
            if q_options:
                # MC/TF: question + options as paragraphs, then small Graider table
                if not visual_dict:
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_number}. ").bold = True
                    q_para.add_run(q_text)
                    if q_points:
                        run = q_para.add_run(f" ({q_points} pts)")
                        run.italic = True

                for opt in q_options:
                    doc.add_paragraph(f"    {opt}")

                _add_graider_table(doc, f"Answer for Question {q_number}",
                                   f"GRAIDER:QUESTION:{q_number}", q_points,
                                   graider_style, 720)  # 0.5 inch
```

**Replace with:**
```python
            if q_options:
                # MC/TF: question + options as paragraphs, then bubble row
                is_tf = q_type in ('true_false', 'tf')
                if not visual_dict:
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_number}. ").bold = True
                    q_para.add_run(q_text)
                    if q_points:
                        run = q_para.add_run(f" ({q_points} pts)")
                        run.italic = True

                for opt in q_options:
                    doc.add_paragraph(f"    {opt}")

                # Empty bubble row for student answers
                if is_tf:
                    bubble_labels = ['True', 'False']
                else:
                    bubble_labels = [chr(65 + i) for i in range(len(q_options))]
                _add_bubble_row(doc, q_number, bubble_labels, is_tf=is_tf)

                # Track for answer key page
                answer_key_questions.append({
                    "number": q_number,
                    "options": bubble_labels,
                    "correct_answer": q.get('answer', ''),
                    "is_tf": is_tf,
                    "question_text": q_text,
                })
```

- [ ] **Step 2: Add answer_key_questions list and answer key page**

At the top of `_export_assignment_docx_graider`, after `question_num = 1` (line 4143), add:

```python
    answer_key_questions = []  # Collect MC/TF questions for answer key page
```

Add the import at the top of the MC/TF block (or at function top):

```python
    from backend.services.worksheet_generator import _add_bubble_row, _add_answer_key_page
```

Before the `doc.save()` call at the end of the function, add:

```python
    # Append answer key page with filled bubbles
    if answer_key_questions:
        _add_answer_key_page(doc, answer_key_questions)
```

Find the `doc.save()` line — it should be near the end of the function. Read the exact location:

```python
    filepath = os.path.join(output_folder, f"{safe_title}.docx")
    doc.save(filepath)
```

Insert the answer key page BEFORE `doc.save(filepath)`.

- [ ] **Step 3: Run existing tests**

Run: `source venv/bin/activate && python -m pytest tests/test_bubble_export.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/routes/planner_routes.py
git commit -m "feat: use bubble answers for MC/TF in planner DOCX export + answer key page"
```

---

### Task 3: Integrate Bubbles into Assignment Export

**Files:**
- Modify: `backend/routes/assignment_routes.py`

- [ ] **Step 1: Modify `_export_docx()` to use bubbles for MC/TF**

In `backend/routes/assignment_routes.py`, find `_export_docx` (line 317). The current export renders all questions the same way (paragraph + underline answer space). Add MC/TF detection with bubble rendering.

Find the question rendering loop (around line 368):

**Current code:**
```python
            # Original paragraph-based export
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
```

**Replace with:**
```python
            from backend.services.worksheet_generator import _add_bubble_row, _add_answer_key_page
            answer_key_questions = []

            # Original paragraph-based export
            for i, q in enumerate(questions, 1):
                marker = q.get('marker', 'Answer:')
                prompt = q.get('prompt', '')
                points = q.get('points', 10)
                q_type = q.get('type', 'short_answer')
                options = q.get('options', [])

                # Question header with marker
                q_para = doc.add_paragraph()
                run = q_para.add_run(f"{marker} ")
                run.bold = True
                q_para.add_run(f"({points} pts)")

                # Question prompt
                if prompt:
                    doc.add_paragraph(prompt)

                # MC/TF: render options + bubbles
                if q_type in ('multiple_choice', 'true_false') and options:
                    is_tf = q_type == 'true_false'
                    for opt in options:
                        doc.add_paragraph(f"    {opt}")

                    if is_tf:
                        bubble_labels = ['True', 'False']
                    else:
                        bubble_labels = [chr(65 + j) for j in range(len(options))]
                    _add_bubble_row(doc, i, bubble_labels, is_tf=is_tf)

                    answer_key_questions.append({
                        "number": i,
                        "options": bubble_labels,
                        "correct_answer": q.get('answer', ''),
                        "is_tf": is_tf,
                        "question_text": prompt,
                    })
                else:
                    # Answer space for non-MC/TF
                    lines = 3 if q_type == 'short_answer' else 6 if q_type == 'essay' else 2
                    for _ in range(lines):
                        doc.add_paragraph("_" * 70)

                doc.add_paragraph()

            # Append answer key page
            if answer_key_questions:
                _add_answer_key_page(doc, answer_key_questions)
```

- [ ] **Step 2: Run all tests**

Run: `source venv/bin/activate && python -m pytest tests/test_bubble_export.py -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/routes/assignment_routes.py
git commit -m "feat: use bubble answers for MC/TF in assignment DOCX export + answer key page"
```

---

### Task 4: Full Verification

- [ ] **Step 1: Run all backend tests**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`
Expected: No new failures

- [ ] **Step 2: Manual verification**

Export a generated assessment with MC + TF + short answer questions:
1. In Graider, go to Planner tab
2. Generate an assessment with mixed question types
3. Click "Export DOCX"
4. Open the exported file — verify:
   - MC questions have `○ A  ○ B  ○ C  ○ D` empty bubbles below options
   - TF questions have `○ True  ○ False` empty bubbles
   - Short answer questions still have line-based answer space
   - Last page is "ANSWER KEY" with correct bubbles filled: `● B` etc.

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "test: verified bubble export renders correctly in Word"
```

---

## Implementation Notes

### Bubble Characters

Using Unicode circle characters for maximum Word compatibility:
- `○` (U+25CB) — empty circle (student answer space)
- `●` (U+25CF) — filled circle (answer key correct answer)

These render consistently in Word, Google Docs, and when printed. They're also visually distinct when scanned — GPT-4o vision can reliably distinguish filled vs empty circles.

### Answer Key Placement

The answer key is always the **last page** of the exported document, separated by a page break. Labeled "ANSWER KEY — For teacher use only" so it's easy to remove before distributing to students (or don't print the last page).

### Backward Compatibility

- Short answer, essay, matching, data table, and math questions are unchanged
- The Graider extraction table is removed for MC/TF (replaced by bubbles) — this is correct because bubble answers don't need the table-based extraction marker
- Non-MC/TF questions still use the existing answer space format

### Vision Scanning

No code changes needed for scanning. The existing GPT-4o image parsing pipeline in `assignment_grader.py` already handles scanned worksheets. Filled bubbles (●) vs empty bubbles (○) are visually distinct and the model can read them reliably.
