import base64
from backend.services.slide_html_builder import build_deck_html

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
