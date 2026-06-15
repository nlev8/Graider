import base64
import re
import shutil
import subprocess
import tempfile

import pytest

from backend.services.slide_html_builder import build_deck_html


def _chromium_available():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:  # noqa: BLE001  # any launch failure => treat as unavailable, skip
        return False


def _render_deps_available():
    return shutil.which("pdffonts") is not None and _chromium_available()


def _embedded_font_names(pdf_bytes):
    """Return the lowercased, subset-prefix-stripped embedded font names of a PDF."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf_bytes)
        f.flush()
        out = subprocess.run(["pdffonts", f.name], capture_output=True, text=True).stdout
    names = [ln.split()[0] for ln in out.splitlines()[2:] if ln.strip()]
    return [re.sub(r"[^a-z0-9]", "", re.sub(r"^[A-Z]{6}\+", "", n).lower()) for n in names]


def _selector_sets_head_font(html, klass):
    """True if some CSS rule whose selector list includes `klass` declares
    font-family: var(--font-head).

    Headings inherit --font-body from the `.slide` rule, so a heading only
    renders in the template's display font when a rule *explicitly* targets its
    class with the head font. (Inheritance from `.slide` is body; a matching
    rule is what overrides it.)
    """
    # Strip CSS comments first: the regex below treats everything between `}` and
    # `{` as the selector, which would otherwise include explanatory comments that
    # mention these class names — making the test pass on the comment text even if
    # the actual rule were reverted (a silently-neutered regression guard).
    css = re.sub(r"/\*.*?\*/", "", html, flags=re.DOTALL)
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if re.search(rf"{re.escape(klass)}(?![\w-])", sel) and \
                "var(--font-head)" in body.replace(" ", ""):
            return True
    return False

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


def test_image_data_cannot_break_out_of_src_attribute():
    """The base64 image string is attacker-controllable via the POST body, so it
    must be escaped before going into src=\"...\"."""
    evil = '"></img><script>alert(1)</script>'
    deck = {"title": "X", "template": "academic", "theme": {},
            "slides": [{"layout": "image_focus", "title": "I"}]}
    html = build_deck_html(deck, images={"0": evil})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_unknown_template_does_not_crash():
    deck = dict(DECK); deck["template"] = "bogus"
    html = build_deck_html(deck, images={})
    assert 'class="slide' in html


def test_slide_headings_use_the_template_head_font():
    """Regression: slide titles and section headings must render in the
    template's display (head) font, not inherit the body font.

    The builder emits headings as <div class="s-title"> / <div class="s-head">
    and the key-concept statement as <div class="big"> — never <h1>/<h2>. BASE_CSS
    applied --font-head only to `.slide h1, .slide h2`, which match nothing, so
    every heading inherited --font-body. On templates where head != body
    (editorial-bold=Playfair, vibrant-gradient/cinematic=Space Grotesk) the
    headline typography silently fell back to Inter — defeating the per-template
    visual identity. (Found via prod PDF font inspection, 2026-06-14.)
    """
    deck = {
        "title": "T", "template": "editorial-bold", "theme": {},
        "slides": [
            {"layout": "title", "title": "Big Title"},
            {"layout": "content", "title": "Section Head", "bullets": ["x"]},
            {"layout": "key_concept", "content": "A focal statement"},
        ],
    }
    html = build_deck_html(deck, images={})
    assert _selector_sets_head_font(html, ".s-title"), ".s-title must use var(--font-head)"
    assert _selector_sets_head_font(html, ".s-head"), ".s-head must use var(--font-head)"
    assert _selector_sets_head_font(html, ".big"), ".key-concept .big must use var(--font-head)"


@pytest.mark.skipif(not _render_deps_available(),
                    reason="needs Chromium + pdffonts (poppler) for an end-to-end render")
def test_headings_render_in_head_font_end_to_end():
    """Cascade-accurate proof that the syntactic test above can't give: actually
    render editorial-bold (head=Playfair Display, body=Inter) through the real
    Chromium PDF path and confirm the heading text embeds the head font.

    Uses a deck with NO two_column slide, so the `.col h3` rule (which already
    used --font-head) cannot mask the result — the Playfair glyphs can only come
    from .s-title/.s-head/.big. Pre-fix this PDF embedded only Inter.
    """
    from backend.services.slide_pdf import html_to_pdf
    deck = {
        "title": "T", "template": "editorial-bold", "theme": {},
        "slides": [
            {"layout": "title", "title": "Big Title"},
            {"layout": "content", "title": "Section Head", "bullets": ["body text"]},
            {"layout": "key_concept", "content": "A focal statement"},
        ],
    }
    fonts = _embedded_font_names(html_to_pdf(build_deck_html(deck, images={})))
    assert any("playfair" in f for f in fonts), \
        f"editorial-bold headings should embed Playfair Display; got {fonts}"
