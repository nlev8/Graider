"""VB8 #18 — SSO session: absolute lifetime cap + session-id rotation.

Before the fix, SSO sessions were sliding-expiry only (8h *idle* timeout,
refreshed on every request → effectively unbounded for an active attacker)
and SSO login did not rotate the server-side session id (session.clear()
empties the dict but reuses the same sid → session-fixation risk).

Fix:
- `establish_sso_session()` is the single SSO-login entry point: it clears the
  session, rotates the server-side sid (anti-fixation), marks it permanent,
  and stamps an absolute login timestamp (`sso_login_ts`).
- `check_auth` rejects any Clever/ClassLink session whose `sso_login_ts` is
  older than `SSO_ABSOLUTE_SESSION_LIFETIME`, clearing the stale session.
"""
import time

import backend.auth as auth


# ---------------------------------------------------------------------------
# establish_sso_session — rotation + absolute-cap stamp
# ---------------------------------------------------------------------------

def test_establish_sso_session_stamps_login_ts_and_permanent():
    from flask import Flask, session
    app = Flask(__name__)
    app.secret_key = "t"
    with app.test_request_context("/"):
        session["leftover"] = "stale"   # pre-existing data must be cleared
        auth.establish_sso_session()
        assert "leftover" not in session            # cleared
        assert session.permanent is True            # absolute-lifetime applies
        assert isinstance(session.get("sso_login_ts"), (int, float))
        assert session["sso_login_ts"] <= time.time() + 1


def test_establish_sso_session_rotates_server_side_sid():
    # Server-side sessions carry a `sid`. Rotation must assign a NEW sid so a
    # fixated pre-login cookie can no longer address the authenticated session.
    from flask import Flask, session
    app = Flask(__name__)
    app.secret_key = "t"
    with app.test_request_context("/"):
        # Simulate a server-side session object that has a sid attribute.
        try:
            session.sid = "attacker-fixated-sid"
        except AttributeError:
            # Default cookie session has no sid — rotation is a no-op for it
            # (no server-side fixation vector). Nothing to assert here.
            return
        auth.establish_sso_session()
        assert getattr(session, "sid", None) not in (None, "", "attacker-fixated-sid")


# ---------------------------------------------------------------------------
# check_auth — absolute cap enforcement on SSO sessions
# ---------------------------------------------------------------------------

def _init_app(monkeypatch):
    from flask import Flask
    monkeypatch.setenv("FLASK_ENV", "production")
    app = Flask(__name__)
    app.secret_key = "t"
    from backend.auth import init_auth
    init_auth(app)
    return app


def _run_hooks(app):
    for fn in app.before_request_funcs.get(None, []):
        rv = fn()
        if rv is not None:
            return rv
    return None


def test_clever_session_within_cap_is_allowed(monkeypatch):
    from flask import g
    app = _init_app(monkeypatch)
    with app.test_request_context("/api/x"):
        from flask import session
        session["clever_user"] = {"clever_id": "c1", "email": "t@x",
                                  "user_id": "uuid-1", "district": "d1"}
        session["sso_login_ts"] = time.time()  # fresh
        rv = _run_hooks(app)
        assert rv is None
        assert g.user_id == "uuid-1"
        assert g.auth_source == "clever"


def test_clever_session_past_absolute_cap_is_rejected(monkeypatch):
    app = _init_app(monkeypatch)
    with app.test_request_context("/api/x"):
        from flask import session
        session["clever_user"] = {"clever_id": "c1", "email": "t@x",
                                  "user_id": "uuid-1", "district": "d1"}
        # login was longer ago than the absolute cap → must be rejected
        session["sso_login_ts"] = time.time() - auth.SSO_ABSOLUTE_SESSION_LIFETIME - 60
        rv = _run_hooks(app)
        # Falls through to the bearer-required 401 (session no longer trusted).
        assert rv is not None
        body, status = rv
        assert status == 401
        assert "clever_user" not in session   # stale session cleared


def test_classlink_session_past_absolute_cap_is_rejected(monkeypatch):
    app = _init_app(monkeypatch)
    with app.test_request_context("/api/x"):
        from flask import session
        session["classlink_user"] = {"user_id": "uuid-2", "email": "t@x",
                                     "tenant_id": "t1"}
        session["sso_login_ts"] = time.time() - auth.SSO_ABSOLUTE_SESSION_LIFETIME - 60
        rv = _run_hooks(app)
        assert rv is not None
        _body, status = rv
        assert status == 401
        assert "classlink_user" not in session


def test_legacy_sso_session_without_ts_is_rejected(monkeypatch):
    # A session minted before this fix has no sso_login_ts. Fail safe: treat a
    # missing stamp as expired so the absolute cap cannot be bypassed by simply
    # omitting the field.
    app = _init_app(monkeypatch)
    with app.test_request_context("/api/x"):
        from flask import session
        session["clever_user"] = {"clever_id": "c1", "email": "t@x",
                                  "user_id": "uuid-1", "district": "d1"}
        # no sso_login_ts at all
        rv = _run_hooks(app)
        assert rv is not None
        _body, status = rv
        assert status == 401
        assert "clever_user" not in session
