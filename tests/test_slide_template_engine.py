import pytest

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


@pytest.mark.parametrize("good", ["#abc", "#1a7f43", "#1A7F43FF"])
def test_valid_hex_accents_pass_through(good):
    # 3/6/8-digit hex are all accepted by the engine's _HEX_COLOR fullmatch.
    from backend.services.slide_templates import template_css
    css = template_css("editorial-bold", accent=good)
    assert f"--accent:{good}" in css.replace(" ", "")


@pytest.mark.parametrize("bad", ["#fff\n", "#1a7f43\n", "#fff\n; }", "#fff\r\n"])
def test_newline_or_breakout_accent_falls_back(bad):
    # Trailing-newline / CSS-breakout accents must fail the fullmatch and be
    # replaced by the safe fallback — the raw payload never reaches the CSS.
    from backend.services.slide_templates import template_css
    css = template_css("editorial-bold", accent=bad)
    assert "--accent:#1a7f43" in css.replace(" ", "")  # safe fallback injected
    assert bad not in css                               # raw payload absent
