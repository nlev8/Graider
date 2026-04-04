# Flashcard Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add flashcard generation to the Tools tab — Gemini Flash extracts term/definition pairs from lesson plans and content, renders as a printable card grid, and exports as PDF (front/back layout) or DOCX.

**Architecture:** Same pattern as study guide: new backend endpoints (`POST /api/generate-flashcards`, `POST /api/export-flashcards`), Gemini 2.0 Flash generates structured JSON, frontend renders card preview in the Tools tab below the Study Guide section. PDF export uses ReportLab to create a 2-column card grid with cut lines. DOCX export uses python-docx tables. Auto-saves to resources library.

**Tech Stack:** Gemini 2.0 Flash, python-docx, ReportLab, existing Flask patterns

**Review notes:**
- Rename `_get_study_guide_export_dir` → `_get_export_dir` in planner_routes.py (used by both study guide and flashcards)
- `api.saveResource` already accepts any `content_type` string — 'flashcards' works without changes (verified: `lesson_routes.py:547` stores whatever type is passed)
- Content passed to prompt is trimmed to 8000 chars (`content[:8000]`) to prevent oversized prompts

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/planner_routes.py` | **Modify** | Add `POST /api/generate-flashcards` + `POST /api/export-flashcards` endpoints |
| `frontend/src/App.jsx` | **Modify** | Add Flashcard Generator UI card below Study Guide in Tools tab |
| `tests/test_flashcards.py` | **Create** | Tests for generation + export |

---

### Task 1: Backend — flashcard generation + export endpoints

**Files:**
- Modify: `backend/routes/planner_routes.py`
- Create: `tests/test_flashcards.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_flashcards.py`:

```python
"""Tests for flashcard generation and export."""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


def _make_app():
    """Create a minimal Flask app with planner routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.config['RATELIMIT_ENABLED'] = False

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.planner_routes import planner_bp
    app.register_blueprint(planner_bp)
    return app


def _mock_gemini_response(text):
    """Create a mock Gemini response."""
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.usage_metadata = MagicMock()
    mock_resp.usage_metadata.prompt_token_count = 100
    mock_resp.usage_metadata.candidates_token_count = 300
    return mock_resp


SAMPLE_FLASHCARDS = json.dumps({
    "title": "Unit 3: The Constitution",
    "cards": [
        {"term": "Federalism", "definition": "Division of power between national and state governments."},
        {"term": "Ratification", "definition": "Formal approval of the Constitution by the states."},
        {"term": "Amendment", "definition": "A change or addition to the Constitution."},
        {"term": "Bill of Rights", "definition": "The first ten amendments to the Constitution, guaranteeing individual rights."},
        {"term": "Separation of Powers", "definition": "Division of government into three branches: legislative, executive, and judicial."},
        {"term": "Checks and Balances", "definition": "System where each branch can limit the powers of the other branches."},
    ]
})


class TestGenerateFlashcards:
    def test_returns_flashcards_json(self):
        """Should return structured flashcards from Gemini."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_FLASHCARDS)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-flashcards', json={
                    "title": "Constitution Flashcards",
                    "content": "Federalism is the division of power...",
                    "subject": "US History",
                    "grade": "8",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            data = resp.get_json()
            assert "flashcards" in data
            assert len(data["flashcards"]["cards"]) == 6
            assert data["flashcards"]["cards"][0]["term"] == "Federalism"

    def test_returns_400_without_content(self):
        """Should reject requests without content."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.post('/api/generate-flashcards', json={
                "title": "Empty",
            }, headers={"X-Test-Teacher-Id": "teacher-1"})
        assert resp.status_code == 400

    def test_handles_gemini_error(self):
        """Should return 500 on Gemini failure."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = Exception("API error")
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-flashcards', json={
                    "title": "Broken",
                    "content": "Some content",
                    "subject": "Math",
                    "grade": "7",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 500

    def test_includes_lesson_plan_vocab(self):
        """Should incorporate lesson plan vocabulary into the prompt."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_FLASHCARDS)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-flashcards', json={
                    "title": "Vocab Cards",
                    "content": "Day 1: Introduction to the Constitution",
                    "lessonPlan": {
                        "title": "Constitution Unit",
                        "vocabulary": ["federalism", "ratification", "amendment"],
                    },
                    "subject": "US History",
                    "grade": "8",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            call_args = mock_model.generate_content.call_args[0][0]
            assert "federalism" in call_args

    def test_respects_global_ai_notes(self):
        """Should include globalAINotes in the prompt."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_FLASHCARDS)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-flashcards', json={
                    "title": "Cards",
                    "content": "Some content",
                    "subject": "Science",
                    "grade": "6",
                    "globalAINotes": "Use simplified vocabulary for grade 6",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            call_args = mock_model.generate_content.call_args[0][0]
            assert "simplified vocabulary" in call_args

    def test_custom_card_count(self):
        """Should pass card count to the prompt."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_FLASHCARDS)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-flashcards', json={
                    "title": "Cards",
                    "content": "Some content",
                    "subject": "Math",
                    "grade": "7",
                    "cardCount": 20,
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            call_args = mock_model.generate_content.call_args[0][0]
            assert "20" in call_args


class TestExportFlashcards:
    def test_exports_pdf(self):
        """Should export flashcards as PDF with card grid."""
        app = _make_app()
        cards = json.loads(SAMPLE_FLASHCARDS)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-flashcards', json={
                    "flashcards": cards,
                    "format": "pdf",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert resp.content_type == 'application/pdf'
        assert resp.data[:5] == b'%PDF-'

    def test_exports_docx(self):
        """Should export flashcards as DOCX with term/definition table."""
        app = _make_app()
        cards = json.loads(SAMPLE_FLASHCARDS)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-flashcards', json={
                    "flashcards": cards,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert 'wordprocessingml' in resp.content_type

    def test_docx_contains_terms(self):
        """Exported DOCX should contain the flashcard terms."""
        from docx import Document
        from io import BytesIO
        app = _make_app()
        cards = json.loads(SAMPLE_FLASHCARDS)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-flashcards', json={
                    "flashcards": cards,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        doc = Document(BytesIO(resp.data))
        text = "\n".join(p.text for p in doc.paragraphs)
        tables_text = "\n".join(
            cell.text for table in doc.tables for row in table.rows for cell in row.cells
        )
        all_text = text + tables_text
        assert "Federalism" in all_text
        assert "Ratification" in all_text

    def test_returns_400_without_flashcards(self):
        """Should reject requests without flashcard data."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.post('/api/export-flashcards', json={
                "format": "pdf",
            }, headers={"X-Test-Teacher-Id": "teacher-1"})
        assert resp.status_code == 400

    def test_defaults_to_pdf(self):
        """Should default to PDF when no format specified."""
        app = _make_app()
        cards = json.loads(SAMPLE_FLASHCARDS)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-flashcards', json={
                    "flashcards": cards,
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert resp.content_type == 'application/pdf'

    def test_empty_cards_does_not_crash(self):
        """Should handle empty card list gracefully."""
        app = _make_app()
        cards = {"title": "Empty Set", "cards": []}
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-flashcards', json={
                    "flashcards": cards,
                    "format": "pdf",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_flashcards.py -v`
Expected: FAIL (endpoints don't exist)

- [ ] **Step 3: Implement generation endpoint**

Add to the END of `backend/routes/planner_routes.py` (after the study guide export endpoint):

```python
# ══════════════════════════════════════════════════════════════
# FLASHCARD GENERATION
# ══════════════════════════════════════════════════════════════

@planner_bp.route('/api/generate-flashcards', methods=['POST'])
@require_teacher
@handle_route_errors
def generate_flashcards():
    """Generate flashcards from content using Gemini Flash."""
    data = request.get_json(silent=True) or {}

    content = data.get('content', '').strip()
    title = data.get('title', 'Flashcards')
    subject = data.get('subject', '')
    grade = data.get('grade', '')
    instructions = data.get('instructions', '')
    global_ai_notes = data.get('globalAINotes', '')
    lesson_plan = data.get('lessonPlan')
    card_count = data.get('cardCount', 15)

    if not content and not lesson_plan:
        return jsonify({"error": "Provide content or a lesson plan to generate flashcards."}), 400

    user_id = getattr(g, 'user_id', 'local-dev')

    prompt_parts = []
    prompt_parts.append("You are an expert " + subject + " teacher creating flashcards for grade " + grade + " students.")

    if global_ai_notes:
        prompt_parts.append("")
        prompt_parts.append("=== TEACHER INSTRUCTIONS (MUST FOLLOW) ===")
        prompt_parts.append(global_ai_notes)
        prompt_parts.append("=== END TEACHER INSTRUCTIONS ===")

    prompt_parts.append("")
    prompt_parts.append("Generate " + str(card_count) + " flashcards in JSON format:")
    prompt_parts.append('- "title": string (flashcard set title)')
    prompt_parts.append('- "cards": array of {"term": string, "definition": string}')
    prompt_parts.append("")
    prompt_parts.append("Guidelines:")
    prompt_parts.append("- Each term should be a key vocabulary word, concept, person, or event")
    prompt_parts.append("- Each definition should be concise (1-2 sentences max)")
    prompt_parts.append("- Use age-appropriate language for grade " + grade)
    prompt_parts.append("- Focus on the most important terms from the source material")
    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON. No markdown, no code fences, no extra text.")

    if lesson_plan:
        prompt_parts.append("")
        prompt_parts.append("=== LESSON PLAN ===")
        prompt_parts.append("Title: " + (lesson_plan.get('title', '') or ''))
        if lesson_plan.get('overview'):
            prompt_parts.append("Overview: " + lesson_plan['overview'])
        if lesson_plan.get('vocabulary'):
            prompt_parts.append("Key Vocabulary: " + ", ".join(lesson_plan['vocabulary']))
        if lesson_plan.get('objectives'):
            prompt_parts.append("Objectives:")
            for obj in lesson_plan['objectives']:
                prompt_parts.append("  - " + obj)
        prompt_parts.append("=== END LESSON PLAN ===")

    if content:
        prompt_parts.append("")
        prompt_parts.append("=== SOURCE CONTENT ===")
        prompt_parts.append(content[:8000])
        prompt_parts.append("=== END SOURCE CONTENT ===")

    if instructions:
        prompt_parts.append("")
        prompt_parts.append("Additional instructions: " + instructions)

    prompt = "\n".join(prompt_parts)

    try:
        from backend.api_keys import get_api_key as _gak
        genai.configure(api_key=_gak('gemini', user_id))
        model = genai.GenerativeModel("gemini-2.0-flash")

        response = with_retry(
            lambda: model.generate_content(prompt),
            label="generate_flashcards",
        )

        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

        flashcards = json.loads(response_text)

        return jsonify({
            "flashcards": flashcards,
            "title": flashcards.get("title", title),
        })

    except json.JSONDecodeError as e:
        logger.error("Flashcard JSON parse failed: %s", e)
        return jsonify({"error": "Failed to parse flashcards. Please try again."}), 500
    except Exception as e:
        logger.exception("Flashcard generation failed")
        return jsonify({"error": "Generation failed: " + str(e)[:200]}), 500
```

- [ ] **Step 4: Implement export endpoint**

Add after the generation endpoint:

```python
def _export_flashcards_pdf(flashcards, filepath):
    """Export flashcards as a printable PDF with 2-column card grid."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, Color
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('FCTitle', parent=styles['Title'],
                                  fontSize=16, spaceAfter=16, alignment=1)
    term_style = ParagraphStyle('FCTerm', parent=styles['Normal'],
                                 fontSize=13, alignment=1, leading=16,
                                 textColor=HexColor('#1a56db'))
    def_style = ParagraphStyle('FCDef', parent=styles['Normal'],
                                fontSize=10, alignment=1, leading=13,
                                textColor=HexColor('#374151'))

    story.append(Paragraph(flashcards.get("title", "Flashcards"), title_style))

    cards = flashcards.get("cards", [])
    if not cards:
        story.append(Paragraph("No flashcards generated.", styles['Normal']))
        doc.build(story)
        return

    # Build 2-column table of cards
    card_width = 3.5 * inch
    card_height = 2.2 * inch
    table_data = []
    row = []

    for card in cards:
        cell_content = [
            Paragraph("<b>" + (card.get("term", "") or "") + "</b>", term_style),
            Spacer(1, 8),
            Paragraph(card.get("definition", "") or "", def_style),
        ]
        row.append(cell_content)
        if len(row) == 2:
            table_data.append(row)
            row = []

    if row:
        row.append([Paragraph("", styles['Normal'])])
        table_data.append(row)

    if table_data:
        t = Table(table_data, colWidths=[card_width, card_width],
                  rowHeights=[card_height] * len(table_data))
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor('#d1d5db')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, HexColor('#d1d5db')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(t)

    doc.build(story)


def _export_flashcards_docx(flashcards, filepath):
    """Export flashcards as a DOCX with a 2-column table."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = Document()

    title_para = doc.add_heading(flashcards.get("title", "Flashcards"), level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title_para.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)

    cards = flashcards.get("cards", [])
    if not cards:
        doc.add_paragraph("No flashcards generated.")
        doc.save(filepath)
        return

    table = doc.add_table(rows=len(cards), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, card in enumerate(cards):
        term_cell = table.cell(i, 0)
        def_cell = table.cell(i, 1)

        term_para = term_cell.paragraphs[0]
        term_run = term_para.add_run(card.get("term", ""))
        term_run.bold = True
        term_run.font.size = Pt(12)
        term_run.font.color.rgb = RGBColor(26, 86, 219)

        def_para = def_cell.paragraphs[0]
        def_run = def_para.add_run(card.get("definition", ""))
        def_run.font.size = Pt(11)

    doc.save(filepath)


@planner_bp.route('/api/export-flashcards', methods=['POST'])
@require_teacher
@handle_route_errors
def export_flashcards():
    """Export flashcards to PDF or DOCX."""
    data = request.get_json(silent=True) or {}
    flashcards = data.get('flashcards')
    fmt = data.get('format', 'pdf').lower()

    if not flashcards:
        return jsonify({"error": "No flashcard data provided."}), 400

    title = flashcards.get("title", "Flashcards")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
    export_dir = _get_export_dir()

    try:
        if fmt == 'docx':
            filepath = os.path.join(export_dir, safe_title + ".docx")
            _export_flashcards_docx(flashcards, filepath)
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            filepath = os.path.join(export_dir, safe_title + ".pdf")
            _export_flashcards_pdf(flashcards, filepath)
            mimetype = 'application/pdf'

        return send_file(filepath, mimetype=mimetype, as_attachment=True,
                         download_name=os.path.basename(filepath))

    except Exception as e:
        logger.exception("Flashcard export failed")
        return jsonify({"error": "Export failed: " + str(e)[:200]}), 500
```

- [ ] **Step 5: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_flashcards.py -v`
Expected: All 12 tests PASS (6 generation + 6 export)

- [ ] **Step 6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/planner_routes.py tests/test_flashcards.py
git commit -m "feat: add flashcard generation and export endpoints (Gemini Flash)"
```

---

### Task 2: Frontend — Flashcard Generator UI

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add flashcard state variables**

Find the study guide state variables (~search for `const [studyGuide`). Add immediately after:

```javascript
  // Flashcard state
  const [flashcards, setFlashcards] = useState(null);
  const [flashcardsGenerating, setFlashcardsGenerating] = useState(false);
  const [flashcardInstructions, setFlashcardInstructions] = useState('');
  const [flashcardCount, setFlashcardCount] = useState(15);
```

- [ ] **Step 2: Add Flashcard Generator UI card below the Study Guide section**

Find the closing `</div>` of the Study Guide Generator glass-card (after the Export PDF button, around line 15115). Add IMMEDIATELY AFTER that closing div:

```javascript
                      {/* Flashcard Generator */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Layers" size={22} style={{ color: "#f59e0b" }} />
                          Flashcard Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate printable flashcards from your lesson plan or content. Terms on front, definitions on back.
                        </p>

                        <div style={{ display: "flex", gap: "12px", marginBottom: "12px" }}>
                          <div style={{ flex: 1 }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>
                              Number of cards
                            </label>
                            <select
                              value={flashcardCount}
                              onChange={function(e) { setFlashcardCount(parseInt(e.target.value)); }}
                              className="input"
                              style={{ maxWidth: "120px" }}
                            >
                              <option value={10}>10</option>
                              <option value={15}>15</option>
                              <option value={20}>20</option>
                              <option value={25}>25</option>
                              <option value={30}>30</option>
                            </select>
                          </div>
                          <div style={{ flex: 2 }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>
                              Custom Instructions (optional)
                            </label>
                            <input
                              type="text"
                              value={flashcardInstructions}
                              onChange={function(e) { setFlashcardInstructions(e.target.value); }}
                              placeholder="e.g., Focus on Chapter 5 vocabulary only"
                              className="input"
                            />
                          </div>
                        </div>

                        <button
                          onClick={async function() {
                            setFlashcardsGenerating(true);
                            setFlashcards(null);
                            try {
                              var content = '';
                              if (lessonPlan && lessonPlan.overview) {
                                content = lessonPlan.overview + String.fromCharCode(10) + (lessonPlan.days || []).map(function(d) { return 'Day ' + d.day + ': ' + d.topic; }).join(String.fromCharCode(10));
                              }
                              if (generatedAssignment) {
                                var sections = generatedAssignment.sections || generatedAssignment.questions || [];
                                content += String.fromCharCode(10) + sections.map(function(s) {
                                  if (s.questions) return s.name + ': ' + s.questions.map(function(q) { return q.question; }).join(', ');
                                  return s.question || '';
                                }).join(String.fromCharCode(10));
                              }
                              if (!content.trim()) {
                                addToast('Generate a lesson plan or assessment first.', 'warning');
                                setFlashcardsGenerating(false);
                                return;
                              }
                              var resp = await fetch('/api/generate-flashcards', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  title: (lessonPlan && lessonPlan.title ? lessonPlan.title : generatedAssignment && generatedAssignment.title ? generatedAssignment.title : 'Flashcards') + ' - Flashcards',
                                  content: content,
                                  lessonPlan: lessonPlan && lessonPlan.overview ? lessonPlan : undefined,
                                  subject: config.subject || '',
                                  grade: config.grade || '',
                                  globalAINotes: config.globalAINotes || '',
                                  instructions: flashcardInstructions,
                                  cardCount: flashcardCount,
                                }),
                              });
                              var data = await resp.json();
                              if (data.error) {
                                addToast(data.error, 'error');
                              } else {
                                setFlashcards(data.flashcards);
                                addToast('Flashcards generated!', 'success');
                                api.saveResource(data.flashcards, 'flashcards', data.title || 'Flashcards');
                              }
                            } catch (err) {
                              addToast('Failed to generate flashcards: ' + err.message, 'error');
                            }
                            setFlashcardsGenerating(false);
                          }}
                          disabled={flashcardsGenerating || (!lessonPlan && !generatedAssignment)}
                          className="btn btn-primary"
                          style={{ padding: "10px 24px", background: "linear-gradient(135deg, #f59e0b, #d97706)", display: "flex", alignItems: "center", gap: "8px" }}
                        >
                          {flashcardsGenerating ? (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }), " Generating...")
                          ) : (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Layers", size: 16 }), " Generate Flashcards")
                          )}
                        </button>

                        {flashcards && (
                          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
                            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
                              {flashcards.title || 'Flashcards'} ({(flashcards.cards || []).length} cards)
                            </h4>

                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "12px", marginBottom: "16px" }}>
                              {(flashcards.cards || []).map(function(card, ci) {
                                return (
                                  <div key={ci} style={{ padding: "16px", borderRadius: "10px", border: "1px solid var(--border)", background: "var(--input-bg)" }}>
                                    <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f59e0b", marginBottom: "8px" }}>
                                      {card.term}
                                    </div>
                                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                      {card.definition}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                onClick={async function() {
                                  try {
                                    var resp = await fetch('/api/export-flashcards', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ flashcards: flashcards, format: 'pdf' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (flashcards.title || 'Flashcards') + '.pdf';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileDown" size={16} /> Export PDF
                              </button>
                              <button
                                onClick={async function() {
                                  try {
                                    var resp = await fetch('/api/export-flashcards', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ flashcards: flashcards, format: 'docx' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (flashcards.title || 'Flashcards') + '.docx';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileText" size={16} /> Export DOCX
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
```

- [ ] **Step 3: Build frontend**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/App.jsx
git commit -m "feat: add Flashcard Generator UI to Tools tab"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Generation + export endpoints + 12 tests | Modify `planner_routes.py`, create `test_flashcards.py` | Low — new endpoints, same pattern as study guide |
| 2 | Flashcard Generator UI in Tools tab | Modify `App.jsx` | Low — adds card below study guide |

**Total: 2 new endpoints, 12 tests, 1 UI card.**

**Cost:** ~$0.001 per flashcard set (Gemini 2.0 Flash).

**What teachers see:**
1. Go to Tools tab in Planner
2. Below Study Guide: Flashcard Generator card
3. Pick number of cards (10-30), optional instructions
4. Click "Generate Flashcards" → preview grid of term/definition cards
5. Export as PDF (printable 2-column card grid with cut lines) or DOCX (table)
6. Auto-saved to Resources library
