"""PDF-safe CSS subset enforcement for template decor_css (spec §3).

decor_css is always code-authored (it comes only from the hardcoded TemplateSpec
descriptors — there is no path for user-supplied CSS to reach it). This validator
is therefore a *developer-error guard*, not an adversarial sanitizer: it catches a
descriptor that accidentally pulls in an external resource (breaks the no-network
self-contained render) or a property that doesn't print reliably in headless
Chromium. Because the input is trusted, literal-spelling matching is sufficient —
it deliberately does NOT decode CSS escape sequences (e.g. `@im\\70ort`), since a
developer obfuscating their own CSS is not in scope. Enforced as a CI gate by
tests/test_slide_template_registry.py::test_every_decor_css_is_pdf_safe, which runs
every shipped decor_css through this validator."""
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
