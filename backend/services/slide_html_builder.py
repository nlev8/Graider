"""Render a deck model into one self-contained HTML string.

Pure + Flask-free. Used for both the iframe preview and the Playwright PDF, so
preview and PDF are pixel-identical. All AI-produced text is HTML-escaped.
Images (base64, keyed by str(slide_index) as produced by planner_study_aids)
are embedded as data URIs so the HTML is portable.
"""
from html import escape

from backend.services.slide_templates import template_css, DEFAULT_TEMPLATE


def _esc(value) -> str:
    return escape(str(value if value is not None else ""))


def _bullets(items) -> str:
    lis = "".join(f"<li>{_esc(b)}</li>" for b in (items or []))
    return f'<ul class="bullets">{lis}</ul>' if lis else ""


def _img_tag(data_uri: str) -> str:
    return f'<img src="{_esc(data_uri)}" alt="">' if data_uri else ""


def _render_title(slide, img):
    sub = f'<div class="s-sub">{_esc(slide.get("subtitle"))}</div>' if slide.get("subtitle") else ""
    return (f'<div class="divider"><div><div class="s-title">{_esc(slide.get("title"))}</div>{sub}</div></div>')


def _render_content(slide, img):
    art = f'<div class="art">{_img_tag(img)}</div>' if img else ""
    cls = "content-row" if img else ""
    text = f'<div class="text">{_bullets(slide.get("bullets"))}</div>' if img else _bullets(slide.get("bullets"))
    return (f'<div class="accent-bar"></div>'
            f'<div class="s-head">{_esc(slide.get("title"))}</div>'
            f'<div class="{cls}">{text}{art}</div>')


def _render_two_column(slide, img):
    left = f'<div class="col"><h3>{_esc(slide.get("left_title"))}</h3>{_bullets(slide.get("left_bullets"))}</div>'
    right = f'<div class="col"><h3>{_esc(slide.get("right_title"))}</h3>{_bullets(slide.get("right_bullets"))}</div>'
    return (f'<div class="accent-bar"></div>'
            f'<div class="s-head">{_esc(slide.get("title"))}</div>'
            f'<div class="body-2col">{left}{right}</div>')


def _render_key_concept(slide, img):
    text = slide.get("content") or slide.get("title")
    return f'<div class="key-concept"><div class="big">{_esc(text)}</div></div>'


def _render_image_focus(slide, img):
    cap = f'<div class="caption">{_esc(slide.get("caption"))}</div>' if slide.get("caption") else ""
    head = f'<div class="s-head">{_esc(slide.get("title"))}</div>' if slide.get("title") else ""
    return f'{head}<div class="image-focus">{_img_tag(img)}{cap}</div>'


def _render_section_divider(slide, img):
    return f'<div class="divider"><div class="s-title">{_esc(slide.get("title"))}</div></div>'


_LAYOUTS = {
    "title": _render_title,
    "content": _render_content,
    "two_column": _render_two_column,
    "key_concept": _render_key_concept,
    "image_focus": _render_image_focus,
    "section_divider": _render_section_divider,
}


def _render_slide(slide, img) -> str:
    fn = _LAYOUTS.get(slide.get("layout"), _render_content)
    return f'<section class="slide layout-{_esc(slide.get("layout"))}">{fn(slide, img)}</section>'


def build_deck_html(deck: dict, images: dict | None = None) -> str:
    """deck model + {str(index): base64} images -> self-contained HTML string."""
    images = images or {}
    template = deck.get("template") or DEFAULT_TEMPLATE
    accent = (deck.get("theme") or {}).get("primary_color") or "#1a7f43"
    css = template_css(template, accent)

    sections = []
    for idx, slide in enumerate(deck.get("slides", [])):
        b64 = images.get(str(idx)) or images.get(idx)
        data_uri = f"data:image/png;base64,{b64}" if b64 else ""
        sections.append(_render_slide(slide or {}, data_uri))

    return (
        "<!DOCTYPE html>"
        f'<html><head><meta charset="utf-8"><title>{_esc(deck.get("title"))}</title>'
        f"<style>{css}</style></head>"
        f'<body><div class="deck">{"".join(sections)}</div></body></html>'
    )
