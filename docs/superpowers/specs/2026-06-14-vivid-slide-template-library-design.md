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
class TemplateSpec:
    key: str             # "anime"
    name: str            # "Anime / Manga"
    group: str           # "Illustrated"  (Classic | Illustrated | Themed | Refined)
    fonts: tuple[Font, ...]
    tokens: dict[str, str]   # CSS variables: colors, --font-head/body, radii, padding
    decor_css: str           # template-specific CSS: backgrounds, overlays, bullets, per-layout flourishes
    image_style: str         # → Gemini image prompt
    accent_role: str = "fixed"   # "fixed" (own palette) | "ai" (inject validated accent into --accent)
```

Adding a template = ~20–50 lines of descriptor. **Escape hatch:** a template needing genuinely different *structure* (e.g. newspaper columns) may register an optional `layout_overrides` mapping `layout_name -> render_fn`; CSS skins cover ~90%, so this is reserved, not built in Phase 1.

Because each deck uses exactly one template, only that template's CSS is in the document — no CSS scoping/prefixing needed.

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

Robustness: before printing the PDF, `slide_pdf` waits on `page.evaluate("document.fonts.ready")` (in addition to `wait_until="load"`) so embedded fonts are guaranteed applied.

~16 font families total; see catalog (§8). Each font's license is verified OFL/Apache before bundling; the license files ship alongside in `backend/assets/slide_fonts/LICENSES/`.

## 5. AI image style per template

Today the Gemini image prompt is generic/color-based (`theme.style_prompt`). Each descriptor's `image_style` becomes the basis of the image prompt, so **Anime → anime art, Storybook → watercolor, Blueprint → schematics, Cosmic → space art**. Threads template → `image_style` → `slide_generator.generate_slide_content` / `generate_slide_images`. Image **count and cost are unchanged** — only the style wording changes. Existing reference-image style-consistency chaining is preserved.

## 6. Accent strategy

Per-template `accent_role`: `"fixed"` templates own their palette (their identity *is* the palette — Cinematic, Synthwave, Art Deco…); `"ai"` templates accept the AI/teacher accent (Minimal, Editorial, Botanical, Sports…). The existing strict-hex `fullmatch` validation stays for the `"ai"` path and is the only place untrusted accent text enters CSS.

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

- **Phase 1 — Engine (PR 1).** Package structure; `base_css.py`; `engine.template_css` with token + `decor_css` + embedded `@font-face`; `fonts.py` bundling + base64; thread `image_style` through `slide_generator`; `accent_role` handling; **migrate the existing 4 templates to descriptors** (Editorial Bold, Vibrant Gradient, Cinematic Dark, Playful Organic) + add Minimal/Swiss as the default; `LEGACY_ALIASES` + registry-driven route validation; `slide_pdf` `document.fonts.ready`; data-driven `SlideTemplatePicker` (grouped, even if only the first specs exist); full tests. Proves the system end-to-end.
- **Phase 2–4 — Template waves (PRs 2–4).** Author the remaining ~21 descriptors in batches of ~6–7 (Illustrated, Themed, Refined), each batch with its fonts bundled and a manual visual-QA pass.
- **Phase 5 — Polish.** Picker thumbnails, filter/search, any structural `layout_overrides` a template proved to need.

Each phase is its own implementation plan (writing-plans), reviewed and merged independently. CI is config/structure-safe; **aesthetic quality is verified by manual visual QA**, not automated tests.

## 10. Testing

- `template_css(key)` for every registered key: contains the template's tokens + its `@font-face`; never raises; unknown key falls back to default.
- `build_deck_html` for each template × each of the 6 layouts: renders without error, escapes injected text, embeds the data-URI image.
- Registry test: every `TemplateSpec` has required fields; every referenced font file exists in `slide_fonts/`; every `image_style` is non-empty; groups are from the allowed set.
- Security regression (carried over): malicious accent (CSS-injection / trailing-newline) still falls back to the safe default; image data still escaped in `src`.
- Frontend: picker renders all registered templates grouped; `onChange` fires the correct key; mount test.
- Visual QA (manual, per wave): render ~3 representative slides per template in the iframe and check the PDF.

## 11. Risks / mitigations

- **Aesthetic quality is human-judged** — automated tests guard structure, not beauty; budget a visual-QA pass per wave.
- **Font licensing** — restrict to OFL/Apache families; ship license files; verify before bundling.
- **Repo size / CQ gates** — package split keeps every file <2,500 LOC and every function <200 LOC; descriptors are data, not logic.
- **PDF font application** — `document.fonts.ready` wait guards against printing before embedded fonts load.
- **Heavy CSS in Chromium print** — gradients/transforms/`print_background` render fine; verify per wave during visual QA.
- **Image-style cost** — unchanged image count; only prompt wording changes.

## 12. Out of scope (v1)

Per-slide template mixing within one deck; user-uploaded custom templates; animated/transition effects; non-16:9 aspect ratios.
