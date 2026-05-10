"""Gap-fill unit tests for backend/lti.py.

Audit MAJOR #4 sprint follow-up to PR #299. Companion to existing
tests/test_lti.py (and test_lti_routes*.py for the routes layer).
Targets the remaining 60 uncovered LOC (75% baseline → ~99%).

Branches covered
* validate_launch_jwt early raises (jwks_uri / client_id / issuer missing)
* validate_launch_jwt pyjwt error variants (Expired / InvalidAudience /
  InvalidIssuer / generic)
* validate_launch_jwt claim validation (message_type / version /
  deployment_id / TOFU recording / allowlist enforcement)
* AGSClient._get_access_token full flow with httpx.post mock
* AGSClient.create_lineitem full flow with httpx.post mock
* Platform config CRUD (get_platform_config, save_platform_config,
  list_platform_configs, delete_platform_config)
* AGS context persistence (save / get / list)
* LTI user mapping CRUD (save_lti_user_mapping, get_lti_user_mappings)
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _make_rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    return priv, pub


# ──────────────────────────────────────────────────────────────────
# validate_launch_jwt — early raises (lines 219, 221, 223)
# ──────────────────────────────────────────────────────────────────


class TestValidateIdTokenEarlyRaises:
    def test_missing_jwks_uri_raises(self):
        from backend.lti import validate_launch_jwt
        with pytest.raises(ValueError, match="jwks_uri"):
            validate_launch_jwt("any-token", {
                "client_id": "ci", "issuer": "iss",
            })

    def test_missing_client_id_raises(self):
        from backend.lti import validate_launch_jwt
        with pytest.raises(ValueError, match="client_id"):
            validate_launch_jwt("any-token", {
                "jwks_uri": "url", "issuer": "iss",
            })

    def test_missing_issuer_raises(self):
        from backend.lti import validate_launch_jwt
        with pytest.raises(ValueError, match="issuer"):
            validate_launch_jwt("any-token", {
                "jwks_uri": "url", "client_id": "ci",
            })


# ──────────────────────────────────────────────────────────────────
# validate_launch_jwt — pyjwt error variants + claim validation
# ──────────────────────────────────────────────────────────────────


def _platform_config():
    return {
        "jwks_uri": "https://platform.example/.well-known/jwks.json",
        "client_id": "test-client",
        "issuer": "https://platform.example",
    }


class TestValidateIdTokenJwtErrors:
    def test_expired_signature_error(self):
        from backend.lti import validate_launch_jwt
        with patch(
            "jwt.PyJWKClient",
        ) as mock_pyjwk_cls, patch(
            "backend.lti.jwt.decode",
            side_effect=pyjwt.ExpiredSignatureError("expired"),
        ):
            mock_pyjwk_cls.return_value.get_signing_key_from_jwt.return_value = (
                MagicMock(key="x")
            )
            with pytest.raises(ValueError, match="expired"):
                validate_launch_jwt("token", _platform_config())

    def test_invalid_audience_error(self):
        from backend.lti import validate_launch_jwt
        with patch(
            "jwt.PyJWKClient",
        ) as mock_pyjwk_cls, patch(
            "backend.lti.jwt.decode",
            side_effect=pyjwt.InvalidAudienceError("aud mismatch"),
        ):
            mock_pyjwk_cls.return_value.get_signing_key_from_jwt.return_value = (
                MagicMock(key="x")
            )
            with pytest.raises(ValueError, match="audience does not match"):
                validate_launch_jwt("token", _platform_config())

    def test_invalid_issuer_error(self):
        from backend.lti import validate_launch_jwt
        with patch(
            "jwt.PyJWKClient",
        ) as mock_pyjwk_cls, patch(
            "backend.lti.jwt.decode",
            side_effect=pyjwt.InvalidIssuerError("iss mismatch"),
        ):
            mock_pyjwk_cls.return_value.get_signing_key_from_jwt.return_value = (
                MagicMock(key="x")
            )
            with pytest.raises(ValueError, match="issuer does not match"):
                validate_launch_jwt("token", _platform_config())

    def test_generic_pyjwt_error(self):
        from backend.lti import validate_launch_jwt
        with patch(
            "jwt.PyJWKClient",
        ) as mock_pyjwk_cls, patch(
            "backend.lti.jwt.decode",
            side_effect=pyjwt.PyJWTError("generic jwt error"),
        ):
            mock_pyjwk_cls.return_value.get_signing_key_from_jwt.return_value = (
                MagicMock(key="x")
            )
            with pytest.raises(ValueError, match="JWT validation failed"):
                validate_launch_jwt("token", _platform_config())


class TestValidateIdTokenClaims:
    def _setup_decode(self, claims):
        # Returns context manager that patches PyJWKClient + jwt.decode
        # to bypass signature verification and return canned claims.
        mock_pyjwk = patch("jwt.PyJWKClient")
        mock_decode = patch("backend.lti.jwt.decode", return_value=claims)
        return mock_pyjwk, mock_decode

    def test_unexpected_message_type(self):
        from backend.lti import validate_launch_jwt
        from backend.lti import (
            _CLAIM_MESSAGE_TYPE, _CLAIM_VERSION, _CLAIM_DEPLOYMENT_ID,
        )
        claims = {
            _CLAIM_MESSAGE_TYPE: "WrongType",
            _CLAIM_VERSION: "1.3.0",
            _CLAIM_DEPLOYMENT_ID: "deploy-1",
        }
        mock_pyjwk, mock_decode = self._setup_decode(claims)
        with mock_pyjwk, mock_decode:
            with pytest.raises(ValueError, match="message_type"):
                validate_launch_jwt("token", _platform_config())

    def test_unexpected_lti_version(self):
        from backend.lti import validate_launch_jwt
        from backend.lti import (
            _CLAIM_MESSAGE_TYPE, _CLAIM_VERSION, _CLAIM_DEPLOYMENT_ID,
        )
        claims = {
            _CLAIM_MESSAGE_TYPE: "LtiResourceLinkRequest",
            _CLAIM_VERSION: "1.2.0",  # wrong version
            _CLAIM_DEPLOYMENT_ID: "deploy-1",
        }
        mock_pyjwk, mock_decode = self._setup_decode(claims)
        with mock_pyjwk, mock_decode:
            with pytest.raises(ValueError, match="LTI version"):
                validate_launch_jwt("token", _platform_config())

    def test_missing_deployment_id_claim(self):
        from backend.lti import validate_launch_jwt
        from backend.lti import (
            _CLAIM_MESSAGE_TYPE, _CLAIM_VERSION,
        )
        claims = {
            _CLAIM_MESSAGE_TYPE: "LtiResourceLinkRequest",
            _CLAIM_VERSION: "1.3.0",
            # missing deployment_id
        }
        mock_pyjwk, mock_decode = self._setup_decode(claims)
        with mock_pyjwk, mock_decode:
            with pytest.raises(ValueError, match="deployment_id"):
                validate_launch_jwt("token", _platform_config())

    def test_tofu_records_first_seen_deployment_id(self):
        # No allowlist + valid deployment_id → record + persist via
        # save_platform_config; accept the launch.
        from backend.lti import validate_launch_jwt
        from backend.lti import (
            _CLAIM_MESSAGE_TYPE, _CLAIM_VERSION, _CLAIM_DEPLOYMENT_ID,
        )
        claims = {
            _CLAIM_MESSAGE_TYPE: "LtiResourceLinkRequest",
            _CLAIM_VERSION: "1.3.0",
            _CLAIM_DEPLOYMENT_ID: "deploy-tofu",
            "iss": "https://platform.example",
        }
        cfg = {**_platform_config(), "_registered_by": "teacher-1"}
        mock_pyjwk, mock_decode = self._setup_decode(claims)
        with mock_pyjwk, mock_decode, patch(
            "backend.lti.save_platform_config",
        ) as save_mock, patch(
            "backend.utils.audit.audit_log",
        ):
            result = validate_launch_jwt("token", cfg)
        assert result == claims
        save_mock.assert_called_once()
        # Saved config has deployment_ids populated with the new one
        saved_cfg = save_mock.call_args.args[1]
        assert saved_cfg["deployment_ids"] == ["deploy-tofu"]

    def test_tofu_falls_back_to_system_teacher_when_no_registered_by(
        self,
    ):
        # _registered_by missing → falls back to _SYSTEM_TEACHER_ID
        from backend.lti import validate_launch_jwt, _SYSTEM_TEACHER_ID
        from backend.lti import (
            _CLAIM_MESSAGE_TYPE, _CLAIM_VERSION, _CLAIM_DEPLOYMENT_ID,
        )
        claims = {
            _CLAIM_MESSAGE_TYPE: "LtiResourceLinkRequest",
            _CLAIM_VERSION: "1.3.0",
            _CLAIM_DEPLOYMENT_ID: "deploy-sys",
            "iss": "https://platform.example",
        }
        # NO _registered_by in cfg
        mock_pyjwk, mock_decode = self._setup_decode(claims)
        with mock_pyjwk, mock_decode, patch(
            "backend.lti.save_platform_config",
        ) as save_mock, patch(
            "backend.utils.audit.audit_log",
        ):
            validate_launch_jwt("token", _platform_config())
        # save called with system teacher_id
        assert save_mock.call_args.args[2] == _SYSTEM_TEACHER_ID

    def test_deployment_id_not_in_allowlist_raises(self):
        from backend.lti import validate_launch_jwt
        from backend.lti import (
            _CLAIM_MESSAGE_TYPE, _CLAIM_VERSION, _CLAIM_DEPLOYMENT_ID,
        )
        claims = {
            _CLAIM_MESSAGE_TYPE: "LtiResourceLinkRequest",
            _CLAIM_VERSION: "1.3.0",
            _CLAIM_DEPLOYMENT_ID: "deploy-attacker",
            "iss": "https://platform.example",
        }
        cfg = {
            **_platform_config(),
            "deployment_ids": ["legit-1", "legit-2"],
        }
        mock_pyjwk, mock_decode = self._setup_decode(claims)
        with mock_pyjwk, mock_decode:
            with pytest.raises(ValueError, match="not in allowlist"):
                validate_launch_jwt("token", cfg)


# ──────────────────────────────────────────────────────────────────
# AGSClient
# ──────────────────────────────────────────────────────────────────


class TestAGSClient:
    def _config(self):
        return {
            "client_id": "test-client",
            "token_url": "https://platform.example/oauth/token",
            "issuer": "https://platform.example",
        }

    def test_get_access_token_full_flow(self):
        from backend.lti import AGSClient

        # get_or_create_rsa_keypair must return a real PEM so jwt.encode
        # doesn't choke on the assertion claims.
        priv, _ = _make_rsa_keypair()
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        token_response = MagicMock()
        token_response.raise_for_status = MagicMock()
        token_response.json.return_value = {"access_token": "tok-xyz"}

        with patch(
            "backend.lti.get_or_create_rsa_keypair",
            return_value=(priv_pem, b"pub-pem", "test-kid"),
        ), patch(
            "backend.lti.httpx.post", return_value=token_response,
        ) as post_mock:
            client = AGSClient(self._config(), "https://x.example/lineitems")
            token = client._get_access_token()

        assert token == "tok-xyz"
        # Subsequent calls cache
        assert client._access_token == "tok-xyz"
        # POST sent with the form-encoded RFC 7523 assertion
        kwargs = post_mock.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "client_credentials"
        assert "client_assertion" in kwargs["data"]

    def test_create_lineitem_uses_cached_token(self):
        from backend.lti import AGSClient
        client = AGSClient(self._config(), "https://x.example/lineitems")
        client._access_token = "tok-cache"

        lineitem_response = MagicMock()
        lineitem_response.raise_for_status = MagicMock()
        lineitem_response.json.return_value = {
            "id": "li-1", "label": "Quiz", "scoreMaximum": 100,
        }

        with patch(
            "backend.lti.httpx.post", return_value=lineitem_response,
        ) as post_mock:
            result = client.create_lineitem(
                "Quiz", 100, "rl-1", tag="optional-tag",
            )

        assert result["id"] == "li-1"
        kwargs = post_mock.call_args.kwargs
        assert kwargs["json"]["scoreMaximum"] == 100
        assert kwargs["json"]["label"] == "Quiz"
        assert kwargs["json"]["resourceLinkId"] == "rl-1"
        assert kwargs["json"]["tag"] == "optional-tag"
        # Bearer token used
        assert kwargs["headers"]["Authorization"] == "Bearer tok-cache"

    def test_create_lineitem_acquires_token_when_unset(self):
        from backend.lti import AGSClient
        client = AGSClient(self._config(), "https://x.example/lineitems")

        priv, _ = _make_rsa_keypair()
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        token_response = MagicMock()
        token_response.raise_for_status = MagicMock()
        token_response.json.return_value = {"access_token": "tok-new"}

        lineitem_response = MagicMock()
        lineitem_response.raise_for_status = MagicMock()
        lineitem_response.json.return_value = {"id": "li-2"}

        with patch(
            "backend.lti.get_or_create_rsa_keypair",
            return_value=(priv_pem, b"pub", "kid"),
        ), patch(
            "backend.lti.httpx.post",
            side_effect=[token_response, lineitem_response],
        ):
            result = client.create_lineitem("Q", 50, "rl-x")

        assert result["id"] == "li-2"
        assert client._access_token == "tok-new"

    def test_create_lineitem_without_tag(self):
        from backend.lti import AGSClient
        client = AGSClient(self._config(), "https://x.example/lineitems")
        client._access_token = "tok-cache"

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": "li-3"}

        with patch(
            "backend.lti.httpx.post", return_value=resp,
        ) as post_mock:
            client.create_lineitem("L", 10, "rl-y")
        # No tag in payload
        kwargs = post_mock.call_args.kwargs
        assert "tag" not in kwargs["json"]


# ──────────────────────────────────────────────────────────────────
# Platform config CRUD
# ──────────────────────────────────────────────────────────────────


class TestPlatformConfigCRUD:
    def test_get_platform_config_teacher_scope_hit(self):
        from backend.lti import get_platform_config
        with patch(
            "backend.storage.load",
            return_value={"client_id": "ci"},
        ) as load_mock:
            result = get_platform_config(
                "https://issuer.example", teacher_id="teacher-1",
            )
        assert result == {"client_id": "ci"}
        # First call: teacher-scoped lookup hit, no fall-through to system
        load_mock.assert_called_once()

    def test_get_platform_config_falls_back_to_system(self):
        from backend.lti import get_platform_config, _SYSTEM_TEACHER_ID
        # First (teacher-scoped) returns None; second (system) returns config
        with patch(
            "backend.storage.load",
            side_effect=[None, {"client_id": "ci-sys"}],
        ) as load_mock:
            result = get_platform_config(
                "https://issuer.example", teacher_id="teacher-1",
            )
        assert result == {"client_id": "ci-sys"}
        assert load_mock.call_count == 2
        # Second call uses system teacher id
        assert load_mock.call_args_list[1].args[1] == _SYSTEM_TEACHER_ID

    def test_get_platform_config_no_teacher_id_uses_system(self):
        from backend.lti import get_platform_config, _SYSTEM_TEACHER_ID
        with patch(
            "backend.storage.load",
            return_value={"x": "y"},
        ) as load_mock:
            get_platform_config("https://issuer.example")
        # Called once, with system teacher id
        load_mock.assert_called_once()
        assert load_mock.call_args.args[1] == _SYSTEM_TEACHER_ID

    def test_save_platform_config_uses_teacher_id(self):
        from backend.lti import save_platform_config
        with patch(
            "backend.storage.save", return_value=True,
        ) as save_mock:
            ok = save_platform_config(
                "https://issuer.example",
                {"client_id": "ci"},
                teacher_id="teacher-1",
            )
        assert ok is True
        assert save_mock.call_args.args[2] == "teacher-1"

    def test_save_platform_config_no_teacher_uses_system(self):
        from backend.lti import save_platform_config, _SYSTEM_TEACHER_ID
        with patch(
            "backend.storage.save", return_value=True,
        ) as save_mock:
            save_platform_config(
                "https://issuer.example",
                {"client_id": "ci"},
            )
        assert save_mock.call_args.args[2] == _SYSTEM_TEACHER_ID

    def test_list_platform_configs(self):
        from backend.lti import list_platform_configs
        with patch(
            "backend.storage.list_keys",
            return_value=["lti_platform:a", "lti_platform:b"],
        ) as list_mock:
            result = list_platform_configs(teacher_id="teacher-1")
        assert result == ["lti_platform:a", "lti_platform:b"]
        list_mock.assert_called_once()
        assert list_mock.call_args.args[1] == "teacher-1"

    def test_list_platform_configs_no_teacher_uses_system(self):
        from backend.lti import list_platform_configs, _SYSTEM_TEACHER_ID
        with patch(
            "backend.storage.list_keys", return_value=[],
        ) as list_mock:
            list_platform_configs()
        assert list_mock.call_args.args[1] == _SYSTEM_TEACHER_ID

    def test_delete_platform_config(self):
        from backend.lti import delete_platform_config
        with patch(
            "backend.storage.delete", return_value=True,
        ) as delete_mock:
            ok = delete_platform_config(
                "https://issuer.example", teacher_id="teacher-1",
            )
        assert ok is True
        assert delete_mock.call_args.args[1] == "teacher-1"

    def test_delete_platform_config_no_teacher_uses_system(self):
        from backend.lti import delete_platform_config, _SYSTEM_TEACHER_ID
        with patch(
            "backend.storage.delete", return_value=True,
        ) as delete_mock:
            delete_platform_config("https://issuer.example")
        assert delete_mock.call_args.args[1] == _SYSTEM_TEACHER_ID


# ──────────────────────────────────────────────────────────────────
# AGS context persistence
# ──────────────────────────────────────────────────────────────────


class TestAGSContext:
    def test_save_ags_context(self):
        from backend.lti import save_ags_context
        with patch(
            "backend.storage.save", return_value=True,
        ) as save_mock:
            ok = save_ags_context(
                "teacher-1", "iss", "ctx-1",
                {"lineitems": "url"},
            )
        assert ok is True
        # Key format: lti_ags:{issuer}:{context_id}
        assert save_mock.call_args.args[0] == "lti_ags:iss:ctx-1"
        assert save_mock.call_args.args[2] == "teacher-1"

    def test_get_ags_context(self):
        from backend.lti import get_ags_context
        with patch(
            "backend.storage.load",
            return_value={"lineitems": "url"},
        ) as load_mock:
            result = get_ags_context("teacher-1", "iss", "ctx-1")
        assert result == {"lineitems": "url"}
        assert load_mock.call_args.args[0] == "lti_ags:iss:ctx-1"

    def test_list_ags_contexts(self):
        from backend.lti import list_ags_contexts
        with patch(
            "backend.storage.list_keys",
            return_value=["lti_ags:iss:ctx-1", "lti_ags:iss:ctx-2"],
        ) as list_mock:
            result = list_ags_contexts("teacher-1")
        assert result == ["lti_ags:iss:ctx-1", "lti_ags:iss:ctx-2"]
        # prefix arg
        assert list_mock.call_args.args[0] == "lti_ags:"
        assert list_mock.call_args.args[1] == "teacher-1"


# ──────────────────────────────────────────────────────────────────
# LTI user mapping
# ──────────────────────────────────────────────────────────────────


class TestLTIUserMapping:
    def test_save_lti_user_mapping(self):
        from backend.lti import save_lti_user_mapping
        with patch(
            "backend.storage.save", return_value=True,
        ) as save_mock:
            ok = save_lti_user_mapping(
                "teacher-1", "iss", "ctx-1", "lti-sub-A",
                "Jane Doe", email="jane@x.com",
            )
        assert ok is True
        # Key format: lti_user:{issuer}:{context_id}:{lti_sub}
        assert save_mock.call_args.args[0] == "lti_user:iss:ctx-1:lti-sub-A"
        payload = save_mock.call_args.args[1]
        assert payload["student_name"] == "Jane Doe"
        assert payload["email"] == "jane@x.com"
        assert payload["lti_sub"] == "lti-sub-A"

    def test_save_lti_user_mapping_no_email(self):
        from backend.lti import save_lti_user_mapping
        with patch(
            "backend.storage.save", return_value=True,
        ) as save_mock:
            save_lti_user_mapping(
                "teacher-1", "iss", "ctx-1", "lti-sub-B", "John Doe",
            )
        payload = save_mock.call_args.args[1]
        assert payload["email"] is None

    def test_get_lti_user_mappings(self):
        from backend.lti import get_lti_user_mappings
        keys = [
            "lti_user:iss:ctx-1:sub-A",
            "lti_user:iss:ctx-1:sub-B",
            "lti_user:iss:ctx-1:sub-MISSING",
        ]
        loads = {
            "lti_user:iss:ctx-1:sub-A": {
                "lti_sub": "sub-A", "student_name": "A",
            },
            "lti_user:iss:ctx-1:sub-B": {
                "lti_sub": "sub-B", "student_name": "B",
            },
            "lti_user:iss:ctx-1:sub-MISSING": None,  # storage.load → None
        }
        with patch(
            "backend.storage.list_keys", return_value=keys,
        ), patch(
            "backend.storage.load",
            side_effect=lambda k, t: loads.get(k),
        ):
            result = get_lti_user_mappings("teacher-1", "iss", "ctx-1")
        # Only mappings with non-None data are returned
        assert len(result) == 2
        names = [m["student_name"] for m in result]
        assert "A" in names and "B" in names

    def test_get_lti_user_mappings_no_keys(self):
        from backend.lti import get_lti_user_mappings
        with patch(
            "backend.storage.list_keys", return_value=None,
        ):
            result = get_lti_user_mappings("teacher-1", "iss", "ctx-1")
        # `for key in (keys or [])` short-circuits to empty iteration
        assert result == []
