"""The 404 handler must NOT mask missing /assets/* requests.

Root cause (2026-06-03 debug): the SPA 404 handler served index.html (HTTP 200)
for every non-/api 404, INCLUDING missing /assets/<hash>.js. When a deploy
deletes old hashed bundles/chunks, a stale browser requesting one got HTML
served as JavaScript instead of an honest 404 — masking the stale frontend and
breaking lazy-chunk loads silently. A missing asset must 404 so the client can
detect a stale build and recover. True SPA routes still fall back to index.html.
"""
import importlib
import sys


def _app():
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        return backend_app
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_missing_asset_returns_404_not_index_html():
    resp = _app().app.test_client().get("/assets/index-deadbeef0000.js")
    assert resp.status_code == 404, "missing /assets/* must 404, not serve index.html"
    assert '<div id="root"' not in resp.get_data(as_text=True), \
        "must not serve the SPA index.html for a missing asset"


def test_missing_api_path_still_returns_json_404():
    resp = _app().app.test_client().get("/api/does-not-exist-xyz")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Not found"}


def test_spa_route_still_falls_back_to_index_html(monkeypatch):
    backend_app = _app()
    # Patch the module's send_from_directory so the test doesn't depend on a
    # built backend/static/index.html existing in the CI runner.
    monkeypatch.setattr(
        backend_app, "send_from_directory",
        lambda folder, name: ("SPA_INDEX_HTML", 200),
    )
    resp = backend_app.app.test_client().get("/district")
    assert resp.status_code == 200
    assert "SPA_INDEX_HTML" in resp.get_data(as_text=True), \
        "non-asset SPA routes must still fall back to index.html"
