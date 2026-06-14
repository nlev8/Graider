"""Compose a template's full <style> body: base geometry + :root tokens (+ AI
accent for accent_role='ai') + embedded @font-face + decor_css. See spec §3."""
import re

from .base_css import BASE_CSS
from .fonts import font_face_css

# fullmatch (not match): `$` also matches before a trailing newline, which would
# let "#fff\n" through. Accept 3/6/8-digit hex only. (Carried from the old engine.)
_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_SAFE_ACCENT_FALLBACK = "#1a7f43"


def _safe_accent(accent) -> str:
    return accent if (isinstance(accent, str) and _HEX_COLOR.fullmatch(accent)) else _SAFE_ACCENT_FALLBACK


def template_css(key, accent=_SAFE_ACCENT_FALLBACK) -> str:
    # local import avoids a circular import (registry imports this module)
    from . import get_spec
    spec = get_spec(key)
    tokens = dict(spec.tokens)
    if spec.accent_role == "ai":
        tokens["--accent"] = _safe_accent(accent)
    root_vars = "".join(f"{k}:{v};" for k, v in tokens.items())
    root = f":root{{{root_vars}}}"
    return BASE_CSS + "\n" + font_face_css(spec.fonts) + "\n" + root + "\n" + spec.decor_css
