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
