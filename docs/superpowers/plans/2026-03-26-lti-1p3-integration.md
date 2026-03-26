# LTI 1.3 + AGS Grade Passback Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LTI 1.3 Tool Provider support so Graider can be launched from any LMS (Canvas, Schoology, Google Classroom) with SSO, and grades pass back automatically to the LMS gradebook via Assignment & Grade Services (AGS).

**Architecture:** New `backend/lti.py` module for LTI 1.3 OIDC login + JWT validation + AGS client. New `backend/routes/lti_routes.py` for OIDC initiation, launch callback, JWKS endpoint, and AGS grade sync. LTI platform registration stored in Supabase via `backend/storage.py`. Settings > Classroom gets an LTI configuration panel. Grade passback triggered automatically after grading completes.

**Tech Stack:** Flask/Python backend, PyJWT + cryptography (already installed) for RS256 JWT signing/verification, RSA key pair generation for tool JWKS, Supabase for platform registration persistence, React frontend (inline styles).

**Spec:** Based on [LTI 1.3 Core Specification](https://www.imsglobal.org/spec/lti/v1p3) and [LTI Advantage AGS](https://www.imsglobal.org/spec/lti-ags/v2p0).

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/lti.py` | CREATE | LTI 1.3 core: RSA key management, OIDC login initiation, JWT launch validation, AGS grade passback client |
| `backend/routes/lti_routes.py` | CREATE | `/api/lti/*` endpoints: OIDC login, launch callback, JWKS, platform registration, grade sync |
| `backend/routes/__init__.py` | MODIFY | Register `lti_bp` blueprint |
| `backend/auth.py` | MODIFY | Add LTI launch endpoints to `PUBLIC_PREFIXES` |
| `frontend/src/services/api.js` | MODIFY | Add LTI API functions |
| `frontend/src/tabs/SettingsTab.jsx` | MODIFY | Add LTI platform registration panel to Classroom sub-tab |
| `tests/test_lti.py` | CREATE | Unit tests for LTI core (JWT, OIDC, AGS) |
| `tests/test_lti_routes.py` | CREATE | Route-level tests (auth, launch, grade passback) |

---

## Task 1: LTI 1.3 Core Module

**Files:**
- Create: `backend/lti.py`
- Create: `tests/test_lti.py`

- [ ] **Step 1: Create `backend/lti.py` with RSA key management**

```python
"""
LTI 1.3 Tool Provider for Graider.
Handles RSA key management, OIDC login initiation, JWT launch validation,
and AGS (Assignment & Grade Services) grade passback.

References:
- LTI 1.3 Core: https://www.imsglobal.org/spec/lti/v1p3
- LTI AGS: https://www.imsglobal.org/spec/lti-ags/v2p0
- Security Framework: https://www.imsglobal.org/spec/security/v1p0
"""
import json
import logging
import os
import time
import uuid

import jwt
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# RSA key storage directory
LTI_KEY_DIR = os.path.expanduser("~/.graider_lti")


def _ensure_key_dir():
    os.makedirs(LTI_KEY_DIR, mode=0o700, exist_ok=True)


def get_or_create_rsa_keypair():
    """Load or generate the tool's RSA key pair for JWT signing.

    Returns:
        tuple: (private_key_pem: bytes, public_key_pem: bytes, kid: str)
    """
    _ensure_key_dir()
    private_path = os.path.join(LTI_KEY_DIR, "private.pem")
    public_path = os.path.join(LTI_KEY_DIR, "public.pem")
    kid_path = os.path.join(LTI_KEY_DIR, "kid.txt")

    if os.path.exists(private_path) and os.path.exists(public_path) and os.path.exists(kid_path):
        with open(private_path, "rb") as f:
            private_pem = f.read()
        with open(public_path, "rb") as f:
            public_pem = f.read()
        with open(kid_path, "r") as f:
            kid = f.read().strip()
        return private_pem, public_pem, kid

    # Generate new 2048-bit RSA key pair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    kid = str(uuid.uuid4())

    with open(private_path, "wb") as f:
        f.write(private_pem)
    os.chmod(private_path, 0o600)
    with open(public_path, "wb") as f:
        f.write(public_pem)
    with open(kid_path, "w") as f:
        f.write(kid)

    logger.info("Generated new LTI RSA key pair (kid=%s)", kid)
    return private_pem, public_pem, kid


def get_jwks():
    """Return the tool's public key as a JWKS document.

    This is served at /api/lti/jwks so platforms can verify tool-signed JWTs.
    """
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    import base64

    _, public_pem, kid = get_or_create_rsa_keypair()
    public_key = serialization.load_pem_public_key(public_pem)
    numbers = public_key.public_numbers()

    def _int_to_base64url(n, length=None):
        b = n.to_bytes(length or ((n.bit_length() + 7) // 8), byteorder="big")
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

    return {
        "keys": [{
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "kid": kid,
            "n": _int_to_base64url(numbers.n, 256),
            "e": _int_to_base64url(numbers.e, 3),
        }]
    }
```

- [ ] **Step 2: Add OIDC login initiation to `backend/lti.py`**

Append to `backend/lti.py`:

```python
def build_oidc_login_response(params, platform_config, tool_url):
    """Build the OIDC authentication response for LTI 1.3 login initiation.

    The platform sends a login initiation request. We respond by redirecting
    the user to the platform's authorization endpoint with our OIDC params.

    Args:
        params: dict with keys from the platform's login initiation:
            - iss: Platform issuer
            - login_hint: Opaque user identifier from platform
            - target_link_uri: Where to redirect after auth
            - lti_message_hint: (optional) Opaque platform hint
            - lti_deployment_id: (optional) Deployment identifier
            - client_id: (optional) Client ID if multiple registrations
        platform_config: dict with platform registration:
            - auth_login_url: Platform's OIDC authorization endpoint
            - client_id: Tool's client ID on this platform
        tool_url: Base URL of Graider (e.g., "https://app.graider.live")

    Returns:
        str: Redirect URL to platform's authorization endpoint
    """
    state = str(uuid.uuid4())
    nonce = str(uuid.uuid4())

    auth_params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "client_id": platform_config["client_id"],
        "redirect_uri": tool_url + "/api/lti/launch",
        "login_hint": params.get("login_hint", ""),
        "state": state,
        "nonce": nonce,
        "prompt": "none",
    }

    if params.get("lti_message_hint"):
        auth_params["lti_message_hint"] = params["lti_message_hint"]

    from urllib.parse import urlencode
    redirect_url = platform_config["auth_login_url"] + "?" + urlencode(auth_params)

    return redirect_url, state, nonce
```

- [ ] **Step 3: Add JWT launch validation to `backend/lti.py`**

Append to `backend/lti.py`:

```python
def validate_launch_jwt(id_token, platform_config):
    """Validate the LTI 1.3 launch JWT (id_token) from the platform.

    Args:
        id_token: The JWT string from the platform's form_post
        platform_config: dict with:
            - issuer: Platform issuer URL
            - client_id: Tool's client ID
            - jwks_url: Platform's JWKS endpoint for signature verification

    Returns:
        dict: Decoded JWT claims if valid

    Raises:
        ValueError: If token is invalid
    """
    try:
        # Fetch platform's public keys
        jwks_client = PyJWKClient(platform_config["jwks_url"])
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=platform_config["client_id"],
            issuer=platform_config["issuer"],
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Launch token expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid launch token: {e}")

    # Validate required LTI claims
    msg_type = claims.get("https://purl.imsglobal.org/spec/lti/claim/message_type")
    if msg_type != "LtiResourceLinkRequest":
        raise ValueError(f"Unexpected message_type: {msg_type}")

    version = claims.get("https://purl.imsglobal.org/spec/lti/claim/version")
    if version != "1.3.0":
        raise ValueError(f"Unsupported LTI version: {version}")

    deployment_id = claims.get("https://purl.imsglobal.org/spec/lti/claim/deployment_id")
    if not deployment_id:
        raise ValueError("Missing deployment_id claim")

    return claims


def extract_launch_data(claims):
    """Extract user info, roles, and context from validated LTI claims.

    Args:
        claims: Decoded JWT claims from validate_launch_jwt()

    Returns:
        dict with keys: user_id, name, email, roles, context_id, context_title,
                        resource_link_id, resource_link_title, is_instructor,
                        ags_endpoint, ags_lineitems_url, ags_lineitem_url
    """
    roles = claims.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
    context = claims.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
    resource_link = claims.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {})

    # AGS endpoint (grade passback)
    ags = claims.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint", {})

    # Check if user is an instructor
    instructor_roles = [
        "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
        "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Instructor",
        "http://purl.imsglobal.org/vocab/lis/v2/membership#ContentDeveloper",
    ]
    is_instructor = any(r in roles for r in instructor_roles)

    return {
        "user_id": claims.get("sub", ""),
        "name": claims.get("name", ""),
        "email": claims.get("email", ""),
        "given_name": claims.get("given_name", ""),
        "family_name": claims.get("family_name", ""),
        "roles": roles,
        "is_instructor": is_instructor,
        "context_id": context.get("id", ""),
        "context_title": context.get("title", ""),
        "resource_link_id": resource_link.get("id", ""),
        "resource_link_title": resource_link.get("title", ""),
        "ags_endpoint": ags.get("lineitems", ""),
        "ags_lineitems_url": ags.get("lineitems", ""),
        "ags_lineitem_url": ags.get("lineitem", ""),
        "ags_scopes": ags.get("scope", []),
        "deployment_id": claims.get("https://purl.imsglobal.org/spec/lti/claim/deployment_id", ""),
        "platform_issuer": claims.get("iss", ""),
    }
```

- [ ] **Step 4: Add AGS grade passback client to `backend/lti.py`**

Append to `backend/lti.py`:

```python
class AGSClient:
    """LTI Advantage Assignment & Grade Services client.

    Sends grades back to the LMS gradebook. Uses OAuth 2.0 client_credentials
    with a tool-signed JWT assertion (RFC 7523) for authentication.
    """

    def __init__(self, platform_config, ags_endpoint):
        """
        Args:
            platform_config: dict with:
                - token_url: Platform's OAuth token endpoint
                - client_id: Tool's client ID
                - issuer: Platform issuer
            ags_endpoint: AGS lineitems URL from launch claims
        """
        self.platform_config = platform_config
        self.ags_endpoint = ags_endpoint
        self._access_token = None
        self._token_expires = 0

    def _get_access_token(self):
        """Get OAuth 2.0 access token using client_credentials + JWT assertion."""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        private_pem, _, kid = get_or_create_rsa_keypair()

        now = int(time.time())
        assertion_claims = {
            "iss": self.platform_config["client_id"],
            "sub": self.platform_config["client_id"],
            "aud": self.platform_config["token_url"],
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        }

        assertion = jwt.encode(
            assertion_claims,
            private_pem,
            algorithm="RS256",
            headers={"kid": kid},
        )

        resp = httpx.post(
            self.platform_config["token_url"],
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
                "scope": "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem "
                         "https://purl.imsglobal.org/spec/lti-ags/scope/score",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        resp.raise_for_status()
        body = resp.json()
        self._access_token = body["access_token"]
        self._token_expires = time.time() + body.get("expires_in", 3600) - 60
        return self._access_token

    def _auth_headers(self):
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def create_lineitem(self, label, max_score, resource_link_id=None, tag=None):
        """Create a grade column (lineitem) in the LMS gradebook.

        Args:
            label: Display name in gradebook (e.g., "US History Ch5 Quiz")
            max_score: Maximum possible score
            resource_link_id: Link to the LTI resource (optional)
            tag: Category tag (optional)

        Returns:
            dict: Created lineitem with 'id' URL
        """
        payload = {
            "scoreMaximum": max_score,
            "label": label,
            "tag": tag or "graider",
        }
        if resource_link_id:
            payload["resourceLinkId"] = resource_link_id

        resp = httpx.post(
            self.ags_endpoint,
            json=payload,
            headers={
                **self._auth_headers(),
                "Content-Type": "application/vnd.ims.lis.v2.lineitem+json",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def post_score(self, lineitem_url, user_id, score, max_score, comment=None):
        """Post a student's score to a lineitem.

        Args:
            lineitem_url: The lineitem 'id' URL
            user_id: LTI user sub (from launch claims)
            score: Points earned
            max_score: Maximum possible points
            comment: Optional feedback comment

        Returns:
            bool: True if score posted successfully
        """
        scores_url = lineitem_url.rstrip("/") + "/scores"
        payload = {
            "userId": user_id,
            "scoreGiven": score,
            "scoreMaximum": max_score,
            "activityProgress": "Completed",
            "gradingProgress": "FullyGraded",
            "timestamp": _iso_now(),
        }
        if comment:
            payload["comment"] = comment

        resp = httpx.post(
            scores_url,
            json=payload,
            headers={
                **self._auth_headers(),
                "Content-Type": "application/vnd.ims.lis.v2.score+json",
            },
            timeout=15.0,
        )
        if resp.status_code in (200, 201, 204):
            logger.info("AGS: posted score %s/%s for user %s", score, max_score, user_id)
            return True
        logger.warning("AGS: failed to post score (%d): %s", resp.status_code, resp.text[:200])
        return False


def _iso_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ── Platform registration helpers ────────────────────────────────────────

def get_platform_config(platform_issuer, teacher_id=None):
    """Load platform registration from storage.

    Args:
        platform_issuer: The platform's issuer URL
        teacher_id: Teacher ID (for per-teacher registrations)

    Returns:
        dict or None
    """
    try:
        from backend.storage import load
        # Try per-teacher config first
        if teacher_id:
            config = load(f"lti_platform:{platform_issuer}", teacher_id)
            if config:
                return config
        # Fall back to system-wide config
        config = load(f"lti_platform:{platform_issuer}", "system")
        return config
    except Exception:
        return None


def save_platform_config(platform_issuer, config, teacher_id=None):
    """Save platform registration to storage.

    Args:
        platform_issuer: Platform issuer URL (used as key)
        config: dict with: issuer, client_id, auth_login_url, auth_token_url, jwks_url, deployment_id
        teacher_id: Teacher ID (for per-teacher registrations)
    """
    from backend.storage import save
    target = teacher_id or "system"
    save(f"lti_platform:{platform_issuer}", config, target)


def list_platform_configs(teacher_id=None):
    """List all registered LTI platforms.

    Returns:
        list of platform config dicts
    """
    try:
        from backend.storage import list_keys, load
        target = teacher_id or "system"
        keys = list_keys("lti_platform:", target)
        platforms = []
        for key in keys:
            config = load(key, target)
            if config and isinstance(config, dict):
                platforms.append(config)
        return platforms
    except Exception:
        return []


def delete_platform_config(platform_issuer, teacher_id=None):
    """Delete a platform registration."""
    from backend.storage import save
    target = teacher_id or "system"
    save(f"lti_platform:{platform_issuer}", None, target)
```

- [ ] **Step 5: Create `tests/test_lti.py`**

```python
"""Unit tests for LTI 1.3 core module."""
import json
import os
import tempfile
import time
import pytest
import jwt as pyjwt
from unittest.mock import patch, MagicMock


class TestRSAKeyManagement:
    def test_get_or_create_generates_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.lti.LTI_KEY_DIR", tmpdir):
                from backend.lti import get_or_create_rsa_keypair
                private_pem, public_pem, kid = get_or_create_rsa_keypair()
                assert private_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
                assert public_pem.startswith(b"-----BEGIN PUBLIC KEY-----")
                assert len(kid) > 0

    def test_get_or_create_returns_same_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.lti.LTI_KEY_DIR", tmpdir):
                from backend.lti import get_or_create_rsa_keypair
                first = get_or_create_rsa_keypair()
                second = get_or_create_rsa_keypair()
                assert first[0] == second[0]  # Same private key
                assert first[2] == second[2]  # Same kid

    def test_jwks_returns_valid_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.lti.LTI_KEY_DIR", tmpdir):
                from backend.lti import get_jwks
                jwks = get_jwks()
                assert "keys" in jwks
                assert len(jwks["keys"]) == 1
                key = jwks["keys"][0]
                assert key["kty"] == "RSA"
                assert key["alg"] == "RS256"
                assert key["use"] == "sig"
                assert "kid" in key
                assert "n" in key
                assert "e" in key


class TestOIDCLogin:
    def test_build_oidc_login_response(self):
        from backend.lti import build_oidc_login_response
        params = {
            "iss": "https://canvas.example.com",
            "login_hint": "user-123",
            "target_link_uri": "https://app.graider.live/api/lti/launch",
            "lti_message_hint": "hint-abc",
        }
        platform_config = {
            "auth_login_url": "https://canvas.example.com/api/lti/authorize_redirect",
            "client_id": "graider-tool-id",
        }
        redirect_url, state, nonce = build_oidc_login_response(
            params, platform_config, "https://app.graider.live"
        )
        assert "canvas.example.com" in redirect_url
        assert "client_id=graider-tool-id" in redirect_url
        assert "response_type=id_token" in redirect_url
        assert "scope=openid" in redirect_url
        assert f"state={state}" in redirect_url
        assert f"nonce={nonce}" in redirect_url
        assert "lti_message_hint=hint-abc" in redirect_url


class TestLaunchValidation:
    def test_extract_launch_data_instructor(self):
        from backend.lti import extract_launch_data
        claims = {
            "sub": "user-456",
            "name": "Jane Teacher",
            "email": "jane@school.edu",
            "given_name": "Jane",
            "family_name": "Teacher",
            "iss": "https://canvas.example.com",
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
            ],
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "course-789",
                "title": "US History Period 3",
            },
            "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
                "id": "link-001",
                "title": "Chapter 5 Quiz",
            },
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "deploy-1",
            "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                "lineitems": "https://canvas.example.com/api/lti/courses/789/line_items",
                "lineitem": "https://canvas.example.com/api/lti/courses/789/line_items/42",
                "scope": [
                    "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                    "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                ],
            },
        }
        data = extract_launch_data(claims)
        assert data["user_id"] == "user-456"
        assert data["name"] == "Jane Teacher"
        assert data["email"] == "jane@school.edu"
        assert data["is_instructor"] is True
        assert data["context_id"] == "course-789"
        assert data["context_title"] == "US History Period 3"
        assert data["resource_link_id"] == "link-001"
        assert "line_items" in data["ags_endpoint"]

    def test_extract_launch_data_student(self):
        from backend.lti import extract_launch_data
        claims = {
            "sub": "stu-111",
            "name": "Bob Student",
            "email": "bob@school.edu",
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
            ],
            "https://purl.imsglobal.org/spec/lti/claim/context": {"id": "c1", "title": "Math"},
            "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "r1"},
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "d1",
        }
        data = extract_launch_data(claims)
        assert data["is_instructor"] is False
        assert data["user_id"] == "stu-111"


class TestAGSClient:
    def test_post_score_payload(self):
        from backend.lti import AGSClient
        client = AGSClient(
            platform_config={
                "token_url": "https://canvas.example.com/login/oauth2/token",
                "client_id": "graider-tool-id",
                "issuer": "https://canvas.example.com",
            },
            ags_endpoint="https://canvas.example.com/api/lti/courses/1/line_items",
        )
        # Mock the token request and score post
        with patch.object(client, "_get_access_token", return_value="mock-token"):
            with patch("backend.lti.httpx.post") as mock_post:
                mock_post.return_value = MagicMock(status_code=200)
                result = client.post_score(
                    lineitem_url="https://canvas.example.com/api/lti/courses/1/line_items/42",
                    user_id="user-456",
                    score=85,
                    max_score=100,
                    comment="Good work!",
                )
                assert result is True
                call_args = mock_post.call_args
                payload = call_args.kwargs.get("json") or call_args[1].get("json")
                assert payload["userId"] == "user-456"
                assert payload["scoreGiven"] == 85
                assert payload["scoreMaximum"] == 100
                assert payload["activityProgress"] == "Completed"
                assert payload["gradingProgress"] == "FullyGraded"
                assert payload["comment"] == "Good work!"
```

- [ ] **Step 6: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_lti.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/lti.py tests/test_lti.py
git commit -m "feat: add LTI 1.3 core module with OIDC, JWT validation, and AGS client"
```

---

## Task 2: LTI Routes

**Files:**
- Create: `backend/routes/lti_routes.py`
- Create: `tests/test_lti_routes.py`
- Modify: `backend/routes/__init__.py`
- Modify: `backend/auth.py`

- [ ] **Step 1: Create `backend/routes/lti_routes.py`**

```python
"""
LTI 1.3 Tool Provider routes for Graider.

Endpoints:
- GET  /api/lti/jwks              — Tool's public JWKS (platform verifies tool JWTs)
- POST /api/lti/login             — OIDC login initiation (platform → tool)
- POST /api/lti/launch            — Launch callback (platform → tool, form_post with id_token)
- GET  /api/lti/config            — List registered platforms (teacher auth)
- POST /api/lti/config            — Register a platform (teacher auth)
- DELETE /api/lti/config          — Delete a platform registration (teacher auth)
- POST /api/lti/sync-grades       — Manual grade sync to LMS (teacher auth)
"""
import logging
import os

from flask import Blueprint, request, jsonify, redirect, session, g

from backend.lti import (
    get_jwks,
    build_oidc_login_response,
    validate_launch_jwt,
    extract_launch_data,
    get_platform_config,
    save_platform_config,
    list_platform_configs,
    delete_platform_config,
    AGSClient,
)
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

logger = logging.getLogger(__name__)

lti_bp = Blueprint("lti", __name__)


def _get_tool_url():
    """Get the tool's base URL from env or request."""
    return os.getenv("LTI_TOOL_URL", request.host_url.rstrip("/"))


# ── Public endpoints (called by LMS platforms) ───────────────────────────

@lti_bp.route("/api/lti/jwks", methods=["GET"])
def jwks_endpoint():
    """Serve the tool's public JWKS for platform verification."""
    return jsonify(get_jwks())


@lti_bp.route("/api/lti/login", methods=["GET", "POST"])
def oidc_login():
    """Handle OIDC third-party login initiation from the platform.

    The platform redirects here with: iss, login_hint, target_link_uri,
    lti_message_hint, client_id. We redirect to the platform's auth endpoint.
    """
    params = {}
    if request.method == "POST":
        params = request.form.to_dict()
    else:
        params = request.args.to_dict()

    issuer = params.get("iss", "")
    client_id = params.get("client_id")

    if not issuer:
        return jsonify({"error": "Missing iss parameter"}), 400

    # Look up platform registration
    platform_config = get_platform_config(issuer)
    if not platform_config:
        logger.warning("LTI login from unregistered platform: %s", issuer)
        return jsonify({"error": "Platform not registered"}), 403

    # If client_id provided, verify it matches
    if client_id and client_id != platform_config.get("client_id"):
        return jsonify({"error": "client_id mismatch"}), 403

    tool_url = _get_tool_url()
    redirect_url, state, nonce = build_oidc_login_response(params, platform_config, tool_url)

    # Store state and nonce in session for validation on callback
    session["lti_state"] = state
    session["lti_nonce"] = nonce
    session["lti_issuer"] = issuer

    return redirect(redirect_url)


@lti_bp.route("/api/lti/launch", methods=["POST"])
def launch_callback():
    """Handle the LTI 1.3 launch callback (form_post with id_token).

    The platform posts the signed JWT here after OIDC auth completes.
    We validate the JWT, extract user/context data, and redirect to Graider.
    """
    id_token = request.form.get("id_token", "")
    state = request.form.get("state", "")

    if not id_token:
        return jsonify({"error": "Missing id_token"}), 400

    # Validate state matches what we stored in OIDC login
    expected_state = session.pop("lti_state", None)
    expected_nonce = session.pop("lti_nonce", None)
    issuer = session.pop("lti_issuer", None)

    if not expected_state or state != expected_state:
        return jsonify({"error": "Invalid state parameter"}), 403

    # Look up platform config
    platform_config = get_platform_config(issuer)
    if not platform_config:
        return jsonify({"error": "Platform not registered"}), 403

    # Validate the JWT
    try:
        claims = validate_launch_jwt(id_token, platform_config)
    except ValueError as e:
        logger.warning("LTI launch validation failed: %s", str(e))
        return jsonify({"error": str(e)}), 403

    # Validate nonce
    if claims.get("nonce") != expected_nonce:
        return jsonify({"error": "Invalid nonce"}), 403

    # Extract launch data
    launch_data = extract_launch_data(claims)

    # Store launch context in session for grade passback later
    session["lti_launch"] = {
        "user_id": launch_data["user_id"],
        "name": launch_data["name"],
        "email": launch_data["email"],
        "is_instructor": launch_data["is_instructor"],
        "context_id": launch_data["context_id"],
        "context_title": launch_data["context_title"],
        "resource_link_id": launch_data["resource_link_id"],
        "ags_endpoint": launch_data["ags_endpoint"],
        "ags_lineitem_url": launch_data["ags_lineitem_url"],
        "ags_scopes": launch_data["ags_scopes"],
        "platform_issuer": launch_data["platform_issuer"],
        "deployment_id": launch_data["deployment_id"],
    }

    from backend.utils.audit import audit_log
    audit_log("LTI_LAUNCH", f"LTI launch: {launch_data['name']} from {issuer}",
              teacher_id=launch_data["user_id"] if launch_data["is_instructor"] else None)

    # Redirect to Graider app
    if launch_data["is_instructor"]:
        return redirect("/")
    else:
        return redirect("/student")


# ── Teacher-authenticated endpoints ──────────────────────────────────────

@lti_bp.route("/api/lti/config", methods=["GET"])
@require_teacher
@handle_route_errors
def get_platforms():
    """List registered LTI platforms."""
    platforms = list_platform_configs(g.teacher_id)
    # Never expose client secrets
    safe = []
    for p in platforms:
        safe.append({
            "issuer": p.get("issuer", ""),
            "client_id": p.get("client_id", ""),
            "auth_login_url": p.get("auth_login_url", ""),
            "auth_token_url": p.get("auth_token_url", ""),
            "jwks_url": p.get("jwks_url", ""),
            "deployment_id": p.get("deployment_id", ""),
            "name": p.get("name", ""),
        })
    tool_url = _get_tool_url()
    return jsonify({
        "platforms": safe,
        "tool_config": {
            "oidc_login_url": tool_url + "/api/lti/login",
            "launch_url": tool_url + "/api/lti/launch",
            "jwks_url": tool_url + "/api/lti/jwks",
            "redirect_uri": tool_url + "/api/lti/launch",
        },
    })


@lti_bp.route("/api/lti/config", methods=["POST"])
@require_teacher
@handle_route_errors
def register_platform():
    """Register an LTI platform (LMS)."""
    data = request.json or {}
    issuer = data.get("issuer", "").strip()
    client_id = data.get("client_id", "").strip()
    auth_login_url = data.get("auth_login_url", "").strip()
    auth_token_url = data.get("auth_token_url", "").strip()
    jwks_url = data.get("jwks_url", "").strip()
    deployment_id = data.get("deployment_id", "").strip()
    name = data.get("name", "").strip()

    if not issuer or not client_id or not auth_login_url or not auth_token_url or not jwks_url:
        return jsonify({"error": "issuer, client_id, auth_login_url, auth_token_url, and jwks_url are required"}), 400

    config = {
        "issuer": issuer,
        "client_id": client_id,
        "auth_login_url": auth_login_url,
        "auth_token_url": auth_token_url,
        "token_url": auth_token_url,  # Alias for AGS client
        "jwks_url": jwks_url,
        "deployment_id": deployment_id,
        "name": name or issuer,
    }
    save_platform_config(issuer, config, g.teacher_id)

    from backend.utils.audit import audit_log
    audit_log("LTI_PLATFORM_REGISTERED", f"Registered LTI platform: {name or issuer}",
              teacher_id=g.teacher_id)

    return jsonify({"status": "registered"})


@lti_bp.route("/api/lti/config", methods=["DELETE"])
@require_teacher
@handle_route_errors
def unregister_platform():
    """Delete a platform registration."""
    data = request.json or {}
    issuer = data.get("issuer", "").strip()
    if not issuer:
        return jsonify({"error": "issuer is required"}), 400

    delete_platform_config(issuer, g.teacher_id)

    from backend.utils.audit import audit_log
    audit_log("LTI_PLATFORM_DELETED", f"Deleted LTI platform: {issuer}",
              teacher_id=g.teacher_id)

    return jsonify({"status": "deleted"})


@lti_bp.route("/api/lti/sync-grades", methods=["POST"])
@require_teacher
@handle_route_errors
def sync_grades():
    """Manually sync grades to the LMS via AGS.

    Body: {
        "platform_issuer": "https://canvas.example.com",
        "lineitem_url": "https://...",  (optional — creates new if omitted)
        "label": "US History Ch5 Quiz",
        "max_score": 100,
        "scores": [
            {"user_id": "lti-sub-1", "score": 85, "comment": "Good work!"},
            {"user_id": "lti-sub-2", "score": 92, "comment": "Excellent!"}
        ]
    }
    """
    data = request.json or {}
    platform_issuer = data.get("platform_issuer", "")
    lineitem_url = data.get("lineitem_url")
    label = data.get("label", "Graider Assessment")
    max_score = data.get("max_score", 100)
    scores = data.get("scores", [])

    if not platform_issuer or not scores:
        return jsonify({"error": "platform_issuer and scores are required"}), 400

    platform_config = get_platform_config(platform_issuer, g.teacher_id)
    if not platform_config:
        return jsonify({"error": "Platform not registered"}), 404

    ags = AGSClient(platform_config, platform_config.get("ags_endpoint", ""))

    # Create lineitem if not provided
    if not lineitem_url:
        try:
            lineitem = ags.create_lineitem(label, max_score)
            lineitem_url = lineitem.get("id", "")
        except Exception as e:
            return jsonify({"error": f"Failed to create lineitem: {e}"}), 502

    # Post each score
    posted = 0
    errors = []
    for s in scores:
        try:
            ok = ags.post_score(lineitem_url, s["user_id"], s["score"], max_score, s.get("comment"))
            if ok:
                posted += 1
            else:
                errors.append(f"{s['user_id']}: post failed")
        except Exception as e:
            errors.append(f"{s['user_id']}: {str(e)}")

    from backend.utils.audit import audit_log
    audit_log("LTI_GRADE_SYNC", f"Synced {posted}/{len(scores)} grades to {platform_issuer}",
              teacher_id=g.teacher_id)

    return jsonify({"posted": posted, "total": len(scores), "errors": errors})
```

- [ ] **Step 2: Register blueprint in `backend/routes/__init__.py`**

Add after the `oneroster_routes` import:

```python
from .lti_routes import lti_bp
```

Add in `register_routes()`:

```python
app.register_blueprint(lti_bp)
```

Add to `__all__`:

```python
'lti_bp',
```

- [ ] **Step 3: Add LTI public routes to `backend/auth.py`**

In `backend/auth.py`, add to `PUBLIC_PREFIXES` (around line 65-69):

```python
'/api/lti/',               # LTI OIDC login, launch callback, JWKS (platform-initiated)
```

- [ ] **Step 4: Create `tests/test_lti_routes.py`**

```python
"""Route-level tests for LTI 1.3 endpoints."""
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    """Create test Flask app."""
    import sys
    sys.path.insert(0, '.')
    from backend.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestJWKS:
    def test_jwks_endpoint_returns_keys(self, client):
        resp = client.get("/api/lti/jwks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "keys" in data
        assert len(data["keys"]) >= 1
        assert data["keys"][0]["kty"] == "RSA"


class TestOIDCLogin:
    def test_login_without_iss_returns_400(self, client):
        resp = client.get("/api/lti/login")
        assert resp.status_code == 400

    def test_login_with_unregistered_platform_returns_403(self, client):
        resp = client.get("/api/lti/login?iss=https://unknown.example.com&login_hint=user1")
        assert resp.status_code == 403


class TestConfig:
    def test_get_config_requires_auth(self, client):
        resp = client.get("/api/lti/config")
        assert resp.status_code == 401

    def test_get_config_returns_tool_config(self, client):
        resp = client.get("/api/lti/config", headers={"X-Test-Teacher-Id": "test-teacher"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tool_config" in data
        assert "platforms" in data
        assert "oidc_login_url" in data["tool_config"]
        assert "jwks_url" in data["tool_config"]

    def test_register_platform_requires_fields(self, client):
        resp = client.post(
            "/api/lti/config",
            headers={"X-Test-Teacher-Id": "test-teacher", "Content-Type": "application/json"},
            data=json.dumps({"issuer": "https://canvas.example.com"}),
        )
        assert resp.status_code == 400
```

- [ ] **Step 5: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_lti_routes.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/routes/lti_routes.py backend/routes/__init__.py backend/auth.py tests/test_lti_routes.py
git commit -m "feat: add LTI 1.3 routes (OIDC login, launch, JWKS, platform config, grade sync)"
```

---

## Task 3: Frontend — LTI Configuration Panel

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/tabs/SettingsTab.jsx`

- [ ] **Step 1: Add API functions in `frontend/src/services/api.js`**

Add after the OneRoster API functions:

```javascript
// LTI 1.3 Integration
export async function getLTIConfig() {
  return fetchApi('/api/lti/config')
}

export async function registerLTIPlatform(config) {
  return fetchApi('/api/lti/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function deleteLTIPlatform(issuer) {
  return fetchApi('/api/lti/config', {
    method: 'DELETE',
    body: JSON.stringify({ issuer: issuer }),
  })
}

export async function syncLTIGrades(payload) {
  return fetchApi('/api/lti/sync-grades', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
```

Add to the default export object:

```javascript
getLTIConfig,
registerLTIPlatform,
deleteLTIPlatform,
syncLTIGrades,
```

- [ ] **Step 2: Add LTI config panel to `SettingsTab.jsx`**

Find the Classroom sub-tab section (after OneRoster section). Add an LTI 1.3 section.

**State variables to add** (alongside other classroom state):

```javascript
var [ltiPlatforms, setLtiPlatforms] = useState([]);
var [ltiToolConfig, setLtiToolConfig] = useState(null);
var [ltiNewPlatform, setLtiNewPlatform] = useState({
  name: '', issuer: '', client_id: '', auth_login_url: '',
  auth_token_url: '', jwks_url: '', deployment_id: '',
});
var [ltiSaving, setLtiSaving] = useState(false);
var [ltiShowForm, setLtiShowForm] = useState(false);
```

**On mount** (in the existing classroom useEffect):

```javascript
api.getLTIConfig().then(function(data) {
  setLtiPlatforms(data.platforms || []);
  setLtiToolConfig(data.tool_config || null);
}).catch(function() {});
```

**LTI section JSX** — placed below OneRoster section, inside `settingsTab === "classroom"`:

The section should contain:
1. **Header**: "LTI 1.3 Integration" with a shield icon
2. **Tool Configuration display** — read-only box showing OIDC Login URL, Launch URL, JWKS URL, Redirect URI (these are what the teacher enters into their LMS's developer key setup). Include a "Copy" button for each URL.
3. **Registered Platforms list** — table of registered platforms with Name, Issuer, Client ID, Delete button
4. **"Add Platform" button** — toggles a form with fields:
   - Platform Name — text input (e.g., "Canvas", "Schoology")
   - Issuer URL — text input, required (e.g., "https://canvas.instructure.com")
   - Client ID — text input, required
   - Authorization URL — text input, required
   - Token URL — text input, required
   - JWKS URL — text input, required
   - Deployment ID — text input, optional
5. **LMS preset buttons** — "Canvas", "Schoology", "Google Classroom" that pre-fill the auth/token/JWKS URLs with known defaults:
   - Canvas: auth=`{issuer}/api/lti/authorize_redirect`, token=`{issuer}/login/oauth2/token`, jwks=`{issuer}/api/lti/security/jwks`
   - Schoology: auth=`https://lti.schoology.com/lti/authorize`, token=`https://lti.schoology.com/lti/token`, jwks=`https://lti.schoology.com/lti/.well-known/jwks`

**CRITICAL CODE STYLE RULES:**
- NO template literals (backticks) — use string concatenation
- Use `var` not `const` or `let`
- Use inline styles, follow existing patterns
- Use existing `Icon` component for icons

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.js frontend/src/tabs/SettingsTab.jsx
git commit -m "feat: add LTI 1.3 platform registration UI to Settings > Classroom"
```

---

## Task 4: Environment Variables & Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add LTI env vars to CLAUDE.md**

Find the "Environment Variables" section. After the "OneRoster Integration" subsection, add:

```markdown
### LTI 1.3 Integration
- `LTI_TOOL_URL` — Tool base URL for OIDC/launch callbacks (defaults to request host, set in production to `https://app.graider.live`)
```

- [ ] **Step 2: Add LTI API endpoints to CLAUDE.md**

Find the "API Reference" section. After the "OneRoster Integration" subsection, add:

```markdown
### LTI 1.3 Integration (1EdTech)
- `GET /api/lti/jwks` — Tool's public JWKS (for platform verification)
- `GET,POST /api/lti/login` — OIDC third-party login initiation
- `POST /api/lti/launch` — Launch callback (platform posts id_token)
- `GET /api/lti/config` — List registered LTI platforms
- `POST /api/lti/config` — Register an LTI platform
- `DELETE /api/lti/config` — Delete a platform registration
- `POST /api/lti/sync-grades` — Sync grades to LMS via AGS
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add LTI 1.3 env vars and API endpoints to CLAUDE.md"
```

---

## Task 5: Full Verification

- [ ] **Step 1: Run all backend tests**

Run: `source venv/bin/activate && python -m pytest tests/test_lti.py tests/test_lti_routes.py -v`
Expected: All tests pass

- [ ] **Step 2: Run full backend test suite**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`
Expected: No new failures

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 4: Run full Playwright E2E suite**

Run: `cd frontend && npx playwright test --reporter=dot --workers=1`
Expected: All existing tests pass (no regressions)

---

## Implementation Notes

### LTI 1.3 Flow Summary

1. **Platform registration**: Teacher enters their LMS details in Settings > Classroom > LTI. Graider shows its Tool Configuration URLs (OIDC Login, Launch, JWKS) for the teacher to enter in their LMS developer key setup.

2. **Launch flow**: Student/teacher clicks an LTI link in their LMS → Platform sends OIDC login initiation to `/api/lti/login` → Graider redirects to platform auth → Platform posts signed JWT to `/api/lti/launch` → Graider validates JWT, stores launch context in session, redirects to app.

3. **Grade passback**: After grading completes, teacher can sync grades to LMS via `/api/lti/sync-grades`. The AGS client authenticates using a tool-signed JWT assertion (RFC 7523) and posts scores to the platform's lineitem endpoint.

### Security

- RSA key pair stored in `~/.graider_lti/` with 0600 permissions on private key
- Platform JWKS used to verify incoming launch JWTs (RS256)
- Tool JWKS served at `/api/lti/jwks` for platforms to verify tool-signed JWTs
- OIDC state+nonce validated to prevent CSRF and replay attacks
- Platform secrets never returned in GET config response

### No Database Schema Changes

- Platform registrations stored in existing `teacher_data` table via `backend/storage.py`
- LTI launch context stored in Flask session (cookie-based, encrypted by FLASK_SECRET_KEY)
- No new Supabase tables or columns needed

### Dependencies: No New Packages

- `PyJWT>=2.8.0` — already installed (JWT signing/verification)
- `cryptography>=42.0.0` — already installed (RSA key generation)
- `httpx` — already installed (AGS HTTP client)

### Phase 2 (Future)

- **Deep Linking 2.0** — Content selection from within LMS
- **NRPS** — Roster sync via LTI (alternative to Clever/OneRoster)
- **Automatic grade passback** — Hook into grading thread completion to auto-sync scores
- **QTI Import/Export** — Assessment portability (separate spec, separate project)
