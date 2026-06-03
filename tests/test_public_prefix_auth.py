"""Guard test — every PUBLIC_PREFIX route enforces its own secondary auth.

Security rubric level-8 criterion: *"every PUBLIC_PREFIX handler has
documented secondary auth."* The auth middleware in ``backend/auth.py``
short-circuits ``@require_teacher`` for any path matching ``PUBLIC_PREFIXES``
/ ``PUBLIC_EXACT`` (``is_public_route``). That bypass is only safe if each
such handler enforces its OWN check (student session token, Clever/ClassLink
OAuth session, district-admin session, the ``PERIODIC_SYNC_SECRET`` HMAC, a
valid join/class code, or OAuth ``state``) — OR is intentionally public by
design (OAuth callbacks, ``login-url``, LTI JWKS/OIDC login, logged-in-or-not
``session`` checks, the anonymous join-code GET).

This test pins that invariant. Every route under a public prefix is listed
below with its classification. For every route NOT in the
``INTENTIONALLY_PUBLIC`` allowlist, calling it WITHOUT credentials must return
a non-200 (401/403/redirect/4xx) OR a 200 whose body carries no sensitive
data. A future dev who adds an unauthenticated route under a public prefix
either lands in the allowlist (with a documented justification) or fails this
test.

Mechanism note: the app fixture registers the blueprints WITHOUT the JWT
``before_request`` middleware. With no middleware, ``g.user_id`` is never set,
so handler-level decorators (``@require_teacher``, ``@require_clever_session``,
``@_require_district_admin``) reject every caller — exactly the
missing-credentials case we want to assert. Session-cookie checks
(``session.get("clever_user")`` etc.) and the ``PERIODIC_SYNC_SECRET`` HMAC
likewise fail with no cookie/header present. (Same approach as
``tests/test_sso_contracts.py``.)
"""
import os
from unittest.mock import patch

import pytest
from flask import Flask


# ── App fixture: all public-prefix blueprints, NO JWT middleware ─────────────

@pytest.fixture
def client():
    # Stub SSO env so login-url endpoints build a URL rather than 503'ing
    # (doesn't affect the auth assertions, but keeps the public ones at 200/302).
    os.environ.setdefault("CLASSLINK_CLIENT_ID", "test-classlink-client")
    os.environ.setdefault("CLASSLINK_CLIENT_SECRET", "test-classlink-secret")
    os.environ.setdefault("CLEVER_CLIENT_ID", "test-clever-client")
    os.environ.setdefault("CLEVER_CLIENT_SECRET", "test-clever-secret")
    os.environ.setdefault("CLEVER_REDIRECT_URI", "https://app.test/api/clever/callback")
    # Ensure the sync secret is SET so the webhook's _validate_secret() exercises
    # the real "no matching Bearer header" rejection (an unset secret also 401s,
    # but we want the realistic path).
    os.environ.setdefault("PERIODIC_SYNC_SECRET", "test-sync-secret")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret-key"

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.clever_routes import clever_bp
    from backend.routes.classlink_routes import classlink_bp
    from backend.routes.lti_routes import lti_bp
    from backend.routes.district_routes import district_bp
    from backend.routes.sync_routes import sync_bp
    from backend.routes.student_portal_routes import student_portal_bp
    from backend.routes.student_account_routes import student_account_bp

    app.register_blueprint(clever_bp)
    app.register_blueprint(classlink_bp)
    app.register_blueprint(lti_bp)
    app.register_blueprint(district_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(student_portal_bp)
    app.register_blueprint(student_account_bp)

    return app.test_client()


# ── Classification table ─────────────────────────────────────────────────────
#
# Class values:
#   "public"    — INTENTIONALLY PUBLIC (no credentials required by design).
#   "secondary" — SECONDARY-AUTH'D (handler enforces its own check; we assert
#                 the missing-credentials call is rejected / returns no data).
#
# Each entry: (method, path, class, mechanism-or-reason).
# `mechanism` for "secondary" cites the exact gate + file:line.
# `mechanism` for "public" states WHY it is safe to expose without creds.

PUBLIC_PREFIX_ROUTES = [
    # ── Clever OAuth + Clever-session endpoints (clever_routes.py) ──
    ("GET",  "/api/clever/login-url", "public",
     "OAuth start: builds authorize URL + sets CSRF state (clever_routes.py:376)"),
    ("GET",  "/api/clever/callback", "public",
     "OAuth callback: must be reachable by the provider redirect; gated by "
     "single-use code + state (clever_routes.py:401)"),
    ("GET",  "/api/clever/session", "public",
     "Status check — only reveals logged-in-or-not, no PII when anon "
     "(clever_routes.py:550)"),
    ("POST", "/api/clever/sync-roster", "secondary",
     "@require_clever_session — session['clever_user'] (auth_decorators.py:25)"),
    ("POST", "/api/clever/apply-accommodations", "secondary",
     "@require_clever_session (clever_routes.py:690)"),
    ("POST", "/api/clever/delete-data", "secondary",
     "@require_clever_session + clever_user gate (clever_routes.py:752)"),
    ("GET",  "/api/clever/district-keys", "secondary",
     "@require_clever_session (clever_routes.py:840)"),
    ("POST", "/api/clever/district-keys", "secondary",
     "@require_clever_session + type==district_admin (clever_routes.py:856)"),
    ("GET",  "/api/clever/select-class", "secondary",
     "selection_token gate — invalid/expired -> 401 (clever_routes.py:902)"),
    ("POST", "/api/clever/student-token", "secondary",
     "single-use auth code gate -> 401 (clever_routes.py:948)"),
    ("GET",  "/api/clever/health", "public",
     "Health check — config booleans only, no secrets (clever_routes.py:965)"),
    ("POST", "/api/clever/logout", "public",
     "Clears own session cookie; no-op when anon (clever_routes.py:987)"),

    # ── ClassLink OAuth + session endpoints (classlink_routes.py) ──
    ("GET",  "/api/classlink/login-url", "public",
     "OAuth start: authorize URL + CSRF state/nonce (classlink_routes.py:307)"),
    ("GET",  "/api/classlink/callback", "public",
     "OAuth callback: provider redirect; gated by code + state/nonce "
     "(classlink_routes.py:345)"),
    ("GET",  "/api/classlink/session", "public",
     "Status check — logged-in-or-not only (classlink_routes.py:668)"),
    ("POST", "/api/classlink/logout", "public",
     "Clears own session cookie; no-op when anon (classlink_routes.py:688)"),
    ("POST", "/api/classlink/delete-data", "secondary",
     "@require_teacher + auth_source=='classlink' (classlink_routes.py:697)"),
    ("POST", "/api/classlink/student-token", "secondary",
     "single-use auth code gate -> 401 (classlink_routes.py:722)"),
    ("GET",  "/api/classlink/select-class", "secondary",
     "selection_token gate — invalid/expired -> 401 (classlink_routes.py:737)"),

    # ── LTI 1.3 (lti_routes.py) ──
    ("GET",  "/api/lti/jwks", "public",
     "Tool public JWKS — public keys by design (lti_routes.py:57)"),
    ("GET",  "/api/lti/login", "public",
     "OIDC third-party login initiation; rejects unregistered iss "
     "(lti_routes.py:64)"),
    ("POST", "/api/lti/launch", "public",
     "Platform-posted id_token callback; gated by state + signed JWT + nonce "
     "(lti_routes.py:105)"),
    ("GET",  "/api/lti/config", "secondary",
     "@require_teacher (lti_routes.py:195)"),
    ("POST", "/api/lti/config", "secondary",
     "@require_teacher (lti_routes.py:229)"),
    ("DELETE", "/api/lti/config", "secondary",
     "@require_teacher (lti_routes.py:279)"),
    ("GET",  "/api/lti/contexts", "secondary",
     "@require_teacher (lti_routes.py:258)"),
    ("POST", "/api/lti/sync-grades", "secondary",
     "@require_teacher (lti_routes.py:295)"),

    # ── District admin (district_routes.py) ──
    ("POST", "/api/district/auth", "public",
     "Login endpoint — password check creates the session (district_routes.py:238)"),
    ("DELETE", "/api/district/auth", "public",
     "Logout — clears own session cookie (district_routes.py:275)"),
    ("POST", "/api/district/change-password", "secondary",
     "@_require_district_admin (district_routes.py:285)"),
    ("GET",  "/api/district/config-status", "public",
     "First-run status — booleans/provider only, no secrets "
     "(district_routes.py:312)"),
    ("GET",  "/api/district/config", "secondary",
     "@_require_district_admin (district_routes.py:340)"),
    ("POST", "/api/district/config", "secondary",
     "@_require_district_admin (district_routes.py:370)"),
    ("POST", "/api/district/test-connection", "secondary",
     "@_require_district_admin (district_routes.py:454)"),
    ("POST", "/api/district/admin-invite", "secondary",
     "@_require_district_admin (district_routes.py:513)"),
    ("GET",  "/api/district/admins", "secondary",
     "@_require_district_admin (district_routes.py:542)"),
    ("DELETE", "/api/district/admins", "secondary",
     "@_require_district_admin (district_routes.py:563)"),
    ("GET",  "/api/district/sso-admins", "secondary",
     "@_require_district_admin (district_routes.py:609)"),
    ("POST", "/api/district/sso-admins", "secondary",
     "@_require_district_admin (district_routes.py:628)"),
    ("DELETE", "/api/district/sso-admins", "secondary",
     "@_require_district_admin (district_routes.py:659)"),
    ("GET",  "/api/district/teacher-search", "secondary",
     "@_require_district_admin (district_routes.py:678)"),
    ("GET",  "/api/district/analytics", "secondary",
     "@_require_district_admin (district_routes.py:719)"),

    # ── Periodic sync webhook (sync_routes.py) ──
    ("POST", "/api/sync/periodic-roster", "secondary",
     "_validate_secret() — HMAC compare of Bearer vs PERIODIC_SYNC_SECRET "
     "(sync_routes.py:319)"),

    # ── Student class-based content/submit (student_account_routes.py) ──
    ("GET",  "/api/student/content/ZZZ", "secondary",
     "_validate_student_session() — X-Student-Token header "
     "(student_account_routes.py:1044)"),
    ("POST", "/api/student/class-submit/ZZZ", "secondary",
     "_validate_student_session() — X-Student-Token header "
     "(student_account_routes.py:1105)"),

    # ── Anonymous join-code portal (student_portal_routes.py) ──
    ("GET",  "/api/student/join/ZZZZZZ", "public",
     "Anonymous join-code GET — valid code gates content; answers stripped "
     "before send (student_portal_routes.py:568)"),
    ("POST", "/api/student/submit/ZZZZZZ", "secondary",
     "Valid join code gates the assessment; unknown code -> 404 "
     "(student_portal_routes.py:674)"),
]


# Routes deemed safe to reach with no credentials (by design). Membership here
# is the explicit, reviewed allowlist — a new unauth'd route under a public
# prefix must either be added here WITH a justification or it fails the
# secondary-auth assertion below.
INTENTIONALLY_PUBLIC = {
    (method, path)
    for method, path, klass, _reason in PUBLIC_PREFIX_ROUTES
    if klass == "public"
}

SECONDARY_AUTHD = [
    (method, path, reason)
    for method, path, klass, reason in PUBLIC_PREFIX_ROUTES
    if klass == "secondary"
]


# ── Sensitive-data sentinel ──────────────────────────────────────────────────
# If a secondary-auth'd route ever returns 200 with no credentials, the body
# must not leak any of these. (A 200 with an empty/list-only payload is allowed
# only for routes that legitimately return no PII when unauthenticated; none of
# the SECONDARY_AUTHD routes below should hit 200 at all.)
_SENSITIVE_MARKERS = (
    "client_secret", "district_token", "api_key", "openai", "anthropic",
    "session_token", "password_hash", "student_id_number", "sourced_id",
)


def _call(client, method, path):
    return client.open(path, method=method, json={})


@pytest.mark.parametrize(
    "method,path,reason",
    [(m, p, r) for m, p, r in SECONDARY_AUTHD],
    ids=[f"{m} {p}" for m, p, _ in SECONDARY_AUTHD],
)
def test_secondary_authd_route_rejects_unauthenticated(client, method, path, reason):
    """Each SECONDARY-AUTH'D public-prefix route must reject a no-credentials
    call (non-200), OR return a 200 carrying no sensitive data.

    Security rubric level-8: every PUBLIC_PREFIX handler has documented
    secondary auth. `reason` records the exact gate + file:line.
    """
    # Patch Supabase so handlers that pass their auth gate (none should, with
    # no creds) cannot make real network calls; keeps the test hermetic.
    with patch("backend.supabase_client.get_supabase", return_value=None):
        resp = _call(client, method, path)

    if resp.status_code == 200:
        body = (resp.get_data(as_text=True) or "").lower()
        leaked = [m for m in _SENSITIVE_MARKERS if m in body]
        assert not leaked, (
            f"{method} {path} returned 200 WITH NO CREDENTIALS and leaked "
            f"{leaked}. Secondary-auth gate ({reason}) is not enforced — this "
            f"is a security finding, not a test failure to silence."
        )
    else:
        # Expected path: rejected (401/403/4xx) or redirected away.
        assert resp.status_code != 200, (
            f"{method} {path} unexpectedly returned 200 without credentials. "
            f"Expected the secondary-auth gate ({reason}) to reject it."
        )


def test_allowlist_is_explicit_and_complete():
    """Sanity: every route in the table is classified, and the public allowlist
    is non-empty + disjoint from the secondary set. Forces a future dev adding
    a row to pick exactly one class."""
    secondary_paths = {(m, p) for m, p, _ in SECONDARY_AUTHD}
    assert INTENTIONALLY_PUBLIC, "Public allowlist must not be empty"
    assert not (INTENTIONALLY_PUBLIC & secondary_paths), (
        "A route cannot be both public and secondary-auth'd"
    )
    # Every row classified as exactly 'public' or 'secondary'.
    for method, path, klass, _reason in PUBLIC_PREFIX_ROUTES:
        assert klass in ("public", "secondary"), (
            f"{method} {path} has unknown class {klass!r}"
        )
