# Slide Deck Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate professional slide decks from lesson plans with AI-generated themed graphics, varied layouts, and speaker notes — exportable as PowerPoint (.pptx). Quality target: match Google NotebookLM's slide output.

**Architecture:** Three-phase pipeline: (1) Gemini 2.5 Flash generates slide content as structured JSON with layout types and image descriptions per slide, (2) Gemini 2.5 Flash Image generates themed graphics using a style-reference approach (first image is held in memory as a PIL Image and passed as a reference to all subsequent image generation calls within the same request), (3) python-pptx assembles content + images into a .pptx using absolute positioning (no layout masters — all slide element positioning is handled programmatically via coordinates in `slide_generator.py`). New service module `backend/services/slide_generator.py` keeps the heavy logic out of planner_routes.py. Two new endpoints: `POST /api/generate-slides` (content + images) and `POST /api/export-slides` (download .pptx). Frontend adds a Slide Deck card to the Tools tab.

**Implementation notes:**
- **No layout masters:** The .pptx template is a blank 16:9 presentation. All slide layouts (title, content, two-column, etc.) are built programmatically with absolute coordinates. There are no real PowerPoint layout masters.
- **Style-reference caching:** The first generated image is stored as a PIL Image object in memory for the duration of the request. It's passed as a reference image to all subsequent Gemini image generation calls. No disk caching — it lives in the request's Python memory and is garbage collected when the request completes.
- **Temp file cleanup:** Generated images are held in memory as bytes (never written to disk). The only file written is the final .pptx, which goes to `_get_export_dir()` (same temp dir as study guides/flashcards).
- **Error handling for images:** Each image generation call is wrapped in try/except. If one image fails, the slide is rendered without a graphic (text-only fallback). The response includes `images_generated` count so the frontend can tell the user "Generated 10 slides with 3/5 graphics." Uses existing `with_retry` for the text content generation call. The google-genai client calls are individually try/excepted (not retried) because retrying a $0.04 image call that timed out is acceptable loss vs retrying and double-charging.
- **Color/style decisions:** The AI picks colors, layouts, and visual style based on the content — teachers don't choose. Teachers can optionally provide a style prompt ("bold and playful", "Christmas-themed", "professional and minimal") which guides the AI's choices for both content structure and image generation.
- **Two format modes** (matching NotebookLM): "Detailed Deck" (comprehensive, full text, standalone) and "Presenter Slides" (clean visuals, key talking points only).

**Review history:**
- Rev 1: Initial plan (5 tasks, 11 tests)
- Rev 2: Clarified no layout masters (absolute positioning), style-reference held in memory not disk, no temp image files (bytes in memory), per-image error handling with text-only fallback, dropped subject-based color palettes
- Rev 3: AI decides all visual choices (colors, layouts, style) — teacher only provides optional style prompt. Added format selector (Detailed Deck vs Presenter Slides). Dropped teacher color picker. Matches NotebookLM's "just generate" approach.

**Tech Stack:**
- `google-genai` (new SDK) — replaces deprecated `google-generativeai` for image generation
- `python-pptx` — PowerPoint file creation (new dependency)
- `Pillow` — image processing (already installed)
- Gemini 2.5 Flash — text content generation (~$0.001/deck)
- Gemini 2.5 Flash Image — graphic generation (~$0.039/image, ~$0.20/deck with 5 images)

**Cost per teacher per month (normal usage: 4 decks):**
- Text generation: $0.004
- Image generation (5 images × 4 decks): $0.78
- **Total: ~$0.78/teacher/month**

---

## Pre-requisites (run before any task)

### Install new dependencies

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
pip install google-genai python-pptx
pip freeze | grep -i "google-genai\|python-pptx" >> requirements.txt
```

Then manually edit `requirements.txt` to use minimum version format:
```
google-genai>=1.0.0
python-pptx>=1.0.0
```

**Important:** The old `google-generativeai` package stays installed for now — existing study guide/flashcard/grading code uses it. The new `google-genai` package is only used by the slide generator for image generation. They can coexist. A full migration to the new SDK is a separate task.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/slide_generator.py` | **Create** | Core logic: content generation, image generation, PPTX assembly |
| `backend/routes/planner_routes.py` | **Modify** | Add `POST /api/generate-slides` + `POST /api/export-slides` endpoints (thin wrappers) |
| `backend/templates/slide_template.pptx` | **Create** | Professional PowerPoint template with 6 layout masters |
| `frontend/src/App.jsx` | **Modify** | Add Slide Deck Generator UI card in Tools tab |
| `tests/test_slide_generator.py` | **Create** | Tests for content generation, image generation, PPTX assembly, export |
| `requirements.txt` | **Modify** | Add google-genai, python-pptx |

---

### Task 1: Create the slide template (.pptx)

This is the foundation — a professional PowerPoint template with layout masters that python-pptx fills in programmatically.

**Files:**
- Create: `backend/templates/slide_template.pptx`

- [ ] **Step 1: Create the template programmatically**

Create a script `backend/scripts/create_slide_template.py` that generates the template:

```python
"""Generate the professional slide template for Graider.

Run once: python backend/scripts/create_slide_template.py
Creates: backend/templates/slide_template.pptx

This template has 6 slide layouts:
  0: Title Slide (big title, subtitle, full-width image area)
  1: Content Slide (title + bullet points, image on right)
  2: Image Focus (large image with caption below)
  3: Two Column (title + two columns of content)
  4: Key Concept (centered large text with accent background)
  5: Section Divider (section title with decorative bar)
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# Create presentation with 16:9 aspect ratio
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Access the slide master
slide_master = prs.slide_masters[0]

# We'll create layouts by adding slides and using them as reference.
# python-pptx has limited layout creation — instead we create a minimal
# template with a blank layout and handle positioning in code.

# For now, create a single blank layout template.
# The slide_generator.py will handle all positioning programmatically
# using the layout type specified in the JSON.

# Add a blank slide as the only layout
blank_layout = prs.slide_layouts[6]  # Index 6 is typically "Blank"

output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "slide_template.pptx")
prs.save(output_path)
print("Template saved to: " + output_path)
```

Run it:
```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python backend/scripts/create_slide_template.py
```

- [ ] **Step 2: Commit**

```bash
git add backend/scripts/create_slide_template.py backend/templates/slide_template.pptx
git commit -m "feat: create base slide template for deck generator"
```

---

### Task 2: Create the slide generator service

This is the core module. It handles content generation, image generation, and PPTX assembly.

**Files:**
- Create: `backend/services/slide_generator.py`
- Create: `tests/test_slide_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_slide_generator.py`:

```python
"""Tests for slide deck generation service."""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO


SAMPLE_SLIDE_CONTENT = {
    "title": "The Constitution",
    "theme": {
        "primary_color": "#1a56db",
        "secondary_color": "#f59e0b",
        "style_prompt": "flat vector illustration, educational, clean minimal, soft blue and amber palette, no text in images"
    },
    "slides": [
        {
            "layout": "title",
            "title": "The Constitution",
            "subtitle": "Foundations of American Government",
            "image_prompt": "an illustration of the US Constitution document with a quill pen",
            "speaker_notes": "Welcome to our lesson on the Constitution."
        },
        {
            "layout": "content",
            "title": "Three Branches of Government",
            "bullets": [
                "Legislative Branch — makes laws (Congress)",
                "Executive Branch — enforces laws (President)",
                "Judicial Branch — interprets laws (Supreme Court)"
            ],
            "image_prompt": "three pillars representing the branches of government",
            "speaker_notes": "The Constitution divides power into three branches."
        },
        {
            "layout": "key_concept",
            "title": "Separation of Powers",
            "content": "No single branch has too much power. Each branch checks the others.",
            "speaker_notes": "This is the key concept of the lesson."
        },
        {
            "layout": "two_column",
            "title": "Federalists vs Anti-Federalists",
            "left_title": "Federalists",
            "left_bullets": ["Strong central government", "Supported ratification"],
            "right_title": "Anti-Federalists",
            "right_bullets": ["Wanted Bill of Rights", "Feared tyranny"],
            "speaker_notes": "Compare the two sides."
        },
        {
            "layout": "content",
            "title": "The Bill of Rights",
            "bullets": [
                "First 10 amendments to the Constitution",
                "Guarantees individual freedoms",
                "Added to gain Anti-Federalist support"
            ],
            "image_prompt": "a scroll with amendments written on it",
            "speaker_notes": "The Bill of Rights was a compromise."
        },
    ]
}


class TestGenerateSlideContent:
    def test_returns_structured_json(self):
        """Should return slide content with title, theme, and slides array."""
        from backend.services.slide_generator import generate_slide_content

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(SAMPLE_SLIDE_CONTENT)

        with patch('backend.services.slide_generator._get_genai_client') as mock_client:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_resp
            mock_client.return_value.models = mock_model

            # Use the old SDK mock pattern since content gen uses text model
            with patch('backend.services.slide_generator.genai') as mock_genai:
                mock_genai_model = MagicMock()
                mock_genai_model.generate_content.return_value = mock_resp
                mock_genai.GenerativeModel.return_value = mock_genai_model

                result = generate_slide_content(
                    content="The Constitution establishes three branches...",
                    subject="US History",
                    grade="8",
                    title="The Constitution",
                    api_key="fake-key",
                )

        assert "slides" in result
        assert "theme" in result
        assert len(result["slides"]) > 0
        assert result["slides"][0]["layout"] in ("title", "content", "key_concept", "two_column", "image_focus", "section_divider")

    def test_returns_error_without_content(self):
        """Should raise ValueError without content."""
        from backend.services.slide_generator import generate_slide_content

        with pytest.raises(ValueError, match="content"):
            generate_slide_content(content="", subject="Math", grade="7", title="Test", api_key="fake")


class TestGenerateSlideImages:
    def test_generates_images_for_slides_with_prompts(self):
        """Should generate images only for slides that have image_prompt."""
        from backend.services.slide_generator import generate_slide_images

        slides = SAMPLE_SLIDE_CONTENT["slides"]
        theme = SAMPLE_SLIDE_CONTENT["theme"]

        # Create a 1x1 white PNG for the mock
        from PIL import Image
        img = Image.new('RGB', (1024, 576), 'white')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        mock_image_data = img_bytes.getvalue()

        mock_part = MagicMock()
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = mock_image_data

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]

        with patch('backend.services.slide_generator._get_genai_client') as mock_get:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            images = generate_slide_images(slides, theme, api_key="fake-key", max_images=5)

        # Only slides with image_prompt get images (3 out of 5 in sample)
        assert len(images) <= 5
        assert len(images) > 0

    def test_respects_max_images_cap(self):
        """Should not generate more images than max_images."""
        from backend.services.slide_generator import generate_slide_images

        slides = [{"layout": "content", "image_prompt": "img " + str(i)} for i in range(20)]
        theme = SAMPLE_SLIDE_CONTENT["theme"]

        from PIL import Image
        img = Image.new('RGB', (100, 56), 'white')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')

        mock_part = MagicMock()
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = img_bytes.getvalue()

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]

        with patch('backend.services.slide_generator._get_genai_client') as mock_get:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            images = generate_slide_images(slides, theme, api_key="fake-key", max_images=5)

        assert len(images) <= 5


class TestAssemblePptx:
    def test_creates_valid_pptx(self):
        """Should create a valid .pptx file from slide data."""
        from backend.services.slide_generator import assemble_pptx

        slides = SAMPLE_SLIDE_CONTENT["slides"]
        theme = SAMPLE_SLIDE_CONTENT["theme"]
        title = SAMPLE_SLIDE_CONTENT["title"]

        filepath = os.path.join(tempfile.mkdtemp(), "test.pptx")
        assemble_pptx(slides, theme, title, {}, filepath)

        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 10000  # Non-trivial PPTX

        # Verify it's a valid PPTX by opening it
        from pptx import Presentation
        prs = Presentation(filepath)
        assert len(prs.slides) == len(slides)

    def test_includes_speaker_notes(self):
        """Speaker notes should be present on each slide."""
        from backend.services.slide_generator import assemble_pptx
        from pptx import Presentation

        slides = SAMPLE_SLIDE_CONTENT["slides"]
        theme = SAMPLE_SLIDE_CONTENT["theme"]

        filepath = os.path.join(tempfile.mkdtemp(), "test.pptx")
        assemble_pptx(slides, theme, "Test", {}, filepath)

        prs = Presentation(filepath)
        for i, slide in enumerate(prs.slides):
            notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
            if slides[i].get("speaker_notes"):
                assert slides[i]["speaker_notes"] in notes

    def test_embeds_images(self):
        """Slides with images should have picture shapes."""
        from backend.services.slide_generator import assemble_pptx
        from pptx import Presentation
        from pptx.shapes.picture import Picture
        from PIL import Image

        slides = [SAMPLE_SLIDE_CONTENT["slides"][1]]  # Content slide with image_prompt
        theme = SAMPLE_SLIDE_CONTENT["theme"]

        # Create a test image
        img = Image.new('RGB', (1024, 576), 'blue')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        images = {0: img_bytes.getvalue()}

        filepath = os.path.join(tempfile.mkdtemp(), "test.pptx")
        assemble_pptx(slides, theme, "Test", images, filepath)

        prs = Presentation(filepath)
        slide = prs.slides[0]
        has_picture = any(isinstance(shape, Picture) for shape in slide.shapes)
        assert has_picture

    def test_handles_empty_slides(self):
        """Should not crash with empty slides list."""
        from backend.services.slide_generator import assemble_pptx

        filepath = os.path.join(tempfile.mkdtemp(), "test.pptx")
        assemble_pptx([], {"primary_color": "#000"}, "Empty", {}, filepath)

        from pptx import Presentation
        prs = Presentation(filepath)
        assert len(prs.slides) == 0

    def test_all_layout_types(self):
        """Should handle all 6 layout types without crashing."""
        from backend.services.slide_generator import assemble_pptx
        from pptx import Presentation

        slides = [
            {"layout": "title", "title": "Title", "subtitle": "Sub"},
            {"layout": "content", "title": "Content", "bullets": ["A", "B"]},
            {"layout": "image_focus", "title": "Image", "caption": "Caption"},
            {"layout": "two_column", "title": "Compare", "left_title": "L", "left_bullets": ["1"], "right_title": "R", "right_bullets": ["2"]},
            {"layout": "key_concept", "title": "Key", "content": "Big idea"},
            {"layout": "section_divider", "title": "Next Section"},
        ]

        filepath = os.path.join(tempfile.mkdtemp(), "test.pptx")
        assemble_pptx(slides, {"primary_color": "#1a56db", "secondary_color": "#f59e0b"}, "All Layouts", {}, filepath)

        prs = Presentation(filepath)
        assert len(prs.slides) == 6


class TestDeckFormat:
    def test_detailed_format_includes_full_text(self):
        """Detailed format prompt should mention full text and standalone."""
        from backend.services.slide_generator import generate_slide_content

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(SAMPLE_SLIDE_CONTENT)

        with patch('backend.services.slide_generator.genai') as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_resp
            mock_genai.GenerativeModel.return_value = mock_model

            generate_slide_content(
                content="Test content", subject="Math", grade="7",
                title="Test", api_key="fake", deck_format="detailed",
            )

            call_args = mock_model.generate_content.call_args[0][0]
            assert "DETAILED DECK" in call_args

    def test_presenter_format_includes_talking_points(self):
        """Presenter format prompt should mention key talking points."""
        from backend.services.slide_generator import generate_slide_content

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(SAMPLE_SLIDE_CONTENT)

        with patch('backend.services.slide_generator.genai') as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_resp
            mock_genai.GenerativeModel.return_value = mock_model

            generate_slide_content(
                content="Test content", subject="Math", grade="7",
                title="Test", api_key="fake", deck_format="presenter",
            )

            call_args = mock_model.generate_content.call_args[0][0]
            assert "PRESENTER SLIDES" in call_args
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_slide_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.slide_generator'`

- [ ] **Step 3: Implement the slide generator service**

Create `backend/services/slide_generator.py`:

```python
"""
Slide Deck Generator Service
=============================
Generates professional slide decks from lesson plan content.

Three-phase pipeline:
  1. Content generation (Gemini 2.5 Flash text) — structured JSON with layouts
  2. Image generation (Gemini 2.5 Flash Image via google-genai) — themed graphics
  3. PPTX assembly (python-pptx) — builds the PowerPoint file

Usage:
    from backend.services.slide_generator import generate_slide_content, generate_slide_images, assemble_pptx

    content = generate_slide_content(text, subject, grade, title, api_key)
    images = generate_slide_images(content["slides"], content["theme"], api_key)
    assemble_pptx(content["slides"], content["theme"], content["title"], images, filepath)
"""

import json
import logging
import os
from io import BytesIO

logger = logging.getLogger(__name__)

# ── Default color fallback (used only if AI doesn't provide colors) ────

DEFAULT_THEME = {
    "primary_color": "#1a56db",
    "secondary_color": "#60a5fa",
    "accent": "#dbeafe",
}


# ── Phase 1: Content generation ─────────────────────────────────────────

def generate_slide_content(content, subject, grade, title, api_key,
                           lesson_plan=None, global_ai_notes="", instructions="",
                           slide_count=10, deck_format="detailed"):
    """Generate structured slide content from source material.

    The AI decides colors, layouts, and visual style based on the content.
    Teachers optionally provide style instructions.

    Args:
        deck_format: "detailed" (full text, standalone) or "presenter" (key talking points only)

    Returns dict with: title, theme, slides[]
    """
    if not content and not lesson_plan:
        raise ValueError("Provide content or lesson_plan to generate slides.")

    import google.generativeai as genai
    from backend.retry import with_retry

    format_instruction = ""
    if deck_format == "presenter":
        format_instruction = "Create PRESENTER SLIDES: clean, visual slides with only key talking points (2-3 words per bullet). The speaker notes should contain the full detail. Slides should be visually clean with minimal text."
    else:
        format_instruction = "Create a DETAILED DECK: comprehensive slides with full text and details, suitable for emailing or reading standalone without a presenter."

    prompt_parts = []
    prompt_parts.append("You are an expert " + subject + " teacher creating a slide deck for grade " + grade + " students.")
    prompt_parts.append("Create exactly " + str(slide_count) + " slides.")
    prompt_parts.append("")
    prompt_parts.append(format_instruction)

    if global_ai_notes:
        prompt_parts.append("")
        prompt_parts.append("=== TEACHER INSTRUCTIONS (MUST FOLLOW) ===")
        prompt_parts.append(global_ai_notes)
        prompt_parts.append("=== END TEACHER INSTRUCTIONS ===")

    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON with this structure:")
    prompt_parts.append('{')
    prompt_parts.append('  "title": "Deck Title",')
    prompt_parts.append('  "theme": {')
    prompt_parts.append('    "primary_color": "#hex (choose a color that fits the subject and mood)",')
    prompt_parts.append('    "secondary_color": "#hex (complementary accent color)",')
    prompt_parts.append('    "accent": "#hex (light tint for backgrounds)",')
    prompt_parts.append('    "style_description": "brief description of the visual style you chose and why"')
    prompt_parts.append('  },')
    prompt_parts.append('  "slides": [')
    prompt_parts.append('    {')
    prompt_parts.append('      "layout": "title|content|image_focus|two_column|key_concept|section_divider",')
    prompt_parts.append('      "title": "Slide Title",')
    prompt_parts.append('      "subtitle": "Only for title layout",')
    prompt_parts.append('      "bullets": ["Point 1", "Point 2"],')
    prompt_parts.append('      "content": "For key_concept layout - one big idea",')
    prompt_parts.append('      "left_title": "For two_column",')
    prompt_parts.append('      "left_bullets": ["Left 1"],')
    prompt_parts.append('      "right_title": "For two_column",')
    prompt_parts.append('      "right_bullets": ["Right 1"],')
    prompt_parts.append('      "caption": "For image_focus layout",')
    prompt_parts.append('      "image_prompt": "Describe an illustration for this slide. Be specific about the subject matter. Do NOT include text in the image.",')
    prompt_parts.append('      "speaker_notes": "What the teacher should say during this slide"')
    prompt_parts.append('    }')
    prompt_parts.append('  ]')
    prompt_parts.append('}')
    prompt_parts.append("")
    prompt_parts.append("Layout rules:")
    prompt_parts.append("- Slide 1 MUST be layout 'title' with the deck title and subtitle")
    prompt_parts.append("- Use 'content' for most slides (title + 3-5 bullet points + image)")
    prompt_parts.append("- Use 'key_concept' for 1-2 important ideas (large centered text)")
    prompt_parts.append("- Use 'two_column' for comparisons (Federalists vs Anti-Federalists)")
    prompt_parts.append("- Use 'section_divider' between major topics")
    prompt_parts.append("- Use 'image_focus' when a visual needs to be the main focus")
    prompt_parts.append("- Max 5 bullet points per slide. Keep bullets concise.")
    prompt_parts.append("- Every content and title slide MUST have an image_prompt")
    prompt_parts.append("- image_prompt should describe a flat, educational illustration. NO text in images.")
    prompt_parts.append("- speaker_notes on EVERY slide (2-3 sentences of what the teacher says)")
    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON. No markdown, no code fences.")

    if lesson_plan:
        prompt_parts.append("")
        prompt_parts.append("=== LESSON PLAN ===")
        prompt_parts.append("Title: " + (lesson_plan.get('title', '') or ''))
        if lesson_plan.get('overview'):
            prompt_parts.append("Overview: " + lesson_plan['overview'])
        if lesson_plan.get('objectives'):
            prompt_parts.append("Objectives:")
            for obj in lesson_plan['objectives']:
                prompt_parts.append("  - " + str(obj))
        if lesson_plan.get('vocabulary'):
            prompt_parts.append("Vocabulary: " + ", ".join(lesson_plan['vocabulary']))
        if lesson_plan.get('essential_questions'):
            prompt_parts.append("Essential Questions:")
            for eq in lesson_plan['essential_questions']:
                prompt_parts.append("  - " + str(eq))
        if lesson_plan.get('days'):
            for day in lesson_plan['days']:
                prompt_parts.append("Day " + str(day.get('day', '?')) + ": " + str(day.get('topic', '')))
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

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    response = with_retry(
        lambda: model.generate_content(prompt),
        label="generate_slide_content",
    )

    response_text = response.text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3].strip()
    if response_text.startswith("json"):
        response_text = response_text[4:].strip()

    result = json.loads(response_text)

    # Ensure theme exists with required fields (AI should have generated it)
    theme = result.get("theme", {})
    if not theme.get("primary_color"):
        theme["primary_color"] = "#1a56db"
        theme["secondary_color"] = "#60a5fa"
        theme["accent"] = "#dbeafe"
    result["theme"] = theme

    # Build the image style prompt from the AI's chosen theme
    result["theme"]["style_prompt"] = (
        "flat vector illustration, clean minimal educational style, "
        "soft color palette using " + theme["primary_color"] + " and " + theme["secondary_color"] + ", "
        "no text in the image, professional, suitable for a classroom presentation"
    )

    return result


# ── Phase 2: Image generation ───────────────────────────────────────────

def _get_genai_client(api_key):
    """Get the new google-genai client for image generation."""
    from google import genai
    return genai.Client(api_key=api_key)


def generate_slide_images(slides, theme, api_key, max_images=5):
    """Generate themed images for slides that have image_prompt.

    Uses Gemini 2.5 Flash Image with style reference: the first generated
    image becomes the reference for all subsequent images, ensuring visual
    consistency across the deck.

    Args:
        slides: list of slide dicts (from generate_slide_content)
        theme: theme dict with style_prompt
        api_key: Gemini API key
        max_images: cap on number of images generated (cost control)

    Returns:
        dict mapping slide index → PNG image bytes

    Style-reference strategy:
        The first successfully generated image is stored as a PIL Image
        object in memory (not disk). It's passed as a reference image to
        all subsequent Gemini calls in the same request, ensuring visual
        consistency across the deck. The PIL Image is garbage collected
        when the function returns — no cleanup needed.

    Error handling:
        Each image generation is individually try/excepted. If one fails
        (timeout, safety filter, quota), that slide gets no image — the
        PPTX assembler renders it as text-only. No retry on image calls
        (acceptable $0.04 loss vs double-charging on retry). The caller
        sees how many images succeeded via len(returned dict).
    """
    from google.genai import types
    from PIL import Image

    client = _get_genai_client(api_key)
    style_prompt = theme.get("style_prompt", "flat educational illustration, no text")

    # Find slides that need images
    image_slides = []
    for i, slide in enumerate(slides):
        if slide.get("image_prompt"):
            image_slides.append((i, slide["image_prompt"]))

    # Cap at max_images (prioritize first slides — title + early content)
    image_slides = image_slides[:max_images]

    images = {}
    reference_image = None  # PIL Image held in memory for style consistency

    for idx, (slide_index, image_prompt) in enumerate(image_slides):
        try:
            full_prompt = style_prompt + ". " + image_prompt

            contents = []
            if reference_image is not None:
                # Pass the first image as a style reference (PIL Image in memory)
                contents.append(reference_image)
                contents.append(
                    "Generate an illustration in the EXACT same visual style as the reference image above. "
                    + full_prompt
                )
            else:
                contents.append(full_prompt)

            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-image-generation",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                    ),
                ),
            )

            # Extract image bytes from response
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    image_data = part.inline_data.data
                    images[slide_index] = image_data  # Store as bytes in memory

                    # First successful image becomes the style reference
                    if reference_image is None:
                        reference_image = Image.open(BytesIO(image_data))
                        logger.info("Style reference image set from slide %d", slide_index)

                    break

        except Exception as e:
            # Individual image failure — slide renders as text-only (graceful degradation)
            logger.warning("Image generation failed for slide %d (will render text-only): %s", slide_index, e)
            # Do NOT retry — $0.04 loss is acceptable vs double-charging

    logger.info("Generated %d/%d slide images", len(images), len(image_slides))
    # reference_image (PIL Image) is garbage collected when this function returns
    return images


# ── Phase 3: PPTX assembly ──────────────────────────────────────────────

def _hex_to_rgb(hex_color):
    """Convert hex color string to RGBColor."""
    from pptx.dml.color import RGBColor
    h = hex_color.lstrip('#')
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _add_title_slide(prs, slide_data, theme, image_bytes=None):
    """Add a title slide with large title, subtitle, and optional background image."""
    from pptx.util import Inches, Pt, Emu
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout

    # Background color bar
    from pptx.util import Inches
    bg_shape = slide.shapes.add_shape(
        1, 0, 0, prs.slide_width, prs.slide_height  # MSO_SHAPE.RECTANGLE = 1
    )
    bg_shape.fill.solid()
    bg_shape.fill.fore_color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))
    bg_shape.line.fill.background()

    # Add image if available (right side, slightly transparent overlay feel)
    if image_bytes:
        img_stream = BytesIO(image_bytes)
        pic = slide.shapes.add_picture(img_stream, Inches(6.5), Inches(0.5), Inches(6), Inches(6))

    # Title text
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(6), Inches(2.5))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = slide_data.get("title", "")
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb("#ffffff")
    p.alignment = PP_ALIGN.LEFT

    # Subtitle
    if slide_data.get("subtitle"):
        p2 = tf.add_paragraph()
        p2.text = slide_data["subtitle"]
        p2.font.size = Pt(22)
        p2.font.color.rgb = _hex_to_rgb("#e0e0e0")
        p2.alignment = PP_ALIGN.LEFT
        p2.space_before = Pt(16)

    # Speaker notes
    if slide_data.get("speaker_notes"):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data["speaker_notes"]


def _add_content_slide(prs, slide_data, theme, image_bytes=None):
    """Add a content slide with title, bullets, and optional image on right."""
    from pptx.util import Inches, Pt

    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Accent bar at top
    bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))
    bar.line.fill.background()

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(7), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = slide_data.get("title", "")
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))

    # Bullets (left side if image, full width if no image)
    bullet_width = Inches(5.5) if image_bytes else Inches(11)
    bullet_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), bullet_width, Inches(5))
    tf = bullet_box.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(slide_data.get("bullets", [])):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = bullet
        p.font.size = Pt(18)
        p.font.color.rgb = _hex_to_rgb("#374151")
        p.space_before = Pt(12)
        p.level = 0

    # Image on right
    if image_bytes:
        img_stream = BytesIO(image_bytes)
        slide.shapes.add_picture(img_stream, Inches(7), Inches(1.6), Inches(5.5), Inches(5))

    if slide_data.get("speaker_notes"):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data["speaker_notes"]


def _add_key_concept_slide(prs, slide_data, theme, image_bytes=None):
    """Add a key concept slide with large centered text."""
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Light background
    bg = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    accent = theme.get("accent", "#dbeafe")
    bg.fill.fore_color.rgb = _hex_to_rgb(accent)
    bg.line.fill.background()

    # Centered title
    title_box = slide.shapes.add_textbox(Inches(1.5), Inches(1.5), Inches(10), Inches(1.5))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = slide_data.get("title", "")
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))
    p.alignment = PP_ALIGN.CENTER

    # Big content text
    if slide_data.get("content"):
        content_box = slide.shapes.add_textbox(Inches(2), Inches(3.5), Inches(9), Inches(2.5))
        tf = content_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = slide_data["content"]
        p.font.size = Pt(24)
        p.font.color.rgb = _hex_to_rgb("#374151")
        p.alignment = PP_ALIGN.CENTER

    if slide_data.get("speaker_notes"):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data["speaker_notes"]


def _add_two_column_slide(prs, slide_data, theme, image_bytes=None):
    """Add a two-column comparison slide."""
    from pptx.util import Inches, Pt

    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Accent bar
    bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))
    bar.line.fill.background()

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = slide_data.get("title", "")
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))

    # Left column
    left_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(5.5), Inches(5))
    tf = left_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = slide_data.get("left_title", "")
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb(theme.get("secondary_color", "#60a5fa"))
    for bullet in slide_data.get("left_bullets", []):
        p2 = tf.add_paragraph()
        p2.text = bullet
        p2.font.size = Pt(16)
        p2.font.color.rgb = _hex_to_rgb("#374151")
        p2.space_before = Pt(8)

    # Divider line
    divider = slide.shapes.add_shape(1, Inches(6.4), Inches(1.6), Inches(0.04), Inches(5))
    divider.fill.solid()
    divider.fill.fore_color.rgb = _hex_to_rgb("#d1d5db")
    divider.line.fill.background()

    # Right column
    right_box = slide.shapes.add_textbox(Inches(6.8), Inches(1.6), Inches(5.5), Inches(5))
    tf = right_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = slide_data.get("right_title", "")
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb(theme.get("secondary_color", "#60a5fa"))
    for bullet in slide_data.get("right_bullets", []):
        p2 = tf.add_paragraph()
        p2.text = bullet
        p2.font.size = Pt(16)
        p2.font.color.rgb = _hex_to_rgb("#374151")
        p2.space_before = Pt(8)

    if slide_data.get("speaker_notes"):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data["speaker_notes"]


def _add_image_focus_slide(prs, slide_data, theme, image_bytes=None):
    """Add a slide with a large centered image and caption."""
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN

    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.3), Inches(11), Inches(0.7))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = slide_data.get("title", "")
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))
    p.alignment = PP_ALIGN.CENTER

    # Large image
    if image_bytes:
        img_stream = BytesIO(image_bytes)
        slide.shapes.add_picture(img_stream, Inches(1.5), Inches(1.2), Inches(10), Inches(5))

    # Caption
    if slide_data.get("caption"):
        cap_box = slide.shapes.add_textbox(Inches(1.5), Inches(6.5), Inches(10), Inches(0.6))
        tf = cap_box.text_frame
        p = tf.paragraphs[0]
        p.text = slide_data["caption"]
        p.font.size = Pt(14)
        p.font.italic = True
        p.font.color.rgb = _hex_to_rgb("#6b7280")
        p.alignment = PP_ALIGN.CENTER

    if slide_data.get("speaker_notes"):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data["speaker_notes"]


def _add_section_divider_slide(prs, slide_data, theme, image_bytes=None):
    """Add a section divider slide with title and decorative bar."""
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Colored background
    bg = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = _hex_to_rgb(theme.get("primary_color", "#1a56db"))
    bg.line.fill.background()

    # Decorative bar
    bar = slide.shapes.add_shape(1, Inches(4), Inches(3.2), Inches(5), Inches(0.06))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _hex_to_rgb(theme.get("secondary_color", "#60a5fa"))
    bar.line.fill.background()

    # Section title
    title_box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(11), Inches(1.5))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = slide_data.get("title", "")
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = _hex_to_rgb("#ffffff")
    p.alignment = PP_ALIGN.CENTER

    if slide_data.get("speaker_notes"):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data["speaker_notes"]


# Layout dispatcher
_LAYOUT_HANDLERS = {
    "title": _add_title_slide,
    "content": _add_content_slide,
    "key_concept": _add_key_concept_slide,
    "two_column": _add_two_column_slide,
    "image_focus": _add_image_focus_slide,
    "section_divider": _add_section_divider_slide,
}


def assemble_pptx(slides, theme, title, images, filepath):
    """Assemble a PPTX file from slide data and generated images.

    Args:
        slides: list of slide dicts
        theme: theme dict with colors
        title: deck title
        images: dict mapping slide index → PNG bytes
        filepath: output .pptx path
    """
    from pptx import Presentation

    prs = Presentation()
    prs.slide_width = 12192000   # 13.333 inches in EMU (16:9)
    prs.slide_height = 6858000   # 7.5 inches in EMU

    for i, slide_data in enumerate(slides):
        layout = slide_data.get("layout", "content")
        handler = _LAYOUT_HANDLERS.get(layout, _add_content_slide)
        image_bytes = images.get(i)
        handler(prs, slide_data, theme, image_bytes)

    prs.save(filepath)
    logger.info("Assembled %d-slide PPTX: %s", len(slides), filepath)
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_slide_generator.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_generator.py tests/test_slide_generator.py
git commit -m "feat: add slide generator service (content + image gen + PPTX assembly)"
```

---

### Task 3: Add API endpoints

**Files:**
- Modify: `backend/routes/planner_routes.py`

- [ ] **Step 1: Add the generation endpoint**

Add to the end of `backend/routes/planner_routes.py`:

```python
# ══════════════════════════════════════════════════════════════
# SLIDE DECK GENERATION
# ══════════════════════════════════════════════════════════════

@planner_bp.route('/api/generate-slides', methods=['POST'])
@require_teacher
@handle_route_errors
def generate_slides():
    """Generate a slide deck from content using Gemini Flash."""
    data = request.get_json(silent=True) or {}

    content = data.get('content', '').strip()
    title = data.get('title', 'Slide Deck')
    subject = data.get('subject', '')
    grade = data.get('grade', '')
    instructions = data.get('instructions', '')
    global_ai_notes = data.get('globalAINotes', '')
    lesson_plan = data.get('lessonPlan')
    slide_count = min(data.get('slideCount', 10), 20)
    max_images = min(data.get('maxImages', 5), 10)
    generate_images = data.get('generateImages', True)
    deck_format = data.get('deckFormat', 'detailed')

    if not content and not lesson_plan:
        return jsonify({"error": "Provide content or a lesson plan to generate slides."}), 400

    user_id = getattr(g, 'user_id', 'local-dev')

    try:
        from backend.api_keys import get_api_key as _gak
        api_key = _gak('gemini', user_id)

        from backend.services.slide_generator import (
            generate_slide_content, generate_slide_images
        )

        # Phase 1: Generate slide content
        slide_data = generate_slide_content(
            content=content, subject=subject, grade=grade, title=title,
            api_key=api_key, lesson_plan=lesson_plan,
            global_ai_notes=global_ai_notes, instructions=instructions,
            slide_count=slide_count,
            deck_format=deck_format,
        )

        # Phase 2: Generate images (optional)
        images_generated = 0
        if generate_images:
            try:
                images = generate_slide_images(
                    slide_data["slides"], slide_data["theme"],
                    api_key=api_key, max_images=max_images,
                )
                images_generated = len(images)
                # Store image references in session for export
                # (images are too large for JSON response)
                import base64
                slide_data["_image_data"] = {
                    str(k): base64.b64encode(v).decode('ascii') for k, v in images.items()
                }
            except Exception as e:
                logger.warning("Image generation failed, continuing without images: %s", e)
                slide_data["_image_data"] = {}

        return jsonify({
            "slides": slide_data,
            "title": slide_data.get("title", title),
            "slide_count": len(slide_data.get("slides", [])),
            "images_generated": images_generated,
        })

    except json.JSONDecodeError as e:
        logger.error("Slide content JSON parse failed: %s", e)
        return jsonify({"error": "Failed to parse slide content. Please try again."}), 500
    except Exception as e:
        logger.exception("Slide generation failed")
        return jsonify({"error": "Generation failed: " + str(e)[:200]}), 500


@planner_bp.route('/api/export-slides', methods=['POST'])
@require_teacher
@handle_route_errors
def export_slides():
    """Export generated slides as PowerPoint (.pptx)."""
    data = request.get_json(silent=True) or {}
    slide_data = data.get('slides')

    if not slide_data or not slide_data.get('slides'):
        return jsonify({"error": "No slide data provided."}), 400

    title = slide_data.get("title", "Slide Deck")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
    export_dir = _get_export_dir()

    try:
        import base64
        from backend.services.slide_generator import assemble_pptx

        # Decode image data from base64
        images = {}
        for k, v in slide_data.get("_image_data", {}).items():
            try:
                images[int(k)] = base64.b64decode(v)
            except Exception:
                pass

        filepath = os.path.join(export_dir, safe_title + ".pptx")
        assemble_pptx(
            slide_data["slides"], slide_data.get("theme", {}),
            title, images, filepath
        )

        return send_file(
            filepath,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            as_attachment=True,
            download_name=safe_title + ".pptx",
        )

    except Exception as e:
        logger.exception("Slide export failed")
        return jsonify({"error": "Export failed: " + str(e)[:200]}), 500
```

- [ ] **Step 2: Verify import works**

```bash
source venv/bin/activate
python -c "from backend.services.slide_generator import generate_slide_content, assemble_pptx; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/routes/planner_routes.py
git commit -m "feat: add slide deck generation and export endpoints"
```

---

### Task 4: Frontend — Slide Deck Generator UI

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add slide deck state variables**

Find the flashcard state variables (search for `const [flashcards`). Add immediately after:

```javascript
  // Slide Deck state
  const [slideDeck, setSlideDeck] = useState(null);
  const [slideDeckGenerating, setSlideDeckGenerating] = useState(false);
  const [slideDeckInstructions, setSlideDeckInstructions] = useState('');
  const [slideCount, setSlideCount] = useState(10);
  const [slideImages, setSlideImages] = useState(true);
  const [slideFormat, setSlideFormat] = useState('detailed');
  const [slideResources, setSlideResources] = useState([]);
  const [slideResourceList, setSlideResourceList] = useState([]);
  const [slideResourcesLoading, setSlideResourcesLoading] = useState(false);
```

- [ ] **Step 2: Add Slide Deck Generator UI card below Flashcard section**

Find the closing `</div>` of the Flashcard Generator glass-card. Add IMMEDIATELY AFTER:

```javascript
                      {/* Slide Deck Generator */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Presentation" size={22} style={{ color: "#8b5cf6" }} />
                          Slide Deck Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate a professional slide deck with AI-generated graphics from your lesson plan. Export as PowerPoint.
                        </p>

                        <div style={{ display: "flex", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
                          <div>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Slides</label>
                            <select value={slideCount} onChange={function(e) { setSlideCount(parseInt(e.target.value)); }} className="input" style={{ maxWidth: "100px" }}>
                              <option value={8}>8</option>
                              <option value={10}>10</option>
                              <option value={12}>12</option>
                              <option value={15}>15</option>
                            </select>
                          </div>
                          <div>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>AI Graphics</label>
                            <select value={slideImages ? "yes" : "no"} onChange={function(e) { setSlideImages(e.target.value === "yes"); }} className="input" style={{ maxWidth: "160px" }}>
                              <option value="yes">With graphics (~$0.20)</option>
                              <option value="no">Text only (free)</option>
                            </select>
                          </div>
                          <div>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Format</label>
                            <select value={slideFormat} onChange={function(e) { setSlideFormat(e.target.value); }} className="input" style={{ maxWidth: "180px" }}>
                              <option value="detailed">Detailed Deck</option>
                              <option value="presenter">Presenter Slides</option>
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: "200px" }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Instructions (optional)</label>
                            <input type="text" value={slideDeckInstructions} onChange={function(e) { setSlideDeckInstructions(e.target.value); }} placeholder="e.g., Focus on vocabulary, include comparison slides" className="input" />
                          </div>
                        </div>

                        {/* Resource picker — include saved resources as source material */}
                        <div style={{ marginBottom: "12px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Include saved resources</label>
                            <button
                              onClick={async function() {
                                setSlideResourcesLoading(true);
                                try {
                                  var data = await api.listResources();
                                  setSlideResourceList(data.resources || []);
                                } catch (err) {
                                  addToast('Failed to load resources', 'error');
                                }
                                setSlideResourcesLoading(false);
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                              disabled={slideResourcesLoading}
                            >
                              {slideResourcesLoading ? 'Loading...' : 'Browse'}
                            </button>
                          </div>
                          {slideResourceList.length > 0 && (
                            <div style={{ maxHeight: "120px", overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px", padding: "6px" }}>
                              {slideResourceList.map(function(res) {
                                var isSelected = slideResources.some(function(r) { return r.id === res.id; });
                                return (
                                  <label key={res.id} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 6px", fontSize: "0.8rem", cursor: "pointer", borderRadius: "4px", background: isSelected ? "rgba(139,92,246,0.1)" : "transparent" }}>
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      onChange={function() {
                                        if (isSelected) {
                                          setSlideResources(slideResources.filter(function(r) { return r.id !== res.id; }));
                                        } else {
                                          setSlideResources(slideResources.concat([res]));
                                        }
                                      }}
                                    />
                                    <span style={{ fontWeight: 500 }}>{res.title || 'Untitled'}</span>
                                    <span style={{ color: "var(--text-secondary)", fontSize: "0.7rem" }}>{res.content_type || ''}</span>
                                  </label>
                                );
                              })}
                            </div>
                          )}
                          {slideResources.length > 0 && (
                            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                              {slideResources.length + ' resource(s) selected — will be included as source material'}
                            </p>
                          )}
                        </div>

                        <button
                          onClick={async function() {
                            setSlideDeckGenerating(true);
                            setSlideDeck(null);
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
                              // Append selected resource content
                              if (slideResources.length > 0) {
                                for (var ri = 0; ri < slideResources.length; ri++) {
                                  try {
                                    var resData = await api.loadResource(slideResources[ri].id);
                                    if (resData && resData.resource) {
                                      var rc = resData.resource.content;
                                      if (typeof rc === 'object') rc = JSON.stringify(rc);
                                      content += String.fromCharCode(10) + '--- Resource: ' + (slideResources[ri].title || '') + ' ---' + String.fromCharCode(10) + (rc || '').substring(0, 4000);
                                    }
                                  } catch (err) { /* skip failed resource loads */ }
                                }
                              }
                              if (!content.trim()) {
                                addToast('Generate a lesson plan, assessment, or select resources first.', 'warning');
                                setSlideDeckGenerating(false);
                                return;
                              }
                              var resp = await fetch('/api/generate-slides', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  title: (lessonPlan && lessonPlan.title ? lessonPlan.title : 'Slide Deck'),
                                  content: content,
                                  lessonPlan: lessonPlan && lessonPlan.overview ? lessonPlan : undefined,
                                  subject: config.subject || '',
                                  grade: config.grade || '',
                                  globalAINotes: config.globalAINotes || '',
                                  instructions: slideDeckInstructions,
                                  slideCount: slideCount,
                                  generateImages: slideImages,
                                  maxImages: 5,
                                  deckFormat: slideFormat,
                                }),
                              });
                              var data = await resp.json();
                              if (data.error) {
                                addToast(data.error, 'error');
                              } else {
                                setSlideDeck(data.slides);
                                addToast('Slide deck generated! (' + data.slide_count + ' slides, ' + data.images_generated + ' graphics)', 'success');
                              }
                            } catch (err) {
                              addToast('Failed to generate slides: ' + err.message, 'error');
                            }
                            setSlideDeckGenerating(false);
                          }}
                          disabled={slideDeckGenerating || (!lessonPlan && !generatedAssignment)}
                          className="btn btn-primary"
                          style={{ padding: "10px 24px", background: "linear-gradient(135deg, #8b5cf6, #6366f1)", display: "flex", alignItems: "center", gap: "8px" }}
                        >
                          {slideDeckGenerating ? (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }),
                              slideDeckGenerating ? " Generating slides..." : " Generate")
                          ) : (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Presentation", size: 16 }), " Generate Slide Deck")
                          )}
                        </button>

                        {slideDeck && (
                          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
                            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
                              {slideDeck.title || 'Slide Deck'} ({(slideDeck.slides || []).length} slides)
                            </h4>

                            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px", maxHeight: "400px", overflowY: "auto" }}>
                              {(slideDeck.slides || []).map(function(slide, si) {
                                return (
                                  <div key={si} style={{ padding: "12px 16px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--input-bg)", display: "flex", gap: "12px", alignItems: "flex-start" }}>
                                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#8b5cf6", minWidth: "24px" }}>{si + 1}</span>
                                    <div>
                                      <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{slide.title}</div>
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                                        {slide.layout} {slide.image_prompt ? ' + graphic' : ''}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            <button
                              onClick={async function() {
                                try {
                                  addToast('Assembling PowerPoint...', 'info');
                                  var resp = await fetch('/api/export-slides', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ slides: slideDeck }),
                                  });
                                  if (!resp.ok) {
                                    var err = await resp.json();
                                    addToast(err.error || 'Export failed', 'error');
                                    return;
                                  }
                                  var blob = await resp.blob();
                                  var url = URL.createObjectURL(blob);
                                  var a = document.createElement('a');
                                  a.href = url;
                                  a.download = (slideDeck.title || 'Slides') + '.pptx';
                                  a.click();
                                  URL.revokeObjectURL(url);
                                  addToast('PowerPoint downloaded!', 'success');
                                } catch (err) { addToast('Export failed: ' + err.message, 'error'); }
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
                            >
                              <Icon name="Download" size={16} /> Download PowerPoint (.pptx)
                            </button>
                          </div>
                        )}
                      </div>
```

- [ ] **Step 3: Build frontend**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/App.jsx
git commit -m "feat: add Slide Deck Generator UI to Tools tab"
```

---

### Task 5: Update dependencies and documentation

**Files:**
- Modify: `requirements.txt`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update requirements.txt**

Add these lines to `requirements.txt`:

```
google-genai>=1.0.0
python-pptx>=1.0.0
```

- [ ] **Step 2: Update CLAUDE.md API Reference**

Add to the API Reference section:

```markdown
### Slide Deck Generation
- `POST /api/generate-slides` — Generate slide deck content + AI graphics from lesson plan
- `POST /api/export-slides` — Export generated slides as PowerPoint (.pptx)
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt CLAUDE.md
git commit -m "docs: add slide deck dependencies and API endpoints"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Create slide template | Script + .pptx template | None — new files |
| 2 | Slide generator service (content + images + PPTX) + 11 tests | Create `slide_generator.py`, `test_slide_generator.py` | Medium — new SDK, image generation |
| 3 | API endpoints (thin wrappers) | Modify `planner_routes.py` | Low — same pattern |
| 4 | Frontend UI in Tools tab | Modify `App.jsx` | Low — same pattern |
| 5 | Dependencies + docs | Modify `requirements.txt`, `CLAUDE.md` | None |

**Total: 1 new service module, 2 new endpoints, 11 tests, 1 UI card, 2 new dependencies.**

**Quality features (matching NotebookLM):**
- AI decides all visual choices — colors, layouts, style — based on content (teacher just clicks "Generate")
- Two format modes: Detailed Deck (full text, standalone) or Presenter Slides (key talking points)
- Optional style prompt from teacher ("bold and playful", "Christmas-themed", "professional and minimal")
- Style-reference image generation (first image held in memory, passed to all subsequent calls for consistency)
- 6 layout types (title, content, key_concept, two_column, image_focus, section_divider)
- All positioning via absolute coordinates (no layout masters)
- Speaker notes on every slide
- Accent bars, colored backgrounds, divider lines
- 16:9 aspect ratio
- "With graphics" vs "Text only" toggle (cost control)
- Per-image error handling (failed images → text-only fallback)
- No temp files — images as bytes in memory, only final .pptx to disk

**Cost per deck:**
- Text only: ~$0.001
- With 5 AI graphics: ~$0.20
- 20 teachers × 4 decks/month: ~$16/month (with graphics) or ~$0.08/month (text only)
