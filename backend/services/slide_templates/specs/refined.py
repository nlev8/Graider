"""Refined group — Minimal/Swiss, the clean default."""
from backend.services.slide_templates.types import ImageStyle, TemplateSpec
from backend.services.slide_templates.specs._fonts import INTER, INTER_BLACK

MINIMAL = TemplateSpec(
    key="minimal", name="Minimal / Swiss", group="Refined",
    fonts=(INTER, INTER_BLACK),
    tokens={
        "--bg": "#ffffff", "--ink": "#111418", "--muted": "#8a8f98", "--accent": "#e63946",
        "--font-head": "'Inter', system-ui, sans-serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "84px", "--img-radius": "8px",
        "--title-size": "64px", "--title-weight": "800", "--head-size": "42px", "--head-color": "#111418",
        "--bar-height": "6px",
    },
    decor_css=".s-title{letter-spacing:-1.5px;} .s-head{letter-spacing:-.5px;}",
    image_style=ImageStyle(
        medium="clean minimal flat illustration", composition="generous whitespace, single-accent, uncluttered",
        avoid="text, logos, watermarks, busy backgrounds",
        education_constraints="clear, age-appropriate, subject-accurate, high contrast"),
    accent_role="ai",
)

SPECS = [MINIMAL]
