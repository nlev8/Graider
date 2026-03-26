"""
Unit tests for backend/lti.py — LTI 1.3 Core Module.

Tests cover:
  - RSA key generation and idempotency
  - JWKS structure
  - OIDC login response building
  - Launch data extraction
  - AGS post_score payload (mocked httpx)
  - match_scores_to_lti_users (name/email matching, case-insensitive, unmatched)
"""

import base64
import os
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_lti_dir(tmp_path, monkeypatch):
    """Redirect LTI key storage to a temp directory for each test."""
    lti_dir = str(tmp_path / "graider_lti")
    monkeypatch.setattr("backend.lti.LTI_KEY_DIR", lti_dir)
    monkeypatch.setattr("backend.lti.LTI_DIR", lti_dir)
    yield lti_dir


# ══════════════════════════════════════════════════════════════
# RSA KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════

class TestRSAKeyManagement:

    def test_generates_valid_pem_on_first_call(self, isolated_lti_dir):
        from backend.lti import get_or_create_rsa_keypair
        private_pem, public_pem, kid = get_or_create_rsa_keypair()

        assert isinstance(private_pem, bytes)
        assert isinstance(public_pem, bytes)
        assert isinstance(kid, str)
        assert private_pem.startswith(b"-----BEGIN RSA PRIVATE KEY-----")
        assert public_pem.startswith(b"-----BEGIN PUBLIC KEY-----")
        assert len(kid) > 0

    def test_returns_same_keys_on_second_call(self, isolated_lti_dir):
        from backend.lti import get_or_create_rsa_keypair
        priv1, pub1, kid1 = get_or_create_rsa_keypair()
        priv2, pub2, kid2 = get_or_create_rsa_keypair()

        assert priv1 == priv2
        assert pub1 == pub2
        assert kid1 == kid2

    def test_private_key_file_is_created(self, isolated_lti_dir):
        from backend.lti import get_or_create_rsa_keypair
        get_or_create_rsa_keypair()
        private_path = os.path.join(isolated_lti_dir, "private.pem")
        assert os.path.exists(private_path)

    def test_private_key_chmod_600(self, isolated_lti_dir):
        from backend.lti import get_or_create_rsa_keypair
        get_or_create_rsa_keypair()
        private_path = os.path.join(isolated_lti_dir, "private.pem")
        mode = oct(os.stat(private_path).st_mode)
        assert mode.endswith("600"), f"Expected 600 permissions, got {mode}"

    def test_kid_is_uuid(self, isolated_lti_dir):
        from backend.lti import get_or_create_rsa_keypair
        _, _, kid = get_or_create_rsa_keypair()
        # Should be parseable as UUID (no exception)
        parsed = uuid.UUID(kid)
        assert str(parsed) == kid


# ══════════════════════════════════════════════════════════════
# JWKS STRUCTURE
# ══════════════════════════════════════════════════════════════

class TestJWKS:

    def test_jwks_has_keys_array(self, isolated_lti_dir):
        from backend.lti import get_jwks
        jwks = get_jwks()
        assert "keys" in jwks
        assert isinstance(jwks["keys"], list)
        assert len(jwks["keys"]) == 1

    def test_jwks_key_has_required_fields(self, isolated_lti_dir):
        from backend.lti import get_jwks
        key = get_jwks()["keys"][0]
        assert key["kty"] == "RSA"
        assert key["alg"] == "RS256"
        assert key["use"] == "sig"
        assert "kid" in key
        assert "n" in key
        assert "e" in key

    def test_jwks_n_and_e_are_base64url(self, isolated_lti_dir):
        from backend.lti import get_jwks
        key = get_jwks()["keys"][0]
        # Base64url strings should decode without error (padding may be absent)
        for field in ("n", "e"):
            val = key[field]
            # Add padding if needed
            padded = val + "=" * (-len(val) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            assert len(decoded) > 0, f"Field {field} decoded to empty bytes"

    def test_jwks_kid_matches_keypair_kid(self, isolated_lti_dir):
        from backend.lti import get_jwks, get_or_create_rsa_keypair
        _, _, kid = get_or_create_rsa_keypair()
        jwks_kid = get_jwks()["keys"][0]["kid"]
        assert jwks_kid == kid


# ══════════════════════════════════════════════════════════════
# OIDC LOGIN RESPONSE
# ══════════════════════════════════════════════════════════════

class TestOIDCLoginResponse:

    def _make_params(self, **kwargs):
        base = {
            "login_hint": "user123",
            "iss": "https://canvas.example.com",
            "client_id": "12345",
        }
        base.update(kwargs)
        return base

    def _make_platform_config(self, **kwargs):
        base = {
            "client_id": "12345",
            "auth_endpoint": "https://canvas.example.com/api/lti/authorize_redirect",
            "issuer": "https://canvas.example.com",
        }
        base.update(kwargs)
        return base

    def test_returns_tuple_of_three(self):
        from backend.lti import build_oidc_login_response
        result = build_oidc_login_response(
            self._make_params(),
            self._make_platform_config(),
            "https://app.graider.live",
        )
        assert len(result) == 3
        redirect_url, state, nonce = result
        assert isinstance(redirect_url, str)
        assert isinstance(state, str)
        assert isinstance(nonce, str)

    def test_redirect_url_contains_auth_endpoint(self):
        from backend.lti import build_oidc_login_response
        redirect_url, _, _ = build_oidc_login_response(
            self._make_params(),
            self._make_platform_config(),
            "https://app.graider.live",
        )
        assert redirect_url.startswith("https://canvas.example.com/api/lti/authorize_redirect")

    def test_redirect_url_has_required_params(self):
        from backend.lti import build_oidc_login_response
        from urllib.parse import urlparse, parse_qs
        redirect_url, state, nonce = build_oidc_login_response(
            self._make_params(),
            self._make_platform_config(),
            "https://app.graider.live",
        )
        parsed = urlparse(redirect_url)
        qs = parse_qs(parsed.query)

        assert qs["scope"] == ["openid"]
        assert qs["response_type"] == ["id_token"]
        assert qs["response_mode"] == ["form_post"]
        assert qs["client_id"] == ["12345"]
        assert qs["redirect_uri"] == ["https://app.graider.live/api/lti/launch"]
        assert qs["login_hint"] == ["user123"]
        assert qs["state"] == [state]
        assert qs["nonce"] == [nonce]
        assert qs["prompt"] == ["none"]

    def test_includes_lti_message_hint_when_present(self):
        from backend.lti import build_oidc_login_response
        from urllib.parse import urlparse, parse_qs
        params = self._make_params(lti_message_hint="hint_value_123")
        redirect_url, _, _ = build_oidc_login_response(
            params,
            self._make_platform_config(),
            "https://app.graider.live",
        )
        qs = parse_qs(urlparse(redirect_url).query)
        assert qs["lti_message_hint"] == ["hint_value_123"]

    def test_omits_lti_message_hint_when_absent(self):
        from backend.lti import build_oidc_login_response
        from urllib.parse import urlparse, parse_qs
        redirect_url, _, _ = build_oidc_login_response(
            self._make_params(),
            self._make_platform_config(),
            "https://app.graider.live",
        )
        qs = parse_qs(urlparse(redirect_url).query)
        assert "lti_message_hint" not in qs

    def test_state_and_nonce_are_unique(self):
        from backend.lti import build_oidc_login_response
        _, state1, nonce1 = build_oidc_login_response(
            self._make_params(), self._make_platform_config(), "https://app.graider.live"
        )
        _, state2, nonce2 = build_oidc_login_response(
            self._make_params(), self._make_platform_config(), "https://app.graider.live"
        )
        assert state1 != state2
        assert nonce1 != nonce2


# ══════════════════════════════════════════════════════════════
# LAUNCH DATA EXTRACTION
# ══════════════════════════════════════════════════════════════

class TestExtractLaunchData:

    def _base_claims(self):
        return {
            "sub": "lti-sub-abc123",
            "name": "Jane Smith",
            "email": "jane@school.edu",
            "given_name": "Jane",
            "family_name": "Smith",
            "iss": "https://canvas.example.com",
            "https://purl.imsglobal.org/spec/lti/claim/roles": [],
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "ctx-001",
                "title": "Biology 101",
            },
            "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
                "id": "rl-001",
                "title": "Chapter 3 Quiz",
            },
            "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                "lineitems": "https://canvas.example.com/api/lti/courses/123/line_items",
                "scores": "https://canvas.example.com/api/lti/courses/123/scores",
                "scope": [
                    "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                    "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                ],
            },
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "deploy-456",
        }

    def test_extracts_basic_user_fields(self):
        from backend.lti import extract_launch_data
        data = extract_launch_data(self._base_claims())
        assert data["user_id"] == "lti-sub-abc123"
        assert data["name"] == "Jane Smith"
        assert data["email"] == "jane@school.edu"
        assert data["given_name"] == "Jane"
        assert data["family_name"] == "Smith"

    def test_extracts_context_and_resource_link(self):
        from backend.lti import extract_launch_data
        data = extract_launch_data(self._base_claims())
        assert data["context_id"] == "ctx-001"
        assert data["context_title"] == "Biology 101"
        assert data["resource_link_id"] == "rl-001"
        assert data["resource_link_title"] == "Chapter 3 Quiz"

    def test_extracts_ags_endpoint(self):
        from backend.lti import extract_launch_data
        data = extract_launch_data(self._base_claims())
        assert "canvas.example.com" in data["ags_endpoint"]
        assert data["ags_lineitems_url"] == data["ags_endpoint"]

    def test_extracts_deployment_id_and_issuer(self):
        from backend.lti import extract_launch_data
        data = extract_launch_data(self._base_claims())
        assert data["deployment_id"] == "deploy-456"
        assert data["platform_issuer"] == "https://canvas.example.com"

    def test_instructor_role_detected_full_urn(self):
        from backend.lti import extract_launch_data
        claims = self._base_claims()
        claims["https://purl.imsglobal.org/spec/lti/claim/roles"] = [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
        ]
        data = extract_launch_data(claims)
        assert data["is_instructor"] is True

    def test_content_developer_role_detected(self):
        from backend.lti import extract_launch_data
        claims = self._base_claims()
        claims["https://purl.imsglobal.org/spec/lti/claim/roles"] = [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#ContentDeveloper",
        ]
        data = extract_launch_data(claims)
        assert data["is_instructor"] is True

    def test_student_role_is_not_instructor(self):
        from backend.lti import extract_launch_data
        claims = self._base_claims()
        claims["https://purl.imsglobal.org/spec/lti/claim/roles"] = [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
        ]
        data = extract_launch_data(claims)
        assert data["is_instructor"] is False

    def test_empty_roles_not_instructor(self):
        from backend.lti import extract_launch_data
        data = extract_launch_data(self._base_claims())
        assert data["is_instructor"] is False

    def test_short_form_instructor_role_detected(self):
        from backend.lti import extract_launch_data
        claims = self._base_claims()
        claims["https://purl.imsglobal.org/spec/lti/claim/roles"] = ["Instructor"]
        data = extract_launch_data(claims)
        assert data["is_instructor"] is True


# ══════════════════════════════════════════════════════════════
# AGS CLIENT — post_score
# ══════════════════════════════════════════════════════════════

class TestAGSPostScore:

    def _make_ags_client(self, isolated_lti_dir):
        from backend.lti import AGSClient
        platform_config = {
            "client_id": "tool-client-123",
            "issuer": "https://canvas.example.com",
            "token_url": "https://canvas.example.com/login/oauth2/token",
        }
        client = AGSClient(platform_config, "https://canvas.example.com/api/lti/courses/1/line_items")
        client._access_token = "mock-access-token"
        return client

    def test_post_score_sends_correct_payload(self, isolated_lti_dir):
        from backend.lti import AGSClient

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client = self._make_ags_client(isolated_lti_dir)
            result = client.post_score(
                lineitem_url="https://canvas.example.com/api/lti/courses/1/line_items/42",
                user_id="lti-user-sub",
                score=85.0,
                max_score=100.0,
                comment="Great work!",
            )

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args

        # Verify URL includes /scores suffix
        url_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs.kwargs.get("url", call_kwargs[0][0])
        # Get first positional arg
        assert "/scores" in call_kwargs[0][0]

        # Verify payload structure
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
        assert payload["userId"] == "lti-user-sub"
        assert payload["scoreGiven"] == 85.0
        assert payload["scoreMaximum"] == 100.0
        assert payload["activityProgress"] == "Completed"
        assert payload["gradingProgress"] == "FullyGraded"
        assert "timestamp" in payload
        assert payload["comment"] == "Great work!"

    def test_post_score_without_comment(self, isolated_lti_dir):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client = self._make_ags_client(isolated_lti_dir)
            result = client.post_score(
                lineitem_url="https://canvas.example.com/api/lti/courses/1/line_items/42",
                user_id="lti-user-sub",
                score=90.0,
                max_score=100.0,
            )

        assert result is True
        payload = mock_post.call_args[1]["json"]
        assert "comment" not in payload

    def test_post_score_uses_correct_content_type(self, isolated_lti_dir):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client = self._make_ags_client(isolated_lti_dir)
            client.post_score(
                lineitem_url="https://canvas.example.com/api/lti/courses/1/line_items/42",
                user_id="lti-user-sub",
                score=75.0,
                max_score=100.0,
            )

        headers = mock_post.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/vnd.ims.lis.v2.score+json"
        assert headers["Authorization"] == "Bearer mock-access-token"

    def test_post_score_returns_false_on_http_error(self, isolated_lti_dir):
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.post", return_value=mock_response):
            client = self._make_ags_client(isolated_lti_dir)
            result = client.post_score(
                lineitem_url="https://canvas.example.com/api/lti/courses/1/line_items/42",
                user_id="lti-user-sub",
                score=50.0,
                max_score=100.0,
            )

        assert result is False

    def test_post_score_appends_scores_to_lineitem_url(self, isolated_lti_dir):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client = self._make_ags_client(isolated_lti_dir)
            client.post_score(
                lineitem_url="https://canvas.example.com/api/lti/courses/1/line_items/42",
                user_id="u1",
                score=10.0,
                max_score=10.0,
            )

        called_url = mock_post.call_args[0][0]
        assert called_url == "https://canvas.example.com/api/lti/courses/1/line_items/42/scores"

    def test_post_score_strips_trailing_slash_before_appending(self, isolated_lti_dir):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client = self._make_ags_client(isolated_lti_dir)
            client.post_score(
                lineitem_url="https://canvas.example.com/api/lti/line_items/42/",
                user_id="u1",
                score=10.0,
                max_score=10.0,
            )

        called_url = mock_post.call_args[0][0]
        assert called_url == "https://canvas.example.com/api/lti/line_items/42/scores"


# ══════════════════════════════════════════════════════════════
# MATCH SCORES TO LTI USERS
# ══════════════════════════════════════════════════════════════

class TestMatchScoresToLtiUsers:

    def _make_mappings(self):
        return [
            {"lti_sub": "sub-001", "student_name": "Alice Johnson", "email": "alice@school.edu"},
            {"lti_sub": "sub-002", "student_name": "Bob Smith", "email": "bob@school.edu"},
            {"lti_sub": "sub-003", "student_name": "Carlos Rivera", "email": "carlos@school.edu"},
        ]

    def test_matches_by_name_exact(self):
        from backend.lti import match_scores_to_lti_users
        scores = [{"student_name": "Alice Johnson", "score": 90}]
        matched, unmatched = match_scores_to_lti_users(scores, self._make_mappings())

        assert len(matched) == 1
        assert matched[0]["lti_sub"] == "sub-001"
        assert matched[0]["score"] == 90
        assert unmatched == []

    def test_matches_case_insensitive(self):
        from backend.lti import match_scores_to_lti_users
        scores = [
            {"student_name": "alice johnson", "score": 85},
            {"student_name": "BOB SMITH", "score": 92},
        ]
        matched, unmatched = match_scores_to_lti_users(scores, self._make_mappings())

        assert len(matched) == 2
        subs = {m["lti_sub"] for m in matched}
        assert subs == {"sub-001", "sub-002"}
        assert unmatched == []

    def test_matches_by_email_when_name_fails(self):
        from backend.lti import match_scores_to_lti_users
        scores = [{"student_name": "C. Rivera", "email": "carlos@school.edu", "score": 78}]
        matched, unmatched = match_scores_to_lti_users(scores, self._make_mappings())

        assert len(matched) == 1
        assert matched[0]["lti_sub"] == "sub-003"
        assert unmatched == []

    def test_unmatched_reported_correctly(self):
        from backend.lti import match_scores_to_lti_users
        scores = [
            {"student_name": "Alice Johnson", "score": 90},
            {"student_name": "Unknown Student", "score": 70},
        ]
        matched, unmatched = match_scores_to_lti_users(scores, self._make_mappings())

        assert len(matched) == 1
        assert len(unmatched) == 1
        assert "Unknown Student" in unmatched

    def test_all_unmatched_when_no_mappings(self):
        from backend.lti import match_scores_to_lti_users
        scores = [
            {"student_name": "Alice Johnson", "score": 90},
            {"student_name": "Bob Smith", "score": 80},
        ]
        matched, unmatched = match_scores_to_lti_users(scores, [])

        assert matched == []
        assert len(unmatched) == 2

    def test_preserves_all_score_fields(self):
        from backend.lti import match_scores_to_lti_users
        scores = [{"student_name": "Alice Johnson", "score": 95, "feedback": "Excellent", "max_score": 100}]
        matched, _ = match_scores_to_lti_users(scores, self._make_mappings())

        assert matched[0]["score"] == 95
        assert matched[0]["feedback"] == "Excellent"
        assert matched[0]["max_score"] == 100
        assert matched[0]["lti_sub"] == "sub-001"

    def test_email_case_insensitive(self):
        from backend.lti import match_scores_to_lti_users
        scores = [{"student_name": "Nomatch", "email": "ALICE@SCHOOL.EDU", "score": 88}]
        matched, unmatched = match_scores_to_lti_users(scores, self._make_mappings())

        assert len(matched) == 1
        assert matched[0]["lti_sub"] == "sub-001"
        assert unmatched == []

    def test_empty_scores_returns_empty(self):
        from backend.lti import match_scores_to_lti_users
        matched, unmatched = match_scores_to_lti_users([], self._make_mappings())
        assert matched == []
        assert unmatched == []


# ══════════════════════════════════════════════════════════════
# ISO TIMESTAMP HELPER
# ══════════════════════════════════════════════════════════════

class TestIsoNow:

    def test_returns_string(self):
        from backend.lti import _iso_now
        result = _iso_now()
        assert isinstance(result, str)

    def test_contains_utc_marker(self):
        from backend.lti import _iso_now
        result = _iso_now()
        # ISO 8601 UTC timestamp should contain +00:00 or Z
        assert "+00:00" in result or result.endswith("Z")
