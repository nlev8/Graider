"""Gap-fill unit tests for backend/routes/classlink_routes.py.

Audit MAJOR #4 sprint follow-up to PR #294. Companion to existing
test_classlink_oidc.py + test_classlink_sso.py + test_classlink_sso_
contract.py which cover the OIDC discovery, login URL, callback
happy/error paths, session, and logout. Targets the remaining 37
uncovered LOC (82% baseline → ~100%):

* _link_classlink_account — already-linked early return, no-sb/no-email
  early return, single-match link path, multi-match warn skip,
  outer except swallow + sentry capture
* _resolve_classlink_user_id — exception fallback to classlink:{id}
* _trigger_roster_sync._bg_sync — no OneRoster config skip; happy
  path that drives the inner asyncio loop + roster normalize +
  sync_roster_to_db; outer except swallow
* Callback gaps: no access_token, token-exchange exception, iat
  in the future, iat >24h stale, userinfo non-200, userinfo
  exception
"""
from __future__ import annotations

import os
import time
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from tests.conftest_classlink import make_id_token


def _make_app():
    """Mirror of the helper in test_classlink_sso.py (private import)."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['RATELIMIT_ENABLED'] = False

    os.environ['CLASSLINK_CLIENT_ID'] = 'test-client-id'
    os.environ['CLASSLINK_CLIENT_SECRET'] = 'test-client-secret'

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.classlink_routes import classlink_bp
    app.register_blueprint(classlink_bp)
    return app


def _make_rsa_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


def _mock_jwks_client(public_key):
    mock_jwks = MagicMock()
    mock_jwks.get_signing_key_from_jwt.return_value = MagicMock(key=public_key)
    return mock_jwks


def _mock_oidc_config():
    return {
        "issuer": "https://launchpad.classlink.com",
        "jwks_uri": "https://launchpad.classlink.com/oauth2/v2/keys",
    }


# ──────────────────────────────────────────────────────────────────
# _link_classlink_account
# ──────────────────────────────────────────────────────────────────


class TestLinkClasslinkAccount:
    def test_already_linked_returns_early(self):
        # links dict already has classlink_id → no-op
        existing_links = {"cl-123": "teacher-uuid-1"}
        with patch(
            "backend.storage.load",
            return_value=existing_links,
        ) as load_mock, patch(
            "backend.storage.save",
        ) as save_mock:
            from backend.routes.classlink_routes import _link_classlink_account
            _link_classlink_account("cl-123", "u@x.com")
        # Save NOT called because we returned early
        save_mock.assert_not_called()

    def test_no_supabase_returns_early(self):
        with patch(
            "backend.storage.load", return_value={},
        ), patch(
            "backend.storage.save",
        ) as save_mock, patch(
            "backend.supabase_client.get_supabase",
            return_value=None,
        ):
            from backend.routes.classlink_routes import _link_classlink_account
            _link_classlink_account("cl-new", "u@x.com")
        save_mock.assert_not_called()

    def test_no_email_returns_early(self):
        sb = MagicMock()
        with patch(
            "backend.storage.load", return_value={},
        ), patch(
            "backend.storage.save",
        ) as save_mock, patch(
            "backend.supabase_client.get_supabase",
            return_value=sb,
        ):
            from backend.routes.classlink_routes import _link_classlink_account
            _link_classlink_account("cl-new", "")
        save_mock.assert_not_called()

    def test_single_match_creates_link(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"teacher_id": "teacher-A"}],
        )
        save_mock = MagicMock()

        # storage.load: first call for classlink_links → empty dict;
        # subsequent calls for `settings` → return matching email config.
        load_count = {"n": 0}

        def load_side_effect(key, tid):
            load_count["n"] += 1
            if key == "classlink_links":
                return {}
            if key == "settings":
                return {"email": "match@x.com"}
            return None

        with patch(
            "backend.storage.load", side_effect=load_side_effect,
        ), patch(
            "backend.storage.save", save_mock,
        ), patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ):
            from backend.routes.classlink_routes import _link_classlink_account
            _link_classlink_account("cl-newest", "MATCH@x.com")
        # storage.save called with the link dict
        save_mock.assert_called_once()
        args = save_mock.call_args.args
        assert args[0] == "classlink_links"
        assert args[1] == {"cl-newest": "teacher-A"}
        assert args[2] == "system"

    def test_multi_match_logs_warning_no_link(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"teacher_id": "teacher-A"},
                {"teacher_id": "teacher-B"},
            ],
        )
        save_mock = MagicMock()

        def load_side_effect(key, tid):
            if key == "classlink_links":
                return {}
            if key == "settings":
                return {"email": "ambiguous@x.com"}
            return None

        with patch(
            "backend.storage.load", side_effect=load_side_effect,
        ), patch(
            "backend.storage.save", save_mock,
        ), patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ):
            from backend.routes.classlink_routes import _link_classlink_account
            _link_classlink_account("cl-amb", "ambiguous@x.com")
        # No link saved (ambiguous → skip)
        save_mock.assert_not_called()

    def test_outer_exception_swallowed_with_sentry(self):
        # Force `from backend.storage import load as storage_load` ImportError-
        # adjacent failure by making load raise. The outer try/except logs +
        # sentry-captures.
        with patch(
            "backend.storage.load",
            side_effect=RuntimeError("storage down"),
        ), patch(
            "backend.routes.classlink_routes.sentry_sdk.capture_exception",
        ) as sentry_mock:
            from backend.routes.classlink_routes import _link_classlink_account
            # Must not raise
            _link_classlink_account("cl-x", "u@x.com")
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# _resolve_classlink_user_id
# ──────────────────────────────────────────────────────────────────


class TestResolveClasslinkUserId:
    def test_linked_returns_supabase_uuid(self):
        with patch(
            "backend.storage.load",
            return_value={"cl-123": "teacher-uuid-1"},
        ):
            from backend.routes.classlink_routes import _resolve_classlink_user_id
            assert _resolve_classlink_user_id("cl-123") == "teacher-uuid-1"

    def test_unlinked_returns_classlink_prefix(self):
        with patch(
            "backend.storage.load",
            return_value={},
        ):
            from backend.routes.classlink_routes import _resolve_classlink_user_id
            assert _resolve_classlink_user_id("cl-X") == "classlink:cl-X"

    def test_storage_exception_falls_back_to_prefix(self):
        with patch(
            "backend.storage.load",
            side_effect=RuntimeError("storage down"),
        ):
            from backend.routes.classlink_routes import _resolve_classlink_user_id
            # Falls back to classlink:{id} on exception
            assert _resolve_classlink_user_id("cl-fallback") == "classlink:cl-fallback"


# ──────────────────────────────────────────────────────────────────
# _trigger_roster_sync (background sync)
# ──────────────────────────────────────────────────────────────────


class TestTriggerRosterSync:
    def test_no_oneroster_config_returns_early(self):
        # Patch threading.Thread to run synchronously
        from backend.routes import classlink_routes as mod

        captured = {}

        class SyncThread:
            def __init__(self, target=None, daemon=None, **kw):
                self.target = target

            def start(self):
                self.target()  # Run inline so we can assert

        with patch("threading.Thread", SyncThread):
            with patch(
                "backend.oneroster.get_oneroster_config",
                return_value={},  # no base_url
            ), patch(
                "backend.oneroster.OneRosterClient",
            ) as client_mock:
                mod._trigger_roster_sync("teacher-1", "tenant-x")
            # OneRosterClient never instantiated
            client_mock.assert_not_called()

    def test_happy_path_drives_sync(self):
        from backend.routes import classlink_routes as mod

        class SyncThread:
            def __init__(self, target=None, daemon=None, **kw):
                self.target = target

            def start(self):
                self.target()

        # Build a fake OneRosterClient + fake roster + fake sync_to_db
        config = {
            "base_url": "https://x.example/oneroster",
            "client_id": "ci",
            "client_secret": "cs",
            "token_url": "https://x.example/token",
            "school_id": "sch-1",
            "teacher_sourced_id": "ts-1",
        }

        # OneRosterClient.fetch_roster is awaited on a fresh event loop
        # → needs to be an awaitable. Build via async-stub function.
        async def fake_fetch(school_id=None, teacher_sourced_id=None):
            return {"raw": "roster"}

        fake_client = MagicMock()
        fake_client.fetch_roster = fake_fetch

        normalize_return = (
            [{"id": "c1"}],   # classes
            [{"id": "s1"}],   # students
            [{"class_external_id": "c1",
              "student_external_id": "s1"}],  # enrollments
            None,
        )
        sync_mock = MagicMock()

        with patch("threading.Thread", SyncThread):
            with patch(
                "backend.oneroster.get_oneroster_config",
                return_value=config,
            ), patch(
                "backend.oneroster.OneRosterClient",
                return_value=fake_client,
            ), patch(
                "backend.oneroster.normalize_roster",
                return_value=normalize_return,
            ), patch(
                "backend.roster_sync.sync_roster_to_db", sync_mock,
            ):
                mod._trigger_roster_sync("teacher-2", "tenant-y")

        # sync_roster_to_db called with the tuple-shaped enrollments
        sync_mock.assert_called_once()
        args = sync_mock.call_args.args
        assert args[0] == [{"id": "c1"}]               # classes
        assert args[1] == [{"id": "s1"}]               # students_norm
        assert args[2] == [("c1", "s1")]               # enrollment tuples
        assert args[3] == "teacher-2"                  # teacher_id
        kwargs = sync_mock.call_args.kwargs
        assert kwargs == {"provider": "classlink"}

    def test_outer_exception_swallowed_with_sentry(self):
        from backend.routes import classlink_routes as mod

        class SyncThread:
            def __init__(self, target=None, daemon=None, **kw):
                self.target = target

            def start(self):
                self.target()

        with patch("threading.Thread", SyncThread):
            with patch(
                "backend.oneroster.get_oneroster_config",
                side_effect=RuntimeError("config dead"),
            ), patch(
                "backend.routes.classlink_routes.sentry_sdk.capture_exception",
            ) as sentry_mock:
                # Must not raise
                mod._trigger_roster_sync("teacher-3", "tenant-z")
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# Callback edge cases
# ──────────────────────────────────────────────────────────────────


class TestCallbackEdgeCases:
    def _stub_token_response(self, *, has_access=True, has_id=True):
        m = MagicMock()
        m.status_code = 200
        body = {}
        if has_access:
            body["access_token"] = "test-access"
        if has_id:
            body["id_token"] = "test-id-token"
        m.json.return_value = body
        return m

    def test_no_access_token_redirects_to_no_token(self):
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "ok-state"
            with patch(
                "backend.routes.classlink_routes.requests.post",
                return_value=self._stub_token_response(has_access=False),
            ):
                resp = client.get(
                    "/api/classlink/callback?code=abc&state=ok-state",
                )
        assert resp.status_code == 302
        assert "classlink_error=no_token" in resp.location

    def test_token_exchange_exception_redirects_to_token_error(self):
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "ok-state"
            with patch(
                "backend.routes.classlink_routes.requests.post",
                side_effect=RuntimeError("network down"),
            ):
                resp = client.get(
                    "/api/classlink/callback?code=abc&state=ok-state",
                )
        assert resp.status_code == 302
        assert "classlink_error=token_error" in resp.location

    def test_iat_too_far_in_future_rejected(self):
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # PyJWT's `verify_iat=True` would reject iat > now+leeway BEFORE
        # the route's own iat-sanity check fires. Workaround: build a
        # token with current iat (pyjwt accepts) and patch `time.time`
        # ONLY on the route module so the route sees iat as 1000 sec in
        # the future. Lines 336-338 then fire as intended.
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-1",
            email="u@x.com",
            given_name="J",
            family_name="D",
            role="teacher",
        )
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "tok", "id_token": id_token,
        }

        # Make the route think 1000 seconds have passed BEFORE the iat —
        # i.e. iat (real now) appears 1000 sec in the future to the route.
        past_time = int(time.time()) - 1000

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "ok-state"
            with patch(
                "backend.routes.classlink_routes.requests.post",
                return_value=token_resp,
            ), patch(
                "backend.routes.classlink_routes.get_classlink_oidc_config",
                return_value=_mock_oidc_config(),
            ), patch(
                "backend.routes.classlink_routes.get_classlink_jwks_client",
                return_value=_mock_jwks_client(pub),
            ), patch(
                "backend.routes.classlink_routes.time.time",
                return_value=past_time,
            ):
                resp = client.get(
                    "/api/classlink/callback?code=abc&state=ok-state",
                )
        # Future-iat → oidc_invalid redirect
        assert resp.status_code == 302
        assert "classlink_error=oidc_invalid" in resp.location

    def test_iat_too_old_rejected(self):
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # iat 25h in the past → > 24h stale. exp still in the future so
        # pyjwt's signature/expiration validation passes and we reach the
        # iat-stale sanity check.
        stale_iat = int(time.time()) - 86400 - 3600
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-1",
            email="u@x.com",
            given_name="J",
            family_name="D",
            role="teacher",
            extra_claims={
                "iat": stale_iat,
                "nbf": stale_iat,
                "exp": int(time.time()) + 3600,
            },
        )
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "tok", "id_token": id_token,
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "ok-state"
            with patch(
                "backend.routes.classlink_routes.requests.post",
                return_value=token_resp,
            ), patch(
                "backend.routes.classlink_routes.get_classlink_oidc_config",
                return_value=_mock_oidc_config(),
            ), patch(
                "backend.routes.classlink_routes.get_classlink_jwks_client",
                return_value=_mock_jwks_client(pub),
            ):
                resp = client.get(
                    "/api/classlink/callback?code=abc&state=ok-state",
                )
        assert resp.status_code == 302
        assert "classlink_error=oidc_invalid" in resp.location

    def _stub_id_token_validation_pass(
        self, role="teacher", email="u@x.com",
    ):
        """Build a valid id_token + matching mock helpers."""
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-1",
            email=email,
            given_name="J",
            family_name="D",
            role=role,
        )
        return id_token, pub

    def test_userinfo_non_200_redirects(self):
        app = _make_app()
        id_token, pub = self._stub_id_token_validation_pass()
        token_resp = MagicMock(); token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "tok", "id_token": id_token,
        }
        userinfo_resp = MagicMock(); userinfo_resp.status_code = 503
        userinfo_resp.json.return_value = {}

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "ok-state"
            with patch(
                "backend.routes.classlink_routes.requests.post",
                return_value=token_resp,
            ), patch(
                "backend.routes.classlink_routes.requests.get",
                return_value=userinfo_resp,
            ), patch(
                "backend.routes.classlink_routes.get_classlink_oidc_config",
                return_value=_mock_oidc_config(),
            ), patch(
                "backend.routes.classlink_routes.get_classlink_jwks_client",
                return_value=_mock_jwks_client(pub),
            ):
                resp = client.get(
                    "/api/classlink/callback?code=abc&state=ok-state",
                )
        assert resp.status_code == 302
        assert "classlink_error=userinfo_failed" in resp.location

    def test_userinfo_exception_redirects(self):
        app = _make_app()
        id_token, pub = self._stub_id_token_validation_pass()
        token_resp = MagicMock(); token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "tok", "id_token": id_token,
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "ok-state"
            with patch(
                "backend.routes.classlink_routes.requests.post",
                return_value=token_resp,
            ), patch(
                "backend.routes.classlink_routes.requests.get",
                side_effect=RuntimeError("network down"),
            ), patch(
                "backend.routes.classlink_routes.get_classlink_oidc_config",
                return_value=_mock_oidc_config(),
            ), patch(
                "backend.routes.classlink_routes.get_classlink_jwks_client",
                return_value=_mock_jwks_client(pub),
            ):
                resp = client.get(
                    "/api/classlink/callback?code=abc&state=ok-state",
                )
        assert resp.status_code == 302
        assert "classlink_error=userinfo_error" in resp.location


# ──────────────────────────────────────────────────────────────────
# _classlink_guid
# ──────────────────────────────────────────────────────────────────


class TestClasslinkGuid:
    def test_assembles_prefixed_composite(self):
        from backend.routes.classlink_routes import _classlink_guid
        assert _classlink_guid("2284", "abc") == "classlink:2284:abc"

    def test_encodes_colon_in_components_to_prevent_collision(self):
        from backend.routes.classlink_routes import _classlink_guid
        # ("a:b","c") and ("a","b:c") must NOT collide
        assert _classlink_guid("a:b", "c") == "classlink:a%3Ab:c"
        assert _classlink_guid("a", "b:c") == "classlink:a:b%3Ac"
        assert _classlink_guid("a:b", "c") != _classlink_guid("a", "b:c")

    def test_returns_none_on_empty_component(self):
        from backend.routes.classlink_routes import _classlink_guid
        assert _classlink_guid("", "abc") is None
        assert _classlink_guid("2284", "") is None
        assert _classlink_guid("  ", "abc") is None

    def test_returns_none_on_none_component(self):
        from backend.routes.classlink_routes import _classlink_guid
        assert _classlink_guid(None, "abc") is None
        assert _classlink_guid("2284", None) is None


# ──────────────────────────────────────────────────────────────────
# _extract_person_id
# ──────────────────────────────────────────────────────────────────


class TestExtractPersonId:
    def test_prefers_sourcedid(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"SourcedId": "s1", "UserId": "u1"}) == "s1"

    def test_accepts_lowercase_sourcedid(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"sourcedId": "s2"}) == "s2"

    def test_uppercase_sourcedid_wins_over_lowercase(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"SourcedId": "s1", "sourcedId": "s-lower"}) == "s1"

    def test_falls_back_to_userid_and_warns(self, caplog):
        import logging
        from backend.routes.classlink_routes import _extract_person_id
        with caplog.at_level(logging.WARNING, logger="backend.routes.classlink_routes"):
            result = _extract_person_id({"UserId": "u1"})
        assert result == "u1"
        # The UserId fallback must NOT be silent (documented contract).
        assert "UserId" in caplog.text

    def test_none_when_no_person_field(self):
        from backend.routes.classlink_routes import _extract_person_id
        assert _extract_person_id({"Email": "x@y.z"}) is None
