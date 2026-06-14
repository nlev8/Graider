# Web-Rendered Slide Decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render generated slide decks as professionally-designed web pages — a pixel-matching in-app iframe preview and a 16:9 PDF — driven by four teacher-selectable templates, while keeping the existing PPTX export as a basic secondary download.

**Architecture:** Reuse the existing deck model (`generate_slide_content` → `{title, theme, slides[]}` + per-slide Gemini images). A new pure function turns the deck model into one self-contained HTML string (inlined CSS tokens + base64 images). The frontend shows that HTML in an iframe (preview); the same HTML is printed to a 16:9 PDF by Playwright. The four templates are one base CSS + four CSS-variable token sets, applied to six layout renderers (built once, not 24 times).

**Tech Stack:** Python/Flask, `python-pptx` (existing), `playwright` (already in requirements; Chromium binary added in `nixpacks.toml`), React/Vite, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-06-14-web-slide-decks-design.md`

**Class:** B (net-new behavior + outward-facing rendering). Per CLAUDE.md Principle #13: PR → opus + Codex review → fix to clean → manual merge. No `--auto` with review in flight.

---

## File Structure

**Create:**
- `backend/services/slide_templates.py` — base CSS + 4 template token sets (data + CSS string builders).
- `backend/services/slide_html_builder.py` — `build_deck_html(deck, images)` + 6 layout renderers + HTML escaping.
- `backend/services/slide_pdf.py` — `html_to_pdf(html)` via Playwright.
- `tests/test_slide_templates.py`, `tests/test_slide_html_builder.py`, `tests/test_slide_pdf.py`, `tests/test_slides_web_routes.py`
- `frontend/src/components/planner-tools/SlideTemplatePicker.jsx` — 4-thumbnail template selector.
- `frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx`

**Modify:**
- `backend/services/slide_generator.py` — `generate_slide_content` accepts `template`, prompt tells AI design is fixed (accent color only); pass `template` through into the returned deck dict.
- `backend/services/planner_study_aids.py` — `generate_slides_payload` accepts + threads `template`.
- `backend/routes/planner_routes.py` — thread `template` into `/api/generate-slides`; add `/api/slides/html` and `/api/slides/pdf`.
- `frontend/src/services/api.js` — add `renderSlidesHtml`, `downloadSlidesPdf` (binary).
- `frontend/src/components/planner-tools/SlideDeckGenerator.jsx` — `slideTemplate` state; pass to picker + generate body; pass to results.
- `frontend/src/components/planner-tools/SlideDeckConfigPanel.jsx` — render `<SlideTemplatePicker>`.
- `frontend/src/components/planner-tools/SlideDeckResults.jsx` — iframe preview + Download PDF (primary) + Download PowerPoint (secondary).
- `nixpacks.toml` — install Chromium for Playwright.

**Design decision (deviation from spec §6, deliberate):** the PDF endpoint generates **synchronously** and returns `send_file`, mirroring the existing `/api/export-slides` PPTX route, rather than the background-thread+polling pattern. Rationale: a typical 5–15 slide deck renders in a few seconds (well under request timeout), and synchronous keeps the route, the API client, and the UI dramatically simpler (YAGNI). If large decks prove too slow later, moving to the background pattern is a contained follow-up. Flagged here for the plan reviewer.

---

## Phase 1 — Deck model gains a `template` field

### Task 1: `generate_slide_content` accepts and records `template`

**Files:**
- Modify: `backend/services/slide_generator.py:39` (signature) and the returned dict (~line 169-183)
- Test: `tests/test_slide_generator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_slide_generator.py`:

```python
def test_generate_slide_content_records_template(monkeypatch):
    """The chosen template is echoed into the returned deck dict, and the AI
    is told design is fixed (it only picks an accent)."""
    import json as _json
    from backend.services import slide_generator
    from backend.services.llm_adapter.types import LLMResponse, TextPart, Usage

    captured = {}

    def fake_chat(self, request):
        captured["prompt"] = request.messages[0].content[0].text
        deck = {"title": "T", "theme": {"primary_color": "#123456"},
                "slides": [{"layout": "title", "title": "T"}]}
        return LLMResponse(content_parts=[TextPart(text=_json.dumps(deck))],
                           tool_calls=[], usage=Usage(0, 0, 0.0),
                           finish_reason="stop", provider="gemini",
                           model="gemini-2.5-flash")

    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.GeminiAdapter.chat", fake_chat)
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.genai.Client",
        lambda api_key=None: object())

    deck = slide_generator.generate_slide_content(
        content="cells are units of life", subject="Bio", grade="7",
        title="Cells", api_key="k", slide_count=3, template="editorial")

    assert deck["template"] == "editorial"
    # AI is steered to pick only an accent color, not full design:
    assert "accent color" in captured["prompt"].lower()
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_generator.py::test_generate_slide_content_records_template -v`
Expected: FAIL — `generate_slide_content() got an unexpected keyword argument 'template'`.

- [ ] **Step 3: Implement**

In `backend/services/slide_generator.py`, change the signature (line 39-41) to add `template`:

```python
def generate_slide_content(content, subject, grade, title, api_key,
                           lesson_plan=None, global_ai_notes="", instructions="",
                           slide_count=10, deck_format="detailed", template="academic"):
```

Replace the theme block of the prompt (the lines that tell the AI to choose colors, ~line 79-84) so design is fixed and only the accent is AI-chosen. Find:

```python
    prompt_parts.append('  "theme": {')
    prompt_parts.append('    "primary_color": "#hex (choose a color that fits the subject and mood)",')
    prompt_parts.append('    "secondary_color": "#hex (complementary accent color)",')
    prompt_parts.append('    "accent": "#hex (light tint for backgrounds)",')
    prompt_parts.append('    "style_description": "brief description of the visual style you chose and why"')
    prompt_parts.append('  },')
```

Replace with:

```python
    prompt_parts.append('  "theme": {')
    prompt_parts.append('    "primary_color": "#hex — a single accent color appropriate to the SUBJECT. The deck design (fonts, layout, spacing) is fixed by a professional template; you ONLY choose this one accent color.",')
    prompt_parts.append('    "secondary_color": "#hex — optional complementary accent"')
    prompt_parts.append('  },')
```

Then where the deck dict is finalized before return (after parsing the AI JSON, ~line 169-177), record the template. Find the return / theme post-processing area and add:

```python
    result["template"] = template
```

(Place it right after `result = json.loads(response_text)` and the theme normalization, before `return result`.)

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_generator.py::test_generate_slide_content_records_template -v`
Expected: PASS.

- [ ] **Step 5: Run the existing slide_generator tests to confirm no regressions**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_generator.py tests/test_slide_generator_gaps.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/slide_generator.py tests/test_slide_generator.py
git commit -m "feat(slides): generate_slide_content accepts template; AI picks accent only"
```

### Task 2: Thread `template` through `generate_slides_payload`

**Files:**
- Modify: `backend/services/planner_study_aids.py:166` (signature) + the `generate_slide_content(...)` call (~line 181)
- Test: `tests/test_planner_study_aids_service.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_planner_study_aids_service.py`:

```python
def test_generate_slides_payload_threads_template():
    from unittest.mock import patch
    from backend.services.planner_study_aids import generate_slides_payload
    captured = {}

    def fake_content(**kwargs):
        captured.update(kwargs)
        return {"title": "Cells", "theme": {}, "slides": [{"h": 1}], "template": kwargs.get("template")}

    with patch('backend.api_keys.get_api_key', return_value='k'), \
         patch('backend.services.slide_generator.generate_slide_content', side_effect=fake_content), \
         patch('backend.services.slide_generator.generate_slide_images', return_value={}):
        out = generate_slides_payload(
            content="cells", title="Cells", subject="Bio", grade="7", instructions="",
            global_ai_notes="", lesson_plan=None, slide_count=10, max_images=5,
            generate_images=False, deck_format="detailed", user_id="t1", template="bold")

    assert captured["template"] == "bold"
    assert out["slides"]["template"] == "bold"
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_planner_study_aids_service.py::test_generate_slides_payload_threads_template -v`
Expected: FAIL — unexpected keyword argument `template`.

- [ ] **Step 3: Implement**

In `backend/services/planner_study_aids.py`, add `template="academic"` to the `generate_slides_payload` keyword-only signature (line 166-168), and pass it into the `generate_slide_content(...)` call (~line 181):

```python
def generate_slides_payload(*, content, title, subject, grade, instructions,
                            global_ai_notes, lesson_plan, slide_count, max_images,
                            generate_images, deck_format, user_id, template="academic"):
```

In the `generate_slide_content(` call, add `template=template,` to the kwargs.

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_planner_study_aids_service.py::test_generate_slides_payload_threads_template -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_study_aids.py tests/test_planner_study_aids_service.py
git commit -m "feat(slides): thread template through generate_slides_payload"
```

### Task 3: `/api/generate-slides` reads `template` from request

**Files:**
- Modify: `backend/routes/planner_routes.py` `generate_slides` (~line 2096-2114)
- Test: `tests/test_generate_slides.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_generate_slides.py` (mirror the existing happy-path test's patching):

```python
def test_generate_slides_passes_template(client, headers):
    from unittest.mock import patch
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.planner_study_aids.generate_slide_content',
               return_value={"title": "Cells", "theme": {}, "slides": [{"h": 1}], "template": "playful"}), \
         patch('backend.services.planner_study_aids.generate_slide_images', return_value={}):
        resp = client.post('/api/generate-slides',
                           json={"content": "cells", "generateImages": False, "template": "playful"},
                           headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["slides"]["template"] == "playful"
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_generate_slides.py::test_generate_slides_passes_template -v`
Expected: FAIL — `template` defaults to `academic`, assertion mismatch (or KeyError).

- [ ] **Step 3: Implement**

In `backend/routes/planner_routes.py` `generate_slides`, read `template` from the request JSON (near where `deckFormat` is read, ~line 2105) and pass it to `generate_slides_payload`:

```python
    template = (data.get('template') or 'academic')
    if template not in ('editorial', 'bold', 'academic', 'playful'):
        template = 'academic'
```

Add `template=template,` to the `generate_slides_payload(...)` call.

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_generate_slides.py::test_generate_slides_passes_template -v`
Expected: PASS.

- [ ] **Step 5: Run all slide route tests**

Run: `OPENAI_API_KEY= python -m pytest tests/test_generate_slides.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/planner_routes.py tests/test_generate_slides.py
git commit -m "feat(slides): /api/generate-slides accepts validated template"
```

---

## Phase 2 — Template design system (CSS)

### Task 4: `slide_templates.py` — base CSS + 4 token sets

**Files:**
- Create: `backend/services/slide_templates.py`
- Test: `tests/test_slide_templates.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_templates.py`:

```python
from backend.services.slide_templates import TEMPLATES, template_css, DEFAULT_TEMPLATE


def test_four_templates_exist():
    assert set(TEMPLATES) == {"editorial", "bold", "academic", "playful"}
    assert DEFAULT_TEMPLATE == "academic"


def test_template_css_includes_base_and_accent():
    css = template_css("academic", accent="#1a7f43")
    assert ".slide" in css           # base layout rules present
    assert "1a7f43" in css           # accent injected
    assert "--accent" in css         # uses CSS variable system


def test_unknown_template_falls_back_to_default():
    css = template_css("nope", accent="#1a7f43")
    assert css == template_css("academic", accent="#1a7f43")
```

- [ ] **Step 2: Run it; verify it fails**

Run: `python -m pytest tests/test_slide_templates.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_templates.py`:

```python
"""Design-system CSS for web-rendered slide decks.

One base stylesheet (16:9 slide geometry + the six layout classes) plus four
token sets (CSS-variable overrides) = four professional templates without
re-implementing layouts per template. The per-deck AI accent color is injected
as --accent. See docs/superpowers/specs/2026-06-14-web-slide-decks-design.md.
"""

DEFAULT_TEMPLATE = "academic"

# 1280x720 = 16:9. Each .slide is one print page.
_BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
@page { size: 1280px 720px; margin: 0; }
html, body { background: #555; }
.deck { display:flex; flex-direction:column; align-items:center; gap:16px; }
.slide {
  width:1280px; height:720px; overflow:hidden; position:relative;
  background: var(--bg); color: var(--ink);
  font-family: var(--font-body);
  padding: var(--pad);
  display:flex; flex-direction:column;
  break-after: page;
}
.slide h1, .slide h2, .slide .kicker { font-family: var(--font-head); }
.kicker { text-transform:uppercase; letter-spacing:3px; font-size:18px; color:var(--accent); margin-bottom:18px; }
.s-title { font-size:64px; font-weight:800; line-height:1.05; color:var(--ink); }
.s-head { font-size:44px; font-weight:800; color:var(--accent); margin-bottom:28px; }
.s-sub { font-size:30px; color:var(--muted); margin-top:18px; }
.bullets { list-style:none; display:flex; flex-direction:column; gap:18px; font-size:28px; line-height:1.4; }
.bullets li { display:flex; gap:16px; align-items:flex-start; }
.bullets li::before { content:"\\25CF"; color:var(--accent); font-size:18px; line-height:1.9; }
.body-2col { display:flex; gap:48px; flex:1; }
.col { flex:1; }
.col h3 { font-size:30px; color:var(--accent); margin-bottom:16px; font-family:var(--font-head); }
.content-row { display:flex; gap:48px; flex:1; align-items:center; }
.content-row .text { flex:1.1; }
.content-row .art { flex:.9; display:flex; align-items:center; justify-content:center; }
.content-row .art img { max-width:100%; max-height:520px; border-radius:var(--img-radius); }
.image-focus { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:24px; }
.image-focus img { max-width:90%; max-height:540px; border-radius:var(--img-radius); }
.caption { font-size:24px; color:var(--muted); }
.key-concept { flex:1; display:flex; align-items:center; justify-content:center; text-align:center; }
.key-concept .big { font-size:52px; font-weight:800; color:var(--ink); max-width:1000px; line-height:1.2; }
.divider { flex:1; display:flex; align-items:center; }
.divider .s-title { font-size:72px; }
.accent-bar { position:absolute; top:0; left:0; right:0; height:10px; background:var(--accent); }
"""

# Per-template CSS-variable token sets + optional template-specific rules.
TEMPLATES = {
    "academic": {
        "vars": {
            "--bg": "#ffffff", "--ink": "#1c2530", "--muted": "#5b6577",
            "--font-head": "'Segoe UI', system-ui, sans-serif",
            "--font-body": "'Segoe UI', system-ui, sans-serif",
            "--pad": "72px", "--img-radius": "10px",
        },
        "extra": ".bullets li::before { content:\"\\2713\"; font-weight:700; }",
    },
    "editorial": {
        "vars": {
            "--bg": "#faf8f3", "--ink": "#23211c", "--muted": "#6b6453",
            "--font-head": "Georgia, 'Times New Roman', serif",
            "--font-body": "system-ui, sans-serif",
            "--pad": "84px", "--img-radius": "4px",
        },
        "extra": ".kicker { border-bottom:1px solid #d8d2c2; padding-bottom:10px; } .bullets li { border-bottom:1px solid #ece7da; padding-bottom:14px; } .bullets li::before { content:\"\\2014\"; }",
    },
    "bold": {
        "vars": {
            "--bg": "linear-gradient(150deg,#0b1220,#101826)", "--ink": "#ffffff",
            "--muted": "#aab6c8",
            "--font-head": "'Segoe UI', system-ui, sans-serif",
            "--font-body": "'Segoe UI', system-ui, sans-serif",
            "--pad": "72px", "--img-radius": "16px",
        },
        "extra": ".s-title, .key-concept .big { letter-spacing:-1px; } .bullets li { background:rgba(255,255,255,.06); padding:12px 18px; border-radius:10px; } .bullets li::before { color:var(--accent); }",
    },
    "playful": {
        "vars": {
            "--bg": "#fffdf8", "--ink": "#4a3b28", "--muted": "#8a7a63",
            "--font-head": "'Trebuchet MS', 'Segoe UI', sans-serif",
            "--font-body": "'Trebuchet MS', 'Segoe UI', sans-serif",
            "--pad": "72px", "--img-radius": "24px",
        },
        "extra": ".s-head, .s-title { color:var(--accent); } .bullets li { background:#fff3e0; padding:14px 20px; border-radius:18px; } .bullets li::before { content:\"\\2728\"; }",
    },
}


def template_css(template: str, accent: str) -> str:
    """Return the full <style> body for a template with the AI accent injected."""
    tmpl = TEMPLATES.get(template) or TEMPLATES[DEFAULT_TEMPLATE]
    safe_accent = accent if (isinstance(accent, str) and accent.startswith("#")) else "#1a7f43"
    root_vars = "".join(f"{k}:{v};" for k, v in tmpl["vars"].items())
    root = f":root{{--accent:{safe_accent};{root_vars}}}"
    return _BASE_CSS + "\n" + root + "\n" + tmpl.get("extra", "")
```

- [ ] **Step 4: Run it; verify it passes**

Run: `python -m pytest tests/test_slide_templates.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_templates.py tests/test_slide_templates.py
git commit -m "feat(slides): slide_templates — base CSS + 4 design-system token sets"
```

---

## Phase 3 — HTML deck builder

### Task 5: `slide_html_builder.py` — escaping + per-layout renderers + `build_deck_html`

**Files:**
- Create: `backend/services/slide_html_builder.py`
- Test: `tests/test_slide_html_builder.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_html_builder.py`:

```python
import base64
from backend.services.slide_html_builder import build_deck_html

DECK = {
    "title": "Photosynthesis", "template": "academic",
    "theme": {"primary_color": "#1a7f43"},
    "slides": [
        {"layout": "title", "title": "Photosynthesis", "subtitle": "Unit 3"},
        {"layout": "content", "title": "Inputs", "bullets": ["Water", "CO2", "Light"],
         "image_prompt": "a leaf"},
        {"layout": "two_column", "title": "Compare",
         "left_title": "Light", "left_bullets": ["A"],
         "right_title": "Dark", "right_bullets": ["B"]},
        {"layout": "key_concept", "content": "Plants make food from light"},
        {"layout": "image_focus", "title": "Chloroplast", "caption": "where it happens",
         "image_prompt": "chloroplast"},
        {"layout": "section_divider", "title": "Part Two"},
    ],
}


def test_builds_html_for_every_layout():
    html = build_deck_html(DECK, images={})
    assert html.startswith("<!DOCTYPE html>")
    assert html.count('class="slide') == 6          # one per slide
    assert "Photosynthesis" in html and "Inputs" in html and "Compare" in html
    assert "1a7f43" in html                          # accent injected via template_css


def test_escapes_ai_text_to_prevent_injection():
    deck = {"title": "X", "template": "academic", "theme": {},
            "slides": [{"layout": "content", "title": "<script>alert(1)</script>",
                        "bullets": ["<img src=x onerror=alert(2)>"]}]}
    html = build_deck_html(deck, images={})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_embeds_images_as_data_uris():
    png = base64.b64encode(b"\x89PNGfake").decode()
    images = {"1": png}     # keyed by str(index), as planner_study_aids stores them
    html = build_deck_html(DECK, images=images)
    assert "data:image/png;base64," in html


def test_unknown_template_does_not_crash():
    deck = dict(DECK); deck["template"] = "bogus"
    html = build_deck_html(deck, images={})
    assert 'class="slide' in html
```

- [ ] **Step 2: Run it; verify it fails**

Run: `python -m pytest tests/test_slide_html_builder.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_html_builder.py`:

```python
"""Render a deck model into one self-contained HTML string.

Pure + Flask-free. Used for both the iframe preview and the Playwright PDF, so
preview and PDF are pixel-identical. All AI-produced text is HTML-escaped.
Images (base64, keyed by str(slide_index) as produced by planner_study_aids)
are embedded as data URIs so the HTML is portable.
"""
from html import escape

from backend.services.slide_templates import template_css, DEFAULT_TEMPLATE


def _esc(value) -> str:
    return escape(str(value if value is not None else ""))


def _bullets(items) -> str:
    lis = "".join(f"<li>{_esc(b)}</li>" for b in (items or []))
    return f'<ul class="bullets">{lis}</ul>' if lis else ""


def _img_tag(data_uri: str) -> str:
    return f'<img src="{data_uri}" alt="">' if data_uri else ""


def _render_title(slide, img):
    sub = f'<div class="s-sub">{_esc(slide.get("subtitle"))}</div>' if slide.get("subtitle") else ""
    return (f'<div class="divider"><div><div class="s-title">{_esc(slide.get("title"))}</div>{sub}</div></div>')


def _render_content(slide, img):
    art = f'<div class="art">{_img_tag(img)}</div>' if img else ""
    cls = "content-row" if img else ""
    text = f'<div class="text">{_bullets(slide.get("bullets"))}</div>' if img else _bullets(slide.get("bullets"))
    return (f'<div class="accent-bar"></div>'
            f'<div class="s-head">{_esc(slide.get("title"))}</div>'
            f'<div class="{cls}">{text}{art}</div>')


def _render_two_column(slide, img):
    left = f'<div class="col"><h3>{_esc(slide.get("left_title"))}</h3>{_bullets(slide.get("left_bullets"))}</div>'
    right = f'<div class="col"><h3>{_esc(slide.get("right_title"))}</h3>{_bullets(slide.get("right_bullets"))}</div>'
    return (f'<div class="accent-bar"></div>'
            f'<div class="s-head">{_esc(slide.get("title"))}</div>'
            f'<div class="body-2col">{left}{right}</div>')


def _render_key_concept(slide, img):
    text = slide.get("content") or slide.get("title")
    return f'<div class="key-concept"><div class="big">{_esc(text)}</div></div>'


def _render_image_focus(slide, img):
    cap = f'<div class="caption">{_esc(slide.get("caption"))}</div>' if slide.get("caption") else ""
    head = f'<div class="s-head">{_esc(slide.get("title"))}</div>' if slide.get("title") else ""
    return f'{head}<div class="image-focus">{_img_tag(img)}{cap}</div>'


def _render_section_divider(slide, img):
    return f'<div class="divider"><div class="s-title">{_esc(slide.get("title"))}</div></div>'


_LAYOUTS = {
    "title": _render_title,
    "content": _render_content,
    "two_column": _render_two_column,
    "key_concept": _render_key_concept,
    "image_focus": _render_image_focus,
    "section_divider": _render_section_divider,
}


def _render_slide(slide, img) -> str:
    fn = _LAYOUTS.get(slide.get("layout"), _render_content)
    return f'<section class="slide layout-{_esc(slide.get("layout"))}">{fn(slide, img)}</section>'


def build_deck_html(deck: dict, images: dict | None = None) -> str:
    """deck model + {str(index): base64} images -> self-contained HTML string."""
    images = images or {}
    template = deck.get("template") or DEFAULT_TEMPLATE
    accent = (deck.get("theme") or {}).get("primary_color") or "#1a7f43"
    css = template_css(template, accent)

    sections = []
    for idx, slide in enumerate(deck.get("slides", [])):
        b64 = images.get(str(idx)) or images.get(idx)
        data_uri = f"data:image/png;base64,{b64}" if b64 else ""
        sections.append(_render_slide(slide or {}, data_uri))

    return (
        "<!DOCTYPE html>"
        f'<html><head><meta charset="utf-8"><title>{_esc(deck.get("title"))}</title>'
        f"<style>{css}</style></head>"
        f'<body><div class="deck">{"".join(sections)}</div></body></html>'
    )
```

- [ ] **Step 4: Run it; verify it passes**

Run: `python -m pytest tests/test_slide_html_builder.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Confirm no function exceeds the CQ limit**

Run: `node scripts/cq_scan_frontend.mjs >/dev/null; python scripts/cq_scan_backend.py 2>&1 | grep -i slide_html_builder || echo "clean"`
Expected: `clean` (every function in the new file is small).

- [ ] **Step 6: Commit**

```bash
git add backend/services/slide_html_builder.py tests/test_slide_html_builder.py
git commit -m "feat(slides): slide_html_builder — deck model -> self-contained HTML (escaped, data-URI images)"
```

---

## Phase 4 — PDF rendering

### Task 6: `slide_pdf.py` — `html_to_pdf` via Playwright

**Files:**
- Create: `backend/services/slide_pdf.py`
- Test: `tests/test_slide_pdf.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_pdf.py`:

```python
import shutil
import pytest


def _chromium_available():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            b.close()
        return True
    except Exception:
        return False


def test_slide_pdf_unavailable_raises_typed_error(monkeypatch):
    """When Playwright/Chromium fails to launch, raise SlidePdfError (not a bare Exception)."""
    from backend.services import slide_pdf

    class _Boom:
        def __enter__(self): raise RuntimeError("no browser")
        def __exit__(self, *a): return False

    monkeypatch.setattr(slide_pdf, "sync_playwright", lambda: _Boom())
    with pytest.raises(slide_pdf.SlidePdfError):
        slide_pdf.html_to_pdf("<html><body>x</body></html>")


@pytest.mark.skipif(not _chromium_available(), reason="Chromium not installed in this env")
def test_html_to_pdf_returns_pdf_bytes():
    from backend.services.slide_pdf import html_to_pdf
    pdf = html_to_pdf("<!DOCTYPE html><html><body><h1>Hi</h1></body></html>")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 500
```

- [ ] **Step 2: Run it; verify it fails**

Run: `python -m pytest tests/test_slide_pdf.py -v`
Expected: FAIL — module not found (the skipif test is collected but errors on import).

- [ ] **Step 3: Implement**

Create `backend/services/slide_pdf.py`:

```python
"""Render slide-deck HTML to a 16:9 PDF via headless Chromium (Playwright).

Synchronous: a typical deck renders in a few seconds, mirroring the existing
PPTX export route. Raises SlidePdfError on any failure so routes return a clean
message instead of a 500.
"""
import logging

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class SlidePdfError(RuntimeError):
    """Raised when PDF rendering is unavailable or fails."""


def html_to_pdf(html: str) -> bytes:
    """Render a self-contained HTML deck to PDF bytes (1280x720 pages)."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="networkidle")
                pdf = page.pdf(width="1280px", height="720px",
                               print_background=True, prefer_css_page_size=True)
            finally:
                browser.close()
        if not pdf or pdf[:5] != b"%PDF-":
            raise SlidePdfError("Playwright returned empty/invalid PDF")
        return pdf
    except SlidePdfError:
        raise
    except Exception as e:  # browser missing, launch failure, timeout, etc.
        logger.warning("slide PDF render failed: %s", e)
        raise SlidePdfError(str(e)) from e
```

- [ ] **Step 4: Run it; verify it passes**

Run: `python -m pytest tests/test_slide_pdf.py -v`
Expected: the typed-error test PASSES; the render test PASSES if Chromium is installed locally, else SKIPS. (If it errors instead of skipping, run `python -m playwright install chromium` locally and re-run.)

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_pdf.py tests/test_slide_pdf.py
git commit -m "feat(slides): slide_pdf.html_to_pdf via Playwright (typed SlidePdfError on failure)"
```

---

## Phase 5 — Web routes

### Task 7: `/api/slides/html` and `/api/slides/pdf`

**Files:**
- Modify: `backend/routes/planner_routes.py` (add two routes near `export_slides`, ~line 2171)
- Test: `tests/test_slides_web_routes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slides_web_routes.py` (reuse the `client`/`headers` fixtures pattern from `tests/test_generate_slides.py`):

```python
import pytest

DECK = {"title": "Cells", "template": "academic", "theme": {"primary_color": "#1a7f43"},
        "slides": [{"layout": "title", "title": "Cells"}]}


def test_slides_html_returns_html(client, headers):
    resp = client.post('/api/slides/html', json={"slides": DECK}, headers=headers)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b"Cells" in resp.data and b"<!DOCTYPE html>" in resp.data


def test_slides_pdf_success(client, headers, monkeypatch):
    monkeypatch.setattr("backend.routes.planner_routes.html_to_pdf", lambda html: b"%PDF-1.4 fake")
    resp = client.post('/api/slides/pdf', json={"slides": DECK}, headers=headers)
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_slides_pdf_unavailable_returns_clean_error(client, headers, monkeypatch):
    from backend.services.slide_pdf import SlidePdfError

    def boom(html): raise SlidePdfError("no chromium")
    monkeypatch.setattr("backend.routes.planner_routes.html_to_pdf", boom)
    resp = client.post('/api/slides/pdf', json={"slides": DECK}, headers=headers)
    assert resp.status_code == 503
    assert "PowerPoint" in resp.get_json().get("error", "")
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slides_web_routes.py -v`
Expected: FAIL — 404 (routes don't exist).

- [ ] **Step 3: Implement**

In `backend/routes/planner_routes.py`, add imports near the top (with the other service imports):

```python
from backend.services.slide_html_builder import build_deck_html
from backend.services.slide_pdf import html_to_pdf, SlidePdfError
```

Add a helper + two routes after `export_slides` (~line 2171). The helper decodes the `_image_data` exactly like `export_slides` does:

```python
def _deck_and_images_from_request():
    data = request.get_json(silent=True) or {}
    deck = data.get('slides') or {}
    images = deck.get('_image_data') or {}
    return deck, images


@planner_bp.route('/api/slides/html', methods=['POST'])
@require_teacher
@handle_route_errors
def slides_html():
    """Render the deck model to self-contained preview HTML (for the iframe)."""
    deck, images = _deck_and_images_from_request()
    if not deck.get('slides'):
        return jsonify({"error": "No slides to render"}), 400
    html = build_deck_html(deck, images)
    return Response(html, mimetype="text/html")


@planner_bp.route('/api/slides/pdf', methods=['POST'])
@require_teacher
@handle_route_errors
def slides_pdf():
    """Render the deck model to a 16:9 PDF download."""
    deck, images = _deck_and_images_from_request()
    if not deck.get('slides'):
        return jsonify({"error": "No slides to render"}), 400
    html = build_deck_html(deck, images)
    try:
        pdf_bytes = html_to_pdf(html)
    except SlidePdfError:
        return jsonify({"error": "PDF rendering is temporarily unavailable. "
                                 "Use the Download PowerPoint export instead."}), 503
    safe_title = "".join(c for c in (deck.get('title') or 'slides')
                         if c.isalnum() or c in " -_").strip() or "slides"
    return Response(
        pdf_bytes, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
    )
```

Ensure `Response` is imported from flask at the top of the file (check the existing imports; `from flask import ..., Response` — add `Response` if missing).

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slides_web_routes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Cross-cutting + scope check**

Run: `OPENAI_API_KEY= python -m pytest tests/test_generate_slides.py tests/test_slides_web_routes.py -q` and `grep -rln "planner_routes" tests/ | head`
Expected: all green; review any other planner_routes tests for breakage.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/planner_routes.py tests/test_slides_web_routes.py
git commit -m "feat(slides): /api/slides/html (preview) + /api/slides/pdf (download) routes"
```

---

## Phase 6 — Frontend

### Task 8: API client functions

**Files:**
- Modify: `frontend/src/services/api.js`
- (No dedicated unit test — exercised via component tests in Tasks 9-10.)

- [ ] **Step 1: Add the functions**

Append to `frontend/src/services/api.js` (HTML returns text; PDF returns a Blob — both are non-JSON, so use raw `fetch` + `getAuthHeaders()` like the existing slide calls):

```javascript
export async function renderSlidesHtml(slideDeck) {
  const resp = await fetch('/api/slides/html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ slides: slideDeck }),
  });
  if (!resp.ok) throw new Error('Failed to render slides preview');
  return resp.text();
}

export async function downloadSlidesPdf(slideDeck) {
  const resp = await fetch('/api/slides/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ slides: slideDeck }),
  });
  if (!resp.ok) {
    let msg = 'Failed to generate PDF';
    try { msg = (await resp.json()).error || msg; } catch (e) { /* non-JSON */ }
    throw new Error(msg);
  }
  return resp.blob();
}
```

Confirm `getAuthHeaders` is already defined/used in this module (it is, per the existing helpers). If it is not exported/in-scope at the append point, move these functions next to the other `getAuthHeaders()` consumers.

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: `✓ built`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat(slides): api client — renderSlidesHtml + downloadSlidesPdf"
```

### Task 9: `SlideTemplatePicker` component

**Files:**
- Create: `frontend/src/components/planner-tools/SlideTemplatePicker.jsx`
- Test: `frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx`:

```jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SlideTemplatePicker from '../components/planner-tools/SlideTemplatePicker';

describe('SlideTemplatePicker', () => {
  it('renders all four templates and marks the selected one', () => {
    render(<SlideTemplatePicker value="academic" onChange={() => {}} />);
    expect(screen.getByText('Editorial')).toBeTruthy();
    expect(screen.getByText('Bold')).toBeTruthy();
    expect(screen.getByText('Academic')).toBeTruthy();
    expect(screen.getByText('Playful')).toBeTruthy();
  });

  it('calls onChange with the template key when clicked', () => {
    const onChange = vi.fn();
    render(<SlideTemplatePicker value="academic" onChange={onChange} />);
    fireEvent.click(screen.getByText('Bold'));
    expect(onChange).toHaveBeenCalledWith('bold');
  });
});
```

- [ ] **Step 2: Run it; verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/SlideTemplatePicker.mount.test.jsx`
Expected: FAIL — component not found.

- [ ] **Step 3: Implement**

Create `frontend/src/components/planner-tools/SlideTemplatePicker.jsx`:

```jsx
import React from "react";

// Four selectable design systems for slide decks. Pure-prop: value + onChange.
const TEMPLATES = [
  { key: "editorial", name: "Editorial", blurb: "Minimal, serif, upper grades" },
  { key: "bold", name: "Bold", blurb: "Gradient, big type, wow" },
  { key: "academic", name: "Academic", blurb: "Clean, structured (default)" },
  { key: "playful", name: "Playful", blurb: "Rounded, warm, younger grades" },
];

export default function SlideTemplatePicker({ value, onChange }) {
  return (
    <div>
      <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>
        Template
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
        {TEMPLATES.map(function (t) {
          const selected = value === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={function () { onChange(t.key); }}
              style={{
                textAlign: "left", padding: "10px 12px", cursor: "pointer",
                borderRadius: "8px",
                border: selected ? "2px solid var(--accent, #6366f1)" : "1px solid var(--glass-border)",
                background: selected ? "rgba(99,102,241,0.08)" : "transparent",
                color: "var(--text-primary)",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.85rem" }}>{t.name}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>{t.blurb}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run it; verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/SlideTemplatePicker.mount.test.jsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/planner-tools/SlideTemplatePicker.jsx frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx
git commit -m "feat(slides): SlideTemplatePicker (4 selectable templates)"
```

### Task 10: Wire template + iframe preview + PDF into the generator

**Files:**
- Modify: `frontend/src/components/planner-tools/SlideDeckGenerator.jsx` (state + generate body + props)
- Modify: `frontend/src/components/planner-tools/SlideDeckConfigPanel.jsx` (render picker)
- Modify: `frontend/src/components/planner-tools/SlideDeckResults.jsx` (iframe + PDF button)
- Test: `frontend/src/__tests__/SlideDeckGenerator.mount.test.jsx` (extend)

- [ ] **Step 1: Write the failing test**

Extend `frontend/src/__tests__/SlideDeckGenerator.mount.test.jsx`. Update the `vi.mock('../services/api', ...)` to add the two new fns, and add:

```jsx
it('renders the template picker with Academic default', () => {
  render(<SlideDeckGenerator {...baseProps()} />);
  expect(screen.getByText('Academic')).toBeTruthy();
  expect(screen.getByText('Editorial')).toBeTruthy();
});
```

In the mock object add: `renderSlidesHtml: vi.fn().mockResolvedValue('<html></html>'), downloadSlidesPdf: vi.fn().mockResolvedValue(new Blob()),`.

- [ ] **Step 2: Run it; verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/SlideDeckGenerator.mount.test.jsx`
Expected: FAIL — "Academic" not found (picker not wired yet).

- [ ] **Step 3: Implement — generator state + threading**

In `SlideDeckGenerator.jsx`:
- Add state (after the other slide states, ~line 27): `const [slideTemplate, setSlideTemplate] = useState('academic');`
- In the generate `fetch` body (~line 101-113), add `template: slideTemplate,`.
- Pass to the config panel: add props `slideTemplate={slideTemplate}` and `setSlideTemplate={setSlideTemplate}` to `<SlideDeckConfigPanel .../>`.
- Pass to results: `<SlideDeckResults slideDeck={slideDeck} addToast={addToast} onShare={...} />` (drop the old `onDownload`; PDF/PPTX handled inside results — see Step 5).

- [ ] **Step 4: Implement — config panel renders the picker**

In `SlideDeckConfigPanel.jsx`:
- Add `slideTemplate, setSlideTemplate` to the prop list.
- Import: `import SlideTemplatePicker from './SlideTemplatePicker';`
- Render it at the top of the controls: `<SlideTemplatePicker value={slideTemplate} onChange={setSlideTemplate} />`

- [ ] **Step 5: Implement — results: iframe preview + downloads**

Replace `SlideDeckResults.jsx` body with an iframe preview + two download buttons. New prop list: `{ slideDeck, addToast, onShare }`. Use the new api fns:

```jsx
import React, { useState, useEffect } from "react";
import * as api from "../../services/api";

export default function SlideDeckResults({ slideDeck, addToast, onShare }) {
  const [previewHtml, setPreviewHtml] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);

  useEffect(function () {
    let cancelled = false;
    api.renderSlidesHtml(slideDeck)
      .then(function (html) { if (!cancelled) setPreviewHtml(html); })
      .catch(function () { if (!cancelled) setPreviewHtml(""); });
    return function () { cancelled = true; };
  }, [slideDeck]);

  async function downloadPdf() {
    setPdfLoading(true);
    try {
      const blob = await api.downloadSlidesPdf(slideDeck);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = (slideDeck.title || "slides") + ".pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      addToast(e.message || "Failed to generate PDF", "error");
    } finally {
      setPdfLoading(false);
    }
  }

  async function downloadPptx() {
    const resp = await fetch("/api/export-slides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slides: slideDeck }),
    });
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (slideDeck.title || "slides") + ".pptx";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{ marginTop: "16px" }}>
      <div style={{ fontWeight: 700, marginBottom: "8px" }}>
        {slideDeck.title || "Slide Deck"} ({(slideDeck.slides || []).length} slides)
      </div>
      <iframe
        title="Slide preview"
        srcDoc={previewHtml}
        style={{ width: "100%", height: "420px", border: "1px solid var(--glass-border)",
                 borderRadius: "8px", background: "#555" }}
      />
      <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
        <button className="btn btn-primary" onClick={downloadPdf} disabled={pdfLoading}>
          {pdfLoading ? "Generating PDF…" : "Download PDF"}
        </button>
        <button className="btn btn-secondary" onClick={downloadPptx}>
          Download PowerPoint (basic)
        </button>
        <button className="btn btn-secondary"
                onClick={function () { onShare(slideDeck, "slide_deck", slideDeck.title || "Slide Deck"); }}>
          Share with class
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run the component tests**

Run: `cd frontend && npx vitest run src/__tests__/SlideDeckGenerator.mount.test.jsx src/__tests__/SlideTemplatePicker.mount.test.jsx`
Expected: PASS.

- [ ] **Step 7: Full FE suite + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: all tests PASS; `✓ built`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/planner-tools/SlideDeckGenerator.jsx frontend/src/components/planner-tools/SlideDeckConfigPanel.jsx frontend/src/components/planner-tools/SlideDeckResults.jsx frontend/src/__tests__/SlideDeckGenerator.mount.test.jsx
git commit -m "feat(slides): template picker + iframe preview + PDF download in planner UI"
```

---

## Phase 7 — Infra

### Task 11: Install Chromium in the deploy image

**Files:**
- Modify: `nixpacks.toml` `[phases.build]`

- [ ] **Step 1: Add the install command**

In `nixpacks.toml`, add a Chromium-install cmd to the `[phases.build]` `cmds` array (after the frontend-build commands). It must run on the web service (not gated by `SKIP_FRONTEND_BUILD`, since PDF rendering is needed at runtime):

```toml
  "python -m playwright install chromium",
```

- [ ] **Step 2: Verify the toml parses**

Run: `python -c "import tomllib; tomllib.load(open('nixpacks.toml','rb')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add nixpacks.toml
git commit -m "build(slides): install Chromium for Playwright PDF rendering"
```

**Note for the operator (Hard Rule #8):** after this deploys to Railway, manually generate a deck and download the PDF against the deployed image to confirm Chromium + its system libs are present. If the PDF endpoint returns 503 in prod, the Chromium runtime libs are missing — add the needed nixPkgs (e.g. via `[phases.setup].nixPkgs`) in a follow-up. CI green does NOT prove prod PDF works.

---

## Phase 8 — Branch verification (per-branch DoD)

### Task 12: Full local CI mirror + review

- [ ] **Step 1: Backend suite**

Run: `OPENAI_API_KEY= python -m pytest -q --ignore=tests/load`
Expected: all green (baseline 6071 passed + the new tests; 32 skipped + possibly 1 skipped slide_pdf render test if Chromium absent).

- [ ] **Step 2: Lint + SAST on changed backend files**

Run: `ruff check backend/ tests/ && bandit -q -r backend/services/slide_html_builder.py backend/services/slide_pdf.py backend/services/slide_templates.py`
Expected: clean. (Bandit may flag `--no-sandbox`; justify inline — it is required for Chromium in many container runtimes, and the HTML is server-generated, not attacker-controlled navigation.)

- [ ] **Step 3: Frontend**

Run: `cd frontend && npx vitest run && npm run build`
Expected: all PASS; `✓ built`.

- [ ] **Step 4: CQ scan (no new oversize files/functions)**

Run: `python scripts/cq_scan_backend.py | tail -1 && node scripts/cq_scan_frontend.mjs | tail -1`
Expected: counts unchanged from baseline (no new >200 functions, no new >2,500 files).

- [ ] **Step 5: GitNexus reindex**

Run: `npx gitnexus analyze --embeddings --skip-agents-md`

- [ ] **Step 6: Open PR (Class B — manual merge after review)**

Push the branch, open a PR with the evidence ledger, classification **Class B**, and the spec/plan refs. Dispatch the opus code-reviewer + a Codex adversarial pass (focus: HTML escaping/XSS in `slide_html_builder`, the `--no-sandbox` decision, route auth, and prod-Chromium risk). Fix to clean. **Do NOT `--auto`-merge** — merge manually after reviews return clean and the operator confirms the spec is satisfied.

---

## Self-Review Notes (author)

- **Spec coverage:** §2 approach → Tasks 4-7,10; §4 deck model `template` → Tasks 1-3; §5 template system → Task 4; §6 backend modules+routes → Tasks 5-7; §7 frontend → Tasks 8-10; §8 infra → Task 11; §9 error handling → Tasks 5 (escape), 6 (typed error), 7 (503 fallback); §10 testing → tests in every task; §11 risks → Task 6 skipif + Task 11 operator note. The one deliberate deviation (synchronous PDF vs spec's background-thread) is called out at the top of the plan for the reviewer.
- **Types/names consistency:** `build_deck_html(deck, images)`, `html_to_pdf(html) -> bytes`, `SlidePdfError`, `template_css(template, accent)`, `TEMPLATES`, `DEFAULT_TEMPLATE`, `renderSlidesHtml`/`downloadSlidesPdf`, `SlideTemplatePicker(value, onChange)` — used consistently across tasks.
- **No placeholders:** every code step has complete code.
