# Vivid Slide Template Library — Design Spec

**Status:** Approved (brainstorm 2026-06-14)
**Class:** B (net-new, outward-facing rendering) — multi-PR feature
**Supersedes nothing; extends:** `docs/superpowers/specs/2026-06-14-web-slide-decks-design.md` (the web-rendered slide deck system: `build_deck_html` → iframe preview + Playwright PDF).

## 1. Problem

The shipped slide system has 4 templates (`academic`, `editorial`, `bold`, `playful`) that look too similar. Root cause is architectural: all four share **one `_BASE_CSS`** (identical 16:9 geometry, identical type scale — 64px titles / 44px heads / 28px bullets, identical layout positions for all six layouts) and differ only in a handful of CSS variables (`--bg`, `--ink`, fonts, padding, bullet marker). The AI is also restricted to choosing an accent color only. Variety-by-token-swap cannot produce the vivid, distinct, "NotebookLM-grade" decks teachers want.

## 2. Goal

A library of **25 genuinely distinct, vivid templates** — each with its own colors, fonts, decoration, layout treatment, **and AI image style** — built on a system where adding a template is a small declarative descriptor, not a hand-written module. Preview (iframe) and PDF (server-side Chromium) must remain pixel-identical and self-contained (offline, no CDN).

Visual reference: the brainstorm mockups in `.superpowers/brainstorm/36732-1781461351/content/` (`directions.html`, `gallery.html`, `gallery-2.html`) — git-ignored, kept for reference.

## 3. Architecture — one engine, 25 declarative skins

Keep the existing **6 layout renderers** (`title / content / two_column / key_concept / image_focus / section_divider`) generic — one set of HTML — and let each template restyle them **dramatically via CSS** that targets the `.layout-*` classes the builder already emits. Distinctiveness comes from CSS (full-bleed backgrounds, `::before/::after` decoration, gradients, transforms, halftone via repeating-gradients, per-layout type scales, bullet markers), **not** from 25×6 hand-written layouts.

Each template is a declarative descriptor:

```python
@dataclass(frozen=True)
class Font:
    family: str          # e.g. "Anton"
    file: str            # e.g. "Anton-Regular.woff2" (in backend/assets/slide_fonts/)
    weight: int = 400
    style: str = "normal"

@dataclass(frozen=True)
class ImageStyle:                 # structured, not one freeform phrase — see §5
    medium: str
    composition: str
    avoid: str
    education_constraints: str

@dataclass(frozen=True)
class TemplateSpec:
    key: str             # "anime"
    name: str            # "Anime / Manga"
    group: str           # "Illustrated"  (Classic | Illustrated | Themed | Refined)
    fonts: tuple[Font, ...]
    tokens: dict[str, str]   # CSS variables: colors, --font-head/body, radii, padding
    decor_css: str           # template-specific CSS (PDF-safe subset, validated) — see §3
    image_style: ImageStyle  # → Gemini image prompt (§5)
    accent_role: str = "fixed"           # "fixed" (own palette) | "ai" (inject validated accent into --accent)
    layout_variants: dict[str, str] = field(default_factory=dict)  # {layout: variant_name}; unset → default (§3)
```

A descriptor is realistically ~40–120 lines (decor CSS for vivid styles sprawls); the package split (below) keeps files within gates.

### Layout variants (not CSS-only) — built in Phase 1

CSS skins alone cannot create genuinely different *reading models*: some styles need structural change, not just paint. Newspaper needs multi-column flow + masthead; Anime needs panels/balloons; Sports needs diagonal masks + stat strips; HUD needs framed metadata panels. (Codex spec-review 2026-06-14.) So each of the six layouts has a **default renderer plus a small set of named variants** a template may opt into — bounded structure, not arbitrary per-template functions:

```python
# in slide_html_builder: registry of {layout: {variant_name: render_fn}}
content:      bullets(default) | columns | card_grid | annotation_board
image_focus:  full_bleed(default) | framed_caption | diagonal_crop | comic_panel
title:        centered(default) | masthead | split
# key_concept / two_column / section_divider: default + 1–2 variants as needed
```

A descriptor declares `layout_variants={"content":"columns", "image_focus":"comic_panel", …}`; unspecified layouts use the default. This gives structure where it matters without exploding to 25×6 bespoke renderers. **Phase 1 builds the variant mechanism and proves it with one structurally-demanding template (Newspaper), so the hard path is validated up front — not deferred.**

Because each deck uses exactly one template, only that template's CSS is in the document — no CSS scoping/prefixing needed.

### PDF-safe CSS + `decor_css` validation

`decor_css` is **code-authored only** (never AI/admin/user-generated — see Security). It is constrained to a **PDF-safe subset** and checked by a validator (run in tests, and at startup in debug) that **rejects**: `@import`, external `url(...)` (anything not a `data:` URI), `backdrop-filter`, `mix-blend-mode`, unbounded `animation`/`infinite`; and **flags for QA**: heavy `filter`, `clip-path` on transformed children, viewport units in decoration, hairline (<1px) borders. The print path locks `@page` size and body dimensions so absolute/pseudo decoration can't be clipped by print margins. (My mockups used `backdrop-filter` + `background-blend-mode` for speed — the real templates must use PDF-safe equivalents.)

### Module structure (respects repo CQ gates: no file >2,500 LOC, no fn >200 LOC)

25 descriptors with CSS strings would blow the file-size gate, so `backend/services/slide_templates.py` becomes a package:

```
backend/services/slide_templates/
  __init__.py        # registry: TEMPLATES (key->spec), DEFAULT_TEMPLATE="minimal",
                     #   LEGACY_ALIASES (old key -> new key), get_spec(key) resolves aliases + default
  engine.py          # template_css(key, accent) -> base + :root{tokens} + @font-face + decor_css
  base_css.py        # shared 16:9 geometry + structural classes (.slide, .s-title, .bullets, …)
  fonts.py           # font registry + base64 woff2 embedding (lru_cache)
  specs/
    classic.py       # 4 specs
    illustrated.py   # 8 specs
    themed.py        # 7 specs
    refined.py       # 6 specs
backend/assets/slide_fonts/*.woff2   # bundled OFL/Apache fonts
```

`backend/services/slide_html_builder.py` is nearly unchanged — it already emits `class="slide layout-{layout}"`, the styling hook. `build_deck_html` keeps escaping all text and embedding base64 data-URI images. Public API stays: `template_css(key, accent) -> str`, `build_deck_html(deck, images) -> str`, `TEMPLATES`, `DEFAULT_TEMPLATE` (re-exported from the package so existing imports keep working).

## 4. Fonts — embedded, self-contained

Vivid styles need display fonts. To make the iframe preview and the server-side Chromium PDF render identically and **offline**, `template_css` embeds **only the selected template's** fonts as base64 `@font-face` (1–3 files per deck, `lru_cache`d). Fonts are OFL/Apache Google Fonts bundled in `backend/assets/slide_fonts/` — embeddable, no CDN, no network fetch, works inside the `sandbox=""` iframe and in headless Chromium with no network.

Robustness: before printing, `slide_pdf` waits on `document.fonts.ready` **and** one `requestAnimationFrame` settle (font-metric reflow can land after `fonts.ready`), in addition to `wait_until="load"`. Data-fonts inside a `sandbox=""` `srcdoc` are verified by an explicit test, not assumed. The iframe preview may briefly show fallback (FOUT) before fonts settle — acceptable; the React preview can fade in on load.

~16 font families total; see catalog (§8). All restricted to OFL/Apache. A **font manifest** (`backend/assets/slide_fonts/MANIFEST.json`) records each file's family, version, license id, and source URL; license texts ship in `slide_fonts/LICENSES/`. **Latin-glyph caveat:** decorative display fonts (Press Start 2P, Bangers, Cinzel Decorative, handwriting faces) are used for **headings only**; **body text uses broad-coverage faces** (Inter / system stack) so translated/ELL content (the app translates feedback for ELL students) and non-Latin glyphs still render.

## 5. AI image style per template

Today the Gemini image prompt is generic/color-based (`theme.style_prompt`). Each descriptor supplies a **structured** image style (not one freeform phrase), so the prompt builder can compose it safely:

```python
image_style = ImageStyle(
    medium="cel-shaded anime-inspired illustration",   # generic medium, NOT a named franchise
    composition="dynamic, clean lineart, vibrant flats",
    avoid="text, logos, watermarks, real people, copyrighted characters",
    education_constraints="clear, age-appropriate, subject-accurate, keeps contrast/legibility behind text",
)
```

So **Anime → anime-inspired cel art, Storybook → watercolor, Blueprint → schematics, Cosmic → space art** — while the `avoid` + `education_constraints` clauses guard against franchise/copyright pull, cultural stereotype, and busy-behind-text clarity loss (important for an education product). Threads template → `image_style` → `slide_generator.generate_slide_content` / `generate_slide_images`. Image **count and cost are unchanged** — only wording. Reference-image style-consistency chaining is preserved, but `avoid` is repeated each call so artifacts don't compound across the deck.

## 6. Accent strategy

Per-template `accent_role`: `"fixed"` templates own their palette (their identity *is* the palette — Cinematic, Synthwave, Art Deco…); `"ai"` templates accept the AI/teacher accent (Minimal, Editorial, Botanical, Sports…). The existing strict-hex `fullmatch` validation stays for the `"ai"` path and is the only place untrusted accent text enters CSS.

**Alias resolution is centralized:** every render path (preview HTML, PDF, PPTX export, both publish flows, regenerate) goes through `template_css(deck.template)` → `get_spec(key)`, which resolves `LEGACY_ALIASES` → default. Because resolution lives in that one choke point, legacy keys render correctly everywhere by construction — no per-call-site handling. The frontend picker also normalizes a legacy/unknown key it receives from an old deck so the control still reflects a selection. Unknown keys are **logged** (and the route may return a `template_warning` field) rather than silently swallowed, so malformed clients are visible in dev.

**Security invariants (explicit):** `decor_css` and `tokens` are **code-authored only** — never AI-, admin-, or user-generated through any UI. User/AI text only ever flows HTML-**escaped** into slide *content* — never into inline `style`, CSS custom properties, font names, or raw CSS. Layout/variant names come from fixed registries (not user input). The accent is the sole user-controlled CSS value and is hex-`fullmatch`-validated. Image `src` is a backend-built `data:` URI, escaped. The `sandbox=""` iframe is defense-in-depth on top of escaping, not a substitute for it.

## 7. Picker UX (frontend)

`SlideTemplatePicker` becomes **data-driven** from a JS registry mirroring the backend keys/names/groups. Rendered **grouped** (Classic / Illustrated / Themed / Refined), each a small live CSS thumbnail + name + blurb, in a scrollable panel with a filter/search box. Selecting sets `slideTemplate` (the key already flows through the generate body and `/api/slides/*`). The thumbnail CSS is a condensed version of the brainstorm mini-mockups.

## 8. Template catalog (25)

`accent`: `ai` = takes teacher/AI accent; `fixed` = own palette. Fonts are indicative (head + body).

**Classic (4)**
1. **Editorial Bold** — Playfair Display / Inter — cream + ink, red accent — `ai` — img: *sophisticated editorial illustration, refined*
2. **Vibrant Gradient** — Space Grotesk / Inter — saturated gradient — `ai` (accent drives hue) — img: *bright bold flat vector, energetic*
3. **Cinematic Dark** — Space Grotesk / Inter — near-black + neon — `fixed` — img: *dramatic dark cinematic, high-contrast, moody*
4. **Playful Organic** — Fredoka — warm peach, coral/teal — `ai` — img: *friendly rounded flat illustration, cheerful*

**Illustrated / Pop (8)**
5. **Anime / Manga** — Anton + Bangers — B&W + hot accent — `fixed` — img: *anime/manga cel-shaded, dynamic clean lineart, vibrant*
6. **Comic / Pop Art** — Bangers / Inter — yellow + Ben-Day dots — `fixed` — img: *comic-book ink, halftone, bold outlines*
7. **Kawaii Pastel** — Baloo 2 — pastel pink/mint — `fixed` — img: *cute chibi kawaii sticker art, soft pastel*
8. **Storybook / Watercolor** — Playfair Display italic / Inter — warm washes — `fixed` — img: *soft children's-book watercolor illustration*
9. **Synthwave / Retro 80s** — Orbitron / Inter — sunset gradient + neon grid — `fixed` — img: *80s synthwave neon retro-futuristic*
10. **Vaporwave** — Playfair Display (wide) / Inter — pastel neon + grid — `fixed` — img: *vaporwave aesthetic, pastel neon, classical statue, glitch*
11. **Pixel / 8-bit** — Press Start 2P / Inter — dark + pixel grid — `fixed` — img: *8-bit pixel-art sprite, retro game*
12. **Cyber / Neon** — Orbitron + Space Mono — black + cyan/magenta — `fixed` — img: *cyberpunk neon, glitch, high-tech*

**Themed (7)**
13. **Fantasy / D&D** — Cinzel Decorative + Cinzel — parchment + gold — `fixed` — img: *epic fantasy painterly illustration, medieval*
14. **Sci-Fi / HUD** — Oxanium + Space Mono — dark + cyan HUD — `fixed` — img: *sleek sci-fi, holographic HUD, futuristic*
15. **Sports / Athletic** — Anton (italic) — team colors, diagonals — `ai` (team color) — img: *dynamic athletic action, bold energetic*
16. **Newspaper / Vintage** — Playfair Display + Space Mono — newsprint cream — `fixed` — img: *vintage engraving / black-and-white halftone*
17. **Cosmic / Galaxy** — Space Grotesk + Orbitron — deep space — `fixed` — img: *cosmic space art, nebula, planets, starfield*
18. **Chalkboard** — Caveat — blackboard green — `fixed` — img: *white chalk drawing on dark, hand-sketched*
19. **Notebook / Doodle** — Permanent Marker + Caveat — lined paper — `fixed` — img: *hand-drawn ballpoint/marker doodle sketch*

**Refined (6)**
20. **Minimal / Swiss** — Inter — white + one accent — `ai` — img: *clean minimal flat, generous whitespace*
21. **Botanical / Nature** — Playfair Display / Inter — sage + cream — `ai` — img: *botanical naturalist illustration, pressed-leaf*
22. **Blueprint / Technical** — Space Mono — blueprint blue grid — `fixed` — img: *technical schematic, blueprint linework*
23. **Art Deco / Gatsby** — Cinzel + Poiret One — black + gold geometric — `fixed` — img: *art-deco gold geometric, 1920s elegance*
24. **Bauhaus / Geometric** — Inter + Space Mono — primary shapes — `fixed` — img: *bauhaus geometric, primary-color shapes, modernist*
25. **Bold Brutalist** — Anton + Space Mono — raw white/black/yellow — `ai` — img: *bold high-contrast graphic, stark, raw*

**Keys** are slugs (`anime`, `editorial-bold`, `cinematic`, `minimal`, …). **`DEFAULT_TEMPLATE = "minimal"`** (the safe clean default). **Back-compat:** the old keys are aliased — `LEGACY_ALIASES = {"academic":"minimal", "editorial":"editorial-bold", "bold":"cinematic", "playful":"playful-organic"}` — so any persisted deck or in-flight selection using an old key resolves to a sensible new template. `get_spec(key)` resolves alias → key → `DEFAULT_TEMPLATE`.

The `/api/generate-slides` route's validation changes from the hardcoded 4-key whitelist to: *accept any key in `TEMPLATES` or `LEGACY_ALIASES`, else fall back to `DEFAULT_TEMPLATE`* (driven by the registry, so new templates need no route edit).

## 9. Phasing (approved: engine first, then waves)

- **Phase 1 — Engine + structural proof (PR 1).** Package structure; `base_css.py`; `engine.template_css` (tokens + `decor_css` + embedded `@font-face`); `fonts.py` bundling/base64 + manifest; **layout-variant mechanism** in `slide_html_builder` (default + named variants per layout); **`decor_css` PDF-safe validator**; structured `image_style` threaded through `slide_generator`; `accent_role` handling; centralized `LEGACY_ALIASES`/`get_spec` + registry-driven route validation with invalid-key logging; `slide_pdf` `document.fonts.ready` + rAF; **registry exposed via API** (`GET /api/slide-templates` → keys/names/groups) so the picker is single-source; data-driven grouped `SlideTemplatePicker`; **migrate the 4 existing templates to descriptors** + add Minimal/Swiss default **+ build Newspaper as the structural proof** (forces the `columns`/`masthead` variants to exist); **automated render smoke tests** (see §10). Proves the *hard* path end-to-end, not just easy skins.
- **Phase 2–4 — Template waves (PRs 2–4).** Author the remaining ~20 descriptors in batches of ~6–7 (Illustrated, Themed, Refined), each batch bundling its fonts, adding any new layout variants it needs, and passing the render smoke tests + a manual visual-QA pass.
- **Phase 5 — Polish.** Picker thumbnails + filter/search; accessibility pass (contrast, all-caps readability); text-overflow tuning across templates.

Each phase is its own implementation plan (writing-plans), reviewed and merged independently. **Effort note:** the hard part is not writing 25 descriptors — it is making each readable across six layouts with arbitrary-length text in both iframe and PDF. Automated render smoke tests (not just CSS-string unit tests) catch blank/overflow/clipping/font-load regressions; final aesthetic judgment stays human (visual QA per wave).

## 10. Testing

**Unit / structure**
- `template_css(key)` for every registered key + every legacy alias: contains the resolved template's tokens + its `@font-face`; never raises; unknown key → default.
- `build_deck_html` for each template × each of the 6 layouts × its declared variants: renders without error, escapes injected text, embeds the data-URI image.
- Registry test: every `TemplateSpec` has required fields; every referenced font file exists in `slide_fonts/` and in `MANIFEST.json` with an OFL/Apache license id; `image_style` has all structured fields; groups + variant names are from the allowed sets.
- **`decor_css` validator test:** every template's `decor_css` passes the PDF-safe validator (no `@import`/external `url()`/`backdrop-filter`/`mix-blend-mode`/unbounded animation).
- Security regression (carried over): malicious accent (CSS-injection / trailing-newline) falls back to safe default; image data escaped in `src`.

**Render smoke (the new layer Codex flagged — beyond string asserts)**
- A Playwright matrix renders each template across a small case set — `{long-text, short-text} × {image, no-image}` over the structural layouts — to PNG, asserting: output is **non-blank**, content is **not clipped/overflowing** the 1280×720 page (no element exceeds the slide box), and the **template's font actually applied** (`getComputedStyle(headingEl).fontFamily` resolves to the template family, not a fallback). Same check runs against the **PDF** path for the structural proof template. Pixel-perfect is not required — blank/overflow/font-load are.

**Frontend / parity**
- Picker renders all registered templates grouped; `onChange` fires the correct key; legacy key normalizes to a selection; mount test.
- **Registry parity:** the JS template list is sourced from / checked against `GET /api/slide-templates` so Python and JS keys cannot drift (a test fails if they diverge).

**Manual**
- Visual QA per wave: render ~3 representative slides per template in the iframe and check the PDF for aesthetic quality + contrast/readability.

## 11. Risks / mitigations

- **Aesthetic quality is human-judged** — automated render-smoke tests guard blank/overflow/font-load; final beauty is visual-QA per wave.
- **Text overflow** — arbitrary-length AI/teacher titles + bullets in display fonts can break decorative layouts; mitigations: per-layout `max-height` + overflow clamps, line-count limits, optional auto-fit scaling on titles. Covered by the overflow smoke check.
- **i18n / glyph coverage** — decorative display fonts lack non-Latin glyphs; decorative faces are headings-only, body uses broad-coverage faces, so ELL-translated content renders.
- **Accessibility** — busy backgrounds + all-caps display faces hurt contrast/readability; Phase 5 a11y pass; `education_constraints` keeps images legible behind text.
- **Heavy CSS in Chromium print** — *not* assumed safe: a PDF-safe CSS subset + validator (§3) bans `backdrop-filter`/`mix-blend-mode`/external resources; gradients/transforms/`print_background` verified per wave; watch moiré from repeating-gradient halftones and disappearing hairlines in Blueprint/HUD/Newspaper.
- **Font application** — `document.fonts.ready` + rAF before PDF; data-fonts-in-sandboxed-srcdoc explicitly tested.
- **Font licensing** — OFL/Apache only; `MANIFEST.json` records version/license/source; license texts shipped.
- **Registry / thumbnail drift** — picker sourced from `GET /api/slide-templates` + parity test; thumbnails derive from the same tokens or are parity-checked.
- **Preview perf** — base64 fonts+images make `srcdoc` heavy; re-render the preview only when the deck/template actually changes (not on every keystroke).
- **Repo size / CQ gates** — package split keeps every file <2,500 LOC and every function <200 LOC; descriptors are data, not logic.
- **Image-style cost** — unchanged image count; only prompt wording changes; `avoid` clause repeated per call so reference-chaining doesn't compound artifacts.

## 12. Out of scope (v1)

Per-slide template mixing within one deck; user-uploaded custom templates; animated/transition effects; non-16:9 aspect ratios.
