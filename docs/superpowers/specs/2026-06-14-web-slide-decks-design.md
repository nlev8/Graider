# Web-Rendered Slide Decks — Design Spec

**Date:** 2026-06-14
**Status:** Approved (brainstorming) → ready for implementation plan
**Author:** main loop + operator (nlev8)

## 1. Problem & Goal

Graider's planner can already generate slide decks (`generate_slide_content` →
deck model → `assemble_pptx`), but the output is a hand-coded `python-pptx` file
with absolute positioning and default fonts — a "basic PowerPoint." The operator
wants slide decks **comparable in visual quality to NotebookLM** — i.e.
*polished static slides*, professionally designed.

**Goal:** A web-rendered slide experience — a beautiful in-app preview and a
pixel-matching PDF — driven by **four selectable, professionally-designed
templates**, while keeping the existing (now model-fixed) PPTX export working as
a basic secondary download.

**Explicitly NOT in scope (YAGNI):** narration / audio overview / video overview,
multi-source RAG with citations, a live "present mode," in-app slide editing, or
any change to grading. This spec is: *4 templates + HTML renderer + iframe
preview + PDF.*

## 2. Chosen Approach (decided in brainstorming)

- **Output medium:** Web-first. Beautiful HTML/CSS rendering → iframe preview +
  Playwright-printed PDF. The existing PPTX export stays as-is (a basic
  secondary "Download PowerPoint" option). No effort spent making the PPTX
  match the web look.
- **Rendering = Approach A:** Implement the slide templates **once** as HTML/CSS.
  The backend turns the deck model into a single self-contained HTML deck. The
  frontend shows that exact HTML in an **iframe** (the live preview). The **same
  HTML** is printed to a 16:9 PDF by Playwright. One template implementation ⇒
  preview and PDF are pixel-identical.
- **Four templates, teacher-selected per deck:** `editorial` (Editorial Minimal),
  `bold` (Bold Gradient), `academic` (Clean Academic), `playful` (Playful
  Illustrated). The AI no longer invents typography/layout/color scheme — the
  template owns those. The AI only chooses an **accent color** appropriate to
  the subject, applied *within* the chosen template's token system.

## 3. Architecture & Data Flow

```
Source content / lesson plan
        │
        ▼
Gemini 2.5 Flash  →  DECK MODEL (structured JSON: title, template, theme(accent), slides[])
        │
        ▼  (per slide image_prompt, if images enabled)
Gemini 2.5 Flash Image  →  per-slide PNG bytes
        │
        ▼
DECK MODEL (content + images)   ← single source of truth
        │
        ▼
slide_html_builder  →  one self-contained HTML deck (inlined CSS + base64 images)
        │                                  │
        ▼                                  ▼
iframe preview (frontend)        slide_pdf (Playwright) → 16:9 PDF download
```

The deck model is renderer-agnostic. The HTML is the single rendering artifact;
preview and PDF consume the identical HTML.

## 4. Deck Model (the contract)

Reuse the existing schema produced by `generate_slide_content`. Slides keep the
six layouts: `title`, `content`, `image_focus`, `two_column`, `key_concept`,
`section_divider`, plus `bullets`, `subtitle`, `content`, `left_*`/`right_*`,
`caption`, `image_prompt`, `speaker_notes`.

**Changes:**
- Add top-level **`template`**: one of `editorial | bold | academic | playful`.
  Set from the teacher's selection (passed into generation), not chosen by the
  AI. Default: `academic`.
- **`theme`** narrows in meaning: the AI now only supplies an **accent color**
  (`primary_color`, plus an optional `secondary_color`) suited to the subject;
  `style_description` is informational only. Typography, spacing, grid,
  decoration come from the template, not `theme`. The prompt is updated so the
  AI is told a fixed template handles design and it should only pick a tasteful
  subject-appropriate accent color.
- Per-slide images unchanged (`gemini-2.5-flash-image`, style-consistent via a
  reference image from the first generated image).

**Backward compatibility:** existing stored decks without a `template` field
render with the `academic` default; existing `theme` colors are honored as the
accent.

## 5. Template System

The professional look comes from a fixed **design system**, implemented once and
reused — *not* 24 bespoke (template × layout) implementations.

- **6 layout renderers** (HTML structure for each layout type), written once.
- **4 token sets** (one CSS variable bundle per template) defining: font pairing,
  color roles (background, surface, ink, accent, muted), spacing scale, radius,
  border/shadow rules, bullet/marker style, and any template-specific layout
  tweak (e.g. `bold`'s gradient title panel, `playful`'s rounded chips).
- The accent color from `theme` is injected as a CSS variable, so each template
  adapts to the subject while keeping its design integrity.
- Adding a 5th template later = one new token set (+ optional layout tweak).

Templates target the four directions validated visually in brainstorming
(`.superpowers/brainstorm/.../aesthetics.html`):

| key | name | character | best for |
|---|---|---|---|
| `editorial` | Editorial Minimal | whitespace, serif/sans pairing, restrained accent | upper grades, sharing |
| `bold` | Bold Gradient | gradient panels, big type, full-bleed imagery | maximum "wow" |
| `academic` | Clean Academic | light, structured, subject-colored header, check markers | any grade (default) |
| `playful` | Playful Illustrated | rounded, warm, big illustrations, larger text | younger grades |

## 6. Backend Components

- **`backend/services/slide_html_builder.py` (new)** — `build_deck_html(deck, images) -> str`.
  Pure function: deck model + per-slide image bytes → one self-contained HTML
  string (inlined `<style>` with the chosen template's tokens + the 6 layout
  renderers; images as base64 data URIs so the HTML is portable to the PDF step
  with no file paths). **Escapes all AI-produced text** before inserting into
  HTML (XSS / markup-injection safety — this is the one place untrusted model
  output meets HTML). Houses the 6 layout renderers + 4 token sets (or imports
  them from a small `slide_templates/` submodule if the file would exceed the
  2,500-LOC / 200-LOC campaign limits — keep functions ≤200 LOC).
- **`backend/services/slide_pdf.py` (new)** — `html_to_pdf(html: str) -> bytes`.
  Renders the HTML to a 16:9 landscape PDF via Playwright (sync API, Chromium),
  with timeout + a single retry; raises a typed error on failure so routes can
  return a clean message rather than a 500.
- **Routes (`backend/routes/planner_routes.py`):**
  - `/api/generate-slides` — **unchanged** externally (still returns the deck
    model JSON); now also threads the `template` selection into generation.
  - `/api/slides/html` (new) — accepts the **deck model in the POST body** (the
    frontend already holds it after `/api/generate-slides`) and returns the
    rendered preview HTML.
  - `/api/slides/pdf` (new) — accepts the **deck model in the POST body** and
    returns the PDF download. Runs the Playwright render in the existing
    background-thread pattern (it is slow), not inline in the request handler.
  - `/api/export-slides` (PPTX) — **unchanged** (basic secondary export).

## 7. Frontend Components

In the planner SlideDeck panel (`frontend/src/components/planner-tools/SlideDeck*`):

- **`SlideDeckConfigPanel`** — add a **template picker**: four thumbnails
  (mirroring the brainstorm mockups), single-select, default `academic`. Keep
  the existing slide-count / format / generate-images controls. The selected
  template is passed to `/api/generate-slides`.
- **`SlideDeckResults`** — replace the current crude preview with:
  - an **iframe preview** of the rendered deck (the real HTML from
    `/api/slides/html`),
  - a primary **Download PDF** button (→ `/api/slides/pdf`),
  - a secondary **Download PowerPoint (basic)** button (existing PPTX path).
- Keep components pure-prop / ≤200 LOC per the CQ campaign conventions
  (parent owns state; extract children if a file grows).

## 8. PDF Generation & Infra

- `playwright==1.58.0` is already in `requirements.txt`. The one infra addition:
  install the Chromium browser binary in the deploy image — add
  `playwright install chromium` (or `--with-deps`) to the build phase in
  `nixpacks.toml`. Verify on Railway after deploy (per workflow Hard Rule #8:
  external-IO/infra paths need an operator deploy-time check, not just CI).
- PDF rendering is CPU/time-heavy → runs in the established background-thread
  pattern with status polling, consistent with how grading/long tasks run.

## 9. Error Handling & Fallbacks

- **Per-slide image failure:** render that slide without an image (existing
  behavior in `generate_slide_images`); never fail the whole deck.
- **Chromium unavailable / PDF render failure:** the iframe preview still works
  (pure HTML, no browser dependency); the PDF endpoint returns a typed error and
  the UI surfaces "PDF temporarily unavailable — use PowerPoint export" instead
  of a 500.
- **Gemini text failure:** existing retry / circuit-breaker path
  (`with_retry`, pybreaker) is unchanged.
- **Untrusted content:** all AI text is HTML-escaped in `slide_html_builder`.

## 10. Testing

- **Unit — `slide_html_builder`:** for every (template × layout) combination,
  `build_deck_html` returns valid, non-empty HTML; AI text with HTML
  metacharacters is escaped (XSS regression test); images embed as data URIs.
- **Unit — `slide_pdf`:** `html_to_pdf` returns a non-empty `%PDF`-headed byte
  string for a sample deck (Playwright is already installed, so this runs in CI;
  guard/skip cleanly if the Chromium binary is absent in the test env).
- **Route tests:** `/api/slides/html` and `/api/slides/pdf` happy-path +
  failure-path (PDF unavailable → typed error, not 500).
- **Frontend:** mount test for the template picker (selection state) and the
  `SlideDeckResults` iframe-preview + download wiring (Vitest native matchers).

## 11. Open Questions / Risks

- **CI Chromium availability:** if the CI image lacks the Chromium binary, the
  `slide_pdf` unit test must skip rather than fail. Confirm during planning.
- **Deck size / PDF time:** large decks with many base64 images make a big HTML
  string; acceptable for typical 5–15 slide decks. Revisit only if it bites.
- **Template fidelity:** the four templates should be implemented to the quality
  bar set by the brainstorm mockups; a design pass during implementation is
  expected.

## 12. Definition of Done

- Teacher can pick one of four templates, generate a deck, see a polished iframe
  preview that matches the brainstorm aesthetic, and download a 16:9 PDF that is
  pixel-identical to the preview; the basic PPTX export still works.
- All tests green; `nixpacks.toml` installs Chromium; operator has verified PDF
  download against the deployed image (Hard Rule #8).
- Code adheres to CQ limits (no file >2,500 LOC, no function >200 LOC).
