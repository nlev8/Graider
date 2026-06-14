"""Temporary bridge: re-export the legacy engine + the new descriptor types so
imports stay stable while the engine is built task-by-task. Replaced in Task 7."""
from .types import Font, ImageStyle, TemplateSpec  # noqa: F401
from backend.services.slide_templates_legacy import (  # noqa: F401
    template_css, TEMPLATES, DEFAULT_TEMPLATE,
)
