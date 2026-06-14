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
