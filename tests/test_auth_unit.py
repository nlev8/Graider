"""
Unit + integration tests for backend/auth.py.

Closes the test-writing half of audit MAJOR #4 of GH issue #217 for the
auth module: prior to this file, backend/auth.py was at 37% line
coverage. Existing tests covered only the `g.supabase_jwt` invariant
(test_auth_supabase_jwt_attr.py); this file expands to:

- `is_public_route` (PUBLIC_EXACT + PUBLIC_PREFIXES branches)
- `get_jwt_secret` env var fallback
- `_get_jwks_client` lazy init
- `validate_token` for ES256 (JWKS) + HS256 fallback + expired/invalid
- `load_clever_links` / `save_clever_link` / `resolve_clever_user_id`
  (storage backed + legacy file fallback)
- `init_auth` before_request branches:
  * dev + localhost + no Bearer → header/env user_id
  * Clever session
  * ClassLink session
  * Non-API path passthrough
  * Public API path passthrough
  * Bearer + invalid token → 401
  * Bearer + unapproved user → 403 NOT_APPROVED
  * Bearer + unapproved JWT but Supabase admin says approved → pass

Each test isolates env vars and module globals so cross-test leakage
doesn't mask coverage.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import jwt
import pytest
from flask import Flask, g, session


# ──────────────────────────────────────────────────────────────────
# is_public_route — pure function, no I/O
# ──────────────────────────────────────────────────────────────────


class TestIsPublicRoute:
    def test_exact_match_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/status') is True
        assert is_public_route('/api/stripe/webhook') is True
        assert is_public_route('/api/student/login') is True

    def test_prefix_match_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/student/join/ABC123') is True
        assert is_public_route('/api/clever/callback?code=x') is True
        assert is_public_route('/api/classlink/login') is True
        assert is_public_route('/api/lti/launch') is True
        assert is_public_route('/api/sync/periodic-roster') is True
        assert is_public_route('/api/student/content/some-id') is True

    def test_protected_route_is_not_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/settings/load') is False
        assert is_public_route('/api/admin/overview') is False
        assert is_public_route('/api/grade') is False

    def test_partial_prefix_does_not_match(self):
        from backend.auth import is_public_route
        # `/api/clever-shadow` is NOT under `/api/clever/`
        assert is_public_route('/api/clever-shadow') is False


# ──────────────────────────────────────────────────────────────────
# get_jwt_secret — env var read with raise
# ──────────────────────────────────────────────────────────────────


class TestGetJwtSecret:
    def test_returns_secret_when_set(self, monkeypatch):
        monkeypatch.setenv('SUPABASE_JWT_SECRET', 'my-test-secret')
        from backend.auth import get_jwt_secret
        assert get_jwt_secret() == 'my-test-secret'

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv('SUPABASE_JWT_SECRET', raising=False)
        from backend.auth import get_jwt_secret
        with pytest.raises(RuntimeError, match='SUPABASE_JWT_SECRET'):
            get_jwt_secret()


# ──────────────────────────────────────────────────────────────────
# _get_jwks_client — lazy init
# ──────────────────────────────────────────────────────────────────


class TestGetJwksClient:
    def test_returns_none_when_supabase_url_unset(self, monkeypatch):
        # Reset the module global so the lazy init re-evaluates env.
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.delenv('SUPABASE_URL', raising=False)
        assert auth_mod._get_jwks_client() is None

    def test_caches_client_after_first_call(self, monkeypatch):
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')

        with patch.object(auth_mod, 'PyJWKClient') as mock_pyjwk:
            mock_instance = MagicMock()
            mock_pyjwk.return_value = mock_instance
            first = auth_mod._get_jwks_client()
            second = auth_mod._get_jwks_client()
            assert first is mock_instance
            assert second is mock_instance
            # Constructor called exactly once — second call hit the cache
            assert mock_pyjwk.call_count == 1


# ──────────────────────────────────────────────────────────────────
# validate_token — ES256 + HS256 + error paths
# ──────────────────────────────────────────────────────────────────


class TestValidateToken:
    def test_es256_success_returns_payload(self, monkeypatch):
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')

        fake_payload = {"sub": "user-1", "email": "a@b.com"}
        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = 'fake-public-key'
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch.object(auth_mod, '_get_jwks_client', return_value=mock_jwks), \
             patch.object(auth_mod.jwt, 'decode', return_value=fake_payload) as mock_decode:
            result = auth_mod.validate_token('fake.token.here')
            assert result == fake_payload
            # Verify the ES256 path was used
            call_kwargs = mock_decode.call_args.kwargs
            assert call_kwargs.get('algorithms') == ['ES256']
            assert call_kwargs.get('audience') == 'authenticated'

    def test_es256_expired_returns_none_no_hs256_fallback(self, monkeypatch):
        # ExpiredSignatureError on ES256 → return None immediately.
        # We do NOT fall back to HS256 because the token is genuinely
        # expired regardless of the verifying key.
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')

        mock_jwks = MagicMock()
        mock_jwks.get_signing_key_from_jwt.return_value = MagicMock(key='k')

        with patch.object(auth_mod, '_get_jwks_client', return_value=mock_jwks), \
             patch.object(auth_mod.jwt, 'decode',
                          side_effect=jwt.ExpiredSignatureError) as mock_decode:
            result = auth_mod.validate_token('expired.token.here')
            assert result is None
            # Codex round-1 MINOR fold: ExpiredSignatureError on ES256
            # MUST NOT fall through to HS256. A regression that retried
            # HS256 and also got expired would still return None — only
            # the call_count assertion catches that case.
            assert mock_decode.call_count == 1

    def test_es256_invalid_falls_back_to_hs256_success(self, monkeypatch):
        # If ES256 raises a non-expired InvalidTokenError, we try HS256.
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
        monkeypatch.setenv('SUPABASE_JWT_SECRET', 'hs256-secret')

        fake_payload = {"sub": "user-2", "email": "h@s.com"}
        mock_jwks = MagicMock()
        mock_jwks.get_signing_key_from_jwt.return_value = MagicMock(key='k')

        # First call raises InvalidTokenError (ES256), second returns payload.
        with patch.object(auth_mod, '_get_jwks_client', return_value=mock_jwks), \
             patch.object(auth_mod.jwt, 'decode',
                          side_effect=[jwt.InvalidTokenError("bad sig"), fake_payload]) as mock_decode:
            result = auth_mod.validate_token('fake.token.here')
            assert result == fake_payload
            # Two decode calls: ES256 attempt + HS256 fallback
            assert mock_decode.call_count == 2
            # Second call uses HS256
            second_kwargs = mock_decode.call_args_list[1].kwargs
            assert second_kwargs.get('algorithms') == ['HS256']

    def test_hs256_only_when_no_jwks(self, monkeypatch):
        # No SUPABASE_URL → JWKS client is None → straight to HS256.
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.delenv('SUPABASE_URL', raising=False)
        monkeypatch.setenv('SUPABASE_JWT_SECRET', 'hs256-secret')

        fake_payload = {"sub": "user-3"}
        with patch.object(auth_mod.jwt, 'decode', return_value=fake_payload) as mock_decode:
            result = auth_mod.validate_token('any.token.here')
            assert result == fake_payload
            # Single decode call, HS256
            assert mock_decode.call_count == 1
            assert mock_decode.call_args.kwargs.get('algorithms') == ['HS256']

    def test_hs256_invalid_returns_none(self, monkeypatch):
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.delenv('SUPABASE_URL', raising=False)
        monkeypatch.setenv('SUPABASE_JWT_SECRET', 'hs256-secret')

        with patch.object(auth_mod.jwt, 'decode',
                          side_effect=jwt.InvalidTokenError("bad")):
            assert auth_mod.validate_token('garbage') is None

    def test_hs256_expired_returns_none(self, monkeypatch):
        import backend.auth as auth_mod
        monkeypatch.setattr(auth_mod, '_jwks_client', None)
        monkeypatch.delenv('SUPABASE_URL', raising=False)
        monkeypatch.setenv('SUPABASE_JWT_SECRET', 'hs256-secret')

        with patch.object(auth_mod.jwt, 'decode',
                          side_effect=jwt.ExpiredSignatureError):
            assert auth_mod.validate_token('expired') is None


# ──────────────────────────────────────────────────────────────────
# Clever links — load / save / resolve
# ──────────────────────────────────────────────────────────────────


class TestCleverLinks:
    def test_load_returns_dict_from_storage(self):
        # Mock storage layer; verify the dict is built from list_keys + load.
        with patch('backend.storage.list_keys', return_value=['clever_link:abc', 'clever_link:def']), \
             patch('backend.storage.load',
                   side_effect=lambda key, ns: (
                       {'supabase_user_id': 'sb-1'} if 'abc' in key
                       else {'supabase_user_id': 'sb-2'}
                   )):
            from backend.auth import load_clever_links
            links = load_clever_links()
            assert links == {'abc': 'sb-1', 'def': 'sb-2'}

    def test_load_returns_empty_when_no_keys(self):
        with patch('backend.storage.list_keys', return_value=[]):
            from backend.auth import load_clever_links
            assert load_clever_links() == {}

    def test_load_falls_back_to_legacy_file_on_storage_error(self, tmp_path, monkeypatch):
        # Storage raises → falls back to ~/.graider_data/clever_links.json
        import backend.auth as auth_mod
        legacy_path = tmp_path / "clever_links.json"
        legacy_path.write_text(json.dumps({'legacy-id': 'sb-legacy'}))
        monkeypatch.setattr(
            'os.path.expanduser',
            lambda p: str(legacy_path) if 'graider_data' in p else p,
        )
        with patch('backend.storage.list_keys',
                   side_effect=Exception("storage down")):
            assert auth_mod.load_clever_links() == {'legacy-id': 'sb-legacy'}

    def test_load_returns_empty_on_legacy_file_missing(self, tmp_path, monkeypatch):
        # Storage raises AND legacy file missing → return {}.
        import backend.auth as auth_mod
        missing = tmp_path / "absent.json"
        monkeypatch.setattr(
            'os.path.expanduser',
            lambda p: str(missing) if 'graider_data' in p else p,
        )
        with patch('backend.storage.list_keys',
                   side_effect=Exception("storage down")):
            assert auth_mod.load_clever_links() == {}

    def test_save_writes_to_storage(self):
        from backend.auth import save_clever_link
        with patch('backend.storage.save') as mock_save:
            save_clever_link('clever-1', 'sb-uuid-1')
            mock_save.assert_called_once_with(
                'clever_link:clever-1',
                {'supabase_user_id': 'sb-uuid-1'},
                'system',
            )

    def test_save_falls_back_to_legacy_file_on_storage_error(self, tmp_path, monkeypatch):
        import backend.auth as auth_mod
        legacy_path = tmp_path / "clever_links.json"
        legacy_path.write_text(json.dumps({'old': 'sb-old'}))
        monkeypatch.setattr(
            'os.path.expanduser',
            lambda p: str(legacy_path) if 'graider_data' in p else p,
        )
        with patch('backend.storage.save', side_effect=Exception("down")), \
             patch('backend.storage.list_keys', side_effect=Exception("down")):
            auth_mod.save_clever_link('new', 'sb-new')
        # Legacy file now contains both keys (legacy persisted via load → save)
        contents = json.loads(legacy_path.read_text())
        assert contents['new'] == 'sb-new'
        assert contents['old'] == 'sb-old'

    def test_resolve_returns_linked_user_id(self):
        with patch('backend.auth.load_clever_links',
                   return_value={'clever-1': 'sb-uuid-1'}):
            from backend.auth import resolve_clever_user_id
            assert resolve_clever_user_id('clever-1') == 'sb-uuid-1'

    def test_resolve_returns_clever_prefixed_id_when_no_link(self):
        with patch('backend.auth.load_clever_links', return_value={}):
            from backend.auth import resolve_clever_user_id
            # No link → fall back to clever:{id} pseudo-user
            assert resolve_clever_user_id('clever-9') == 'clever:clever-9'


# ──────────────────────────────────────────────────────────────────
# init_auth — before_request branches via Flask test client
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def auth_app(monkeypatch):
    """Minimal Flask app with init_auth hook attached + a protected route."""
    monkeypatch.setenv('SUPABASE_JWT_SECRET', 'x' * 48)
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    # backend/extensions.py raises if FLASK_ENV is non-dev and REDIS_URL
    # is unset. Some lazy imports inside check_auth (classlink_routes)
    # trigger that cascade when we run with FLASK_ENV=production for
    # SSO branch coverage. Stub REDIS_URL so the import succeeds.
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    from backend.auth import init_auth

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-' + 'x' * 50

    init_auth(app)

    @app.route('/api/protected')
    def protected():
        return {'user_id': getattr(g, 'user_id', None),
                'email': getattr(g, 'user_email', None),
                'auth_source': getattr(g, 'auth_source', None)}, 200

    @app.route('/static-page')
    def static_page():
        return 'static', 200

    @app.route('/api/auth/approval-status')
    def approval_status():
        # Tested specifically — this endpoint must allow unapproved users
        # so they can see their pending status.
        return {'user_id': getattr(g, 'user_id', None)}, 200

    return app


class TestInitAuthDevPath:
    def test_dev_localhost_no_bearer_uses_test_header(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'development')
        client = auth_app.test_client()
        resp = client.get('/api/protected', headers={
            'X-Test-Teacher-Id': 'teacher-7',
            'Host': 'localhost',
        })
        assert resp.status_code == 200
        assert resp.get_json()['user_id'] == 'teacher-7'

    def test_dev_localhost_no_bearer_uses_dev_user_env(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'development')
        monkeypatch.setenv('DEV_USER_ID', 'dev-default')
        monkeypatch.setenv('DEV_EMAIL', 'dev@local')
        client = auth_app.test_client()
        resp = client.get('/api/protected',
                          headers={'Host': 'localhost'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['user_id'] == 'dev-default'
        assert body['email'] == 'dev@local'

    def test_dev_with_bearer_falls_through_to_jwt_path(self, auth_app, monkeypatch):
        # Even on localhost, if Bearer is present we MUST validate JWT
        # rather than auto-grant dev access (proxy environments hit this).
        monkeypatch.setenv('FLASK_ENV', 'development')
        client = auth_app.test_client()
        with patch('backend.auth.validate_token', return_value=None):
            resp = client.get('/api/protected', headers={
                'Authorization': 'Bearer some-bogus-token',
                'Host': 'localhost',
            })
            assert resp.status_code == 401


class TestInitAuthSsoPath:
    def test_clever_session_resolves_user(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        with client.session_transaction() as sess:
            sess['clever_user'] = {
                'clever_id': 'cl-1',
                'email': 'clever@school.edu',
                'district': 'd-1',
            }
        with patch('backend.auth.resolve_clever_user_id', return_value='sb-uuid-cl'):
            resp = client.get('/api/protected')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['user_id'] == 'sb-uuid-cl'
        assert body['email'] == 'clever@school.edu'
        assert body['auth_source'] == 'clever'

    def test_classlink_session_resolves_user(self, auth_app, monkeypatch):
        # The tenant-scoped GUID is stored as `user_id` in the session at
        # callback time (Task 3 refactor). auth.py reads it verbatim —
        # no resolver call needed.
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        with client.session_transaction() as sess:
            sess['classlink_user'] = {
                'user_id': 'classlink:t-1:cl-link-1',
                'classlink_id': 'cl-link-1',
                'email': 'cl@school.edu',
                'tenant_id': 't-1',
            }
        resp = client.get('/api/protected')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['user_id'] == 'classlink:t-1:cl-link-1'
        assert body['auth_source'] == 'classlink'


class TestInitAuthBearerPath:
    def test_non_api_path_passes_without_auth(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        resp = client.get('/static-page')
        assert resp.status_code == 200

    def test_public_api_path_passes_without_auth(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        # Add a public route INSIDE the test app's PUBLIC_EXACT for this test
        # by registering /api/status which is already on the public exact list.
        @auth_app.route('/api/status')
        def status():
            return {'status': 'ok'}, 200
        client = auth_app.test_client()
        resp = client.get('/api/status')
        assert resp.status_code == 200

    def test_missing_bearer_returns_401(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        resp = client.get('/api/protected')
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Authentication required'

    def test_invalid_token_returns_401(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        with patch('backend.auth.validate_token', return_value=None):
            resp = client.get('/api/protected', headers={
                'Authorization': 'Bearer bogus.token.here',
            })
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Invalid or expired token'

    def test_valid_approved_user_passes(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        payload = {
            'sub': 'user-good',
            'email': 'good@x.com',
            'user_metadata': {'approved': True},
        }
        with patch('backend.auth.validate_token', return_value=payload):
            resp = client.get('/api/protected', headers={
                'Authorization': 'Bearer good.token.here',
            })
        assert resp.status_code == 200
        assert resp.get_json()['user_id'] == 'user-good'

    def test_unapproved_user_returns_403_not_approved(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        payload = {
            'sub': 'user-pending',
            'email': 'pending@x.com',
            'user_metadata': {'approved': False},
        }
        with patch('backend.auth.validate_token', return_value=payload), \
             patch('backend.auth._get_supabase', return_value=None):
            resp = client.get('/api/protected', headers={
                'Authorization': 'Bearer pending.token.here',
            })
        assert resp.status_code == 403
        body = resp.get_json()
        assert body['code'] == 'NOT_APPROVED'

    def test_unapproved_jwt_but_supabase_admin_says_approved_passes(self, auth_app, monkeypatch):
        # Stale JWT scenario: JWT says not approved, but Supabase
        # admin API says yes (approved after token issuance). We
        # honor the fresh truth.
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        payload = {
            'sub': 'user-approved-stale',
            'email': 's@x.com',
            'user_metadata': {'approved': False},
        }
        # Mock the Supabase admin response
        mock_user = MagicMock()
        mock_user.user_metadata = {'approved': True}
        mock_res = MagicMock()
        mock_res.user = mock_user
        mock_sb = MagicMock()
        mock_sb.auth.admin.get_user_by_id.return_value = mock_res

        with patch('backend.auth.validate_token', return_value=payload), \
             patch('backend.auth._get_supabase', return_value=mock_sb):
            resp = client.get('/api/protected', headers={
                'Authorization': 'Bearer stale.token.here',
            })
        assert resp.status_code == 200

    def test_approval_status_endpoint_skips_approval_gate(self, auth_app, monkeypatch):
        # /api/auth/approval-status itself MUST work for unapproved users
        # — that's literally how they discover their pending status.
        monkeypatch.setenv('FLASK_ENV', 'production')
        client = auth_app.test_client()
        payload = {
            'sub': 'user-pending',
            'email': 'p@x.com',
            'user_metadata': {'approved': False},
        }
        with patch('backend.auth.validate_token', return_value=payload):
            resp = client.get('/api/auth/approval-status', headers={
                'Authorization': 'Bearer pending.token.here',
            })
        # Path matches the early-skip branch — should be 200 even
        # without approval.
        assert resp.status_code == 200

    def test_request_id_set_on_g(self, auth_app, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'development')
        # Capture g.request_id via a probe route
        captured = {}

        @auth_app.route('/api/probe-req-id')
        def probe():
            captured['rid'] = getattr(g, 'request_id', None)
            return {'rid': captured['rid']}, 200

        client = auth_app.test_client()
        resp = client.get('/api/probe-req-id', headers={
            'Host': 'localhost',
            'X-Test-Teacher-Id': 't',
        })
        assert resp.status_code == 200
        rid = resp.get_json()['rid']
        # uuid4()[:8] format — 8 hex chars
        assert rid is not None and len(rid) == 8
