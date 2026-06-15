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
