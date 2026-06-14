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
