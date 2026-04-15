"""Boot + route-snapshot smoke tests for backend/app.py.

Phase 3a safety net: pin that the app still boots, has the expected
minimum URL rules, and no SIS-critical endpoint silently changed path
or methods across the refactor.
"""
import importlib
import sys


def _import_app():
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        return backend_app
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


def test_app_module_imports_cleanly():
    backend_app = _import_app()
    assert hasattr(backend_app, "app"), "Module must expose a Flask `app` instance"


def test_app_registers_expected_route_count():
    backend_app = _import_app()
    rule_count = len(backend_app.app.url_map._rules)
    assert rule_count >= 250, f"Expected >= 250 rules, got {rule_count}"


def test_app_exposes_init_app_initializer():
    backend_app = _import_app()
    assert callable(backend_app.init_app), "init_app(app) must be callable"


def test_app_route_snapshot_has_no_silent_drift():
    """Pin SIS-critical endpoint → (rule, methods). Drift = fail."""
    backend_app = _import_app()
    snapshot = {
        rule.endpoint: (rule.rule, sorted(rule.methods - {"HEAD", "OPTIONS"}))
        for rule in backend_app.app.url_map.iter_rules()
    }
    required = {
        "clever.clever_login_url":       ("/api/clever/login-url",       ["GET"]),
        "clever.clever_callback":        ("/api/clever/callback",        ["GET"]),
        "clever.clever_session_check":   ("/api/clever/session",         ["GET"]),
        "classlink.classlink_login_url": ("/api/classlink/login-url",    ["GET"]),
        "classlink.classlink_callback":  ("/api/classlink/callback",     ["GET"]),
        "oneroster.get_config":          ("/api/oneroster/config",       ["GET"]),
        "oneroster.save_config":         ("/api/oneroster/config",       ["POST"]),
    }
    missing = {k: v for k, v in required.items() if k not in snapshot}
    mismatched = {
        k: (snapshot[k], v)
        for k, v in required.items()
        if k in snapshot and snapshot[k] != v
    }
    assert not missing, f"SIS-critical endpoints missing from snapshot: {missing}"
    assert not mismatched, f"SIS-critical endpoint path/method drift: {mismatched}"
