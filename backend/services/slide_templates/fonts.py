"""Embed bundled woff2 fonts as base64 @font-face so decks are self-contained
(identical iframe preview + Chromium PDF, offline). Only the selected template's
fonts are embedded per deck. See spec §4."""
import base64
import functools
import os

_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "slide_fonts")


class SlideFontError(RuntimeError):
    """Raised when a referenced font file is missing from the bundle."""


@functools.lru_cache(maxsize=128)
def _b64(filename: str) -> str:
    path = os.path.join(_FONT_DIR, filename)
    if not os.path.exists(path):
        raise SlideFontError(f"bundled font missing: {filename}")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def font_face_css(fonts) -> str:
    """fonts: tuple[Font, ...] -> @font-face block embedding each as a data URI."""
    blocks = []
    for f in fonts:
        b64 = _b64(f.file)
        blocks.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%d;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2');}"
            % (f.family, f.style, f.weight, b64)
        )
    return "".join(blocks)
