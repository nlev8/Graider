# Study Guide Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the NotebookLM Materials UI with a native study guide generator that uses Gemini Flash to produce study guides from lesson plans and uploaded content, exportable as DOCX/PDF.

**Architecture:** New backend endpoint `POST /api/generate-study-guide` takes lesson plan content + optional uploaded documents + subject/grade context, sends to Gemini 2.0 Flash, returns structured JSON (sections with key concepts, vocabulary, review questions, summary). Frontend replaces the NotebookLM Materials block in the Tools tab with a simpler "Study Guide" card. Export reuses the existing `python-docx` and ReportLab patterns. Auto-saves to resources library via existing `save-resource` endpoint.

**Tech Stack:** Gemini 2.0 Flash (`google-generativeai`), python-docx, ReportLab, existing Flask export patterns

**Review history:**
- Rev 1: Initial plan (3 tasks, 9 tests)
- Rev 2: Fixed API key helper (uses `_gak` not `_get_api_key_for_user`), added export test assertions for file content, documented all NotebookLM references to clean up (3 files, 206 refs), confirmed Gemini SDK accepts plain string for generate_content
- Rev 3: Test app patches limiter to no-op (avoids shared state conflicts). Task 3 now strips unused NotebookLM state from App.jsx (not just hides UI). Export tests already cover /api/export-study-guide endpoint (TestExportStudyGuide class).

**Implementation notes:**
- API key helper in planner_routes.py: `from backend.api_keys import get_api_key as _gak` then `_gak('gemini', user_id)`
- Gemini SDK: `generate_content(prompt_string)` accepts plain strings (verified in assignment_grader.py:4647)
- NotebookLM references span 3 files: App.jsx (115 refs), api.js (13 refs), PlannerTab.jsx (90 refs). Task 3 replaces the UI block in App.jsx. The api.js functions and PlannerTab.jsx refs become dead code but are left intact (not breaking, can be cleaned up later). State variables in App.jsx that are only used by the NotebookLM section become unused but harmless.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/planner_routes.py` | **Modify** | Add `POST /api/generate-study-guide` endpoint + `POST /api/export-study-guide` endpoint |
| `frontend/src/App.jsx` | **Modify** | Replace NotebookLM Materials section with Study Guide generator UI, hide NotebookLM "Materials" button |
| `tests/test_study_guide.py` | **Create** | Tests for study guide generation + export |

---

### Task 1: Backend — study guide generation endpoint

**Files:**
- Modify: `backend/routes/planner_routes.py`
- Create: `tests/test_study_guide.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_study_guide.py`:

```python
"""Tests for study guide generation and export."""

import json
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


def _make_app():
    """Create a minimal Flask app with planner routes.

    Patches the limiter to a no-op to avoid shared state conflicts
    when other tests have already initialized it.
    """
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.config['RATELIMIT_ENABLED'] = False  # Disable rate limiting in tests

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
    mock_resp.usage_metadata.candidates_token_count = 500
    return mock_resp


SAMPLE_STUDY_GUIDE = json.dumps({
    "title": "Unit 3: The Constitution",
    "sections": [
        {
            "heading": "Key Concepts",
            "content": [
                "The Constitution establishes three branches of government.",
                "Separation of powers prevents any one branch from dominating."
            ]
        },
        {
            "heading": "Vocabulary",
            "terms": [
                {"term": "Federalism", "definition": "Division of power between national and state governments."},
                {"term": "Ratification", "definition": "Formal approval of the Constitution by the states."}
            ]
        },
        {
            "heading": "Review Questions",
            "questions": [
                {"question": "What are the three branches of government?", "answer": "Legislative, Executive, and Judicial."},
                {"question": "Why is separation of powers important?", "answer": "It prevents tyranny by ensuring no single branch has too much power."}
            ]
        },
        {
            "heading": "Summary",
            "content": ["The Constitution created a federal system with checks and balances to protect individual rights."]
        }
    ]
})


class TestGenerateStudyGuide:
    def test_returns_study_guide_json(self):
        """Should return structured study guide from Gemini."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_STUDY_GUIDE)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Unit 3 Study Guide",
                    "content": "The Constitution establishes three branches...",
                    "subject": "US History",
                    "grade": "8",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            data = resp.get_json()
            assert "study_guide" in data
            assert data["study_guide"]["title"] == "Unit 3: The Constitution"
            assert len(data["study_guide"]["sections"]) == 4

    def test_returns_400_without_content(self):
        """Should reject requests without content."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.post('/api/generate-study-guide', json={
                "title": "Empty Guide",
            }, headers={"X-Test-Teacher-Id": "teacher-1"})
        assert resp.status_code == 400

    def test_handles_gemini_error(self):
        """Should return 500 with message on Gemini failure."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = Exception("API error")
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Broken Guide",
                    "content": "Some content",
                    "subject": "Math",
                    "grade": "7",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 500
            assert "error" in resp.get_json()

    def test_includes_lesson_plan_content(self):
        """Should incorporate lesson plan sections into the prompt."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_STUDY_GUIDE)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Lesson Review",
                    "content": "Day 1: Introduction to fractions...",
                    "lessonPlan": {
                        "title": "Fractions Unit",
                        "overview": "Students learn to add and subtract fractions.",
                        "days": [{"day": 1, "topic": "Intro to fractions"}]
                    },
                    "subject": "Math",
                    "grade": "6",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            # Verify lesson plan was included in the prompt
            call_args = mock_model.generate_content.call_args[0][0]
            assert "Fractions Unit" in call_args

    def test_includes_custom_instructions(self):
        """Should pass custom instructions to the prompt."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.routes.planner_routes.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_gemini_response(SAMPLE_STUDY_GUIDE)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Custom Guide",
                    "content": "Some content",
                    "subject": "Science",
                    "grade": "7",
                    "instructions": "Focus on lab safety procedures",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            call_args = mock_model.generate_content.call_args[0][0]
            assert "lab safety procedures" in call_args
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_study_guide.py -v`
Expected: FAIL (endpoint doesn't exist yet)

- [ ] **Step 3: Implement the generation endpoint**

In `backend/routes/planner_routes.py`, add at the end of the file (before the final blueprint registration, if any) or after the last route:

```python
# ══════════════════════════════════════════════════════════════
# STUDY GUIDE GENERATION
# ══════════════════════════════════════════════════════════════

@planner_bp.route('/api/generate-study-guide', methods=['POST'])
@require_teacher
@handle_route_errors
def generate_study_guide():
    """Generate a structured study guide from content using Gemini Flash."""
    data = request.get_json(silent=True) or {}

    content = data.get('content', '').strip()
    title = data.get('title', 'Study Guide')
    subject = data.get('subject', '')
    grade = data.get('grade', '')
    instructions = data.get('instructions', '')
    lesson_plan = data.get('lessonPlan')

    if not content and not lesson_plan:
        return jsonify({"error": "Provide content or a lesson plan to generate a study guide."}), 400

    user_id = getattr(g, 'user_id', 'local-dev')

    # Build the prompt
    prompt_parts = []
    prompt_parts.append(f"You are an expert {subject} teacher creating a study guide for grade {grade} students.")
    prompt_parts.append("")
    prompt_parts.append("Generate a comprehensive study guide in JSON format with these sections:")
    prompt_parts.append('- "title": string')
    prompt_parts.append('- "sections": array of objects, each with:')
    prompt_parts.append('  - "heading": string (section name)')
    prompt_parts.append('  - "content": array of strings (bullet points) — for Key Concepts, Summary')
    prompt_parts.append('  - "terms": array of {"term": string, "definition": string} — for Vocabulary section')
    prompt_parts.append('  - "questions": array of {"question": string, "answer": string} — for Review Questions')
    prompt_parts.append("")
    prompt_parts.append("Include these sections in order:")
    prompt_parts.append("1. Key Concepts — main ideas students should understand")
    prompt_parts.append("2. Vocabulary — important terms with definitions")
    prompt_parts.append("3. Review Questions — 5-8 questions with answers to help students self-test")
    prompt_parts.append("4. Summary — concise recap of the material")
    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON. No markdown, no code fences, no extra text.")

    if lesson_plan:
        prompt_parts.append("")
        prompt_parts.append("=== LESSON PLAN ===")
        prompt_parts.append(f"Title: {lesson_plan.get('title', '')}")
        if lesson_plan.get('overview'):
            prompt_parts.append(f"Overview: {lesson_plan['overview']}")
        if lesson_plan.get('objectives'):
            prompt_parts.append("Objectives:")
            for obj in lesson_plan['objectives']:
                prompt_parts.append(f"  - {obj}")
        if lesson_plan.get('vocabulary'):
            prompt_parts.append("Vocabulary: " + ", ".join(lesson_plan['vocabulary']))
        if lesson_plan.get('days'):
            for day in lesson_plan['days']:
                prompt_parts.append(f"Day {day.get('day', '?')}: {day.get('topic', '')}")
        prompt_parts.append("=== END LESSON PLAN ===")

    if content:
        prompt_parts.append("")
        prompt_parts.append("=== SOURCE CONTENT ===")
        prompt_parts.append(content[:8000])
        prompt_parts.append("=== END SOURCE CONTENT ===")

    if instructions:
        prompt_parts.append("")
        prompt_parts.append(f"Additional instructions: {instructions}")

    prompt = "\n".join(prompt_parts)

    try:
        import google.generativeai as genai
        from backend.api_keys import get_api_key as _gak
        genai.configure(api_key=_gak('gemini', user_id))
        model = genai.GenerativeModel("gemini-2.0-flash")

        response = with_retry(
            lambda: model.generate_content(prompt),
            label="generate_study_guide",
        )

        response_text = response.text.strip()
        # Strip markdown code fences if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

        study_guide = json.loads(response_text)

        return jsonify({
            "study_guide": study_guide,
            "title": study_guide.get("title", title),
        })

    except json.JSONDecodeError as e:
        logger.error("Study guide JSON parse failed: %s", e)
        return jsonify({"error": "Failed to parse study guide. Please try again."}), 500
    except Exception as e:
        logger.exception("Study guide generation failed")
        return jsonify({"error": f"Generation failed: {str(e)[:200]}"}), 500
```

Note: `_get_api_key_for_user` is the existing helper in planner_routes.py (search for it — it wraps `get_api_key` with teacher_id). If named differently, use the actual function name. Also `with_retry` is already imported from the retry-with-backoff work.

- [ ] **Step 4: Verify the function name for getting API keys**

Search `planner_routes.py` for the Gemini API key helper:
```bash
grep -n "def _get_api_key\|def _gak\|_get_api_key_for_user\|get_api_key.*gemini" backend/routes/planner_routes.py | head -5
```
Use whatever function name is found. Common patterns: `_gak('gemini', user_id)` or `get_api_key('gemini', user_id)`.

- [ ] **Step 5: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_study_guide.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/planner_routes.py tests/test_study_guide.py
git commit -m "feat: add study guide generation endpoint using Gemini Flash"
```

---

### Task 2: Backend — study guide export (DOCX/PDF)

**Files:**
- Modify: `backend/routes/planner_routes.py`
- Modify: `tests/test_study_guide.py`

- [ ] **Step 1: Write failing tests for export**

Append to `tests/test_study_guide.py`:

```python
import os
import tempfile


class TestExportStudyGuide:
    def test_exports_docx(self):
        """Should export study guide as DOCX with actual content."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_study_guide_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        # Verify file is non-trivial (DOCX with 4 sections should be > 5KB)
        assert len(resp.data) > 5000

    def test_docx_contains_sections(self):
        """Exported DOCX should contain the study guide sections."""
        from docx import Document
        from io import BytesIO
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_study_guide_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        doc = Document(BytesIO(resp.data))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "Key Concepts" in text
        assert "Vocabulary" in text
        assert "Federalism" in text
        assert "Review Questions" in text

    def test_exports_pdf(self):
        """Should export study guide as valid PDF."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_study_guide_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "pdf",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert resp.content_type == 'application/pdf'
        # Verify it's a real PDF (starts with %PDF)
        assert resp.data[:5] == b'%PDF-'
        assert len(resp.data) > 3000

    def test_returns_400_without_study_guide(self):
        """Should reject requests without study_guide data."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.post('/api/export-study-guide', json={
                "format": "docx",
            }, headers={"X-Test-Teacher-Id": "teacher-1"})
        assert resp.status_code == 400

    def test_defaults_to_docx(self):
        """Should default to DOCX when no format specified."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_study_guide_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert 'wordprocessingml' in resp.content_type

    def test_export_handles_empty_sections(self):
        """Should not crash when study guide has empty sections."""
        app = _make_app()
        guide = {"title": "Empty Guide", "sections": [
            {"heading": "Empty", "content": []},
            {"heading": "No terms", "terms": []},
            {"heading": "No questions", "questions": []},
        ]}
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_study_guide_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
```

- [ ] **Step 2: Implement the export endpoint**

Add to `backend/routes/planner_routes.py` after the generate endpoint:

```python
def _get_study_guide_export_dir():
    """Get temp directory for study guide exports."""
    d = os.path.join(tempfile.gettempdir(), "graider_study_guides")
    os.makedirs(d, exist_ok=True)
    return d


def _export_study_guide_docx(study_guide, filepath):
    """Export a study guide to DOCX format."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Title
    title_para = doc.add_heading(study_guide.get("title", "Study Guide"), level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title_para.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)

    doc.add_paragraph("")

    for section in study_guide.get("sections", []):
        heading = section.get("heading", "")
        doc.add_heading(heading, level=1)

        # Key Concepts / Summary — bullet points
        if section.get("content"):
            for point in section["content"]:
                para = doc.add_paragraph(point, style='List Bullet')
                para.paragraph_format.space_after = Pt(4)

        # Vocabulary — term: definition
        if section.get("terms"):
            for item in section["terms"]:
                para = doc.add_paragraph()
                run_term = para.add_run(item.get("term", "") + ": ")
                run_term.bold = True
                run_term.font.size = Pt(11)
                run_def = para.add_run(item.get("definition", ""))
                run_def.font.size = Pt(11)
                para.paragraph_format.space_after = Pt(4)

        # Review Questions — numbered Q&A
        if section.get("questions"):
            for i, qa in enumerate(section["questions"], 1):
                q_para = doc.add_paragraph()
                q_run = q_para.add_run(f"{i}. {qa.get('question', '')}")
                q_run.bold = True
                q_run.font.size = Pt(11)

                a_para = doc.add_paragraph()
                a_run = a_para.add_run(f"   Answer: {qa.get('answer', '')}")
                a_run.font.size = Pt(10)
                a_run.font.color.rgb = RGBColor(80, 80, 80)
                a_para.paragraph_format.space_after = Pt(8)

    doc.save(filepath)


def _export_study_guide_pdf(study_guide, filepath):
    """Export a study guide to PDF format."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('SGTitle', parent=styles['Title'],
                                  fontSize=20, spaceAfter=20, alignment=1)
    story.append(Paragraph(study_guide.get("title", "Study Guide"), title_style))
    story.append(Spacer(1, 12))

    heading_style = ParagraphStyle('SGHeading', parent=styles['Heading2'],
                                    fontSize=14, spaceAfter=8, spaceBefore=16,
                                    textColor=HexColor('#1a56db'))
    body_style = ParagraphStyle('SGBody', parent=styles['Normal'],
                                 fontSize=11, spaceAfter=4, leftIndent=12)
    term_style = ParagraphStyle('SGTerm', parent=styles['Normal'],
                                 fontSize=11, spaceAfter=4, leftIndent=12)
    q_style = ParagraphStyle('SGQuestion', parent=styles['Normal'],
                              fontSize=11, spaceAfter=2, leftIndent=12)
    a_style = ParagraphStyle('SGAnswer', parent=styles['Normal'],
                              fontSize=10, spaceAfter=8, leftIndent=24,
                              textColor=HexColor('#555555'))

    for section in study_guide.get("sections", []):
        heading = section.get("heading", "")
        story.append(Paragraph(heading, heading_style))

        if section.get("content"):
            for point in section["content"]:
                story.append(Paragraph("&bull; " + point, body_style))

        if section.get("terms"):
            for item in section["terms"]:
                term = item.get("term", "")
                defn = item.get("definition", "")
                story.append(Paragraph(f"<b>{term}:</b> {defn}", term_style))

        if section.get("questions"):
            for i, qa in enumerate(section["questions"], 1):
                story.append(Paragraph(f"<b>{i}. {qa.get('question', '')}</b>", q_style))
                story.append(Paragraph(f"Answer: {qa.get('answer', '')}", a_style))

    doc.build(story)


@planner_bp.route('/api/export-study-guide', methods=['POST'])
@require_teacher
@handle_route_errors
def export_study_guide():
    """Export a study guide to DOCX or PDF."""
    data = request.get_json(silent=True) or {}
    study_guide = data.get('study_guide')
    fmt = data.get('format', 'docx').lower()

    if not study_guide:
        return jsonify({"error": "No study guide data provided."}), 400

    title = study_guide.get("title", "Study Guide")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
    export_dir = _get_study_guide_export_dir()

    try:
        if fmt == 'pdf':
            filepath = os.path.join(export_dir, f"{safe_title}.pdf")
            _export_study_guide_pdf(study_guide, filepath)
            mimetype = 'application/pdf'
        else:
            filepath = os.path.join(export_dir, f"{safe_title}.docx")
            _export_study_guide_docx(study_guide, filepath)
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        return send_file(filepath, mimetype=mimetype, as_attachment=True,
                         download_name=os.path.basename(filepath))

    except Exception as e:
        logger.exception("Study guide export failed")
        return jsonify({"error": f"Export failed: {str(e)[:200]}"}), 500
```

Make sure `send_file` is imported — check if it's already imported at the top of `planner_routes.py`:
```bash
grep -n "from flask import.*send_file" backend/routes/planner_routes.py
```
If not present, add `send_file` to the existing Flask import line.

- [ ] **Step 3: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_study_guide.py -v`
Expected: All 12 tests PASS (5 generation + 7 export)

- [ ] **Step 4: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/planner_routes.py tests/test_study_guide.py
git commit -m "feat: add study guide DOCX/PDF export endpoint"
```

---

### Task 3: Frontend — replace NotebookLM with Study Guide UI

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Hide the "Materials" button that links to NotebookLM**

In `frontend/src/App.jsx`, find the Materials button (~line 10971-10978):

```javascript
                              <button
                                onClick={() => { setNlmIncludePlan(true); setNlmNotebookId(null); setPlannerMode("tools"); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 14px", background: "linear-gradient(135deg, rgba(236,72,153,0.15), rgba(139,92,246,0.15))", border: "1px solid rgba(139,92,246,0.3)" }}
                                title="Generate study materials with NotebookLM"
                              >
                                <Icon name="Sparkles" size={16} /> Materials
                              </button>
```

Replace with a Study Guide button that navigates to tools mode:

```javascript
                              <button
                                onClick={() => { setPlannerMode("tools"); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 14px", background: "linear-gradient(135deg, rgba(6,182,212,0.15), rgba(8,145,178,0.15))", border: "1px solid rgba(6,182,212,0.3)" }}
                                title="Generate study guide from this content"
                              >
                                <Icon name="BookOpen" size={16} /> Study Guide
                              </button>
```

- [ ] **Step 2: Replace NotebookLM state variables with study guide state**

Find the NotebookLM state block (~line 1595-1615):
```javascript
  // NotebookLM materials state
  const [nlmAuthenticated, setNlmAuthenticated] = useState(false);
  const [nlmNotebookId, setNlmNotebookId] = useState(null);
  const [nlmGenerating, setNlmGenerating] = useState(false);
  const [nlmProgress, setNlmProgress] = useState([]);
  const [nlmCompleted, setNlmCompleted] = useState([]);
  const [nlmErrors, setNlmErrors] = useState([]);
  const [nlmMaterials, setNlmMaterials] = useState({});
  const [nlmContextFiles, setNlmContextFiles] = useState([]);
  const [nlmIncludePlan, setNlmIncludePlan] = useState(false);
  const [nlmUploading, setNlmUploading] = useState(false);
  const [nlmDownloading, setNlmDownloading] = useState(null);
  const [nlmSelectedMaterials, setNlmSelectedMaterials] = useState({...});
  const [nlmOptions, setNlmOptions] = useState({});
  const [nlmPreviewData, setNlmPreviewData] = useState(null);
  const [nlmShareResult, setNlmShareResult] = useState(null);
  const [nlmTotalSelected, setNlmTotalSelected] = useState(0);
```

Replace the entire block with:
```javascript
  // Study Guide state
  const [studyGuide, setStudyGuide] = useState(null);
  const [studyGuideGenerating, setStudyGuideGenerating] = useState(false);
  const [studyGuideInstructions, setStudyGuideInstructions] = useState('');
```

- [ ] **Step 2b: Remove NotebookLM useEffect hooks**

Find and remove these useEffect blocks:
1. NotebookLM auth check (~line 2520-2527): `if (activeTab === "planner") { api.notebookLMAuthStatus()...`
2. NotebookLM generation status polling (~line 2535-2560): `if (!nlmGenerating) return; var interval = setInterval...`

- [ ] **Step 2c: Remove the handleNLMGenerate function**

Search for `handleNLMGenerate` or `function handleNLMGenerate` and remove the entire function definition. It's only called from the NotebookLM UI which is being replaced.

- [ ] **Step 2d: Remove NLM_MATERIAL_TYPES constant**

Search for `NLM_MATERIAL_TYPES` and remove the array definition. It's only used in the NotebookLM materials grid.

- [ ] **Step 3: Replace the NotebookLM Materials section with Study Guide UI**

In `frontend/src/App.jsx`, find the NotebookLM Materials block (~line 15072-15455):

```javascript
                      {/* NotebookLM Materials */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 ...>
                          <Icon name="Sparkles" .../>
                          NotebookLM Materials
                        </h3>
                        ... (entire NotebookLM section through line ~15455)
                      </div>
```

Replace the ENTIRE block (from `{/* NotebookLM Materials */}` through the closing `</div>` of that glass-card) with:

```javascript
                      {/* Study Guide Generator */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="BookOpen" size={22} style={{ color: "#06b6d4" }} />
                          Study Guide Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate a study guide from your lesson plan or pasted content. Includes key concepts, vocabulary, review questions, and summary.
                        </p>

                        <div style={{ marginBottom: "12px" }}>
                          <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>
                            Custom Instructions (optional)
                          </label>
                          <textarea
                            value={studyGuideInstructions}
                            onChange={(e) => setStudyGuideInstructions(e.target.value)}
                            placeholder="e.g., Focus on vocabulary from Chapter 5, include diagram descriptions, emphasize lab safety..."
                            style={{ width: "100%", minHeight: "60px", padding: "10px", borderRadius: "8px", border: "1px solid var(--input-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem", resize: "vertical" }}
                          />
                        </div>

                        <button
                          onClick={async () => {
                            setStudyGuideGenerating(true);
                            setStudyGuide(null);
                            try {
                              var content = '';
                              if (lessonPlan && lessonPlan.overview) {
                                content = lessonPlan.overview + '\n' + (lessonPlan.days || []).map(function(d) { return 'Day ' + d.day + ': ' + d.topic; }).join('\n');
                              }
                              if (generatedAssignment) {
                                var sections = generatedAssignment.sections || generatedAssignment.questions || [];
                                content += '\n' + sections.map(function(s) {
                                  if (s.questions) return s.name + ': ' + s.questions.map(function(q) { return q.question; }).join(', ');
                                  return s.question || '';
                                }).join('\n');
                              }
                              if (!content.trim()) {
                                addToast('Generate a lesson plan or assessment first, or use the Reading Level Adjuster to paste content.', 'warning');
                                setStudyGuideGenerating(false);
                                return;
                              }
                              var resp = await fetch('/api/generate-study-guide', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  title: (lessonPlan && lessonPlan.title ? lessonPlan.title : generatedAssignment && generatedAssignment.title ? generatedAssignment.title : 'Study Guide') + ' - Study Guide',
                                  content: content,
                                  lessonPlan: lessonPlan && lessonPlan.overview ? lessonPlan : undefined,
                                  subject: config.subject || '',
                                  grade: config.grade || '',
                                  instructions: studyGuideInstructions,
                                }),
                              });
                              var data = await resp.json();
                              if (data.error) {
                                addToast(data.error, 'error');
                              } else {
                                setStudyGuide(data.study_guide);
                                addToast('Study guide generated!', 'success');
                                // Auto-save to resources
                                api.saveResource(data.study_guide, 'study_guide', data.title || 'Study Guide');
                              }
                            } catch (err) {
                              addToast('Failed to generate study guide: ' + err.message, 'error');
                            }
                            setStudyGuideGenerating(false);
                          }}
                          disabled={studyGuideGenerating || (!lessonPlan && !generatedAssignment)}
                          className="btn btn-primary"
                          style={{ padding: "10px 24px", background: "linear-gradient(135deg, #06b6d4, #0891b2)", display: "flex", alignItems: "center", gap: "8px" }}
                        >
                          {studyGuideGenerating ? (
                            <><Icon name="Loader" size={16} className="spinning" /> Generating...</>
                          ) : (
                            <><Icon name="BookOpen" size={16} /> Generate Study Guide</>
                          )}
                        </button>

                        {studyGuide && (
                          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
                            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
                              {studyGuide.title || 'Study Guide'}
                            </h4>

                            {(studyGuide.sections || []).map(function(section, si) {
                              return (
                                <div key={si} style={{ marginBottom: "16px" }}>
                                  <h5 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#06b6d4", marginBottom: "8px" }}>
                                    {section.heading}
                                  </h5>
                                  {section.content && section.content.map(function(point, pi) {
                                    return <p key={pi} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px" }}>{String.fromCharCode(8226)} {point}</p>;
                                  })}
                                  {section.terms && section.terms.map(function(item, ti) {
                                    return <p key={ti} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px" }}><strong>{item.term}:</strong> {item.definition}</p>;
                                  })}
                                  {section.questions && section.questions.map(function(qa, qi) {
                                    return (
                                      <div key={qi} style={{ marginBottom: "8px", paddingLeft: "12px" }}>
                                        <p style={{ fontSize: "0.85rem", fontWeight: 600 }}>{qi + 1}. {qa.question}</p>
                                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", paddingLeft: "16px" }}>Answer: {qa.answer}</p>
                                      </div>
                                    );
                                  })}
                                </div>
                              );
                            })}

                            <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                              <button
                                onClick={async () => {
                                  try {
                                    var resp = await fetch('/api/export-study-guide', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ study_guide: studyGuide, format: 'docx' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (studyGuide.title || 'Study Guide') + '.docx';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileText" size={16} /> Export DOCX
                              </button>
                              <button
                                onClick={async () => {
                                  try {
                                    var resp = await fetch('/api/export-study-guide', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ study_guide: studyGuide, format: 'pdf' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (studyGuide.title || 'Study Guide') + '.pdf';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileDown" size={16} /> Export PDF
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
```

- [ ] **Step 4: Build and verify**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 5: Run all tests**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -m pytest tests/test_study_guide.py tests/test_retry.py -v
```
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/App.jsx
git commit -m "feat: replace NotebookLM Materials UI with native study guide generator"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Generation endpoint (Gemini Flash) + 5 tests | Modify `planner_routes.py`, create `test_study_guide.py` | Low — new endpoint |
| 2 | Export endpoint (DOCX + PDF) + 7 tests | Modify `planner_routes.py`, modify tests | Low — new endpoint |
| 3 | Frontend UI (replace NotebookLM) | Modify `App.jsx` | Medium — replaces existing UI block |

**Total: 2 new endpoints, 12 tests (5 generation + 7 export), 1 UI replacement.**

**Before:** "Materials" button → NotebookLM (broken for multi-user, uses developer's Google account).
**After:** "Study Guide" button → Gemini Flash generates structured study guide → preview in-app → export DOCX/PDF. Per-teacher, no shared accounts, ~$0.001 per generation.

**What teachers see:**
1. Create a lesson plan or assessment in the Planner
2. Click "Study Guide" button (or go to Tools tab)
3. Optionally add custom instructions ("focus on vocabulary")
4. Click "Generate Study Guide"
5. Preview: Key Concepts, Vocabulary, Review Questions, Summary
6. Export as DOCX or PDF
7. Auto-saved to Resources library
