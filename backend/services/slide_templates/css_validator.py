"""PDF-safe CSS subset enforcement for template decor_css (spec §3).

decor_css is code-authored, but this validator guards against print-hostile or
non-self-contained CSS slipping in: external resources break the no-network
self-contained render, and some properties don't print reliably in headless
Chromium. Run in tests (and at startup in debug)."""
import re

# url(...) that is NOT a data: URI
_EXTERNAL_URL = re.compile(r"url\(\s*['\"]?(?!data:)", re.IGNORECASE)
_IMPORT = re.compile(r"@import", re.IGNORECASE)
_INFINITE = re.compile(r"\binfinite\b", re.IGNORECASE)
# properties that don't print reliably
_BANNED_PROPS = ("backdrop-filter", "mix-blend-mode")


def validate_decor_css(css: str) -> list[str]:
    """Return a list of violation messages ([] means PDF-safe)."""
    errors = []
    if _IMPORT.search(css):
        errors.append("@import is not allowed (breaks self-contained render)")
    if _EXTERNAL_URL.search(css):
        errors.append("external url(...) is not allowed; only data: URIs")
    if _INFINITE.search(css):
        errors.append("unbounded/infinite animation is not allowed")
    for prop in _BANNED_PROPS:
        if re.search(r"\b" + re.escape(prop) + r"\s*:", css, re.IGNORECASE):
            errors.append(f"print-hostile property '{prop}' is not allowed")
    return errors
