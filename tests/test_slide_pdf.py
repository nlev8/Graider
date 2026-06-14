import pytest


def _chromium_available():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            b.close()
        return True
    except Exception:
        return False


def test_slide_pdf_unavailable_raises_typed_error(monkeypatch):
    """When Playwright/Chromium fails to launch, raise SlidePdfError (not a bare Exception)."""
    from backend.services import slide_pdf

    class _Boom:
        def __enter__(self): raise RuntimeError("no browser")
        def __exit__(self, *a): return False

    monkeypatch.setattr(slide_pdf, "sync_playwright", lambda: _Boom())
    with pytest.raises(slide_pdf.SlidePdfError):
        slide_pdf.html_to_pdf("<html><body>x</body></html>")


@pytest.mark.skipif(not _chromium_available(), reason="Chromium not installed in this env")
def test_html_to_pdf_returns_pdf_bytes():
    from backend.services.slide_pdf import html_to_pdf
    pdf = html_to_pdf("<!DOCTYPE html><html><body><h1>Hi</h1></body></html>")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 500
