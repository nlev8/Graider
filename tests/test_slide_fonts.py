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
