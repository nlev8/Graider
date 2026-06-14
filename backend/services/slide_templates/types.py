"""Declarative template descriptor types. See
docs/superpowers/specs/2026-06-14-vivid-slide-template-library-design.md §3."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Font:
    family: str            # CSS family name, e.g. "Inter"
    file: str              # woff2 filename in backend/assets/slide_fonts/
    weight: int = 400
    style: str = "normal"  # "normal" | "italic"


@dataclass(frozen=True)
class ImageStyle:
    """Structured Gemini image style — composed into theme.style_prompt, never
    passed as one freeform phrase (spec §5)."""
    medium: str
    composition: str
    avoid: str
    education_constraints: str


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    name: str
    group: str                 # Classic | Illustrated | Themed | Refined
    fonts: tuple
    tokens: dict
    decor_css: str             # PDF-safe subset, validated (spec §3)
    image_style: ImageStyle
    accent_role: str = "fixed"             # "fixed" | "ai"
    layout_variants: dict = field(default_factory=dict)   # {layout: variant_name} (Plan 1B)
