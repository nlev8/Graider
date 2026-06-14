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


def test_html_to_pdf_awaits_fonts_ready(monkeypatch):
    """The PDF path must await document.fonts.ready (+ rAF) before printing so
    embedded @font-face are applied. We assert the page is driven through that
    wait by recording evaluate() calls on a fake page."""
    from backend.services import slide_pdf

    calls = []
    class _Page:
        def set_content(self, html, **kw): calls.append(("set_content", kw.get("wait_until")))
        def evaluate(self, expr): calls.append(("evaluate", expr))
        def pdf(self, **kw): calls.append(("pdf", None)); return b"%PDF-1.4 x"
    class _Browser:
        def new_page(self): return _Page()
        def close(self): pass
    class _PW:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        class chromium:
            @staticmethod
            def launch(args=None): return _Browser()
    monkeypatch.setattr(slide_pdf, "sync_playwright", lambda: _PW())

    pdf = slide_pdf.html_to_pdf("<html><body>x</body></html>")
    assert pdf[:5] == b"%PDF-"
    evals = " ".join(e for (k, e) in calls if k == "evaluate")
    assert "fonts.ready" in evals
    # fonts.ready awaited BEFORE pdf()
    order = [k for (k, _) in calls]
    assert order.index("evaluate") < order.index("pdf")


@pytest.mark.skipif(not _chromium_available(), reason="Chromium not installed in this env")
def test_html_to_pdf_returns_pdf_bytes():
    from backend.services.slide_pdf import html_to_pdf
    pdf = html_to_pdf("<!DOCTYPE html><html><body><h1>Hi</h1></body></html>")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 500
