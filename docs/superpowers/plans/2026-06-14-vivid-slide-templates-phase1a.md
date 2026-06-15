# Vivid Slide Templates — Phase 1A (Backend Engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the token-swap slide-template system with a declarative descriptor engine (per-template tokens + PDF-safe `decor_css` + embedded fonts + structured AI image style), and migrate the 4 existing templates + a new Minimal default onto it — all rendering through the existing `build_deck_html`/PDF path, with no visible regression.

**Architecture:** `backend/services/slide_templates.py` becomes a package: `types.py` (dataclasses), `base_css.py` (shared 16:9 geometry), `css_validator.py` (PDF-safe subset enforcement), `fonts.py` (base64 `@font-face` embedding of bundled OFL woff2), `specs/` (descriptors), `engine.py` (`template_css`), `__init__.py` (registry + aliases). The HTML builder and PDF/preview path are unchanged in 1A (layout variants + Newspaper proof + smoke tests are Plan 1B).

**Tech Stack:** Python 3.14 / Flask, dataclasses, `playwright` (existing), React/Vite, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-06-14-vivid-slide-template-library-design.md`

**Class:** B (net-new, outward-facing). PR → opus + Codex review → fix to clean → manual merge.

**Elegance bar (enforced — operator directive):** This code must be as elegant as possible. Concretely, every task and every review holds to:
- **Pure data vs. logic split** — `TemplateSpec` descriptors are *pure data* (no behaviour); all behaviour lives in `engine`/`fonts`/`css_validator`, each a single small module with one job.
- **One obvious way** — `get_spec`/`resolve_key` is the *single* resolution choke point; `template_css` is the *single* composition entry. No alternate paths, no duplicated alias logic at call sites.
- **Small, named, total functions** — each function does one thing, is named for what it returns, handles its own edge (unknown key → default, missing font → typed error) — no `None`-juggling at call sites.
- **No incidental cleverness** — readable regex with a comment on the non-obvious (`fullmatch` vs `match`), f-strings over concatenation, `OrderedDict`/comprehensions over manual loops, no premature abstraction.
- **DRY descriptors** — shared `Font` instances (`_INTER`) reused; tokens express intent (`--title-size`), not magic numbers scattered in CSS.
- Reviewers (opus + Codex) are asked specifically to flag any seam that reads as inelegant, duplicated, or surprising — not just bugs.

**Out of scope for 1A (→ Plan 1B):** layout-variant mechanism, the Newspaper structural-proof template, the grouped picker thumbnails/search, and Playwright render-smoke tests. 1A keeps the existing flat 4-thumbnail picker working (updated to the new keys) and ships 5 templates that render via the current default layouts.

---

## File Structure

**Create:**
- `backend/services/slide_templates/__init__.py` — registry: `TEMPLATES`, `GROUPS`, `DEFAULT_TEMPLATE`, `LEGACY_ALIASES`, `get_spec()`; re-exports `template_css`, `Font`, `ImageStyle`, `TemplateSpec`.
- `backend/services/slide_templates/types.py` — `Font`, `ImageStyle`, `TemplateSpec` dataclasses.
- `backend/services/slide_templates/base_css.py` — `BASE_CSS` (shared geometry + structural classes, fully tokenised).
- `backend/services/slide_templates/css_validator.py` — `validate_decor_css(css) -> list[str]`.
- `backend/services/slide_templates/fonts.py` — `font_face_css(fonts) -> str` (base64 embed, cached).
- `backend/services/slide_templates/engine.py` — `template_css(key, accent) -> str`.
- `backend/services/slide_templates/specs/__init__.py` — collects the descriptor lists.
- `backend/services/slide_templates/specs/classic.py` — Editorial Bold, Vibrant Gradient, Cinematic, Playful Organic.
- `backend/services/slide_templates/specs/refined.py` — Minimal (default).
- `backend/assets/slide_fonts/*.woff2` + `MANIFEST.json` + `LICENSES/` — bundled OFL fonts.
- `scripts/fetch_slide_fonts.py` — reproducible font fetcher.
- Tests: `tests/test_slide_template_types.py`, `tests/test_slide_css_validator.py`, `tests/test_slide_fonts.py`, `tests/test_slide_template_registry.py`, `tests/test_slide_template_engine.py`, `tests/test_slide_template_api.py`.

**Modify:**
- `backend/services/slide_templates.py` — **deleted** (replaced by the package; the old `tests/test_slide_templates.py` is updated/retired).
- `backend/services/slide_generator.py` — `generate_slide_content` builds `theme["style_prompt"]` from the template's structured `ImageStyle`.
- `backend/routes/planner_routes.py` — `generate_slides` template validation becomes registry-driven + logs invalid keys; add `GET /api/slide-templates`.
- `backend/services/slide_pdf.py` — wait on `document.fonts.ready` + one rAF before `page.pdf()`.
- `frontend/src/services/api.js` — add `getSlideTemplates()`.
- `frontend/src/components/planner-tools/SlideTemplatePicker.jsx` — keys updated to the new slugs (still flat in 1A; grouped UI is 1B).

---

## Phase 1A — Tasks

### Task 1: Descriptor dataclasses (`types.py`)

**Files:**
- Create: `backend/services/slide_templates/types.py`
- Create: `backend/services/slide_templates/__init__.py` (minimal, just enough to import in this task; expanded in Task 7)
- Test: `tests/test_slide_template_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_template_types.py`:

```python
from backend.services.slide_templates.types import Font, ImageStyle, TemplateSpec


def test_font_defaults():
    f = Font(family="Inter", file="Inter-Regular.woff2")
    assert f.weight == 400 and f.style == "normal"


def test_image_style_has_all_fields():
    s = ImageStyle(medium="m", composition="c", avoid="a", education_constraints="e")
    assert (s.medium, s.composition, s.avoid, s.education_constraints) == ("m", "c", "a", "e")


def test_template_spec_minimal_construction_and_defaults():
    spec = TemplateSpec(
        key="x", name="X", group="Refined",
        fonts=(Font("Inter", "Inter-Regular.woff2"),),
        tokens={"--bg": "#fff"},
        decor_css=".slide{}",
        image_style=ImageStyle("m", "c", "a", "e"),
    )
    assert spec.accent_role == "fixed"
    assert spec.layout_variants == {}
    # frozen
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.key = "y"
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_types.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.services.slide_templates.types` (the old `slide_templates.py` module still exists; importing the submodule path fails because it is a module, not a package).

- [ ] **Step 3: Implement**

A module and a package can't share the name `slide_templates`, so first **rename the old module to a legacy bridge** — the package re-exports its `template_css`/`TEMPLATES`/`DEFAULT_TEMPLATE` so every existing import keeps working and the suite stays green at every task, until Task 8 ships the real engine and Task 9 deletes the bridge:

```bash
git mv backend/services/slide_templates.py backend/services/slide_templates_legacy.py
mkdir -p backend/services/slide_templates
```

Create `backend/services/slide_templates/types.py`:

```python
"""Declarative template descriptor types. See
docs/superpowers/specs/2026-06-14-vivid-slide-template-library-design.md §3."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Font:
    family: str            # CSS family name, e.g. "Inter"
    file: str              # woff2 filename in backend/assets/slide_fonts/
    weight: int = 400
    style: str = "normal"  # "normal" | "italic"


@dataclass(frozen=True)
class ImageStyle:
    """Structured Gemini image style — composed into theme.style_prompt, never
    passed as one freeform phrase (spec §5)."""
    medium: str
    composition: str
    avoid: str
    education_constraints: str


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    name: str
    group: str                 # Classic | Illustrated | Themed | Refined
    fonts: tuple
    tokens: dict
    decor_css: str             # PDF-safe subset, validated (spec §3)
    image_style: ImageStyle
    accent_role: str = "fixed"             # "fixed" | "ai"
    layout_variants: dict = field(default_factory=dict)   # {layout: variant_name} (Plan 1B)
```

Create `backend/services/slide_templates/__init__.py` — the temporary legacy bridge (Task 7 replaces this whole file with the real registry):

```python
"""Temporary bridge: re-export the legacy engine + the new descriptor types so
imports stay stable while the engine is built task-by-task. Replaced in Task 7."""
from .types import Font, ImageStyle, TemplateSpec  # noqa: F401
from backend.services.slide_templates_legacy import (  # noqa: F401
    template_css, TEMPLATES, DEFAULT_TEMPLATE,
)
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_types.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Confirm existing slide tests still import cleanly**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_templates.py tests/test_slide_html_builder.py tests/test_slide_pdf.py -q`
Expected: all PASS (the `__init__.py` re-exports `template_css`/`TEMPLATES`/`DEFAULT_TEMPLATE` from the legacy module, so `from backend.services.slide_templates import template_css` still resolves).

- [ ] **Step 6: Commit**

```bash
git add backend/services/slide_templates/ backend/services/slide_templates_legacy.py tests/test_slide_template_types.py
git commit -m "feat(slides): template descriptor dataclasses + package scaffold (legacy re-export)"
```

---

### Task 2: Shared base CSS (`base_css.py`)

**Files:**
- Create: `backend/services/slide_templates/base_css.py`
- Test: `tests/test_slide_template_engine.py` (started here; extended in Task 8)

The base CSS is the structural skeleton only — every visual value is a `var(--token)` a descriptor supplies. It is the current `_BASE_CSS` from `slide_templates_legacy.py` with all hard-coded colours/fonts/sizes replaced by tokens (so templates can override type scale, not just colour).

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_template_engine.py`:

```python
from backend.services.slide_templates.base_css import BASE_CSS


def test_base_css_is_structural_and_tokenised():
    # structural layout classes present
    for sel in (".slide", ".bullets", ".s-title", ".s-head", ".body-2col",
                ".content-row", ".image-focus", ".key-concept", ".divider"):
        assert sel in BASE_CSS
    # 16:9 print page
    assert "1280px 720px" in BASE_CSS
    # vivid values come from tokens, not hard-coded literals
    assert "var(--bg)" in BASE_CSS and "var(--ink)" in BASE_CSS
    assert "var(--title-size)" in BASE_CSS   # type scale is tokenised now
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_engine.py::test_base_css_is_structural_and_tokenised -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_templates/base_css.py`:

```python
"""Shared 16:9 slide geometry + structural layout classes. Every vivid value is
a CSS variable a TemplateSpec supplies; this file fixes structure, not look.
See spec §3."""

BASE_CSS = """
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
.slide h1, .slide h2, .kicker { font-family: var(--font-head); }
.kicker { text-transform:uppercase; letter-spacing:var(--kicker-spacing,3px); font-size:var(--kicker-size,18px); color:var(--accent); margin-bottom:18px; }
.s-title { font-size:var(--title-size); font-weight:var(--title-weight,800); line-height:var(--title-leading,1.05); color:var(--title-color,var(--ink)); }
.s-head  { font-size:var(--head-size); font-weight:var(--head-weight,800); color:var(--head-color,var(--accent)); margin-bottom:28px; }
.s-sub   { font-size:var(--sub-size,30px); color:var(--muted); margin-top:18px; }
.bullets { list-style:none; display:flex; flex-direction:column; gap:var(--bullet-gap,18px); font-size:var(--bullet-size,28px); line-height:1.4; }
.bullets li { display:flex; gap:16px; align-items:flex-start; color:var(--ink); }
.bullets li::before { content:var(--bullet-mark,"\\25CF"); color:var(--accent); font-size:18px; line-height:1.9; }
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
.key-concept .big { font-size:var(--concept-size,52px); font-weight:800; color:var(--ink); max-width:1000px; line-height:1.2; }
.divider { flex:1; display:flex; align-items:center; }
.divider .s-title { font-size:var(--divider-size,72px); }
.accent-bar { position:absolute; top:0; left:0; right:0; height:var(--bar-height,10px); background:var(--accent); }
"""
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_engine.py::test_base_css_is_structural_and_tokenised -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_templates/base_css.py tests/test_slide_template_engine.py
git commit -m "feat(slides): tokenised base CSS (structure only; vivid values via vars)"
```

---

### Task 3: PDF-safe `decor_css` validator (`css_validator.py`)

**Files:**
- Create: `backend/services/slide_templates/css_validator.py`
- Test: `tests/test_slide_css_validator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_css_validator.py`:

```python
from backend.services.slide_templates.css_validator import validate_decor_css


def test_clean_css_passes():
    css = '.slide{background:linear-gradient(#fff,#000)} .bullets li::before{content:"-"}'
    assert validate_decor_css(css) == []


def test_data_uri_url_is_allowed():
    assert validate_decor_css('.x{background:url(data:image/png;base64,AAAA)}') == []


def test_external_url_rejected():
    errs = validate_decor_css('.x{background:url(https://evil.example/a.png)}')
    assert any("external url" in e.lower() for e in errs)


def test_import_rejected():
    assert any("@import" in e.lower() for e in validate_decor_css('@import "x.css";'))


def test_print_hostile_properties_rejected():
    for prop in ("backdrop-filter:blur(4px)", "mix-blend-mode:multiply"):
        errs = validate_decor_css(".x{%s}" % prop)
        assert errs, prop


def test_unbounded_animation_rejected():
    assert validate_decor_css(".x{animation:spin 2s infinite}")
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_css_validator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_templates/css_validator.py`:

```python
"""PDF-safe CSS subset enforcement for template decor_css (spec §3).

decor_css is code-authored, but this validator guards against print-hostile or
non-self-contained CSS slipping in: external resources break the no-network
self-contained render, and some properties don't print reliably in headless
Chromium. Run in tests (and at startup in debug)."""
import re

# url(...) that is NOT a data: URI
_EXTERNAL_URL = re.compile(r"url\(\s*['\"]?(?!data:)", re.IGNORECASE)
_IMPORT = re.compile(r"@import", re.IGNORECASE)
_INFINITE = re.compile(r"\binfinite\b", re.IGNORECASE)
# properties that don't print reliably
_BANNED_PROPS = ("backdrop-filter", "mix-blend-mode")


def validate_decor_css(css: str) -> list:
    """Return a list of violation messages ([] means PDF-safe)."""
    errors = []
    if _IMPORT.search(css):
        errors.append("@import is not allowed (breaks self-contained render)")
    if _EXTERNAL_URL.search(css):
        errors.append("external url(...) is not allowed; only data: URIs")
    if _INFINITE.search(css):
        errors.append("unbounded/infinite animation is not allowed")
    for prop in _BANNED_PROPS:
        if re.search(r"\b" + re.escape(prop) + r"\s*:", css, re.IGNORECASE):
            errors.append(f"print-hostile property '{prop}' is not allowed")
    return errors
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_css_validator.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_templates/css_validator.py tests/test_slide_css_validator.py
git commit -m "feat(slides): PDF-safe decor_css validator (no @import/external url/blend/infinite)"
```

---

### Task 4: Bundle the Phase-1A fonts

**Files:**
- Create: `scripts/fetch_slide_fonts.py`
- Create: `backend/assets/slide_fonts/*.woff2`, `backend/assets/slide_fonts/MANIFEST.json`, `backend/assets/slide_fonts/LICENSES/`
- Test: `tests/test_slide_fonts.py` (manifest half; embedding half is Task 5)

Phase 1A templates use five OFL families: **Inter** (body everywhere), **Playfair Display** (Editorial), **Space Grotesk** (Vibrant/Cinematic head), **Fredoka** (Playful), **Space Mono** (Newspaper body — fetched now so 1B needs no font work). All are SIL OFL 1.1.

- [ ] **Step 1: Write the fetch script**

Create `scripts/fetch_slide_fonts.py`:

```python
"""Fetch the OFL woff2 files the slide templates embed, into
backend/assets/slide_fonts/, and write MANIFEST.json. Re-runnable.

Sources are the @fontsource CDN (jsDelivr), which serves OFL Google Fonts as
woff2 at stable paths. Pin exact versions here so builds are reproducible."""
import json
import os
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "assets", "slide_fonts")
BASE = "https://cdn.jsdelivr.net/npm"

# (family, css_family, weight, style, npm pkg@ver, woff2 path within pkg, license_id)
FONTS = [
    ("Inter",          "Inter",          400, "normal", "@fontsource/inter@5.0.18",          "/files/inter-latin-400-normal.woff2",          "OFL-1.1"),
    ("Inter",          "Inter",          800, "normal", "@fontsource/inter@5.0.18",          "/files/inter-latin-800-normal.woff2",          "OFL-1.1"),
    ("PlayfairDisplay","Playfair Display",700, "normal","@fontsource/playfair-display@5.0.19","/files/playfair-display-latin-700-normal.woff2","OFL-1.1"),
    ("PlayfairDisplay","Playfair Display",900, "normal","@fontsource/playfair-display@5.0.19","/files/playfair-display-latin-900-normal.woff2","OFL-1.1"),
    ("SpaceGrotesk",   "Space Grotesk",  700, "normal", "@fontsource/space-grotesk@5.0.18",  "/files/space-grotesk-latin-700-normal.woff2",  "OFL-1.1"),
    ("Fredoka",        "Fredoka",        600, "normal", "@fontsource/fredoka@5.0.20",        "/files/fredoka-latin-600-normal.woff2",        "OFL-1.1"),
    ("SpaceMono",      "Space Mono",     700, "normal", "@fontsource/space-mono@5.0.18",     "/files/space-mono-latin-700-normal.woff2",     "OFL-1.1"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for fam, css_family, weight, style, pkg, path, lic in FONTS:
        fname = f"{fam}-{weight}-{style}.woff2"
        url = f"{BASE}/{pkg}{path}"
        dest = os.path.join(OUT, fname)
        print("fetch", url)
        urllib.request.urlretrieve(url, dest)
        manifest.append({"file": fname, "family": css_family, "weight": weight,
                         "style": style, "license": lic, "source": url})
    with open(os.path.join(OUT, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("wrote", len(manifest), "fonts +", "MANIFEST.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the fetcher + add the OFL license**

```bash
source venv/bin/activate
python scripts/fetch_slide_fonts.py
mkdir -p backend/assets/slide_fonts/LICENSES
# All seven files are SIL OFL 1.1; ship the canonical text once:
curl -sL https://raw.githubusercontent.com/google/fonts/main/ofl/inter/OFL.txt \
  -o backend/assets/slide_fonts/LICENSES/OFL-1.1.txt
ls -la backend/assets/slide_fonts/
```
Expected: 7 `.woff2` files + `MANIFEST.json` + `LICENSES/OFL-1.1.txt`. If a jsDelivr path 404s, open `https://cdn.jsdelivr.net/npm/<pkg>/files/` in a browser, find the exact `*-latin-<wt>-normal.woff2` name, and correct the path in the script.

- [ ] **Step 3: Write the manifest test**

Create `tests/test_slide_fonts.py`:

```python
import json
import os

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "assets", "slide_fonts")


def test_manifest_files_all_exist_and_are_licensed():
    with open(os.path.join(FONT_DIR, "MANIFEST.json")) as f:
        manifest = json.load(f)
    assert manifest, "manifest is empty"
    for entry in manifest:
        assert os.path.exists(os.path.join(FONT_DIR, entry["file"])), entry["file"]
        assert entry["license"] in ("OFL-1.1", "Apache-2.0")
        assert entry["family"] and entry["weight"] and entry["source"]
    # license text shipped
    assert os.path.exists(os.path.join(FONT_DIR, "LICENSES", "OFL-1.1.txt"))
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_fonts.py::test_manifest_files_all_exist_and_are_licensed -v`
Expected: PASS.

- [ ] **Step 5: Commit (fonts are binary assets — commit them)**

```bash
git add scripts/fetch_slide_fonts.py backend/assets/slide_fonts/ tests/test_slide_fonts.py
git commit -m "build(slides): bundle Phase-1A OFL fonts (woff2) + manifest + fetch script"
```
> NOTE: `backend/assets/slide_fonts/` must NOT be gitignored. Confirm with `git check-ignore backend/assets/slide_fonts/Inter-400-normal.woff2` (no output = not ignored). If ignored, add `!backend/assets/slide_fonts/` to `.gitignore`.

---

### Task 5: Font embedding (`fonts.py`)

**Files:**
- Create: `backend/services/slide_templates/fonts.py`
- Test: `tests/test_slide_fonts.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_slide_fonts.py`:

```python
def test_font_face_css_embeds_base64():
    from backend.services.slide_templates.fonts import font_face_css
    from backend.services.slide_templates.types import Font
    css = font_face_css((Font("Inter", "Inter-400-normal.woff2", 400),))
    assert "@font-face" in css
    assert "font-family:'Inter'" in css.replace(" ", "")
    assert "data:font/woff2;base64," in css
    assert "font-weight:400" in css.replace(" ", "")


def test_font_face_css_missing_file_raises():
    import pytest
    from backend.services.slide_templates.fonts import font_face_css, SlideFontError
    from backend.services.slide_templates.types import Font
    with pytest.raises(SlideFontError):
        font_face_css((Font("Nope", "does-not-exist.woff2"),))
```

(Use the actual filenames the fetcher produced — `Inter-400-normal.woff2`.)

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_fonts.py -v`
Expected: the two new tests FAIL — module not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_templates/fonts.py`:

```python
"""Embed bundled woff2 fonts as base64 @font-face so decks are self-contained
(identical iframe preview + Chromium PDF, offline). Only the selected template's
fonts are embedded per deck. See spec §4."""
import base64
import functools
import os

_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "slide_fonts")


class SlideFontError(RuntimeError):
    """Raised when a referenced font file is missing from the bundle."""


@functools.lru_cache(maxsize=128)
def _b64(filename: str) -> str:
    path = os.path.join(_FONT_DIR, filename)
    if not os.path.exists(path):
        raise SlideFontError(f"bundled font missing: {filename}")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def font_face_css(fonts) -> str:
    """fonts: tuple[Font, ...] -> @font-face block embedding each as a data URI."""
    blocks = []
    for f in fonts:
        b64 = _b64(f.file)
        blocks.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%d;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2');}"
            % (f.family, f.style, f.weight, b64)
        )
    return "".join(blocks)
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_fonts.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_templates/fonts.py tests/test_slide_fonts.py
git commit -m "feat(slides): base64 @font-face embedding (cached, self-contained)"
```

---

### Task 6: Template descriptors (the 5 Phase-1A templates)

**Files:**
- Create: `backend/services/slide_templates/specs/__init__.py`
- Create: `backend/services/slide_templates/specs/classic.py`
- Create: `backend/services/slide_templates/specs/refined.py`
- Test: `tests/test_slide_template_registry.py` (descriptor-shape half)

Each descriptor's `decor_css` MUST pass `validate_decor_css` (no `@import`/external url/blend/infinite). The four Classic templates reproduce the look of the legacy `academic/editorial/bold/playful` token sets, now as full descriptors; Minimal is the new clean default.

- [ ] **Step 1: Write the failing test**

Create `tests/test_slide_template_registry.py`:

```python
from backend.services.slide_templates.specs import ALL_SPECS
from backend.services.slide_templates.css_validator import validate_decor_css
from backend.services.slide_templates.types import TemplateSpec, ImageStyle

EXPECTED_KEYS = {"editorial-bold", "vibrant-gradient", "cinematic", "playful-organic", "minimal"}


def test_phase1a_specs_present_and_well_formed():
    by_key = {s.key: s for s in ALL_SPECS}
    assert EXPECTED_KEYS <= set(by_key)
    for s in ALL_SPECS:
        assert isinstance(s, TemplateSpec)
        assert s.group in ("Classic", "Illustrated", "Themed", "Refined")
        assert isinstance(s.image_style, ImageStyle)
        assert s.accent_role in ("fixed", "ai")
        assert s.tokens.get("--bg") and s.tokens.get("--font-head") and s.tokens.get("--font-body")
        assert s.tokens.get("--title-size") and s.tokens.get("--head-size")
        assert s.fonts, s.key


def test_every_decor_css_is_pdf_safe():
    for s in ALL_SPECS:
        assert validate_decor_css(s.decor_css) == [], s.key
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_registry.py -v`
Expected: FAIL — `backend.services.slide_templates.specs` not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_templates/specs/classic.py`:

```python
"""Classic group descriptors — the four migrated templates, now full skins."""
from backend.services.slide_templates.types import Font, ImageStyle, TemplateSpec

_INTER = Font("Inter", "Inter-400-normal.woff2", 400)
_INTER_BLACK = Font("Inter", "Inter-800-normal.woff2", 800)

EDITORIAL_BOLD = TemplateSpec(
    key="editorial-bold", name="Editorial Bold", group="Classic",
    fonts=(Font("Playfair Display", "PlayfairDisplay-700-normal.woff2", 700),
           Font("Playfair Display", "PlayfairDisplay-900-normal.woff2", 900), _INTER),
    tokens={
        "--bg": "#f7f3ea", "--ink": "#1f1b16", "--muted": "#6b6453", "--accent": "#c0392b",
        "--font-head": "'Playfair Display', Georgia, serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "84px", "--img-radius": "4px",
        "--title-size": "72px", "--title-weight": "900", "--head-size": "44px",
    },
    decor_css=".kicker{border-bottom:1px solid #d8d2c2;padding-bottom:10px;}"
              ".bullets li{border-bottom:1px solid #ece7da;padding-bottom:14px;}"
              ".bullets li::before{content:'\\2014';}",
    image_style=ImageStyle(
        medium="refined editorial illustration", composition="elegant, generous whitespace, sophisticated",
        avoid="text, logos, watermarks, clutter",
        education_constraints="clear, age-appropriate, subject-accurate, legible behind text"),
    accent_role="ai",
)

VIBRANT_GRADIENT = TemplateSpec(
    key="vibrant-gradient", name="Vibrant Gradient", group="Classic",
    fonts=(Font("Space Grotesk", "SpaceGrotesk-700-normal.woff2", 700), _INTER),
    tokens={
        "--bg": "linear-gradient(135deg,#6d28d9,#db2777 55%,#f59e0b)", "--ink": "#ffffff",
        "--muted": "#f0e6ff", "--accent": "#ffe14d",
        "--font-head": "'Space Grotesk', system-ui, sans-serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "72px", "--img-radius": "16px",
        "--title-size": "66px", "--head-size": "44px", "--title-color": "#ffffff", "--head-color": "#ffffff",
    },
    decor_css=".bullets li{background:rgba(255,255,255,.14);padding:12px 18px;border-radius:10px;}"
              ".s-head{letter-spacing:-1px;}",
    image_style=ImageStyle(
        medium="bright bold flat-vector illustration", composition="energetic, high-saturation, dynamic",
        avoid="text, logos, watermarks",
        education_constraints="clear, age-appropriate, subject-accurate, legible behind text"),
    accent_role="ai",
)

CINEMATIC = TemplateSpec(
    key="cinematic", name="Cinematic Dark", group="Classic",
    fonts=(Font("Space Grotesk", "SpaceGrotesk-700-normal.woff2", 700), _INTER),
    tokens={
        "--bg": "radial-gradient(120% 120% at 80% 0%,#13233a,#070b12 70%)", "--ink": "#ffffff",
        "--muted": "#8aa0bf", "--accent": "#7CFC00",
        "--font-head": "'Space Grotesk', system-ui, sans-serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "72px", "--img-radius": "14px",
        "--title-size": "72px", "--head-size": "46px",
    },
    decor_css=".s-title,.key-concept .big{letter-spacing:-1px;}"
              ".bullets li{background:rgba(255,255,255,.06);padding:12px 18px;border-radius:10px;}",
    image_style=ImageStyle(
        medium="dramatic dark cinematic illustration", composition="high-contrast, moody, atmospheric",
        avoid="text, logos, watermarks",
        education_constraints="clear, age-appropriate, subject-accurate, legible behind text"),
    accent_role="fixed",
)

PLAYFUL_ORGANIC = TemplateSpec(
    key="playful-organic", name="Playful Organic", group="Classic",
    fonts=(Font("Fredoka", "Fredoka-600-normal.woff2", 600),),
    tokens={
        "--bg": "#fff6ec", "--ink": "#4a3b28", "--muted": "#8a7a63", "--accent": "#ef476f",
        "--font-head": "'Fredoka', 'Trebuchet MS', sans-serif", "--font-body": "'Fredoka', 'Trebuchet MS', sans-serif",
        "--pad": "72px", "--img-radius": "24px",
        "--title-size": "64px", "--head-size": "44px", "--head-color": "#ef476f", "--title-color": "#3d348b",
    },
    decor_css=".bullets li{background:#fff3e0;padding:14px 20px;border-radius:18px;}"
              ".bullets li::before{content:'\\2728';}",
    image_style=ImageStyle(
        medium="friendly rounded flat illustration", composition="cheerful, warm, simple shapes",
        avoid="text, logos, watermarks, scary imagery",
        education_constraints="clear, age-appropriate for younger grades, subject-accurate"),
    accent_role="ai",
)

SPECS = [EDITORIAL_BOLD, VIBRANT_GRADIENT, CINEMATIC, PLAYFUL_ORGANIC]
```

Create `backend/services/slide_templates/specs/refined.py`:

```python
"""Refined group — Minimal/Swiss, the clean default."""
from backend.services.slide_templates.types import Font, ImageStyle, TemplateSpec

MINIMAL = TemplateSpec(
    key="minimal", name="Minimal / Swiss", group="Refined",
    fonts=(Font("Inter", "Inter-400-normal.woff2", 400),
           Font("Inter", "Inter-800-normal.woff2", 800)),
    tokens={
        "--bg": "#ffffff", "--ink": "#111418", "--muted": "#8a8f98", "--accent": "#e63946",
        "--font-head": "'Inter', system-ui, sans-serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "84px", "--img-radius": "8px",
        "--title-size": "64px", "--title-weight": "800", "--head-size": "42px", "--head-color": "#111418",
        "--bar-height": "6px",
    },
    decor_css=".s-title{letter-spacing:-1.5px;} .s-head{letter-spacing:-.5px;}",
    image_style=ImageStyle(
        medium="clean minimal flat illustration", composition="generous whitespace, single-accent, uncluttered",
        avoid="text, logos, watermarks, busy backgrounds",
        education_constraints="clear, age-appropriate, subject-accurate, high contrast"),
    accent_role="ai",
)

SPECS = [MINIMAL]
```

Create `backend/services/slide_templates/specs/__init__.py`:

```python
from .classic import SPECS as _CLASSIC
from .refined import SPECS as _REFINED

ALL_SPECS = [*_CLASSIC, *_REFINED]
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_registry.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_templates/specs/ tests/test_slide_template_registry.py
git commit -m "feat(slides): 5 Phase-1A template descriptors (4 migrated + Minimal default)"
```

---

### Task 7: Registry, default, aliases (`__init__.py`)

**Files:**
- Modify: `backend/services/slide_templates/__init__.py`
- Test: `tests/test_slide_template_registry.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_slide_template_registry.py`:

```python
def test_registry_resolution_and_aliases():
    from backend.services.slide_templates import (
        TEMPLATES, DEFAULT_TEMPLATE, LEGACY_ALIASES, get_spec, GROUPS,
    )
    assert DEFAULT_TEMPLATE == "minimal"
    assert "editorial-bold" in TEMPLATES
    # legacy aliases resolve to a real spec
    assert get_spec("academic").key == "minimal"
    assert get_spec("editorial").key == "editorial-bold"
    assert get_spec("bold").key == "cinematic"
    assert get_spec("playful").key == "playful-organic"
    # unknown / None -> default
    assert get_spec("not-a-real-key").key == "minimal"
    assert get_spec(None).key == "minimal"
    # groups index every template exactly once
    grouped = [k for keys in GROUPS.values() for k in keys]
    assert sorted(grouped) == sorted(TEMPLATES)
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_registry.py::test_registry_resolution_and_aliases -v`
Expected: FAIL — `DEFAULT_TEMPLATE` is still `"academic"` (re-exported from legacy) and `get_spec`/`GROUPS`/`LEGACY_ALIASES` don't exist.

- [ ] **Step 3: Implement**

Replace `backend/services/slide_templates/__init__.py` entirely:

```python
"""Slide-template registry + resolution. Public API:
`template_css`, `get_spec`, `TEMPLATES`, `GROUPS`, `DEFAULT_TEMPLATE`, `LEGACY_ALIASES`,
and the descriptor types. See spec §3/§6/§8."""
from collections import OrderedDict

from .types import Font, ImageStyle, TemplateSpec  # noqa: F401
from .specs import ALL_SPECS

TEMPLATES = OrderedDict((s.key, s) for s in ALL_SPECS)
DEFAULT_TEMPLATE = "minimal"

# Old keys (pre-vivid-library) → new keys. Old `bold` was already a dark gradient,
# so bold→cinematic is faithful (spec §6 / §8).
LEGACY_ALIASES = {
    "academic": "minimal",
    "editorial": "editorial-bold",
    "bold": "cinematic",
    "playful": "playful-organic",
}

# group -> ordered list of keys (drives the picker; single source of truth)
_GROUP_ORDER = ["Classic", "Illustrated", "Themed", "Refined"]
GROUPS = OrderedDict(
    (g, [s.key for s in ALL_SPECS if s.group == g]) for g in _GROUP_ORDER
)
GROUPS = OrderedDict((g, ks) for g, ks in GROUPS.items() if ks)  # drop empty groups


def resolve_key(key):
    """Resolve a request key/alias to a registered key, falling back to default."""
    if key in TEMPLATES:
        return key
    if key in LEGACY_ALIASES:
        return LEGACY_ALIASES[key]
    return DEFAULT_TEMPLATE


def get_spec(key) -> TemplateSpec:
    """Return the TemplateSpec for a key/alias, default if unknown/None."""
    return TEMPLATES[resolve_key(key)]


# engine.template_css is imported last to avoid a circular import at module load
from .engine import template_css  # noqa: E402,F401
```

> The legacy `slide_templates_legacy.py` and its re-export are now gone from `__init__`; Task 8 provides the real `engine.template_css`, and Task 9 deletes the legacy file.

- [ ] **Step 4: Run it; verify it fails differently (engine missing)**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_registry.py::test_registry_resolution_and_aliases -v`
Expected: FAIL on `from .engine import template_css` (engine not yet created). This is expected — Task 8 creates it. **Do not commit until Task 8 makes this green.**

---

### Task 8: The engine (`engine.py`) + legacy swap

**Files:**
- Create: `backend/services/slide_templates/engine.py`
- Test: `tests/test_slide_template_engine.py` (extend) + the carried-over security test

- [ ] **Step 1: Write the failing test**

Append to `tests/test_slide_template_engine.py`:

```python
def test_template_css_composes_base_tokens_fonts_decor():
    from backend.services.slide_templates import template_css
    css = template_css("editorial-bold", accent="#1a7f43")
    assert ".slide" in css                         # base
    assert "--bg:#f7f3ea" in css.replace(" ", "")  # tokens
    assert "@font-face" in css                     # embedded fonts
    assert "\\2014" in css or "—" in css           # decor (em-dash bullet)


def test_ai_accent_injected_only_for_ai_role():
    from backend.services.slide_templates import template_css
    ai = template_css("editorial-bold", accent="#1a7f43")   # accent_role="ai"
    assert "--accent:#1a7f43" in ai.replace(" ", "")
    fixed = template_css("cinematic", accent="#1a7f43")      # accent_role="fixed"
    assert "--accent:#1a7f43" not in fixed.replace(" ", "")  # keeps its own palette


def test_alias_and_unknown_resolve():
    from backend.services.slide_templates import template_css
    assert template_css("academic", "#1a7f43") == template_css("minimal", "#1a7f43")
    assert template_css("nope", "#1a7f43") == template_css("minimal", "#1a7f43")


def test_malicious_accent_rejected():  # carried over from the old security test
    from backend.services.slide_templates import template_css
    payload = "#fff; } body { background:url(http://169.254.169.254/) } :root{--x:"
    css = template_css("editorial-bold", accent=payload)
    assert "169.254.169.254" not in css


def test_accent_trailing_newline_rejected():
    from backend.services.slide_templates import template_css
    assert "\n;" not in template_css("editorial-bold", accent="#fff\n")
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_engine.py -v`
Expected: FAIL — engine module not found.

- [ ] **Step 3: Implement**

Create `backend/services/slide_templates/engine.py`:

```python
"""Compose a template's full <style> body: base geometry + :root tokens (+ AI
accent for accent_role='ai') + embedded @font-face + decor_css. See spec §3."""
import re

from .base_css import BASE_CSS
from .fonts import font_face_css

# fullmatch (not match): `$` also matches before a trailing newline, which would
# let "#fff\n" through. Accept 3/6/8-digit hex only. (Carried from the old engine.)
_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_SAFE_ACCENT_FALLBACK = "#1a7f43"


def _safe_accent(accent) -> str:
    return accent if (isinstance(accent, str) and _HEX_COLOR.fullmatch(accent)) else _SAFE_ACCENT_FALLBACK


def template_css(key, accent="#1a7f43") -> str:
    # local import avoids a circular import (registry imports this module)
    from . import get_spec
    spec = get_spec(key)
    tokens = dict(spec.tokens)
    if spec.accent_role == "ai":
        tokens["--accent"] = _safe_accent(accent)
    root_vars = "".join(f"{k}:{v};" for k, v in tokens.items())
    root = f":root{{{root_vars}}}"
    return BASE_CSS + "\n" + font_face_css(spec.fonts) + "\n" + root + "\n" + spec.decor_css
```

- [ ] **Step 4: Run it; verify it passes**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_engine.py tests/test_slide_template_registry.py -v`
Expected: PASS (all engine + registry tests, including the registry-resolution test from Task 7).

- [ ] **Step 5: Commit (Tasks 7 + 8 together — they're interdependent)**

```bash
git add backend/services/slide_templates/__init__.py backend/services/slide_templates/engine.py tests/test_slide_template_engine.py tests/test_slide_template_registry.py
git commit -m "feat(slides): template engine (base+tokens+fonts+decor) + registry/aliases/get_spec"
```

---

### Task 9: Retire the legacy module + update its test

**Files:**
- Delete: `backend/services/slide_templates_legacy.py`
- Modify/replace: `tests/test_slide_templates.py` (the old token-swap test)

- [ ] **Step 1: Find every consumer of the legacy module**

Run:
```bash
grep -rn "slide_templates_legacy" backend tests
grep -rn "from backend.services.slide_templates import\|import slide_templates" backend tests | grep -v slide_templates_legacy
```
Expected: the only `slide_templates_legacy` reference left is the file itself (the `__init__` no longer imports it after Task 7). Public imports of `template_css`/`TEMPLATES`/`DEFAULT_TEMPLATE`/`build_deck_html` resolve through the package.

- [ ] **Step 2: Delete the legacy module**

```bash
git rm backend/services/slide_templates_legacy.py
```

- [ ] **Step 3: Replace the old token-swap test**

The old `tests/test_slide_templates.py` asserted the legacy `TEMPLATES` token dict + the old `template_css(name, accent)` signature. Replace its body so it exercises the new package surface (the engine/registry tests already cover internals; this file becomes a thin public-API smoke test):

```python
"""Public-API smoke test for the slide-template package (replaces the old
token-swap tests; engine/registry/validator have dedicated suites)."""
from backend.services.slide_templates import (
    template_css, TEMPLATES, DEFAULT_TEMPLATE, get_spec,
)


def test_public_api_renders_default():
    css = template_css(DEFAULT_TEMPLATE, accent="#1a7f43")
    assert ".slide" in css and "@font-face" in css


def test_unknown_template_falls_back_to_default():
    assert template_css("nope", "#1a7f43") == template_css(DEFAULT_TEMPLATE, "#1a7f43")


def test_legacy_key_resolves():
    assert get_spec("academic").key == DEFAULT_TEMPLATE
    assert "editorial-bold" in TEMPLATES
```

- [ ] **Step 4: Run the full slide suite + the html builder (which imports template_css)**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_templates.py tests/test_slide_html_builder.py tests/test_slide_generator.py tests/test_slides_web_routes.py -q`
Expected: all PASS. `build_deck_html` calls `template_css(deck["template"], accent)` — confirm the web-routes test (which posts a deck with `template:"academic"`) still renders (academic now resolves to minimal).

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_templates_legacy.py tests/test_slide_templates.py
git commit -m "refactor(slides): retire legacy slide_templates module; package is the single source"
```

---

### Task 10: Structured image style → `theme.style_prompt`

**Files:**
- Modify: `backend/services/slide_generator.py` (`generate_slide_content`, the `style_prompt` build at ~line 176-181)
- Test: `tests/test_slide_generator.py` (extend)

The image loop in `generate_slide_images` reads `theme["style_prompt"]` (verified: `slide_generator.py:216`). So we compose the template's structured `ImageStyle` into `style_prompt` inside `generate_slide_content` — the loop is unchanged, and `avoid` naturally prefixes every image call.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_slide_generator.py` (mirror the existing `test_generate_slide_content_records_template` patching):

```python
def test_image_style_comes_from_template(monkeypatch):
    import json as _json
    from backend.services import slide_generator
    from backend.services.llm_adapter.types import LLMResponse, TextPart, Usage

    def fake_chat(self, request):
        deck = {"title": "T", "theme": {"primary_color": "#123456"},
                "slides": [{"layout": "title", "title": "T"}]}
        return LLMResponse(content_parts=[TextPart(text=_json.dumps(deck))],
                           tool_calls=[], usage=Usage(0, 0, 0.0),
                           finish_reason="stop", provider="gemini", model="gemini-2.5-flash")

    monkeypatch.setattr("backend.services.llm_adapter.gemini_adapter.GeminiAdapter.chat", fake_chat)
    monkeypatch.setattr("backend.services.llm_adapter.gemini_adapter.genai.Client", lambda api_key=None: object())

    deck = slide_generator.generate_slide_content(
        content="cells", subject="Bio", grade="7", title="Cells", api_key="k",
        slide_count=3, template="playful-organic")
    sp = deck["theme"]["style_prompt"]
    assert "friendly rounded flat illustration" in sp   # template medium
    assert "avoid" in sp.lower() and "text" in sp.lower()  # avoid clause present
```

- [ ] **Step 2: Run it; verify it fails**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_generator.py::test_image_style_comes_from_template -v`
Expected: FAIL — current `style_prompt` is the generic color-based string, not the template medium.

- [ ] **Step 3: Implement**

In `backend/services/slide_generator.py`, replace the `style_prompt` build (currently lines ~176-181, the block starting `# Build the image style prompt from the AI's chosen theme`):

```python
    # Build the image style prompt from the SELECTED TEMPLATE's structured style
    # (spec §5) — medium + composition steer the look, avoid + education_constraints
    # guard franchise/clarity drift. Repeated on every image call via this prompt.
    from backend.services.slide_templates import get_spec
    _img = get_spec(template).image_style
    result["theme"]["style_prompt"] = (
        f"{_img.medium}, {_img.composition}. "
        f"Avoid: {_img.avoid}. Must be {_img.education_constraints}. "
        "No text in the image."
    )
```

(`template` is already a parameter of `generate_slide_content`.)

- [ ] **Step 4: Run it; verify it passes + no regression**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_generator.py -q`
Expected: all PASS (the older `test_generate_slide_content_records_template` still passes — it only asserts `deck["template"]` + the "accent color" prompt steer, both unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_generator.py tests/test_slide_generator.py
git commit -m "feat(slides): image style_prompt composed from template's structured ImageStyle"
```

---

### Task 11: Registry-driven route validation + `GET /api/slide-templates`

**Files:**
- Modify: `backend/routes/planner_routes.py` (`generate_slides` validation ~line 2107-2109; add a route near `generate_slides`)
- Test: `tests/test_generate_slides.py` (extend) + `tests/test_slide_template_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_slide_template_api.py` (reuse the `client`/`headers` fixture pattern from `tests/test_generate_slides.py` — copy the `app`/`client`/`headers` fixtures verbatim):

```python
import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'; os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app

@pytest.fixture
def client(app): return app.test_client()

@pytest.fixture
def headers(): return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def test_slide_templates_endpoint_returns_grouped_registry(client, headers):
    resp = client.get('/api/slide-templates', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "groups" in data
    keys = [t["key"] for g in data["groups"] for t in g["templates"]]
    assert "editorial-bold" in keys and "minimal" in keys
    # each template exposes key + name + group
    sample = data["groups"][0]["templates"][0]
    assert {"key", "name"} <= set(sample)
```

Add to `tests/test_generate_slides.py`:

```python
def test_generate_slides_garbage_template_falls_back_to_minimal(client, headers):
    from unittest.mock import patch
    captured = {}
    def fake_content(**kwargs):
        captured.update(kwargs)
        return {"title": "C", "theme": {}, "slides": [{"h": 1}], "template": kwargs.get("template")}
    with patch('backend.api_keys.get_api_key', return_value='k'), \
         patch('backend.services.slide_generator.generate_slide_content', side_effect=fake_content), \
         patch('backend.services.slide_generator.generate_slide_images', return_value={}):
        resp = client.post('/api/generate-slides',
                           json={"content": "x", "generateImages": False, "template": "<garbage>"},
                           headers=headers)
    assert resp.status_code == 200
    assert captured["template"] == "minimal"
```

> Design note: validation now means "resolve via the registry." A key that is a registered template OR a legacy alias passes through as-is; anything else resolves to `DEFAULT_TEMPLATE` and is logged. In Phase 1A only the 5 keys + 4 aliases are registered, so `"<garbage>"` → `minimal`. (Keys for not-yet-built templates like `anime` are not registered until their wave, so they too would resolve to `minimal` — acceptable; the picker only offers registered keys.)

- [ ] **Step 2: Run them; verify they fail**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_api.py tests/test_generate_slides.py::test_generate_slides_garbage_template_falls_back_to_minimal -v`
Expected: FAIL — `/api/slide-templates` 404; garbage template currently kept as `academic` default (old hardcoded whitelist), not `minimal`.

- [ ] **Step 3: Implement**

In `backend/routes/planner_routes.py`:

(a) Replace the template validation in `generate_slides` (currently):
```python
    template = (data.get('template') or 'academic')
    if template not in ('editorial', 'bold', 'academic', 'playful'):
        template = 'academic'
```
with registry-driven resolution + logging:
```python
    from backend.services.slide_templates import resolve_key, TEMPLATES, LEGACY_ALIASES
    _req_template = data.get('template') or 'minimal'
    template = resolve_key(_req_template)
    if _req_template not in TEMPLATES and _req_template not in LEGACY_ALIASES:
        _logger.warning("unknown slide template %r -> %s", _req_template, template)
```

(b) Add a route next to `generate_slides`:
```python
@planner_bp.route('/api/slide-templates', methods=['GET'])
@require_teacher
@handle_route_errors
def slide_templates():
    """Registry for the picker — single source of truth (spec §7/§9)."""
    from backend.services.slide_templates import GROUPS, TEMPLATES
    groups = [
        {"group": g, "templates": [
            {"key": k, "name": TEMPLATES[k].name, "group": g} for k in keys
        ]}
        for g, keys in GROUPS.items()
    ]
    return jsonify({"groups": groups})
```

- [ ] **Step 4: Run them; verify they pass**

Run: `OPENAI_API_KEY= python -m pytest tests/test_slide_template_api.py tests/test_generate_slides.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/planner_routes.py tests/test_slide_template_api.py tests/test_generate_slides.py
git commit -m "feat(slides): registry-driven template validation + GET /api/slide-templates"
```

---

### Task 12: PDF waits for embedded fonts (`slide_pdf.py`)

**Files:**
- Modify: `backend/services/slide_pdf.py` (`html_to_pdf`, after `set_content`)
- Test: `tests/test_slide_pdf.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_slide_pdf.py`:

```python
def test_html_to_pdf_awaits_fonts_ready(monkeypatch):
    """The PDF path must await document.fonts.ready (+ rAF) before printing so
    embedded @font-face are applied. We assert the page is driven through that
    wait by recording evaluate() calls on a fake page."""
    from backend.services import slide_pdf

    calls = []
    class _Page:
        def set_content(self, html, **kw): calls.append(("set_content", kw.get("wait_until")))
        def evaluate(self, expr): calls.append(("evaluate", expr))
        def pdf(self, **kw): calls.append(("pdf", None)); return b"%PDF-1.4 x"
    class _Browser:
        def new_page(self): return _Page()
        def close(self): pass
    class _PW:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        class chromium:
            @staticmethod
            def launch(args=None): return _Browser()
    monkeypatch.setattr(slide_pdf, "sync_playwright", lambda: _PW())

    pdf = slide_pdf.html_to_pdf("<html><body>x</body></html>")
    assert pdf[:5] == b"%PDF-"
    evals = " ".join(e for (k, e) in calls if k == "evaluate")
    assert "fonts.ready" in evals
    # fonts.ready awaited BEFORE pdf()
    order = [k for (k, _) in calls]
    assert order.index("evaluate") < order.index("pdf")
```

> NOTE: `_PW.chromium.launch` is a nested class with a static method so `p.chromium.launch(...)` works on the fake.

- [ ] **Step 2: Run it; verify it fails**

Run: `python -m pytest tests/test_slide_pdf.py::test_html_to_pdf_awaits_fonts_ready -v`
Expected: FAIL — no `evaluate("...fonts.ready...")` call today (and the fake page lacks the methods the real code calls in the right order).

- [ ] **Step 3: Implement**

In `backend/services/slide_pdf.py`, inside `html_to_pdf`, between `page.set_content(...)` and `pdf = page.pdf(...)`, add the font-settle wait:

```python
                page = browser.new_page()
                page.set_content(html, wait_until="load", timeout=15000)
                # Ensure embedded @font-face are applied before printing: await
                # fonts.ready, then one rAF so any font-metric reflow settles.
                page.evaluate(
                    "async () => { await document.fonts.ready;"
                    " await new Promise(r => requestAnimationFrame(r)); }"
                )
                pdf = page.pdf(width="1280px", height="720px",
                               print_background=True, prefer_css_page_size=True)
```

- [ ] **Step 4: Run it; verify it passes (+ the real render test if Chromium present)**

Run: `python -m pytest tests/test_slide_pdf.py -v`
Expected: the new test PASSES; `test_html_to_pdf_returns_pdf_bytes` PASSES (Chromium local) or SKIPS; `test_slide_pdf_unavailable_raises_typed_error` PASSES.

- [ ] **Step 5: Commit**

```bash
git add backend/services/slide_pdf.py tests/test_slide_pdf.py
git commit -m "feat(slides): await document.fonts.ready + rAF before printing PDF"
```

---

### Task 13: Frontend — API client + picker keys

**Files:**
- Modify: `frontend/src/services/api.js` (add `getSlideTemplates`)
- Modify: `frontend/src/components/planner-tools/SlideTemplatePicker.jsx` (new keys; still flat in 1A)
- Test: `frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx` (update)

In 1A the picker stays a flat list but uses the **new** keys/names so generated decks carry valid keys. (The grouped, API-driven, thumbnailed picker is Plan 1B; `getSlideTemplates` is added now so 1B can consume it.)

- [ ] **Step 1: Add the API client function**

Append to `frontend/src/services/api.js` (next to `renderSlidesHtml`):

```javascript
export async function getSlideTemplates() {
  const authHeaders = await getAuthHeaders();
  const resp = await fetch('/api/slide-templates', {
    headers: { 'Content-Type': 'application/json', ...authHeaders },
  });
  if (!resp.ok) throw new Error('Failed to load slide templates');
  return resp.json();   // { groups: [{ group, templates: [{key,name,group}] }] }
}
```

- [ ] **Step 2: Update the picker test (red), then the picker**

Replace `frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx`:

```jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SlideTemplatePicker from '../components/planner-tools/SlideTemplatePicker';

describe('SlideTemplatePicker', () => {
  it('renders the five Phase-1A templates by name', () => {
    render(<SlideTemplatePicker value="minimal" onChange={() => {}} />);
    for (const name of ['Editorial Bold', 'Vibrant Gradient', 'Cinematic Dark', 'Playful Organic', 'Minimal / Swiss']) {
      expect(screen.getByText(name)).toBeTruthy();
    }
  });

  it('calls onChange with the template key when clicked', () => {
    const onChange = vi.fn();
    render(<SlideTemplatePicker value="minimal" onChange={onChange} />);
    fireEvent.click(screen.getByText('Cinematic Dark'));
    expect(onChange).toHaveBeenCalledWith('cinematic');
  });
});
```

Run (red): `cd frontend && npx vitest run src/__tests__/SlideTemplatePicker.mount.test.jsx` → FAIL (old names/keys).

Then replace the `TEMPLATES` array in `frontend/src/components/planner-tools/SlideTemplatePicker.jsx`:

```jsx
const TEMPLATES = [
  { key: "editorial-bold", name: "Editorial Bold", blurb: "Magazine serif, refined" },
  { key: "vibrant-gradient", name: "Vibrant Gradient", blurb: "Bold gradient keynote" },
  { key: "cinematic", name: "Cinematic Dark", blurb: "Dark, neon, dramatic" },
  { key: "playful-organic", name: "Playful Organic", blurb: "Warm, rounded, younger grades" },
  { key: "minimal", name: "Minimal / Swiss", blurb: "Clean, structured (default)" },
];
```
(Everything else in the component is unchanged.)

- [ ] **Step 3: Run picker tests + the generator mount test + full FE suite + build**

Run: `cd frontend && npx vitest run src/__tests__/SlideTemplatePicker.mount.test.jsx src/__tests__/SlideDeckGenerator.mount.test.jsx`
Expected: PASS. (The generator mount test asserts "Academic"/"Editorial" earlier — update those assertions to `Minimal / Swiss`/`Editorial Bold` if they fail.)
Then: `cd frontend && npx vitest run && npm run build`
Expected: all PASS; `✓ built`.

- [ ] **Step 4: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add frontend/src/services/api.js frontend/src/components/planner-tools/SlideTemplatePicker.jsx frontend/src/__tests__/SlideTemplatePicker.mount.test.jsx frontend/src/__tests__/SlideDeckGenerator.mount.test.jsx
git commit -m "feat(slides): api.getSlideTemplates + picker on new template keys"
```

> NOTE: the generator's default `useState('academic')` (SlideDeckGenerator.jsx) should become `useState('minimal')` so a fresh deck defaults to the new default. Include that one-line change in this commit and confirm the mount test still passes.

---

### Task 14: Phase 1A branch verification + PR

- [ ] **Step 1: Full backend suite**

Run: `OPENAI_API_KEY= python -m pytest -q --ignore=tests/load`
Expected: all green (baseline 6100 passed + the new tests; the chromium render test passes locally or skips).

- [ ] **Step 2: Cross-cutting grep for everything touched**

Run: `grep -rln "slide_templates\|slide_generator\|slide_pdf\|generate-slides\|SlideTemplatePicker" tests/ frontend/src/__tests__/`
Run every file surfaced; confirm green.

- [ ] **Step 3: Lint + SAST + CQ**

Run: `ruff check backend/ && bandit -q -r backend/services/slide_templates/ backend/services/slide_pdf.py && python scripts/cq_scan_backend.py | tail -3 && node scripts/cq_scan_frontend.mjs | tail -2`
Expected: ruff clean; bandit no new findings; CQ scan shows no new function >200 LOC and no file >2,500 (the package split keeps each file small).

- [ ] **Step 4: Frontend**

Run: `cd frontend && npx vitest run && npm run build`
Expected: all PASS; `✓ built`.

- [ ] **Step 5: GitNexus reindex**

Run: `npx gitnexus analyze --embeddings --skip-agents-md`

- [ ] **Step 6: Open PR (Class B — manual merge after review)**

Push; open a PR titled `feat(slides): Phase 1A — declarative template engine + 5 templates`. Body: classification **Class B**, spec/plan refs, the evidence ledger (test counts), and the note that **no visual regression** is expected (the 5 templates render via the existing builder/PDF path; the legacy 4 looks are reproduced as descriptors). Dispatch the opus code-reviewer + a Codex adversarial pass (focus: the font-embedding path, the alias/`get_spec` choke point being used by every render path, the `decor_css` validator completeness, and the `accent_role` injection). Fix to clean. **Do NOT `--auto`-merge.** Operator (Hard Rule #8): after deploy, generate a deck in each of the 5 styles and download the PDF to confirm embedded fonts render in prod Chromium.

---

## Self-Review Notes (author)

- **Spec coverage (1A scope):** §3 package structure → Tasks 1,2,3,5,7,8,9; descriptors → Task 6; §4 fonts (embed + manifest + ready) → Tasks 4,5,12; §5 structured image_style → Task 10; §6 accent + centralized alias resolution + logging → Tasks 7,8,11; §7 picker (flat in 1A; API added) → Tasks 11,13; §9 registry-via-API single source → Task 11; §10 unit/validator/registry/security tests → Tasks 1,3,6,7,8; §11 licensing manifest → Task 4. **Deferred to Plan 1B (called out up front):** layout-variant mechanism, Newspaper structural proof, grouped picker thumbnails/search, Playwright render-smoke tests, `document.fonts` computed-family assertion.
- **Types/names consistency:** `Font(family,file,weight,style)`, `ImageStyle(medium,composition,avoid,education_constraints)`, `TemplateSpec(...,accent_role,layout_variants)`, `template_css(key,accent)`, `get_spec`/`resolve_key`, `font_face_css(fonts)`, `validate_decor_css(css)->list`, `TEMPLATES`/`GROUPS`/`DEFAULT_TEMPLATE`/`LEGACY_ALIASES`, `getSlideTemplates()` — used consistently across tasks.
- **No placeholders:** every code step has complete code; the only manual step is running `fetch_slide_fonts.py` (Task 4), which is a real reproducible script with pinned versions and a fallback instruction.
- **Ordering hazard handled:** the module→package shadowing is resolved by the Task 1 `git mv` to `_legacy` + temporary re-export, with the legacy module deleted in Task 9 once the engine is live. Tasks 7+8 are committed together (interdependent); the plan says so explicitly.
