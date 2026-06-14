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
