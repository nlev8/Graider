"""Render slide-deck HTML to a 16:9 PDF via headless Chromium (Playwright).

Synchronous: a typical deck renders in a few seconds, mirroring the existing
PPTX export route. Raises SlidePdfError on any failure so routes return a clean
message instead of a 500.
"""
import logging

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class SlidePdfError(RuntimeError):
    """Raised when PDF rendering is unavailable or fails."""


def html_to_pdf(html: str) -> bytes:
    """Render a self-contained HTML deck to PDF bytes (1280x720 pages)."""
    try:
        with sync_playwright() as p:
            # --no-sandbox: Chromium cannot enable its sandbox when running as
            # root, the common container/Railway case. Safe here because the
            # input HTML is server-generated and fully escaped (see
            # slide_html_builder) — there is no untrusted page navigation.
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                page = browser.new_page()
                # The deck is self-contained (CSS + data-URI images inlined), so
                # "load" fires promptly; an explicit timeout makes the bound
                # intentional rather than inheriting the 30s default.
                page.set_content(html, wait_until="load", timeout=15000)
                pdf = page.pdf(width="1280px", height="720px",
                               print_background=True, prefer_css_page_size=True)
            finally:
                browser.close()
        if not pdf or pdf[:5] != b"%PDF-":
            raise SlidePdfError("Playwright returned empty/invalid PDF")
        return pdf
    except SlidePdfError:
        raise
    except Exception as e:  # browser missing, launch failure, timeout, etc.
        logger.warning("slide PDF render failed: %s", e)
        raise SlidePdfError(str(e)) from e
